"""
Reversible Memory Region - Bridge to v0.8

This module introduces the concept of reversible memory operations:
exchange-based loads/stores that don't destroy information.

Standard memory:
  STORE r1 -> mem[addr]   # Old mem[addr] value is LOST
  LOAD  r1 <- mem[addr]   # Old r1 value is LOST

Reversible memory:
  RSTORE r1 <-> mem[addr]  # Values SWAPPED, nothing lost
  RLOAD  r1 <-> mem[addr]  # Same operation (symmetric)

This is the foundation for:
- Reversible memory regions in silicon
- Garbage-free computation (Bennett's method)
- Transactional memory without logging

v0.7: Introduces the concept and basic simulation
v0.8: Full integration with history buffer and silicon modeling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
from enum import Enum, auto


class MemoryRegionType(Enum):
    """Classification of memory regions."""
    STANDARD = auto()      # Normal irreversible memory
    REVERSIBLE = auto()    # Exchange-based reversible memory
    MIXED = auto()         # Region supports both (runtime decision)


@dataclass
class ReversibleMemory:
    """
    Memory subsystem with reversible region support.
    
    This extends the basic Memory class to track:
    - Which regions are reversible vs standard
    - Exchange history for reversible operations
    - Memory access patterns for silicon analysis
    """
    
    # Core storage
    data: Dict[int, int] = field(default_factory=dict)
    
    # Region configuration (address ranges)
    # Format: (start_addr, end_addr, region_type)
    regions: List[Tuple[int, int, MemoryRegionType]] = field(default_factory=list)
    
    # Default region type for unconfigured addresses
    default_type: MemoryRegionType = MemoryRegionType.STANDARD
    
    # Exchange log for reversible regions (for analysis, not required for reversal)
    exchange_log: List[Tuple[int, int, int]] = field(default_factory=list)  # (addr, old_mem, old_reg)
    
    # Statistics
    reversible_accesses: int = 0
    standard_accesses: int = 0
    
    def configure_region(
        self, 
        start: int, 
        end: int, 
        region_type: MemoryRegionType
    ) -> None:
        """Configure a memory region type."""
        self.regions.append((start, end, region_type))
    
    def get_region_type(self, addr: int) -> MemoryRegionType:
        """Get the region type for an address."""
        for start, end, rtype in self.regions:
            if start <= addr < end:
                return rtype
        return self.default_type
    
    def load_word(self, addr: int) -> int:
        """Standard (irreversible) load."""
        self.standard_accesses += 1
        return self.data.get(addr, 0)
    
    def store_word(self, addr: int, value: int) -> None:
        """Standard (irreversible) store."""
        self.standard_accesses += 1
        self.data[addr] = value & 0xFFFFFFFF
    
    def exchange(self, addr: int, reg_value: int) -> int:
        """
        Reversible exchange: swap register value with memory value.
        
        This is the core reversible memory primitive.
        
        Args:
            addr: Memory address
            reg_value: Current register value
            
        Returns:
            Old memory value (new register value)
        """
        self.reversible_accesses += 1
        
        old_mem = self.data.get(addr, 0)
        self.data[addr] = reg_value & 0xFFFFFFFF
        
        # Log for analysis (not required for algebraic reversal)
        self.exchange_log.append((addr, old_mem, reg_value))
        
        return old_mem
    
    def reverse_exchange(self, addr: int, reg_value: int) -> int:
        """
        Reverse a previous exchange.
        
        Since exchange is symmetric (swap), reversing is just exchanging again.
        This method exists for clarity in the execution model.
        """
        return self.exchange(addr, reg_value)
    
    def summary(self) -> Dict[str, Any]:
        """Return memory subsystem statistics."""
        return {
            "total_words": len(self.data),
            "reversible_accesses": self.reversible_accesses,
            "standard_accesses": self.standard_accesses,
            "reversibility_ratio": (
                self.reversible_accesses / (self.reversible_accesses + self.standard_accesses)
                if (self.reversible_accesses + self.standard_accesses) > 0 else 0
            ),
            "configured_regions": len(self.regions),
            "exchange_log_depth": len(self.exchange_log),
        }


@dataclass
class MemoryController:
    """
    Memory controller with hot/cold pipeline awareness.
    
    This models what a silicon memory controller would look like
    with both reversible and irreversible access paths.
    
    HOT path: Standard load/store, high bandwidth, irreversible
    COLD path: Exchange-based, lower bandwidth, reversible
    
    The controller routes requests based on:
    1. Instruction type (LOAD vs RLOAD)
    2. Address region configuration
    3. Runtime hints
    """
    
    memory: ReversibleMemory = field(default_factory=ReversibleMemory)
    
    # Pipeline statistics
    hot_requests: int = 0
    cold_requests: int = 0
    
    # Latency modeling (in cycles)
    hot_latency: int = 1
    cold_latency: int = 2  # Exchange may be slower
    
    # Bandwidth tracking
    total_cycles: int = 0
    
    def hot_load(self, addr: int) -> Tuple[int, int]:
        """
        Hot path load (standard, irreversible).
        Returns (value, latency).
        """
        self.hot_requests += 1
        self.total_cycles += self.hot_latency
        return self.memory.load_word(addr), self.hot_latency
    
    def hot_store(self, addr: int, value: int) -> int:
        """
        Hot path store (standard, irreversible).
        Returns latency.
        """
        self.hot_requests += 1
        self.total_cycles += self.hot_latency
        self.memory.store_word(addr, value)
        return self.hot_latency
    
    def cold_exchange(self, addr: int, reg_value: int) -> Tuple[int, int]:
        """
        Cold path exchange (reversible).
        Returns (old_mem_value, latency).
        """
        self.cold_requests += 1
        self.total_cycles += self.cold_latency
        return self.memory.exchange(addr, reg_value), self.cold_latency
    
    def summary(self) -> Dict[str, Any]:
        """Return controller statistics for silicon analysis."""
        total_requests = self.hot_requests + self.cold_requests
        return {
            "hot_requests": self.hot_requests,
            "cold_requests": self.cold_requests,
            "total_requests": total_requests,
            "hot_ratio": self.hot_requests / total_requests if total_requests > 0 else 0,
            "cold_ratio": self.cold_requests / total_requests if total_requests > 0 else 0,
            "total_cycles": self.total_cycles,
            "avg_latency": self.total_cycles / total_requests if total_requests > 0 else 0,
            "memory": self.memory.summary(),
        }
    
    def format_report(self) -> str:
        """Format a report for silicon engineers."""
        s = self.summary()
        m = s['memory']
        
        lines = [
            "=" * 60,
            "MEMORY CONTROLLER ANALYSIS",
            "=" * 60,
            "",
            "Request Distribution:",
            f"  HOT (irreversible):  {s['hot_requests']:5d} ({s['hot_ratio']:5.1%})",
            f"  COLD (reversible):   {s['cold_requests']:5d} ({s['cold_ratio']:5.1%})",
            f"  Total:               {s['total_requests']:5d}",
            "",
            "Latency:",
            f"  Total cycles:        {s['total_cycles']:5d}",
            f"  Avg cycles/request:  {s['avg_latency']:5.2f}",
            "",
            "Memory Subsystem:",
            f"  Words allocated:     {m['total_words']:5d}",
            f"  Exchange log depth:  {m['exchange_log_depth']:5d}",
            "",
            "Silicon Implications:",
            f"  If HOT-only: {s['hot_requests'] * self.hot_latency} cycles",
            f"  With COLD:   {s['total_cycles']} cycles",
            f"  Overhead:    {(s['total_cycles'] - s['hot_requests'] * self.hot_latency)}"
            f" cycles for reversibility",
            "=" * 60,
        ]
        
        return "\n".join(lines)


# =============================================================================
# ISA Extensions for v0.8
# =============================================================================

"""
New instructions for reversible memory (to be added in v0.8):

RLOAD  rd, rs1, imm   # rd <-> mem[rs1 + imm]  (exchange)
RSTORE rd, rs1, imm   # rd <-> mem[rs1 + imm]  (same as RLOAD, symmetric)

These are semantically identical - both perform exchange.
Two mnemonics provided for code clarity.

The key insight: exchange is self-inverse.
  RLOAD r1, r2, 0   ; swap r1 with mem[r2]
  RLOAD r1, r2, 0   ; swap again → back to original

No history buffer entry needed for reversal.
Just execute the same instruction again.

This is why reversible memory is powerful:
- No logging required
- No checkpoints required  
- Just algebraic inversion

Silicon cost: MUX for exchange path, slightly higher latency
Silicon benefit: Zero trace buffer for memory operations
"""


def demo_reversible_memory() -> None:
    """Demonstrate reversible memory operations."""
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║  REVERSIBLE MEMORY DEMO (v0.7 Preview)                            ║")
    print("║                                                                   ║")
    print("║  Exchange-based memory: nothing is ever lost.                     ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    
    ctrl = MemoryController()
    
    # Configure a reversible region
    ctrl.memory.configure_region(0x1000, 0x2000, MemoryRegionType.REVERSIBLE)
    
    print("Scenario: Swap a register with memory, then swap back")
    print()
    
    # Initial state
    reg_value = 42
    mem_addr = 0x1000
    ctrl.memory.store_word(mem_addr, 100)  # Pre-initialize
    
    print(f"Initial:")
    print(f"  Register = {reg_value}")
    print(f"  Memory[0x{mem_addr:04x}] = {ctrl.memory.load_word(mem_addr)}")
    print()
    
    # First exchange (forward)
    old_mem, _ = ctrl.cold_exchange(mem_addr, reg_value)
    reg_value = old_mem
    
    print(f"After RLOAD (exchange):")
    print(f"  Register = {reg_value}")
    print(f"  Memory[0x{mem_addr:04x}] = {ctrl.memory.load_word(mem_addr)}")
    print()
    
    # Second exchange (reverse - same operation!)
    old_mem, _ = ctrl.cold_exchange(mem_addr, reg_value)
    reg_value = old_mem
    
    print(f"After second RLOAD (reverse):")
    print(f"  Register = {reg_value}")
    print(f"  Memory[0x{mem_addr:04x}] = {ctrl.memory.load_word(mem_addr)}")
    print()
    
    print("Key insight: Exchange is self-inverse. No history needed.")
    print()
    
    # Show mixed hot/cold access pattern
    print("=" * 60)
    print("Mixed hot/cold access pattern:")
    print("=" * 60)
    print()
    
    # Simulate a realistic access pattern
    for i in range(10):
        # Hot path: standard loads/stores
        ctrl.hot_load(0x100 + i * 4)
        ctrl.hot_store(0x200 + i * 4, i * 10)
        
        # Cold path: reversible exchanges
        ctrl.cold_exchange(0x1000 + i * 4, i)
    
    print(ctrl.format_report())


if __name__ == "__main__":
    demo_reversible_memory()
