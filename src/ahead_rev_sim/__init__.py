"""
ahead-rev-sim v0.8.0

Reversible execution simulator for RISC-V.
History is recoverable, not recorded.
"""

from __future__ import annotations

__version__ = "0.8.0"

from .isa import Instruction, OpCode
from .machine import Machine
from .memory import Memory
from .energy import EnergyModel
from .metrics import ReversibilityMetrics
from .parser import AssemblyParser
from .history import HistoryBuffer, HistoryAnalyzer, HistoryEntry, EntryType
from .debugger import TimeTravelDebugger, Watchpoint, CorruptionReport
from .reversible_memory import ReversibleMemory, MemoryController, MemoryRegionType
from .frontier import ArchitectureProfile, FrontierArtifact, analyze_assembly, analyze_program
from .frontier_exec import ArchitectedState, ExecutionProof, HistoryCompleteMachine, run_and_prove
from .semantics import (
    BijectivityCheck,
    BijectivityStatus,
    InformationEffect,
    OperationSemantics,
    SemanticClass,
    analyze_instruction,
    verify_bijective,
)
from .physical_substrate import (
    OPTIONAL_RISCV_EXTENSION,
    PHYSICAL_COMPUTE_MMIO_V1,
    PORTABLE_BINDING,
    CouplingMode,
    DeterminismContract as PhysicalDeterminismContract,
    DynamicsClass,
    EntropyTrace,
    PhysicalComputeRuntime,
    PhysicalSignalFrame,
    PhysicalSubstrateDescriptor,
    PhysicalSubstrateReceipt,
    RealizationClass,
    SignalRole,
    default_runtime as default_physical_runtime,
    harvested_world_descriptor,
    rc_relaxation_cartridge,
    thermal_sampler_cartridge,
)
from .fambs import (
    FAMBS_IMPORT_SCHEMA_VERSION,
    FAMBS_SOURCE_MANIFEST_SCHEMA_VERSION,
    FambsImportArtifact,
    FambsResultRow,
    derive_source_emission,
    import_fambs,
    load_manifest as load_fambs_manifest,
    parse_jsonl as parse_fambs_jsonl,
)
from .fambs_svk_lowering import (
    SVK_EXPECTED_RESULT,
    SVK_LOWERING_SCHEMA_VERSION,
    RoundTripProof,
    SVKConfig,
    SVKLoweringArtifact,
    SVKStrategyPoint,
    analyze_svk,
    prove_checkpoint_round_trip,
    prove_linear_round_trip,
    svk_dot,
    svk_source_result,
)
from .fambs_pck_lowering import (
    PCK_EXPECTED_RESULT,
    PCK_LOWERING_SCHEMA_VERSION,
    PCKConfig,
    PCKLoweringArtifact,
    PCKPool,
    PCKStrategyPoint,
    analyze_pck,
    initialize_pool,
    pck_chase,
    pck_inverse_step,
    pck_reverse_chase,
    pck_source_result,
    pck_step,
    prove_control_map,
    prove_initialization_round_trip,
)

__all__ = [
    # Version
    "__version__",
    # ISA
    "Instruction",
    "OpCode",
    # Machine
    "Machine",
    # Memory
    "Memory",
    "ReversibleMemory",
    "MemoryController",
    "MemoryRegionType",
    # Energy
    "EnergyModel",
    # Metrics
    "ReversibilityMetrics",
    # History Buffer
    "HistoryBuffer",
    "HistoryAnalyzer",
    "HistoryEntry",
    "EntryType",
    # Debugger
    "TimeTravelDebugger",
    "Watchpoint",
    "CorruptionReport",
    # Parser
    "AssemblyParser",
    # Reversibility frontier
    "ArchitectureProfile",
    "FrontierArtifact",
    "analyze_assembly",
    "analyze_program",
    "BijectivityCheck",
    "BijectivityStatus",
    "InformationEffect",
    "OperationSemantics",
    "SemanticClass",
    "analyze_instruction",
    "verify_bijective",
    "ArchitectedState",
    "ExecutionProof",
    "HistoryCompleteMachine",
    "run_and_prove",
    # Commodity physical compute
    "OPTIONAL_RISCV_EXTENSION",
    "PHYSICAL_COMPUTE_MMIO_V1",
    "PORTABLE_BINDING",
    "SignalRole",
    "DynamicsClass",
    "RealizationClass",
    "CouplingMode",
    "PhysicalDeterminismContract",
    "PhysicalSubstrateDescriptor",
    "PhysicalSignalFrame",
    "EntropyTrace",
    "PhysicalSubstrateReceipt",
    "PhysicalComputeRuntime",
    "rc_relaxation_cartridge",
    "thermal_sampler_cartridge",
    "harvested_world_descriptor",
    "default_physical_runtime",
    # FAMBS intake
    "FAMBS_IMPORT_SCHEMA_VERSION",
    "FAMBS_SOURCE_MANIFEST_SCHEMA_VERSION",
    "FambsResultRow",
    "FambsImportArtifact",
    "load_fambs_manifest",
    "derive_source_emission",
    "parse_fambs_jsonl",
    "import_fambs",
    # FAMBS SVK lowering
    "SVK_EXPECTED_RESULT",
    "SVK_LOWERING_SCHEMA_VERSION",
    "SVKConfig",
    "RoundTripProof",
    "SVKStrategyPoint",
    "SVKLoweringArtifact",
    "svk_dot",
    "svk_source_result",
    "prove_linear_round_trip",
    "prove_checkpoint_round_trip",
    "analyze_svk",
    # FAMBS PCK lowering
    "PCK_EXPECTED_RESULT",
    "PCK_LOWERING_SCHEMA_VERSION",
    "PCKConfig",
    "PCKPool",
    "PCKStrategyPoint",
    "PCKLoweringArtifact",
    "initialize_pool",
    "prove_initialization_round_trip",
    "prove_control_map",
    "pck_step",
    "pck_inverse_step",
    "pck_chase",
    "pck_reverse_chase",
    "pck_source_result",
    "analyze_pck",
]
