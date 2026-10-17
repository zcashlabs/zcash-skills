# Versioned facts

Single source of truth for version- and date-sensitive claims used by the
skills. When upstream changes one of these, update the value **and** the
`verified` date here, then run `python3 docs/check-facts.py` to find skill text
that disagrees. `pattern` is a Python regex — the checker flags any repo `.md`
file whose match text differs from `value`.

## Protocol / network upgrades

| Fact | Value | Verified | Source |
| --- | --- | --- | --- |
| Current deployed upgrade | NU6.3 (Ironwood, v6 tx format) | 2026-10-06 | [ZIP 258](https://zips.z.cash/zip-0258) |
| NU7 status | Draft; Testnet activation height 4,465,026 (2026-10-06); Mainnet height assigned 2026-10-20, activation target 2026-11-05 | 2026-10-06 | [ZIP 259](https://zips.z.cash/zip-0259) |
| NU7 consensus branch ID | `0x77190AD9` | 2026-10-06 | ZIP 259 |
| NU7 min network protocol version | Testnet `170180` / Mainnet `170190` | 2026-10-06 | ZIP 259 |
| NU7 block spacing / shielded action limits | 25 s; global 330, Orchard 330, Ironwood 330, Sapling 300 I/O, Sprout 0 | 2026-10-06 | [ZIP 218](https://zips.z.cash/zip-0218) |
| NU7 default expiry delta guidance | 120 blocks (was 40; ~50 min wall-clock) — non-consensus | 2026-10-06 | ZIP 218 |
| NU6.3 activation heights | Mainnet 3,428,143; Testnet 4,134,000 | 2026-10-08 | ZIP 258 |
| NU6.3 consensus branch ID | `0x37A5165B` | 2026-10-08 | ZIP 258 |
| NU6.3 min network protocol version | `170160` (both networks — last shared value; ZIP 204 requires distinct from NU7) | 2026-10-08 | ZIP 258 |
| ZIP 316 (Unified Addresses) | Revision 0 active; Revision 1 withdrawn; Revision 2 draft | 2026-10-08 | [ZIP 316](https://zips.z.cash/zip-0316) |
| ZIP 317 (conventional fee) | Rev 0 active; Rev 1 (Ironwood contribution) enacted at NU6.3; Rev 2 draft | 2026-10-06 | [ZIP 317](https://zips.z.cash/zip-0317) |
| ZIP 320 (TEX addresses) | Active; `tex`/`textest` HRP, Bech32m P2PKH re-encode | 2026-10-06 | [ZIP 320](https://zips.z.cash/zip-0320) |
| ZIP 321 (payment URIs) | Active | 2026-10-06 | [ZIP 321](https://zips.z.cash/zip-0321) |

## Thus Spoke Zakura (`zcashlabs/thus-spoke-zakura`)

| Fact | Value | Verified | Source |
| --- | --- | --- | --- |
| Workspace version | `0.3.0` | 2026-10-08 | `Cargo.toml` |
| Packages / binary | `ths-cli`, `ths-server`; package `thus-spoke-zakura`, binary `ths` | 2026-10-02 | `Cargo.toml` |
| Rust toolchain | `1.98.0` (`rust-toolchain.toml`); Node `24` for `web/` | 2026-10-02 | `rust-toolchain.toml`, `ci.yml` |
| Pinned node image | `zakuracore/zakura:1.6.0` (`ZAKURA_IMAGE` in `runtime/images.rs`) | 2026-10-16 | `crates/ths-cli/src/runtime/images.rs` |
| zcashd-compat sidecar image | `zakuracore/zcashd` — current docs tag `v1.2.0` (zcashd-versioned, independent of Zakura tags) | 2026-10-08 | `zakura` repo `docs/zcashd-compat.md` |
| App / lightwalletd images | `ghcr.io/zcashlabs/thus-spoke-zakura-app`, `-lightwalletd` | 2026-10-16 | `crates/ths-cli/src/runtime/images.rs`, `release.yml` |
| Wallet crate pins | `zakura-{keys,primitives,proofs,orchard,sapling-crypto,transparent,zip321} = 2.2.0`; `zakura-client-{backend,sqlite} = 0.1.0-rc7`; `zakura-pczt = 0.1.0-rc4`; imported under `zcash_*` aliases | 2026-10-08 | `crates/ths-server/Cargo.toml` |
| Account layout | accounts `1..=5` user-facing; account `6` treasury/miner | 2026-10-02 | `db.rs` |
| Default loopback ports | dashboard `32805`, RPC `18232`, lightwalletd `9067`, P2P `18233` (+offset stride 10) | 2026-10-16 | `crates/ths-cli/src/runtime/instance.rs` |
| Shielded pool | Ironwood; `orchard` rejected as destination pool post-NU6.3 | 2026-10-02 | `crates/ths-server/src/api/payments.rs`, `wallet/payments.rs` |
| Wallet DB schema names | `ext_tsz_*` — intentionally kept for migration stability despite the crate rename | 2026-10-16 | `crates/ths-server/src/wallet/journal.rs`, `wallet/recovery.rs` |
| Dev API env var | `THS_DEV_API` (not `TSZ_DEV_API`) | 2026-10-02 | `AGENTS.md` |
| Regtest NU activation | NU6–NU6.3 at height 1 in generated `zakurad.toml`; `regtest_network().nu7 = None` | 2026-10-06 | `crates/ths-server/src/bootstrap/config.rs`, `wallet.rs` |
| Address-faucet idempotency | `faucet_address` requires a key; `claim_address_faucet` persists to `address_faucets`; replay resumes the operation; `activities`/`address_faucets` share one key space (`IdempotencyConflict`) | 2026-10-16 | `crates/ths-server/src/api/payments.rs`, `db/address_faucet.rs`, `db/activity.rs`, `payments/progression.rs` |
| Address-faucet replay tests | `confirmed_address_faucet_replays_without_sending_a_second_payment`, `address_faucet_replay_survives_restart_and_rejects_conflicting_intents`, `address_faucet_reconciles_the_original_txid_after_a_lost_broadcast_response` | 2026-10-16 | `crates/ths-server/tests/unit/api/payments/tests.rs`, `tests/unit/db/address_faucet/tests.rs`, `tests/unit/payments/submission/tests.rs`; pair legacy adapter tests with production progression tests |
| CI live cases | `activity_recovery` selects six: `broadcast_recovers_after_auto_mine_failure`, `concurrent_identical_sends_have_one_chain_effect`, `address_faucet_retry_after_server_restart_pays_each_destination_once`, `queued_send_retry_survives_lost_response_and_restart`, `queued_external_faucet_retry_survives_lost_response_and_restart`, `reorg_and_rollback_preserve_canonical_wallet_and_payment_state`; the 10k-block workload is not selected | 2026-10-17 | `.github/workflows/ci.yml` |
| Chain SSE invalidation | status, blocks, block, transaction, address; mempool is omitted | 2026-10-16 | `web/src/hooks/useServerEvents.ts` `TOPICS.chain` |
| Runtime / payment orchestration owners | `runtime/startup.rs::start_owned`; `payments/progression.rs::payment_confirmation_loop` | 2026-10-16 | `crates/ths-cli/src/runtime/startup.rs`, `crates/ths-server/src/payments/progression.rs` |

## Machine-checkable facts

Each block maps a `pattern` (regex appearing in repo docs) to the canonical
`value`. A doc line is stale when the match does not contain the value after
normalisation (backticks, commas, spaces and case ignored) — a pattern may match
a span around the value, but a truncated value never passes. Without a `pattern`,
only the verification date and optional upstream oracle are checked. Keep one
`pattern` per fact; make it match the whole token
(e.g. `name:version`). A block may instead set `kind: forbid` (no `value`
needed): every match of the pattern is then a stale-claim failure — use this
for "X does not exist / X is not required" statements that upstream has since
made false. With `negation: true`, a forbid match inside a negated sentence
("X is *not* a consensus rule") is skipped, so the fact can cover claims that
correct prose correctly denies.

A block can also name its oracle: `upstream` is a raw URL of the file that
states the value, and `extract` is a regex whose first group captures it.
`python3 docs/check-facts.py --upstream` compares every oracle with `value` by
exact normalised equality, and the PR fact check uses the same oracles for the
lines a PR changes. Prefer an oracle whenever the value lives in a parseable
upstream file — this works for `.rst` ZIP sources as well as `.md`.

For unordered source lists, set `extract_all: true`: every first capture is
collected into a comma-separated set and compared without regard to order. Use
this for selected CI case names. A `coverage` regex scopes extraction to each
selector line; every scope must yield exactly one capture or verification is
incomplete, including partially changed selector syntax. Behavioral oracles may omit `pattern` and
compare a source expression or owning symbol directly. Changed expressions or
case sets are drift; moved files and unrecognized formats leave verification
incomplete. A source-text oracle detects change for review; it does not prove
runtime behavior.

Exit statuses: `0` means the requested checks completed without contradictions,
`1` means a contradiction or invalid definition, and `2` means upstream
verification was incomplete. Without `--upstream`, `0` establishes local claim
consistency only. The nightly workflow reports and fails incomplete verification;
the PR claim report keeps its advisory policy and labels unverified rows.

```facts
id: ths-ci-live-cases
value: address_faucet_retry_after_server_restart_pays_each_destination_once, broadcast_recovers_after_auto_mine_failure, concurrent_identical_sends_have_one_chain_effect, queued_external_faucet_retry_survives_lost_response_and_restart, queued_send_retry_survives_lost_response_and_restart, reorg_and_rollback_preserve_canonical_wallet_and_payment_state
verified: 2026-10-16
source: .github/workflows/ci.yml — exact ignored live selections
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/.github/workflows/ci.yml
extract: --exact\s+([A-Za-z_][A-Za-z0-9_]*)
extract_all: true
coverage: ^.*--ignored\b.*$
```

```facts
id: ths-chain-invalidation
value: [[...queryKeys.status], ['blocks'], ['block'], ['transaction'], ['address']]
verified: 2026-10-16
source: web/src/hooks/useServerEvents.ts — TOPICS.chain expression
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/web/src/hooks/useServerEvents.ts
extract: ^  chain:\s*(\[[^\n]+\]),$
```

```facts
id: ths-runtime-startup-owner
value: start_owned
verified: 2026-10-16
source: crates/ths-cli/src/runtime/startup.rs — production startup entry
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/crates/ths-cli/src/runtime/startup.rs
extract: ^\s*fn (start_owned)\(
```

```facts
id: ths-payment-worker-owner
value: payment_confirmation_loop
verified: 2026-10-16
source: crates/ths-server/src/payments/progression.rs — background payment progression
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/crates/ths-server/src/payments/progression.rs
extract: ^pub\(crate\) async fn (payment_confirmation_loop)\(
```

```facts
id: zakura-image
value: zakuracore/zakura:1.6.0
pattern: zakuracore/zakura:[0-9a-zA-Z.\-]+
verified: 2026-10-16
source: crates/ths-cli/src/runtime/images.rs (ZAKURA_IMAGE)
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/crates/ths-cli/src/runtime/images.rs
extract: const ZAKURA_IMAGE: &str = "([^"]+)"
```

```facts
id: ths-rust-toolchain
value: 1.98.0
pattern: Rust 1\.[0-9]+\.[0-9]+|rust-toolchain[^;\n]*1\.[0-9]+\.[0-9]+
verified: 2026-10-02
source: rust-toolchain.toml
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/rust-toolchain.toml
extract: ^channel = "([^"]+)"
```

```facts
id: nu7-testnet-height
value: 4,465,026
pattern: 4,?465,?026|NU7[^\n]{0,40}Testnet[^\n]{0,40}[0-9][0-9,]{5,}[0-9]
verified: 2026-10-06
source: ZIP 259
upstream: https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0259.md
extract: ^ACTIVATION_HEIGHT \(NU7\)\n: Testnet: ([0-9]+)
```

```facts
id: nu7-branch-id
value: 0x77190AD9
pattern: 0x77190AD9
verified: 2026-10-09
source: ZIP 259
upstream: https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0259.md
extract: ^CONSENSUS_BRANCH_ID\n: `?(0x[0-9A-Fa-f]{8})
```

```facts
id: nu63-branch-id
value: 0x37A5165B
pattern: 0x37A5165B
verified: 2026-10-09
source: ZIP 258
upstream: https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0258.md
extract: ^CONSENSUS_BRANCH_ID\n: `?(0x[0-9A-Fa-f]{8})
```

```facts
id: nu63-mainnet-height
value: 3,428,143
verified: 2026-10-09
source: ZIP 258
upstream: https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0258.md
extract: ^ACTIVATION_HEIGHT \(NU6\.3\)\n: Testnet: [0-9]+\n: Mainnet: ([0-9]+)
```

```facts
id: ths-workspace-version
value: 0.3.0
verified: 2026-10-09
source: Cargo.toml ([workspace.package])
upstream: https://raw.githubusercontent.com/zcashlabs/thus-spoke-zakura/main/Cargo.toml
extract: ^\[workspace\.package\]\n(?:.*\n)*?version = "([^"]+)"
```

```facts
id: address-faucet-idempotency
kind: forbid
pattern: faucet[^\n]{0,100}(?:no idempotency|(?:creates?|has|requires?|needs?|with) no activity row|does not (?:create|persist)[^\n]{0,30}(?:activity|row)|without (?:an? )?idempotency)|(?:no idempotency|no activity row)[^\n]{0,60}faucet
verified: 2026-10-16
source: crates/ths-server/src/api/payments.rs — production faucet_address requires the key and persists via db/address_faucet.rs::claim_address_faucet; payments/progression.rs resumes intent
```

```facts
id: nu63-tx-versions
kind: forbid
pattern: transactions are (?:all )?version 6|(?:all|only) transactions (?:are|use|must be) (?:v6|version 6)|v6[- ]only transactions|version 6 transactions only
verified: 2026-10-08
source: ZIPs 229/2003 — NU6.3 permits v4, v5, and v6; v6 is required for Ironwood outputs and v4 is disallowed only from NU7
```
```facts
id: nu63-orchard-receives
kind: forbid
negation: true
pattern: (?i)\b(?:new|incoming)\s+(?:shielded\s+)?(?:value|notes?|outputs?)\b[^\n.;:!]{0,30}\b(?:goes?|flows?|sent|moves?|moved|enters?|entered|to|into)\b[^\n.;:!]{0,15}\bOrchard\b|\bOrchard\b[^\n.;:!]{0,40}\b(?:receives?|accepts?|gets)\s+(?:new|incoming)\b
verified: 2026-10-12
source: ZIP 229/NU6.3 — new shielded value goes to Ironwood; Orchard is spend-only for new value post-NU6.3
```

```facts
id: zip317-consensus
kind: forbid
negation: true
pattern: (?i)\bZIPs? ?317\b[^\n]{0,50}\bconsensus\b|\bconsensus\b[^\n]{0,50}\bZIPs? ?317\b
verified: 2026-10-12
source: ZIP 317 — the proportional fee is a wallet convention, not a consensus validity rule
```

```facts
id: zip320-tex-fixture
value: t1VmmGiyjVNeCjxDZzg7vZmd99WyzVby9yC
pattern: t1VmmGiyjVNeCjxDZzg7vZmd99WyzVby9yC
verified: 2026-10-12
source: ZIP 320 reference implementation — transparent P2PKH fixture address (rst oracle coverage)
upstream: https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0320.rst
extract: bs58check\.decode\('([^']+)'\)
```
