from __future__ import annotations

from .prog_increment import make_program  # reuse structure if needed
from ..machine import Machine
from ..isa import Instruction, OpCode


def make_buggy_program() -> list[Instruction]:
    """Build a small reversible program with an intentional bug.

    r1 holds a base value.
    r2 accumulates a sum that should end at 15.
    A final reversible operation corrupts r2 so the last value is wrong.
    """
    prog: list[Instruction] = []

    # Initialize r1 and r2 in irreversible mode
    # r1 = 5
    prog.append(Instruction(op=OpCode.ADD, rd=1, rs1=0, rs2=0, imm=5))
    # r2 = 10
    prog.append(Instruction(op=OpCode.ADD, rd=2, rs1=0, rs2=0, imm=10))

    # Enter reversible region via a no op label. The marker is conceptual here.
    # Correct reversible step: r2 = r2 + r1 = 15
    prog.append(Instruction(op=OpCode.RADD, rd=2, rs1=1))

    # Buggy reversible step: corrupt r2 by XOR with r1
    prog.append(Instruction(op=OpCode.RXOR, rd=2, rs1=1))

    # Halt
    prog.append(Instruction(op=OpCode.HALT))

    return prog


def main() -> None:
    print("=== ahead-rev-sim 0.6.0: Time travel debugging demo ===\n")

    m = Machine()
    program = make_buggy_program()
    m.load_program(program)

    # Run until halt
    steps = m.run()
    print(f"Forward execution completed in {steps} steps.")
    actual = m.registers[2]
    expected = (10 + 5)  # r2 should be 15 if we had not corrupted it

    print(f"Final r2 = {actual} (expected {expected})")
    if actual == expected:
        print("No mismatch detected. Demo program did not trigger the bug.")
        return

    print("\nMismatch detected. Beginning reversible history walk...\n")

    last_val = actual
    bug_pc = None
    bug_instr: Instruction | None = None

    # Walk backward through reversible history until r2 changes
    while m.exec_log:
        pc, instr, snapshot = m.exec_log[-1]
        m.reverse_step()
        new_val = m.registers[2]
        if new_val != last_val:
            bug_pc = pc
            bug_instr = instr
            break
        last_val = new_val

    print(f"r2 after reversing one or more steps: {m.registers[2]}")

    if bug_instr is None:
        print("Could not find a reversible step that changed r2.")
        return

    print("\nBug located in reversible region:")
    print(f"  PC index: {bug_pc}")
    print(f"  Instruction: {bug_instr}")
    print("\nReversible execution allowed us to walk back in time and")
    print("identify the exact reversible operation that introduced the error.")


if __name__ == "__main__":
    main()
