"""
History buffer instrumentation for ahead-rev-sim.

This module answers questions silicon designers actually ask:
- How much state do we need to store for reversal?
- What's the overhead per instruction class?
- How does buffer depth vary with program structure?
- Where are the high-water marks?

These metrics inform FPGA/ASIC history buffer sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from enum import Enum, auto


class EntryType(Enum):
    """Classification of history buffer entries."""
    BRANCH_DECISION = auto()    # 1 bit: taken/not taken
    BRANCH_SOURCE = auto()      # PC width: where we came from
    REVERSIBLE_OP = auto()      # Minimal: just op type (state derived)
    IRREVERSIBLE_OP = auto()    # Not stored (can't reverse anyway)


@dataclass
class HistoryEntry:
    """One entry in the history buffer."""
    pc: int
    op_name: str
    entry_type: EntryType
    payload: Any  # The actual data stored
    
    @property
    def bit_cost(self) -> int:
        """Estimated bits required to store this entry."""
        if self.entry_type == EntryType.BRANCH_DECISION:
            # 1 bit for taken/not-taken + PC for source
            return 1 + 32  # Assuming 32-bit PC
        elif self.entry_type == EntryType.BRANCH_SOURCE:
            return 32  # Just the source PC
        elif self.entry_type == EntryType.REVERSIBLE_OP:
            # We don't actually need to store data for algebraic reversal
            # Just need to know it happened (for ordering)
            return 8  # Op type identifier
        else:
            return 0  # Irreversible ops not stored


@dataclass
class HistoryBuffer:
    """
    Instrumented history buffer that tracks storage overhead.
    
    This simulates what a hardware history buffer would need to store
    to enable backward execution.
    """
    
    entries: List[HistoryEntry] = field(default_factory=list)
    
    # High-water marks
    max_depth: int = 0
    max_bits: int = 0
    
    # Per-type statistics
    counts_by_type: Dict[EntryType, int] = field(default_factory=dict)
    bits_by_type: Dict[EntryType, int] = field(default_factory=dict)
    
    # Snapshot points (for analyzing buffer pressure over time)
    depth_timeline: List[Tuple[int, int]] = field(default_factory=list)  # (step, depth)
    
    def push(self, pc: int, op_name: str, entry_type: EntryType, payload: Any = None) -> None:
        """Record a history entry."""
        entry = HistoryEntry(pc=pc, op_name=op_name, entry_type=entry_type, payload=payload)
        self.entries.append(entry)
        
        # Update statistics
        self.counts_by_type[entry_type] = self.counts_by_type.get(entry_type, 0) + 1
        self.bits_by_type[entry_type] = self.bits_by_type.get(entry_type, 0) + entry.bit_cost
        
        # Update high-water marks
        current_depth = len(self.entries)
        current_bits = sum(e.bit_cost for e in self.entries)
        
        if current_depth > self.max_depth:
            self.max_depth = current_depth
        if current_bits > self.max_bits:
            self.max_bits = current_bits
    
    def pop(self) -> HistoryEntry | None:
        """Remove and return the most recent entry."""
        if not self.entries:
            return None
        return self.entries.pop()
    
    def record_snapshot(self, step: int) -> None:
        """Record current depth for timeline analysis."""
        self.depth_timeline.append((step, len(self.entries)))
    
    @property
    def current_depth(self) -> int:
        return len(self.entries)
    
    @property
    def current_bits(self) -> int:
        return sum(e.bit_cost for e in self.entries)
    
    @property
    def total_entries_ever(self) -> int:
        return sum(self.counts_by_type.values())
    
    @property
    def total_bits_ever(self) -> int:
        return sum(self.bits_by_type.values())
    
    def summary(self) -> Dict[str, Any]:
        """Return summary statistics for silicon sizing."""
        return {
            "current_depth": self.current_depth,
            "current_bits": self.current_bits,
            "max_depth": self.max_depth,
            "max_bits": self.max_bits,
            "total_entries": self.total_entries_ever,
            "total_bits": self.total_bits_ever,
            "by_type": {
                t.name: {"count": self.counts_by_type.get(t, 0), "bits": self.bits_by_type.get(t, 0)}
                for t in EntryType
            },
            "bits_per_entry_avg": (
                self.total_bits_ever / self.total_entries_ever 
                if self.total_entries_ever > 0 else 0
            ),
        }
    
    def format_report(self) -> str:
        """Format a human-readable report for silicon engineers."""
        s = self.summary()
        lines = [
            "=" * 60,
            "HISTORY BUFFER ANALYSIS",
            "=" * 60,
            "",
            "Peak Requirements:",
            f"  Max depth:     {s['max_depth']} entries",
            f"  Max bits:      {s['max_bits']} bits ({s['max_bits'] / 8:.1f} bytes)",
            "",
            "Cumulative (full execution):",
            f"  Total entries: {s['total_entries']}",
            f"  Total bits:    {s['total_bits']} bits ({s['total_bits'] / 8:.1f} bytes)",
            f"  Avg bits/entry: {s['bits_per_entry_avg']:.1f}",
            "",
            "By Entry Type:",
        ]
        
        for t in EntryType:
            count = s['by_type'][t.name]['count']
            bits = s['by_type'][t.name]['bits']
            if count > 0:
                lines.append(f"  {t.name:20s}: {count:5d} entries, {bits:6d} bits")
        
        lines.extend([
            "",
            "Silicon Implications:",
            f"  SRAM for history buffer: ~{s['max_bits'] / 8 / 1024:.2f} KB",
            f"  Entries at 64-deep FIFO: {'OK' if s['max_depth'] <= 64 else 'OVERFLOW'}",
            f"  Entries at 256-deep FIFO: {'OK' if s['max_depth'] <= 256 else 'OVERFLOW'}",
            "=" * 60,
        ])
        
        return "\n".join(lines)


@dataclass  
class HistoryAnalyzer:
    """
    Analyzes history buffer patterns across different program types.
    
    Use this to compare:
    - Linear code vs loops
    - Branch-heavy vs compute-heavy
    - Different reversibility ratios
    """
    
    results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def record_run(self, name: str, buffer: HistoryBuffer, metrics: Any) -> None:
        """Record results from one program run."""
        self.results[name] = {
            "history": buffer.summary(),
            "reversibility_ratio": getattr(metrics, 'reversible_ratio', 0),
            "total_instructions": getattr(metrics, 'total', 0),
        }
    
    def compare(self) -> str:
        """Generate comparison report across all recorded runs."""
        if not self.results:
            return "No runs recorded."
        
        lines = [
            "=" * 70,
            "HISTORY BUFFER COMPARISON ACROSS PROGRAMS",
            "=" * 70,
            "",
            f"{'Program':<25} {'MaxDepth':>10} {'MaxBits':>10} {'Rev%':>8} {'Bits/Instr':>12}",
            "-" * 70,
        ]
        
        for name, data in self.results.items():
            h = data['history']
            total_instr = data['total_instructions']
            bits_per_instr = h['max_bits'] / total_instr if total_instr > 0 else 0
            
            lines.append(
                f"{name:<25} "
                f"{h['max_depth']:>10} "
                f"{h['max_bits']:>10} "
                f"{data['reversibility_ratio']:>7.0%} "
                f"{bits_per_instr:>12.1f}"
            )
        
        lines.extend([
            "-" * 70,
            "",
            "Key Insight: Bits/Instruction tells you buffer cost per compute.",
            "Lower is better for silicon area.",
            "=" * 70,
        ])
        
        return "\n".join(lines)
