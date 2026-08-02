from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chipyard-subsystem.yml"


def test_elaboration_sources_chipyard_environment_without_nounset() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    start = workflow.index("      - name: Elaborate the pinned subsystem to FIRRTL")
    end = workflow.index("      - name: Resolve and copy the elaboration products")
    step = workflow[start:end]

    assert "set -Eeo pipefail" in step
    assert "set -Eeuo pipefail" not in step
    assert step.index("source env.sh") < step.index("make -C sims/verilator")
    assert "elaboration.log" in step
    assert "elaboration-diagnostics.txt" in step


def test_failed_elaboration_is_always_uploaded_with_diagnostics() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "      - name: Collect generated products after any outcome" in workflow
    assert "        if: always()" in workflow
    assert "      - name: Upload Chipyard subsystem evidence and diagnostics" in workflow
    assert "          path: artifacts/chipyard-subsystem" in workflow
