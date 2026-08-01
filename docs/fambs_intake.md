# FAMBS Deterministic Intake

The Future AI Microbench Suite is the first workload estate used to drive the reversibility frontier. The intake does not copy benchmark names into a dashboard and call the work integrated. It binds a suite version, Git commit, configuration, harness, common result contract, seven source blobs, source-emission behavior, reference-result prose, and any observed JSONL stream into one sealed artifact.

## Pinned source

The initial manifest targets:

```text
repository  BigBirdReturns/future-ai-microbench-suite
commit      a57c72d46c601fa253b8bc1acda5c37b31f8264e
version     0.3.2
workloads   SVK MGT MAK MRK PCK MBW MAL
```

Each workload carries its source Git blob SHA-1, exact configuration, architectural class, required semantic capabilities, emitted result notes, accepted-output status, and known gaps.

## Source shape versus published reference shape

The pinned harness does not emit one row per named workload. Five standalone kernels emit one row each. `MBW` emits separate sequential, random, and 64-byte-strided rows. `MAL` executes four child benchmarks inside each of its 64 outer iterations, and every child call emits its own JSON row before `MAL` emits its summary.

The source-derived full stream is therefore:

```text
SVK   65
MGT   65
MAK   65
MRK   65
PCK    1
MBW    3
MAL    1
      ---
total 265
```

The published reference document contains seven rows. Its `MBW` row also uses `bandwidth_mix`, a note not emitted by the pinned source. The intake preserves those rows as source material and deterministically marks the shape divergence. It does not discard the reference document or silently reinterpret it.

## Accepted work remains open

All seven source files end with placeholder self-check comments. Their timed loops retain sink values to resist dead-code elimination, but the result stream contains only benchmark identity, cycles, iteration count, and a note. It contains no output digest, exact expected result, tolerance, top-k identity, traversal count, or composite acceptance rule.

Accordingly, a run-to-completion row is not admitted as useful work. The intake carries:

```text
ACCEPTED_OUTPUT_CONTRACTS_UNBOUND
WORKLOAD_SELF_CHECKS_PLACEHOLDER
```

until the benchmark estate publishes stable result custody. Cycle comparisons remain blocked even when the observed stream matches the source shape.

## MAL measurement contamination

`MAL` calls `run_svk`, `run_mgt`, `run_mrk`, and `run_mak` inside its timed interval. Those functions perform their own cycle reads and print JSON before returning. The current `MAL` cycle count therefore includes child reporting and instrumentation, while the standalone child rows are also emitted as independent observations. The intake names this rather than treating the composite row as a clean workload measurement.

## CLI

```bash
ahead-rev-fambs examples/fambs/fambs-v0.3.2-source-manifest.json \
  --out artifacts/fambs-v0.3.2-intake.json
```

An observed harness stream can be reconciled without changing source custody:

```bash
ahead-rev-fambs examples/fambs/fambs-v0.3.2-source-manifest.json \
  --results run.jsonl \
  --out artifacts/fambs-v0.3.2-observed.json
```

`--require-qualified` returns exit code `2` while blockers remain. Ordinary capture returns zero because preserving an incomplete frontier is valid even when promoting it is not.

## Claim boundary

The intake establishes pinned source identity, workload taxonomy, source-emission shape, reference reconciliation, and optional observed-stream shape. It does not establish accepted output, comparable performance, physical energy, timing closure, or architecture advantage.
