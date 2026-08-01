from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.congruent_shapes import load_pylon_catalog


ROOT = Path(__file__).resolve().parents[1]
PROJECTION = (
    ROOT
    / "src"
    / "ahead_rev_sim"
    / "data"
    / "congruent_shape_surface_projection.json"
)
SCHEMA = ROOT / "schemas" / "congruent-shape-surface-projection.schema.json"


def test_surface_projection_covers_every_pylon_exactly_once() -> None:
    catalog = load_pylon_catalog()
    projection = json.loads(PROJECTION.read_text(encoding="utf-8"))
    catalog_ids = {item["pylon_id"] for item in catalog["pylons"]}
    entry_ids = [item["pylon_id"] for item in projection["entries"]]

    assert projection["schema_version"] == (
        "ahead.congruent-shape-surface-projection/v0.1"
    )
    assert len(entry_ids) == 19
    assert len(set(entry_ids)) == 19
    assert set(entry_ids) == catalog_ids

    states = Counter(item["implementation_state"] for item in projection["entries"])
    assert states == {
        "contract_implemented": 9,
        "partial_contract": 8,
        "mapped_open": 2,
    }


def test_every_declared_repo_surface_exists_and_every_pylon_has_open_work() -> None:
    projection = json.loads(PROJECTION.read_text(encoding="utf-8"))
    for entry in projection["entries"]:
        assert entry["implemented_invariants"]
        assert entry["open_invariants"]
        assert entry["next_design_transaction"]
        assert entry["control_question"]
        for reference in entry["current_surface_refs"]:
            assert reference.startswith("repo://")
            path = ROOT / reference.removeprefix("repo://")
            assert path.is_file(), f"missing surface for {entry['pylon_id']}: {path}"


def test_surface_projection_schema_accepts_current_map() -> None:
    projection = json.loads(PROJECTION.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(projection)


def test_critical_design_order_is_reflected_in_current_surfaces() -> None:
    projection = json.loads(PROJECTION.read_text(encoding="utf-8"))
    entries = {item["pylon_id"]: item for item in projection["entries"]}

    assert entries["authority-outside-provider"]["implementation_state"] == (
        "contract_implemented"
    )
    assert "repo://src/ahead_rev_sim/provider_hitch.py" in entries[
        "authority-outside-provider"
    ]["current_surface_refs"]

    assert entries["compute-vs-sensing-separation"]["implementation_state"] == (
        "contract_implemented"
    )
    assert "repo://src/ahead_rev_sim/physical_assay.py" in entries[
        "compute-vs-sensing-separation"
    ]["current_surface_refs"]

    assert entries["complete-system-envelope"]["implementation_state"] == (
        "partial_contract"
    )
    assert entries["evp-pareto-frontier"]["implementation_state"] == (
        "contract_implemented"
    )
    assert "measured complete-system EVP candidate" in entries[
        "evp-pareto-frontier"
    ]["open_invariants"]

    assert entries["scale-seam-communication-tax"]["implementation_state"] == (
        "mapped_open"
    )
    assert entries["remote-venue-envelope"]["implementation_state"] == (
        "mapped_open"
    )
