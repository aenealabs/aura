"""Verification helpers for coupled-set consolidation.

When several Dependabot PRs must land together, the consolidation branch has to
contain exactly the union of their changes -- no more, no less. An extra added
line in a consolidation branch is an unreviewed change riding along with an
approved one, so the union check is a security control, not a convenience.
"""

from __future__ import annotations

import re

_SLUG = re.compile(r"[^a-z0-9.]+")


def added_lines(diff: str) -> set[str]:
    """Return the set of content lines added by a unified diff."""
    out: set[str] = set()
    for line in diff.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            stripped = line[1:].strip()
            if stripped:
                out.add(stripped)
    return out


def verify_union(
    member_diffs: list[str], combined_diff: str
) -> tuple[bool, set[str], set[str]]:
    """Check a consolidation diff equals the union of its members' additions.

    Returns (ok, missing, extra). ``missing`` are member additions absent from
    the consolidation; ``extra`` are additions present in the consolidation that
    no member PR introduced.
    """
    expected: set[str] = set()
    for diff in member_diffs:
        expected |= added_lines(diff)
    actual = added_lines(combined_diff)
    missing = expected - actual
    extra = actual - expected
    return (not missing and not extra, missing, extra)


def branch_name(family: str, version: str) -> str:
    """Build the consolidation branch name for a family and target version."""
    slug = _SLUG.sub("-", family.lower()).strip("-")
    return f"dep-consolidate/{slug}-{version}"
