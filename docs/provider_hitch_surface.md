# Provider Hitch Surface

`ahead-rev-sim` now exposes a provider-neutral coupling contract for conventional RISC-V hosts and nonconventional physical-compute cartridges. The contract is intentionally narrower than a partnership API. It fixes the host transaction, accepted-work boundary, software fallback, refusal behavior, and receipt custody while allowing the host microarchitecture and physical substrate to be replaced independently.

The portable floor remains `physical-compute-mmio/v1`. Every host and cartridge reserves the complete `reset`, `load`, `evolve`, `read`, and `capture` command surface. `Xphys` remains optional and `evidence_only`; a provider may propose an acceleration only after the ordinary MMIO transaction has produced a measured bottleneck. A custom instruction cannot alter accepted work, state semantics, fallback behavior, or evidence fields.

## Two couplers, separate authority

A **host hitch** describes the conventional RISC-V side. It must eventually supply a RISC-V implementation, MMIO driver, accepted target trace, reset and refusal receipt, and toolchain receipt. Complete-system energy, timing, thermal, volume, and independent-validation evidence remain separate physical-claim slots.

A **cartridge hitch** describes the physical or virtual substrate side. It must eventually supply a substrate descriptor, software fallback, device interface, accepted-output receipt, and reset-state receipt. A physical cartridge must additionally supply complete-system energy, timing, thermal, occupied-volume, and independent-validation receipts before any physical or energy claim is admitted.

The composed artifact is a **consist**. A consist reports interface compatibility, execution admission, negotiated commands and capabilities, execution blockers, physical-claim blockers, and the hashes of both hitches. Its substitution contract permits providers to change implementation, microarchitecture, substrate, package, and internal compiler. It forbids providers from changing the portable binding, accepted work, refusal semantics, software fallback, receipt schema, or evidence boundary.

## AheadComputing host offer

The committed offer at:

```text
examples/hitches/aheadcomputing-riscv-host.offer.json
```

reserves an ordinary RISC-V host position for AheadComputing. It is issued by `ahead-rev-sim`; `actor_acknowledged` is explicitly false. The file is not a statement by AheadComputing, an endorsement, a partnership claim, or evidence that its current product implements the interface.

AheadComputing can convert the offer into a submission by declaring the complete MMIO command surface and software-fallback capability, then filling the host artifact slots with pinned source, target, toolchain, refusal, and measurement evidence. Its core may be wider, faster, more speculative, or internally proprietary. Those choices remain implementation details unless they change the public transaction or accepted result.

## Vaire cartridge offer

The committed offer at:

```text
examples/hitches/vaire-reversible-cartridge.offer.json
```

reserves a physical-cartridge position for Vaire Computing. It is also issued by `ahead-rev-sim` with explicit nonacknowledgement. It does not represent Vaire's public papers as a completed processor or as evidence of complete-system advantage.

Vaire can convert the offer into a submission by declaring one packaged determinism class, retaining a software fallback, and supplying the cartridge execution artifacts. Any reversible or adiabatic advantage remains blocked until the submitted receipt includes the accepted workload, power-clock generation, memory, conversion, control, data movement, reset, complete supplied and recovered energy, timing, thermal state, occupied volume, and independent reconstruction.

## Reserved Ahead plus Vaire consist

The committed composition at:

```text
examples/hitches/ahead-vaire.reserved-consist.json
```

is `compatible`, `hitchable`, and `hitchable_unqualified`. Execution is refused because neither company has supplied or acknowledged a provider submission. This is deliberate. The interface is waiting for them, but the public offer cannot manufacture evidence or participation.

The independently qualified reference composition is:

```text
examples/hitches/reference.consist.json
```

It joins the current RV64GC target-model host to the virtual loopback cartridge. That consist is execution-admitted because its source, driver, trace, fallback, reset, and receipt artifacts are present. It still refuses every physical-compute and energy claim because both components are virtual references.

## Full-impulse execution binding

The dedicated RISC-V target workflow now treats the admitted reference consist as an input to execution rather than an adjacent document. After compiling and running the independent RV64GC client and software device model, it compares the new target proof with the committed accepted fixture at `examples/hitches/reference-riscv-target-proof.json` and creates a `physical_compute_consist_execution_proof`. That proof binds the consist hash, both hitch hashes, the target-proof hash, binary hash, accepted-trace hash, target identity, semantic observations, and the exact host and cartridge receipt slots that admitted execution.

The accepted reference proof is committed at `examples/hitches/reference-consist-execution-proof.json`. An unqualified offer cannot enter that proof. Attempting to bind the reserved Ahead plus Vaire consist fails because its execution admission is `refused`. A future Ahead host submission or Vaire cartridge submission can therefore replace one reference hitch at a time, but only after its required artifacts move the new consist to `execution_admitted`.

The proof still carries the unresolved physical ledger. QEMU target execution proves the RISC-V transaction and independent software-device behavior. Chipyard RTL execution, physical transformation, complete supplied and recovered energy, timing, thermal state, occupied volume, fabrication, and independent physical acceptance remain blocked.

## Command line

Generate the reserved Ahead plus Vaire consist:

```bash
ahead-rev-hitch \
  --host examples/hitches/aheadcomputing-riscv-host.offer.json \
  --cartridge examples/hitches/vaire-reversible-cartridge.offer.json \
  --out artifacts/ahead-vaire-consist.json
```

Generate the admitted reference consist and fail if admission regresses:

```bash
ahead-rev-hitch \
  --host examples/hitches/reference-rv64gc-host.hitch.json \
  --cartridge examples/hitches/reference-loopback-cartridge.hitch.json \
  --out artifacts/reference-consist.json \
  --require-admitted
```

Bind that admitted consist to a sealed target proof:

```bash
ahead-rev-consist-proof \
  --consist artifacts/reference-consist.json \
  --host-hitch examples/hitches/reference-rv64gc-host.hitch.json \
  --cartridge-hitch examples/hitches/reference-loopback-cartridge.hitch.json \
  --target-proof artifacts/riscv-target/riscv-target-proof.json \
  --out artifacts/riscv-target/reference-consist-execution-proof.json
```

The provider-hitch workflow generates both consists on every pull request. It requires the reference composition to remain admitted and requires the Ahead plus Vaire composition to remain compatible but unqualified. The latter check prevents a future edit from silently turning a public integration offer into an implementation or endorsement claim.

The control question is: can a host or cartridge provider replace the current implementation, reproduce the same admission and refusal behavior, satisfy the same accepted work, retain software fallback, and leave enough pinned evidence to determine what the complete system actually did and paid?
