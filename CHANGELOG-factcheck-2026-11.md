# Fact-check 2026-11

Checked on 2026-11-26 against official sources only. Facts marked verified on that date were re-read at the source.

## Changes

- **NU7 is live.** ZIP 259 is Final; NU7 activated on Mainnet at height 3,543,405 on 2026-11-06 at 02:34 UTC. Replaced "Draft, target 2026-11-05" with the activation, added the Mainnet `NSM_REISSUANCE_HEIGHT` (8,939,664), and added a `nu7-mainnet-height` oracle. Root `SKILL.md`, `README.md`, `zcash`, `zcash-protocol`, `zcash-payments`, `docs/versioned-facts.md`.
- **Sprout is unspendable.** ZIP 2003 makes v4 transactions invalid from NU7, so Sprout funds cannot be spent; it does not burn them and says spending "may never be re-enabled". Rewrote `sprout-rescue` around the holder's situation (keep `wallet.dat` offline, no recovery path to promise, scam warning), kept the migration tool as history, and corrected the protocol reference that said ZIP 2003 advises moving funds before activation. Updated three Sprout eval prompts.
- **zcashd halted.** The End-of-Support halt at block 3,417,100 on 2026-07-18 shut down every zcashd 6.20.0 node. "Deprecated" statements now say so.
- **Zallet and Sprout.** Zallet's zcashd migration does not import Sprout keys or funds.
- **ECC and ZODL.** "ECC is now ZODL" became "ECC's Zcash team is now ZODL", per zodl.com/about.
- **ZIP 317.** Revision 2 is Proposed and comes from ZIP 2009 (marginal fee 5,000 to 1,000 zatoshis, weight ratio cap 4 to 10), not a draft tied to ZIP 248.
- **Zakura.** zcashd-compat has five installer modes (adds `build-from-source`); the documented sidecar is v1.3.1, the first to schedule Mainnet NU7.
- **Thus Spoke Zakura v0.5.0.** Workspace 0.5.0; wallet crates `zakura-*` 4.0.0 and `zakura-client-*` 0.1.0-rc9.4 with no direct `zakura-pczt` pin; native runtime by default (`start --docker` for images); NU7 Regtest height configurable with `--nu7-height` (default 1). Updated `ths`, `ths-runtime`, `ths-wallet-server`, `ths-dashboard`, root `SKILL.md`, `README.md`.
- **zcashjs 0.1.4.** Presets include NU7; Node filesystem storage can be encrypted at rest.
- Re-verified and re-dated the NU6.3, ZIP 316/320/321, Node-engine, image, and Sprout-doc facts. Updated a test fixture for the new THS version.

## Source(s) of truth

- https://github.com/zcash/zips/blob/main/README.rst ("Settled Mainnet Network Upgrade")
- https://zips.z.cash/zip-0259
- https://zips.z.cash/zip-2003
- https://zips.z.cash/zip-0258
- https://zips.z.cash/zip-0218
- https://zips.z.cash/zip-0317
- https://zips.z.cash/zip-2009
- https://zips.z.cash/zip-0316
- https://zips.z.cash/zip-0320
- https://zips.z.cash/zip-0321
- https://zcash.github.io/zcash/user/end-of-life.html
- https://z.cash/support/zcashd-deprecation/
- https://zcash.github.io/zallet/zcashd/index.html
- https://zfnd.org/zebra-7-0-0-release/
- https://zodl.com/about/
- https://zcash.readthedocs.io/en/master/rtd_pages/sapling_turnstile.html
- https://github.com/zakura-core/zakura/blob/main/docs/zcashd-compat.md
- https://github.com/zakura-core/zakura/blob/main/README.md
- https://github.com/zcashlabs/thus-spoke-zakura/blob/main/Cargo.toml
- https://github.com/zcashlabs/thus-spoke-zakura/blob/main/crates/ths-server/Cargo.toml
- https://github.com/zcashlabs/thus-spoke-zakura/blob/main/crates/ths-server/src/network.rs
- https://github.com/zcashlabs/thus-spoke-zakura/blob/main/crates/ths-server/src/bootstrap/config.rs
- https://github.com/zcashlabs/thus-spoke-zakura/blob/main/AGENTS.md
- https://github.com/zcashlabs/thus-spoke-zakura/blob/main/CHANGELOG.md
- https://github.com/zcashlabs/zcashjs/blob/main/package.json
- https://github.com/zcashlabs/zcashjs/blob/main/CHANGELOG.md
- https://github.com/zcashlabs/zcashjs/blob/main/docs/api/networks-amounts.md
- https://github.com/zcashlabs/zcashjs/blob/main/docs/api/platforms.md
