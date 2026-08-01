"""Validation for machine-readable commodity ecosystem records."""

from __future__ import annotations

from typing import Any, Mapping

from .commodity_registry_constants import REGISTRY_SCHEMA_VERSION


def validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(f"unsupported commodity registry schema: {registry.get('schema_version')!r}")
    if registry.get("artifact_type") != "commodity_ecosystem_registry":
        raise ValueError("commodity registry artifact_type is invalid")

    doctrine = registry.get("doctrine")
    if not isinstance(doctrine, Mapping) or doctrine.get("dependency_mode") != "commodity_only":
        raise ValueError("registry doctrine must preserve commodity_only dependency mode")

    gaps = registry.get("gap_taxonomy")
    records = registry.get("records")
    if not isinstance(gaps, list) or not gaps:
        raise ValueError("registry gap_taxonomy must be a non-empty array")
    if not isinstance(records, list) or not records:
        raise ValueError("registry records must be a non-empty array")

    gap_ids = [str(item.get("gap_id", "")) for item in gaps if isinstance(item, Mapping)]
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
        if not isinstance(policy, Mapping) or policy.get("dependency_mode") != "commodity_only":
            raise ValueError(f"{record_id}: dependency mode must be commodity_only")
        priority = policy.get("priority")
        if not isinstance(priority, int) or not 1 <= priority <= 5:
            raise ValueError(f"{record_id}: priority must be in the range 1..5")

        sources = record.get("official_sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{record_id}: official_sources must be present")
        for source in sources:
            if not isinstance(source, Mapping) or not str(source.get("url", "")).startswith("https://"):
                raise ValueError(f"{record_id}: every official source must use https")

        assets = record.get("commodity_assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError(f"{record_id}: commodity_assets must be present")
        for asset in assets:
            if not isinstance(asset, Mapping) or not str(asset.get("locator", "")).startswith("https://"):
                raise ValueError(f"{record_id}: every commodity locator must use https")

        system_gaps = record.get("system_gaps")
        if not isinstance(system_gaps, list) or not system_gaps:
            raise ValueError(f"{record_id}: system_gaps must be present")
        unknown = set(map(str, system_gaps)) - known_gaps
        if unknown:
            raise ValueError(f"{record_id}: unknown system gaps: {sorted(unknown)}")

        questions = record.get("completion_questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError(f"{record_id}: completion_questions must be present")

    if len(set(record_ids)) != len(record_ids):
        raise ValueError("commodity record identifiers must be unique")
