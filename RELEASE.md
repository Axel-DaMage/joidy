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
3. It auto-determines the next version (patch bump from latest stable tag), bumps all version strings (README badge, AUR `PKGBUILD`/`.SRCINFO`, `docs/*.md` metadata, `CHANGELOG.md` compare links), commits the bump, tags it, and creates the GitHub Release.
4. The `.github/workflows/publish.yml` triggers on `release: published` and builds Docker images, Homebrew formula, and AUR package.

### Manual (for minor/major releases or pre-releases)

1. Make sure `main` is green (CI passes).
2. Update `CHANGELOG.md`: move `[Unreleased]` body to a new `[X.Y.Z] - YYYY-MM-DD` section, add a fresh empty `[Unreleased]`.
3. Trigger the release workflow manually via `workflow_dispatch` with the desired version tag (e.g. `v0.3.0`, `v0.3.0-alpha.1`).
4. The workflow bumps version strings, commits, tags, and creates the release.
5. `publish.yml` handles Docker/Homebrew/AUR publishing automatically.

## Version string automation

The `release.yml` workflow automatically updates version strings in these files when a release is created:

| File | What gets updated |
|------|-------------------|
| `README.md` | Badge version (`JOIDY-vX.Y.Z`) |
| `aur/PKGBUILD` | `pkgver` and `source` URL |
| `aur/.SRCINFO` | `pkgver` and `source` URL |
| `docs/index.md` | Metadata `version` |
| `docs/api.md` | Metadata `version` |
| `docs/architecture.md` | Metadata `version` |
| `docs/troubleshooting.md` | `last_updated` and `version` |
| `CHANGELOG.md` | `[unreleased]` compare link |

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
