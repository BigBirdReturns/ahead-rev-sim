from __future__ import annotations

import argparse
import json
from pathlib import Path

from .commodity_registry import load_registry
from .congruent_shapes import load_pylon_catalog
from .pylon_wave import (
    build_wave_report,
    format_wave_report,
    load_wave,
    write_wave_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-wave",
        description=(
            "Project a second-wave ecosystem intake onto existing design pylons "
            "and emit bounded promotion transactions without changing the admitted "
            "commodity registry."
        ),
    )
    parser.add_argument("--wave", type=Path, help="alternate wave JSON")
    parser.add_argument("--registry", type=Path, help="alternate admitted registry")
    parser.add_argument("--catalog", type=Path, help="alternate pylon catalog")
    parser.add_argument(
        "--front",
        action="append",
        default=[],
        choices=("scale_seam", "remote_venue", "causal_custody"),
        help="select one intake front; repeat for more than one",
    )
    parser.add_argument(
        "--priority-max",
        type=int,
        default=5,
        help="include priorities from 1 through this value",
    )
    parser.add_argument("--out", type=Path, help="write sealed report JSON")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="stdout presentation",
    )
    parser.add_argument(
        "--require-closed-intake",
        action="store_true",
        help=(
            "return exit code 2 unless every selected record is intake-ready or "
            "promoted and has no promotion blockers"
        ),
    )
    args = parser.parse_args(argv)

    registry = load_registry(args.registry)
    catalog = load_pylon_catalog(args.catalog, registry=registry)
    wave = load_wave(
        args.wave,
        registry=registry,
        pylon_catalog=catalog,
    )
    report = build_wave_report(
        wave,
        registry=registry,
        pylon_catalog=catalog,
        fronts=args.front,
        priority_max=args.priority_max,
    )
    if args.out is not None:
        write_wave_report(args.out, report)

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_wave_report(report))

    if (
        args.require_closed_intake
        and report["summary"]["promotion_ready_count"]
        != report["summary"]["record_count"]
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
