from __future__ import annotations
from dataclasses import dataclass


@dataclass
class EnergyModel:
    reversible_cost: float = 0.1
    irreversible_cost: float = 1.0

    total_energy: float = 0.0

    def charge_reversible(self) -> None:
        self.total_energy += self.reversible_cost

    def charge_irreversible(self) -> None:
        self.total_energy += self.irreversible_cost
