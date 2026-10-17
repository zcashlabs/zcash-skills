---
name: zcash-wallet
description: Use when building Zcash wallet account, seed, key, viewing-authority, address, receiver-selection, or payment-request handling across implementations.
---

# Zcash wallet

Resolve the target network and the selected wallet library before implementing wallet identity or address behavior.

For key authority or account identity, load [the contract and capability boundaries](references/keys-addresses.md#establish-the-contract). For UA receiver selection or TEX destinations, load [address handling](references/keys-addresses.md#handling-an-address). For seed restore or ZIP 321 parsing, load [recovery and requests](references/keys-addresses.md#recovery-and-requests); for an index-0 discovery failure, load [the worked restore task](references/keys-addresses.md#worked-task-restore-an-index-0-transparent-payment). Choose boundary tests from [useful checks](references/keys-addresses.md#useful-checks).

Model account, spending key, viewing key, receiver, and encoded address as separate concepts. An address decoder does not establish account ownership or spending authority. Check how wallet birthdays and derivation paths affect restoration and discovery. Preserve shielded receiver choice and key privacy when adding logs or export paths.

## Core workflow

1. Identify the key capability and network at each API boundary.
2. Separate parsing, wallet ownership, and recipient selection; inspect the pinned decoder and derivation implementation.
3. Check the applicable ZIP revision before accepting a receiver or payment-request format.
4. Test wrong-network and unsupported inputs alongside the intended path, then restore disposable keys against a controlled history if recovery is claimed.

Use [official Zcash test vectors](https://github.com/zcash/zcash-test-vectors) for encodings and key derivation where applicable. An address round trip alone does not prove account recovery or spendability.

## Review examples

- A UA with shielded and transparent receivers tests decoding, the sender's supported pools, the selected receiver, and the privacy consequence of the choice. Post-NU6.3, a shielded Orchard-protocol receiver lands in the Ironwood pool.
- A seed restore tests account derivation, birthday, transparent diversifier index 0, and discovered funds on a known chain. Matching address text alone is too weak.
- A ZIP 321 URI with an unsupported `req-*` parameter is rejected as a whole request; ordinary unknown parameters do not justify inventing a payment.
- A `tex1…` destination (ZIP 320) must be funded only from transparent UTXOs — a shielded-funded output to a TEX is a wallet bug, not a consensus failure. The conforming shielded path unshields to an ephemeral transparent address first.

Report the network, ZIP revision, selected library version, receiver or key capability, and the observed recovery or payment-request result. Keep secret key material out of reports.
