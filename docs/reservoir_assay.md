# Reservoir Compute Assay

A changing physical system is not admitted as a compute substrate merely because it produces a signal. The reservoir assay asks whether the substrate response improves held-out task performance over the raw stimulus when both are evaluated with the same deterministic readout family.

Each episode binds the presented or observed stimulus, the candidate substrate response, train or test partition, accepted label, calibration hash, environmental hash, evidence class, and whether a software fallback produced the response. The assay trains one nearest-centroid readout on raw stimuli and another on substrate responses.

```text
compute gain = substrate-response accuracy - raw-stimulus accuracy
```

A positive compute gain means the declared dynamics created task-relevant separation for this dataset and readout. It does not by itself establish a general-purpose computer, net energy advantage, or deployment readiness.

The reference fixture is XOR-like. The raw stimulus centroids coincide, producing 0.5 held-out accuracy. The synthetic reservoir responses separate the classes and produce 1.0 accuracy, for a compute gain of 0.5. Because those episodes are simulated and produced by fallback, the result is `software_assay_pass`, not a physical-compute finding.

A `physical_compute_candidate` additionally requires every episode to be measured and produced without fallback. Even then, end-to-end advantage remains blocked until occupied volume, timing, thermal behavior, acquisition, readout, control, and full-boundary energy are closed by EVP receipts.

This makes the physical world a commodity substrate surface. A plant, structure, fluid, body, weather field, oscillator network, stochastic device, or engineered reservoir can replace the response vectors while retaining the same task, split, readout, calibration custody, software fallback, and receipt semantics. The control question is whether the measured response adds held-out separation beyond the raw stimulus and whether that gain survives the complete system accounting.
