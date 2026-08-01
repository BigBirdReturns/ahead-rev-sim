"""Installed-package and source-checkout production preflight."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module, metadata, resources
import platform
import sys
from pathlib import Path
from typing import Any

from ._version import __version__

DOCTOR_SCHEMA_VERSION = "ahead.doctor-report/v0.1"

EXPECTED_CONSOLE_SCRIPTS = (
    "ahead-rev-sim",
    "ahead-rev-debug",
    "ahead-rev-history",
    "ahead-rev-memory",
    "ahead-rev-frontier",
    "ahead-rev-prove",
    "ahead-rev-substrate",
    "ahead-rev-fambs",
    "ahead-rev-svk",
    "ahead-rev-pck",
    "ahead-rev-commodities",
    "ahead-rev-fanout",
    "ahead-rev-pylons",
    "ahead-rev-wave",
    "ahead-rev-scale-seam",
    "ahead-rev-venue",
    "ahead-rev-causal",
    "ahead-rev-mmio",
    "ahead-rev-rtl",
    "ahead-rev-chipyard",
    "ahead-rev-riscv-target-proof",
    "ahead-rev-hitch",
    "ahead-rev-consist-proof",
    "ahead-rev-evp",
    "ahead-rev-doctor",
)

REQUIRED_PACKAGE_RESOURCES = (
    "data/commodity_ecosystem_registry.json",
    "data/commodity_completion_program.json",
    "data/congruent_shape_pylons.json",
    "data/congruent_shape_surface_projection.json",
    "data/pylon_fanout_wave_2026_08.json",
    "data/pylon_surface_advances_2026_08.json",
)

REQUIRED_IMPORTS = (
    "ahead_rev_sim.frontier",
    "ahead_rev_sim.frontier_exec",
    "ahead_rev_sim.physical_substrate",
    "ahead_rev_sim.provider_hitch",
    "ahead_rev_sim.evp",
    "ahead_rev_sim.scale_seam",
    "ahead_rev_sim.remote_venue",
    "ahead_rev_sim.causal_custody",
    "ahead_rev_sim.congruent_shapes",
    "ahead_rev_sim.debugger_cli",
    "ahead_rev_sim.history_cli",
    "ahead_rev_sim.memory_cli",
    "ahead_rev_sim.rtl_attachment",
    "ahead_rev_sim.rtl_attachment_cli",
)

SOURCE_GOVERNANCE_FILES = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "SECURITY.md",
    "GOVERNANCE.md",
    "LICENSE",
    "CITATION.cff",
    "MANIFEST.in",
    "docs/production_readiness.md",
    "docs/release_process.md",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
)


@dataclass(frozen=True)
class Check:
    check_id: str
    passed: bool
    detail: str


def _console_scripts() -> dict[str, str]:
    discovered = metadata.entry_points()
    selected = (
        discovered.select(group="console_scripts")
        if hasattr(discovered, "select")
        else discovered.get("console_scripts", ())
    )
    return {
        item.name: item.value
        for item in selected
        if item.name.startswith("ahead-rev-")
    }


def _source_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[2]
    return candidate if (candidate / "pyproject.toml").is_file() else None


def build_doctor_report() -> dict[str, Any]:
    checks: list[Check] = []
    blockers: list[str] = []

    supported_python = sys.version_info >= (3, 10)
    checks.append(
        Check(
            "python-supported",
            supported_python,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )
    if not supported_python:
        blockers.append("PYTHON_VERSION_UNSUPPORTED")

    try:
        installed_version = metadata.version("ahead-rev-sim")
    except metadata.PackageNotFoundError:
        installed_version = None
    version_matches = installed_version == __version__
    checks.append(
        Check(
            "metadata-version-matches-package",
            version_matches,
            f"package={__version__}; metadata={installed_version or 'missing'}",
        )
    )
    if not version_matches:
        blockers.append("PACKAGE_METADATA_VERSION_MISMATCH")

    package_root = resources.files("ahead_rev_sim")
    resource_status: dict[str, bool] = {}
    for relative in REQUIRED_PACKAGE_RESOURCES:
        present = package_root.joinpath(relative).is_file()
        resource_status[relative] = present
        checks.append(Check(f"resource:{relative}", present, relative))
        if not present:
            blockers.append(f"PACKAGE_RESOURCE_MISSING:{relative}")

    scripts = _console_scripts()
    missing_scripts = sorted(set(EXPECTED_CONSOLE_SCRIPTS) - set(scripts))
    unexpected_scripts = sorted(set(scripts) - set(EXPECTED_CONSOLE_SCRIPTS))
    scripts_match = not missing_scripts and not unexpected_scripts
    checks.append(
        Check(
            "console-script-surface",
            scripts_match,
            f"expected={len(EXPECTED_CONSOLE_SCRIPTS)}; installed={len(scripts)}",
        )
    )
    if missing_scripts:
        blockers.extend(f"CONSOLE_SCRIPT_MISSING:{item}" for item in missing_scripts)
    if unexpected_scripts:
        blockers.extend(f"CONSOLE_SCRIPT_UNDECLARED:{item}" for item in unexpected_scripts)

    import_status: dict[str, str] = {}
    for module_name in REQUIRED_IMPORTS:
        try:
            import_module(module_name)
        except Exception as exc:  # pragma: no cover - failure path is the product
            import_status[module_name] = f"{type(exc).__name__}: {exc}"
            checks.append(Check(f"import:{module_name}", False, import_status[module_name]))
            blockers.append(f"MODULE_IMPORT_FAILED:{module_name}")
        else:
            import_status[module_name] = "ok"
            checks.append(Check(f"import:{module_name}", True, "ok"))

    source_root = _source_root()
    source_files: dict[str, bool] | None = None
    if source_root is not None:
        source_files = {
            relative: (source_root / relative).is_file()
            for relative in SOURCE_GOVERNANCE_FILES
        }
        for relative, present in source_files.items():
            checks.append(Check(f"source:{relative}", present, relative))
            if not present:
                blockers.append(f"SOURCE_GOVERNANCE_FILE_MISSING:{relative}")

    report: dict[str, Any] = {
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "status": "pass" if not blockers else "refused",
        "package": {
            "name": "ahead-rev-sim",
            "version": __version__,
            "installed_metadata_version": installed_version,
        },
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "checks": [asdict(check) for check in checks],
        "package_resources": resource_status,
        "console_scripts": dict(sorted(scripts.items())),
        "missing_console_scripts": missing_scripts,
        "unexpected_console_scripts": unexpected_scripts,
        "module_imports": import_status,
        "source_checkout": {
            "detected": source_root is not None,
            "root": str(source_root) if source_root is not None else None,
            "governance_files": source_files,
        },
        "blockers": blockers,
        "claim_boundary": (
            "A passing doctor report proves packaging, import, entry-point, resource, "
            "and source-governance integrity. It does not prove physical execution, "
            "measured EVP advantage, fabrication, or independent physical acceptance."
        ),
        "control_question": (
            "Can the installed package and source checkout reconstruct the declared "
            "software authority surface without relying on undeclared files or commands?"
        ),
    }
    return report
