# Security policy

## Supported versions

Security fixes are applied to the current `0.9.x` release line and to `main`. Earlier research releases may receive a backport only when the issue affects artifact integrity, unsafe execution, credential exposure, or a widely used compatibility surface.

| Version | Supported |
| --- | --- |
| `0.9.x` | Yes |
| `0.8.x` and earlier | Best effort |

## Reporting a vulnerability

Use GitHub private vulnerability reporting from the repository Security tab when available. When that channel is unavailable, send a concise report to `jonathan@nodalflow.ai` with the subject `ahead-rev-sim security report`.

Include:

- the affected version, commit, command, or workflow;
- the attacker capability and trust boundary;
- a minimal deterministic reproducer;
- expected and observed behavior;
- whether secrets, repository contents, generated artifacts, measurements, or execution authority are affected;
- any suggested mitigation.

Do not open a public issue for an unpatched vulnerability that exposes credentials, permits arbitrary code execution through an expected-safe input, corrupts accepted evidence, bypasses refusal behavior, or forges provenance.

## Response process

The maintainer will acknowledge a complete report, reproduce it in an isolated fixture, classify the affected authority boundary, and preserve the original failure as evidence. Remediation will include a regression fixture and a claim-boundary review. Publication timing will be coordinated with the reporter when practical.

## Security boundaries

The repository processes assembly, JSON, schemas, generated source, workflow artifacts, and externally supplied provider or venue manifests. Treat all such inputs as untrusted unless pinned and validated.

The current software evidence does not provide a hardware root of trust, confidential-computing boundary, side-channel resistance, safe high-voltage control, laboratory safety certification, export-control determination, or physical-device isolation. Provider hitches and security-component records do not imply that an external actor has reviewed or accepted this security policy.

## Supply-chain policy

Production releases are built from tagged commits through GitHub Actions, checked as wheels and source distributions, accompanied by SHA-256 checksums, and required to pass the repository audit. Dependency and GitHub Actions updates are reviewed through Dependabot rather than silently floated.
