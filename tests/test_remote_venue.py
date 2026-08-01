from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.remote_venue import (
    REMOTE_COMPARISON_SCHEMA_VERSION,
    REMOTE_RECEIPT_SCHEMA_VERSION,
    REMOTE_SUBMISSION_SCHEMA_VERSION,
    build_remote_submission,
    build_remote_venue_comparison,
    build_remote_venue_receipt,
    canonical_json,
)
from ahead_rev_sim.remote_venue_cli import main as venue_main


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "remote_venue" / "reference-submission-source.json"
RETURN_A = ROOT / "examples" / "remote_venue" / "reference-return-a.json"
RETURN_B = ROOT / "examples" / "remote_venue" / "reference-return-b.json"
SUBMISSION_SCHEMA = ROOT / "schemas" / "remote-venue-submission.schema.json"
RECEIPT_SCHEMA = ROOT / "schemas" / "remote-venue-receipt.schema.json"
COMPARISON_SCHEMA = ROOT / "schemas" / "remote-venue-comparison.schema.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def submission() -> dict:
    return build_remote_submission(load(SOURCE))


def test_submission_is_venue_neutral_sealed_and_provider_subordinate() -> None:
    packet = submission()
    assert packet["schema_version"] == REMOTE_SUBMISSION_SCHEMA_VERSION
    assert packet["artifact_type"] == "remote_venue_submission"
    assert packet["submission_id"] == "svk-portable-venue-v1"
    assert packet["policy"] == {
        "dependency_mode": "commodity_only",
        "provider_authority": "execution_only",
        "service_completion_is_acceptance": False,
        "raw_return_required": True,
        "local_replay_required": True,
        "migration_allowed": True,
    }
    assert [item["path"] for item in packet["files"]] == [
        "bin/fambs-svk",
        "inputs/config.json",
    ]
    claimed = packet.pop("submission_sha256")
    assert claimed == sha256(canonical_json(packet).encode("utf-8")).hexdigest()


def test_completed_return_is_accepted_locally_only_after_raw_custody() -> None:
    receipt = build_remote_venue_receipt(submission(), load(RETURN_A))
    assert receipt["schema_version"] == REMOTE_RECEIPT_SCHEMA_VERSION
    assert receipt["terminal_state"] == "completed"
    assert receipt["service_completed"] is True
    assert receipt["output_matches"] is True
    assert receipt["missing_return_artifacts"] == []
    assert receipt["local_acceptance"] == "accepted"
    assert receipt["accepted_work_allowed"] is True
    assert receipt["blockers"] == []
    assert receipt["migration_eligible"] is True


def test_completed_service_with_wrong_output_or_missing_raw_artifact_is_refused() -> None:
    wrong = load(RETURN_A)
    wrong["accepted_output_sha256"] = "f" * 64
    wrong_receipt = build_remote_venue_receipt(submission(), wrong)
    assert wrong_receipt["service_completed"] is True
    assert wrong_receipt["local_acceptance"] == "refused"
    assert wrong_receipt["accepted_work_allowed"] is False
    assert "ACCEPTED_OUTPUT_MISMATCH_OR_MISSING" in wrong_receipt["blockers"]

    missing = load(RETURN_A)
    missing["raw_artifacts"] = [
        item for item in missing["raw_artifacts"]
        if item["role"] != "execution_trace"
    ]
    missing_receipt = build_remote_venue_receipt(submission(), missing)
    assert missing_receipt["service_completed"] is True
    assert missing_receipt["missing_return_artifacts"] == ["execution_trace"]
    assert missing_receipt["accepted_work_allowed"] is False
    assert "REQUIRED_RAW_ARTIFACTS_MISSING" in missing_receipt["blockers"]


def test_cancelled_faulted_and_refused_venue_states_remain_distinct_receipts() -> None:
    for state in ("cancelled", "faulted", "refused"):
        returned = load(RETURN_A)
        returned["terminal_state"] = state
        receipt = build_remote_venue_receipt(submission(), returned)
        assert receipt["terminal_state"] == state
        assert receipt["service_completed"] is False
        assert receipt["local_acceptance"] == "refused"
        assert receipt["accepted_work_allowed"] is False
        assert "VENUE_TERMINAL_STATE_NOT_COMPLETED" in receipt["blockers"]
        assert len(receipt["receipt_sha256"]) == 64


def test_same_packet_across_two_venues_proves_substitution() -> None:
    packet = submission()
    first = build_remote_venue_receipt(packet, load(RETURN_A))
    second = build_remote_venue_receipt(packet, load(RETURN_B))
    comparison = build_remote_venue_comparison([first, second])
    assert comparison["schema_version"] == REMOTE_COMPARISON_SCHEMA_VERSION
    assert comparison["submission_sha256"] == packet["submission_sha256"]
    assert comparison["venue_ids"] == [
        "reference-venue-a",
        "reference-venue-b",
    ]
    assert comparison["accepted_venue_count"] == 2
    assert comparison["refused_venue_count"] == 0
    assert comparison["output_consensus"] is True
    assert comparison["substitution_proved"] is True


def test_substitution_refuses_different_packet_duplicate_venue_and_refused_result() -> None:
    packet = submission()
    first = build_remote_venue_receipt(packet, load(RETURN_A))
    second = build_remote_venue_receipt(packet, load(RETURN_B))

    different_source = load(SOURCE)
    different_source["submission_id"] = "other-submission"
    different_packet = build_remote_submission(different_source)
    different_receipt = build_remote_venue_receipt(
        different_packet,
        load(RETURN_B),
    )
    with pytest.raises(ValueError, match="one sealed submission"):
        build_remote_venue_comparison([first, different_receipt])

    duplicate = deepcopy(second)
    duplicate["venue"]["venue_id"] = first["venue"]["venue_id"]
    unsigned = deepcopy(duplicate)
    unsigned.pop("receipt_sha256")
    duplicate["receipt_sha256"] = sha256(
        canonical_json(unsigned).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="duplicate venue"):
        build_remote_venue_comparison([first, duplicate])

    refused_return = load(RETURN_B)
    refused_return["accepted_output_sha256"] = "f" * 64
    refused = build_remote_venue_receipt(packet, refused_return)
    comparison = build_remote_venue_comparison([first, refused])
    assert comparison["substitution_proved"] is False
    assert comparison["output_consensus"] is False
    assert comparison["refused_venue_count"] == 1


def test_tampered_submission_is_rejected_before_venue_acceptance() -> None:
    packet = submission()
    packet["workload"]["contract_id"] = "tampered"
    with pytest.raises(ValueError, match="seal mismatch"):
        build_remote_venue_receipt(packet, load(RETURN_A))


def test_remote_venue_schemas_accept_generated_artifacts() -> None:
    packet = submission()
    first = build_remote_venue_receipt(packet, load(RETURN_A))
    second = build_remote_venue_receipt(packet, load(RETURN_B))
    comparison = build_remote_venue_comparison([first, second])

    fixtures = (
        (SUBMISSION_SCHEMA, packet),
        (RECEIPT_SCHEMA, first),
        (COMPARISON_SCHEMA, comparison),
    )
    for schema_path, artifact in fixtures:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(artifact)


def test_remote_venue_cli_seals_verifies_and_compares(tmp_path: Path) -> None:
    packet_path = tmp_path / "submission.json"
    first_path = tmp_path / "venue-a.json"
    second_path = tmp_path / "venue-b.json"
    comparison_path = tmp_path / "comparison.json"

    assert venue_main(
        ["seal", str(SOURCE), "--out", str(packet_path)]
    ) == 0
    assert venue_main(
        [
            "verify",
            str(packet_path),
            str(RETURN_A),
            "--out",
            str(first_path),
            "--require-accepted",
        ]
    ) == 0
    assert venue_main(
        [
            "verify",
            str(packet_path),
            str(RETURN_B),
            "--out",
            str(second_path),
            "--require-accepted",
        ]
    ) == 0
    assert venue_main(
        [
            "compare",
            str(first_path),
            str(second_path),
            "--out",
            str(comparison_path),
            "--require-substitution",
        ]
    ) == 0
    payload = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert payload["substitution_proved"] is True
    assert len(payload["comparison_sha256"]) == 64
