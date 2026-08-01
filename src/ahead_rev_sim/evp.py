"""First-class Energy, Volume, and Performance receipts.

EVP is emitted as a measured vector, never as a policy-weighted scalar.  The
receipt binds accepted work, the measurement boundary, energy flows, occupied
volume, performance, provenance, and an optional comparable baseline.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .physical_serialization import is_sha256

EVP_SCHEMA_VERSION = "ahead.evp-receipt/v0.1"
EVP_ARTIFACT_TYPE = "energy_volume_performance_receipt"

EVIDENCE_CLASSES = frozenset({"reference_model", "simulated", "measured"})
CLAIM_SCOPES = frozenset({"component", "subsystem", "complete_system"})


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _string(value: Any, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _number(
    value: Any,
    name: str,
    *,
    minimum: float = 0.0,
    strictly_positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if strictly_positive and number <= minimum:
        raise ValueError(f"{name} must be greater than {minimum}")
    if not strictly_positive and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be finite")
    return number


def _fraction(value: Any, name: str) -> float:
    result = _number(value, name)
    if result > 1:
        raise ValueError(f"{name} must be in the closed interval 0..1")
    return result


def _sha256(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    digest = _string(value, name)
    if not is_sha256(digest):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _string_list(value: Any, name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} must be an array")
    result = [_string(item, f"{name}[]") for item in value]
    if not allow_empty and not result:
        raise ValueError(f"{name} must contain at least one entry")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} entries must be unique")
    return result


def _nonnegative_map(value: Any, name: str, *, allow_empty: bool = False) -> dict[str, float]:
    source = _mapping(value, name)
    result = {
        _string(key, f"{name} key"): _number(item, f"{name}.{key}")
        for key, item in source.items()
    }
    if not allow_empty and not result:
        raise ValueError(f"{name} must contain at least one entry")
    return dict(sorted(result.items()))


def _evidence(section: Mapping[str, Any], name: str) -> tuple[str, list[str], float]:
    evidence_class = _string(section.get("evidence_class"), f"{name}.evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValueError(
            f"{name}.evidence_class must be one of {sorted(EVIDENCE_CLASSES)}"
        )
    instruments = _string_list(
        section.get("instrument_refs", []),
        f"{name}.instrument_refs",
        allow_empty=evidence_class != "measured",
    )
    uncertainty = _fraction(
        section.get("uncertainty_fraction", 0.0),
        f"{name}.uncertainty_fraction",
    )
    return evidence_class, instruments, uncertainty


def _supplier_chain(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("provenance.supplier_chain must be an array")
    suppliers: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        supplier = _mapping(raw, f"provenance.supplier_chain[{index}]")
        artifact = supplier.get("artifact_sha256")
        suppliers.append(
            {
                "actor": _string(
                    supplier.get("actor"),
                    f"provenance.supplier_chain[{index}].actor",
                ),
                "component_role": _string(
                    supplier.get("component_role"),
                    f"provenance.supplier_chain[{index}].component_role",
                ),
                "implementation_id": _string(
                    supplier.get("implementation_id"),
                    f"provenance.supplier_chain[{index}].implementation_id",
                ),
                "artifact_sha256": _sha256(
                    artifact,
                    f"provenance.supplier_chain[{index}].artifact_sha256",
                    optional=True,
                ),
            }
        )
    return suppliers


def _baseline(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    baseline = _mapping(value, "baseline")
    claim_scope = _string(baseline.get("claim_scope"), "baseline.claim_scope")
    if claim_scope not in CLAIM_SCOPES:
        raise ValueError(f"baseline.claim_scope must be one of {sorted(CLAIM_SCOPES)}")
    return {
        "receipt_sha256": _sha256(
            baseline.get("receipt_sha256"),
            "baseline.receipt_sha256",
        ),
        "workload_contract_id": _string(
            baseline.get("workload_contract_id"),
            "baseline.workload_contract_id",
        ),
        "boundary_id": _string(
            baseline.get("boundary_id"),
            "baseline.boundary_id",
        ),
        "claim_scope": claim_scope,
        "environment_manifest_sha256": _sha256(
            baseline.get("environment_manifest_sha256"),
            "baseline.environment_manifest_sha256",
        ),
        "net_physical_joules_per_accepted_work_unit": _number(
            baseline.get("net_physical_joules_per_accepted_work_unit"),
            "baseline.net_physical_joules_per_accepted_work_unit",
        ),
        "occupied_mm3": _number(
            baseline.get("occupied_mm3"),
            "baseline.occupied_mm3",
            strictly_positive=True,
        ),
        "throughput_accepted_work_units_per_second": _number(
            baseline.get("throughput_accepted_work_units_per_second"),
            "baseline.throughput_accepted_work_units_per_second",
            strictly_positive=True,
        ),
        "latency_seconds": _number(
            baseline.get("latency_seconds"),
            "baseline.latency_seconds",
            strictly_positive=True,
        ),
    }


def _comparison(
    candidate: Mapping[str, float],
    baseline: Mapping[str, Any] | None,
    *,
    comparable: bool,
) -> dict[str, Any] | None:
    if baseline is None:
        return None

    energy_ratio = (
        candidate["net_physical_joules_per_accepted_work_unit"]
        / baseline["net_physical_joules_per_accepted_work_unit"]
        if baseline["net_physical_joules_per_accepted_work_unit"] > 0
        else None
    )
    volume_ratio = candidate["occupied_mm3"] / baseline["occupied_mm3"]
    throughput_ratio = (
        candidate["throughput_accepted_work_units_per_second"]
        / baseline["throughput_accepted_work_units_per_second"]
    )
    latency_ratio = candidate["latency_seconds"] / baseline["latency_seconds"]

    no_worse = (
        candidate["net_physical_joules_per_accepted_work_unit"]
        <= baseline["net_physical_joules_per_accepted_work_unit"]
        and candidate["occupied_mm3"] <= baseline["occupied_mm3"]
        and candidate["throughput_accepted_work_units_per_second"]
        >= baseline["throughput_accepted_work_units_per_second"]
        and candidate["latency_seconds"] <= baseline["latency_seconds"]
    )
    strictly_better = (
        candidate["net_physical_joules_per_accepted_work_unit"]
        < baseline["net_physical_joules_per_accepted_work_unit"]
        or candidate["occupied_mm3"] < baseline["occupied_mm3"]
        or candidate["throughput_accepted_work_units_per_second"]
        > baseline["throughput_accepted_work_units_per_second"]
        or candidate["latency_seconds"] < baseline["latency_seconds"]
    )
    return {
        "baseline_receipt_sha256": baseline["receipt_sha256"],
        "comparable": comparable,
        "energy_ratio": round(energy_ratio, 12) if energy_ratio is not None else None,
        "volume_ratio": round(volume_ratio, 12),
        "throughput_ratio": round(throughput_ratio, 12),
        "latency_ratio": round(latency_ratio, 12),
        "pareto_dominates_baseline": bool(comparable and no_worse and strictly_better),
        "scalar_score_allowed": False,
    }


def build_evp_receipt(source: Mapping[str, Any]) -> dict[str, Any]:
    """Validate, derive, qualify, and seal one EVP vector receipt."""

    workload_raw = _mapping(source.get("workload"), "workload")
    accepted_work_units = _number(
        workload_raw.get("accepted_work_units"),
        "workload.accepted_work_units",
        strictly_positive=True,
    )
    workload = {
        "contract_id": _string(workload_raw.get("contract_id"), "workload.contract_id"),
        "artifact_sha256": _sha256(
            workload_raw.get("artifact_sha256"),
            "workload.artifact_sha256",
        ),
        "accepted_work_unit": _string(
            workload_raw.get("accepted_work_unit"),
            "workload.accepted_work_unit",
        ),
        "accepted_work_units": accepted_work_units,
        "result": workload_raw.get("result"),
        "quality_rule": _string(
            workload_raw.get("quality_rule"),
            "workload.quality_rule",
        ),
        "accepted": _boolean(workload_raw.get("accepted"), "workload.accepted"),
    }

    boundary_raw = _mapping(source.get("boundary"), "boundary")
    claim_scope = _string(boundary_raw.get("claim_scope"), "boundary.claim_scope")
    if claim_scope not in CLAIM_SCOPES:
        raise ValueError(f"boundary.claim_scope must be one of {sorted(CLAIM_SCOPES)}")
    start_ns = int(
        _number(boundary_raw.get("measurement_start_ns"), "boundary.measurement_start_ns")
    )
    end_ns = int(
        _number(boundary_raw.get("measurement_end_ns"), "boundary.measurement_end_ns")
    )
    if end_ns <= start_ns:
        raise ValueError("boundary.measurement_end_ns must be greater than start")
    boundary = {
        "boundary_id": _string(boundary_raw.get("boundary_id"), "boundary.boundary_id"),
        "claim_scope": claim_scope,
        "included_components": _string_list(
            boundary_raw.get("included_components"),
            "boundary.included_components",
        ),
        "excluded_components": _string_list(
            boundary_raw.get("excluded_components", []),
            "boundary.excluded_components",
            allow_empty=True,
        ),
        "allocation_rule": _string(
            boundary_raw.get("allocation_rule"),
            "boundary.allocation_rule",
        ),
        "measurement_start_ns": start_ns,
        "measurement_end_ns": end_ns,
        "concurrency": _number(
            boundary_raw.get("concurrency", 1),
            "boundary.concurrency",
            strictly_positive=True,
        ),
    }

    energy_raw = _mapping(source.get("energy"), "energy")
    energy_evidence, energy_instruments, energy_uncertainty = _evidence(
        energy_raw, "energy"
    )
    external_supply = _number(
        energy_raw.get("external_supply_joules"),
        "energy.external_supply_joules",
    )
    ambient_harvested = _number(
        energy_raw.get("ambient_harvested_joules", 0.0),
        "energy.ambient_harvested_joules",
    )
    signal_coupled = _number(
        energy_raw.get("signal_coupled_joules", 0.0),
        "energy.signal_coupled_joules",
    )
    recovered = _number(
        energy_raw.get("recovered_joules", 0.0),
        "energy.recovered_joules",
    )
    measurement_overhead = _number(
        energy_raw.get("measurement_overhead_joules", 0.0),
        "energy.measurement_overhead_joules",
    )
    gross_physical_input = external_supply + ambient_harvested + signal_coupled
    if recovered > gross_physical_input:
        raise ValueError(
            "energy.recovered_joules cannot exceed declared physical energy inputs"
        )
    net_physical = gross_physical_input - recovered
    net_external = external_supply - recovered
    breakdown = _nonnegative_map(
        energy_raw.get("breakdown_joules", {}),
        "energy.breakdown_joules",
        allow_empty=True,
    )
    breakdown_total = sum(breakdown.values())
    breakdown_error_fraction = (
        abs(breakdown_total - gross_physical_input)
        / max(gross_physical_input, breakdown_total)
        if gross_physical_input or breakdown_total
        else 0.0
    )
    energy = {
        "evidence_class": energy_evidence,
        "instrument_refs": energy_instruments,
        "uncertainty_fraction": energy_uncertainty,
        "external_supply_joules": external_supply,
        "ambient_harvested_joules": ambient_harvested,
        "signal_coupled_joules": signal_coupled,
        "recovered_joules": recovered,
        "measurement_overhead_joules": measurement_overhead,
        "breakdown_joules": breakdown,
        "breakdown_total_joules": round(breakdown_total, 12),
        "breakdown_error_fraction": round(breakdown_error_fraction, 12),
        "gross_physical_input_joules": round(gross_physical_input, 12),
        "net_physical_joules": round(net_physical, 12),
        "net_external_joules": round(net_external, 12),
        "instrumented_total_joules": round(net_physical + measurement_overhead, 12),
        "net_physical_joules_per_accepted_work_unit": round(
            net_physical / accepted_work_units, 12
        ),
        "net_external_joules_per_accepted_work_unit": round(
            net_external / accepted_work_units, 12
        ),
    }

    volume_raw = _mapping(source.get("volume"), "volume")
    volume_evidence, volume_instruments, volume_uncertainty = _evidence(
        volume_raw, "volume"
    )
    components_mm3 = _nonnegative_map(
        volume_raw.get("components_mm3"),
        "volume.components_mm3",
    )
    occupied_mm3 = sum(components_mm3.values())
    if occupied_mm3 <= 0:
        raise ValueError("volume.components_mm3 must declare positive occupied volume")
    volume = {
        "evidence_class": volume_evidence,
        "instrument_refs": volume_instruments,
        "uncertainty_fraction": volume_uncertainty,
        "allocation_rule": _string(
            volume_raw.get("allocation_rule"),
            "volume.allocation_rule",
        ),
        "components_mm3": components_mm3,
        "occupied_mm3": round(occupied_mm3, 12),
        "mm3_per_concurrent_work_unit": round(
            occupied_mm3 / boundary["concurrency"], 12
        ),
    }

    performance_raw = _mapping(source.get("performance"), "performance")
    performance_evidence, performance_instruments, performance_uncertainty = _evidence(
        performance_raw, "performance"
    )
    elapsed_seconds = _number(
        performance_raw.get("elapsed_seconds"),
        "performance.elapsed_seconds",
        strictly_positive=True,
    )
    latency_seconds = _number(
        performance_raw.get("latency_seconds"),
        "performance.latency_seconds",
        strictly_positive=True,
    )
    p95_latency_raw = performance_raw.get("p95_latency_seconds")
    p95_latency = (
        _number(
            p95_latency_raw,
            "performance.p95_latency_seconds",
            strictly_positive=True,
        )
        if p95_latency_raw is not None
        else None
    )
    if p95_latency is not None and p95_latency < latency_seconds:
        raise ValueError(
            "performance.p95_latency_seconds cannot be below latency_seconds"
        )
    observed_interval_seconds = (end_ns - start_ns) / 1_000_000_000
    interval_error_fraction = abs(elapsed_seconds - observed_interval_seconds) / max(
        observed_interval_seconds, elapsed_seconds
    )
    performance = {
        "evidence_class": performance_evidence,
        "instrument_refs": performance_instruments,
        "uncertainty_fraction": performance_uncertainty,
        "clock_kind": _string(
            performance_raw.get("clock_kind"),
            "performance.clock_kind",
        ),
        "clock_ref": _string(
            performance_raw.get("clock_ref"),
            "performance.clock_ref",
        ),
        "elapsed_seconds": elapsed_seconds,
        "boundary_interval_seconds": round(observed_interval_seconds, 12),
        "interval_error_fraction": round(interval_error_fraction, 12),
        "latency_seconds": latency_seconds,
        "p95_latency_seconds": p95_latency,
        "throughput_accepted_work_units_per_second": round(
            accepted_work_units / elapsed_seconds, 12
        ),
    }

    provenance_raw = _mapping(source.get("provenance"), "provenance")
    provenance = {
        "implementation_id": _string(
            provenance_raw.get("implementation_id"),
            "provenance.implementation_id",
        ),
        "implementation_class": _string(
            provenance_raw.get("implementation_class"),
            "provenance.implementation_class",
        ),
        "substrate_receipt_sha256": _sha256(
            provenance_raw.get("substrate_receipt_sha256"),
            "provenance.substrate_receipt_sha256",
            optional=True,
        ),
        "host_proof_sha256": _sha256(
            provenance_raw.get("host_proof_sha256"),
            "provenance.host_proof_sha256",
            optional=True,
        ),
        "compiler_artifact_sha256": _sha256(
            provenance_raw.get("compiler_artifact_sha256"),
            "provenance.compiler_artifact_sha256",
            optional=True,
        ),
        "measurement_manifest_sha256": _sha256(
            provenance_raw.get("measurement_manifest_sha256"),
            "provenance.measurement_manifest_sha256",
            optional=True,
        ),
        "environment_manifest_sha256": _sha256(
            provenance_raw.get("environment_manifest_sha256"),
            "provenance.environment_manifest_sha256",
            optional=True,
        ),
        "calibration_manifest_sha256": _sha256(
            provenance_raw.get("calibration_manifest_sha256"),
            "provenance.calibration_manifest_sha256",
            optional=True,
        ),
        "supplier_chain": _supplier_chain(provenance_raw.get("supplier_chain")),
    }

    baseline = _baseline(source.get("baseline"))
    baseline_comparable = bool(
        baseline
        and baseline["workload_contract_id"] == workload["contract_id"]
        and baseline["boundary_id"] == boundary["boundary_id"]
        and baseline["claim_scope"] == boundary["claim_scope"]
        and baseline["environment_manifest_sha256"]
        == provenance["environment_manifest_sha256"]
    )

    candidate_vector = {
        "net_physical_joules_per_accepted_work_unit": energy[
            "net_physical_joules_per_accepted_work_unit"
        ],
        "occupied_mm3": volume["occupied_mm3"],
        "throughput_accepted_work_units_per_second": performance[
            "throughput_accepted_work_units_per_second"
        ],
        "latency_seconds": performance["latency_seconds"],
    }
    comparison = _comparison(
        candidate_vector,
        baseline,
        comparable=baseline_comparable,
    )

    blockers: list[str] = []
    if not workload["accepted"]:
        blockers.append("ACCEPTED_WORK_UNPROVEN")
    if energy_evidence != "measured":
        blockers.append("ENERGY_UNMEASURED")
    if volume_evidence != "measured":
        blockers.append("VOLUME_UNMEASURED")
    if performance_evidence != "measured":
        blockers.append("PERFORMANCE_UNMEASURED")
    if claim_scope != "complete_system":
        blockers.append("COMPLETE_SYSTEM_BOUNDARY_NOT_DECLARED")
    if boundary["excluded_components"]:
        blockers.append("BOUNDARY_EXCLUSIONS_PRESENT")
    if not all((energy_instruments, volume_instruments, performance_instruments)):
        blockers.append("INSTRUMENT_CUSTODY_INCOMPLETE")
    if breakdown_error_fraction > max(0.01, energy_uncertainty):
        blockers.append("ENERGY_BREAKDOWN_INCOMPLETE")
    if provenance["measurement_manifest_sha256"] is None:
        blockers.append("MEASUREMENT_MANIFEST_MISSING")
    if provenance["environment_manifest_sha256"] is None:
        blockers.append("ENVIRONMENT_MANIFEST_MISSING")
    if provenance["calibration_manifest_sha256"] is None:
        blockers.append("CALIBRATION_MANIFEST_MISSING")
    if interval_error_fraction > max(0.01, performance_uncertainty):
        blockers.append("PERFORMANCE_INTERVAL_MISMATCH")
    if baseline is None:
        blockers.append("BASELINE_MISSING_FOR_ADVANTAGE")
    elif not baseline_comparable:
        blockers.append("BASELINE_BOUNDARY_MISMATCH")

    measured_vector_allowed = bool(
        workload["accepted"]
        and energy_evidence == "measured"
        and volume_evidence == "measured"
        and performance_evidence == "measured"
        and all((energy_instruments, volume_instruments, performance_instruments))
    )
    complete_system_measurement_allowed = bool(
        measured_vector_allowed
        and claim_scope == "complete_system"
        and not boundary["excluded_components"]
        and "PERFORMANCE_INTERVAL_MISMATCH" not in blockers
        and "ENERGY_BREAKDOWN_INCOMPLETE" not in blockers
        and provenance["measurement_manifest_sha256"] is not None
        and provenance["environment_manifest_sha256"] is not None
        and provenance["calibration_manifest_sha256"] is not None
    )
    pareto_dominates = bool(
        comparison and comparison["pareto_dominates_baseline"]
    )
    advantage_claim_allowed = bool(
        complete_system_measurement_allowed
        and baseline_comparable
        and pareto_dominates
    )

    if not workload["accepted"]:
        status = "refused"
    elif measured_vector_allowed:
        status = "measured_evp_vector"
    else:
        status = "modeled_evp_vector"

    receipt: dict[str, Any] = {
        "schema_version": EVP_SCHEMA_VERSION,
        "artifact_type": EVP_ARTIFACT_TYPE,
        "workload": workload,
        "boundary": boundary,
        "energy": energy,
        "volume": volume,
        "performance": performance,
        "provenance": provenance,
        "baseline": baseline,
        "comparison": comparison,
        "qualification": {
            "status": status,
            "measured_evp_vector_allowed": measured_vector_allowed,
            "complete_system_measurement_allowed": complete_system_measurement_allowed,
            "advantage_claim_allowed": advantage_claim_allowed,
            "blockers": list(dict.fromkeys(blockers)),
        },
        "claim_boundary": (
            "The receipt reports Energy, Volume, and Performance as a workload-bound "
            "vector. It does not emit a policy-weighted scalar. A complete-system "
            "advantage requires accepted work, measured E/V/P, instrument custody, a "
            "closed boundary, a comparable baseline, and Pareto improvement."
        ),
        "control_question": (
            "For the same accepted work and measurement boundary, does the candidate "
            "use no more net physical energy and occupied volume while delivering no "
            "less throughput and no greater latency than the sealed baseline?"
        ),
    }
    receipt["receipt_sha256"] = sha256(
        canonical_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt


def write_evp_receipt(
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
