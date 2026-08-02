from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.chipyard_cli import main as chipyard_main
from ahead_rev_sim.chipyard_integration import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    CHIPYARD_CONFIG_PACKAGE,
    CHIPYARD_INTEGRATION_SCHEMA_VERSION,
    CHIPYARD_REFERENCE_BLOB_SHA,
    CHIPYARD_REFERENCE_PATH,
    CHIPYARD_REFERENCE_URL,
    CHIPYARD_SCALA_INSTALL_PATH,
    CHIPYARD_SOURCE_WITNESSES,
    DEFAULT_BASE_ADDRESS,
    ELABORATION_WITNESS_NAME,
    ELABORATION_WITNESS_VALUE,
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


def test_chipyard_source_contract_is_pinned_to_current_upstream_commit() -> None:
    manifest = build_chipyard_manifest()
    contract = manifest["chipyard_source_contract"]
    assert contract["repository"] == "ucb-bar/chipyard"
    assert contract["commit"] == CHIPYARD_COMMIT
    assert CHIPYARD_COMMIT == "e27c6561c0066c1f60bf4eb4885a38391c850ac0"
    assert contract["source_witnesses"] == CHIPYARD_SOURCE_WITNESSES
    assert contract["source_witnesses"][CHIPYARD_REFERENCE_PATH]["blob_sha"] == (
        CHIPYARD_REFERENCE_BLOB_SHA
    )
    assert CHIPYARD_REFERENCE_BLOB_SHA == "f1579822bc7bacab7dcdfac742034266ddea012b"
    assert CHIPYARD_COMMIT in CHIPYARD_REFERENCE_URL
    assert {
        "ClockSinkDomain",
        "TLRegisterNode",
        "RegField",
        "TLInwardClockCrossingHelper",
        "TLFragmenter",
        "BaseSubsystem",
        "PBUS",
    } == set(
        contract["source_witnesses"][CHIPYARD_REFERENCE_PATH]["required_patterns"]
    )


def test_generated_scala_uses_upstream_subsystem_injector_without_top_patch() -> None:
    scala = render_chipyard_scala()
    assert f"package {CHIPYARD_CONFIG_PACKAGE}" in scala
    assert "extends ClockSinkDomain(ClockSinkParameters())" in scala
    assert "TLRegisterNode(" in scala
    assert "node.regmap(" in scala
    assert "case object PhysicalComputeInjector extends SubsystemInjector" in scala
    assert "case SubsystemInjectorKey" in scala
    assert "up(SubsystemInjectorKey) + PhysicalComputeInjector" in scala
    assert "TLInwardClockCrossingHelper(" in scala
    assert "TLFragmenter(pbus.beatBytes, pbus.blockBytes)" in scala
    assert f"class {CHIPYARD_CONFIG_CLASS} extends Config" in scala
    assert "trait CanHavePeripheryPhysicalCompute" not in scala
    assert "Add `with" not in scala
    for offset in PHYSICAL_COMPUTE_MMIO_V1.values():
        assert f"0x{offset:02X} ->" in scala


def test_generated_scala_preserves_refusal_fallback_and_elaboration_witness() -> None:
    scala = render_chipyard_scala()
    assert "val oneHotSupported" in scala
    assert "PopCount(command) === 1.U" in scala
    assert "val pointersReady" in scala
    assert "statusReg := StatusReady | StatusRefused" in scala
    assert "loopbackFallback" in scala
    assert "The v0.11 Chipyard proof admits only" in scala
    assert "StatusReceiptValid" in scala
    assert "val loopbackDone = RegNext(loopbackAccepted, false.B)" in scala
    assert ELABORATION_WITNESS_NAME in scala
    assert f'"h{ELABORATION_WITNESS_VALUE:08X}".U(32.W)' in scala
    assert "dontTouch(elaborationWitness)" in scala


def test_manifest_declares_install_config_and_fallback_authority() -> None:
    manifest = build_chipyard_manifest()
    integration = manifest["integration"]
    assert integration["scala_install_path"] == CHIPYARD_SCALA_INSTALL_PATH
    assert integration["config_package"] == CHIPYARD_CONFIG_PACKAGE
    assert integration["config_class"] == CHIPYARD_CONFIG_CLASS
    assert integration["entry_api"] == "testchipip.soc.SubsystemInjectorKey"
    assert integration["patches_digital_top"] is False
    assert integration["loopback_fallback"] is True
    assert manifest["qualification"]["status"] == "pinned_injector_bundle_unelaborated"
    assert manifest["qualification"]["subsystem_elaboration_allowed"] is False
    assert "CHIPYARD_SUBSYSTEM_ELABORATION_UNRUN" in manifest["qualification"]["blockers"]
    assert "CHIPYARD_EXTERNAL_CARTRIDGE_BINDING_UNRUN" in manifest["qualification"]["blockers"]


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


def test_chipyard_bundle_files_match_manifest_hashes_and_use_lf(tmp_path: Path) -> None:
    outputs = write_chipyard_bundle(tmp_path)
    assert {path.name for path in outputs.values()} == {
        "PhysicalCompute.scala",
        "physical_compute_smoke.c",
        "chipyard-physical-compute-integration.json",
    }
    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    for key, name in (
        ("scala", "PhysicalCompute.scala"),
        ("smoke", "physical_compute_smoke.c"),
    ):
        payload = outputs[key].read_bytes()
        record = manifest["generated_artifacts"][name]
        assert record["sha256"] == sha256(payload).hexdigest()
        assert record["bytes"] == len(payload)
        assert b"\r\n" not in payload
    assert b"\r\n" not in outputs["manifest"].read_bytes()


def test_chipyard_cli_preserves_legacy_bundle_form_and_subcommand(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert chipyard_main(["--out-dir", str(first)]) == 0
    assert chipyard_main(
        [
            "bundle",
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
