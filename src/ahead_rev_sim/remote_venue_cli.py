from __future__ import annotations

import argparse
import json
from pathlib import Path

from .remote_venue import (
    build_remote_submission,
    build_remote_venue_comparison,
    build_remote_venue_receipt,
    write_json_artifact,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-venue",
        description=(
            "Seal portable remote submissions, verify raw venue returns locally, "
            "and compare the same packet across replaceable venues."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    seal = subparsers.add_parser("seal", help="seal a venue-neutral submission")
    seal.add_argument("source", type=Path)
    seal.add_argument("--out", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="verify one venue return locally")
    verify.add_argument("submission", type=Path)
    verify.add_argument("returned", type=Path)
    verify.add_argument("--out", type=Path, required=True)
    verify.add_argument("--require-accepted", action="store_true")

    compare = subparsers.add_parser(
        "compare",
        help="compare one sealed packet across at least two venue receipts",
    )
    compare.add_argument("receipts", type=Path, nargs="+")
    compare.add_argument("--out", type=Path, required=True)
    compare.add_argument("--require-substitution", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "seal":
        artifact = build_remote_submission(_load(args.source))
        write_json_artifact(args.out, artifact)
        print(f"submission sha256: {artifact['submission_sha256']}")
        print(f"wrote: {args.out}")
        return 0

    if args.command == "verify":
        artifact = build_remote_venue_receipt(
            _load(args.submission),
            _load(args.returned),
        )
        write_json_artifact(args.out, artifact)
        print(f"terminal state: {artifact['terminal_state']}")
        print(f"local acceptance: {artifact['local_acceptance']}")
        print(f"receipt sha256: {artifact['receipt_sha256']}")
        print(f"wrote: {args.out}")
        if args.require_accepted and not artifact["accepted_work_allowed"]:
            return 2
        return 0 if artifact["accepted_work_allowed"] else 2

    receipts = [_load(path) for path in args.receipts]
    artifact = build_remote_venue_comparison(receipts)
    write_json_artifact(args.out, artifact)
    print(f"venues: {len(artifact['venue_ids'])}")
    print(f"substitution proved: {artifact['substitution_proved']}")
    print(f"comparison sha256: {artifact['comparison_sha256']}")
    print(f"wrote: {args.out}")
    if args.require_substitution and not artifact["substitution_proved"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
