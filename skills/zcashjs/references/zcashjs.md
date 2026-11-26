# Zcash JS (`@zcashlabs/zcash.js`)

Map checked against zcashjs `v0.1.4` on 2026-11-26 for install, defaults, networks, storage, and limits; other rows were written at `0.1.1` (`de75201`, 2026-10-26). The package is an experimental prerelease: re-resolve every symbol and default below against the installed version's `src/index.ts`, `src/types.ts`, and `docs/api/` before asserting it. Anything under `docs/planning/` or `docs/research/` is a plan, not shipped API.

## Where behavior lives

| Task | Upstream source |
| --- | --- |
| Public exports and types | `src/index.ts`, `src/types.ts` |
| Install, ESM/Node requirements | `docs/api/installation.md`, `package.json` (`engines`, `type`) |
| Platform/storage constraints | `docs/api/platforms.md` |
| Networks, amounts, identifiers | `docs/api/networks-amounts.md`, `src/network-parameters.ts` |
| Public/light client behavior | `docs/api/public-client.md`, `docs/api/light-client.md` |
| Wallet open/defaults | `docs/api/wallet-runtime.md` |
| Accounts, signers, mnemonics | `docs/api/accounts-signers.md` |
| Sync semantics | `docs/api/sync.md` |
| Proposals, send/shield, recovery | `docs/api/proposals.md`, `docs/api/send-shield.md`, `docs/api/operations.md` |
| Signing, PCZT | `docs/api/signing.md` |
| Errors, cancellation, cleanup | `docs/api/errors-lifecycle.md` |
| Security/privacy posture | `docs/api/security-privacy.md` |
| Full method inventory | `docs/api/reference.md` |
| Runnable examples | `docs/api/examples/*.ts`, `examples/browser/`, `examples/testnet/` |

The [API reference](https://zcashlabs.github.io/zcashjs/api/reference.html) groups exports by purpose; use it for orientation, then confirm signatures in `src/types.ts`.

## Install and runtime

- `npm install @zcashlabs/zcash.js` — engine-pinned to Node `22.23.4` (`package.json` `engines`; pinned since 0.1.1 for the Brotli security update). ESM only (`"type": "module"`); TypeScript projects use `"module": "NodeNext"`.
- One package carries the wallet engine, workers, and local proving assets — no separate runtime package, Rust toolchain, or post-install download.
- It is an **experimental prerelease**: assume any specific behavior below drifted until checked.

## Storage and platforms

| Environment | Storage | Transport | Notes |
| --- | --- | --- | --- |
| Node | `{ kind: 'node-filesystem', path }` | native gRPC (light), JSON-RPC (public) | Persistent storage is **Linux-only** via `/usr/bin/flock`; macOS/Windows are unqualified |
| Browser (secure context) | `{ kind: 'browser-opfs', name }` | gRPC-Web + CORS (light), JSON-RPC + CORS (public) | Also needs `JSON.parse` reviver `context.source` and `AbortSignal.any` — WASM alone is not enough |
| Any | `{ kind: 'memory' }` | — | Disposable; no restart recovery |

- Bundlers must emit the lazy WASM/worker/proving assets and the app must deploy them; the qualified consumer check is a Vite build with `assetsInlineLimit: 0` and a non-root base (`examples/browser/`).
- One writer per database: a second owner gets `STORAGE_BUSY`. `memory` storage loses operation records at close.
- Endpoint shorthand `createWalletClient(endpoint, {...})` defaults: mainnet unless `network` is passed; Ironwood-only spend/change (transparent inputs disallowed); 3+3 confirmations, no zero-conf shielding; ZIP-317 fee; expiry 80 blocks; proposal lock 20 blocks; shielding threshold 10,000 zatoshis; offline startup recovery. See `wallet-runtime.md` "Defaults" for the full table — confirm at the installed version.
- Component form `createWalletClient({ network, light, storage, ... })`: omitting `broadcaster`/`transactionPolicy` leaves submission unconfigured; `light` alone gives scanning, not sending.

## Clients and transports

- **Networks:** `defineNetwork()` selects mainnet; `'testnet'` explicit. Presets carry genesis hash + activation schedule through NU7 (mainnet 3543405, testnet 4465026) as version-2 parameter documents since 0.1.4; upgrades through NU6.3 match bundled `zcash_protocol` 0.10.6, which leaves NU7 unset. A wallet database created with an earlier preset fails to open with `NETWORK_MISMATCH` (see `CHANGELOG.md`). Mismatch fails rather than switching chains. Custom networks call `defineNetwork({ identity, genesisHash, ...encodeNetworkParameters(params) })` — `encoding` plus every activation height Overwinter→Nu6_3, nondecreasing or `null`, all required; an explicit `Nu7` field selects version 2 of the document. `readGenesisHash(transport)` discovers genesis only — it does not authenticate the endpoint; for a known chain, supply the configured hash.
- **Amounts/IDs:** `parseZec`/`formatZec` keep bigint zatoshis (1 ZEC = 10⁸); `txId`/`blockHash` validate display-order hex; `accountIndex`/`diversifierIndex` are typed validators. Pool names are `transparent`, `sapling`, `ironwood` — `orchard` is not selectable.
- **Public client:** `createPublicClient(rpcUrl)` (30 s/attempt, two read attempts 500 ms apart, 4 MiB, label `public-rpc`) for `getTip`, `getBlock`/`getBlockHeader` (exactly one of `{height}`/`{hash}`), `getTransaction`, `getTransactionStatus`, `getUtxos` (transparent), tree/subtree reads, `watchTransaction`/`waitForTransaction`, `broadcastTransaction`. Credential-bearing URLs are rejected — use the `headers` callback.
- **Light client:** `createLightClient(endpoint, { network })` — lazy handshake validating chain label, Sapling height, branch ID, genesis, protocol revision. Node gets native gRPC; browsers need gRPC-Web + CORS. Regtest accepts `regtest` or the BIP70 `test` label Zakura/Zaino send. Streams (`streamCompactBlocks`, `streamAddressTransactions`, `streamMempool`) are inclusive ranges; stop a long one with an `AbortController` or `break` the loop — never pull the same iterator concurrently.
- **Transports:** `httpTransport(url, overrides)` is the JSON-RPC transport factory (renamed from `http`); `grpc(endpoint, opts)` is the lightwallet factory — native gRPC on Node, gRPC-Web in browsers. `@zcashlabs/zcash.js/grpc-node` additionally exports `createGrpcNodeTransport` for explicit Node byte-transport use.
- **Status vocabulary:** tx status `notSeen|mempool|mined|offMainChain|unknown`; broadcast outcome `acknowledged|rejected|unknown`. `unknown` means the source cannot establish the result — it is neither success nor failure.
- `createZcashClient({ public, light, wallet })` groups existing same-network clients without new state.

## Wallet lifecycle

1. **Open** — storage is required; nothing silently becomes temporary. Opening does not generate a mnemonic, attach a signer, or start a scan.
2. **Account** — `accounts.import({ mnemonic, accountIndex, birthday })` returns `{ account, signer }` with the signer **unattached**; `accounts.create({ mnemonic })` needs a synced wallet (`targetReached`) or returns `SYNC_REQUIRED`. `birthday: 'fullScan'` is explicit and expensive; `resolveBirthday({ light, firstScanHeight })` bounds it. The SDK never generates or backs up the phrase — the app owns UTF-8 mnemonic bytes end to end.
3. **Signer** — `accounts.attachSigner` must reach `binding.state === 'ready'`. `accounts.restoreSigner` re-derives from the mnemonic against the stored index (`ACCOUNT_KEY_MISMATCH` on wrong material; view-only accounts reject `SIGNER_CAPABILITY_MISMATCH`; bundled baseline runtime only).
4. **Sync** — explicit `wallet.sync({ signal })`; check `targetReached`. `watchSync` shares background progress; `getSyncStatus` reads locally. Source movement replans at most three times then returns retryable `SYNC_REQUIRED`.
5. **Query** — `getBalance` (`amounts === null` means unavailable, not zero), `getHistory` (50/page default, 200 max, opaque cursor, `CURSOR_STALE` → restart), `getTransaction`, `listNotes`/`listUtxos` (`spendState: 'unspent'` is not a spendability verdict).
6. **Receive** — `addresses.next` commits exposure before returning; `current` is a read; `at` exposes an exact index. Ironwood-only UAs match the default policy (`{ format: 'unified', transparent: 'omit', sapling: 'omit', ironwood: 'require' }`).
7. **Close** — always `await wallet.close()`; dispose caller-owned signers, bindings, viewing handles, PCZT handles separately.

## Propose, send, shield, and recover

- `wallet.propose({ accountId, to, amount, idempotencyKey })` binds inputs, outputs, fees, and consensus context — review it whole (a payment can be several transactions). `send({ proposal })` executes exactly what was reviewed. `operations.abandon` retires an unbuilt proposal; it cannot undo broadcast.
- `wallet.send({ accountId, to, amount, idempotencyKey })` plans, executes, dispatches, and returns a `PendingPayment` — dispatch is not inclusion. Reuse one request ID per intended payment; conflicting reuse → `IDEMPOTENCY_CONFLICT`.
- `pending.wait({ confirmations, timeoutMs, signal })` observes every required step; a timeout preserves `operationId`/payment state and does not cancel the payment. `wait` alone does not scan — drain `watchSync` concurrently (see `send-shield.md`'s helper).
- `wallet.shield` needs an explicit `transactionPolicy` admitting owned transparent inputs (`transparent: 'allow-owned'`, Ironwood change); the default policy rejects transparent inputs. `NOTHING_TO_SHIELD` is a real outcome, not a zero-value success.
- **Recovery:** the database retains operations, exact finalized bytes, and attempts. `operations.list`/`get`/`resume` rediscover work after reopen; `resume` rehydrates without signing or broadcasting. Startup policy: `offline` (endpoint default), `online` (bounded pass — discloses recorded tx queries), or `online + rebroadcast` (retries only previously-dispatched exact bytes within limits). Inspect `wallet.recovery.lastError` and deferred counts.
- **PCZT/external signing:** `build({ proposal })` → `wallet.pczt.export` → signer owns the exchange → `wallet.pczt.import` → `finalize` (stores bytes; does **not** submit) → `pending.broadcast()`. Local stages `build/prove/sign/finalize`; `createCustomSigner` for own signers (single-step only: `PCZT_MULTI_STEP_UNSUPPORTED`). Standalone `pczt` namespace: `parse/inspect/serialize/combine/redact` — parse needs the correct `ConsensusContext` from `getConsensusContext({ network, targetHeight })`; dispose every handle.
- **Viewing without a wallet:** `accountFromViewingKey({ network, format: 'ufvk', encoded, enabledPools })`, `addresses.find/derive/decode/selectReceiver`, `viewing.toIncoming`/`export` (requires `acknowledge: 'discloses-viewing-authority'`). Wallet `viewOnly` imports are tracking-only and never upgrade to spending.

## Errors and lifecycle

`isZcashError` narrows SDK failures; branch on `code` (messages are diagnostic text, not API). Retry-relevant codes: `SYNC_REQUIRED` (revalidate; if a payment exists, recover that operation), `STALE_PROPOSAL`, `SIGNER_REQUIRED`, `PROVING_MATERIAL_REQUIRED`, `STORAGE_BUSY`, `CURSOR_STALE`, `OBSERVATION_UNAVAILABLE`, `ABORTED`/`TIMEOUT` (inspect retained state before retrying), `RECOVERY_REQUIRED`. `ACCOUNT_BUSY`, `INVALID_AUTHORIZATION`, `REVIEW_MISMATCH` are reserved but not emitted by the bundled runtime. `retryable` is not permission to replay a whole payment.

## Limits and security

Explicitly unqualified or absent at v0.1.4 — check `platforms.md` before promising: persistent storage outside Linux; historical database migration; the complete live-browser send/receive round trip; managed artifact hosting; a persistent secret vault; a database backup API; remote proving; hardware signer integration. Node filesystem storage can be encrypted at rest with an application-supplied key; OPFS and memory storage are not encrypted (`platforms.md`). There is a documented closed-wallet `flock` backup procedure on Linux only (`operations.md`).

Privacy posture: keep secrets out of URLs (rejected anyway), logs, telemetry, and browser bundles. Viewing keys, memos, PCZTs, and operation records are sensitive even when they can't spend. Address/UTXO lookups and broadcasts disclose interest to the endpoint; online recovery queries recorded transactions. Default UAs expose all supported receivers including transparent — request shielded receivers explicitly where linking matters. Exported PCZTs are sensitive data.

## Review examples

- "Send retried after crash paid twice" → the second call had a new `idempotencyKey`; the operations journal was ignored. Correct path: reopen, `operations.list`, `resume` the recorded `operationId`.
- "Wallet opens but `send` needs a signer" → import returns an unattached signer; also check the app never generated a mnemonic to send (the SDK doesn't).
- "Browser wallet can't fetch" → endpoint speaks native gRPC, not gRPC-Web, or CORS blocks the origin; also verify the bundler deployed the lazy asset directory.
- "Regtest wallet won't handshake" → check the server's chain label (`regtest`/`test` accepted), Sapling height, branch ID, genesis match, and protocol revision.
- "Balance shows funds, proposal fails" → spendable inputs ≠ displayed total: confirmations, freshness, pool policy, and fee all gate selection.

## Sources

Last verified: 2026-11-26.

- zcashjs `package.json` (version 0.1.4, `engines.node` 22.23.4), `CHANGELOG.md` 0.1.4
- `docs/api/networks-amounts.md`: "activation schedules through NU7 (mainnet 3543405, testnet 4465026)"
- `docs/api/wallet-runtime.md` "Defaults", `docs/api/platforms.md`
