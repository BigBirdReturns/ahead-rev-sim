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
    assert "LIBGLOSS_COMMIT: 39234a16247ab1fa234821b251f1f1870c3de343" in workflow
    assert "git submodule update --init toolchains/libgloss" in workflow
    assert "Build and verify the pinned HTIF runtime" in workflow
    assert 'SYSROOT="$(riscv64-unknown-elf-gcc -print-sysroot)"' in workflow
    assert "-print-file-name=htif_nano.specs" in workflow
    assert "-print-file-name=libgloss_htif.a" in workflow
    assert 'cp "$RUNTIME_LIBRARY" "$ROOT/libgloss_htif.a"' in workflow
    assert '--runtime-dir "$ROOT"' in workflow
    assert 'make install 2>&1 | tee "$ROOT/libgloss-install.log"' in workflow
    assert (
        "RISCV_ISA_SIM_COMMIT: "
        "9c190a07c6838f6392bafa4ad83acea462c7f759"
    ) in workflow
    assert (
        "git submodule update --init "
        "toolchains/riscv-tools/riscv-isa-sim"
    ) in workflow
    assert "Build and verify the pinned FESVR host runtime" in workflow
    assert "--with-boost=no" in workflow
    assert 'SEALED_FESVR_HEADER="$ROOT/fesvr-memif.h"' in workflow
    assert 'SEALED_FESVR_LIBRARY="$ROOT/libfesvr.a"' in workflow
    assert 'SEALED_RISCV_LIBRARY="$ROOT/libriscv.so"' in workflow
    assert 'cmp "$FESVR_HEADER" "$SEALED_FESVR_HEADER"' in workflow
    assert 'cmp "$FESVR_LIBRARY" "$SEALED_FESVR_LIBRARY"' in workflow
    assert 'cmp "$RISCV_LIBRARY" "$SEALED_RISCV_LIBRARY"' in workflow
    proof_start = workflow.index(
        "      - name: Prove lifecycle trace refusal and seal the lifecycle proof"
    )
    proof_end = workflow.index("      - name: Run the focused repository gates")
    proof_step = workflow[proof_start:proof_end]
    assert "set -Eeo pipefail" in proof_step
    assert "set -Eeuo pipefail" not in proof_step
    assert proof_step.index("source env.sh") < proof_step.index("set -u")
    assert proof_step.index("set -u") < proof_step.index('cd "$GITHUB_WORKSPACE"')
    assert "find . -maxdepth 1 -type f -printf" in workflow
    assert "> kit/root-artifacts.txt" in workflow
    assert "sha256sum --check --strict kit/root-artifacts.sha256" in workflow
    assert "find . -type f" in workflow
    assert "! -path './SHA256SUMS'" in workflow
    assert "! -path './SHA256SUMS.sha256'" in workflow
    assert "xargs -0 --no-run-if-empty sha256sum > SHA256SUMS" in workflow
    assert "checksum ledger unexpectedly includes itself" in workflow
    assert "sha256sum --check --strict SHA256SUMS" in workflow
    assert "sha256sum SHA256SUMS > SHA256SUMS.sha256" in workflow
    assert "sha256sum --check --strict SHA256SUMS.sha256" in workflow
    assert '| sort > "$ROOT/SHA256SUMS"' not in workflow
    assert "CIRCT_RELEASE: firtool-1.75.0" in workflow
    assert "CIRCT_COMMIT: 481cb60add7358934414a3c6b396f5d29ad934fe" in workflow
    assert "CIRCT_ASSET_NAME: circt-full-static-linux-x64.tar.gz" in workflow
    assert (
        "CIRCT_INSTALLER_COMMIT: "
        "3f8dda6e1c1965537b5801a43c81c287bac4eae4"
    ) in workflow
    assert "--skip-circt" not in workflow
    assert "Verify the pinned CIRCT lowering authority" in workflow
    assert 'FIRTOOL="$(command -v firtool)"' in workflow
    assert 'TAG_REPO="$GITHUB_WORKSPACE/chipyard/.circt-tag"' in workflow
    assert 'test "$CIRCT_TAG_COMMIT" = "$CIRCT_COMMIT"' in workflow
    assert 'SEALED_FIRTOOL="$ROOT/firtool"' in workflow
    assert 'cmp "$FIRTOOL" "$SEALED_FIRTOOL"' in workflow
    assert 'firtool --version 2>&1 | tee "$ROOT/firtool-version.txt"' in workflow
    assert '--firtool "$ROOT/firtool"' in workflow
    assert '--firtool-version-file "$ROOT/firtool-version.txt"' in workflow


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
