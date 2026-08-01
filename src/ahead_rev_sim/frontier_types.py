"""Data contracts and deterministic sealing for reversibility-frontier artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any

from .semantics import OperationSemantics

SCHEMA_VERSION = "ahead.reversibility-frontier/v0.1"
ARTIFACT_TYPE = "reversibility_frontier"
REQUIRED_ACCEPTED_OUTPUT_FIELDS = (
    "contract_id",
    "result",
    "quality_rule",
    "accepted_work_unit",
)

@dataclass(frozen=True)
class ArchitectureProfile:
    profile_id: str = "normalized-hybrid-v0"
    word_bits: int = 32
    pc_bits: int = 32
    hot_energy_per_operation: float = 1.0
    cold_gross_energy_per_operation: float = 1.0
    transition_energy_per_crossing: float = 0.25
    power_clock_overhead_energy: float = 0.0
    hot_cycles_per_operation: float = 1.0
    cold_cycles_per_operation: float = 2.0
    transition_cycles_per_crossing: float = 1.0
    evidence_class: str = "normalized_uncalibrated_model"

    def __post_init__(self) -> None:
        numeric = (
            self.hot_energy_per_operation,
            self.cold_gross_energy_per_operation,
            self.transition_energy_per_crossing,
            self.power_clock_overhead_energy,
            self.hot_cycles_per_operation,
            self.cold_cycles_per_operation,
            self.transition_cycles_per_crossing,
        )
        if self.word_bits <= 0 or self.pc_bits <= 0:
            raise ValueError("word_bits and pc_bits must be positive")
        if any(value < 0 for value in numeric):
            raise ValueError("profile costs must be non-negative")


@dataclass(frozen=True)
class RegionRecord:
    region_id: str
    start_pc: int
    end_pc: int
    classification: str
    operation_count: int
    opcodes: tuple[str, ...]
    intrinsic_erasure_bits: int
    reversal_metadata_bits: int
    overwritten_state_bits: int
    hazards: tuple[str, ...]


@dataclass(frozen=True)
class BreakEvenEnvelope:
    baseline_energy_units: float
    fixed_transformed_energy_units: float
    cold_gross_energy_units: float
    minimum_recovery_fraction_for_energy_parity: float | None
    energy_parity_status: str
    baseline_cycles: float
    fixed_transformed_cycles: float
    cold_operation_count: int
    maximum_cold_cycle_multiplier_for_runtime_parity: float | None
    runtime_parity_status: str
    evidence_class: str = "modeled_not_measured"


@dataclass(frozen=True)
class StrategyPoint:
    strategy_id: str
    proof_status: str
    history_bits: int
    ancilla_peak_bytes: int
    extra_operations: int
    hot_operations: int
    cold_operations: int
    commit_boundaries: int
    domain_crossings: int
    restorable_operation_fraction: float
    break_even: BreakEvenEnvelope
    assumptions: tuple[str, ...] = ()
    pareto_nondominated: bool = True


@dataclass
class FrontierArtifact:
    schema_version: str
    artifact_type: str
    generated_by: str
    source: dict[str, Any]
    accepted_output_contract: dict[str, Any] | None
    architecture_profile: ArchitectureProfile
    operations: list[OperationSemantics]
    regions: list[RegionRecord]
    frontier: list[StrategyPoint]
    summary: dict[str, Any]
    qualification: dict[str, Any]
    claim_boundary: str
    control_question: str
    artifact_sha256: str | None = None

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        data = _jsonable(self)
        if not include_hash:
            data.pop("artifact_sha256", None)
        return data

    def seal(self) -> str:
        digest = sha256(_canonical_json(self.to_dict(include_hash=False)).encode("utf-8")).hexdigest()
        self.artifact_sha256 = digest
        return digest

    def to_json(self, *, indent: int = 2) -> str:
        if self.artifact_sha256 is None:
            self.seal()
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


