from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.hitch_cli import main as hitch_main
from ahead_rev_sim.provider_hitch import (
    CONSIST_SCHEMA_VERSION,
    HITCH_SCHEMA_VERSION,
    build_consist,
    load_hitch,
    seal_hitch,
    validate_consist,
    validate_hitch,
)

ROOT = Path(__file__).resolve().parents[1]
HITCH_DIR = ROOT / "examples" / "hitches"
HITCH_SCHEMA = ROOT / "schemas" / "physical-compute-provider-hitch.schema.json"
CONSIST_SCHEMA = ROOT / "schemas" / "physical-compute-consist.schema.json"
SUBSTRATE_SCHEMA = ROOT / "schemas" / "physical-substrate.schema.json"

AHEAD = HITCH_DIR / "aheadcomputing-riscv-host.offer.json"
VAIRE = HITCH_DIR / "vaire-reversible-cartridge.offer.json"
REFERENCE_HOST = HITCH_DIR / "reference-rv64gc-host.hitch.json"
REFERENCE_CARTRIDGE = HITCH_DIR / "reference-loopback-cartridge.hitch.json"
RESERVED_CONSIST = HITCH_DIR / "ahead-vaire.reserved-consist.json"
REFERENCE_CONSIST = HITCH_DIR / "reference.consist.json"
LOOPBACK_DESCRIPTOR = HITCH_DIR / "reference-loopback-substrate.json"


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_hitch_examples_are_schema_valid_and_sealed() -> None:
    schema = _payload(HITCH_SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for path in (AHEAD, VAIRE, REFERENCE_HOST, REFERENCE_CARTRIDGE):
        payload = load_hitch(path)
        assert payload["schema_version"] == HITCH_SCHEMA_VERSION
        validator.validate(payload)


def test_consist_examples_are_schema_valid_and_reconstructable() -> None:
    schema = _payload(CONSIST_SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    ahead = load_hitch(AHEAD)
    vaire = load_hitch(VAIRE)
    reserved = _payload(RESERVED_CONSIST)
    validator.validate(reserved)
    validate_consist(reserved, host=ahead, cartridge=vaire)

    host = load_hitch(REFERENCE_HOST)
    cartridge = load_hitch(REFERENCE_CARTRIDGE)
    reference = _payload(REFERENCE_CONSIST)
    assert reference["schema_version"] == CONSIST_SCHEMA_VERSION
    validator.validate(reference)
    validate_consist(reference, host=host, cartridge=cartridge)


def test_ahead_and_vaire_have_reserved_compatible_couplers() -> None:
    ahead = load_hitch(AHEAD)
    vaire = load_hitch(VAIRE)
    consist = build_consist(ahead, vaire)

    assert ahead["actor"] == "AheadComputing"
    assert ahead["commodity_record_id"] == "ahead-high-performance-riscv"
    assert ahead["role"] == "host"
    assert ahead["manifest_kind"] == "offer"
    assert ahead["actor_acknowledged"] is False

    assert vaire["actor"] == "Vaire Computing"
    assert vaire["commodity_record_id"] == "vaire-arc-evp"
    assert vaire["role"] == "cartridge"
    assert vaire["manifest_kind"] == "offer"
    assert vaire["actor_acknowledged"] is False

    assert consist["interface_state"] == "compatible"
    assert consist["hitchable"] is True
    assert consist["qualification_state"] == "hitchable_unqualified"
    assert consist["execution_admission"] == "refused"
    assert "HOST_SUBMISSION_ABSENT" in consist["execution_blockers"]
    assert "CARTRIDGE_SUBMISSION_ABSENT" in consist["execution_blockers"]
    assert consist["physical_compute_claim_allowed"] is False
    assert consist["physical_energy_claim_allowed"] is False


def test_reference_consist_executes_without_making_a_physical_claim() -> None:
    consist = build_consist(
        load_hitch(REFERENCE_HOST),
        load_hitch(REFERENCE_CARTRIDGE),
    )
    assert consist == _payload(REFERENCE_CONSIST)
    assert consist["interface_state"] == "compatible"
    assert consist["qualification_state"] == "execution_admitted"
    assert consist["execution_admission"] == "accepted"
    assert consist["negotiated_commands"] == [
        "capture",
        "evolve",
        "load",
        "read",
        "reset",
    ]
    assert consist["negotiated_capabilities"] == [
        "exact",
        "software_fallback",
    ]
    assert consist["execution_blockers"] == []
    assert consist["physical_compute_claim_allowed"] is False
    assert "HOST_PHYSICAL_REALIZATION_ABSENT" in consist["physical_claim_blockers"]
    assert "CARTRIDGE_PHYSICAL_REALIZATION_ABSENT" in consist["physical_claim_blockers"]


def test_substitution_contract_preserves_authority_boundaries() -> None:
    consist = _payload(REFERENCE_CONSIST)
    contract = consist["substitution_contract"]
    assert contract["dependency_mode"] == "commodity_only"
    assert contract["host_replaceable"] is True
    assert contract["cartridge_replaceable"] is True
    assert contract["software_fallback_required"] is True
    assert {
        "portable_binding",
        "accepted_work",
        "refusal_semantics",
        "software_fallback",
        "receipt_schema",
        "evidence_boundary",
    } == set(contract["provider_may_not_change"])


def test_hitch_cli_emits_reserved_and_admitted_consists(tmp_path: Path) -> None:
    reserved_path = tmp_path / "reserved.json"
    assert (
        hitch_main(
            [
                "--host",
                str(AHEAD),
                "--cartridge",
                str(VAIRE),
                "--out",
                str(reserved_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert _payload(reserved_path) == _payload(RESERVED_CONSIST)
    assert (
        hitch_main(
            [
                "--host",
                str(AHEAD),
                "--cartridge",
                str(VAIRE),
                "--require-admitted",
            ]
        )
        == 2
    )

    reference_path = tmp_path / "reference.json"
    assert (
        hitch_main(
            [
                "--host",
                str(REFERENCE_HOST),
                "--cartridge",
                str(REFERENCE_CARTRIDGE),
                "--out",
                str(reference_path),
                "--require-admitted",
            ]
        )
        == 0
    )
    assert _payload(reference_path) == _payload(REFERENCE_CONSIST)


def test_hitch_seals_refuse_tampering_and_authority_claims() -> None:
    tampered = _payload(AHEAD)
    tampered["project"] = "tampered"
    with pytest.raises(ValueError, match="seal does not match"):
        validate_hitch(tampered)

    claimed = _payload(AHEAD)
    claimed["workload_authority"] = "provider"
    claimed = seal_hitch(claimed)
    with pytest.raises(ValueError, match="may not claim workload_authority"):
        validate_hitch(claimed)


def test_hitch_requires_fallback_complete_commands_and_honest_offers() -> None:
    no_fallback = _payload(AHEAD)
    no_fallback["interface"]["required_capabilities"] = []
    no_fallback = seal_hitch(no_fallback)
    with pytest.raises(ValueError, match="require software fallback"):
        validate_hitch(no_fallback)

    incomplete = _payload(AHEAD)
    incomplete["interface"]["required_commands"].remove("capture")
    incomplete = seal_hitch(incomplete)
    with pytest.raises(ValueError, match="complete MMIO command surface"):
        validate_hitch(incomplete)

    false_acknowledgement = _payload(AHEAD)
    false_acknowledgement["actor_acknowledged"] = True
    false_acknowledgement = seal_hitch(false_acknowledgement)
    with pytest.raises(ValueError, match="must not imply actor acknowledgement"):
        validate_hitch(false_acknowledgement)


def test_physical_hitches_cannot_mark_claim_evidence_not_applicable() -> None:
    invalid = _payload(VAIRE)
    artifact = next(
        item
        for item in invalid["artifacts"]
        if item["required_for"] == "physical_claim"
    )
    artifact["status"] = "not_applicable"
    invalid = seal_hitch(invalid)
    with pytest.raises(ValueError, match="only virtual-reference"):
        validate_hitch(invalid)


def test_reference_loopback_descriptor_is_schema_valid() -> None:
    schema = _payload(SUBSTRATE_SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_payload(LOOPBACK_DESCRIPTOR))


def test_offers_cannot_self_supply_and_submissions_require_acknowledgement() -> None:
    self_supplied = _payload(AHEAD)
    self_supplied["interface"]["declared_commands"] = ["reset"]
    self_supplied = seal_hitch(self_supplied)
    with pytest.raises(ValueError, match="may not declare implementation"):
        validate_hitch(self_supplied)

    unacknowledged = _payload(AHEAD)
    unacknowledged["manifest_kind"] = "submission"
    unacknowledged = seal_hitch(unacknowledged)
    with pytest.raises(ValueError, match="requires explicit actor acknowledgement"):
        validate_hitch(unacknowledged)


def test_physical_claim_and_xphys_capabilities_require_receipts() -> None:
    weak_claim = _payload(VAIRE)
    weak_claim["manifest_kind"] = "submission"
    weak_claim["actor_acknowledged"] = True
    weak_claim["interface"]["declared_commands"] = list(
        weak_claim["interface"]["required_commands"]
    )
    weak_claim["interface"]["declared_capabilities"] = [
        "exact",
        "software_fallback",
    ]
    for artifact in weak_claim["artifacts"]:
        if artifact["required_for"] == "execution":
            artifact.update(
                status="present",
                locator=f"artifact://test/{artifact['slot']}",
                digest={"algorithm": "sha256", "value": "1" * 64, "scope": "content"},
                evidence_class=(
                    "target_observed"
                    if artifact["slot"]
                    in {
                        "accepted_target_trace",
                        "reset_refusal_receipt",
                        "accepted_output_receipt",
                        "reset_state_receipt",
                    }
                    else "source"
                ),
            )
    physical = next(
        item
        for item in weak_claim["artifacts"]
        if item["required_for"] == "physical_claim"
    )
    physical.update(
        status="present",
        locator="artifact://test/weak-claim",
        digest={"algorithm": "sha256", "value": "2" * 64, "scope": "content"},
        evidence_class="source",
    )
    weak_claim = seal_hitch(weak_claim)
    with pytest.raises(ValueError, match="must be measured or independently validated"):
        validate_hitch(weak_claim)

    xphys = _payload(REFERENCE_HOST)
    xphys["interface"]["declared_capabilities"].append("xphys_acceleration")
    xphys = seal_hitch(xphys)
    with pytest.raises(ValueError, match="bottleneck receipt"):
        validate_hitch(xphys)
