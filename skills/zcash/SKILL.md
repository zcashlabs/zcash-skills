---
name: zcash
description: Use when a Zcash development task crosses wallet, payment, light-client, node, or protocol boundaries, or when the responsible Zcash layer is unclear.
---

# Zcash

Use this skill for Zcash behavior across implementations and languages. First identify the network, target height, active protocol rules, and the exact library and service versions in use. Apply the governing specification to the intended behavior, then inspect the selected implementation for its actual API and policy. A draft ZIP, a wallet convention, and a consensus rule have different authority.

Keep these boundaries explicit: the node validates chain state; an indexer or lightwallet service (lightwalletd, Zaino) serves compact data; a wallet scans, tracks spendable state, and constructs transactions; an application owns its user workflow and display. Confirm which layer owns the decision before changing code or claiming a result.

Know the current landscape before citing components. `zcashd` is deprecated: production nodes are [Zebra](https://github.com/ZcashFoundation/zebra) or [Zakura](https://github.com/zakura-core/zakura) (a Zebra fork); the legacy wallet surface moves to [Zallet](https://github.com/zcash/zallet) or zcashd-compat sidecar mode. The wallet stack is `librustzcash` crates or their `zakura-*` forks; ZODL ships the mobile SDKs and apps. Since NU6.3, new shielded value goes to the Ironwood pool and the Orchard pool is spend-only — "Orchard receiver" in a Unified Address resolves to Ironwood for new outputs. Verify any of these before relying on them; the ecosystem moves.

For each cross-layer request, write down the user-visible result, the layer that decides it, the neighboring layer that supplies evidence, and the state that must survive failure or restart. Trace one real path through those layers before proposing a change. For example, a Unified Address send uses wallet receiver selection, payment proposal and broadcast, then chain scanning to establish inclusion; a node accepting the broadcast does not establish the wallet's final balance.

## Choose the specialist

| Task | Read |
| --- | --- |
| Keys, viewing authority, addresses, receiver choice, payment URIs | [zcash-wallet](../zcash-wallet/SKILL.md) |
| Amounts, proposals, fees, privacy of spends, broadcast and inclusion | [zcash-payments](../zcash-payments/SKILL.md) |
| Light-client sync, birthdays, commitment trees, reorgs, service boundaries | [zcash-light-client](../zcash-light-client/SKILL.md) |
| Consensus rules, transaction formats, activation, node validation | [zcash-protocol](../zcash-protocol/SKILL.md) |
| Zakura node operation, zcashd-compat mode, pruning/snapshots, Regtest infra | [zakura](../zakura/SKILL.md) |
| Work inside the Thus Spoke Zakura repo or its `ths` CLI | [ths](../ths/SKILL.md) |

For Rust implementation details, use an available Rust skill and the repository's pinned crate documentation. For a particular application, also follow that repository's instructions. This skill does not encode any application's account layout, Docker setup, or release process.
