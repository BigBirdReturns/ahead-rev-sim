# Chipyard RV64GC Lifecycle Execution

This train closes the execution boundary between the merged pinned-subsystem elaboration proof and the still-open physical-target boundary. The qualified object is an RV64GC bare-metal lifecycle client executing against the generated `physical-compute-mmio/v1` peripheral inside the exact pinned Chipyard Verilator `TestHarness`. The object is narrower than a physical-compute workload and broader than elaboration. It proves that a real RISC-V instruction stream can reach the injected register block and reproduce its admission, refusal, terminal-state, fallback, and receipt semantics through compiled RTL.

The actors remain deliberately separate. The repository owns the portable MMIO contract, generated client, accepted trace, proof admission, fallback policy, claim boundary, and release gate. The pinned Chipyard checkout supplies the Rocket subsystem, `DigitalTop`, test harness, upstream injector API, generated RTL pipeline, and Verilator execution venue. The generated `PhysicalComputeTL` peripheral owns only the declared register state machine. The RV64GC client owns transaction sequencing and observation. Verilator executes the model but receives no authority over accepted output or qualification.

## Authority chain

The workflow begins from `ucb-bar/chipyard` commit `e27c6561c0066c1f60bf4eb4885a38391c850ac0`. It regenerates the integration bundle, installs `PhysicalCompute.scala` at its declared source path, verifies that `DigitalTop.scala` remains unmodified, initializes the exact critical submodules, and reconstructs the already admitted Chisel-to-FIRRTL elaboration proof. The lifecycle proof will not admit a simulation unless that elaboration proof is sealed, accepted, bound to the current integration manifest, bound to `PhysicalComputeRocketConfig`, and still records the internal loopback fallback.

The generated lifecycle bundle contains three deterministic files:

```text
physical_compute_chipyard_lifecycle.c
physical_compute_chipyard_lifecycle.expected
chipyard-rv64gc-lifecycle-manifest.json
```

The manifest binds the source and expected trace by SHA-256 to the pinned Chipyard commit, configuration, base address, injector API, integration-manifest seal, RV64GC ISA, LP64D ABI, and loopback execution boundary. Before execution it retains the explicit `CHIPYARD_RTL_SIMULATION_UNRUN`, `RISC_V_BINARY_BUILD_UNRUN`, and `TARGET_TRACE_UNOBSERVED` blockers.

## Compiled transaction

The workflow uses the RISC-V toolchain supplied by the pinned Chipyard environment and follows the upstream HTIF bare-metal contract. The generated C client is compiled and linked with the essential target flags:

```text
riscv64-unknown-elf-gcc
-march=rv64gc
-mabi=lp64d
-mcmodel=medany
-specs=htif_nano.specs
-static
```

The resulting file must be nonempty and identify as ELF64 for the RISC-V machine under `readelf`. The workflow retains the compiler identity, ELF header, disassembly, size report, source, and binary digest.

The same pinned configuration is then elaborated, lowered, compiled into the full Verilator simulator, and executed with Chipyard's `run-binary-fast` rule. The run is bounded by a timeout and retains the complete raw simulator log before extracting any semantic records. The accepted trace is therefore a projection of retained raw execution evidence rather than a replacement for it.

## Accepted lifecycle

The client first reads the implementation identity and capabilities. It then submits an ambiguous `RESET | READ` command and requires a refusal without a receipt. It submits reset, programs the descriptor, input, output, and receipt pointers, and executes load, evolve, read, and capture. Every accepted command must terminate with ready, done, and receipt-valid asserted while busy, refused, and fault remain clear.

The exact semantic trace is:

```text
ahead-chipyard:abi=physical-compute-mmio/v1 isa=rv64gc
ahead-chipyard:identity=41504859 capabilities=00000009
ahead-chipyard:ambiguous status=00000009 result=refused receipt=absent
ahead-chipyard:reset status=00000025 result=done receipt=valid
ahead-chipyard:load status=00000025 result=done receipt=valid
ahead-chipyard:evolve status=00000025 result=done receipt=valid
ahead-chipyard:read status=00000025 result=done receipt=valid
ahead-chipyard:capture status=00000025 result=done receipt=valid
ahead-chipyard:result=pass
```

Proof admission requires byte identity between the generated accepted trace and the extracted trace. It also parses the records independently, requires exactly one record for every declared stage, requires the declared order, verifies the identity and capability mask, and checks every status, result, and receipt combination. The raw simulator log must contain the same records in order. A reordered, duplicated, omitted, altered, or independently forged trace is refused.

## Sealed receipt

`ahead-rev-chipyard lifecycle-proof` binds the integration manifest, lifecycle manifest, accepted elaboration proof, generated C source, expected trace, ELF binary, Verilator simulator executable, simulator-build log, raw execution log, semantic trace, tool identities, and the exact build and run command descriptions. The deterministic proof seal can be recomputed from the JSON object after removing `proof_sha256`.

A passing proof changes the admitted software evidence state in three ways. Chipyard subsystem elaboration remains admitted. Chipyard RTL simulation becomes admitted for the pinned loopback configuration. RV64GC lifecycle execution becomes admitted for the exact MMIO fixture. It does not admit an external cartridge or physical target.

The release workflow calls this workflow as a reusable gate alongside the standalone provider-neutral RTL attachment. A tagged release can therefore be published only after the immutable tagged source reconstructs both the standalone attachment transaction and the pinned Chipyard RV64GC lifecycle transaction.

## Evidence boundary

The evidence tier is executed Chipyard RTL simulation. The venue is the full Verilator simulator generated from the exact pinned Chipyard checkout and `PhysicalComputeRocketConfig` on a GitHub Actions Ubuntu runner. The target is an ELF64 RV64GC HTIF binary operating the injected `PhysicalComputeTL` register block through the upstream subsystem injector. The upside is an actual processor-to-peripheral lifecycle across compiled RISC-V software and compiled Chipyard RTL, with refusal and receipt behavior bound to the preceding elaboration proof. The downside is that the peripheral still terminates accepted commands through its internal loopback fallback. The failure mode is promoting this receipt into evidence for an external cartridge, FPGA, silicon, physical substrate, recovered energy, fabrication, or complete-system advantage.

The retained blockers are:

```text
CHIPYARD_EXTERNAL_CARTRIDGE_BINDING_UNRUN
FPGA_OR_SILICON_EXECUTION_UNRUN
PHYSICAL_SUBSTRATE_UNMEASURED
PHYSICAL_ENERGY_UNMEASURED
TIMING_THERMAL_VOLUME_UNMEASURED
COMPLETE_SYSTEM_EVP_UNMEASURED
INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING
```

The control question is whether the same content-addressed lifecycle can now replace the internal loopback with an external cartridge or physical target while preserving command, refusal, terminal-state, receipt, provenance, and fallback semantics.
