---
name: zakura
description: Use when running, integrating, or reviewing the Zakura Zcash full node (zakurad, zakuracore/zakura image, zakura-* crates), including zcashd compatibility mode, pruning and snapshots, Regtest deployments like Thus Spoke Zakura, or its experimental P2P v2 stack.
---

# Zakura

Zakura is a consensus-compatible Zcash full node in Rust, forked from [Zebra](https://github.com/ZcashFoundation/zebra) and developed at [zakura-core/zakura](https://github.com/zakura-core/zakura). It is a node — validation, networking, chain state — not a wallet. Do not treat it as a renamed `zcashd`: the legacy wallet/RPC surface runs through zcashd-compat mode or [Zallet](https://github.com/zcash/zallet), not inside `zakurad`.

For deployment, load [install paths](references/node.md#install-and-run); for legacy RPCs, load [compat topology](references/node.md#zcashd-compat-mode). For disk/history or bootstrap claims, load [pruning and snapshots](references/node.md#pruning-and-snapshots); for numerical speed/size claims, also load [historical benchmark verification](references/node.md#historical-benchmark-claims). For transport changes, load [P2P v2](references/node.md#p2p-v2-experimental); for dependencies, load [the crate map](references/node.md#crate-map).

## Core workflow

1. Resolve the deployment shape before advising: binary installer, Docker image (`zakuracore/zakura`), crates.io build, or embedded in a stack like Thus Spoke Zakura. Each has different versioning.
2. Identify which RPC surface the consumer needs. Modern gRPC/JSON-RPC is served by the node and indexers; legacy `zcashd` wallet RPCs exist only under zcashd-compat (a supervised or externally managed `zcashd` P2P sidecar — Zakura is the network-facing node, zcashd talks only to it).
3. Check pruning and snapshot assumptions before promising historical data. A pruned node keeps configurable retention, not full history; a snapshot skips independent verification of its bootstrap range. Establish size and speed from a versioned source and the measured workload before quoting them.
4. Keep feature maturity honest: P2P v2 (QUIC/iroh-based transport, mempool aggregation aimed at Project Tachyon) is experimental, off by default on Mainnet, and has known DoS risks.

## Boundaries that matter

- Zakura validates and serves chain data; a separate lightwallet service (lightwalletd today, Zaino going forward) serves light clients; wallet construction lives in the `librustzcash`/`zakura-*` client crates. A `zakurad` RPC answer is node truth, not wallet state.
- Regtest is a supported deployment — Thus Spoke Zakura pins `zakuracore/zakura:1.6.0` for exactly this — but a Regtest result proves nothing about Mainnet peer behavior, which is where zcashd-compat and P2P v2 live.
- Distinguish node crates from crypto/wallet crates. Dependents may import the wallet family under `zcash_*` aliases; resolve the real packages in `Cargo.toml` and `Cargo.lock` before applying upstream API documentation.

## Review examples

- "Run a Zcash node" is ambiguous: sync target, disk budget (pruning), bootstrap path (snapshot vs P2P), and whether the caller needs legacy `zcashd` RPCs all change the answer.
- A `zcashd` RPC call failing against `zakurad` directly is expected, not a bug — check whether the deployment runs the compat sidecar.
- Claiming a speedup over Zebra or P2P sync requires a pinned version and workload; report the measurement or omit it.

Report the Zakura version or image tag, network, deployment shape, enabled modes (compat, pruning retention, P2P v2), and which layer answered each observation.
