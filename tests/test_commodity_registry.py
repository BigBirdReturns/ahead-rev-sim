from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.commodity_cli import main as commodity_main
from ahead_rev_sim.commodity_registry import (
    REGISTRY_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    build_harvest_report,
    default_registry_path,
    load_registry,
    registry_digest,
    select_records,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "commodity-ecosystem-registry.schema.json"
REPORT_SCHEMA = ROOT / "schemas" / "commodity-harvest-report.schema.json"


def test_registry_validates_against_draft_2020_12_schema() -> None:
    registry = load_registry()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(registry)


def test_registry_is_packaged_and_machine_readable() -> None:
    path = default_registry_path()
    assert path.exists()
    registry = load_registry(path)
    assert registry["schema_version"] == REGISTRY_SCHEMA_VERSION
    assert registry["artifact_type"] == "commodity_ecosystem_registry"
    assert len(registry["records"]) == 73
    assert len({record["category"] for record in registry["records"]}) == 25
    assert len(registry["gap_taxonomy"]) == 26


def test_packaged_manifest_expands_all_shards_without_loss() -> None:
    manifest_path = default_registry_path()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_type"] == "commodity_ecosystem_registry_manifest"
    assert manifest["record_count"] == 73
    assert len(manifest["shards"]) == 19
    assert sum(item["record_count"] for item in manifest["shards"]) == 73
    assert len({item["shard_id"] for item in manifest["shards"]}) == len(
        manifest["shards"]
    )
    assert all(
        (manifest_path.parent / item["resource"]).exists()
        for item in manifest["shards"]
    )


def test_every_external_actor_is_a_commodity_not_a_dependency() -> None:
    registry = load_registry()
    assert registry["doctrine"]["dependency_mode"] == "commodity_only"
    assert all(
        record["ingestion_policy"]["dependency_mode"] == "commodity_only"
        for record in registry["records"]
    )
    assert all(record["commodity_assets"] for record in registry["records"])
    assert all(record["completion_questions"] for record in registry["records"])


def test_registry_contains_frontier_completion_and_failure_ecosystems() -> None:
    record_ids = {record["id"] for record in load_registry()["records"]}
    assert {
        "vaire-arc-evp",
        "ahead-high-performance-riscv",
        "normal-cn101-carnot",
        "normal-thermox",
        "extropic-thrml",
        "aria-scaling-inference-lab",
        "chipyard",
        "openasip",
        "circt-mlir",
        "riscv-verification-stack",
        "ucie-3",
        "cxl-4",
        "caliptra-root-of-trust",
        "intel-loihi2-hala-point",
        "ebrains-brainscales2",
        "neuromorphic-nir-synfire",
        "lightmatter-passage",
        "gdsfactory-sax-gsim",
        "ngspice-xyce",
        "reservoirpy",
        "nupack-molecular-programming",
        "mlcommons-mlcflow",
        "reproducible-builds-slsa-in-toto",
        "smart-usa-terminated",
    } <= record_ids


def test_all_gap_references_resolve_and_all_taxonomy_gaps_are_used() -> None:
    registry = load_registry()
    validate_registry(registry)
    declared = {item["gap_id"] for item in registry["gap_taxonomy"]}
    used = {
        gap
        for record in registry["records"]
        for gap in record["system_gaps"]
    }
    assert used == declared


def test_harvest_report_is_deterministic_and_prioritized() -> None:
    registry = load_registry()
    first = build_harvest_report(registry)
    second = build_harvest_report(registry)
    assert first == second
    assert first["schema_version"] == REPORT_SCHEMA_VERSION
    assert first["registry_sha256"] == registry_digest(registry)
    assert first["summary"]["record_count"] == 73
    assert first["summary"]["priority_counts"] == {
        "1": 32,
        "2": 37,
        "3": 4,
    }
    assert len(first["report_sha256"]) == 64
    report_schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(report_schema)
    Draft202012Validator(report_schema).validate(first)
    priorities = [item["priority"] for item in first["transactions"]]
    assert priorities == sorted(priorities)


def test_priority_one_selection_is_the_immediate_harvest_floor() -> None:
    registry = load_registry()
    selected = select_records(registry, priority_max=1)
    assert len(selected) == 32
    assert all(item["ingestion_policy"]["priority"] == 1 for item in selected)
    assert {
        "vaire-arc-evp",
        "normal-cn101-carnot",
        "normal-thermox",
        "extropic-thrml",
        "aria-scaling-inference-lab",
        "chipyard",
        "openasip",
        "circt-mlir",
        "ucie-3",
        "cxl-4",
        "caliptra-root-of-trust",
        "ebrains-brainscales2",
        "neuromorphic-nir-synfire",
        "ibm-aihwkit",
        "gdsfactory-sax-gsim",
        "ngspice-xyce",
        "reservoirpy",
        "mlcommons-mlcflow",
        "reproducible-builds-slsa-in-toto",
        "spec-ptdaemon",
    } <= {item["id"] for item in selected}


def test_category_selection_does_not_change_registry_authority() -> None:
    registry = load_registry()
    report = build_harvest_report(
        registry,
        categories=["photonic_interconnect", "chiplet_interconnect"],
        priority_max=5,
    )
    assert report["summary"]["record_count"] == 9
    assert set(report["summary"]["category_counts"]) == {
        "photonic_interconnect",
        "chiplet_interconnect",
    }
    assert report["registry_sha256"] == registry_digest(registry)


def test_every_source_and_asset_uses_an_explicit_https_locator() -> None:
    registry = load_registry()
    for record in registry["records"]:
        assert all(
            source["url"].startswith("https://")
            for source in record["official_sources"]
        )
        assert all(
            asset["locator"].startswith("https://")
            for asset in record["commodity_assets"]
        )


def test_registry_priority_counts_are_closed() -> None:
    registry = load_registry()
    counts = Counter(
        record["ingestion_policy"]["priority"]
        for record in registry["records"]
    )
    assert counts == Counter({1: 32, 2: 37, 3: 4})


def test_validator_rejects_noncommodity_dependency_mode() -> None:
    registry = load_registry()
    registry["records"][0]["ingestion_policy"]["dependency_mode"] = "partner"
    with pytest.raises(ValueError, match="commodity_only"):
        validate_registry(registry)


def test_cli_writes_a_sealed_harvest_report(tmp_path: Path) -> None:
    output = tmp_path / "commodity-harvest.json"
    assert commodity_main(["--priority-max", "1", "--out", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == REPORT_SCHEMA_VERSION
    assert payload["summary"]["record_count"] == 32
    assert len(payload["report_sha256"]) == 64
