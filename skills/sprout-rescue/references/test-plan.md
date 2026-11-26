# Test plan

Last verified: 2026-11-26. Verification for this skill is source reading only; no node was run. The procedures below are for an operator.

## Status checks (before advising a user)

1. Re-read [ZIP 2003](https://zips.z.cash/zip-2003) and [ZIP 259](https://zips.z.cash/zip-0259): confirm v4 transactions are still invalid and no later ZIP restores a Sprout spending path.
2. Check the [zcash/zips README](https://github.com/zcash/zips/blob/main/README.rst) "Settled Mainnet Network Upgrade" section for the current upgrade.
3. Re-read the [Zallet book](https://zcash.github.io/zallet/zcashd/index.html) "What is not migrated" list before saying what Zallet does with Sprout keys.

## Consensus check (operator-run, Regtest)

The rule behind this skill is "v4 is invalid from NU7". Exercise it on a Zebra or Zakura Regtest with NU7 at a deferred height `H`, as in [zcash-protocol](../../zcash-protocol/SKILL.md): a v4 transaction is accepted below `H` and rejected at `H` and `H+1`. Record the rejecting layer. This proves the rule on that build, not anything about a user's funds.

The zcashd migration tool cannot be exercised against Mainnet: zcashd 6.20.0 halted at block 3,417,100 and refuses to restart.

## Read-only checks (real wallet)

Nothing here spends or exposes keys: Zallet's migration report (it logs Sprout keys and funds it did not import), saved `z_getmigrationstatus` output, and migration txids the user looks up themselves.

## Repo-side checks (run for this skill)

- `python3 docs/check-facts.py` and `--upstream`; the Sprout-migration oracles still read the zcashd docs page.
- `python3 docs/gen-manifest.py`, `python3 docs/verify-claims.py --base <base>`, `python3 -m unittest discover -s tests`.
- Secret/address scan: only `zc…`/`zs…` placeholders appear in the skill.

## Sources

- [ZIP 2003](https://zips.z.cash/zip-2003), [ZIP 259](https://zips.z.cash/zip-0259)
- [zcashd end-of-life notice](https://zcash.github.io/zcash/user/end-of-life.html)
- [Zallet book: Migrating from zcashd](https://zcash.github.io/zallet/zcashd/index.html)
