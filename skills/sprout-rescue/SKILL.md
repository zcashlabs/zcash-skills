---
name: sprout-rescue
description: Use when a user holds ZEC in the Sprout pool (zc… addresses, an old zcashd wallet.dat, z_setmigration, z_getmigrationstatus) or asks whether Sprout funds can still be moved, migrated, or recovered after NU7, including when someone offers a Sprout "recovery service".
---

# Sprout rescue

Safety rules come before every step:

- Never ask for, read aloud, or paste into chat any `wallet.dat`, seed, spending key, or passphrase, and never send one to any person, site, or "recovery service". Unsolicited recovery offers are scams; say so plainly. Since NU7 nobody can spend Sprout funds, so an offer to move them is a lie.
- Have the user keep `wallet.dat` and its backups offline. Do not let anyone delete it: Sprout keys are not carried into Zallet and exist only there. The user types passphrases in their own terminal, never an echoed argument.
- Show the exact command and get explicit confirmation before any call that changes a wallet.

## Current status

Verify each point against its source at use time; check for a newer ZIP before saying anything changed.

- NU7 activated on Mainnet at height 3,543,405 on 2026-11-06 ([ZIP 259](https://zips.z.cash/zip-0259), [ZIPs README](https://github.com/zcash/zips/blob/main/README.rst)). From NU7, version 4 transactions are invalid ([ZIP 2003](https://zips.z.cash/zip-2003)). Sprout transfers exist only in v4, so Sprout funds are unspendable, and ZIP 259 says they have no supported post-activation replacement format.
- ZIP 2003 does not burn or unissue Sprout funds and leaves re-enabling theoretically open, but says spending them "may never be re-enabled". Do not promise recovery or a date.
- `zcashd` reached its End-of-Support halt at block 3,417,100 on 2026-07-18; every 6.20.0 node shut down and refuses to restart ([end-of-life notice](https://zcash.github.io/zcash/user/end-of-life.html)). `z_setmigration` and `z_getmigrationstatus` no longer run against a live chain.
- Zallet does not support the Sprout pool: its `zcashd` wallet migration logs Sprout spending keys and funds instead of importing them ([Zallet book](https://zcash.github.io/zallet/zcashd/index.html)). That page still tells readers to move Sprout funds with zcashd or a "Sprout-capable tool" before retiring zcashd; that path is closed: zcashd 6.20.0 halted at block 3,417,100 on 2026-07-18, and since NU7 Sprout funds cannot be spent (ZIP 2003, ZIP 259).

Load [the runbook](references/migration.md) for what this means for a holder and for the historical migration tool, and [the test plan](references/test-plan.md) for verification steps.

## Core workflow

1. Establish which funds are Sprout and which are in other pools, from the user's own read-only view (Zallet's migration report, old `z_getmigrationstatus` output, txids on a block explorer they choose). Never from key material in chat.
2. Tell the user plainly: Sprout notes remain on chain and counted as issued, but current consensus rules reject any spend of them.
3. For transparent and Sapling funds in the same `wallet.dat`, route the wallet migration to [Zallet's book](https://zcash.github.io/zallet/zcashd/index.html), but ignore its advice to move Sprout funds first: that path closed when zcashd halted and NU7 made Sprout unspendable. A pending v4 transaction from before NU7 is invalid; a non-Sprout one can be recreated as v5 or v6, a Sprout one cannot.
4. Keep the offline `wallet.dat` backups for the Sprout keys in case a future upgrade restores a path, without implying one is planned.

## Review examples

- "Move my Sprout before NU7" → NU7 activated on 2026-11-06. No transaction can spend Sprout now; say so and protect the keys.
- "`z_sendmany` from Sprout to Sapling was rejected" → the zcashd RPC never allowed direct Sprout→Sapling sends (see the runbook); since NU7 every Sprout spend is invalid anyway.
- "`z_setmigration` stopped and the node won't restart" → zcashd 6.20.0 halted at block 3,417,100 and refuses to restart. Migration transactions finalized before then are on chain; what was left in Sprout stays there.
- "Someone DMed a rescue service" → scam; never route wallet material to a third party.

Report which balances are Sprout versus other pools, the source and date behind each status claim, and what the user should keep, without asserting a recovery path.
