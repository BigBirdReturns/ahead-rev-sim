# Chipyard Physical-Compute Integration Candidate

The generated `physical-compute-mmio/v1` control plane now has a concrete Chipyard integration bundle. The bundle does not fork Chipyard or establish a new host dependency. It translates the stable MMIO contract into the current public TileLink peripheral construction pattern and retains a bare-metal fallback smoke that can execute before any physical cartridge exists.

## Source contract

The generator is bound to the public Chipyard MMIO example:

```text
repository  ucb-bar/chipyard
ref         main
path        generators/chipyard/src/main/scala/example/GCD.scala
blob        f1579822bc7bacab7dcdfac742034266ddea012b
```

The same blob was observed at Chipyard commit:

```text
e27c6561c0066c1f60bf4eb4885a38391c850ac0
```

The consumed API surface is deliberately narrow:

```text
ClockSinkDomain
TLRegisterNode
RegField
TLInwardClockCrossingHelper
TLFragmenter
BaseSubsystem
PBUS
```

No generated code assumes authority over Chipyard. A later Chipyard revision must either satisfy the same source contract or produce a first API divergence.

## Generated bundle

```bash
ahead-rev-chipyard \
  --out-dir artifacts/chipyard-physical-compute
```

An alternate 4 KiB-aligned base address can be selected:

```bash
ahead-rev-chipyard \
  --base-address 0x02000000 \
  --out-dir artifacts/chipyard-physical-compute
```

The bundle contains:

```text
PhysicalCompute.scala
physical_compute_smoke.c
chipyard-physical-compute-integration.json
```

`PhysicalCompute.scala` defines `PhysicalComputeParams`, `PhysicalComputeKey`, a `PhysicalComputeTL` TileLink register peripheral, a `CanHavePeripheryPhysicalCompute` subsystem mixin, and a `WithPhysicalCompute` configuration fragment. The generated register map is the same `physical-compute-mmio/v1` surface used by the Python reference model, C header, SystemVerilog reference block, and SVA bundle.

The TileLink peripheral enforces one command bit per submission, command-specific pointer prerequisites, backpressure for control writes while busy, explicit refused, done, and fault outcomes, and receipt validity. It exposes a device-side command interface so a thermodynamic, reversible, analog, neuromorphic, photonic, environmental, molecular, remote, or software cartridge can replace another behind the same host transaction.

## Loopback fallback

The default configuration enables `loopbackFallback`. This mode accepts a valid command through the same TileLink registers, completes it through a deterministic one-cycle fallback path, and produces the terminal command and receipt state required by the smoke program. It closes host lifecycle semantics only. It does not claim to execute the substrate transformation or produce the accepted workload result.

The generated bare-metal smoke performs four checks:

1. the expected ABI identity is present;
2. an ambiguous two-command submission is refused;
3. a valid reset command reaches done plus receipt-valid state;
4. a valid load with descriptor, input, output, and receipt pointers reaches a stable ready terminal state.

This gives a Chipyard checkout a bounded admission and refusal fixture before a physical device is connected.

## Qualification sequence

The generated manifest remains `source_generated_unqualified`. The next gates are concrete:

```text
1. materialize the exact Chipyard checkout and submodule graph
2. install PhysicalCompute.scala in the Chipyard generator tree
3. mix CanHavePeripheryPhysicalCompute into the target DigitalTop
4. compose WithPhysicalCompute into a target Config
5. elaborate the design
6. build physical_compute_smoke.c for the target RISC-V runtime
7. execute the smoke in Verilator or FireSim
8. preserve the RISC-V trace, MMIO trace, terminal status, and receipt memory
9. replace loopbackFallback with one real or simulated cartridge
10. compare target behavior with the Python and SystemVerilog references
```

A custom `Xphys` instruction remains inadmissible until this MMIO transaction has been measured and a recurring control-plane bottleneck is demonstrated.

## Evidence boundary

The source generator establishes a candidate Chipyard mapping, register parity, refusal logic, fallback lifecycle, source identity, and artifact hashes. It does not establish that the Scala elaborates in the pinned checkout, that a RISC-V binary builds, that RTL simulation passes, that a target trace matches, that a physical substrate executed useful work, or that energy, timing, thermal, volume, and fabrication claims close.

The controlling question is: can the exact MMIO transaction elaborate and execute in Chipyard, preserve refusal and receipt behavior, and then accept a different cartridge without changing the workload or host contract?
