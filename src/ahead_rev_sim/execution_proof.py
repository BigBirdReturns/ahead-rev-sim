"""Generate accepted-output and exact-restoration execution proofs."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .execution_types import (
    EXECUTION_PROOF_ARTIFACT_TYPE,
    EXECUTION_PROOF_SCHEMA_VERSION,
    ArchitectedState,
    ExecutionProof,
    sha256_json,
)
from .history_machine import HistoryCompleteMachine, apply_initial_state
from .parser import AssemblyParser


def _first_expected_divergence(
    state: ArchitectedState,
    expected: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if expected is None:
        return None

    registers = expected.get("registers", {})
    if not isinstance(registers, Mapping):
        return {"path": "expected_final_state.registers", "reason": "must be an object"}
    for raw_index in sorted(registers, key=lambda value: int(value)):
        index = int(raw_index)
        expected_value = int(registers[raw_index]) & 0xFFFFFFFF
        actual_value = state.registers[index]
        if actual_value != expected_value:
            return {
                "path": f"registers.{index}",
                "expected": expected_value,
                "actual": actual_value,
            }

    memory = expected.get("memory", {})
    if not isinstance(memory, Mapping):
        return {"path": "expected_final_state.memory", "reason": "must be an object"}
    actual_memory = dict(state.memory)
    for raw_addr in sorted(memory, key=lambda value: int(value)):
        addr = int(raw_addr)
        expected_value = int(memory[raw_addr]) & 0xFFFFFFFF
        actual_value = actual_memory.get(addr, 0)
        if actual_value != expected_value:
            return {
                "path": f"memory.{addr}",
                "expected": expected_value,
                "actual": actual_value,
            }

    for field_name in ("pc", "halted"):
        if field_name in expected:
            actual_value = getattr(state, field_name)
            expected_value = expected[field_name]
            if actual_value != expected_value:
                return {
                    "path": field_name,
                    "expected": expected_value,
                    "actual": actual_value,
                }
    return None


def _first_state_divergence(
    expected: ArchitectedState,
    actual: ArchitectedState,
) -> dict[str, Any] | None:
    for index, (left, right) in enumerate(zip(expected.registers, actual.registers)):
        if left != right:
            return {"path": f"registers.{index}", "expected": left, "actual": right}

    expected_memory = dict(expected.memory)
    actual_memory = dict(actual.memory)
    for addr in sorted(set(expected_memory) | set(actual_memory)):
        left = expected_memory.get(addr, "<absent>")
        right = actual_memory.get(addr, "<absent>")
        if left != right:
            return {"path": f"memory.{addr}", "expected": left, "actual": right}

    if expected.pc != actual.pc:
        return {"path": "pc", "expected": expected.pc, "actual": actual.pc}
    if expected.halted != actual.halted:
        return {"path": "halted", "expected": expected.halted, "actual": actual.halted}
    return None


def run_and_prove(
    source_text: str,
    *,
    fixture: Mapping[str, Any],
    source_name: str = "program.asm",
    word_bits: int = 32,
    pc_bits: int = 32,
) -> ExecutionProof:
    parser = AssemblyParser()
    program = parser.parse(source_text)
    machine = HistoryCompleteMachine(word_bits=word_bits, pc_bits=pc_bits)
    machine.load_program(program, labels=parser.labels)
    apply_initial_state(machine, fixture.get("initial_state", {}))

    initial_state = ArchitectedState.capture(machine)
    max_steps = int(fixture.get("max_steps", 100_000))
    steps = machine.run(max_steps=max_steps)
    final_state = ArchitectedState.capture(machine)

    trace_payload = [record.digest_payload() for record in machine.undo_log]
    trace_sha256 = sha256_json(trace_payload)
    history_records_peak = machine.max_history_records
    history_payload_bits_peak = machine.max_history_payload_bits
    per_op_history_bits: dict[str, int] = {}
    for record in machine.undo_log:
        per_op_history_bits[record.op] = (
            per_op_history_bits.get(record.op, 0) + record.history_payload_bits
        )

    expected_final = fixture.get("expected_final_state")
    expected_divergence = _first_expected_divergence(final_state, expected_final)
    accepted_status = (
        "unbound"
        if expected_final is None
        else ("pass" if expected_divergence is None else "fail")
    )

    reversed_steps = machine.reverse_all()
    restored_state = ArchitectedState.capture(machine)
    restoration_divergence = _first_state_divergence(initial_state, restored_state)
    restoration_status = "pass" if restoration_divergence is None else "fail"

    blockers: list[str] = [
        "PHYSICAL_ENERGY_UNMEASURED",
        "PHYSICAL_VOLUME_UNMEASURED",
        "TIMING_UNMEASURED",
    ]
    if not final_state.halted:
        blockers.insert(0, "MAX_STEPS_OR_NONTERMINATION")
    if accepted_status == "unbound":
        blockers.insert(0, "ACCEPTED_OUTPUT_UNBOUND")
    elif accepted_status == "fail":
        blockers.insert(0, "ACCEPTED_OUTPUT_MISMATCH")
    if restoration_status == "fail":
        blockers.insert(0, "ENTRY_STATE_NOT_RESTORED")

    semantic_proof_pass = (
        final_state.halted
        and accepted_status == "pass"
        and restoration_status == "pass"
        and reversed_steps == steps
    )

    fixture_payload = dict(fixture)
    proof = ExecutionProof(
        schema_version=EXECUTION_PROOF_SCHEMA_VERSION,
        artifact_type=EXECUTION_PROOF_ARTIFACT_TYPE,
        generated_by="ahead-rev-sim/history-complete-v0.9-draft",
        source={
            "name": source_name,
            "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            "normalized_program_sha256": sha256_json(
                [
                    {
                        "op": instr.op.name,
                        "rd": instr.rd,
                        "rs1": instr.rs1,
                        "rs2": instr.rs2,
                        "imm": instr.imm,
                        "label": instr.label,
                    }
                    for instr in program
                ]
            ),
        },
        fixture={
            "fixture_sha256": sha256_json(fixture_payload),
            "max_steps": max_steps,
            "accepted_output_bound": expected_final is not None,
        },
        execution={
            "steps_forward": steps,
            "steps_reversed": reversed_steps,
            "halted": final_state.halted,
            "initial_state_sha256": initial_state.sha256,
            "final_state_sha256": final_state.sha256,
            "restored_state_sha256": restored_state.sha256,
            "trace_sha256": trace_sha256,
            "history_records_peak": history_records_peak,
            "history_payload_bits_peak": history_payload_bits_peak,
            "history_payload_bits_by_opcode": dict(sorted(per_op_history_bits.items())),
            "legacy_normalized_forward_energy_units": machine.energy.total_energy,
            "energy_evidence_class": "normalized_uncalibrated_model",
        },
        accepted_output={
            "status": accepted_status,
            "first_divergence": expected_divergence,
        },
        restoration={
            "status": restoration_status,
            "exact_entry_state_restored": restoration_divergence is None,
            "first_divergence": restoration_divergence,
        },
        qualification={
            "status": "semantic_execution_proved" if semantic_proof_pass else "refused",
            "blockers": blockers,
            "physical_claim_allowed": False,
        },
        claim_boundary=(
            "This proof establishes deterministic forward execution, sparse accepted-output checks, "
            "history-complete reverse traversal, and exact architected entry-state restoration for the "
            "simulator fixture. It does not establish physical charge recovery, measured joule savings, "
            "thermal closure, occupied volume, timing closure, or manufacturable silicon."
        ),
        control_question=(
            "Can the same accepted result and exact restoration be reproduced after the software history "
            "payload is replaced by a measured hardware mechanism inside a closed physical boundary?"
        ),
    )
    proof.seal()
    return proof
