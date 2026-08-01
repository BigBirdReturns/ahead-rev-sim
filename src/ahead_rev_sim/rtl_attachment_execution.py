"""Fail-closed admission for executed RTL attachment evidence.

Generation and simulation live in :mod:`ahead_rev_sim.rtl_attachment`. This
module adds the source-custody checks required before an execution trace can be
promoted into an accepted proof.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from .mmio_abi import render_systemverilog
from .rtl_attachment import (
    build_attachment_manifest,
    build_rtl_attachment_proof as _build_rtl_attachment_proof,
    command_version,
    sha256_bytes,
)

_REQUIRED_SOURCE_NAMES = {
    "ahead_physical_compute_mmio_v1.sv",
    "ahead_reference_handle_resolver_v1.sv",
    "ahead_reference_reversible_cartridge_v1.sv",
    "ahead_physical_compute_attachment_tb.sv",
}

_MANIFEST_BOUND_SOURCE_NAMES = _REQUIRED_SOURCE_NAMES - {
    "ahead_physical_compute_mmio_v1.sv"
}


def _validate_source_custody(
    manifest_path: str | Path,
    source_paths: Sequence[str | Path],
) -> None:
    if len(source_paths) != len(_REQUIRED_SOURCE_NAMES):
        raise ValueError(
            "RTL proof requires exactly the MMIO, resolver, cartridge, and "
            "testbench sources"
        )

    resolved: dict[str, Path] = {}
    for raw_path in source_paths:
        path = Path(raw_path)
        if path.name in resolved:
            raise ValueError(f"duplicate RTL source basename: {path.name}")
        resolved[path.name] = path

    if set(resolved) != _REQUIRED_SOURCE_NAMES:
        raise ValueError(
            "RTL proof requires exactly the MMIO, resolver, cartridge, and "
            "testbench sources"
        )

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    expected_manifest = build_attachment_manifest()
    if manifest != expected_manifest:
        raise ValueError("RTL attachment manifest diverges from the generated contract")

    for name in sorted(_MANIFEST_BOUND_SOURCE_NAMES):
        payload = resolved[name].read_bytes()
        record = manifest["files"][name]
        if sha256_bytes(payload) != record["sha256"] or len(payload) != record["bytes"]:
            raise ValueError(f"RTL source diverges from sealed manifest: {name}")

    mmio_payload = resolved["ahead_physical_compute_mmio_v1.sv"].read_bytes()
    expected_mmio = render_systemverilog().encode("utf-8")
    if mmio_payload != expected_mmio:
        raise ValueError("generated MMIO RTL diverges from the current ABI authority")


def build_rtl_attachment_proof(
    executable_path: str | Path,
    trace_path: str | Path,
    expected_trace_path: str | Path,
    manifest_path: str | Path,
    source_paths: Sequence[str | Path],
    *,
    iverilog_version: str,
    vvp_version: str,
) -> dict[str, Any]:
    _validate_source_custody(manifest_path, source_paths)
    return _build_rtl_attachment_proof(
        executable_path,
        trace_path,
        expected_trace_path,
        manifest_path,
        source_paths,
        iverilog_version=iverilog_version,
        vvp_version=vvp_version,
    )


def build_rtl_attachment_proof_from_tools(
    executable_path: str | Path,
    trace_path: str | Path,
    expected_trace_path: str | Path,
    manifest_path: str | Path,
    source_paths: Sequence[str | Path],
    *,
    iverilog: str = "iverilog",
    vvp: str = "vvp",
) -> dict[str, Any]:
    return build_rtl_attachment_proof(
        executable_path,
        trace_path,
        expected_trace_path,
        manifest_path,
        source_paths,
        iverilog_version=command_version(iverilog),
        vvp_version=command_version(vvp),
    )
