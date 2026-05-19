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


## Current branch and project hygiene

This repository currently works as a single-branch simulator workflow and is intentionally lightweight. For extension work, prefer adding feature docs under `docs/` first, then code and tests in lockstep.
