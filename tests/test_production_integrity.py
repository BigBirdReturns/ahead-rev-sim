from __future__ import annotations

from pathlib import Path

from ahead_rev_sim._version import __version__
from ahead_rev_sim.release_preflight import build_release_manifest
from ahead_rev_sim.repository_audit import audit_repository


ROOT = Path(__file__).resolve().parents[1]


def test_repository_audit_passes_and_is_deterministic() -> None:
    first = audit_repository(ROOT)
    second = audit_repository(ROOT)
    assert first == second
    assert first["status"] == "pass", first["blockers"]
    assert first["version"] == __version__ == "0.9.0"
    assert first["blockers"] == []
    assert first["summary"]["console_script_count"] == 25
    assert first["summary"]["json_file_count"] >= 42
    assert first["summary"]["workflow_count"] >= 8


def test_release_preflight_refuses_missing_distributions(tmp_path: Path) -> None:
    manifest = build_release_manifest(
        root=ROOT,
        dist=tmp_path,
        tag=f"v{__version__}",
    )
    assert manifest["status"] == "refused"
    assert "WHEEL_COUNT_INVALID:0" in manifest["blockers"]
    assert "SDIST_COUNT_INVALID:0" in manifest["blockers"]
    assert manifest["repository_audit_status"] == "pass"
    assert len(manifest["manifest_sha256"]) == 64


def test_release_preflight_refuses_tag_drift(tmp_path: Path) -> None:
    manifest = build_release_manifest(
        root=ROOT,
        dist=tmp_path,
        tag="v9.9.9",
    )
    assert any(
        blocker.startswith("TAG_VERSION_MISMATCH")
        for blocker in manifest["blockers"]
    )
