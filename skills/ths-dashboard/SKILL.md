---
name: ths-dashboard
description: Use when changing Thus Spoke Zakura's React dashboard, wallet or explorer views, web API schemas, query hooks, mutations, or server-event updates.
---

# THS dashboard

Read the current repository `AGENTS.md`. Follow data from `ths-server` through `web/src/lib/api` and query hooks into the affected view.

Load only the reference section needed for the task:

- For an unfamiliar endpoint or money representation, use the [source map](references/dashboard.md#current-source-map).
- For stale balances, use [balance diagnosis](references/dashboard.md#stale-balance-diagnosis); for retry identity or missed updates, use [mutations and events](references/dashboard.md#mutation-and-event-behavior).
- For a stale explorer detail, use the [worked chain-event task](references/dashboard.md#worked-task-explorer-detail-is-stale-after-a-chain-change). For form states and web checks, use [UI verification](references/dashboard.md#ui-and-verification).

Keep the server wallet snapshot authoritative for balances. Reuse Zod schemas, query keys, mutation invalidation, and SSE handling rather than introducing another account-state store. Check loading, error, and stale-result behavior when the server syncs or chain state changes. Use Node 24 and run the repository's web checks after changing `web/`. Rebuild the app image before claiming a live dashboard reflects source edits.

## Core workflow

1. Trace the response from Rust endpoint through Zod schema, query key, hook, and affected component.
2. For a mutation, check both successful invalidation and later SSE-driven refresh.
3. Test valid, pending, error, and stale-result states at the real query owner.
4. Run the web checks and verify the built frontend artifact if the claim is about a running container.

## Review examples

- A stale balance after mining starts at `/api/v1/accounts`: compare its snapshot with `useAccounts()` (`queryKeys.accounts`, `api.accounts` in `web/src/hooks/queries.ts`) before changing UI state. Server edits require `cargo run -p thus-spoke-zakura -- build --dev` and a new instance; `THS_DEV_API` with Vite only changes the frontend's API target.
- A money change checks wallet `bigint` fields and explorer `number` fields separately; the current schemas do not give both paths the same arithmetic representation.
- A new server field updates the Zod schema, request helper, affected query or mutation, view, and boundary test in that order.
