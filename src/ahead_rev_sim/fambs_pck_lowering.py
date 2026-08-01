"""Exact PCK reference and state-recoverable control lowering.

PCK is memory irregular and data dependent, but its generated piecewise index
transition is a permutation. The branch outcome is recoverable from the next
index, so reverse execution needs no path bit and no prior-index log. This
module proves that property exhaustively and emits a retained-final-state
space-time frontier for the complete accepted workload.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any

from .physical_substrate import OPTIONAL_RISCV_EXTENSION, PORTABLE_BINDING

PCK_LOWERING_SCHEMA_VERSION = "ahead.fambs-pck-lowering/v0.1"
PCK_LOWERING_ARTIFACT_TYPE = "fambs_memory_irregular_reversible_lowering"
PCK_SOURCE_COMMIT = "69498d4eebec9bed6f9c6793f13f9e20e89a866b"
PCK_SOURCE_BLOB = "fc75ef688c0dd81c17d3f647d0328797a3378d76"
PCK_EXPECTED_RESULT = "0000000006de4698"

_MASK32 = 0xFFFFFFFF
_LCG_A = 1103515245
_LCG_B = 12345
_LCG_A_INVERSE = pow(_LCG_A, -1, 1 << 32)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class PCKConfig:
    pool_size: int = 1024
    depth: int = 128
    iterations: int = 256

    def __post_init__(self) -> None:
        if self.pool_size != 1024:
            raise ValueError("the pinned PCK source contract requires pool_size=1024")
        if not 1 <= self.depth <= 256:
            raise ValueError("depth must be in the range 1..256")
        if self.iterations <= 0:
            raise ValueError("iterations must be positive")

    @property
    def is_default_contract(self) -> bool:
        return self == PCKConfig()


@dataclass(frozen=True)
class PCKPool:
    order: tuple[int, ...]
    payload: tuple[int, ...]
    next_index: tuple[int, ...]
    final_seed: int
    inverse_transition: tuple[int, ...]


@dataclass(frozen=True)
class PCKStrategyPoint:
    strategy_id: str
    retained_final_states: int
    output_result: str
    output_match: bool
    entry_state_restored: bool
    pool_state_restored: bool
    path_history_bits: int
    retained_state_bits: int
    peak_reversible_state_bits: int
    total_semantic_operations: int
    operation_delta_vs_conventional: int
    erasure_bits: int
    minimum_recovery_fraction_zero_support: float
    maximum_support_energy_units_at_80pct_recovery: float
    evidence_class: str = "exhaustive_control_map_and_reference_execution"
    pareto_nondominated: bool = True


@dataclass
class PCKLoweringArtifact:
    schema_version: str
    artifact_type: str
    generated_by: str
    source: dict[str, Any]
    accepted_output_contract: dict[str, Any]
    numeric_contract: dict[str, Any]
    initialization_proof: dict[str, Any]
    control_map_proof: dict[str, Any]
    source_reference: dict[str, Any]
    parity_baseline: dict[str, Any]
    frontier: list[PCKStrategyPoint]
    architecture_consequences: dict[str, Any]
    physical_handoff: dict[str, Any]
    qualification: dict[str, Any]
    claim_boundary: str
    control_question: str
    artifact_sha256: str | None = None

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_hash:
            payload.pop("artifact_sha256", None)
        return payload

    def seal(self) -> str:
        self.artifact_sha256 = sha256(
            _canonical_json(self.to_dict(include_hash=False)).encode("utf-8")
        ).hexdigest()
        return self.artifact_sha256

    def to_json(self, *, indent: int = 2) -> str:
        if self.artifact_sha256 is None:
            self.seal()
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"


def initialize_pool(config: PCKConfig = PCKConfig()) -> PCKPool:
    order = list(range(config.pool_size))
    seed = 12345
    for index in range(config.pool_size):
        seed = (seed * _LCG_A + _LCG_B) & _MASK32
        swap_index = seed % config.pool_size
        order[index], order[swap_index] = order[swap_index], order[index]

    payload = [order[index] * 7 for index in range(config.pool_size)]
    next_index = [order[(index + 1) % config.pool_size] for index in range(config.pool_size)]
    transition = [
        next_index[index]
        if payload[index] & 1
        else (index + 13) % config.pool_size
        for index in range(config.pool_size)
    ]
    if len(set(transition)) != config.pool_size:
        raise AssertionError("PCK index transition is not a permutation")
    inverse = [0] * config.pool_size
    for old_index, new_index in enumerate(transition):
        inverse[new_index] = old_index

    return PCKPool(
        order=tuple(order),
        payload=tuple(payload),
        next_index=tuple(next_index),
        final_seed=seed,
        inverse_transition=tuple(inverse),
    )


def prove_initialization_round_trip(
    pool: PCKPool,
    config: PCKConfig = PCKConfig(),
) -> dict[str, Any]:
    order = list(pool.order)
    seed = pool.final_seed

    payload_cleared = all(
        pool.payload[index] == pool.order[index] * 7
        for index in range(config.pool_size)
    )
    next_cleared = all(
        pool.next_index[index] == pool.order[(index + 1) % config.pool_size]
        for index in range(config.pool_size)
    )

    for index in reversed(range(config.pool_size)):
        swap_index = seed % config.pool_size
        order[index], order[swap_index] = order[swap_index], order[index]
        seed = ((seed - _LCG_B) * _LCG_A_INVERSE) & _MASK32

    return {
        "lcg_multiplier": _LCG_A,
        "lcg_increment": _LCG_B,
        "lcg_multiplier_inverse": _LCG_A_INVERSE,
        "final_seed": pool.final_seed,
        "seed_restored": seed == 12345,
        "order_restored": order == list(range(config.pool_size)),
        "payload_recomputable_into_clean_target": payload_cleared,
        "next_recomputable_into_clean_target": next_cleared,
        "history_bits": 0,
    }


def _forward_index(pool: PCKPool, index: int, config: PCKConfig) -> int:
    if pool.payload[index] & 1:
        return pool.next_index[index]
    return (index + 13) % config.pool_size


def pck_step(
    accumulator: int,
    index: int,
    pool: PCKPool,
    config: PCKConfig = PCKConfig(),
) -> tuple[int, int]:
    payload = pool.payload[index]
    return (
        (accumulator + payload) & _MASK32,
        _forward_index(pool, index, config),
    )


def pck_inverse_step(
    accumulator: int,
    index: int,
    pool: PCKPool,
) -> tuple[int, int]:
    old_index = pool.inverse_transition[index]
    payload = pool.payload[old_index]
    return ((accumulator - payload) & _MASK32, old_index)


def prove_control_map(pool: PCKPool, config: PCKConfig = PCKConfig()) -> dict[str, Any]:
    odd_images = {
        pool.next_index[index]
        for index in range(config.pool_size)
        if pool.payload[index] & 1
    }
    even_images = {
        (index + 13) % config.pool_size
        for index in range(config.pool_size)
        if not pool.payload[index] & 1
    }
    outputs = [_forward_index(pool, index, config) for index in range(config.pool_size)]

    round_trip = True
    accumulator_probes = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
    for old_index in range(config.pool_size):
        for accumulator in accumulator_probes:
            new_accumulator, new_index = pck_step(accumulator, old_index, pool, config)
            restored_accumulator, restored_index = pck_inverse_step(
                new_accumulator,
                new_index,
                pool,
            )
            if (restored_accumulator, restored_index) != (accumulator, old_index):
                round_trip = False
                break
        if not round_trip:
            break

    return {
        "domain_states": config.pool_size,
        "unique_outputs": len(set(outputs)),
        "odd_branch_domain": sum(pool.payload[index] & 1 != 0 for index in range(config.pool_size)),
        "even_branch_domain": sum(pool.payload[index] & 1 == 0 for index in range(config.pool_size)),
        "odd_branch_image": len(odd_images),
        "even_branch_image": len(even_images),
        "branch_image_intersection": len(odd_images & even_images),
        "combined_map_bijective": len(set(outputs)) == config.pool_size,
        "inverse_table_complete": sorted(pool.inverse_transition) == list(range(config.pool_size)),
        "sampled_accumulator_round_trip": round_trip,
        "path_history_bits_per_step": 0,
        "explanation": (
            "Both branch-local maps are injective and their image sets are disjoint. The next "
            "index therefore identifies the predecessor index and branch without a path bit."
        ),
    }


def pck_chase(
    start: int,
    depth: int,
    pool: PCKPool,
    config: PCKConfig = PCKConfig(),
) -> tuple[int, int]:
    accumulator = 0
    index = start
    for _ in range(depth):
        accumulator, index = pck_step(accumulator, index, pool, config)
    return accumulator, index


def pck_reverse_chase(
    accumulator: int,
    index: int,
    depth: int,
    pool: PCKPool,
) -> tuple[int, int]:
    for _ in range(depth):
        accumulator, index = pck_inverse_step(accumulator, index, pool)
    return accumulator, index


def pck_source_result(config: PCKConfig = PCKConfig()) -> int:
    pool = initialize_pool(config)
    sink = 0
    for iteration in range(config.iterations):
        result, _ = pck_chase(iteration % config.pool_size, config.depth, pool, config)
        sink = (sink + result) & _MASK32
    return sink


def _retained_indices(iterations: int, retained_count: int) -> set[int]:
    if not 0 <= retained_count <= iterations:
        raise ValueError("retained_count must be in the range 0..iterations")
    if retained_count == 0:
        return set()
    if retained_count == iterations:
        return set(range(iterations))
    return {
        min(iterations - 1, (slot * iterations) // retained_count)
        for slot in range(retained_count)
    }


def _prove_strategy(
    *,
    retained_count: int,
    pool: PCKPool,
    config: PCKConfig,
    pool_round_trip: bool,
    conventional_operations: int,
) -> PCKStrategyPoint:
    retained_set = _retained_indices(config.iterations, retained_count)
    if len(retained_set) != retained_count:
        raise AssertionError("retained-state schedule did not produce the requested cardinality")

    sink = 0
    retained: dict[int, tuple[int, int]] = {}
    all_local_restored = True

    for iteration in range(config.iterations):
        start = iteration % config.pool_size
        result, final_index = pck_chase(start, config.depth, pool, config)
        sink = (sink + result) & _MASK32
        if iteration in retained_set:
            retained[iteration] = (result, final_index)
        else:
            restored = pck_reverse_chase(result, final_index, config.depth, pool)
            all_local_restored &= restored == (0, start)

    output = sink

    for iteration in reversed(range(config.iterations)):
        start = iteration % config.pool_size
        if iteration in retained:
            result, final_index = retained.pop(iteration)
        else:
            result, final_index = pck_chase(start, config.depth, pool, config)
        sink = (sink - result) & _MASK32
        restored = pck_reverse_chase(result, final_index, config.depth, pool)
        all_local_restored &= restored == (0, start)

    step_operations = 4
    initialization_operations = 8 * config.pool_size
    chase_operations = config.depth * step_operations
    total_operations = (
        2 * initialization_operations
        + 1
        + 2 * config.iterations
        + retained_count * (2 * chase_operations)
        + (config.iterations - retained_count) * (4 * chase_operations)
    )
    retained_state_bits = retained_count * 42
    peak_state_bits = (
        retained_count * 42
        if retained_count == config.iterations
        else (retained_count + 1) * 42
    )
    minimum_recovery = max(
        0.0,
        min(1.0, 1.0 - conventional_operations / total_operations),
    )
    support_at_80pct = conventional_operations - 0.2 * total_operations
    output_result = f"{output:016x}"

    return PCKStrategyPoint(
        strategy_id=f"retain-{retained_count:03d}-final-chase-states",
        retained_final_states=retained_count,
        output_result=output_result,
        output_match=output_result == PCK_EXPECTED_RESULT,
        entry_state_restored=(sink == 0 and not retained and all_local_restored),
        pool_state_restored=pool_round_trip,
        path_history_bits=0,
        retained_state_bits=retained_state_bits,
        peak_reversible_state_bits=peak_state_bits,
        total_semantic_operations=total_operations,
        operation_delta_vs_conventional=total_operations - conventional_operations,
        erasure_bits=0,
        minimum_recovery_fraction_zero_support=round(minimum_recovery, 9),
        maximum_support_energy_units_at_80pct_recovery=round(support_at_80pct, 9),
    )


def analyze_pck(config: PCKConfig = PCKConfig()) -> PCKLoweringArtifact:
    pool = initialize_pool(config)
    initialization = prove_initialization_round_trip(pool, config)
    control = prove_control_map(pool, config)
    source_result = pck_source_result(config)

    chase_results: list[int] = []
    chase_round_trips = True
    for iteration in range(config.iterations):
        start = iteration % config.pool_size
        result, final_index = pck_chase(start, config.depth, pool, config)
        chase_results.append(result)
        chase_round_trips &= (
            pck_reverse_chase(result, final_index, config.depth, pool) == (0, start)
        )

    initialization_operations = 8 * config.pool_size
    chase_operations = config.depth * 4
    conventional_operations = (
        initialization_operations
        + config.iterations * chase_operations
        + config.iterations
    )
    pool_round_trip = all(
        (
            initialization["seed_restored"],
            initialization["order_restored"],
            initialization["payload_recomputable_into_clean_target"],
            initialization["next_recomputable_into_clean_target"],
        )
    )

    retained_counts = (0, 1, 2, 4, 8, 16, 32, 64, 128, config.iterations)
    frontier = [
        _prove_strategy(
            retained_count=count,
            pool=pool,
            config=config,
            pool_round_trip=pool_round_trip,
            conventional_operations=conventional_operations,
        )
        for count in retained_counts
    ]

    default_contract_match = config.is_default_contract and (
        f"{source_result:016x}" == PCK_EXPECTED_RESULT
    )
    all_restored = all(point.entry_state_restored for point in frontier)
    all_outputs = all(point.output_match for point in frontier)
    blockers = [
        "RISC_V_CODEGEN_UNIMPLEMENTED",
        "RISC_V_TARGET_RESULT_PARITY_UNQUALIFIED",
        "TARGET_MEMORY_SYSTEM_UNQUALIFIED",
        "PHYSICAL_SUBSTRATE_RESULT_UNMEASURED",
        "PHYSICAL_ENERGY_UNMEASURED",
        "TIMING_UNMEASURED",
        "OCCUPIED_VOLUME_UNMEASURED",
    ]
    if not default_contract_match:
        blockers.insert(0, "FAMBS_ACCEPTED_OUTPUT_MISMATCH")
    if not control["combined_map_bijective"] or not chase_round_trips or not all_restored:
        blockers.insert(0, "REVERSIBLE_RESTORATION_FAILED")

    artifact = PCKLoweringArtifact(
        schema_version=PCK_LOWERING_SCHEMA_VERSION,
        artifact_type=PCK_LOWERING_ARTIFACT_TYPE,
        generated_by="ahead-rev-sim/pck-lowering-v0.9-draft",
        source={
            "repository": "BigBirdReturns/future-ai-microbench-suite",
            "commit": PCK_SOURCE_COMMIT,
            "path": "src/pck_pointer_chase.c",
            "git_blob_sha1": PCK_SOURCE_BLOB,
            "configuration": asdict(config),
        },
        accepted_output_contract={
            "schema": "fambs.result/v1",
            "suite_version": "0.4.0",
            "contract_id": "fambs-v0.4.0-default",
            "bench": "PCK",
            "notes": "pointer_chase",
            "iters": 256,
            "result": PCK_EXPECTED_RESULT,
            "result_kind": "i32_sum_bits",
        },
        numeric_contract={
            "index_bits": 10,
            "accumulator_bits": 32,
            "accumulator_semantics": "unsigned_modular_model_of_default_nonoverflowing_int32_source",
            "default_max_chase_result": max(chase_results),
            "default_sink_within_signed_int32": sum(chase_results) < (1 << 31),
        },
        initialization_proof=initialization,
        control_map_proof=control,
        source_reference={
            "result": f"{source_result:016x}",
            "accepted_output_match": default_contract_match,
            "chase_round_trips": chase_round_trips,
            "minimum_chase_result": min(chase_results),
            "maximum_chase_result": max(chase_results),
            "chase_result_count": len(chase_results),
        },
        parity_baseline={
            "baseline_id": "conventional_full_workload_default_contract",
            "semantic_operations": conventional_operations,
            "initialization_operations": initialization_operations,
            "chase_operations": config.iterations * chase_operations,
            "sink_operations": config.iterations,
            "step_operation_model": [
                "payload_load",
                "accumulator_add",
                "parity_select",
                "next_load_or_modular_index_add",
            ],
            "evidence_class": "algorithmic_reference_not_measured_timing",
        },
        frontier=frontier,
        architecture_consequences={
            "control_class": "state_recoverable_piecewise_permutation",
            "branch_history_required": False,
            "prior_index_log_required": False,
            "inverse_mechanism": "inverse_transition_table_plus_modular_accumulator_subtract",
            "compiler_rule": (
                "Prove the combined state map before assigning branch-history cost. Data-dependent "
                "control does not imply information loss when successor state identifies the branch."
            ),
            "suggested_riscv_support": [
                "read_only_inverse_transition_table",
                "modular_accumulator_add_subtract",
                "dynamic_indexed_load",
                "reversible_local_state_retention_hint",
            ],
        },
        physical_handoff={
            "portable_binding": PORTABLE_BINDING,
            "optional_riscv_extension": OPTIONAL_RISCV_EXTENSION,
            "operator_classes": [
                "read_only_irregular_walk",
                "state_recoverable_piecewise_transition",
            ],
            "operand_channels": [
                "payload_i32_array",
                "next_index_u10_array",
                "start_index_u10",
                "depth_u32",
            ],
            "result_contract": {
                "result": PCK_EXPECTED_RESULT,
                "result_kind": "i32_sum_bits",
                "quality_rule": "exact default-contract identity",
            },
            "fallback": "pck_state_recoverable_reference_v1",
            "required_measurements": [
                "complete_boundary_joules",
                "latency",
                "occupied_volume",
                "thermal_state",
                "memory_read_energy",
                "control_energy",
                "inverse_table_energy",
            ],
        },
        qualification={
            "status": (
                "semantic_lowering_proved"
                if default_contract_match
                and control["combined_map_bijective"]
                and chase_round_trips
                and all_restored
                and all_outputs
                and pool_round_trip
                else "refused"
            ),
            "blockers": blockers,
            "accepted_output_match": default_contract_match and all_outputs,
            "entry_state_restored": all_restored and chase_round_trips and pool_round_trip,
            "path_history_eliminated": control["combined_map_bijective"],
            "riscv_codegen_qualified": False,
            "target_result_qualified": False,
            "physical_claim_allowed": False,
            "energy_claim_allowed": False,
        },
        claim_boundary=(
            "This artifact proves the default PCK semantic result, reversible initialization, the "
            "complete 1,024-state index permutation, zero-bit path-history recovery, all default "
            "chase round trips, and a retained-state work frontier. It does not prove emitted RISC-V "
            "code, target memory-system behavior, measured timing, physical substrate execution, "
            "energy, volume, thermal closure, or manufacturability."
        ),
        control_question=(
            "Before logging a data-dependent branch, can the successor state and immutable operand "
            "map reconstruct the predecessor and branch more cheaply than storing path history?"
        ),
    )
    artifact.seal()
    return artifact
