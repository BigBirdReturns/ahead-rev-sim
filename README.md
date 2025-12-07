# ahead-rev-sim

Reversible compute playground for an Ahead Computing style RISC V extension.

This project models a very small RISC V like core with:

- A split between reversible and irreversible instructions
- A simple execution engine that can step forward and backward
- A basic energy model that charges more for irreversible work
- A tiny assembly parser so you can write `.asm` kernels
- A small metrics module to track reversible versus irreversible work
- A command line entry point so you can run kernels from the shell

The long term goal is to bridge:

- Legacy mode: run normal RISC V style code
- Hybrid mode: mix reversible and irreversible instructions
- Reversible mode: run fully reversible kernels and measure energy gains

This simulator is a software counterpart to a future open RISC V core that includes
reversible execution lanes. It is designed to let hardware and software teams explore:

- Which instruction patterns reverse cleanly
- How to structure compilers around reversible basic blocks
- How to size history buffers for reversible control flow
- How to surface energy and reversibility metrics to developers

## Features

- Register file with 32 integer registers
- Clear separation between reversible and irreversible opcodes
- Forward and reverse execution for reversible instructions using algebraic inversion
- Minimal history log for control flow (branches)
- Simple energy accounting per instruction
- Assembly parser for a small reversible ISA
- Metrics for reversible versus irreversible instruction counts
- CLI entry point for running examples and `.asm` kernels

This is not a full RISC V implementation. It is a focused environment to design and test
reversible instruction set ideas before silicon is frozen.

## Quick start

```bash
git clone <your-repo-url> ahead-rev-sim
cd ahead-rev-sim

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .

# Run Python examples
python -m ahead_rev_sim.examples.run_example
python -m ahead_rev_sim.examples.run_loop

# Or use the CLI
ahead-rev-sim example
ahead-rev-sim loop
ahead-rev-sim run path/to/program.asm
```

## Concept

Core ideas:

- Mark some instructions as logically reversible and give them algebraic inverses.
- Track an execution log only where history is required, mostly for branches.
- Allow the machine to walk that log backward to undo reversible work.
- Count reversible versus irreversible instructions to show where energy is spent.

Irreversible instructions still work but cost more energy and cannot be undone.

This structure is the bridge between current RISC V pipelines and future reversible or
adiabatic execution units.


## Documentation

MkDocs configuration is provided in `mkdocs.yml` with content under `docs/`.
You can build the site locally with:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```
