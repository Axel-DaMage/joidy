#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 D4MAG3_WIZ4RD and contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# check_requirements_dev_sync.sh — assert that the dev/test tool pins in
# api/requirements-dev.txt, ai-service/requirements-dev.txt and
# worker/requirements-dev.txt match the canonical pins in the repo-root
# requirements-dev.txt (#1557).
#
# Why copies instead of a shared "-r" include: each service image builds
# with the service directory as its Docker context, so a requirements file
# inside the image cannot reference ../requirements-dev.txt. The pins must
# live physically in every context; this script keeps the copies honest.
#
# Single source for the comparison: invoked by scripts/lint.sh (`make
# lint`) and by the api-lint job in .github/workflows/ci.yml so a bump
# that edits only some copies (e.g. dependabot) fails fast.
#
# Exit codes:
#   0 — every service file carries the canonical pins + "-r requirements.txt"
#   1 — a file is missing, lost its runtime include, or its pins differ

set -u

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

CANONICAL="requirements-dev.txt"

# Non-comment, non-blank, non-directive (-r/-c/-e/...) lines; sorted so the
# comparison is order-insensitive.
pins() {
    grep -vE '^[[:space:]]*(#|$)' "$1" | grep -vE '^[[:space:]]*-' | sort
}

CANONICAL_PINS="$(pins "$CANONICAL")"
if [ -z "$CANONICAL_PINS" ]; then
    echo "ERROR: could not parse any pins from $CANONICAL" >&2
    exit 1
fi

FAILED=0
for svc in api ai-service worker; do
    svc_file="$svc/requirements-dev.txt"
    if [ ! -f "$svc_file" ]; then
        echo "ERROR: $svc_file is missing" >&2
        FAILED=1
        continue
    fi
    if ! grep -qE '^[[:space:]]*-r[[:space:]]+requirements\.txt[[:space:]]*$' "$svc_file"; then
        echo "ERROR: $svc_file lost its '-r requirements.txt' runtime include" >&2
        FAILED=1
    fi
    if ! diff <(printf '%s\n' "$CANONICAL_PINS") <(pins "$svc_file"); then
        echo "ERROR: $svc_file pins differ from $CANONICAL (see diff above)" >&2
        echo "Edit $CANONICAL, then copy the pin lines into each service requirements-dev.txt." >&2
        FAILED=1
    fi
done

if [ "$FAILED" -ne 0 ]; then
    exit 1
fi
echo "requirements-dev.txt pins in sync: root canonical == api/ == ai-service/ == worker/"
