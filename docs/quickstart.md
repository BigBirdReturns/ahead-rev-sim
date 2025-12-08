# Quick Start

## Install

```bash
git clone https://github.com/BigBirdReturns/ahead-rev-sim
cd ahead-rev-sim

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
```

## Run the examples

```bash
python -m ahead_rev_sim.examples.run_example
python -m ahead_rev_sim.examples.run_loop
```

Or use the CLI:

```bash
ahead-rev-sim example
ahead-rev-sim loop
```

## Run the tests

```bash
pytest
```

If the tests pass, you have a working reversible compute simulator.
