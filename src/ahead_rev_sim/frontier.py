"""Reversibility-frontier analysis and modeled break-even envelopes."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Sequence

from .frontier_cost import _partition_regions, _strategy_points
from .frontier_types import (
    ARTIFACT_TYPE,
    REQUIRED_ACCEPTED_OUTPUT_FIELDS,
    SCHEMA_VERSION,
    ArchitectureProfile,
    BreakEvenEnvelope,
    FrontierArtifact,
    RegionRecord,
    StrategyPoint,
    _canonical_json,
)
from .isa import Instruction, OpCode
from .parser import AssemblyParser
from .semantics import SemanticClass, analyze_instruction, verify_bijective

def _instruction_payload(instr: Instruction) -> dict[str, Any]:
    return {
        "op": instr.op.name,
        "rd": instr.rd,
        "rs1": instr.rs1,
        "rs2": instr.rs2,
        "imm": instr.imm,
        "label": instr.label,
    }


def analyze_program(
    program: Sequence[Instruction],
    *,
    source_text: str,
    source_name: str = "program.asm",
    accepted_output_contract: dict[str, Any] | None = None,
    profile: ArchitectureProfile | None = None,
    verify_word_bits: int = 4,
    max_verifier_states: int = 1_000_000,
) -> FrontierArtifact:
    profile = profile or ArchitectureProfile()
    records = [
        analyze_instruction(instr, pc=pc, word_bits=profile.word_bits, pc_bits=profile.pc_bits)
        for pc, instr in enumerate(program)
    ]
    regions = _partition_regions(records)
    strategies = _strategy_points(records, profile)
    program_payload = [_instruction_payload(instr) for instr in program]
    source_hash = sha256(source_text.encode("utf-8")).hexdigest()
    program_hash = sha256(_canonical_json(program_payload).encode("utf-8")).hexdigest()

    invalid = [record for record in records if record.semantic_class == SemanticClass.INVALID]
    acceptance_missing = (
        list(REQUIRED_ACCEPTED_OUTPUT_FIELDS)
        if accepted_output_contract is None
        else [
            field_name
            for field_name in REQUIRED_ACCEPTED_OUTPUT_FIELDS
            if field_name not in accepted_output_contract
            or accepted_output_contract[field_name] in (None, "")
        ]
    )
    blockers = [
        "PHYSICAL_ENERGY_UNMEASURED",
        "PHYSICAL_VOLUME_UNMEASURED",
        "ENERGY_MODEL_UNCALIBRATED",
    ]
    if accepted_output_contract is None:
        blockers.append("WORKLOAD_ACCEPTANCE_UNBOUND")
    elif acceptance_missing:
        blockers.append("WORKLOAD_ACCEPTANCE_INCOMPLETE")
    if invalid:
        blockers.insert(0, "SEMANTIC_INVALIDITY")

    summary = {
        "operation_count": len(program),
        "native_reversible_operations": sum(record.semantic_class == SemanticClass.NATIVE_REVERSIBLE for record in records),
        "conditionally_reversible_operations": sum(record.semantic_class == SemanticClass.CONDITIONALLY_REVERSIBLE for record in records),
        "irreversible_operations": sum(record.semantic_class == SemanticClass.IRREVERSIBLE for record in records),
        "commit_operations": sum(record.semantic_class == SemanticClass.COMMIT for record in records),
        "invalid_operations": len(invalid),
        "intrinsic_erasure_bits": sum(record.intrinsic_erasure_bits for record in records),
        "reversal_metadata_bits": sum(record.reversal_metadata_bits for record in records),
        "overwritten_state_bits": sum(record.overwritten_state_bits for record in records),
        "first_invalid_pc": invalid[0].pc if invalid else None,
        "accepted_output_contract_bound": accepted_output_contract is not None,
        "accepted_output_missing_fields": acceptance_missing,
        "bounded_bijectivity_checks": [
            {
                "pc": pc,
                "opcode": instr.op.name,
                **verify_bijective(
                    instr,
                    word_bits=verify_word_bits,
                    max_domain_states=max_verifier_states,
                ).to_dict(),
            }
            for pc, instr in enumerate(program)
            if instr.op in {OpCode.RXOR, OpCode.RMODADD, OpCode.RSWAP, OpCode.ADD, OpCode.SUB}
        ],
    }

    artifact = FrontierArtifact(
        schema_version=SCHEMA_VERSION,
        artifact_type=ARTIFACT_TYPE,
        generated_by="ahead-rev-sim/frontier-v0.9-draft",
        source={
            "name": source_name,
            "source_sha256": source_hash,
            "normalized_program_sha256": program_hash,
            "instruction_encoding": "ahead-rev-sim/assembly-v0.8",
        },
        accepted_output_contract=accepted_output_contract,
        architecture_profile=profile,
        operations=records,
        regions=regions,
        frontier=strategies,
        summary=summary,
        qualification={
            "status": "refused" if invalid else "modeled_candidate",
            "blockers": blockers,
            "physical_claim_allowed": False,
        },
        claim_boundary=(
            "This artifact establishes information semantics, candidate lowerings, and normalized "
            "break-even conditions. It does not establish physical charge recovery, joule savings, "
            "volume advantage, timing closure, or silicon feasibility."
        ),
        control_question=(
            "For the fixed accepted result, which state is destroyed, preserved, recomputed, or "
            "uncomputed, and what measured physical recovery must close the resulting overhead?"
        ),
    )
    artifact.seal()
    return artifact


def analyze_assembly(
    source_text: str,
    *,
    source_name: str = "program.asm",
    accepted_output_contract: dict[str, Any] | None = None,
    profile: ArchitectureProfile | None = None,
    verify_word_bits: int = 4,
    max_verifier_states: int = 1_000_000,
) -> FrontierArtifact:
    parser = AssemblyParser()
    program = parser.parse(source_text)
    return analyze_program(
        program,
        source_text=source_text,
        source_name=source_name,
        accepted_output_contract=accepted_output_contract,
        profile=profile,
        verify_word_bits=verify_word_bits,
        max_verifier_states=max_verifier_states,
    )


def format_frontier_summary(artifact: FrontierArtifact) -> str:
    summary = artifact.summary
    lines = [
        "REVERSIBILITY FRONTIER",
        f"source: {artifact.source['name']}",
        f"status: {artifact.qualification['status']}",
        f"operations: {summary['operation_count']}",
        f"native reversible: {summary['native_reversible_operations']}",
        f"conditional: {summary['conditionally_reversible_operations']}",
        f"irreversible: {summary['irreversible_operations']}",
        f"invalid: {summary['invalid_operations']}",
        f"intrinsic erasure: {summary['intrinsic_erasure_bits']} bits",
        "",
        "strategy                 history   ancilla   extra   commits   min recovery",
        "--------------------------------------------------------------------------",
    ]
    for point in artifact.frontier:
        recovery = point.break_even.minimum_recovery_fraction_for_energy_parity
        recovery_text = "n/a" if recovery is None else f"{recovery:.3f}"
        lines.append(
            f"{point.strategy_id:<24} {point.history_bits:>7}   "
            f"{point.ancilla_peak_bytes:>7}   {point.extra_operations:>5}   "
            f"{point.commit_boundaries:>7}   {recovery_text:>12}"
        )
    lines.extend(("", f"artifact sha256: {artifact.artifact_sha256}"))
    return "\n".join(lines)


