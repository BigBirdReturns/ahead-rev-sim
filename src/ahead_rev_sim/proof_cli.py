from __future__ import annotations

import argparse
import json
from pathlib import Path

from .frontier_exec import run_and_prove


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-prove",
        description="Execute a history-complete lowering and prove exact architected-state restoration.",
    )
    parser.add_argument("path", help="Assembly source path")
    parser.add_argument("--fixture", required=True, help="JSON initial-state and expected-output fixture")
    parser.add_argument("--out", help="Execution-proof JSON output path")
    parser.add_argument("--word-bits", type=int, default=32)
    parser.add_argument("--pc-bits", type=int, default=32)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    source_path = Path(args.path)
    fixture_path = Path(args.fixture)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(fixture, dict):
        raise ValueError("execution fixture must be a JSON object")

    proof = run_and_prove(
        source_path.read_text(encoding="utf-8"),
        fixture=fixture,
        source_name=source_path.name,
        word_bits=args.word_bits,
        pc_bits=args.pc_bits,
    )
    output = Path(args.out) if args.out else source_path.with_suffix(".execution-proof.json")
    output.write_text(proof.to_json(), encoding="utf-8")

    if not args.quiet:
        print(f"status: {proof.qualification['status']}")
        print(f"steps: {proof.execution['steps_forward']} forward / {proof.execution['steps_reversed']} reversed")
        print(f"history payload peak: {proof.execution['history_payload_bits_peak']} bits")
        print(f"accepted output: {proof.accepted_output['status']}")
        print(f"restoration: {proof.restoration['status']}")
        print(f"proof sha256: {proof.proof_sha256}")
        print(f"wrote: {output}")

    return 0 if proof.qualification["status"] == "semantic_execution_proved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
