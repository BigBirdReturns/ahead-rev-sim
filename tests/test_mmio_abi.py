from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.mmio_abi import (
    CAPABILITY_BITS,
    COMMAND_BITS,
    MMIO_APERTURE_BYTES,
    MMIO_ABI_SCHEMA_VERSION,
    PhysicalComputeMMIOReference,
    STATUS_BITS,
    bit_mask,
    build_mmio_abi,
    canonical_json,
    render_c_header,
    render_sva,
    render_systemverilog,
    write_bundle,
)
from ahead_rev_sim.mmio_cli import main as mmio_main
from ahead_rev_sim.physical_constants import (
    OPTIONAL_RISCV_EXTENSION,
    PHYSICAL_COMPUTE_MMIO_V1,
    PORTABLE_BINDING,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "physical-compute-mmio-abi.schema.json"


def test_mmio_abi_validates_against_draft_2020_12_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(build_mmio_abi())


def test_mmio_abi_is_deterministic_and_sealed() -> None:
    first = build_mmio_abi()
    second = build_mmio_abi()
    assert first == second
    assert first["schema_version"] == MMIO_ABI_SCHEMA_VERSION
    assert first["portable_binding"] == PORTABLE_BINDING
    assert first["optional_riscv_extension"] == OPTIONAL_RISCV_EXTENSION
    claimed = first.pop("abi_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()


def test_mmio_register_map_is_exact_aligned_and_inside_aperture() -> None:
    abi = build_mmio_abi()
    observed = {item["name"]: item["offset"] for item in abi["registers"]}
    assert observed == dict(PHYSICAL_COMPUTE_MMIO_V1)
    offsets = [item["offset"] for item in abi["registers"]]
    assert offsets == sorted(offsets)
    assert len(offsets) == len(set(offsets))
    assert all(offset % 4 == 0 for offset in offsets)
    assert max(offsets) + 4 <= MMIO_APERTURE_BYTES


def test_generated_c_header_preserves_offsets_and_portability_floor() -> None:
    header = render_c_header()
    assert f'#define AHEAD_PHYS_MMIO_BINDING "{PORTABLE_BINDING}"' in header
    assert (
        f'#define AHEAD_PHYS_OPTIONAL_RISCV_EXTENSION "{OPTIONAL_RISCV_EXTENSION}"'
        in header
    )
    for name, offset in PHYSICAL_COMPUTE_MMIO_V1.items():
        macro = name.upper()
        assert f"AHEAD_PHYS_REG_{macro} 0x{offset:02X}u" in header
        assert f"offsetof(ahead_phys_mmio_v1_t, {name})" in header


def test_generated_systemverilog_implements_standard_mmio_and_refusal() -> None:
    rtl = render_systemverilog()
    assert "module ahead_physical_compute_mmio_v1" in rtl
    assert "command_onehot" in rtl
    assert "command_pointers_ready" in rtl
    assert "STATUS_REFUSED" in rtl
    assert "command_valid_o" in rtl
    for offset in PHYSICAL_COMPUTE_MMIO_V1.values():
        assert f"8'h{offset:02X}" in rtl
    assert "Xphys may accelerate this interface but cannot change it" in rtl


def test_generated_assertions_cover_command_terminal_and_pointer_custody() -> None:
    assertions = render_sva()
    assert "$onehot(command_i)" in assertions
    assert "$onehot0" in assertions
    assert "STATUS_RECEIPT_VALID" in assertions
    assert "$stable" in assertions


def test_reference_model_refuses_read_only_unaligned_and_unknown_access() -> None:
    model = PhysicalComputeMMIOReference()
    assert model.read(PHYSICAL_COMPUTE_MMIO_V1["identity"]) == 0x41504859
    with pytest.raises(PermissionError, match="read-only"):
        model.write(PHYSICAL_COMPUTE_MMIO_V1["status"], 1)
    with pytest.raises(ValueError, match="unaligned"):
        model.read(1)
    with pytest.raises(KeyError, match="unknown MMIO offset"):
        model.read(0xFC)


def test_reference_model_refuses_ambiguous_command_and_missing_pointers() -> None:
    model = PhysicalComputeMMIOReference()
    model.write(
        PHYSICAL_COMPUTE_MMIO_V1["command"],
        bit_mask(COMMAND_BITS["load"]) | bit_mask(COMMAND_BITS["read"]),
    )
    model.write(PHYSICAL_COMPUTE_MMIO_V1["doorbell"], 1)
    status = model.read(PHYSICAL_COMPUTE_MMIO_V1["status"])
    assert status & bit_mask(STATUS_BITS["ready"])
    assert status & bit_mask(STATUS_BITS["refused"])
    assert not model.busy

    model.reset()
    model.write(PHYSICAL_COMPUTE_MMIO_V1["command"], bit_mask(COMMAND_BITS["load"]))
    model.write(PHYSICAL_COMPUTE_MMIO_V1["doorbell"], 1)
    status = model.read(PHYSICAL_COMPUTE_MMIO_V1["status"])
    assert status & bit_mask(STATUS_BITS["refused"])


def test_reference_model_executes_valid_load_and_custodies_busy_state() -> None:
    model = PhysicalComputeMMIOReference(
        capabilities=(
            bit_mask(CAPABILITY_BITS["software_fallback"])
            | bit_mask(CAPABILITY_BITS["exact"])
        )
    )
    model.write(PHYSICAL_COMPUTE_MMIO_V1["descriptor_ptr_lo"], 0x1000)
    model.write(PHYSICAL_COMPUTE_MMIO_V1["input_queue_ptr_lo"], 0x2000)
    model.write(PHYSICAL_COMPUTE_MMIO_V1["command"], bit_mask(COMMAND_BITS["load"]))
    model.write(PHYSICAL_COMPUTE_MMIO_V1["doorbell"], 1)
    assert model.busy
    with pytest.raises(RuntimeError, match="immutable while busy"):
        model.write(PHYSICAL_COMPUTE_MMIO_V1["command"], 0)

    model.complete(outcome="done", receipt_valid=True)
    status = model.read(PHYSICAL_COMPUTE_MMIO_V1["status"])
    assert status & bit_mask(STATUS_BITS["ready"])
    assert status & bit_mask(STATUS_BITS["done"])
    assert status & bit_mask(STATUS_BITS["receipt_valid"])
    assert not model.busy


def test_generated_bundle_is_complete_and_deterministic(tmp_path: Path) -> None:
    first = write_bundle(tmp_path / "first")
    second = write_bundle(tmp_path / "second")
    assert set(first) == {"abi", "c_header", "systemverilog", "sva"}
    assert set(second) == set(first)
    for name in first:
        assert first[name].read_bytes() == second[name].read_bytes()


def test_mmio_cli_writes_single_artifact_and_bundle(tmp_path: Path) -> None:
    abi_path = tmp_path / "abi.json"
    assert mmio_main(["--format", "json", "--out", str(abi_path)]) == 0
    payload = json.loads(abi_path.read_text(encoding="utf-8"))
    assert payload["portable_binding"] == PORTABLE_BINDING
    assert len(payload["abi_sha256"]) == 64

    bundle = tmp_path / "bundle"
    assert mmio_main(["--format", "bundle", "--out-dir", str(bundle)]) == 0
    assert {path.name for path in bundle.iterdir()} == {
        "physical-compute-mmio-v1.json",
        "ahead_physical_compute_mmio_v1.h",
        "ahead_physical_compute_mmio_v1.sv",
        "ahead_physical_compute_mmio_v1_sva.sv",
    }
