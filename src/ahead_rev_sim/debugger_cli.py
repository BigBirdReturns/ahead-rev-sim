from __future__ import annotations

import argparse

from ._version import __version__
from .debugger import main as run_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-debug",
        description="Run the deterministic reversible time-travel debugging demonstration.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)
    del args
    run_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
