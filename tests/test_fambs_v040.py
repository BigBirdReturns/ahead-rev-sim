from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.fambs import import_fambs, load_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "fambs" / "fambs-v0.4.0-pr1-source-manifest.json"
SCHEMA = ROOT / "schemas" / "fambs-import.schema.json"
COMMIT = "69498d4eebec9bed6f9c6793f13f9e20e89a866b"


def _observed_stream(*, mixed_clock: bool = False, mutate_result: bool = False) -> str:
    manifest = load_manifest(MANIFEST)
    contract = manifest["result_contract"]
    rows: list[str] = []
    for index, expected in enumerate(contract["rows"]):
        row = {
            "schema": contract["schema"],
            "suite_version": contract["suite_version"],
            "contract_id": contract["contract_id"],
            "bench": expected["bench"],
            "cycles": 1000 + index,
            "clock_kind": (
                "riscv_rdcycle" if not mixed_clock or index < 8 else "host_monotonic_ns"
            ),
            "iters": expected["iters"],
            "notes": expected["notes"],
            "result": expected["result"],
            "result_kind": expected["result_kind"],
            "accepted": True,
        }
        if mutate_result and index == 0:
            row["result"] = "0000000000000000"
        rows.append(json.dumps(row, sort_keys=True))
    return "\n".join(rows) + "\n"


def test_v040_candidate_closes_source_shape_and_binds_output_contract() -> None:
    artifact = import_fambs(MANIFEST)
    assert artifact.source["commit"] == COMMIT
    assert artifact.source["status"] == "proposed_pull_request"
    assert artifact.source_emission["expected_total_rows"] == 9
    assert artifact.source_emission["nested_expansions"] == []
    assert artifact.reference_results["shape_status"] == "match"
    assert artifact.reference_results["result_contract_validation"]["status"] == "pass"
    assert artifact.coverage["missing_accepted_output_contracts"] == []
    assert artifact.coverage["placeholder_self_checks"] == []
    assert artifact.qualification["status"] == "captured_shape_closed"
    assert artifact.qualification["blockers"] == []
    assert artifact.qualification["result_contract_bound"] is True
    assert artifact.qualification["accepted_work_claim_allowed"] is False
    assert artifact.qualification["performance_claim_allowed"] is False
    assert artifact.qualification["energy_claim_allowed"] is False


def test_v040_exact_nine_row_stream_qualifies_accepted_work() -> None:
    artifact = import_fambs(MANIFEST, result_stream_text=_observed_stream())
    assert artifact.observed_result_stream["row_count"] == 9
    assert artifact.observed_result_stream["shape_status"] == "match"
    assert artifact.observed_result_stream["clock_kinds"] == ["riscv_rdcycle"]
    assert artifact.observed_result_stream["result_contract_validation"]["status"] == "pass"
    assert artifact.observed_result_stream["result_contract_validation"]["qualified_rows"] == 9
    assert artifact.observed_result_stream["blockers"] == []
    assert artifact.qualification["status"] == "captured_result_qualified"
    assert artifact.qualification["observed_result_qualified"] is True
    assert artifact.qualification["accepted_work_claim_allowed"] is True


def test_v040_result_mutation_is_named_and_refused() -> None:
    artifact = import_fambs(
        MANIFEST,
        result_stream_text=_observed_stream(mutate_result=True),
    )
    assert "OBSERVED_RESULT_VALUE_MISMATCH" in artifact.qualification["blockers"]
    assert artifact.observed_result_stream["result_contract_validation"]["status"] == "fail"
    assert artifact.observed_result_stream["result_contract_validation"]["first_divergence"] == {
        "row": 0,
        "divergences": [
            {
                "field": "result",
                "expected": "000000004700158d",
                "actual": "0000000000000000",
            }
        ],
    }
    assert artifact.qualification["accepted_work_claim_allowed"] is False


def test_v040_mixed_clock_kinds_are_refused() -> None:
    artifact = import_fambs(
        MANIFEST,
        result_stream_text=_observed_stream(mixed_clock=True),
    )
    assert artifact.observed_result_stream["clock_kinds"] == [
        "host_monotonic_ns",
        "riscv_rdcycle",
    ]
    assert "OBSERVED_RESULT_CLOCK_KIND_MIXED" in artifact.qualification["blockers"]
    assert artifact.qualification["accepted_work_claim_allowed"] is False


def test_v040_mbw_retains_three_mode_identities_and_mal_has_one_row() -> None:
    manifest = load_manifest(MANIFEST)
    records = {record["bench_id"]: record for record in manifest["workloads"]}
    assert records["MBW"]["emission"] == {
        "standalone_rows": 3,
        "notes": ["sequential", "random", "strided_64B"],
    }
    assert records["MAL"]["emission"] == {
        "standalone_rows": 1,
        "notes": ["micro_autonomy_loop"],
    }
    assert manifest["source_emission_model"]["timed_region_contamination"] == []


def test_v040_result_contract_order_drift_is_rejected_at_manifest_admission() -> None:
    manifest = load_manifest(MANIFEST)
    manifest = deepcopy(manifest)
    rows = manifest["result_contract"]["rows"]
    rows[0], rows[1] = rows[1], rows[0]
    with pytest.raises(ValueError, match="row order"):
        load_manifest(manifest)


def test_v040_artifact_validates_against_draft_2020_12_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        import_fambs(MANIFEST, result_stream_text=_observed_stream()).to_dict()
    )
