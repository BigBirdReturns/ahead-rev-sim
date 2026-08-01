from __future__ import annotations

import argparse
from pathlib import Path

from .consist_execution import (
    build_consist_execution_proof,
    load_json_object,
    write_consist_execution_proof,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-consist-proof",
        description=(
            "Bind an execution-admitted physical-compute consist to a sealed "
            "RISC-V target-model proof."
        ),
    )
    parser.add_argument("--consist", type=Path, required=True)
    parser.add_argument("--host-hitch", type=Path, required=True)
    parser.add_argument("--cartridge-hitch", type=Path, required=True)
    parser.add_argument("--target-proof", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    consist = load_json_object(args.consist, label="physical-compute consist")
    host_hitch = load_json_object(
        args.host_hitch,
        label="host hitch",
    )
    cartridge_hitch = load_json_object(
        args.cartridge_hitch,
        label="cartridge hitch",
    )
    target_proof = load_json_object(
        args.target_proof,
        label="RISC-V target proof",
    )
    proof = build_consist_execution_proof(
        consist,
        target_proof,
        host_hitch,
        cartridge_hitch,
    )
    output = write_consist_execution_proof(args.out, proof)
    print(f"proof: {output}")
    print(f"proof sha256: {proof['proof_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
