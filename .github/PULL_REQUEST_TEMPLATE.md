## Classification

Describe the object being changed: semantics, lowering, runtime, substrate, interface, provider hitch, scale seam, venue, causal custody, EVP, materialization, governance, or release engineering.

## Accepted work and identity

State the workload, fixture, source, schema, or repository invariant affected. Include pinned identities where applicable.

## Pylon and authority boundary

- Pylon or system gap:
- Authority retained outside the implementation:
- Forbidden collapse prevented:
- Substitution or fallback path:

## Evidence tier

- [ ] Reference model
- [ ] Simulated
- [ ] Target-observed
- [ ] Measured
- [ ] Independently validated

Explain why the selected tier is justified.

## Mechanism

Explain the causal mechanism and the actors involved. Distinguish execution from acceptance and component behavior from complete-system behavior.

## Receipts and tests

List the schemas, artifacts, deterministic fixtures, admission tests, refusal tests, first-divergence evidence, and replay material added or updated.

## Claim boundary

State the strongest claim established by this change and the claims that remain blocked.

## Public-material declaration

- [ ] The change contains only public or independently generated material.
- [ ] It contains no employer or client PDKs, unreleased libraries, customer designs, internal roadmaps, restricted documents, private device data, credentials, or unauthorized work product.
- [ ] Third-party names do not imply participation or endorsement without acknowledged evidence.

## Production checklist

- [ ] `ruff check src tests scripts`
- [ ] `mypy`
- [ ] `pytest -q`
- [ ] `python scripts/repository_audit.py`
- [ ] `python -m build`
- [ ] `python -m twine check dist/*`
- [ ] Documentation, changelog, citation metadata, and version authority are current when release-facing.
