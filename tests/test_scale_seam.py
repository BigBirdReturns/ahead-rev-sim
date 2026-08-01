from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.scale_seam import (
    SCALE_SEAM_ARTIFACT_TYPE,
    SCALE_SEAM_SCHEMA_VERSION,
    build_scale_seam_receipt,
    canonical_json,
)
from ahead_rev_sim.scale_seam_cli import main as scale_seam_main


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "scale_seam" / "reference-model.json"
SCHEMA = ROOT / "schemas" / "scale-seam-receipt.schema.json"
H = "a" * 64


def source_contract() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_reference_scale_seam_exposes_incremental_tax_without_evp_claim() -> None:
    receipt = build_scale_seam_receipt(source_contract())
    assert receipt["schema_version"] == SCALE_SEAM_SCHEMA_VERSION
    assert receipt["artifact_type"] == SCALE_SEAM_ARTIFACT_TYPE
    assert len(receipt["seams"]) == 5
    assert receipt["totals"]["traffic_bytes"] == 31000
    assert receipt["totals"]["message_count"] == 310
    assert receipt["totals"]["synchronization_events"] == 62
    assert receipt["totals"]["retries"] == 8
    assert receipt["totals"]["latency_seconds"] == 0.31
    assert receipt["totals"]["energy_joules"] == 31
    assert receipt["totals"]["incremental_occupied_mm3"] == 310
    assert receipt["totals"]["latency_seconds_per_accepted_work_unit"] == 0.0031
    assert receipt["totals"]["energy_joules_per_accepted_work_unit"] == 0.31
    assert receipt["dominant_seams"] == {
        "traffic": "board-to-rack",
        "latency": "board-to-rack",
        "energy": "board-to-rack",
        "incremental_volume": "board-to-rack",
    }
    assert receipt["qualification"]["status"] == "modeled_scale_seam"
    assert receipt["qualification"]["modeled_scale_seam_allowed"] is True
    assert receipt["qualification"]["measured_scale_seam_allowed"] is False
    assert receipt["qualification"][
        "complete_system_advantage_claim_allowed"
    ] is False
    assert {
        "SCALE_SEAMS_UNMEASURED",
        "BASELINE_MISSING_FOR_COMPARISON",
        "COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED",
    } <= set(receipt["qualification"]["blockers"])


def test_measured_scale_seam_requires_manifests_but_still_defers_to_evp() -> None:
    contract = source_contract()
    contract["model"]["evidence_class"] = "measured"
    contract["model"]["instrument_refs"] = ["trace-clock-a", "power-meter-a"]
    contract["model"]["uncertainty_fraction"] = 0.02
    contract["baseline"] = {
        "receipt_sha256": H,
        "workload_contract_id": contract["workload"]["contract_id"],
        "topology_sha256": contract["model"]["topology_sha256"],
        "latency_seconds_per_accepted_work_unit": 0.004,
        "energy_joules_per_accepted_work_unit": 0.4,
        "incremental_occupied_mm3": 400,
        "traffic_bytes_per_accepted_work_unit": 400,
    }
    receipt = build_scale_seam_receipt(contract)
    assert receipt["qualification"]["status"] == "measured_scale_seam"
    assert receipt["qualification"]["measured_scale_seam_allowed"] is True
    assert receipt["comparison"]["comparable"] is True
    assert receipt["comparison"]["latency_ratio"] == 0.775
    assert receipt["comparison"]["energy_ratio"] == 0.775
    assert receipt["comparison"]["incremental_volume_ratio"] == 0.775
    assert receipt["comparison"]["traffic_ratio"] == 0.775
    assert receipt["comparison"][
        "complete_system_advantage_claim_allowed"
    ] is False
    assert receipt["qualification"][
        "complete_system_advantage_claim_allowed"
    ] is False
    assert receipt["qualification"]["blockers"] == [
        "COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED"
    ]


def test_scale_chain_refuses_skips_duplicates_and_discontinuities() -> None:
    skipped = source_contract()
    skipped["seams"][1]["to_scale"] = "package"
    with pytest.raises(ValueError, match="adjacent scale domains"):
        build_scale_seam_receipt(skipped)

    duplicate = source_contract()
    duplicate["seams"][1]["seam_id"] = duplicate["seams"][0]["seam_id"]
    with pytest.raises(ValueError, match="duplicate seam id"):
        build_scale_seam_receipt(duplicate)

    discontinuous = source_contract()
    discontinuous["seams"][2]["from_scale"] = "package"
    discontinuous["seams"][2]["to_scale"] = "board"
    with pytest.raises(ValueError, match="contiguous"):
        build_scale_seam_receipt(discontinuous)


def test_unaccepted_work_is_refused() -> None:
    contract = source_contract()
    contract["workload"]["accepted"] = False
    receipt = build_scale_seam_receipt(contract)
    assert receipt["qualification"]["status"] == "refused"
    assert receipt["qualification"]["modeled_scale_seam_allowed"] is False
    assert "ACCEPTED_WORK_UNPROVEN" in receipt["qualification"]["blockers"]


def test_scale_seam_schema_accepts_reference_receipt() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        build_scale_seam_receipt(source_contract())
    )


def test_scale_seam_receipt_is_deterministic_and_sealed() -> None:
    first = build_scale_seam_receipt(source_contract())
    second = build_scale_seam_receipt(source_contract())
    assert first == second
    claimed = first.pop("receipt_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()


def test_scale_seam_cli_writes_receipt_and_measured_gate_refuses(
    tmp_path: Path,
) -> None:
    output = tmp_path / "scale.json"
    assert scale_seam_main(
        [str(SOURCE), "--out", str(output), "--quiet"]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["qualification"]["status"] == "modeled_scale_seam"
    assert scale_seam_main(
        [
            str(SOURCE),
            "--out",
            str(output),
            "--quiet",
            "--require-measured",
        ]
    ) == 2
