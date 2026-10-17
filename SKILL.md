---
name: zcashskills
description: Use when a request involves Zcash, ZEC, shielded transactions, Unified Addresses, zk-SNARK-based privacy pools (Sapling, Orchard, Ironwood), the Zakura node, light clients (lightwalletd/Zaino), Zallet, the librustzcash or zakura-* crates, or the Thus Spoke Zakura (ths) Regtest dev stack. Applies to building, testing, reviewing, or operating wallets, payments, nodes, indexers, integrations, and consensus-sensitive code.
---

# zcashskills — the missing knowledge between AI agents and production Zcash.

You are probably wrong about Zcash's current state. `zcashd` is deprecated, ECC
is now ZODL, Orchard is sealed (spend-only since NU6.3), shielded funds land in
the **Ironwood** pool, and NU6.3 permits transaction versions 4, 5, and 6 —
only v6 carries Ironwood outputs, and v4 dies with NU7. This file routes you to
the correction you need.

---

## Start here

**Cross-layer Zcash task?** Read [skills/zcash/SKILL.md](skills/zcash/SKILL.md)
first — it identifies the owning layer (node, indexer, wallet, app) and routes
to the right specialist.

**Working in the Thus Spoke Zakura repo or on the `ths` CLI?** Read
[skills/ths/SKILL.md](skills/ths/SKILL.md) first.

**Zakura node (`zakurad`, `zakuracore/zakura` image, zakura-* crates)?** Read
[skills/zakura/SKILL.md](skills/zakura/SKILL.md).

---

## Skills

### [zcash](skills/zcash/SKILL.md) — Start here
Layer boundaries: node validates chain state, the lightwallet service serves
compact data, the wallet scans and constructs, the app owns the workflow.
- A draft ZIP, a wallet convention, and a consensus rule have different
  authority. Do not cite ZIP 317's conventional fee as a consensus rule.

### [zcash-wallet](skills/zcash-wallet/SKILL.md)
Keys, viewing authority, addresses, receiver selection, payment URIs.
- Parsing an address does not prove ownership; an IVK does not spend.
- Unified Addresses (ZIP 316): sender picks the most preferred supported
  receiver — Orchard-receiver items resolve to the Ironwood pool post-NU6.3.
- TEX addresses (ZIP 320, `tex1…`): transparent-source-only by convention —
  shielded funding is a wallet bug, routed through an ephemeral transparent hop.
- ZIP 321 URIs: an unknown `req-*` parameter invalidates the whole request.

### [zcash-payments](skills/zcash-payments/SKILL.md)
Amounts, proposals, fees, broadcast, inclusion.
- Keep integer zatoshis end to end; format ZEC only at the display edge.
- A timed-out send is an *unknown* outcome — reconcile the original txid before
  ever constructing a replacement.
- Expiry height `N` (ZIP 203): the tx can still be mined *in* block `N`; it
  fails at `N+1`.

### [zcash-light-client](skills/zcash-light-client/SKILL.md)
Sync, birthdays, commitment trees, reorgs.
- Equal heights with different hashes = fork. Find the common ancestor, rewind,
  rescan — a displayed balance change does not repair wallet state.
- A published scan cursor must never outrun durable wallet state.

### [zcash-protocol](skills/zcash-protocol/SKILL.md)
Consensus rules, activation boundaries, encodings, verification.
- NU6.3 sealed the Orchard pool (no new value in; cross-address transfers off)
  and added the Ironwood pool + v6 transactions (ZIPs 258, 229, 2005).
- Test rule changes at `H-1`, `H`, `H+1`; use zcash-test-vectors for encodings.

### [zakura](skills/zakura/SKILL.md)
The Zakura full node — a Zebra fork built for scale.
- `zakurad` is not `zcashd`: the legacy RPC/wallet surface runs through
  zcashd-compat sidecar mode or Zallet, not the node itself.
- Pruning and snapshots change what "full node" means; P2P v2 is experimental.

### [ths](skills/ths/SKILL.md) — THS router
Thus Spoke Zakura: disposable Regtest stack — Zakura node + lightwalletd +
`ths-server` + React dashboard, launched by the `ths` CLI.
- Regtest-only, loopback-only. Accounts 1–5 are users; account 6 is the
  mining/faucet treasury and stays hidden.
- `ths` runs prebuilt images — source edits need `build --dev` first.

### [ths-runtime](skills/ths-runtime/SKILL.md)
CLI commands, Docker instance lifecycle, cleanup ownership, endpoints.

### [ths-wallet-server](skills/ths-wallet-server/SKILL.md)
Wallet sync, treasury reward discovery, send/faucet idempotency, snapshots.

### [ths-dashboard](skills/ths-dashboard/SKILL.md)
Zod schemas, TanStack Query hooks, mutations, SSE invalidation.

### [ths-regtest-verifier](skills/ths-regtest-verifier/SKILL.md)
Live Docker evidence: `#[ignore]`d `activity_recovery` cases, real proofs.

### [ths-release](skills/ths-release/SKILL.md)
Versioned images, installer/updater, candidate → publish workflow.
