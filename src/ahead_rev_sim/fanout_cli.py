from __future__ import annotations

import argparse
import json
from pathlib import Path

from .commodity_program import (
    build_completion_plan,
    format_completion_plan,
    load_completion_program,
)
from .commodity_registry import load_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-fanout",
        description=(
            "Expand public compute projects into concurrent commodity-only "
            "completion lanes and emit a sealed execution plan."
        ),
    )
    parser.add_argument("--registry", type=Path, help="alternate commodity registry JSON")
    parser.add_argument("--program", type=Path, help="alternate completion programme JSON")
    parser.add_argument(
        "--lane",
        action="append",
        default=[],
        help="select one completion lane; repeat to select more than one",
    )
    parser.add_argument(
        "--priority-max",
        type=int,
        default=5,
        help="include commodity priorities from 1 through this value",
    )
    parser.add_argument("--out", type=Path, help="write the sealed JSON plan")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="stdout presentation",
    )
    args = parser.parse_args(argv)

    registry = load_registry(args.registry)
    program = load_completion_program(args.program, registry=registry)
    plan = build_completion_plan(
        registry,
        program,
        lane_ids=args.lane,
        priority_max=args.priority_max,
    )
    serialized = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")

    if args.format == "json":
        print(serialized, end="")
    else:
        print(format_completion_plan(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
