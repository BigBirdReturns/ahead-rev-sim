from __future__ import annotations

import argparse
from pathlib import Path

from .rtl_attachment import (
    build_rtl_attachment_proof_from_tools,
    write_attachment_bundle,
    write_rtl_attachment_proof,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-rtl",
        description=(
            "Generate and qualify the provider-neutral SystemVerilog MMIO, "
            "opaque-handle resolver, and replaceable-cartridge attachment."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle_parser = subparsers.add_parser(
        "bundle",
        help="generate the resolver, cartridge, testbench, expected trace, and manifest",
    )
    bundle_parser.add_argument("--out-dir", type=Path, required=True)

    proof_parser = subparsers.add_parser(
        "proof",
        help="seal an executed Icarus RTL attachment trace",
    )
    proof_parser.add_argument("--executable", type=Path, required=True)
    proof_parser.add_argument("--trace", type=Path, required=True)
    proof_parser.add_argument("--expected", type=Path, required=True)
    proof_parser.add_argument("--manifest", type=Path, required=True)
    proof_parser.add_argument(
        "--source",
        action="append",
        type=Path,
        required=True,
        help="repeat for the MMIO, resolver, cartridge, and testbench sources",
    )
    proof_parser.add_argument("--iverilog", default="iverilog")
    proof_parser.add_argument("--vvp", default="vvp")
    proof_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "bundle":
        outputs = write_attachment_bundle(args.out_dir)
        for name, path in sorted(outputs.items()):
            print(f"{name}: {path}")
        return 0

    proof = build_rtl_attachment_proof_from_tools(
        args.executable,
        args.trace,
        args.expected,
        args.manifest,
        args.source,
        iverilog=args.iverilog,
        vvp=args.vvp,
    )
    output = write_rtl_attachment_proof(args.out, proof)
    print(f"status: {proof['qualification']['status']}")
    print(f"proof sha256: {proof['proof_sha256']}")
    print(f"wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
