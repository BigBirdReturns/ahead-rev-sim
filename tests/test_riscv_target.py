from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.mmio_abi import canonical_json
from ahead_rev_sim.riscv_target import (
    RISCV_TARGET_PROOF_SCHEMA_VERSION,
    build_riscv_target_proof,
    parse_target_trace,
    write_riscv_target_proof,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "riscv-target-proof.schema.json"
SOURCE = ROOT / "examples" / "riscv" / "mmio_target_smoke.c"
EXPECTED = ROOT / "examples" / "riscv" / "mmio_target_smoke.expected"
WORKFLOW = ROOT / ".github" / "workflows" / "riscv-target.yml"


def _fixture_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    binary = tmp_path / "mmio-target"
    trace = tmp_path / "trace.txt"
    expected = tmp_path / "expected.txt"
    binary.write_bytes(b"\x7fELF-riscv64-static-fixture")
    expected.write_bytes(EXPECTED.read_bytes())
    trace.write_bytes(expected.read_bytes())
    return binary, trace, expected


def _build_fixture_proof(tmp_path: Path) -> dict[str, object]:
    binary, trace, expected = _fixture_files(tmp_path)
    return build_riscv_target_proof(
        binary,
        trace,
        expected,
        compiler_version="riscv64-linux-gnu-gcc (Fixture) 14.2.0",
        emulator_version="qemu-riscv64 version 9.2.0",
        readelf_output="Class: ELF64\nMachine: RISC-V\n",
    )


def test_target_proof_is_deterministic_sealed_and_schema_valid(tmp_path: Path) -> None:
    first = _build_fixture_proof(tmp_path)
    second = _build_fixture_proof(tmp_path)
    assert first == second
    assert first["schema_version"] == RISCV_TARGET_PROOF_SCHEMA_VERSION
    assert first["qualification"]["status"] == "riscv_target_model_execution_proved"
    claimed = first.pop("proof_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    first["proof_sha256"] = claimed
    Draft202012Validator(schema).validate(first)


def test_accepted_trace_proves_refusal_reset_load_and_receipt() -> None:
    observations = parse_target_trace(EXPECTED.read_text(encoding="utf-8"))
    assert observations["line_count"] == 6
    assert all(observations["checks"].values())
    assert observations["checks"]["ambiguous_command_refused"] is True
    assert observations["checks"]["reset_completed"] is True
    assert observations["checks"]["load_completed"] is True


def test_target_proof_refuses_trace_or_machine_divergence(tmp_path: Path) -> None:
    binary, trace, expected = _fixture_files(tmp_path)
    trace.write_text("result=pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="diverges from the accepted trace"):
        build_riscv_target_proof(
            binary,
            trace,
            expected,
            compiler_version="gcc fixture",
            emulator_version="qemu fixture",
            readelf_output="Class: ELF64\nMachine: RISC-V\n",
        )

    trace.write_bytes(expected.read_bytes())
    with pytest.raises(ValueError, match="not identified as RISC-V"):
        build_riscv_target_proof(
            binary,
            trace,
            expected,
            compiler_version="gcc fixture",
            emulator_version="qemu fixture",
            readelf_output="Class: ELF64\nMachine: Advanced Micro Devices X86-64\n",
        )


def test_target_source_consumes_generated_header_and_has_no_physical_claim() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert '#include "ahead_physical_compute_mmio_v1.h"' in source
    assert "AHEAD_PHYS_CMD_RESET | AHEAD_PHYS_CMD_READ" in source
    assert "AHEAD_PHYS_STATUS_REFUSED" in source
    assert "AHEAD_PHYS_STATUS_RECEIPT_VALID" in source
    assert "does not stand in for Chipyard RTL or a physical" in source
    assert EXPECTED.read_text(encoding="utf-8").endswith("result=pass\n")


def test_target_proof_writer_and_workflow_close_actual_riscv_execution(tmp_path: Path) -> None:
    proof = _build_fixture_proof(tmp_path)
    output = write_riscv_target_proof(tmp_path / "proof.json", proof)
    assert json.loads(output.read_text(encoding="utf-8")) == proof

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "gcc-riscv64-linux-gnu" in workflow
    assert "qemu-user" in workflow
    assert "riscv64-linux-gnu-gcc" in workflow
    assert "qemu-riscv64" in workflow
    assert "riscv64-linux-gnu-readelf" in workflow
    assert "diff -u" in workflow
    assert "ahead-rev-riscv-target-proof" in workflow
    assert "actions/upload-artifact@v4" in workflow
