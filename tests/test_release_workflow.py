from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RTL_WORKFLOW = ROOT / ".github" / "workflows" / "rtl-attachment.yml"


def test_rtl_workflow_is_directly_runnable_and_reusable() -> None:
    workflow = RTL_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "ahead-rev-rtl proof" in workflow
    assert "Prove trace and source-custody refusal" in workflow


def test_release_waits_for_rtl_requalification_before_publication() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "rtl-attachment:" in workflow
    assert "uses: ./.github/workflows/rtl-attachment.yml" in workflow
    assert "needs:\n      - rtl-attachment" in workflow
    assert "ahead-rev-rtl --version" in workflow
    assert "ahead-rev-rtl --help" in workflow
    assert "gh release create" in workflow

    rtl_position = workflow.index("uses: ./.github/workflows/rtl-attachment.yml")
    release_position = workflow.index("name: Build, verify, and publish release artifacts")
    publish_position = workflow.index("gh release create")
    assert rtl_position < release_position < publish_position
