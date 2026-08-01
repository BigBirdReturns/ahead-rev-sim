# FAMBS Deterministic Intake

The Future AI Microbench Suite is the first workload estate used to drive the reversibility frontier and the physical-substrate contract. Intake is not a name-level integration. It binds a suite version, Git commit, configuration, harness, result format, workload source blobs, source-emission behavior, reference results, accepted-output contract, and any observed JSONL stream into one sealed artifact.

## Two preserved source generations

The repository now carries two manifests because the defect and its correction are both evidence.

### FAMBS v0.3.2 source candidate

```text
repository  BigBirdReturns/future-ai-microbench-suite
commit      a57c72d46c601fa253b8bc1acda5c37b31f8264e
version     0.3.2
manifest    examples/fambs/fambs-v0.3.2-source-manifest.json
```

The pinned source emits 265 JSON rows for a complete harness run. Five standalone kernels emit one row each. `MBW` emits sequential, random, and 64-byte-strided rows. `MAL` calls four reporting wrappers inside each of its 64 timed iterations, producing 256 nested child rows before its own summary.

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

The published v0.3.2 reference document contains seven rows and gives `MBW` a `bandwidth_mix` note that the pinned source does not emit. Every workload also ends with a placeholder self-check and exposes no accepted-output digest or quality rule. The intake preserves that source state and refuses performance or useful-work promotion.

### FAMBS v0.4.0 proposed correction

```text
repository  BigBirdReturns/future-ai-microbench-suite
commit      69498d4eebec9bed6f9c6793f13f9e20e89a866b
status      proposed_pull_request
pull request 1
version     0.4.0
manifest    examples/fambs/fambs-v0.4.0-pr1-source-manifest.json
```

The proposed source emits nine rows. `MBW` retains three distinct modes. `MAL` calls non-reporting semantic functions inside its timed interval and emits one composite result. The result contract binds each row to `fambs.result/v1`, suite version, contract identity, benchmark, mode, iteration count, semantic result, result interpretation, producer acceptance, and one explicit clock kind per observed stream.

The nine accepted result identities are:

```text
SVK                       000000004700158d  f32_bits
MGT                       0000000000008000  u32_sum
MAK                       0000000000060f8d  f32_q1e4
MRK                       94c54bd23e4e55b9  topk_index_fnv1a64
PCK                       0000000006de4698  i32_sum_bits
MBW sequential            00000000ff500000  u32_sum
MBW random                00000000ff500000  u32_sum
MBW strided_64B            00000000fef60000  u32_sum
MAL                       da291590ff6769a5  child_result_fnv1a64
```

The intake distinguishes three states:

```text
captured_blocked
source, reference, or observed evidence conflicts with the declared contract

captured_shape_closed
source shape and result contract are internally closed, but no observed run is bound

captured_result_qualified
an observed stream matches source shape and every semantic result contract row
```

A result-qualified stream establishes accepted workload output for that source and configuration. It still does not establish comparable performance. Timing comparison additionally requires the same clock semantics and a pinned compiler, runtime, emulator or hardware, and measurement boundary.

## Observed result validation

An observed v0.4.0 stream is checked for:

- source-derived row count and benchmark distribution;
- JSON parse integrity;
- unknown benchmark identities;
- result schema, suite version, and contract identity;
- benchmark, mode, and iteration identity in exact row order;
- semantic result and result-kind equality;
- producer acceptance;
- a present clock kind; and
- one clock kind across the complete harness stream.

The first mismatch is retained as a machine-readable divergence. A producer cannot promote a row merely by setting `accepted=true`, because the external intake independently compares the row with the pinned result contract.

## CLI

Capture a source generation without claiming that an observed run exists:

```bash
ahead-rev-fambs examples/fambs/fambs-v0.4.0-pr1-source-manifest.json \
  --out artifacts/fambs-v0.4.0-intake.json
```

Bind an observed result stream:

```bash
ahead-rev-fambs examples/fambs/fambs-v0.4.0-pr1-source-manifest.json \
  --results run.jsonl \
  --out artifacts/fambs-v0.4.0-observed.json \
  --require-qualified
```

`--require-qualified` returns exit code `2` unless accepted work is established by an observed stream. Ordinary capture returns zero because preserving a source candidate, including a blocked one, is valid even when promoting it is not.

## Claim boundary

The intake establishes pinned source identity, workload taxonomy, source-emission shape, reference reconciliation, result-contract identity, and accepted output for a matching observed stream. It does not establish physical energy, thermal closure, occupied volume, RISC-V target parity, timing comparability, or architecture advantage.
