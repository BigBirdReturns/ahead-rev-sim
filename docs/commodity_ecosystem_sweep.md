# Commodity Ecosystem Harvest

This registry treats the frontier compute ecosystem as a supply field. Vaire, AheadComputing, Normal Computing, Extropic, ARIA, SRC, open-source toolchains, benchmark communities, fabrication services, and physical-computing researchers do not sit beside `ahead-rev-sim` as privileged integrations. Their public artifacts enter as pinned commodities. We extract their mechanisms, reproduce their software baselines, wrap their devices behind our contracts, use their testbeds and manufacturing routes, and retain independent workload and evidence authority.

The governing transaction is deliberately asymmetric. External actors can contribute code, device models, papers, interfaces, measurements, silicon, test capacity, or failure evidence. They cannot redefine the accepted workload, replace the software fallback, collapse a multidimensional frontier into a promotional score, or declare a physical advantage outside the measurement boundary. Every commodity remains removable and substitutable.

## What the public ecosystem is asking someone to finish

The strongest public signals are not vague aspirations. They identify specific seams that remain unclosed:

- Vaire publishes the reversible power-clock and logic mechanism, a software-first architecture, component energy-recovery results, and EVP. The missing transaction is a workload-bound processor receipt that includes clock generation, memory, data movement, control, occupied volume, timing, and thermal state.
- Normal Computing has taped out CN101 and publicly states that characterization and benchmarking come next. Its own scaling account identifies low-speed I/O, off-chip transfers, on-chip control, caching, network-on-chip design, memory interfaces, and reticle-scale integration as the work between a primitive and a production system.
- Extropic publishes THRML, a simulator and model-development layer, while XTR-0 and Z1 provide the future physical target. The open seam is the exact mapping from graph, schedule, temperature, mixing, and sample quality to device behavior, host transport, and card-level energy.
- ARIA is funding simulators, open ground truth, and a rack testbed that inserts one unproven technology every six months. This is an explicit demand for a stable workload, fallback, telemetry, integration, and complete-system comparison contract.
- SRC ACE asks for standard, composable, replaceable accelerator interfaces. PRISM asks where data should move and compute. SUPREME asks for application benchmarking to feed materials and device design. CHIMES asks for system metrics, portability, and scaling. Together they describe the same missing cross-layer receipt from workload semantics to device and package evidence.
- OpenPRC states that physical reservoir computing remains fragmented across simulation, experimental ingestion, readout training, and evaluation. CrossSim provides rich analog nonideality and accuracy simulation while explicitly omitting energy, area, and speed. NeuroBench separates algorithm correctness from deployed-system performance. MLPerf Power supplies full-system wall-power discipline. These components become stronger when joined under one accepted-result and physical-receipt model.
- Chipyard and OpenASIP already provide the open RISC-V host and customization machinery. OpenROAD, OpenLane, OpenFASoC, open PDKs, Tiny Tapeout, and wafer.space provide implementation and test-silicon routes. Their incompleteness is useful evidence because it tells us exactly where mixed-signal models, adiabatic power clocks, calibration, signoff, and measured silicon must enter.

## Machine-readable registry

The authoritative registry is packaged at:

```text
src/ahead_rev_sim/data/commodity_ecosystem_registry.json
```

Its schema is:

```text
schemas/commodity-ecosystem-registry.schema.json
```

Every record names the actor and project, public stage, official source, commodity assets, ingestion modes, immediate transaction, unresolved system gaps, and completion questions. The registry contains no partnership or dependency state. The only allowed dependency mode is `commodity_only`.

The gap taxonomy asks the same questions across every paradigm: accepted result, workload identity, host interface, compiler lowering, state and reset, entropy custody, calibration and environment, data movement, complete energy boundary, recovered or harvested energy, timing, thermal state, occupied volume, software fallback, fabrication signoff, scaling interconnect, model-to-hardware fidelity, measurement reproducibility, independent validation, and governance durability.

## Current fan-out

| Priority | Actor | Project | Commodity assets | First transaction |
|---:|---|---|---|---|
| 1 | MLCommons Power Working Group | MLPerf Power | power_methodology, approved_instrument_practice, submission_format | Map MLPerf Power fields into EVP receipts and add the physical-cartridge fields MLPerf does not carry. |
| 1 | NeuroBench community | Neuromorphic algorithm and system benchmarks | benchmark_harness, algorithm_track, system_track | Adapt one chaotic forecasting or event-stream benchmark to compare raw stimulus, digital fallback, and physical substrate response. |
| 1 | OpenROAD and OpenLane communities | Open autonomous RTL-to-GDSII flows | rtl_to_gds_flow, physical_design_metrics, signoff_logs | Produce a minimal RISC-V physical-cartridge control block through an open RTL-to-GDS flow with archived PPA and signoff logs. |
| 1 | Sandia National Laboratories | CrossSim analog in-memory computing simulator | python_simulator, device_nonideality_models, application_accuracy_adapters | Run one FAMBS matrix workload through CrossSim and bind quality loss to an explicit accepted-output contract. |
| 1 | ARIA and CommonAI CIC | Scaling Compute and Scaling Inference Lab | open_rack_testbed, system_simulators, benchmark_ground_truth | Produce a rack-insertion evidence package that lets any physical cartridge replace one component while preserving workload, fallback, and complete-system measurement. |
| 1 | OpenPRC researchers and physical reservoir computing community | OpenPRC physics-to-task evaluation framework | trajectory_schema, physics_to_task_pipeline, vision_ingestion | Implement an OpenPRC trajectory adapter that emits our calibration, environment, fallback, and compute-gain receipts. |
| 1 | Semiconductor Research Corporation and DARPA JUMP 2.0 | ACE Evolvable Computing | composable_interface_research, demonstrators_and_benchmarks | Create an ACE crosswalk showing where physical state, calibration, entropy, and measured receipts extend ordinary accelerator composability. |
| 1 | Vaire Computing | Adiabatic reversible computing, Ice River, and EVP | architecture_claims, energy_recovery_measurements, evp_metric_proposal | Bind every public Ice River measurement to its exact component boundary and compare it with the workload-level reversal overhead already emitted by ahead-rev-sim. |
| 1 | UC Berkeley and the Chipyard community | Chipyard heterogeneous RISC-V SoC framework | soc_generator, mmio_and_rocc_interfaces, firesim_and_vlsi_flows | Generate a Chipyard MMIO peripheral stub and software driver from the cartridge descriptor schema. |
| 1 | Tampere University OpenASIP community | OpenASIP retargetable accelerator and RISC-V instruction co-design | retargetable_compiler, function_unit_generator, riscv_custom_instruction_flow | Lower one proven reversible primitive and one cartridge queue operation through OpenASIP, then compare against MMIO. |
| 1 | Extropic | THRML thermodynamic hypergraphical-model library | jax_library, graph_and_schedule_models, probabilistic_workloads | Translate one THRML block-Gibbs workload into our distributional acceptance and entropy-custody receipt. |
| 1 | Normal Computing | thermox exact Ornstein-Uhlenbeck simulator | python_library, ou_reference_model, thermodynamic_linear_algebra_workloads | Add thermox-backed OU solve, inverse, exponential, and sampling fixtures to the physical-substrate assay. |
| 1 | Extropic | X0, XTR-0, and Z1 thermodynamic sampling hardware | future_sampling_card, probabilistic_circuit_taxonomy, host_communication_claim | Create an XTR-0 and Z1 capability manifest that can be satisfied by hardware, THRML, or another stochastic provider. |
| 1 | Normal Computing | Carnot CN101, CN201, and thermodynamic ASIC roadmap | ou_and_sde_operator_specifications, future_physical_asic, characterization_targets | Create a CN101 cartridge profile whose acceptance requires matching thermox output quality and a complete device-plus-host measurement boundary. |
| 2 | IHP Open PDK community | SG13G2 130 nm BiCMOS open PDK | bipolar_cmos_pdk, device_models | Compile one oscillator or relaxation reference design against SG13G2 models while refusing production qualification. |
| 2 | Normal Computing | AI-built open Verilog simulation and verification stack | verilog_simulator, formal_and_mutation_tools | Build a verification adapter that consumes cartridge-generated RTL and emits simulator, formal, mutation, and equivalence receipts. |
| 2 | OpenFASoC community | Open analog and mixed-signal SoC generation | analog_generators, temperature_and_power_generators | Wrap one OpenFASoC sensor generator as a calibrated context channel behind physical-compute-mmio/v1. |
| 2 | Tiny Tapeout and wafer.space | Commodity open-silicon shuttles | mpw_shuttle, gf180mcu_manufacturing, community_templates | Prepare a minimal measured stochastic or relaxation cartridge test macro with on-chip calibration and external receipt hooks. |
| 2 | Protean and Shepherd Nova communities | Battery-free adaptive execution and repeatable harvesting testbeds | battery_free_runtime, harvester_and_sensor_modules, energy_trace_testbed | Run one accepted workload under repeatable Shepherd energy traces with Protean-style tier selection and our receipt boundary. |
| 2 | Oscillator Ising machine research community | Coupled nonlinear oscillator optimization | oscillator_network_model, maxcut_and_graph_coloring_workloads | Define an oscillator-Ising descriptor with graph mapping, coupling, injection schedule, readout, success probability, and replay fields. |
| 2 | Purdue probabilistic computing community | p-bits and probabilistic spin logic | pbit_primitive_semantics, probabilistic_workloads | Add a p-bit cartridge profile interoperable with THRML and the thermal sampler reference. |
| 2 | Semiconductor Research Corporation and DARPA JUMP 2.0 | CHIMES heterogeneous integration | heterogeneous_integration_research, thermal_reliability_measurements | Add package, interconnect, and thermal fields to physical-cartridge handoff without binding to one integration stack. |
| 2 | Semiconductor Research Corporation and DARPA JUMP 2.0 | PRISM intelligent storage and memory | near_data_architecture_research, future_benchmarks | Add a data-movement pressure adapter linking reversibility frontier state to PRISM memory and near-data locations. |
| 2 | Semiconductor Research Corporation and DARPA JUMP 2.0 | SUPREME materials and devices | device_models, materials_measurements | Generate device-level target envelopes from SVK and PCK workload receipts rather than abstract operation counts. |
| 2 | AheadComputing | High-performance open-standard RISC-V cores | future_core_ip, riscv_ecosystem_signals | Define an Ahead-compatible host profile whose only authority is measured workload, memory, latency, and reliability receipts. |
| 3 | SkyWater, Google, and open silicon community | SKY130 open PDK | cmos_pdk, test_chip_ecosystem | Build the standard MMIO control plane and calibration sequencer in SKY130 as a portable reference. |
| 3 | Lava neuromorphic software community | Lava process model and heterogeneous backends | process_model, cpu_backend, neuromorphic_examples | Crosswalk Lava process ports and execution phases to physical-compute channels and determinism contracts. |
| 3 | Applied Brain Research and Nengo community | Nengo neural simulation and hardware backend ecosystem | model_and_simulator, backend_pattern | Create a Nengo workload adapter that emits identical model identity to CPU, simulator, and physical cartridges. |

## Execution order

Priority 1 contains the artifacts that can immediately change the architecture or the evidence floor. We first ingest thermox, THRML, CrossSim, NeuroBench, MLPerf Power, and OpenPRC as software, workload, and measurement commodities. In parallel, Chipyard and OpenASIP become host and lowering commodities, while OpenROAD supplies a reproducible digital implementation path. Vaire, Normal, and Extropic remain physical targets behind the same contracts. ARIA and SRC provide system-test and cross-layer venues whose public requirements are already aligned with the registry.

Priority 2 expands the substrate and implementation surface. PRISM, SUPREME, and CHIMES feed memory, device, package, and thermal models into the frontier. Tiny Tapeout, wafer.space, IHP, p-bits, oscillator Ising systems, and battery-free testbeds become physical experiment routes. Each enters through a software fallback and leaves a sealed receipt.

Priority 3 supplies useful portability and failure lessons. SKY130, Lava, and Nengo show how open model and backend ecosystems can survive, drift, or lose vendor support. We consume their abstractions and fixtures without inheriting their governance.

## CLI

```bash
ahead-rev-commodities --priority-max 1 --out artifacts/commodity-harvest.json
```

The report is deterministic and SHA-256 sealed. It preserves the registry identity, selected categories and priorities, gap frequency, source locators, commodity locators, and the first completion transaction for each actor.

## Evidence boundary

The registry records public claims and public artifacts as intake leads. It does not qualify the actors' physical, performance, energy, volume, timing, thermal, fabrication, or production claims. Those claims remain blocked until the corresponding code, workload, measurement, silicon, and independent acceptance artifacts are available and consumed through the relevant receipt.

The control question for every new press release, repository, paper, demo, or tapeout is: what can be pinned and ingested immediately, which complete-system seam did the actor leave exposed, and how do we force that contribution to compete behind our workload and receipt contract?
