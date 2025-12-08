from __future__ import annotations

from ..machine import Machine
from .prog_increment import make_program


def main() -> None:
    m = Machine()
    prog = make_program()
    m.load_program(prog)

    m.registers[1] = 5
    m.registers[2] = 1

    print("Initial state:")
    print("r1 =", m.registers[1], "r2 =", m.registers[2])

    while not m.halted:
        m.step()

    print("\nAfter forward execution:")
    print("r1 =", m.registers[1], "r2 =", m.registers[2])
    print("Energy used:", m.energy.total_energy)
    print("Metrics:", m.metrics.summary())

    for _ in range(3):
        m.reverse_step()

    print("\nAfter reverse execution:")
    print("r1 =", m.registers[1], "r2 =", m.registers[2])
    print("Energy still:", m.energy.total_energy)


if __name__ == "__main__":
    main()
