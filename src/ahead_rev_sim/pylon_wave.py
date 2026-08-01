"""Second-wave ecosystem intake over existing design pylons.

The wave is deliberately separate from the admitted commodity registry. It
can collect official public artifacts, project them onto existing pylons and
gaps, and emit bounded promotion transactions without silently changing the
authority or denominator of the current registry.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .commodity_registry import canonical_json, load_registry, registry_digest
from .congruent_shapes import load_pylon_catalog, pylon_catalog_digest

WAVE_SCHEMA_VERSION = "ahead.pylon-fanout-wave/v0.1"
REPORT_SCHEMA_VERSION = "ahead.pylon-fanout-report/v0.1"
WAVE_RESOURCE = "data/pylon_fanout_wave_2026_08.json"

PROMOTION_STATES = frozenset({"candidate", "intake_ready", "promoted"})
FRONTS = frozenset({"scale_seam", "remote_venue", "causal_custody"})


def default_wave_path() -> Path:
    resource = files("ahead_rev_sim").joinpath(WAVE_RESOURCE)
    return Path(str(resource))


def wave_digest(wave: Mapping[str, Any]) -> str:
    return sha256(canonical_json(wave).encode("utf-8")).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def _unique_strings(
    value: Any,
    field: str,
    *,
    minimum: int = 1,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise ValueError(f"{field} must be an array")
    result = [_nonempty(item, f"{field}[]") for item in value]
    if len(result) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} entries")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} entries must be unique")
    return result


def load_wave(
    path: str | Path | None = None,
    *,
    registry: Mapping[str, Any] | None = None,
    pylon_catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    wave_path = Path(path) if path is not None else default_wave_path()
    payload = json.loads(wave_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pylon fan-out wave must be a JSON object")
    registry_payload = dict(registry or load_registry())
    catalog_payload = dict(
        pylon_catalog or load_pylon_catalog(registry=registry_payload)
    )
    validate_wave(payload, registry_payload, catalog_payload)
    return payload


def validate_wave(
    wave: Mapping[str, Any],
    registry: Mapping[str, Any],
    pylon_catalog: Mapping[str, Any],
) -> None:
    if wave.get("schema_version") != WAVE_SCHEMA_VERSION:
        raise ValueError(
            "unsupported pylon fan-out wave schema: "
            f"{wave.get('schema_version')!r}"
        )
    if wave.get("artifact_type") != "pylon_fanout_wave":
        raise ValueError("pylon fan-out wave artifact_type is invalid")
    _nonempty(wave.get("wave_id"), "wave_id")
    _nonempty(wave.get("as_of"), "as_of")

    doctrine = wave.get("doctrine")
    if not isinstance(doctrine, Mapping):
        raise ValueError("wave doctrine must be an object")
    if doctrine.get("dependency_mode") != "commodity_only":
        raise ValueError("wave doctrine must preserve commodity_only")
    for field in (
        "statement",
        "admission_rule",
        "promotion_rule",
        "control_question",
    ):
        _nonempty(doctrine.get(field), f"doctrine.{field}")

    registry_records = registry.get("records")
    registry_gaps = registry.get("gap_taxonomy")
    catalog_pylons = pylon_catalog.get("pylons")
    if not isinstance(registry_records, list) or not registry_records:
        raise ValueError("admitted registry records are unavailable")
    if not isinstance(registry_gaps, list) or not registry_gaps:
        raise ValueError("admitted registry gaps are unavailable")
    if not isinstance(catalog_pylons, list) or not catalog_pylons:
        raise ValueError("pylon catalog is unavailable")

    admitted_ids = {str(record["id"]) for record in registry_records}
    known_gap_ids = {str(item["gap_id"]) for item in registry_gaps}
    known_pylon_ids = {str(item["pylon_id"]) for item in catalog_pylons}

    fronts = wave.get("fronts")
    if not isinstance(fronts, list) or not fronts:
        raise ValueError("wave fronts must be a non-empty array")
    front_by_id: dict[str, Mapping[str, Any]] = {}
    for front in fronts:
        if not isinstance(front, Mapping):
            raise ValueError("every wave front must be an object")
        front_id = _nonempty(front.get("front_id"), "front.front_id")
        if front_id not in FRONTS:
            raise ValueError(f"unknown wave front: {front_id}")
        if front_id in front_by_id:
            raise ValueError(f"duplicate wave front: {front_id}")
        _nonempty(front.get("mission"), f"{front_id}.mission")
        primary_pylons = _unique_strings(
            front.get("primary_pylon_ids"),
            f"{front_id}.primary_pylon_ids",
            minimum=2,
        )
        unknown_primary = set(primary_pylons) - known_pylon_ids
        if unknown_primary:
            raise ValueError(
                f"{front_id}: unknown primary pylons {sorted(unknown_primary)}"
            )
        _unique_strings(
            front.get("promotion_receipts"),
            f"{front_id}.promotion_receipts",
            minimum=1,
        )
        front_by_id[front_id] = front
    if set(front_by_id) != FRONTS:
        raise ValueError(f"wave must declare exactly the fronts {sorted(FRONTS)}")

    records = wave.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("wave records must be a non-empty array")
    if wave.get("record_count") != len(records):
        raise ValueError("wave record_count does not match records")

    wave_ids: list[str] = []
    front_counts: Counter[str] = Counter()
    pylon_coverage: Counter[str] = Counter()
    gap_coverage: Counter[str] = Counter()
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("every wave record must be an object")
        record_id = _nonempty(record.get("id"), "record.id")
        if record_id in admitted_ids:
            raise ValueError(
                f"{record_id}: wave record collides with admitted registry"
            )
        wave_ids.append(record_id)
        for field in ("actor", "project", "public_stage", "first_transaction"):
            _nonempty(record.get(field), f"{record_id}.{field}")

        front_id = _nonempty(record.get("front"), f"{record_id}.front")
        if front_id not in front_by_id:
            raise ValueError(f"{record_id}: unknown front {front_id}")
        front_counts[front_id] += 1

        if record.get("dependency_mode") != "commodity_only":
            raise ValueError(f"{record_id}: dependency mode must be commodity_only")
        priority = record.get("priority")
        if not isinstance(priority, int) or not 1 <= priority <= 5:
            raise ValueError(f"{record_id}: priority must be in 1..5")

        promotion_state = _nonempty(
            record.get("promotion_state"),
            f"{record_id}.promotion_state",
        )
        if promotion_state not in PROMOTION_STATES:
            raise ValueError(
                f"{record_id}: unknown promotion state {promotion_state}"
            )
        blockers = _unique_strings(
            record.get("promotion_blockers", []),
            f"{record_id}.promotion_blockers",
            minimum=0,
        )
        if promotion_state == "candidate" and not blockers:
            raise ValueError(f"{record_id}: candidate records require promotion blockers")
        if promotion_state == "promoted" and blockers:
            raise ValueError(f"{record_id}: promoted records cannot retain blockers")

        pylon_ids = _unique_strings(
            record.get("pylon_ids"),
            f"{record_id}.pylon_ids",
            minimum=2,
        )
        unknown_pylons = set(pylon_ids) - known_pylon_ids
        if unknown_pylons:
            raise ValueError(f"{record_id}: unknown pylons {sorted(unknown_pylons)}")
        for pylon_id in pylon_ids:
            pylon_coverage[pylon_id] += 1

        gap_ids = _unique_strings(
            record.get("gap_ids"),
            f"{record_id}.gap_ids",
            minimum=2,
        )
        unknown_gaps = set(gap_ids) - known_gap_ids
        if unknown_gaps:
            raise ValueError(f"{record_id}: unknown gaps {sorted(unknown_gaps)}")
        for gap_id in gap_ids:
            gap_coverage[gap_id] += 1

        sources = record.get("official_sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{record_id}: official_sources must be present")
        for source in sources:
            if not isinstance(source, Mapping):
                raise ValueError(f"{record_id}: official source must be an object")
            for field in ("kind", "title", "public_completion_signal"):
                _nonempty(
                    source.get(field),
                    f"{record_id}.official_sources.{field}",
                )
            url = _nonempty(
                source.get("url"),
                f"{record_id}.official_sources.url",
            )
            if not url.startswith("https://"):
                raise ValueError(f"{record_id}: official source must use https")

        assets = record.get("commodity_assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError(f"{record_id}: commodity_assets must be present")
        for asset in assets:
            if not isinstance(asset, Mapping):
                raise ValueError(f"{record_id}: commodity asset must be an object")
            for field in ("asset_kind", "license"):
                _nonempty(
                    asset.get(field),
                    f"{record_id}.commodity_assets.{field}",
                )
            locator = _nonempty(
                asset.get("locator"),
                f"{record_id}.commodity_assets.locator",
            )
            if not locator.startswith("https://"):
                raise ValueError(f"{record_id}: commodity locator must use https")
            _unique_strings(
                asset.get("ingest_modes"),
                f"{record_id}.commodity_assets.ingest_modes",
                minimum=1,
            )

        _unique_strings(
            record.get("required_receipts"),
            f"{record_id}.required_receipts",
            minimum=1,
        )
        _unique_strings(
            record.get("completion_questions"),
            f"{record_id}.completion_questions",
            minimum=1,
        )

    if len(set(wave_ids)) != len(wave_ids):
        raise ValueError("wave record identifiers must be unique")
    if any(front_counts[front_id] < 2 for front_id in FRONTS):
        raise ValueError("each wave front must contain at least two candidate records")

    for front_id, front in front_by_id.items():
        front_record_pylons = {
            pylon_id
            for record in records
            if record["front"] == front_id
            for pylon_id in record["pylon_ids"]
        }
        missing = set(front["primary_pylon_ids"]) - front_record_pylons
        if missing:
            raise ValueError(
                f"{front_id}: primary pylons are not represented {sorted(missing)}"
            )
    if not pylon_coverage:
        raise ValueError("wave projects onto no pylons")
    if not gap_coverage:
        raise ValueError("wave projects onto no registry gaps")


def select_wave_records(
    wave: Mapping[str, Any],
    *,
    fronts: Iterable[str] | None = None,
    priority_max: int = 5,
) -> list[Mapping[str, Any]]:
    if not 1 <= priority_max <= 5:
        raise ValueError("priority_max must be in the range 1..5")
    selected_fronts = set(fronts or ())
    unknown = selected_fronts - FRONTS
    if unknown:
        raise ValueError(f"unknown wave fronts: {sorted(unknown)}")
    selected = [
        record
        for record in wave["records"]
        if int(record["priority"]) <= priority_max
        and (not selected_fronts or str(record["front"]) in selected_fronts)
    ]
    return sorted(
        selected,
        key=lambda record: (
            int(record["priority"]),
            str(record["front"]),
            str(record["id"]),
        ),
    )


def build_wave_report(
    wave: Mapping[str, Any] | None = None,
    *,
    registry: Mapping[str, Any] | None = None,
    pylon_catalog: Mapping[str, Any] | None = None,
    fronts: Iterable[str] | None = None,
    priority_max: int = 5,
) -> dict[str, Any]:
    registry_payload = dict(registry or load_registry())
    catalog_payload = dict(
        pylon_catalog or load_pylon_catalog(registry=registry_payload)
    )
    wave_payload = dict(
        wave
        or load_wave(
            registry=registry_payload,
            pylon_catalog=catalog_payload,
        )
    )
    validate_wave(wave_payload, registry_payload, catalog_payload)
    selected = select_wave_records(
        wave_payload,
        fronts=fronts,
        priority_max=priority_max,
    )
    if not selected:
        raise ValueError("wave selection contains no records")

    front_counts = Counter(str(record["front"]) for record in selected)
    priority_counts = Counter(str(record["priority"]) for record in selected)
    state_counts = Counter(str(record["promotion_state"]) for record in selected)
    pylon_counts = Counter(
        str(pylon_id)
        for record in selected
        for pylon_id in record["pylon_ids"]
    )
    gap_counts = Counter(
        str(gap_id) for record in selected for gap_id in record["gap_ids"]
    )
    asset_counts = Counter(
        str(asset["asset_kind"])
        for record in selected
        for asset in record["commodity_assets"]
    )

    front_definitions = {
        str(front["front_id"]): front for front in wave_payload["fronts"]
    }
    front_readiness = []
    for front_id in sorted(front_counts):
        records = [record for record in selected if record["front"] == front_id]
        blockers = Counter(
            blocker
            for record in records
            for blocker in record["promotion_blockers"]
        )
        projected_pylons = sorted(
            {
                pylon_id
                for record in records
                for pylon_id in record["pylon_ids"]
            }
        )
        projected_gaps = sorted(
            {gap_id for record in records for gap_id in record["gap_ids"]}
        )
        definition = front_definitions[front_id]
        front_readiness.append(
            {
                "front_id": front_id,
                "mission": definition["mission"],
                "record_count": len(records),
                "priority_one_count": sum(
                    int(record["priority"]) == 1 for record in records
                ),
                "primary_pylon_ids": definition["primary_pylon_ids"],
                "projected_pylon_ids": projected_pylons,
                "projected_gap_ids": projected_gaps,
                "promotion_receipts": definition["promotion_receipts"],
                "blocker_frequency": dict(
                    sorted(
                        blockers.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                ),
                "promotion_ready": all(
                    record["promotion_state"] in {"intake_ready", "promoted"}
                    and not record["promotion_blockers"]
                    for record in records
                ),
            }
        )

    transactions = [
        {
            "id": record["id"],
            "actor": record["actor"],
            "project": record["project"],
            "front": record["front"],
            "priority": record["priority"],
            "promotion_state": record["promotion_state"],
            "pylon_ids": record["pylon_ids"],
            "gap_ids": record["gap_ids"],
            "first_transaction": record["first_transaction"],
            "required_receipts": record["required_receipts"],
            "promotion_blockers": record["promotion_blockers"],
            "completion_questions": record["completion_questions"],
            "source_urls": [
                source["url"] for source in record["official_sources"]
            ],
            "commodity_locators": [
                asset["locator"] for asset in record["commodity_assets"]
            ],
        }
        for record in selected
    ]

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "artifact_type": "pylon_fanout_report",
        "wave_id": wave_payload["wave_id"],
        "wave_sha256": wave_digest(wave_payload),
        "registry_sha256": registry_digest(registry_payload),
        "pylon_catalog_sha256": pylon_catalog_digest(catalog_payload),
        "selection": {
            "front_ids": sorted(set(fronts or ())),
            "priority_max": priority_max,
        },
        "summary": {
            "record_count": len(selected),
            "front_counts": dict(sorted(front_counts.items())),
            "priority_counts": dict(sorted(priority_counts.items())),
            "promotion_state_counts": dict(sorted(state_counts.items())),
            "pylon_frequency": dict(
                sorted(
                    pylon_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "gap_frequency": dict(
                sorted(
                    gap_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "asset_frequency": dict(
                sorted(
                    asset_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "promotion_ready_count": sum(
                record["promotion_state"] in {"intake_ready", "promoted"}
                and not record["promotion_blockers"]
                for record in selected
            ),
            "existing_registry_collision_count": 0,
            "all_records_commodity_only": all(
                record["dependency_mode"] == "commodity_only"
                for record in selected
            ),
        },
        "front_readiness": front_readiness,
        "transactions": transactions,
        "claim_boundary": (
            "This report qualifies public intake structure and bounded promotion "
            "transactions. It does not promote any candidate into the admitted "
            "registry, establish external participation, or prove execution, "
            "physical compute, measurement, or EVP advantage."
        ),
        "control_question": wave_payload["doctrine"]["control_question"],
    }
    report["report_sha256"] = sha256(
        canonical_json(report).encode("utf-8")
    ).hexdigest()
    return report


def write_wave_report(
    output_path: str | Path,
    report: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def format_wave_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "PYLON FAN-OUT WAVE",
        f"wave: {report['wave_id']}",
        f"wave sha256: {report['wave_sha256']}",
        f"records: {summary['record_count']}",
        f"promotion ready: {summary['promotion_ready_count']}",
        "",
        "front  records  priority-one  ready  mission",
        "-----  -------  ------------  -----  -------",
    ]
    for front in report["front_readiness"]:
        lines.append(
            f"{front['front_id']}  "
            f"{front['record_count']:>7}  "
            f"{front['priority_one_count']:>12}  "
            f"{str(front['promotion_ready']).lower():>5}  "
            f"{front['mission']}"
        )
    lines.extend(("", f"report sha256: {report['report_sha256']}"))
    return "\n".join(lines)
