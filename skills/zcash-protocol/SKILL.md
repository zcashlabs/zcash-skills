---
name: zcash-protocol
description: Use when changing or evaluating Zcash consensus rules, network-upgrade activation, transaction encodings, proof verification, or node validation.
---

# Zcash protocol

Resolve the target network, block height, activated upgrade, transaction version, and governing specification revision before editing or reviewing consensus-sensitive code.

For a disputed rule or rejection, load [rule classification](references/protocol-consensus.md#choose-the-governing-rule). For NU6.3 pool or transaction behavior, load [Ironwood](references/protocol-consensus.md#nu63-and-the-ironwood-pool); for NU7 activation, branch IDs, or changed expiry defaults, load [NU7](references/protocol-consensus.md#nu7-zip-259). For a boundary test, load [implementation tracing](references/protocol-consensus.md#trace-the-implementation) and [the evidence matrix](references/protocol-consensus.md#evidence-matrix). For v5 transaction IDs and authorization, load [the worked transaction task](references/protocol-consensus.md#worked-task-v5-transaction-effects-and-authorization).

Keep consensus validity distinct from node mempool policy and wallet construction choices. Use the applicable protocol specification and ZIPs to define expected behavior; use the pinned implementation to locate the code path. Exercise exact boundary heights, malformed encodings, and published vectors where applicable. Investigate differences between implementations before deciding which is correct.

## Core workflow

1. State the exact rule and its activation context before examining the implementation.
2. Trace the byte representation and validation call reached at the target height.
3. Derive positive and negative cases from the rule and [official test vectors](https://github.com/zcash/zcash-test-vectors).
4. Run the relevant node or primitive tests; report the rule, vectors, configurations, and remaining uncertainty.

## Review examples

- For a rule activated at `H`, exercise `H-1`, `H`, and `H+1` with the same encoded case where the format permits it.
- For expiry height `N`, check block validity at `N` and `N+1`; do not use mempool rejection as the consensus oracle.
- For a fee dispute, identify whether the claim comes from ZIP 317 wallet guidance, node relay policy, or an actual block-validity rule.
- For an Orchard-pool claim post-NU6.3, name whether it is a spend (allowed, with `enableCrossAddress` off), a change note, or a new output (forbidden — that output belongs to Ironwood).
- For a NU7 rehearsal on Regtest, assign the upgrade a deferred activation height in the node's regtest parameters and verify the wallet's activation map matches — wallet and node disagreeing about `nu7` is a real failure mode.

Report the governing document revision, target network and height, exact bytes or vector, code path reached, and which layer accepted or rejected it.
