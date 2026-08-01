# Executable scale-seam and remote-venue pylons

The congruent-shape atlas identified two pylons that were structurally clear but not yet executable: the scale-seam communication tax and the remote-venue envelope. This transaction gives both a deterministic software reference contract. It does not claim measured scale behavior, remote institutional participation, physical execution, or complete-system advantage.

## Scale-seam receipt

A scale-seam receipt attributes the incremental work introduced when accepted computation crosses adjacent scale domains:

```text
operation
→ tile
→ die
→ package
→ board
→ rack
→ facility
```

Each seam declares:

- traffic bytes and message count;
- synchronization events and retries;
- latency;
- modeled or measured energy;
- incremental occupied allocation;
- utilization; and
- failure domains.

The receipt normalizes those values by accepted work, accumulates them across the chain, identifies the dominant traffic, latency, energy, and volume seams, and optionally compares them with a workload- and topology-matched baseline.

The scale receipt does not emit a complete-system advantage. Even a measured seam receipt remains blocked on `COMPLETE_SYSTEM_EVP_RECEIPT_REQUIRED`. It must enter the complete-system envelope with host, memory, conversion, control, sensing, readout, package, cooling, and accepted result before EVP can judge advantage.

Generate the reference receipt:

```bash
ahead-rev-scale-seam \
  examples/scale_seam/reference-model.json \
  --out artifacts/scale-seam.json
```

A measured gate can be enforced with `--require-measured`.

## Remote-venue envelope

A remote venue receives a sealed execution packet. It does not receive authority over accepted work.

```text
venue-neutral source packet
        ↓
sealed submission
        ↓
queue and execution venue
        ↓
provider return
        ↓
local raw-artifact and output verification
        ↓
accepted work or refusal
        ↓
comparison with another venue
```

The sealed submission binds workload identity, expected output, accepted work unit, command, environment, resources, software fallback, input files, required returned artifacts, requested receipts, and migration policy. The policy fixes `dependency_mode=commodity_only`, `provider_authority=execution_only`, and `service_completion_is_acceptance=false`.

A venue return binds service API and version, venue and queue identity, job identity, hardware, firmware, software and environment manifests, timestamps, terminal state, raw artifacts, accepted output, logs, and provider receipt. Local acceptance requires all of them. A completed remote service with the wrong output or a missing required trace remains refused.

The same sealed submission may then be compared across at least two distinct venues. Substitution is proved only when every venue return is locally accepted and the output digest is identical. This proof does not establish physical or EVP equivalence between the venues.

Seal, verify, and compare the reference transaction:

```bash
ahead-rev-venue seal \
  examples/remote_venue/reference-submission-source.json \
  --out artifacts/remote-submission.json

ahead-rev-venue verify \
  artifacts/remote-submission.json \
  examples/remote_venue/reference-return-a.json \
  --out artifacts/venue-a.json \
  --require-accepted

ahead-rev-venue verify \
  artifacts/remote-submission.json \
  examples/remote_venue/reference-return-b.json \
  --out artifacts/venue-b.json \
  --require-accepted

ahead-rev-venue compare \
  artifacts/venue-a.json \
  artifacts/venue-b.json \
  --out artifacts/venue-comparison.json \
  --require-substitution
```

## Ecosystem adapters

The reference contracts are deliberately independent of Chakra, ASTRA-sim, gem5, FireSim, WES, TES, RO-Crate, Globus, Flux, Open OnDemand, ReFrame, OpenTelemetry, Perfetto, PTP, White Rabbit, OpenHTF, QCoDeS, Bluesky, or PyMeasure. Those projects may now supply adapters, traces, models, services, clocks, instruments, and workflow envelopes behind stable receipts.

The scale-seam adapters should converge on one accepted trace and emit comparable per-seam observations. The remote-venue adapters should converge on the same sealed packet, raw-return requirements, and local verifier. The causal-custody adapters should align the resulting execution, instrumentation, and acceptance intervals.

## Remaining physical boundary

Both pylons now have software-reference authority. Their remaining claims are explicit:

- scale models must be replaced by measured traffic, timing, energy, thermal, volume, and failure observations;
- the generated Chipyard candidate must elaborate and execute at RTL;
- at least one external venue must acknowledge and return a reconstructable packet;
- clocks, instruments, calibration, environment, and accepted output must share one measured interval;
- the complete system must enter EVP against a matched sealed baseline; and
- an independent acceptor must reconstruct the transaction from artifacts alone.

The control question is: can the same accepted work move across a larger scale or a different venue while the additional causal tax, raw evidence, local acceptance, fallback, and complete-system boundary remain independently reconstructable?
