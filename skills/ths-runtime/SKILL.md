---
name: ths-runtime
description: Use when changing the Thus Spoke Zakura ths CLI, named Docker instances, service startup or cleanup, images, installation, or local endpoints.
---

# THS runtime

Read the current repository `AGENTS.md`. Trace command parsing in `crates/ths-cli/src/args.rs` and dispatch in `commands.rs` through the relevant `runtime/` submodule or `client.rs` to Docker resources or the server API.

Load [the source map](references/launcher-runtime.md#where-behavior-lives) when locating an unfamiliar owner, [command surface](references/launcher-runtime.md#command-surface) for CLI changes, and [instance lifecycle](references/launcher-runtime.md#instance-lifecycle) for startup or cleanup. For a same-name resource collision, load [the worked ownership task](references/launcher-runtime.md#worked-task-a-foreign-resource-has-our-instance-name). For stale behavior after source edits, load [artifact diagnosis](references/launcher-runtime.md#source-versus-running-artifact).

Preserve Regtest-only behavior, loopback host ports, and instance-scoped cleanup during normal exit, interruption, and partial startup failure. Check that a source change reaches the built image before using live behavior as evidence. For command changes, update the README command table and run the Rust checks; run `tests/install.sh` when the installer changes.

## Core workflow

1. Identify the parsed command, selected instance, exact images, and Docker resources it owns.
2. Trace startup, normal shutdown, interruption, and each reachable partial failure.
3. Verify resource ownership before reuse or deletion and check loopback host bindings.
4. Run the nearest lifecycle or CLI test, then the repository's required checks for changed files.

## Review examples

- A same-name Docker resource may belong to someone else; inspect the current deletion path before trusting a cleanup test that only records calls.
- A server source edit requires a new app image for `ths start`, while the live `activity_recovery` Cargo target runs a source-built server process.
- A command or flag change reaches README's command table, parsed CLI behavior, the affected API call, and the resulting instance state.
