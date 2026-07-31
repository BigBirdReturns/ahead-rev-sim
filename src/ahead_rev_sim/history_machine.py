"""History-complete executable lowering for the ahead reversible ISA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .execution_types import UndoRecord
from .isa import Instruction, OpCode
from .machine import Machine


@dataclass
class HistoryCompleteMachine(Machine):
    """Make overwrite and path loss explicit and exactly reversible.

    Native reversible operations use their algebraic inverse. Branches retain
    path metadata. Irreversible register and memory writes retain the exact old
    architected value. HALT is a reversible simulator boundary, not a claim
    that external I/O can be undone.
    """

    word_bits: int = 32
    pc_bits: int = 32
    undo_log: list[UndoRecord] = field(default_factory=list)
    max_history_records: int = 0
    max_history_payload_bits: int = 0

    def load_program(
        self,
        program: list[Instruction],
        labels: dict[str, int] | None = None,
        *,
        reset_state: bool = True,
    ) -> None:
        super().load_program(program, labels=labels, reset_state=reset_state)
        self.undo_log.clear()
        self.max_history_records = 0
        self.max_history_payload_bits = 0

    @property
    def current_history_payload_bits(self) -> int:
        return sum(record.history_payload_bits for record in self.undo_log)

    def _append_undo(self, record: UndoRecord) -> None:
        self.undo_log.append(record)
        self.max_history_records = max(self.max_history_records, len(self.undo_log))
        self.max_history_payload_bits = max(
            self.max_history_payload_bits,
            self.current_history_payload_bits,
        )

    def step(self) -> None:
        if self.halted:
            return
        if not (0 <= self.pc < len(self.program)):
            raise IndexError(f"PC out of range: {self.pc}")

        instr = self.program[self.pc]
        from_pc = self.pc

        if instr.op == OpCode.BEQ:
            if instr.rs1 is None or instr.rs2 is None:
                raise ValueError(f"BEQ missing operands: {instr!r}")
            self._validate_reg_index(instr.rs1)
            self._validate_reg_index(instr.rs2)
            taken = self.registers[instr.rs1] == self.registers[instr.rs2]
            self._append_undo(
                UndoRecord(
                    pc=from_pc,
                    op=instr.op.name,
                    payload={"taken": taken, "from_pc": from_pc},
                    history_payload_bits=self.pc_bits + 1,
                )
            )
            self.energy.charge_reversible()
            self.metrics.record(instr.op, True)
            self.pc = self._resolve_label(instr.label) if taken else self.pc + 1
            return

        if instr.reversible:
            snapshot = self._exec_reversible(instr)
            self._append_undo(
                UndoRecord(
                    pc=from_pc,
                    op=instr.op.name,
                    payload={"snapshot": snapshot},
                    history_payload_bits=0,
                )
            )
            self.energy.charge_reversible()
            self.metrics.record(instr.op, True)
        else:
            payload, history_bits = self._capture_overwrite(instr)
            self._exec_irreversible(instr)
            self._append_undo(
                UndoRecord(
                    pc=from_pc,
                    op=instr.op.name,
                    payload=payload,
                    history_payload_bits=history_bits,
                )
            )
            self.energy.charge_irreversible()
            self.metrics.record(instr.op, False)

        if instr.op != OpCode.HALT:
            self.pc += 1

    def _capture_overwrite(self, instr: Instruction) -> tuple[dict[str, Any], int]:
        if instr.op in {OpCode.ADD, OpCode.SUB, OpCode.LOAD}:
            if instr.rd is None:
                raise ValueError(f"{instr.op.name} missing destination: {instr!r}")
            self._validate_reg_index(instr.rd)
            return {"rd": instr.rd, "old_value": self.registers[instr.rd]}, self.word_bits

        if instr.op == OpCode.STORE:
            if instr.rs1 is None or instr.rs2 is None:
                raise ValueError(f"STORE missing operands: {instr!r}")
            self._validate_reg_index(instr.rs1)
            self._validate_reg_index(instr.rs2)
            addr = self.registers[instr.rs1] + (instr.imm or 0)
            present = addr in self.memory.data
            return {
                "addr": addr,
                "present": present,
                "old_value": self.memory.load_word(addr),
            }, self.word_bits + 1

        if instr.op == OpCode.HALT:
            return {}, 0

        raise NotImplementedError(f"History capture not implemented for {instr.op}")

    def reverse_step(self) -> None:
        if not self.undo_log:
            return

        record = self.undo_log.pop()
        instr = self.program[record.pc]

        if instr.op == OpCode.BEQ:
            self.pc = int(record.payload["from_pc"])
            return

        if instr.reversible:
            self._undo_reversible(instr, record.payload.get("snapshot"))
            self.pc = record.pc
            return

        if instr.op in {OpCode.ADD, OpCode.SUB, OpCode.LOAD}:
            rd = int(record.payload["rd"])
            self.registers[rd] = int(record.payload["old_value"]) & 0xFFFFFFFF
        elif instr.op == OpCode.STORE:
            addr = int(record.payload["addr"])
            if bool(record.payload["present"]):
                self.memory.store_word(addr, int(record.payload["old_value"]))
            else:
                self.memory.data.pop(addr, None)
        elif instr.op == OpCode.HALT:
            self.halted = False
        else:
            raise NotImplementedError(f"History restore not implemented for {instr.op}")

        self.pc = record.pc

    def reverse_all(self) -> int:
        steps = 0
        while self.undo_log:
            self.reverse_step()
            steps += 1
        return steps


def apply_initial_state(
    machine: HistoryCompleteMachine,
    initial: Mapping[str, Any],
) -> None:
    registers = initial.get("registers", {})
    if not isinstance(registers, Mapping):
        raise ValueError("initial_state.registers must be an object")
    for raw_index, raw_value in registers.items():
        index = int(raw_index)
        machine._validate_reg_index(index)
        machine.registers[index] = int(raw_value) & 0xFFFFFFFF

    memory = initial.get("memory", {})
    if not isinstance(memory, Mapping):
        raise ValueError("initial_state.memory must be an object")
    for raw_addr, raw_value in memory.items():
        machine.memory.store_word(int(raw_addr), int(raw_value))
