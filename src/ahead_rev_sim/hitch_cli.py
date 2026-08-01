from __future__ import annotations

import argparse
import json
from pathlib import Path

from .provider_hitch import (
    build_consist,
    format_consist,
    load_hitch,
    write_consist,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-hitch",
        description=(
            "Compose one provider-neutral RISC-V host hitch and one physical-compute "
            "cartridge hitch without transferring workload, fallback, or evidence authority."
        ),
    )
    parser.add_argument("--host", type=Path, required=True, help="host hitch JSON")
    parser.add_argument(
        "--cartridge",
        type=Path,
        required=True,
        help="cartridge hitch JSON",
    )
    parser.add_argument("--out", type=Path, help="write the sealed consist JSON")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="stdout presentation",
    )
    parser.add_argument(
        "--require-admitted",
        action="store_true",
        help="return exit status 2 unless the composed consist is execution-admitted",
    )
    args = parser.parse_args(argv)

    host = load_hitch(args.host)
    cartridge = load_hitch(args.cartridge)
    consist = build_consist(host, cartridge)
    if args.out is not None:
        write_consist(args.out, consist)

    if args.format == "json":
        print(json.dumps(consist, indent=2, sort_keys=True))
    else:
        print(format_consist(consist))

    if args.require_admitted and consist["execution_admission"] != "accepted":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
