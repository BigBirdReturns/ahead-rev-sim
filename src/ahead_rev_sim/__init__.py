"""Public package surface for ahead-rev-sim.

The package separates workload semantics, reversible execution proofs, physical
substrate contracts, provider-neutral integration, causal custody, scale and
venue receipts, and complete-system EVP qualification.
"""

from __future__ import annotations

from ._version import __version__
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
from .rtl_attachment import (
    EXPECTED_TRACE as RTL_ATTACHMENT_EXPECTED_TRACE,
    RTL_ATTACHMENT_CONTRACT_SCHEMA_VERSION,
    RTL_ATTACHMENT_LINK,
    RTL_ATTACHMENT_MANIFEST_SCHEMA_VERSION,
    RTL_ATTACHMENT_PROOF_SCHEMA_VERSION,
    RTL_ATTACHMENT_RESOLVER,
    build_attachment_contract,
    build_attachment_manifest,
    parse_rtl_attachment_trace,
    render_cartridge_systemverilog,
    render_contract_json,
    render_resolver_systemverilog,
    render_testbench_systemverilog,
)
from .rtl_attachment_execution import (
    build_rtl_attachment_proof,
    build_rtl_attachment_proof_from_tools,
)
from .rtl_attachment_io import (
    write_attachment_bundle,
    write_rtl_attachment_proof,
)
from .evp import (
    EVP_ARTIFACT_TYPE,
    EVP_SCHEMA_VERSION,
    build_evp_receipt,
    write_evp_receipt,
)
from .congruent_shapes import (
    PYLON_ATLAS_SCHEMA_VERSION,
    PYLON_CATALOG_SCHEMA_VERSION,
    build_congruent_shape_atlas,
    load_pylon_catalog,
    write_congruent_shape_atlas,
)
from .pylon_wave import (
    REPORT_SCHEMA_VERSION as PYLON_WAVE_REPORT_SCHEMA_VERSION,
    WAVE_SCHEMA_VERSION as PYLON_WAVE_SCHEMA_VERSION,
    build_wave_report,
    load_wave,
    write_wave_report,
)
from .scale_seam import (
    SCALE_SEAM_ARTIFACT_TYPE,
    SCALE_SEAM_SCHEMA_VERSION,
    build_scale_seam_receipt,
    write_scale_seam_receipt,
)
from .remote_venue import (
    REMOTE_COMPARISON_SCHEMA_VERSION,
    REMOTE_RECEIPT_SCHEMA_VERSION,
    REMOTE_SUBMISSION_SCHEMA_VERSION,
    build_remote_submission,
    build_remote_venue_comparison,
    build_remote_venue_receipt,
    write_json_artifact as write_remote_venue_artifact,
)
from .causal_custody import (
    CAUSAL_CUSTODY_ARTIFACT_TYPE,
    CAUSAL_CUSTODY_SCHEMA_VERSION,
    build_causal_custody_receipt,
    write_causal_custody_receipt,
)
from .execution_target import (
    EXECUTION_TARGET_ABI,
    EXECUTION_TARGET_ATTEMPT_ARTIFACT_TYPE,
    EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION,
    EXECUTION_TARGET_INVOCATION_ARTIFACT_TYPE,
    EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION,
    PHYSICAL_BLOCKERS as EXECUTION_TARGET_PHYSICAL_BLOCKERS,
    ReferenceSoftwareTargetAdapter,
    TargetArtifact,
    TargetDescriptor,
    TargetFault,
    TargetRefusal,
    TargetStageResult,
    UnboundPhysicalTargetAdapter,
    build_execution_target_invocation,
    execute_target_attempt,
    verify_execution_target_attempt,
    verify_execution_target_invocation,
    write_json_artifact as write_execution_target_artifact,
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
    analyze_pck as analyze_pck_lowering,
    initialize_pool,
    pck_chase,
    pck_inverse_step,
    pck_reverse_chase,
    pck_source_result,
    pck_step,
    prove_control_map,
    prove_initialization_round_trip,
)
from .fambs_pck_frontier import analyze_pck as analyze_pck_frontier

# Preserve the established package-level name while exposing the two distinct
# implementation surfaces explicitly. The frontier wrapper is the current
# public behavior because it enforces workload-cardinality-safe sampling.
analyze_pck = analyze_pck_frontier

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
    # Provider-neutral RTL attachment
    "RTL_ATTACHMENT_CONTRACT_SCHEMA_VERSION",
    "RTL_ATTACHMENT_MANIFEST_SCHEMA_VERSION",
    "RTL_ATTACHMENT_PROOF_SCHEMA_VERSION",
    "RTL_ATTACHMENT_LINK",
    "RTL_ATTACHMENT_RESOLVER",
    "RTL_ATTACHMENT_EXPECTED_TRACE",
    "build_attachment_contract",
    "build_attachment_manifest",
    "write_attachment_bundle",
    "parse_rtl_attachment_trace",
    "build_rtl_attachment_proof",
    "build_rtl_attachment_proof_from_tools",
    "write_rtl_attachment_proof",
    "render_contract_json",
    "render_resolver_systemverilog",
    "render_cartridge_systemverilog",
    "render_testbench_systemverilog",
    # Energy, Volume, and Performance receipts
    "EVP_SCHEMA_VERSION",
    "EVP_ARTIFACT_TYPE",
    "build_evp_receipt",
    "write_evp_receipt",
    # Congruent-shape design pylons
    "PYLON_CATALOG_SCHEMA_VERSION",
    "PYLON_ATLAS_SCHEMA_VERSION",
    "load_pylon_catalog",
    "build_congruent_shape_atlas",
    "write_congruent_shape_atlas",
    # Second-wave pylon intake
    "PYLON_WAVE_SCHEMA_VERSION",
    "PYLON_WAVE_REPORT_SCHEMA_VERSION",
    "load_wave",
    "build_wave_report",
    "write_wave_report",
    # Scale-seam reference contract
    "SCALE_SEAM_SCHEMA_VERSION",
    "SCALE_SEAM_ARTIFACT_TYPE",
    "build_scale_seam_receipt",
    "write_scale_seam_receipt",
    # Remote-venue reference contract
    "REMOTE_SUBMISSION_SCHEMA_VERSION",
    "REMOTE_RECEIPT_SCHEMA_VERSION",
    "REMOTE_COMPARISON_SCHEMA_VERSION",
    "build_remote_submission",
    "build_remote_venue_receipt",
    "build_remote_venue_comparison",
    "write_remote_venue_artifact",
    # Causal-custody reference contract
    "CAUSAL_CUSTODY_SCHEMA_VERSION",
    "CAUSAL_CUSTODY_ARTIFACT_TYPE",
    "build_causal_custody_receipt",
    "write_causal_custody_receipt",
    # Provider-neutral execution targets
    "EXECUTION_TARGET_ABI",
    "EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION",
    "EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION",
    "EXECUTION_TARGET_INVOCATION_ARTIFACT_TYPE",
    "EXECUTION_TARGET_ATTEMPT_ARTIFACT_TYPE",
    "EXECUTION_TARGET_PHYSICAL_BLOCKERS",
    "TargetArtifact",
    "TargetStageResult",
    "TargetDescriptor",
    "TargetRefusal",
    "TargetFault",
    "ReferenceSoftwareTargetAdapter",
    "UnboundPhysicalTargetAdapter",
    "build_execution_target_invocation",
    "verify_execution_target_invocation",
    "execute_target_attempt",
    "verify_execution_target_attempt",
    "write_execution_target_artifact",
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
    "analyze_pck_lowering",
    "analyze_pck_frontier",
    "analyze_pck",
]
