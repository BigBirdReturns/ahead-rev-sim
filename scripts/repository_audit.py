"""Deterministic source-tree production audit for ahead-rev-sim."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from importlib import import_module
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from ahead_rev_sim._version import __version__
from ahead_rev_sim.doctor import EXPECTED_CONSOLE_SCRIPTS

AUDIT_SCHEMA_VERSION = "ahead.repository-audit/v0.1"

REQUIRED_FILES = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "GOVERNANCE.md",
    "LICENSE",
    "CITATION.cff",
    "pyproject.toml",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    "docs/production_readiness.md",
    "docs/release_process.md",
    "src/ahead_rev_sim/_version.py",
    "src/ahead_rev_sim/py.typed",
)

IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
}

NONEMPTY_SUFFIXES = {
    ".py",
    ".json",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".cff",
}

LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
REPO_REFERENCE = re.compile(r"repo://([^\s\"']+)")
ACTION_MAJOR_TAG = re.compile(r"uses:\s+[^\s]+@v\d+\s*$", re.MULTILINE)


@dataclass(frozen=True)
class AuditCheck:
    check_id: str
    passed: bool
    detail: str


def _read_toml(path: Path) -> Mapping[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _iter_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not (set(path.relative_to(root).parts) & IGNORED_PARTS)
    )


def _check_markdown_links(root: Path, path: Path) -> list[str]:
    missing: list[str] = []
    for raw_target in LOCAL_LINK.findall(path.read_text(encoding="utf-8")):
        target = raw_target.split(" ", 1)[0].strip("<>")
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_path = target.split("#", 1)[0]
        if not target_path:
            continue
        resolved = (path.parent / target_path).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            missing.append(target)
            continue
        if not resolved.exists():
            missing.append(target)
    return missing


def audit_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    checks: list[AuditCheck] = []
    blockers: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED_FILES:
        present = (root / relative).is_file()
        checks.append(AuditCheck(f"required:{relative}", present, relative))
        if not present:
            blockers.append(f"REQUIRED_FILE_MISSING:{relative}")

    pyproject_path = root / "pyproject.toml"
    pyproject = _read_toml(pyproject_path)
    project = pyproject.get("project", {})
    dynamic = project.get("dynamic", []) if isinstance(project, Mapping) else []
    setuptools = pyproject.get("tool", {}).get("setuptools", {})
    version_spec = setuptools.get("dynamic", {}).get("version", {})
    dynamic_version_ok = (
        "version" in dynamic
        and version_spec.get("attr") == "ahead_rev_sim._version.__version__"
        and "version" not in project
    )
    checks.append(
        AuditCheck(
            "single-version-authority",
            dynamic_version_ok,
            "src/ahead_rev_sim/_version.py",
        )
    )
    if not dynamic_version_ok:
        blockers.append("VERSION_AUTHORITY_NOT_SINGLE_SOURCE")

    version_checks = {
        "README.md": f"ahead-rev-sim {__version__}",
        "CHANGELOG.md": f"[{__version__}]",
        "CITATION.cff": f"version: {__version__}",
    }
    for relative, marker in version_checks.items():
        content = (root / relative).read_text(encoding="utf-8")
        passed = marker in content
        checks.append(AuditCheck(f"version:{relative}", passed, marker))
        if not passed:
            blockers.append(f"VERSION_MARKER_MISSING:{relative}")

    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    license_ok = (
        "Jonathan Sandhu and ahead-rev-sim contributors" in license_text
        and "Copyright (c) 2025 Ahead Computing" not in license_text
    )
    checks.append(AuditCheck("license-attribution", license_ok, "MIT attribution"))
    if not license_ok:
        blockers.append("LICENSE_ATTRIBUTION_INVALID")

    scripts = project.get("scripts", {}) if isinstance(project, Mapping) else {}
    script_names = set(scripts) if isinstance(scripts, Mapping) else set()
    expected_scripts = set(EXPECTED_CONSOLE_SCRIPTS)
    scripts_match = script_names == expected_scripts
    checks.append(
        AuditCheck(
            "console-script-declaration",
            scripts_match,
            f"expected={len(expected_scripts)}; declared={len(script_names)}",
        )
    )
    for name in sorted(expected_scripts - script_names):
        blockers.append(f"CONSOLE_SCRIPT_MISSING:{name}")
    for name in sorted(script_names - expected_scripts):
        blockers.append(f"CONSOLE_SCRIPT_UNDECLARED:{name}")

    if isinstance(scripts, Mapping):
        for name, target in sorted(scripts.items()):
            module_name, separator, callable_name = str(target).partition(":")
            valid = bool(separator and module_name and callable_name)
            detail = str(target)
            if valid:
                try:
                    module = import_module(module_name)
                    valid = callable(getattr(module, callable_name, None))
                except Exception as exc:  # pragma: no cover - product failure path
                    valid = False
                    detail = f"{target}: {type(exc).__name__}: {exc}"
            checks.append(AuditCheck(f"entry-point:{name}", valid, detail))
            if not valid:
                blockers.append(f"CONSOLE_ENTRY_POINT_INVALID:{name}")

    files = _iter_files(root)
    forbidden_generated = [
        path.relative_to(root).as_posix()
        for path in files
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}
    ]
    checks.append(
        AuditCheck(
            "no-generated-python-state",
            not forbidden_generated,
            f"count={len(forbidden_generated)}",
        )
    )
    blockers.extend(f"GENERATED_FILE_COMMITTED:{item}" for item in forbidden_generated)

    empty_critical = [
        path.relative_to(root).as_posix()
        for path in files
        if path.suffix in NONEMPTY_SUFFIXES
        and path.name != "py.typed"
        and path.stat().st_size == 0
    ]
    checks.append(
        AuditCheck(
            "no-empty-critical-files",
            not empty_critical,
            f"count={len(empty_critical)}",
        )
    )
    blockers.extend(f"EMPTY_CRITICAL_FILE:{item}" for item in empty_critical)

    invalid_json: list[str] = []
    parsed_json: dict[Path, Any] = {}
    for path in (item for item in files if item.suffix == ".json"):
        try:
            parsed_json[path] = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            invalid_json.append(f"{path.relative_to(root).as_posix()}: {exc}")
    checks.append(
        AuditCheck("json-parse", not invalid_json, f"files={len(parsed_json)}")
    )
    blockers.extend(f"JSON_INVALID:{item}" for item in invalid_json)

    invalid_schemas: list[str] = []
    for path, payload in parsed_json.items():
        if path.name.endswith(".schema.json"):
            try:
                Draft202012Validator.check_schema(payload)
            except Exception as exc:  # pragma: no cover - schema library detail
                invalid_schemas.append(f"{path.relative_to(root).as_posix()}: {exc}")
    checks.append(
        AuditCheck(
            "json-schema-validity",
            not invalid_schemas,
            f"schemas={sum(path.name.endswith('.schema.json') for path in parsed_json)}",
        )
    )
    blockers.extend(f"JSON_SCHEMA_INVALID:{item}" for item in invalid_schemas)

    missing_repo_refs: list[str] = []
    for path, payload in parsed_json.items():
        serialized = json.dumps(payload, sort_keys=True)
        for relative in REPO_REFERENCE.findall(serialized):
            if not (root / relative).is_file():
                missing_repo_refs.append(
                    f"{path.relative_to(root).as_posix()} -> {relative}"
                )
    checks.append(
        AuditCheck(
            "repo-reference-integrity",
            not missing_repo_refs,
            f"missing={len(missing_repo_refs)}",
        )
    )
    blockers.extend(f"REPO_REFERENCE_MISSING:{item}" for item in missing_repo_refs)

    broken_links: list[str] = []
    for path in (item for item in files if item.suffix == ".md"):
        for target in _check_markdown_links(root, path):
            broken_links.append(f"{path.relative_to(root).as_posix()} -> {target}")
    checks.append(
        AuditCheck(
            "local-markdown-links",
            not broken_links,
            f"broken={len(broken_links)}",
        )
    )
    blockers.extend(f"MARKDOWN_LINK_BROKEN:{item}" for item in broken_links)

    workflow_files = sorted((root / ".github" / "workflows").glob("*.yml"))
    workflow_permission_failures: list[str] = []
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        if "permissions:" not in text:
            workflow_permission_failures.append(path.name)
        if ACTION_MAJOR_TAG.search(text):
            warnings.append(f"ACTION_REF_FLOATS_AT_MAJOR_TAG:{path.name}")
        if "timeout-minutes:" not in text:
            warnings.append(f"WORKFLOW_TIMEOUT_NOT_DECLARED:{path.name}")
    checks.append(
        AuditCheck(
            "workflow-permissions",
            not workflow_permission_failures,
            f"workflows={len(workflow_files)}",
        )
    )
    blockers.extend(
        f"WORKFLOW_PERMISSIONS_MISSING:{item}"
        for item in workflow_permission_failures
    )

    report: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "pass" if not blockers else "refused",
        "version": __version__,
        "root": str(root),
        "summary": {
            "check_count": len(checks),
            "passed_count": sum(check.passed for check in checks),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "json_file_count": len(parsed_json),
            "workflow_count": len(workflow_files),
            "console_script_count": len(script_names),
        },
        "checks": [asdict(check) for check in checks],
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
        "claim_boundary": (
            "A passing audit establishes source-tree, package-surface, schema, link, "
            "and governance integrity. It does not establish physical execution, "
            "complete-system EVP advantage, fabrication, or independent acceptance."
        ),
        "control_question": (
            "Can the release be rebuilt from the repository without version drift, "
            "missing authority files, broken local custody, or undeclared commands?"
        ),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repository-audit")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = audit_repository(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(f"status: {report['status']}")
        print(f"version: {report['version']}")
        print(
            f"checks: {summary['passed_count']}/{summary['check_count']} passed; "
            f"blockers={summary['blocker_count']}; warnings={summary['warning_count']}"
        )
        for blocker in report["blockers"]:
            print(f"BLOCKER {blocker}")
        for warning in report["warnings"]:
            print(f"WARNING {warning}")

    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
