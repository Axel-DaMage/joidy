#!/bin/bash
# Host-side lint parity with CI (.github/workflows/ci.yml) — no Docker needed.
#
# Runs the same cheap gates the api-lint / security / frontend-check jobs use:
#   1. python -m compileall api ai-service worker          (syntax)
#   2. ruff check + ruff format --check                    (lint + format)
#   3. ruff version sync — .pre-commit-config.yaml rev must match the ruff
#      pin in api/requirements-dev.txt (#1586; always runs, no tools needed)
#   4. mypy — one invocation per service                   (typecheck)
#   5. bandit -lll -iii (tests excluded, like CI)          (security)
#   6. npm run check (svelte-check) if frontend deps exist (typecheck)
#
# Versions are pinned in api/requirements-dev.txt so local output matches CI:
#   pip install -r api/requirements-dev.txt
# The script probes PATH first, then ./.venv/bin and ./venv/bin.
#
# A missing tool is skipped with a warning (compileall always runs) so the
# command works on a bare checkout. STRICT=1 turns missing tools into a
# failure instead:
#   STRICT=1 make lint
#
# Exit code: 0 only if every gate that ran passed.

set -u

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

STRICT="${STRICT:-0}"
FAILED=0
SKIPPED=0
RAN=0

# Resolve a tool from PATH or common venv locations.
find_tool() {
    local name="$1"
    if command -v "$name" >/dev/null 2>&1; then
        command -v "$name"
        return 0
    fi
    for dir in .venv/bin venv/bin env/bin; do
        if [ -x "$PROJECT_ROOT/$dir/$name" ]; then
            echo "$PROJECT_ROOT/$dir/$name"
            return 0
        fi
    done
    return 1
}

gate() { echo -e "\n── ${BLUE}$1${NC} ──"; }

skip() {
    SKIPPED=$((SKIPPED + 1))
    echo -e "${YELLOW}⚠${NC} $1 — skipped"
    if [ "$STRICT" = "1" ]; then
        echo -e "${RED}✗ STRICT=1: missing tool is a failure${NC}"
        FAILED=1
    fi
}

run() {
    RAN=$((RAN + 1))
    "$@"
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        FAILED=1
    fi
    return "$rc"
}

PYTHON="$(find_tool python3 || find_tool python || true)"
RUFF="$(find_tool ruff || true)"
MYPY="$(find_tool mypy || true)"
BANDIT="$(find_tool bandit || true)"

# ── 1. Syntax (always runs — this is the old `make lint` behavior) ──────────
gate "compileall — Python syntax"
if [ -n "$PYTHON" ]; then
    run "$PYTHON" -m compileall -q api ai-service worker \
        && echo -e "${GREEN}✓${NC} compileall passed"
else
    skip "python3 not found — cannot run even the syntax check"
fi

# ── 2. Ruff (same invocations as the api-lint CI job) ───────────────────────
gate "ruff check + ruff format --check"
if [ -n "$RUFF" ]; then
    run "$RUFF" check api ai-service worker \
        && echo -e "${GREEN}✓${NC} ruff check passed"
    run "$RUFF" format --check api ai-service worker \
        && echo -e "${GREEN}✓${NC} ruff format --check passed"
else
    skip "ruff not installed (pip install -r api/requirements-dev.txt)"
fi

# ── 3. Pre-commit ruff version parity (always runs — pure text check) ──────
# The ruff-pre-commit rev must match the ruff pin in api/requirements-dev.txt
# (canonical parity source) so local hooks and CI run the same ruff (#1586).
# Shared with the api-lint CI job via check_ruff_precommit_sync.sh.
gate "ruff version sync — .pre-commit-config.yaml vs api/requirements-dev.txt"
run bash scripts/check_ruff_precommit_sync.sh \
    && echo -e "${GREEN}✓${NC} ruff version sync passed"

# ── 4. Mypy (one invocation per service, same as CI) ────────────────────────
gate "mypy — per-service typecheck"
if [ -n "$MYPY" ]; then
    for svc in api ai-service worker; do
        echo "[$svc]"
        (cd "$svc" && MYPYPATH=. "$MYPY" --explicit-package-bases --config-file ../pyproject.toml .)
        if [ "$?" -ne 0 ]; then
            FAILED=1
        fi
        RAN=$((RAN + 1))
    done
else
    skip "mypy not installed (pip install -r api/requirements-dev.txt)"
fi

# ── 5. Bandit (same flags as the security CI job) ───────────────────────────
gate "bandit — security scan (-lll -iii, tests excluded)"
if [ -n "$BANDIT" ]; then
    run "$BANDIT" -r api/ ai-service/ worker/ -lll -iii -x api/tests,ai-service/tests,worker/tests -q \
        && echo -e "${GREEN}✓${NC} bandit passed"
else
    skip "bandit not installed (pip install -r api/requirements-dev.txt)"
fi

# ── 6. Frontend typecheck (same as the frontend-check CI job) ───────────────
gate "frontend — npm run check (svelte-check)"
if [ -d "$PROJECT_ROOT/frontend/node_modules" ] && command -v npm >/dev/null 2>&1; then
    (cd frontend && npm run check)
    if [ "$?" -ne 0 ]; then
        FAILED=1
    fi
    RAN=$((RAN + 1))
else
    skip "frontend deps missing (cd frontend && npm ci)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
if [ "$FAILED" -ne 0 ]; then
    echo -e "${RED}✗ Lint failed${NC} — $RAN gates ran, $SKIPPED skipped."
    exit 1
fi
if [ "$SKIPPED" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Lint passed but $SKIPPED gate(s) were skipped${NC} (tools not installed)."
    echo "  For full CI parity: pip install -r api/requirements-dev.txt && (cd frontend && npm ci)"
    exit 0
fi
echo -e "${GREEN}✓ Lint passed${NC} — $RAN gates ran, same checks as CI."
exit 0
