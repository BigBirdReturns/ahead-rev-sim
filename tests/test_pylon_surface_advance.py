from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.congruent_shapes import load_pylon_catalog


ROOT = Path(__file__).resolve().parents[1]
PRIOR = (
    ROOT
    / "src"
    / "ahead_rev_sim"
    / "data"
    / "congruent_shape_surface_projection.json"
)
ADVANCE = (
    ROOT
    / "src"
    / "ahead_rev_sim"
    / "data"
    / "pylon_surface_advances_2026_08.json"
)
SCHEMA = ROOT / "schemas" / "pylon-surface-advance.schema.json"


def test_advances_close_open_and_partial_pylons_at_reference_tier() -> None:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    advance = json.loads(ADVANCE.read_text(encoding="utf-8"))
    prior_by_id = {item["pylon_id"]: item for item in prior["entries"]}
    advance_by_id = {item["pylon_id"]: item for item in advance["advances"]}

    assert set(advance_by_id) == {
        "scale-seam-communication-tax",
        "remote-venue-envelope",
        "causal-custody-braid",
    }
    for pylon_id in (
        "scale-seam-communication-tax",
        "remote-venue-envelope",
    ):
        item = advance_by_id[pylon_id]
        assert prior_by_id[pylon_id]["implementation_state"] == "mapped_open"
        assert item["prior_state"] == "mapped_open"
        assert item["new_state"] == "contract_implemented"
        assert item["evidence_tier"] == "software_reference"

    causal = advance_by_id["causal-custody-braid"]
    assert prior_by_id["causal-custody-braid"]["implementation_state"] == (
        "partial_contract"
    )
    assert causal["prior_state"] == "partial_contract"
    assert causal["new_state"] == "contract_implemented"
    assert causal["evidence_tier"] == "software_reference"

    for item in advance_by_id.values():
        assert item["qualified_invariants"]
        assert item["remaining_blockers"]
        assert item["proof_transaction"]


def test_effective_state_counts_match_prior_plus_advances() -> None:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    advance = json.loads(ADVANCE.read_text(encoding="utf-8"))
    states = {
        item["pylon_id"]: item["implementation_state"]
        for item in prior["entries"]
    }
    for item in advance["advances"]:
        assert states[item["pylon_id"]] == item["prior_state"]
        states[item["pylon_id"]] = item["new_state"]
    observed = Counter(states.values())
    normalized = {
        state: observed[state]
        for state in (
            "contract_implemented",
            "partial_contract",
            "mapped_open",
        )
    }
    assert normalized == advance["effective_state_counts"]
    assert advance["effective_state_counts"] == {
        "contract_implemented": 12,
        "partial_contract": 7,
        "mapped_open": 0,
    }


def test_advance_covers_known_pylons_and_existing_repo_surfaces() -> None:
    catalog = load_pylon_catalog()
    known = {item["pylon_id"] for item in catalog["pylons"]}
    advance = json.loads(ADVANCE.read_text(encoding="utf-8"))
    for item in advance["advances"]:
        assert item["pylon_id"] in known
        for reference in item["new_surface_refs"]:
            assert reference.startswith("repo://")
            path = ROOT / reference.removeprefix("repo://")
            assert path.is_file(), (item["pylon_id"], path)


def test_pylon_surface_advance_schema_accepts_current_artifact() -> None:
    artifact = json.loads(ADVANCE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)
