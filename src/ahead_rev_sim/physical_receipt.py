"""Sealed receipts for physical-compute substrate attempts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .physical_constants import (
    SUBSTRATE_RECEIPT_SCHEMA_VERSION,
    DeterminismContract,
    EvidenceClass,
    ExecutionStatus,
)
from .physical_serialization import jsonable, sha256_json


@dataclass
class PhysicalSubstrateReceipt:
    descriptor_sha256: str
    substrate_id: str
    operator_class: str
    portable_binding: str
    optional_riscv_extension: str
    input_frame_sha256: str
    output_sha256: str | None
    state_before_sha256: str | None
    state_after_sha256: str | None
    entropy_trace_sha256: str | None
    determinism_contract: DeterminismContract
    exact_replay: bool
    fallback_used: bool
    execution_status: ExecutionStatus
    outputs: tuple[int, ...]
    role_map: Mapping[str, tuple[str, ...]]
    energy_evidence_class: EvidenceClass
    physical_energy_claim_allowed: bool
    physical_compute_claim_allowed: bool
    blockers: tuple[str, ...]
    claim_boundary: str
    receipt_sha256: str | None = None
    schema_version: str = SUBSTRATE_RECEIPT_SCHEMA_VERSION

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = jsonable(self)
        if not include_hash:
            payload.pop("receipt_sha256", None)
        return payload

    def seal(self) -> str:
        self.receipt_sha256 = sha256_json(self.to_dict(include_hash=False))
        return self.receipt_sha256

    def to_json(self, *, indent: int = 2) -> str:
        if self.receipt_sha256 is None:
            self.seal()
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"
