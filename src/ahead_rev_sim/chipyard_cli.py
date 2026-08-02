from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ._version import __version__
from .chipyard_elaboration import build_chipyard_elaboration_proof_from_checkout
from .chipyard_io import write_chipyard_bundle, write_chipyard_elaboration_proof
from .chipyard_subsystem import DEFAULT_BASE_ADDRESS


def _parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer address: {value!r}") from exc


def _normalized_argv(argv: list[str] | None) -> list[str]:
    supplied = list(sys.argv[1:] if argv is None else argv)
    if supplied and supplied[0] not in {"bundle", "proof", "--help", "-h", "--version"}:
        supplied.insert(0, "bundle")
    return supplied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-chipyard",
        description=(
            "Generate the pinned Chipyard subsystem-injector bundle or seal an "
            "executed Chisel-to-FIRRTL elaboration proof."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle_parser = subparsers.add_parser(
        "bundle",
        help="generate Scala, bare-metal smoke, and the pinned integration manifest",
    )
    bundle_parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="destination for the generated Scala, C smoke, and JSON manifest",
    )
    bundle_parser.add_argument(
        "--base-address",
        type=_parse_int,
        default=DEFAULT_BASE_ADDRESS,
        help="4 KiB-aligned MMIO base address; decimal or 0x-prefixed",
    )

    proof_parser = subparsers.add_parser(
        "proof",
        help="seal a pinned Chipyard subsystem elaboration",
    )
    proof_parser.add_argument("--checkout-root", type=Path, required=True)
    proof_parser.add_argument("--manifest", type=Path, required=True)
    proof_parser.add_argument("--scala", type=Path, required=True)
    proof_parser.add_argument("--firrtl", type=Path, required=True)
    proof_parser.add_argument("--annotations", type=Path, required=True)
    proof_parser.add_argument("--chisel-log", type=Path, required=True)
    proof_parser.add_argument("--elaboration-log", type=Path, required=True)
    proof_parser.add_argument("--java-version-file", type=Path, required=True)
    proof_parser.add_argument("--sbt-version-file", type=Path, required=True)
    proof_parser.add_argument("--make-command", required=True)
    proof_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(_normalized_argv(argv))
    if args.command == "bundle":
        outputs = write_chipyard_bundle(
            args.out_dir,
            base_address=args.base_address,
        )
        for name, path in sorted(outputs.items()):
            print(f"{name}: {path}")
        return 0

    proof = build_chipyard_elaboration_proof_from_checkout(
        checkout_root=args.checkout_root,
        manifest_path=args.manifest,
        scala_source_path=args.scala,
        firrtl_path=args.firrtl,
        annotations_path=args.annotations,
        chisel_log_path=args.chisel_log,
        elaboration_log_path=args.elaboration_log,
        java_version=args.java_version_file.read_text(encoding="utf-8"),
        sbt_version=args.sbt_version_file.read_text(encoding="utf-8"),
        make_command=args.make_command,
    )
    output = write_chipyard_elaboration_proof(args.out, proof)
    print(f"status: {proof['qualification']['status']}")
    print(f"proof sha256: {proof['proof_sha256']}")
    print(f"wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
