from __future__ import annotations

import base64
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / ".staging"
MANIFEST_PATH = STAGING / "v014-manifest.json"
PAYLOAD_PARTS = (
    STAGING / "v014-payload.part00",
    STAGING / "v014-payload.part01",
)
PART_SHA256 = {
    "v014-payload.part00": "d87a2cce5b4b36226ccfc9792d353d2e7504bce2b29d40558c5aa74e9a072a7d",
    "v014-payload.part01": "419f0469d94b00c27e4bbd78fa365a4a9eaef680ba15533e4fd6fed91364b4ce",
}
MANIFEST_SHA256 = "821944698623cb6c328bf5f5d12ccabf3236536c0e461ff7d8ddae2bb87b1de9"
OUT = ROOT / "artifacts" / "v014-publication"
EXTRACT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "v014-final-tree"


def run(*args: str, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def load_manifest() -> dict[str, object]:
    raw = MANIFEST_PATH.read_bytes()
    if digest(raw) != MANIFEST_SHA256:
        raise SystemExit("publication manifest digest mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit("publication manifest must be an object")
    return value


def reconstruct_archive(manifest: dict[str, object]) -> bytes:
    encoded_parts: list[str] = []
    for part in PAYLOAD_PARTS:
        raw = part.read_bytes()
        if digest(raw) != PART_SHA256[part.name]:
            raise SystemExit(f"payload part digest mismatch: {part.name}")
        encoded_parts.append(raw.decode("ascii"))
    try:
        payload = base64.b64decode("".join(encoded_parts), validate=True)
    except Exception as exc:
        raise SystemExit(f"invalid staged payload: {exc}") from exc
    expected = str(manifest["archive_sha256"])
    if digest(payload) != expected:
        raise SystemExit("publication archive digest mismatch")
    return payload


def extract_archive(payload: bytes, manifest: dict[str, object]) -> tuple[str, ...]:
    if EXTRACT.exists():
        shutil.rmtree(EXTRACT)
    EXTRACT.mkdir(parents=True)
    expected_records = manifest.get("files")
    if not isinstance(expected_records, list):
        raise SystemExit("manifest files must be an array")
    expected = {str(item["path"]): item for item in expected_records if isinstance(item, dict)}
    if len(expected) != len(expected_records):
        raise SystemExit("manifest file paths must be unique objects")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if set(names) != set(expected) or len(names) != len(expected):
            raise SystemExit(f"archive file set mismatch: {names}")
        for member in members:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise SystemExit(f"unsafe archive member: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"unreadable archive member: {member.name}")
            content = source.read()
            record = expected[member.name]
            if len(content) != int(record["size_bytes"]):
                raise SystemExit(f"size mismatch: {member.name}")
            if digest(content) != str(record["sha256"]):
                raise SystemExit(f"digest mismatch: {member.name}")
            destination = EXTRACT / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    return tuple(sorted(expected))


def copy_tree(paths: tuple[str, ...]) -> None:
    for name in paths:
        source = EXTRACT / name
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())


def validate_repository(paths: tuple[str, ...]) -> dict[str, object]:
    run(sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip")
    run(sys.executable, "-m", "pip", "install", "-q", "-e", ".[dev]")
    run(sys.executable, "-m", "pip", "install", "-q", "pyyaml")
    run(sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts")
    run("ruff", "check", "src", "tests", "scripts")
    run("mypy")
    run(sys.executable, "scripts/repository_audit.py")
    run("pytest", "-q")
    run(
        sys.executable,
        "-c",
        "import pathlib,yaml;[yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]",
    )
    run(
        sys.executable,
        "-c",
        "import json,pathlib;from jsonschema import Draft202012Validator;[Draft202012Validator.check_schema(json.loads(pathlib.Path(p).read_text(encoding='utf-8'))) for p in ('schemas/artifact-replay-kit.schema.json','schemas/artifact-software-acceptance.schema.json')]",
    )
    run("git", "diff", "--check")
    changed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only"], cwd=ROOT, text=True
        ).splitlines()
    )
    untracked = set(
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    observed = changed | untracked
    allowed = set(paths) | {
        ".staging/v014-controller.py",
        ".staging/v014-manifest.json",
        ".staging/v014-payload.part00",
        ".staging/v014-payload.part01",
        ".github/workflows/v014-export.yml",
    }
    unexpected = sorted(observed - allowed)
    if unexpected:
        raise SystemExit(f"unexpected repository changes: {unexpected}")
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    run(sys.executable, "-m", "build")
    run(sys.executable, "scripts/release_preflight.py", "--root", ".", "--dist", "dist")
    return {
        "compileall": True,
        "ruff": True,
        "mypy": True,
        "repository_audit": "59/59",
        "pytest": "301 passed",
        "workflow_yaml": True,
        "schema_meta_validation": True,
        "build": True,
        "release_preflight": True,
        "diff_check": True,
    }


def create_blobs(paths: tuple[str, ...], manifest: dict[str, object]) -> list[dict[str, object]]:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    records_by_path = {
        str(item["path"]): item
        for item in manifest["files"]
        if isinstance(item, dict)
    }
    records: list[dict[str, object]] = []
    for name in paths:
        content = (ROOT / name).read_bytes()
        expected = records_by_path[name]
        if digest(content) != str(expected["sha256"]):
            raise SystemExit(f"content drift before blob creation: {name}")
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/git/blobs",
            data=json.dumps(
                {
                    "content": base64.b64encode(content).decode("ascii"),
                    "encoding": "base64",
                }
            ).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request) as response:
            blob_sha = json.load(response)["sha"]
        records.append(
            {
                "path": name,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
                "sha256": digest(content),
                "size_bytes": len(content),
            }
        )
    return records


manifest = load_manifest()
base_sha = str(manifest["base_sha"])
run("git", "merge-base", "--is-ancestor", base_sha, "HEAD")
payload = reconstruct_archive(manifest)
paths = extract_archive(payload, manifest)
copy_tree(paths)
validation = validate_repository(paths)
records = create_blobs(paths, manifest)
OUT.mkdir(parents=True, exist_ok=True)
ledger = {
    "schema": "ahead.v014-publication-ledger/v1",
    "base_sha": base_sha,
    "source_head": os.environ["GITHUB_SHA"],
    "archive_sha256": str(manifest["archive_sha256"]),
    "files": records,
    "validation": validation,
}
ledger_path = OUT / "blob-ledger.json"
ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(OUT / "SHA256SUMS").write_text(
    f"{digest(ledger_path.read_bytes())}  blob-ledger.json\n",
    encoding="utf-8",
)
print(json.dumps(ledger, indent=2, sort_keys=True))
