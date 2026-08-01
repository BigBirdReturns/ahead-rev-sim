from __future__ import annotations

import argparse

from ._version import __version__
from .examples.analyze_history import main as run_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-history",
        description="Run deterministic history-buffer sizing examples and comparison.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)
    del args
    run_analysis()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
