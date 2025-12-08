# Command Line Interface

After you install the package with `pip install -e .` you get a small CLI.

```bash
ahead-rev-sim example
ahead-rev-sim loop
ahead-rev-sim run path/to/program.asm --max-steps 1000
```

- `example` runs a reversible increment program.
- `loop` runs a mixed reversible and irreversible loop.
- `run` executes an assembly file and prints:

  - Final register values
  - Total energy
  - Reversibility metrics
