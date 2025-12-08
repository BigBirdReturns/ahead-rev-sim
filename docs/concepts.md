# Concepts

ahead-rev-sim explores three core ideas.

## 1. Algebraic reversibility

Some instructions are logically reversible given the right inputs:

- `RXOR rd, rs1` is its own inverse
- `RSWAP rd, rs1` is its own inverse
- `RADD rd, rs1` can be undone with subtraction of the same `rs1`

The simulator uses these rules to undo reversible steps without saving full copies of register files. 
This keeps the model closer to what real reversible hardware can do.

## 2. Reversible control flow

Branches are handled with a minimal execution history. For `BEQ` the machine records:

- The program counter where the branch executed
- Whether the branch was taken

The reverse step uses this record to restore the previous program counter. 
The branch itself is counted as a reversible control flow operation.

## 3. Reversibility metrics

Every instruction updates a small metrics object:

- Reversible instruction count
- Irreversible instruction count
- Per opcode counts
- Reversibility ratio

These metrics tell you how much of a kernel can in principle be executed on an adiabatic or reversible unit.
