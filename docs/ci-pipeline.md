<!--
SPDX-FileCopyrightText: 2025 D4MAG3_WIZ4RD and contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# CI Pipeline Policy

How `.github/workflows/ci.yml` is structured and why. Written for #1464 —
the November 2026 outage where no `development` CI run completed for ~2
weeks (~119+ commits unverified).

## What was actually wrong (#1464 post-mortem)

Two separate problems were conflated as "every run gets cancelled":

1. **Superseded push runs** — fixed earlier by #1336: `cancel-in-progress`
   is now `true` only for `pull_request` events. Push runs on
   `main`/`development` **queue** instead of cancelling each other.
   Caveat to know when reading `gh run list`: GitHub keeps at most **one
   pending run per concurrency group**, so during a merge storm each new
   push cancels the *previously queued* run — those show as `cancelled`
   with short durations. That is expected and desirable: the latest
   commit is what gets verified.

2. **The Playwright job timed out** — the real killer. `workers: 1` in
   `playwright.config.ts` under `CI` ran ~230 tests across 15 spec files
   **serially** on one runner. The suite outgrew the job's
   `timeout-minutes: 30`; every push run's e2e leg died at ~30m30s and
   the run recorded `cancelled`. All other jobs finished in ~2 minutes.

## Current shape

| Job | Purpose | Typical |
|-----|---------|---------|
| `api-lint` | compileall, ruff, mypy, baseline ratchet, alembic round-trip, pytest + coverage (85% floor), populated-.env re-run | ~2 min |
| `ai-service-test` | pytest + coverage (80% floor) | ~1 min |
| `frontend-check` | `npm run check`, eslint, production build, vitest | ~2 min |
| `cli-tests` | CLI unit tests | <1 min |
| `docker-build` | build 4 images, boot stack, API health | ~1.5 min |
| `e2e-plan` | decide e2e scope + shard count | ~15 s |
| `frontend-e2e` | Playwright, sharded matrix | ~5-10 min wall |
| `security` | bandit, pip-audit ×3, npm audit, trivy | ~1 min |
| `sbom` | source SBOM + license policy preview | <1 min |

`frontend-e2e` is the critical path; everything else is under ~2.5 min.

## e2e sharding policy

- **`e2e-plan`** computes the diff for the event and emits `run`,
  `specs`, `shards` (JSON matrix array).
- **Push to `main`/`development`**: always the **full suite** — post-merge
  verification stays complete — split across `SHARD_COUNT` (default 8)
  parallel legs via `npx playwright test --shard=n/M`. Each shard boots
  its **own** docker stack + Postgres, so tests remain serial per shard
  (`workers: 1`, matching the config's CI posture) and fully isolated.
- **Pull requests**: smoke + route-scoped specs on a **single** leg
  (`src/routes/<dir>/` → `e2e/<dir>.spec.ts`, same mapping as #1255),
  unless shared frontend code changed (`src/lib`, root layout, `e2e/`,
  playwright config, package files) **or** the workflows/actions
  themselves changed (`.github/workflows/`, `.github/actions/` — CI
  self-tests the full suite) — then the full sharded suite.
- **Docs/metadata-only diffs** (under `docs/`, `*.md`, `LICENSE*`,
  `CHANGELOG*`, `CODEOWNERS`, dotfiles, `.reuse/`, `REUSE.toml`,
  `.trivyignore`, `.pre-commit-config.yaml`, `aur/`): e2e is **skipped**.
  These files cannot affect the app — markdown is only ever linked from
  the frontend, never bundled into it. The list is deliberately narrow:
  anything else (backend code, compose files, workflows, scripts) keeps
  full verification.
- **Failed/empty diff** (e.g. unreachable `before` SHA after a
  force-push, or >300 changed files which the compare API truncates):
  the safe default is the **full suite** — an unknown diff is never
  scoped or skipped.
- The diff comes from the **compare API** (`/compare/{base}...{head}`),
  not `git diff`: a depth-1 checkout plus a depth-1 base fetch has no
  merge base, so the old inline `git diff origin/base...HEAD` failed
  silently and every PR quietly ran smoke-only (#1255's route scoping
  never actually engaged). GITHUB_TOKEN is enough — no user secrets.

### Tuning

Measured on run `44833334196` (2026-11-20): ~55-60 min of total serial
test time — shard legs ran 3-10 min of tests plus ~2.5 min setup.
`SHARD_COUNT: 8` keeps a typical leg around ~10 min wall clock including
retry inflation when tests fail. If a shard leg starts approaching ~10
min again, raise `SHARD_COUNT` in `e2e-plan` — do **not** raise
Playwright `workers`: tests share the shard's API + DB and are only
guaranteed serially safe. `timeout-minutes: 30` on the job stays as the
hard bound.

Artifacts are per-shard (`playwright-report-<n>`) because
`upload-artifact` v4+ rejects duplicate names across parallel legs.

## Why not shared image artifacts

`docker-build` and every `frontend-e2e` leg build the same 4 service
images, but each leg is a separate runner and the BuildKit GitHub
Actions cache (`type=gha`, per-service scopes) makes the rebuild a ~1-min
cache hit. `docker save` + `upload-artifact` would move ~1-2 GB per leg
(slower), and pushing to a registry would need `packages: write`
credentials — not available to fork-PR runs, which must stay
secrets-free by policy. The composite actions in `.github/actions/`
(`build-joidy-images`, `boot-joidy-stack`) keep the definitions shared so
tags/env/health-checks can't drift between jobs.

## Release gate

`release.yml` refuses to tag a commit whose CI is not green:

- Before computing the version, the release job polls the REST API for
  the latest CI run on `github.sha` (`actions/workflows/ci.yml/runs?
  head_sha=…`, requires `actions: read`).
- It waits up to 45 min for the run to complete, then requires
  `conclusion == success`. `failure`, `cancelled`, timed-out and missing
  runs all refuse the release.
- Because a push to `main` fires CI and Release simultaneously, the gate
  normally waits ~10 min for the in-flight CI run — this is what makes it
  work identically for merge, squash and direct commits (a "check the
  development run" lookup misses fresh merge commits).
- To release after a red CI: fix the failure, get a green CI run on the
  target commit, then re-push or re-dispatch — the gate re-evaluates the
  same commit.

This replaces relying on "CI happened to be green at merge time": with
queueing (not cancellation) for push runs, a completed green run on the
released commit is now actually attainable.

## Fork-safety

Repo policy runs workflows on fork PRs without approval. Therefore:

- No PR-triggered job uses secrets or write permissions; every job
  declares `permissions: contents: read`.
- The release gate's `actions: read` only exists in `release.yml`, which
  never triggers on PRs.
- Playwright shards use no secrets; each leg's stack is ephemeral.
