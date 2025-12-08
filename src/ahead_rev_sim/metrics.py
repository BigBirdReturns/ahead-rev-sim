from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

from .isa import OpCode


@dataclass
class ReversibilityMetrics:
    reversible_count: int = 0
    irreversible_count: int = 0
    per_op_counts: Dict[str, int] = field(default_factory=dict)

    def record(self, op: OpCode, reversible: bool) -> None:
        if reversible:
            self.reversible_count += 1
        else:
            self.irreversible_count += 1
        name = op.name
        self.per_op_counts[name] = self.per_op_counts.get(name, 0) + 1

    @property
    def total(self) -> int:
        return self.reversible_count + self.irreversible_count

    @property
    def reversible_ratio(self) -> float:
        if self.total == 0:
            return 0.0
        return self.reversible_count / self.total

    def summary(self) -> str:
        return (
            f"reversible={self.reversible_count}, "
            f"irreversible={self.irreversible_count}, "
            f"ratio={self.reversible_ratio:.2f}"
        )
