from __future__ import annotations

import base64
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/pr11-finalization"
MANIFEST = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    raise SystemExit("GITHUB_TOKEN is unavailable")


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def git_blob_digest(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return sha1(header + data).hexdigest()


endpoint = "https://api.github.com/repos/BigBirdReturns/ahead-rev-sim/git/blobs"
records: list[dict[str, object]] = []
for declared in MANIFEST["files"]:
    relative = str(declared["path"])
    path = OUT / "files" / relative
    data = path.read_bytes()
    actual_sha256 = digest(data)
    if actual_sha256 != declared["sha256"]:
        raise SystemExit(f"export digest changed: {relative}")
    payload = json.dumps(
        {
            "content": base64.b64encode(data).decode("ascii"),
            "encoding": "base64",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "ahead-rev-sim-pr11-finalizer",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            document = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"Git blob creation failed for {relative}: HTTP {exc.code}: {body}"
        ) from exc
    blob_sha = str(document["sha"])
    expected_blob_sha = git_blob_digest(data)
    if blob_sha != expected_blob_sha:
        raise SystemExit(
            f"Git blob identity mismatch for {relative}: "
            f"expected {expected_blob_sha}, observed {blob_sha}"
        )
    record = {
        "path": relative,
        "size_bytes": len(data),
        "sha256": actual_sha256,
        "git_blob_sha": blob_sha,
    }
    records.append(record)
    print(json.dumps(record, sort_keys=True), flush=True)

output = {
    "schema": "ahead.pr11-finalization-git-blobs/v1",
    "repository": "BigBirdReturns/ahead-rev-sim",
    "branch": MANIFEST["branch"],
    "source_head": MANIFEST["source_head"],
    "files": records,
    "delete_paths": MANIFEST["delete_paths"],
    "validated": MANIFEST["validated"],
}
(OUT / "blob-shas.json").write_text(
    json.dumps(output, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
checksums = []
for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
    checksums.append(f"{digest(path.read_bytes())}  {path.relative_to(OUT).as_posix()}")
(OUT / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
print(json.dumps(output, indent=2, sort_keys=True))
