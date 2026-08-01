from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.commodity_registry import canonical_json, load_registry
from ahead_rev_sim.congruent_shapes import (
    PYLON_ATLAS_SCHEMA_VERSION,
    PYLON_CATALOG_SCHEMA_VERSION,
    build_congruent_shape_atlas,
    load_pylon_catalog,
    validate_pylon_catalog,
)
from ahead_rev_sim.pylons_cli import main as pylons_main


ROOT = Path(__file__).resolve().parents[1]
CATALOG_SCHEMA = ROOT / "schemas" / "congruent-shape-pylon-catalog.schema.json"
ATLAS_SCHEMA = ROOT / "schemas" / "congruent-shape-atlas.schema.json"


def _projection(atlas: dict, record_id: str) -> dict:
    return next(
        item for item in atlas["record_projections"]
        if item["record_id"] == record_id
    )


def _coverage(atlas: dict, pylon_id: str) -> dict:
    return next(
        item for item in atlas["pylon_coverage"]
        if item["pylon_id"] == pylon_id
    )


def test_catalog_is_registry_bound_and_cross_domain() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)
    assert catalog["schema_version"] == PYLON_CATALOG_SCHEMA_VERSION
    assert len(catalog["pylons"]) == 19
    assert sum(item["pylon_class"] == "foundation" for item in catalog["pylons"]) == 4
    assert sum(item["pylon_class"] == "domain" for item in catalog["pylons"]) == 15

    record_by_id = {record["id"]: record for record in registry["records"]}
    registry_gaps = {item["gap_id"] for item in registry["gap_taxonomy"]}
    catalog_gaps = {
        gap
        for pylon in catalog["pylons"]
        for gap in pylon["matched_gap_ids"]
    }
    assert catalog_gaps == registry_gaps
    for pylon in catalog["pylons"]:
        witness_categories = {
            record_by_id[record_id]["category"]
            for record_id in pylon["witness_record_ids"]
        }
        assert len(witness_categories) >= 2
        assert pylon["proof_transaction"]
        assert pylon["authority_location"]
        assert pylon["forbidden_collapse"]


def test_full_atlas_covers_every_record_gap_and_design_plane() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)
    atlas = build_congruent_shape_atlas(registry, catalog)
    summary = atlas["summary"]

    assert atlas["schema_version"] == PYLON_ATLAS_SCHEMA_VERSION
    assert summary["record_count"] == 73
    assert summary["registry_record_count"] == 73
    assert summary["pylon_count"] == 19
    assert summary["foundation_pylon_count"] == 4
    assert summary["domain_pylon_count"] == 15
    assert summary["registry_gap_count"] == 26
    assert summary["selected_gap_count"] == 26
    assert summary["selected_gap_coverage_complete"] is True
    assert summary["all_selected_records_covered"] is True
    assert summary["minimum_foundation_pylons_per_record"] == 4
    assert summary["minimum_domain_pylons_per_record"] >= 2
    assert summary["cross_domain_witness_pair_count"] >= 19
    assert len(summary["design_plane_counts"]) == 19

    assert len(atlas["record_projections"]) == 73
    assert set(atlas["gap_to_pylon_ids"]) == {
        item["gap_id"] for item in registry["gap_taxonomy"]
    }
    assert all(atlas["gap_to_pylon_ids"].values())
    for projection in atlas["record_projections"]:
        assert len(projection["foundation_pylon_ids"]) == 4
        assert len(projection["domain_pylon_ids"]) >= 2
        assert len(projection["primary_domain_pylon_ids"]) >= 2
        assert projection["matches"]


def test_curated_cross_ecosystem_shapes_land_on_the_same_pylons() -> None:
    atlas = build_congruent_shape_atlas()

    vaire = _projection(atlas, "vaire-arc-evp")
    mlcommons = _projection(atlas, "mlcommons-power")
    assert "evp-pareto-frontier" in vaire["domain_pylon_ids"]
    assert "evp-pareto-frontier" in mlcommons["domain_pylon_ids"]

    nir = _projection(atlas, "neuromorphic-nir-synfire")
    circt = _projection(atlas, "circt-mlir")
    assert "semantic-ir-lowering-sandwich" in nir["domain_pylon_ids"]
    assert "semantic-ir-lowering-sandwich" in circt["domain_pylon_ids"]

    openebl = _projection(atlas, "openebl-photonics")
    openroad = _projection(atlas, "openroad-openlane")
    assert "materialization-funnel" in openebl["domain_pylon_ids"]
    assert "materialization-funnel" in openroad["domain_pylon_ids"]

    brainscales = _projection(atlas, "ebrains-brainscales2")
    aria = _projection(atlas, "aria-scaling-inference-lab")
    assert "remote-venue-envelope" in brainscales["domain_pylon_ids"]
    assert "remote-venue-envelope" in aria["domain_pylon_ids"]

    thermox = _projection(atlas, "normal-thermox")
    reservoirpy = _projection(atlas, "reservoirpy")
    assert "reference-twin-substitution" in thermox["domain_pylon_ids"]
    assert "reference-twin-substitution" in reservoirpy["domain_pylon_ids"]


def test_pylon_witness_pairs_preserve_category_contrast() -> None:
    atlas = build_congruent_shape_atlas()
    for coverage in atlas["pylon_coverage"]:
        assert coverage["cross_domain_witness_pairs"]
        for pair in coverage["cross_domain_witness_pairs"]:
            assert pair["left"]["category"] != pair["right"]["category"]
            assert pair["congruence_basis"] == coverage["invariant"]

    evp = _coverage(atlas, "evp-pareto-frontier")
    witness_ids = {
        pair[side]["record_id"]
        for pair in evp["cross_domain_witness_pairs"]
        for side in ("left", "right")
    }
    assert "vaire-arc-evp" in witness_ids
    assert {"mlcommons-power", "spec-ptdaemon"} & witness_ids


def test_atlas_is_deterministic_and_sealed() -> None:
    first = build_congruent_shape_atlas()
    second = build_congruent_shape_atlas()
    assert first == second
    claimed = first.pop("atlas_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()


def test_catalog_and_atlas_schemas_accept_generated_artifacts() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)
    atlas = build_congruent_shape_atlas(registry, catalog)

    catalog_schema = json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8"))
    atlas_schema = json.loads(ATLAS_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(catalog_schema)
    Draft202012Validator.check_schema(atlas_schema)
    Draft202012Validator(catalog_schema).validate(catalog)
    Draft202012Validator(atlas_schema).validate(atlas)


def test_catalog_refuses_unknown_gaps_witnesses_and_cycles() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)

    unknown_gap = deepcopy(catalog)
    unknown_gap["pylons"][0]["matched_gap_ids"].append("imaginary_gap")
    with pytest.raises(ValueError, match="unknown gaps"):
        validate_pylon_catalog(unknown_gap, registry)

    unknown_witness = deepcopy(catalog)
    unknown_witness["pylons"][0]["witness_record_ids"][0] = "imaginary-record"
    with pytest.raises(ValueError, match="unknown witness records"):
        validate_pylon_catalog(unknown_witness, registry)

    cycle = deepcopy(catalog)
    cycle["pylons"][0]["upstream_pylon_ids"] = [cycle["pylons"][1]["pylon_id"]]
    cycle["pylons"][1]["upstream_pylon_ids"] = [cycle["pylons"][0]["pylon_id"]]
    with pytest.raises(ValueError, match="dependency cycle"):
        validate_pylon_catalog(cycle, registry)


def test_category_selection_retains_complete_local_coverage() -> None:
    atlas = build_congruent_shape_atlas(
        categories=["photonic_interconnect", "chiplet_interconnect"],
        priority_max=5,
    )
    assert atlas["summary"]["record_count"] > 1
    assert atlas["summary"]["all_selected_records_covered"] is True
    assert atlas["summary"]["selected_gap_coverage_complete"] is True
    assert set(atlas["selection"]["category_ids"]) == {
        "photonic_interconnect",
        "chiplet_interconnect",
    }
    assert {
        projection["category"] for projection in atlas["record_projections"]
    } <= {"photonic_interconnect", "chiplet_interconnect"}


def test_pylons_cli_writes_complete_atlas(tmp_path: Path) -> None:
    output = tmp_path / "pylons.json"
    assert pylons_main(
        [
            "--out",
            str(output),
            "--format",
            "json",
            "--require-complete",
        ]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["record_count"] == 73
    assert payload["summary"]["all_selected_records_covered"] is True
    assert len(payload["atlas_sha256"]) == 64
