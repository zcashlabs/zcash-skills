# Launcher and runtimes

## Where behavior lives

| Concern | Current owner |
| --- | --- |
| Command parsing and dispatch | `crates/ths-cli/src/args.rs`, `args/amount.rs`, `commands.rs`, `commands/wallet.rs`; `main.rs` calls `lib.rs::run_from` (`thus-spoke-zakura` package, `ths` binary). `commands.rs` sends `start` and `run` to `Runtime::native_start` unless `--docker` is set |
| Runtime module wiring, Docker `doctor`, NU7 default | `crates/ths-cli/src/runtime.rs` (`DEFAULT_NU7_ACTIVATION_HEIGHT`, `MiningConfig`) |
| Native startup, readiness, shutdown, cleanup, logs, status (default) | `crates/ths-cli/src/runtime/native/mod.rs` (`native_start`, `native_validate`, `native_environment`, `native_cleanup`, `native_logs`, `native_doctor`) |
| Native child processes and listener ownership | `crates/ths-cli/src/runtime/native/process.rs` (`Processes`, `owns_listener`, `prerequisites`) |
| Native bundle selection and validation (`--runtime-dir`, `THS_RUNTIME_DIR`) | `crates/ths-cli/src/runtime/native/bundle.rs` (`resolve`, `validate`); component pins in `native/runtime.json`; bundle build in `tools/build_native.sh` |
| Docker startup, readiness, shutdown, child commands (`--docker`) | `crates/ths-cli/src/runtime/startup.rs`, `readiness.rs`, `runner.rs`; helper deadlines and cancellation in `crates/ths-cli/src/lifecycle.rs` |
| Docker creation, ownership, verified cleanup, recovery journal | `crates/ths-cli/src/runtime/resources.rs`, `docker.rs`, `cleanup.rs`, `recovery.rs` |
| Monitoring external deletion of an allocated app container | `crates/ths-cli/src/runtime/deletion.rs` |
| Backend-aware `stop`, `reset`, `logs`, `rpc`, activity watch | `crates/ths-cli/src/runtime/cleanup.rs`, `logs.rs`, `rpc.rs`, `watch.rs` (each branches on `Backend::Native`) |
| Instance names, backend, persisted endpoints, host ports, status, ownership lock | `crates/ths-cli/src/runtime/instance.rs` (`Backend`, `Instance`, `host_ports`, `endpoints_for`, `loopback_publish`, `verified_cleanup_with`) |
| Image constants, selectors, build and pull | `crates/ths-cli/src/runtime/images.rs` |
| Wallet/API client calls and durable retry keys | `crates/ths-cli/src/client.rs`, `intents.rs` |
| Runtime unit and lifecycle tests | `crates/ths-cli/tests/unit/runtime/`; follow the `#[path]` declarations from `crates/ths-cli/src/runtime.rs`. Native: `crates/ths-cli/tests/native_runtime.rs` with `tests/fixtures/native_service.rs`, and the `#[cfg(test)]` module in `native/bundle.rs` |
| Self-update, native runtime install, uninstall | `crates/ths-cli/src/updater.rs` (`install_native_runtime`), `install.sh` (`THS_INSTALL_RUNTIME`) |
| Source-built app and lightwalletd images | `Dockerfile`, `docker/lightwalletd.Dockerfile` |

Map checked against THS tag `v0.5.0` (`530a2434765529d6ecf3535d1c43f3c02ed5db5f`) on 2026-11-26. Paths without a crate prefix in a row are siblings of that row's first file. Resolve the actual checked-out symbols before editing; this map is navigation, not a substitute for reading the full function and its callers. A CLI request may cross into `ths-server` over HTTP, so inspect both ends of a changed command.

## Command surface

Names only; `book/cli.md` is canonical for flags and semantics. Verify there before asserting behavior.

- Bare `ths` starts a fresh native environment and opens the dashboard. Lifecycle: `start` (`--docker`, `--runtime-dir`, `--timeout`, `--no-open`, `--port-offset`, `--block-time`, `--mine-on-mempool`, `--no-auto-mine`, `--nu7-height`), `wait`, `status`, `endpoints` (`--env`), `open`, `list`, `stop`, `reset --force`, `run [--docker] [--runtime-dir] -- <cmd>`.
- `--native` was removed when native became the default; `commands.rs` rejects it with a migration message. `--runtime-dir` and `start --timeout` conflict with `--docker`.
- Wallet: `wallet balances`, `wallet faucet`, `wallet send`, `wallet quote`, `wallet activity`, `wallet shield`, `wallet unshield`; `faucet <ADDRESS>` funds an external address. `wallet send`/`wallet faucet`/`faucet` persist an idempotency key; repeating the command checks the pending payment instead of duplicating it.
- Operations: `mine <N>`, `reorg --depth <N>` (`--keep-txs`), `rollback --depth <N>`, `rpc <METHOD>`, `tx <TXID>`, `block [ID]`, `logs [service]` (`-f`, `--tail`, `--head`), `build` (`--dev`), `pull`, `doctor` (`--docker`, `--runtime-dir`), `update`, `uninstall`, `completions`.
- Globals: `--name <instance>` for isolated environments, `--json` where supported. `cargo run -p thus-spoke-zakura -- <args>` invokes the source build.

## Instance lifecycle

**Native (default).** `Runtime::native_start` in `runtime/native/mod.rs` serves both `start` and `run`. It resolves the bundle, checks `process::prerequisites`, claims startup ownership through `own_start`, creates private instance state, and writes `native.json` before reserving ports or any other fallible initialization. It reserves the four loopback ports, writes `instance.json` with `backend: native`, runs `ths-server init` (which receives `--nu7-height`), then starts `zakurad`, `lightwalletd`, and `ths-server serve` as child processes. Before contacting each service it waits for the child to own its listener (`wait_listener`, `owns_listener`), checks the Regtest genesis, and checks the server's instance identity and settlement. `start` uses the fixed default ports (or those `--port-offset` shifts) and fails if one is taken; `run` takes free ones. On exit `Processes::stop_all` stops every child. State is deleted after an interrupt or success; after a failure, `native.json` is marked `cleaned` and logs stay under the instance's `logs/`. Later cleanup goes through `cleanup.rs::verified_cleanup`, which hands native instances to `native_cleanup`. That refuses to signal persisted PIDs or delete state unless the launcher recorded a verified cleanup.

**Docker (`--docker`).** Trace production `Runtime::start` through `own_start` and `start_owned` in `runtime/startup.rs` (and `Runtime::run` in `runner.rs` for `run --docker`): claim startup ownership, verify initial cleanup, pull any missing images (`images.rs::pull_missing_images`, release builds only), allocate the stack, wait for readiness, run until shutdown, and clean up the selected instance. `start_with` and `start_with_policy` are test adapters. For any change in this path, walk normal shutdown, Ctrl+C, failure before the first resource, failure after each resource, readiness failure, and browser-open failure.

`CleanupOnDrop` starts inactive and becomes armed only after initial cleanup is verified. An initial cleanup failure must not retry deletion on Drop; `initial_cleanup_failure_does_not_retry_on_drop` covers this boundary. The fake `StartHost` tests verify call order and selected instance names, while actual resource ownership is decided in the Docker operations.

The required Docker invariant is ownership: a name collision is not proof that a preexisting Docker resource belongs to this instance. `runtime/instance.rs::prefix` supplies the `ths-<name>` prefix; inspect `runtime/resources.rs` for container, volume, and network suffixes. `owned_resource` and `inspected_resource_identity` in `resources.rs` reject missing or foreign `com.zakura.ths.instance` labels (`INSTANCE_LABEL`) and ambiguous names. Production deletion runs through `runtime/cleanup.rs::verified_cleanup` and `cleanup_core`, with recorded identity and absence verification in `cleanup.rs` and journal state in `recovery.rs`. `deletion.rs` monitors external deletion of the allocated app container. Preserve recorded identities so cleanup cannot adopt a same-name replacement. `delete_instance_resources_with_mode` is a test adapter. Check containers, network, volumes, helpers, and metadata independently; report uncertain or failed cleanup and retain recovery evidence.

Host ports stay on `127.0.0.1` in both runtimes: native services bind loopback directly (`TcpListener::bind(("127.0.0.1", port))`, `THS_LISTEN`, lightwalletd `--grpc-bind-addr`), and Docker publishes through `instance.rs::loopback_publish`. Container-internal services may listen on `0.0.0.0`. Default host ports come from `instance.rs::host_ports`: dashboard `32805`, RPC `18232`, P2P `18233`, lightwalletd `9067`, with `--port-offset` a multiple of 10. Keep the runtime Regtest-only.

Both runtimes run Zakura 1.7.0. Docker uses `runtime/images.rs::ZAKURA_IMAGE` (`zakuracore/zakura:1.7.0`); the native bundle builds `zakurad` from `zakura_commit` in `native/runtime.json` (`c572f8faf88e58dcaefd80ec8e4ed05f2d8643b6`, the Zakura `v1.7.0` tag commit), and `bundle.rs::validate` rejects a bundle whose manifest pins differ. Docker unit tests live in `crates/ths-cli/tests/unit/runtime/tests/` and `lifecycle_tests/`, with Docker lifecycle cases in `docker_lifecycle_tests.rs`; the fake allocator creates no Docker resources, so those tests do not prove safe cleanup after partial real allocation or a name collision. Native lifecycle regressions in `tests/native_runtime.rs` run compiled disposable service fixtures without Docker or a real node; `tests/native_smoke.mjs` exercises real services.

### Status and endpoint diagnosis

In `runtime/instance.rs`, `Runtime::endpoints` reads persisted `instance.json`; it does not prove a service is currently listening. `Runtime::status` reads `instance.json` and branches on its backend. Native status comes from `native_environment`, which reports `running` only when `native_validate` passes (an active ready owner, each recorded PID owning its loopback listener, and the server's identity), `degraded` when the owner is active but validation fails, and `stopped` otherwise. Docker status comes from `inspect_environment`; Docker errors propagate instead of reading as a stopped environment (`commands_report_docker_errors_instead_of_a_stopped_environment`). A status response containing a dashboard URL can still coexist with a stopped service; check its state and probe readiness separately.

If `ths status --json` shows a URL that does not respond, compare `instance.json` with what is live: for native, the recorded PIDs in `native.json` and their listeners; for Docker, the app container and its host-published ports. Separate a stopped service from an inspection error, and check readiness at the endpoint before claiming the stack is healthy.

## Source versus running artifact

`ths` runs prebuilt Docker images or a native bundle, not edited source files. After server or web changes, `cargo run -p thus-spoke-zakura -- build --dev` rebuilds the local Docker images only (`images.rs::build_project_images`); start a new named instance from them with `start --docker`, since a running container keeps its existing image. A source build never pulls published images, because an image with its version tag would not contain local changes. The native path needs a bundle instead: build one per `RELEASING.md` ("Native runtime contract", `tools/build_native.sh`) and pass it with `--runtime-dir` or `THS_RUNTIME_DIR`. Without one, a source build stops with an error naming both ways out; only a release launcher installs a missing bundle. Preserve the old instance's failure evidence and identify the image or bundle and instance actually exercised before claiming a live result. `cargo run -p thus-spoke-zakura -- <args>` invokes the source launcher; the package name is not `ths`.

`THS_DEV_API=<dashboard-url> npm run dev --prefix web` serves the edited frontend through Vite and proxies `/api` to the existing instance (`web/vite.config.ts`). Obtain that URL from `ths endpoints`. This frontend-only mode does not update `ths-server`; edited server code still needs the rebuild and new-instance workflow above.

For new or changed flags, update `book/cli.md`. Run Rust checks after `crates/` edits and `tests/install.sh` after `install.sh` edits. Image names, tags, native pins, dependencies, workflows, and updater behavior have release impact under `AGENTS.md`; read `RELEASING.md` and use `ths-release` when touching them.

## Review examples

- **New `ths` command:** verify parsing, JSON/text output where supported, errors, server API contract, `book/cli.md`, and both backends where the command branches on `Backend::Native`.
- **Startup fix:** name the runtime first. Prove that the failing checkpoint is reachable and, for Docker, that only owned resources are removed on each exit; for native, that every child stops and state is retained or deleted as `native_start` intends. A happy-path start test alone is insufficient.
- **Image or pin change:** state which exact tags `build`, `pull`, and `start --docker` select, which `native/runtime.json` commits the bundle must match, and how the change affects existing released launchers.

## Worked task: a foreign resource has our instance name

This task is Docker-only: the native runtime owns no Docker resources and refuses to reuse an existing instance directory.

**Input:** An unrelated Docker daemon already contains a container named `ths-alpha-app`, or a volume such as `ths-alpha-wallet`. The user runs `ths --name alpha start --docker`. `start_owned` calls deletion before allocation, and `owned_resource` must refuse the foreign resource because its `com.zakura.ths.instance` label does not name `alpha`. Trace `instance.rs::prefix`, `resources.rs::ensure_*`, and `cleanup.rs::cleanup_core` under `crates/ths-cli/src/runtime/`. Use this task when changing anything on the reuse or deletion path.

1. In an isolated disposable Docker environment, create one deliberately foreign resource with the colliding name and record its Docker ID, labels, and data. Use a unique test name; never run this collision test against a shared daemon.
2. Exercise the ownership check at the shared reuse/deletion boundary. An unowned name must cause a clear error before `start`, `stop`, `reset`, or partial-start cleanup mutates it. A resource with matching ownership metadata may follow the existing instance lifecycle. An unlabeled network is adopted only when every container on it is owned, and refused once a foreign container joins.
3. Recheck the foreign resource by **ID and data**, not name alone. Assert no new app allocation happened, its metadata directory was not removed, and a normally owned instance still cleans up on shutdown and interruption.

`RecordingHost` lifecycle tests only observe `delete:<name>` calls. Ownership is covered through the `DockerResourceCommands` seam with `RecordingDocker`: `foreign_volume_collision_preserves_all_resources`, `foreign_container_collision_is_not_deleted`, `unlabeled_network_collision_preserves_data_and_metadata`, `unlabeled_network_is_adopted_when_its_containers_are_owned`, `unlabeled_network_with_a_foreign_container_is_refused`, `new_networks_are_labeled_for_owned_cleanup`, and `partial_startup_cleanup_removes_only_owned_resources`. Extend those for a new path, and still run step 3 against a disposable daemon before claiming real Docker behavior.

**Fast navigation and checks:**

```console
rg -n 'fn (start|start_owned|owned_resource|inspected_resource_identity|verified_cleanup|cleanup_core|ensure_network_with|ensure_volume_with|ensure_app|native_start|native_cleanup)' crates/ths-cli/src/runtime
rg -n 'foreign_volume_collision|foreign_container_collision|unlabeled_network|new_networks_are_labeled|partial_startup_cleanup|initial_cleanup_failure' crates/ths-cli/tests/unit/runtime
cargo test -p thus-spoke-zakura
cargo test -p thus-spoke-zakura --test native_runtime
cargo fmt --all -- --check
```

The searches locate production entry points and nearby regression tests; follow their callers and helpers to find every affected reuse or removal branch. The Cargo tests are fast local gates; run the full `AGENTS.md` Rust checks after changing `crates/` and use a disposable Docker daemon for the collision oracle.

## Sources

Last verified: 2026-11-26 against THS `v0.5.0` (`530a243`).

- THS `AGENTS.md`, `CHANGELOG.md` (v0.5.0), `book/cli.md`, `book/development.md` ("Native runtime (no Docker)"), `RELEASING.md` ("Native runtime contract")
- THS `crates/ths-cli/src/runtime.rs` and its modules, `commands.rs`, `args.rs`, `runtime/images.rs`, `native/runtime.json`, `install.sh`, `Dockerfile`, `docker/lightwalletd.Dockerfile`
- Zakura tag `v1.7.0` compared with `c572f8faf88e58dcaefd80ec8e4ed05f2d8643b6`: identical
