from __future__ import annotations

import json

from ahead_rev_sim._version import __version__
from ahead_rev_sim.doctor import (
    EXPECTED_CONSOLE_SCRIPTS,
    REQUIRED_PACKAGE_RESOURCES,
    build_doctor_report,
)
from ahead_rev_sim.doctor_cli import main as doctor_main


def test_doctor_passes_for_editable_install() -> None:
    report = build_doctor_report()
    assert report["status"] == "pass", report["blockers"]
    assert report["package"]["version"] == "0.10.0"
    assert report["package"]["version"] == __version__
    assert report["package"]["installed_metadata_version"] == __version__
    assert set(report["console_scripts"]) == set(EXPECTED_CONSOLE_SCRIPTS)
    assert all(report["package_resources"].values())
    assert set(report["package_resources"]) == set(REQUIRED_PACKAGE_RESOURCES)
    assert set(report["module_imports"].values()) == {"ok"}
    assert report["source_checkout"]["detected"] is True
    assert all(report["source_checkout"]["governance_files"].values())
    assert report["blockers"] == []


def test_doctor_cli_emits_machine_readable_report(capsys) -> None:
    assert doctor_main(["--json", "--strict"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass"
    assert payload["package"]["version"] == __version__
    assert len(payload["checks"]) >= 20
