from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.frontier_exec import (
    ArchitectedState,
    HistoryCompleteMachine,
    run_and_prove,
)
from ahead_rev_sim.isa import Instruction, OpCode
from ahead_rev_sim.parser import AssemblyParser
from ahead_rev_sim.proof_cli import main as proof_main


ROOT = Path(__file__).resolve().parents[1]


def test_history_complete_machine_restores_sparse_memory_absence() -> None:
    source = "ADD r1, r0, 7\nSTORE r0, r1, 64\nLOAD r2, r0, 64\nHALT\n"
    parser = AssemblyParser()
    machine = HistoryCompleteMachine()
    machine.load_program(parser.parse(source), labels=parser.labels)
    before = ArchitectedState.capture(machine)

    steps = machine.run(max_steps=100)
    assert machine.halted
    assert machine.registers[2] == 7
    assert machine.memory.load_word(64) == 7
    assert machine.max_history_payload_bits == 97

    assert machine.reverse_all() == steps
    assert ArchitectedState.capture(machine) == before
    assert 64 not in machine.memory.data


def test_history_complete_machine_restores_taken_branch() -> None:
    source = "ADD r1, r0, 1\nBEQ r1, r1, done\nADD r2, r0, 99\ndone:\nHALT\n"
    parser = AssemblyParser()
    machine = HistoryCompleteMachine()
    machine.load_program(parser.parse(source), labels=parser.labels)
    before = ArchitectedState.capture(machine)

    steps = machine.run(max_steps=100)
    assert steps == 3
    assert machine.registers[2] == 0
    assert machine.reverse_all() == steps
    assert ArchitectedState.capture(machine) == before


def test_execution_proof_passes_sample_and_restores_exact_state() -> None:
    source_path = ROOT / "examples" / "asm" / "mixed_frontier.asm"
    fixture_path = ROOT / "examples" / "asm" / "execution-fixture.json"
    proof = run_and_prove(
        source_path.read_text(encoding="utf-8"),
        fixture=json.loads(fixture_path.read_text(encoding="utf-8")),
        source_name=source_path.name,
    )

    assert proof.qualification["status"] == "semantic_execution_proved"
    assert proof.accepted_output["status"] == "pass"
    assert proof.restoration["status"] == "pass"
    assert proof.execution["steps_forward"] == proof.execution["steps_reversed"]
    assert proof.execution["initial_state_sha256"] == proof.execution["restored_state_sha256"]
    assert proof.qualification["physical_claim_allowed"] is False


def test_execution_proof_names_first_output_divergence() -> None:
    fixture = {
        "initial_state": {},
        "expected_final_state": {"registers": {"1": 999}},
        "max_steps": 10,
    }
    proof = run_and_prove("ADD r1, r0, 1\nHALT\n", fixture=fixture)
    assert proof.qualification["status"] == "refused"
    assert proof.accepted_output["first_divergence"] == {
        "path": "registers.1",
        "expected": 999,
        "actual": 1,
    }


def test_execution_proof_schema_accepts_generated_proof() -> None:
    schema = json.loads((ROOT / "schemas" / "execution-proof.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    proof = run_and_prove(
        (ROOT / "examples" / "asm" / "mixed_frontier.asm").read_text(encoding="utf-8"),
        fixture=json.loads((ROOT / "examples" / "asm" / "execution-fixture.json").read_text(encoding="utf-8")),
    )
    Draft202012Validator(schema).validate(proof.to_dict())


def test_proof_cli_writes_sealed_artifact(tmp_path: Path) -> None:
    source = tmp_path / "sample.asm"
    fixture = tmp_path / "fixture.json"
    output = tmp_path / "proof.json"
    source.write_text("ADD r1, r0, 1\nHALT\n", encoding="utf-8")
    fixture.write_text(
        json.dumps(
            {
                "initial_state": {},
                "expected_final_state": {"registers": {"1": 1}, "halted": True},
                "max_steps": 10,
            }
        ),
        encoding="utf-8",
    )

    assert proof_main([str(source), "--fixture", str(fixture), "--out", str(output), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["qualification"]["status"] == "semantic_execution_proved"
    assert len(payload["proof_sha256"]) == 64


def test_native_reversible_alias_rejection_still_applies() -> None:
    machine = HistoryCompleteMachine()
    machine.load_program([Instruction(OpCode.RXOR, rd=1, rs1=1)])
    try:
        machine.step()
    except ValueError as exc:
        assert "collapses the word to zero" in str(exc)
    else:
        raise AssertionError("self-aliasing RXOR must be rejected")
