"""
Reversible Memory Demo for ahead-rev-sim v0.8.

Run with: ahead-rev-memory
"""

from __future__ import annotations

from ahead_rev_sim.machine import Machine
from ahead_rev_sim.isa import Instruction, OpCode
from ahead_rev_sim.history import HistoryBuffer, EntryType
from ahead_rev_sim.reversible_memory import MemoryController, MemoryRegionType


def run_rload_round_trip() -> None:
    print("=" * 65)
    print("RLOAD/RSTORE ROUND-TRIP")
    print("=" * 65)
    print()

    m = Machine()
    program = [
        Instruction(op=OpCode.ADD, rd=1, rs1=0, imm=42),
        Instruction(op=OpCode.ADD, rd=2, rs1=0, imm=16),
        Instruction(op=OpCode.ADD, rd=3, rs1=0, imm=100),
        Instruction(op=OpCode.STORE, rs1=2, rs2=3, imm=0),
        Instruction(op=OpCode.RLOAD, rd=1, rs1=2, imm=0),
        Instruction(op=OpCode.HALT),
    ]

    m.load_program(program)

    for _ in range(4):
        m.step()

    print("After setup:")
    print(f"  r1      = {m.registers[1]}")
    print(f"  mem[16] = {m.memory.load_word(16)}")
    print()

    m.step()
    print("After RLOAD:")
    print(f"  r1      = {m.registers[1]}")
    print(f"  mem[16] = {m.memory.load_word(16)}")
    print()

    m.reverse_step()
    print("After reverse_step:")
    print(f"  r1      = {m.registers[1]}")
    print(f"  mem[16] = {m.memory.load_word(16)}")
    print()


def run_history_cost_analysis() -> None:
    print("=" * 65)
    print("HISTORY BUFFER COST")
    print("=" * 65)
    history = HistoryBuffer()
    for i in range(10):
        history.push(pc=i, op_name="RLOAD", entry_type=EntryType.REVERSIBLE_OP, payload=None)
    rload_bits = history.current_bits
    for i in range(5):
        history.push(pc=10 + i, op_name="BEQ", entry_type=EntryType.BRANCH_DECISION, payload=None)
    branch_bits = history.current_bits - rload_bits
    print(f"10 x RLOAD ops: {rload_bits} bits")
    print(f"5 x BEQ ops:    {branch_bits} bits")
    print()


def run_hot_cold_comparison() -> None:
    print("=" * 65)
    print("HOT/COLD MEMORY CONTROLLER COMPARISON")
    print("=" * 65)
    ctrl = MemoryController()
    ctrl.memory.configure_region(0x1000, 0x2000, MemoryRegionType.REVERSIBLE)
    for i in range(10):
        ctrl.hot_load(0x100 + i * 4)
        ctrl.hot_store(0x200 + i * 4, i)
    reg_val = 99
    for i in range(10):
        old, _ = ctrl.cold_exchange(0x1000 + i * 4, reg_val)
        reg_val = old
    s = ctrl.summary()
    print(f"HOT requests:   {s['hot_requests']}")
    print(f"COLD requests:  {s['cold_requests']}")
    print(f"Total cycles:   {s['total_cycles']}")
    print()


def main() -> None:
    print("AHEAD-REV-SIM v0.8: Reversible Memory Demo")
    run_rload_round_trip()
    run_history_cost_analysis()
    run_hot_cold_comparison()


if __name__ == "__main__":
    main()
