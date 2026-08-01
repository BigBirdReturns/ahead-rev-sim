# Production readiness

Version 0.9.0 separates repository and package production quality from scientific and physical claim closure. The software can be production-hardened while physical execution, fabrication, and complete-system advantage remain unqualified.

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
| Provider hitches | Implemented | Interface compatibility and explicit execution admission or refusal |
| Physical substrate | Reference only | Contract behavior and replay conditions |
| Scale seams | Reference only | Deterministic modeled seam attribution |
| Remote venues | Reference only | Bounded software venue substitution |
| Causal custody | Reference only | Internally reconstructable reference event order |
| Complete-system EVP | Contract implemented | Modeled vector and refusal of unmatched or incomplete claims |
| RTL and fabrication | Open | Source-bound candidate only |
| Independent physical acceptance | Open | No physical advantage claim |

## Open production risks

### Scientific and physical risks

- No measured nonfallback physical cartridge has entered the substrate receipt.
- No complete-system measurement includes host, memory, conversion, sensing, readout, package, cooling, and accepted work in one interval.
- Chipyard Scala generation has not yet been replaced by elaborated and executed RTL.
- Fabrication, packaging, reliability, and measured-silicon evidence remain absent.

### Integration risks

- External provider offer manifests remain unacknowledged.
- Remote venue contracts have not yet been exercised against an external service.
- Precision clock and instrument adapters have not replaced reference mappings.
- Composite workload lowering remains open.

### Governance risks

- Branch-protection settings must be configured in GitHub repository settings because they are not represented by source files.
- Trusted publishing and release environments must be configured before PyPI publication.
- Private vulnerability reporting should be enabled in repository settings.

## Recommended branch protection

Protect `main` with the following rules:

- require a pull request before merging;
- require the CI, CodeQL, Provider Hitch Surface, RV64GC Target Model, Congruent Shape Pylons, Pylon Fan-out Wave, Scale and Venue Reference Contracts, and Causal Custody Braid checks;
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
7. SHA-256 checksums are generated.
8. The changelog, citation file, and evidence boundary match the release.
9. No physical or provider claim exceeds its receipt.

## Control question

Can an external user install the package, reconstruct the declared software authority surface, rerun the qualified fixtures, identify every remaining blocker, and distinguish software production quality from unproven physical advantage?
