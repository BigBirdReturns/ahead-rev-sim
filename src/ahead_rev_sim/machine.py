from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Any, Dict

from .isa import Instruction, OpCode
from .memory import Memory
from .energy import EnergyModel
from .metrics import ReversibilityMetrics


@dataclass
class Machine:
    num_regs: int = 32
    registers: List[int] = field(default_factory=lambda: [0] * 32)
    pc: int = 0
    program: List[Instruction] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)
    energy: EnergyModel = field(default_factory=EnergyModel)
    metrics: ReversibilityMetrics = field(default_factory=ReversibilityMetrics)

    labels: Dict[str, int] = field(default_factory=dict)
    exec_log: List[Tuple[int, Instruction, Any]] = field(default_factory=list)
    halted: bool = False

    def load_program(self, program: List[Instruction], labels: Dict[str, int] | None = None) -> None:
        self.program = program
        self.pc = 0
        self.exec_log.clear()
        self.halted = False
        self.metrics = ReversibilityMetrics()
        if labels is not None:
            self.labels = dict(labels)

    def run(self, max_steps: int | None = None) -> int:
        steps = 0
        while not self.halted:
            self.step()
            steps += 1
            if max_steps is not None and steps >= max_steps:
                break
        return steps

    def _resolve_label(self, label: str | None) -> int:
        if label is None:
            raise ValueError("Branch instruction missing label")
        try:
            return self.labels[label]
        except KeyError:
            raise ValueError(f"Unknown label: {label!r}")

    def step(self) -> None:
        if self.halted:
            return

        if not (0 <= self.pc < len(self.program)):
            raise IndexError(f"PC out of range: {self.pc}")

        instr = self.program[self.pc]

        if instr.op == OpCode.BEQ:
            self._exec_beq(instr)
            return

        if instr.reversible:
            snapshot = self._exec_reversible(instr)
            self.exec_log.append((self.pc, instr, snapshot))
            self.energy.charge_reversible()
            self.metrics.record(instr.op, True)
        else:
            self._exec_irreversible(instr)
            self.energy.charge_irreversible()
            self.metrics.record(instr.op, False)

        if instr.op != OpCode.HALT:
            self.pc += 1

    def reverse_step(self) -> None:
        if not self.exec_log:
            return

        pc, instr, snapshot = self.exec_log.pop()

        if instr.op == OpCode.BEQ:
            from_pc = snapshot["from_pc"]
            self.pc = from_pc
            return

        self._undo_reversible(instr, snapshot)
        self.pc = pc

    def _exec_beq(self, instr: Instruction) -> None:
        assert instr.rs1 is not None
        assert instr.rs2 is not None

        val1 = self.registers[instr.rs1]
        val2 = self.registers[instr.rs2]
        taken = (val1 == val2)

        snapshot = {"taken": taken, "from_pc": self.pc}
        self.exec_log.append((self.pc, instr, snapshot))
        self.energy.charge_reversible()
        self.metrics.record(instr.op, True)

        if taken:
            target_pc = self._resolve_label(instr.label)
            self.pc = target_pc
        else:
            self.pc += 1

    def _exec_reversible(self, instr: Instruction):
        rd = instr.rd
        rs1 = instr.rs1
        assert rd is not None

        if instr.op == OpCode.RXOR:
            assert rs1 is not None
            self.registers[rd] = self.registers[rd] ^ self.registers[rs1]
            return None

        if instr.op == OpCode.RADD:
            assert rs1 is not None
            self.registers[rd] = (
                self.registers[rd] + self.registers[rs1]
            ) & 0xFFFFFFFF
            return None

        if instr.op == OpCode.RSWAP:
            assert rs1 is not None
            self.registers[rd], self.registers[rs1] = (
                self.registers[rs1],
                self.registers[rd],
            )
            return None

        raise NotImplementedError(f"Reversible op not implemented: {instr.op}")

    def _undo_reversible(self, instr: Instruction, snapshot: Any) -> None:
        rd = instr.rd
        rs1 = instr.rs1
        assert rd is not None

        if instr.op == OpCode.RXOR:
            assert rs1 is not None
            self.registers[rd] = self.registers[rd] ^ self.registers[rs1]
            return

        if instr.op == OpCode.RADD:
            assert rs1 is not None
            self.registers[rd] = (
                self.registers[rd] - self.registers[rs1]
            ) & 0xFFFFFFFF
            return

        if instr.op == OpCode.RSWAP:
            assert rs1 is not None
            self.registers[rd], self.registers[rs1] = (
                self.registers[rs1],
                self.registers[rd],
            )
            return

        raise NotImplementedError(f"Undo for reversible op not implemented: {instr.op}")

    def _exec_irreversible(self, instr: Instruction) -> None:
        if instr.op == OpCode.ADD:
            assert instr.rd is not None
            assert instr.rs1 is not None
            if instr.imm is not None:
                self.registers[instr.rd] = (
                    self.registers[instr.rs1] + instr.imm
                ) & 0xFFFFFFFF
            else:
                assert instr.rs2 is not None
                self.registers[instr.rd] = (
                    self.registers[instr.rs1] + self.registers[instr.rs2]
                ) & 0xFFFFFFFF
            return

        if instr.op == OpCode.SUB:
            assert instr.rd is not None
            assert instr.rs1 is not None
            if instr.imm is not None:
                self.registers[instr.rd] = (
                    self.registers[instr.rs1] - instr.imm
                ) & 0xFFFFFFFF
            else:
                assert instr.rs2 is not None
                self.registers[instr.rd] = (
                    self.registers[instr.rs1] - self.registers[instr.rs2]
                ) & 0xFFFFFFFF
            return

        if instr.op == OpCode.LOAD:
            assert instr.rd is not None
            assert instr.rs1 is not None
            addr = self.registers[instr.rs1] + (instr.imm or 0)
            self.registers[instr.rd] = self.memory.load_word(addr)
            return

        if instr.op == OpCode.STORE:
            assert instr.rs1 is not None
            assert instr.rs2 is not None
            addr = self.registers[instr.rs1] + (instr.imm or 0)
            value = self.registers[instr.rs2]
            self.memory.store_word(addr, value)
            return

        if instr.op == OpCode.HALT:
            self.halted = True
            return

        raise NotImplementedError(f"Irreversible op not implemented: {instr.op}")
