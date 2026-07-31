# Reversibility Frontier

The v0.9 frontier surface changes the unit of analysis from a mnemonic count to an information ledger. Every instantiated instruction is classified by its state transform, operand aliases, overwritten state, reversal metadata, and admissible lowering strategies.

## The new object

For a fixed workload and accepted-output contract, the frontier records the trade space among:

- intrinsic information erasure;
- branch and predecessor metadata;
- retained history;
- ancilla allocation;
- recomputation and uncomputation;
- hot and cold execution domains;
- domain crossings;
- modeled latency overhead; and
- the physical recovery fraction required for energy parity under an explicit assumption profile.

The output is a vector of strategies. There is no universal scalar EVP score. The accepted-output contract is also checked for a result definition, quality rule, accepted work unit, and stable contract identity so a workload denominator cannot be changed silently.

## Semantic admission

An opcode name does not establish reversibility. Operand instantiation matters. In particular:

- `RXOR r1, r1` maps every input word to zero and is rejected.
- `RMODADD r1, r1` performs doubling modulo `2^N`, which is two-to-one and is rejected.
- `RSWAP r1, r1` is a reversible identity operation.
- `REXCH` remains admissible only when the destination does not alias the address-base register.

The bounded bijectivity verifier exhaustively searches a reduced word domain and emits a collision witness for non-bijective transforms. Enumeration is fail-bounded by a configurable maximum state count so a wide three-register transform cannot exhaust the analysis host. This is semantic evidence, not physical evidence.

## Evidence boundary

The artifact can establish information semantics, candidate compiler lowerings, normalized architecture pressure, and break-even equations. It cannot establish physical charge recovery, measured joule savings, thermal closure, occupied volume, timing closure, or manufacturable silicon. Those claims remain blocked until a physical receipt closes them.

## CLI

```bash
ahead-rev-frontier examples/asm/mixed_frontier.asm \
  --accepted-output examples/asm/accepted-output.json \
  --out artifacts/mixed-frontier.json
```

The command returns exit code `2` when semantic invalidity makes the artifact inadmissible. An artifact with valid semantics remains a `modeled_candidate` until physical and workload-acceptance evidence is supplied.
