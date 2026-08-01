from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evp import build_evp_receipt, write_evp_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-evp",
        description=(
            "Build a sealed Energy, Volume, and Performance vector receipt. "
            "The command never emits a policy-weighted scalar score."
        ),
    )
    parser.add_argument("contract", type=Path, help="EVP source-contract JSON")
    parser.add_argument("--out", type=Path, required=True, help="sealed receipt JSON")
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="return exit code 2 unless a measured EVP vector is qualified",
    )
    parser.add_argument(
        "--require-advantage",
        action="store_true",
        help="return exit code 2 unless complete-system Pareto advantage is qualified",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    source = json.loads(args.contract.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("EVP source contract must be a JSON object")
    receipt = build_evp_receipt(source)
    write_evp_receipt(args.out, receipt)

    qualification = receipt["qualification"]
    if not args.quiet:
        print(f"status: {qualification['status']}")
        print(
            "energy: "
            f"{receipt['energy']['net_physical_joules_per_accepted_work_unit']} "
            "J / accepted work unit"
        )
        print(f"volume: {receipt['volume']['occupied_mm3']} mm^3")
        print(
            "performance: "
            f"{receipt['performance']['throughput_accepted_work_units_per_second']} "
            "accepted work units / s"
        )
        print(f"latency: {receipt['performance']['latency_seconds']} s")
        if receipt["comparison"] is not None:
            print(
                "pareto dominates baseline: "
                f"{receipt['comparison']['pareto_dominates_baseline']}"
            )
        print(f"receipt sha256: {receipt['receipt_sha256']}")
        print(f"wrote: {args.out}")

    if args.require_advantage and not qualification["advantage_claim_allowed"]:
        return 2
    if args.require_measured and not qualification["measured_evp_vector_allowed"]:
        return 2
    return 0 if qualification["status"] != "refused" else 2


if __name__ == "__main__":
    raise SystemExit(main())
