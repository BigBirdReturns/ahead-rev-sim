"""Software reference operators for physical-compute cartridges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .physical_constants import DeterminismContract
from .physical_descriptor import PhysicalSubstrateDescriptor
from .physical_signal import EntropyTrace


@dataclass(frozen=True)
class OperatorResult:
    outputs: tuple[int, ...]
    state_before: tuple[int, ...]
    state_after: tuple[int, ...]


class PhysicalOperator(Protocol):
    descriptor: PhysicalSubstrateDescriptor

    def reset(self) -> None: ...

    def snapshot(self) -> tuple[int, ...]: ...

    def execute(
        self,
        samples: Sequence[int],
        entropy_trace: EntropyTrace | None = None,
    ) -> OperatorResult: ...


@dataclass
class LeakyIntegratorOperator:
    """Deterministic Q16 reference for an RC-like relaxation substrate."""

    descriptor: PhysicalSubstrateDescriptor
    state_q16: int = 0

    def __post_init__(self) -> None:
        alpha = int(self.descriptor.parameters.get("alpha_q16", 32768))
        if not 0 <= alpha <= 65536:
            raise ValueError("alpha_q16 must be in the closed range 0..65536")
        if self.descriptor.determinism != DeterminismContract.EXACT:
            raise ValueError("leaky integrator requires exact determinism")

    def reset(self) -> None:
        self.state_q16 = int(self.descriptor.parameters.get("reset_state_q16", 0))

    def snapshot(self) -> tuple[int, ...]:
        return (self.state_q16,)

    def execute(
        self,
        samples: Sequence[int],
        entropy_trace: EntropyTrace | None = None,
    ) -> OperatorResult:
        del entropy_trace
        before = self.snapshot()
        alpha = int(self.descriptor.parameters.get("alpha_q16", 32768))
        beta = 65536 - alpha
        outputs: list[int] = []
        for sample in samples:
            numerator = alpha * self.state_q16 + beta * int(sample)
            adjustment = 32768 if numerator >= 0 else -32768
            self.state_q16 = (numerator + adjustment) // 65536
            outputs.append(self.state_q16)
        return OperatorResult(tuple(outputs), before, self.snapshot())


@dataclass
class ThermalBitSamplerOperator:
    """Trace-replay model for a stochastic thermodynamic bit source."""

    descriptor: PhysicalSubstrateDescriptor
    sample_count: int = 0

    def __post_init__(self) -> None:
        if self.descriptor.determinism != DeterminismContract.REPLAY_WITH_TRACE:
            raise ValueError("thermal sampler requires replay_with_trace determinism")

    def reset(self) -> None:
        self.sample_count = 0

    def snapshot(self) -> tuple[int, ...]:
        return (self.sample_count,)

    def execute(
        self,
        samples: Sequence[int],
        entropy_trace: EntropyTrace | None = None,
    ) -> OperatorResult:
        if entropy_trace is None:
            raise ValueError("entropy trace is required for exact stochastic replay")
        if len(entropy_trace.words) < len(samples):
            raise ValueError("entropy trace is shorter than the requested sample count")
        before = self.snapshot()
        outputs: list[int] = []
        for threshold, entropy_word in zip(samples, entropy_trace.words):
            if threshold < 0 or threshold > 0xFFFFFFFF:
                raise ValueError("thermal threshold must fit unsigned 32-bit range")
            outputs.append(1 if entropy_word < int(threshold) else 0)
            self.sample_count += 1
        return OperatorResult(tuple(outputs), before, self.snapshot())
