from __future__ import annotations

import argparse
from pathlib import Path

from .machine import Machine
from .parser import AssemblyParser
from .examples.run_example import main as run_example_main
from .examples.run_loop import main as run_loop_main


def run_asm(path: str, max_steps: int | None = None) -> None:
    source = Path(path).read_text(encoding="utf-8")
    parser = AssemblyParser()
    program = parser.parse(source)

    m = Machine()
    m.load_program(program, labels=parser.labels)

    steps = m.run(max_steps=max_steps)
    print(f"Executed {steps} steps.")
    print("Registers r1..r3:", m.registers[1], m.registers[2], m.registers[3])
    print("Energy:", m.energy.total_energy)
    print("Metrics:", m.metrics.summary())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-sim",
        description="Reversible compute playground CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("example", help="Run the simple reversible increment example.")
    sub.add_parser("loop", help="Run the mixed reversible/irreversible loop example.")

    run_parser = sub.add_parser("run", help="Run an assembly program from a file.")
    run_parser.add_argument("path", help="Path to .asm file.")
    run_parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Optional maximum steps to execute.",
    )

    args = parser.parse_args(argv)

    if args.command == "example":
        run_example_main()
    elif args.command == "loop":
        run_loop_main()
    elif args.command == "run":
        run_asm(args.path, max_steps=args.max_steps)
    else:
        parser.print_help()
