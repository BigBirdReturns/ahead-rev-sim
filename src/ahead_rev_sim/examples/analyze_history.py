"""
History Buffer Analysis: Comparing different program patterns.

This example answers the question silicon engineers actually ask:
"How big does my history buffer need to be?"

The answer depends on:
- Program structure (loops vs linear)
- Reversibility ratio (more reversible = more entries)
- Branch density (branches cost more bits than ALU ops)

Run this to see concrete numbers for buffer sizing.
"""

from __future__ import annotations

from ahead_rev_sim.machine import Machine
from ahead_rev_sim.isa import Instruction, OpCode
from ahead_rev_sim.history import HistoryBuffer, HistoryAnalyzer, EntryType
from ahead_rev_sim.parser import AssemblyParser


def analyze_program(
    name: str,
    program: list[Instruction],
    labels: dict[str, int] | None = None,
    max_steps: int = 10000,
) -> tuple[Machine, HistoryBuffer]:
    """Run a program with history buffer instrumentation."""
    
    m = Machine()
    m.load_program(program, labels=labels)
    
    history = HistoryBuffer()
    step = 0
    
    while not m.halted and step < max_steps:
        if 0 <= m.pc < len(m.program):
            instr = m.program[m.pc]
            
            # Record in history buffer based on instruction type
            if instr.op == OpCode.BEQ:
                history.push(
                    pc=m.pc,
                    op_name=instr.op.name,
                    entry_type=EntryType.BRANCH_DECISION,
                    payload=None
                )
            elif instr.reversible:
                history.push(
                    pc=m.pc,
                    op_name=instr.op.name,
                    entry_type=EntryType.REVERSIBLE_OP,
                    payload=None
                )
        
        m.step()
        step += 1
        history.record_snapshot(step)
    
    return m, history


# =============================================================================
# Test Programs
# =============================================================================

def make_linear_reversible() -> tuple[list[Instruction], dict, str]:
    """Pure linear reversible code - no branches."""
    prog = []
    # 20 reversible operations in sequence
    prog.append(Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=1))  # r1 = 1
    prog.append(Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=2))  # r2 = 2
    
    for _ in range(20):
        prog.append(Instruction(op=OpCode.RADD, rd=3, rs1=1))
        prog.append(Instruction(op=OpCode.RXOR, rd=3, rs1=2))
    
    prog.append(Instruction(op=OpCode.HALT))
    return prog, {}, "Linear reversible (40 rev ops, 0 branches)"


def make_linear_mixed() -> tuple[list[Instruction], dict, str]:
    """Linear code mixing reversible and irreversible."""
    prog = []
    prog.append(Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=1))
    prog.append(Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=2))
    
    for _ in range(10):
        # Reversible
        prog.append(Instruction(op=OpCode.RADD, rd=3, rs1=1))
        # Irreversible
        prog.append(Instruction(op=OpCode.ADD, rd=4, rs1=3, rs2=2))
    
    prog.append(Instruction(op=OpCode.HALT))
    return prog, {}, "Linear mixed (10 rev, 12 irrev, 0 branches)"


def make_tight_loop() -> tuple[list[Instruction], dict, str]:
    """Tight loop with branches - stress test for history depth."""
    # r1 = counter, r2 = 1, r3 = limit (10)
    labels = {"loop": 3, "done": 7}
    prog = [
        Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=0),   # r1 = 0
        Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=1),   # r2 = 1
        Instruction(op=OpCode.ADD, rd=3, rs1=0, imm=10),  # r3 = 10
        # loop:
        Instruction(op=OpCode.RADD, rd=1, rs1=2),         # r1 += r2 (reversible)
        Instruction(op=OpCode.RADD, rd=4, rs1=1),         # r4 += r1 (reversible accumulate)
        Instruction(op=OpCode.SUB, rd=5, rs1=1, rs2=3),   # r5 = r1 - r3 (for comparison)
        Instruction(op=OpCode.BEQ, rs1=1, rs2=3, label="done"),  # if r1 == 10, done
        Instruction(op=OpCode.BEQ, rs1=0, rs2=0, label="loop"),  # else loop (unconditional)
        # done:
        Instruction(op=OpCode.HALT),
    ]
    return prog, labels, "Tight loop (10 iterations, branch-heavy)"


def make_nested_loop() -> tuple[list[Instruction], dict, str]:
    """Nested loops - worst case for history depth."""
    # Outer: 5 iterations, Inner: 4 iterations = 20 total inner ops
    labels = {"outer": 4, "inner": 5, "inner_done": 9, "outer_done": 12}
    prog = [
        Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=0),   # r1 = outer counter
        Instruction(op=OpCode.ADD, rd=5, rs1=0, imm=5),   # r5 = outer limit
        Instruction(op=OpCode.ADD, rd=6, rs1=0, imm=4),   # r6 = inner limit
        Instruction(op=OpCode.ADD, rd=7, rs1=0, imm=1),   # r7 = 1
        # outer:
        Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=0),   # r2 = inner counter (reset)
        # inner:
        Instruction(op=OpCode.RADD, rd=3, rs1=7),         # r3 += 1 (reversible work)
        Instruction(op=OpCode.RADD, rd=2, rs1=7),         # r2 += 1
        Instruction(op=OpCode.BEQ, rs1=2, rs2=6, label="inner_done"),
        Instruction(op=OpCode.BEQ, rs1=0, rs2=0, label="inner"),
        # inner_done:
        Instruction(op=OpCode.RADD, rd=1, rs1=7),         # r1 += 1 (outer increment)
        Instruction(op=OpCode.BEQ, rs1=1, rs2=5, label="outer_done"),
        Instruction(op=OpCode.BEQ, rs1=0, rs2=0, label="outer"),
        # outer_done:
        Instruction(op=OpCode.HALT),
    ]
    return prog, labels, "Nested loops (5×4=20 inner iterations)"


def make_branch_heavy() -> tuple[list[Instruction], dict, str]:
    """Lots of conditional branches - tests branch history overhead."""
    labels = {f"skip{i}": 3 + i * 3 for i in range(10)}
    labels["end"] = 33
    
    prog = [
        Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=5),   # r1 = 5
        Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=5),   # r2 = 5
        Instruction(op=OpCode.ADD, rd=3, rs1=0, imm=1),   # r3 = 1
    ]
    
    # 10 conditional branches (some taken, some not)
    for i in range(10):
        if i % 2 == 0:
            # Taken branch
            prog.append(Instruction(op=OpCode.BEQ, rs1=1, rs2=2, label=f"skip{i}"))
        else:
            # Not taken branch  
            prog.append(Instruction(op=OpCode.BEQ, rs1=1, rs2=3, label=f"skip{i}"))
        prog.append(Instruction(op=OpCode.RADD, rd=4, rs1=3))  # Skipped or not
        # skip{i}: (label target)
        prog.append(Instruction(op=OpCode.RADD, rd=5, rs1=3))  # Always executed
    
    prog.append(Instruction(op=OpCode.HALT))
    return prog, labels, "Branch-heavy (10 conditionals, mixed taken/not-taken)"


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║  HISTORY BUFFER ANALYSIS                                          ║")
    print("║                                                                   ║")
    print("║  Comparing buffer requirements across program patterns.           ║")
    print("║  These numbers inform FPGA/ASIC history buffer sizing.            ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    
    analyzer = HistoryAnalyzer()
    
    test_cases = [
        make_linear_reversible(),
        make_linear_mixed(),
        make_tight_loop(),
        make_nested_loop(),
        make_branch_heavy(),
    ]
    
    for program, labels, description in test_cases:
        print(f"Running: {description}")
        m, history = analyze_program(description, program, labels)
        analyzer.record_run(description, history, m.metrics)
        
        # Quick summary
        s = history.summary()
        print(f"  → {m.metrics.total} instructions, "
              f"{s['max_depth']} max depth, "
              f"{s['max_bits']} max bits")
        print()
    
    # Full comparison
    print(analyzer.compare())
    
    # Detailed report for one interesting case
    print()
    print("Detailed analysis of nested loop case:")
    print()
    _, history = analyze_program(
        "nested", 
        *make_nested_loop()[:2]  # program and labels
    )
    print(history.format_report())


if __name__ == "__main__":
    main()
