# Light-client scanning and integration

## Locate the state owner

| Layer | State it can establish |
| --- | --- |
| Full node | Its selected chain tip, block/transaction data, and validation result |
| Lightwallet service | The compact-block range and auxiliary data it has indexed and served |
| Wallet | Scanned range, discovered notes and UTXOs, spends, witnesses, and spendability |
| Application | A published view of wallet state and its own pending operations |

Identify the actual deployment path and versions. The serving layer is in transition: `lightwalletd` (Go) still serves many stacks, while [Zaino](https://github.com/zingolabs/zaino) is the Rust indexer intended to replace it for both light clients and full-node wallets like Zallet — and the two have different API and lag characteristics. [ZIP 307](https://zips.z.cash/zip-0307) is a draft light-client design centered on Sapling; it describes node, proxy, and wallet roles but does not establish which checks a deployed implementation performs. Transport success and equal reported heights do not prove the service and wallet describe the node's current chain: compare hashes and relevant checkpoints.

## A scan pass, end to end

1. Establish the account birthday and initial commitment-tree state. The start height is a recovery boundary, not only a performance setting.
2. Download a contiguous compact-block range and any required subtree roots or chain state. Validate heights, hashes, and continuity for local consistency. These checks do not prove the service reported the best chain; ZIP 307's light-client model trusts the node and proxy for that claim.
3. Trial-decrypt supported shielded outputs, record received notes and spends/nullifiers, and update note commitment trees and witnesses required for later spending.
4. Discover transparent outputs through the selected server's separate API where needed. Confirm address scope, `startHeight` and page/stream semantics in the actual server and wallet versions; do not infer that a field bounds the underlying query.
5. Persist wallet effects and the corresponding scan checkpoint in the owning store. A published cursor must never outrun durable notes, spends, and tree state.
6. On a reorg, find a verified common ancestor, rewind through the wallet's supported API, and rescan the replacement branch. A displayed balance change alone does not repair wallet state.

### Checkpoint example

Suppose the node and service report height 120, while the wallet has durably scanned `(118, hash A)`. The wallet may download 119–120, but it must publish a checkpoint for 120 only after the corresponding note, spend, tree, and witness changes are durable. If the process stops after those effects commit but before a UI refresh, the next pass should read the persisted checkpoint and avoid duplicating them. If it stops before commit, the next pass should process the range again. A progress message alone is not the commit oracle.

Now suppose a new height-120 branch replaces the old one. Matching heights do not identify the same block. Compare hashes, find the common ancestor, rewind the wallet's own state, then scan the replacement. Check both the previously received note and any spend on the displaced branch. A wallet that only updates a displayed balance can leave a stale witness or spend marker and fail later payment construction.

The upstream [`zcash_client_backend` sync design](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_client_backend/index.html) and [chain API](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_client_backend/data_api/chain/index.html) show the relevant concepts when that crate family is used (including the `zakura-client-backend` fork). Recheck behavior in the pinned implementation, including database transaction boundaries and scan-range priorities.

The upstream chain API's concrete sequence is to update subtree roots, set the chain tip, obtain suggested scan ranges, fetch initial chain state at `range.start - 1`, cache blocks, and scan. On a continuity error, its example rewinds the wallet to a safe height before the error, drops later cached blocks, re-downloads, and rescans. This is an upstream implementation example, not a promise that a fork or service exposes identical calls. A successful scan establishes local consistency; it may still lag the latest node tip.

## Privacy and failure boundaries

Compact scanning avoids asking the service only for a user's shielded transactions. Fetching full transactions for memos or outgoing history can reveal interest in particular transactions; ZIP 307 discusses this privacy tradeoff. Transparent address queries reveal address interest to the queried service. Determine which leak belongs to the protocol, service API, or product policy before changing a fetch pattern.

Classify a timeout or interruption by the last durable checkpoint. Retain the wallet database for a restart test; resetting it tests a fresh scan, not recovery. Preserve old state until the replacement scan proves its chain history and state updates are consistent.

### Which boundary failed?

| Symptom | First boundary to inspect |
| --- | --- |
| Node advanced; service range stops earlier | Service indexing lag or unavailable compact blocks |
| Service range complete; wallet checkpoint behind | Scan scheduler, decryption, tree state, or durable write |
| Wallet checkpoint current; balance absent | Account birthday, receiver derivation, transparent discovery, spend tracking, or snapshot publication |
| Same height, different hash | Reorg handling and common-ancestor search |
| Restart repeats work or misses output | Cursor-to-wallet-state commit boundary |

These comparisons establish where to investigate, not which remote party supplied the best chain. ZIP 307's proposed architecture treats the full node as the root of trust; local compact-block continuity checks cannot replace that trust. Its [header-validation section](https://zips.z.cash/zip-0307#block-header-validation) also distinguishes desired checks from those implemented at the time of the draft, so inspect the actual client and proxy versions before claiming header validation.

## Decisive tests

| Change | Useful oracle |
| --- | --- |
| Batch size or cursor | One-pass and incremental scans of the same history produce the same notes, spends, tree state, and final checkpoint |
| Crash/restart | Resume from a retained store without missing or duplicating effects around the commit boundary |
| Reorg | Same-height and lower-tip forks find the common ancestor; orphaned effects disappear and replacement-chain effects appear |
| Transparent discovery | Newly added outputs are found without repeatedly materializing the full historical set, if the service supports a bounded query |
| Performance | Same chain history and final wallet state with measured work, memory, and latency |

Use a real node/service only for claims that require their behavior; use a controlled source or store seam for wallet scan logic. Keep the test oracle at the wallet-state boundary rather than a progress percentage.

For a reorg oracle, compare transactions, note/nullifier spend state, and witnesses before and after rewind, then verify the replacement branch and a spend that needs the rebuilt witness. Seeing an orphaned incoming note disappear is only one part of the rollback. ZIP 307's [client-operation sketch](https://zips.z.cash/zip-0307#client-operation) is Sapling-focused; extend the oracle to every pool the selected wallet actually supports — post-NU6.3 that includes Ironwood notes, which use Orchard-protocol machinery with their own commitment tree and nullifier set.

## Worked task: same-height fork and interrupted commit

Build a controlled compact-block fixture with common block `(118, C)`. Branch A has `(119, A19)` receiving a shielded note and `(120, A20)` spending it. Branch B has `(119, B19)` and `(120, B20)` without that receipt or spend. Use deterministic viewing keys and retained wallet storage; record the note commitment, nullifier, witness state, and scan checkpoint after each committed block.

| Transition | Required wallet state |
| --- | --- |
| Scan A to 120 | Checkpoint `(120, A20)`; A's note and spend are represented consistently |
| Change service's selected branch to B at the same height | Height equality is insufficient; hash mismatch triggers rewind to common `(118, C)` |
| Rescan B | Checkpoint `(120, B20)`; A's orphaned note, spend marker, and witness effects are absent |
| Crash before the B commit | Restart from retained pre-commit state and safely reprocess B |
| Crash after the B commit | Restart sees durable `(120, B20)` and does not duplicate wallet effects |

Compare the final persisted state with a fresh one-pass scan of branch B. The comparison needs account outputs, spent/nullifier state, commitment-tree/witness state, and checkpoint hash—not only balance or height. For an implementation using upstream [`scan_cached_blocks`](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_client_backend/data_api/chain/index.html), identify the actual cache and wallet transaction boundary before injecting the crash. This fixture proves local rollback behavior; a service-backed test is still needed for claims about that service's fork reporting or indexing.
