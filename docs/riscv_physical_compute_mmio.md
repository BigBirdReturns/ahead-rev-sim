# RISC-V Physical-Compute MMIO Control Plane

The physical-compute substrate contract now has a generated host boundary. Ordinary RISC-V MMIO remains the portable floor. A thermodynamic device, reversible lane, analog reservoir, neuromorphic target, photonic subsystem, molecular experiment, environmental trajectory, remote testbed, or software model can implement the same control-plane transaction without requiring a new sovereign processor or toolchain.

The ABI identity is:

```text
physical-compute-mmio/v1
```

The optional non-standard RISC-V extension name remains:

```text
Xphys
```

`Xphys` may eventually accelerate queue operations, state exchange, entropy capture, barriers, or receipt access. It cannot change register semantics, accepted work, fallback behavior, refusal conditions, or evidence boundaries. A standard RISC-V host must be able to execute the complete transaction through MMIO alone.

## Register surface

| Offset | Register | Access | Purpose |
|---:|---|:---:|---|
| `0x00` | `identity` | RO | Implementation identity and ABI compatibility |
| `0x04` | `capabilities` | RO | Determinism, fallback, measured-energy, and optional acceleration capabilities |
| `0x08` | `command` | RW | One selected command |
| `0x0C` | `status` | RO | Ready, busy, terminal result, and receipt state |
| `0x10` | `descriptor_ptr_lo` | RW | Substrate descriptor pointer, low word |
| `0x14` | `descriptor_ptr_hi` | RW | Substrate descriptor pointer, high word |
| `0x18` | `input_queue_ptr_lo` | RW | Input queue pointer, low word |
| `0x1C` | `input_queue_ptr_hi` | RW | Input queue pointer, high word |
| `0x20` | `output_queue_ptr_lo` | RW | Output queue pointer, low word |
| `0x24` | `output_queue_ptr_hi` | RW | Output queue pointer, high word |
| `0x28` | `receipt_ptr_lo` | RW | Receipt pointer, low word |
| `0x2C` | `receipt_ptr_hi` | RW | Receipt pointer, high word |
| `0x30` | `doorbell` | WO | Submit the selected command |

The first command set is `reset`, `load`, `evolve`, `read`, and `capture`. Exactly one command bit may be submitted at a time. Each command declares its pointer prerequisites. A malformed command, ambiguous bit mask, or missing pointer is refused rather than interpreted permissively.

The status surface separates `ready`, `busy`, `done`, `refused`, `fault`, and `receipt_valid`. Terminal outcomes are mutually exclusive. Pointer and command state remain immutable while a command is busy. A valid receipt indication belongs to a terminal execution rather than an unbounded asynchronous observation.

## Generated artifacts

The generator emits four synchronized artifacts:

```text
physical-compute-mmio-v1.json
    machine-readable ABI and SHA-256 seal

ahead_physical_compute_mmio_v1.h
    C register constants, command and status masks,
    typed register structure, pointer helpers, and offset assertions

ahead_physical_compute_mmio_v1.sv
    synthesizable reference control plane with refusal behavior

ahead_physical_compute_mmio_v1_sva.sv
    command, terminal-state, receipt, and pointer-custody assertions
```

Generate the complete bundle with:

```bash
ahead-rev-mmio \
  --format bundle \
  --out-dir artifacts/mmio-v1
```

Individual artifacts can be written independently:

```bash
ahead-rev-mmio --format json --out artifacts/mmio-v1.json
ahead-rev-mmio --format c-header --out include/ahead_physical_compute_mmio_v1.h
ahead-rev-mmio --format systemverilog --out rtl/ahead_physical_compute_mmio_v1.sv
ahead-rev-mmio --format sva --out formal/ahead_physical_compute_mmio_v1_sva.sv
```

## Reference execution and refusal model

`PhysicalComputeMMIOReference` is an executable Python model of the control-plane state machine. It enforces read-only registers, word alignment, known offsets, one-hot commands, command-specific pointer requirements, immutable control state while busy, and terminal completion with or without a valid receipt.

This model is the differential reference for future Chipyard, OpenASIP, CIRCT, Calyx, FPGA, RTL-to-GDS, remote-device, and commercial-host implementations. Those implementations compete by matching the same register and refusal semantics. They do not define them.

## Immediate system use

The generated ABI closes the first transaction in the RISC-V control and hardware-compiler lane. The next implementation sequence is:

1. wrap the SystemVerilog block as a TileLink MMIO peripheral in Chipyard;
2. generate a minimal bare-metal driver from the C header;
3. drive the peripheral through reset, refused submission, accepted fallback execution, and receipt capture;
4. compare an MMIO implementation against an OpenASIP or CIRCT-generated acceleration path;
5. measure queue, interrupt, memory, and host overhead before admitting any `Xphys` instruction.

The same fixture will then enter the open-silicon lane through SiliconCompiler and OpenROAD, with the generated SVA properties retained through simulation and formal checks.

## Evidence boundary

The ABI generator and reference block establish register layout, command lifecycle, pointer custody, refusal behavior, software fallback compatibility, and receipt access. They do not establish that a physical substrate performed useful computation, that energy was recovered or harvested, that a device closes timing or thermal limits, that the occupied volume is favorable, or that the RTL is manufacturable. Those claims require the corresponding target, workload, implementation, measurement, and independent-acceptance receipts.

The control question is: can any physical or simulated implementation replace another behind this RISC-V surface, produce the same accepted result and refusal behavior, and leave enough evidence to determine what the complete system paid?
