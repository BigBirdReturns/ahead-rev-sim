# Pinned Chipyard subsystem elaboration

The Chipyard subsystem train tests whether the physical-compute control plane can enter an exact upstream SoC checkout without granting Chipyard authority over the accepted workload, fallback, execution proof, or claim boundary.

## Upstream authority

The integration pins:

```text
repository  ucb-bar/chipyard
commit      e27c6561c0066c1f60bf4eb4885a38391c850ac0
config      chipyard.physicalcompute.PhysicalComputeRocketConfig
```

The manifest also pins the Git blob identities and required API patterns for the current GCD TileLink example, Rocket configuration, `DigitalTop`, `variables.mk`, and `build-setup.sh`. The `testchipip` injector source is transitively pinned by the Chipyard superproject commit and is checked from the initialized submodule before proof admission.

## Entry mechanism

The generated source uses `testchipip.soc.SubsystemInjectorKey`, which the current `DigitalTop` already executes. The bundle therefore adds an injector through configuration rather than editing Berkeley’s top-level class.

```text
PhysicalComputeRocketConfig
        ↓ WithPhysicalCompute
SubsystemInjectorKey + PhysicalComputeInjector
        ↓
DigitalTop CanHaveSubsystemInjectors
        ↓
PBUS / TLFragmenter / synchronous crossing
        ↓
PhysicalComputeTL register node
```

The admitted configuration retains the sealed software loopback fallback. It does not expose an external cartridge port in the Chipyard top. That restriction prevents successful elaboration from being misrepresented as an external-device or physical-compute result.

## Generated bundle

`ahead-rev-chipyard bundle` writes:

```text
PhysicalCompute.scala
physical_compute_smoke.c
chipyard-physical-compute-integration.json
```

The Scala source provides the MMIO register block, one-hot command admission, pointer requirements, refusal state, receipt-valid completion, deterministic loopback fallback, elaboration witness, upstream injector, and complete Rocket configuration.

The source is installed at:

```text
generators/chipyard/src/main/scala/physicalcompute/PhysicalCompute.scala
```

## Elaboration transaction

The workflow performs the following transaction against the exact pinned checkout:

1. Creates the lean upstream Conda environment without toolchain, FireSim, FireMarshal, precompile, or CIRCT work that is unnecessary for Chisel elaboration.
2. Initializes the minimally required pinned submodules.
3. Verifies exact `rocket-chip` and `testchipip` submodule state.
4. Copies the generated Scala source into the declared package path.
5. Proves `DigitalTop.scala` remains untouched.
6. Runs:

```bash
make -C chipyard/sims/verilator \
  CONFIG=PhysicalComputeRocketConfig \
  CONFIG_PACKAGE=chipyard.physicalcompute \
  JAVA_HEAP_SIZE=6G \
  firrtl
```

7. Captures FIRRTL, annotations, Chisel log, elaboration log, Java version, SBT version, submodule state, upstream source witnesses, and generated-source identity.
8. Seals the result with `ahead-rev-chipyard proof`.

## Proof admission

The proof refuses a transaction unless:

- the Chipyard checkout commit is exact;
- the integration manifest equals the current deterministic manifest;
- the generated Scala is installed at the declared path and matches the current generator byte for byte;
- every pinned upstream source file matches its Git blob identity and required API patterns;
- `rocket-chip` and `testchipip` are initialized at their superproject-pinned commits;
- the injector source contains the declared `SubsystemInjector`, `SubsystemInjectorKey`, and `CanHaveSubsystemInjectors` API;
- FIRRTL, annotations, Chisel log, and elaboration log are nonempty;
- annotations are valid JSON;
- the FIRRTL filename identifies `PhysicalComputeRocketConfig`;
- the FIRRTL contains at least one module and the retained `ahead_physical_compute_elaboration_witness`.

The workflow also demonstrates refusal for the wrong checkout, altered generated Scala, and FIRRTL with the witness removed.

## Evidence ledger

The evidence tier is pinned Chisel-to-FIRRTL subsystem elaboration. The venue is the official Chipyard build environment on a GitHub Actions Ubuntu runner. The target is the physical-compute TileLink peripheral entering `DigitalTop` through the official injector API. The upside is actual upstream subsystem elaboration without a local top-level fork. The downside is that FIRRTL generation does not execute the resulting RTL or a RISC-V workload. The failure mode is treating elaboration as compiled Verilog, RTL simulation, external-cartridge execution, FPGA or silicon behavior, physical work, or complete-system advantage.

After acceptance, the following blockers remain:

```text
CHIPYARD_RTL_SIMULATION_UNRUN
CHIPYARD_EXTERNAL_CARTRIDGE_BINDING_UNRUN
RISC_V_BINARY_BUILD_UNRUN
TARGET_TRACE_UNOBSERVED
FPGA_OR_SILICON_EXECUTION_UNRUN
PHYSICAL_SUBSTRATE_UNMEASURED
PHYSICAL_ENERGY_UNMEASURED
TIMING_THERMAL_VOLUME_UNMEASURED
COMPLETE_SYSTEM_EVP_UNMEASURED
INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING
```

## Control question

Can the physical-compute control plane enter the exact Chipyard subsystem through a replaceable injector, elaborate without patching `DigitalTop`, and preserve fallback and acceptance authority outside Chipyard?
