from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.fambs import (
    FAMBS_IMPORT_SCHEMA_VERSION,
    derive_source_emission,
    import_fambs,
    load_manifest,
    parse_jsonl,
)
from ahead_rev_sim.fambs_cli import main as fambs_main

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "fambs" / "fambs-v0.3.2-source-manifest.json"
SCHEMA = ROOT / "schemas" / "fambs-import.schema.json"


def _full_source_stream() -> str:
    notes = {
        "SVK": "sparse_vector_dot",
        "MGT": "micro_graph_bfs",
        "MAK": "micro_attention",
        "MRK": "micro_retrieval_topk",
        "PCK": "pointer_chase",
        "MAL": "micro_autonomy_loop",
    }
    rows: list[dict[str, object]] = []
    for bench in ("SVK", "MGT", "MAK", "MRK"):
        for index in range(65):
            rows.append(
                {
                    "bench": bench,
                    "cycles": index + 1,
                    "iters": 1,
                    "notes": notes[bench],
                }
            )
    rows.append({"bench": "PCK", "cycles": 1, "iters": 1, "notes": notes["PCK"]})
    for index, note in enumerate(("sequential", "random", "strided_64B"), start=1):
        rows.append({"bench": "MBW", "cycles": index, "iters": 1, "notes": note})
    rows.append({"bench": "MAL", "cycles": 1, "iters": 1, "notes": notes["MAL"]})
    return "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"


def test_manifest_binds_all_seven_workloads_in_harness_order() -> None:
    manifest = load_manifest(MANIFEST)
    assert manifest["expected_workload_ids"] == [
        "SVK",
        "MGT",
        "MAK",
        "MRK",
        "PCK",
        "MBW",
        "MAL",
    ]
    assert [record["bench_id"] for record in manifest["workloads"]] == manifest[
        "expected_workload_ids"
    ]


def test_source_emission_reconstructs_265_rows() -> None:
    shape = derive_source_emission(load_manifest(MANIFEST))
    assert shape["expected_total_rows"] == 265
    assert shape["expected_bench_counts"] == {
        "SVK": 65,
        "MGT": 65,
        "MAK": 65,
        "MRK": 65,
        "PCK": 1,
        "MBW": 3,
        "MAL": 1,
    }
    assert shape["nested_expansions"][0]["expanded_rows"] == 256


def test_reference_results_are_preserved_but_refused_as_source_shape() -> None:
    artifact = import_fambs(MANIFEST)
    assert artifact.reference_results["row_count"] == 7
    assert artifact.reference_results["shape_status"] == "diverges"
    assert "REFERENCE_RESULT_ROW_COUNT_DIVERGES" in artifact.qualification["blockers"]
    assert "REFERENCE_RESULT_BENCH_DISTRIBUTION_DIVERGES" in artifact.qualification[
        "blockers"
    ]
    assert "REFERENCE_RESULT_NOTES_DIVERGE" in artifact.qualification["blockers"]


def test_mbw_and_mal_source_shapes_are_not_flattened() -> None:
    manifest = load_manifest(MANIFEST)
    records = {record["bench_id"]: record for record in manifest["workloads"]}
    assert records["MBW"]["emission"]["standalone_rows"] == 3
    assert records["MBW"]["emission"]["notes"] == [
        "sequential",
        "random",
        "strided_64B",
    ]
    assert "TIMED_REGION_INCLUDES_CHILD_REPORTING" in records["MAL"]["gaps"]


def test_accepted_work_remains_unbound_for_all_workloads() -> None:
    artifact = import_fambs(MANIFEST)
    assert artifact.coverage["missing_accepted_output_contracts"] == [
        "SVK",
        "MGT",
        "MAK",
        "MRK",
        "PCK",
        "MBW",
        "MAL",
    ]
    assert artifact.qualification["accepted_work_claim_allowed"] is False
    assert "ACCEPTED_OUTPUT_CONTRACTS_UNBOUND" in artifact.qualification["blockers"]


def test_jsonl_parser_ignores_comments_and_names_bad_lines() -> None:
    rows, errors = parse_jsonl(
        '# comment\n{"bench":"SVK","cycles":3,"iters":1,"notes":"sparse_vector_dot"}\n'
        "not-json\n"
    )
    assert len(rows) == 1
    assert rows[0].bench == "SVK"
    assert errors[0]["line"] == 3
    assert len(errors[0]["text_sha256"]) == 64


def test_full_source_shaped_stream_is_recognized() -> None:
    artifact = import_fambs(MANIFEST, result_stream_text=_full_source_stream())
    assert artifact.observed_result_stream["row_count"] == 265
    assert artifact.observed_result_stream["shape_status"] == "match"
    assert artifact.observed_result_stream["blockers"] == []
    assert artifact.qualification["status"] == "captured_blocked"


def test_observed_unknown_bench_is_refused() -> None:
    text = _full_source_stream() + json.dumps(
        {"bench": "MYSTERY", "cycles": 1, "iters": 1, "notes": "unknown"}
    )
    artifact = import_fambs(MANIFEST, result_stream_text=text)
    assert "OBSERVED_RESULT_UNKNOWN_BENCH" in artifact.qualification["blockers"]
    assert artifact.observed_result_stream["unknown_benches"] == ["MYSTERY"]


def test_artifact_is_deterministically_sealed() -> None:
    first = import_fambs(MANIFEST)
    second = import_fambs(MANIFEST)
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.to_json() == second.to_json()
    assert len(first.artifact_sha256 or "") == 64


def test_generated_artifact_validates_against_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(import_fambs(MANIFEST).to_dict())


def test_manifest_rejects_source_emission_drift() -> None:
    manifest = load_manifest(MANIFEST)
    manifest["source_emission_model"]["expected_total_rows"] = 7
    with pytest.raises(ValueError, match="emission total"):
        load_manifest(manifest)


def test_cli_writes_sealed_capture_and_can_fail_on_blockers(tmp_path: Path) -> None:
    output = tmp_path / "fambs-intake.json"
    assert fambs_main([str(MANIFEST), "--out", str(output), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == FAMBS_IMPORT_SCHEMA_VERSION
    assert len(payload["artifact_sha256"]) == 64
    assert (
        fambs_main(
            [
                str(MANIFEST),
                "--out",
                str(output),
                "--quiet",
                "--require-qualified",
            ]
        )
        == 2
    )
