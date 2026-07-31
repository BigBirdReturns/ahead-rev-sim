"""Region partitioning, strategy construction, and normalized break-even models."""

from __future__ import annotations

from dataclasses import replace
import math
from typing import Iterable, Sequence

from .frontier_types import ArchitectureProfile, BreakEvenEnvelope, RegionRecord, StrategyPoint
from .isa import OpCode
from .semantics import OperationSemantics, SemanticClass

def _classification(record: OperationSemantics) -> str:
    return {
        SemanticClass.NATIVE_REVERSIBLE: "reversible",
        SemanticClass.CONDITIONALLY_REVERSIBLE: "conditional",
        SemanticClass.IRREVERSIBLE: "irreversible",
        SemanticClass.COMMIT: "commit",
        SemanticClass.INVALID: "invalid",
    }[record.semantic_class]


def _partition_regions(records: Sequence[OperationSemantics]) -> list[RegionRecord]:
    if not records:
        return []
    regions: list[RegionRecord] = []
    start = 0
    current = _classification(records[0])

    def emit(stop: int) -> None:
        chunk = records[start:stop]
        regions.append(
            RegionRecord(
                region_id=f"region-{len(regions):03d}",
                start_pc=chunk[0].pc,
                end_pc=chunk[-1].pc,
                classification=current,
                operation_count=len(chunk),
                opcodes=tuple(item.opcode for item in chunk),
                intrinsic_erasure_bits=sum(item.intrinsic_erasure_bits for item in chunk),
                reversal_metadata_bits=sum(item.reversal_metadata_bits for item in chunk),
                overwritten_state_bits=sum(item.overwritten_state_bits for item in chunk),
                hazards=tuple(hazard for item in chunk for hazard in item.hazards),
            )
        )

    for index in range(1, len(records)):
        kind = _classification(records[index])
        if kind != current:
            emit(index)
            start = index
            current = kind
    emit(len(records))
    return regions


def _count_crossings(domains: Iterable[str]) -> int:
    cleaned = [domain for domain in domains if domain in {"hot", "cold"}]
    return sum(1 for left, right in zip(cleaned, cleaned[1:]) if left != right)


def _break_even(
    *,
    baseline_operations: int,
    hot_operations: int,
    cold_operations: int,
    extra_operations: int,
    crossings: int,
    profile: ArchitectureProfile,
) -> BreakEvenEnvelope:
    baseline_energy = baseline_operations * profile.hot_energy_per_operation
    fixed_energy = (
        hot_operations * profile.hot_energy_per_operation
        + crossings * profile.transition_energy_per_crossing
        + profile.power_clock_overhead_energy
    )
    cold_count = cold_operations + extra_operations
    cold_gross = cold_count * profile.cold_gross_energy_per_operation

    if cold_gross == 0:
        min_recovery = None
        energy_status = "no_cold_domain_work"
    else:
        min_recovery = 1.0 - ((baseline_energy - fixed_energy) / cold_gross)
        if min_recovery <= 0:
            energy_status = "parity_without_recovery_under_profile"
        elif min_recovery < 1:
            energy_status = "recovery_threshold_feasible_under_profile"
        else:
            energy_status = "parity_impossible_under_profile"

    baseline_cycles = baseline_operations * profile.hot_cycles_per_operation
    fixed_cycles = (
        hot_operations * profile.hot_cycles_per_operation
        + crossings * profile.transition_cycles_per_crossing
    )
    if cold_count == 0:
        max_multiplier = None
        runtime_status = "no_cold_domain_work"
    else:
        available = baseline_cycles - fixed_cycles
        max_cold_cycles_per_op = available / cold_count
        max_multiplier = max_cold_cycles_per_op / profile.hot_cycles_per_operation
        runtime_status = (
            "runtime_parity_feasible_under_profile"
            if max_multiplier >= 0
            else "runtime_parity_impossible_under_profile"
        )

    return BreakEvenEnvelope(
        baseline_energy_units=round(baseline_energy, 9),
        fixed_transformed_energy_units=round(fixed_energy, 9),
        cold_gross_energy_units=round(cold_gross, 9),
        minimum_recovery_fraction_for_energy_parity=(round(min_recovery, 9) if min_recovery is not None else None),
        energy_parity_status=energy_status,
        baseline_cycles=round(baseline_cycles, 9),
        fixed_transformed_cycles=round(fixed_cycles, 9),
        cold_operation_count=cold_count,
        maximum_cold_cycle_multiplier_for_runtime_parity=(round(max_multiplier, 9) if max_multiplier is not None else None),
        runtime_parity_status=runtime_status,
    )


def _strategy_points(records: Sequence[OperationSemantics], profile: ArchitectureProfile) -> list[StrategyPoint]:
    effective = [record for record in records if record.opcode != OpCode.HALT.name]
    baseline = len(effective)
    invalid_count = sum(record.semantic_class == SemanticClass.INVALID for record in effective)
    commit_count = sum(record.semantic_class == SemanticClass.COMMIT for record in records)
    intrinsic_bits = sum(record.intrinsic_erasure_bits for record in effective)
    metadata_bits = sum(record.reversal_metadata_bits for record in effective)
    overwritten_bits = [record.overwritten_state_bits for record in effective if record.overwritten_state_bits]

    points: list[StrategyPoint] = []

    definitions = (
        ("native-regions", "executable_semantics", False, False),
        ("history-complete", "modeled_storage_required", True, False),
        ("uncompute-candidate", "requires_liveness_and_lowering_proof", False, True),
    )

    for strategy_id, proof_status, preserve_history, uncompute in definitions:
        domains: list[str] = []
        hot = 0
        cold = 0
        commits = commit_count + invalid_count
        extra = 0
        assumptions: list[str] = []

        for record in effective:
            if record.semantic_class == SemanticClass.NATIVE_REVERSIBLE:
                domains.append("cold")
                cold += 1
            elif record.semantic_class == SemanticClass.CONDITIONALLY_REVERSIBLE:
                if record.opcode == OpCode.BEQ.name or preserve_history or uncompute:
                    domains.append("cold")
                    cold += 1
                else:
                    domains.append("hot")
                    hot += 1
                    commits += 1
            elif record.semantic_class == SemanticClass.IRREVERSIBLE:
                if uncompute:
                    domains.append("cold")
                    cold += 1
                    extra += 2
                else:
                    domains.append("hot")
                    hot += 1
                    if not preserve_history:
                        commits += 1
            else:
                domains.append("hot")
                hot += 1

        crossings = _count_crossings(domains)
        if preserve_history:
            history_bits = intrinsic_bits + metadata_bits
            restorable = sum(
                record.semantic_class not in {SemanticClass.INVALID, SemanticClass.COMMIT}
                for record in effective
            )
            assumptions.append("all overwritten state remains available until reverse traversal")
        elif uncompute:
            history_bits = metadata_bits
            restorable = sum(record.semantic_class != SemanticClass.INVALID for record in effective)
            assumptions.extend(
                (
                    "compiler proves liveness and alias constraints",
                    "ancilla can be uncomputed before reuse",
                    "modeled extra operations are not measured cycles",
                )
            )
        else:
            history_bits = metadata_bits
            restorable = sum(
                record.semantic_class == SemanticClass.NATIVE_REVERSIBLE
                or record.opcode == OpCode.BEQ.name
                for record in effective
            )

        ancilla_bytes = math.ceil(max(overwritten_bits, default=0) / 8) if uncompute else 0
        fraction = restorable / baseline if baseline else 1.0
        point = StrategyPoint(
            strategy_id=strategy_id,
            proof_status=proof_status,
            history_bits=history_bits,
            ancilla_peak_bytes=ancilla_bytes,
            extra_operations=extra,
            hot_operations=hot,
            cold_operations=cold,
            commit_boundaries=commits,
            domain_crossings=crossings,
            restorable_operation_fraction=round(fraction, 9),
            break_even=_break_even(
                baseline_operations=baseline,
                hot_operations=hot,
                cold_operations=cold,
                extra_operations=extra,
                crossings=crossings,
                profile=profile,
            ),
            assumptions=tuple(assumptions),
        )
        points.append(point)

    return _mark_pareto(points)


def _mark_pareto(points: list[StrategyPoint]) -> list[StrategyPoint]:
    result: list[StrategyPoint] = []
    for candidate in points:
        candidate_vector = (
            candidate.history_bits,
            candidate.ancilla_peak_bytes,
            candidate.extra_operations,
            candidate.commit_boundaries,
        )
        dominated = False
        for other in points:
            if other is candidate:
                continue
            other_vector = (
                other.history_bits,
                other.ancilla_peak_bytes,
                other.extra_operations,
                other.commit_boundaries,
            )
            if all(a <= b for a, b in zip(other_vector, candidate_vector)) and any(
                a < b for a, b in zip(other_vector, candidate_vector)
            ):
                dominated = True
                break
        result.append(replace(candidate, pareto_nondominated=not dominated))
    return result


