from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Memory:
    data: Dict[int, int] = field(default_factory=dict)

    def load_word(self, addr: int) -> int:
        return self.data.get(addr, 0)

    def store_word(self, addr: int, value: int) -> None:
        self.data[addr] = value
