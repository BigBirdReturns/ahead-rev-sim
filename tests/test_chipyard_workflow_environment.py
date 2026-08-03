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


LIFECYCLE_WORKFLOW = ROOT / ".github" / "workflows" / "chipyard-lifecycle.yml"
PINNED_LEAN_LOCKFILE = (
    "conda-reqs/conda-lock-reqs/"
    "conda-requirements-riscv-tools-linux-64-lean.conda-lock.yml"
)
PINNED_LEAN_LOCKFILE_BLOB = "5efb7750bcd6df90db0b69a11308a4f17c74e571"


def test_chipyard_workflows_install_the_checked_in_lean_lockfile() -> None:
    for path in (WORKFLOW, LIFECYCLE_WORKFLOW):
        workflow = path.read_text(encoding="utf-8")
        start = workflow.index("      - name: Install the lean pinned Chipyard environment")
        if path == WORKFLOW:
            end = workflow.index(
                "      - name: Initialize the minimally required pinned submodules",
                start,
            )
        else:
            end = workflow.index(
                "      - name: Verify the pinned CIRCT lowering authority",
                start,
            )
        step = workflow[start:end]

        assert PINNED_LEAN_LOCKFILE in step
        assert PINNED_LEAN_LOCKFILE_BLOB in step
        assert "conda-lock install" in step
        assert "conda-lock=2.5.7" in step
        assert "generate-conda-lockfiles.sh" not in step
        assert "--skip-conda" in step
        assert "conda-lock-authority.txt" in step
        assert "conda-lock-install.log" in step
        assert "conda-explicit.txt" in step
        assert "git diff --exit-code" in step
        assert "source env.sh" in step


def test_only_subsystem_setup_skips_circt_installation() -> None:
    subsystem = WORKFLOW.read_text(encoding="utf-8")
    lifecycle = LIFECYCLE_WORKFLOW.read_text(encoding="utf-8")
    subsystem_step = subsystem[
        subsystem.index("      - name: Install the lean pinned Chipyard environment") :
        subsystem.index("      - name: Initialize the minimally required pinned submodules")
    ]
    lifecycle_step = lifecycle[
        lifecycle.index("      - name: Install the lean pinned Chipyard environment") :
        lifecycle.index("      - name: Verify the pinned CIRCT lowering authority")
    ]

    assert "--skip-circt" in subsystem_step
    assert "--skip-circt" not in lifecycle_step
