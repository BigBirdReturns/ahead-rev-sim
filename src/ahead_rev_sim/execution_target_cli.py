from __future__ import annotations

import argparse
import json
from pathlib import Path

from ._version import __version__
from .execution_target import (
    ReferenceSoftwareTargetAdapter,
    UnboundPhysicalTargetAdapter,
    build_execution_target_invocation,
    execute_target_attempt,
    verify_execution_target_attempt,
    write_json_artifact,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ahead-rev-target",
        description=(
            "Seal provider-neutral capsule invocations, execute bounded target "
            "attempts, and verify accepted, refused, or faulted attempt receipts."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    seal = subparsers.add_parser("seal", help="seal one capsule invocation")
    seal.add_argument("source", type=Path)
    seal.add_argument("--out", type=Path, required=True)

    attempt = subparsers.add_parser(
        "attempt",
        help="execute a reference target or preserve an unbound physical refusal",
    )
    attempt.add_argument("invocation", type=Path)
    attempt.add_argument(
        "--target",
        choices=("reference-software", "unbound-fpga"),
        required=True,
    )
    attempt.add_argument("--observed-output-sha256")
    attempt.add_argument("--target-id")
    attempt.add_argument("--out", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="verify one attempt receipt")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("--require-accepted", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "seal":
        invocation = build_execution_target_invocation(_load(args.source))
        write_json_artifact(args.out, invocation)
        print(f"invocation sha256: {invocation['invocation_sha256']}")
        print(f"wrote: {args.out}")
        return 0

    if args.command == "attempt":
        invocation = _load(args.invocation)
        if args.target == "reference-software":
            if args.observed_output_sha256 is None:
                parser.error(
                    "--observed-output-sha256 is required for reference-software"
                )
            adapter = ReferenceSoftwareTargetAdapter(
                args.observed_output_sha256,
                target_id=args.target_id or "reference-software-loopback",
            )
        else:
            if args.observed_output_sha256 is not None:
                parser.error(
                    "--observed-output-sha256 is invalid for unbound-fpga"
                )
            adapter = UnboundPhysicalTargetAdapter(
                target_id=args.target_id or "unbound-fpga-target",
            )
        receipt = execute_target_attempt(invocation, adapter)
        write_json_artifact(args.out, receipt)
        print(f"terminal state: {receipt['terminal_state']}")
        print(f"status: {receipt['qualification']['status']}")
        print(f"attempt sha256: {receipt['attempt_sha256']}")
        print(f"wrote: {args.out}")
        return 0 if receipt["qualification"]["accepted"] else 2

    receipt = _load(args.receipt)
    verify_execution_target_attempt(receipt)
    accepted = bool(receipt["qualification"]["accepted"])
    print(f"terminal state: {receipt['terminal_state']}")
    print(f"accepted: {accepted}")
    print(f"attempt sha256: {receipt['attempt_sha256']}")
    if args.require_accepted and not accepted:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
