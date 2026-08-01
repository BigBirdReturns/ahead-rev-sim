"""Reference cartridges proving the physical-compute commodity contract."""

from __future__ import annotations

from .physical_constants import (
    ChannelDirection,
    CouplingMode,
    DeterminismContract,
    DynamicsClass,
    EnergySourceClass,
    EvidenceClass,
    RealizationClass,
    ResetContract,
    SignalRole,
)
from .physical_descriptor import ChannelSpec, EnergyContract, PhysicalSubstrateDescriptor
from .physical_operators import LeakyIntegratorOperator, ThermalBitSamplerOperator
from .physical_runtime import PhysicalComputeRuntime, PhysicalSubstrateCartridge


def rc_relaxation_cartridge(
    *,
    substrate_id: str = "rc-relaxation-reference-v1",
    alpha_q16: int = 32768,
) -> PhysicalSubstrateCartridge:
    descriptor = PhysicalSubstrateDescriptor(
        substrate_id=substrate_id,
        operator_class="leaky_integrator_q16",
        dynamics_class=DynamicsClass.DETERMINISTIC_RELAXATION,
        realization_class=RealizationClass.DESIGNED_DEVICE,
        coupling_mode=CouplingMode.STIMULATE_AND_OBSERVE,
        determinism=DeterminismContract.EXACT,
        reset_contract=ResetContract.EXACT,
        channels=(
            ChannelSpec(
                channel_id="field_input_q16",
                direction=ChannelDirection.INPUT,
                roles=(SignalRole.OPERAND,),
                physical_quantity="programmed_or_sensed_field",
                unit="q16",
            ),
            ChannelSpec(
                channel_id="relaxation_state_q16",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.DYNAMICS,),
                physical_quantity="relaxation_state",
                unit="q16",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="relaxed_output_q16",
                direction=ChannelDirection.OUTPUT,
                roles=(SignalRole.RESULT,),
                physical_quantity="relaxed_field",
                unit="q16",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="supply",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.ENERGY,),
                physical_quantity="energy_supply",
                unit="joule",
                calibration_required=False,
            ),
        ),
        state_words=1,
        environment_boundary="device terminals plus readout",
        parameters={"alpha_q16": alpha_q16, "reset_state_q16": 0},
        energy_contract=EnergyContract(
            source_class=EnergySourceClass.EXTERNAL,
            evidence_class=EvidenceClass.REFERENCE_MODEL,
        ),
        fallback_model_id="leaky-integrator-fixed-point/v1",
    )
    return PhysicalSubstrateCartridge(descriptor, LeakyIntegratorOperator)


def thermal_sampler_cartridge(
    *,
    substrate_id: str = "thermal-bit-sampler-reference-v1",
) -> PhysicalSubstrateCartridge:
    descriptor = PhysicalSubstrateDescriptor(
        substrate_id=substrate_id,
        operator_class="thermodynamic_bit_sampler_u32",
        dynamics_class=DynamicsClass.THERMODYNAMIC_STOCHASTIC,
        realization_class=RealizationClass.DESIGNED_DEVICE,
        coupling_mode=CouplingMode.STIMULATE_AND_OBSERVE,
        determinism=DeterminismContract.REPLAY_WITH_TRACE,
        reset_contract=ResetContract.STATISTICAL,
        channels=(
            ChannelSpec(
                channel_id="probability_threshold_u32",
                direction=ChannelDirection.INPUT,
                roles=(SignalRole.OPERAND,),
                physical_quantity="programmed_energy_bias_threshold",
                unit="u32",
            ),
            ChannelSpec(
                channel_id="thermal_fluctuation",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.DYNAMICS, SignalRole.CONTEXT),
                physical_quantity="stochastic_fluctuation",
                unit="u32",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="sampled_bit",
                direction=ChannelDirection.OUTPUT,
                roles=(SignalRole.RESULT,),
                physical_quantity="stochastic_bit",
                unit="bit",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="ambient_heat_bath",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.CONTEXT,),
                physical_quantity="thermal_environment",
                unit="kelvin",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="bias_supply",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.ENERGY,),
                physical_quantity="device_energy_supply",
                unit="joule",
                calibration_required=False,
            ),
        ),
        state_words=1,
        environment_boundary="biased device, heat bath, sampler, and readout",
        parameters={"entropy_word_bits": 32},
        energy_contract=EnergyContract(
            source_class=EnergySourceClass.EXTERNAL,
            evidence_class=EvidenceClass.REFERENCE_MODEL,
        ),
        fallback_model_id="thermal-sampler-trace-replay/v1",
    )
    return PhysicalSubstrateCartridge(descriptor, ThermalBitSamplerOperator)


def harvested_world_descriptor(
    *,
    substrate_id: str = "harvested-world-reservoir-contract-v1",
) -> PhysicalSubstrateDescriptor:
    """Contract-only example for environmental dynamics used as a reservoir.

    The trajectory can originate in a plant, structure, weather field, body, or
    other naturally evolving system.  No capability is claimed until a task
    benchmark establishes separation, memory, readout quality, and stability.
    """

    return PhysicalSubstrateDescriptor(
        substrate_id=substrate_id,
        operator_class="harvested_world_reservoir",
        dynamics_class=DynamicsClass.RESERVOIR,
        realization_class=RealizationClass.HARVESTED_ENVIRONMENT,
        coupling_mode=CouplingMode.OBSERVE_ONLY,
        determinism=DeterminismContract.DISTRIBUTIONAL,
        reset_contract=ResetContract.NONE,
        channels=(
            ChannelSpec(
                channel_id="world_trajectory_q16",
                direction=ChannelDirection.INPUT,
                roles=(SignalRole.OPERAND, SignalRole.DYNAMICS),
                physical_quantity="measured_environment_trajectory",
                unit="q16",
            ),
            ChannelSpec(
                channel_id="environment_context",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.CONTEXT,),
                physical_quantity="environment_state",
                unit="manifest",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="reservoir_readout_q16",
                direction=ChannelDirection.OUTPUT,
                roles=(SignalRole.RESULT,),
                physical_quantity="trained_readout",
                unit="q16",
                calibration_required=False,
            ),
            ChannelSpec(
                channel_id="sensor_readout_supply",
                direction=ChannelDirection.INTERNAL,
                roles=(SignalRole.ENERGY,),
                physical_quantity="acquisition_and_readout_energy",
                unit="joule",
                calibration_required=False,
            ),
        ),
        state_words=0,
        environment_boundary="declared field, observation window, sensors, and readout",
        parameters={"readout": "external_trained_linear", "capability": "unproven"},
        energy_contract=EnergyContract(
            source_class=EnergySourceClass.EXTERNAL,
            evidence_class=EvidenceClass.REFERENCE_MODEL,
        ),
        fallback_model_id="recorded-trajectory-replay/v1",
    )


def default_runtime() -> PhysicalComputeRuntime:
    runtime = PhysicalComputeRuntime()
    runtime.register(rc_relaxation_cartridge())
    runtime.register(thermal_sampler_cartridge())
    return runtime
