# Changelog

All notable changes to Joidy are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Release and versioning process (`RELEASE.md`, `CHANGELOG.md`, `release.yml`).

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] - 2026-07-30

### Added

- Initial project scaffolding: FastAPI backend, SvelteKit frontend, AI service, worker, Docker Compose setup.
- Note CRUD with Markdown, WikiLink parsing, tags, and AI embeddings.
- Gamification engine: XP, streaks, plant growth stages.
- Goals with temporal types and rollover/snowball failure modes.
- Skill tree auto-generation from tag usage.
- Tag co-occurrence knowledge graph.
- Obsidian vault sync and bidirectional import.
- GitHub OAuth device flow integration.
- Image and file attachments in notes.
- Responsive base layout and mobile streak actions.
- CI pipeline: API tests, frontend typecheck, Docker build smoke test.

[unreleased]: https://github.com/Axel-DaMage/joidy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Axel-DaMage/joidy/releases/tag/v0.1.0
