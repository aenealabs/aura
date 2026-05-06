"""Enforce that buildspec image builds pass --build-arg for the base image.

Per the CLAUDE.md container-security mandate, every CI/CD container build MUST
override the public-registry defaults baked into Dockerfiles. The 2026-05-06
audit found this rule was unenforced: a buildspec that forgot --build-arg
would silently produce production images from public.ecr.aws / docker.io.

This script scans `deploy/buildspecs/*.yml` for `docker build` and
`podman build` invocations and asserts each one supplies a `--build-arg
*_BASE_IMAGE*=...` flag whose value does not point at a public registry.

Exit codes:
    0  All builds in scope are compliant.
    1  At least one build is missing --build-arg or uses a public source.
    2  Buildspec directory not found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILDSPEC_DIR = REPO_ROOT / "deploy" / "buildspecs"

PUBLIC_REGISTRY_PATTERNS = (
    "public.ecr.aws",
    "docker.io",
    "ghcr.io",
    "nvcr.io",
    "quay.io",
)

BUILD_COMMAND = re.compile(r"\b(?:docker|podman)\s+build\b")
BUILD_ARG = re.compile(r"--build-arg\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s\\]+)")


def extract_build_blocks(text: str) -> list[tuple[int, str]]:
    """Return (start_line, command_text) for each docker/podman build invocation.

    A "build block" is a contiguous run of lines starting with the `docker
    build` (or `podman build`) line and continuing through trailing
    backslash-continuations. Blocks are terminated by a non-continued line.
    """
    blocks: list[tuple[int, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if BUILD_COMMAND.search(lines[i]):
            start = i
            chunk: list[str] = [lines[i]]
            while chunk[-1].rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                chunk.append(lines[i])
            blocks.append((start + 1, "\n".join(chunk)))
        i += 1
    return blocks


def evaluate_block(block: str, surrounding: str) -> tuple[bool, str]:
    """Return (ok, reason) for a single build block.

    `surrounding` is the buildspec text preceding the block (within ~80 lines)
    so we can recognize a buildspec that exports BASE_IMAGE_ARG/URI into the
    build invocation indirectly (e.g., through ``$BUILD_ARGS``) and validates
    them with a fail-fast guard.
    """
    args = dict(BUILD_ARG.findall(block))
    base_args = {k: v for k, v in args.items() if "BASE_IMAGE" in k.upper()}
    indirect_via_build_args = "$BUILD_ARGS" in block or "${BUILD_ARGS}" in block
    has_failfast_guard = (
        "BASE_IMAGE_ARG" in surrounding
        and "BASE_IMAGE_URI" in surrounding
        and "exit 1" in surrounding
        and "public.ecr.aws" in surrounding
    )
    if not base_args:
        if indirect_via_build_args and has_failfast_guard:
            return True, "ok (indirect via $BUILD_ARGS with fail-fast guard)"
        return False, "no --build-arg *_BASE_IMAGE provided"
    for name, value in base_args.items():
        if value.startswith("$"):
            continue
        for public in PUBLIC_REGISTRY_PATTERNS:
            if public in value:
                return False, f"{name}={value} points at public registry ({public})"
    return True, "ok"


def main() -> int:
    if not BUILDSPEC_DIR.is_dir():
        print(f"ERROR: {BUILDSPEC_DIR} not found", file=sys.stderr)
        return 2

    failures: list[tuple[Path, int, str]] = []
    inspected = 0
    for spec in sorted(BUILDSPEC_DIR.glob("*.yml")):
        text = spec.read_text(encoding="utf-8")
        all_lines = text.splitlines()
        for line, block in extract_build_blocks(text):
            inspected += 1
            window_start = max(0, line - 80)
            surrounding = "\n".join(all_lines[window_start : line - 1])
            ok, reason = evaluate_block(block, surrounding)
            if not ok:
                failures.append((spec, line, reason))

    if not failures:
        print(f"OK: {inspected} build invocations compliant across {BUILDSPEC_DIR}")
        return 0

    print("BUILDSPEC --build-arg POLICY VIOLATIONS")
    print("-" * 80)
    for spec, line, reason in failures:
        rel = spec.relative_to(REPO_ROOT)
        print(f"{rel}:{line}: {reason}")
    print()
    print("Every CI/CD container build MUST pass --build-arg *_BASE_IMAGE=<private-ecr-uri>")
    print("(see CLAUDE.md > Container Security).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
