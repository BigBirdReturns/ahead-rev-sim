"""Sealed evidence for a RISC-V execution of the MMIO lifecycle model."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from .mmio_abi import build_mmio_abi, canonical_json
from .physical_constants import OPTIONAL_RISCV_EXTENSION, PORTABLE_BINDING

RISCV_TARGET_PROOF_SCHEMA_VERSION = "ahead.riscv-target-proof/v0.1"


def sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _first_line(value: str) -> str:
    return value.strip().splitlines()[0] if value.strip() else ""


def command_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    version = _first_line(completed.stdout)
    if not version:
        raise ValueError(f"{executable}: version output is empty")
    return version


def readelf_header(executable: str, binary_path: str | Path) -> str:
    completed = subprocess.run(
        [executable, "-h", str(binary_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not completed.stdout.strip():
        raise ValueError(f"{executable}: ELF header output is empty")
    return completed.stdout


def parse_target_trace(trace: str) -> dict[str, Any]:
    lines = [line.strip() for line in trace.splitlines() if line.strip()]
    required_prefixes = (
        "abi=",
        "identity=",
        "ambiguous ",
        "reset ",
        "load ",
        "result=",
    )
    positions: dict[str, int] = {}
    for prefix in required_prefixes:
        matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(
                f"target trace requires exactly one line beginning with {prefix!r}"
            )
        positions[prefix] = matches[0]
    if [positions[prefix] for prefix in required_prefixes] != sorted(positions.values()):
        raise ValueError("target trace lifecycle lines are out of order")

    abi_line = lines[positions["abi="]]
    identity_line = lines[positions["identity="]]
    ambiguous_line = lines[positions["ambiguous "]]
    reset_line = lines[positions["reset "]]
    load_line = lines[positions["load "]]
    result_line = lines[positions["result="]]

    checks = {
        "portable_binding": f"abi={PORTABLE_BINDING}" in abi_line,
        "target_isa": "isa=rv64gc" in abi_line,
        "identity": "identity=41504859" in identity_line,
        "software_fallback_capability": "capabilities=00000009" in identity_line,
        "ambiguous_command_refused": (
            "status=00000009" in ambiguous_line and "result=refused" in ambiguous_line
        ),
        "reset_completed": (
            "status=00000025" in reset_line
            and "result=done" in reset_line
            and "receipt=valid" in reset_line
        ),
        "load_completed": (
            "status=00000025" in load_line
            and "result=done" in load_line
            and "receipt=valid" in load_line
            and "descriptor=0000000010001000" in load_line
            and "input=0000000010002000" in load_line
        ),
        "result_pass": result_line == "result=pass",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"target trace semantic checks failed: {failed}")
    return {
        "line_count": len(lines),
        "checks": checks,
    }


def build_riscv_target_proof(
    binary_path: str | Path,
    trace_path: str | Path,
    expected_trace_path: str | Path,
    *,
    compiler_version: str,
    emulator_version: str,
    readelf_output: str,
) -> dict[str, Any]:
    binary = Path(binary_path).read_bytes()
    trace = Path(trace_path).read_bytes()
    expected = Path(expected_trace_path).read_bytes()
    if not binary:
        raise ValueError("RISC-V target binary is empty")
    if trace != expected:
        raise ValueError("RISC-V target trace diverges from the accepted trace")

    readelf_lower = readelf_output.lower()
    if "class:" not in readelf_lower or "elf64" not in readelf_lower:
        raise ValueError("target binary is not identified as ELF64")
    if "machine:" not in readelf_lower or "risc-v" not in readelf_lower:
        raise ValueError("target binary is not identified as RISC-V")
    if not compiler_version.strip() or not emulator_version.strip():
        raise ValueError("compiler and emulator versions are required")

    observations = parse_target_trace(trace.decode("utf-8"))
    abi = build_mmio_abi()
    proof: dict[str, Any] = {
        "schema_version": RISCV_TARGET_PROOF_SCHEMA_VERSION,
        "artifact_type": "riscv_target_model_execution_proof",
        "portable_binding": PORTABLE_BINDING,
        "optional_riscv_extension": OPTIONAL_RISCV_EXTENSION,
        "target": {
            "isa": "rv64gc",
            "abi": "lp64d",
            "execution_environment": "qemu-riscv64-user",
            "test_class": "mmio_client_and_independent_device_model",
        },
        "toolchain": {
            "compiler": _first_line(compiler_version),
            "emulator": _first_line(emulator_version),
            "readelf_machine": "RISC-V",
            "readelf_class": "ELF64",
        },
        "artifacts": {
            "abi_sha256": abi["abi_sha256"],
            "binary_sha256": sha256_bytes(binary),
            "binary_bytes": len(binary),
            "trace_sha256": sha256_bytes(trace),
            "expected_trace_sha256": sha256_bytes(expected),
        },
        "observations": observations,
        "qualification": {
            "status": "riscv_target_model_execution_proved",
            "accepted": True,
            "physical_claim_allowed": False,
            "blockers": [
                "CHIPYARD_ELABORATION_UNRUN",
                "CHIPYARD_RTL_SIMULATION_UNRUN",
                "PHYSICAL_SUBSTRATE_UNMEASURED",
                "PHYSICAL_ENERGY_UNMEASURED",
                "TIMING_THERMAL_VOLUME_UNMEASURED",
            ],
        },
        "claim_boundary": (
            "The proof establishes that a statically linked RV64GC binary executed "
            "under qemu-riscv64, consumed the generated MMIO header, reproduced the "
            "accepted admission and refusal trace, and matched an independent C device "
            "model. It does not establish Chipyard elaboration, RTL execution, physical "
            "substrate work, energy, timing, thermal closure, occupied volume, or silicon."
        ),
    }
    proof["proof_sha256"] = sha256(
        canonical_json(proof).encode("utf-8")
    ).hexdigest()
    return proof


def build_riscv_target_proof_from_tools(
    binary_path: str | Path,
    trace_path: str | Path,
    expected_trace_path: str | Path,
    *,
    compiler: str = "riscv64-linux-gnu-gcc",
    emulator: str = "qemu-riscv64",
    readelf: str = "riscv64-linux-gnu-readelf",
) -> dict[str, Any]:
    return build_riscv_target_proof(
        binary_path,
        trace_path,
        expected_trace_path,
        compiler_version=command_version(compiler),
        emulator_version=command_version(emulator),
        readelf_output=readelf_header(readelf, binary_path),
    )


def write_riscv_target_proof(
    output_path: str | Path,
    proof: dict[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
