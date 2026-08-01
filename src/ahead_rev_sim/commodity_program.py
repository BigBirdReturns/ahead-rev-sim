"""Concurrent completion lanes for the commodity-only external ecosystem."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .commodity_registry import canonical_json, registry_digest
from .commodity_registry_constants import (
    PLAN_SCHEMA_VERSION,
    PROGRAM_RESOURCE,
    PROGRAM_SCHEMA_VERSION,
)
from .commodity_validation import validate_completion_program, validate_registry


def default_program_path() -> Path:
    resource = files("ahead_rev_sim").joinpath(PROGRAM_RESOURCE)
    return Path(str(resource))


def program_digest(program: Mapping[str, Any]) -> str:
    return sha256(canonical_json(program).encode("utf-8")).hexdigest()


def load_completion_program(
    path: str | Path | None = None,
    *,
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    program_path = Path(path) if path is not None else default_program_path()
    payload = json.loads(program_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("commodity completion programme must be a JSON object")
    validate_completion_program(payload, registry)
    return payload


def select_lanes(
    program: Mapping[str, Any],
    *,
    lane_ids: Iterable[str] | None = None,
) -> list[Mapping[str, Any]]:
    requested = tuple(dict.fromkeys(lane_ids or ()))
    lanes = {str(lane["lane_id"]): lane for lane in program["lanes"]}
    if not requested:
        return [lanes[lane_id] for lane_id in sorted(lanes)]
    unknown = set(requested) - set(lanes)
    if unknown:
        raise ValueError(f"unknown completion lanes: {sorted(unknown)}")
    return [lanes[lane_id] for lane_id in requested]


def build_completion_plan(
    registry: Mapping[str, Any],
    program: Mapping[str, Any],
    *,
    lane_ids: Iterable[str] | None = None,
    priority_max: int = 5,
) -> dict[str, Any]:
    validate_registry(registry)
    validate_completion_program(program, registry)
    if not 1 <= priority_max <= 5:
        raise ValueError("priority_max must be in the range 1..5")

    selected_lanes = select_lanes(program, lane_ids=lane_ids)
    records = {
        str(record["id"]): record
        for record in registry["records"]
    }
    selected_record_ids = sorted(
        {
            str(record_id)
            for lane in selected_lanes
            for record_id in lane["record_ids"]
            if int(records[str(record_id)]["ingestion_policy"]["priority"])
            <= priority_max
        }
    )
    if not selected_record_ids:
        raise ValueError(
            "completion selection contains no records at the requested priority"
        )
    selected_records = [records[record_id] for record_id in selected_record_ids]

    lane_transactions: list[dict[str, Any]] = []
    for lane in selected_lanes:
        lane_record_ids = [
            str(record_id)
            for record_id in lane["record_ids"]
            if str(record_id) in selected_record_ids
        ]
        if not lane_record_ids:
            continue
        lane_transactions.append(
            {
                "lane_id": lane["lane_id"],
                "mission": lane["mission"],
                "record_ids": lane_record_ids,
                "gap_ids": lane["gap_ids"],
                "required_receipts": lane["required_receipts"],
                "first_transaction": lane["first_transaction"],
                "control_question": lane["control_question"],
            }
        )

    covered_by_lane = Counter(
        record_id
        for lane in lane_transactions
        for record_id in lane["record_ids"]
    )
    priority_counts = Counter(
        str(record["ingestion_policy"]["priority"])
        for record in selected_records
    )
    category_counts = Counter(
        str(record["category"])
        for record in selected_records
    )
    gap_counts = Counter(
        str(gap)
        for record in selected_records
        for gap in record["system_gaps"]
    )

    record_transactions = [
        {
            "id": record["id"],
            "actor": record["actor"],
            "project": record["project"],
            "category": record["category"],
            "priority": record["ingestion_policy"]["priority"],
            "covered_by_lanes": sorted(
                lane["lane_id"]
                for lane in lane_transactions
                if record["id"] in lane["record_ids"]
            ),
            "first_transaction": record["ingestion_policy"]["first_transaction"],
            "actions": record["ingestion_policy"]["actions"],
            "system_gaps": record["system_gaps"],
            "completion_questions": record["completion_questions"],
            "source_urls": [
                source["url"]
                for source in record["official_sources"]
            ],
            "commodity_locators": [
                asset["locator"]
                for asset in record["commodity_assets"]
            ],
        }
        for record in selected_records
    ]

    plan: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "artifact_type": "commodity_completion_plan",
        "registry_sha256": registry_digest(registry),
        "program_sha256": program_digest(program),
        "selection": {
            "lane_ids": [lane["lane_id"] for lane in selected_lanes],
            "priority_max": priority_max,
        },
        "summary": {
            "lane_count": len(lane_transactions),
            "record_count": len(selected_records),
            "priority_counts": dict(sorted(priority_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "gap_frequency": dict(
                sorted(gap_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            "records_with_multiple_lanes": sum(
                count > 1 for count in covered_by_lane.values()
            ),
            "all_selected_records_covered": (
                set(selected_record_ids) == set(covered_by_lane)
            ),
        },
        "lane_transactions": lane_transactions,
        "record_transactions": record_transactions,
        "control_question": program["control_question"],
    }
    plan["plan_sha256"] = sha256(
        canonical_json(plan).encode("utf-8")
    ).hexdigest()
    return plan


def format_completion_plan(plan: Mapping[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "COMMODITY COMPLETION PLAN",
        f"registry: {plan['registry_sha256']}",
        f"program: {plan['program_sha256']}",
        f"lanes: {summary['lane_count']}",
        f"records: {summary['record_count']}",
        "",
        "lane  records  first transaction",
        "----  -------  -----------------",
    ]
    for lane in plan["lane_transactions"]:
        lines.append(
            f"{lane['lane_id']}  {len(lane['record_ids']):>7}  "
            f"{lane['first_transaction']}"
        )
    lines.extend(("", f"plan sha256: {plan['plan_sha256']}"))
    return "\n".join(lines)
