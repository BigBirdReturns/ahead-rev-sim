"""Causal custody for state, entropy, environment, calibration, and time.

The receipt maps events from multiple clock domains into one bounded interval,
checks explicit causal edges under uncertainty, binds raw trace manifests and
accepted output, and keeps reference, simulated, and measured evidence tiers
separate. It does not establish physical-compute or EVP advantage.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .physical_serialization import is_sha256

CAUSAL_CUSTODY_SCHEMA_VERSION = "ahead.causal-custody-receipt/v0.1"
CAUSAL_CUSTODY_ARTIFACT_TYPE = "causal_custody_receipt"

EVIDENCE_CLASSES = frozenset({"reference_model", "simulated", "measured"})
DETERMINISM_CLASSES = frozenset(
    {"exact", "replay_with_trace", "distributional"}
)


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


def _integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _number(
    value: Any,
    field: str,
    *,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{field} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return number


def _fraction(value: Any, field: str) -> float:
    result = _number(value, field, minimum=0.0)
    if result > 1:
        raise ValueError(f"{field} must be in the closed interval 0..1")
    return result


def _strings(value: Any, field: str, *, minimum: int = 1) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be an array")
    result = [_text(item, f"{field}[]") for item in value]
    if len(result) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} entries")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} entries must be unique")
    return result


def _mapped_timestamp(local_ns: int, offset_ns: int, rate_ppb: float) -> int:
    rate_adjustment = round(local_ns * rate_ppb / 1_000_000_000)
    return local_ns + offset_ns + rate_adjustment


def _unique_event(events: Sequence[Mapping[str, Any]], kind: str) -> Mapping[str, Any] | None:
    matches = [event for event in events if event["event_kind"] == kind]
    return matches[0] if len(matches) == 1 else None


def build_causal_custody_receipt(source: Mapping[str, Any]) -> dict[str, Any]:
    """Validate, align, qualify, and seal a multi-clock causal record."""

    workload_raw = _mapping(source.get("workload"), "workload")
    accepted = workload_raw.get("accepted")
    if not isinstance(accepted, bool):
        raise ValueError("workload.accepted must be a boolean")
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
        "accepted_work_units": _number(
            workload_raw.get("accepted_work_units"),
            "workload.accepted_work_units",
            minimum=0.000000000001,
        ),
        "quality_rule": _text(
            workload_raw.get("quality_rule"),
            "workload.quality_rule",
        ),
        "accepted": accepted,
    }

    determinism_raw = _mapping(source.get("determinism"), "determinism")
    determinism_class = _text(
        determinism_raw.get("determinism_class"),
        "determinism.determinism_class",
    )
    if determinism_class not in DETERMINISM_CLASSES:
        raise ValueError(
            "determinism.determinism_class must be one of "
            f"{sorted(DETERMINISM_CLASSES)}"
        )
    entropy_trace_sha256 = _sha(
        determinism_raw.get("entropy_trace_sha256"),
        "determinism.entropy_trace_sha256",
        optional=True,
    )
    stochastic_path_sha256 = _sha(
        determinism_raw.get("stochastic_path_sha256"),
        "determinism.stochastic_path_sha256",
        optional=True,
    )
    if determinism_class == "replay_with_trace" and (
        entropy_trace_sha256 is None or stochastic_path_sha256 is None
    ):
        raise ValueError(
            "replay_with_trace determinism requires entropy and stochastic-path traces"
        )
    determinism = {
        "determinism_class": determinism_class,
        "entropy_trace_sha256": entropy_trace_sha256,
        "stochastic_path_sha256": stochastic_path_sha256,
    }

    interval_raw = _mapping(source.get("interval"), "interval")
    start_ns = _integer(
        interval_raw.get("start_ns"), "interval.start_ns", minimum=0
    )
    end_ns = _integer(interval_raw.get("end_ns"), "interval.end_ns", minimum=1)
    if end_ns <= start_ns:
        raise ValueError("interval.end_ns must be greater than interval.start_ns")
    reference_clock_id = _text(
        interval_raw.get("reference_clock_id"),
        "interval.reference_clock_id",
    )
    interval = {
        "reference_clock_id": reference_clock_id,
        "start_ns": start_ns,
        "end_ns": end_ns,
        "duration_seconds": round((end_ns - start_ns) / 1_000_000_000, 12),
    }

    raw_clocks = source.get("clocks")
    if not isinstance(raw_clocks, Sequence) or isinstance(
        raw_clocks, (str, bytes, bytearray)
    ) or not raw_clocks:
        raise ValueError("clocks must be a non-empty array")
    clocks: list[dict[str, Any]] = []
    clock_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_clocks):
        clock_raw = _mapping(raw, f"clocks[{index}]")
        clock_id = _text(clock_raw.get("clock_id"), f"clocks[{index}].clock_id")
        if clock_id in clock_by_id:
            raise ValueError(f"duplicate clock id: {clock_id}")
        evidence_class = _text(
            clock_raw.get("evidence_class"),
            f"clocks[{index}].evidence_class",
        )
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(
                f"{clock_id}: evidence_class must be one of {sorted(EVIDENCE_CLASSES)}"
            )
        instrument_ref = clock_raw.get("instrument_ref")
        if instrument_ref is not None:
            instrument_ref = _text(
                instrument_ref, f"clocks[{index}].instrument_ref"
            )
        if evidence_class == "measured" and instrument_ref is None:
            raise ValueError(f"{clock_id}: measured clock requires instrument_ref")
        mapping_raw = _mapping(
            clock_raw.get("mapping"), f"clocks[{index}].mapping"
        )
        clock = {
            "clock_id": clock_id,
            "clock_kind": _text(
                clock_raw.get("clock_kind"), f"clocks[{index}].clock_kind"
            ),
            "evidence_class": evidence_class,
            "instrument_ref": instrument_ref,
            "calibration_sha256": _sha(
                clock_raw.get("calibration_sha256"),
                f"clocks[{index}].calibration_sha256",
                optional=True,
            ),
            "environment_sha256": _sha(
                clock_raw.get("environment_sha256"),
                f"clocks[{index}].environment_sha256",
                optional=True,
            ),
            "mapping": {
                "offset_ns": _integer(
                    mapping_raw.get("offset_ns"),
                    f"clocks[{index}].mapping.offset_ns",
                ),
                "rate_ppb": _number(
                    mapping_raw.get("rate_ppb", 0.0),
                    f"clocks[{index}].mapping.rate_ppb",
                ),
                "uncertainty_ns": _number(
                    mapping_raw.get("uncertainty_ns"),
                    f"clocks[{index}].mapping.uncertainty_ns",
                    minimum=0.0,
                ),
            },
        }
        clocks.append(clock)
        clock_by_id[clock_id] = clock
    if reference_clock_id not in clock_by_id:
        raise ValueError("interval.reference_clock_id is not declared in clocks")
    reference_mapping = clock_by_id[reference_clock_id]["mapping"]
    if reference_mapping["offset_ns"] != 0 or reference_mapping["rate_ppb"] != 0:
        raise ValueError("reference clock must use zero offset and zero rate correction")

    required_event_kinds = _strings(
        source.get("required_event_kinds"),
        "required_event_kinds",
    )
    raw_events = source.get("events")
    if not isinstance(raw_events, Sequence) or isinstance(
        raw_events, (str, bytes, bytearray)
    ) or not raw_events:
        raise ValueError("events must be a non-empty array")

    events: list[dict[str, Any]] = []
    event_by_id: dict[str, dict[str, Any]] = {}
    last_local_by_clock: dict[str, tuple[int, int]] = {}
    for index, raw in enumerate(raw_events):
        event_raw = _mapping(raw, f"events[{index}]")
        event_id = _text(event_raw.get("event_id"), f"events[{index}].event_id")
        if event_id in event_by_id:
            raise ValueError(f"duplicate event id: {event_id}")
        clock_id = _text(event_raw.get("clock_id"), f"events[{index}].clock_id")
        if clock_id not in clock_by_id:
            raise ValueError(f"{event_id}: unknown clock {clock_id}")
        local_timestamp_ns = _integer(
            event_raw.get("local_timestamp_ns"),
            f"events[{index}].local_timestamp_ns",
            minimum=0,
        )
        sequence = _integer(
            event_raw.get("sequence"),
            f"events[{index}].sequence",
            minimum=0,
        )
        previous = last_local_by_clock.get(clock_id)
        current = (local_timestamp_ns, sequence)
        if previous is not None and current <= previous:
            raise ValueError(
                f"{event_id}: events must be strictly ordered within clock {clock_id}"
            )
        last_local_by_clock[clock_id] = current

        mapping = clock_by_id[clock_id]["mapping"]
        global_timestamp_ns = _mapped_timestamp(
            local_timestamp_ns,
            int(mapping["offset_ns"]),
            float(mapping["rate_ppb"]),
        )
        uncertainty_ns = float(mapping["uncertainty_ns"])
        if not start_ns <= global_timestamp_ns <= end_ns:
            raise ValueError(
                f"{event_id}: mapped timestamp is outside the custody interval"
            )
        event = {
            "event_id": event_id,
            "event_kind": _text(
                event_raw.get("event_kind"), f"events[{index}].event_kind"
            ),
            "source_role": _text(
                event_raw.get("source_role"), f"events[{index}].source_role"
            ),
            "clock_id": clock_id,
            "local_timestamp_ns": local_timestamp_ns,
            "sequence": sequence,
            "artifact_sha256": _sha(
                event_raw.get("artifact_sha256"),
                f"events[{index}].artifact_sha256",
                optional=True,
            ),
            "value_sha256": _sha(
                event_raw.get("value_sha256"),
                f"events[{index}].value_sha256",
                optional=True,
            ),
            "global_timestamp_ns": global_timestamp_ns,
            "lower_bound_ns": global_timestamp_ns - uncertainty_ns,
            "upper_bound_ns": global_timestamp_ns + uncertainty_ns,
        }
        events.append(event)
        event_by_id[event_id] = event
    events.sort(
        key=lambda event: (
            event["global_timestamp_ns"],
            event["sequence"],
            event["event_id"],
        )
    )

    raw_edges = source.get("causal_edges")
    if not isinstance(raw_edges, Sequence) or isinstance(
        raw_edges, (str, bytes, bytearray)
    ) or not raw_edges:
        raise ValueError("causal_edges must be a non-empty array")
    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str]] = set()
    unresolved_edges: list[str] = []
    for index, raw in enumerate(raw_edges):
        edge_raw = _mapping(raw, f"causal_edges[{index}]")
        from_event_id = _text(
            edge_raw.get("from_event_id"),
            f"causal_edges[{index}].from_event_id",
        )
        to_event_id = _text(
            edge_raw.get("to_event_id"),
            f"causal_edges[{index}].to_event_id",
        )
        relation = _text(
            edge_raw.get("relation"), f"causal_edges[{index}].relation"
        )
        if from_event_id not in event_by_id or to_event_id not in event_by_id:
            raise ValueError("causal edge references an unknown event")
        key = (from_event_id, to_event_id, relation)
        if key in edge_keys:
            raise ValueError(f"duplicate causal edge: {key}")
        edge_keys.add(key)
        source_event = event_by_id[from_event_id]
        target_event = event_by_id[to_event_id]
        resolved = source_event["upper_bound_ns"] < target_event["lower_bound_ns"]
        edge_id = f"{from_event_id}->{to_event_id}:{relation}"
        if not resolved:
            unresolved_edges.append(edge_id)
        edges.append(
            {
                "edge_id": edge_id,
                "from_event_id": from_event_id,
                "to_event_id": to_event_id,
                "relation": relation,
                "resolved": resolved,
                "minimum_separation_ns": round(
                    target_event["lower_bound_ns"]
                    - source_event["upper_bound_ns"],
                    6,
                ),
            }
        )

    manifests_raw = _mapping(source.get("trace_manifests"), "trace_manifests")
    trace_manifests = {
        "execution_sha256": _sha(
            manifests_raw.get("execution_sha256"),
            "trace_manifests.execution_sha256",
            optional=True,
        ),
        "telemetry_sha256": _sha(
            manifests_raw.get("telemetry_sha256"),
            "trace_manifests.telemetry_sha256",
            optional=True,
        ),
        "power_sha256": _sha(
            manifests_raw.get("power_sha256"),
            "trace_manifests.power_sha256",
            optional=True,
        ),
        "thermal_sha256": _sha(
            manifests_raw.get("thermal_sha256"),
            "trace_manifests.thermal_sha256",
            optional=True,
        ),
        "environment_sha256": _sha(
            manifests_raw.get("environment_sha256"),
            "trace_manifests.environment_sha256",
            optional=True,
        ),
        "calibration_sha256": _sha(
            manifests_raw.get("calibration_sha256"),
            "trace_manifests.calibration_sha256",
            optional=True,
        ),
    }

    kind_counts = Counter(str(event["event_kind"]) for event in events)
    role_counts = Counter(str(event["source_role"]) for event in events)
    missing_event_kinds = sorted(
        set(required_event_kinds) - set(kind_counts)
    )
    duplicate_singletons = sorted(
        kind
        for kind in ("workload_start", "workload_end", "accepted_output")
        if kind_counts[kind] != 1
    )
    workload_start = _unique_event(events, "workload_start")
    workload_end = _unique_event(events, "workload_end")
    accepted_output = _unique_event(events, "accepted_output")
    output_matches = bool(
        accepted_output is not None
        and accepted_output["value_sha256"] == workload["accepted_output_sha256"]
    )

    power_events = [event for event in events if event["event_kind"] == "power_sample"]
    power_covers_interval = bool(
        workload_start is not None
        and workload_end is not None
        and any(
            event["upper_bound_ns"] <= workload_start["lower_bound_ns"]
            for event in power_events
        )
        and any(
            event["lower_bound_ns"] >= workload_end["upper_bound_ns"]
            for event in power_events
        )
    )
    calibration_event = _unique_event(events, "calibration_applied")
    environment_event = _unique_event(events, "environment_sample")
    calibration_precedes_work = bool(
        calibration_event is not None
        and workload_start is not None
        and calibration_event["upper_bound_ns"] < workload_start["lower_bound_ns"]
    )
    environment_precedes_work = bool(
        environment_event is not None
        and workload_start is not None
        and environment_event["upper_bound_ns"] < workload_start["lower_bound_ns"]
    )

    blockers: list[str] = []
    if not accepted:
        blockers.append("ACCEPTED_WORK_UNPROVEN")
    if missing_event_kinds:
        blockers.append("REQUIRED_EVENT_KINDS_MISSING")
    if duplicate_singletons:
        blockers.append("SINGLETON_EVENT_CARDINALITY_INVALID")
    if unresolved_edges:
        blockers.append("CAUSAL_ORDER_UNRESOLVED")
    if not output_matches:
        blockers.append("ACCEPTED_OUTPUT_MISMATCH_OR_MISSING")
    if not power_covers_interval:
        blockers.append("POWER_TRACE_DOES_NOT_BRACKET_WORK")
    if not calibration_precedes_work:
        blockers.append("CALIBRATION_NOT_BOUND_BEFORE_WORK")
    if not environment_precedes_work:
        blockers.append("ENVIRONMENT_NOT_BOUND_BEFORE_WORK")
    missing_manifests = sorted(
        key for key, value in trace_manifests.items() if value is None
    )
    if missing_manifests:
        blockers.append("TRACE_MANIFESTS_INCOMPLETE")

    all_measured = all(clock["evidence_class"] == "measured" for clock in clocks)
    all_instrumented = all(clock["instrument_ref"] is not None for clock in clocks)
    if not all_measured:
        blockers.append("CAUSAL_CUSTODY_UNMEASURED")
    if not all_instrumented:
        blockers.append("INSTRUMENT_CUSTODY_UNMEASURED")
    blockers.append("COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED")

    reference_custody_allowed = bool(
        accepted
        and not missing_event_kinds
        and not duplicate_singletons
        and not unresolved_edges
        and output_matches
        and power_covers_interval
        and calibration_precedes_work
        and environment_precedes_work
        and not missing_manifests
    )
    measured_custody_allowed = bool(
        reference_custody_allowed and all_measured and all_instrumented
    )
    if not reference_custody_allowed:
        status = "refused"
    elif measured_custody_allowed:
        status = "measured_causal_custody"
    else:
        status = "reference_causal_custody"

    receipt: dict[str, Any] = {
        "schema_version": CAUSAL_CUSTODY_SCHEMA_VERSION,
        "artifact_type": CAUSAL_CUSTODY_ARTIFACT_TYPE,
        "workload": workload,
        "determinism": determinism,
        "interval": interval,
        "clocks": sorted(clocks, key=lambda clock: clock["clock_id"]),
        "required_event_kinds": sorted(required_event_kinds),
        "events": events,
        "causal_edges": sorted(edges, key=lambda edge: edge["edge_id"]),
        "trace_manifests": trace_manifests,
        "summary": {
            "clock_count": len(clocks),
            "event_count": len(events),
            "causal_edge_count": len(edges),
            "resolved_causal_edge_count": sum(edge["resolved"] for edge in edges),
            "unresolved_causal_edge_ids": sorted(unresolved_edges),
            "event_kind_counts": dict(sorted(kind_counts.items())),
            "source_role_counts": dict(sorted(role_counts.items())),
            "missing_event_kinds": missing_event_kinds,
            "duplicate_singleton_event_kinds": duplicate_singletons,
            "maximum_clock_uncertainty_ns": max(
                float(clock["mapping"]["uncertainty_ns"]) for clock in clocks
            ),
            "power_covers_work_interval": power_covers_interval,
            "calibration_precedes_work": calibration_precedes_work,
            "environment_precedes_work": environment_precedes_work,
            "accepted_output_matches": output_matches,
        },
        "qualification": {
            "status": status,
            "reference_causal_custody_allowed": reference_custody_allowed,
            "measured_causal_custody_allowed": measured_custody_allowed,
            "physical_compute_claim_allowed": False,
            "complete_system_advantage_claim_allowed": False,
            "blockers": list(dict.fromkeys(blockers)),
        },
        "claim_boundary": (
            "The receipt establishes causal alignment, event completeness, trace "
            "identity, and accepted-output custody for the declared interval. It "
            "does not establish that a physical substrate performed useful work or "
            "that the complete system has an EVP advantage."
        ),
        "control_question": (
            "Can an independent acceptor reconstruct the same event order and "
            "accepted interval from clock mappings, uncertainty, state and entropy "
            "traces, environment, calibration, instruments, and raw manifests?"
        ),
    }
    receipt["receipt_sha256"] = sha256(
        canonical_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt


def write_causal_custody_receipt(
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
