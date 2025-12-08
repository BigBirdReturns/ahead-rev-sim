from __future__ import annotations

from ahead_rev_sim.machine import Machine
from ahead_rev_sim.parser import AssemblyParser


SOURCE = (
    "; Example mixed reversible and irreversible loop\n"
    "\n"
    "; r1 = loop counter\n"
    "; r2 = accumulator\n"
    "; r3 = decrement value (1)\n"
    "\n"
    "ADD r1, r0, 10      ; r1 = 10\n"
    "ADD r2, r0, 0       ; r2 = 0\n"
    "ADD r3, r0, 1       ; r3 = 1\n"
    "\n"
    "loop_start:\n"
    "BEQ r1, r0, done    ; if r1 == 0, exit loop\n"
    "\n"
    "; Reversible work\n"
    "RADD r2, r1         ; r2 = r2 + r1\n"
    "RXOR r2, r1         ; reversible mix\n"
    "RXOR r2, r1         ; unmix\n"
    "\n"
    "; Irreversible decrement\n"
    "SUB r1, r1, r3      ; r1 = r1 - 1\n"
    "\n"
    "; Unconditional jump via BEQ r0, r0, label\n"
    "BEQ r0, r0, loop_start\n"
    "\n"
    "done:\n"
    "HALT\n"
)


def main() -> None:
    parser = AssemblyParser()
    program = parser.parse(SOURCE)

    m = Machine()
    m.load_program(program, labels=parser.labels)

    print("Running reversible loop...\n")

    steps = m.run(max_steps=1000)

    print(f"Steps executed: {steps}")
    print(f"Final registers (r1, r2, r3): {m.registers[1]}, {m.registers[2]}, {m.registers[3]}")
    print(f"Total energy: {m.energy.total_energy:.2f}")
    print(f"Metrics: {m.metrics.summary()}")
    print(f"Execution log depth: {len(m.exec_log)}")

    print("\nReversing reversible steps...")

    while m.exec_log:
        m.reverse_step()

    print("Registers after full reverse of reversible ops:")
    print(f"(r1, r2, r3): {m.registers[1]}, {m.registers[2]}, {m.registers[3]}")


if __name__ == "__main__":
    main()
