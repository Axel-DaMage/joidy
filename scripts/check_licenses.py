#!/usr/bin/env python3
"""Enforce the third-party license policy on CycloneDX SBOMs (#1386).

License policy for distributed Joidy artifacts
---------------------------------------------

Joidy is GPL-3.0-only. Its Docker images convey binary copies of every
listed dependency, so each dependency license must be (a) compatible with
distribution alongside GPL-3.0 code and (b) free of terms we cannot satisfy
(network copyleft, field-of-use or commercial restrictions).

DENIED — hard fail, the pipeline refuses to publish:
    AGPL-*              network copyleft would extend to our API services
    SSPL-*              service-side copyleft (OSI-rejected)
    GPL-1.0*            incompatible with GPL-3.0
    GPL-2.0-only        GPLv2-only cannot combine with GPLv3
                        (GPL-2.0-or-later is ALLOWED; a bare deprecated
                        "GPL-2.0" id is REVIEW — ambiguous upstream metadata)
    CC-BY-NC*/CC-BY-ND* non-free terms for code distribution
    BUSL-*, Elastic-*, Commons-Clause, Proprietary/Commercial/Unlicensed

REVIEW — warning, does not fail unless --strict:
    weak copyleft that is distributable but needs file-level diligence:
    LGPL-*, MPL-*, EPL-*, CDDL-*, CPL-*, EUPL-*, OSL-*, CECILL-*, CC-BY-SA-*,
    bare deprecated GPL-2.0, and LicenseRef-* (unidentified custom text)

UNKNOWN — license metadata missing (NOASSERTION/NONE):
    counted and reported; fails only under --strict. Source-mode SBOMs
    (`make sbom`) are largely UNKNOWN by nature — manifest files carry no
    license fields. The authoritative check runs on image SBOMs (dist-info /
    package.json metadata) in .github/workflows/publish.yml.

ALLOWED (implicit): everything else — MIT, Apache-2.0, BSD-*, ISC, PSF,
    Python-2.0, Zlib, GPL-3.0-* (our own license), GPL-2.0-or-later,
    CC0-1.0, Unlicense, WTFPL, ...

Usage:
    python3 scripts/check_licenses.py [--strict] [--quiet] sbom/*.cdx.json

Exit code: 0 when no DENIED license is found (plus no REVIEW/UNKNOWN under
--strict), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DENY_PATTERNS = [
    r"^AGPL",
    r"^SSPL",
    r"^GPL-1\.0",
    r"^GPL-2\.0-ONLY$",
    r"^CC-BY-NC",
    r"^CC-BY-ND",
    r"^BUSL",
    r"^ELASTIC",
    r"^COMMONS-CLAUSE",
    r"^PROPRIETARY",
    r"^COMMERCIAL",
    r"^UNLICENSED",
]

REVIEW_PATTERNS = [
    r"^LGPL",
    r"^MPL",
    r"^EPL",
    r"^EUPL",
    r"^CDDL",
    r"^CPL",
    r"^OSL",
    r"^CECILL",
    r"^CC-BY-SA",
    r"^GPL-2\.0$",  # bare deprecated id — ambiguous (only vs or-later)
    r"^LICENSEREF",
]

UNKNOWN_TOKENS = {"", "NOASSERTION", "NONE", "UNKNOWN"}

_DENY_RE = [re.compile(p) for p in DENY_PATTERNS]
_REVIEW_RE = [re.compile(p) for p in REVIEW_PATTERNS]

DENY, REVIEW, UNKNOWN, ALLOWED = "deny", "review", "unknown", "allowed"
_SEVERITY = {ALLOWED: 0, UNKNOWN: 1, REVIEW: 2, DENY: 3}
_ON_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def canon(token: str) -> str:
    """Normalize a license id/name for policy matching."""
    t = token.strip().strip("()").upper()
    t = re.sub(r"\s+", "-", t)
    # Deprecated '+' suffix means "-or-later" (e.g. GPL-2.0+).
    if t.endswith("+"):
        t = t[:-1] + "-OR-LATER"
    return t


def classify(token: str) -> str:
    if token in UNKNOWN_TOKENS:
        return UNKNOWN
    for rx in _DENY_RE:
        if rx.search(token):
            return DENY
    for rx in _REVIEW_RE:
        if rx.search(token):
            return REVIEW
    return ALLOWED


def split_expression(expr: str) -> list[list[str]]:
    """Split an SPDX expression into OR-alternatives of AND-ed tokens.

    Sufficient for scanner output: parentheses are flattened and WITH
    exceptions stay attached to their base license (the base id is what the
    policy matches on).
    """
    flat = expr.replace("(", " ").replace(")", " ")
    alternatives = []
    for alt in re.split(r"\bOR\b", flat, flags=re.IGNORECASE):
        tokens = [
            canon(part)
            for part in re.split(r"\bAND\b|\bWITH\b", alt, flags=re.IGNORECASE)
            if part.strip("() \t")
        ]
        alternatives.append(tokens)
    return alternatives


def component_verdict(component: dict) -> tuple[str, str]:
    """Return (worst_category, display_string) for a CycloneDX component."""
    licenses = component.get("licenses") or []
    if not licenses:
        return UNKNOWN, "NOASSERTION"

    display = []
    worst = ALLOWED
    for entry in licenses:
        if "expression" in entry:
            expr = entry["expression"]
            display.append(expr)
            # OR semantics: the component is distributable under the most
            # permissive alternative, so take the best alternative's verdict.
            alt_verdicts = []
            for tokens in split_expression(expr):
                alt_verdicts.append(max((classify(t) for t in tokens), key=_SEVERITY.get, default=UNKNOWN))
            verdict = min(alt_verdicts, key=_SEVERITY.get, default=UNKNOWN)
        else:
            lic = entry.get("license") or {}
            token = canon(lic.get("id") or lic.get("name") or "")
            display.append(token or "NOASSERTION")
            verdict = classify(token or "NOASSERTION")
            # AND semantics: every listed license must be acceptable.
        worst = max(worst, verdict, key=_SEVERITY.get)
    return worst, " OR ".join(display)


def annotate(level: str, message: str) -> None:
    if _ON_CI:
        print(f"::{level}::{message}")
    else:
        print(f"[{level.upper()}] {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sboms", nargs="+", type=Path, help="CycloneDX JSON SBOM files")
    parser.add_argument("--strict", action="store_true", help="fail on REVIEW/UNKNOWN too")
    parser.add_argument("--quiet", action="store_true", help="print only DENY details + summary")
    args = parser.parse_args()

    counts = {DENY: 0, REVIEW: 0, UNKNOWN: 0, ALLOWED: 0}
    violations: list[str] = []
    reviews: list[str] = []
    unknowns: list[str] = []

    for sbom in args.sboms:
        doc = json.loads(sbom.read_text(encoding="utf-8"))
        for comp in doc.get("components") or []:
            # "file"-type entries are the manifest files themselves, not
            # packages — they carry no license obligation.
            if comp.get("type") == "file":
                continue
            verdict, display = component_verdict(comp)
            counts[verdict] += 1
            who = f"{sbom.name}: {comp.get('name', '?')}@{comp.get('version', '?')} — {display}"
            if verdict == DENY:
                violations.append(who)
            elif verdict == REVIEW:
                reviews.append(who)
            elif verdict == UNKNOWN:
                unknowns.append(who)

    for v in violations:
        annotate("error", f"DENIED license — {v}")
    if not args.quiet:
        for r in reviews:
            annotate("warning", f"weak-copyleft (review) — {r}")
        for u in unknowns:
            annotate("warning", f"license not detected — {u}")

    print(
        "License policy summary: "
        f"{counts[DENY]} denied, {counts[REVIEW]} review, "
        f"{counts[UNKNOWN]} unknown, {counts[ALLOWED]} allowed "
        f"({sum(counts.values())} components)"
    )

    failed = bool(violations) or (args.strict and (reviews or unknowns))
    if failed:
        print("::error::license policy check FAILED" if _ON_CI else "License policy check FAILED")
        return 1
    print("License policy check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
