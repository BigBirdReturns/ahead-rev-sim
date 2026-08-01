"""Release artifact admission and checksum generation."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import tarfile
from typing import Any
import zipfile

from ._version import __version__
from .repository_audit import audit_repository

RELEASE_MANIFEST_SCHEMA_VERSION = "ahead.release-manifest/v0.1"


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _wheel_members(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def _sdist_members(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as archive:
        return set(archive.getnames())


def build_release_manifest(
    *,
    root: Path,
    dist: Path,
    tag: str | None = None,
) -> dict[str, Any]:
    audit = audit_repository(root)
    blockers = list(audit["blockers"])

    expected_tag = f"v{__version__}"
    if tag is not None and tag != expected_tag:
        blockers.append(f"TAG_VERSION_MISMATCH:expected={expected_tag};actual={tag}")

    artifacts = (
        sorted(
            path
            for path in dist.iterdir()
            if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
        )
        if dist.is_dir()
        else []
    )
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
    if len(wheels) != 1:
        blockers.append(f"WHEEL_COUNT_INVALID:{len(wheels)}")
    if len(sdists) != 1:
        blockers.append(f"SDIST_COUNT_INVALID:{len(sdists)}")

    normalized_version = __version__.replace("-", "_")
    artifact_records: list[dict[str, Any]] = []
    for path in artifacts:
        if normalized_version not in path.name:
            blockers.append(f"ARTIFACT_VERSION_MISMATCH:{path.name}")
        artifact_records.append(
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _digest(path),
            }
        )

    if wheels:
        members = _wheel_members(wheels[0])
        required_wheel_suffixes = {
            "ahead_rev_sim/_version.py",
            "ahead_rev_sim/py.typed",
            "ahead_rev_sim/data/commodity_ecosystem_registry.json",
            "ahead_rev_sim/data/congruent_shape_pylons.json",
        }
        for suffix in required_wheel_suffixes:
            if not any(member.endswith(suffix) for member in members):
                blockers.append(f"WHEEL_MEMBER_MISSING:{suffix}")
        if not any(member.endswith(".dist-info/METADATA") for member in members):
            blockers.append("WHEEL_METADATA_MISSING")
        if not any(
            ".dist-info/" in member and member.endswith("LICENSE")
            for member in members
        ):
            blockers.append("WHEEL_LICENSE_MISSING")

    if sdists:
        members = _sdist_members(sdists[0])
        required_sdist_suffixes = {
            "/README.md",
            "/CHANGELOG.md",
            "/LICENSE",
            "/CITATION.cff",
            "/pyproject.toml",
            "/src/ahead_rev_sim/_version.py",
        }
        for suffix in required_sdist_suffixes:
            if not any(member.endswith(suffix) for member in members):
                blockers.append(f"SDIST_MEMBER_MISSING:{suffix}")

    manifest: dict[str, Any] = {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "artifact_type": "ahead_rev_sim_release_manifest",
        "version": __version__,
        "expected_tag": expected_tag,
        "observed_tag": tag,
        "status": "pass" if not blockers else "refused",
        "repository_audit_status": audit["status"],
        "artifacts": artifact_records,
        "blockers": blockers,
        "warnings": audit["warnings"],
        "claim_boundary": (
            "Release admission proves source and package integrity at the software "
            "evidence tier. It does not establish physical execution, measured EVP "
            "advantage, fabrication, or independent physical acceptance."
        ),
    }
    manifest["manifest_sha256"] = sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return manifest


def write_release_outputs(dist: Path, manifest: dict[str, Any]) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    records = manifest["artifacts"]
    checksum_text = "".join(
        f"{record['sha256']}  {record['name']}\n"
        for record in sorted(records, key=lambda item: item["name"])
    )
    (dist / "SHA256SUMS").write_text(checksum_text, encoding="utf-8")
    (dist / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release-preflight")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--tag")
    args = parser.parse_args(argv)

    manifest = build_release_manifest(root=args.root, dist=args.dist, tag=args.tag)
    write_release_outputs(args.dist, manifest)
    print(f"status: {manifest['status']}")
    print(f"version: {manifest['version']}")
    print(f"artifacts: {len(manifest['artifacts'])}")
    print(f"manifest sha256: {manifest['manifest_sha256']}")
    for blocker in manifest["blockers"]:
        print(f"BLOCKER {blocker}")
    return 0 if manifest["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
