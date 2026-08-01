"""Byte-deterministic writers for generated MMIO authority artifacts."""

from __future__ import annotations

from pathlib import Path

from .mmio_abi import (
    render_abi_json,
    render_c_header,
    render_sva,
    render_systemverilog,
)


def _write_utf8_lf(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def write_bundle(output_dir: str | Path) -> dict[str, Path]:
    """Write the four-file MMIO bundle without host newline translation."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "abi": root / "physical-compute-mmio-v1.json",
        "c_header": root / "ahead_physical_compute_mmio_v1.h",
        "systemverilog": root / "ahead_physical_compute_mmio_v1.sv",
        "sva": root / "ahead_physical_compute_mmio_v1_sva.sv",
    }
    _write_utf8_lf(outputs["abi"], render_abi_json())
    _write_utf8_lf(outputs["c_header"], render_c_header())
    _write_utf8_lf(outputs["systemverilog"], render_systemverilog())
    _write_utf8_lf(outputs["sva"], render_sva())
    return outputs
