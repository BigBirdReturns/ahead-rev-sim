from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.fambs_pck_lowering import (
    PCKConfig,
    PCK_EXPECTED_RESULT,
    analyze_pck,
    initialize_pool,
    pck_chase,
    pck_inverse_step,
    pck_reverse_chase,
    pck_source_result,
    pck_step,
    prove_control_map,
    prove_initialization_round_trip,
)
from ahead_rev_sim.pck_cli import main as pck_main

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "fambs-pck-lowering.schema.json"


def test_default_pck_reference_matches_the_fambs_v040_contract() -> None:
    assert f"{pck_source_result():016x}" == PCK_EXPECTED_RESULT
    artifact = analyze_pck()
    assert artifact.source_reference["result"] == PCK_EXPECTED_RESULT
    assert artifact.source_reference["accepted_output_match"] is True
    assert artifact.source_reference["minimum_chase_result"] == 395220
    assert artifact.source_reference["maximum_chase_result"] == 508396
    assert artifact.numeric_contract["default_sink_within_signed_int32"] is True


def test_lcg_shuffle_and_pool_materialization_are_reversibly_reconstructible() -> None:
    pool = initialize_pool()
    proof = prove_initialization_round_trip(pool)
    assert pool.final_seed == 0x80930C39
    assert proof["lcg_multiplier_inverse"] == 0xEEB9EB65
    assert proof["seed_restored"] is True
    assert proof["order_restored"] is True
    assert proof["payload_recomputable_into_clean_target"] is True
    assert proof["next_recomputable_into_clean_target"] is True
    assert proof["history_bits"] == 0


def test_piecewise_data_dependent_index_map_is_an_exhaustive_permutation() -> None:
    proof = prove_control_map(initialize_pool())
    assert proof["domain_states"] == 1024
    assert proof["unique_outputs"] == 1024
    assert proof["odd_branch_domain"] == 512
    assert proof["even_branch_domain"] == 512
    assert proof["odd_branch_image"] == 512
    assert proof["even_branch_image"] == 512
    assert proof["branch_image_intersection"] == 0
    assert proof["combined_map_bijective"] is True
    assert proof["inverse_table_complete"] is True
    assert proof["sampled_accumulator_round_trip"] is True
    assert proof["path_history_bits_per_step"] == 0


def test_every_index_and_accumulator_probe_round_trips_without_a_path_bit() -> None:
    pool = initialize_pool()
    probes = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
    for index in range(1024):
        for accumulator in probes:
            forward = pck_step(accumulator, index, pool)
            assert pck_inverse_step(*forward, pool) == (accumulator, index)


def test_all_default_chases_restore_start_index_and_zero_accumulator() -> None:
    pool = initialize_pool()
    for start in range(256):
        result, final_index = pck_chase(start, 128, pool)
        assert pck_reverse_chase(result, final_index, 128, pool) == (0, start)


def test_every_retained_state_frontier_point_matches_and_restores() -> None:
    artifact = analyze_pck()
    assert artifact.qualification["status"] == "semantic_lowering_proved"
    assert artifact.qualification["path_history_eliminated"] is True
    assert len(artifact.frontier) == 10
    assert [point.retained_final_states for point in artifact.frontier] == [
        0,
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
        256,
    ]
    assert all(point.output_match for point in artifact.frontier)
    assert all(point.entry_state_restored for point in artifact.frontier)
    assert all(point.pool_state_restored for point in artifact.frontier)
    assert all(point.path_history_bits == 0 for point in artifact.frontier)
    assert all(point.erasure_bits == 0 for point in artifact.frontier)


def test_frontier_exposes_zero_history_and_minimum_work_endpoints() -> None:
    artifact = analyze_pck()
    minimum_state = artifact.frontier[0]
    minimum_work = artifact.frontier[-1]

    assert minimum_state.strategy_id == "retain-000-final-chase-states"
    assert minimum_state.peak_reversible_state_bits == 42
    assert minimum_state.total_semantic_operations == 541185
    assert minimum_state.minimum_recovery_fraction_zero_support == 0.742195368
    assert minimum_state.maximum_support_energy_units_at_80pct_recovery == 31283.0

    assert minimum_work.strategy_id == "retain-256-final-chase-states"
    assert minimum_work.retained_state_bits == 10752
    assert minimum_work.peak_reversible_state_bits == 10752
    assert minimum_work.total_semantic_operations == 279041
    assert minimum_work.minimum_recovery_fraction_zero_support == 0.500001792
    assert minimum_work.maximum_support_energy_units_at_80pct_recovery == 83711.8


def test_retained_state_frontier_is_pareto_nondominated() -> None:
    points = analyze_pck().frontier
    for candidate in points:
        assert not any(
            other is not candidate
            and other.peak_reversible_state_bits <= candidate.peak_reversible_state_bits
            and other.total_semantic_operations <= candidate.total_semantic_operations
            and (
                other.peak_reversible_state_bits < candidate.peak_reversible_state_bits
                or other.total_semantic_operations < candidate.total_semantic_operations
            )
            for other in points
        )


def test_conventional_baseline_and_architecture_consequence_are_explicit() -> None:
    artifact = analyze_pck()
    assert artifact.parity_baseline["semantic_operations"] == 139520
    assert artifact.parity_baseline["initialization_operations"] == 8192
    assert artifact.parity_baseline["chase_operations"] == 131072
    assert artifact.parity_baseline["sink_operations"] == 256
    assert artifact.architecture_consequences["control_class"] == (
        "state_recoverable_piecewise_permutation"
    )
    assert artifact.architecture_consequences["branch_history_required"] is False
    assert artifact.architecture_consequences["prior_index_log_required"] is False


def test_physical_handoff_is_portable_and_remains_unmeasured() -> None:
    artifact = analyze_pck()
    assert artifact.physical_handoff["portable_binding"] == "physical-compute-mmio/v1"
    assert artifact.physical_handoff["optional_riscv_extension"] == "Xphys"
    assert artifact.physical_handoff["result_contract"]["result"] == PCK_EXPECTED_RESULT
    assert artifact.qualification["physical_claim_allowed"] is False
    assert artifact.qualification["energy_claim_allowed"] is False
    assert "TARGET_MEMORY_SYSTEM_UNQUALIFIED" in artifact.qualification["blockers"]


def test_nondefault_pck_is_preserved_but_refused_against_default_contract() -> None:
    artifact = analyze_pck(PCKConfig(depth=8, iterations=8))
    assert artifact.source["configuration"] == {
        "pool_size": 1024,
        "depth": 8,
        "iterations": 8,
    }
    assert artifact.qualification["status"] == "refused"
    assert "FAMBS_ACCEPTED_OUTPUT_MISMATCH" in artifact.qualification["blockers"]


def test_pck_lowering_artifact_is_deterministically_sealed() -> None:
    first = analyze_pck()
    second = analyze_pck()
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.to_json() == second.to_json()
    assert len(first.artifact_sha256 or "") == 64


def test_pck_lowering_validates_against_draft_2020_12_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(analyze_pck().to_dict())


def test_pck_cli_writes_a_sealed_accepted_artifact(tmp_path: Path) -> None:
    output = tmp_path / "pck-lowering.json"
    assert pck_main(["--out", str(output), "--quiet", "--require-accepted"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["qualification"]["status"] == "semantic_lowering_proved"
    assert payload["control_map_proof"]["path_history_bits_per_step"] == 0
    assert len(payload["artifact_sha256"]) == 64
