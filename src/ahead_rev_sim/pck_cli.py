from __future__ import annotations

import argparse
from pathlib import Path

from .fambs_pck_lowering import PCKConfig, analyze_pck


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-pck",
        description=(
            "Prove the FAMBS v0.4.0 PCK result, exhaustively verify its state-recoverable "
            "piecewise index map, and emit the retained-state work frontier."
        ),
    )
    parser.add_argument("--depth", type=int, default=128)
    parser.add_argument("--iterations", type=int, default=256)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-accepted", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    artifact = analyze_pck(PCKConfig(depth=args.depth, iterations=args.iterations))
    output = args.out or Path("artifacts/fambs-pck-lowering.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(artifact.to_json(), encoding="utf-8")

    if not args.quiet:
        print(f"status: {artifact.qualification['status']}")
        print(f"source result: {artifact.source_reference['result']}")
        print(
            "index transition: "
            f"{artifact.control_map_proof['unique_outputs']}/"
            f"{artifact.control_map_proof['domain_states']} unique"
        )
        print(
            "path history: "
            f"{artifact.control_map_proof['path_history_bits_per_step']} bits per step"
        )
        print(f"frontier points: {len(artifact.frontier)}")
        minimum_state = min(
            artifact.frontier,
            key=lambda point: point.peak_reversible_state_bits,
        )
        minimum_work = min(
            artifact.frontier,
            key=lambda point: point.total_semantic_operations,
        )
        print(
            "minimum retained state: "
            f"{minimum_state.peak_reversible_state_bits} bits at {minimum_state.strategy_id}"
        )
        print(
            "minimum reversible work: "
            f"{minimum_work.total_semantic_operations} operations at {minimum_work.strategy_id}"
        )
        print(f"artifact sha256: {artifact.artifact_sha256}")
        print(f"wrote: {output}")

    if args.require_accepted and artifact.qualification["status"] != "semantic_lowering_proved":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
