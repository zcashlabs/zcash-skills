# Live Regtest validation

## Pick the oracle before the command

| Claim | Smallest relevant route |
| --- | --- |
| Rust/server logic without a real node or proof | `cargo test --workspace` or a targeted Rust test; Docker is not required |
| Web request, schema, or view behavior | The relevant `npm test --prefix web` case and web checks |
| Real background recovery after auto-mine failure | Ignored `broadcast_recovers_after_auto_mine_failure` in `activity_recovery` |
| Duplicate concurrent sends share one chain effect | Ignored `concurrent_identical_sends_have_one_chain_effect` |
| Address-faucet retry across a server restart pays each destination once | Ignored `address_faucet_retry_after_server_restart_pays_each_destination_once` |
| Queued send or external faucet survives a lost response and restart | Ignored `queued_send_retry_survives_lost_response_and_restart`, `queued_external_faucet_retry_survives_lost_response_and_restart` |
| Reorg/rollback preserves canonical wallet and payment state | Ignored `reorg_and_rollback_preserve_canonical_wallet_and_payment_state` |
| Address-faucet variants (internal/external, auto-mine failure, replay-safe pool round trip) | Ignored `internal_address_faucets_record_confirmed_activity`, `internal_address_faucet_recovers_after_auto_mine_failure`, `external_address_faucet_behavior_is_unchanged`, `same_account_cross_pool_round_trip_is_replay_safe` |
| Large transparent reward history and later faucet responsiveness | Ignored `large_reward_history_keeps_treasury_faucet_responsive` |
| Source-built dashboard or launcher behavior in containers | Rebuild app image, start a named disposable instance, inspect the actual running image |

Read the current `README.md` activity-recovery section and `crates/ths-server/tests/activity_recovery.rs` before a live run. The fixture is in `crates/ths-server/tests/support/regtest.rs`; it owns UUID-prefixed resources, a source-built server process, private data directories, and cleanup. The live integration target uses the Cargo-built `ths-server` binary, not the app image. The app image must be rebuilt for a separate `ths` container run after server or web edits.

## Documented recovery run

From the repository root, the current sequence is (check `README.md` for the pinned image tag at your revision):

```console
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery --no-run
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery
docker pull zakuracore/zakura:1.6.0
docker build -f docker/lightwalletd.Dockerfile -t ths-recovery-lightwalletd:local .
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact broadcast_recovers_after_auto_mine_failure
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact concurrent_identical_sends_have_one_chain_effect
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact address_faucet_retry_after_server_restart_pays_each_destination_once
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact queued_send_retry_survives_lost_response_and_restart
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact queued_external_faucet_retry_survives_lost_response_and_restart
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact reorg_and_rollback_preserve_canonical_wallet_and_payment_state
```

The first command compiles the integration target; the second runs Docker-free helper tests while the live cases remain ignored. The explicit `--ignored --exact` selections run the real cases. `broadcast_recovers_after_auto_mine_failure` broadcasts an Ironwood payment, rejects exactly one automatic `generate([1])`, mines directly through the node, and waits for background wallet sync to confirm the **existing** activity row. Retrying Send or calling the server mine endpoint would exercise a different repair path. Assert the exact transaction's inclusion, unchanged activity identity, confirmed block hash, and resulting wallet state.

The 10,000-block case is a separate, expensive performance and correctness workload. It mines the history directly, waits for wallet sync, mines one incremental block, then exercises the faucet. Use it for reward-history and treasury-cursor claims; it is not required to prove auto-mine recovery. Its absence from the ordinary CI live job must be reported when making a large-history claim.

The current large-history case makes ten confirmed 5 ZEC faucet payments and checks account 2's final increase of 5,000,000,000 zatoshis. Record the bulk catch-up and one-block incremental refresh separately if claiming that the path scales. At the checked revision, `.github/workflows/ci.yml` selects **six** ignored live cases with `--ignored --exact`: `broadcast_recovers_after_auto_mine_failure`, `concurrent_identical_sends_have_one_chain_effect`, `address_faucet_retry_after_server_restart_pays_each_destination_once`, `queued_send_retry_survives_lost_response_and_restart`, `queued_external_faucet_retry_survives_lost_response_and_restart`, and `reorg_and_rollback_preserve_canonical_wallet_and_payment_state`. It does not select `large_reward_history_keeps_treasury_faucet_responsive` or the other faucet variants listed in the oracle table. A green CI run provides no 10k-block performance evidence or evidence for those unselected variants. Confirm which cases CI selects at your revision — the list can change.

This live case establishes observed responsiveness and resulting wallet state. It does not instrument how many records lightwalletd retrieved or prove a server-side UTXO query is bounded. For an underlying-query claim, inspect or measure the selected lightwalletd/Zakura query separately.

The recovery case rejects one automatic mine, confirms the original txid is still in the mempool at the unchanged height, mines directly through the node, and then mines a later block. It waits for wallet sync through that later tip, checks the same activity identity and confirmed block hash, and checks read-only persistence. These observations make the regression stronger than a generic “HTTP 200” or “height advanced” assertion.

## Artifact, cleanup, and reporting

Before running, identify the source revision, Cargo profile, selected test, expected node and lightwalletd images, Docker daemon, and available time. Do not use a previously installed server binary as evidence for edited source. Distinguish setup failure, compilation failure, helper-test pass, live-case pass, timeout, and cleanup failure. A green command with zero selected live cases proves no Docker behavior.

The fixture must remove only resources it registered, even after cancellation or partial startup. Do not prune shared Docker state or erase another instance. Inspect the fixture's allowlisted failure report rather than leaking keys, raw wallet data, or process logs. Report the exact command, observed chain and wallet checkpoints, transaction/activity oracle, elapsed time for a performance claim, and any untested boundary. For a negative control, follow the README's isolated-worktree procedure and restore temporary instrumentation immediately.

## Worked task: verify 10,000 reward blocks

After building the integration target and preparing the two images in the documented sequence above, select the large-history case explicitly:

```console
cargo test --locked --profile dev-runtime -p ths-server --test activity_recovery -- --ignored --exact large_reward_history_keeps_treasury_faucet_responsive
```

The exact-name filter is part of the oracle. Confirm the output reports **one** selected ignored case; a green command with zero cases is a selection mistake. The case mines 10,000 blocks directly with a 3,600-second bulk-mine timeout, waits for the wallet to scan the resulting tip, mines one more block, then makes ten 5 ZEC faucet payments. It expects account 2 to gain 5,000,000,000 zatoshis. The incremental wallet wait and each faucet have separate timeout paths. If the test fails, report the phase; if making a measured speed claim, add phase timing and rerun.

The stock test asserts the pre-mine-to-bulk height delta, one more block, wallet catch-up at both tips, ten confirmed payments, account balance delta, and cleanup. It does not print the ten txids or per-phase elapsed times on success. If the claim needs those identities or a measured responsiveness bound, instrument the test or its reporter to emit them and rerun the case; do not present its timeout ceilings as measured timings. A pass supports correctness within those ceilings for that source revision. It does not measure lightwalletd's underlying query cardinality. If the claim is about Zakura query work, instrument or inspect that service separately. The CI recovery case does not select this workload.
