from __future__ import annotations

import argparse
from pathlib import Path

from .fambs_svk_lowering import SVKConfig, analyze_svk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-svk",
        description=(
            "Prove the FAMBS v0.4.0 SVK binary32 result and emit its reversible "
            "checkpoint space-time frontier."
        ),
    )
    parser.add_argument("--vector-length", type=int, default=2048)
    parser.add_argument("--nnz", type=int, default=128)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-accepted", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    artifact = analyze_svk(
        SVKConfig(
            vector_length=args.vector_length,
            nnz=args.nnz,
            iterations=args.iterations,
        )
    )
    output = args.out or Path("artifacts/fambs-svk-lowering.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(artifact.to_json(), encoding="utf-8")

    if not args.quiet:
        print(f"status: {artifact.qualification['status']}")
        print(f"source result: {artifact.source_reference['result']}")
        print(f"frontier points: {len(artifact.frontier)}")
        best_space = min(artifact.frontier, key=lambda point: point.peak_support_bits)
        best_work = min(artifact.frontier, key=lambda point: point.total_semantic_operations)
        print(
            "minimum support state: "
            f"{best_space.peak_support_bits} bits at {best_space.strategy_id}"
        )
        print(
            "minimum reversible work: "
            f"{best_work.total_semantic_operations} operations at {best_work.strategy_id}"
        )
        print(f"artifact sha256: {artifact.artifact_sha256}")
        print(f"wrote: {output}")

    if args.require_accepted and artifact.qualification["status"] != "semantic_lowering_proved":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
