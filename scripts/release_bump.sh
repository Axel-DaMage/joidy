#!/usr/bin/env bash
#
# release_bump.sh — single-source version bumper for Joidy (#1258)
#
# The canonical project version lives in the root VERSION file as a bare
# semver string WITHOUT the leading "v" (e.g. "1.1.0-beta.8"); the "v" prefix
# exists only on git tags. This script regenerates every dependent file from
# that single source and then verifies they all agree — replacing the ad-hoc
# per-file sed chain that used to live inline in .github/workflows/release.yml
# and shipped wrong versions three times (#753, #754, #1163, #1195).
#
# Usage:
#   scripts/release_bump.sh <version>            bump VERSION + dependents, verify
#   scripts/release_bump.sh --check <version>    verify only (no writes)
#   scripts/release_bump.sh --dry-run <version>  exercise the bump on a scratch
#                                                copy of the tracked files
#
# <version> accepts an optional leading "v" (git tag form). Arch pkgver
# forbids hyphens, so pre-release versions map "-" -> "_" (1.1.0-beta.8 ->
# 1.1.0_beta.8). sha256sums are reset to 'SKIP' because the release tarball
# does not exist until the tag is pushed — release.yml's "Inject release
# checksums" step (and aur-publish.yml at publish time) fills in the real
# sums afterwards (#1296, #1394).
#
# aur/.SRCINFO is NEVER edited by hand: it is regenerated with
# `makepkg --printsrcinfo` — locally when makepkg is available to a non-root
# user, otherwise inside a throwaway archlinux:latest container (the same
# approach dist-smoke.yml uses for its AUR job).
#
# Dependents rewritten (see RELEASE.md "Version string automation"):
#   VERSION, pyproject.toml [project] version,
#   frontend/package.json + package-lock.json (package version fields only),
#   aur/PKGBUILD (pkgver + sha256sums), aur/.SRCINFO (regenerated),
#   docker-compose.release.yml image tags,
#   README.md badge + pinned installer URLs,
#   INSTALL.md / scripts/install.sh / scripts/install.ps1 pinned URLs,
#   docs/{index,api,architecture,troubleshooting}.md metadata,
#   CHANGELOG.md [unreleased] compare link.

set -euo pipefail

readonly PROG="release_bump.sh"

# Diagnostics go to stderr so stdout stays pure data: gen_srcinfo_stdout's
# output is captured as aur/.SRCINFO and must never contain log lines.
info() { printf '%s: %s\n' "$PROG" "$*" >&2; }
die() { printf '%s: error: %s\n' "$PROG" "$*" >&2; exit 1; }

usage() {
    cat >&2 <<'EOF'
Usage: scripts/release_bump.sh [--check|--dry-run] <version>

  <version>           bump VERSION and regenerate every dependent, then verify
  --check <version>   verify only: fail loudly if any versioned file disagrees
  --dry-run <version> run the bump on a scratch copy of the tracked files and
                      report what would change (the repo is left untouched)

<version> may be given with or without the leading "v" (e.g. v1.2.3 or
1.2.3-beta.4). See RELEASE.md "Version string automation".
EOF
    exit "${1:-0}"
}

# --- argument parsing ---------------------------------------------------------
MODE="bump"
case "${1:-}" in
    --check)   MODE="check";   shift ;;
    --dry-run) MODE="dry-run"; shift ;;
    -h|--help) usage 0 ;;
    "")        usage 2 ;;
esac
[ "$#" -eq 1 ] || usage 2
VERSION_INPUT="$1"

# --- normalize / validate -----------------------------------------------------
# Same tag shape release.yml enforces: vMAJOR.MINOR.PATCH[-prerelease.N]
VERSION_CLEAN="${VERSION_INPUT#v}"
[[ "$VERSION_CLEAN" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$ ]] \
    || die "invalid version '$VERSION_INPUT' — expected vX.Y.Z or X.Y.Z with optional -prerelease.N"
VERSION_TAG="v${VERSION_CLEAN}"
# Arch pkgver forbids hyphens (1.1.0-beta.8 -> 1.1.0_beta.8)
VERSION_AUR="${VERSION_CLEAN//-/_}"
TODAY="$(date +%Y-%m-%d)"

# --- locate repo root ---------------------------------------------------------
# The script always manages the tree it lives in: <root>/scripts/release_bump.sh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ ! -f "$ROOT/aur/PKGBUILD" ] || [ ! -f "$ROOT/frontend/package.json" ]; then
    die "cannot locate repository root from $SCRIPT_DIR"
fi
cd "$ROOT"

# --- helpers ------------------------------------------------------------------
# GNU vs BSD sed -i (same convention as Makefile's SED_INPLACE)
if sed --version >/dev/null 2>&1; then
    SED_INPLACE=(sed -i)
else
    SED_INPLACE=(sed -i '')
fi

sedi() { "${SED_INPLACE[@]}" "$@"; }

# Escape a literal string for use inside an ERE pattern.
ere() { printf '%s' "$1" | sed 's/[][\.*^$()+?{}|]/\\&/g'; }
V_ERE="$(ere "$VERSION_CLEAN")"
AUR_ERE="$(ere "$VERSION_AUR")"

# Rewrite "version" fields that belong to the named package. In
# frontend/package.json there is exactly one ("name": "joidy-frontend" ->
# "version" on the next line). In package-lock.json (lockfileVersion 3) the
# same pair appears twice: top-level and packages."". Only adjacent
# name->version pairs are touched, so dependency versions are never rewritten
# (the successor of the old sed N-trick). Exits non-zero unless exactly $2
# replacements were made — callers only mv the temp file on success.
bump_named_version() {
    local f="$1" want="$2" tmp
    [ -f "$f" ] || die "missing $f"
    tmp="$(mktemp)"
    if ! awk -v ver="$VERSION_CLEAN" -v want="$want" '
        {
            if (prev_name && /"version": "/) {
                sub(/"version": "[^"]*"/, "\"version\": \"" ver "\"")
                replaced++
            }
            prev_name = ($0 ~ /"name": "joidy-frontend",/)
            print
        }
        END { exit (replaced == want) ? 0 : 1 }
    ' "$f" > "$tmp"; then
        rm -f "$tmp"
        die "failed to bump $f: expected $want package version field(s)"
    fi
    mv "$tmp" "$f"
}

# --- .SRCINFO generation ------------------------------------------------------
# makepkg refuses to run as root and wants a writable BUILDDIR, so the AUR
# directory is copied to a scratch dir first — the repo is never polluted.
# Prefers a local non-root makepkg; falls back to a throwaway
# archlinux:latest container (same makepkg the dist-smoke AUR job uses).
# Prints canonical .SRCINFO on stdout.
gen_srcinfo_stdout() {
    local tmp out
    tmp="$(mktemp -d)"
    cp -a aur/. "$tmp/"
    out="$tmp/srcinfo"
    if command -v makepkg >/dev/null 2>&1 && [ "$(id -u)" != "0" ]; then
        if ! (cd "$tmp" && makepkg --printsrcinfo > "$out"); then
            rm -rf "$tmp"; die "makepkg --printsrcinfo failed"
        fi
    elif command -v docker >/dev/null 2>&1; then
        info "makepkg unavailable — generating .SRCINFO in archlinux:latest container"
        if ! docker run --rm -v "$tmp:/src-aur:ro" archlinux:latest bash -c '
            set -e
            useradd -m builder >/dev/null 2>&1 || true
            cp -a /src-aur /tmp/aur-check
            chown -R builder:builder /tmp/aur-check
            su builder -c "cd /tmp/aur-check && makepkg --printsrcinfo"
        ' > "$out"; then
            rm -rf "$tmp"; die "dockerized makepkg --printsrcinfo failed"
        fi
    else
        rm -rf "$tmp"; die "cannot generate .SRCINFO: need makepkg (non-root) or docker"
    fi
    [ -s "$out" ] || { rm -rf "$tmp"; die "makepkg produced an empty .SRCINFO"; }
    cat "$out"
    rm -rf "$tmp"
}

# --- bump ---------------------------------------------------------------------
bump_all() {
    info "bumping to $VERSION_TAG (AUR pkgver $VERSION_AUR)"
    local f tmp

    # 1. Canonical source — rewritten first; everything else derives from it.
    printf '%s\n' "$VERSION_CLEAN" > VERSION

    # 2. README badge. Consume everything up to the closing quote or '?',
    #    then re-append the color: the historical bug was a character class
    #    that matched only "-b" of "-blue" and accumulated junk like
    #    "v1.1.0-beta.7ta.6..." on every release.
    sedi -E "s|badge/JOIDY-v[^\"?]*|badge/JOIDY-v${VERSION_CLEAN}-blue|g" README.md

    # 3. Pinned installer URLs (raw.githubusercontent.com/.../joidy/<ref>/
    #    scripts/install.{sh,ps1}). Concrete git refs — tags, branches, SHAs —
    #    are pinned to the release tag so one-shot installs are immutable
    #    (#1394). Template refs like ${TAG} are deliberately preserved.
    for f in README.md INSTALL.md scripts/install.sh scripts/install.ps1; do
        [ -f "$f" ] || die "missing $f"
        # Single-quoted pattern keeps ${...} template refs literal for sed;
        # only the replacement version is expanded by the shell. ';'
        # delimiter: '|' would collide with the (sh|ps1) alternation.
        sedi -E 's;(raw\.githubusercontent\.com/Axel-DaMage/joidy/)[^/${}]+/(scripts/install\.(sh|ps1));\1v'"${VERSION_CLEAN}"'/\2;g' "$f"
    done

    # 4. AUR PKGBUILD — pkgver only; _tag=${pkgver//_/-} and the source URL
    #    derive from it automatically. sha256sums reset to SKIP: the tarball
    #    does not exist until the tag is pushed.
    sedi -E "s|^pkgver=.*|pkgver=${VERSION_AUR}|" aur/PKGBUILD
    sedi -E "s|^sha256sums=.*|sha256sums=('SKIP' 'SKIP')|" aur/PKGBUILD

    # 5. aur/.SRCINFO — regenerated by makepkg, never hand-edited (#1163).
    #    Written via a temp file so a makepkg failure cannot leave a
    #    truncated .SRCINFO behind.
    tmp="$(mktemp)"
    if ! gen_srcinfo_stdout > "$tmp"; then
        rm -f "$tmp"
        die "failed to generate aur/.SRCINFO"
    fi
    mv "$tmp" aur/.SRCINFO

    # 6. docker-compose.release.yml — pinned image tags of the release it
    #    ships with (#1394).
    sedi -E "s|(image: d4mag3/joidy-[a-z-]+:)[0-9A-Za-z.+-]+|\1${VERSION_CLEAN}|g" docker-compose.release.yml

    # 7. docs metadata version fields (+ last_updated in troubleshooting).
    local doc
    for doc in docs/index.md docs/api.md docs/architecture.md docs/troubleshooting.md; do
        [ -f "$doc" ] || die "missing $doc"
        sedi -E "s|^version: [0-9A-Za-z.+-]+|version: ${VERSION_CLEAN}|" "$doc"
    done
    sedi -E "s|^last_updated: [0-9-]+|last_updated: ${TODAY}|" docs/troubleshooting.md

    # 8. frontend package.json + package-lock.json — package version fields
    #    only; dependency versions are never touched.
    bump_named_version frontend/package.json 1
    bump_named_version frontend/package-lock.json 2

    # 9. pyproject.toml [project] version — the third drifting source the
    #    issue called out (it sat at 0.2.0 while releases were at 1.1.0).
    tmp="$(mktemp)"
    if ! awk -v ver="$VERSION_CLEAN" '
        !done && /^version = "/ {
            sub(/^version = "[^"]*"/, "version = \"" ver "\"")
            done = 1
        }
        { print }
    ' pyproject.toml > "$tmp"; then
        rm -f "$tmp"
        die "failed to bump pyproject.toml"
    fi
    mv "$tmp" pyproject.toml

    # 10. CHANGELOG.md — point the [unreleased] compare link at the new tag.
    sedi -E "s|^\[unreleased\]: .*compare/v[^ ]*\.\.\.HEAD|\[unreleased\]: https://github.com/Axel-DaMage/joidy/compare/v${VERSION_CLEAN}...HEAD|" CHANGELOG.md

    info "dependents regenerated"
}

# --- verify -------------------------------------------------------------------
# Shared by bump mode (post-write self-check) and --check mode. Fails loudly:
# every versioned file must agree with the target version or the release
# aborts before anything is committed.
verify_version() {
    local errors=0 f n ctags refs bad pbad pcount

    vfail() { printf '%s: VERIFY FAIL: %s\n' "$PROG" "$*" >&2; errors=$((errors + 1)); }
    vok()   { info "ok: $*"; }

    # Canonical VERSION file.
    if [ -f VERSION ] && [ "$(cat VERSION)" = "$VERSION_CLEAN" ]; then
        vok "VERSION = $VERSION_CLEAN"
    else
        vfail "VERSION: expected '$VERSION_CLEAN', found '$(cat VERSION 2>/dev/null || echo '<missing>')'"
    fi

    # frontend/package.json — the "version" field belonging to
    # "name": "joidy-frontend" (the line right after it). Scoped to the
    # name->version pair so coincidental dependency versions can't skew it.
    n="$(grep -A1 '"name": "joidy-frontend"' frontend/package.json 2>/dev/null | grep -cF "\"version\": \"${VERSION_CLEAN}\"" || true)"
    if [ "$n" = "1" ]; then
        vok "frontend/package.json version"
    else
        vfail "frontend/package.json: expected own version '$VERSION_CLEAN', found $n match(es)"
    fi

    # frontend/package-lock.json — lockfileVersion 3 stores the package
    # version twice (top-level + packages."") as name->version pairs.
    n="$(grep -A1 '"name": "joidy-frontend"' frontend/package-lock.json 2>/dev/null | grep -cF "\"version\": \"${VERSION_CLEAN}\"" || true)"
    if [ "$n" = "2" ]; then
        vok "frontend/package-lock.json version fields"
    else
        vfail "frontend/package-lock.json: expected 2 own version fields '$VERSION_CLEAN', found $n"
    fi

    # pyproject.toml — every top-level `version = "..."` must be the release
    # version (there must be at least one, i.e. [project] version exists).
    pcount="$(grep -cE '^version = "' pyproject.toml 2>/dev/null || true)"
    pbad="$(grep -E '^version = "' pyproject.toml 2>/dev/null | grep -cvE "^version = \"${V_ERE}\"" || true)"
    if [ "$pcount" -ge 1 ] && [ "$pbad" = "0" ]; then
        vok "pyproject.toml version"
    else
        vfail "pyproject.toml: $pcount 'version =' line(s), $pbad not equal to $VERSION_CLEAN"
    fi

    # aur/PKGBUILD — pkgver in Arch form (hyphens -> underscores).
    if grep -qE "^pkgver=${AUR_ERE}[[:space:]]*$" aur/PKGBUILD; then
        vok "aur/PKGBUILD pkgver = $VERSION_AUR"
    else
        vfail "aur/PKGBUILD: missing '^pkgver=$VERSION_AUR'"
    fi

    # aur/.SRCINFO — makepkg format (tab-indented), pkgver + resolved source.
    if grep -qE "^[[:space:]]+pkgver = ${AUR_ERE}[[:space:]]*$" aur/.SRCINFO \
        && grep -qE "source = https://github\.com/Axel-DaMage/joidy/archive/v${V_ERE}\.tar\.gz" aur/.SRCINFO; then
        vok "aur/.SRCINFO pkgver + source"
    else
        vfail "aur/.SRCINFO: pkgver != $VERSION_AUR or source URL mismatch"
    fi

    # docker-compose.release.yml — every pinned image tag is the release.
    ctags="$(grep -oE 'image: d4mag3/joidy-[a-z-]+:[0-9A-Za-z.+-]+' docker-compose.release.yml 2>/dev/null | sed 's/.*://' | sort -u)"
    if [ "$ctags" = "$VERSION_CLEAN" ]; then
        vok "docker-compose.release.yml image tags"
    else
        vfail "docker-compose.release.yml: image tags are '$ctags', expected only '$VERSION_CLEAN'"
    fi

    # README badge.
    if grep -qF "badge/JOIDY-v${VERSION_CLEAN}-blue" README.md; then
        vok "README badge"
    else
        vfail "README.md: missing 'badge/JOIDY-v$VERSION_CLEAN-blue'"
    fi

    # docs metadata version fields.
    for f in docs/index.md docs/api.md docs/architecture.md docs/troubleshooting.md; do
        if [ -f "$f" ] && grep -qE "^version: +${V_ERE}([[:space:]]*)$" "$f"; then
            vok "$f version"
        else
            vfail "$f: missing 'version: $VERSION_CLEAN'"
        fi
    done

    # Pinned installer URLs — every concrete ref must be the release tag;
    # template refs like ${TAG} are intentionally preserved.
    refs="$(grep -ohE 'joidy/[^/${}]+/scripts/install\.(sh|ps1)' \
        README.md INSTALL.md scripts/install.sh scripts/install.ps1 2>/dev/null \
        | sed 's|^joidy/||; s|/scripts/install\..*||' | sort -u || true)"
    if [ -z "$refs" ]; then
        vfail "installer URLs: none found in README.md/INSTALL.md/scripts/install.*"
    else
        bad="$(printf '%s\n' "$refs" | grep -vxF "v${VERSION_CLEAN}" | grep -vxF '${TAG}' | grep -v '^$' || true)"
        if [ -z "$bad" ]; then
            vok "installer URLs pinned to v$VERSION_CLEAN"
        else
            vfail "installer URL refs not at v$VERSION_CLEAN: $(printf '%s' "$bad" | tr '\n' ' ')"
        fi
    fi

    # CHANGELOG [unreleased] compare link.
    if grep -qE "^\[unreleased\]: .*compare/v${V_ERE}\.\.\.HEAD" CHANGELOG.md; then
        vok "CHANGELOG compare link"
    else
        vfail "CHANGELOG.md: [unreleased] compare link does not point at v$VERSION_CLEAN"
    fi

    if [ "$errors" -eq 0 ]; then
        info "all versioned files consistent with $VERSION_TAG"
        return 0
    fi
    die "$errors version check(s) failed for $VERSION_TAG"
}

# --- dry-run ------------------------------------------------------------------
# Exercise the real bump on a scratch copy of the tracked files (node_modules,
# .env, data/ are untracked and excluded). Proves the whole pipeline —
# including makepkg — without touching the working tree.
dry_run() {
    command -v git >/dev/null 2>&1 || die "--dry-run requires git"
    # Not local: the EXIT trap must still see it after this function returns.
    # Eager expansion is intended — mktemp paths contain no spaces.
    tmp="$(mktemp -d)"
    # shellcheck disable=SC2064
    trap "rm -rf $tmp" EXIT
    mkdir -p "$tmp/orig" "$tmp/work"
    (cd "$ROOT" && git ls-files -z | tar --null --files-from=- -cf -) | tar -xf - -C "$tmp/orig"
    cp -a "$tmp/orig/." "$tmp/work/"
    # The script itself may be uncommitted — always copy it in.
    mkdir -p "$tmp/work/scripts"
    cp "$SCRIPT_DIR/release_bump.sh" "$tmp/work/scripts/release_bump.sh"
    chmod +x "$tmp/work/scripts/release_bump.sh"

    info "dry-run: exercising bump of $VERSION_TAG on a scratch copy"
    if ! (cd "$tmp/work" && bash scripts/release_bump.sh "$VERSION_INPUT"); then
        die "dry-run: bump failed on the scratch copy"
    fi
    info "dry-run: files that would change:"
    diff -rq "$tmp/orig" "$tmp/work" | sed "s|$tmp/||g" || true
    info "dry-run OK — bump verified on scratch copy; repo untouched"
}

# --- main ---------------------------------------------------------------------
case "$MODE" in
    check)
        verify_version
        ;;
    bump)
        bump_all
        verify_version
        ;;
    dry-run)
        dry_run
        ;;
esac
