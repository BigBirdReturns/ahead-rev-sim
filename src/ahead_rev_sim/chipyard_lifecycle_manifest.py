"""Deterministic bundle manifest for the Chipyard RV64GC lifecycle."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    CHIPYARD_CONFIG_PACKAGE,
    CHIPYARD_REPOSITORY,
    DEFAULT_BASE_ADDRESS,
    build_chipyard_manifest,
)
from .mmio_abi import canonical_json
from .physical_constants import PORTABLE_BINDING
from .chipyard_lifecycle_program import (
    CHIPYARD_LIFECYCLE_EXPECTED_NAME,
    CHIPYARD_LIFECYCLE_MANIFEST_NAME,
    CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION,
    CHIPYARD_LIFECYCLE_SOURCE_NAME,
    CIRCT_ASSET_NAME,
    CIRCT_COMMIT,
    CIRCT_INSTALLER_COMMIT,
    CIRCT_INSTALLER_REPOSITORY,
    CIRCT_RELEASE,
    CIRCT_REPOSITORY,
    CIRCT_VERSION_FILE_NAME,
    FESVR_HEADER_SOURCE,
    FESVR_LIBRARY_NAME,
    RISCV_ISA_SIM_COMMIT,
    RISCV_ISA_SIM_REPOSITORY,
    RISCV_LIBRARY_NAME,
    LIBGLOSS_HTIF_COMMIT,
    LIBGLOSS_HTIF_LIBRARY_NAME,
    LIBGLOSS_HTIF_LINKER_SCRIPT_NAME,
    LIBGLOSS_HTIF_REPOSITORY,
    LIBGLOSS_HTIF_SPECS_NAME,
    LIFECYCLE_BLOCKERS,
    render_chipyard_lifecycle_source,
    render_chipyard_lifecycle_trace,
    sha256_bytes,
)


def _artifact_record(content: str) -> dict[str, Any]:
    payload = content.encode("utf-8")
    return {"sha256": sha256_bytes(payload), "bytes": len(payload)}


def build_chipyard_lifecycle_manifest(
    *,
    base_address: int = DEFAULT_BASE_ADDRESS,
) -> dict[str, Any]:
    source = render_chipyard_lifecycle_source(base_address=base_address)
    expected = render_chipyard_lifecycle_trace()
    integration = build_chipyard_manifest(base_address=base_address)
    payload: dict[str, Any] = {
        "schema_version": CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION,
        "artifact_type": "chipyard_rv64gc_lifecycle_bundle",
        "portable_binding": PORTABLE_BINDING,
        "chipyard": {
            "repository": CHIPYARD_REPOSITORY,
            "commit": CHIPYARD_COMMIT,
            "config_package": CHIPYARD_CONFIG_PACKAGE,
            "config_class": CHIPYARD_CONFIG_CLASS,
            "base_address": base_address,
            "entry_api": "testchipip.soc.SubsystemInjectorKey",
            "integration_manifest_sha256": integration["manifest_sha256"],
        },
        "target": {
            "isa": "rv64gc",
            "abi": "lp64d",
            "execution_environment": "chipyard-verilator-testharness",
            "loopback_fallback": True,
        },
        "simulator_runtime": {
            "repository": RISCV_ISA_SIM_REPOSITORY,
            "commit": RISCV_ISA_SIM_COMMIT,
            "header": FESVR_HEADER_SOURCE,
            "fesvr_library": FESVR_LIBRARY_NAME,
            "riscv_library": RISCV_LIBRARY_NAME,
        },
        "runtime": {
            "repository": LIBGLOSS_HTIF_REPOSITORY,
            "commit": LIBGLOSS_HTIF_COMMIT,
            "specs": LIBGLOSS_HTIF_SPECS_NAME,
            "linker_script": LIBGLOSS_HTIF_LINKER_SCRIPT_NAME,
            "library": LIBGLOSS_HTIF_LIBRARY_NAME,
        },
        "lowering": {
            "repository": CIRCT_REPOSITORY,
            "release": CIRCT_RELEASE,
            "commit": CIRCT_COMMIT,
            "asset": CIRCT_ASSET_NAME,
            "tool": "firtool",
            "version_file": CIRCT_VERSION_FILE_NAME,
            "installer_repository": CIRCT_INSTALLER_REPOSITORY,
            "installer_commit": CIRCT_INSTALLER_COMMIT,
        },
        "generated_artifacts": {
            CHIPYARD_LIFECYCLE_SOURCE_NAME: _artifact_record(source),
            CHIPYARD_LIFECYCLE_EXPECTED_NAME: _artifact_record(expected),
        },
        "qualification": {
            "status": "chipyard_rv64gc_lifecycle_unexecuted",
            "chipyard_rtl_simulation_claim_allowed": False,
            "physical_claim_allowed": False,
            "blockers": [
                "CHIPYARD_RTL_SIMULATION_UNRUN",
                "RISC_V_BINARY_BUILD_UNRUN",
                "TARGET_TRACE_UNOBSERVED",
                *LIFECYCLE_BLOCKERS,
            ],
        },
        "claim_boundary": (
            "The bundle supplies a deterministic RV64GC bare-metal lifecycle client "
            "and accepted trace for the pinned Chipyard physical-compute peripheral. "
            "It names the exact libgloss-htif runtime authority required by the "
            "HTIF-linked target, the exact riscv-isa-sim and FESVR host runtime "
            "required to build the simulator, and the exact CIRCT release required "
            "to lower the "
            "pinned FIRRTL into simulator RTL. It does not establish binary "
            "construction, Verilator "
            "compilation, RTL "
            "execution, an external cartridge, FPGA or silicon behavior, physical "
            "work, measured energy, complete-system EVP, or independent acceptance."
        ),
        "control_question": (
            "Can the same physical-compute MMIO admission, refusal, done, and receipt "
            "semantics execute as an RV64GC binary inside the pinned Chipyard "
            "TestHarness without transferring acceptance authority to Chipyard?"
        ),
    }
    payload["manifest_sha256"] = sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def write_chipyard_lifecycle_bundle(
    output_dir: str | Path,
    *,
    base_address: int = DEFAULT_BASE_ADDRESS,
) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "source": root / CHIPYARD_LIFECYCLE_SOURCE_NAME,
        "expected": root / CHIPYARD_LIFECYCLE_EXPECTED_NAME,
        "manifest": root / CHIPYARD_LIFECYCLE_MANIFEST_NAME,
    }
    outputs["source"].write_bytes(
        render_chipyard_lifecycle_source(base_address=base_address).encode("utf-8")
    )
    outputs["expected"].write_bytes(
        render_chipyard_lifecycle_trace().encode("utf-8")
    )
    outputs["manifest"].write_bytes(
        (
            json.dumps(
                build_chipyard_lifecycle_manifest(base_address=base_address),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    )
    return outputs
