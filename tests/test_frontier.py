from __future__ import annotations

import json
from pathlib import Path

import pytest

from ahead_rev_sim.frontier import ArchitectureProfile, analyze_assembly
from ahead_rev_sim.frontier_cli import main as frontier_main
from ahead_rev_sim.isa import Instruction, OpCode
from ahead_rev_sim.machine import Machine
from ahead_rev_sim.semantics import (
    BijectivityStatus,
    SemanticClass,
    analyze_instruction,
    verify_bijective,
)


def test_rxor_self_alias_is_rejected_by_machine() -> None:
    machine = Machine()
    machine.load_program([Instruction(OpCode.RXOR, rd=1, rs1=1)])
    with pytest.raises(ValueError, match="collapses the word to zero"):
        machine.step()


def test_rmodadd_self_alias_is_rejected_by_machine() -> None:
    machine = Machine()
    machine.load_program([Instruction(OpCode.RMODADD, rd=2, rs1=2)])
    with pytest.raises(ValueError, match="not bijective"):
        machine.step()


def test_distinct_rxor_round_trip_survives() -> None:
    machine = Machine()
    machine.registers[1] = 0xAA55
    machine.registers[2] = 0x0F0F
    before = machine.registers.copy()
    machine.load_program([Instruction(OpCode.RXOR, rd=1, rs1=2)], reset_state=False)
    machine.step()
    machine.reverse_step()
    assert machine.registers == before


def test_bounded_verifier_catches_alias_collision() -> None:
    result = verify_bijective(Instruction(OpCode.RXOR, rd=1, rs1=1), word_bits=4)
    assert result.status == BijectivityStatus.NON_BIJECTIVE
    assert result.collision is not None


def test_bounded_verifier_accepts_distinct_modular_add() -> None:
    result = verify_bijective(Instruction(OpCode.RMODADD, rd=1, rs1=2), word_bits=4)
    assert result.status == BijectivityStatus.BIJECTIVE
    assert result.domain_states == 256




def test_bounded_verifier_refuses_explosive_domain() -> None:
    result = verify_bijective(
        Instruction(OpCode.ADD, rd=3, rs1=1, rs2=2),
        word_bits=8,
        max_domain_states=1_000_000,
    )
    assert result.status == BijectivityStatus.LIMIT_EXCEEDED
    assert result.domain_states == 16_777_216

def test_out_of_place_add_records_word_erasure() -> None:
    record = analyze_instruction(Instruction(OpCode.ADD, rd=3, rs1=1, rs2=2))
    assert record.semantic_class == SemanticClass.IRREVERSIBLE
    assert record.intrinsic_erasure_bits == 32
    assert record.overwritten_state_bits == 32


def test_in_place_add_is_conditionally_reversible() -> None:
    record = analyze_instruction(Instruction(OpCode.ADD, rd=1, rs1=1, rs2=2))
    assert record.semantic_class == SemanticClass.CONDITIONALLY_REVERSIBLE
    assert record.intrinsic_erasure_bits == 0


def test_branch_carries_path_metadata() -> None:
    record = analyze_instruction(Instruction(OpCode.BEQ, rs1=1, rs2=2, label="done"))
    assert record.reversal_metadata_bits == 33


def test_frontier_is_deterministic() -> None:
    source = "ADD r1, r0, 1\nRMODADD r1, r2\nHALT\n"
    first = analyze_assembly(source, source_name="x.asm")
    second = analyze_assembly(source, source_name="x.asm")
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.to_json() == second.to_json()


def test_invalid_semantics_refuse_artifact() -> None:
    artifact = analyze_assembly("RXOR r1, r1\nHALT\n")
    assert artifact.qualification["status"] == "refused"
    assert "SEMANTIC_INVALIDITY" in artifact.qualification["blockers"]
    assert artifact.summary["first_invalid_pc"] == 0




def test_incomplete_accepted_output_contract_is_named() -> None:
    artifact = analyze_assembly(
        "RMODADD r1, r2\nHALT\n",
        accepted_output_contract={"contract_id": "partial"},
    )
    assert "WORKLOAD_ACCEPTANCE_INCOMPLETE" in artifact.qualification["blockers"]
    assert artifact.summary["accepted_output_missing_fields"] == [
        "result",
        "quality_rule",
        "accepted_work_unit",
    ]

def test_frontier_preserves_vector_instead_of_scalar_score() -> None:
    artifact = analyze_assembly(
        "ADD r1, r0, 1\nRMODADD r1, r2\nSTORE r0, r1, 4\nHALT\n",
        accepted_output_contract={"accepted_work_unit": "one exact run"},
    )
    assert {point.strategy_id for point in artifact.frontier} == {
        "native-regions",
        "history-complete",
        "uncompute-candidate",
    }
    assert all(not hasattr(point, "score") for point in artifact.frontier)
    assert all(point.break_even.evidence_class == "modeled_not_measured" for point in artifact.frontier)


def test_profile_changes_break_even_without_changing_semantics() -> None:
    source = "RMODADD r1, r2\nHALT\n"
    fast = analyze_assembly(source, profile=ArchitectureProfile(cold_cycles_per_operation=1.0))
    slow = analyze_assembly(source, profile=ArchitectureProfile(cold_cycles_per_operation=4.0))
    assert fast.summary == slow.summary
    assert fast.architecture_profile != slow.architecture_profile


def test_cli_writes_sealed_artifact(tmp_path: Path) -> None:
    source = tmp_path / "sample.asm"
    out = tmp_path / "sample.frontier.json"
    source.write_text("ADD r1, r0, 1\nRMODADD r1, r2\nHALT\n", encoding="utf-8")
    rc = frontier_main([str(source), "--out", str(out), "--quiet"])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ahead.reversibility-frontier/v0.1"
    assert len(payload["artifact_sha256"]) == 64


def test_energy_threshold_is_explicitly_normalized() -> None:
    artifact = analyze_assembly("RMODADD r1, r2\nHALT\n")
    point = next(item for item in artifact.frontier if item.strategy_id == "native-regions")
    assert point.break_even.minimum_recovery_fraction_for_energy_parity == 0.0
    assert artifact.architecture_profile.evidence_class == "normalized_uncalibrated_model"
