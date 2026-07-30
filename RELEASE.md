# Release & Versioning Process

Joidy follows [Semantic Versioning 2.0.0](https://semver.org/lang/es/) (`MAJOR.MINOR.PATCH`).

## Version scheme

| Level | When to bump | Example |
|-------|--------------|---------|
| **MAJOR** | Breaking changes in API, storage format, or configuration | `v2.0.0` |
| **MINOR** | New features, integrations, or non-breaking UI changes | `v1.3.0` |
| **PATCH** | Bug fixes, docs, security patches, refactorings | `v1.3.1` |

Pre-release versions use a suffix: `v1.4.0-alpha.1`, `v1.4.0-beta.2`, `v1.4.0-rc.1`.

## Branch strategy

- `main` — production-ready code.
- `development` — integration branch for the next release.
- `feat/*`, `fix/*`, `docs/*`, `refactor/*` — short-lived branches merged via PR.

Release branches are not required for this project; tags on `main` are enough.

## Release steps

1. Make sure `main` is green (CI passes).
2. Update `CHANGELOG.md` with the new version.
3. Create and push a signed tag:
   ```bash
   git checkout main
   git pull
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. The `.github/workflows/release.yml` workflow will create the GitHub Release automatically.
5. The existing `.github/workflows/publish.yml` triggers on `release: published` and builds Docker images, Homebrew formula, and AUR package.

## Changelog format

`CHANGELOG.md` follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format with these sections:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

## Release automation

- `release.yml` — creates a GitHub Release and generates notes from merged PRs.
- `publish.yml` — publishes Docker images, Homebrew tap, and AUR package after a release is published.
