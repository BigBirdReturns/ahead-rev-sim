# FAMBS PCK Memory-Irregular Lowering

The second workload-specific lowering binds the proposed FAMBS v0.4.0 Pointer Chase Kernel to its accepted result and tests the assumption that data-dependent control necessarily requires branch history.

## Source and accepted result

```text
repository  BigBirdReturns/future-ai-microbench-suite
commit      69498d4eebec9bed6f9c6793f13f9e20e89a866b
source      src/pck_pointer_chase.c
blob        fc75ef688c0dd81c17d3f647d0328797a3378d76
result      0000000006de4698
kind        i32_sum_bits
```

The reference pool contains 1,024 nodes. Initialization generates a deterministic shuffled order with a 32-bit linear congruential generator, then derives immutable payload and next-index arrays from that order. The default workload executes 256 chases of depth 128 and accumulates the chase results.

## Reversible initialization

The LCG multiplier is odd and therefore invertible modulo `2^32`. The lowering records the final seed and uses the modular inverse `0xeeb9eb65` to traverse the shuffle backward. Each swap is self-inverse once its generated index is reconstructed. The derived payload and next-index arrays can then be cleared by recomputing their expected values into clean targets.

The initialization proof restores the original ordered array and seed without a per-swap history log.

## The control result

Each chase step applies one of two index transitions:

```text
odd payload   next_index[index]
even payload  (index + 13) mod 1024
```

The complete generated map was enumerated over all 1,024 indices. The odd branch has 512 domain elements and 512 outputs. The even branch has 512 domain elements and 512 outputs. Their output sets are disjoint, and the union covers every index exactly once.

```text
domain states              1,024
unique successor states    1,024
odd image                     512
even image                    512
image intersection               0
path-history bits per step       0
```

The successor index therefore identifies both the predecessor index and the branch. The accumulator is restored by modular subtraction of the predecessor payload. An inverse-transition table supplies constant-time reverse lookup.

This is the architectural finding: branch irregularity is a control-flow property, while information loss is a state-map property. A data-dependent branch whose combined state transition is bijective does not require a stored path bit.

## Retained-state frontier

After each chase, the outer sink needs the chase result. The complete program can either retain a chase's final 42-bit `(accumulator,index)` state for later cleanup or reverse it immediately and recompute it when the sink is uncomputed. The frontier varies the number of retained final states from zero to all 256.

The endpoints are:

```text
retain 0 final chase states
peak reversible state       42 bits
semantic work          541,185 operations
zero-support recovery threshold  74.2195368%

retain all 256 final chase states
peak reversible state   10,752 bits
semantic work          279,041 operations
zero-support recovery threshold  50.0001792%
```

All ten retained-state points are nondominated. More retained state reduces recomputation. Every point reproduces the exact accepted result, restores the outer sink, restores every chase to `(accumulator=0,start_index)`, and restores the initialized pool construction with zero modeled path history and zero modeled information erasure.

The conventional parity baseline contains 139,520 normalized semantic operations. Energy thresholds remain normalized. Support memory, inverse-table access, target latency, memory-system behavior, and physical readout must enter the measured receipt before a physical advantage can be claimed.

## RISC-V and physical-substrate consequences

The portable handoff remains `physical-compute-mmio/v1`, with `Xphys` available only as an optional acceleration path. Candidate substrate operators are:

```text
read_only_irregular_walk
state_recoverable_piecewise_transition
```

A future RISC-V implementation would benefit from efficient dynamic indexed loads, modular accumulator add and subtract, a read-only inverse-transition table, and a reversible local-state retention hint. These are candidate mechanisms, not yet an ISA proposal.

The same operator contract can be implemented by conventional memory, near-memory logic, a reversible data path, an analog or physical associative structure, or another substrate. Every implementation must return the same accepted result or use the software fallback.

## CLI

```bash
ahead-rev-pck \
  --out artifacts/fambs-pck-lowering.json \
  --require-accepted
```

## Claim boundary

The artifact proves the default PCK semantic result, reversible initialization, the complete 1,024-state index permutation, zero-bit path-history recovery, all default chase round trips, and a retained-state space-time frontier. It does not prove emitted RISC-V code, target memory-system behavior, measured timing, physical substrate execution, energy, volume, thermal closure, or manufacturability.
