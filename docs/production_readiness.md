# Production readiness

Version 0.10.0 separates repository and package production quality from scientific and physical claim closure. The post-release main line now includes executed standalone RTL evidence and an exact pinned Chipyard RV64GC lifecycle through generated Verilator RTL. External-cartridge binding, physical execution, fabrication, and complete-system advantage remain unqualified.

## Production-grade software floor

The release floor requires:

- one authoritative package version;
- wheel and source-distribution builds;
- Python 3.10 through 3.13 test coverage;
- Windows and Linux installation smoke tests;
- deterministic repository and schema audit;
- import and console-entry-point qualification;
- packaged authority-resource checks;
- lint and focused type checks;
- security, contribution, governance, citation, and release policies;
- dependency and GitHub Actions update automation;
- release checksums and clean-wheel execution;
- byte-identical generated artifacts across supported operating systems;
- preserved claim boundaries and provider neutrality.

The `ahead-rev-doctor` command verifies the installed package surface. `scripts/repository_audit.py` verifies source-tree integrity. CI verifies both before a release can be tagged.

## Evidence maturity

The current evidence tiers are:

| Layer | Current state | Strongest allowed claim |
| --- | --- | --- |
| Information semantics | Implemented | Instantiated information effects and bounded collision evidence |
| Software execution | Implemented | Accepted output and exact simulator restoration |
| Workload custody | Partial | Pinned source shape and qualified reference rows |
| RISC-V target model | Implemented | RV64GC software-device lifecycle execution |
| MMIO control plane | Implemented | Generated portable register, command, refusal, and receipt semantics |
| Standalone RTL attachment | Executed | Icarus-compiled MMIO, resolver, and cartridge lifecycle with sealed source custody |
| Chipyard subsystem | Executed | Pinned elaboration and RV64GC lifecycle through generated Verilator RTL with internal loopback |
| Execution-target boundary | Implemented | Content-addressed capsule orchestration, ordered stage custody, accepted reference execution, and unbound-target refusal |
| Provider hitches | Implemented | Interface compatibility and explicit execution admission or refusal |
| Physical substrate | Reference only | Contract behavior and replay conditions |
| Scale seams | Reference only | Deterministic modeled seam attribution |
| Remote venues | Reference only | Bounded software venue substitution |
| Causal custody | Reference only | Internally reconstructable reference event order |
| Complete-system EVP | Contract implemented | Modeled vector and refusal of unmatched or incomplete claims |
| FPGA, silicon, and fabrication | Open | No physical execution or manufacturability claim |
| Independent physical acceptance | Open | No physical advantage claim |

## Executed RTL boundary

The qualified standalone RTL transaction includes:

- generated `physical-compute-mmio/v1` SystemVerilog;
- `physical-cartridge-link/v1` between the bridge and cartridge;
- `physical-cartridge-handle-resolver/v1` for opaque-handle interpretation;
- bridge refusal of an ambiguous command;
- cartridge refusal of invalid descriptor content;
- resolver-fault propagation;
- reset, load, evolve, read, capture, and receipt completion;
- byte-identical accepted-trace comparison;
- exact source, manifest, executable, trace, tool, and proof hashes;
- refusal of stale MMIO, altered source, forged manifest, and divergent trace evidence.

This transaction proves an open-source simulator lifecycle for a standalone reference attachment. The separately sealed Chipyard transaction proves pinned subsystem elaboration and one RV64GC lifecycle through generated Verilator RTL with the internal loopback fallback. Neither transaction proves external-cartridge binding, timing closure, FPGA behavior, silicon behavior, physical substrate work, energy recovery, occupied volume, thermal closure, or complete-system advantage.

## Open production risks

### Scientific and physical risks

- No measured nonfallback physical cartridge has entered the substrate receipt.
- No complete-system measurement includes host, memory, conversion, sensing, readout, package, cooling, and accepted work in one interval.
- No external cartridge or physical-target adapter has replaced the declared internal Chipyard loopback fallback.
- FPGA, fabrication, packaging, reliability, and measured-silicon evidence remain absent.

### Integration risks

- External provider offer manifests remain unacknowledged.
- Remote venue contracts have not yet been exercised against an external service.
- Precision clock and instrument adapters have not replaced reference mappings.
- Composite workload lowering remains open.
- The standalone resolver and cartridge have not yet been replaced by a second independently implemented pair under the same accepted trace.

### Governance risks

- Branch-protection settings must be configured in GitHub repository settings because they are not represented by source files.
- Trusted publishing and release environments must be configured before PyPI publication.
- Private vulnerability reporting should be enabled in repository settings.

## Recommended branch protection

Protect `main` with the following rules:

- require a pull request before merging;
- require CI, CodeQL, RTL Attachment Execution, Execution Target Boundary, Chipyard RV64GC Lifecycle, Provider Hitch Surface, RISC-V Target Model, Congruent Shape Pylons, Pylon Fan-out Wave, Scale and Venue Reference Contracts, and Causal Custody Braid;
- require the branch to be current before merge;
- dismiss stale approvals when the head changes;
- block force pushes and deletions;
- require conversation resolution;
- allow repository administrators to bypass only for incident recovery, with a follow-up receipt.

## Release admission

A version tag is admitted only when:

1. The tag equals the package version.
2. CI and specialized evidence workflows are green at the tagged commit.
3. The repository audit passes.
4. Wheel and source distribution pass `twine check`.
5. The wheel installs into a clean environment.
6. `ahead-rev-doctor --strict` passes from the clean wheel.
7. The RTL attachment compiles, executes, matches the accepted trace, and passes source-custody refusal tests.
8. The execution-target workflow preserves accepted reference execution, unbound-target refusal, cleanup custody, and tamper refusal.
9. The pinned Chipyard workflow reconstructs elaboration, RV64GC execution, semantic trace, tool custody, and portable evidence checksums.
10. SHA-256 checksums are generated.
11. The changelog, citation file, and evidence boundary match the release.
12. No physical or provider claim exceeds its receipt.

## Control question

Can an external user install the package, reconstruct the declared software, execution-target, standalone RTL, and pinned Chipyard authority surfaces, rerun the qualified fixtures, identify every remaining blocker, and distinguish executed simulation from unproven external-target, physical, fabrication, and complete-system claims?
