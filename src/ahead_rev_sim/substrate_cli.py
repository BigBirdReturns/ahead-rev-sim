from __future__ import annotations

import argparse
from pathlib import Path

from .physical_substrate import (
    EntropyTrace,
    EvidenceClass,
    PhysicalSignalFrame,
    default_runtime,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-substrate",
        description="Run a commodity physical-compute substrate reference cartridge.",
    )
    parser.add_argument(
        "cartridge",
        choices=("rc-relaxation-reference-v1", "thermal-bit-sampler-reference-v1"),
    )
    parser.add_argument("--samples", required=True, help="Comma-separated integer samples")
    parser.add_argument("--calibration-sha256", required=True)
    parser.add_argument("--entropy-seed", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    samples = tuple(int(item.strip(), 0) for item in args.samples.split(",") if item.strip())
    if not samples:
        parser.error("--samples must contain at least one integer")

    if args.cartridge.startswith("rc-"):
        channel_id = "field_input_q16"
        unit = "q16"
        entropy = None
    else:
        channel_id = "probability_threshold_u32"
        unit = "u32"
        entropy = (
            EntropyTrace.from_seed(args.entropy_seed, len(samples))
            if args.entropy_seed is not None
            else None
        )

    frame = PhysicalSignalFrame(
        channel_id=channel_id,
        samples=samples,
        start_tick=0,
        tick_period_ns=1_000,
        unit=unit,
        calibration_sha256=args.calibration_sha256,
        evidence_class=EvidenceClass.SIMULATED,
    )
    receipt = default_runtime().execute(
        args.cartridge,
        frame,
        entropy_trace=entropy,
    )
    text = receipt.to_json()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if receipt.execution_status.value == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
