from __future__ import annotations

import argparse
from pathlib import Path

from .riscv_target import build_riscv_target_proof_from_tools, write_riscv_target_proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-riscv-target-proof",
        description=(
            "Seal a RISC-V target execution of the physical-compute MMIO lifecycle "
            "against an accepted trace and actual toolchain identity."
        ),
    )
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compiler", default="riscv64-linux-gnu-gcc")
    parser.add_argument("--emulator", default="qemu-riscv64")
    parser.add_argument("--readelf", default="riscv64-linux-gnu-readelf")
    args = parser.parse_args(argv)

    proof = build_riscv_target_proof_from_tools(
        args.binary,
        args.trace,
        args.expected,
        compiler=args.compiler,
        emulator=args.emulator,
        readelf=args.readelf,
    )
    output = write_riscv_target_proof(args.out, proof)
    print(f"proof: {output}")
    print(f"proof sha256: {proof['proof_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
