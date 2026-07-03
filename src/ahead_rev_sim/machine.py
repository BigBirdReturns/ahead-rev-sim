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
    registers: List[int] = field(init=False)
    pc: int = 0
    program: List[Instruction] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)
    energy: EnergyModel = field(default_factory=EnergyModel)
    metrics: ReversibilityMetrics = field(default_factory=ReversibilityMetrics)

    labels: Dict[str, int] = field(default_factory=dict)
    exec_log: List[Tuple[int, Instruction, Any]] = field(default_factory=list)
    halted: bool = False

    def __post_init__(self) -> None:
        self.registers = [0] * self.num_regs

    def load_program(
        self,
        program: List[Instruction],
        labels: Dict[str, int] | None = None,
        *,
        reset_state: bool = True,
    ) -> None:
        self.program = program
        self.pc = 0
        self.exec_log.clear()
        self.halted = False
        self.metrics = ReversibilityMetrics()
        if reset_state:
            self.registers = [0] * self.num_regs
            self.memory = Memory()
            self.energy = EnergyModel()
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
        except KeyError as exc:
            raise ValueError(f"Unknown label: {label!r}") from exc

    def _validate_reg_index(self, reg: int) -> None:
        if not 0 <= reg < self.num_regs:
            raise ValueError(f"Register index out of range: r{reg} (num_regs={self.num_regs})")

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
            self.pc = snapshot["from_pc"]
            return

        self._undo_reversible(instr, snapshot)
        self.pc = pc

    def _exec_beq(self, instr: Instruction) -> None:
        if instr.rs1 is None or instr.rs2 is None:
            raise ValueError(f"BEQ missing operands: {instr!r}")

        self._validate_reg_index(instr.rs1)
        self._validate_reg_index(instr.rs2)
        taken = self.registers[instr.rs1] == self.registers[instr.rs2]

        snapshot = {"taken": taken, "from_pc": self.pc}
        self.exec_log.append((self.pc, instr, snapshot))
        self.energy.charge_reversible()
        self.metrics.record(instr.op, True)

        if taken:
            self.pc = self._resolve_label(instr.label)
        else:
            self.pc += 1

    def _exec_reversible(self, instr: Instruction):
        rd = instr.rd
        rs1 = instr.rs1
        if rd is None:
            raise ValueError(f"Reversible op missing destination register: {instr!r}")

        if instr.op == OpCode.RXOR:
            if rs1 is None:
                raise ValueError(f"RXOR missing source register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            self.registers[rd] = self.registers[rd] ^ self.registers[rs1]
            return None

        if instr.op == OpCode.RMODADD:
            if rs1 is None:
                raise ValueError(f"RMODADD missing source register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            self.registers[rd] = (self.registers[rd] + self.registers[rs1]) & 0xFFFFFFFF
            return None

        if instr.op == OpCode.RSWAP:
            if rs1 is None:
                raise ValueError(f"RSWAP missing source register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            self.registers[rd], self.registers[rs1] = self.registers[rs1], self.registers[rd]
            return None

        if instr.op == OpCode.REXCH:
            if rs1 is None:
                raise ValueError(f"REXCH missing base register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            # The undo recomputes the effective address from rs1. If rd
            # aliased rs1, the exchange would rewrite the base register and
            # the undo would target a different address, silently breaking
            # reversibility — so aliasing is rejected outright.
            if rd == rs1:
                raise ValueError(f"REXCH requires rd != rs1 (got r{rd} for both): {instr!r}")
            addr = self.registers[rs1] + (instr.imm or 0)
            self.registers[rd] = self.memory.exchange(addr, self.registers[rd])
            return None

        raise NotImplementedError(f"Reversible op not implemented: {instr.op}")

    def _undo_reversible(self, instr: Instruction, snapshot: Any) -> None:
        rd = instr.rd
        rs1 = instr.rs1
        if rd is None:
            raise ValueError(f"Undo missing destination register: {instr!r}")

        if instr.op == OpCode.RXOR:
            if rs1 is None:
                raise ValueError(f"Undo RXOR missing source register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            self.registers[rd] = self.registers[rd] ^ self.registers[rs1]
            return

        if instr.op == OpCode.RMODADD:
            if rs1 is None:
                raise ValueError(f"Undo RMODADD missing source register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            self.registers[rd] = (self.registers[rd] - self.registers[rs1]) & 0xFFFFFFFF
            return

        if instr.op == OpCode.RSWAP:
            if rs1 is None:
                raise ValueError(f"Undo RSWAP missing source register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            self.registers[rd], self.registers[rs1] = self.registers[rs1], self.registers[rd]
            return

        if instr.op == OpCode.REXCH:
            if rs1 is None:
                raise ValueError(f"Undo REXCH missing base register: {instr!r}")
            self._validate_reg_index(rd)
            self._validate_reg_index(rs1)
            addr = self.registers[rs1] + (instr.imm or 0)
            self.registers[rd] = self.memory.exchange(addr, self.registers[rd])
            return

        raise NotImplementedError(f"Undo for reversible op not implemented: {instr.op}")

    def _exec_irreversible(self, instr: Instruction) -> None:
        if instr.op == OpCode.ADD:
            if instr.rd is None or instr.rs1 is None:
                raise ValueError(f"ADD missing operands: {instr!r}")
            self._validate_reg_index(instr.rd)
            self._validate_reg_index(instr.rs1)
            if instr.imm is not None:
                self.registers[instr.rd] = (self.registers[instr.rs1] + instr.imm) & 0xFFFFFFFF
            else:
                if instr.rs2 is None:
                    raise ValueError(f"ADD missing rs2: {instr!r}")
                self._validate_reg_index(instr.rs2)
                self.registers[instr.rd] = (self.registers[instr.rs1] + self.registers[instr.rs2]) & 0xFFFFFFFF
            return

        if instr.op == OpCode.SUB:
            if instr.rd is None or instr.rs1 is None:
                raise ValueError(f"SUB missing operands: {instr!r}")
            self._validate_reg_index(instr.rd)
            self._validate_reg_index(instr.rs1)
            if instr.imm is not None:
                self.registers[instr.rd] = (self.registers[instr.rs1] - instr.imm) & 0xFFFFFFFF
            else:
                if instr.rs2 is None:
                    raise ValueError(f"SUB missing rs2: {instr!r}")
                self._validate_reg_index(instr.rs2)
                self.registers[instr.rd] = (self.registers[instr.rs1] - self.registers[instr.rs2]) & 0xFFFFFFFF
            return

        if instr.op == OpCode.LOAD:
            if instr.rd is None or instr.rs1 is None:
                raise ValueError(f"LOAD missing operands: {instr!r}")
            self._validate_reg_index(instr.rd)
            self._validate_reg_index(instr.rs1)
            addr = self.registers[instr.rs1] + (instr.imm or 0)
            self.registers[instr.rd] = self.memory.load_word(addr)
            return

        if instr.op == OpCode.STORE:
            if instr.rs1 is None or instr.rs2 is None:
                raise ValueError(f"STORE missing operands: {instr!r}")
            self._validate_reg_index(instr.rs1)
            self._validate_reg_index(instr.rs2)
            addr = self.registers[instr.rs1] + (instr.imm or 0)
            value = self.registers[instr.rs2]
            self.memory.store_word(addr, value)
            return

        if instr.op == OpCode.HALT:
            self.halted = True
            return

        raise NotImplementedError(f"Irreversible op not implemented: {instr.op}")
