#!/usr/bin/env python3
"""Generate a THIRD-PARTY-NOTICES license report from CycloneDX SBOMs (#1386).

Reads one or more CycloneDX JSON files produced by scripts/generate_sbom.sh
and renders a flat text notice file: one section per SBOM (service image),
one entry per component with its declared license, copyright holder (when the
upstream package metadata reports one) and purl.

Copyright/license obligations for the permissive families we ship (MIT,
Apache-2.0, BSD, ISC, ...) require the license text and attribution to
accompany the binary distribution — i.e. our Docker Hub images. The rendered
file is attached to each image as an OCI referrer and uploaded to the GitHub
release by .github/workflows/publish.yml.

Stdlib only — runs on a bare runner/host.

Usage:
    python3 scripts/generate_notices.py --output THIRD-PARTY-NOTICES.txt \
        sbom/*.cdx.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HEADER = """\
THIRD-PARTY NOTICES
===================

Project: Joidy (GPL-3.0-only) — https://github.com/Axel-DaMage/joidy

The Joidy distribution (Docker images d4mag3/joidy-*, release assets and
packages that install those images) contains the third-party software
components listed below. Each entry shows the package name and version, its
declared license and the copyright notice reported by its package metadata.

This file is generated automatically from CycloneDX SBOMs
(sbom/joidy-*.cdx.json, produced by anchore/syft) — see
scripts/generate_sbom.sh and scripts/generate_notices.py.
"""


def license_text(component: dict) -> str:
    """Render a human-readable license string for a CycloneDX component."""
    licenses = component.get("licenses") or []
    parts = []
    for entry in licenses:
        if "expression" in entry:
            parts.append(entry["expression"])
        elif "license" in entry:
            lic = entry["license"] or {}
            parts.append(lic.get("id") or lic.get("name") or "NOASSERTION")
    return ", ".join(parts) if parts else "NOASSERTION"


def component_label(path: Path, doc: dict) -> str:
    """Prefer the SBOM metadata component name, else the file stem."""
    meta = doc.get("metadata", {}).get("component", {})
    name = meta.get("name")
    if name:
        return name
    return path.stem.removesuffix(".cdx")


def collect(path: Path) -> tuple[str, list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    # Skip "file"-type components — syft catalogs the manifest files
    # themselves (/requirements.txt, package-lock.json); they are not
    # third-party packages and carry no license obligation.
    components = [c for c in doc.get("components") or [] if c.get("type") != "file"]
    return component_label(path, doc), components


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sboms", nargs="+", type=Path, help="CycloneDX JSON SBOM files")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("THIRD-PARTY-NOTICES.txt"),
        help="Output file (default: THIRD-PARTY-NOTICES.txt)",
    )
    args = parser.parse_args()

    sections: list[tuple[str, list[dict]]] = []
    total = 0
    for sbom in args.sboms:
        label, components = collect(sbom)
        sections.append((label, components))
        total += len(components)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [HEADER, f"Generated: {now}\n", f"Components: {total} across {len(sections)} SBOM(s)\n"]

    for label, components in sections:
        lines.append("")
        lines.append(f"── {label} ({len(components)} components) " + "─" * 40)
        lines.append("")
        # Dedupe by (name, version, license) — syft can emit both apk/dpkg
        # and language-level entries for the same package.
        seen: set[tuple[str, str, str]] = set()
        for comp in sorted(components, key=lambda c: (c.get("name") or "", c.get("version") or "")):
            name = comp.get("name") or "unknown"
            version = comp.get("version") or ""
            lic = license_text(comp)
            key = (name, version, lic)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{name} {version}".rstrip())
            lines.append(f"    License: {lic}")
            copyright_text = (comp.get("copyright") or "").strip()
            if copyright_text and copyright_text != "NOASSERTION":
                for c_line in copyright_text.splitlines():
                    lines.append(f"    Copyright: {c_line.strip()}")
            purl = comp.get("purl")
            if purl:
                lines.append(f"    PURL: {purl}")
            lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({total} components, {len(sections)} SBOMs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
