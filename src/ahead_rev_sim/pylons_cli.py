from __future__ import annotations

import argparse
import json
from pathlib import Path

from .commodity_registry import load_registry
from .congruent_shapes import (
    build_congruent_shape_atlas,
    format_congruent_shape_atlas,
    load_pylon_catalog,
    write_congruent_shape_atlas,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-pylons",
        description=(
            "Project recurring causal shapes across the commodity ecosystem into a "
            "sealed design-pylon atlas."
        ),
    )
    parser.add_argument("--registry", type=Path, help="alternate commodity registry JSON")
    parser.add_argument("--catalog", type=Path, help="alternate pylon catalog JSON")
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="select one ecosystem category; repeat to select more than one",
    )
    parser.add_argument(
        "--priority-max",
        type=int,
        default=5,
        help="include commodity priorities from 1 through this value",
    )
    parser.add_argument("--out", type=Path, help="write sealed atlas JSON")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="stdout presentation",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help=(
            "return exit code 2 unless every selected record has the configured "
            "foundation and domain coverage and every selected gap has a pylon"
        ),
    )
    args = parser.parse_args(argv)

    registry = load_registry(args.registry)
    catalog = load_pylon_catalog(args.catalog, registry=registry)
    atlas = build_congruent_shape_atlas(
        registry,
        catalog,
        priority_max=args.priority_max,
        categories=args.category,
    )
    if args.out is not None:
        write_congruent_shape_atlas(args.out, atlas)

    if args.format == "json":
        print(json.dumps(atlas, indent=2, sort_keys=True))
    else:
        print(format_congruent_shape_atlas(atlas))

    summary = atlas["summary"]
    complete = bool(
        summary["all_selected_records_covered"]
        and summary["selected_gap_coverage_complete"]
        and summary["minimum_foundation_pylons_per_record"] >= 4
        and summary["minimum_domain_pylons_per_record"] >= 2
    )
    if args.require_complete and not complete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
