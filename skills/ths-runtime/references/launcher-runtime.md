# Launcher and Docker runtime

## Where behavior lives

| Concern | Current owner |
| --- | --- |
| Command parsing and dispatch | `crates/ths-cli/src/args.rs`, `args/amount.rs`, `commands.rs`, `commands/wallet.rs`; `main.rs` calls `lib.rs::run_from` (`thus-spoke-zakura` package, `ths` binary) |
| Runtime module wiring and diagnostics | `crates/ths-cli/src/runtime.rs` |
| Startup, readiness, shutdown, child commands | `crates/ths-cli/src/runtime/startup.rs`, `readiness.rs`, `runner.rs`; helper deadlines and cancellation in `crates/ths-cli/src/lifecycle.rs` |
| Docker creation, ownership, verified cleanup, recovery journal | `crates/ths-cli/src/runtime/resources.rs`, `docker.rs`, `cleanup.rs`, `recovery.rs` |
| Monitoring external deletion of an allocated app container | `crates/ths-cli/src/runtime/deletion.rs` |
| Instance names, persisted endpoints, host ports, status | `crates/ths-cli/src/runtime/instance.rs` |
| Image constants, selectors, build and pull | `crates/ths-cli/src/runtime/images.rs` |
| Wallet/API client calls and durable retry keys | `crates/ths-cli/src/client.rs`, `intents.rs` |
| Runtime unit and lifecycle tests | `crates/ths-cli/tests/unit/runtime/`; follow the `#[path]` declarations from `crates/ths-cli/src/runtime.rs` |
| Self-update and uninstall | `crates/ths-cli/src/updater.rs`, `install.sh` |
| Source-built app and lightwalletd images | `Dockerfile`, `docker/lightwalletd.Dockerfile` |

Map checked against THS main at `6b00d0f0e40ecd42f61ca046485a03b69c5f3338` on 2026-10-16. Paths without a crate prefix in a row are siblings of that row's first file. Resolve the actual checked-out symbols before editing; this map is navigation, not a substitute for reading the full function and its callers. A CLI request may cross into `ths-server` over HTTP, so inspect both ends of a changed command.

## Command surface

Names only; the README command table and `book/cli.md` are canonical for flags and semantics — verify before asserting behavior.

- Bare `ths` starts the default environment and opens the dashboard. Lifecycle: `start` (`--no-open`, `--port-offset`), `wait`, `status`, `endpoints`, `open`, `list`, `stop`, `reset --force`, `run -- <cmd>`.
- Wallet: `wallet balances`, `wallet faucet`, `wallet send`, `wallet activity`, `wallet shield`, `wallet unshield`; `faucet <ADDRESS>` funds an external address. `wallet send`/`wallet faucet`/`faucet` persist an idempotency key — repeating the command checks the pending payment instead of duplicating it.
- Operations: `mine <N>`, `logs {app,zakura,lightwalletd}` (`-f`, `--tail`, `--head`), `pull`, `doctor`, `update`, `uninstall`.
- Globals: `--name <instance>` for isolated environments, `--json` where supported. `cargo run -p thus-spoke-zakura -- <args>` invokes the source build.

## Instance lifecycle

Trace production `Runtime::start` through `own_start` and `start_owned` in `runtime/startup.rs`: claim startup ownership, verify initial cleanup, allocate the stack, wait for readiness, run until shutdown, and clean up the selected instance. `start_with` and `start_with_policy` are test adapters. For any change in this path, walk normal shutdown, Ctrl+C, failure before the first resource, failure after each resource, readiness failure, and browser-open failure.

`CleanupOnDrop` starts inactive and becomes armed only after initial cleanup is verified. An initial cleanup failure must not retry deletion on Drop; `initial_cleanup_failure_does_not_retry_on_drop` covers this boundary. The fake `StartHost` tests verify call order and selected instance names, while actual resource ownership is decided in the Docker operations.

The required invariant is ownership: a name collision is not proof that a preexisting Docker resource belongs to this instance. `runtime/instance.rs::prefix` supplies the `ths-<name>` prefix; inspect `runtime/resources.rs` for container, volume, and network suffixes. `owned_resource` and `inspected_resource_identity` in `resources.rs` reject missing or foreign `com.zakura.ths.instance` labels and ambiguous names. Production deletion runs through `runtime/cleanup.rs::verified_cleanup` and `cleanup_core`, with recorded identity and absence verification in `cleanup.rs` and journal state in `recovery.rs`. `deletion.rs` monitors external deletion of the allocated app container. Preserve recorded identities so cleanup cannot adopt a same-name replacement. `delete_instance_resources_with_mode` is a test adapter. Check containers, network, volumes, helpers, and metadata independently; report uncertain or failed cleanup and retain recovery evidence.

Host-published ports stay on `127.0.0.1`. Container-internal services may listen on `0.0.0.0`. Keep the runtime Regtest-only and verify the selected image in `runtime/images.rs::ZAKURA_IMAGE` (currently `zakuracore/zakura:1.6.0`). Unit tests live in `crates/ths-cli/tests/unit/runtime/tests/` and `lifecycle_tests/`, with Docker lifecycle cases in `docker_lifecycle_tests.rs`. The fake allocator creates no Docker resources, so those tests do not prove safe cleanup after partial real allocation or a name collision.

### Status and endpoint diagnosis

In `runtime/instance.rs`, `Runtime::endpoints` reads persisted `instance.json`; it does not prove a service is currently listening. `Runtime::status` reads persisted metadata first and falls back to endpoint inspection. Its `container_running` error propagates. A status response containing a dashboard URL can still coexist with a stopped container; check its `running` value and probe readiness separately.

If `ths status --json` shows a URL that does not respond, compare the live app container and host-published ports with `instance.json`; then separate a stopped container from an inspection error. Check readiness at the endpoint before claiming the stack is healthy.

## Source versus running artifact

`ths` uses images, not edited source files. After server or web changes, `cargo run -p thus-spoke-zakura -- build --dev` builds local images for the next launch. Start a new named instance from the rebuilt images; a running container still has its existing image. Preserve the old instance's failure evidence and identify the image and instance actually exercised before claiming a live result. `cargo run -p thus-spoke-zakura -- <args>` invokes the source launcher; the package name is not `ths`.

`THS_DEV_API=<dashboard-url> npm run dev --prefix web` serves the edited frontend through Vite and proxies `/api` to the existing instance (`web/vite.config.ts`). Obtain that URL from `ths endpoints`. This frontend-only mode does not update `ths-server`; edited server code still needs the image rebuild and new-instance workflow above.

For new or changed flags, update the command table in `README.md`. Run Rust checks after `crates/` edits and `tests/install.sh` after `install.sh` edits. Image names, tags, dependencies, workflows, and updater behavior have release impact under `AGENTS.md`; read `RELEASING.md` and use `ths-release` when touching them.

## Review examples

- **New `ths` command:** verify parsing, JSON/text output where supported, errors, server API contract, README table, and an end-to-end invocation against the source-built artifact if the behavior needs Docker.
- **Startup fix:** prove that the failing checkpoint is reachable and only owned resources are removed on each exit; a happy-path start test alone is insufficient.
- **Image change:** state which exact tags are selected by `build`, `pull`, and `start`, and how the change affects existing released launchers.

## Worked task: a foreign resource has our instance name

**Input:** An unrelated Docker daemon already contains a container named `ths-alpha-app`, or a volume such as `ths-alpha-wallet`. The user runs `ths --name alpha start`. `start_owned` calls deletion before allocation, and `owned_resource` must refuse the foreign resource because its `com.zakura.ths.instance` label does not name `alpha`. Trace `instance.rs::prefix`, `resources.rs::ensure_*`, and `cleanup.rs::cleanup_core` under `crates/ths-cli/src/runtime/`. Use this task when changing anything on the reuse or deletion path.

1. In an isolated disposable Docker environment, create one deliberately foreign resource with the colliding name and record its Docker ID, labels, and data. Use a unique test name; never run this collision test against a shared daemon.
2. Exercise the ownership check at the shared reuse/deletion boundary. An unowned name must cause a clear error before `start`, `stop`, `reset`, or partial-start cleanup mutates it. A resource with matching ownership metadata may follow the existing instance lifecycle. A network created by THS before thus-spoke-zakura#133 has no label, so it is refused too; say so in the change if users may still have one.
3. Recheck the foreign resource by **ID and data**, not name alone. Assert no new app allocation happened, its metadata directory was not removed, and a normally owned instance still cleans up on shutdown and interruption.

`RecordingHost` lifecycle tests only observe `delete:<name>` calls. Ownership is covered through the `DockerResourceCommands` seam with `RecordingDocker`: `foreign_volume_collision_preserves_all_resources`, `foreign_container_collision_is_not_deleted`, `unlabeled_network_collision_preserves_data_and_metadata`, `partial_startup_cleanup_removes_only_owned_resources`, and `owned_resources_still_clean_up`. Extend those for a new path, and still run step 3 against a disposable daemon before claiming real Docker behavior.

**Fast navigation and checks:**

```console
rg -n 'fn (start|start_owned|owned_resource|inspected_resource_identity|verified_cleanup|cleanup_core|ensure_network_with|ensure_volume_with|ensure_app)' crates/ths-cli/src/runtime
rg -n 'foreign_volume_collision|foreign_container_collision|unlabeled_network_collision|partial_startup_cleanup|owned_resources_still|initial_cleanup_failure' crates/ths-cli/tests/unit/runtime
cargo test -p thus-spoke-zakura
cargo fmt --all -- --check
```

The searches locate production entry points and nearby regression tests; follow their callers and helpers to find every affected reuse or removal branch. The Cargo test is a fast local gate; run the full `AGENTS.md` Rust checks after changing `crates/` and use a disposable Docker daemon for the collision oracle.
