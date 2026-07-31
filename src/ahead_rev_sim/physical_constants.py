"""Names and enums shared by the physical-compute commodity interface."""

from __future__ import annotations

from enum import Enum
from typing import Mapping

SUBSTRATE_SCHEMA_VERSION = "ahead.physical-substrate/v0.1"
SUBSTRATE_RECEIPT_SCHEMA_VERSION = "ahead.physical-substrate-receipt/v0.1"
PORTABLE_BINDING = "physical-compute-mmio/v1"
OPTIONAL_RISCV_EXTENSION = "Xphys"

PHYSICAL_COMPUTE_MMIO_V1: Mapping[str, int] = {
    "identity": 0x00,
    "capabilities": 0x04,
    "command": 0x08,
    "status": 0x0C,
    "descriptor_ptr_lo": 0x10,
    "descriptor_ptr_hi": 0x14,
    "input_queue_ptr_lo": 0x18,
    "input_queue_ptr_hi": 0x1C,
    "output_queue_ptr_lo": 0x20,
    "output_queue_ptr_hi": 0x24,
    "receipt_ptr_lo": 0x28,
    "receipt_ptr_hi": 0x2C,
    "doorbell": 0x30,
}


class SignalRole(str, Enum):
    OPERAND = "operand"
    DYNAMICS = "dynamics"
    ENERGY = "energy"
    CONTEXT = "context"
    RESULT = "result"


class ChannelDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    INTERNAL = "internal"


class DynamicsClass(str, Enum):
    DETERMINISTIC_RELAXATION = "deterministic_relaxation"
    THERMODYNAMIC_STOCHASTIC = "thermodynamic_stochastic"
    OSCILLATORY = "oscillatory"
    RESERVOIR = "reservoir"
    REVERSIBLE = "reversible"


class RealizationClass(str, Enum):
    DESIGNED_DEVICE = "designed_device"
    HARVESTED_ENVIRONMENT = "harvested_environment"
    EMBODIED_STRUCTURE = "embodied_structure"
    BIOLOGICAL_SYSTEM = "biological_system"
    VIRTUAL_REFERENCE = "virtual_reference"


class CouplingMode(str, Enum):
    OBSERVE_ONLY = "observe_only"
    STIMULATE_AND_OBSERVE = "stimulate_and_observe"
    CLOSED_LOOP = "closed_loop"


class DeterminismContract(str, Enum):
    EXACT = "exact"
    REPLAY_WITH_TRACE = "replay_with_trace"
    DISTRIBUTIONAL = "distributional"


class ResetContract(str, Enum):
    EXACT = "exact"
    CALIBRATED = "calibrated"
    STATISTICAL = "statistical"
    NONE = "none"


class EnergySourceClass(str, Enum):
    EXTERNAL = "external"
    AMBIENT_HARVESTED = "ambient_harvested"
    SIGNAL_COUPLED = "signal_coupled"
    RECOVERED = "recovered"


class EvidenceClass(str, Enum):
    REFERENCE_MODEL = "reference_model"
    SIMULATED = "simulated"
    MEASURED = "measured"


class ExecutionStatus(str, Enum):
    ACCEPTED = "accepted"
    REFUSED = "refused"


class SubstrateCommand(str, Enum):
    RESET = "reset"
    LOAD = "load"
    EVOLVE = "evolve"
    READ = "read"
    CAPTURE = "capture"
