# Executable causal-custody braid

Scale and venue receipts are meaningful only when their events, instruments, state, environment, calibration, and accepted result refer to the same causal interval. The causal-custody receipt makes that requirement executable.

```text
workload state
+ device state
+ entropy or stochastic path
+ environment
+ calibration
+ instrument identity
+ clock mapping and uncertainty
+ power and thermal traces
+ accepted output
        ↓
one bounded causal record
```

The reference contract is independent of any one observability, tracing, synchronization, or instrument framework. OpenTelemetry may transport semantic events and metrics. Perfetto may provide a high-resolution trace and query surface. LinuxPTP or White Rabbit may establish clock relationships. OpenHTF, QCoDeS, Bluesky, Ophyd, or PyMeasure may operate instruments and experimental procedures. Their outputs become commodities behind one receipt.

## Clock custody

Every clock declares:

- clock identity and kind;
- reference, simulated, or measured evidence class;
- instrument identity where measured;
- calibration and environment manifests;
- offset to the reference clock;
- rate correction in parts per billion; and
- mapping uncertainty in nanoseconds.

The reference clock must use zero offset and zero rate correction. Events are strictly ordered within each clock before they are mapped into the common interval. The receipt preserves local timestamp, sequence, mapped timestamp, and lower and upper bounds under uncertainty.

## Causal edges

Causality is not inferred from display order. The source contract declares edges such as:

```text
calibration_applied -> workload_start
environment_sample  -> workload_start
power_pre            -> workload_start
workload_start       -> workload_end
workload_end         -> accepted_output
```

An edge is resolved only when the source event's upper uncertainty bound is strictly earlier than the target event's lower uncertainty bound. Overlapping bounds produce `CAUSAL_ORDER_UNRESOLVED` while preserving the receipt and the exact unresolved edge IDs.

## Required interval coverage

The reference contract requires one workload start, one workload end, and one accepted-output event. It also requires declared event kinds, a matching accepted-output digest, calibration and environment before work begins, and power observations that bracket the work interval. Execution, telemetry, power, thermal, environment, and calibration manifests are separately retained.

Determinism remains explicit:

- `exact` requires no stochastic trace;
- `replay_with_trace` requires both entropy and stochastic-path digests; and
- `distributional` permits statistical acceptance without pretending to exact replay.

## Evidence tiers

A complete reference record may qualify as `reference_causal_custody`. Measured custody additionally requires every clock to be measured and instrument identified. Neither tier authorizes a physical-compute or complete-system EVP claim. Those remain blocked until the physical substrate and complete system satisfy their own receipts.

Generate the reference receipt:

```bash
ahead-rev-causal \
  examples/causal_custody/reference-model.json \
  --out artifacts/causal-custody.json
```

The measured tier can be required with:

```bash
ahead-rev-causal \
  measurement.json \
  --out artifacts/measured-causal-custody.json \
  --require-measured
```

## Adapter order

The first adapter should define ahead semantic conventions over OpenTelemetry for workload, lifecycle, cartridge, instrument, energy, environment, acceptance, refusal, and supersession. The second should emit the same event identities into Perfetto and prove that Trace Processor queries reconstruct the accepted interval. The third should replace reference clock mappings with LinuxPTP or White Rabbit measurements and retain offset, drift, correction, holdover, path delay, synchronization energy, and fault behavior.

Instrument frameworks then attach behind the same clock and event contract. OpenHTF is appropriate for phase-based hardware qualification and limit checks. QCoDeS is appropriate for instrument snapshots, parameter sweeps, and datasets. Bluesky and Ophyd are appropriate for reusable experiment plans and device abstraction. PyMeasure provides a smaller local instrument and procedure path. None receives authority over workload acceptance or EVP.

## Claim boundary

The causal-custody receipt proves that the declared causal record is internally reconstructable at its evidence tier. It does not prove that a physical substrate performed useful work, that the trace is complete outside the declared event and manifest surfaces, or that the complete system has an EVP advantage.

The control question is: can an independent acceptor reconstruct the same event order and accepted interval from clock mappings, uncertainty, state and entropy traces, environment, calibration, instruments, and raw manifests?
