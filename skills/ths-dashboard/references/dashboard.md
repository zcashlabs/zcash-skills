# Dashboard data flow

## Current source map

| Concern | Owner |
| --- | --- |
| HTTP client, endpoints, errors, and runtime validation | `web/src/lib/api/` |
| Server-backed data and query keys | `web/src/hooks/queries.ts` |
| Send, faucet, mine, and query invalidation | `web/src/hooks/mutations.ts` |
| Retained send/faucet identity, browser storage, and cross-tab locks | `web/src/hooks/payment-identity.ts` |
| SSE topic invalidation | `web/src/hooks/useServerEvents.ts` |
| Balance and activity UI | `web/src/features/wallet/` |
| Block, transaction, and address views | `web/src/features/explorer/` |

The server wallet snapshot is the authority for account balances. `WalletPage` reads `useAccounts()` in `web/src/hooks/queries.ts`, which binds `queryKeys.accounts` (`['accounts']`) to `api.accounts`. Follow that request into `web/src/lib/api/` and its account schema before inspecting the rendered aggregate. `WalletPage` may sum the query's account values for display; it must not reconstruct balances from activity or chain data. Activity is a separate record of user operations and confirmation. Keep data ownership in TanStack Query and derive presentation in components.

The API client validates Rust responses with Zod at the boundary. Wallet account and activity zatoshi fields are checked and converted to `bigint` in `schemas.ts`; forms parse decimal strings in `web/src/lib/money.ts`. Explorer chain-value fields (`chainValueZat`, `valueDeltaZat`) currently remain JavaScript `number`, and `SupplyPanel` sums them as numbers. Valid ZEC supply is at most 2.1 quadrillion zatoshis, below JavaScript's safe-integer limit, so this representation is exact for valid chain values. Check the range and API representation if explorer money behavior changes. If Rust changes an endpoint shape, update the endpoint call, schema, affected hook/component, and boundary tests together.

## Mutation and event behavior

`useSend` and `useFaucet` both wrap `usePaymentMutation` in `web/src/hooks/mutations.ts`. Before POST, `payment-identity.ts::retainPayment` retains the operation's exact variables and idempotency key under `withPaymentLock`; this requires `navigator.locks`. It writes a durable per-key `localStorage` record, a shared key when absent, and a per-tab `sessionStorage` `{name}:tab` entry. Resolve the identity using `paymentName`, `retainedPaymentKey`, and `clearPayment` in that file; `operationKey` in `mutations.ts` serves mining, not send/faucet identity. Resume reuses the retained key and variables. A transport error or accepted pending result must preserve that identity across reload or browser restart.

Both payment hooks return `{ activity, key }` (with an optional cleanup error). Their success handler seeds `queryKeys.payment(key)`, preserves an already-terminal cache result, invalidates wallet queries without waiting for them, and clears retained identity only for terminal `confirmed` or `failed` responses. `clearPayment` removes only entries still matching that identity, under the payment lock. Follow `usePaymentStatus` and `PaymentStatus.tsx` for later confirmation, failure, and storage cleanup. Test lost responses, cross-tab submissions, restored identities, and newer same-details keys at the actual storage and query owners before claiming duplicate prevention.

At the checked THS revision, `useServerEvents.ts::TOPICS` maps `wallet` to accounts/activity/send-quote, `chain` to status/blocks plus the `block`/`transaction`/`address` detail prefixes, `sync` to status, and `mining` to `['mining']`. The `chain` topic does not invalidate mempool or accounts. An unknown topic invalidates all mapped keys. Check the actual key and event when a view is stale; adding local mirrored state will hide the broken invalidation. Recheck `TOPICS` in the target checkout before relying on this map.

The activity query key is `['activity', limit]` and block-page key is `['blocks', before ?? 'tip']`; invalidating the shorter prefixes reaches all mounted variants. Detail keys are `['block', id]`, `['transaction', txid]`, `['address', address]` — verify the current `TOPICS` map covers a key before asserting a refresh gap; this mapping has changed before.

The SSE endpoint emits topics without event IDs or replay. If a connection drops or lags, a missed event does not prove the cache is fresh. Compare the current `/api/v1/accounts` result with `useAccounts()` and check whether a refetch occurred. If the API is stale, trace server sync and snapshot publication; if only the UI is stale, trace query invalidation, cache identity, and SSE delivery. Do not assume a fixed sync delay.

## Stale balance diagnosis

1. Record source revision, running app image identity, instance, and `ths endpoints` output before changing state. After server edits, run `cargo run -p thus-spoke-zakura -- build --dev`, then start a **new named instance** using the rebuilt image. A build does not replace an existing container. Preserve the old instance and wallet store while collecting failure evidence.
2. For frontend work, `THS_DEV_API=<dashboard-url> npm run dev --prefix web` runs Vite with `/api` proxied to the existing instance. It updates frontend code only; it does not rebuild or replace that instance's server. Verify `web/vite.config.ts` and the chosen API target.
3. Compare raw `/api/v1/status` and `/api/v1/accounts` with node height and hash. Inspect sync state, last error, and last success; `/api/v1/health` may remain 200 after an earlier successful sync. If accounts are already stale over HTTP, follow [snapshot publication](../../ths-wallet-server/references/wallet-server.md#sync-and-balance-publication).
4. If HTTP accounts are current, trace `web/src/hooks/queries.ts::useAccounts` → `queryKeys.accounts` → `api.accounts` and its Zod validation into `WalletPage`. Compare the response, cached data, query update time, and rendered values. Check the `wallet` event and exact key refetch; `chain` and `sync` alone do not refresh accounts.
5. For a UI regression, mount the real accounts query with a changed API fixture, deliver `wallet`, and assert a refetch plus the changed displayed total. Separately test snapshot preservation on sync failure and same-height hash replacement for server changes. Report which artifact and boundary each check exercised.

### Worked response-state diagnosis

The production `api/payments.rs::send` handler persists the claim and returns a payment response; background progression performs wallet work. `payment_response` returns HTTP 202 for `preparing`/`prepared`/`broadcast` and HTTP 200 for terminal `confirmed`/`failed`. A successful POST does not by itself establish inclusion or successful payment. `SendDialog` announces confirmation only when `activity.status === 'confirmed'`; accepted work is followed through `queryKeys.payment(key)` / `usePaymentStatus` and `PaymentStatus.tsx`.

For an accepted payment whose response is lost, keep the retained key, restore or resume that operation, and inspect the read-only keyed status before creating new work. Test a pending response followed by confirmation, a failed terminal response, an unavailable status read, and a newer draft edited while POST is in flight. Assert confirmation announcements use terminal evidence and occur once, while the newer draft survives. Inspect `SendDialog.test.tsx`, `WalletPage.test.tsx`, `web/src/hooks/send.test.tsx`, `faucet.test.tsx`, and the API schema tests for the nearest seam. A helper that combines submission and mining is not the production HTTP path.

For a fresh request, `SendDialog` checks the displayed account pool total and `useSendQuote`'s maximum after fees; the wallet SDK decides actual spendability at proposal time. A retained request resumes before those fresh-balance and quote checks, because it may already have spent its inputs. For a retry or error-state change, test the user action, retained variables, and exact key through `payment-identity.ts`, rather than checking only that one UUID-shaped key exists.

## UI and verification

For wallet forms, preserve server validation as the trust boundary while giving prompt field feedback. Check empty, invalid, pending, success, and error states. For explorer changes, distinguish chain data from wallet activity and check loading, not-found, and stale-query paths.

Use Node 24. Run the web lint, format, test, and build commands in `AGENTS.md` after `web/` changes. Nearby tests include `WalletPage.test.tsx`, `SendDialog.test.tsx`, `FaucetDialog.test.tsx`, `schemas.test.ts`, `useServerEvents.test.tsx`, and explorer tests (`ExplorerPage`, `BlockDetail`, `TransactionDetail`, `SearchBar`, `resolve-input`, `shielding`). Choose Vite or a rebuilt container using the artifact distinction in [balance diagnosis](#stale-balance-diagnosis).

## Worked task: explorer detail is stale after a chain change

**Input:** The user opens `/explorer/tx/:txid` or `/explorer/block/:id`, then mines or reorganizes the selected chain. `ExplorerPage` routes to `TransactionDetail` or `BlockDetail`; their hooks use `queryKeys.transaction(txid)` and `queryKeys.block(id)`. The `chain` SSE topic currently invalidates status, the `['blocks']` list prefix, and the `['block']`/`['transaction']`/`['address']` detail prefixes; mempool is outside this mapping. Confirm the mapping in `useServerEvents.ts` covers the affected key before assuming a refresh gap.

1. Reproduce with a mounted detail query and a controlled `chain` event. Record the API response before and after the event and whether that exact detail key refetched.
2. If the API changed but the view did not, fix invalidation at `useServerEvents.ts` or the owning query key; do not copy server data into component state. If the API itself is stale, trace the server RPC and snapshot path instead.
3. Assert a refetch for `['transaction', txid]`, `['block', id]`, and any affected `['address', address]` entry. Keep list pagination keyed by `before` intact. Test a missing detail and a same-height reorg, since a height-only comparison can miss the latter.

**Money oracle for a separate supply-format change:** `schemas.ts` leaves explorer `chainValueZat` and `valueDeltaZat` as numbers. `SupplyPanel` sums pool values as numbers before formatting. Test an ordinary block and a valid value near the 2.1 quadrillion zatoshi supply cap, including signed deltas. Those values are safely representable as integers. A value above `Number.MAX_SAFE_INTEGER` is malformed for ZEC supply; reject it at the API boundary if widening the accepted input range. Do not cite the current number arithmetic as a demonstrated loss of valid ZEC value.

```console
npm test --prefix web -- src/features/explorer/ExplorerPage.test.tsx
npm test --prefix web -- src/features/explorer/TransactionDetail.test.tsx
```

These are nearby tests, not a substitute for a new event-invalidation or supply-precision case. Run all web checks from `AGENTS.md` after editing `web/`.
