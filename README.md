# ahead-rev-sim 0.10.0

[![CI](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/ci.yml/badge.svg)](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/ci.yml)
[![RTL Attachment Execution](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/rtl-attachment.yml/badge.svg)](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/rtl-attachment.yml)
[![Provider Hitch Surface](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/provider-hitch.yml/badge.svg)](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/provider-hitch.yml)
[![RISC-V Target Model](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/riscv-target.yml/badge.svg)](https://github.com/BigBirdReturns/ahead-rev-sim/actions/workflows/riscv-target.yml)

`ahead-rev-sim` is a workload-to-physics evidence system for reversible and heterogeneous RISC-V compute. It combines instantiated information semantics, exact forward and reverse execution proofs, workload custody, provider-neutral physical-compute interfaces, executed RTL attachment evidence, scale and venue receipts, causal synchronization, and complete-system Energy, Volume, and Performance qualification.

The repository is production-hardened as a Python software package and evidence producer. It does not claim that a physical substrate has performed useful computation, recovered net energy, achieved a complete-system EVP advantage, closed timing or thermal requirements, or reached fabrication acceptance.

## Authority model

The system keeps the accepted workload, reference fallback, verifier, refusal behavior, evidence boundary, and historical record outside every provider and implementation.

```text
accepted workload and quality contract
        ↓
information and reversibility frontier
        ↓
executable lowering and restoration proof
        ↓
provider-neutral RISC-V host, MMIO, resolver, and cartridge transaction
        ↓
scale, venue, and causal-custody receipts
        ↓
complete-system EVP vector
        ↓
independent acceptance
```

Companies, universities, standards bodies, open-source projects, testbeds, foundries, and research programmes are treated as replaceable commodity suppliers. Their code, models, devices, interfaces, facilities, and measurements can enter the system without acquiring authority over the workload or result.

## What is implemented

The current software estate provides:

- instantiated reversibility analysis that rejects collapsing aliases rather than trusting mnemonics;
- deterministic frontier artifacts for history, ancilla, uncomputation, commits, crossings, runtime, and normalized recovery pressure;
- exact history-complete execution with accepted-output verification and entry-state restoration;
- source-pinned Future AI Microbench Suite intake, including structured SVK and memory-irregular PCK lowerings;
- `physical-compute-mmio/v1`, with generated JSON, C, SystemVerilog, and SVA artifacts;
- `physical-cartridge-link/v1`, with an opaque-handle resolver and replaceable cartridge boundary;
- an executed Icarus Verilog lifecycle across bridge admission, cartridge refusal, resolver fault, load, evolve, read, capture, and receipt paths;
- fail-closed RTL source custody that rejects altered manifests, stale MMIO, changed resolver or cartridge sources, incomplete source sets, and divergent traces;
- deterministic RC-like and trace-replay thermodynamic reference cartridges;
- a held-out assay that separates useful physical transformation from sensing;
- provider-neutral host and cartridge hitches, including reserved AheadComputing and Vaire offer manifests that do not imply participation or endorsement;
- an independently implemented RV64GC lifecycle proof under GNU RISC-V tooling and QEMU;
- a source-bound Chipyard TileLink integration candidate;
- Energy, Volume, throughput, and latency receipts with matched-baseline Pareto admission;
- explicit scale-seam tax across adjacent system domains;
- portable remote-venue submission, return, local acceptance, and substitution receipts;
- multi-clock causal custody for state, entropy, environment, calibration, instruments, power, thermal traces, and accepted output;
- a 73-record admitted commodity registry, 12 completion lanes, 19 congruent-shape pylons, and a controlled second-wave intake surface.

## Evidence boundary

The current qualified tier is deterministic software evidence, RV64GC target-model execution, and provider-neutral Icarus RTL attachment execution. The standalone RTL proof establishes compiled command, state, refusal, fault, resolver, and receipt behavior. It does not establish a Chipyard subsystem, FPGA, silicon, or physical-compute result.

The following remain open gates:

- target-observed FAMBS v0.4 output;
- composite workload lowering;
- Chipyard subsystem elaboration and RTL execution;
- FPGA or measured-silicon execution;
- an acknowledged external provider submission;
- a measured nonfallback physical cartridge;
- synchronized physical instruments and entropy custody;
- complete-system EVP against a matched sealed baseline;
- fabrication, package, and reliability evidence;
- artifact-only independent physical acceptance.

## Installation

Python 3.10 through 3.13 are supported by the declared test matrix.

```bash
git clone https://github.com/BigBirdReturns/ahead-rev-sim.git
cd ahead-rev-sim
python -m venv .venv
```

On Linux or macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Verify the installed authority surface:

```bash
ahead-rev-doctor --strict
ahead-rev-sim --version
pytest -q
```

## First execution proof

Generate a reversibility frontier from the repository fixture:

```bash
ahead-rev-frontier \
  examples/asm/mixed_frontier.asm \
  --accepted-output examples/asm/accepted-output.json \
  --out artifacts/frontier.json
```

Execute the history-complete lowering and prove exact restoration:

```bash
ahead-rev-prove \
  examples/asm/mixed_frontier.asm \
  --fixture examples/asm/execution-fixture.json \
  --out artifacts/execution-proof.json
```

## Generate the RISC-V control plane

```bash
ahead-rev-mmio \
  --format bundle \
  --out-dir artifacts/mmio

ahead-rev-chipyard \
  --out-dir artifacts/chipyard
```

The MMIO interface is the portability floor. `Xphys` is reserved as an optional acceleration path and cannot alter the workload, descriptor, refusal behavior, fallback, or evidence boundary.

## Execute the provider-neutral RTL attachment

Install Icarus Verilog, then generate the current MMIO authority and attachment bundle:

```bash
mkdir -p artifacts/rtl-attachment

ahead-rev-mmio \
  --format systemverilog \
  --out artifacts/rtl-attachment/ahead_physical_compute_mmio_v1.sv

ahead-rev-rtl bundle \
  --out-dir artifacts/rtl-attachment
```

Compile and execute the bridge, opaque-handle resolver, cartridge, and testbench:

```bash
iverilog \
  -g2012 \
  -Wall \
  -s ahead_physical_compute_attachment_tb \
  -o artifacts/rtl-attachment/rtl-attachment.vvp \
  artifacts/rtl-attachment/ahead_physical_compute_mmio_v1.sv \
  artifacts/rtl-attachment/ahead_reference_handle_resolver_v1.sv \
  artifacts/rtl-attachment/ahead_reference_reversible_cartridge_v1.sv \
  artifacts/rtl-attachment/ahead_physical_compute_attachment_tb.sv

vvp artifacts/rtl-attachment/rtl-attachment.vvp \
  | tee artifacts/rtl-attachment/rtl-attachment.raw.trace

sed '/\$finish called at /d' \
  artifacts/rtl-attachment/rtl-attachment.raw.trace \
  > artifacts/rtl-attachment/rtl-attachment.trace

diff -u \
  artifacts/rtl-attachment/rtl-attachment.expected \
  artifacts/rtl-attachment/rtl-attachment.trace
```

Seal the execution only after source custody and accepted-trace comparison pass:

```bash
ahead-rev-rtl proof \
  --executable artifacts/rtl-attachment/rtl-attachment.vvp \
  --trace artifacts/rtl-attachment/rtl-attachment.trace \
  --expected artifacts/rtl-attachment/rtl-attachment.expected \
  --manifest artifacts/rtl-attachment/rtl-attachment-manifest.json \
  --source artifacts/rtl-attachment/ahead_physical_compute_mmio_v1.sv \
  --source artifacts/rtl-attachment/ahead_reference_handle_resolver_v1.sv \
  --source artifacts/rtl-attachment/ahead_reference_reversible_cartridge_v1.sv \
  --source artifacts/rtl-attachment/ahead_physical_compute_attachment_tb.sv \
  --out artifacts/rtl-attachment/rtl-attachment-proof.json
```

The accepted reference transaction loads state `0x2A`, evolves it to output `0x54`, and captures the deterministic receipt word `0x52544C50524F4F46`. See [the RTL attachment proof](docs/rtl_attachment_proof.md) for the complete actor map, refusal ledger, and reconstruction procedure.

## Exercise a physical-compute reference cartridge

```bash
ahead-rev-substrate \
  rc-relaxation-reference-v1 \
  --samples "65536,32768,16384,8192" \
  --calibration-sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --out artifacts/rc-reference.json
```

Reference execution proves contract behavior only. It does not prove that a physical device performed the transformation.

## Compose host and cartridge hitches

The internal reference pair is execution-admitted:

```bash
ahead-rev-hitch \
  --host examples/hitches/reference-rv64gc-host.hitch.json \
  --cartridge examples/hitches/reference-loopback-cartridge.hitch.json \
  --out artifacts/reference-consist.json \
  --require-admitted
```

The reserved AheadComputing plus Vaire offers are interface-compatible but deliberately unqualified:

```bash
ahead-rev-hitch \
  --host examples/hitches/aheadcomputing-riscv-host.offer.json \
  --cartridge examples/hitches/vaire-reversible-cartridge.offer.json \
  --out artifacts/ahead-vaire-offer-consist.json
```

Those offer manifests reserve replaceable integration positions. They do not state that either company has acknowledged, implemented, supplied, or endorsed the interface.

## Generate system receipts

```bash
ahead-rev-evp \
  examples/evp/reference-model.json \
  --out artifacts/reference.evp.json

ahead-rev-scale-seam \
  examples/scale_seam/reference-model.json \
  --out artifacts/scale-seam.json

ahead-rev-causal \
  examples/causal_custody/reference-model.json \
  --out artifacts/causal-custody.json
```

Reference receipts retain blockers for measured and complete-system claims.

## Prove bounded venue substitution

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

Service completion is never treated as accepted work. Local verification retains authority.

## Ecosystem and pylon commands

```bash
ahead-rev-commodities --priority-max 1 --out artifacts/commodities.json
ahead-rev-fanout --priority-max 1 --out artifacts/completion-plan.json
ahead-rev-pylons --out artifacts/pylon-atlas.json --require-complete
ahead-rev-wave --priority-max 1 --out artifacts/second-wave.json
```

The admitted registry and second-wave staging surface are intentionally separate. A candidate must close source, license, adapter, fixture, receipt, refusal, and substitute-coverage requirements before promotion.

## Command surface

| Command | Authority |
| --- | --- |
| `ahead-rev-sim` | Core simulator, examples, version, and doctor entry point |
| `ahead-rev-frontier` | Information-effect and reversibility frontier |
| `ahead-rev-prove` | Accepted output and exact restoration proof |
| `ahead-rev-fambs`, `ahead-rev-svk`, `ahead-rev-pck` | Workload custody and lowerings |
| `ahead-rev-substrate` | Reference physical-compute cartridges |
| `ahead-rev-mmio` | Portable RISC-V MMIO control-plane generation |
| `ahead-rev-rtl` | Provider-neutral RTL bundle generation and executed-proof sealing |
| `ahead-rev-chipyard` | Source-bound Chipyard integration generation |
| `ahead-rev-hitch`, `ahead-rev-consist-proof` | Provider-neutral composition and target binding |
| `ahead-rev-evp` | Complete-system Energy, Volume, and Performance vector |
| `ahead-rev-scale-seam` | Adjacent scale-domain cost attribution |
| `ahead-rev-venue` | Remote submission, return verification, and substitution |
| `ahead-rev-causal` | Multi-clock causal custody |
| `ahead-rev-commodities`, `ahead-rev-fanout` | Admitted ecosystem intake and completion lanes |
| `ahead-rev-pylons`, `ahead-rev-wave` | Congruent-shape architecture and controlled second-wave intake |
| `ahead-rev-doctor` | Installed package and source-governance preflight |

## Repository governance

The repository accepts only public or independently generated material. Do not contribute employer PDKs, unreleased libraries, customer designs, internal roadmaps, confidential scripts, restricted documents, private device data, or work performed through unauthorized systems or accounts.

Review the following before contributing:

- [Contributing](CONTRIBUTING.md)
- [Governance](GOVERNANCE.md)
- [Security policy](SECURITY.md)
- [Production readiness](docs/production_readiness.md)
- [Release process](docs/release_process.md)
- [Changelog](CHANGELOG.md)

## License and citation

The software is released under the MIT License. Citation metadata is provided in [`CITATION.cff`](CITATION.cff).

Copyright 2025-2026 Jonathan Sandhu and ahead-rev-sim contributors.
