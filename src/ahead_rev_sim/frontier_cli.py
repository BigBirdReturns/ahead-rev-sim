from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .frontier import ArchitectureProfile, analyze_assembly, format_frontier_summary


def _load_contract(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("accepted-output contract must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-frontier",
        description="Generate an erasure ledger and reversibility frontier from ahead-rev assembly.",
    )
    parser.add_argument("path", help="Assembly source path")
    parser.add_argument("--out", help="JSON artifact output path")
    parser.add_argument("--accepted-output", help="JSON accepted-output contract")
    parser.add_argument(
        "--verify-word-bits",
        type=int,
        default=4,
        help="Bounded exhaustive verifier width, 1..8",
    )
    parser.add_argument(
        "--max-verifier-states",
        type=int,
        default=1_000_000,
        help="Maximum states enumerated per instantiated ALU transform",
    )
    parser.add_argument("--word-bits", type=int, default=32)
    parser.add_argument("--pc-bits", type=int, default=32)
    parser.add_argument("--cold-cycle-multiplier", type=float, default=2.0)
    parser.add_argument("--transition-energy", type=float, default=0.25)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    source_path = Path(args.path)
    source = source_path.read_text(encoding="utf-8")
    profile = ArchitectureProfile(
        word_bits=args.word_bits,
        pc_bits=args.pc_bits,
        cold_cycles_per_operation=args.cold_cycle_multiplier,
        transition_energy_per_crossing=args.transition_energy,
    )
    artifact = analyze_assembly(
        source,
        source_name=source_path.name,
        accepted_output_contract=_load_contract(args.accepted_output),
        profile=profile,
        verify_word_bits=args.verify_word_bits,
        max_verifier_states=args.max_verifier_states,
    )
    output = Path(args.out) if args.out else source_path.with_suffix(".frontier.json")
    output.write_text(artifact.to_json(), encoding="utf-8")
    if not args.quiet:
        print(format_frontier_summary(artifact))
        print(f"wrote: {output}")
    return 2 if artifact.qualification["status"] == "refused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
