"""Machine-readable intake for external compute projects treated as commodities."""

from __future__ import annotations

from collections import Counter
from importlib.resources import files
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .commodity_registry_constants import (
    REGISTRY_RESOURCE,
    REGISTRY_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    SHARD_SCHEMA_VERSION,
)
from .commodity_validation import validate_registry


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def default_registry_path() -> Path:
    resource = files("ahead_rev_sim").joinpath(REGISTRY_RESOURCE)
    return Path(str(resource))


def registry_digest(registry: Mapping[str, Any]) -> str:
    return sha256(canonical_json(registry).encode("utf-8")).hexdigest()


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path is not None else default_registry_path()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("commodity registry must be a JSON object")

    if payload.get("artifact_type") == "commodity_ecosystem_registry_manifest":
        payload = _expand_manifest(payload, registry_path.parent)

    validate_registry(payload)
    return payload


def _expand_manifest(manifest: Mapping[str, Any], base_dir: Path) -> dict[str, Any]:
    if manifest.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(f"unsupported commodity registry schema: {manifest.get('schema_version')!r}")
    shards = manifest.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("commodity registry manifest must declare record shards")

    records: list[Mapping[str, Any]] = []
    seen_shards: set[str] = set()
    for shard_ref in shards:
        if not isinstance(shard_ref, Mapping):
            raise ValueError("commodity registry shard reference must be an object")
        shard_id = str(shard_ref.get("shard_id", ""))
        resource = str(shard_ref.get("resource", ""))
        expected_count = shard_ref.get("record_count")
        if not shard_id or shard_id in seen_shards:
            raise ValueError("commodity registry shard ids must be non-empty and unique")
        if not resource or Path(resource).name != resource:
            raise ValueError(f"{shard_id}: shard resource must be a sibling JSON filename")
        shard_path = base_dir / resource
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        if not isinstance(shard, Mapping):
            raise ValueError(f"{shard_id}: shard must be a JSON object")
        if shard.get("schema_version") != SHARD_SCHEMA_VERSION:
            raise ValueError(f"{shard_id}: unsupported shard schema")
        if shard.get("artifact_type") != "commodity_ecosystem_record_shard":
            raise ValueError(f"{shard_id}: invalid shard artifact_type")
        if shard.get("shard_id") != shard_id:
            raise ValueError(f"{shard_id}: shard identity mismatch")
        shard_records = shard.get("records")
        if not isinstance(shard_records, list):
            raise ValueError(f"{shard_id}: records must be an array")
        if expected_count != len(shard_records):
            raise ValueError(f"{shard_id}: declared record count does not match shard")
        records.extend(shard_records)
        seen_shards.add(shard_id)

    if manifest.get("record_count") != len(records):
        raise ValueError("commodity registry manifest record_count does not match shards")

    expanded = {
        key: value
        for key, value in manifest.items()
        if key not in {"record_count", "shards"}
    }
    expanded["artifact_type"] = "commodity_ecosystem_registry"
    expanded["records"] = records
    return expanded


def select_records(
    registry: Mapping[str, Any],
    *,
    categories: Iterable[str] | None = None,
    priority_max: int = 5,
) -> list[Mapping[str, Any]]:
    if not 1 <= priority_max <= 5:
        raise ValueError("priority_max must be in the range 1..5")
    category_set = set(categories or ())
    selected = []
    for record in registry["records"]:
        if category_set and record["category"] not in category_set:
            continue
        if int(record["ingestion_policy"]["priority"]) > priority_max:
            continue
        selected.append(record)
    return sorted(
        selected,
        key=lambda item: (
            int(item["ingestion_policy"]["priority"]),
            item["category"],
            item["id"],
        ),
    )


def build_harvest_report(
    registry: Mapping[str, Any],
    *,
    categories: Iterable[str] | None = None,
    priority_max: int = 5,
) -> dict[str, Any]:
    validate_registry(registry)
    selected = select_records(
        registry,
        categories=categories,
        priority_max=priority_max,
    )
    category_counts = Counter(str(record["category"]) for record in selected)
    priority_counts = Counter(str(record["ingestion_policy"]["priority"]) for record in selected)
    gap_counts = Counter(
        str(gap)
        for record in selected
        for gap in record["system_gaps"]
    )
    asset_counts = Counter(
        str(asset["asset_kind"])
        for record in selected
        for asset in record["commodity_assets"]
    )

    transactions = [
        {
            "id": record["id"],
            "actor": record["actor"],
            "project": record["project"],
            "category": record["category"],
            "priority": record["ingestion_policy"]["priority"],
            "first_transaction": record["ingestion_policy"]["first_transaction"],
            "actions": record["ingestion_policy"]["actions"],
            "system_gaps": record["system_gaps"],
            "completion_questions": record["completion_questions"],
            "source_urls": [source["url"] for source in record["official_sources"]],
            "commodity_locators": [asset["locator"] for asset in record["commodity_assets"]],
        }
        for record in selected
    ]

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "artifact_type": "commodity_harvest_report",
        "registry_sha256": registry_digest(registry),
        "selection": {
            "categories": sorted(set(categories or ())),
            "priority_max": priority_max,
        },
        "summary": {
            "record_count": len(selected),
            "category_counts": dict(sorted(category_counts.items())),
            "priority_counts": dict(sorted(priority_counts.items())),
            "gap_frequency": dict(sorted(gap_counts.items(), key=lambda item: (-item[1], item[0]))),
            "asset_frequency": dict(sorted(asset_counts.items(), key=lambda item: (-item[1], item[0]))),
        },
        "transactions": transactions,
        "control_question": registry["doctrine"]["control_question"],
    }
    report["report_sha256"] = sha256(canonical_json(report).encode("utf-8")).hexdigest()
    return report


def format_harvest_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "COMMODITY HARVEST REPORT",
        f"registry: {report['registry_sha256']}",
        f"records: {summary['record_count']}",
        "",
        "priority  actor / project  first transaction",
        "--------  ---------------  -----------------",
    ]
    for transaction in report["transactions"]:
        lines.append(
            f"{transaction['priority']:<8}  "
            f"{transaction['actor']} / {transaction['project']}  "
            f"{transaction['first_transaction']}"
        )
    lines.extend(("", f"report sha256: {report['report_sha256']}"))
    return "\n".join(lines)
