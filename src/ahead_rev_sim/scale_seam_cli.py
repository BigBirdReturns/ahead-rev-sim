from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scale_seam import build_scale_seam_receipt, write_scale_seam_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-scale-seam",
        description=(
            "Attribute communication, synchronization, retry, latency, energy, "
            "occupied allocation, and failure tax to explicit scale seams."
        ),
    )
    parser.add_argument("contract", type=Path, help="scale-seam source JSON")
    parser.add_argument("--out", type=Path, required=True, help="sealed receipt JSON")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="return exit code 2 unless measured scale-seam evidence is qualified",
    )
    args = parser.parse_args(argv)

    source = json.loads(args.contract.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("scale-seam source contract must be a JSON object")
    receipt = build_scale_seam_receipt(source)
    write_scale_seam_receipt(args.out, receipt)

    if not args.quiet:
        print(f"status: {receipt['qualification']['status']}")
        print(f"seams: {len(receipt['seams'])}")
        print(
            "latency: "
            f"{receipt['totals']['latency_seconds_per_accepted_work_unit']} "
            "s / accepted work unit"
        )
        print(
            "energy: "
            f"{receipt['totals']['energy_joules_per_accepted_work_unit']} "
            "J / accepted work unit"
        )
        print(
            "incremental volume: "
            f"{receipt['totals']['incremental_occupied_mm3']} mm^3"
        )
        print(f"receipt sha256: {receipt['receipt_sha256']}")
        print(f"wrote: {args.out}")

    if (
        args.require_measured
        and not receipt["qualification"]["measured_scale_seam_allowed"]
    ):
        return 2
    return 0 if receipt["qualification"]["status"] != "refused" else 2


if __name__ == "__main__":
    raise SystemExit(main())
