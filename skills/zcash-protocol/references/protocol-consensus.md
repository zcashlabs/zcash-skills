# Protocol and consensus

## Choose the governing rule

Start with the [Zcash Protocol Specification and ZIP index](https://zips.z.cash/). Record the target network, activation heights, block height, transaction version, and the exact specification and ZIP revisions that apply. A ZIP page can contain an active revision plus drafts for future upgrades; current web text is not automatically the rule for an older height or pinned node.

| Layer | Example question | Authority |
| --- | --- | --- |
| Consensus | Would a block containing this transaction be valid at height `H`? | Activated protocol rule and applicable ZIP |
| Node policy | Will this node admit or relay the transaction now? | Selected node version and configuration |
| Wallet policy | What fee, receiver, or input selection does the wallet produce? | Applicable wallet standard and pinned library |
| Application | What status does the user see and when? | Product contract and observed wallet/chain state |

**Two boundary examples:** [ZIP 203](https://zips.z.cash/zip-0203) makes an ordinary transaction with nonzero expiry `N` invalid for inclusion after `N`; `N` itself remains eligible. [ZIP 317](https://zips.z.cash/zip-0317) describes a conventional fee and explicitly does not make its formula a consensus requirement. These belong to different layers even when the same transaction is involved.

### Worked classification

A wallet proposes fee `F`, the node rejects the transaction from its mempool, and a developer asks whether the transaction is “invalid.” Split the observation:

1. Check encoding, signatures/proofs, expiry, and active upgrade at the intended block height against the protocol rule. This answers block validity.
2. Check the selected node's mempool policy and rejection reason. This answers admission or relay behavior for that node version.
3. Check the wallet's fee strategy against the applicable ZIP 317 revision and implementation. This answers whether its construction follows the intended convention.

The same transaction can pass the consensus test and fail the mempool-policy test. A green wallet construction test establishes neither. Keep the exact rejection code, transaction bytes or txid, target height, and node version in the report.

## NU6.3 and the Ironwood pool

NU6.3 ([ZIP 258](https://zips.z.cash/zip-0258)) introduced the Ironwood shielded pool — an Orchard-*protocol* pool with its own note commitment tree, nullifier set, anchors, and chain value pool balance — and sealed the legacy Orchard pool. Governing documents: [ZIP 229](https://zips.z.cash/zip-0229) (version 6 transaction format, txid/sighash/block-commitment changes), [ZIP 2005](https://zips.z.cash/zip-2005) (quantum-recoverable note plaintexts, lead byte `0x03`), the updated Orchard Action circuit (consensus branch 6 verifying key), and the [Ironwood book](https://zcash.github.io/ironwood/) for design intent.

Key consensus consequences to test:

- No new value may enter the Orchard pool: `v^OrchardPoolBalance ≥ 0` per transaction after NU6.3, regardless of transaction version.
- Orchard-pool Actions must have `enableCrossAddress = 0` — an Orchard spend can produce change to the spender's own receiver but cannot pay a *different* Orchard-pool recipient.
- Coinbase must not contain Orchard-pool Actions.
- ZIP 209 turnstile tracking is extended to the Ironwood pool; `valuePools` reporting gains an `ironwood` entry — a real compatibility break for consumers with a fixed pool list (it broke pinned Zaino releases against Zebra 6).
- v6 transactions add the Ironwood-pool bundle (encoded as a second Orchard-shaped bundle); NU6.3 admits v4, v5, and v6 (v4 is only disallowed from NU7 onward), but only v6 can carry Ironwood outputs. Address encodings are unchanged — Ironwood notes sit at Orchard-protocol receivers.

Do not extrapolate pre-NU6.3 Orchard rules to current height, and do not treat "Orchard" in a UA as naming a distinct destination pool from Ironwood.

## NU7 ([ZIP 259](https://zips.z.cash/zip-0259))

NU7 activated on Testnet at height 4,465,026 (2026-10-06); Mainnet height is assigned 2026-10-20 with activation targeted for 2026-11-05. Consensus branch ID `0x77190AD9`; minimum network protocol versions 170180 (Testnet) / 170190 (Mainnet). NU7 deploys **no new transaction format** — v5 and v6 stay structurally valid — but every signature commits to a consensus branch ID, so a transaction signed before activation is invalid after it even though its format is unchanged. Verify these constants against the ZIP at use time; heights marked TBD move.

Deployed changes:

- **ZIP 218** — block target spacing 75 s → 25 s. Per-block shielded limits: `GlobalShieldedBudget = 330` units shared by Orchard+Ironwood Actions (each Action costs 1), per-pool caps of 330 Orchard and 330 Ironwood actions, `SaplingBlockIOLimit = 300` spends+outputs, `SproutBlockJoinSplitLimit = 0`. Testnet minimum-difficulty threshold moves from 6 to 18 block spacings (block time > 450 s after parent). Block subsidies rescale so halvings are preserved.
- **ZIP 2003** — version 4 transactions invalid → the Sprout pool is unspendable while v4 is disallowed. ZIP 2003 deliberately does not claim permanence and advises holders to move funds out of Sprout before activation.
- **ZIP 235** — 60% of transaction fees removed from circulation (block-level consensus calculation, not a tx field).
- **ZIP 237** — halving-preserving Network Sustainability Mechanism; `NSM_REISSUANCE_HEIGHT` Testnet 7,305,222, Mainnet per formula.
- **ZIP 207 rev 2 / ZIP 214 rev 3 / ZIP 2008** — funding-stream address periods, end heights (NU7 activation heights must be multiples of 3), and the `FS_FPF_ZCG_H3` address list.

**Expiry under NU7.** ZIP 203 expiry heights are still block heights, but wall-clock expiry is now 3× faster at the same delta. [ZIP 218](https://zips.z.cash/zip-0218) says node defaults SHOULD move `-txexpirydelta` from 40 blocks (~50 min at 75 s) to 120 blocks after activation. This is non-consensus default behavior — wallets and nodes that hard-code 40 now expire in ~16 minutes. Mempool eviction bounds measured in blocks compress the same way. Check what the pinned node/wallet actually defaults to, and note the boundary case: a transaction signed before NU7 activation is invalid after it regardless of its expiry height, because signatures commit to the branch ID.

**Rehearsing NU7 on Regtest.** Do not wait for the network to tell you the boundary works. Run a Zakura (or Zebra) Regtest with NU7 assigned a deferred activation height — in the node config's `[network]` section, `testnet_parameters.activation_heights` is keyed by upgrade name (THS's generated `zakurad.toml` shows the pattern: `[network.testnet_parameters.activation_heights]` with `"NU6.3" = 1` etc.). That legacy key is still accepted on current Zebra/Zakura; the newer spelling is `network = { params = { activation_heights = { NU7 = H } } }` inside `[network]`. Mine up to `H-1`, build transactions under the old rules, cross `H`, then exercise: v4 rejection, pre-signed v5/v6 txs failing on branch ID, the new spacing under `generate`/`pow` behavior if the regtest controls difficulty, and expiry deltas in your wallet layer. In THS specifically the wallet's `regtest_network()` must mirror the node's activation heights (`nu7: Some(H)` vs `None`) or wallet and node disagree about which rules apply — keep both sides in sync, that's a real failure mode, not a hypothetical.

## Trace the implementation

For parsing, serialization, sighash, commitments, proof verification, or network-upgrade activation, find the exact production caller and the representation it validates. Determine whether a decoder rejects malformed bytes before semantic checks, whether canonical encodings are required, and which feature gates or upgrade branches are reachable at `H`. Check both accepted and rejected boundary cases. A consensus change needs a rule-level oracle, not only a wallet send test.

Compare independent implementations when useful, such as [Zebra](https://github.com/ZcashFoundation/zebra), [Zakura](https://github.com/zakura-core/zakura) (a Zebra fork with its own `zakura-*` crate family), and the selected wallet's primitives from [librustzcash](https://github.com/zcash/librustzcash) or its zakura forks. `zcashd` is deprecated — do not use it as the reference for current consensus behavior. A disagreement starts an investigation; do not pick a winner from implementation popularity. Published vectors, exact byte encodings, and the applicable specification decide the expected result.

### Activation boundary procedure

For a rule first active at height `H`, derive three expected outcomes from the governing specification: just before activation (`H-1`), at activation (`H`), and immediately after (`H+1`). Use the same transaction shape only if that shape is valid to test on both sides; some formats are deliberately unavailable before activation. Pin network parameters and node configuration. When a rule is conditional on transaction version or branch ID, include those fields in the fixture. Record the layer that rejects each invalid case: parser, contextual validation, mempool policy, or block validation.

[ZIP 200](https://zips.z.cash/zip-0200#activation-mechanism) defines consecutive upgrade epochs beginning at activation heights. A reorg across `H` can change which rule set applies to the next block. For applicable transaction formats, signatures commit to a consensus branch ID, so a test that changes only a version byte misses replay-protection behavior. Record the branch ID and selected chain height with every activation fixture.

For v5 transactions, [ZIP 244](https://zips.z.cash/zip-0244#specification) separates the digest of transaction effects (`txid`) from the authorization digest. A focused vector test changes only authorization data and expects the txid to remain stable while the authorization digest changes; changing a recipient output should change the txid. Do not apply that v5 property to a legacy v4 transaction — and for v6, use the ZIP 229 digest updates rather than assuming v5 formulas carry over. Use official vectors and the selected primitive implementation to verify exact bytes rather than relying on a high-level send result.

## Evidence matrix

- Activation: test `H-1`, `H`, and `H+1` for the relevant rule on each supported network.
- Encoding: test a valid vector, malformed length or field, non-canonical representation where relevant, and round-trip behavior only where a round trip is an adequate oracle.
- Verification: test valid and invalid signatures, proofs, or commitments with vectors from the governing rule; identify which layer rejects each case.
- Compatibility: check persisted formats, RPC outputs, and downstream consumers only where the protocol change reaches them — e.g. indexers parsing `valuePools` after NU6.3.
- Review: state the rule, applicable revision, selected code path, vectors run, and configurations not exercised. Do not claim consensus correctness from a green application test suite alone.

## Worked task: v5 transaction effects and authorization

Choose a row from the official [`zip_0244.json` vectors](https://github.com/zcash/zcash-test-vectors/blob/master/test-vectors/json/zip_0244.json), whose columns include transaction bytes, expected `txid`, and expected `auth_digest`. Pin the vector file revision, selected row, primitive library revision, network, and consensus branch ID in the test record. First compare both computed digests with that row's expected values. Then make two controlled mutations of the **decoded fields**, serialize, and recompute:

| Mutation | Expected digest relation | Additional check |
| --- | --- | --- |
| Change only an authorization field that stays parseable, such as a `scriptSig` byte in a vector with a transparent input | Same `txid`, different `auth_digest` | The mutated authorization may fail validity; digest behavior is the oracle here |
| Change an effecting field, such as a recipient output | Different `txid` | Rebuild authorization if testing a valid transaction, rather than treating a broken signature as an encoding failure |

This is a v5 [ZIP 244](https://zips.z.cash/zip-0244#specification) test. Do not use a v4 fixture or infer the property from a wallet's displayed transaction ID. Keep parse success, digest output, signature/proof validity, and block-context validity as separate assertions.

For a network-upgrade test, take the activated height `H` from the selected network parameters and run contextual validation at `H-1`, `H`, and `H+1`. A v5-only format may be rejected before `H`, so use a comparable format where possible and record the rejecting layer when not. Include branch-ID-dependent signatures and a fork that changes the selected height across `H`. This exercises [ZIP 200's activation and replay-protection mechanism](https://zips.z.cash/zip-0200#activation-mechanism), not merely a transaction-version parser branch.
