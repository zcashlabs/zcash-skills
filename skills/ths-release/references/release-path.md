# Release path and compatibility

`RELEASING.md` and the current workflows are the procedural authority; re-read them at the revision being released. This map highlights the relationships most likely to be missed when changing or preparing a release.

## Artifacts that must agree

| Artifact | Current owner or check |
| --- | --- |
| Cargo version and launcher binary | `[workspace.package].version`, `crates/ths-cli`, `release-distribution` feature |
| App and lightwalletd images | `Dockerfile`, `docker/lightwalletd.Dockerfile`, `crates/ths-cli/src/runtime/images.rs` image selectors |
| Pinned Zakura node image | `crates/ths-cli/src/runtime/images.rs` (`ZAKURA_IMAGE` constant) |
| Installer and updater | `install.sh`, `crates/ths-cli/src/updater.rs`, `tests/install.sh` |
| Candidate and published workflows | `.github/workflows/release.yml`, `.github/workflows/publish.yml` |
| Human release notes | `CHANGELOG.md`, `RELEASING.md` |

The launcher selects exact app and lightwalletd image tags from its compiled version; `start` does not resolve `latest`. A source build can use local images with those exact tags. Official launcher artifacts enable `release-distribution` for self-replacement (`updater.rs` refuses self-replacement without it); ordinary Cargo builds do not. State the compatibility impact of any tag, image, installer, updater, dependency, or workflow change.

## Candidate to publication

1. Confirm the intended version and changelog are in the reviewed final commit. The workflow requires a `vX.Y.Z` tag matching the Cargo version.
2. Run the `Release candidate` workflow as a dry run before tagging. It tests and builds targets without publishing images or a release (its image jobs run with `push: false` unless the event is a tag push).
3. For a tagged build, inspect the four launcher archives and installer in `SHA256SUMS`, the draft release notes, image digests, both `linux/amd64` and `linux/arm64` manifest entries, and any attestation needed for the claim.
4. Publication triggers `publish.yml`, which promotes immutable versioned manifests to `latest` and runs a public installer smoke test. Do not treat candidate success as proof that this later job has passed.

The current release guide forbids deleting and recreating a released tag; corrections receive a new patch version. Repository visibility, package visibility, and tag protection are manual controls described in `RELEASING.md`. A skill does not authorize tagging, pushing images, changing those settings, or publishing; use the user's actual instruction and the host's approval boundary.

### Candidate-green, pull-fails diagnosis

The manual `workflow_dispatch` candidate builds targets with image `push: false`. It exercises compilation and packaging, while a tagged run uploads architecture images, resolves their digests into versioned multi-platform manifests (`image-manifests` job), attests them, and creates the draft release. Publishing that draft triggers `publish.yml`, which promotes the immutable versioned manifests to `latest` and runs an anonymous installer smoke test. A candidate pass cannot prove that a released `ths pull` can fetch images.

If a released launcher cannot pull, record its compiled Cargo version and the exact app/lightwalletd tags it selects. Then inspect the tagged workflow's two platform digests, versioned manifests, GHCR visibility, and the publish job's public smoke result. Check the node image separately. `updater.rs` refuses self-replacement without the `release-distribution` feature, while release launcher jobs build with it; a source-built binary is not evidence for the updater behavior of the published archive.

### Installer replacement boundary

`install.sh` stages an archive under the destination, verifies `SHA256SUMS`, checks that the archive contains the expected single `ths` member and executable version, optionally runs `ths pull`, then replaces the installed binary with `mv -f`. If the optional image pull fails, the old binary stays installed; any images already downloaded may remain in Docker's cache. Use `tests/install.sh` for checksum, bad archive, and failed-pull behavior. Report the installed binary version and selected image tags after an update instead of inferring success from a downloaded archive.

## Checks by edit

- `crates/` or runtime tag changes: the Rust checks in `AGENTS.md`, including the `release-distribution` test; verify exact selected tags.
- `install.sh`: `tests/install.sh`, including upgrade/rollback or checksum behavior affected by the edit.
- Workflow or Dockerfile changes: inspect the candidate build on both architectures and the resulting manifests before making a public compatibility claim.
- Release preparation: record exact commit, tag, artifact hashes/digests, workflow run, and any missing gate. A draft release is still a draft.

## Worked task: candidate passes but released images cannot be pulled

**Input:** The manually dispatched `Release candidate` workflow is green, but a versioned launcher reports a missing app or lightwalletd image. The candidate's image jobs use `push: false`; only a tag-triggered run publishes architecture digests and assembles the versioned manifests. Diagnose the tagged artifact path before changing Dockerfiles or installer logic.

1. Read the launcher's compiled version (`ths --version`) and `crates/ths-cli/src/runtime/images.rs`'s app/lightwalletd image selectors. The expected tags are the exact Cargo version, not `latest`.
2. Inspect the tag-triggered `release.yml` run, especially both native architecture image jobs and `image-manifests`. The versioned app and lightwalletd manifests must each list `linux/amd64` and `linux/arm64`; record their digest identities and GHCR visibility.
3. Download the draft's `SHA256SUMS`, four `ths-<target>.tar.gz` archives, and `install.sh`. Verify hashes in one directory and inspect that each archive contains only `ths`. A candidate artifact is not interchangeable with the tagged draft.
4. After publication, inspect `publish.yml`'s promotion and anonymous installer smoke. A published `latest` tag is a convenience alias; the launcher still selects the exact version.

Read-only inspection commands for the relevant environment:

```console
gh run list --workflow release.yml
gh run view <tagged-run-id> --json event,headSha,conclusion,jobs
gh release download <tag> --pattern 'SHA256SUMS' --pattern 'ths-*.tar.gz' --pattern 'install.sh' --dir <empty-download-dir>
docker buildx imagetools inspect ghcr.io/zcashlabs/thus-spoke-zakura-app:<version>
docker buildx imagetools inspect ghcr.io/zcashlabs/thus-spoke-zakura-lightwalletd:<version>
sha256sum -c SHA256SUMS
```

Use the actual tag run ID and version; run `sha256sum` in the directory containing all listed artifacts. On macOS use `shasum -a 256 -c SHA256SUMS`. If the manifest is absent, a candidate pass offers no contrary evidence. If the manifest exists but anonymous pull fails, check GHCR package visibility and the public smoke result. Do not publish or retag merely to run this diagnosis.
