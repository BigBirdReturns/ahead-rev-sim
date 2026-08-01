from __future__ import annotations

import argparse
from pathlib import Path

from ._version import __version__
from .doctor_cli import main as doctor_main
from .examples.run_example import main as run_example_main
from .examples.run_loop import main as run_loop_main
from .machine import Machine
from .parser import AssemblyParser


def run_asm(path: str, max_steps: int | None = None) -> None:
    source = Path(path).read_text(encoding="utf-8")
    parser = AssemblyParser()
    program = parser.parse(source)

    machine = Machine()
    machine.load_program(program, labels=parser.labels)

    steps = machine.run(max_steps=max_steps)
    print(f"Executed {steps} steps.")
    print(
        "Registers r1..r3:",
        machine.registers[1],
        machine.registers[2],
        machine.registers[3],
    )
    print("Energy:", machine.energy.total_energy)
    print("Metrics:", machine.metrics.summary())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-sim",
        description=(
            "Workload-to-physics evidence tooling for reversible and heterogeneous "
            "RISC-V compute."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("example", help="Run the simple reversible increment example.")
    subparsers.add_parser("loop", help="Run the mixed reversible/irreversible loop example.")

    run_parser = subparsers.add_parser("run", help="Run an assembly program from a file.")
    run_parser.add_argument("path", help="Path to an assembly source file.")
    run_parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Optional maximum number of instructions to execute.",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Verify package, entry-point, resource, and governance integrity.",
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.add_argument("--strict", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "example":
        run_example_main()
        return 0
    if args.command == "loop":
        run_loop_main()
        return 0
    if args.command == "run":
        run_asm(args.path, max_steps=args.max_steps)
        return 0
    if args.command == "doctor":
        doctor_args: list[str] = []
        if args.json:
            doctor_args.append("--json")
        if args.strict:
            doctor_args.append("--strict")
        return doctor_main(doctor_args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
