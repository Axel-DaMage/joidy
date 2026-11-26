#!/usr/bin/env python3
"""Quality-debt ratchet (#1264) — CI-enforced burn-down of grandfathered
lint/typecheck exceptions.

Two budgets, pinned by checked-in files next to this script:

* ``scripts/mypy_baseline.txt`` — the exact module list allowed in
  ``[[tool.mypy.overrides]]`` entries with ``ignore_errors = true`` in
  ``pyproject.toml``. The list can only shrink: adding a module means new
  type debt would go completely unchecked.
* ``scripts/ruff_budgets.txt`` — per-rule site budgets for ruff rules that
  stay globally ignored (``B904``, ``UP042``) because fixing them changes
  runtime semantics. ``ruff check --select <RULE>`` counts live violations;
  exceeding the budget fails, and so does drifting below it (stale budget —
  regenerate so the ratchet tightens).

Usage:
    python scripts/check_quality_baselines.py            # check (CI gate)
    python scripts/check_quality_baselines.py --update   # regenerate budgets

``--update`` is how you *claim* a burn-down — after un-ignoring a module or
fixing ruff sites. It must never be used to admit new debt.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
MYPY_BASELINE = REPO_ROOT / "scripts" / "mypy_baseline.txt"
RUFF_BUDGETS = REPO_ROOT / "scripts" / "ruff_budgets.txt"
RUFF_TARGETS = ("api", "ai-service", "worker")

MYPY_BASELINE_HEADER = """\
# mypy ignore_errors baseline (#1264) — the ratchet list.
#
# Every module pattern allowed to appear in [[tool.mypy.overrides]] entries
# with ``ignore_errors = true`` in pyproject.toml, one per line. The list can
# only SHRINK: CI fails if a module is added (new debt sneaks in unchecked)
# and also fails if the file drifts out of sync when a module is un-ignored.
#
# After fixing a module's type errors, remove its entry from pyproject.toml
# and regenerate this file:
#     python scripts/check_quality_baselines.py --update
"""

RUFF_BUDGETS_HEADER = """\
# Ruff violation budgets (#1264) — site-count ratchet for globally-ignored rules.
#
# Format: ``RULE = COUNT``. ``ruff check --select <RULE>`` must report at
# most COUNT violations across api/, ai-service/ and worker/. These rules are
# in [tool.ruff.lint].ignore (see pyproject.toml) because fixing them changes
# runtime semantics; the budget keeps the debt from growing and burns it
# down as sites are fixed.
#
# CI fails when the count EXCEEDS the budget (new violations) and when the
# count DROPS BELOW it (budget is stale). After fixing sites, lower the
# number or regenerate:
#     python scripts/check_quality_baselines.py --update
"""


def _read_lines(path: Path) -> list[str]:
    """Non-empty, non-comment lines of a budget file."""
    return [
        line.split("#", 1)[0].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.split("#", 1)[0].strip()
    ]


def ignored_mypy_modules() -> list[str]:
    """Modules covered by ``ignore_errors = true`` overrides in pyproject.toml."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    modules: list[str] = []
    for override in data.get("tool", {}).get("mypy", {}).get("overrides", []):
        if not override.get("ignore_errors"):
            continue
        entry = override.get("module", [])
        modules.extend(entry if isinstance(entry, list) else [entry])
    return sorted(modules)


def ruff_site_counts(rules: list[str]) -> dict[str, int]:
    """Live violation count per rule via ``ruff check --select`` (config
    ``lint.ignore`` does not apply to explicitly selected rules)."""
    counts = dict.fromkeys(rules, 0)
    proc = subprocess.run(
        ["ruff", "check", "--statistics", *[f"--select={r}" for r in rules], *RUFF_TARGETS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    for line in proc.stdout.splitlines():
        match = re.match(r"^\s*(\d+)\s+([A-Z]+\d+)\b", line)
        if match and match.group(2) in counts:
            counts[match.group(2)] = int(match.group(1))
    return counts


def ruff_budgets() -> dict[str, int]:
    budgets: dict[str, int] = {}
    for line in _read_lines(RUFF_BUDGETS):
        rule, _, count = line.partition("=")
        budgets[rule.strip()] = int(count.strip())
    return budgets


def check_mypy_baseline() -> list[str]:
    failures: list[str] = []
    configured = set(ignored_mypy_modules())
    baseline = set(_read_lines(MYPY_BASELINE))
    grown = sorted(configured - baseline)
    shrunk = sorted(baseline - configured)
    if grown:
        failures.append(
            "mypy ignore_errors GREW (ratchet can only shrink): "
            + ", ".join(grown)
            + " — remove the entries from pyproject.toml or fix the module's"
            " type errors instead of hiding them."
        )
    if shrunk:
        failures.append(
            "mypy baseline is STALE — modules no longer ignored: "
            + ", ".join(shrunk)
            + " — regenerate: python scripts/check_quality_baselines.py --update"
        )
    if not failures:
        print(f"PASS  mypy ignore_errors: {len(configured)} module(s) match scripts/mypy_baseline.txt")
    return failures


def check_ruff_budgets() -> list[str]:
    failures: list[str] = []
    budgets = ruff_budgets()
    if not budgets:
        return failures
    counts = ruff_site_counts(list(budgets))
    for rule, budget in sorted(budgets.items()):
        count = counts.get(rule, 0)
        if count > budget:
            failures.append(
                f"ruff {rule}: {count} site(s) exceeds budget {budget} — fix the"
                f" new violations (ruff check --select={rule} {' '.join(RUFF_TARGETS)})"
            )
        elif count < budget:
            failures.append(
                f"ruff {rule}: {count} site(s) is below budget {budget} — tighten it:"
                " python scripts/check_quality_baselines.py --update"
            )
        else:
            print(f"PASS  ruff {rule}: {count} site(s) within budget {budget}")
    return failures


def update() -> None:
    modules = ignored_mypy_modules()
    MYPY_BASELINE.write_text(
        MYPY_BASELINE_HEADER + "\n".join(modules) + ("\n" if modules else ""),
        encoding="utf-8",
    )
    print(f"Wrote {MYPY_BASELINE.relative_to(REPO_ROOT)}: {len(modules)} module(s)")

    old = ruff_budgets()
    counts = ruff_site_counts(list(old))
    # Preserve any per-rule trailing comments already in the file.
    comments = {
        m.group(1): m.group(2)
        for line in RUFF_BUDGETS.read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"^\s*([A-Z]+\d+)\s*=\s*\d+\s*(#.*)$", line))
    }
    lines = [RUFF_BUDGETS_HEADER]
    for rule in sorted(counts):
        suffix = f"   {comments[rule]}" if rule in comments else ""
        lines.append(f"{rule} = {counts[rule]}{suffix}")
    RUFF_BUDGETS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {RUFF_BUDGETS.relative_to(REPO_ROOT)}: {dict(counts)}")


def main() -> int:
    if "--update" in sys.argv[1:]:
        update()
        return 0
    failures = check_mypy_baseline() + check_ruff_budgets()
    for failure in failures:
        print(f"FAIL  {failure}")
    if failures:
        print("\nQuality baseline ratchet failed — see scripts/mypy_baseline.txt and scripts/ruff_budgets.txt")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
