from __future__ import annotations

import argparse
from pathlib import Path

from .fambs import import_fambs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-fambs",
        description=(
            "Bind a pinned Future AI Microbench Suite source manifest, reconcile its "
            "expected result-stream shape, and emit a sealed intake artifact."
        ),
    )
    parser.add_argument("manifest", help="Pinned FAMBS source-manifest JSON")
    parser.add_argument("--results", help="Optional observed JSONL result stream")
    parser.add_argument("--out", help="Artifact output path")
    parser.add_argument("--require-qualified", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    result_text = None
    if args.results:
        result_text = Path(args.results).read_text(encoding="utf-8")

    artifact = import_fambs(args.manifest, result_stream_text=result_text)
    output = (
        Path(args.out)
        if args.out
        else Path(args.manifest).with_suffix(".intake.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(artifact.to_json(), encoding="utf-8")

    if not args.quiet:
        print(f"status: {artifact.qualification['status']}")
        print(
            "workloads: "
            f"{artifact.coverage['imported_workloads']}/"
            f"{artifact.coverage['expected_workloads']}"
        )
        print(
            "source rows: "
            f"{artifact.source_emission['expected_total_rows']} expected / "
            f"{artifact.reference_results['row_count']} reference"
        )
        print(f"blockers: {len(artifact.qualification['blockers'])}")
        print(f"artifact sha256: {artifact.artifact_sha256}")
        print(f"wrote: {output}")

    if args.require_qualified and artifact.qualification["blockers"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
