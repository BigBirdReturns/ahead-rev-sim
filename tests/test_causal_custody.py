from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.causal_custody import (
    CAUSAL_CUSTODY_ARTIFACT_TYPE,
    CAUSAL_CUSTODY_SCHEMA_VERSION,
    build_causal_custody_receipt,
    canonical_json,
)
from ahead_rev_sim.causal_custody_cli import main as causal_main


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "causal_custody" / "reference-model.json"
SCHEMA = ROOT / "schemas" / "causal-custody-receipt.schema.json"


def source_contract() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_reference_causal_custody_aligns_two_clocks_and_accepts_output() -> None:
    receipt = build_causal_custody_receipt(source_contract())
    assert receipt["schema_version"] == CAUSAL_CUSTODY_SCHEMA_VERSION
    assert receipt["artifact_type"] == CAUSAL_CUSTODY_ARTIFACT_TYPE
    assert receipt["summary"]["clock_count"] == 2
    assert receipt["summary"]["event_count"] == 10
    assert receipt["summary"]["causal_edge_count"] == 5
    assert receipt["summary"]["resolved_causal_edge_count"] == 5
    assert receipt["summary"]["unresolved_causal_edge_ids"] == []
    assert receipt["summary"]["missing_event_kinds"] == []
    assert receipt["summary"]["duplicate_singleton_event_kinds"] == []
    assert receipt["summary"]["maximum_clock_uncertainty_ns"] == 5
    assert receipt["summary"]["power_covers_work_interval"] is True
    assert receipt["summary"]["calibration_precedes_work"] is True
    assert receipt["summary"]["environment_precedes_work"] is True
    assert receipt["summary"]["accepted_output_matches"] is True
    assert receipt["qualification"]["status"] == "reference_causal_custody"
    assert receipt["qualification"]["reference_causal_custody_allowed"] is True
    assert receipt["qualification"]["measured_causal_custody_allowed"] is False
    assert receipt["qualification"]["physical_compute_claim_allowed"] is False
    assert receipt["qualification"][
        "complete_system_advantage_claim_allowed"
    ] is False
    assert receipt["qualification"]["blockers"] == [
        "CAUSAL_CUSTODY_UNMEASURED",
        "INSTRUMENT_CUSTODY_UNMEASURED",
        "COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED",
    ]


def test_measured_clock_custody_qualifies_measurement_but_not_physical_claim() -> None:
    contract = source_contract()
    for index, clock in enumerate(contract["clocks"]):
        clock["evidence_class"] = "measured"
        clock["instrument_ref"] = f"clock-instrument-{index}"
    receipt = build_causal_custody_receipt(contract)
    assert receipt["qualification"]["status"] == "measured_causal_custody"
    assert receipt["qualification"]["reference_causal_custody_allowed"] is True
    assert receipt["qualification"]["measured_causal_custody_allowed"] is True
    assert receipt["qualification"]["physical_compute_claim_allowed"] is False
    assert receipt["qualification"]["blockers"] == [
        "COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED"
    ]


def test_uncertainty_can_make_causal_edge_unresolved_without_losing_receipt() -> None:
    contract = source_contract()
    instrument = next(
        clock for clock in contract["clocks"]
        if clock["clock_id"] == "instrument-clock"
    )
    instrument["mapping"]["uncertainty_ns"] = 150
    receipt = build_causal_custody_receipt(contract)
    assert receipt["qualification"]["status"] == "refused"
    assert receipt["qualification"]["reference_causal_custody_allowed"] is False
    assert "CAUSAL_ORDER_UNRESOLVED" in receipt["qualification"]["blockers"]
    assert receipt["summary"]["unresolved_causal_edge_ids"]
    assert len(receipt["receipt_sha256"]) == 64


def test_wrong_output_missing_power_and_missing_required_kind_refuse_separately() -> None:
    wrong = source_contract()
    accepted = next(
        event for event in wrong["events"]
        if event["event_kind"] == "accepted_output"
    )
    accepted["value_sha256"] = "0" * 64
    wrong_receipt = build_causal_custody_receipt(wrong)
    assert "ACCEPTED_OUTPUT_MISMATCH_OR_MISSING" in wrong_receipt[
        "qualification"
    ]["blockers"]

    power = source_contract()
    power["events"] = [
        event for event in power["events"]
        if event["event_id"] != "power-post"
    ]
    power_receipt = build_causal_custody_receipt(power)
    assert "POWER_TRACE_DOES_NOT_BRACKET_WORK" in power_receipt[
        "qualification"
    ]["blockers"]

    missing = source_contract()
    missing["required_event_kinds"].append("entropy_observed")
    missing_receipt = build_causal_custody_receipt(missing)
    assert missing_receipt["summary"]["missing_event_kinds"] == [
        "entropy_observed"
    ]
    assert "REQUIRED_EVENT_KINDS_MISSING" in missing_receipt[
        "qualification"
    ]["blockers"]


def test_replay_with_trace_requires_entropy_and_path_custody() -> None:
    contract = source_contract()
    contract["determinism"]["determinism_class"] = "replay_with_trace"
    with pytest.raises(ValueError, match="requires entropy and stochastic-path"):
        build_causal_custody_receipt(contract)

    contract["determinism"]["entropy_trace_sha256"] = "1" * 64
    contract["determinism"]["stochastic_path_sha256"] = "2" * 64
    receipt = build_causal_custody_receipt(contract)
    assert receipt["determinism"]["determinism_class"] == "replay_with_trace"
    assert receipt["qualification"]["reference_causal_custody_allowed"] is True


def test_in_clock_event_order_and_reference_clock_mapping_are_fail_closed() -> None:
    out_of_order = source_contract()
    event = next(
        event for event in out_of_order["events"]
        if event["event_id"] == "power-mid"
    )
    event["local_timestamp_ns"] = 600
    with pytest.raises(ValueError, match="strictly ordered within clock"):
        build_causal_custody_receipt(out_of_order)

    shifted_reference = source_contract()
    reference = next(
        clock for clock in shifted_reference["clocks"]
        if clock["clock_id"] == "host-clock"
    )
    reference["mapping"]["offset_ns"] = 1
    with pytest.raises(ValueError, match="reference clock must use zero"):
        build_causal_custody_receipt(shifted_reference)


def test_causal_custody_schema_accepts_reference_receipt() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        build_causal_custody_receipt(source_contract())
    )


def test_causal_receipt_is_deterministic_and_sealed() -> None:
    first = build_causal_custody_receipt(source_contract())
    second = build_causal_custody_receipt(source_contract())
    assert first == second
    claimed = first.pop("receipt_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()


def test_causal_cli_writes_reference_and_measured_gate_refuses(
    tmp_path: Path,
) -> None:
    output = tmp_path / "causal.json"
    assert causal_main([str(SOURCE), "--out", str(output), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["qualification"]["status"] == "reference_causal_custody"
    assert causal_main(
        [
            str(SOURCE),
            "--out",
            str(output),
            "--quiet",
            "--require-measured",
        ]
    ) == 2
