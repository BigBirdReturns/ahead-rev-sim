# Provider-neutral RTL attachment proof

The RTL attachment closes the gap between a generated MMIO register block and an executed, replaceable cartridge transaction. It compiles and runs the generated `physical-compute-mmio/v1` SystemVerilog control plane with two independently replaceable actors:

1. An opaque-handle resolver that owns host address interpretation and bounded memory access.
2. A cartridge state machine that owns only its declared reset, load, evolve, read, capture, refusal, fault, and receipt behavior.

The attachment does not give either actor authority over the accepted workload, fallback, proof rule, or complete-system claim.

## Transaction shape

```text
RISC-V host or independent MMIO driver
        ↓ physical-compute-mmio/v1
MMIO command and state bridge
        ↓ physical-cartridge-link/v1
replaceable cartridge state machine
        ↓ opaque handle requests
physical-cartridge-handle-resolver/v1
        ↓ bounded fixture memory
accepted trace and execution proof
```

The cartridge receives opaque 64-bit handles rather than host pointers. The resolver alone maps those handles to reference descriptor, input, output, and receipt locations. A provider may replace the resolver or cartridge independently, but the replacement must reproduce the same command, terminal-state, fallback, and receipt contract.

## Executed lifecycle

The Icarus transaction exercises every command and three distinct failure classes:

| Transaction | Expected result | Status |
| --- | --- | --- |
| Ambiguous `RESET | READ` command | Refused before cartridge dispatch | `0x00000009` |
| Reset | Done with a valid receipt | `0x00000025` |
| Load with invalid descriptor content | Refused with a valid receipt | `0x00000029` |
| Load through an unmapped resolver handle | Fault with a valid receipt | `0x00000031` |
| Load with valid descriptor and input | Done with a valid receipt | `0x00000025` |
| Evolve | Input is consumed and transformed output is written | `0x00000025` |
| Read | Output is recovered into cartridge state | `0x00000025` |
| Capture | Receipt material is written through the resolver | `0x00000025` |

The reference transformation begins with input word `0x2A`, loads it as cartridge state, adds the same input during evolve, and writes output word `0x54`. The capture command writes the deterministic receipt word `0x52544C50524F4F46`, the ASCII payload `RTLPROOF`.

## Generated authority artifacts

`ahead-rev-rtl bundle` writes:

```text
physical-cartridge-link-v1.json
rtl-attachment-manifest.json
ahead_reference_handle_resolver_v1.sv
ahead_reference_reversible_cartridge_v1.sv
ahead_physical_compute_attachment_tb.sv
rtl-attachment.expected
```

The separate `ahead-rev-mmio` command generates `ahead_physical_compute_mmio_v1.sv` from the MMIO ABI authority. The manifest seals every generated attachment file. The proof admission path additionally requires the supplied MMIO source to match the current generated ABI byte for byte.

## Proof admission

`ahead-rev-rtl proof` admits an execution only when all of the following are true:

- the executable is nonempty;
- the observed trace is byte-identical to the accepted trace;
- the manifest is identical to the current deterministic manifest;
- the resolver, cartridge, and testbench match their sealed manifest records;
- the MMIO SystemVerilog matches the current ABI generator output;
- exactly four uniquely named source files are supplied;
- the trace contains one ordered record for every required lifecycle stage;
- every semantic trace check passes;
- the compiler and runtime versions are recorded.

The proof retains source hashes, executable hash and size, trace hashes, ABI hash, contract hash, manifest hash, tool versions, semantic observations, blockers, and a deterministic proof seal.

## Reproduce the transaction

Install the development surface and Icarus Verilog, then run:

```bash
mkdir -p artifacts/rtl-attachment

ahead-rev-mmio \
  --format systemverilog \
  --out artifacts/rtl-attachment/ahead_physical_compute_mmio_v1.sv

ahead-rev-rtl bundle \
  --out-dir artifacts/rtl-attachment

iverilog \
  -g2012 \
  -Wall \
  -s ahead_physical_compute_attachment_tb \
  -o artifacts/rtl-attachment/rtl-attachment.vvp \
  artifacts/rtl-attachment/ahead_physical_compute_mmio_v1.sv \
  artifacts/rtl-attachment/ahead_reference_handle_resolver_v1.sv \
  artifacts/rtl-attachment/ahead_reference_reversible_cartridge_v1.sv \
  artifacts/rtl-attachment/ahead_physical_compute_attachment_tb.sv

vvp artifacts/rtl-attachment/rtl-attachment.vvp \
  | tee artifacts/rtl-attachment/rtl-attachment.trace

diff -u \
  artifacts/rtl-attachment/rtl-attachment.expected \
  artifacts/rtl-attachment/rtl-attachment.trace

ahead-rev-rtl proof \
  --executable artifacts/rtl-attachment/rtl-attachment.vvp \
  --trace artifacts/rtl-attachment/rtl-attachment.trace \
  --expected artifacts/rtl-attachment/rtl-attachment.expected \
  --manifest artifacts/rtl-attachment/rtl-attachment-manifest.json \
  --source artifacts/rtl-attachment/ahead_physical_compute_mmio_v1.sv \
  --source artifacts/rtl-attachment/ahead_reference_handle_resolver_v1.sv \
  --source artifacts/rtl-attachment/ahead_reference_reversible_cartridge_v1.sv \
  --source artifacts/rtl-attachment/ahead_physical_compute_attachment_tb.sv \
  --out artifacts/rtl-attachment/rtl-attachment-proof.json
```

## Evidence ledger

The evidence tier is executed open-source RTL simulation. The venue is Icarus Verilog on the GitHub Actions Ubuntu runner. The target is the generated MMIO bridge, independent opaque-handle resolver, and replaceable reference cartridge. The upside is actual compiled lifecycle evidence across admission, refusal, fault, state transformation, output, and receipt paths. The downside is that the transaction remains a reference simulator environment. The principal failure mode is promoting RTL simulation into a Chipyard subsystem, FPGA, silicon, physical-substrate, or complete-system EVP claim.

The following claims remain blocked:

```text
CHIPYARD_SUBSYSTEM_ELABORATION_UNRUN
FPGA_OR_SILICON_EXECUTION_UNRUN
PHYSICAL_SUBSTRATE_UNMEASURED
PHYSICAL_ENERGY_UNMEASURED
TIMING_THERMAL_VOLUME_UNMEASURED
COMPLETE_SYSTEM_EVP_UNMEASURED
INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING
```

## Control question

Can the same accepted RTL trace survive replacement of the host bridge, resolver, or cartridge without changing command, refusal, fault, state, fallback, or receipt semantics?
