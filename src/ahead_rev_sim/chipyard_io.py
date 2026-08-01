"""Byte-deterministic I/O for Chipyard integration and proof artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .chipyard_subsystem import (
    build_chipyard_manifest,
    render_baremetal_smoke,
    render_chipyard_scala,
)


def _write_utf8_lf(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def write_chipyard_bundle(
    output_dir: str | Path,
    *,
    base_address: int,
) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "scala": root / "PhysicalCompute.scala",
        "smoke": root / "physical_compute_smoke.c",
        "manifest": root / "chipyard-physical-compute-integration.json",
    }
    _write_utf8_lf(
        outputs["scala"],
        render_chipyard_scala(base_address=base_address),
    )
    _write_utf8_lf(
        outputs["smoke"],
        render_baremetal_smoke(base_address=base_address),
    )
    _write_utf8_lf(
        outputs["manifest"],
        json.dumps(
            build_chipyard_manifest(base_address=base_address),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return outputs


def write_chipyard_elaboration_proof(
    output_path: str | Path,
    proof: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    _write_utf8_lf(
        output,
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
    )
    return output
