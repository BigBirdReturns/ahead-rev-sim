from __future__ import annotations

import argparse
from pathlib import Path

from .chipyard_integration import DEFAULT_BASE_ADDRESS, write_chipyard_bundle


def _parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer address: {value!r}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-chipyard",
        description=(
            "Generate the source-pinned Chipyard TileLink integration candidate, "
            "bare-metal lifecycle smoke, and sealed qualification manifest."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="destination for the generated Scala, C smoke, and JSON manifest",
    )
    parser.add_argument(
        "--base-address",
        type=_parse_int,
        default=DEFAULT_BASE_ADDRESS,
        help="4 KiB-aligned MMIO base address; decimal or 0x-prefixed",
    )
    args = parser.parse_args(argv)

    outputs = write_chipyard_bundle(
        args.out_dir,
        base_address=args.base_address,
    )
    for name, path in sorted(outputs.items()):
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
