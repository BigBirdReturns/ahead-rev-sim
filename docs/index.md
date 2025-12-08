# ahead-rev-sim

ahead-rev-sim is a reversible compute simulator for a RISC V style core.

It lets you:

- Define small programs in a reversible friendly ISA
- Run them forward and then step them backward
- Mix reversible and irreversible instructions
- Measure how much of your workload can be undone
- Track a simple energy model for reversible versus irreversible work

This is a bridge between classical compute and future adiabatic or reversible hardware. 
It aims to let hardware and compiler teams experiment before silicon is ready.
