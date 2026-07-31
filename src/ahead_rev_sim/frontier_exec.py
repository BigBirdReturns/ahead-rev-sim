"""Public executable-restoration surface for the reversibility frontier."""

from .execution_proof import run_and_prove
from .execution_types import (
    EXECUTION_PROOF_ARTIFACT_TYPE,
    EXECUTION_PROOF_SCHEMA_VERSION,
    ArchitectedState,
    ExecutionProof,
    UndoRecord,
)
from .history_machine import HistoryCompleteMachine, apply_initial_state

__all__ = [
    "EXECUTION_PROOF_ARTIFACT_TYPE",
    "EXECUTION_PROOF_SCHEMA_VERSION",
    "ArchitectedState",
    "ExecutionProof",
    "HistoryCompleteMachine",
    "UndoRecord",
    "apply_initial_state",
    "run_and_prove",
]
