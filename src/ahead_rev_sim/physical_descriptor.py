"""Descriptor contracts for designed and harvested physical computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .physical_constants import (
    OPTIONAL_RISCV_EXTENSION,
    PORTABLE_BINDING,
    SUBSTRATE_SCHEMA_VERSION,
    ChannelDirection,
    CouplingMode,
    DeterminismContract,
    DynamicsClass,
    EnergySourceClass,
    EvidenceClass,
    RealizationClass,
    ResetContract,
    SignalRole,
)
from .physical_serialization import jsonable, sha256_json


@dataclass(frozen=True)
class ChannelSpec:
    channel_id: str
    direction: ChannelDirection
    roles: tuple[SignalRole, ...]
    physical_quantity: str
    unit: str
    dtype: str = "int32"
    calibration_required: bool = True
    sample_period_ns: int | None = None

    def __post_init__(self) -> None:
        if not self.channel_id or not self.physical_quantity or not self.unit:
            raise ValueError("channel id, physical quantity, and unit are required")
        if not self.roles or len(set(self.roles)) != len(self.roles):
            raise ValueError(f"channel {self.channel_id!r} needs unique declared roles")
        if self.sample_period_ns is not None and self.sample_period_ns <= 0:
            raise ValueError("sample_period_ns must be positive")


@dataclass(frozen=True)
class EnergyContract:
    source_class: EnergySourceClass
    evidence_class: EvidenceClass = EvidenceClass.REFERENCE_MODEL
    measurement_boundary: str = "unmeasured"
    instrument_ref: str | None = None
    supplied_joules: float | None = None
    recovered_or_harvested_joules: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("supplied_joules", self.supplied_joules),
            ("recovered_or_harvested_joules", self.recovered_or_harvested_joules),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.evidence_class == EvidenceClass.MEASURED:
            if not self.instrument_ref or self.supplied_joules is None:
                raise ValueError("measured energy requires an instrument and supplied joules")

    @property
    def physical_energy_claim_allowed(self) -> bool:
        return (
            self.evidence_class == EvidenceClass.MEASURED
            and self.instrument_ref is not None
            and self.supplied_joules is not None
        )


@dataclass(frozen=True)
class PhysicalSubstrateDescriptor:
    substrate_id: str
    operator_class: str
    dynamics_class: DynamicsClass
    realization_class: RealizationClass
    coupling_mode: CouplingMode
    determinism: DeterminismContract
    reset_contract: ResetContract
    channels: tuple[ChannelSpec, ...]
    state_words: int
    environment_boundary: str
    parameters: Mapping[str, int | float | str | bool] = field(default_factory=dict)
    energy_contract: EnergyContract = field(
        default_factory=lambda: EnergyContract(EnergySourceClass.EXTERNAL)
    )
    portable_binding: str = PORTABLE_BINDING
    optional_riscv_extension: str = OPTIONAL_RISCV_EXTENSION
    fallback_model_id: str = ""
    schema_version: str = SUBSTRATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.substrate_id or not self.operator_class or not self.environment_boundary:
            raise ValueError("substrate id, operator class, and environment boundary are required")
        if self.state_words < 0 or not self.channels:
            raise ValueError("state_words must be non-negative and channels must be present")
        ids = [channel.channel_id for channel in self.channels]
        if len(set(ids)) != len(ids):
            raise ValueError("channel identifiers must be unique")
        if self.portable_binding != PORTABLE_BINDING:
            raise ValueError(f"unsupported portable binding: {self.portable_binding}")
        if self.optional_riscv_extension != OPTIONAL_RISCV_EXTENSION:
            raise ValueError(f"non-standard RISC-V extension must be {OPTIONAL_RISCV_EXTENSION}")
        if not self.fallback_model_id:
            raise ValueError("fallback_model_id is required for commodity substitution")
        if not self.role_channels(SignalRole.OPERAND):
            raise ValueError("descriptor must declare at least one operand channel")
        if not self.role_channels(SignalRole.DYNAMICS):
            raise ValueError("descriptor must declare the physical dynamics")
        if not any(
            SignalRole.OPERAND in channel.roles and channel.direction == ChannelDirection.INPUT
            for channel in self.channels
        ):
            raise ValueError("descriptor must declare an input operand")
        if not any(
            SignalRole.RESULT in channel.roles and channel.direction == ChannelDirection.OUTPUT
            for channel in self.channels
        ):
            raise ValueError("descriptor must declare an output result")

    def role_channels(self, role: SignalRole) -> tuple[str, ...]:
        return tuple(channel.channel_id for channel in self.channels if role in channel.roles)

    def channel(self, channel_id: str) -> ChannelSpec:
        for channel in self.channels:
            if channel.channel_id == channel_id:
                return channel
        raise KeyError(f"unknown substrate channel: {channel_id}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def sha256(self) -> str:
        return sha256_json(self.to_dict())
