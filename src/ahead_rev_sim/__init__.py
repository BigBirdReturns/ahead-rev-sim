"""
ahead-rev-sim v0.7.0

Reversible execution simulator for RISC-V.
History is recoverable, not recorded.
"""

from __future__ import annotations

__version__ = "0.7.0"

from .isa import Instruction, OpCode
from .machine import Machine
from .memory import Memory
from .energy import EnergyModel
from .metrics import ReversibilityMetrics
from .parser import AssemblyParser
from .history import HistoryBuffer, HistoryAnalyzer, HistoryEntry, EntryType
from .debugger import TimeTraveDebugger, Watchpoint, CorruptionReport
from .reversible_memory import ReversibleMemory, MemoryController, MemoryRegionType

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
    "TimeTraveDebugger",
    "Watchpoint",
    "CorruptionReport",
    # Parser
    "AssemblyParser",
]
