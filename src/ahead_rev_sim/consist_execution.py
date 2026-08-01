"""Bind an admitted provider consist to a sealed RISC-V target proof."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .mmio_abi import build_mmio_abi, canonical_json
from .physical_constants import OPTIONAL_RISCV_EXTENSION, PORTABLE_BINDING
from .physical_serialization import is_sha256
from .provider_hitch import validate_consist, validate_hitch

CONSIST_EXECUTION_PROOF_SCHEMA_VERSION = (
    "ahead.physical-compute-consist-execution-proof/v0.1"
)


def _without_seal(
    value: Mapping[str, Any],
    field: str,
) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    payload.pop(field, None)
    return payload


def load_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _artifact_digest(
    hitch: Mapping[str, Any],
    slot: str,
    *,
    algorithm: str,
    scope: str,
) -> str:
    for artifact in hitch["artifacts"]:
        if artifact["slot"] != slot:
            continue
        if artifact["status"] != "present":
            raise ValueError(f"{hitch['role']} hitch artifact {slot!r} is not present")
        digest = artifact.get("digest")
        if (
            not isinstance(digest, Mapping)
            or digest.get("algorithm") != algorithm
            or digest.get("scope") != scope
        ):
            raise ValueError(
                f"{hitch['role']} hitch artifact {slot!r} must use "
                f"{algorithm}/{scope}"
            )
        value = str(digest.get("value", ""))
        if algorithm == "sha256" and not is_sha256(value):
            raise ValueError(f"{hitch['role']} hitch artifact {slot!r} digest is invalid")
        return value
    raise ValueError(f"{hitch['role']} hitch artifact {slot!r} is missing")


def validate_target_proof(proof: Mapping[str, Any]) -> None:
    if proof.get("schema_version") != "ahead.riscv-target-proof/v0.1":
        raise ValueError("target proof schema version is invalid")
    if proof.get("artifact_type") != "riscv_target_model_execution_proof":
        raise ValueError("target proof artifact_type is invalid")
    if proof.get("portable_binding") != PORTABLE_BINDING:
        raise ValueError("target proof portable binding is invalid")
    if proof.get("optional_riscv_extension") != OPTIONAL_RISCV_EXTENSION:
        raise ValueError("target proof optional RISC-V extension is invalid")

    target = proof.get("target")
    if not isinstance(target, Mapping):
        raise ValueError("target proof target identity is required")
    if target.get("isa") != "rv64gc" or target.get("abi") != "lp64d":
        raise ValueError("target proof must identify the RV64GC LP64D target")
    if not str(target.get("execution_environment", "")).strip():
        raise ValueError("target proof execution environment is required")
    if not str(target.get("test_class", "")).strip():
        raise ValueError("target proof test class is required")

    qualification = proof.get("qualification")
    if not isinstance(qualification, Mapping):
        raise ValueError("target proof qualification is required")
    if qualification.get("status") != "riscv_target_model_execution_proved":
        raise ValueError("target proof status is not accepted")
    if qualification.get("accepted") is not True:
        raise ValueError("target proof is not accepted")
    if qualification.get("physical_claim_allowed") is not False:
        raise ValueError("target-model proof may not grant a physical claim")

    artifacts = proof.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("target proof artifacts are required")
    if artifacts.get("abi_sha256") != build_mmio_abi()["abi_sha256"]:
        raise ValueError("target proof ABI digest is invalid")
    for field in (
        "binary_sha256",
        "trace_sha256",
        "expected_trace_sha256",
    ):
        if not is_sha256(str(artifacts.get(field, ""))):
            raise ValueError(f"target proof {field} is invalid")
    if artifacts.get("trace_sha256") != artifacts.get("expected_trace_sha256"):
        raise ValueError("target proof trace does not match the accepted trace")

    observations = proof.get("observations")
    if not isinstance(observations, Mapping):
        raise ValueError("target proof observations are required")
    checks = observations.get("checks")
    if not isinstance(checks, Mapping) or not checks:
        raise ValueError("target proof semantic checks are required")
    if not all(value is True for value in checks.values()):
        raise ValueError("target proof contains a failed semantic check")
    line_count = observations.get("line_count")
    if not isinstance(line_count, int) or line_count <= 0:
        raise ValueError("target proof observation line count is invalid")

    claimed = str(proof.get("proof_sha256", ""))
    if not is_sha256(claimed):
        raise ValueError("target proof requires a SHA-256 seal")
    expected = sha256(
        canonical_json(_without_seal(proof, "proof_sha256")).encode("utf-8")
    ).hexdigest()
    if claimed != expected:
        raise ValueError("target proof SHA-256 seal does not match its content")


def build_consist_execution_proof(
    consist: Mapping[str, Any],
    target_proof: Mapping[str, Any],
    host_hitch: Mapping[str, Any],
    cartridge_hitch: Mapping[str, Any],
) -> dict[str, Any]:
    validate_hitch(host_hitch)
    validate_hitch(cartridge_hitch)
    validate_consist(
        consist,
        host=host_hitch,
        cartridge=cartridge_hitch,
    )
    validate_target_proof(target_proof)
    if consist.get("execution_admission") != "accepted":
        raise ValueError("consist execution is not admitted")
    if consist.get("interface_state") != "compatible":
        raise ValueError("consist interface is not compatible")
    if consist.get("abi_sha256") != target_proof["artifacts"]["abi_sha256"]:
        raise ValueError("consist and target proof ABI digests diverge")

    accepted_trace_sha256 = _artifact_digest(
        host_hitch,
        "accepted_target_trace",
        algorithm="sha256",
        scope="content",
    )
    host_receipt_sha256 = _artifact_digest(
        host_hitch,
        "reset_refusal_receipt",
        algorithm="sha256",
        scope="artifact_seal",
    )
    cartridge_output_sha256 = _artifact_digest(
        cartridge_hitch,
        "accepted_output_receipt",
        algorithm="sha256",
        scope="artifact_seal",
    )
    cartridge_reset_sha256 = _artifact_digest(
        cartridge_hitch,
        "reset_state_receipt",
        algorithm="sha256",
        scope="artifact_seal",
    )
    if accepted_trace_sha256 != target_proof["artifacts"]["expected_trace_sha256"]:
        raise ValueError("host hitch accepted trace diverges from target proof")
    for label, value in (
        ("host reset and refusal receipt", host_receipt_sha256),
        ("cartridge accepted-output receipt", cartridge_output_sha256),
        ("cartridge reset-state receipt", cartridge_reset_sha256),
    ):
        if value != target_proof["proof_sha256"]:
            raise ValueError(f"{label} diverges from target proof")

    target_blockers = [
        str(item)
        for item in target_proof["qualification"].get("blockers", [])
    ]
    physical_blockers = list(
        dict.fromkeys(
            [
                *map(str, consist.get("physical_claim_blockers", [])),
                *target_blockers,
            ]
        )
    )

    proof: dict[str, Any] = {
        "schema_version": CONSIST_EXECUTION_PROOF_SCHEMA_VERSION,
        "artifact_type": "physical_compute_consist_execution_proof",
        "portable_binding": PORTABLE_BINDING,
        "abi_sha256": consist["abi_sha256"],
        "consist": {
            "consist_sha256": consist["consist_sha256"],
            "host_hitch_id": consist["host"]["hitch_id"],
            "host_hitch_sha256": consist["host"]["hitch_sha256"],
            "cartridge_hitch_id": consist["cartridge"]["hitch_id"],
            "cartridge_hitch_sha256": consist["cartridge"]["hitch_sha256"],
        },
        "target_proof": {
            "proof_sha256": target_proof["proof_sha256"],
            "binary_sha256": target_proof["artifacts"]["binary_sha256"],
            "trace_sha256": target_proof["artifacts"]["trace_sha256"],
            "expected_trace_sha256": target_proof["artifacts"][
                "expected_trace_sha256"
            ],
        },
        "evidence_bindings": {
            "host_accepted_target_trace_sha256": accepted_trace_sha256,
            "host_reset_refusal_receipt_sha256": host_receipt_sha256,
            "cartridge_accepted_output_receipt_sha256": cartridge_output_sha256,
            "cartridge_reset_state_receipt_sha256": cartridge_reset_sha256,
        },
        "target": deepcopy(target_proof["target"]),
        "observations": deepcopy(target_proof["observations"]),
        "qualification": {
            "status": "reference_consist_execution_proved",
            "accepted": True,
            "interface_compatible": True,
            "execution_admitted": True,
            "physical_compute_claim_allowed": False,
            "physical_energy_claim_allowed": False,
            "blockers": physical_blockers,
        },
        "claim_boundary": (
            "The proof binds one execution-admitted host and cartridge consist to the "
            "accepted RV64GC target-model trace. It proves that the ordinary MMIO "
            "transaction, admission, refusal, reset, pointer, fallback, and receipt "
            "semantics survive an independently compiled RISC-V client and software "
            "device model. It does not establish Chipyard RTL execution, a physical "
            "substrate transformation, recovered or harvested energy, timing, thermal "
            "closure, occupied volume, fabrication, or provider qualification."
        ),
    }
    proof["proof_sha256"] = sha256(
        canonical_json(proof).encode("utf-8")
    ).hexdigest()
    return proof


def validate_consist_execution_proof(
    proof: Mapping[str, Any],
    *,
    consist: Mapping[str, Any] | None = None,
    target_proof: Mapping[str, Any] | None = None,
    host_hitch: Mapping[str, Any] | None = None,
    cartridge_hitch: Mapping[str, Any] | None = None,
) -> None:
    if (
        proof.get("schema_version")
        != CONSIST_EXECUTION_PROOF_SCHEMA_VERSION
    ):
        raise ValueError(
            f"unsupported consist execution proof schema: "
            f"{proof.get('schema_version')!r}"
        )
    if proof.get("artifact_type") != "physical_compute_consist_execution_proof":
        raise ValueError("consist execution proof artifact_type is invalid")
    if proof.get("portable_binding") != PORTABLE_BINDING:
        raise ValueError("consist execution proof portable binding is invalid")
    if proof.get("abi_sha256") != build_mmio_abi()["abi_sha256"]:
        raise ValueError("consist execution proof ABI digest is invalid")

    qualification = proof.get("qualification")
    if not isinstance(qualification, Mapping):
        raise ValueError("consist execution proof qualification is required")
    if qualification.get("status") != "reference_consist_execution_proved":
        raise ValueError("consist execution proof status is invalid")
    if qualification.get("accepted") is not True:
        raise ValueError("consist execution proof is not accepted")
    if qualification.get("interface_compatible") is not True:
        raise ValueError("consist execution proof interface is not compatible")
    if qualification.get("execution_admitted") is not True:
        raise ValueError("consist execution proof execution is not admitted")
    if qualification.get("physical_compute_claim_allowed") is not False:
        raise ValueError("consist execution proof may not grant a physical claim")
    if qualification.get("physical_energy_claim_allowed") is not False:
        raise ValueError("consist execution proof may not grant an energy claim")

    claimed = str(proof.get("proof_sha256", ""))
    if not is_sha256(claimed):
        raise ValueError("consist execution proof requires a SHA-256 seal")
    expected = sha256(
        canonical_json(_without_seal(proof, "proof_sha256")).encode("utf-8")
    ).hexdigest()
    if claimed != expected:
        raise ValueError(
            "consist execution proof SHA-256 seal does not match its content"
        )

    supplied = (
        consist,
        target_proof,
        host_hitch,
        cartridge_hitch,
    )
    if any(item is not None for item in supplied):
        if not all(item is not None for item in supplied):
            raise ValueError(
                "consist, target proof, host hitch, and cartridge hitch "
                "must be supplied together"
            )
        rebuilt = build_consist_execution_proof(
            consist,
            target_proof,
            host_hitch,
            cartridge_hitch,
        )
        if canonical_json(rebuilt) != canonical_json(proof):
            raise ValueError(
                "consist execution proof does not match its input artifacts"
            )


def write_consist_execution_proof(
    output_path: str | Path,
    proof: Mapping[str, Any],
) -> Path:
    validate_consist_execution_proof(proof)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
