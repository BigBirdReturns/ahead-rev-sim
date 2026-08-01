from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.consist_execution import (
    CONSIST_EXECUTION_PROOF_SCHEMA_VERSION,
    build_consist_execution_proof,
    validate_consist_execution_proof,
    validate_target_proof,
)
from ahead_rev_sim.consist_execution_cli import main as consist_proof_main
from ahead_rev_sim.mmio_abi import build_mmio_abi, canonical_json

ROOT = Path(__file__).resolve().parents[1]
HITCH_DIR = ROOT / "examples" / "hitches"
SCHEMA = ROOT / "schemas" / "physical-compute-consist-execution-proof.schema.json"
REFERENCE_CONSIST = HITCH_DIR / "reference.consist.json"
RESERVED_CONSIST = HITCH_DIR / "ahead-vaire.reserved-consist.json"
REFERENCE_HOST = HITCH_DIR / "reference-rv64gc-host.hitch.json"
REFERENCE_CARTRIDGE = HITCH_DIR / "reference-loopback-cartridge.hitch.json"
AHEAD = HITCH_DIR / "aheadcomputing-riscv-host.offer.json"
VAIRE = HITCH_DIR / "vaire-reversible-cartridge.offer.json"
TARGET_PROOF = HITCH_DIR / "reference-riscv-target-proof.json"
REFERENCE_EXECUTION_PROOF = HITCH_DIR / "reference-consist-execution-proof.json"


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_proof() -> dict:
    return _payload(TARGET_PROOF)


def test_consist_execution_proof_is_deterministic_sealed_and_schema_valid() -> None:
    consist = _payload(REFERENCE_CONSIST)
    target = _target_proof()
    host = _payload(REFERENCE_HOST)
    cartridge = _payload(REFERENCE_CARTRIDGE)
    first = build_consist_execution_proof(consist, target, host, cartridge)
    second = build_consist_execution_proof(consist, target, host, cartridge)
    assert first == second
    assert first == _payload(REFERENCE_EXECUTION_PROOF)
    assert first["schema_version"] == CONSIST_EXECUTION_PROOF_SCHEMA_VERSION
    validate_consist_execution_proof(
        first,
        consist=consist,
        target_proof=target,
        host_hitch=host,
        cartridge_hitch=cartridge,
    )

    schema = _payload(SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)


def test_consist_execution_proof_binds_both_couplers_and_target_evidence() -> None:
    consist = _payload(REFERENCE_CONSIST)
    target = _target_proof()
    proof = build_consist_execution_proof(
        consist,
        target,
        _payload(REFERENCE_HOST),
        _payload(REFERENCE_CARTRIDGE),
    )

    assert proof["consist"]["consist_sha256"] == consist["consist_sha256"]
    assert proof["consist"]["host_hitch_sha256"] == consist["host"]["hitch_sha256"]
    assert proof["consist"]["cartridge_hitch_sha256"] == consist["cartridge"]["hitch_sha256"]
    assert proof["target_proof"]["proof_sha256"] == target["proof_sha256"]
    assert proof["qualification"]["status"] == "reference_consist_execution_proved"
    assert proof["qualification"]["accepted"] is True
    assert proof["qualification"]["physical_compute_claim_allowed"] is False
    assert proof["qualification"]["physical_energy_claim_allowed"] is False
    assert "HOST_PHYSICAL_REALIZATION_ABSENT" in proof["qualification"]["blockers"]
    assert "CARTRIDGE_PHYSICAL_REALIZATION_ABSENT" in proof["qualification"]["blockers"]
    assert "CHIPYARD_RTL_SIMULATION_UNRUN" in proof["qualification"]["blockers"]


def test_reserved_ahead_vaire_offer_cannot_be_promoted_to_execution() -> None:
    with pytest.raises(ValueError, match="execution is not admitted"):
        build_consist_execution_proof(
            _payload(RESERVED_CONSIST),
            _target_proof(),
            _payload(AHEAD),
            _payload(VAIRE),
        )


def test_target_proof_tampering_or_physical_self_promotion_is_refused() -> None:
    tampered = _target_proof()
    tampered["observations"]["checks"]["result_pass"] = False
    with pytest.raises(ValueError, match="failed semantic check"):
        validate_target_proof(tampered)

    promoted = _target_proof()
    promoted["qualification"]["physical_claim_allowed"] = True
    promoted["proof_sha256"] = sha256(
        canonical_json({k: v for k, v in promoted.items() if k != "proof_sha256"}).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="may not grant a physical claim"):
        validate_target_proof(promoted)

    resealed_tamper = _target_proof()
    resealed_tamper["artifacts"]["binary_sha256"] = "3" * 64
    with pytest.raises(ValueError, match="seal does not match"):
        validate_target_proof(resealed_tamper)


def test_consist_execution_cli_writes_reconstructable_proof(tmp_path: Path) -> None:
    target_path = tmp_path / "target-proof.json"
    target_path.write_text(
        json.dumps(_target_proof(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "consist-proof.json"
    assert (
        consist_proof_main(
            [
                "--consist",
                str(REFERENCE_CONSIST),
                "--host-hitch",
                str(REFERENCE_HOST),
                "--cartridge-hitch",
                str(REFERENCE_CARTRIDGE),
                "--target-proof",
                str(target_path),
                "--out",
                str(output),
            ]
        )
        == 0
    )
    proof = _payload(output)
    validate_consist_execution_proof(
        proof,
        consist=_payload(REFERENCE_CONSIST),
        target_proof=_target_proof(),
        host_hitch=_payload(REFERENCE_HOST),
        cartridge_hitch=_payload(REFERENCE_CARTRIDGE),
    )


def test_consist_execution_proof_seal_refuses_mutation() -> None:
    proof = build_consist_execution_proof(
        _payload(REFERENCE_CONSIST),
        _target_proof(),
        _payload(REFERENCE_HOST),
        _payload(REFERENCE_CARTRIDGE),
    )
    mutated = deepcopy(proof)
    mutated["target"]["execution_environment"] = "invented"
    with pytest.raises(ValueError, match="seal does not match"):
        validate_consist_execution_proof(mutated)


def test_consist_execution_requires_hitch_receipts_to_match_target_proof() -> None:
    from ahead_rev_sim.provider_hitch import build_consist, seal_hitch

    host = _payload(REFERENCE_HOST)
    receipt = next(
        item
        for item in host["artifacts"]
        if item["slot"] == "reset_refusal_receipt"
    )
    receipt["digest"]["value"] = "9" * 64
    host = seal_hitch(host)
    cartridge = _payload(REFERENCE_CARTRIDGE)
    consist = build_consist(host, cartridge)
    with pytest.raises(ValueError, match="host reset and refusal receipt diverges"):
        build_consist_execution_proof(
            consist,
            _target_proof(),
            host,
            cartridge,
        )
