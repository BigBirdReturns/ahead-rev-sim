"""Portable execution surface for interchangeable physical-compute cartridges."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .physical_constants import (
    ChannelDirection,
    DeterminismContract,
    EvidenceClass,
    ExecutionStatus,
    SignalRole,
)
from .physical_descriptor import PhysicalSubstrateDescriptor
from .physical_receipt import PhysicalSubstrateReceipt
from .physical_serialization import blocker_code, sha256_json
from .physical_signal import EntropyTrace, PhysicalSignalFrame
from .physical_operators import PhysicalOperator


@dataclass(frozen=True)
class PhysicalSubstrateCartridge:
    descriptor: PhysicalSubstrateDescriptor
    operator_factory: Callable[[PhysicalSubstrateDescriptor], PhysicalOperator]

    def create_operator(self) -> PhysicalOperator:
        operator = self.operator_factory(self.descriptor)
        operator.reset()
        return operator


@dataclass
class PhysicalComputeRuntime:
    """MMIO-contract runtime shared by physical, simulated, and fallback devices."""

    cartridges: dict[str, PhysicalSubstrateCartridge] = field(default_factory=dict)

    def register(self, cartridge: PhysicalSubstrateCartridge) -> None:
        substrate_id = cartridge.descriptor.substrate_id
        if substrate_id in self.cartridges:
            raise ValueError(f"substrate cartridge already registered: {substrate_id}")
        self.cartridges[substrate_id] = cartridge

    def execute(
        self,
        substrate_id: str,
        frame: PhysicalSignalFrame,
        *,
        entropy_trace: EntropyTrace | None = None,
    ) -> PhysicalSubstrateReceipt:
        try:
            cartridge = self.cartridges[substrate_id]
        except KeyError as exc:
            raise KeyError(f"unknown substrate cartridge: {substrate_id}") from exc

        descriptor = cartridge.descriptor
        blockers: list[str] = []
        outputs: tuple[int, ...] = ()
        state_before: tuple[int, ...] | None = None
        state_after: tuple[int, ...] | None = None

        try:
            channel = descriptor.channel(frame.channel_id)
            if channel.direction != ChannelDirection.INPUT:
                raise ValueError(f"channel {frame.channel_id!r} is not an input channel")
            if SignalRole.OPERAND not in channel.roles:
                raise ValueError(f"channel {frame.channel_id!r} is not an operand channel")
            if frame.unit != channel.unit:
                raise ValueError(
                    f"frame unit {frame.unit!r} does not match channel unit {channel.unit!r}"
                )
            if channel.calibration_required and frame.calibration_sha256 is None:
                raise ValueError(f"channel {frame.channel_id!r} requires calibration evidence")
            if (
                descriptor.determinism == DeterminismContract.REPLAY_WITH_TRACE
                and entropy_trace is None
            ):
                raise ValueError("entropy trace is required for replay_with_trace execution")
            result = cartridge.create_operator().execute(
                frame.samples,
                entropy_trace=entropy_trace,
            )
            outputs = result.outputs
            state_before = result.state_before
            state_after = result.state_after
        except (KeyError, ValueError) as exc:
            blockers.append(blocker_code(str(exc)))
            status = ExecutionStatus.REFUSED
        else:
            status = ExecutionStatus.ACCEPTED

        if descriptor.energy_contract.evidence_class != EvidenceClass.MEASURED:
            blockers.append("ENERGY_BOUNDARY_UNMEASURED")
        blockers.extend(
            (
                "PHYSICAL_SUBSTRATE_UNMEASURED",
                "OCCUPIED_VOLUME_UNMEASURED",
                "TIMING_AND_THERMAL_CLOSURE_UNMEASURED",
            )
        )
        exact_replay = status == ExecutionStatus.ACCEPTED and (
            descriptor.determinism == DeterminismContract.EXACT
            or (
                descriptor.determinism == DeterminismContract.REPLAY_WITH_TRACE
                and entropy_trace is not None
            )
        )

        receipt = PhysicalSubstrateReceipt(
            descriptor_sha256=descriptor.sha256,
            substrate_id=descriptor.substrate_id,
            operator_class=descriptor.operator_class,
            portable_binding=descriptor.portable_binding,
            optional_riscv_extension=descriptor.optional_riscv_extension,
            input_frame_sha256=frame.sha256,
            output_sha256=sha256_json(list(outputs)) if outputs else None,
            state_before_sha256=(
                sha256_json(list(state_before)) if state_before is not None else None
            ),
            state_after_sha256=(
                sha256_json(list(state_after)) if state_after is not None else None
            ),
            entropy_trace_sha256=entropy_trace.sha256 if entropy_trace else None,
            determinism_contract=descriptor.determinism,
            exact_replay=exact_replay,
            fallback_used=True,
            execution_status=status,
            outputs=outputs,
            role_map={role.value: descriptor.role_channels(role) for role in SignalRole},
            energy_evidence_class=descriptor.energy_contract.evidence_class,
            physical_energy_claim_allowed=False,
            physical_compute_claim_allowed=False,
            blockers=tuple(dict.fromkeys(blockers)),
            claim_boundary=(
                "The receipt establishes declared operator semantics, signal custody, "
                "fallback execution, and replay conditions. It does not establish that a "
                "physical substrate performed the transformation, supplied or recovered "
                "energy, occupied a declared volume, or met timing and thermal limits."
            ),
        )
        receipt.seal()
        return receipt
