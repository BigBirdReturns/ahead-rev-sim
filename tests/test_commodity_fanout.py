from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.commodity_program import (
    PLAN_SCHEMA_VERSION,
    PROGRAM_SCHEMA_VERSION,
    build_completion_plan,
    default_program_path,
    load_completion_program,
    program_digest,
    select_lanes,
)
from ahead_rev_sim.commodity_registry import load_registry
from ahead_rev_sim.commodity_validation import validate_completion_program
from ahead_rev_sim.fanout_cli import main as fanout_main

ROOT = Path(__file__).resolve().parents[1]
PROGRAM_SCHEMA = ROOT / "schemas" / "commodity-completion-program.schema.json"
PLAN_SCHEMA = ROOT / "schemas" / "commodity-completion-plan.schema.json"


def test_completion_program_is_packaged_and_valid() -> None:
    registry = load_registry()
    program_path = default_program_path()
    assert program_path.exists()
    program = load_completion_program(program_path, registry=registry)
    assert program["schema_version"] == PROGRAM_SCHEMA_VERSION
    assert program["artifact_type"] == "commodity_completion_program"
    assert program["registry_record_count"] == 73
    assert len(program["lanes"]) == 12
    assert program["coverage"] == {
        "all_registry_records_covered": True,
        "control_question": program["coverage"]["control_question"],
        "lane_count": 12,
        "record_count": 73,
    }


def test_completion_program_validates_against_draft_2020_12_schema() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)
    schema = json.loads(PROGRAM_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(program)


def test_completion_program_covers_every_record_and_priority_one() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)
    record_ids = {record["id"] for record in registry["records"]}
    covered = {
        record_id
        for lane in program["lanes"]
        for record_id in lane["record_ids"]
    }
    priority_one = {
        record["id"]
        for record in registry["records"]
        if record["ingestion_policy"]["priority"] == 1
    }
    assert covered == record_ids
    assert priority_one <= covered


def test_completion_plan_is_deterministic_sealed_and_schema_valid() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)
    first = build_completion_plan(registry, program)
    second = build_completion_plan(registry, program)
    assert first == second
    assert first["schema_version"] == PLAN_SCHEMA_VERSION
    assert first["program_sha256"] == program_digest(program)
    assert first["summary"]["lane_count"] == 12
    assert first["summary"]["record_count"] == 73
    assert first["summary"]["all_selected_records_covered"] is True
    assert first["summary"]["records_with_multiple_lanes"] >= 20
    assert len(first["plan_sha256"]) == 64

    schema = json.loads(PLAN_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)


def test_priority_one_plan_keeps_all_lanes_active() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)
    plan = build_completion_plan(registry, program, priority_max=1)
    assert plan["summary"]["record_count"] == 32
    assert plan["summary"]["lane_count"] == 12
    assert plan["summary"]["priority_counts"] == {"1": 32}
    assert plan["summary"]["all_selected_records_covered"] is True


def test_lane_selection_is_bounded_and_deterministic() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)
    requested = [
        "photonics-and-data-movement",
        "chiplet-and-package-composition",
    ]
    lanes = select_lanes(program, lane_ids=requested)
    assert [lane["lane_id"] for lane in lanes] == requested
    plan = build_completion_plan(
        registry,
        program,
        lane_ids=requested,
        priority_max=2,
    )
    assert plan["selection"]["lane_ids"] == requested
    assert set(plan["summary"]["category_counts"]) >= {
        "photonic_interconnect",
        "photonic_eda",
        "chiplet_interconnect",
    }


def test_program_rejects_missing_record_coverage() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)
    broken = copy.deepcopy(program)
    target = broken["lanes"][0]["record_ids"][0]
    for lane in broken["lanes"]:
        lane["record_ids"] = [
            record_id
            for record_id in lane["record_ids"]
            if record_id != target
        ]
    with pytest.raises(ValueError, match="cover every registry record"):
        validate_completion_program(broken, registry)


def test_program_rejects_unknown_record_and_gap() -> None:
    registry = load_registry()
    program = load_completion_program(registry=registry)

    unknown_record = copy.deepcopy(program)
    unknown_record["lanes"][0]["record_ids"].append("invented-sovereign-platform")
    with pytest.raises(ValueError, match="unknown commodity records"):
        validate_completion_program(unknown_record, registry)

    unknown_gap = copy.deepcopy(program)
    unknown_gap["lanes"][0]["gap_ids"].append("marketing_magic")
    with pytest.raises(ValueError, match="unknown completion gaps"):
        validate_completion_program(unknown_gap, registry)


def test_fanout_cli_writes_sealed_plan(tmp_path: Path) -> None:
    output = tmp_path / "fanout-plan.json"
    assert fanout_main(
        [
            "--lane",
            "measurement-and-benchmark-custody",
            "--priority-max",
            "1",
            "--out",
            str(output),
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == PLAN_SCHEMA_VERSION
    assert payload["summary"]["lane_count"] == 1
    assert payload["summary"]["record_count"] >= 5
    assert payload["summary"]["all_selected_records_covered"] is True
    assert len(payload["plan_sha256"]) == 64
