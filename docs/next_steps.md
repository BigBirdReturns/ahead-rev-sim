# Next Steps — Planning Snapshot (2026-07)

Working notes from the v0.8.0 release session. Five paths, ordered
nearest-first. The order is also a dependency chain: each one makes the
next credible.

## Where things stand

- **v0.8.0 is on this branch** (PR #4): `REXCH` register/memory exchange
  in the ISA (single self-inverse op, `rd == rs1` rejected), `RADD`
  renamed `RMODADD` (closes #1; legacy mnemonic parses with a
  `DeprecationWarning` for one release cycle), `TimeTravelDebugger` typo
  fixed, memory demo integrated with the ISA, 13/13 tests green.
- **Landing page** (`index.html`) is on this branch — single-file GitHub
  Pages site with an interactive forward/reverse stepper.
- **The sibling evidence project** (signed, content-addressed knowledge
  shards; post-quantum hybrid signatures; frozen v1 spec) is at
  1.0.0rc1 with a maintainer runbook standing between rc1 and the tag.

## Housekeeping (do these first, all small)

1. Merge PR #4 → releases v0.8.0 and auto-closes issue #1.
2. Close PR #3 with a pointer here — its salvageable delta was rebuilt
   on this branch with the `rd == rs1` reversibility bug fixed and the
   RLOAD/RSTORE alias pair collapsed into `REXCH`.
3. Enable GitHub Pages (deploy from branch, main, root) to publish the
   landing page.
4. Sibling project: merge its open spoke-support PR, run the offline key
   ceremony per its RELEASE.md, cut the v1.0.0 tag.

## The five paths

### 1. Ship the evidence kernel v1.0.0 (days)

Everything is done except the maintainer-only runbook: rename stale
prototype tags, offline key ceremony, ceremony re-mint of the gold
shard, tag. Durable by construction — frozen spec, breaking changes
forbidden, hybrid post-quantum signing, correctness defined by a shard
that never recompiles. The independent second-language verifier already
merged is what turns a format into a standard.

**Proof event:** the tag exists and both verifiers accept the
ceremony-minted gold shard.

### 2. Sealed flight recorder — embodied journal shards (weeks)

Kernel side is finished (embodied profile, gap-free binary stream
check, spoke compilation support). Missing piece is one integration: a
hot buffer of sensor frames + decision events, sealed into a signed
shard at session end, verified cold on someone else's machine.

**Proof event:** record a session (simulated is fine), seal it, verify
it with only the shard + public key — and show a tampered copy failing.

### 3. Provable replay — bridge the two projects (weeks, after 2)

Reverse-debuggable execution *inside* a signed record: the shard proves
what happened; reversible execution walks backward to why. No new
theory — a demo that loads a sealed journal shard and drives this
project's time-travel debugger over it.

**Proof event:** one recorded incident, one signed shard, one
reverse-step session that locates the bad decision. Record the screen.

### 4. History-buffer sizing as a silicon design input (a month, parallel)

The nearest credible influence on chip design is the undo-FIFO sizing
data, not reversible ALUs. Calibrate `ahead-rev-history` on real
kernels (not toy loops), then write an application-note-style report:
max depth, bits/instruction, SRAM-area implications at candidate FIFO
depths. Evergreen regardless of whether reversible computing wins.

**Proof event:** a published sizing note that a silicon engineer cites
back at us.

- Sub-steps: pick 3–5 representative kernels (vision inner loop, state
  estimator, comms framing); validate the bit-cost model per entry
  type; add a `--csv` export to the analyzer; write the note.

### 5. Sovereign soft-core — RISC-V custom extension + FPGA (a season)

v0.9 (compiler intrinsics + LLVM pass) and v1.0 (RTL) get aimed at a
real target: express the reversible lane as a legal RISC-V custom
extension and run it as a soft-core on Zynq/Kria-class FPGAs — the
open-ISA, open-RTL, rebuild-from-source compute lane. Start scoping
now; start building after 1–3 land.

- v0.9 scope: reversible-region semantics, ancilla/liveness rules,
  an intrinsics header, an LLVM pass that verifies region invertibility.
- v1.0 scope: RISC-V opcode-space claim (custom-0/custom-1), undo-FIFO
  microarchitecture, exchange memory port, soft-core (Rocket/VexRiscv
  base or minimal custom), this simulator as the golden model for
  cosimulation.

**Proof event:** the v0.8 ISA re-expressed as a legal RISC-V encoding
running one mission-shaped kernel on a soft-core, cosimulated against
this simulator.

## Explicitly parked

- **Adiabatic energy-savings claims** — the two-constant energy model
  (0.1/1.0) is relative accounting, not physics. Keep as framing; do
  not present as a quantitative claim until calibrated. A decade early
  as a product pitch.
- **Performance competition with commercial NPU/SoC stacks** — wrong
  axis; the durable axes are sovereignty (open ISA/RTL) and evidence
  (signed, non-selective records).

## Open decisions to circle on

- Does path 3's replay demo live in this repo, the evidence repo, or a
  new integration repo? (Leaning: new thin repo that depends on both.)
- v0.9: LLVM upstream-style extension vs. a standalone MLIR dialect —
  issue #1's discussion (typed reversible domains, MLIR inference)
  points at the dialect route; the LLVM intrinsics route is faster.
- Which soft-core base for v1.0 (VexRiscv is the pragmatic default;
  custom core is cleaner pedagogy but slower).
- Whether the landing page should grow a "research" section hosting the
  path-4 sizing note when it exists.
