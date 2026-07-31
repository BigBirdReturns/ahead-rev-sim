"""Information-semantic analysis for reversible workload lowering.

This module deliberately separates an opcode's marketing label from its
actual state transform.  A mnemonic is admissible as reversible only when
its instantiated operands preserve a one-to-one mapping over machine state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Any

from .isa import Instruction, OpCode


class SemanticClass(str, Enum):
    NATIVE_REVERSIBLE = "native_reversible"
    CONDITIONALLY_REVERSIBLE = "conditionally_reversible"
    IRREVERSIBLE = "irreversible"
    COMMIT = "commit"
    INVALID = "invalid"


class InformationEffect(str, Enum):
    BIJECTIVE = "bijective"
    PATH_METADATA = "path_metadata"
    OVERWRITE = "overwrite"
    TERMINAL = "terminal"
    INVALID_COLLAPSE = "invalid_collapse"


class BijectivityStatus(str, Enum):
    BIJECTIVE = "bijective"
    NON_BIJECTIVE = "non_bijective"
    NOT_APPLICABLE = "not_applicable"
    LIMIT_EXCEEDED = "limit_exceeded"
    INVALID = "invalid"


@dataclass(frozen=True)
class OperationSemantics:
    pc: int
    opcode: str
    instruction: str
    semantic_class: SemanticClass
    information_effect: InformationEffect
    native_reversible: bool
    intrinsic_erasure_bits: int
    reversal_metadata_bits: int
    overwritten_state_bits: int
    lowering_options: tuple[str, ...]
    hazards: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "pc": self.pc,
            "opcode": self.opcode,
            "instruction": self.instruction,
            "semantic_class": self.semantic_class.value,
            "information_effect": self.information_effect.value,
            "native_reversible": self.native_reversible,
            "intrinsic_erasure_bits": self.intrinsic_erasure_bits,
            "reversal_metadata_bits": self.reversal_metadata_bits,
            "overwritten_state_bits": self.overwritten_state_bits,
            "lowering_options": list(self.lowering_options),
            "hazards": list(self.hazards),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class BijectivityCheck:
    status: BijectivityStatus
    word_bits: int
    domain_states: int
    collision: dict[str, Any] | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "word_bits": self.word_bits,
            "domain_states": self.domain_states,
            "collision": self.collision,
            "reason": self.reason,
        }


def _record(
    instr: Instruction,
    pc: int,
    semantic_class: SemanticClass,
    effect: InformationEffect,
    *,
    native: bool = False,
    intrinsic: int = 0,
    metadata: int = 0,
    overwritten: int = 0,
    lowering: tuple[str, ...] = (),
    hazards: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> OperationSemantics:
    return OperationSemantics(
        pc=pc,
        opcode=instr.op.name,
        instruction=str(instr),
        semantic_class=semantic_class,
        information_effect=effect,
        native_reversible=native,
        intrinsic_erasure_bits=intrinsic,
        reversal_metadata_bits=metadata,
        overwritten_state_bits=overwritten,
        lowering_options=lowering,
        hazards=hazards,
        notes=notes,
    )


def analyze_instruction(
    instr: Instruction,
    *,
    pc: int = 0,
    word_bits: int = 32,
    pc_bits: int = 32,
) -> OperationSemantics:
    if word_bits <= 0 or pc_bits <= 0:
        raise ValueError("word_bits and pc_bits must be positive")

    if instr.op == OpCode.RXOR:
        if instr.rd is None or instr.rs1 is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))
        if instr.rd == instr.rs1:
            return _record(
                instr,
                pc,
                SemanticClass.INVALID,
                InformationEffect.INVALID_COLLAPSE,
                intrinsic=word_bits,
                hazards=("RXOR_SELF_ALIAS_COLLAPSES_TO_ZERO",),
                notes=("x XOR x maps every input word to zero",),
            )
        return _record(instr, pc, SemanticClass.NATIVE_REVERSIBLE, InformationEffect.BIJECTIVE, native=True, lowering=("native_rxor",))

    if instr.op == OpCode.RMODADD:
        if instr.rd is None or instr.rs1 is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))
        if instr.rd == instr.rs1:
            return _record(
                instr,
                pc,
                SemanticClass.INVALID,
                InformationEffect.INVALID_COLLAPSE,
                intrinsic=1,
                hazards=("RMODADD_SELF_ALIAS_IS_DOUBLING",),
                notes=("x -> 2x mod 2^N is two-to-one and loses the high input bit",),
            )
        return _record(instr, pc, SemanticClass.NATIVE_REVERSIBLE, InformationEffect.BIJECTIVE, native=True, lowering=("native_modular_add",))

    if instr.op == OpCode.RSWAP:
        if instr.rd is None or instr.rs1 is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))
        notes = ("same-register swap is an identity operation",) if instr.rd == instr.rs1 else ()
        return _record(instr, pc, SemanticClass.NATIVE_REVERSIBLE, InformationEffect.BIJECTIVE, native=True, lowering=("native_swap",), notes=notes)

    if instr.op == OpCode.REXCH:
        if instr.rd is None or instr.rs1 is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))
        if instr.rd == instr.rs1:
            return _record(
                instr,
                pc,
                SemanticClass.INVALID,
                InformationEffect.INVALID_COLLAPSE,
                intrinsic=word_bits,
                hazards=("REXCH_BASE_ALIAS_CHANGES_EFFECTIVE_ADDRESS",),
            )
        return _record(instr, pc, SemanticClass.NATIVE_REVERSIBLE, InformationEffect.BIJECTIVE, native=True, lowering=("native_register_memory_exchange",))

    if instr.op == OpCode.BEQ:
        if instr.rs1 is None or instr.rs2 is None or instr.label is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_BRANCH_OPERAND",))
        return _record(
            instr,
            pc,
            SemanticClass.CONDITIONALLY_REVERSIBLE,
            InformationEffect.PATH_METADATA,
            native=True,
            metadata=pc_bits + 1,
            lowering=("preserve_branch_decision_and_source_pc",),
            notes=("control reversal requires path custody even when data operands survive",),
        )

    if instr.op in {OpCode.ADD, OpCode.SUB}:
        if instr.rd is None or instr.rs1 is None or (instr.imm is None and instr.rs2 is None):
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))

        if instr.imm is not None:
            if instr.rd == instr.rs1:
                lowering = "rewrite_as_modular_add" if instr.op == OpCode.ADD else "rewrite_as_modular_subtract"
                return _record(
                    instr,
                    pc,
                    SemanticClass.CONDITIONALLY_REVERSIBLE,
                    InformationEffect.BIJECTIVE,
                    lowering=(lowering,),
                    notes=("in-place addition or subtraction by a known constant is bijective modulo 2^N",),
                )
            return _record(
                instr,
                pc,
                SemanticClass.IRREVERSIBLE,
                InformationEffect.OVERWRITE,
                intrinsic=word_bits,
                overwritten=word_bits,
                lowering=("preserve_destination_history", "allocate_ancilla_then_uncompute"),
            )

        assert instr.rs2 is not None
        all_same = instr.rd == instr.rs1 == instr.rs2
        if all_same and instr.op == OpCode.ADD:
            return _record(
                instr,
                pc,
                SemanticClass.INVALID,
                InformationEffect.INVALID_COLLAPSE,
                intrinsic=1,
                hazards=("ADD_SELF_ALIAS_IS_DOUBLING",),
            )
        if all_same and instr.op == OpCode.SUB:
            return _record(
                instr,
                pc,
                SemanticClass.INVALID,
                InformationEffect.INVALID_COLLAPSE,
                intrinsic=word_bits,
                hazards=("SUB_SELF_ALIAS_COLLAPSES_TO_ZERO",),
            )

        if instr.rd in {instr.rs1, instr.rs2}:
            return _record(
                instr,
                pc,
                SemanticClass.CONDITIONALLY_REVERSIBLE,
                InformationEffect.BIJECTIVE,
                lowering=("rewrite_as_in_place_reversible_alu",),
                notes=("the non-destination source must remain live and unchanged through reversal",),
            )

        return _record(
            instr,
            pc,
            SemanticClass.IRREVERSIBLE,
            InformationEffect.OVERWRITE,
            intrinsic=word_bits,
            overwritten=word_bits,
            lowering=("preserve_destination_history", "allocate_ancilla_then_uncompute"),
        )

    if instr.op == OpCode.LOAD:
        if instr.rd is None or instr.rs1 is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))
        return _record(
            instr,
            pc,
            SemanticClass.IRREVERSIBLE,
            InformationEffect.OVERWRITE,
            intrinsic=word_bits,
            overwritten=word_bits,
            lowering=("preserve_destination_history", "lower_to_exchange_with_scratch_contract"),
        )

    if instr.op == OpCode.STORE:
        if instr.rs1 is None or instr.rs2 is None:
            return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("MISSING_OPERAND",))
        return _record(
            instr,
            pc,
            SemanticClass.IRREVERSIBLE,
            InformationEffect.OVERWRITE,
            intrinsic=word_bits,
            overwritten=word_bits,
            lowering=("preserve_old_memory_word", "lower_to_exchange_with_scratch_contract"),
        )

    if instr.op == OpCode.HALT:
        return _record(
            instr,
            pc,
            SemanticClass.COMMIT,
            InformationEffect.TERMINAL,
            lowering=("declare_commit_boundary",),
            notes=("external completion is an authority boundary, not a reversible ALU transform",),
        )

    return _record(instr, pc, SemanticClass.INVALID, InformationEffect.INVALID_COLLAPSE, hazards=("UNSUPPORTED_OPCODE",))


def verify_bijective(
    instr: Instruction,
    *,
    word_bits: int = 4,
    max_domain_states: int = 1_000_000,
) -> BijectivityCheck:
    """Exhaustively test the instantiated ALU transform on a bounded word domain.

    The verifier is intentionally small-domain.  It catches alias and transform
    mistakes without pretending that enumeration at four bits proves physical
    behavior or implementation correctness at 32 bits.
    """

    if not 1 <= word_bits <= 8:
        raise ValueError("word_bits must be in the range 1..8 for exhaustive verification")
    if max_domain_states <= 0:
        raise ValueError("max_domain_states must be positive")

    supported = {OpCode.RXOR, OpCode.RMODADD, OpCode.RSWAP, OpCode.ADD, OpCode.SUB}
    if instr.op not in supported:
        return BijectivityCheck(
            status=BijectivityStatus.NOT_APPLICABLE,
            word_bits=word_bits,
            domain_states=0,
            reason="bounded verifier currently covers ALU transforms only",
        )
    if instr.rd is None or instr.rs1 is None or (instr.op in {OpCode.ADD, OpCode.SUB} and instr.imm is None and instr.rs2 is None):
        return BijectivityCheck(BijectivityStatus.INVALID, word_bits, 0, reason="missing operand")

    register_ids = sorted({r for r in (instr.rd, instr.rs1, instr.rs2) if r is not None})
    mask = (1 << word_bits) - 1
    domain_states = (1 << word_bits) ** len(register_ids)
    if domain_states > max_domain_states:
        return BijectivityCheck(
            status=BijectivityStatus.LIMIT_EXCEEDED,
            word_bits=word_bits,
            domain_states=domain_states,
            reason=(
                f"exhaustive domain has {domain_states} states, exceeding "
                f"the configured limit of {max_domain_states}"
            ),
        )

    outputs: dict[tuple[int, ...], tuple[int, ...]] = {}
    for state in product(range(1 << word_bits), repeat=len(register_ids)):
        regs = dict(zip(register_ids, state))
        before = tuple(regs[r] for r in register_ids)
        if instr.op == OpCode.RXOR:
            regs[instr.rd] = (regs[instr.rd] ^ regs[instr.rs1]) & mask
        elif instr.op == OpCode.RMODADD:
            regs[instr.rd] = (regs[instr.rd] + regs[instr.rs1]) & mask
        elif instr.op == OpCode.RSWAP:
            regs[instr.rd], regs[instr.rs1] = regs[instr.rs1], regs[instr.rd]
        elif instr.op == OpCode.ADD:
            rhs = instr.imm if instr.imm is not None else regs[instr.rs2]  # type: ignore[index]
            regs[instr.rd] = (regs[instr.rs1] + rhs) & mask
        elif instr.op == OpCode.SUB:
            rhs = instr.imm if instr.imm is not None else regs[instr.rs2]  # type: ignore[index]
            regs[instr.rd] = (regs[instr.rs1] - rhs) & mask
        after = tuple(regs[r] for r in register_ids)
        prior = outputs.get(after)
        if prior is not None and prior != before:
            return BijectivityCheck(
                status=BijectivityStatus.NON_BIJECTIVE,
                word_bits=word_bits,
                domain_states=domain_states,
                collision={"input_a": list(prior), "input_b": list(before), "output": list(after)},
            )
        outputs[after] = before

    return BijectivityCheck(BijectivityStatus.BIJECTIVE, word_bits, domain_states)
