---
name: ths-regtest-verifier
description: Use when validating Thus Spoke Zakura changes with real Docker containers, Zakura, lightwalletd, mining, shielded proofs, wallet restart, or activity recovery.
---

# THS Regtest verifier

Read the current `AGENTS.md`, the affected test, and the relevant section of `README.md`. Match the test to the claim: Rust and web checks cover their own code paths; the live stack is needed when the claim depends on actual container images, node behavior, proving, retained wallet data, or background recovery.

Before a live run, identify the exact source revision, selected Cargo-built server binary, required node/lightwalletd images, selected test, and Docker resources it creates. For a separate `ths` container run, rebuild the app image after server or web changes. Never use a result from an older artifact as evidence for current source. Select only the needed scenario; the 10,000-block reward-history case is a substantial performance workload and is not part of the ordinary CI live job.

For an uncertain test choice, use [the oracle table](references/live-tests.md#pick-the-oracle-before-the-command). For an ordinary live recovery run, load [the documented sequence](references/live-tests.md#documented-recovery-run) and [artifact/cleanup reporting](references/live-tests.md#artifact-cleanup-and-reporting). Load [the large-history worked task](references/live-tests.md#worked-task-verify-10000-reward-blocks) only for reward-history or responsiveness claims. Preserve the fixture's instance-scoped cleanup; do not prune shared Docker resources or delete another environment. Report the command, selected case, resulting wallet and chain observations, elapsed time where relevant, and any setup or cleanup failure. A green helper test does not establish that an ignored Docker case ran.

## Review examples

- `cargo test --workspace` can pass while every ignored Docker case remains unrun; report the selected case name and exact command.
- For broadcast recovery, assert the original activity and txid reach confirmation after background sync without another Send.
- For concurrent duplicate sends, assert one chain effect for the same idempotency key.
- For an address-faucet restart retry, assert each destination is paid once with the claimed idempotency key — that case runs in CI alongside the send cases.
- For the large reward history, assert the wallet catches up and the next faucet succeeds; record elapsed time and resource use if responsiveness is claimed.
