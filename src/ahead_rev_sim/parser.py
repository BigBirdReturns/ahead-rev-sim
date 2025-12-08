from __future__ import annotations
from typing import List, Dict

from .isa import Instruction, OpCode


class AssemblyParser:
    # Very small assembly parser for ahead-rev-sim.

    def __init__(self) -> None:
        self.labels: Dict[str, int] = {}

    def parse(self, source_text: str) -> List[Instruction]:
        lines = source_text.strip().split("\n")
        instructions: List[Instruction] = []

        cleaned_lines: List[str] = []
        current_pc = 0

        for raw in lines:
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue

            if line.endswith(":"):
                label_name = line[:-1].strip()
                if not label_name:
                    raise ValueError(f"Empty label in line: {raw!r}")
                if label_name in self.labels:
                    raise ValueError(f"Duplicate label: {label_name}")
                self.labels[label_name] = current_pc
                continue

            cleaned_lines.append(line)
            current_pc += 1

        for line in cleaned_lines:
            parts = line.replace(",", " ").split()
            if not parts:
                continue

            op_str = parts[0].upper()

            try:
                op = OpCode[op_str]
            except KeyError:
                raise ValueError(f"Unknown OpCode in line: {line!r}")

            instr = Instruction(op=op)
            args = parts[1:]

            if op == OpCode.BEQ:
                if len(args) != 3:
                    raise ValueError(f"BEQ requires 3 operands in line: {line!r}")
                instr.rs1 = self._parse_reg(args[0])
                instr.rs2 = self._parse_reg(args[1])
                instr.label = args[2]
            elif op in {OpCode.STORE}:
                if len(args) < 2:
                    raise ValueError(f"STORE requires at least 2 operands in line: {line!r}")
                instr.rs1 = self._parse_reg(args[0])
                instr.rs2 = self._parse_reg(args[1])
                if len(args) > 2:
                    instr.imm = int(args[2])
            elif op in {OpCode.LOAD}:
                if len(args) < 2:
                    raise ValueError(f"LOAD requires at least 2 operands in line: {line!r}")
                instr.rd = self._parse_reg(args[0])
                instr.rs1 = self._parse_reg(args[1])
                if len(args) > 2:
                    instr.imm = int(args[2])
            elif op == OpCode.HALT:
                pass
            else:
                if args:
                    instr.rd = self._parse_reg(args[0])
                if len(args) > 1:
                    instr.rs1 = self._parse_reg(args[1])
                if len(args) > 2:
                    tail = args[2]
                    if tail.lower().startswith(("r", "x")) or tail.isdigit():
                        if tail.lower().startswith(("r", "x")):
                            instr.rs2 = self._parse_reg(tail)
                        else:
                            instr.imm = int(tail)
                    else:
                        instr.label = tail

            instructions.append(instr)

        return instructions

    def _parse_reg(self, token: str) -> int:
        token = token.strip().lower()
        if token.startswith("x") or token.startswith("r"):
            token = token[1:]
        return int(token)
