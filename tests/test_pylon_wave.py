from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.commodity_registry import canonical_json, load_registry
from ahead_rev_sim.congruent_shapes import load_pylon_catalog
from ahead_rev_sim.pylon_wave import (
    REPORT_SCHEMA_VERSION,
    WAVE_SCHEMA_VERSION,
    build_wave_report,
    default_wave_path,
    load_wave,
    validate_wave,
)
from ahead_rev_sim.pylon_wave_cli import main as wave_main


ROOT = Path(__file__).resolve().parents[1]
WAVE_SCHEMA = ROOT / "schemas" / "pylon-fanout-wave.schema.json"
REPORT_SCHEMA = ROOT / "schemas" / "pylon-fanout-report.schema.json"


def test_wave_is_packaged_separate_and_pylon_bound() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)
    wave = load_wave(registry=registry, pylon_catalog=catalog)

    assert default_wave_path().is_file()
    assert wave["schema_version"] == WAVE_SCHEMA_VERSION
    assert wave["artifact_type"] == "pylon_fanout_wave"
    assert wave["record_count"] == 25
    assert Counter(record["front"] for record in wave["records"]) == {
        "scale_seam": 10,
        "remote_venue": 8,
        "causal_custody": 7,
    }
    assert Counter(record["priority"] for record in wave["records"]) == {
        1: 13,
        2: 10,
        3: 2,
    }
    assert all(
        record["dependency_mode"] == "commodity_only"
        for record in wave["records"]
    )

    admitted_ids = {record["id"] for record in registry["records"]}
    wave_ids = {record["id"] for record in wave["records"]}
    assert admitted_ids.isdisjoint(wave_ids)
    assert len(wave_ids) == 25

    pylon_ids = {item["pylon_id"] for item in catalog["pylons"]}
    gap_ids = {item["gap_id"] for item in registry["gap_taxonomy"]}
    for record in wave["records"]:
        assert len(record["pylon_ids"]) >= 2
        assert set(record["pylon_ids"]) <= pylon_ids
        assert len(record["gap_ids"]) >= 2
        assert set(record["gap_ids"]) <= gap_ids
        assert record["promotion_state"] == "candidate"
        assert record["promotion_blockers"]


def test_wave_and_report_validate_against_draft_2020_12() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)
    wave = load_wave(registry=registry, pylon_catalog=catalog)
    report = build_wave_report(
        wave,
        registry=registry,
        pylon_catalog=catalog,
    )

    wave_schema = json.loads(WAVE_SCHEMA.read_text(encoding="utf-8"))
    report_schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(wave_schema)
    Draft202012Validator.check_schema(report_schema)
    Draft202012Validator(wave_schema).validate(wave)
    Draft202012Validator(report_schema).validate(report)


def test_full_report_is_deterministic_sealed_and_not_promoted() -> None:
    first = build_wave_report()
    second = build_wave_report()
    assert first == second
    assert first["schema_version"] == REPORT_SCHEMA_VERSION
    assert first["summary"]["record_count"] == 25
    assert first["summary"]["front_counts"] == {
        "causal_custody": 7,
        "remote_venue": 8,
        "scale_seam": 10,
    }
    assert first["summary"]["priority_counts"] == {
        "1": 13,
        "2": 10,
        "3": 2,
    }
    assert first["summary"]["promotion_state_counts"] == {
        "candidate": 25
    }
    assert first["summary"]["promotion_ready_count"] == 0
    assert first["summary"]["existing_registry_collision_count"] == 0
    assert first["summary"]["all_records_commodity_only"] is True
    assert all(not front["promotion_ready"] for front in first["front_readiness"])

    claimed = first.pop("report_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()


def test_wave_expands_the_two_open_pylons_and_causal_dependencies() -> None:
    report = build_wave_report()
    pylon_frequency = report["summary"]["pylon_frequency"]
    assert pylon_frequency["scale-seam-communication-tax"] >= 6
    assert pylon_frequency["remote-venue-envelope"] >= 8
    assert pylon_frequency["causal-custody-braid"] >= 7
    assert pylon_frequency["reference-twin-substitution"] >= 5
    assert pylon_frequency["provenance-succession-chain"] >= 8

    readiness = {item["front_id"]: item for item in report["front_readiness"]}
    assert readiness["scale_seam"]["record_count"] == 10
    assert readiness["remote_venue"]["record_count"] == 8
    assert readiness["causal_custody"]["record_count"] == 7
    assert "scale-seam-communication-tax" in readiness["scale_seam"][
        "primary_pylon_ids"
    ]
    assert "remote-venue-envelope" in readiness["remote_venue"][
        "primary_pylon_ids"
    ]
    assert "causal-custody-braid" in readiness["causal_custody"][
        "primary_pylon_ids"
    ]


def test_priority_one_report_is_the_immediate_wave_floor() -> None:
    report = build_wave_report(priority_max=1)
    assert report["summary"]["record_count"] == 13
    assert report["summary"]["priority_counts"] == {"1": 13}
    ids = {item["id"] for item in report["transactions"]}
    assert {
        "mlcommons-chakra-traces",
        "astra-sim-scale-model",
        "gem5-garnet-scale-model",
        "firesim-scaleout-rtl",
        "firemarshal-workload-bundles",
        "accelergy-energy-estimator",
        "three-d-ice-thermal-model",
        "ga4gh-wes-portable-workflows",
        "ga4gh-tes-portable-tasks",
        "ro-crate-1-3-audit-bundles",
        "opentelemetry-causal-telemetry",
        "perfetto-causal-trace",
        "linuxptp-white-rabbit-timebase",
    } == ids


def test_front_selection_does_not_change_registry_or_catalog_authority() -> None:
    full = build_wave_report()
    selected = build_wave_report(
        fronts=["scale_seam", "causal_custody"],
        priority_max=5,
    )
    assert selected["summary"]["record_count"] == 17
    assert selected["selection"]["front_ids"] == [
        "causal_custody",
        "scale_seam",
    ]
    assert selected["registry_sha256"] == full["registry_sha256"]
    assert selected["pylon_catalog_sha256"] == full["pylon_catalog_sha256"]
    assert selected["wave_sha256"] == full["wave_sha256"]


def test_validator_rejects_registry_collision_unknown_pylon_and_false_promotion() -> None:
    registry = load_registry()
    catalog = load_pylon_catalog(registry=registry)
    wave = load_wave(registry=registry, pylon_catalog=catalog)

    collision = deepcopy(wave)
    collision["records"][0]["id"] = registry["records"][0]["id"]
    with pytest.raises(ValueError, match="collides with admitted registry"):
        validate_wave(collision, registry, catalog)

    unknown_pylon = deepcopy(wave)
    unknown_pylon["records"][0]["pylon_ids"].append("imaginary-pylon")
    with pytest.raises(ValueError, match="unknown pylons"):
        validate_wave(unknown_pylon, registry, catalog)

    false_promotion = deepcopy(wave)
    false_promotion["records"][0]["promotion_state"] = "promoted"
    with pytest.raises(ValueError, match="cannot retain blockers"):
        validate_wave(false_promotion, registry, catalog)


def test_cli_writes_report_and_closed_intake_refuses(tmp_path: Path) -> None:
    output = tmp_path / "wave.json"
    assert wave_main(
        [
            "--priority-max",
            "1",
            "--out",
            str(output),
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["record_count"] == 13
    assert len(payload["report_sha256"]) == 64

    assert wave_main(
        [
            "--front",
            "remote_venue",
            "--out",
            str(output),
            "--require-closed-intake",
        ]
    ) == 2
