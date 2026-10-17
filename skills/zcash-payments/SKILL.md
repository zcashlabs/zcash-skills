---
name: zcash-payments
description: Use when constructing, signing, sending, retrying, or tracking Zcash payments, including input selection, fees, memos, expiry, and confirmation.
---

# Zcash payments

Resolve the network, transaction version, target height, receiver pool, and pinned wallet API first.

For proposal, fee, or memo behavior, load [payment construction](references/payments.md#constructing-the-intended-payment). For broadcast, expiry, inclusion, or uncertain retries, load [transaction tracking](references/payments.md#following-the-same-transaction); for a lost response, load [the worked retry task](references/payments.md#worked-task-response-lost-after-a-successful-submission). Choose regression oracles from [evidence for a change](references/payments.md#evidence-for-a-change).

Treat a payment as a sequence of distinct states: intent, proposal, signed transaction, transmission, mempool observation, inclusion, and confirmation. Keep exact zatoshi amounts and transaction identities through those states. After an uncertain send result, reconcile the original transaction before making another payment. Derive spendability from the wallet's proposal rules, not a displayed total.

## Core workflow

1. Record the recipient receiver, source pool, exact amount, memo, fee policy, and target height.
2. Inspect the complete proposal and all selected inputs and dependent steps.
3. Preserve the signed transaction identity across submission and retries; classify unknown outcomes before replacement.
4. Validate the intended transaction's inclusion and resulting wallet state, with adjacent valid and invalid cases for parsing, fees, and expiry.

## Review examples

- A timeout after broadcast leaves submission status unknown. Identify the original txid and reconcile it before asking the wallet to select inputs again.
- A visible balance greater than the requested amount can still produce no valid proposal because available inputs, anchor, coinbase maturity, and fee are separate constraints.
- A transaction expiring at height `N` can be mined in block `N`; test the boundary at `N+1` and check earlier inclusion before calling it lost.
- Post-NU6.3, new shielded outputs go to the Ironwood pool. An Orchard-pool input can still be spent, but a request to *receive* into Orchard cannot be satisfied — check which pool the proposal actually targets.

Report proposal inputs and outputs, fee policy, exact txid, submission observation, inclusion height and hash, and wallet state after scanning. Distinguish each observation from the conclusion it supports.
