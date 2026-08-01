# RISC-V Target-Model Execution Proof

The portable MMIO contract now has an actual RISC-V execution lane. The lane compiles a statically linked RV64GC binary against the generated `physical-compute-mmio/v1` C header, executes it under `qemu-riscv64`, compares the complete stdout trace with a committed accepted trace, inspects the ELF machine identity, and seals the binary, trace, ABI, toolchain, and semantic observations into a target proof.

This transaction is deliberately independent of the Python lifecycle model and the generated Chipyard Scala. The C program contains a second device-state implementation. It exercises the generated header as a host-visible ABI, refuses an ambiguous command, completes reset and load through the software fallback, preserves descriptor and input pointers, and reports terminal receipt state.

## Workflow

The GitHub Actions workflow is:

```text
.github/workflows/riscv-target.yml
```

It installs the commodity GNU RISC-V cross compiler and QEMU user-mode emulator, then performs:

```bash
ahead-rev-mmio \
  --format c-header \
  --out artifacts/riscv-target/ahead_physical_compute_mmio_v1.h

riscv64-linux-gnu-gcc \
  -static \
  -std=c11 \
  -O2 \
  -Wall \
  -Wextra \
  -Werror \
  -march=rv64gc \
  -mabi=lp64d \
  -I artifacts/riscv-target \
  examples/riscv/mmio_target_smoke.c \
  -o artifacts/riscv-target/mmio_target_smoke.riscv64

qemu-riscv64 artifacts/riscv-target/mmio_target_smoke.riscv64 \
  | tee artifacts/riscv-target/mmio_target_smoke.trace

diff -u \
  examples/riscv/mmio_target_smoke.expected \
  artifacts/riscv-target/mmio_target_smoke.trace

ahead-rev-riscv-target-proof \
  --binary artifacts/riscv-target/mmio_target_smoke.riscv64 \
  --trace artifacts/riscv-target/mmio_target_smoke.trace \
  --expected examples/riscv/mmio_target_smoke.expected \
  --out artifacts/riscv-target/riscv-target-proof.json
```

The workflow uploads the generated header, RISC-V binary, ELF header, target trace, and sealed proof as one evidence artifact.

## Accepted target trace

```text
abi=physical-compute-mmio/v1 isa=rv64gc
identity=41504859 capabilities=00000009
ambiguous status=00000009 result=refused
reset status=00000025 result=done receipt=valid
load status=00000025 result=done receipt=valid descriptor=0000000010001000 input=0000000010002000
result=pass
```

The target proof checks the trace byte for byte, then checks its semantics independently. The eight semantic checks cover the portable binding, RV64GC identity, MMIO identity word, exact-plus-fallback capability mask, ambiguous-command refusal, reset completion, load completion and pointer custody, and final pass state.

## Proof boundary

A passing proof establishes that:

- the generated C header is consumable by a real RISC-V GNU toolchain;
- the produced binary is ELF64 and identifies RISC-V as its machine;
- the RV64GC binary executes under `qemu-riscv64`;
- a separate C device model reproduces the accepted admission, refusal, fallback, and receipt lifecycle;
- the target binary and trace are SHA-256 bound to the ABI and toolchain identities.

It does not establish that the Chipyard peripheral elaborates, that RTL executes, that a physical cartridge performed the transformation, or that energy, latency, thermal state, occupied volume, reliability, or fabrication claims close. Those remain explicit blockers in the proof.

The controlling question is: does the same accepted MMIO transaction survive an actual RISC-V binary and independent device model before we spend any custom-ISA or silicon budget?
