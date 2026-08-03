"""Fail-closed proof admission for Chipyard RV64GC lifecycle execution."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .chipyard_elaboration import CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION
from .chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    CHIPYARD_CONFIG_PACKAGE,
    CHIPYARD_REPOSITORY,
    build_chipyard_manifest,
)
from .mmio_abi import CAPABILITY_BITS, STATUS_BITS, bit_mask, canonical_json
from .physical_constants import PORTABLE_BINDING
from .chipyard_lifecycle_manifest import build_chipyard_lifecycle_manifest
from .chipyard_lifecycle_program import (
    CHIPYARD_LIFECYCLE_EXPECTED_NAME,
    CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION,
    CHIPYARD_LIFECYCLE_SOURCE_NAME,
    CHIPYARD_LIFECYCLE_TRACE_PREFIX,
    CIRCT_ASSET_NAME,
    CIRCT_COMMIT,
    CIRCT_INSTALLER_COMMIT,
    CIRCT_INSTALLER_REPOSITORY,
    CIRCT_INSTALLER_REVISION_NAME,
    CIRCT_RELEASE,
    CIRCT_REPOSITORY,
    CIRCT_TAG_REVISION_NAME,
    CIRCT_VERSION_FILE_NAME,
    COMPILER_SEARCH_DIRS_NAME,
    FIRTOOL_AUTHORITY_REPORT_NAME,
    FIRTOOL_VERSION_NAME,
    FESVR_HEADER_NAME,
    FESVR_HEADERS_MANIFEST_NAME,
    FESVR_HOST_RUNTIME_REPORT_NAME,
    FESVR_LIBRARY_NAME,
    FESVR_STATIC_LOG_NAME,
    HTIF_RUNTIME_REPORT_NAME,
    LIBGLOSS_HTIF_BUILD_LOG_NAME,
    LIBGLOSS_HTIF_COMMIT,
    LIBGLOSS_HTIF_CONFIGURE_LOG_NAME,
    LIBGLOSS_HTIF_INSTALL_LOG_NAME,
    LIBGLOSS_HTIF_LIBRARY_NAME,
    LIBGLOSS_HTIF_LINKER_SCRIPT_NAME,
    LIBGLOSS_HTIF_REPOSITORY,
    LIBGLOSS_HTIF_REVISION_NAME,
    LIBGLOSS_HTIF_SPECS_NAME,
    RISCV_ISA_SIM_BUILD_LOG_NAME,
    RISCV_ISA_SIM_COMMIT,
    RISCV_ISA_SIM_CONFIGURE_LOG_NAME,
    RISCV_ISA_SIM_INSTALL_LOG_NAME,
    RISCV_ISA_SIM_REPOSITORY,
    RISCV_ISA_SIM_REVISION_NAME,
    RISCV_LIBRARY_NAME,
    LIFECYCLE_BLOCKERS,
    LIFECYCLE_STAGES,
    render_chipyard_lifecycle_source,
    render_chipyard_lifecycle_trace,
    sha256_bytes,
)


def _file_record(path: str | Path, label: str) -> dict[str, Any]:
    file_path = Path(path)
    payload = file_path.read_bytes()
    if not payload:
        raise ValueError(f"{label} is empty")
    return {
        "name": file_path.name,
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
    }


def _read_nonempty(path: str | Path, label: str) -> bytes:
    payload = Path(path).read_bytes()
    if not payload:
        raise ValueError(f"{label} is empty")
    return payload


def _first_line(value: str) -> str:
    return value.strip().splitlines()[0] if value.strip() else ""


def parse_chipyard_lifecycle_trace(trace: str) -> dict[str, Any]:
    lines = [line.strip() for line in trace.splitlines() if line.strip()]
    expected_prefixes = [
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}abi=",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}identity=",
        *[
            f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}{stage} "
            for stage in LIFECYCLE_STAGES
        ],
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}result=",
    ]
    positions: dict[str, int] = {}
    for prefix in expected_prefixes:
        matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(
                f"Chipyard lifecycle trace requires one line beginning with {prefix!r}"
            )
        positions[prefix] = matches[0]
    ordered_positions = [positions[prefix] for prefix in expected_prefixes]
    if ordered_positions != sorted(ordered_positions):
        raise ValueError("Chipyard lifecycle trace records are out of order")
    if len(lines) != len(expected_prefixes):
        raise ValueError("Chipyard lifecycle trace contains undeclared records")

    abi_line = lines[0]
    identity_line = lines[1]
    stage_lines = {
        stage: lines[2 + index] for index, stage in enumerate(LIFECYCLE_STAGES)
    }
    result_line = lines[-1]

    status_pattern = re.compile(
        r" status=([0-9a-f]{8}) result=([a-z]+) receipt=([a-z]+)$"
    )
    parsed_stages: dict[str, dict[str, Any]] = {}
    for stage, line in stage_lines.items():
        match = status_pattern.search(line)
        if match is None:
            raise ValueError(f"Chipyard lifecycle stage is malformed: {stage}")
        parsed_stages[stage] = {
            "status": int(match.group(1), 16),
            "result": match.group(2),
            "receipt": match.group(3),
        }

    ready = bit_mask(STATUS_BITS["ready"])
    done = bit_mask(STATUS_BITS["done"])
    refused = bit_mask(STATUS_BITS["refused"])
    receipt_valid = bit_mask(STATUS_BITS["receipt_valid"])
    accepted_status = ready | done | receipt_valid

    expected_caps = bit_mask(CAPABILITY_BITS["exact"]) | bit_mask(
        CAPABILITY_BITS["software_fallback"]
    )
    checks: dict[str, bool] = {
        "portable_binding": f"abi={PORTABLE_BINDING}" in abi_line,
        "target_isa": "isa=rv64gc" in abi_line,
        "identity": "identity=41504859" in identity_line,
        "capability_mask": f"capabilities={expected_caps:08x}" in identity_line,
        "ambiguous_command_refused": (
            parsed_stages["ambiguous"]["status"] == (ready | refused)
            and parsed_stages["ambiguous"]["result"] == "refused"
            and parsed_stages["ambiguous"]["receipt"] == "absent"
        ),
        "reset_completed": parsed_stages["reset"]
        == {"status": accepted_status, "result": "done", "receipt": "valid"},
        "load_completed": parsed_stages["load"]
        == {"status": accepted_status, "result": "done", "receipt": "valid"},
        "evolve_completed": parsed_stages["evolve"]
        == {"status": accepted_status, "result": "done", "receipt": "valid"},
        "read_completed": parsed_stages["read"]
        == {"status": accepted_status, "result": "done", "receipt": "valid"},
        "capture_completed": parsed_stages["capture"]
        == {"status": accepted_status, "result": "done", "receipt": "valid"},
        "result_pass": result_line
        == f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}result=pass",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"Chipyard lifecycle trace semantic checks failed: {failed}")
    return {
        "line_count": len(lines),
        "checks": checks,
        "stages": parsed_stages,
    }


def _validate_sealed_object(
    payload: Mapping[str, Any],
    *,
    seal_key: str,
    label: str,
) -> str:
    claimed = payload.get(seal_key)
    if not isinstance(claimed, str) or not re.fullmatch(r"[0-9a-f]{64}", claimed):
        raise ValueError(f"{label} has no valid {seal_key}")
    unsigned = dict(payload)
    unsigned.pop(seal_key, None)
    observed = sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    if observed != claimed:
        raise ValueError(f"{label} seal mismatch")
    return claimed


def _raw_log_contains_trace(raw_log: bytes, expected_trace: bytes) -> bool:
    raw_text = raw_log.decode("utf-8", errors="replace").replace("\r\n", "\n")
    cursor = 0
    for line in expected_trace.decode("utf-8").splitlines():
        position = raw_text.find(line, cursor)
        if position < 0:
            return False
        cursor = position + len(line)
    return True


def build_chipyard_lifecycle_proof(
    *,
    integration_manifest_path: str | Path,
    lifecycle_manifest_path: str | Path,
    elaboration_proof_path: str | Path,
    source_path: str | Path,
    expected_trace_path: str | Path,
    binary_path: str | Path,
    simulator_path: str | Path,
    firtool_path: str | Path,
    simulator_build_log_path: str | Path,
    raw_log_path: str | Path,
    trace_path: str | Path,
    runtime_dir: str | Path,
    compiler_version: str,
    readelf_output: str,
    verilator_version: str,
    firtool_version: str,
    build_command: str,
    run_command: str,
) -> dict[str, Any]:
    integration_file = Path(integration_manifest_path)
    lifecycle_file = Path(lifecycle_manifest_path)
    elaboration_file = Path(elaboration_proof_path)

    integration = json.loads(integration_file.read_text(encoding="utf-8"))
    lifecycle = json.loads(lifecycle_file.read_text(encoding="utf-8"))
    elaboration = json.loads(elaboration_file.read_text(encoding="utf-8"))
    if not isinstance(integration, dict) or not isinstance(lifecycle, dict):
        raise ValueError("Chipyard manifests must be JSON objects")
    if not isinstance(elaboration, dict):
        raise ValueError("Chipyard elaboration proof must be a JSON object")

    base_address = int(lifecycle.get("chipyard", {}).get("base_address", -1))
    expected_integration = build_chipyard_manifest(base_address=base_address)
    expected_lifecycle = build_chipyard_lifecycle_manifest(
        base_address=base_address
    )
    if integration != expected_integration:
        raise ValueError("Chipyard integration manifest diverges from current authority")
    if lifecycle != expected_lifecycle:
        raise ValueError("Chipyard lifecycle manifest diverges from current authority")
    lifecycle_seal = _validate_sealed_object(
        lifecycle,
        seal_key="manifest_sha256",
        label="Chipyard lifecycle manifest",
    )
    elaboration_seal = _validate_sealed_object(
        elaboration,
        seal_key="proof_sha256",
        label="Chipyard elaboration proof",
    )

    if elaboration.get("schema_version") != CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION:
        raise ValueError("Chipyard elaboration proof schema is not recognized")
    if elaboration.get("qualification", {}).get("accepted") is not True:
        raise ValueError("Chipyard elaboration proof is not accepted")
    if (
        elaboration.get("qualification", {}).get("status")
        != "chipyard_subsystem_elaboration_proved"
    ):
        raise ValueError("Chipyard elaboration proof status is not admitted")
    if elaboration.get("chipyard", {}).get("commit") != CHIPYARD_COMMIT:
        raise ValueError("Chipyard elaboration proof commit mismatch")
    if (
        elaboration.get("chipyard", {}).get("manifest_sha256")
        != integration["manifest_sha256"]
    ):
        raise ValueError("Chipyard elaboration proof manifest mismatch")
    if elaboration.get("target", {}).get("config_class") != CHIPYARD_CONFIG_CLASS:
        raise ValueError("Chipyard elaboration proof config mismatch")
    if elaboration.get("observations", {}).get("loopback_fallback_retained") is not True:
        raise ValueError("Chipyard elaboration proof lost the loopback fallback")

    source = _read_nonempty(source_path, "Chipyard lifecycle source")
    expected_trace = _read_nonempty(
        expected_trace_path,
        "Chipyard lifecycle expected trace",
    )
    _read_nonempty(binary_path, "Chipyard RV64GC binary")
    _read_nonempty(simulator_path, "Chipyard Verilator simulator")
    firtool_binary = _read_nonempty(firtool_path, "Chipyard firtool binary")
    _read_nonempty(
        simulator_build_log_path,
        "Chipyard simulator build log",
    )
    raw_log = _read_nonempty(raw_log_path, "Chipyard raw simulation log")
    trace = _read_nonempty(trace_path, "Chipyard semantic trace")

    runtime_root = Path(runtime_dir)
    revision_path = runtime_root / LIBGLOSS_HTIF_REVISION_NAME
    specs_path = runtime_root / LIBGLOSS_HTIF_SPECS_NAME
    linker_script_path = runtime_root / LIBGLOSS_HTIF_LINKER_SCRIPT_NAME
    runtime_library_path = runtime_root / LIBGLOSS_HTIF_LIBRARY_NAME
    configure_log_path = runtime_root / LIBGLOSS_HTIF_CONFIGURE_LOG_NAME
    runtime_build_log_path = runtime_root / LIBGLOSS_HTIF_BUILD_LOG_NAME
    install_log_path = runtime_root / LIBGLOSS_HTIF_INSTALL_LOG_NAME
    compiler_search_dirs_path = runtime_root / COMPILER_SEARCH_DIRS_NAME
    runtime_report_path = runtime_root / HTIF_RUNTIME_REPORT_NAME
    circt_version_path = runtime_root / CIRCT_VERSION_FILE_NAME
    circt_tag_revision_path = runtime_root / CIRCT_TAG_REVISION_NAME
    circt_installer_revision_path = (
        runtime_root / CIRCT_INSTALLER_REVISION_NAME
    )
    firtool_version_path = runtime_root / FIRTOOL_VERSION_NAME
    firtool_authority_report_path = (
        runtime_root / FIRTOOL_AUTHORITY_REPORT_NAME
    )
    riscv_isa_sim_revision_path = runtime_root / RISCV_ISA_SIM_REVISION_NAME
    riscv_isa_sim_configure_log_path = (
        runtime_root / RISCV_ISA_SIM_CONFIGURE_LOG_NAME
    )
    riscv_isa_sim_build_log_path = (
        runtime_root / RISCV_ISA_SIM_BUILD_LOG_NAME
    )
    riscv_isa_sim_install_log_path = (
        runtime_root / RISCV_ISA_SIM_INSTALL_LOG_NAME
    )
    fesvr_static_log_path = runtime_root / FESVR_STATIC_LOG_NAME
    fesvr_header_path = runtime_root / FESVR_HEADER_NAME
    fesvr_library_path = runtime_root / FESVR_LIBRARY_NAME
    riscv_library_path = runtime_root / RISCV_LIBRARY_NAME
    fesvr_headers_manifest_path = runtime_root / FESVR_HEADERS_MANIFEST_NAME
    fesvr_host_runtime_report_path = (
        runtime_root / FESVR_HOST_RUNTIME_REPORT_NAME
    )

    revision = _read_nonempty(
        revision_path,
        "Chipyard libgloss-htif revision witness",
    ).decode("utf-8")
    specs = _read_nonempty(
        specs_path,
        "Chipyard HTIF nano specs",
    ).decode("utf-8")
    linker_script = _read_nonempty(
        linker_script_path,
        "Chipyard HTIF linker script",
    ).decode("utf-8")
    runtime_library = _read_nonempty(
        runtime_library_path,
        "Chipyard HTIF runtime library",
    )
    _read_nonempty(configure_log_path, "Chipyard libgloss configure log")
    _read_nonempty(runtime_build_log_path, "Chipyard libgloss build log")
    _read_nonempty(install_log_path, "Chipyard libgloss install log")
    compiler_search_dirs = _read_nonempty(
        compiler_search_dirs_path,
        "Chipyard compiler search directories",
    ).decode("utf-8", errors="replace")
    runtime_report = _read_nonempty(
        runtime_report_path,
        "Chipyard HTIF runtime report",
    ).decode("utf-8", errors="replace")
    circt_version_payload = _read_nonempty(
        circt_version_path,
        "Chipyard CIRCT release authority",
    )
    circt_tag_revision = _read_nonempty(
        circt_tag_revision_path,
        "Chipyard CIRCT tag revision witness",
    ).decode("utf-8")
    circt_installer_revision = _read_nonempty(
        circt_installer_revision_path,
        "Chipyard CIRCT installer revision witness",
    ).decode("utf-8")
    sealed_firtool_version = _read_nonempty(
        firtool_version_path,
        "Chipyard firtool version evidence",
    ).decode("utf-8", errors="replace")
    firtool_authority_report = _read_nonempty(
        firtool_authority_report_path,
        "Chipyard firtool authority report",
    ).decode("utf-8", errors="replace")
    riscv_isa_sim_revision = _read_nonempty(
        riscv_isa_sim_revision_path,
        "Chipyard riscv-isa-sim revision witness",
    ).decode("utf-8")
    _read_nonempty(
        riscv_isa_sim_configure_log_path,
        "Chipyard riscv-isa-sim configure log",
    )
    _read_nonempty(
        riscv_isa_sim_build_log_path,
        "Chipyard riscv-isa-sim build log",
    )
    _read_nonempty(
        riscv_isa_sim_install_log_path,
        "Chipyard riscv-isa-sim install log",
    )
    _read_nonempty(
        fesvr_static_log_path,
        "Chipyard FESVR static-library log",
    )
    fesvr_header = _read_nonempty(
        fesvr_header_path,
        "Chipyard FESVR memif header",
    ).decode("utf-8")
    fesvr_library = _read_nonempty(
        fesvr_library_path,
        "Chipyard FESVR static library",
    )
    riscv_library = _read_nonempty(
        riscv_library_path,
        "Chipyard riscv simulator library",
    )
    fesvr_headers_manifest = _read_nonempty(
        fesvr_headers_manifest_path,
        "Chipyard FESVR header manifest",
    ).decode("utf-8", errors="replace")
    fesvr_host_runtime_report = _read_nonempty(
        fesvr_host_runtime_report_path,
        "Chipyard FESVR host-runtime report",
    ).decode("utf-8", errors="replace")

    if revision.strip() != LIBGLOSS_HTIF_COMMIT:
        raise ValueError("Chipyard libgloss-htif revision mismatch")
    required_specs_fragments = (
        "%include <nano.specs>",
        "-lgloss_htif",
        "htif.ld",
        "-static",
    )
    if not all(fragment in specs for fragment in required_specs_fragments):
        raise ValueError("Chipyard HTIF nano specs contract is incomplete")
    required_linker_fragments = (
        'OUTPUT_ARCH ("riscv")',
        "ENTRY (_start)",
        ". = 0x80000000;",
        ".htif",
    )
    if not all(fragment in linker_script for fragment in required_linker_fragments):
        raise ValueError("Chipyard HTIF linker script contract is incomplete")
    if not runtime_library.startswith(b"!<arch>\n"):
        raise ValueError("Chipyard HTIF runtime library is not a static archive")
    if "libraries:" not in compiler_search_dirs:
        raise ValueError("Chipyard compiler search-directory evidence is malformed")
    required_report_fragments = (
        f"libgloss_commit={LIBGLOSS_HTIF_COMMIT}",
        "htif_nano_specs=",
        "htif_linker_script=",
        "htif_runtime_library=",
        sha256_bytes(specs.encode("utf-8")),
        sha256_bytes(linker_script.encode("utf-8")),
        sha256_bytes(runtime_library),
    )
    if not all(fragment in runtime_report for fragment in required_report_fragments):
        raise ValueError("Chipyard HTIF runtime report is incomplete")

    if riscv_isa_sim_revision.strip() != RISCV_ISA_SIM_COMMIT:
        raise ValueError("Chipyard riscv-isa-sim revision mismatch")
    required_fesvr_header_fragments = (
        "#ifndef __MEMIF_H",
        "class chunked_memif_t",
        "class memif_t",
        "virtual void read",
    )
    if not all(fragment in fesvr_header for fragment in required_fesvr_header_fragments):
        raise ValueError("Chipyard FESVR memif header contract is incomplete")
    if not fesvr_library.startswith(b"!<arch>\n"):
        raise ValueError("Chipyard FESVR library is not a static archive")
    if not riscv_library.startswith(b"\x7fELF"):
        raise ValueError("Chipyard riscv simulator library is not identified as ELF")
    if "/include/fesvr/memif.h" not in fesvr_headers_manifest:
        raise ValueError("Chipyard FESVR header manifest is incomplete")
    required_fesvr_report_fragments = (
        f"riscv_isa_sim_repository={RISCV_ISA_SIM_REPOSITORY}",
        f"riscv_isa_sim_commit={RISCV_ISA_SIM_COMMIT}",
        "fesvr_header=",
        "fesvr_library=",
        "riscv_library=",
        sha256_bytes(fesvr_header.encode("utf-8")),
        sha256_bytes(fesvr_library),
        sha256_bytes(riscv_library),
    )
    if not all(
        fragment in fesvr_host_runtime_report
        for fragment in required_fesvr_report_fragments
    ):
        raise ValueError("Chipyard FESVR host-runtime report is incomplete")

    try:
        circt_version = json.loads(circt_version_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Chipyard CIRCT release authority is malformed") from exc
    if circt_version != {"version": CIRCT_RELEASE}:
        raise ValueError("Chipyard CIRCT release authority mismatch")
    if circt_tag_revision.strip() != CIRCT_COMMIT:
        raise ValueError("Chipyard CIRCT tag revision mismatch")
    if circt_installer_revision.strip() != CIRCT_INSTALLER_COMMIT:
        raise ValueError("Chipyard CIRCT installer revision mismatch")
    if Path(firtool_path).name != "firtool":
        raise ValueError("Chipyard firtool path does not identify firtool")
    if not firtool_binary.startswith(b"\x7fELF"):
        raise ValueError("Chipyard firtool binary is not identified as ELF")
    if sealed_firtool_version.strip() != firtool_version.strip():
        raise ValueError("Chipyard firtool version evidence mismatch")
    release_version = CIRCT_RELEASE.removeprefix("firtool-")
    if release_version not in sealed_firtool_version:
        raise ValueError("Chipyard firtool version does not identify the release")
    required_firtool_report_fragments = (
        f"circt_repository={CIRCT_REPOSITORY}",
        f"circt_release={CIRCT_RELEASE}",
        f"circt_commit={CIRCT_COMMIT}",
        f"circt_asset={CIRCT_ASSET_NAME}",
        f"installer_repository={CIRCT_INSTALLER_REPOSITORY}",
        f"installer_commit={CIRCT_INSTALLER_COMMIT}",
        "firtool_source_path=",
        "firtool_sealed_path=",
        sha256_bytes(firtool_binary),
        sha256_bytes(circt_version_payload),
    )
    if not all(
        fragment in firtool_authority_report
        for fragment in required_firtool_report_fragments
    ):
        raise ValueError("Chipyard firtool authority report is incomplete")

    expected_source = render_chipyard_lifecycle_source(
        base_address=base_address
    ).encode("utf-8")
    expected_trace_authority = render_chipyard_lifecycle_trace().encode("utf-8")
    if source != expected_source:
        raise ValueError("Chipyard lifecycle source diverges from generator authority")
    if expected_trace != expected_trace_authority:
        raise ValueError("Chipyard lifecycle expected trace diverges from authority")
    if trace != expected_trace:
        raise ValueError("Chipyard lifecycle trace diverges from accepted trace")
    if not _raw_log_contains_trace(raw_log, expected_trace):
        raise ValueError("Chipyard raw simulation log does not contain the accepted trace")

    source_record = lifecycle["generated_artifacts"][
        CHIPYARD_LIFECYCLE_SOURCE_NAME
    ]
    expected_record = lifecycle["generated_artifacts"][
        CHIPYARD_LIFECYCLE_EXPECTED_NAME
    ]
    if (
        source_record["sha256"] != sha256_bytes(source)
        or source_record["bytes"] != len(source)
    ):
        raise ValueError("Chipyard lifecycle source diverges from its manifest")
    if (
        expected_record["sha256"] != sha256_bytes(expected_trace)
        or expected_record["bytes"] != len(expected_trace)
    ):
        raise ValueError("Chipyard expected trace diverges from its manifest")

    semantic_observations = parse_chipyard_lifecycle_trace(
        trace.decode("utf-8")
    )
    readelf_lower = readelf_output.lower()
    if "class:" not in readelf_lower or "elf64" not in readelf_lower:
        raise ValueError("Chipyard lifecycle binary is not identified as ELF64")
    if "machine:" not in readelf_lower or "risc-v" not in readelf_lower:
        raise ValueError("Chipyard lifecycle binary is not identified as RISC-V")
    if (
        not compiler_version.strip()
        or not verilator_version.strip()
        or not firtool_version.strip()
    ):
        raise ValueError(
            "compiler, Verilator, and firtool version evidence are required"
        )
    if not build_command.strip() or not run_command.strip():
        raise ValueError("Chipyard build and run commands are required")
    if CHIPYARD_CONFIG_CLASS not in Path(simulator_path).name:
        raise ValueError("Chipyard simulator filename does not identify the config")

    proof: dict[str, Any] = {
        "schema_version": CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION,
        "artifact_type": "chipyard_rv64gc_lifecycle_execution_proof",
        "portable_binding": PORTABLE_BINDING,
        "chipyard": {
            "repository": CHIPYARD_REPOSITORY,
            "commit": CHIPYARD_COMMIT,
            "config_package": CHIPYARD_CONFIG_PACKAGE,
            "config_class": CHIPYARD_CONFIG_CLASS,
            "base_address": base_address,
            "entry_api": "testchipip.soc.SubsystemInjectorKey",
            "integration_manifest_sha256": integration["manifest_sha256"],
            "lifecycle_manifest_sha256": lifecycle_seal,
            "elaboration_proof_sha256": elaboration_seal,
        },
        "simulator_runtime": {
            "repository": RISCV_ISA_SIM_REPOSITORY,
            "commit": RISCV_ISA_SIM_COMMIT,
            "header": "fesvr/memif.h",
            "fesvr_library": FESVR_LIBRARY_NAME,
            "riscv_library": RISCV_LIBRARY_NAME,
        },
        "runtime": {
            "repository": LIBGLOSS_HTIF_REPOSITORY,
            "commit": LIBGLOSS_HTIF_COMMIT,
            "specs": LIBGLOSS_HTIF_SPECS_NAME,
            "linker_script": LIBGLOSS_HTIF_LINKER_SCRIPT_NAME,
            "library": LIBGLOSS_HTIF_LIBRARY_NAME,
        },
        "lowering": {
            "repository": CIRCT_REPOSITORY,
            "release": CIRCT_RELEASE,
            "commit": CIRCT_COMMIT,
            "asset": CIRCT_ASSET_NAME,
            "tool": "firtool",
            "version_file": CIRCT_VERSION_FILE_NAME,
            "installer_repository": CIRCT_INSTALLER_REPOSITORY,
            "installer_commit": CIRCT_INSTALLER_COMMIT,
        },
        "target": {
            "isa": "rv64gc",
            "abi": "lp64d",
            "execution_environment": "chipyard-verilator-testharness",
            "loopback_fallback": True,
            "build_command": build_command.strip(),
            "run_command": run_command.strip(),
        },
        "tools": {
            "compiler": _first_line(compiler_version),
            "readelf": _first_line(readelf_output),
            "verilator": _first_line(verilator_version),
            "firtool": _first_line(firtool_version),
        },
        "artifacts": {
            "integration_manifest": _file_record(
                integration_file,
                "Chipyard integration manifest",
            ),
            "lifecycle_manifest": _file_record(
                lifecycle_file,
                "Chipyard lifecycle manifest",
            ),
            "elaboration_proof": _file_record(
                elaboration_file,
                "Chipyard elaboration proof",
            ),
            "riscv_isa_sim_revision": _file_record(
                riscv_isa_sim_revision_path,
                "Chipyard riscv-isa-sim revision witness",
            ),
            "riscv_isa_sim_configure_log": _file_record(
                riscv_isa_sim_configure_log_path,
                "Chipyard riscv-isa-sim configure log",
            ),
            "riscv_isa_sim_build_log": _file_record(
                riscv_isa_sim_build_log_path,
                "Chipyard riscv-isa-sim build log",
            ),
            "riscv_isa_sim_install_log": _file_record(
                riscv_isa_sim_install_log_path,
                "Chipyard riscv-isa-sim install log",
            ),
            "fesvr_static_log": _file_record(
                fesvr_static_log_path,
                "Chipyard FESVR static-library log",
            ),
            "fesvr_header": _file_record(
                fesvr_header_path,
                "Chipyard FESVR memif header",
            ),
            "fesvr_library": _file_record(
                fesvr_library_path,
                "Chipyard FESVR static library",
            ),
            "riscv_library": _file_record(
                riscv_library_path,
                "Chipyard riscv simulator library",
            ),
            "fesvr_headers_manifest": _file_record(
                fesvr_headers_manifest_path,
                "Chipyard FESVR header manifest",
            ),
            "fesvr_host_runtime_report": _file_record(
                fesvr_host_runtime_report_path,
                "Chipyard FESVR host-runtime report",
            ),
            "libgloss_revision": _file_record(
                revision_path,
                "Chipyard libgloss-htif revision witness",
            ),
            "htif_specs": _file_record(
                specs_path,
                "Chipyard HTIF nano specs",
            ),
            "htif_linker_script": _file_record(
                linker_script_path,
                "Chipyard HTIF linker script",
            ),
            "htif_runtime_library": _file_record(
                runtime_library_path,
                "Chipyard HTIF runtime library",
            ),
            "libgloss_configure_log": _file_record(
                configure_log_path,
                "Chipyard libgloss configure log",
            ),
            "libgloss_build_log": _file_record(
                runtime_build_log_path,
                "Chipyard libgloss build log",
            ),
            "libgloss_install_log": _file_record(
                install_log_path,
                "Chipyard libgloss install log",
            ),
            "compiler_search_dirs": _file_record(
                compiler_search_dirs_path,
                "Chipyard compiler search directories",
            ),
            "htif_runtime_report": _file_record(
                runtime_report_path,
                "Chipyard HTIF runtime report",
            ),
            "circt_version_file": _file_record(
                circt_version_path,
                "Chipyard CIRCT release authority",
            ),
            "circt_tag_revision": _file_record(
                circt_tag_revision_path,
                "Chipyard CIRCT tag revision witness",
            ),
            "circt_installer_revision": _file_record(
                circt_installer_revision_path,
                "Chipyard CIRCT installer revision witness",
            ),
            "firtool_version": _file_record(
                firtool_version_path,
                "Chipyard firtool version evidence",
            ),
            "firtool_authority_report": _file_record(
                firtool_authority_report_path,
                "Chipyard firtool authority report",
            ),
            "firtool_binary": _file_record(
                firtool_path,
                "Chipyard firtool binary",
            ),
            "source": _file_record(source_path, "Chipyard lifecycle source"),
            "expected_trace": _file_record(
                expected_trace_path,
                "Chipyard expected trace",
            ),
            "binary": {
                **_file_record(binary_path, "Chipyard RV64GC binary"),
                "elf_class": "ELF64",
                "machine": "RISC-V",
            },
            "simulator": _file_record(
                simulator_path,
                "Chipyard Verilator simulator",
            ),
            "simulator_build_log": _file_record(
                simulator_build_log_path,
                "Chipyard simulator build log",
            ),
            "raw_log": _file_record(
                raw_log_path,
                "Chipyard raw simulation log",
            ),
            "trace": _file_record(
                trace_path,
                "Chipyard semantic trace",
            ),
        },
        "observations": {
            **semantic_observations,
            "accepted_trace_exact": True,
            "raw_trace_embedded": True,
            "elaboration_proof_bound": True,
            "riscv_isa_sim_revision_exact": True,
            "fesvr_host_runtime_bound": True,
            "fesvr_header_contract_checked": True,
            "fesvr_library_archive_checked": True,
            "riscv_library_elf_checked": True,
            "libgloss_revision_exact": True,
            "htif_runtime_bound": True,
            "htif_specs_contract_checked": True,
            "htif_linker_contract_checked": True,
            "htif_library_archive_checked": True,
            "circt_release_exact": True,
            "circt_tag_revision_exact": True,
            "circt_installer_revision_exact": True,
            "firtool_binary_bound": True,
            "loopback_fallback_retained": True,
        },
        "qualification": {
            "status": "chipyard_rv64gc_lifecycle_execution_proved",
            "accepted": True,
            "chipyard_subsystem_claim_allowed": True,
            "chipyard_rtl_simulation_claim_allowed": True,
            "chipyard_rv64gc_lifecycle_claim_allowed": True,
            "external_cartridge_claim_allowed": False,
            "physical_claim_allowed": False,
            "complete_system_advantage_claim_allowed": False,
            "blockers": list(LIFECYCLE_BLOCKERS),
        },
        "claim_boundary": (
            "The proof establishes that an ELF64 RV64GC binary compiled against the "
            "generated lifecycle source executed under the Verilator simulator built "
            "from the exact pinned Chipyard configuration, reached the injected "
            "physical-compute MMIO peripheral, reproduced the accepted refusal, done, "
            "and receipt trace, remained bound to the accepted elaboration proof, "
            "bound the exact pinned riscv-isa-sim revision, FESVR header, FESVR "
            "archive, and riscv host library used to build the simulator, and bound "
            "the exact pinned libgloss-htif revision, specs, linker script, "
            "and static runtime library used to construct the target. It also bound "
            "the exact CIRCT release tag, release commit, asset name, installer "
            "revision, and firtool binary used "
            "to lower the pinned FIRRTL into simulator RTL. The admitted "
            "device retains the internal loopback fallback. The proof "
            "does not establish an external cartridge, FPGA or silicon execution, "
            "physical-substrate work, measured energy, timing, thermal closure, "
            "occupied volume, complete-system EVP advantage, fabrication, or "
            "independent physical acceptance."
        ),
        "control_question": (
            "Can the same content-addressed lifecycle now replace the loopback fallback "
            "with an external cartridge or physical target without changing command, "
            "refusal, terminal-state, receipt, provenance, or fallback semantics?"
        ),
    }
    proof["proof_sha256"] = sha256(
        canonical_json(proof).encode("utf-8")
    ).hexdigest()
    return proof


def write_chipyard_lifecycle_proof(
    output_path: str | Path,
    proof: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        (json.dumps(proof, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return output
