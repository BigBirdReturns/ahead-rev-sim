from __future__ import annotations

import argparse
import json
from pathlib import Path

from .commodity_registry import build_harvest_report, format_harvest_report, load_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-commodities",
        description=(
            "Select external compute projects as commodity inputs and emit the first "
            "completion transaction required from each."
        ),
    )
    parser.add_argument("--registry", type=Path, help="alternate commodity registry JSON")
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="include one category; repeat to include more than one",
    )
    parser.add_argument(
        "--priority-max",
        type=int,
        default=5,
        help="include priorities from 1 through this value",
    )
    parser.add_argument("--out", type=Path, help="write the sealed JSON report")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="stdout presentation",
    )
    args = parser.parse_args(argv)

    registry = load_registry(args.registry)
    report = build_harvest_report(
        registry,
        categories=args.category,
        priority_max=args.priority_max,
    )
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")

    if args.format == "json":
        print(serialized, end="")
    else:
        print(format_harvest_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
