---
name: ths-release
description: Use when preparing, validating, or changing Thus Spoke Zakura versioned launcher builds, installer or updater behavior, runtime image tags, release workflows, or publication artifacts.
---

# THS release

Read current `AGENTS.md`, `RELEASING.md`, and the relevant contribution instructions before acting. Identify the exact source commit, Cargo version, tag, launcher artifacts, checksums, and app and lightwalletd image digests. The launcher uses exact versioned image tags; a source build and a published binary can have different update behavior.

For version or image compatibility, load [the artifact map](references/release-path.md#artifacts-that-must-agree). For a release run, load [candidate to publication](references/release-path.md#candidate-to-publication); for pull failures, load [the worked diagnosis](references/release-path.md#worked-task-candidate-passes-but-released-images-cannot-be-pulled). For installer/updater changes, load [replacement boundaries](references/release-path.md#installer-replacement-boundary). Select local checks with [checks by edit](references/release-path.md#checks-by-edit).

Check the compatibility of launcher, app image, lightwalletd image, and pinned Zakura image as one release set. Verify the `release-distribution` feature path separately from ordinary source builds. For installer or updater edits, run the repository's Rust and install checks. For workflow edits, explain the release impact and inspect the candidate result before any public publication.

The documented release candidate is a dry run. Creating tags, pushing manifests, changing package visibility, or publishing a release are external mutations; follow the user's authorization for those actions. Do not replace a released tag to correct an artifact; follow the current release procedure for a new version.

## Review examples

- A launcher binary from one version with images from another is a compatibility mismatch even if each artifact builds separately.
- A green candidate job proves the build matrix completed; it does not prove a later tagged draft or publish job passed.
- An installer or updater change needs the exact archive, checksum, platform, and self-replacement behavior of the artifact being delivered.
