from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RTL_WORKFLOW = ROOT / ".github" / "workflows" / "rtl-attachment.yml"
CHIPYARD_WORKFLOW = ROOT / ".github" / "workflows" / "chipyard-lifecycle.yml"


def test_rtl_workflow_is_directly_runnable_and_reusable() -> None:
    workflow = RTL_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "ahead-rev-rtl proof" in workflow
    assert "Prove trace and source-custody refusal" in workflow


def test_chipyard_lifecycle_workflow_is_directly_runnable_and_reusable() -> None:
    workflow = CHIPYARD_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "ahead-rev-chipyard\" lifecycle-proof" in workflow
    assert "Prove lifecycle trace refusal" in workflow


def test_release_waits_for_hardware_model_requalification_before_publication() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "rtl-attachment:" in workflow
    assert "uses: ./.github/workflows/rtl-attachment.yml" in workflow
    assert "chipyard-lifecycle:" in workflow
    assert "uses: ./.github/workflows/chipyard-lifecycle.yml" in workflow
    assert "needs:\n      - rtl-attachment\n      - chipyard-lifecycle" in workflow
    assert "ahead-rev-rtl --version" in workflow
    assert "ahead-rev-chipyard lifecycle-bundle --help" in workflow
    assert "ahead-rev-chipyard lifecycle-proof --help" in workflow
    assert "gh release create" in workflow

    rtl_position = workflow.index("uses: ./.github/workflows/rtl-attachment.yml")
    chipyard_position = workflow.index(
        "uses: ./.github/workflows/chipyard-lifecycle.yml"
    )
    release_position = workflow.index(
        "name: Build, verify, and publish release artifacts"
    )
    publish_position = workflow.index("gh release create")
    assert rtl_position < release_position < publish_position
    assert chipyard_position < release_position < publish_position
