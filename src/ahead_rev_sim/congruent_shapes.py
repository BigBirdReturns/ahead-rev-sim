"""Derive scale-invariant design pylons from the commodity ecosystem registry.

A congruent shape is a repeated causal transaction across unlike substrates,
scales, and institutions.  The atlas turns those repetitions into explicit
interface, custody, failure, measurement, and succession constraints.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from importlib.resources import files
from itertools import combinations
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .commodity_registry import canonical_json, load_registry, registry_digest

PYLON_CATALOG_RESOURCE = "data/congruent_shape_pylons.json"
PYLON_CATALOG_SCHEMA_VERSION = "ahead.congruent-shape-pylon-catalog/v0.1"
PYLON_ATLAS_SCHEMA_VERSION = "ahead.congruent-shape-atlas/v0.1"


def default_pylon_catalog_path() -> Path:
    resource = files("ahead_rev_sim").joinpath(PYLON_CATALOG_RESOURCE)
    return Path(str(resource))


def pylon_catalog_digest(catalog: Mapping[str, Any]) -> str:
    return sha256(canonical_json(catalog).encode("utf-8")).hexdigest()


def load_pylon_catalog(
    path: str | Path | None = None,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else default_pylon_catalog_path()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("congruent-shape pylon catalog must be a JSON object")
    validate_pylon_catalog(payload, registry or load_registry())
    return payload


def _nonempty_text(value: Any, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def _unique_strings(
    value: Any,
    field: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be an array")
    normalized = [_nonempty_text(item, f"{field}[]") for item in value]
    if not allow_empty and not normalized:
        raise ValueError(f"{field} must contain at least one entry")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} entries must be unique")
    return normalized


def _validate_pylon_dag(pylons: Mapping[str, Mapping[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(pylon_id: str) -> None:
        if pylon_id in visited:
            return
        if pylon_id in visiting:
            raise ValueError(f"congruent-shape pylon dependency cycle at {pylon_id}")
        visiting.add(pylon_id)
        for upstream in pylons[pylon_id]["upstream_pylon_ids"]:
            if upstream not in pylons:
                raise ValueError(f"{pylon_id}: unknown upstream pylon {upstream}")
            visit(upstream)
        visiting.remove(pylon_id)
        visited.add(pylon_id)

    for pylon_id in pylons:
        visit(pylon_id)


def validate_pylon_catalog(
    catalog: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> None:
    if catalog.get("schema_version") != PYLON_CATALOG_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported pylon catalog schema: {catalog.get('schema_version')!r}"
        )
    if catalog.get("artifact_type") != "congruent_shape_pylon_catalog":
        raise ValueError("pylon catalog artifact_type is invalid")
    doctrine = catalog.get("doctrine")
    if not isinstance(doctrine, Mapping):
        raise ValueError("pylon catalog doctrine must be an object")
    for field in ("statement", "shape_definition", "admission_rule", "control_question"):
        _nonempty_text(doctrine.get(field), f"doctrine.{field}")

    minimum_foundation = catalog.get("minimum_foundation_pylons_per_record")
    minimum_domain = catalog.get("minimum_domain_pylons_per_record")
    if not isinstance(minimum_foundation, int) or minimum_foundation < 1:
        raise ValueError("minimum_foundation_pylons_per_record must be positive")
    if not isinstance(minimum_domain, int) or minimum_domain < 1:
        raise ValueError("minimum_domain_pylons_per_record must be positive")

    records = registry.get("records")
    gaps = registry.get("gap_taxonomy")
    if not isinstance(records, list) or not records:
        raise ValueError("registry records must be present before pylon validation")
    if not isinstance(gaps, list) or not gaps:
        raise ValueError("registry gap taxonomy must be present before pylon validation")
    record_by_id = {str(record["id"]): record for record in records}
    category_ids = {str(record["category"]) for record in records}
    gap_ids = {str(item["gap_id"]) for item in gaps}

    raw_pylons = catalog.get("pylons")
    if not isinstance(raw_pylons, list) or not raw_pylons:
        raise ValueError("pylon catalog must declare pylons")

    pylons: dict[str, Mapping[str, Any]] = {}
    foundation_count = 0
    domain_count = 0
    catalog_gap_coverage: set[str] = set()
    for raw in raw_pylons:
        if not isinstance(raw, Mapping):
            raise ValueError("every pylon must be a JSON object")
        pylon_id = _nonempty_text(raw.get("pylon_id"), "pylon_id")
        if pylon_id in pylons:
            raise ValueError(f"duplicate pylon id: {pylon_id}")
        pylon_class = _nonempty_text(raw.get("pylon_class"), f"{pylon_id}.pylon_class")
        if pylon_class not in {"foundation", "domain"}:
            raise ValueError(f"{pylon_id}: pylon_class must be foundation or domain")
        if pylon_class == "foundation":
            foundation_count += 1
        else:
            domain_count += 1

        for field in (
            "name",
            "design_plane",
            "shape_notation",
            "invariant",
            "authority_location",
            "forbidden_collapse",
            "proof_transaction",
        ):
            _nonempty_text(raw.get(field), f"{pylon_id}.{field}")
        for field in (
            "scale_domains",
            "required_surfaces",
            "failure_modes",
            "design_consequences",
            "witness_record_ids",
        ):
            _unique_strings(raw.get(field), f"{pylon_id}.{field}")
        _unique_strings(
            raw.get("category_ids", []),
            f"{pylon_id}.category_ids",
            allow_empty=True,
        )
        _unique_strings(
            raw.get("matched_gap_ids", []),
            f"{pylon_id}.matched_gap_ids",
            allow_empty=pylon_class == "foundation",
        )
        _unique_strings(
            raw.get("upstream_pylon_ids", []),
            f"{pylon_id}.upstream_pylon_ids",
            allow_empty=True,
        )
        minimum_gap_matches = raw.get("minimum_gap_matches")
        if not isinstance(minimum_gap_matches, int) or minimum_gap_matches < 0:
            raise ValueError(f"{pylon_id}.minimum_gap_matches must be non-negative")
        if pylon_class == "foundation" and minimum_gap_matches != 0:
            raise ValueError(f"{pylon_id}: foundation pylons must use zero gap threshold")
        if pylon_class == "domain" and minimum_gap_matches < 1:
            raise ValueError(f"{pylon_id}: domain pylons require a positive gap threshold")

        unknown_categories = set(map(str, raw["category_ids"])) - category_ids
        if unknown_categories:
            raise ValueError(
                f"{pylon_id}: unknown categories {sorted(unknown_categories)}"
            )
        unknown_gaps = set(map(str, raw["matched_gap_ids"])) - gap_ids
        if unknown_gaps:
            raise ValueError(f"{pylon_id}: unknown gaps {sorted(unknown_gaps)}")
        catalog_gap_coverage.update(map(str, raw["matched_gap_ids"]))

        witnesses = list(map(str, raw["witness_record_ids"]))
        unknown_witnesses = set(witnesses) - set(record_by_id)
        if unknown_witnesses:
            raise ValueError(
                f"{pylon_id}: unknown witness records {sorted(unknown_witnesses)}"
            )
        witness_categories = {str(record_by_id[item]["category"]) for item in witnesses}
        if len(witness_categories) < 2:
            raise ValueError(
                f"{pylon_id}: witnesses must span at least two ecosystem categories"
            )
        pylons[pylon_id] = raw

    if foundation_count < minimum_foundation:
        raise ValueError("catalog does not contain enough foundation pylons")
    if domain_count < minimum_domain:
        raise ValueError("catalog does not contain enough domain pylons")
    missing_gaps = gap_ids - catalog_gap_coverage
    if missing_gaps:
        raise ValueError(f"pylon catalog leaves registry gaps uncovered: {sorted(missing_gaps)}")
    _validate_pylon_dag(pylons)


def _match_pylon(
    record: Mapping[str, Any],
    pylon: Mapping[str, Any],
) -> dict[str, Any]:
    record_id = str(record["id"])
    category = str(record["category"])
    record_gaps = set(map(str, record["system_gaps"]))
    pylon_gaps = set(map(str, pylon["matched_gap_ids"]))
    overlap = sorted(record_gaps & pylon_gaps)
    category_match = category in set(map(str, pylon["category_ids"]))
    witness_match = record_id in set(map(str, pylon["witness_record_ids"]))
    score = len(overlap) * 10 + int(category_match) * 25 + int(witness_match) * 50
    strong = bool(
        witness_match
        or category_match
        or len(overlap) >= int(pylon["minimum_gap_matches"])
    )
    reasons: list[str] = []
    if witness_match:
        reasons.append("curated_cross_domain_witness")
    if category_match:
        reasons.append("ecosystem_category_match")
    if overlap:
        reasons.append("shared_system_gaps")
    return {
        "pylon_id": pylon["pylon_id"],
        "score": score,
        "strength": "strong" if strong else "overlap_candidate",
        "matched_gap_ids": overlap,
        "category_match": category_match,
        "witness_match": witness_match,
        "reasons": reasons,
    }


def _cross_domain_witness_pairs(
    pylon: Mapping[str, Any],
    record_by_id: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    pylon_gaps = set(map(str, pylon["matched_gap_ids"]))
    candidates: list[tuple[int, str, str, dict[str, Any]]] = []
    for left_id, right_id in combinations(map(str, pylon["witness_record_ids"]), 2):
        left = record_by_id[left_id]
        right = record_by_id[right_id]
        left_category = str(left["category"])
        right_category = str(right["category"])
        if left_category == right_category:
            continue
        shared_gaps = sorted(
            set(map(str, left["system_gaps"]))
            & set(map(str, right["system_gaps"]))
        )
        pylon_overlap = sorted(set(shared_gaps) & pylon_gaps)
        pair = {
            "left": {
                "record_id": left_id,
                "actor": left["actor"],
                "project": left["project"],
                "category": left_category,
            },
            "right": {
                "record_id": right_id,
                "actor": right["actor"],
                "project": right["project"],
                "category": right_category,
            },
            "shared_system_gap_ids": shared_gaps,
            "pylon_gap_overlap_ids": pylon_overlap,
            "congruence_basis": pylon["invariant"],
        }
        candidates.append(
            (-len(pylon_overlap), left_id, right_id, pair)
        )
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in candidates[:limit]]


def build_congruent_shape_atlas(
    registry: Mapping[str, Any] | None = None,
    catalog: Mapping[str, Any] | None = None,
    *,
    priority_max: int = 5,
    categories: Iterable[str] | None = None,
) -> dict[str, Any]:
    if not 1 <= priority_max <= 5:
        raise ValueError("priority_max must be in the range 1..5")
    registry_payload = dict(registry or load_registry())
    catalog_payload = dict(
        catalog or load_pylon_catalog(registry=registry_payload)
    )
    validate_pylon_catalog(catalog_payload, registry_payload)

    selected_categories = set(categories or ())
    known_categories = {str(record["category"]) for record in registry_payload["records"]}
    unknown_categories = selected_categories - known_categories
    if unknown_categories:
        raise ValueError(f"unknown ecosystem categories: {sorted(unknown_categories)}")

    records = [
        record
        for record in registry_payload["records"]
        if int(record["ingestion_policy"]["priority"]) <= priority_max
        and (
            not selected_categories
            or str(record["category"]) in selected_categories
        )
    ]
    records.sort(
        key=lambda record: (
            int(record["ingestion_policy"]["priority"]),
            str(record["category"]),
            str(record["id"]),
        )
    )
    if not records:
        raise ValueError("congruent-shape selection contains no commodity records")

    all_record_by_id = {
        str(record["id"]): record for record in registry_payload["records"]
    }
    selected_record_by_id = {str(record["id"]): record for record in records}
    foundations = [
        pylon for pylon in catalog_payload["pylons"]
        if pylon["pylon_class"] == "foundation"
    ]
    domains = [
        pylon for pylon in catalog_payload["pylons"]
        if pylon["pylon_class"] == "domain"
    ]
    minimum_domain = int(catalog_payload["minimum_domain_pylons_per_record"])

    record_projections: list[dict[str, Any]] = []
    assigned_records: dict[str, set[str]] = {
        str(pylon["pylon_id"]): set() for pylon in catalog_payload["pylons"]
    }
    category_to_pylons: dict[str, set[str]] = {
        category: set() for category in known_categories
    }
    gap_to_pylons: dict[str, set[str]] = {
        str(item["gap_id"]): set() for item in registry_payload["gap_taxonomy"]
    }

    for record in records:
        foundation_ids = [str(pylon["pylon_id"]) for pylon in foundations]
        for pylon_id in foundation_ids:
            assigned_records[pylon_id].add(str(record["id"]))

        matches = [_match_pylon(record, pylon) for pylon in domains]
        strong_matches = [match for match in matches if match["strength"] == "strong"]
        strong_ids = {str(match["pylon_id"]) for match in strong_matches}
        if len(strong_matches) < minimum_domain:
            fallback = sorted(
                (
                    match for match in matches
                    if match["pylon_id"] not in strong_ids and match["score"] > 0
                ),
                key=lambda match: (-int(match["score"]), str(match["pylon_id"])),
            )
            for match in fallback[: minimum_domain - len(strong_matches)]:
                match = dict(match)
                match["strength"] = "fallback_overlap"
                match["reasons"] = list(match["reasons"]) + [
                    "minimum_domain_coverage"
                ]
                strong_matches.append(match)
        strong_matches.sort(
            key=lambda match: (-int(match["score"]), str(match["pylon_id"]))
        )
        if len(strong_matches) < minimum_domain:
            raise ValueError(
                f"{record['id']}: fewer than {minimum_domain} domain pylons matched"
            )

        domain_ids = [str(match["pylon_id"]) for match in strong_matches]
        for pylon_id in domain_ids:
            assigned_records[pylon_id].add(str(record["id"]))
            category_to_pylons[str(record["category"])].add(pylon_id)
        for pylon_id in foundation_ids:
            category_to_pylons[str(record["category"])].add(pylon_id)
        for gap_id in map(str, record["system_gaps"]):
            for match in strong_matches:
                if gap_id in match["matched_gap_ids"]:
                    gap_to_pylons[gap_id].add(str(match["pylon_id"]))
            for pylon in foundations:
                if gap_id in set(map(str, pylon["matched_gap_ids"])):
                    gap_to_pylons[gap_id].add(str(pylon["pylon_id"]))

        record_projections.append(
            {
                "record_id": record["id"],
                "actor": record["actor"],
                "project": record["project"],
                "category": record["category"],
                "priority": record["ingestion_policy"]["priority"],
                "system_gap_ids": record["system_gaps"],
                "foundation_pylon_ids": foundation_ids,
                "domain_pylon_ids": domain_ids,
                "primary_domain_pylon_ids": domain_ids[:5],
                "matches": strong_matches,
                "design_control_question": (
                    "Which matched pylon invariants must remain stable when this "
                    "commodity is replaced, scaled, refused, or measured?"
                ),
            }
        )

    pylon_coverage: list[dict[str, Any]] = []
    design_plane_counts: Counter[str] = Counter()
    all_atlas_gap_ids: set[str] = set()
    cross_domain_pair_count = 0
    for pylon in catalog_payload["pylons"]:
        pylon_id = str(pylon["pylon_id"])
        covered_ids = sorted(assigned_records[pylon_id])
        covered_records = [selected_record_by_id[item] for item in covered_ids]
        covered_categories = sorted(
            {str(record["category"]) for record in covered_records}
        )
        observed_gaps = sorted(
            set(map(str, pylon["matched_gap_ids"]))
            & {
                str(gap)
                for record in covered_records
                for gap in record["system_gaps"]
            }
        )
        all_atlas_gap_ids.update(observed_gaps)
        witness_pairs = _cross_domain_witness_pairs(
            pylon,
            all_record_by_id,
        )
        cross_domain_pair_count += len(witness_pairs)
        design_plane_counts[str(pylon["design_plane"])] += 1
        pylon_coverage.append(
            {
                "pylon_id": pylon_id,
                "name": pylon["name"],
                "pylon_class": pylon["pylon_class"],
                "design_plane": pylon["design_plane"],
                "record_count": len(covered_ids),
                "record_ids": covered_ids,
                "category_count": len(covered_categories),
                "category_ids": covered_categories,
                "observed_gap_ids": observed_gaps,
                "cross_domain_witness_pairs": witness_pairs,
                "shape_notation": pylon["shape_notation"],
                "invariant": pylon["invariant"],
                "authority_location": pylon["authority_location"],
                "forbidden_collapse": pylon["forbidden_collapse"],
                "design_consequences": pylon["design_consequences"],
                "proof_transaction": pylon["proof_transaction"],
                "upstream_pylon_ids": pylon["upstream_pylon_ids"],
            }
        )

    registry_gap_ids = {
        str(item["gap_id"]) for item in registry_payload["gap_taxonomy"]
    }
    selected_gap_ids = {
        str(gap)
        for record in records
        for gap in record["system_gaps"]
    }
    missing_selected_gap_pylons = {
        gap_id for gap_id in selected_gap_ids
        if not gap_to_pylons[gap_id]
    }
    if missing_selected_gap_pylons:
        raise ValueError(
            "selected records contain gaps without assigned domain pylons: "
            f"{sorted(missing_selected_gap_pylons)}"
        )

    foundation_counts = [
        len(projection["foundation_pylon_ids"])
        for projection in record_projections
    ]
    domain_counts = [
        len(projection["domain_pylon_ids"])
        for projection in record_projections
    ]
    primary_counts = Counter(
        pylon_id
        for projection in record_projections
        for pylon_id in projection["primary_domain_pylon_ids"]
    )
    pylon_edges = sorted(
        (
            {
                "from_pylon_id": str(upstream),
                "to_pylon_id": str(pylon["pylon_id"]),
                "edge_kind": "design_dependency",
            }
            for pylon in catalog_payload["pylons"]
            for upstream in pylon["upstream_pylon_ids"]
        ),
        key=lambda edge: (edge["from_pylon_id"], edge["to_pylon_id"]),
    )

    atlas: dict[str, Any] = {
        "schema_version": PYLON_ATLAS_SCHEMA_VERSION,
        "artifact_type": "congruent_shape_atlas",
        "registry_sha256": registry_digest(registry_payload),
        "catalog_sha256": pylon_catalog_digest(catalog_payload),
        "selection": {
            "priority_max": priority_max,
            "category_ids": sorted(selected_categories),
        },
        "summary": {
            "record_count": len(records),
            "registry_record_count": len(registry_payload["records"]),
            "pylon_count": len(catalog_payload["pylons"]),
            "foundation_pylon_count": len(foundations),
            "domain_pylon_count": len(domains),
            "design_plane_counts": dict(sorted(design_plane_counts.items())),
            "ecosystem_category_count": len(
                {str(record["category"]) for record in records}
            ),
            "registry_gap_count": len(registry_gap_ids),
            "selected_gap_count": len(selected_gap_ids),
            "selected_gap_coverage_complete": not missing_selected_gap_pylons,
            "minimum_foundation_pylons_per_record": min(foundation_counts),
            "minimum_domain_pylons_per_record": min(domain_counts),
            "maximum_domain_pylons_per_record": max(domain_counts),
            "cross_domain_witness_pair_count": cross_domain_pair_count,
            "records_by_primary_pylon": dict(
                sorted(primary_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            "all_selected_records_covered": (
                len(record_projections) == len(records)
                and all(domain_counts)
                and all(foundation_counts)
            ),
        },
        "design_spine": [
            "bounded-transition-spine",
            "authority-outside-provider",
            "negative-space-refusal-ledger",
            "provenance-succession-chain",
            "semantic-ir-lowering-sandwich",
            "self-describing-cartridge",
            "lifecycle-refusal-state-machine",
            "causal-custody-braid",
            "reference-twin-substitution",
            "model-fidelity-staircase",
            "compute-vs-sensing-separation",
            "composition-fabric",
            "scale-seam-communication-tax",
            "materialization-funnel",
            "complete-system-envelope",
            "evp-pareto-frontier",
            "remote-venue-envelope",
            "intermittent-commit-recovery",
            "registry-gap-transaction-dispatch"
        ],
        "pylon_edges": pylon_edges,
        "pylon_coverage": pylon_coverage,
        "record_projections": record_projections,
        "gap_to_pylon_ids": {
            gap_id: sorted(pylon_ids)
            for gap_id, pylon_ids in sorted(gap_to_pylons.items())
            if gap_id in selected_gap_ids
        },
        "category_to_pylon_ids": {
            category: sorted(pylon_ids)
            for category, pylon_ids in sorted(category_to_pylons.items())
            if category in {str(record["category"]) for record in records}
        },
        "claim_boundary": (
            "The atlas establishes recurring causal shapes in the registered public "
            "ecosystem. It guides architecture and proof transactions. It does not "
            "establish that any witness actor implemented ahead-rev-sim, accepted a "
            "hitch, supplied evidence, or achieved physical or EVP advantage."
        ),
        "control_question": catalog_payload["doctrine"]["control_question"],
    }
    atlas["atlas_sha256"] = sha256(
        canonical_json(atlas).encode("utf-8")
    ).hexdigest()
    return atlas


def write_congruent_shape_atlas(
    output_path: str | Path,
    atlas: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(atlas, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def format_congruent_shape_atlas(atlas: Mapping[str, Any]) -> str:
    summary = atlas["summary"]
    lines = [
        "CONGRUENT SHAPE PYLON ATLAS",
        f"registry: {atlas['registry_sha256']}",
        f"catalog: {atlas['catalog_sha256']}",
        f"records: {summary['record_count']}",
        f"pylons: {summary['pylon_count']} "
        f"({summary['foundation_pylon_count']} foundation, "
        f"{summary['domain_pylon_count']} domain)",
        f"categories: {summary['ecosystem_category_count']}",
        f"selected gaps: {summary['selected_gap_count']}",
        "",
        "pylon  class  records  categories  proof transaction",
        "------  -----  -------  ----------  -----------------",
    ]
    for coverage in atlas["pylon_coverage"]:
        lines.append(
            f"{coverage['pylon_id']}  {coverage['pylon_class']}  "
            f"{coverage['record_count']}  {coverage['category_count']}  "
            f"{coverage['proof_transaction']}"
        )
    lines.extend(("", f"atlas sha256: {atlas['atlas_sha256']}"))
    return "\n".join(lines)
