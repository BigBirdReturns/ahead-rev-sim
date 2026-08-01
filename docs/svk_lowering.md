# FAMBS SVK Reversible Lowering

The first workload-specific lowering binds the proposed FAMBS v0.4.0 Sparse Vector Kernel to its accepted binary32 result and produces an executable support-state versus work frontier.

## Source and numeric contract

```text
repository  BigBirdReturns/future-ai-microbench-suite
commit      69498d4eebec9bed6f9c6793f13f9e20e89a866b
source      src/svk_sparse_vec.c
blob        cc581df1181f6eeaa8592d22189c4c42b222bb80
result      000000004700158d
kind        f32_bits
```

The reference model rounds each multiplication to IEEE-754 binary32 and then rounds each addition separately. It does not fuse multiply and add and does not use fast-math reassociation. The 128-term sparse dot produces binary32 bits `420328f6`. Repeating the sink addition 1,000 times produces the contracted bits `4700158d`.

## Fair optimization boundary

The sparse vectors and dense vector are initialized before the outer loop and are not mutated inside it. The dot product is therefore loop invariant. The lowering hoists it for both the conventional parity baseline and every reversible strategy.

```text
source-order semantic operations       513,000
fair optimized conventional baseline     1,512
```

The removed repeated dot work is ordinary compiler optimization. It is not counted as an energy-recovery or reversible-computing advantage.

## Exact reversible schedules

A linear history schedule retains every prior sink state, copies the accepted output, and restores the sink in reverse order. It minimizes semantic work but requires 32,032 support bits, excluding the retained 32-bit accepted output.

A Bennett-style checkpoint schedule divides a recurrence into segments. Each segment is computed, its endpoint is copied, and the local history is reversed immediately. After the final output is copied, the retained checkpoints are removed by recomputing segments in reverse order. The same construction is applied independently to the 128-step dot reduction and the 1,000-step sink recurrence.

The Pareto endpoints are:

```text
dot-linear / sink-linear
support state       32,032 bits
semantic work        4,051 operations
zero-support recovery threshold  62.6758825%

 dot-pebble-32 / sink-pebble-32
support state        2,048 bits
semantic work        8,179 operations
zero-support recovery threshold  81.5136325%
```

The full frontier contains eleven nondominated points. Reducing support state increases recomputation. Each point reproduces the exact FAMBS result and restores its reference entry state with zero modeled information erasure.

The recovery threshold is deliberately normalized. For a transformed gross work value `G`, conventional parity energy `B`, physical recovery fraction `r`, and support energy `S`, parity requires:

```text
S + (1 - r)G <= B
```

The reported zero-support threshold sets `S=0`. The artifact separately reports the maximum support energy available at 80 percent recovery. A negative allowance means 80 percent physical recovery cannot close parity even before timing, memory, control, and readout are measured.

## Physical-substrate handoff

The lowering exports `binary32_sparse_dot` and `binary32_stateful_recurrence` as candidate physical operators behind `physical-compute-mmio/v1`, with `Xphys` reserved as an optional acceleration path. A thermodynamic, analog, reservoir, optical, mechanical, or harvested-world implementation must produce the same contracted result or invoke the software fallback. Its complete receipt must include readout, calibration, control, memory, energy, latency, volume, and thermal evidence.

## CLI

```bash
ahead-rev-svk \
  --out artifacts/fambs-svk-lowering.json \
  --require-accepted
```

## Claim boundary

The artifact proves the default SVK binary32 semantic result, fair loop-invariant motion, checkpoint schedules, exact reference restoration, and normalized break-even equations. It does not prove emitted RISC-V code, target floating-point parity, measured timing, physical substrate execution, energy, volume, thermal closure, or manufacturability.
