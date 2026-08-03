from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PARENT = "674644dc0d79660cbe18cc66f0f611ed2b7f27a6"
BRANCH = "agent/v0.12-chipyard-rv64gc-lifecycle"


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


head_parent = subprocess.check_output(
    ["git", "rev-parse", "HEAD^"], cwd=ROOT, text=True
).strip()
if head_parent != EXPECTED_PARENT:
    raise SystemExit(
        f"controller parent moved: expected {EXPECTED_PARENT}, observed {head_parent}"
    )
branch = subprocess.check_output(
    ["git", "branch", "--show-current"], cwd=ROOT, text=True
).strip()
if branch != BRANCH:
    raise SystemExit(f"unexpected branch: {branch}")

pylon_stage = ROOT / ".staging/pr11-pylon-wave.yml"
pylon_active = ROOT / ".github/workflows/pylon-wave.yml"
if not pylon_stage.is_file():
    raise SystemExit("preserved pylon workflow is missing")
pylon_active.write_bytes(pylon_stage.read_bytes())

workflow_path = ROOT / ".github/workflows/chipyard-lifecycle.yml"
release_test_path = ROOT / "tests/test_release_workflow.py"
lifecycle_test_path = ROOT / "tests/test_chipyard_lifecycle.py"
document_path = ROOT / "docs/chipyard_rv64gc_lifecycle.md"

workflow = workflow_path.read_text(encoding="utf-8")
old_activation = '''          set -Eeuo pipefail
          cd chipyard
          source env.sh
          cd "$GITHUB_WORKSPACE"
          ROOT="artifacts/chipyard-lifecycle"
'''
new_activation = '''          set -Eeo pipefail
          cd chipyard
          source env.sh
          set -u
          cd "$GITHUB_WORKSPACE"
          ROOT="artifacts/chipyard-lifecycle"
'''
if workflow.count(old_activation) != 1:
    raise SystemExit("proof activation boundary changed unexpectedly")
workflow = workflow.replace(old_activation, new_activation)

old_kit = '''          find "$ROOT" -maxdepth 1 -type f -print | sort \\
            > "$ROOT/kit/root-artifacts.txt"
          while IFS= read -r file; do sha256sum "$file"; done \\
            < "$ROOT/kit/root-artifacts.txt" \\
            > "$ROOT/kit/root-artifacts.sha256"
'''
new_kit = '''          (
            cd "$ROOT"
            find . -maxdepth 1 -type f -printf '%f\\n' | sort \\
              > kit/root-artifacts.txt
            while IFS= read -r file; do sha256sum "$file"; done \\
              < kit/root-artifacts.txt \\
              > kit/root-artifacts.sha256
            sha256sum --check --strict kit/root-artifacts.sha256
          )
'''
if workflow.count(old_kit) != 1:
    raise SystemExit("kit checksum boundary changed unexpectedly")
workflow = workflow.replace(old_kit, new_kit)

old_outer = '''          find "$ROOT" -maxdepth 1 -type f \\
            ! -name SHA256SUMS \\
            ! -name SHA256SUMS.sha256 \\
            -exec sha256sum {} \\; \\
            | sort > "$ROOT/SHA256SUMS"
          sha256sum "$ROOT/SHA256SUMS" > "$ROOT/SHA256SUMS.sha256"
          sha256sum -c "$ROOT/SHA256SUMS"
          sha256sum -c "$ROOT/SHA256SUMS.sha256"
'''
new_outer = '''          (
            cd "$ROOT"
            rm -f SHA256SUMS SHA256SUMS.sha256
            find . -type f \\
              ! -path './SHA256SUMS' \\
              ! -path './SHA256SUMS.sha256' \\
              -print0 \\
              | sort -z \\
              | xargs -0 --no-run-if-empty sha256sum > SHA256SUMS
            test -s SHA256SUMS
            if grep -Fq '  ./SHA256SUMS' SHA256SUMS; then
              echo "checksum ledger unexpectedly includes itself" >&2
              exit 1
            fi
            sha256sum --check --strict SHA256SUMS
            sha256sum SHA256SUMS > SHA256SUMS.sha256
            sha256sum --check --strict SHA256SUMS.sha256
          )
'''
if workflow.count(old_outer) != 1:
    raise SystemExit("outer checksum boundary changed unexpectedly")
workflow = workflow.replace(old_outer, new_outer)
workflow_path.write_text(workflow, encoding="utf-8")

old_assertions = '''    assert "! -name SHA256SUMS" in workflow
    assert 'sha256sum "$ROOT/SHA256SUMS" > "$ROOT/SHA256SUMS.sha256"' in workflow
    assert 'sha256sum -c "$ROOT/SHA256SUMS"' in workflow
    assert 'sha256sum -c "$ROOT/SHA256SUMS.sha256"' in workflow
'''
new_assertions = '''    proof_start = workflow.index(
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
'''
for path in (release_test_path, lifecycle_test_path):
    text = path.read_text(encoding="utf-8")
    if text.count(old_assertions) != 1:
        raise SystemExit(f"checksum assertions changed unexpectedly: {path}")
    path.write_text(text.replace(old_assertions, new_assertions), encoding="utf-8")

document = document_path.read_text(encoding="utf-8")
old_paragraph = (
    "The final evidence collector writes `SHA256SUMS` over every root "
    "evidence file except the checksum manifests themselves, verifies "
    "every entry immediately, writes `SHA256SUMS.sha256` as the external "
    "seal for that manifest, and verifies the manifest seal. This avoids "
    "the invalid recursive pattern in which a checksum file records the "
    "hash of its own empty pre-redirection state. The earlier reconstructable "
    "kit manifest remains an independently verified inventory of the files "
    "present when the proof and kit were assembled."
)
new_paragraph = (
    "The final evidence collector writes an extraction-relative `SHA256SUMS` "
    "over the complete uploaded evidence tree, including the reconstruction "
    "kit and generated-source archive, while excluding only the two checksum "
    "manifests. It verifies every entry before upload, writes "
    "`SHA256SUMS.sha256` as the external seal for that manifest, and verifies "
    "the manifest seal. The reconstruction-kit ledger is also extraction-relative "
    "and is verified at assembly time. This avoids self-inclusion and removes "
    "GitHub Actions workspace paths from the portable receipt."
)
if document.count(old_paragraph) != 1:
    raise SystemExit("evidence collector documentation changed unexpectedly")
document = document.replace(old_paragraph, new_paragraph)
marker = "\n## Evidence boundary\n"
section = '''
## Downloaded artifact verification

After downloading and extracting the GitHub Actions artifact, enter the extracted artifact root and run:

```bash
sha256sum --check --strict kit/root-artifacts.sha256
sha256sum --check --strict SHA256SUMS
sha256sum --check --strict SHA256SUMS.sha256
```

The kit ledger covers the core lifecycle evidence present when the reconstruction kit is assembled. The outer ledger recursively covers every uploaded file except the two checksum manifests and uses paths relative to the extracted artifact root. The final command verifies the external seal over the outer ledger.
'''
if marker not in document:
    raise SystemExit("evidence boundary heading missing")
if "## Downloaded artifact verification" in document:
    raise SystemExit("download verification section already exists")
document_path.write_text(document.replace(marker, section + marker, 1), encoding="utf-8")

run(
    "git",
    "rm",
    ".staging/pr11-pylon-wave.yml",
    ".staging/pr11-finalize.py",
    ".github/workflows/pr11-finalize.yml",
    "connector-probe-2.txt",
    "connector-probe-4.txt",
    "connector-probe-push-files-2.txt",
    "connector-probe-push-files.txt",
    "connector-probe-utf8.txt",
)
run("python", "-m", "compileall", "-q", "src", "tests", "scripts")
run("ruff", "check", "src", "tests", "scripts")
run("mypy")
run("python", "scripts/repository_audit.py")
run("pytest", "-q")
run("git", "diff", "--check")
run("git", "config", "user.name", "BigBirdReturns Evidence Finalizer")
run(
    "git",
    "config",
    "user.email",
    "219768509+BigBirdReturns@users.noreply.github.com",
)
run(
    "git",
    "add",
    ".github/workflows/pylon-wave.yml",
    ".github/workflows/chipyard-lifecycle.yml",
    "docs/chipyard_rv64gc_lifecycle.md",
    "tests/test_chipyard_lifecycle.py",
    "tests/test_release_workflow.py",
)
run("git", "commit", "-m", "Close PR 11 proof and artifact custody")
run("git", "push", "origin", f"HEAD:{BRANCH}")
print(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
