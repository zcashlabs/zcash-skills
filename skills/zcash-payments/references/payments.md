# Payments and transaction state

## Constructing the intended payment

Keep amounts as checked integer zatoshis across input, proposal, persistence, and wire boundaries; format ZEC only at the display edge. A displayed balance is not the same as spendable inputs. Confirm the selected wallet's rules for confirmation depth, coinbase maturity, note witnesses or anchors, locked or reserved inputs, fee, change, and source pool.

Trace the complete proposal, including each transaction and dependency it returns. [The `zcash_client_backend` proposal API](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_client_backend/data_api/wallet/fn.propose_transfer.html) can propose a transaction or series of transactions and can lock selected inputs; use this as an implementation example only when that exact API is selected (the `zakura-client-backend` fork exposes a corresponding surface). A payment workflow must not drop later proposal steps.

| Decision | Concrete question |
| --- | --- |
| Recipient | Which address receiver and pool will actually receive the funds? |
| Inputs | Are shielded notes spendable at the chosen anchor? Which transparent addresses may be linked by input selection? |
| Fee and change | What does the pinned change strategy return, and can the fee consume the apparent available value? |
| Memo | Does the chosen shielded output support the encoded memo? A transparent output cannot carry a shielded memo. |
| Authorization | Does the signer have spending authority for every selected input? |

Post-NU6.3 pool behavior matters at proposal time: new shielded outputs are created in the Ironwood pool (reusing Orchard-protocol receivers), the Orchard pool is spend-only — existing Orchard notes can be spent and produce change, but no new value can enter Orchard, and Orchard cross-address transfers are disabled. A wallet asking which "shielded pool" to use after NU6.3 means Ironwood.

The [ZIP 317](https://zips.z.cash/zip-0317) conventional fee is wallet guidance, not a consensus validity formula. Its active and draft revisions differ; resolve which applies to the target network and implementation. Keep node mempool acceptance policy separate from both wallet convention and consensus.

For active Revision 0, the [fee calculation](https://zips.z.cash/zip-0317#fee-calculation) is `5,000 × max(2, logical_actions)` zatoshis. One Orchard action therefore has a 10,000-zatoshi conventional fee and three Orchard actions have 15,000. Three Sapling spends plus two Sapling outputs contribute three logical actions, since that pool contributes `max(spends, outputs)`, not their sum. The transparent contribution uses the larger of rounded-up serialized input bytes divided by 150 and output bytes divided by 34; counting addresses alone misses a large script. These examples are a check on the selected wallet policy, not a hard-coded fee rule for a different ZIP revision or pinned SDK.

**Ironwood (Revision 1, enacted at NU6.3):** adds `contribution_Ironwood = nActionsIronwood` — one logical action per Ironwood Action, identical weight to an Orchard Action. So a v6 transaction with two Ironwood Actions has the same conventional fee as a two-Action Orchard transaction (10,000 zatoshis). Orchard and Ironwood contributions are counted separately and summed — a cross-pool tx with one Orchard spend and one Ironwood output is two logical actions, not "one shielded action." Revision 2 (draft, depends on undeployed ZIP 248) adds memo-bundle handling; check which revision the pinned wallet implements.

### Proposal review in practice

Given a request for an exact amount, inspect the proposal before signing. Record the receiver actually selected from a UA, each source pool, the selected notes or UTXOs, the anchor or witness requirements, change, fee, and any additional transaction steps. If the wallet cannot form a proposal, report the failing constraint. A total balance larger than the amount is insufficient evidence of spendability: pending change, immature coinbase, locked inputs, and the fee can each change the result.

For a transparent source, the selected input addresses and output values are public and may link wallet activity. For a shielded source, a transparent destination still reveals destination and amount on-chain. A UI label such as “shielded account” does not change the receiver or source pool that the proposal actually uses.

## Following the same transaction

| Observation | What it establishes | What remains open |
| --- | --- | --- |
| Proposal built | Inputs, outputs, fee, and possible dependent steps were selected | No signature or network effect |
| Signed transaction saved | Exact bytes and transaction identity exist | No broadcast or inclusion |
| Submission returned success | A node or service accepted the request at that boundary | Mempool presence and inclusion |
| Submission timed out or failed | The local call did not return success | Broadcast may still have happened |
| Mempool observation | The node currently sees the transaction | Mining and confirmation |
| Mined block includes that txid | Inclusion on the observed chain | Reorg and confirmation policy |

After an unknown submission result, query the original transaction identity and wallet inputs before creating a replacement. Replaying the same signed bytes and constructing a fresh payment have different effects. An application idempotency key is an intent record, not a substitute for chain reconciliation.

**Worked unknown-outcome case:** The client sends signed bytes for txid `T`, then the HTTP connection closes before a response. Preserve the bytes, txid, and selected inputs. Check the node or service for `T`, then scan the wallet and inspect whether those inputs remain reserved or are spent. Retrying the same signed bytes cannot create a second transaction identity; making a fresh proposal might. If `T` is not visible, the result remains unknown until the relevant network and expiry/reorg evidence resolves it. Do not turn a transport error into “safe to send again.”

[ZIP 203](https://zips.z.cash/zip-0203) defines expiry by inclusion height: for ordinary nonzero expiry height `N`, block `N` can include the transaction and `N+1` cannot. Zero and coinbase have separate treatment. A current height past `N` does not prove the transaction was never included earlier; inspect chain history and reorg state.

**NU7 timing change:** expiry is still measured in blocks, but NU7's 25-second spacing makes a fixed delta expire 3× sooner in wall-clock. Node implementations that create transactions are guided (ZIP 218, non-consensus) to move the default `txexpirydelta` from 40 to 120 blocks, preserving ~50 minutes. If your code or a pinned wallet sets an explicit delta, re-check it — a hard-coded 40 now gives ~17 minutes. Also: a transaction signed before NU7 activation carries the pre-NU7 consensus branch ID and is invalid after activation, whatever its expiry height. When a wallet caches or defers signed transactions across a boundary (scheduled payments, multi-step proposals), treat activation as a hard invalidation point for already-signed material.

For expiry tests, include `N`, `N+1`, and zero (no expiry). Coinbase transactions have their own rule; since NU5 their expiry height must equal their block height. For a dependent unconfirmed transaction, check what happens when its parent expires from the mempool. Keep this [ZIP 203](https://zips.z.cash/zip-0203#specification) behavior separate from UI timeouts, which are measured in wall-clock time.

| Observation at height `N+1` | Next check |
| --- | --- |
| `T` included in block `N` | Track confirmations and reorgs; expiry has not invalidated that inclusion |
| `T` absent from the selected chain | Check mempool and wallet reservation state before replacement |
| `T` was in an orphaned block | Reconcile the selected chain and wallet rewind before deciding whether to recreate it |

## Evidence for a change

- For amount parsing, check exact zatoshi conversion, minimum/maximum, and adjacent invalid values.
- For fees or input selection, compare the actual proposal's selected inputs, output amounts, change, fee, and any reservations.
- For retry logic, force an unknown broadcast result and prove that the original txid is reconciled before a new signed transaction can be created.
- For success, observe the intended txid in a block and the wallet's resulting notes or UTXOs, not only an HTTP status or mined height.
- Use disposable keys and controlled funds. Match the test network, height, fee policy, and pinned wallet version to the claim.

See the [wallet data API](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_client_backend/data_api/index.html) for current upstream concepts; inspect the selected version and any fork before using an API or assuming its policy.

## Worked task: response lost after a successful submission

**Fixture:** The wallet has one spendable source set. Build one proposal and sign its transaction bytes as `T`; persist the payment intent, signed bytes, txid, and selected input identities before network submission. In a controlled node/service seam, accept `T` but drop the HTTP response. Restart the client with its durable store intact, then trigger the user-visible retry.

| Point | Expected state or call |
| --- | --- |
| Before send | One intent, one proposal, one signed `T`, selected inputs reserved according to the wallet's policy |
| Response dropped after acceptance | Client reports an unknown outcome, not a failed payment; node can identify `T` |
| Restart and retry | Reconcile `T` or retransmit the **same bytes**; no second proposal or txid is created for the same intent |
| Mine `T` | Observe its txid in a selected-chain block and scan the wallet to its resulting state |
| Reorg the including block | Return to an unconfirmed/unknown state and reconcile before replacement |

Assert the node saw at most the one transaction identity and that the wallet did not select inputs for a second payment. If `T` is absent, test the ordinary [ZIP 203](https://zips.z.cash/zip-0203#specification) expiry boundary at `N` and `N+1` and inspect chain history and retained input locks before authorizing a new proposal. “The HTTP call failed” is never the replacement oracle. The [current upstream proposal API](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_client_backend/data_api/wallet/fn.propose_transfer.html) can return multiple dependent transactions and lock inputs; use the behavior of the version actually pinned by the project.
