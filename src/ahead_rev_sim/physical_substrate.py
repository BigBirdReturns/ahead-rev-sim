"""Commodity physical-compute substrate API.

RISC-V remains the deterministic control and custody plane.  Physical devices,
harvested environments, embodied structures, and software fallbacks implement
the same descriptor, queue, reset, replay, and receipt contracts.
"""

from .physical_cartridges import (
    default_runtime,
    harvested_world_descriptor,
    rc_relaxation_cartridge,
    thermal_sampler_cartridge,
)
from .physical_constants import (
    OPTIONAL_RISCV_EXTENSION,
    PHYSICAL_COMPUTE_MMIO_V1,
    PORTABLE_BINDING,
    SUBSTRATE_RECEIPT_SCHEMA_VERSION,
    SUBSTRATE_SCHEMA_VERSION,
    ChannelDirection,
    CouplingMode,
    DeterminismContract,
    DynamicsClass,
    EnergySourceClass,
    EvidenceClass,
    ExecutionStatus,
    RealizationClass,
    ResetContract,
    SignalRole,
    SubstrateCommand,
)
from .physical_descriptor import ChannelSpec, EnergyContract, PhysicalSubstrateDescriptor
from .physical_receipt import PhysicalSubstrateReceipt
from .physical_signal import EntropyTrace, PhysicalSignalFrame
from .physical_operators import (
    LeakyIntegratorOperator,
    OperatorResult,
    PhysicalOperator,
    ThermalBitSamplerOperator,
)
from .physical_runtime import PhysicalComputeRuntime, PhysicalSubstrateCartridge

__all__ = [
    "SUBSTRATE_SCHEMA_VERSION",
    "SUBSTRATE_RECEIPT_SCHEMA_VERSION",
    "PORTABLE_BINDING",
    "OPTIONAL_RISCV_EXTENSION",
    "PHYSICAL_COMPUTE_MMIO_V1",
    "SignalRole",
    "ChannelDirection",
    "DynamicsClass",
    "RealizationClass",
    "CouplingMode",
    "DeterminismContract",
    "ResetContract",
    "EnergySourceClass",
    "EvidenceClass",
    "ExecutionStatus",
    "SubstrateCommand",
    "ChannelSpec",
    "EnergyContract",
    "PhysicalSubstrateDescriptor",
    "PhysicalSignalFrame",
    "EntropyTrace",
    "OperatorResult",
    "PhysicalOperator",
    "PhysicalSubstrateReceipt",
    "PhysicalSubstrateCartridge",
    "PhysicalComputeRuntime",
    "LeakyIntegratorOperator",
    "ThermalBitSamplerOperator",
    "rc_relaxation_cartridge",
    "thermal_sampler_cartridge",
    "harvested_world_descriptor",
    "default_runtime",
]
