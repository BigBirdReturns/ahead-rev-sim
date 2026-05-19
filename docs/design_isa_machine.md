# ISA and Machine Design

The simulator separates instructions into reversible and irreversible groups.

## Reversible instructions

- `RXOR` bitwise XOR, self inverse
- `RADD` addition with algebraic inverse
- `RSWAP` register swap, self inverse
- `BEQ` branch, reversible at the control flow level

The `Machine` keeps an execution log for reversible steps:

- For data operations it logs the program counter and opcode.
- For branches it logs the program counter and whether the branch was taken.

A reverse step walks that log backward and applies the inverse operation.

## Irreversible instructions

- `ADD`
- `SUB`
- `LOAD`
- `STORE`
- `HALT`

These update the machine state but cannot be undone. They cost more in the energy model.


## Extensibility notes

- `Machine.load_program(..., reset_state=True)` now supports deterministic clean runs by default while still allowing stateful experiments when set to `False`.
- Parser labels are reset every parse call, so a single parser instance can be safely reused across multiple source files in CLI or notebooks.
- Register access now validates machine bounds (`num_regs`) before execution to make architecture variants safer to prototype.
