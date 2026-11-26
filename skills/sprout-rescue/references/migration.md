# Sprout after NU7, and the historical migration tool

Last verified: 2026-11-26.

## Status for a Sprout holder

- **Spending is disabled.** [ZIP 2003](https://zips.z.cash/zip-2003) makes version 4 transactions invalid from NU7, and "because Sprout transfers can only be represented in v4 transactions" it disables spending Sprout funds. [ZIP 259](https://zips.z.cash/zip-0259) deployed it: NU7 activated on Mainnet at height 3,543,405 (2026-11-06, per the ZIPs README). ZIP 259 adds that Sprout transactions have no supported post-activation replacement format.
- **Not burned.** ZIP 2003 does not unissue or burn Sprout funds; the Sprout balance stays in `IssuedSupply`. It leaves re-enabling v4, or another retrieval facility, as a theoretical option and says the ability "may never be re-enabled". Do not predict one.
- **No software path.** `zcashd` halted at block 3,417,100 on 2026-07-18 and refuses to restart ([end-of-life notice](https://zcash.github.io/zcash/user/end-of-life.html), [deprecation page](https://z.cash/support/zcashd-deprecation/)). Zallet's `zcashd` migration does not import Sprout keys or funds; it logs them with a count, and that key material stays only in `wallet.dat` ([Zallet book](https://zcash.github.io/zallet/zcashd/index.html)). That page still tells readers to move Sprout funds with zcashd or a "Sprout-capable tool" before retiring zcashd; that path is closed: zcashd 6.20.0 halted at block 3,417,100 on 2026-07-18, and since NU7 Sprout funds cannot be spent (ZIP 2003, ZIP 259). ZIP 2003 notes zcashd was the last maintained software with Sprout wallet support.
- **Other pools are unaffected.** Transparent and Sapling funds in the same wallet move to Zallet through its migration. Any pending v4 transaction from before NU7 is invalid; a non-Sprout one can be recreated in a supported format, and re-signing alone cannot make a v4 transaction valid (ZIP 259).

What to keep: the original `wallet.dat` and offline backups. If the community ever restores a spending path, those keys would be needed.

## The historical migration tool

Before NU7 the supported exit was zcashd's built-in tool. These statements trace to the zcashd docs page [*Sprout-to-Sapling Migration*](https://zcash.readthedocs.io/en/master/rtd_pages/sapling_turnstile.html); use them to read old `z_getmigrationstatus` output or explain migration txids already on chain, not as steps to run today.

### Why a tool existed

- **User level:** the zcashd payment RPCs (`z_sendmany`, `z_mergetoaddress`) prohibit any transaction directly between Sprout and Sapling addresses. Sending between them requires a transparent intermediary address, which publicly exposes the balance.
- **Consensus level (pre-NU7):** a direct Sprout→Sapling transaction was allowed, but its value passed through the transparent value pool, which still exposes it. The tool was the supported way to use it.

Moving value out of Sprout was never private: the value crosses the transparent pool either way (ZIP 2003 also notes the amount is visible through `vpub_old`/`vpub_new`). The tool's privacy claim was narrower: it hid each user's migration among other users' migrations at the same time, with amounts drawn from a random distribution.

### What it did

Available since zcashd **2.0.5-2**, it migrated funds from **any** Sprout address in the wallet to a **single** destination Sapling address:

- up to 5 transactions **whenever the blockchain reaches a 500-block-height interval**
- amounts picked from a random distribution
- auto-disabled once the wallet's Sprout balance fell below **0.01 ZEC**
- destination: the Sapling account 0 address by default, or `-migrationdestaddress=<SAPLINGADDR>` in `zcash.conf`
- `z_setmigration` did not persist across restarts unless `-migration` was set in `zcash.conf`, and with that flag a restart re-enabled it even after `z_setmigration false`

### `z_getmigrationstatus` fields

From the doc's example output, for reading saved output:

| Field | Type | Meaning |
| --- | --- | --- |
| `enabled` | boolean | whether migration is enabled |
| `destination_address` | string | Sapling address receiving the funds |
| `unmigrated_amount` | numeric | total unmigrated ZEC |
| `unfinalized_migrated_amount` | numeric | sent but not yet finalized |
| `finalized_migrated_amount` | numeric | finalized total |
| `finalized_migration_transactions` | numeric | count of this wallet's migration txs |
| `time_started` | numeric, optional | block time of the first migration tx (Unix timestamp) |
| `migration_txids` | array | all migration txids involving this wallet |

A nonzero `unmigrated_amount` in output saved before the halt is Sprout value that is now unspendable. Unfinalized migration transactions that were never mined are v4 and invalid after NU7.

## Sources

- [ZIP 2003](https://zips.z.cash/zip-2003), Status: Final
- [ZIP 259](https://zips.z.cash/zip-0259), Status: Final; [zcash/zips README.rst](https://github.com/zcash/zips/blob/main/README.rst) "Settled Mainnet Network Upgrade"
- [zcashd end-of-life notice](https://zcash.github.io/zcash/user/end-of-life.html), [zcashd deprecation page](https://z.cash/support/zcashd-deprecation/)
- [Zallet book: Migrating from zcashd](https://zcash.github.io/zallet/zcashd/index.html) (its advice to move Sprout funds with zcashd or a "Sprout-capable tool" before retiring zcashd is out of date: zcashd halted at block 3,417,100 and NU7 made Sprout unspendable)
- [zcashd docs: Sprout-to-Sapling Migration](https://zcash.readthedocs.io/en/master/rtd_pages/sapling_turnstile.html)
