"""Data contracts and deterministic sealing for execution proofs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from .machine import Machine


EXECUTION_PROOF_SCHEMA_VERSION = "ahead.execution-proof/v0.1"
EXECUTION_PROOF_ARTIFACT_TYPE = "history_complete_execution_proof"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ArchitectedState:
    registers: tuple[int, ...]
    memory: tuple[tuple[int, int], ...]
    pc: int
    halted: bool

    @classmethod
    def capture(cls, machine: "Machine") -> "ArchitectedState":
        return cls(
            registers=tuple(value & 0xFFFFFFFF for value in machine.registers),
            memory=tuple(
                sorted(
                    (int(addr), int(value) & 0xFFFFFFFF)
                    for addr, value in machine.memory.data.items()
                )
            ),
            pc=machine.pc,
            halted=machine.halted,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "registers": list(self.registers),
            "memory": {str(addr): value for addr, value in self.memory},
            "pc": self.pc,
            "halted": self.halted,
        }

    @property
    def sha256(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class UndoRecord:
    pc: int
    op: str
    payload: Mapping[str, Any]
    history_payload_bits: int

    def digest_payload(self) -> dict[str, Any]:
        return {
            "pc": self.pc,
            "op": self.op,
            "payload": dict(self.payload),
            "history_payload_bits": self.history_payload_bits,
        }


@dataclass
class ExecutionProof:
    schema_version: str
    artifact_type: str
    generated_by: str
    source: dict[str, Any]
    fixture: dict[str, Any]
    execution: dict[str, Any]
    accepted_output: dict[str, Any]
    restoration: dict[str, Any]
    qualification: dict[str, Any]
    claim_boundary: str
    control_question: str
    proof_sha256: str | None = None

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_hash:
            payload.pop("proof_sha256", None)
        return payload

    def seal(self) -> str:
        self.proof_sha256 = sha256_json(self.to_dict(include_hash=False))
        return self.proof_sha256

    def to_json(self, *, indent: int = 2) -> str:
        if self.proof_sha256 is None:
            self.seal()
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"
