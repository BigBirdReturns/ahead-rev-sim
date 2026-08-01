# Contributing to ahead-rev-sim

Contributions are evaluated as bounded evidence transactions. A change should identify the workload or system gap it addresses, the authority boundary it preserves, the pylon it strengthens, the failure mode it refuses, and the receipt or test that proves the change.

## Public-material boundary

Only public or independently generated material may enter this repository. Do not contribute:

- employer or client PDKs;
- unreleased libraries, models, device data, or roadmaps;
- customer or partner designs;
- confidential scripts, documents, measurements, or credentials;
- restricted information obtained through private devices, networks, accounts, or work time;
- artifacts whose copyright, patent, export, confidentiality, or access status is unclear.

When public material is incomplete, preserve the gap as structured evidence. Classify it as unknown, restricted, undocumented, experimentally resolvable, ill-posed, or an ownership and discipline gap. Do not silently fill the gap with an assumption.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate            # Linux or macOS
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
ahead-rev-doctor --strict
pytest -q
```

Run the production checks before opening a pull request:

```bash
ruff check src tests scripts
mypy
python scripts/repository_audit.py
python -m build
python -m twine check dist/*
```

## Change classification

Every pull request should state:

1. The object being changed: semantics, lowering, runtime, substrate, interface, provider hitch, scale seam, venue, causal custody, EVP, materialization, or governance.
2. The accepted workload, fixture, or repository invariant affected.
3. The evidence tier: reference, simulated, target-observed, measured, or independently validated.
4. The pylon or system gap strengthened.
5. The authority that remains outside the implementation.
6. The forbidden collapse the change prevents.
7. The refusal and failure fixtures added.
8. The claim boundary after the change.

A provider, device, compiler, service, or facility may not define its own acceptance rule. Service completion, successful compilation, generated RTL, tape-out, or returned data is not accepted work without the corresponding verifier and receipt.

## Tests and fixtures

Tests should be deterministic unless the contract is explicitly distributional. A stochastic test must preserve the seed, entropy trace, or statistical acceptance rule required for replay.

Prefer fixtures that exercise both admission and refusal. At minimum, cover:

- valid execution;
- malformed or incomplete input;
- ambiguous state;
- stale or mismatched identity;
- missing evidence;
- first divergence;
- fallback and substitution behavior;
- claim refusal above the evidence tier actually established.

Do not rewrite a historical fixture to make a new result appear consistent. Add a superseding fixture and preserve the prior artifact.

## Interfaces and compatibility

The stable portability floor is `physical-compute-mmio/v1`. Optional implementation features, including `Xphys`, may improve transport or control performance but cannot alter workload identity, accepted output, fallback, refusal behavior, receipt fields, or evidence authority.

Public Python APIs and console commands follow Semantic Versioning. Breaking changes require a major release or an explicit compatibility period with deprecation tests.

## Documentation

Documentation must distinguish:

- mechanism from complete system;
- model from measurement;
- sensing from computation;
- component energy from complete-system energy;
- execution from acceptance;
- provider offer from provider participation;
- normalized break-even pressure from measured physical advantage.

Direct claims about third parties require public sources and must not imply participation, endorsement, or implementation unless acknowledged evidence is present.

## Pull-request flow

Create a focused branch from `main`, make the smallest coherent change, and open a pull request using the repository template. The branch must pass the full CI matrix, production audit, packaging smoke, and relevant evidence workflows before merge.

The preferred merge method is a merge commit for long-running evidence trains whose internal history matters. Focused maintenance changes may use squash merge when their intermediate history has no independent evidentiary value.
