#!/usr/bin/env bash
# generate_sbom.sh — Generate SPDX-JSON + CycloneDX-JSON SBOMs for every
# distributed Joidy artifact (issue #1386).
#
# Modes:
#   source (default)  Scan each service directory. syft catalogs
#                     requirements.txt / package-lock.json directly. License
#                     metadata is sparse in this mode (manifest files carry
#                     no license fields), so use it for local previews only.
#   image             Scan the pushed Docker images
#                     (<image-prefix>/joidy-<service>:<tag>) — the exact
#                     object code we distribute. publish.yml uses this mode;
#                     licenses come from dist-info / package.json metadata
#                     inside the image.
#
# Usage:
#   scripts/generate_sbom.sh [--mode source|image]
#                            [--image-prefix <registry/namespace>]
#                            [--tag <image-tag>]
#                            [--scheme <syft-source-scheme>]
#                            [--service <name>]...     (default: all 4)
#                            [--out-dir <dir>]
#
# Tooling resolution (first match wins):
#   1. `syft` on $PATH
#   2. `docker run anchore/syft:v$SYFT_VERSION` when the Docker daemon is
#      reachable (source mode mounts the repo read-only, output dir rw)
#   3. Downloaded + sha256-verified syft release binary (linux/darwin,
#      amd64/arm64) into a temp dir — used in CI.
#
# Environment:
#   SYFT_VERSION    Pinned tool version. Default: 1.57.2
#   SYFT_PLATFORM   Override auto-detected <os>_<arch> (e.g. linux_amd64).
#   IMAGE_PREFIX    Default registry/namespace for --mode image (d4mag3).
#   IMAGE_TAG       Default tag for --mode image (latest).

set -euo pipefail

SYFT_VERSION="${SYFT_VERSION:-1.57.2}"
MODE="source"
IMAGE_PREFIX="${IMAGE_PREFIX:-d4mag3}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SCHEME=""                 # empty → dir: for source, registry: for image
OUT_DIR="sbom"
SERVICES=(api ai-service worker frontend)
SERVICES_OVERRIDE=()

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "::error::$*" >&2; exit 1; }
# Progress goes to stderr so stdout stays usable for machine-readable output.
info() { echo "==> $*" >&2; }

usage() { sed -n '2,32p' "$0"; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --mode)         MODE="$2"; shift 2 ;;
        --image-prefix) IMAGE_PREFIX="$2"; shift 2 ;;
        --tag)          IMAGE_TAG="$2"; shift 2 ;;
        --scheme)       SCHEME="$2"; shift 2 ;;
        --service)      SERVICES_OVERRIDE+=("$2"); shift 2 ;;   # repeatable
        --out-dir)      OUT_DIR="$2"; shift 2 ;;
        -h|--help)      usage 0 ;;
        *)              die "unknown argument: $1 (try --help)" ;;
    esac
done

if [ ${#SERVICES_OVERRIDE[@]} -gt 0 ]; then
    SERVICES=("${SERVICES_OVERRIDE[@]}")
fi

case "$MODE" in
    source|image) ;;
    *) die "invalid --mode '$MODE' (expected: source|image)" ;;
esac

OUT_ABS="$(cd "$REPO_ROOT" && mkdir -p "$OUT_DIR" && cd "$OUT_DIR" && pwd)"

# ── Resolve syft ─────────────────────────────────────────────────────────────
SYFT=()
USE_DOCKER=0
SYFT_TMP=""

sha256_verify() {
    # Reads "<sha256>  <file>" lines on stdin, verifies them against cwd.
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c -
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c -
    else
        die "no sha256 checksum tool available (need sha256sum or shasum)"
    fi
}

install_syft() {
    # Download the pinned release binary and verify it against the signed
    # checksums manifest published in the same GitHub release.
    local os arch plat tmp url tarball
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"      # linux | darwin
    arch="$(uname -m)"
    case "$arch" in
        x86_64|amd64)   arch="amd64" ;;
        aarch64|arm64)  arch="arm64" ;;
        *) die "unsupported architecture: $arch" ;;
    esac
    plat="${SYFT_PLATFORM:-${os}_${arch}}"
    url="https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}"
    tmp="$(mktemp -d)"
    SYFT_TMP="$tmp"
    trap 'rm -rf "$SYFT_TMP"' EXIT
    info "Installing syft v${SYFT_VERSION} (${plat})"
    # Keep the real release filename: sha256sum -c resolves entries relative
    # to cwd inside the checksum manifest.
    tarball="syft_${SYFT_VERSION}_${plat}.tar.gz"
    curl -fsSL -o "$tmp/$tarball"       "$url/$tarball"
    curl -fsSL -o "$tmp/checksums.txt"  "$url/syft_${SYFT_VERSION}_checksums.txt"
    (cd "$tmp" && grep " ${tarball}\$" checksums.txt | sha256_verify)
    tar -xzf "$tmp/$tarball" -C "$tmp" syft
    # Returned via global — a command substitution would swallow set -e
    # failures inside this function and continue with an empty path.
    SYFT_BIN="$tmp/syft"
}

if command -v syft >/dev/null 2>&1; then
    SYFT=(syft)
    info "Using syft from PATH: $(syft version | head -1)"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    USE_DOCKER=1
    info "Using syft via docker image anchore/syft:v${SYFT_VERSION}"
else
    install_syft
    SYFT=("$SYFT_BIN")
fi

# ── Generate ─────────────────────────────────────────────────────────────────
# $1 = syft source (dir:api | registry:img | docker:img), $2 = output basename
syft_scan() {
    local src="$1" name="$2"
    info "Scanning ${src} → ${name}.{spdx,cdx}.json"
    if [ "$USE_DOCKER" = "1" ]; then
        docker run --rm --user "$(id -u):$(id -g)" \
            -v "$REPO_ROOT:/src:ro" -v "$OUT_ABS:/out:rw" -w /src \
            "anchore/syft:v${SYFT_VERSION}" \
            "$src" \
            -o "spdx-json=/out/${name}.spdx.json" \
            -o "cyclonedx-json=/out/${name}.cdx.json"
    else
        "${SYFT[@]}" "$src" \
            -o "spdx-json=${OUT_ABS}/${name}.spdx.json" \
            -o "cyclonedx-json=${OUT_ABS}/${name}.cdx.json"
    fi
}

for svc in "${SERVICES[@]}"; do
    if [ "$MODE" = "source" ]; then
        [ -d "$REPO_ROOT/$svc" ] || die "service directory not found: $svc"
        syft_scan "${SCHEME:-dir:}${svc}" "joidy-${svc}"
    else
        syft_scan "${SCHEME:-registry:}${IMAGE_PREFIX}/joidy-${svc}:${IMAGE_TAG}" "joidy-${svc}"
    fi
done

info "Done. SBOMs written to ${OUT_ABS}"
ls -la "$OUT_ABS"
