# Zakura node reference

Source: [zakura-core/zakura](https://github.com/zakura-core/zakura) (binary `zakurad`). Verify versions at use time — this page reflects the state observed when the skill was written.

## Install and run

| Path | Command / artifact |
| --- | --- |
| Interactive installer | `curl -fsSL https://zakura.com/install.sh \| bash` — can set up standard Zakura or a zcashd-compat variant |
| Docker | `zakuracore/zakura:<tag>`; compat sidecar image `zakuracore/zcashd:<tag>` |
| crates.io | `zakura` binary crate plus the `zakura-*` library family |
| Source | needs Rust, libclang, and a C++ compiler |

Basic mainnet Docker run:

```sh
docker run -d \
  --name zakura \
  -p 8233:8233 \
  -v zakurad-cache:/home/zakura/.cache/zakura \
  zakuracore/zakura:<tag>
```

`8233` is Mainnet P2P (`18233` on Testnet). The volume persists chain state across restarts. In Thus Spoke Zakura the Regtest node listens on loopback `18232` (RPC) / `18233` (P2P) via the pinned `zakuracore/zakura` image — see the `ths` skills.

## zcashd-compat mode

For operators (exchanges, custodians) whose integration depends on the `zcashd` wallet and RPC surface. Zakura is the consensus node facing the Zcash network; `zcashd` runs as a **P2P sidecar** making a single outbound connection to the local Zakura and listening to nothing else.

```text
Zcash network ═P2P (8233)═▶ zakurad ◀═P2P, internal only═ zcashd ◀─wallet RPC, ZMQ─ your systems
                            (front)   connect=zakura:8233  (sidecar)
```

zcashd config that produces this topology:

```text
connect=<zakura-host>:8233   # one outbound peer: Zakura
listen=0                    # no inbound P2P
```

| Provided by `zcashd` (unchanged) | Moved to Zakura |
| --- | --- |
| Wallet RPC methods (transparent + Sapling) | Public P2P networking and peer selection |
| Local block files, chainstate, indexes | Network-facing block and transaction relay |
| ZMQ notifications | Block templates for miners |
| Local RPC response semantics | DNS seeding and peer discovery |

Four install modes under `--zcashd-compat`:

| Mode | Behavior |
| --- | --- |
| `split-binary` (default) | Installer drops `zakurad` + `zcashd`; operator runs both |
| `supervised` | Zakura downloads a hash-pinned `zcashd` and manages it (`[zcashd_compat].manage_zcashd = true`) |
| `docker-split-containers` | Two `docker run` commands |
| `docker-supervised` | One supervised container run |

Do not imply shielded/Ironwood-era wallet features exist on the sidecar — the sidecar's wallet RPC is the legacy transparent + Sapling surface.

## Pruning and snapshots

- Native block pruning with configurable retention — a pruned Zakura is a full validating node but does not keep full historical blocks. Resolve the retention setting and the range available from the selected node before relying on historical RPCs.
- Snapshot bootstrapping trades trust: the skipped range is not independently verified by the node. Say so when recommending it.

## Historical benchmark claims

Treat the previously reported ~11 GB pruned snapshot and ~680× bootstrap speedup over P2P sync associated with [the snapshot page](https://zakura.com/snapshots) as historical claims requiring verification. They are not current measurements or defaults. Before quoting either, locate the dated source or archived revision, identify the Zakura version, chain height, snapshot format, pruning retention, hardware, network, and comparison workload, and verify what was timed or counted. If those conditions cannot be recovered, omit the number. For a current recommendation, measure the selected version and workload separately rather than carrying a historical ratio forward.

## P2P v2 (experimental)

A new transport stack (iroh/QUIC-based; see the `iroh`/`iroh-quinn` forks under `zakura-core`) targeting sub-500 ms worst-case block propagation, mempool aggregation for Project Tachyon, and bandwidth-bound sync. Off by default on Mainnet; documented DoS risks; not production-hardened. Do not enable it for someone else's node without flagging the maturity.

## Crate map

Node crates mirror the `zebra_*` layout (`zakura-chain`, `zakura-state`, `zakura-consensus`, `zakura-network`, `zakura-rpc`, `zakura-script`, `zakura-node-services`, `zakura-header-chain`, `zakura-mmr-tree`, `zakura-test`, `zakura-utils`, `zakura-jsonl-trace`, plus the publish-only `zakura-assets` crate excluded from the workspace). Wallet/crypto crates live separately:

- `zakura-core/common` — `zakura-keys`, `zakura-primitives`, `zakura-proofs`, `zakura-orchard`, `zakura-sapling-crypto`, `zakura-transparent`, `zakura-zip321`, `zakura-pczt`, `zakura-protocol`, plus `zakura-vct-sprout-history*`
- `zakura-core/wallet-libraries` — `zakura-client-backend`, `zakura-client-sqlite`, `zakura-wallet-lib` (the `zcash_client_*` wallet-layer crates forked onto the Zakura crypto stack)
- `zakura-core/ironwood-formal-verification` — Lean formal verification of the Ironwood pool
- `zakura-core/librustzcash` — fork of the upstream Rust assets

Downstream projects pin exact versions and may alias packages (e.g. `zcash_keys = { package = "zakura-keys", ... }`). Always read the consumer's `Cargo.toml`/`Cargo.lock` rather than assuming crate names.

## Useful docs in-repo

`docs/` holds `zcashd-compat.md`, `design/`, `specs/`, `decisions/`, `upstream-sync/`, `verify.md`, `security.md`, `cpu-profiling.md`, and release/runbooks (`pr-node-do-setup.md`, `security-hotfix-release.md`, `header-chain-v1.4-migration.md`). Prefer the doc at the checked-out revision over this summary.
