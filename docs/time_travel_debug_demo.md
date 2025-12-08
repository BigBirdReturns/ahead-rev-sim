# Time travel debugging demo

The time travel debugging demo shows how reversible execution can help track
down a corrupted register without restarting or replaying a program.

The example program:

- Initializes r1 and r2 in irreversible mode.
- Uses reversible RADD to update r2.
- Applies a reversible RXOR that corrupts r2.
- Halts with a wrong final value in r2.

The demo then walks backward through the reversible history buffer until the
value of r2 changes. The instruction that produced that change is reported as
the source of corruption, and the machine state is restored to the expected
value before that step.
