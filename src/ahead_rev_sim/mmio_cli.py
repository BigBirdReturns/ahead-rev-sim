from __future__ import annotations

import argparse
from pathlib import Path

from .mmio_abi import (
    render_abi_json,
    render_c_header,
    render_sva,
    render_systemverilog,
    write_bundle,
)


_RENDERERS = {
    "json": render_abi_json,
    "c-header": render_c_header,
    "systemverilog": render_systemverilog,
    "sva": render_sva,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-mmio",
        description=(
            "Generate the portable physical-compute-mmio/v1 ABI, C header, "
            "reference SystemVerilog control plane, and assertions."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "c-header", "systemverilog", "sva", "bundle"),
        default="json",
        help="artifact written to stdout or the selected destination",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="write one generated artifact instead of stdout",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="write the complete four-file bundle; required for --format bundle",
    )
    args = parser.parse_args(argv)

    if args.format == "bundle":
        if args.out_dir is None:
            parser.error("--format bundle requires --out-dir")
        if args.out is not None:
            parser.error("--out cannot be combined with --format bundle")
        outputs = write_bundle(args.out_dir)
        for name, path in sorted(outputs.items()):
            print(f"{name}: {path}")
        return 0

    if args.out_dir is not None:
        parser.error("--out-dir is available only with --format bundle")

    rendered = _RENDERERS[args.format]()
    if not rendered.endswith("\n"):
        rendered += "\n"
    if args.out is None:
        print(rendered, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(rendered.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
