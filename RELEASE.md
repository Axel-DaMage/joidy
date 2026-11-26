# Release & Versioning Process

Joidy follows [Semantic Versioning 2.0.0](https://semver.org/lang/es/) (`MAJOR.MINOR.PATCH`).

## Version scheme

| Level | When to bump | Example |
|-------|--------------|---------|
| **MAJOR** | Breaking changes in API, storage format, or configuration | `v1.0.0` |
| **MINOR** | New features, integrations, or non-breaking UI changes | `v0.3.0` |
| **PATCH** | Bug fixes, docs, security patches, refactorings | `v0.2.1` |

Pre-release versions use a suffix: `v0.3.0-alpha.1`, `v0.3.0-beta.2`, `v0.3.0-rc.1`.

## Branch strategy

- `main` — production-ready code.
- `development` — integration branch for the next release.
- `feat/*`, `fix/*`, `docs/*`, `refactor/*` — short-lived branches merged via PR.

Release branches are not required for this project; tags on `main` are enough.

## Release steps

### Automated (default)

1. Merge `development` into `main` via PR.
2. The `.github/workflows/release.yml` workflow triggers automatically on push to `main`.
3. It auto-determines the next version (patch bump from latest stable tag), runs `scripts/release_bump.sh` to regenerate every versioned file from the canonical `VERSION` file, commits the bump, tags it, and creates the GitHub Release.
4. The `.github/workflows/publish.yml` triggers on `release: published` and builds Docker images, Homebrew formula, and AUR package.

### Manual (for minor/major releases or pre-releases)

1. Make sure `main` is green (CI passes).
2. Update `CHANGELOG.md`: move `[Unreleased]` body to a new `[X.Y.Z] - YYYY-MM-DD` section, add a fresh empty `[Unreleased]`.
3. Trigger the release workflow manually via `workflow_dispatch` with the desired version tag (e.g. `v0.3.0`, `v0.3.0-alpha.1`).
4. The workflow bumps version strings via `scripts/release_bump.sh`, commits, tags, and creates the release.
5. `publish.yml` handles Docker/Homebrew/AUR publishing automatically.

## Version string automation

Since #1258 the project version has a **single canonical source**: the root
`VERSION` file, holding a bare semver string without the leading `v`
(e.g. `1.1.0-beta.8`; the `v` prefix exists only on git tags). At release
time `.github/workflows/release.yml` calls `scripts/release_bump.sh`, which
rewrites every dependent from that one source and then verifies they all
agree — failing loudly before anything is committed. The old inline chain of
per-file `sed` edits (which shipped wrong versions three times: #753, #754,
#1163, #1195) is gone.

| File | What gets updated |
|------|-------------------|
| `VERSION` | Canonical version (bare semver, no `v`) |
| `pyproject.toml` | `[project] version` |
| `frontend/package.json` | `"version"` field |
| `frontend/package-lock.json` | the two root package version fields only — dependency versions are never touched |
| `aur/PKGBUILD` | `pkgver` (`-` → `_` for pre-releases) and `sha256sums` reset to `SKIP` |
| `aur/.SRCINFO` | **Regenerated** via `makepkg --printsrcinfo` — never hand-edited |
| `docker-compose.release.yml` | pinned `d4mag3/joidy-*` image tags |
| `README.md` | `JOIDY-vX.Y.Z` badge + pinned installer URLs |
| `INSTALL.md`, `scripts/install.sh`, `scripts/install.ps1` | pinned installer URLs (template refs like `${TAG}` are preserved) |
| `docs/index.md`, `docs/api.md`, `docs/architecture.md`, `docs/troubleshooting.md` | metadata `version` (+ `last_updated` in troubleshooting) |
| `CHANGELOG.md` | `[unreleased]` compare link |

`sha256sums` stay `SKIP` in the tagged commit because the release tarball
does not exist until the tag is pushed; the workflow's "Inject release
checksums" step (and `aur-publish.yml` at publish time) fills in the real
sums afterwards (#1296, #1394).

### `scripts/release_bump.sh`

```bash
scripts/release_bump.sh <version>            # bump VERSION + dependents, then verify
scripts/release_bump.sh --check <version>    # verify only — fails if any file disagrees
scripts/release_bump.sh --dry-run <version>  # exercise the bump on a scratch copy
```

`<version>` accepts an optional leading `v`. `.SRCINFO` generation prefers a
local non-root `makepkg` and falls back to a throwaway `archlinux:latest`
container (the same approach `dist-smoke.yml` uses for its AUR job).
`dist-smoke.yml` exercises the script on every PR that touches `scripts/`,
`aur/` or the release workflows, `release.yml` runs `--check` as a
post-bump assertion, and `ci.yml`'s `version-consistency` job runs
`release_bump.sh --check "$(cat VERSION)"` on every push/PR so drift fails
fast on regular commits instead of on release night (#1554). The
independently-versioned `joidy-cli` package (`cli/pyproject.toml`,
`joidy_cli.__version__`) is intentionally not part of the check — the
release flow does not own it.

For minor/major releases, `CHANGELOG.md` section management (moving `[Unreleased]` to a versioned section) should still be done manually before triggering the release.

## Changelog format

`CHANGELOG.md` follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format with these sections:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

## Release automation

- `release.yml` — auto-determines version, bumps version strings, creates tag and GitHub Release with generated notes.
- `publish.yml` — publishes Docker images, Homebrew tap, and AUR package after a release is published.
