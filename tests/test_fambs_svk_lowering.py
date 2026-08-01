from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.fambs_svk_lowering import (
    SVKConfig,
    SVK_EXPECTED_RESULT,
    analyze_svk,
    svk_dot,
    svk_source_result,
)
from ahead_rev_sim.svk_cli import main as svk_main

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "fambs-svk-lowering.schema.json"


def test_default_svk_reference_matches_the_fambs_v040_contract() -> None:
    assert f"{svk_source_result():016x}" == SVK_EXPECTED_RESULT
    artifact = analyze_svk()
    assert artifact.source_reference["result"] == SVK_EXPECTED_RESULT
    assert artifact.source_reference["accepted_output_match"] is True
    assert artifact.source_reference["dot_result"] == "420328f6"
    assert svk_dot() == artifact.source_reference["dot_float"]


def test_every_pareto_point_matches_output_and_restores_entry_state() -> None:
    artifact = analyze_svk()
    assert artifact.qualification["status"] == "semantic_lowering_proved"
    assert artifact.qualification["accepted_output_match"] is True
    assert artifact.qualification["entry_state_restored"] is True
    assert all(point.output_match for point in artifact.frontier)
    assert all(point.dot_state_restored for point in artifact.frontier)
    assert all(point.sink_state_restored for point in artifact.frontier)
    assert all(point.entry_state_restored for point in artifact.frontier)
    assert all(point.erasure_bits == 0 for point in artifact.frontier)


def test_space_time_frontier_preserves_linear_and_pebbled_endpoints() -> None:
    artifact = analyze_svk()
    assert len(artifact.frontier) == 11
    minimum_space = min(artifact.frontier, key=lambda point: point.peak_support_bits)
    minimum_work = min(artifact.frontier, key=lambda point: point.total_semantic_operations)

    assert minimum_space.strategy_id == "dot-pebble-32_sink-pebble-32"
    assert minimum_space.peak_support_bits == 2048
    assert minimum_space.total_semantic_operations == 8179

    assert minimum_work.strategy_id == "dot-linear_sink-linear"
    assert minimum_work.peak_support_bits == 32032
    assert minimum_work.total_semantic_operations == 4051


def test_frontier_is_pareto_nondominated_in_support_bits_and_work() -> None:
    points = analyze_svk().frontier
    for candidate in points:
        assert not any(
            other is not candidate
            and other.peak_support_bits <= candidate.peak_support_bits
            and other.total_semantic_operations <= candidate.total_semantic_operations
            and (
                other.peak_support_bits < candidate.peak_support_bits
                or other.total_semantic_operations < candidate.total_semantic_operations
            )
            for other in points
        )


def test_fair_baseline_applies_dot_hoisting_to_conventional_execution() -> None:
    artifact = analyze_svk()
    assert artifact.parity_baseline["semantic_operations"] == 1512
    assert artifact.parity_baseline["dot_operations"] == 512
    assert artifact.parity_baseline["sink_operations"] == 1000
    assert artifact.diagnostic_source_lowering == {
        "baseline_id": "source_order_full_history_round_trip",
        "forward_semantic_operations": 513000,
        "total_semantic_operations": 1026001,
        "peak_support_bits": 4160000,
        "pareto_admissible": False,
        "reason": (
            "Retaining every repeated dot reduction is dominated after fair loop-invariant "
            "motion. Eliminated work is compiler evidence, not a physical recovery credit."
        ),
    }


def test_normalized_recovery_thresholds_are_explicit_and_support_bounded() -> None:
    artifact = analyze_svk()
    linear = next(
        point for point in artifact.frontier if point.strategy_id == "dot-linear_sink-linear"
    )
    minimum_space = next(
        point
        for point in artifact.frontier
        if point.strategy_id == "dot-pebble-32_sink-pebble-32"
    )
    assert linear.minimum_recovery_fraction_zero_support == 0.626758825
    assert linear.maximum_support_energy_units_at_80pct_recovery == 701.8
    assert minimum_space.minimum_recovery_fraction_zero_support == 0.815136325
    assert minimum_space.maximum_support_energy_units_at_80pct_recovery == -123.8


def test_physical_handoff_is_portable_and_does_not_grant_a_physical_claim() -> None:
    artifact = analyze_svk()
    assert artifact.physical_handoff["portable_binding"] == "physical-compute-mmio/v1"
    assert artifact.physical_handoff["optional_riscv_extension"] == "Xphys"
    assert artifact.physical_handoff["result_contract"]["result"] == SVK_EXPECTED_RESULT
    assert artifact.qualification["physical_claim_allowed"] is False
    assert artifact.qualification["energy_claim_allowed"] is False
    assert "RISC_V_CODEGEN_UNIMPLEMENTED" in artifact.qualification["blockers"]
    assert "PHYSICAL_SUBSTRATE_RESULT_UNMEASURED" in artifact.qualification["blockers"]


def test_nondefault_configuration_is_preserved_but_refused_against_default_contract() -> None:
    artifact = analyze_svk(SVKConfig(iterations=8))
    assert artifact.source["configuration"]["iterations"] == 8
    assert artifact.qualification["status"] == "refused"
    assert artifact.qualification["accepted_output_match"] is False
    assert "FAMBS_ACCEPTED_OUTPUT_MISMATCH" in artifact.qualification["blockers"]


def test_svk_lowering_artifact_is_deterministically_sealed() -> None:
    first = analyze_svk()
    second = analyze_svk()
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.to_json() == second.to_json()
    assert len(first.artifact_sha256 or "") == 64


def test_svk_lowering_validates_against_draft_2020_12_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(analyze_svk().to_dict())


def test_svk_cli_writes_a_sealed_accepted_artifact(tmp_path: Path) -> None:
    output = tmp_path / "svk-lowering.json"
    assert svk_main(["--out", str(output), "--quiet", "--require-accepted"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["qualification"]["status"] == "semantic_lowering_proved"
    assert payload["source_reference"]["result"] == SVK_EXPECTED_RESULT
    assert len(payload["artifact_sha256"]) == 64
