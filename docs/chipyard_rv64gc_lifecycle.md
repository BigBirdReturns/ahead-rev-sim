# Chipyard RV64GC Lifecycle Execution

This train closes the execution boundary between the merged pinned-subsystem elaboration proof and the still-open physical-target boundary. The qualified object is an RV64GC bare-metal lifecycle client executing against the generated `physical-compute-mmio/v1` peripheral inside the exact pinned Chipyard Verilator `TestHarness`. The object is narrower than a physical-compute workload and broader than elaboration. It proves that a real RISC-V instruction stream can reach the injected register block and reproduce its admission, refusal, terminal-state, fallback, and receipt semantics through compiled RTL.

The actors remain deliberately separate. The repository owns the portable MMIO contract, generated client, accepted trace, proof admission, fallback policy, claim boundary, and release gate. The pinned Chipyard checkout supplies the Rocket subsystem, `DigitalTop`, test harness, upstream injector API, generated RTL pipeline, and Verilator execution venue. The generated `PhysicalComputeTL` peripheral owns only the declared register state machine. The RV64GC client owns transaction sequencing and observation. Verilator executes the model but receives no authority over accepted output or qualification.

## Authority chain

The workflow begins from `ucb-bar/chipyard` commit `e27c6561c0066c1f60bf4eb4885a38391c850ac0`. It regenerates the integration bundle, installs `PhysicalCompute.scala` at its declared source path, verifies that `DigitalTop.scala` remains unmodified, initializes the exact critical submodules, and reconstructs the already admitted Chisel-to-FIRRTL elaboration proof. The simulator host runtime is pinned to Chipyard's `toolchains/riscv-tools/riscv-isa-sim` gitlink at `riscv-software-src/riscv-isa-sim` commit `9c190a07c6838f6392bafa4ad83acea462c7f759`. The lifecycle target runtime is separately pinned to the `toolchains/libgloss` gitlink at `ucb-bar/libgloss-htif` commit `39234a16247ab1fa234821b251f1f1870c3de343`. RTL lowering is pinned through Chipyard's own `conda-reqs/circt.json` authority to `llvm/circt` release `firtool-1.75.0`, installed by the exact `circt/install-circt` gitlink at commit `3f8dda6e1c1965537b5801a43c81c287bac4eae4`. The lifecycle proof will not admit a simulation unless the elaboration proof is sealed, accepted, bound to the current integration manifest, bound to `PhysicalComputeRocketConfig`, still records the internal loopback fallback, and carries the FESVR host runtime, HTIF target runtime, and CIRCT lowering authorities used to construct the executable objects.

The generated lifecycle bundle contains three deterministic files:

```text
physical_compute_chipyard_lifecycle.c
physical_compute_chipyard_lifecycle.expected
chipyard-rv64gc-lifecycle-manifest.json
```

The manifest binds the source and expected trace by SHA-256 to the pinned Chipyard commit, configuration, base address, injector API, integration-manifest seal, RV64GC ISA, LP64D ABI, and loopback execution boundary. Before execution it retains the explicit `CHIPYARD_RTL_SIMULATION_UNRUN`, `RISC_V_BINARY_BUILD_UNRUN`, and `TARGET_TRACE_UNOBSERVED` blockers.

## Compiled transaction

The workflow first reconstructs the simulator's host-side RISC-V support from the exact pinned `riscv-isa-sim` gitlink. It configures, builds, and installs the upstream runtime into Chipyard's pinned RISC-V prefix with Boost explicitly disabled, then seals the installed `fesvr/memif.h`, `libfesvr.a`, and `libriscv.so` together with the revision witness, header inventory, configure, build, and install logs, and a report containing their content digests. These are the headers and libraries consumed by the generated Verilator link command.

The workflow then uses the RISC-V compiler supplied by the pinned Chipyard environment and reconstructs the upstream HTIF bare-metal runtime from the exact pinned `libgloss-htif` gitlink. It configures and installs that runtime into the compiler sysroot, then resolves and copies the installed `htif_nano.specs`, `htif.ld`, and RV64GC-selected `libgloss_htif.a` into the evidence estate. The generated C client is compiled and linked with the essential target flags:

```text
riscv64-unknown-elf-gcc
-march=rv64gc
-mabi=lp64d
-mcmodel=medany
-specs=htif_nano.specs
-static
```

The resulting file must be nonempty and identify as ELF64 for the RISC-V machine under `readelf`. The workflow retains the compiler identity, ELF header, disassembly, size report, source, and binary digest. It also retains the exact libgloss revision witness, compiler search directories, configure, build, and install logs, installed specs, installed linker script, selected static runtime archive, their source paths, and their digests.

The same pinned configuration is then elaborated and lowered by the pinned `firtool-1.75.0` executable before Verilator compiles the full simulator. The workflow requires `firtool` to resolve inside Chipyard's pinned RISC-V prefix and retains Chipyard's CIRCT release file, the installer revision, the version output, the executable digest, and an authority report containing the resolved path and source digests. The simulator then executes the target with Chipyard's `run-binary-fast` rule. The run is bounded by a timeout and retains the complete raw simulator log before extracting any semantic records. The accepted trace is therefore a projection of retained raw execution evidence rather than a replacement for it.

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

`ahead-rev-chipyard lifecycle-proof` binds the integration manifest, lifecycle manifest, accepted elaboration proof, generated C source, expected trace, ELF binary, Verilator simulator executable, simulator-build log, raw execution log, semantic trace, tool identities, and the exact build and run command descriptions. The simulator side binds the pinned `riscv-isa-sim` revision, sealed FESVR header, FESVR static archive, RISC-V shared library, header inventory, host-runtime report, and configure, build, install, and static-library logs. The target side binds the pinned `libgloss-htif` revision, installed HTIF specs, linker script, selected static runtime archive, compiler search directories, runtime report, and configure, build, and install logs. The lowering side binds the exact CIRCT release file, release-tag commit, installer revision, `firtool` version record, authority report, and executable digest. Admission independently checks the host and target runtime revisions, FESVR header contract, archive and ELF formats, required HTIF specs directives, RISC-V linker-script structure, CIRCT release and tag, installer revision, ELF identity of the `firtool` executable, version consistency, and cross-record digests. The deterministic proof seal can be recomputed from the JSON object after removing `proof_sha256`.


The final evidence collector writes `SHA256SUMS` over every root evidence file except the checksum manifests themselves, verifies every entry immediately, writes `SHA256SUMS.sha256` as the external seal for that manifest, and verifies the manifest seal. This avoids the invalid recursive pattern in which a checksum file records the hash of its own empty pre-redirection state. The earlier reconstructable kit manifest remains an independently verified inventory of the files present when the proof and kit were assembled.

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
