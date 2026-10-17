# Wallet server

## Current ownership map

| Boundary | Current owner |
| --- | --- |
| Process entry, argument parsing, startup and background tasks | `crates/ths-server/src/main.rs`, `lib.rs`, `args.rs`, `bootstrap.rs`, `bootstrap/config.rs` |
| Zakura JSON-RPC and node-selected chain checkpoint | `crates/ths-server/src/rpc.rs` |
| lightwalletd download, rewind, transparent discovery, scan ranges | `crates/ths-server/src/reconcile.rs` |
| Pinned wallet API and balances; SDK payment creation, journal, submission | `crates/ths-server/src/wallet.rs`, `wallet/payments.rs`, `wallet/journal.rs`, `wallet/submission.rs` |
| Store and account constants; schema, accounts, activity claims, address-faucet claims | `crates/ths-server/src/db.rs`, `db/schema.rs`, `db/accounts.rs`, `db/activity.rs`, `db/address_faucet.rs` |
| Atomic treasury reward import, cursor extension, rewind | `crates/ths-server/src/wallet/recovery.rs` |
| State and wallet snapshot publication / sync loop | `crates/ths-server/src/state.rs`, `sync.rs` |
| HTTP routing; status, payment validation/claims, mining, explorer, events, errors | `crates/ths-server/src/api.rs`, `api/status.rs`, `api/payments.rs`, `api/mining.rs`, `api/explorer.rs`, `api/events.rs`, `api/error.rs` |
| Background payment progression and execution | `crates/ths-server/src/payments/progression.rs`, `payments/execution.rs`, `payments/attempt.rs` |
| Treasury replenishment, saved-transaction recovery, confirmation | `crates/ths-server/src/payments/treasury.rs`, `payments/submission.rs`, `payments/confirmation.rs` |
| Mining jobs | `crates/ths-server/src/mining.rs` |
| Docker-free tests | `crates/ths-server/tests/unit/` mirrors the source modules; follow their `#[path]` declarations |

Map checked against THS main at `6b00d0f0e40ecd42f61ca046485a03b69c5f3338` on 2026-10-16. Paths without a crate prefix in a row are relative to `crates/ths-server/src/`. Re-resolve symbols in the target checkout and distinguish production callers from `#[cfg(test)]` adapters.

Inspect `Cargo.toml` and `crates/ths-server/Cargo.toml` before using upstream wallet documentation. This repository imports Zakura wallet crates (`zakura-keys`, `zakura-primitives`, `zakura-client-backend`, `zakura-client-sqlite`, `zakura-proofs`, `zakura-orchard`, `zakura-sapling-crypto`, `zakura-pczt`, `zakura-transparent`, `zakura-zip321`) under `zcash_*` aliases at exact-pinned versions. API semantics and compatibility claims must follow the resolved source.

The wallet database keeps legacy `ext_tsz_*` schema names and migration UUIDs on purpose — see the migrations in `wallet/journal.rs` and `wallet/recovery.rs`. Keep them stable for existing wallets when following the `tsz-*` → `ths-*` crate rename elsewhere.

## Sync and balance publication

The path is Zakura checkpoint → lightwalletd indexed data → wallet database → `sync.rs::refresh_wallet_snapshot_until` → `api/status.rs::accounts` → `web/src/hooks/queries.ts::useAccounts`, which binds `queryKeys.accounts` to `api.accounts` → `WalletPage`. `synchronize_wallet_until` holds the sync lock, checks a shared deadline, runs `reconcile::sync_wallet`, then publishes the snapshot. `scan_is_publishable` checks scanned, target, and observed checkpoints, including canonical hash evidence when the chain has advanced. Failures before publication leave the earlier account snapshot in place. Payment progression runs separately in `payments/progression.rs`; do not assume activity reconciliation is a step inside snapshot publication.

Before attributing a stale balance to that path, verify the running artifact. After server edits, run `cargo run -p thus-spoke-zakura -- build --dev` and launch a new named instance; the existing container retains its original image. Preserve its wallet store and failure evidence. `THS_DEV_API=<dashboard-url> npm run dev --prefix web` only serves the edited frontend with API requests proxied to the existing server. It does not rebuild or replace server code. If raw accounts are current but the page is stale, use the dashboard's [balance diagnosis](../../ths-dashboard/references/dashboard.md#stale-balance-diagnosis) to inspect that exact accounts query and `wallet` event.

At startup, `bootstrap.rs::serve` binds HTTP while background startup continues. `start_and_sync` checks dependencies, synchronizes, and provisions Account 1 with 5 Ironwood ZEC before marking the server started and entering the wallet sync loop. `/api/v1/health` in `api/status.rs` can return 200 with a prior successful sync even if the current wallet-sync state is `error`; runtime readiness probes this route. For a stale balance after startup, compare `/api/v1/status` wallet-sync state and scanned/observed height **and hash**, then `/api/v1/accounts`. A green health check establishes less than a current, ready wallet snapshot. `reconcile.rs::within_deadline` applies per-operation and shared sync deadlines, so locate the phase that timed out.

In `reconcile.rs`, separate reorg detection and rewind, subtree-root updates, transparent output discovery, and prioritized shielded scan ranges. Check which operation advances each cursor and whether the write is durable before a progress claim. The node tip, lightwalletd tip, wallet scanned checkpoint, and user-facing balance can differ transiently. Equal heights do not prove equal block hashes.

Public transparent discovery and treasury reward discovery deliberately use different paths. `wallet.rs::public_transparent_queries` covers accounts 1–5; `reconcile.rs::refresh_transparent_outputs` streams lightwalletd UTXOs for those queries with the selected start height. Account 6 is excluded. For treasury coinbase rewards, `payments/treasury.rs::replenish_treasury` walks the node's block/coinbase evidence through `discover_reward_with_attempt`, then `wallet/recovery.rs` imports the reward and advances `ext_tsz_treasury_cursor`. A claim that public UTXO streaming alone fixes treasury scale misses the separate reward path.

## Treasury and payments

Accounts 1–5 are public development accounts. Account 6 (`TREASURY_ACCOUNT_ID`) is the miner and faucet treasury; it must stay out of account lists, displayed balances, and routine user transparent queries. Reward discovery has a persisted treasury cursor; reorg handling and immature coinbase outputs affect when funds can be spent. A change to bulk or incremental reward processing must preserve the cursor's chain identity and make the next faucet request work after a large reward history.

The production handlers in `api/payments.rs` validate requests and persist intent **before** wallet work: `db/activity.rs::claim_transfer` and `claim_faucet` use `activities`; `db/address_faucet.rs::claim_address_faucet` uses `address_faucets`. Pending HTTP responses are accepted operations, not proof of broadcast or inclusion. `bootstrap.rs` starts `payments/progression.rs::payment_confirmation_loop`, which resumes durable intents through `execute_activity_intent` or `execute_address_payment`. Follow `payments/execution.rs`, `submission.rs`, and `confirmation.rs` for proposal, original-transaction lookup, retransmission, expiry, and chain inclusion. `wallet/journal.rs` persists `ext_tsz_prepared_payments`; the application store also keeps prepared transaction bytes. Inspect both stores and the exact failure window before changing retry behavior — a timed-out response does not prove no transaction was sent.

For faucet changes, inspect `PaymentAttempt` in `payments/attempt.rs`, `PaymentSubmitter` in `payments/submission.rs`, and `FaucetRuntime` in `payments/treasury.rs` before introducing another abstraction. Production `api/payments.rs::faucet_address` keeps an existing external claim in its original store; otherwise, a destination owned by accounts 1–5 claims an account activity and an external destination claims an address faucet. Send, account faucet, and address faucet share one key space; mismatched intent returns `IdempotencyConflict`. Follow `payments/progression.rs::execute_address_payment` for `preparing`/`prepared`/`broadcast`/terminal states, journal repair, and replenishment; `submit_address_prepared` in `payments/submission.rs` handles saved-transaction recovery and expiry; `confirm_address_after_mining_with_attempt` in `payments/confirmation.rs` checks chain evidence. `AddressFaucetRuntime` and `execute_address_faucet` in `api/payments.rs` are test-only legacy adapters, and `fund_address_from_treasury` is absent at the checked revision. Use production callers as the workflow authority. Preserve validation, account boundaries, exact zatoshi arithmetic, and `ApiError`/`ApiResult` for HTTP failures.

### Reward-discovery trace

In `payments/treasury.rs`, `prepare_with_replenishment` distinguishes the wallet's `ScanRequired` from `InsufficientFunds`. The first path retries after sync and may mine forward from the birthday; the second uses the SDK's deficit to seek enough spendable rewards. `replenish_treasury` checks the persisted cursor's receiver and selected-chain hash, walks reward candidates, and mines until a candidate can mature. `discover_reward_with_attempt` verifies coinbase, unspent/spender evidence, and the selected chain hash around the wallet commit. `wallet/recovery.rs::commit_treasury_discovery` stores the reward and advances the cursor in one database transaction with a compare-and-swap check.

**Worked large-history diagnosis:** A faucet stalls after 10,000 mined blocks. First determine whether the wallet returned `ScanRequired` or `InsufficientFunds`; those trigger different work. Then compare the persisted cursor's height, hash, and receiver with the selected chain, inspect coinbase maturity and SDK spendability, and measure bulk catch-up separately from the next incremental block. The narrow test `insufficient_funds_discovers_only_the_needed_mature_reward_and_retries` checks the deficit path; the ignored large-history Docker case checks the real stack. A treasury total balance is not a substitute for the wallet's proposal result.

**Cursor interruption example:** Let the persisted treasury cursor be `(H, hash H, receiver R)`. Discovery checks block `H+1` on the selected chain and, if it contains a relevant reward, commits both the imported transaction and cursor `(H+1, hash H+1, R)` in one wallet database transaction. A failure before that commit must leave both at `H`; a restart rechecks `H+1`. A reorg that replaces `hash H+1` must rewind the imported reward and cursor together. The tests `failed_cursor_commit_rolls_back_reward_import_and_reopen_keeps_progress` and `rewind_updates_sdk_and_cursor_atomically` directly exercise these boundaries; `known_spender_must_be_stored_and_spend_the_exact_reward_output` checks spent-reward evidence. These are stronger oracles than a successful faucet HTTP response.

### Send failure windows

| Point of failure | Persisted or external effect to check |
| --- | --- |
| Before `claim_transfer`/`claim_faucet` | Validation or replay lookup failed; no activity row exists for this request |
| After claim, before `submit_prepared` | An activity row exists; wallet sync/proposal may have failed before prepare — no transaction is established |
| After broadcast, before confirmation | A transaction with a known txid exists; reconcile it before any replacement, and inspect background progression separately from HTTP replay |
| After mining, before the client observes completion | The client may miss completion although the original txid is included; reconcile chain and row identity |

This table describes possible boundaries, not proof that each state is currently recovered automatically. For a money-flow change, force the relevant boundary and assert the activity row, txid, chain inclusion, and final wallet snapshot independently.

## Evidence by claim

| Claim | Nearest useful evidence |
| --- | --- |
| Snapshot reads and pre-publication failure | `tests/unit/state/tests.rs::account_reads_return_the_snapshot_without_contacting_lightwalletd`, `tests/unit/sync/tests.rs::synchronization_failure_preserves_the_last_good_snapshot` |
| Reorg or scan range | `same_height_and_lower_tip_reorgs_find_the_last_common_block`, `scan_ranges_are_split_without_gaps` |
| Hidden treasury or transparent scope | `creates_user_accounts_and_hidden_treasury`, `routine_transparent_queries_exclude_the_treasury` |
| Input validation and replay identity | `invalid_sends_are_rejected_before_replay_or_synchronization`, `a_valid_replay_returns_the_original_without_the_wallet_or_network` in `tests/unit/api/payments/tests.rs`; inspect whether each exercises a production handler or a test-only adapter |
| Address-faucet replay and key conflicts | `confirmed_address_faucet_replays_without_sending_a_second_payment`, `address_faucet_replay_survives_restart_and_rejects_conflicting_intents`, `concurrent_address_faucet_claims_share_one_operation` |
| Real broadcast recovery | The ignored live `broadcast_recovers_after_auto_mine_failure` case through `ths-regtest-verifier` |

Run `AGENTS.md` Rust checks after `crates/` edits. Rebuild the app image before a live `ths` run reflects server source changes. Keep Docker-free seam tests for logic that does not require a real node or proof.

Resolve test names recursively under `crates/ths-server/tests/unit/`, including `api/payments/`, `payments/`, `db/`, and `wallet/`. A test-only legacy adapter passing does not prove the production background worker recovered an intent; select a progression test for that claim.

## Worked task: external-address faucet times out

**Input:** A client calls `faucet_address` with a valid Regtest destination and loses the HTTP response while background progression may have broadcast and mined. Retry with the **same key, address, and amount** to recover the persisted operation; a different address or amount on the same key is rejected with `IdempotencyConflict`. Trace `api/payments.rs::faucet_address` → `db/address_faucet.rs::claim_address_faucet` → `payments/progression.rs::payment_confirmation_loop` / `execute_address_payment` → `payments/submission.rs::submit_address_prepared` → `payments/confirmation.rs::confirm_address_after_mining_with_attempt`. Internal destinations use the account activity path instead.

| Observation after timeout | Safe conclusion |
| --- | --- |
| Original txid and confirmed block found | Payment occurred; a replayed key does not pay again |
| Row in `broadcast` but no confirmed block | `submit_address_prepared` retransmits the saved transaction or reconciles `transaction_known` |
| Prepared row past `expiry_height` and tx unknown | Inspect original-transaction absence and expiry evidence before `reset_address_for_retry` returns it to `preparing` |
| `preparing` row after a prepare failure | Production progression retains intent and checks `repair_address_journal` before preparing; inspect stored errors and replay the same key |

Locate the regression oracles by name under `tests/unit/`: `confirmed_address_faucet_replays_without_sending_a_second_payment`, `address_faucet_replay_survives_restart_and_rejects_conflicting_intents`, `internal_address_faucet_replays_preserve_activity_after_store_reopen`, `address_faucet_reconciles_the_original_txid_after_a_lost_broadcast_response`, `concurrent_address_faucet_claims_share_one_operation`, and `address_faucet_rejects_missing_or_invalid_operation_keys_before_network_work`. Pair adapter-level tests with `tests/unit/payments/progression/tests.rs` for production intent recovery. Inject uncovered failure windows at the owning production boundary or its existing `PaymentSubmitter` / `FaucetRuntime` seam.

```console
rg -n 'async fn faucet_address|fn claim_address_faucet|payment_confirmation_loop|execute_address_payment|async fn submit_address_prepared' crates/ths-server/src/api crates/ths-server/src/payments crates/ths-server/src/db
rg -n 'replay|restart|journal|broadcast' crates/ths-server/tests/unit/payments/progression crates/ths-server/tests/unit/db/address_faucet
cargo test -p ths-server confirmed_address_faucet_replays_without_sending_a_second_payment
cargo test -p ths-server address_faucet_replay_survives_restart_and_rejects_conflicting_intents
cargo test -p ths-server payments::progression::tests
```

Test both an account faucet replay and the address endpoint — they share the idempotency key space, and the same key is rejected across `activities` and `address_faucets`.
