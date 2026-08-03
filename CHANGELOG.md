# Changelog

All notable changes to `ahead-rev-sim` are recorded here. The format follows Keep a Changelog, and releases use Semantic Versioning for the Python package and command surface.

## [Unreleased]

### Added

- Exact pinned Chipyard subsystem elaboration and RV64GC lifecycle execution through the generated Verilator `TestHarness`, with FESVR, HTIF, CIRCT, binary, simulator, trace, refusal, and portable artifact custody.
- `ahead.execution-target-invocation/v0.1` and `ahead.execution-target-attempt/v0.1` for content-addressed capsule invocation and ordered target-attempt receipts.
- `ahead-rev-target` for sealing invocations, executing deterministic reference or unbound-FPGA attempts, and verifying accepted, refused, or faulted receipts.
- A reusable execution-target workflow that proves the accepted reference path, discovery refusal, tamper refusal, schema conformance, and extraction-relative artifact checksums.

### Changed

- Tagged release admission now reconstructs the provider-neutral execution-target boundary in addition to the standalone RTL attachment and Chipyard lifecycle.
- Production documentation now distinguishes executed pinned Chipyard RTL from still-unproven external-cartridge, FPGA, silicon, physical-substrate, and complete-system claims.

### Evidence boundary

The new execution-target receipt qualifies capsule identity, target identity, ordered stage history, accepted-output comparison, fallback, cleanup, and refusal behavior at the software or simulation tier. It cannot self-authorize physical execution, measured energy, timing, thermal, volume, fabrication, complete-system advantage, or independent physical acceptance.

## [0.10.0] - 2026-08-01

### Added

- `physical-cartridge-link/v1`, which separates the generated MMIO bridge, opaque-handle resolver, and replaceable cartridge state machine.
- `ahead-rev-rtl bundle` for deterministic generation of the resolver, cartridge, testbench, accepted trace, contract, and sealed manifest.
- `ahead-rev-rtl proof` for admitting an executed RTL transaction only after source custody and byte-identical trace comparison pass.
- Actual Icarus Verilog compilation and `vvp` execution across ambiguous-command refusal, reset, invalid-descriptor refusal, resolver fault, load, evolve, read, capture, and receipt paths.
- Draft 2020-12 schemas for the RTL attachment contract, generated manifest, and executed proof.
- Fail-closed source-custody checks for stale MMIO, altered resolver, cartridge or testbench sources, incomplete source sets, duplicate source identities, forged manifests, and divergent traces.
- A reconstructable RTL evidence kit containing the exact sources, accepted and raw traces, schemas, manifest, and sealed proof.
- Production packaging, release, security, governance, support, conduct, and repository-integrity controls.
- Installed-package doctor, clean-wheel smoke qualification, Windows command qualification, CodeQL, and dependency update automation.

### Changed

- The qualified software evidence tier now includes provider-neutral standalone RTL attachment execution in addition to deterministic Python evidence and RV64GC target-model execution.
- The public RTL proof API now routes through fail-closed source custody rather than exposing the lower-level proof constructor directly.
- All generated RTL attachment and MMIO artifacts written by the public CLIs use exact UTF-8 LF bytes on every supported operating system.
- The installed command surface expands to twenty-five commands with `ahead-rev-rtl`.

### Fixed

- Windows newline translation can no longer change generated SystemVerilog, expected traces, manifests, or proof bytes after their hashes are calculated.
- Simulator diagnostics emitted after `$finish` are retained in a raw trace but excluded from the accepted semantic trace.
- Package-level RTL writers and proof builders now resolve to the deterministic and fail-closed implementations.

### Evidence boundary

Version 0.10.0 establishes executed open-source RTL evidence for the standalone MMIO, resolver, and cartridge attachment. It does not establish Chipyard subsystem elaboration, FPGA or silicon execution, physical substrate work, measured energy recovery, complete-system EVP advantage, fabrication, acknowledged external-provider participation, or independent physical acceptance.

## [0.9.0] - 2026-08-01

### Added

- Instantiated information-effect analysis that rejects collapsing operand aliases.
- Deterministic reversibility-frontier artifacts for history, ancilla, uncomputation, commits, crossings, runtime, and normalized recovery pressure.
- History-complete execution proofs with accepted-output verification and exact entry-state restoration.
- Source-pinned Future AI Microbench Suite intake, including structured SVK and memory-irregular PCK lowerings.
- Typed physical-compute substrate descriptors, signal roles, entropy custody, reset semantics, fallbacks, and sealed receipts.
- Deterministic RC-like relaxation and trace-replay thermodynamic reference cartridges.
- Held-out physical assay separating sensing from useful transformation.
- Generated `physical-compute-mmio/v1` JSON, C, SystemVerilog, and SVA surfaces.
- Source-bound Chipyard TileLink integration candidate and bare-metal lifecycle smoke.
- Provider-neutral host and cartridge hitches, including unacknowledged AheadComputing and Vaire offer manifests.
- Independently implemented RV64GC target-model execution and consist-bound proof.
- First-class Energy, Volume, throughput, and latency receipts with matched-baseline Pareto admission.
- Explicit scale-seam communication, synchronization, retry, latency, energy, volume, utilization, and failure-domain receipts.
- Portable remote-venue submission, raw-return verification, local acceptance, and bounded substitution receipts.
- Multi-clock causal custody for state, entropy, environment, calibration, instruments, power, thermal traces, and accepted output.
- A 73-record admitted commodity registry, twelve completion lanes, nineteen congruent-shape pylons, and a controlled twenty-five-record second-wave staging surface.

### Changed

- RISC-V is treated as the portable control, isolation, state-custody, fallback, and provenance plane rather than as a privileged physical implementation.
- External companies, standards bodies, open-source projects, facilities, and programmes are treated as replaceable commodities behind workload and receipt authority.
- EVP is a vector and may not be collapsed into a policy-weighted scalar score.
- Provider offer manifests are explicitly nonparticipatory until acknowledged external artifacts are supplied and independently reconstructable.

### Fixed

- `RXOR` and `RMODADD` self-alias cases are rejected because they collapse state.
- PCK retained-state frontier generation is bounded to the actual workload cardinality.
- The package-level PCK analysis surface now exposes explicit lowering and frontier names while preserving the established `analyze_pck` behavior.
- The repository license no longer attributes copyright to an external company that does not govern the project.

### Evidence boundary

Version 0.9.0 establishes deterministic software evidence and RV64GC target-model execution. It does not establish physical substrate execution, measured energy recovery, complete-system EVP advantage, Chipyard RTL execution, fabrication, or independent physical acceptance.

## [0.8.0] - 2026-07-02

### Added

- `REXCH` reversible register-memory exchange.
- Modular-add naming through `RMODADD`.
- Parser, register validation, and deterministic loading hardening.

## [0.7.0] - 2026-05-19

### Added

- Time-travel debugger.
- History-buffer analysis.
- Reversible-memory preview.

## [0.6.0] - 2025-12-08

### Added

- Initial complete forward and reverse execution release.

[Unreleased]: https://github.com/BigBirdReturns/ahead-rev-sim/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/BigBirdReturns/ahead-rev-sim/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/BigBirdReturns/ahead-rev-sim/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/BigBirdReturns/ahead-rev-sim/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/BigBirdReturns/ahead-rev-sim/compare/v0.6.0...v0.7.0
