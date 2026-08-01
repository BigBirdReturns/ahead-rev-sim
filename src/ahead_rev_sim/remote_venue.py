"""Portable remote-venue submission, return, and substitution receipts.

Remote services may schedule and execute a sealed packet. They cannot redefine
accepted work or turn queue completion into local acceptance. The same packet
must be replayable locally and migratable to another venue.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .physical_serialization import is_sha256

REMOTE_SUBMISSION_SCHEMA_VERSION = "ahead.remote-venue-submission/v0.1"
REMOTE_RECEIPT_SCHEMA_VERSION = "ahead.remote-venue-receipt/v0.1"
REMOTE_COMPARISON_SCHEMA_VERSION = "ahead.remote-venue-comparison/v0.1"

TERMINAL_STATES = frozenset({"completed", "refused", "faulted", "cancelled"})


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def _sha(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    digest = _text(value, field)
    if not is_sha256(digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _number(
    value: Any,
    field: str,
    *,
    minimum: float = 0.0,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{field} must be finite")
    if positive and number <= minimum:
        raise ValueError(f"{field} must be greater than {minimum}")
    if not positive and number < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return number


def _strings(value: Any, field: str, *, minimum: int = 1) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be an array")
    result = [_text(item, f"{field}[]") for item in value]
    if len(result) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} entries")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} entries must be unique")
    return result


def _string_mapping(value: Any, field: str) -> dict[str, str]:
    raw = _mapping(value, field)
    return {
        _text(key, f"{field} key"): _text(item, f"{field}.{key}")
        for key, item in sorted(raw.items(), key=lambda pair: str(pair[0]))
    }


def _resource_mapping(value: Any, field: str) -> dict[str, int | float | str | bool]:
    raw = _mapping(value, field)
    result: dict[str, int | float | str | bool] = {}
    for key, item in sorted(raw.items(), key=lambda pair: str(pair[0])):
        normalized_key = _text(key, f"{field} key")
        if not isinstance(item, (int, float, str, bool)):
            raise ValueError(
                f"{field}.{normalized_key} must be a string, number, or boolean"
            )
        if isinstance(item, str) and not item.strip():
            raise ValueError(f"{field}.{normalized_key} cannot be empty")
        result[normalized_key] = item
    return result


def _file_entries(value: Any, field: str) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be an array")
    if not value:
        raise ValueError(f"{field} must contain at least one entry")
    entries: list[dict[str, str]] = []
    paths: set[str] = set()
    for index, raw in enumerate(value):
        item = _mapping(raw, f"{field}[{index}]")
        path = _text(item.get("path"), f"{field}[{index}].path")
        if path.startswith("/") or ".." in Path(path).parts:
            raise ValueError(f"{field}[{index}].path must be relative and traversal-free")
        if path in paths:
            raise ValueError(f"duplicate file path in {field}: {path}")
        paths.add(path)
        entries.append(
            {
                "path": path,
                "role": _text(item.get("role"), f"{field}[{index}].role"),
                "sha256": _sha(item.get("sha256"), f"{field}[{index}].sha256"),
            }
        )
    return sorted(entries, key=lambda item: item["path"])


def _artifact_entries(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be an array")
    entries: list[dict[str, Any]] = []
    paths: set[str] = set()
    for index, raw in enumerate(value):
        item = _mapping(raw, f"{field}[{index}]")
        path = _text(item.get("path"), f"{field}[{index}].path")
        if path.startswith("/") or ".." in Path(path).parts:
            raise ValueError(f"{field}[{index}].path must be relative and traversal-free")
        if path in paths:
            raise ValueError(f"duplicate returned artifact path: {path}")
        paths.add(path)
        entries.append(
            {
                "path": path,
                "role": _text(item.get("role"), f"{field}[{index}].role"),
                "sha256": _sha(item.get("sha256"), f"{field}[{index}].sha256"),
                "size_bytes": _integer(
                    item.get("size_bytes"),
                    f"{field}[{index}].size_bytes",
                ),
            }
        )
    return sorted(entries, key=lambda item: item["path"])


def _seal(payload: Mapping[str, Any], hash_field: str) -> dict[str, Any]:
    result = dict(payload)
    result[hash_field] = sha256(canonical_json(result).encode("utf-8")).hexdigest()
    return result


def _verify_seal(
    artifact: Mapping[str, Any],
    *,
    hash_field: str,
    field: str,
) -> None:
    claimed = _sha(artifact.get(hash_field), f"{field}.{hash_field}")
    unsigned = dict(artifact)
    unsigned.pop(hash_field, None)
    actual = sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    if claimed != actual:
        raise ValueError(f"{field} seal mismatch")


def build_remote_submission(source: Mapping[str, Any]) -> dict[str, Any]:
    """Build one venue-neutral sealed execution packet."""

    workload_raw = _mapping(source.get("workload"), "workload")
    accepted_work_units = _number(
        workload_raw.get("accepted_work_units"),
        "workload.accepted_work_units",
        positive=True,
    )
    workload = {
        "contract_id": _text(workload_raw.get("contract_id"), "workload.contract_id"),
        "artifact_sha256": _sha(
            workload_raw.get("artifact_sha256"),
            "workload.artifact_sha256",
        ),
        "accepted_output_sha256": _sha(
            workload_raw.get("accepted_output_sha256"),
            "workload.accepted_output_sha256",
        ),
        "accepted_work_unit": _text(
            workload_raw.get("accepted_work_unit"),
            "workload.accepted_work_unit",
        ),
        "accepted_work_units": accepted_work_units,
        "quality_rule": _text(
            workload_raw.get("quality_rule"),
            "workload.quality_rule",
        ),
    }

    execution_raw = _mapping(source.get("execution"), "execution")
    execution = {
        "command": _strings(execution_raw.get("command"), "execution.command"),
        "working_directory": _text(
            execution_raw.get("working_directory", "."),
            "execution.working_directory",
        ),
        "environment": _string_mapping(
            execution_raw.get("environment", {}),
            "execution.environment",
        ),
        "resource_request": _resource_mapping(
            execution_raw.get("resource_request", {}),
            "execution.resource_request",
        ),
        "timeout_seconds": _number(
            execution_raw.get("timeout_seconds"),
            "execution.timeout_seconds",
            positive=True,
        ),
        "software_fallback_id": _text(
            execution_raw.get("software_fallback_id"),
            "execution.software_fallback_id",
        ),
        "container_image_digest": _sha(
            execution_raw.get("container_image_digest"),
            "execution.container_image_digest",
            optional=True,
        ),
    }

    payload: dict[str, Any] = {
        "schema_version": REMOTE_SUBMISSION_SCHEMA_VERSION,
        "artifact_type": "remote_venue_submission",
        "submission_id": _text(source.get("submission_id"), "submission_id"),
        "workload": workload,
        "execution": execution,
        "files": _file_entries(source.get("files"), "files"),
        "required_return_artifacts": _strings(
            source.get("required_return_artifacts"),
            "required_return_artifacts",
        ),
        "requested_receipts": _strings(
            source.get("requested_receipts"),
            "requested_receipts",
        ),
        "policy": {
            "dependency_mode": "commodity_only",
            "provider_authority": "execution_only",
            "service_completion_is_acceptance": False,
            "raw_return_required": True,
            "local_replay_required": True,
            "migration_allowed": True,
        },
        "control_question": (
            "Can the same sealed packet execute at another venue while workload, "
            "fallback, required raw artifacts, local acceptance, and historical "
            "custody remain unchanged?"
        ),
    }
    return _seal(payload, "submission_sha256")


def build_remote_venue_receipt(
    submission: Mapping[str, Any],
    returned: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify one venue return locally and preserve refusal separately."""

    if submission.get("schema_version") != REMOTE_SUBMISSION_SCHEMA_VERSION:
        raise ValueError("unsupported remote submission schema")
    if submission.get("artifact_type") != "remote_venue_submission":
        raise ValueError("remote submission artifact_type is invalid")
    _verify_seal(submission, hash_field="submission_sha256", field="submission")

    venue_raw = _mapping(returned.get("venue"), "returned.venue")
    venue = {
        "venue_id": _text(venue_raw.get("venue_id"), "returned.venue.venue_id"),
        "venue_type": _text(
            venue_raw.get("venue_type"), "returned.venue.venue_type"
        ),
        "service_api": _text(
            venue_raw.get("service_api"), "returned.venue.service_api"
        ),
        "service_version": _text(
            venue_raw.get("service_version"), "returned.venue.service_version"
        ),
        "queue_id": _text(venue_raw.get("queue_id"), "returned.venue.queue_id"),
        "job_id": _text(venue_raw.get("job_id"), "returned.venue.job_id"),
    }

    terminal_state = _text(returned.get("terminal_state"), "returned.terminal_state")
    if terminal_state not in TERMINAL_STATES:
        raise ValueError(
            f"returned.terminal_state must be one of {sorted(TERMINAL_STATES)}"
        )
    started_ns = _integer(returned.get("started_ns"), "returned.started_ns")
    ended_ns = _integer(returned.get("ended_ns"), "returned.ended_ns")
    if ended_ns <= started_ns:
        raise ValueError("returned.ended_ns must be greater than started_ns")

    manifests_raw = _mapping(returned.get("manifests"), "returned.manifests")
    manifests = {
        "hardware_sha256": _sha(
            manifests_raw.get("hardware_sha256"),
            "returned.manifests.hardware_sha256",
            optional=True,
        ),
        "firmware_sha256": _sha(
            manifests_raw.get("firmware_sha256"),
            "returned.manifests.firmware_sha256",
            optional=True,
        ),
        "software_sha256": _sha(
            manifests_raw.get("software_sha256"),
            "returned.manifests.software_sha256",
            optional=True,
        ),
        "environment_sha256": _sha(
            manifests_raw.get("environment_sha256"),
            "returned.manifests.environment_sha256",
            optional=True,
        ),
    }
    raw_artifacts = _artifact_entries(
        returned.get("raw_artifacts", []), "returned.raw_artifacts"
    )
    accepted_output_sha256 = _sha(
        returned.get("accepted_output_sha256"),
        "returned.accepted_output_sha256",
        optional=True,
    )
    logs_sha256 = _sha(
        returned.get("logs_sha256"),
        "returned.logs_sha256",
        optional=True,
    )
    provider_receipt_sha256 = _sha(
        returned.get("provider_receipt_sha256"),
        "returned.provider_receipt_sha256",
        optional=True,
    )

    required_roles = set(map(str, submission["required_return_artifacts"]))
    returned_roles = {str(item["role"]) for item in raw_artifacts}
    missing_return_artifacts = sorted(required_roles - returned_roles)
    unexpected_return_artifacts = sorted(returned_roles - required_roles)
    output_matches = bool(
        accepted_output_sha256 is not None
        and accepted_output_sha256 == submission["workload"]["accepted_output_sha256"]
    )

    blockers: list[str] = []
    if terminal_state != "completed":
        blockers.append("VENUE_TERMINAL_STATE_NOT_COMPLETED")
    if missing_return_artifacts:
        blockers.append("REQUIRED_RAW_ARTIFACTS_MISSING")
    if not output_matches:
        blockers.append("ACCEPTED_OUTPUT_MISMATCH_OR_MISSING")
    if manifests["hardware_sha256"] is None:
        blockers.append("HARDWARE_MANIFEST_MISSING")
    if manifests["firmware_sha256"] is None:
        blockers.append("FIRMWARE_MANIFEST_MISSING")
    if manifests["software_sha256"] is None:
        blockers.append("SOFTWARE_MANIFEST_MISSING")
    if manifests["environment_sha256"] is None:
        blockers.append("ENVIRONMENT_MANIFEST_MISSING")
    if logs_sha256 is None:
        blockers.append("VENUE_LOGS_MISSING")
    if provider_receipt_sha256 is None:
        blockers.append("PROVIDER_RECEIPT_MISSING")

    service_completed = terminal_state == "completed"
    accepted_work_allowed = bool(
        service_completed
        and not missing_return_artifacts
        and output_matches
        and all(manifests.values())
        and logs_sha256 is not None
        and provider_receipt_sha256 is not None
    )

    payload: dict[str, Any] = {
        "schema_version": REMOTE_RECEIPT_SCHEMA_VERSION,
        "artifact_type": "remote_venue_receipt",
        "submission_sha256": submission["submission_sha256"],
        "submission_id": submission["submission_id"],
        "workload_contract_id": submission["workload"]["contract_id"],
        "expected_output_sha256": submission["workload"]["accepted_output_sha256"],
        "venue": venue,
        "terminal_state": terminal_state,
        "service_completed": service_completed,
        "started_ns": started_ns,
        "ended_ns": ended_ns,
        "elapsed_seconds": round((ended_ns - started_ns) / 1_000_000_000, 12),
        "manifests": manifests,
        "raw_artifacts": raw_artifacts,
        "required_return_artifacts": sorted(required_roles),
        "missing_return_artifacts": missing_return_artifacts,
        "unexpected_return_artifacts": unexpected_return_artifacts,
        "accepted_output_sha256": accepted_output_sha256,
        "output_matches": output_matches,
        "logs_sha256": logs_sha256,
        "provider_receipt_sha256": provider_receipt_sha256,
        "local_acceptance": "accepted" if accepted_work_allowed else "refused",
        "accepted_work_allowed": accepted_work_allowed,
        "migration_eligible": True,
        "blockers": blockers,
        "claim_boundary": (
            "Venue execution and queue completion are provider observations. "
            "Accepted work is decided locally from the sealed submission, required "
            "raw artifacts, output digest, manifests, logs, and provider receipt."
        ),
        "control_question": submission["control_question"],
    }
    return _seal(payload, "receipt_sha256")


def build_remote_venue_comparison(
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare the same sealed submission across at least two venues."""

    if not isinstance(receipts, Sequence) or isinstance(
        receipts, (str, bytes, bytearray)
    ) or len(receipts) < 2:
        raise ValueError("at least two remote venue receipts are required")

    normalized: list[Mapping[str, Any]] = []
    venue_ids: set[str] = set()
    for index, receipt in enumerate(receipts):
        if receipt.get("schema_version") != REMOTE_RECEIPT_SCHEMA_VERSION:
            raise ValueError(f"receipts[{index}] has unsupported schema")
        if receipt.get("artifact_type") != "remote_venue_receipt":
            raise ValueError(f"receipts[{index}] has invalid artifact_type")
        _verify_seal(receipt, hash_field="receipt_sha256", field=f"receipts[{index}]")
        venue_id = _text(
            _mapping(receipt.get("venue"), f"receipts[{index}].venue").get(
                "venue_id"
            ),
            f"receipts[{index}].venue.venue_id",
        )
        if venue_id in venue_ids:
            raise ValueError(f"duplicate venue in comparison: {venue_id}")
        venue_ids.add(venue_id)
        normalized.append(receipt)

    submission_shas = {str(item["submission_sha256"]) for item in normalized}
    workload_ids = {str(item["workload_contract_id"]) for item in normalized}
    expected_outputs = {str(item["expected_output_sha256"]) for item in normalized}
    if len(submission_shas) != 1:
        raise ValueError("remote venue comparison requires one sealed submission")
    if len(workload_ids) != 1 or len(expected_outputs) != 1:
        raise ValueError("remote venue comparison workload identity mismatch")

    accepted_receipts = [item for item in normalized if item["accepted_work_allowed"]]
    returned_outputs = {
        str(item["accepted_output_sha256"])
        for item in accepted_receipts
        if item["accepted_output_sha256"] is not None
    }
    output_consensus = bool(
        len(accepted_receipts) == len(normalized)
        and len(returned_outputs) == 1
        and next(iter(returned_outputs)) == next(iter(expected_outputs))
    )
    substitution_proved = bool(
        len(venue_ids) >= 2
        and len(accepted_receipts) == len(normalized)
        and output_consensus
    )

    payload: dict[str, Any] = {
        "schema_version": REMOTE_COMPARISON_SCHEMA_VERSION,
        "artifact_type": "remote_venue_comparison",
        "submission_sha256": next(iter(submission_shas)),
        "workload_contract_id": next(iter(workload_ids)),
        "expected_output_sha256": next(iter(expected_outputs)),
        "venue_ids": sorted(venue_ids),
        "receipt_sha256s": sorted(
            str(item["receipt_sha256"]) for item in normalized
        ),
        "accepted_venue_count": len(accepted_receipts),
        "refused_venue_count": len(normalized) - len(accepted_receipts),
        "output_consensus": output_consensus,
        "substitution_proved": substitution_proved,
        "claim_boundary": (
            "Substitution is proven only for the sealed workload packet, required "
            "returned artifacts, and local accepted-output rule exercised by these "
            "venues. It does not establish physical or EVP equivalence."
        ),
        "control_question": (
            "Can the same sealed packet move between at least two venue envelopes "
            "and produce locally accepted, digest-identical output with raw-return "
            "and manifest custody intact?"
        ),
    }
    return _seal(payload, "comparison_sha256")


def write_json_artifact(
    output_path: str | Path,
    artifact: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
