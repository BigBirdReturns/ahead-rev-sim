from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.chipyard_cli import main as chipyard_main
from ahead_rev_sim.chipyard_integration import (
    CHIPYARD_INTEGRATION_SCHEMA_VERSION,
    CHIPYARD_REFERENCE_BLOB_SHA,
    CHIPYARD_REFERENCE_PATH,
    CHIPYARD_REFERENCE_URL,
    DEFAULT_BASE_ADDRESS,
    build_chipyard_manifest,
    render_baremetal_smoke,
    render_chipyard_scala,
    write_chipyard_bundle,
)
from ahead_rev_sim.mmio_abi import COMMAND_BITS, STATUS_BITS, bit_mask, canonical_json
from ahead_rev_sim.physical_constants import PHYSICAL_COMPUTE_MMIO_V1, PORTABLE_BINDING

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "chipyard-physical-compute-integration.schema.json"


def test_chipyard_manifest_is_deterministic_sealed_and_schema_valid() -> None:
    first = build_chipyard_manifest()
    second = build_chipyard_manifest()
    assert first == second
    assert first["schema_version"] == CHIPYARD_INTEGRATION_SCHEMA_VERSION
    assert first["portable_binding"] == PORTABLE_BINDING
    claimed = first.pop("manifest_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    first["manifest_sha256"] = claimed
    Draft202012Validator(schema).validate(first)


def test_chipyard_source_contract_is_pinned_to_public_mmio_example_blob() -> None:
    manifest = build_chipyard_manifest()
    contract = manifest["chipyard_source_contract"]
    assert contract["repository"] == "ucb-bar/chipyard"
    assert contract["path"] == CHIPYARD_REFERENCE_PATH
    assert contract["blob_sha"] == CHIPYARD_REFERENCE_BLOB_SHA
    assert contract["url"] == CHIPYARD_REFERENCE_URL
    assert CHIPYARD_REFERENCE_BLOB_SHA == "f1579822bc7bacab7dcdfac742034266ddea012b"
    assert {
        "ClockSinkDomain",
        "TLRegisterNode",
        "RegField",
        "TLInwardClockCrossingHelper",
        "TLFragmenter",
        "BaseSubsystem",
        "PBUS",
    } == set(contract["api_patterns"])


def test_generated_scala_uses_current_chipyard_tilelink_construction() -> None:
    scala = render_chipyard_scala()
    assert "extends ClockSinkDomain(ClockSinkParameters())" in scala
    assert "TLRegisterNode(" in scala
    assert "node.regmap(" in scala
    assert "TLInwardClockCrossingHelper(" in scala
    assert "TLFragmenter(pbus.beatBytes, pbus.blockBytes)" in scala
    assert "trait CanHavePeripheryPhysicalCompute" in scala
    assert "class WithPhysicalCompute" in scala
    for offset in PHYSICAL_COMPUTE_MMIO_V1.values():
        assert f"0x{offset:02X} ->" in scala


def test_generated_scala_preserves_refusal_fallback_and_receipt_semantics() -> None:
    scala = render_chipyard_scala()
    assert "val oneHotSupported" in scala
    assert "PopCount(command) === 1.U" in scala
    assert "val pointersReady" in scala
    assert "statusReg := StatusReady | StatusRefused" in scala
    assert "loopbackFallback" in scala
    assert "io.fallback_used" in scala
    assert "StatusReceiptValid" in scala
    assert "commandValid && observedReady" in scala


def test_baremetal_smoke_exercises_refusal_and_accepted_lifecycle() -> None:
    smoke = render_baremetal_smoke()
    assert f"#define PHYS_BASE UINT64_C(0x{DEFAULT_BASE_ADDRESS:08X})" in smoke
    for offset in PHYSICAL_COMPUTE_MMIO_V1.values():
        assert f"0x{offset:02X}u" in smoke
    assert "CMD_RESET | CMD_READ" in smoke
    assert "STATUS_REFUSED" in smoke
    assert "STATUS_DONE | STATUS_RECEIPT_VALID" in smoke
    assert "write_ptr(REG_DESCRIPTOR_LO" in smoke
    assert "return 0;" in smoke


def test_generated_command_and_status_masks_match_the_abi() -> None:
    scala = render_chipyard_scala()
    smoke = render_baremetal_smoke()
    for name, bit in COMMAND_BITS.items():
        value = bit_mask(bit)
        scala_name = "Cmd" + "".join(part.title() for part in name.split("_"))
        assert f'val {scala_name} = "h{value:08X}".U(32.W)' in scala
    for name in ("ready", "busy", "done", "refused", "fault", "receipt_valid"):
        assert f"0x{bit_mask(STATUS_BITS[name]):08X}" in smoke


def test_base_address_must_be_4k_aligned() -> None:
    with pytest.raises(ValueError, match="4 KiB aligned"):
        render_chipyard_scala(base_address=0x0200_0004)
    with pytest.raises(ValueError, match="4 KiB aligned"):
        render_baremetal_smoke(base_address=-0x1000)
    with pytest.raises(ValueError, match="4 KiB aligned"):
        build_chipyard_manifest(base_address=7)


def test_chipyard_bundle_files_match_manifest_hashes(tmp_path: Path) -> None:
    outputs = write_chipyard_bundle(tmp_path)
    assert {path.name for path in outputs.values()} == {
        "PhysicalCompute.scala",
        "physical_compute_smoke.c",
        "chipyard-physical-compute-integration.json",
    }
    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    assert manifest["generated_artifacts"]["PhysicalCompute.scala"] == sha256(
        outputs["scala"].read_bytes()
    ).hexdigest()
    assert manifest["generated_artifacts"]["physical_compute_smoke.c"] == sha256(
        outputs["smoke"].read_bytes()
    ).hexdigest()
    assert manifest["qualification"]["physical_claim_allowed"] is False
    assert "CHIPYARD_ELABORATION_UNRUN" in manifest["qualification"]["blockers"]
    assert "TARGET_TRACE_UNOBSERVED" in manifest["qualification"]["blockers"]


def test_chipyard_cli_writes_deterministic_bundle(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert chipyard_main(["--out-dir", str(first)]) == 0
    assert chipyard_main(
        [
            "--out-dir",
            str(second),
            "--base-address",
            hex(DEFAULT_BASE_ADDRESS),
        ]
    ) == 0
    for name in (
        "PhysicalCompute.scala",
        "physical_compute_smoke.c",
        "chipyard-physical-compute-integration.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
