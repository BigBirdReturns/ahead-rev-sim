"""Signal and entropy custody for physical-compute execution."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from .physical_constants import EvidenceClass
from .physical_serialization import is_sha256, jsonable, sha256_json


@dataclass(frozen=True)
class PhysicalSignalFrame:
    channel_id: str
    samples: tuple[int, ...]
    start_tick: int
    tick_period_ns: int
    unit: str
    calibration_sha256: str | None
    environment_sha256: str | None = None
    evidence_class: EvidenceClass = EvidenceClass.SIMULATED

    def __post_init__(self) -> None:
        if not self.channel_id or not self.samples or not self.unit:
            raise ValueError("frame channel, samples, and unit are required")
        if self.start_tick < 0 or self.tick_period_ns <= 0:
            raise ValueError("frame timing must be non-negative with a positive period")
        for name, digest in (
            ("calibration_sha256", self.calibration_sha256),
            ("environment_sha256", self.environment_sha256),
        ):
            if digest is not None and not is_sha256(digest):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def sha256(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class EntropyTrace:
    source: str
    words: tuple[int, ...]
    evidence_class: EvidenceClass
    sample_window_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.source or not self.words:
            raise ValueError("entropy source and words are required")
        if any(word < 0 or word > 0xFFFFFFFF for word in self.words):
            raise ValueError("entropy words must fit unsigned 32-bit values")
        if self.sample_window_sha256 is not None and not is_sha256(self.sample_window_sha256):
            raise ValueError("sample_window_sha256 must be a SHA-256 digest")

    @classmethod
    def from_seed(cls, seed: int, count: int) -> "EntropyTrace":
        if count <= 0:
            raise ValueError("count must be positive")
        generator = random.Random(seed)
        return cls(
            source=f"reference-seed:{seed}",
            words=tuple(generator.getrandbits(32) for _ in range(count)),
            evidence_class=EvidenceClass.REFERENCE_MODEL,
        )

    @property
    def sha256(self) -> str:
        return sha256_json(jsonable(self))
