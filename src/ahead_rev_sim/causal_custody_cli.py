from __future__ import annotations

import argparse
import json
from pathlib import Path

from .causal_custody import (
    build_causal_custody_receipt,
    write_causal_custody_receipt,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-causal",
        description=(
            "Align workload, device, entropy, environment, calibration, instrument, "
            "power, thermal, and accepted-output events across clock domains."
        ),
    )
    parser.add_argument("contract", type=Path, help="causal-custody source JSON")
    parser.add_argument("--out", type=Path, required=True, help="sealed receipt JSON")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="return exit code 2 unless measured causal custody is qualified",
    )
    args = parser.parse_args(argv)

    source = json.loads(args.contract.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("causal-custody source contract must be a JSON object")
    receipt = build_causal_custody_receipt(source)
    write_causal_custody_receipt(args.out, receipt)

    if not args.quiet:
        summary = receipt["summary"]
        qualification = receipt["qualification"]
        print(f"status: {qualification['status']}")
        print(f"clocks: {summary['clock_count']}")
        print(f"events: {summary['event_count']}")
        print(
            "causal edges: "
            f"{summary['resolved_causal_edge_count']}/"
            f"{summary['causal_edge_count']} resolved"
        )
        print(f"accepted output matches: {summary['accepted_output_matches']}")
        print(f"receipt sha256: {receipt['receipt_sha256']}")
        print(f"wrote: {args.out}")

    if (
        args.require_measured
        and not receipt["qualification"]["measured_causal_custody_allowed"]
    ):
        return 2
    return 0 if receipt["qualification"]["status"] != "refused" else 2


if __name__ == "__main__":
    raise SystemExit(main())
