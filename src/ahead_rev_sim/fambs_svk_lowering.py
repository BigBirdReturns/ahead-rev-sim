"""Exact binary32 SVK reference and reversible space-time lowerings.

The first structured FAMBS lowering starts from the accepted v0.4.0 SVK
result. It reproduces the source arithmetic with separate binary32 multiply
and add rounding, proves exact output identity, and then applies Bennett-style
checkpoint pebbling to the dot reduction and outer sink recurrence.

Algorithmic loop-invariant motion is applied to both the conventional parity
baseline and the reversible strategies. Work eliminated by ordinary compiler
optimization is never credited to physical reversibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import struct
from typing import Any, Callable

from .physical_substrate import OPTIONAL_RISCV_EXTENSION, PORTABLE_BINDING

SVK_LOWERING_SCHEMA_VERSION = "ahead.fambs-svk-lowering/v0.1"
SVK_LOWERING_ARTIFACT_TYPE = "fambs_structured_reversible_lowering"
SVK_SOURCE_COMMIT = "69498d4eebec9bed6f9c6793f13f9e20e89a866b"
SVK_SOURCE_BLOB = "cc581df1181f6eeaa8592d22189c4c42b222bb80"
SVK_EXPECTED_RESULT = "000000004700158d"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _f32(value: float | int) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _f32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def _f32_from_bits(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]


@dataclass(frozen=True)
class SVKConfig:
    vector_length: int = 2048
    nnz: int = 128
    iterations: int = 1000

    def __post_init__(self) -> None:
        if not 1 <= self.vector_length <= 2048:
            raise ValueError("vector_length must be in the range 1..2048")
        if not 1 <= self.nnz <= 256:
            raise ValueError("nnz must be in the range 1..256")
        if self.iterations <= 0:
            raise ValueError("iterations must be positive")

    @property
    def is_default_contract(self) -> bool:
        return self == SVKConfig()


@dataclass(frozen=True)
class RoundTripProof:
    output_bits: int
    entry_state_restored: bool
    peak_history_words: int
    checkpoint_words: int
    transition_count: int


@dataclass(frozen=True)
class SVKStrategyPoint:
    strategy_id: str
    dot_strategy: str
    dot_span: int | None
    sink_strategy: str
    sink_span: int | None
    output_result: str
    output_match: bool
    dot_state_restored: bool
    sink_state_restored: bool
    entry_state_restored: bool
    peak_support_bits: int
    accepted_output_bits_excluded_from_peak: int
    total_semantic_operations: int
    operation_delta_vs_optimized_conventional: int
    history_bits_written: int
    checkpoint_copy_operations: int
    erasure_bits: int
    minimum_recovery_fraction_zero_support: float
    maximum_support_energy_units_at_80pct_recovery: float
    evidence_class: str = "semantic_reference_and_normalized_break_even"
    pareto_nondominated: bool = True


@dataclass
class SVKLoweringArtifact:
    schema_version: str
    artifact_type: str
    generated_by: str
    source: dict[str, Any]
    accepted_output_contract: dict[str, Any]
    numeric_contract: dict[str, Any]
    source_reference: dict[str, Any]
    parity_baseline: dict[str, Any]
    diagnostic_source_lowering: dict[str, Any]
    frontier: list[SVKStrategyPoint]
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


def _svk_vectors(config: SVKConfig) -> tuple[tuple[int, ...], tuple[float, ...], tuple[float, ...]]:
    f01 = _f32(0.1)
    f001 = _f32(0.01)
    dense = tuple(
        _f32(f01 * _f32((index % 7) + 1))
        for index in range(config.vector_length)
    )
    indices = tuple((item * 17) % config.vector_length for item in range(config.nnz))
    values = tuple(_f32(f001 * _f32(item + 1)) for item in range(config.nnz))
    return indices, values, dense


def svk_dot(config: SVKConfig = SVKConfig()) -> float:
    indices, values, dense = _svk_vectors(config)
    accumulator = _f32(0.0)
    for item in range(config.nnz):
        product = _f32(values[item] * dense[indices[item]])
        accumulator = _f32(accumulator + product)
    return accumulator


def svk_source_result(config: SVKConfig = SVKConfig()) -> int:
    dot = svk_dot(config)
    sink = _f32(0.0)
    for _ in range(config.iterations):
        sink = _f32(sink + dot)
    return _f32_bits(sink)


def _dot_transition(config: SVKConfig) -> Callable[[int, int], int]:
    indices, values, dense = _svk_vectors(config)

    def transition(accumulator_bits: int, step: int) -> int:
        accumulator = _f32_from_bits(accumulator_bits)
        product = _f32(values[step] * dense[indices[step]])
        return _f32_bits(_f32(accumulator + product))

    return transition


def _sink_transition(dot_bits: int) -> Callable[[int, int], int]:
    dot = _f32_from_bits(dot_bits)

    def transition(sink_bits: int, _step: int) -> int:
        return _f32_bits(_f32(_f32_from_bits(sink_bits) + dot))

    return transition


def prove_linear_round_trip(
    *,
    total_steps: int,
    transition: Callable[[int, int], int],
    entry_bits: int = 0,
) -> RoundTripProof:
    state = entry_bits
    history: list[int] = []
    for step in range(total_steps):
        history.append(state)
        state = transition(state, step)
    output_bits = state
    peak = len(history)
    for old_state in reversed(history):
        state = old_state
    return RoundTripProof(
        output_bits=output_bits,
        entry_state_restored=state == entry_bits,
        peak_history_words=peak,
        checkpoint_words=0,
        transition_count=2 * total_steps,
    )


def _pebble_peak_states(total_steps: int, span: int) -> tuple[int, int]:
    if span <= 0:
        raise ValueError("checkpoint span must be positive")
    segments = math.ceil(total_steps / span)
    peak = 0
    for segment in range(segments):
        steps = min(span, total_steps - segment * span)
        retained_checkpoints = segment + 1
        peak = max(peak, retained_checkpoints + steps)
    return peak, segments


def prove_checkpoint_round_trip(
    *,
    total_steps: int,
    span: int,
    transition: Callable[[int, int], int],
    entry_bits: int = 0,
) -> RoundTripProof:
    if span <= 0:
        raise ValueError("checkpoint span must be positive")

    checkpoints: list[int] = [entry_bits]
    peak_states = 0
    segments = math.ceil(total_steps / span)

    for segment in range(segments):
        start_step = segment * span
        steps = min(span, total_steps - start_step)
        state = checkpoints[-1]
        local_history: list[int] = []
        for offset in range(steps):
            local_history.append(state)
            state = transition(state, start_step + offset)
        checkpoints.append(state)
        peak_states = max(peak_states, len(checkpoints) - 1 + len(local_history))
        for old_state in reversed(local_history):
            state = old_state
        if state != checkpoints[-2]:
            raise AssertionError("checkpoint forward cleanup did not restore its segment entry")

    output_bits = checkpoints[-1]

    for segment in reversed(range(segments)):
        start_step = segment * span
        steps = min(span, total_steps - start_step)
        state = checkpoints[segment]
        local_history = []
        for offset in range(steps):
            local_history.append(state)
            state = transition(state, start_step + offset)
        if state != checkpoints[segment + 1]:
            raise AssertionError("checkpoint cleanup recomputation diverged")
        checkpoints.pop()
        for old_state in reversed(local_history):
            state = old_state
        if state != checkpoints[segment]:
            raise AssertionError("checkpoint cleanup did not restore its segment entry")

    return RoundTripProof(
        output_bits=output_bits,
        entry_state_restored=checkpoints == [entry_bits],
        peak_history_words=peak_states,
        checkpoint_words=segments,
        transition_count=4 * total_steps,
    )


def _dot_metrics(mode: str, span: int | None, config: SVKConfig) -> tuple[int, int, int, int]:
    transition_cost = 4
    if mode == "linear":
        operations = 2 * config.nnz * transition_cost + 1
        total_operations = 2 * operations
        peak_bits = (config.nnz + 1) * 32
        history_bits_written = 2 * config.nnz * 32
        checkpoint_copies = 2
        return total_operations, peak_bits, history_bits_written, checkpoint_copies
    if mode != "pebble" or span is None:
        raise ValueError("unknown dot strategy")
    peak_states, segments = _pebble_peak_states(config.nnz, span)
    total_operations = 2 * (
        4 * config.nnz * transition_cost + 2 * segments + 1
    )
    peak_bits = (peak_states + 1) * 32
    history_bits_written = 8 * config.nnz * 32
    checkpoint_copies = 4 * segments + 2
    return total_operations, peak_bits, history_bits_written, checkpoint_copies


def _sink_metrics(mode: str, span: int | None, config: SVKConfig) -> tuple[int, int, int, int]:
    if mode == "linear":
        operations = 2 * config.iterations + 1
        peak_bits = (config.iterations + 1) * 32
        history_bits_written = config.iterations * 32
        checkpoint_copies = 1
        return operations, peak_bits, history_bits_written, checkpoint_copies
    if mode != "pebble" or span is None:
        raise ValueError("unknown sink strategy")
    peak_states, segments = _pebble_peak_states(config.iterations, span)
    operations = 4 * config.iterations + 2 * segments + 1
    peak_bits = (peak_states + 1) * 32
    history_bits_written = 4 * config.iterations * 32
    checkpoint_copies = 2 * segments + 1
    return operations, peak_bits, history_bits_written, checkpoint_copies


def _prove_strategy(
    *,
    config: SVKConfig,
    dot_mode: str,
    dot_span: int | None,
    sink_mode: str,
    sink_span: int | None,
    optimized_baseline_operations: int,
) -> SVKStrategyPoint:
    dot_transition = _dot_transition(config)
    if dot_mode == "linear":
        dot_proof = prove_linear_round_trip(
            total_steps=config.nnz,
            transition=dot_transition,
        )
    else:
        assert dot_span is not None
        dot_proof = prove_checkpoint_round_trip(
            total_steps=config.nnz,
            span=dot_span,
            transition=dot_transition,
        )

    dot_clear_proof = (
        prove_linear_round_trip(total_steps=config.nnz, transition=dot_transition)
        if dot_mode == "linear"
        else prove_checkpoint_round_trip(
            total_steps=config.nnz,
            span=int(dot_span),
            transition=dot_transition,
        )
    )
    dot_copy_cleared = (
        dot_proof.output_bits == dot_clear_proof.output_bits
        and dot_proof.entry_state_restored
        and dot_clear_proof.entry_state_restored
    )

    sink_transition = _sink_transition(dot_proof.output_bits)
    if sink_mode == "linear":
        sink_proof = prove_linear_round_trip(
            total_steps=config.iterations,
            transition=sink_transition,
        )
    else:
        assert sink_span is not None
        sink_proof = prove_checkpoint_round_trip(
            total_steps=config.iterations,
            span=sink_span,
            transition=sink_transition,
        )

    dot_operations, dot_peak, dot_history, dot_copies = _dot_metrics(
        dot_mode,
        dot_span,
        config,
    )
    sink_operations, sink_peak, sink_history, sink_copies = _sink_metrics(
        sink_mode,
        sink_span,
        config,
    )
    total_operations = dot_operations + sink_operations
    peak_support_bits = max(dot_peak, sink_peak)
    minimum_recovery = max(
        0.0,
        min(1.0, 1.0 - optimized_baseline_operations / total_operations),
    )
    support_at_80pct = optimized_baseline_operations - 0.2 * total_operations
    output_result = f"{sink_proof.output_bits:016x}"

    return SVKStrategyPoint(
        strategy_id=(
            f"dot-{dot_mode}{'-' + str(dot_span) if dot_span is not None else ''}_"
            f"sink-{sink_mode}{'-' + str(sink_span) if sink_span is not None else ''}"
        ),
        dot_strategy=dot_mode,
        dot_span=dot_span,
        sink_strategy=sink_mode,
        sink_span=sink_span,
        output_result=output_result,
        output_match=output_result == SVK_EXPECTED_RESULT,
        dot_state_restored=dot_copy_cleared,
        sink_state_restored=sink_proof.entry_state_restored,
        entry_state_restored=dot_copy_cleared and sink_proof.entry_state_restored,
        peak_support_bits=peak_support_bits,
        accepted_output_bits_excluded_from_peak=32,
        total_semantic_operations=total_operations,
        operation_delta_vs_optimized_conventional=(
            total_operations - optimized_baseline_operations
        ),
        history_bits_written=dot_history + sink_history,
        checkpoint_copy_operations=dot_copies + sink_copies,
        erasure_bits=0,
        minimum_recovery_fraction_zero_support=round(minimum_recovery, 9),
        maximum_support_energy_units_at_80pct_recovery=round(support_at_80pct, 9),
    )


def _pareto(points: list[SVKStrategyPoint]) -> list[SVKStrategyPoint]:
    selected: list[SVKStrategyPoint] = []
    for candidate in points:
        dominated = False
        for other in points:
            if other is candidate:
                continue
            no_worse = (
                other.peak_support_bits <= candidate.peak_support_bits
                and other.total_semantic_operations <= candidate.total_semantic_operations
            )
            strictly_better = (
                other.peak_support_bits < candidate.peak_support_bits
                or other.total_semantic_operations < candidate.total_semantic_operations
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            selected.append(candidate)
    return sorted(
        selected,
        key=lambda item: (item.peak_support_bits, item.total_semantic_operations),
    )


def analyze_svk(config: SVKConfig = SVKConfig()) -> SVKLoweringArtifact:
    source_result_bits = svk_source_result(config)
    dot_bits = _f32_bits(svk_dot(config))
    optimized_baseline_operations = 4 * config.nnz + config.iterations
    unoptimized_source_operations = config.iterations * (4 * config.nnz + 1)
    source_history_peak_bits = config.iterations * (config.nnz + 2) * 32
    source_history_total_operations = 2 * unoptimized_source_operations + 1

    dot_options: list[tuple[str, int | None]] = [("linear", None)] + [
        ("pebble", span) for span in (1, 2, 4, 8, 11, 12, 16, 24, 32, 64, 128)
    ]
    sink_options: list[tuple[str, int | None]] = [("linear", None)] + [
        ("pebble", span)
        for span in (1, 2, 4, 8, 12, 16, 24, 32, 40, 64, 100, 125, 128, 200, 250, 500, 1000)
    ]

    candidates = [
        _prove_strategy(
            config=config,
            dot_mode=dot_mode,
            dot_span=dot_span,
            sink_mode=sink_mode,
            sink_span=sink_span,
            optimized_baseline_operations=optimized_baseline_operations,
        )
        for dot_mode, dot_span in dot_options
        for sink_mode, sink_span in sink_options
    ]
    frontier = _pareto(candidates)

    default_contract_match = config.is_default_contract and (
        f"{source_result_bits:016x}" == SVK_EXPECTED_RESULT
    )
    all_restored = all(point.entry_state_restored for point in frontier)
    all_outputs_match = all(point.output_match for point in frontier)
    blockers = [
        "RISC_V_CODEGEN_UNIMPLEMENTED",
        "RISC_V_TARGET_RESULT_PARITY_UNQUALIFIED",
        "TARGET_FLOAT_ROUNDING_PARITY_UNQUALIFIED",
        "PHYSICAL_SUBSTRATE_RESULT_UNMEASURED",
        "PHYSICAL_ENERGY_UNMEASURED",
        "TIMING_UNMEASURED",
        "OCCUPIED_VOLUME_UNMEASURED",
    ]
    if not default_contract_match:
        blockers.insert(0, "FAMBS_ACCEPTED_OUTPUT_MISMATCH")
    if not all_restored:
        blockers.insert(0, "REVERSIBLE_RESTORATION_FAILED")

    artifact = SVKLoweringArtifact(
        schema_version=SVK_LOWERING_SCHEMA_VERSION,
        artifact_type=SVK_LOWERING_ARTIFACT_TYPE,
        generated_by="ahead-rev-sim/svk-lowering-v0.9-draft",
        source={
            "repository": "BigBirdReturns/future-ai-microbench-suite",
            "commit": SVK_SOURCE_COMMIT,
            "path": "src/svk_sparse_vec.c",
            "git_blob_sha1": SVK_SOURCE_BLOB,
            "configuration": asdict(config),
        },
        accepted_output_contract={
            "schema": "fambs.result/v1",
            "suite_version": "0.4.0",
            "contract_id": "fambs-v0.4.0-default",
            "bench": "SVK",
            "notes": "sparse_vector_dot",
            "iters": 1000,
            "result": SVK_EXPECTED_RESULT,
            "result_kind": "f32_bits",
        },
        numeric_contract={
            "format": "IEEE-754 binary32",
            "rounding": "round_to_nearest_ties_to_even",
            "multiply_add": "separate_binary32_multiply_then_binary32_add",
            "fused_multiply_add": False,
            "fast_math": False,
            "source_dot_bits": f"{dot_bits:08x}",
        },
        source_reference={
            "result": f"{source_result_bits:016x}",
            "accepted_output_match": default_contract_match,
            "dot_result": f"{dot_bits:08x}",
            "dot_float": svk_dot(config),
            "sink_float": _f32_from_bits(source_result_bits),
        },
        parity_baseline={
            "baseline_id": "conventional_loop_invariant_dot_hoist",
            "semantic_operations": optimized_baseline_operations,
            "dot_operations": 4 * config.nnz,
            "sink_operations": config.iterations,
            "optimization": "dot is pure and loop invariant; apply the same hoist to every architecture",
            "evidence_class": "algorithmic_reference_not_measured_timing",
        },
        diagnostic_source_lowering={
            "baseline_id": "source_order_full_history_round_trip",
            "forward_semantic_operations": unoptimized_source_operations,
            "total_semantic_operations": source_history_total_operations,
            "peak_support_bits": source_history_peak_bits,
            "pareto_admissible": False,
            "reason": (
                "Retaining every repeated dot reduction is dominated after fair loop-invariant "
                "motion. Eliminated work is compiler evidence, not a physical recovery credit."
            ),
        },
        frontier=frontier,
        physical_handoff={
            "portable_binding": PORTABLE_BINDING,
            "optional_riscv_extension": OPTIONAL_RISCV_EXTENSION,
            "operator_classes": [
                "binary32_sparse_dot",
                "binary32_stateful_recurrence",
            ],
            "operand_channels": [
                "sparse_indices_u16",
                "sparse_values_binary32",
                "dense_values_binary32",
                "iteration_count_u32",
            ],
            "result_contract": {
                "result": SVK_EXPECTED_RESULT,
                "result_kind": "f32_bits",
                "quality_rule": "exact default-contract identity",
            },
            "fallback": "svk_binary32_reference_v1",
            "required_measurements": [
                "complete_boundary_joules",
                "latency",
                "occupied_volume",
                "thermal_state",
                "calibration_and_drift",
                "readout_energy",
                "control_and_memory_energy",
            ],
        },
        qualification={
            "status": (
                "semantic_lowering_proved"
                if default_contract_match and all_restored and all_outputs_match
                else "refused"
            ),
            "blockers": blockers,
            "accepted_output_match": default_contract_match and all_outputs_match,
            "entry_state_restored": all_restored,
            "riscv_codegen_qualified": False,
            "target_result_qualified": False,
            "physical_claim_allowed": False,
            "energy_claim_allowed": False,
        },
        claim_boundary=(
            "This artifact proves the default SVK binary32 semantic result, loop-invariant dot "
            "motion, reversible checkpoint schedules, exact reference entry-state restoration, "
            "and normalized zero-support recovery thresholds. It does not prove emitted RISC-V "
            "code, target floating-point parity, measured timing, physical substrate execution, "
            "energy, volume, thermal closure, or manufacturability."
        ),
        control_question=(
            "After applying the same ordinary compiler optimization to every architecture, which "
            "checkpoint schedule minimizes support state without requiring a physical recovery "
            "fraction that the complete measured system cannot supply?"
        ),
    )
    artifact.seal()
    return artifact
