from __future__ import annotations

import argparse
import json

from .doctor import build_doctor_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-doctor",
        description=(
            "Verify package metadata, entry points, packaged authority resources, "
            "module imports, and source-governance files."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the complete machine-readable report",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 2 when any production-integrity blocker is present",
    )
    args = parser.parse_args(argv)

    report = build_doctor_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        package = report["package"]
        print(f"ahead-rev-sim {package['version']}")
        print(f"status: {report['status']}")
        print(f"python: {report['runtime']['python']}")
        print(f"console scripts: {len(report['console_scripts'])}")
        print(
            "package resources: "
            f"{sum(report['package_resources'].values())}/"
            f"{len(report['package_resources'])}"
        )
        print(
            "module imports: "
            f"{sum(value == 'ok' for value in report['module_imports'].values())}/"
            f"{len(report['module_imports'])}"
        )
        if report["blockers"]:
            print("blockers:")
            for blocker in report["blockers"]:
                print(f"  - {blocker}")

    if args.strict and report["status"] != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
