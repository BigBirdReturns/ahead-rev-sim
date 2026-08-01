"""Byte-deterministic I/O for generated RTL attachment artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .rtl_attachment import _bundle_sources, build_attachment_manifest


def _write_utf8_lf(path: Path, content: str) -> None:
    """Write exact UTF-8 bytes without host newline translation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def write_attachment_bundle(output_dir: str | Path) -> dict[str, Path]:
    """Write the generated attachment with byte-identical content on every OS."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for name, content in _bundle_sources().items():
        path = root / name
        _write_utf8_lf(path, content)
        outputs[name] = path

    manifest_path = root / "rtl-attachment-manifest.json"
    _write_utf8_lf(
        manifest_path,
        json.dumps(build_attachment_manifest(), indent=2, sort_keys=True) + "\n",
    )
    outputs["rtl-attachment-manifest.json"] = manifest_path
    return outputs


def write_rtl_attachment_proof(
    output_path: str | Path,
    proof: Mapping[str, Any],
) -> Path:
    """Write the proof without platform-dependent newline conversion."""
    output = Path(output_path)
    _write_utf8_lf(
        output,
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
    )
    return output
