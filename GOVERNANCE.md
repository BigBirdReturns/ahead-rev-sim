# Governance

`ahead-rev-sim` is maintained by Jonathan Sandhu under the `BigBirdReturns` GitHub account. The project is open source under the MIT License and accepts external contributions through reviewed pull requests.

## Architectural authority

The repository retains authority over:

- workload and fixture identity;
- accepted-output contracts;
- reference fallbacks;
- admission, refusal, fault, and supersession semantics;
- evidence tiers and claim boundaries;
- receipt schemas and deterministic seals;
- release, publication, and historical custody.

A company, project, device, compiler, foundry, testbed, facility, or research programme may contribute a replaceable implementation or evidence source. It does not receive architectural authority by appearing in the registry, a provider offer, a pylon witness set, or a compatibility fixture.

## Decision process

Changes are accepted when they improve the repository's ability to reconstruct, compare, refuse, substitute, or independently validate an execution transaction. Decisions are grounded in code, fixtures, schemas, measurements, and explicit control questions.

The maintainer may reject a change that:

- transfers acceptance authority to a provider;
- obscures a denominator, boundary, fallback, or failure mode;
- promotes modeled evidence into a measured claim;
- removes historical evidence rather than superseding it;
- introduces restricted or ambiguously licensed material;
- creates an implementation dependency without a substitution route;
- weakens deterministic replay or provenance.

## Pylon admission

New architectural surfaces should identify the congruent-shape pylon they strengthen. A feature is not complete merely because its local mechanism works. The change should state the authority location, forbidden collapse, open invariant, bounded proof transaction, and receipt that demonstrates progress.

New ecosystem records must project onto the existing pylon and system-gap taxonomy before entering an execution lane. Retiring a record or programme requires substitute coverage for the pylons and gaps it served.

## Releases

The Python package follows Semantic Versioning.

- Patch releases repair behavior without changing the declared contract.
- Minor releases add compatible commands, schemas, fixtures, or evidence surfaces.
- Major releases may change stable public APIs, receipt semantics, or portability contracts.

A release requires a clean tagged commit, green CI, a passing repository audit, a wheel and source distribution that pass `twine check`, a clean-wheel doctor pass, SHA-256 checksums, updated changelog and citation metadata, and an explicit evidence boundary.

Long-running development trains may be merged with a merge commit to preserve independently meaningful history. Small maintenance changes may be squashed.

## Claim governance

The strongest allowable claim is determined by the weakest unresolved layer in the transaction. Successful software execution cannot establish physical execution. Physical component measurement cannot establish complete-system advantage. Complete-system measurement cannot establish independent acceptance without reconstructable external review.

Third-party names in offer manifests or supplier-chain fields indicate reserved or observed roles only. Participation, endorsement, implementation, or acceptance must be supported by acknowledged artifacts.

## Succession

Project history, release artifacts, schemas, fixtures, and public evidence should remain reconstructable if a maintainer, provider, facility, tool, or programme becomes unavailable. Supersession adds a new record and preserves the old one. It does not rewrite the original transaction.
