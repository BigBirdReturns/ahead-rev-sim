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
        parser.parse("RADD r-1, r2")


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



def test_reversible_memory_exchange_round_trip():
    parser = AssemblyParser()
    program = parser.parse("""
ADD r1, r0, 256
ADD r2, r0, 42
RLOAD r2, r1, 0
RLOAD r2, r1, 0
HALT
""")
    m = Machine()
    m.memory.store_word(0x100, 99)
    m.load_program(program, labels=parser.labels, reset_state=False)

    m.run(max_steps=20)

    assert m.registers[2] == 42
    assert m.memory.load_word(0x100) == 99


def test_parser_accepts_rstore_and_rload():
    parser = AssemblyParser()
    program = parser.parse("""
RLOAD r1, r2, 0
RSTORE r3, r4, 8
HALT
""")
    assert program[0].op.name == "RLOAD"
    assert program[1].op.name == "RSTORE"
