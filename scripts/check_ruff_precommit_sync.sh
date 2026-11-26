#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 D4MAG3_WIZ4RD and contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# check_ruff_precommit_sync.sh — assert that the ruff-pre-commit `rev:` in
# .pre-commit-config.yaml matches the ruff pin in api/requirements-dev.txt
# (the canonical parity source), so local pre-commit hooks and the CI lint
# gate run the exact same ruff version (#1586).
#
# Single source for the comparison: invoked by scripts/lint.sh (`make lint`)
# for local runs and by the api-lint job in .github/workflows/ci.yml so
# drift is also caught on PRs that bump requirements-dev.txt (e.g.
# dependabot) without anyone running `make lint`.
#
# Exit codes:
#   0 — versions match
#   1 — versions differ, or a pin could not be parsed (missing files count
#       as unparseable: both always exist in a real checkout)

set -u

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

RUFF_PIN="$(sed -n 's/^ruff==\([^[:space:]]*\).*/\1/p' api/requirements-dev.txt 2>/dev/null | head -n1)"
HOOK_REV="$(awk '/ruff-pre-commit/{found=1} found && /^[[:space:]]*rev:/{gsub(/[[:space:]]/, "", $2); print $2; exit}' .pre-commit-config.yaml 2>/dev/null)"

if [ -z "$RUFF_PIN" ] || [ -z "$HOOK_REV" ]; then
    echo "ERROR: could not parse ruff pins (requirements ruff=='$RUFF_PIN', hook rev='$HOOK_REV')" >&2
    exit 1
fi

if [ "$HOOK_REV" != "v$RUFF_PIN" ]; then
    echo "ERROR: ruff-pre-commit rev ($HOOK_REV) != ruff pin in api/requirements-dev.txt (v$RUFF_PIN)" >&2
    echo "Bump 'rev:' under astral-sh/ruff-pre-commit in .pre-commit-config.yaml to v$RUFF_PIN." >&2
    exit 1
fi

echo "ruff-pre-commit $HOOK_REV matches api/requirements-dev.txt"
