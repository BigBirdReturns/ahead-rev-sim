from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.physical_substrate import (
    DeterminismContract,
    EntropyTrace,
    EvidenceClass,
    ExecutionStatus,
    OPTIONAL_RISCV_EXTENSION,
    PHYSICAL_COMPUTE_MMIO_V1,
    PORTABLE_BINDING,
    PhysicalComputeRuntime,
    PhysicalSignalFrame,
    RealizationClass,
    CouplingMode,
    SignalRole,
    default_runtime,
    harvested_world_descriptor,
    rc_relaxation_cartridge,
    thermal_sampler_cartridge,
)
from ahead_rev_sim.substrate_cli import main as substrate_main

ROOT = Path(__file__).resolve().parents[1]
CAL = "a" * 64


def test_roles_are_typed_separately() -> None:
    descriptor = thermal_sampler_cartridge().descriptor
    assert descriptor.role_channels(SignalRole.OPERAND) == (
        "probability_threshold_u32",
    )
    assert descriptor.role_channels(SignalRole.RESULT) == ("sampled_bit",)
    assert descriptor.role_channels(SignalRole.DYNAMICS) == ("thermal_fluctuation",)
    assert descriptor.role_channels(SignalRole.ENERGY) == ("bias_supply",)
    assert descriptor.role_channels(SignalRole.CONTEXT) == (
        "thermal_fluctuation",
        "ambient_heat_bath",
    )


def test_commodity_binding_is_mmio_first_with_optional_xphys() -> None:
    descriptor = rc_relaxation_cartridge().descriptor
    assert descriptor.portable_binding == PORTABLE_BINDING
    assert descriptor.optional_riscv_extension == OPTIONAL_RISCV_EXTENSION
    assert OPTIONAL_RISCV_EXTENSION == "Xphys"
    assert PHYSICAL_COMPUTE_MMIO_V1["command"] == 0x08
    assert PHYSICAL_COMPUTE_MMIO_V1["receipt_ptr_lo"] == 0x28


def test_relaxation_reference_is_exact_and_deterministic() -> None:
    runtime = default_runtime()
    frame = PhysicalSignalFrame(
        channel_id="field_input_q16",
        samples=(65536, 65536, 0),
        start_tick=0,
        tick_period_ns=1000,
        unit="q16",
        calibration_sha256=CAL,
    )
    first = runtime.execute("rc-relaxation-reference-v1", frame)
    second = runtime.execute("rc-relaxation-reference-v1", frame)
    assert first.execution_status == ExecutionStatus.ACCEPTED
    assert first.outputs == (32768, 49152, 24576)
    assert first.exact_replay is True
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.fallback_used is True
    assert first.physical_compute_claim_allowed is False
    assert "PHYSICAL_SUBSTRATE_UNMEASURED" in first.blockers


def test_missing_calibration_is_refused() -> None:
    frame = PhysicalSignalFrame(
        channel_id="field_input_q16",
        samples=(1,),
        start_tick=0,
        tick_period_ns=1000,
        unit="q16",
        calibration_sha256=None,
    )
    receipt = default_runtime().execute("rc-relaxation-reference-v1", frame)
    assert receipt.execution_status == ExecutionStatus.REFUSED
    assert any("REQUIRES_CALIBRATION_EVIDENCE" in blocker for blocker in receipt.blockers)


def test_unknown_channel_is_refused() -> None:
    frame = PhysicalSignalFrame(
        channel_id="mystery",
        samples=(1,),
        start_tick=0,
        tick_period_ns=1000,
        unit="q16",
        calibration_sha256=CAL,
    )
    receipt = default_runtime().execute("rc-relaxation-reference-v1", frame)
    assert receipt.execution_status == ExecutionStatus.REFUSED
    assert any("UNKNOWN_SUBSTRATE_CHANNEL" in blocker for blocker in receipt.blockers)


def test_stochastic_execution_requires_entropy_custody() -> None:
    frame = PhysicalSignalFrame(
        channel_id="probability_threshold_u32",
        samples=(0x80000000, 0x80000000),
        start_tick=0,
        tick_period_ns=1000,
        unit="u32",
        calibration_sha256=CAL,
    )
    receipt = default_runtime().execute("thermal-bit-sampler-reference-v1", frame)
    assert receipt.execution_status == ExecutionStatus.REFUSED
    assert receipt.exact_replay is False
    assert any("ENTROPY_TRACE_IS_REQUIRED" in blocker for blocker in receipt.blockers)


def test_stochastic_trace_replays_exactly() -> None:
    frame = PhysicalSignalFrame(
        channel_id="probability_threshold_u32",
        samples=(0x80000000, 0x80000000, 0x80000000),
        start_tick=0,
        tick_period_ns=1000,
        unit="u32",
        calibration_sha256=CAL,
    )
    trace = EntropyTrace.from_seed(7, 3)
    runtime = default_runtime()
    first = runtime.execute(
        "thermal-bit-sampler-reference-v1", frame, entropy_trace=trace
    )
    second = runtime.execute(
        "thermal-bit-sampler-reference-v1", frame, entropy_trace=trace
    )
    assert first.execution_status == ExecutionStatus.ACCEPTED
    assert first.determinism_contract == DeterminismContract.REPLAY_WITH_TRACE
    assert first.exact_replay is True
    assert first.outputs == second.outputs
    assert first.entropy_trace_sha256 == trace.sha256
    assert first.receipt_sha256 == second.receipt_sha256


def test_energy_role_does_not_create_energy_claim() -> None:
    descriptor = thermal_sampler_cartridge().descriptor
    assert descriptor.role_channels(SignalRole.ENERGY)
    assert descriptor.energy_contract.evidence_class == EvidenceClass.REFERENCE_MODEL
    assert descriptor.energy_contract.physical_energy_claim_allowed is False


def test_cartridge_substitution_uses_same_runtime_contract() -> None:
    runtime = PhysicalComputeRuntime()
    runtime.register(rc_relaxation_cartridge(substrate_id="cartridge-a"))
    frame = PhysicalSignalFrame(
        channel_id="field_input_q16",
        samples=(100, 200),
        start_tick=0,
        tick_period_ns=1000,
        unit="q16",
        calibration_sha256=CAL,
    )
    receipt = runtime.execute("cartridge-a", frame)
    assert receipt.execution_status == ExecutionStatus.ACCEPTED
    assert receipt.fallback_used is True
    assert receipt.portable_binding == PORTABLE_BINDING


def test_duplicate_registration_is_refused() -> None:
    runtime = PhysicalComputeRuntime()
    cartridge = rc_relaxation_cartridge()
    runtime.register(cartridge)
    with pytest.raises(ValueError, match="already registered"):
        runtime.register(cartridge)



def test_harvested_world_is_a_first_class_non_chip_substrate() -> None:
    descriptor = harvested_world_descriptor()
    assert descriptor.realization_class == RealizationClass.HARVESTED_ENVIRONMENT
    assert descriptor.coupling_mode == CouplingMode.OBSERVE_ONLY
    assert descriptor.role_channels(SignalRole.OPERAND) == ("world_trajectory_q16",)
    assert descriptor.role_channels(SignalRole.DYNAMICS) == ("world_trajectory_q16",)
    assert descriptor.determinism == DeterminismContract.DISTRIBUTIONAL
    assert descriptor.parameters["capability"] == "unproven"


def test_reference_cartridges_declare_physical_target_and_boundary() -> None:
    for descriptor in (
        rc_relaxation_cartridge().descriptor,
        thermal_sampler_cartridge().descriptor,
    ):
        assert descriptor.realization_class == RealizationClass.DESIGNED_DEVICE
        assert descriptor.coupling_mode == CouplingMode.STIMULATE_AND_OBSERVE
        assert descriptor.environment_boundary


def test_descriptor_schema_accepts_reference_cartridges() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "physical-substrate.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(rc_relaxation_cartridge().descriptor.to_dict())
    validator.validate(thermal_sampler_cartridge().descriptor.to_dict())
    validator.validate(harvested_world_descriptor().to_dict())


def test_receipt_schema_accepts_reference_receipt() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "physical-substrate-receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    frame = PhysicalSignalFrame(
        channel_id="field_input_q16",
        samples=(1, 2, 3),
        start_tick=0,
        tick_period_ns=1000,
        unit="q16",
        calibration_sha256=CAL,
    )
    receipt = default_runtime().execute("rc-relaxation-reference-v1", frame)
    Draft202012Validator(schema).validate(receipt.to_dict())


def test_cli_writes_sealed_receipt(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    rc = substrate_main(
        [
            "rc-relaxation-reference-v1",
            "--samples",
            "65536,65536,0",
            "--calibration-sha256",
            CAL,
            "--out",
            str(output),
        ]
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["execution_status"] == "accepted"
    assert len(payload["receipt_sha256"]) == 64
    assert payload["optional_riscv_extension"] == "Xphys"
