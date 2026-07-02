from __future__ import annotations
from typing import List

from ..isa import Instruction, OpCode


def make_program() -> List[Instruction]:
    prog: List[Instruction] = [
        Instruction(op=OpCode.RMODADD, rd=1, rs1=2, label="inc_1"),
        Instruction(op=OpCode.RMODADD, rd=1, rs1=2, label="inc_2"),
        Instruction(op=OpCode.RMODADD, rd=1, rs1=2, label="inc_3"),
        Instruction(op=OpCode.HALT, label="halt"),
    ]
    return prog
