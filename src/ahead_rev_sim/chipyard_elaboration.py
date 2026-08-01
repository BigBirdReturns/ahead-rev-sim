"""Fail-closed proof for pinned Chipyard subsystem elaboration."""

from __future__ import annotations

from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from .chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    CHIPYARD_CONFIG_PACKAGE,
    CHIPYARD_REPOSITORY,
    CHIPYARD_SCALA_INSTALL_PATH,
    CHIPYARD_SOURCE_WITNESSES,
    CHIPYARD_SUBMODULE_WITNESSES,
    ELABORATION_WITNESS_NAME,
    build_chipyard_manifest,
    render_chipyard_scala,
)
from .mmio_abi import canonical_json
from .physical_constants import PORTABLE_BINDING

CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION = (
    "ahead.chipyard-subsystem-elaboration-proof/v0.1"
)
CRITICAL_SUBMODULE_PATHS = (
    "generators/rocket-chip",
    "generators/testchipip",
)


def sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return sha1(header + payload).hexdigest()


def _read_nonempty(path: str | Path, label: str) -> bytes:
    payload = Path(path).read_bytes()
    if not payload:
        raise ValueError(f"{label} is empty")
    return payload


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0] if text.strip() else ""


def parse_submodule_status(status: str) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for raw_line in status.splitlines():
        if not raw_line.strip():
            continue
        prefix = raw_line[0]
        body = raw_line[1:].strip()
        fields = body.split()
        if len(fields) < 2 or not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
            raise ValueError(f"invalid git submodule status line: {raw_line!r}")
        path = fields[1]
        if path in records:
            raise ValueError(f"duplicate submodule status path: {path}")
        records[path] = {
            "commit": fields[0],
            "state": {
                " ": "exact",
                "-": "uninitialized",
                "+": "diverged",
                "U": "conflicted",
            }.get(prefix, "unknown"),
            "prefix": prefix,
        }
    if not records:
        raise ValueError("git submodule status is empty")
    return records


def _validate_required_patterns(
    payload: bytes,
    patterns: list[str],
    *,
    label: str,
) -> None:
    text = payload.decode("utf-8")
    missing = [pattern for pattern in patterns if pattern not in text]
    if missing:
        raise ValueError(f"{label} is missing required API patterns: {missing}")


def validate_chipyard_checkout(
    checkout_root: str | Path,
    manifest_path: str | Path,
    scala_source_path: str | Path,
    *,
    checkout_commit: str,
    submodule_status: str,
) -> dict[str, Any]:
    root = Path(checkout_root).resolve()
    if checkout_commit.strip() != CHIPYARD_COMMIT:
        raise ValueError(
            "Chipyard checkout commit mismatch: "
            f"expected {CHIPYARD_COMMIT}, observed {checkout_commit.strip()}"
        )

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Chipyard integration manifest must be a JSON object")
    base_address = int(manifest.get("base_address", -1))
    expected_manifest = build_chipyard_manifest(base_address=base_address)
    if manifest != expected_manifest:
        raise ValueError("Chipyard integration manifest diverges from current authority")

    expected_source = root / CHIPYARD_SCALA_INSTALL_PATH
    observed_source = Path(scala_source_path).resolve()
    if observed_source != expected_source:
        raise ValueError(
            "Chipyard Scala source is not installed at the declared authority path"
        )
    scala_payload = _read_nonempty(observed_source, "Chipyard Scala source")
    expected_scala = render_chipyard_scala(base_address=base_address).encode("utf-8")
    if scala_payload != expected_scala:
        raise ValueError("installed Chipyard Scala source diverges from generator authority")
    scala_record = manifest["generated_artifacts"]["PhysicalCompute.scala"]
    if (
        sha256_bytes(scala_payload) != scala_record["sha256"]
        or len(scala_payload) != scala_record["bytes"]
    ):
        raise ValueError("installed Chipyard Scala source diverges from its manifest")

    source_witnesses: dict[str, dict[str, Any]] = {}
    for relative, contract in sorted(CHIPYARD_SOURCE_WITNESSES.items()):
        path = root / relative
        payload = _read_nonempty(path, f"Chipyard source witness {relative}")
        observed_blob = git_blob_sha1(payload)
        if observed_blob != contract["blob_sha"]:
            raise ValueError(
                f"Chipyard source witness blob mismatch: {relative}; "
                f"expected {contract['blob_sha']}; observed {observed_blob}"
            )
        _validate_required_patterns(
            payload,
            list(contract["required_patterns"]),
            label=f"Chipyard source witness {relative}",
        )
        source_witnesses[relative] = {
            "git_blob_sha1": observed_blob,
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
        }

    submodule_records = parse_submodule_status(submodule_status)
    for path in CRITICAL_SUBMODULE_PATHS:
        record = submodule_records.get(path)
        if record is None:
            raise ValueError(f"critical Chipyard submodule is absent: {path}")
        if record["state"] != "exact":
            raise ValueError(
                f"critical Chipyard submodule is not at the pinned commit: {path}"
            )

    submodule_witnesses: dict[str, dict[str, Any]] = {}
    for relative, patterns in sorted(CHIPYARD_SUBMODULE_WITNESSES.items()):
        path = root / relative
        payload = _read_nonempty(path, f"Chipyard submodule witness {relative}")
        _validate_required_patterns(
            payload,
            list(patterns),
            label=f"Chipyard submodule witness {relative}",
        )
        submodule_witnesses[relative] = {
            "git_blob_sha1": git_blob_sha1(payload),
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
        }

    return {
        "repository": CHIPYARD_REPOSITORY,
        "commit": CHIPYARD_COMMIT,
        "source_witnesses": source_witnesses,
        "submodule_status_sha256": sha256_bytes(submodule_status.encode("utf-8")),
        "submodule_count": len(submodule_records),
        "critical_submodules": {
            path: submodule_records[path] for path in CRITICAL_SUBMODULE_PATHS
        },
        "submodule_witnesses": submodule_witnesses,
        "scala_source": {
            "path": CHIPYARD_SCALA_INSTALL_PATH,
            "sha256": sha256_bytes(scala_payload),
            "bytes": len(scala_payload),
        },
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_file_sha256": sha256_bytes(manifest_file.read_bytes()),
        "base_address": base_address,
    }


def assemble_chipyard_elaboration_proof(
    *,
    checkout_evidence: Mapping[str, Any],
    firrtl_path: str | Path,
    annotations_path: str | Path,
    chisel_log_path: str | Path,
    elaboration_log_path: str | Path,
    java_version: str,
    sbt_version: str,
    make_command: str,
) -> dict[str, Any]:
    firrtl = _read_nonempty(firrtl_path, "Chipyard FIRRTL")
    annotations = _read_nonempty(annotations_path, "Chipyard annotations")
    chisel_log = _read_nonempty(chisel_log_path, "Chipyard Chisel log")
    elaboration_log = _read_nonempty(elaboration_log_path, "Chipyard elaboration log")
    if not java_version.strip() or not sbt_version.strip():
        raise ValueError("Java and SBT version evidence are required")
    if not make_command.strip():
        raise ValueError("Chipyard make command is required")

    firrtl_text = firrtl.decode("utf-8")
    if ELABORATION_WITNESS_NAME not in firrtl_text:
        raise ValueError("Chipyard FIRRTL is missing the physical-compute witness")
    if CHIPYARD_CONFIG_CLASS not in Path(firrtl_path).name:
        raise ValueError("Chipyard FIRRTL filename does not identify the target config")

    try:
        annotation_payload = json.loads(annotations.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Chipyard annotations are not valid JSON") from exc
    if not isinstance(annotation_payload, (list, dict)) or not annotation_payload:
        raise ValueError("Chipyard annotations contain no elaboration records")

    module_count = len(
        re.findall(r"(?m)^\s*(?:extmodule|module)\s+", firrtl_text)
    )
    if module_count < 1:
        raise ValueError("Chipyard FIRRTL contains no modules")

    proof: dict[str, Any] = {
        "schema_version": CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION,
        "artifact_type": "chipyard_physical_compute_subsystem_elaboration_proof",
        "portable_binding": PORTABLE_BINDING,
        "chipyard": dict(checkout_evidence),
        "target": {
            "config_package": CHIPYARD_CONFIG_PACKAGE,
            "config_class": CHIPYARD_CONFIG_CLASS,
            "make_command": make_command.strip(),
            "entry_api": "testchipip.soc.SubsystemInjectorKey",
            "patches_digital_top": False,
            "loopback_fallback": True,
        },
        "tools": {
            "java": _first_line(java_version),
            "sbt": _first_line(sbt_version),
        },
        "artifacts": {
            "firrtl": {
                "name": Path(firrtl_path).name,
                "sha256": sha256_bytes(firrtl),
                "bytes": len(firrtl),
                "module_count": module_count,
            },
            "annotations": {
                "name": Path(annotations_path).name,
                "sha256": sha256_bytes(annotations),
                "bytes": len(annotations),
                "record_count": len(annotation_payload),
            },
            "chisel_log": {
                "name": Path(chisel_log_path).name,
                "sha256": sha256_bytes(chisel_log),
                "bytes": len(chisel_log),
            },
            "elaboration_log": {
                "name": Path(elaboration_log_path).name,
                "sha256": sha256_bytes(elaboration_log),
                "bytes": len(elaboration_log),
            },
        },
        "observations": {
            "elaboration_witness_present": True,
            "source_contract_reconstructed": True,
            "critical_submodules_exact": True,
            "digital_top_unpatched": True,
            "loopback_fallback_retained": True,
        },
        "qualification": {
            "status": "chipyard_subsystem_elaboration_proved",
            "accepted": True,
            "chipyard_subsystem_claim_allowed": True,
            "chipyard_rtl_simulation_claim_allowed": False,
            "physical_claim_allowed": False,
            "complete_system_advantage_claim_allowed": False,
            "blockers": [
                "CHIPYARD_RTL_SIMULATION_UNRUN",
                "CHIPYARD_EXTERNAL_CARTRIDGE_BINDING_UNRUN",
                "RISC_V_BINARY_BUILD_UNRUN",
                "TARGET_TRACE_UNOBSERVED",
                "FPGA_OR_SILICON_EXECUTION_UNRUN",
                "PHYSICAL_SUBSTRATE_UNMEASURED",
                "PHYSICAL_ENERGY_UNMEASURED",
                "TIMING_THERMAL_VOLUME_UNMEASURED",
                "COMPLETE_SYSTEM_EVP_UNMEASURED",
                "INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING",
            ],
        },
        "claim_boundary": (
            "The proof establishes that the exact generated physical-compute Scala "
            "source entered the pinned Chipyard checkout through the upstream "
            "SubsystemInjectorKey API and elaborated into FIRRTL with the declared "
            "configuration, critical submodules, annotations, and fallback witness. "
            "It does not establish compiled Chipyard Verilog, RTL simulation, an "
            "external cartridge binding, RISC-V workload execution, FPGA or silicon "
            "behavior, physical substrate work, measured EVP, fabrication, or "
            "independent physical acceptance."
        ),
        "control_question": (
            "Can the physical-compute control plane enter the exact Chipyard subsystem "
            "through a replaceable injector, elaborate without patching DigitalTop, "
            "and preserve fallback and acceptance authority outside Chipyard?"
        ),
    }
    proof["proof_sha256"] = sha256(
        canonical_json(proof).encode("utf-8")
    ).hexdigest()
    return proof


def _git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout


def build_chipyard_elaboration_proof_from_checkout(
    *,
    checkout_root: str | Path,
    manifest_path: str | Path,
    scala_source_path: str | Path,
    firrtl_path: str | Path,
    annotations_path: str | Path,
    chisel_log_path: str | Path,
    elaboration_log_path: str | Path,
    java_version: str,
    sbt_version: str,
    make_command: str,
) -> dict[str, Any]:
    root = Path(checkout_root).resolve()
    checkout_commit = _git_output(root, "rev-parse", "HEAD").strip()
    submodule_status = _git_output(root, "submodule", "status", "--recursive")
    checkout_evidence = validate_chipyard_checkout(
        root,
        manifest_path,
        scala_source_path,
        checkout_commit=checkout_commit,
        submodule_status=submodule_status,
    )
    return assemble_chipyard_elaboration_proof(
        checkout_evidence=checkout_evidence,
        firrtl_path=firrtl_path,
        annotations_path=annotations_path,
        chisel_log_path=chisel_log_path,
        elaboration_log_path=elaboration_log_path,
        java_version=java_version,
        sbt_version=sbt_version,
        make_command=make_command,
    )
