# Reversibility Metrics

The `ReversibilityMetrics` class tracks:

- Count of reversible instructions
- Count of irreversible instructions
- Per opcode counts
- A reversibility ratio

The simulator updates metrics on each executed instruction.

These metrics enable:

- Comparing different kernels
- Estimating how much of a workload can run on reversible units
- Guiding compiler optimizations that try to increase reversible coverage
