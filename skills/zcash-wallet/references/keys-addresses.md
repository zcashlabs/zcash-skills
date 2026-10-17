# Keys, addresses, and payment requests

## Establish the contract

Resolve the target network, active upgrade, supported pools, wallet library revision, and applicable ZIP revision. Parsing, account ownership, and spending authority are separate checks. A syntactically valid address for the right network may belong to someone else; a viewing key may reveal transactions without authorizing spends.

| Capability | Question to answer before exposing it |
| --- | --- |
| Seed or spending key | Who can derive accounts or authorize spends, and where can the secret be stored? |
| Full viewing key | Which incoming, outgoing, and spent activity can its holder observe? |
| Incoming viewing key | Which incoming payments can its holder detect? |
| Address or receiver | Which pool and network can a sender use, and does this wallet control it? |

Use [ZIP 32](https://zips.z.cash/zip-0032) for shielded account/key derivation and [ZIP 316](https://zips.z.cash/zip-0316) for Unified Addresses and viewing-key containers. Confirm the selected library's implementation rather than assuming its types match the latest ZIP text.

### Capability boundaries

Do not collapse these operations into one `valid_address` check:

| Operation | Evidence required | What it does not prove |
| --- | --- | --- |
| Decode an address | Encoding, network, recognized receiver items | The current wallet owns it |
| Recognize a wallet receiver | Derived or persisted account receiver matches | A viewing-only wallet can spend |
| Discover a payment | Chain scan from an adequate birthday, with the relevant viewing authority | The note is currently spendable |
| Authorize a spend | The selected account has the required spending authority and spendable inputs | The broadcast will be mined |

For viewing-key export, state exactly whether the material is a UFVK, UIVK, pool-specific FVK, or account public derivation key. A full viewing key and an incoming viewing key have different observation capabilities. Treat encoded viewing keys as sensitive even though they cannot sign a spend.

## Handling an address

1. Parse the encoded address and check its network and supported type. Treat unsupported receiver types, invalid encodings, and wrong-network addresses as distinct outcomes when the API exposes them.
2. For a wallet-owned-address claim, compare decoded receivers with the account's derived receivers or persisted wallet metadata. Parsing alone proves no ownership. A full viewing key can establish viewing capability without implying spending capability.
3. When sending to a Unified Address, apply the applicable receiver-selection rule to the sender's supported set. Active ZIP 316 Revision 0 orders Orchard, Sapling, then transparent; the sender uses the most preferred supported receiver. Do not choose a transparent receiver merely because it is easy to construct: this changes on-chain visibility.
4. Preserve unknown items according to the applicable ZIP's forward-compatibility rules. A newer draft revision or experimental receiver is not automatically supported by an older wallet.

ZIP 316 Revision 0 is active; Revision 2 is draft as of this reference's review. Check the status again when implementing. Revision 0 has receiver selection rules for understood items; Revision 2 adds MUST-understand typecodes and new encodings: `zu` for shielded-only UAs (transparent items forbidden) and `tu` for transparent-enabled UAs, plus `uvf`/`uvi` viewing-key prefixes replacing `uview`. Do not apply a draft rule to a Revision 0 address without an activated implementation contract.

**Ironwood note (NU6.3):** The Ironwood pool reuses the Orchard protocol's keys and receiver item — UA encodings did not change. An Orchard-type receiver selected under ZIP 316 produces a note committed to the Ironwood pool on post-NU6.3 chains; the legacy Orchard pool accepts spends and change but no new incoming value. When a fixture or test says "Orchard payment," check whether the claim is about the *address receiver type* (unchanged) or the *destination pool* (now Ironwood). See [ZIP 229](https://zips.z.cash/zip-0229) and the [Ironwood book](https://zcash.github.io/ironwood/).

**TEX addresses (ZIP 320):** a `tex1…` (Mainnet) or `textest1…` (Testnet) address is a Bech32m re-encoding of a transparent P2PKH validating-key hash — same 20-byte payload as the `t1`/`t3`-family address, different encoding, different promise. The encoding is a directive from the recipient (originally motivated by exchange deposit requirements): **only transparent UTXOs may fund a transaction output to a TEX address**. It is a wallet-behavior rule, not consensus — a non-conforming sender risks loss of funds (the recipient may be unable to identify a source address to return them).

Sender handling:

- Sending transparent funds to a TEX: no extra requirements beyond the encoding.
- Sending shielded funds to a TEX: the conforming path is **two transactions** — unshield to an ephemeral transparent address, then send transparently to the TEX. The ephemeral address should be recoverable from the ZIP 32 seed and not linkable across transactions.
- TEX is not a Unified Address and does not participate in ZIP 316 receiver selection; decode it on its own path (`bech32m`, HRP `tex`/`textest`, 20-byte payload) and do not mistake it for a `uregtest`/`u1` UA or a raw `t1`.
- Conversion `tex` ↔ `t1` is mechanical (same key hash); display both forms if it aids UX, but honor the source restriction only for the TEX form.
- Round-trip fixture from the ZIP: `t1VmmGiyjVNeCjxDZzg7vZmd99WyzVby9yC` ↔ `tex1s2rt77ggv6q989lr49rkgzmh5slsksa9khdgte`.

**Decode matrix from ZIP 316:** Treat raw item ordering and send preference as separate rules. Encoded receiver items use ascending typecode order, while a sender's preferred supported receiver is Orchard, then Sapling, then transparent. For a Revision 0 UA, test duplicate typecodes, descending encoded typecodes, both P2SH and P2PKH transparent receivers, a transparent-only UA, and trailing bytes as invalid encodings. Test an ordinary unknown item as forward-compatible input; it does not become a receiver the sender can spend to. See the [UA requirements](https://zips.z.cash/zip-0316#requirements-for-both-unified-addresses-and-unified-viewing-keys) and [encoding rules](https://zips.z.cash/zip-0316#encoding-of-unified-addresses). Prefer the [official UA vectors](https://github.com/zcash/zcash-test-vectors) to hand-written address strings.

**Example:** A UA with Orchard and transparent receivers sent from an Orchard-capable wallet selects the Orchard-type receiver under ZIP 316 Revision 0 (producing an Ironwood-pool note after NU6.3). A wallet that cannot use it must check whether another supported receiver is valid under its actual rules; it must not silently claim a shielded payment was made.

## Recovery and requests

Account derivation, diversified addresses, and wallet birthday serve different purposes. For a restore, confirm the seed or viewing key derives the expected account, the scan starts early enough, and the wallet eventually discovers the expected outputs. ZIP 316 requires scanning transparent diversifier index 0 for every ZIP 32 account, even if that wallet would not derive a Unified Address at index 0. An address round-trip test does not establish recovery.

**Worked restore case:** A wallet generates its first UA at a nonzero diversifier index because index 0 is invalid for its Sapling component. Another wallet previously received transparent funds at the account's index-0 P2PKH receiver. A restore that scans only addresses represented in generated UAs misses those funds. The test must seed a payment to that index-0 receiver, restore the account from the same key material, scan from before the payment, and observe the transparent output. See [ZIP 316's derivation rule](https://zips.z.cash/zip-0316#deriving-a-unified-address-from-a-uivk).

[ZIP 321](https://zips.z.cash/zip-0321) requests can include multiple indexed payments, amounts, and optional memos. Treat the indexed payments as one payment intent; partial fulfillment must be presented as a different intent. Parse the entire request before presenting it as payable: an unknown `req-*` parameter invalidates the URI, while an ordinary unknown parameter is ignored. In the active ZIP, a memo is invalid for a transparent-only address and decoded memo content is limited to 512 bytes. Use the pinned URI parser where available rather than ad hoc query-string splitting.

ZIP 321 specifies that implementations **should** construct one transaction paying all requested addresses. If the selected wallet cannot do that, surface that limitation rather than silently dropping an indexed payment. Review address indices, duplicate parameters, amount precision, memo decoding, and unsupported required parameters together. A parser that takes only the first `address` and `amount` can make a syntactically valid URI into a different payment.

| Request shape | Expected handling |
| --- | --- |
| `address` plus `address.1`, each with its own amount | Retain both indexed payments in one proposed request |
| An unknown `req-*` key | Reject the entire URI |
| An unknown ordinary key | Ignore that key under the ZIP's forward-compatibility rule |
| Memo associated with a transparent-only receiver | Reject the invalid memo/payment combination |

More parser cases from the [ZIP 321 syntax and semantics](https://zips.z.cash/zip-0321#uri-syntax): a duplicate parameter at the same index, `amount.1` without `address.1`, and a leading-zero index such as `.01` are invalid. Nonsequential indices are permitted. Amounts have at most eight fractional decimal places; memo data uses unpadded Base64URL; `amount` and `req-asset` at the same index are mutually exclusive. Use the ZIP's published valid/invalid examples as fixtures so the test checks the whole URI, not a synthetic fragment that cannot parse.

**Concrete URI fixture:** This [ZIP 321 valid example](https://zips.z.cash/zip-0321#examples) is a testnet request with a transparent payment, a Sapling payment, and a memo for the Sapling payment. Use it as parser input, never as a real recipient.

```text
zcash:?address=tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU&amount=123.456&address.1=ztestsapling10yy2ex5dcqkclhc7z7yrnjq2z6feyjad56ptwlfgmy77dmaqqrl9gyhprdx59qgmsnyfska2kez&amount.1=0.789&memo.1=VGhpcyBpcyBhIHVuaWNvZGUgbWVtbyDinKjwn6aE8J-PhvCfjok
```

The parsed intent has two payments: `(transparent address, 12,345,600,000 zatoshis)` and `(Sapling address, 78,900,000 zatoshis, memo)`. Remove `address.1` but keep `amount.1`, duplicate `amount.1`, or add an unsupported `req-*` key; each mutation must invalidate the whole request. Renumber both `.1` fields to `.2`; the resulting nonsequential index remains valid. Test the selected wallet's exact decimal conversion before constructing either payment.

## Useful checks

- Wrong network, malformed encoding, and unsupported receiver each produce the intended error.
- A decoded external address is not marked wallet-owned; an address derived from the account is.
- Receiver selection prefers the applicable shielded option and preserves a valid fallback case.
- Restoring disposable keys from a controlled chain finds the same account outputs at the expected birthday.
- Logs, API errors, and test diagnostics do not disclose seeds, spending keys, viewing keys, or memos.

Implementation maps: [`zcash_address`](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_address/) for parsing and [`zcash_keys`](https://zcash.github.io/librustzcash/rustdoc/latest/zcash_keys/) for key/address types when those crates are selected — the `zakura-*` forks (e.g. `zakura-keys`, `zakura-zip321`) expose the same API surface under `zcash_*` package aliases in the projects that use them. Resolve the pinned versions first.

## Worked task: restore an index-0 transparent payment

**Input fixture:** On a disposable chain, account `A` has a ZIP 32 key or UFVK and birthday `B`. Its first generated UA skips diversifier index 0 because the Sapling component cannot use that index. A legacy wallet was paid at height `B+5` to the account's transparent external receiver at path `m / 44' / coin_type' / A' / 0 / 0`. Record the exact outpoint and value before restoring.

| Step | Required observation |
| --- | --- |
| Derive index-0 transparent receiver from account viewing material | It matches the funded transparent address even though no generated UA displays that index |
| Restore the same UFVK with birthday at or before `B+5` | Transparent discovery queries the index-0 receiver; if the selected API is history-bounded, its range covers the funding block |
| Finish the scan | The exact outpoint and zatoshi value appear under account `A`; no second account owns it |
| Attempt spending with only the UFVK | Viewing is possible; spending authority is absent |

Negative control: omit index-0 transparent discovery and observe the missing outpoint. A late birthday is a valid negative control only when the selected transparent-history API actually excludes earlier outputs; a current-UTXO API may still return an older unspent output. Restore from spending material separately if spendability is part of the claim. This distinguishes ZIP 316's [index-0 recovery requirement](https://zips.z.cash/zip-0316#deriving-a-unified-address-from-a-uivk) from address decoding and from authorization. Use the selected wallet's actual derivation and scan APIs; an upstream `latest` API page is navigation, not a version pin.

For a send built from a ZIP 321 request, carry the parsed payment indices into the transaction request and record the receiver selected from each UA. A successful parse alone does not prove the sender used the preferred supported receiver or paid every requested output. Check the constructed outputs and exact amounts against the parsed fixture above.
