# ahead-rev-sim v0.7.0

Reversible execution simulator for RISC-V.  
**History is recoverable, not recorded.**

## What This Is

A software simulator for a RISC-V style core with reversible execution lanes.

```
Standard execution:  Run forward. State is overwritten. History lost.
Reversible execution: Run forward. Run backward. State derived from operations.
```

This is not theory. This is working code that demonstrates:
- Time-travel debugging (find bugs by running backward)
- History buffer sizing (answer silicon questions)
- Hot/cold pipeline modeling (preview of v0.8)

## Why It Matters

**The power wall is real.** Moore's Law ended. Dennard scaling ended. Data centers are building nuclear plants.

**The physics says:** Irreversible computation must dissipate kT ln(2) per bit erased (Landauer). Reversible computation approaches zero in the limit.

**The gap:** Nobody has a usable reversible execution environment. The theory exists (Bennett, Fredkin, Toffoli). The silicon doesn't. The toolchain doesn't.

**This project:** Working code that proves reversible execution is tractable. MIT licensed. Fork it.

## Quick Start

```bash
git clone https://github.com/BigBirdReturns/ahead-rev-sim
cd ahead-rev-sim
pip install -e .

# Time-travel debugger (the demo that makes it click)
ahead-rev-debug

# History buffer analysis (answers silicon sizing questions)
ahead-rev-history

# Reversible memory preview (bridge to v0.8)
ahead-rev-memory

# Run your own programs
ahead-rev-sim run program.asm
```

## What's New in v0.7

### Time-Travel Debugger

Run a buggy program. Walk backward to find the bug. No trace buffers.

```
$ ahead-rev-debug

Program: Compute r1 = 10 + 5 + 3 = 18
Bug: One instruction is RXOR instead of RADD

Forward execution: 7 steps
Expected r1 = 18
Actual r1   = 15

✗ Mismatch detected!

Beginning reverse execution to locate bug...

  Step back 1: Undid RADD at PC 5
    r1: 15 → 12
  Step back 2: Undid RXOR at PC 4
    r1: 12 → 15
    ⚠ This is a reversible XOR - suspicious!

Bug located at PC 4: RXOR r1 r3

The RXOR instruction corrupted the accumulator.
It should have been RADD to continue the sum.
```

### History Buffer Analysis

Answer the question silicon engineers ask: "How big does my buffer need to be?"

```
$ ahead-rev-history

HISTORY BUFFER COMPARISON ACROSS PROGRAMS

Program                      MaxDepth    MaxBits     Rev%   Bits/Instr
-----------------------------------------------------------------------
Linear reversible                  40        320     93%          7.4
Linear mixed                       10         80     43%          3.5
Tight loop                       7998     163934     80%         16.4
Nested loops                       89       1812     90%         18.3
Branch-heavy                     9997     329901    100%         33.0

Silicon Implications:
  SRAM for history buffer: ~0.22 KB
  Entries at 64-deep FIFO: OVERFLOW
  Entries at 256-deep FIFO: OK
```

### Reversible Memory Preview

Exchange-based memory operations that don't destroy information.

```
$ ahead-rev-memory

Initial:
  Register = 42
  Memory[0x1000] = 100

After RLOAD (exchange):
  Register = 100
  Memory[0x1000] = 42

After second RLOAD (reverse):
  Register = 42
  Memory[0x1000] = 100

Key insight: Exchange is self-inverse. No history needed.
```

## The ISA

### Reversible Instructions

These can be algebraically inverted:

```asm
RXOR  rd, rs1      ; rd = rd XOR rs1 (self-inverse)
RADD  rd, rs1      ; rd = rd + rs1 (inverse: subtract)
RSWAP rd, rs1      ; swap rd <-> rs1 (self-inverse)
```

### Control Flow

Branches store minimal history (1 bit + source PC):

```asm
BEQ   rs1, rs2, label    ; branch if equal
```

### Irreversible Instructions

Standard operations that overwrite state:

```asm
ADD   rd, rs1, rs2    ; rd = rs1 + rs2
SUB   rd, rs1, rs2    ; rd = rs1 - rs2
LOAD  rd, rs1, imm    ; rd = mem[rs1 + imm]
STORE rs1, rs2, imm   ; mem[rs1 + imm] = rs2
HALT
```

## The Vision: HOT/COLD Dual Pipeline

```
┌──────────────────────────────────┐
│  HOT PIPELINE  (standard CMOS)   │  ➤  current workloads
│  • irreversible ALU ops          │
│  • high frequency / high drive   │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│  COLD PIPELINE (reversible)      │  ➤  future low-power workloads
│  • reversible ALU primitives     │
│  • adiabatic switching window    │
└──────────────────────────────────┘

Shared: registers, memory, ISA decode, page tables, OS ABI
```

Legacy code still runs. Reversible code runs too. Same silicon.

## Roadmap

```
v0.6.0 ✅ First full release (forward/backward, clean repo)
v0.7.0 ✅ Time-travel debugger, history buffer analysis, memory preview
v0.8.0    Reversible memory region + RLOAD/RSTORE in ISA
v0.9.0    Compiler intrinsics + LLVM pass
v1.0.0    FPGA/RTL reference implementation
```

## For Silicon Engineers

This simulator answers your questions:

1. **Buffer sizing:** History analysis shows max depth and bits for different program patterns
2. **Instruction mix:** Metrics track reversible vs irreversible ratio
3. **Memory interface:** Hot/cold controller models bandwidth and latency tradeoffs
4. **Area estimation:** Bits per instruction tells you buffer cost per compute

## For Compiler Engineers

The reversible ISA is designed for:

1. **Basic block reversal:** Mark regions as reversible, compiler ensures algebraic invertibility
2. **Register allocation:** Reversible ops update in place, need careful liveness analysis
3. **Spill strategy:** RLOAD/RSTORE for reversible spills (v0.8)

## For Debug Engineers

Time-travel debugging changes everything:

1. **No trace buffers:** State derived from operations, not recorded
2. **No Heisenbugs:** Deterministic reversal finds exact instruction
3. **Post-silicon:** Works on real hardware with reversible ISA support

## Related Work

- Bennett, C.H. (1973). "Logical Reversibility of Computation"
- Landauer, R. (1961). "Irreversibility and Heat Generation in the Computing Process"
- Frank, M.P. (2017). "Throwing Computing into Reverse"
- [Ahead Computing](https://aheadcomputing.com) - The hardware this simulates

## License

MIT

## Author

Jonathan Sandhu ([@BigBirdReturns](https://github.com/BigBirdReturns))

---

*The audit trail is not a log. It's a physical property of the execution.*
