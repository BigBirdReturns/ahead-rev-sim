# Energy, Volume, and Performance receipts

EVP is a first-class qualification layer. It is not a descriptive tag attached to a device, a scalar ranking chosen by the framework, or a synonym for energy efficiency.

The reversibility frontier, physical-substrate receipt, RISC-V attachment surface, and EVP receipt have different authority:

1. The reversibility frontier derives information loss, history, ancilla, uncompute, domain-crossing, normalized energy-recovery, and runtime-parity requirements from an accepted workload.
2. A physical-substrate receipt establishes execution identity, signal roles, state, reset, determinism, entropy custody, fallback, admission, refusal, and output for one substrate attempt.
3. The RISC-V MMIO and cartridge interfaces transport the transaction. They do not prove that the attached host or cartridge is efficient.
4. The EVP receipt measures the accepted result across a declared complete boundary and compares the resulting Energy, Volume, and Performance vector with a sealed baseline.

A later attachment, vendor profile, compiler, RTL block, package, or testbed cannot supersede any earlier layer. It contributes evidence to the next layer.

## Energy

The energy ledger keeps energy origins and returns separate:

- external supply;
- ambient harvested energy;
- signal-coupled energy;
- recovered energy returned across the declared boundary;
- measurement overhead; and
- a component-level breakdown covering host, memory, cartridge, interconnect, conversion, control, sensing, readout, and cooling where applicable.

The receipt derives gross physical input, net physical energy, net external energy, instrumented total, and both net physical and net external joules per accepted work unit. Recovered energy cannot exceed all declared physical inputs. A complete-system claim is blocked when the component breakdown does not reconcile with the boundary input within the declared uncertainty.

Ambient energy is therefore not declared free. It appears as a physical input even when it reduces conventional utility draw.

## Volume

Volume is the occupied allocation required to deliver the accepted result. The source contract lists component volumes in cubic millimetres and names the allocation rule. A complete-system boundary normally includes the host, memory, cartridge, interconnect, conversion, board or package, sensing and readout, and cooling allocations.

The receipt derives total occupied volume and occupied volume per concurrent accepted work unit. A device-only die area cannot silently become a complete-system volume claim.

## Performance

Performance binds the accepted work count to the same measurement interval used by the other dimensions. The receipt records:

- elapsed time;
- boundary interval;
- primary latency;
- optional p95 latency;
- accepted work per second;
- clock kind and clock identity; and
- uncertainty.

A complete-system claim is blocked when the performance interval and boundary interval diverge beyond the declared uncertainty.

## Comparison

EVP remains a vector. The receipt does not emit a policy-weighted scalar score. When a baseline is supplied, it must match:

- workload contract;
- accepted work unit;
- measurement boundary;
- claim scope; and
- environment manifest.

The comparison emits separate energy, volume, throughput, and latency ratios. `pareto_dominates_baseline` becomes true only when the candidate is no worse in every dimension and strictly better in at least one. `advantage_claim_allowed` additionally requires accepted work, measured E/V/P, instrument custody, calibration and environment manifests, a closed complete-system boundary, reconciled energy, synchronized time, and a comparable sealed baseline.

## Ahead and Vaire attachment

AheadComputing may appear in `provenance.supplier_chain` as a RISC-V host candidate. Vaire Computing may appear as a reversible-cartridge candidate. Their names do not alter the receipt rules. Either implementation remains replaceable, and neither receives authority over accepted work, the measurement boundary, fallback, or the baseline.

The same receipt can qualify an open RISC-V core, a conventional host, a thermodynamic sampler, an RC relaxation network, a photonic fabric, a neuromorphic system, a molecular system, or a harvested-world reservoir.

## CLI

```bash
ahead-rev-evp examples/evp/reference-model.json \
  --out artifacts/reference-model.evp.json
```

A measured qualification may be enforced with:

```bash
ahead-rev-evp measurement.json \
  --out artifacts/measurement.evp.json \
  --require-measured
```

A complete-system Pareto advantage may be enforced with:

```bash
ahead-rev-evp candidate.json \
  --out artifacts/candidate.evp.json \
  --require-measured \
  --require-advantage
```

The command exits with code `2` when the requested evidence tier is not qualified.

## Claim boundary

A modeled receipt remains useful for architecture pressure and experiment design. It does not establish physical advantage. A measured component receipt remains useful for bounded device characterization. It does not establish complete-system advantage. A complete-system EVP advantage requires a sealed baseline and a Pareto improvement across the same accepted work, boundary, and environment.

The control question is: for the same accepted work and measurement boundary, does the candidate use no more net physical energy and occupied volume while delivering no less throughput and no greater latency than the sealed baseline?
