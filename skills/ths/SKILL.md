---
name: ths
description: Use when a Thus Spoke Zakura change crosses the launcher, wallet server, dashboard, testing, or release boundaries, or when its owning subsystem is unclear.
---

# Thus Spoke Zakura developer

Read the current repository `AGENTS.md` and relevant source before editing. This repository runs a disposable Zcash Regtest stack: `ths` starts Zakura, lightwalletd, and an app image containing `ths-server` and the dashboard. Treat the pinned Zakura wallet crates in `Cargo.toml` and `crates/ths-server/Cargo.toml` as the implementation in use, even where imports have `zcash_*` aliases. Use the general Zcash skills for protocol or wallet semantics, then confirm behavior in these pinned crates.

The local chain activates every network upgrade through NU6.3 at height 1, so shielded funds live in the Ironwood pool — the wallet API rejects `orchard` as a pool, and Orchard can only be spent from, not received into.

## Choose the affected path

| Work | Read |
| --- | --- |
| CLI commands, instance lifecycle, Docker resources, image build or install | [ths-runtime](../ths-runtime/SKILL.md) |
| Wallet sync, treasury, payments, API, activity, persisted state | [ths-wallet-server](../ths-wallet-server/SKILL.md) |
| Dashboard balances, forms, explorer, requests, SSE and cache updates | [ths-dashboard](../ths-dashboard/SKILL.md) |
| Real Docker, proofs, recovery or reward-history validation | [ths-regtest-verifier](../ths-regtest-verifier/SKILL.md) |
| Versioned images, installer, updater, candidate or public release | [ths-release](../ths-release/SKILL.md) |

Keep changes Regtest-only. Host-published services bind to loopback; cleanup must preserve resources outside the selected instance. The launcher reuses or deletes a Docker resource only when its instance label names the selected instance (see `ths-runtime`); keep new deletion paths behind that check. Accounts 1–5 are user accounts and account 6 is the mining and faucet treasury. The server wallet snapshot owns displayed balances. Preserve the relevant endpoint's idempotency and activity recovery behavior when touching money movement. Select checks from `AGENTS.md` and use `ths-regtest-verifier` for live Docker evidence.

For a cross-layer change, name the owner of the behavior and follow one request or sync pass end to end. Example: after mining, Zakura and lightwalletd provide chain data, `ths-server` updates the wallet and publishes a snapshot, and the dashboard refetches through its query hooks. Test the boundary where the claimed change becomes observable, using the image or binary actually built from the edited source.
