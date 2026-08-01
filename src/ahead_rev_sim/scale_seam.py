"""Reference model for scale-seam communication, synchronization, and cost.

The receipt exposes the incremental tax introduced as accepted work crosses
tile, die, package, board, rack, and facility boundaries. It is a reference
model and measurement adapter, not a complete-system EVP claim.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .physical_serialization import is_sha256

SCALE_SEAM_SCHEMA_VERSION = "ahead.scale-seam-receipt/v0.1"
SCALE_SEAM_ARTIFACT_TYPE = "scale_seam_receipt"

SCALE_ORDER = (
    "operation",
    "tile",
    "die",
    "package",
    "board",
    "rack",
    "facility",
)
EVIDENCE_CLASSES = frozenset({"reference_model", "simulated", "measured"})


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


def _integer(
    value: Any,
    field: str,
    *,
    minimum: int = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _fraction(value: Any, field: str) -> float:
    result = _number(value, field)
    if result > 1:
        raise ValueError(f"{field} must be in the closed interval 0..1")
    return result


def _sha(
    value: Any,
    field: str,
    *,
    optional: bool = False,
) -> str | None:
    if value is None and optional:
        return None
    digest = _text(value, field)
    if not is_sha256(digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _strings(
    value: Any,
    field: str,
    *,
    minimum: int = 1,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be an array")
    result = [_text(item, f"{field}[]") for item in value]
    if len(result) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} entries")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} entries must be unique")
    return result


def _evidence(model: Mapping[str, Any]) -> tuple[str, list[str], float]:
    evidence_class = _text(model.get("evidence_class"), "model.evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValueError(
            f"model.evidence_class must be one of {sorted(EVIDENCE_CLASSES)}"
        )
    instruments = _strings(
        model.get("instrument_refs", []),
        "model.instrument_refs",
        minimum=1 if evidence_class == "measured" else 0,
    )
    uncertainty = _fraction(
        model.get("uncertainty_fraction", 0.0),
        "model.uncertainty_fraction",
    )
    return evidence_class, instruments, uncertainty


def _dominant(seams: Sequence[Mapping[str, Any]], field: str) -> str:
    return str(
        max(
            seams,
            key=lambda seam: (float(seam[field]), str(seam["seam_id"])),
        )["seam_id"]
    )


def build_scale_seam_receipt(source: Mapping[str, Any]) -> dict[str, Any]:
    """Validate, derive, and seal one scale-seam receipt."""

    workload_raw = _mapping(source.get("workload"), "workload")
    accepted_work_units = _number(
        workload_raw.get("accepted_work_units"),
        "workload.accepted_work_units",
        positive=True,
    )
    accepted = workload_raw.get("accepted")
    if not isinstance(accepted, bool):
        raise ValueError("workload.accepted must be a boolean")
    workload = {
        "contract_id": _text(workload_raw.get("contract_id"), "workload.contract_id"),
        "artifact_sha256": _sha(
            workload_raw.get("artifact_sha256"),
            "workload.artifact_sha256",
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
        "accepted": accepted,
        "result": workload_raw.get("result"),
    }

    model_raw = _mapping(source.get("model"), "model")
    evidence_class, instrument_refs, uncertainty_fraction = _evidence(model_raw)
    model = {
        "model_id": _text(model_raw.get("model_id"), "model.model_id"),
        "model_sha256": _sha(model_raw.get("model_sha256"), "model.model_sha256"),
        "evidence_class": evidence_class,
        "instrument_refs": instrument_refs,
        "uncertainty_fraction": uncertainty_fraction,
        "topology_sha256": _sha(
            model_raw.get("topology_sha256"),
            "model.topology_sha256",
            optional=True,
        ),
        "configuration_sha256": _sha(
            model_raw.get("configuration_sha256"),
            "model.configuration_sha256",
            optional=True,
        ),
        "environment_manifest_sha256": _sha(
            model_raw.get("environment_manifest_sha256"),
            "model.environment_manifest_sha256",
            optional=True,
        ),
        "clock_ref": _text(model_raw.get("clock_ref"), "model.clock_ref"),
    }

    raw_seams = source.get("seams")
    if not isinstance(raw_seams, Sequence) or isinstance(
        raw_seams, (str, bytes, bytearray)
    ) or not raw_seams:
        raise ValueError("seams must be a non-empty array")

    seams: list[dict[str, Any]] = []
    seam_ids: set[str] = set()
    previous_to_scale: str | None = None
    order = {scale: index for index, scale in enumerate(SCALE_ORDER)}
    failure_domains: set[str] = set()

    for index, raw in enumerate(raw_seams):
        seam_raw = _mapping(raw, f"seams[{index}]")
        seam_id = _text(seam_raw.get("seam_id"), f"seams[{index}].seam_id")
        if seam_id in seam_ids:
            raise ValueError(f"duplicate seam id: {seam_id}")
        seam_ids.add(seam_id)

        from_scale = _text(seam_raw.get("from_scale"), f"{seam_id}.from_scale")
        to_scale = _text(seam_raw.get("to_scale"), f"{seam_id}.to_scale")
        if from_scale not in order or to_scale not in order:
            raise ValueError(
                f"{seam_id}: scales must be drawn from {list(SCALE_ORDER)}"
            )
        if order[to_scale] != order[from_scale] + 1:
            raise ValueError(
                f"{seam_id}: scale seam must connect adjacent scale domains"
            )
        if previous_to_scale is not None and from_scale != previous_to_scale:
            raise ValueError(
                f"{seam_id}: seam chain must be contiguous from previous scale"
            )
        previous_to_scale = to_scale

        traffic_bytes = _integer(
            seam_raw.get("traffic_bytes"), f"{seam_id}.traffic_bytes"
        )
        message_count = _integer(
            seam_raw.get("message_count"), f"{seam_id}.message_count"
        )
        synchronization_events = _integer(
            seam_raw.get("synchronization_events"),
            f"{seam_id}.synchronization_events",
        )
        retries = _integer(seam_raw.get("retries", 0), f"{seam_id}.retries")
        latency_seconds = _number(
            seam_raw.get("latency_seconds"), f"{seam_id}.latency_seconds"
        )
        energy_joules = _number(
            seam_raw.get("energy_joules"), f"{seam_id}.energy_joules"
        )
        incremental_occupied_mm3 = _number(
            seam_raw.get("incremental_occupied_mm3"),
            f"{seam_id}.incremental_occupied_mm3",
        )
        utilization_fraction = _fraction(
            seam_raw.get("utilization_fraction"),
            f"{seam_id}.utilization_fraction",
        )
        seam_failure_domains = _strings(
            seam_raw.get("failure_domains", []),
            f"{seam_id}.failure_domains",
            minimum=0,
        )
        failure_domains.update(seam_failure_domains)

        seams.append(
            {
                "seam_id": seam_id,
                "from_scale": from_scale,
                "to_scale": to_scale,
                "traffic_bytes": traffic_bytes,
                "message_count": message_count,
                "synchronization_events": synchronization_events,
                "retries": retries,
                "latency_seconds": latency_seconds,
                "energy_joules": energy_joules,
                "incremental_occupied_mm3": incremental_occupied_mm3,
                "utilization_fraction": utilization_fraction,
                "failure_domains": seam_failure_domains,
                "traffic_bytes_per_accepted_work_unit": round(
                    traffic_bytes / accepted_work_units, 12
                ),
                "messages_per_accepted_work_unit": round(
                    message_count / accepted_work_units, 12
                ),
                "synchronization_events_per_accepted_work_unit": round(
                    synchronization_events / accepted_work_units, 12
                ),
                "retries_per_accepted_work_unit": round(
                    retries / accepted_work_units, 12
                ),
                "latency_seconds_per_accepted_work_unit": round(
                    latency_seconds / accepted_work_units, 12
                ),
                "energy_joules_per_accepted_work_unit": round(
                    energy_joules / accepted_work_units, 12
                ),
            }
        )

    totals = {
        "traffic_bytes": sum(seam["traffic_bytes"] for seam in seams),
        "message_count": sum(seam["message_count"] for seam in seams),
        "synchronization_events": sum(
            seam["synchronization_events"] for seam in seams
        ),
        "retries": sum(seam["retries"] for seam in seams),
        "latency_seconds": round(sum(seam["latency_seconds"] for seam in seams), 12),
        "energy_joules": round(sum(seam["energy_joules"] for seam in seams), 12),
        "incremental_occupied_mm3": round(
            sum(seam["incremental_occupied_mm3"] for seam in seams), 12
        ),
        "failure_domain_count": len(failure_domains),
        "failure_domains": sorted(failure_domains),
    }
    totals.update(
        {
            "traffic_bytes_per_accepted_work_unit": round(
                totals["traffic_bytes"] / accepted_work_units, 12
            ),
            "messages_per_accepted_work_unit": round(
                totals["message_count"] / accepted_work_units, 12
            ),
            "synchronization_events_per_accepted_work_unit": round(
                totals["synchronization_events"] / accepted_work_units, 12
            ),
            "retries_per_accepted_work_unit": round(
                totals["retries"] / accepted_work_units, 12
            ),
            "latency_seconds_per_accepted_work_unit": round(
                totals["latency_seconds"] / accepted_work_units, 12
            ),
            "energy_joules_per_accepted_work_unit": round(
                totals["energy_joules"] / accepted_work_units, 12
            ),
            "throughput_accepted_work_units_per_second": (
                round(accepted_work_units / totals["latency_seconds"], 12)
                if totals["latency_seconds"] > 0
                else None
            ),
        }
    )

    baseline_raw = source.get("baseline")
    baseline: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    if baseline_raw is not None:
        raw = _mapping(baseline_raw, "baseline")
        baseline = {
            "receipt_sha256": _sha(
                raw.get("receipt_sha256"), "baseline.receipt_sha256"
            ),
            "workload_contract_id": _text(
                raw.get("workload_contract_id"),
                "baseline.workload_contract_id",
            ),
            "topology_sha256": _sha(
                raw.get("topology_sha256"), "baseline.topology_sha256"
            ),
            "latency_seconds_per_accepted_work_unit": _number(
                raw.get("latency_seconds_per_accepted_work_unit"),
                "baseline.latency_seconds_per_accepted_work_unit",
            ),
            "energy_joules_per_accepted_work_unit": _number(
                raw.get("energy_joules_per_accepted_work_unit"),
                "baseline.energy_joules_per_accepted_work_unit",
            ),
            "incremental_occupied_mm3": _number(
                raw.get("incremental_occupied_mm3"),
                "baseline.incremental_occupied_mm3",
            ),
            "traffic_bytes_per_accepted_work_unit": _number(
                raw.get("traffic_bytes_per_accepted_work_unit"),
                "baseline.traffic_bytes_per_accepted_work_unit",
            ),
        }
        comparable = bool(
            baseline["workload_contract_id"] == workload["contract_id"]
            and baseline["topology_sha256"] == model["topology_sha256"]
        )

        def ratio(candidate: float, reference: float) -> float | None:
            return round(candidate / reference, 12) if reference > 0 else None

        comparison = {
            "baseline_receipt_sha256": baseline["receipt_sha256"],
            "comparable": comparable,
            "latency_ratio": ratio(
                totals["latency_seconds_per_accepted_work_unit"],
                baseline["latency_seconds_per_accepted_work_unit"],
            ),
            "energy_ratio": ratio(
                totals["energy_joules_per_accepted_work_unit"],
                baseline["energy_joules_per_accepted_work_unit"],
            ),
            "incremental_volume_ratio": ratio(
                totals["incremental_occupied_mm3"],
                baseline["incremental_occupied_mm3"],
            ),
            "traffic_ratio": ratio(
                totals["traffic_bytes_per_accepted_work_unit"],
                baseline["traffic_bytes_per_accepted_work_unit"],
            ),
            "complete_system_advantage_claim_allowed": False,
        }

    blockers: list[str] = []
    if not accepted:
        blockers.append("ACCEPTED_WORK_UNPROVEN")
    if evidence_class != "measured":
        blockers.append("SCALE_SEAMS_UNMEASURED")
    if evidence_class == "measured" and not instrument_refs:
        blockers.append("INSTRUMENT_CUSTODY_INCOMPLETE")
    if model["topology_sha256"] is None:
        blockers.append("TOPOLOGY_MANIFEST_MISSING")
    if model["configuration_sha256"] is None:
        blockers.append("CONFIGURATION_MANIFEST_MISSING")
    if model["environment_manifest_sha256"] is None:
        blockers.append("ENVIRONMENT_MANIFEST_MISSING")
    if baseline is None:
        blockers.append("BASELINE_MISSING_FOR_COMPARISON")
    elif comparison is not None and not comparison["comparable"]:
        blockers.append("BASELINE_TOPOLOGY_OR_WORKLOAD_MISMATCH")
    blockers.append("COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED")

    modeled_scale_seam_allowed = accepted
    measured_scale_seam_allowed = bool(
        accepted
        and evidence_class == "measured"
        and instrument_refs
        and model["topology_sha256"] is not None
        and model["configuration_sha256"] is not None
        and model["environment_manifest_sha256"] is not None
    )
    if not accepted:
        status = "refused"
    elif measured_scale_seam_allowed:
        status = "measured_scale_seam"
    else:
        status = "modeled_scale_seam"

    receipt: dict[str, Any] = {
        "schema_version": SCALE_SEAM_SCHEMA_VERSION,
        "artifact_type": SCALE_SEAM_ARTIFACT_TYPE,
        "workload": workload,
        "model": model,
        "seams": seams,
        "totals": totals,
        "dominant_seams": {
            "traffic": _dominant(seams, "traffic_bytes"),
            "latency": _dominant(seams, "latency_seconds"),
            "energy": _dominant(seams, "energy_joules"),
            "incremental_volume": _dominant(seams, "incremental_occupied_mm3"),
        },
        "baseline": baseline,
        "comparison": comparison,
        "qualification": {
            "status": status,
            "modeled_scale_seam_allowed": modeled_scale_seam_allowed,
            "measured_scale_seam_allowed": measured_scale_seam_allowed,
            "complete_system_advantage_claim_allowed": False,
            "blockers": list(dict.fromkeys(blockers)),
        },
        "claim_boundary": (
            "The receipt attributes incremental communication, synchronization, "
            "retry, latency, modeled or measured energy, occupied allocation, and "
            "failure-domain tax to explicit scale seams. It does not establish a "
            "complete-system advantage. Candidate and baseline must still enter a "
            "matched complete-system EVP receipt."
        ),
        "control_question": (
            "For the same accepted work and topology, what incremental movement, "
            "coordination, failure, latency, energy, and occupied allocation appears "
            "at each scale seam, and which measured behavior replaces the model?"
        ),
    }
    receipt["receipt_sha256"] = sha256(
        canonical_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt


def write_scale_seam_receipt(
    output_path: str | Path,
    receipt: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
