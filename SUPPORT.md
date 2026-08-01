# Support

`ahead-rev-sim` is an open research and engineering project. Support is provided through public GitHub issues for reproducible software defects, documentation problems, compatibility failures, and bounded commodity-intake proposals.

## Before opening an issue

Run:

```bash
ahead-rev-doctor --strict
ahead-rev-sim --version
pytest -q
```

Then search existing issues and include the exact version or commit, operating system, Python version, command, fixture, expected result, observed result, blocker codes, and smallest relevant receipt or trace.

## Supported requests

Public issues are appropriate for:

- deterministic simulator or CLI defects;
- schema and receipt inconsistencies;
- packaging and installation failures;
- Windows or Linux compatibility problems;
- broken documentation or examples;
- public commodity, pylon, testbed, model, or standard intake;
- reproducible divergence among reference implementations.

## Unsupported requests

The project cannot provide private operational support for proprietary devices, employer infrastructure, customer systems, restricted PDKs, confidential data, unsafe laboratory procedures, credential recovery, or unauthorized access. Do not upload those materials to an issue.

The project also does not certify physical safety, electrical safety, export-control status, medical suitability, investment suitability, or complete-system energy advantage.

## Security reports

Potential vulnerabilities that expose credentials, permit arbitrary code execution through an expected-safe input, corrupt accepted evidence, or forge provenance should follow [`SECURITY.md`](SECURITY.md) and should not be disclosed first in a public issue.

## Response expectations

Issue response is best effort. A complete deterministic reproducer receives priority over a broad request. The maintainer may close an issue that lacks the information necessary to reconstruct the transaction, exceeds the project's evidence boundary, or depends on restricted material.
