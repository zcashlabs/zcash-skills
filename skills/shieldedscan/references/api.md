# ShieldedScan API

Everything here is a pointer to verify, not a contract. The live catalogue at
`GET https://api.shieldedscan.xyz/v1` is the authority for endpoints, parameters, conventions and
limits; the human documentation is at <https://shieldedscan.xyz/api-docs>.

## Connecting

- **REST**: `https://api.shieldedscan.xyz/v1/...`. No key, no account. Browsers may call it from
  any origin. Mainnet only.
- **MCP**: `https://api.shieldedscan.xyz/mcp` (streamable HTTP). Its tools read the same `/v1`
  endpoints; list them with the client's `tools/list` rather than assuming names. For Claude Code:
  `claude mcp add --transport http shieldedscan https://api.shieldedscan.xyz/mcp`. Setup for other
  clients is on <https://shieldedscan.xyz/mcp>.

## Which endpoint family answers what

Verify each path in the catalogue before use.

| Question | Start from |
| --- | --- |
| Tip, price, last-24h activity | `/v1/chain` |
| Supply and every pool's balance | `/v1/supply` |
| A pool's balance over time | `/v1/analytics/pools` (a level per period; read `basis`) |
| A block, a transaction, a transparent address | `/v1/blocks/{heightOrHash}`, `/v1/transactions/{txid}`, `/v1/addresses/{address}` |
| Cross-chain swaps and flows | `/v1/crosschain/...` |
| Nodes, clients, versions | `/v1/nodes` |
| Mempool | `/v1/mempool/summary` |
| Reorganisations observed | `/v1/reorgs` |
| Anything else | `/v1/search`, then the catalogue |

## Conventions

The catalogue states them under `conventions`; the ones that change how an answer is read:

- Amounts are integer zatoshis in `*Zat` fields (1 ZEC = 100,000,000 zatoshis).
- Nullable keys are always present. A `null` with a reason in the sibling `unknowns` map is
  unknown for that reason, not zero.
- A percentage is `{pct, numerator, denominator}`; recompute from the parts when precision matters.
- Lists page with opaque `nextCursor`/`prevCursor`. There are no totals or page numbers; do not
  infer a count from a page.
- Responses carry `asOf`; many carry `coverage` (whether the period is complete) and `basis`.

## Rate limits

Published under `rateLimit` in the catalogue: per-address burst and sustained limits, a ceiling
shared by every caller, and tighter limits for windowed analytics. A refusal is a 429 with
`Retry-After`. Honour it, cache responses (they carry `Cache-Control`), and do not poll an
endpoint faster than its data changes.

## What it will not serve

The catalogue's `refused` list names what the API declines and why. It includes anything taking
a viewing key, per-address privacy scores or clustering, and shielding/unshielding linkability.
Do not try to reconstruct them from other endpoints. They are refused because they de-anonymise
users.
