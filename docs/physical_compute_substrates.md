# Physical Compute Substrates

The physical world can participate in a computation in three separate roles. A measured field can be the operand. Relaxation, stochastic fluctuation, oscillation, dissipation, or another physical process can perform the transformation. Ambient, recovered, or externally supplied energy can power that process. The same phenomenon may occupy more than one role, but every role is declared and measured independently.

This separation prevents three category errors. Sampling a sensor does not by itself prove that the physical world performed useful computation. Using thermal noise does not make an execution exactly replayable unless the entropy realization is captured or the acceptance contract is distributional. Declaring an ambient or recovered energy source does not establish an energy advantage until a closed measurement boundary records supplied and harvested or recovered joules.

## Commodity architecture

RISC-V remains the deterministic control, isolation, and provenance plane. A physical substrate is a cartridge behind `physical-compute-mmio/v1`. The base interface uses descriptor, input, output, and receipt queues so it can operate on an ordinary RISC-V platform without a custom instruction set. The optional non-standard extension name is `Xphys`; it may accelerate queue operations or state access but cannot change the cartridge contract or evidence boundary.

A cartridge may target a designed device, harvested environment, embodied structure, or biological system. Its coupling is separately declared as observe-only, stimulate-and-observe, or closed-loop. A cartridge declares:

- operand, dynamics, energy, and context channels;
- physical quantities, units, calibration requirements, and sample timing;
- reset semantics and state size;
- exact, trace-replay, or distributional determinism;
- energy-source class and evidence tier;
- a software reference fallback; and
- a stable receipt schema.

The fallback is a design requirement. Hardware can be absent, simulated, emulated, or replaced without changing the workload interface. Physical implementations compete by satisfying the same contract with better measured energy, latency, uncertainty, or volume.

## Harvesting the world without category errors

`harvested-world-reservoir-contract-v1` treats a measured environmental trajectory as both operand and dynamics. It is intentionally contract-only: the world may supply nonlinear response and memory, while a simple readout produces the result, but the descriptor keeps capability marked unproven until task quality, drift, calibration, observation energy, and environmental custody are measured. The substrate can be a plant, structure, body, weather field, fluid, oscillator network, or other evolving system. It does not need to be a chip.

## Reference cartridges

`rc-relaxation-reference-v1` models an RC-like leaky integrator using deterministic Q16 fixed-point arithmetic. It demonstrates a field operand transformed by dissipative relaxation.

`thermal-bit-sampler-reference-v1` models a stochastic thermodynamic bit source. Its input is a probability threshold and its stochastic realization is supplied by an entropy trace. Exact replay therefore depends on trace custody. A future live cartridge can replace the injected trace with measured physical fluctuations while preserving the same receipt.

## Claim boundary

Reference execution proves contract behavior, calibration enforcement, state custody, fallback substitution, and replay conditions. It does not prove that a physical substrate performed the transformation, supplied or recovered energy, occupied a declared volume, or met timing and thermal limits. Those claims belong in measured physical receipts and EVP qualification.
