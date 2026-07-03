from ahead_rev_sim.machine import Machine
from ahead_rev_sim.examples.prog_increment import make_program
from ahead_rev_sim.parser import AssemblyParser
from ahead_rev_sim.examples.run_loop import SOURCE
import pytest


def test_reversible_increment_round_trip():
    m = Machine()
    prog = make_program()
    m.load_program(prog)
    m.registers[1] = 5
    m.registers[2] = 1

    while not m.halted:
        m.step()

    assert m.registers[1] == 8

    for _ in range(3):
        m.reverse_step()

    assert m.registers[1] == 5


def test_loop_halts_and_accumulates():
    parser = AssemblyParser()
    program = parser.parse(SOURCE)
    m = Machine()
    m.load_program(program, labels=parser.labels)

    steps = m.run(max_steps=1000)
    assert steps < 1000  # should halt before step limit
    assert m.halted
    # r2 should be sum 10+9+...+1 = 55
    assert m.registers[2] == 55



def test_parser_resets_labels_between_parses():
    parser = AssemblyParser()
    parser.parse("""start:
HALT""")
    parser.parse("""other:
HALT""")
    assert set(parser.labels.keys()) == {"other"}


def test_invalid_register_raises_value_error():
    parser = AssemblyParser()
    with pytest.raises(ValueError):
        parser.parse("RMODADD r-1, r2")


def test_load_program_reset_state_default_and_opt_out():
    m = Machine()
    parser = AssemblyParser()
    prog = parser.parse("HALT")
    m.registers[1] = 123
    m.memory.store_word(0x10, 77)

    m.load_program(prog, labels=parser.labels)
    assert m.registers[1] == 0
    assert m.memory.load_word(0x10) == 0

    m.registers[1] = 456
    m.memory.store_word(0x10, 88)
    m.load_program(prog, labels=parser.labels, reset_state=False)
    assert m.registers[1] == 456
    assert m.memory.load_word(0x10) == 88


def test_radd_legacy_mnemonic_warns_and_maps_to_rmodadd():
    from ahead_rev_sim.isa import OpCode

    parser = AssemblyParser()
    with pytest.warns(DeprecationWarning, match="RADD is deprecated"):
        program = parser.parse("RADD r1, r2")
    assert program[0].op == OpCode.RMODADD


def test_rmodadd_round_trip_wraps_modularly():
    from ahead_rev_sim.isa import Instruction, OpCode

    m = Machine()
    m.load_program([
        Instruction(op=OpCode.RMODADD, rd=1, rs1=2),
        Instruction(op=OpCode.HALT),
    ])
    m.registers[1] = 0xFFFFFFFF
    m.registers[2] = 2

    m.step()
    assert m.registers[1] == 1  # wrapped mod 2^32

    m.reverse_step()
    assert m.registers[1] == 0xFFFFFFFF


def test_rexch_exchanges_register_and_memory():
    from ahead_rev_sim.isa import Instruction, OpCode

    m = Machine()
    m.load_program([
        Instruction(op=OpCode.REXCH, rd=1, rs1=2, imm=4),
        Instruction(op=OpCode.HALT),
    ])
    m.registers[1] = 42
    m.registers[2] = 0x100
    m.memory.store_word(0x104, 99)

    m.step()
    assert m.registers[1] == 99
    assert m.memory.load_word(0x104) == 42


def test_rexch_reverse_step_restores_exact_state():
    from ahead_rev_sim.isa import Instruction, OpCode

    m = Machine()
    m.load_program([
        Instruction(op=OpCode.REXCH, rd=1, rs1=2, imm=0),
        Instruction(op=OpCode.HALT),
    ])
    m.registers[1] = 42
    m.registers[2] = 16
    m.memory.store_word(16, 100)

    m.step()
    m.reverse_step()
    assert m.registers[1] == 42
    assert m.registers[2] == 16
    assert m.memory.load_word(16) == 100
    assert m.pc == 0
    assert not m.exec_log


def test_rexch_rejects_rd_aliasing_rs1():
    from ahead_rev_sim.isa import Instruction, OpCode

    m = Machine()
    m.load_program([
        Instruction(op=OpCode.REXCH, rd=1, rs1=1, imm=0),
        Instruction(op=OpCode.HALT),
    ])
    m.registers[1] = 16
    with pytest.raises(ValueError, match="rd != rs1"):
        m.step()


def test_parser_accepts_rexch_with_negative_immediate():
    from ahead_rev_sim.isa import OpCode

    parser = AssemblyParser()
    program = parser.parse("REXCH r1, r2, -4")
    instr = program[0]
    assert instr.op == OpCode.REXCH
    assert instr.rd == 1
    assert instr.rs1 == 2
    assert instr.imm == -4


def test_rexch_counts_as_reversible_zero_history_payload():
    from ahead_rev_sim.isa import Instruction, OpCode

    m = Machine()
    m.load_program([
        Instruction(op=OpCode.REXCH, rd=1, rs1=2, imm=0),
        Instruction(op=OpCode.HALT),
    ])
    m.registers[2] = 8
    m.step()
    pc, instr, snapshot = m.exec_log[-1]
    assert instr.op == OpCode.REXCH
    assert snapshot is None  # self-inverse: nothing stored
    assert m.metrics.reversible_count == 1


def test_debugger_class_name_typo_fixed():
    from ahead_rev_sim import TimeTravelDebugger  # noqa: F401
