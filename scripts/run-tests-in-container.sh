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
#   AURA_TEST_HARNESS_RUNTIME  override (default: ``podman``, falls
#                              back to ``docker`` if podman missing)
#   AURA_TEST_HARNESS_IMAGE    override image tag (default
#                              ``aura/test-harness:latest``)
#   AURA_TEST_HARNESS_PLATFORM override (default ``linux/amd64``)

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
    "$RUNTIME" build \
        --platform "$PLATFORM" \
        -f "$DOCKERFILE" \
        -t "$IMAGE" \
        "$REPO_ROOT"
fi

# SELinux relabel suffix is harmless on macOS / non-SELinux Linux.
MOUNT_OPTS=":Z"
if [[ "$(uname -s)" == "Darwin" ]]; then
    MOUNT_OPTS=""  # no relabel needed; ``:Z`` confuses some Podman Machine versions
fi

RUN_ARGS=(
    run --rm
    --platform "$PLATFORM"
    -v "${REPO_ROOT}:/workspace${MOUNT_OPTS}"
    -w /workspace
    -e PYTHONDONTWRITEBYTECODE=1
    -e PYTHONUNBUFFERED=1
)

if [[ $SHELL_MODE -eq 1 ]]; then
    echo "==> Dropping into bash in $IMAGE"
    exec "$RUNTIME" "${RUN_ARGS[@]}" -it "$IMAGE" /bin/bash
fi

# Default command is ``pytest --no-cov -q``; the user can append extra
# args or pass ``--`` followed by a completely custom command.
if [[ ${#PYTEST_ARGS[@]} -eq 0 ]]; then
    CMD=(pytest --no-cov -q)
else
    CMD=(pytest --no-cov "${PYTEST_ARGS[@]}")
fi

echo "==> Running ${CMD[*]} in $IMAGE"
exec "$RUNTIME" "${RUN_ARGS[@]}" "$IMAGE" "${CMD[@]}"
