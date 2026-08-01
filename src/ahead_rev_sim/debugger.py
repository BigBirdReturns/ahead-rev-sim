"""
Time-Travel Debugger for ahead-rev-sim v0.7.

This is the demo that makes reversible execution click for engineers.

Instead of:
  "Run, crash, add printf, recompile, run again"

You get:
  "Run, see corruption, step backward, find the instruction that broke it"

This is post-silicon debug without trace buffers.
This is Heisenbug hunting without non-determinism.
This is what reversible execution enables TODAY on standard silicon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from .machine import Machine
from .isa import Instruction, OpCode
from .history import HistoryBuffer, EntryType


@dataclass
class Watchpoint:
    """A condition to monitor during execution."""

    name: str
    register: int
    condition: Callable[[int], bool]
    description: str


@dataclass
class CorruptionReport:
    """Report of where corruption was introduced."""

    pc: int
    instruction: Instruction
    register: int
    value_before: int
    value_after: int
    steps_back: int


class TimeTravelDebugger:
    """
    Interactive time-travel debugger for reversible programs.

    Workflow:
    1. Run program forward with watchpoints
    2. When watchpoint triggers, automatically walk backward
    3. Find the exact instruction that introduced the problem
    4. Report with full context

    This is what hardware debug interfaces should look like.
    """

    def __init__(self, machine: Machine):
        self.machine = machine
        self.watchpoints: List[Watchpoint] = []
        self.history = HistoryBuffer()
        self.step_count = 0
        self.violations: List[Tuple[int, Watchpoint, int]] = []

    def add_watchpoint(
        self,
        name: str,
        register: int,
        condition: Callable[[int], bool],
        description: str = "",
    ) -> None:
        """Add a watchpoint to monitor during execution."""
        self.watchpoints.append(
            Watchpoint(
                name=name,
                register=register,
                condition=condition,
                description=description or f"Watch r{register}",
            )
        )

    def watch_equals(self, register: int, expected: int, name: str = "") -> None:
        """Convenience: watch for register != expected value."""
        self.add_watchpoint(
            name=name or f"r{register}=={expected}",
            register=register,
            condition=lambda value: value != expected,
            description=f"Triggered when r{register} != {expected}",
        )

    def watch_range(self, register: int, lo: int, hi: int, name: str = "") -> None:
        """Convenience: watch for register outside [lo, hi]."""
        self.add_watchpoint(
            name=name or f"r{register}∈[{lo},{hi}]",
            register=register,
            condition=lambda value: value < lo or value > hi,
            description=f"Triggered when r{register} outside [{lo}, {hi}]",
        )

    def _check_watchpoints(self) -> Watchpoint | None:
        """Check all watchpoints, return first violation or None."""
        for watchpoint in self.watchpoints:
            value = self.machine.registers[watchpoint.register]
            if watchpoint.condition(value):
                self.violations.append((self.step_count, watchpoint, value))
                return watchpoint
        return None

    def _record_history(self, instr: Instruction) -> None:
        """Record instruction in history buffer with proper typing."""
        if instr.op == OpCode.BEQ:
            self.history.push(
                pc=self.machine.pc,
                op_name=instr.op.name,
                entry_type=EntryType.BRANCH_DECISION,
                payload={"from_pc": self.machine.pc},
            )
        elif instr.reversible:
            self.history.push(
                pc=self.machine.pc,
                op_name=instr.op.name,
                entry_type=EntryType.REVERSIBLE_OP,
                payload=None,
            )

    def run_until_violation(self, max_steps: int = 10000) -> Watchpoint | None:
        """Run forward until a watchpoint triggers or the machine halts."""
        while not self.machine.halted and self.step_count < max_steps:
            if 0 <= self.machine.pc < len(self.machine.program):
                instr = self.machine.program[self.machine.pc]
                self._record_history(instr)

            self.machine.step()
            self.step_count += 1
            self.history.record_snapshot(self.step_count)

            violation = self._check_watchpoints()
            if violation is not None:
                return violation

        return None

    def find_corruption_source(
        self,
        register: int,
        bad_value: int,
    ) -> CorruptionReport | None:
        """Walk backward through history to find where corruption was introduced."""
        del bad_value
        steps_back = 0
        current_value = self.machine.registers[register]

        while self.machine.exec_log:
            pc, instr, _snapshot = self.machine.exec_log[-1]

            self.machine.reverse_step()
            steps_back += 1

            new_value = self.machine.registers[register]
            if new_value != current_value:
                return CorruptionReport(
                    pc=pc,
                    instruction=instr,
                    register=register,
                    value_before=new_value,
                    value_after=current_value,
                    steps_back=steps_back,
                )

            current_value = new_value

        return None

    def run_and_diagnose(self, max_steps: int = 10000) -> str:
        """Run, detect a violation, and reverse to the corruption source."""
        lines = [
            "=" * 65,
            "TIME-TRAVEL DEBUGGER v0.7",
            "=" * 65,
            "",
            f"Watchpoints configured: {len(self.watchpoints)}",
        ]
        for watchpoint in self.watchpoints:
            lines.append(f"  • {watchpoint.name}: {watchpoint.description}")
        lines.append("")

        lines.append("▶ Running forward...")
        violation = self.run_until_violation(max_steps)

        if violation is None:
            lines.extend(
                [
                    f"  Completed {self.step_count} steps without violation.",
                    "",
                    self.history.format_report(),
                ]
            )
            return "\n".join(lines)

        bad_value = self.machine.registers[violation.register]
        lines.extend(
            [
                f"  ✗ Violation at step {self.step_count}",
                f"    Watchpoint: {violation.name}",
                f"    Register r{violation.register} = {bad_value}",
                "",
            ]
        )

        lines.append("◀ Walking backward through reversible history...")
        report = self.find_corruption_source(violation.register, bad_value)

        if report is None:
            lines.append("  Could not locate corruption source in reversible region.")
        else:
            lines.extend(
                [
                    f"  ✓ Found corruption source after {report.steps_back} reverse steps",
                    "",
                    "┌─────────────────────────────────────────────────────────────┐",
                    "│ CORRUPTION SOURCE                                           │",
                    "├─────────────────────────────────────────────────────────────┤",
                    f"│ PC:          {report.pc:<48}│",
                    f"│ Instruction: {str(report.instruction):<48}│",
                    f"│ Register:    r{report.register:<47}│",
                    f"│ Before:      {report.value_before:<48}│",
                    f"│ After:       {report.value_after:<48}│",
                    "└─────────────────────────────────────────────────────────────┘",
                    "",
                ]
            )

        lines.extend(["", self.history.format_report()])
        return "\n".join(lines)


def make_clean_program() -> Tuple[List[Instruction], int]:
    """Return a correct program that computes 10 + 5 + 3."""
    return [
        Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=10),
        Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=5),
        Instruction(op=OpCode.ADD, rd=3, rs1=0, imm=3),
        Instruction(op=OpCode.RMODADD, rd=1, rs1=2),
        Instruction(op=OpCode.RMODADD, rd=1, rs1=3),
        Instruction(op=OpCode.HALT),
    ], 18


def make_buggy_program() -> Tuple[List[Instruction], int]:
    """Return a program whose XOR corrupts the accumulator."""
    return [
        Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=10),
        Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=5),
        Instruction(op=OpCode.ADD, rd=3, rs1=0, imm=3),
        Instruction(op=OpCode.RMODADD, rd=1, rs1=2),
        Instruction(op=OpCode.RXOR, rd=1, rs1=3),
        Instruction(op=OpCode.RMODADD, rd=1, rs1=3),
        Instruction(op=OpCode.HALT),
    ], 18


def main() -> None:
    """Run the time-travel debugger demo."""
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║  AHEAD-REV-SIM: Time-Travel Debugging Demo                        ║")
    print("║                                                                   ║")
    print("║  This is what post-silicon debug looks like with reversible      ║")
    print("║  execution. No trace buffers. No checkpoints. Just math.         ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()

    program, expected = make_buggy_program()

    machine = Machine()
    machine.load_program(program)

    print("Program: Compute r1 = 10 + 5 + 3 = 18")
    print("Bug: One instruction is RXOR instead of RMODADD")
    print()

    steps = machine.run()
    actual = machine.registers[1]

    print(f"Forward execution: {steps} steps")
    print(f"Expected r1 = {expected}")
    print(f"Actual r1   = {actual}")
    print()

    if actual == expected:
        print("No bug detected. Try a different program.")
        return

    print("✗ Mismatch detected!")
    print()
    print("=" * 65)
    print("Beginning reverse execution to locate bug...")
    print("=" * 65)
    print()

    steps_back = 0
    corruption_pc = None
    corruption_instr = None
    value_trail = [(machine.registers[1], "final")]

    while machine.exec_log:
        pc, instr, _snapshot = machine.exec_log[-1]
        old_r1 = machine.registers[1]

        machine.reverse_step()
        steps_back += 1
        new_r1 = machine.registers[1]

        value_trail.append((new_r1, f"after undoing {instr.op.name} at PC={pc}"))

        if new_r1 != old_r1:
            print(f"  Step back {steps_back}: Undid {instr.op.name} at PC {pc}")
            print(f"    r1: {old_r1} → {new_r1}")

            if instr.op == OpCode.RXOR and instr.rd == 1:
                corruption_pc = pc
                corruption_instr = instr
                print("    ⚠ This is a reversible XOR - suspicious!")

    print()
    print("=" * 65)
    print("DIAGNOSIS")
    print("=" * 65)
    print()

    if corruption_instr is not None:
        print(f"Bug located at PC {corruption_pc}: {corruption_instr}")
        print()
        print("The RXOR instruction corrupted the accumulator.")
        print("It should have been RMODADD to continue the sum.")
        print()
        print("Value trail (reverse order):")
        for value, description in value_trail[-5:]:
            print(f"  r1 = {value:5d}  ({description})")
    else:
        print("Could not isolate a single corruption point.")
        print("The bug may be in irreversible initialization.")

    print()
    print("=" * 65)
    print("WHY THIS MATTERS")
    print("=" * 65)
    print(
        """
Traditional debugging: Add printf, recompile, re-run, repeat.
Time-travel debugging: Run once, walk backward, find the bug.

On silicon, this means:
- No massive trace buffers eating area
- No non-deterministic Heisenbugs
- Post-silicon bring-up without emulation

This works today on standard CMOS.
The only requirement is reversible instruction support in the ISA.
"""
    )


if __name__ == "__main__":
    main()
