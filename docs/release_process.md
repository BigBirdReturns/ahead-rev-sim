# Release process

Releases are evidence transactions. A tag names an immutable source state, and the release workflow must reconstruct the package, validate the authority surface, and publish checksums without changing the tagged commit.

## Prepare the release

1. Update `src/ahead_rev_sim/_version.py`.
2. Update `CHANGELOG.md`, `README.md`, and `CITATION.cff`.
3. Run the production checks:

```bash
python -m pip install -e ".[dev]"
ruff check src tests scripts
mypy
pytest -q
python scripts/repository_audit.py
python -m build
python -m twine check dist/*
python scripts/release_preflight.py --dist dist
```

4. Require the RTL Attachment Execution workflow to compile, execute, compare, seal, validate, and red-team the current MMIO, resolver, cartridge, and accepted trace.
5. Open a release pull request and require the complete check suite.
6. Merge without rewriting independently meaningful evidence history.
7. Create an annotated tag matching the package version, for example `v0.10.0`.
8. Push the tag. The release workflow builds the distributions, runs the clean-wheel doctor, generates `SHA256SUMS`, and creates the GitHub release.

## Trusted publication

PyPI publication is intentionally not enabled by source configuration alone. Configure a GitHub release environment and a PyPI trusted publisher before adding a publish job. The environment should require approval and should permit only version-tag workflows from the canonical repository.

Do not place a long-lived PyPI token in repository secrets when trusted publishing is available.

## Version authority

The only package-version source is:

```text
src/ahead_rev_sim/_version.py
```

`pyproject.toml` reads that attribute dynamically. The primary CLI, installed metadata, citation file, changelog, release tag, wheel filename, and source-distribution filename must agree.

## Reproducibility and checksums

The release workflow derives `SOURCE_DATE_EPOCH` from the tagged commit and records SHA-256 checksums for every distribution. Generated MMIO and RTL attachment artifacts are written as exact UTF-8 LF bytes so their manifests remain identical on Windows and Linux. A checksum proves byte identity only. It does not replace source provenance, workflow logs, the package doctor, or the executed RTL proof.

## Rollback and supersession

Do not move or delete a published version tag. When a release is defective, publish a patch release that records the failure and supersession in the changelog. Preserve the original release and its evidence.

## Claim boundary

A software release may be production-grade while physical execution and complete-system advantage remain open. Release notes must state the strongest qualified evidence tier and the remaining blockers. A version tag cannot promote modeled, provider-offer, standalone RTL, or component evidence into a Chipyard, FPGA, silicon, physical-substrate, fabrication, or measured complete-system claim.
