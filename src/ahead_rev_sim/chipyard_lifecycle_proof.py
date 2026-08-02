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
    simulator_build_log_path: str | Path,
    raw_log_path: str | Path,
    trace_path: str | Path,
    compiler_version: str,
    readelf_output: str,
    verilator_version: str,
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
    _read_nonempty(
        simulator_build_log_path,
        "Chipyard simulator build log",
    )
    raw_log = _read_nonempty(raw_log_path, "Chipyard raw simulation log")
    trace = _read_nonempty(trace_path, "Chipyard semantic trace")

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
    if not compiler_version.strip() or not verilator_version.strip():
        raise ValueError("compiler and Verilator version evidence are required")
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
            "and receipt trace, and remained bound to the accepted elaboration proof. "
            "The admitted device retains the internal loopback fallback. The proof "
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
