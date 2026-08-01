"""Validation for machine-readable commodity ecosystem records and completion lanes."""

from __future__ import annotations

from typing import Any, Mapping

from .commodity_registry_constants import PROGRAM_SCHEMA_VERSION, REGISTRY_SCHEMA_VERSION


def validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported commodity registry schema: {registry.get('schema_version')!r}"
        )
    if registry.get("artifact_type") != "commodity_ecosystem_registry":
        raise ValueError("commodity registry artifact_type is invalid")

    doctrine = registry.get("doctrine")
    if (
        not isinstance(doctrine, Mapping)
        or doctrine.get("dependency_mode") != "commodity_only"
    ):
        raise ValueError("registry doctrine must preserve commodity_only dependency mode")

    gaps = registry.get("gap_taxonomy")
    records = registry.get("records")
    if not isinstance(gaps, list) or not gaps:
        raise ValueError("registry gap_taxonomy must be a non-empty array")
    if not isinstance(records, list) or not records:
        raise ValueError("registry records must be a non-empty array")

    gap_ids = [
        str(item.get("gap_id", ""))
        for item in gaps
        if isinstance(item, Mapping)
    ]
    if len(gap_ids) != len(gaps):
        raise ValueError("each registry gap must be an object")
    if len(set(gap_ids)) != len(gap_ids) or any(not item for item in gap_ids):
        raise ValueError("gap identifiers must be non-empty and unique")
    known_gaps = set(gap_ids)

    record_ids: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("each commodity record must be an object")
        record_id = str(record.get("id", ""))
        if not record_id:
            raise ValueError("commodity record id is required")
        record_ids.append(record_id)

        policy = record.get("ingestion_policy")
        if (
            not isinstance(policy, Mapping)
            or policy.get("dependency_mode") != "commodity_only"
        ):
            raise ValueError(f"{record_id}: dependency mode must be commodity_only")
        priority = policy.get("priority")
        if not isinstance(priority, int) or not 1 <= priority <= 5:
            raise ValueError(f"{record_id}: priority must be in the range 1..5")
        actions = policy.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError(f"{record_id}: ingestion actions must be present")
        if not str(policy.get("first_transaction", "")).strip():
            raise ValueError(f"{record_id}: first_transaction must be present")

        sources = record.get("official_sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{record_id}: official_sources must be present")
        for source in sources:
            if (
                not isinstance(source, Mapping)
                or not str(source.get("url", "")).startswith("https://")
            ):
                raise ValueError(f"{record_id}: every official source must use https")

        assets = record.get("commodity_assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError(f"{record_id}: commodity_assets must be present")
        for asset in assets:
            if (
                not isinstance(asset, Mapping)
                or not str(asset.get("locator", "")).startswith("https://")
            ):
                raise ValueError(f"{record_id}: every commodity locator must use https")
            modes = asset.get("ingest_modes")
            if not isinstance(modes, list) or not modes:
                raise ValueError(f"{record_id}: every commodity asset needs ingest_modes")

        system_gaps = record.get("system_gaps")
        if not isinstance(system_gaps, list) or not system_gaps:
            raise ValueError(f"{record_id}: system_gaps must be present")
        if len(set(map(str, system_gaps))) != len(system_gaps):
            raise ValueError(f"{record_id}: system_gaps must be unique")
        unknown = set(map(str, system_gaps)) - known_gaps
        if unknown:
            raise ValueError(f"{record_id}: unknown system gaps: {sorted(unknown)}")

        questions = record.get("completion_questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError(f"{record_id}: completion_questions must be present")

    if len(set(record_ids)) != len(record_ids):
        raise ValueError("commodity record identifiers must be unique")


def validate_completion_program(
    program: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> None:
    validate_registry(registry)
    if program.get("schema_version") != PROGRAM_SCHEMA_VERSION:
        raise ValueError(
            "unsupported commodity completion programme schema: "
            f"{program.get('schema_version')!r}"
        )
    if program.get("artifact_type") != "commodity_completion_program":
        raise ValueError("commodity completion programme artifact_type is invalid")

    doctrine = program.get("doctrine")
    if (
        not isinstance(doctrine, Mapping)
        or doctrine.get("dependency_mode") != "commodity_only"
    ):
        raise ValueError(
            "completion programme doctrine must preserve commodity_only dependency mode"
        )

    lanes = program.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        raise ValueError("completion programme lanes must be a non-empty array")

    registry_record_ids = {
        str(record["id"])
        for record in registry["records"]
    }
    registry_gap_ids = {
        str(item["gap_id"])
        for item in registry["gap_taxonomy"]
    }
    priority_one_ids = {
        str(record["id"])
        for record in registry["records"]
        if int(record["ingestion_policy"]["priority"]) == 1
    }

    lane_ids: list[str] = []
    covered: set[str] = set()
    for lane in lanes:
        if not isinstance(lane, Mapping):
            raise ValueError("each completion lane must be an object")
        lane_id = str(lane.get("lane_id", ""))
        if not lane_id:
            raise ValueError("completion lane id is required")
        lane_ids.append(lane_id)

        record_ids = lane.get("record_ids")
        if not isinstance(record_ids, list) or len(record_ids) < 2:
            raise ValueError(f"{lane_id}: at least two commodity records are required")
        normalized_records = [str(item) for item in record_ids]
        if len(set(normalized_records)) != len(normalized_records):
            raise ValueError(f"{lane_id}: record ids must be unique within the lane")
        unknown_records = set(normalized_records) - registry_record_ids
        if unknown_records:
            raise ValueError(
                f"{lane_id}: unknown commodity records: {sorted(unknown_records)}"
            )
        covered.update(normalized_records)

        gap_ids = lane.get("gap_ids")
        if not isinstance(gap_ids, list) or not gap_ids:
            raise ValueError(f"{lane_id}: gap_ids must be present")
        unknown_gaps = set(map(str, gap_ids)) - registry_gap_ids
        if unknown_gaps:
            raise ValueError(
                f"{lane_id}: unknown completion gaps: {sorted(unknown_gaps)}"
            )

        receipts = lane.get("required_receipts")
        if not isinstance(receipts, list) or not receipts:
            raise ValueError(f"{lane_id}: required_receipts must be present")
        for field_name in ("mission", "first_transaction", "control_question"):
            if not str(lane.get(field_name, "")).strip():
                raise ValueError(f"{lane_id}: {field_name} is required")

    if len(set(lane_ids)) != len(lane_ids):
        raise ValueError("completion lane identifiers must be unique")
    if covered != registry_record_ids:
        missing = registry_record_ids - covered
        extra = covered - registry_record_ids
        raise ValueError(
            "completion programme must cover every registry record exactly as a union; "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if not priority_one_ids <= covered:
        raise ValueError("every priority-one commodity must be covered")
    if program.get("registry_record_count") != len(registry_record_ids):
        raise ValueError(
            "completion programme registry_record_count does not match registry"
        )

    coverage = program.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("completion programme coverage must be an object")
    if coverage.get("lane_count") != len(lanes):
        raise ValueError("completion programme lane_count does not match lanes")
    if coverage.get("record_count") != len(covered):
        raise ValueError("completion programme record_count does not match coverage")
    if coverage.get("all_registry_records_covered") is not True:
        raise ValueError("completion programme must declare complete registry coverage")
