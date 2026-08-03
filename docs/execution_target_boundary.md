# Provider-Neutral Execution-Target Boundary

This boundary turns Verilator, reference software, FPGA hosts, silicon, physical substrates, and remote venues into replaceable execution-target implementations behind one sealed capsule invocation. The target may discover, prepare, execute, observe, collect, and clean up. It does not own workload identity, accepted output, fallback policy, refusal semantics, qualification, or succession.

## Qualified object

The invocation is `ahead.execution-target-invocation/v0.1`. It binds the capsule identifier, workload, descriptor, input, accepted-output digest, MMIO ABI, command surface, required capabilities, software fallback, timeout, cleanup policy, and local acceptance authority. Its capsule and complete invocation are independently content-addressed.

The attempt receipt is `ahead.execution-target-attempt/v0.1`. It embeds the exact sealed invocation, target identity, ordered stage history, observations, target artifacts, output comparison, fallback state, cleanup custody, qualification, blockers, and a canonical attempt seal.

The declared stage sequence is:

```text
discover -> prepare -> execute -> observe -> collect -> cleanup
```

A refusal or fault terminates the forward prefix. Cleanup is attempted only after preparation completed and is recorded as a separate final stage. Discovery refusal therefore cannot manufacture a prepared target or a cleanup receipt. Cleanup failure converts the attempt into a fault even when execution and output observation succeeded.

## Reference and physical refusal fixtures

The deterministic reference adapter implements the complete stage sequence, reports the observed output independently of the invocation builder, emits a target receipt digest, uses the declared software fallback, and completes cleanup. It qualifies only as `reference_target_execution_proved`.

The unbound FPGA adapter advertises the portable MMIO capability but refuses during discovery because no transport or programming authority is bound. Its valid attempt receipt contains only one refused discovery record. Preparation, execution, observation, collection, and cleanup remain unreachable.

## Claim boundary

An accepted target attempt proves only that the exact capsule moved through the declared target stages, reproduced the accepted output digest, retained fallback state, emitted a target receipt, and satisfied cleanup policy. Every attempt retains these blockers:

```text
PHYSICAL_EXECUTION_UNPROVEN
PHYSICAL_ENERGY_UNMEASURED
TIMING_THERMAL_VOLUME_UNMEASURED
COMPLETE_SYSTEM_EVP_UNMEASURED
INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING
```

A future physical session must bind programming authority, transport, device identity, reset, clocks, power, instruments, calibration, environment, timebase, raw return, and independent acceptance before any of those blockers can move. This target boundary cannot self-authorize physical execution or complete-system advantage.

## Control question

Can the same content-addressed capsule move from reference software through RTL simulation, FPGA or silicon, physical substrate, and remote venues while preserving command, refusal, fallback, cleanup, output acceptance, and receipt semantics at every replacement seam?
