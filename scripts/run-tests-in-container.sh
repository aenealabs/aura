#!/usr/bin/env bash
# Project Aura - Run pytest inside the Linux test-harness container.
#
# Wraps the build+run cycle for ``deploy/docker/test-harness/`` so the
# developer doesn't have to remember the flag set. Closes the ~6,576
# macOS-fork test skips (see the Dockerfile header for the full skip
# accounting).
#
# Usage:
#   scripts/run-tests-in-container.sh                 # full suite, -q
#   scripts/run-tests-in-container.sh tests/test_x.py # subset
#   scripts/run-tests-in-container.sh -- pytest -k auth -v  # custom pytest args
#   scripts/run-tests-in-container.sh --rebuild       # force image rebuild
#   scripts/run-tests-in-container.sh --shell         # drop into bash
#
# Environment:
#   AURA_TEST_HARNESS_RUNTIME     override (default: ``podman``, falls
#                                 back to ``docker`` if podman missing)
#   AURA_TEST_HARNESS_IMAGE       override image tag (default
#                                 ``aura/test-harness:latest``)
#   AURA_TEST_HARNESS_PLATFORM    override (default ``linux/amd64``)
#   AURA_TEST_HARNESS_BASE_IMAGE  override the FROM base image at
#                                 build time. REQUIRED in CI (the
#                                 script refuses to run without it
#                                 when ``CI=true``). Local dev can
#                                 leave it unset to get the public
#                                 ECR Gallery default.
#                                 Format example:
#                                 <account>.dkr.ecr.<region>.amazonaws.com/aura-base-images/python:3.12-slim@sha256:...

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RUNTIME="${AURA_TEST_HARNESS_RUNTIME:-}"
if [[ -z "$RUNTIME" ]]; then
    if command -v podman >/dev/null 2>&1; then
        RUNTIME="podman"
    elif command -v docker >/dev/null 2>&1; then
        RUNTIME="docker"
    else
        echo "Error: neither podman nor docker is installed." >&2
        echo "Install Podman (recommended per ADR-049) or Docker, then retry." >&2
        exit 2
    fi
fi

IMAGE="${AURA_TEST_HARNESS_IMAGE:-aura/test-harness:latest}"
PLATFORM="${AURA_TEST_HARNESS_PLATFORM:-linux/amd64}"
DOCKERFILE="deploy/docker/test-harness/Dockerfile.test-harness"

# CI guard: this harness defaults to a public ECR Gallery base image
# (acceptable for per-dev local builds; see issue #195 for the Phase 2
# promotion to private ECR). In any CI environment, the caller MUST
# override ``PYTHON_BASE_IMAGE`` with a private ECR digest so the
# harness picks up the hardened, vulnerability-scanned base instead
# of pulling unvetted public artifacts. Fail-fast if that didn't
# happen.
if [[ -n "${CI:-}" ]] && [[ -z "${AURA_TEST_HARNESS_BASE_IMAGE:-}" ]]; then
    echo "Error: CI runs must set AURA_TEST_HARNESS_BASE_IMAGE to a private ECR digest." >&2
    echo "       Expected format: <account>.dkr.ecr.<region>.amazonaws.com/aura-base-images/python:3.12-slim@sha256:..." >&2
    echo "       See issue #195 for the Phase 2 promotion plan." >&2
    exit 2
fi

REBUILD=0
SHELL_MODE=0
PYTEST_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rebuild) REBUILD=1; shift ;;
        --shell)   SHELL_MODE=1; shift ;;
        --)        shift; PYTEST_ARGS+=("$@"); break ;;
        -h|--help)
            sed -n '2,20p' "$0"
            exit 0
            ;;
        *) PYTEST_ARGS+=("$1"); shift ;;
    esac
done

image_exists() {
    "$RUNTIME" image inspect "$IMAGE" >/dev/null 2>&1
}

if [[ $REBUILD -eq 1 ]] || ! image_exists; then
    echo "==> Building $IMAGE via $RUNTIME ($PLATFORM)"
    BUILD_ARGS=()
    if [[ -n "${AURA_TEST_HARNESS_BASE_IMAGE:-}" ]]; then
        BUILD_ARGS+=(--build-arg "PYTHON_BASE_IMAGE=${AURA_TEST_HARNESS_BASE_IMAGE}")
    fi
    "$RUNTIME" build \
        --platform "$PLATFORM" \
        -f "$DOCKERFILE" \
        "${BUILD_ARGS[@]}" \
        -t "$IMAGE" \
        "$REPO_ROOT"
fi

# Mount the repo read-only by default (issue #195 P4). A compromised
# wheel or misbehaving test can't rewrite ``.git/hooks/``, source files,
# or any other on-disk state. Pytest's writable paths
# (``.pytest_cache``, coverage outputs, ``tmp_path`` roots) get tmpfs
# mounts so they remain functional and isolated to the container's
# lifetime. The ``--shell`` mode keeps RW because interactive debug
# sessions often need to edit / install / scratch-write inside the
# container; the production pytest path stays read-only.
#
# SELinux relabel suffix is harmless on macOS / non-SELinux Linux.
MOUNT_OPTS=":ro,Z"
if [[ "$(uname -s)" == "Darwin" ]]; then
    MOUNT_OPTS=":ro"  # no relabel needed; ``:Z`` confuses some Podman Machine versions
fi

# Shell mode: keep RW because the user is interactively debugging and
# will need to write scratch files / install ad-hoc packages.
if [[ $SHELL_MODE -eq 1 ]]; then
    SHELL_MOUNT_OPTS="${MOUNT_OPTS//:ro/}"
    SHELL_MOUNT_OPTS="${SHELL_MOUNT_OPTS//,,/,}"
    SHELL_MOUNT_OPTS="${SHELL_MOUNT_OPTS#:,}"  # strip leading comma if any
    [[ -z "$SHELL_MOUNT_OPTS" || "$SHELL_MOUNT_OPTS" == ":" ]] && SHELL_MOUNT_OPTS=""
    echo "==> Dropping into bash in $IMAGE (RW mount for interactive use)"
    exec "$RUNTIME" run --rm \
        --platform "$PLATFORM" \
        -v "${REPO_ROOT}:/workspace${SHELL_MOUNT_OPTS}" \
        -w /workspace \
        -e PYTHONDONTWRITEBYTECODE=1 \
        -e PYTHONUNBUFFERED=1 \
        -it "$IMAGE" /bin/bash
fi

# Read-only RUN_ARGS with tmpfs for pytest write paths.
#
# Layout:
#   /workspace          -- repo bind-mount, READ-ONLY
#   /tmp                -- tmpfs, 2GB, exec-enabled (pytest tmp_path
#                          uses this; needs exec for compiled extension
#                          loading some tests do)
#   /home/aura/.cache   -- tmpfs, 512MB (pip user-config, matplotlib
#                          cache, etc. -- anything writing to $HOME)
#
# Pytest writes (``.pytest_cache``, coverage XML, junit, etc.) get
# redirected to ``/tmp`` via the explicit ``-o cache_dir`` override
# below. Tmpfs-mounting over a sub-path of a RO bind-mount works on
# Linux but is undocumented behavior; routing pytest's writes to a
# top-level tmpfs is cleaner and works the same on macOS Podman
# Machine where the over-mount trick is flaky.
RUN_ARGS=(
    run --rm
    --platform "$PLATFORM"
    -v "${REPO_ROOT}:/workspace${MOUNT_OPTS}"
    -w /workspace
    --tmpfs "/tmp:exec,size=2g,mode=1777"
    --tmpfs "/home/aura/.cache:size=512m,mode=1777"
    -e PYTHONDONTWRITEBYTECODE=1
    -e PYTHONUNBUFFERED=1
    -e PYTEST_DEBUG_TEMPROOT=/tmp
)

# Default command is ``pytest --no-cov -q``; the user can append extra
# args or pass ``--`` followed by a completely custom command.
# ``-o cache_dir=/tmp/.pytest_cache`` routes pytest's cache to the
# writable tmpfs since ``/workspace`` is now RO (#195 P4).
if [[ ${#PYTEST_ARGS[@]} -eq 0 ]]; then
    CMD=(pytest -o "cache_dir=/tmp/.pytest_cache" --no-cov -q)
else
    CMD=(pytest -o "cache_dir=/tmp/.pytest_cache" --no-cov "${PYTEST_ARGS[@]}")
fi

echo "==> Running ${CMD[*]} in $IMAGE"
exec "$RUNTIME" "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}"
