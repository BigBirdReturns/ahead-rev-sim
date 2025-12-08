from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto


class OpCode(Enum):
    # Reversible data
    RXOR = auto()      # rd = rd XOR rs1
    RADD = auto()      # rd = rd + rs1   (algebraically inverted with subtraction)
    RSWAP = auto()     # swap rd, rs1

    # Control flow (treated as reversible at the PC level)
    BEQ = auto()       # if rs1 == rs2: PC = label

    # Irreversible data
    ADD = auto()       # rd = rs1 + rs2
    SUB = auto()       # rd = rs1 - rs2
    STORE = auto()
    LOAD = auto()

    # System
    HALT = auto()


@dataclass
class Instruction:
    op: OpCode
    rd: int | None = None
    rs1: int | None = None
    rs2: int | None = None
    imm: int | None = None
    label: str | None = None

    @property
    def reversible(self) -> bool:
        return self.op in {
            OpCode.RXOR,
            OpCode.RADD,
            OpCode.RSWAP,
            OpCode.BEQ,
        }

    def __str__(self) -> str:
        parts = [self.op.name]
        if self.rd is not None:
            parts.append(f"r{self.rd}")
        if self.rs1 is not None:
            parts.append(f"r{self.rs1}")
        if self.rs2 is not None:
            parts.append(f"r{self.rs2}")
        if self.imm is not None:
            parts.append(str(self.imm))
        if self.label is not None and self.op == OpCode.BEQ:
            parts.append(self.label)
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"Instruction({self.op}, rd={self.rd}, rs1={self.rs1}, "
            f"rs2={self.rs2}, imm={self.imm}, label={self.label!r})"
        )
