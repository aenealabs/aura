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
    """Return the set of content lines added by a unified diff.

    Two details are load-bearing, because this set is what decides whether a
    consolidation branch carries anything its member pull requests did not.

    Indentation is preserved. Only trailing whitespace is stripped. In YAML --
    which is what these consolidations mostly touch -- indentation is
    semantics, so the same text at a different depth is a different change, and
    comparing without it would accept a line relocated into another scope as
    identical to the reviewed one.

    The `+++ b/path` file header is recognised by its position, not its prefix:
    it counts as a header only when it directly follows the matching `--- a/path`
    line. Matching the `+++` prefix anywhere would also swallow a genuine added
    line whose own content begins with `++`, making an unreviewed addition
    invisible rather than reporting it as extra.
    """
    out: set[str] = set()
    previous = ""
    for line in diff.splitlines():
        if line.startswith("+++") and previous.startswith("---"):
            previous = line
            continue
        if line.startswith("+"):
            content = line[1:].rstrip()
            if content:
                out.add(content)
        previous = line
    return out


def verify_union(
    member_diffs: list[str], combined_diff: str
) -> tuple[bool, set[str], set[str]]:
    """Check a consolidation diff equals the union of its members' additions.

    Returns (ok, missing, extra). ``missing`` are member additions absent from
    the consolidation; ``extra`` are additions present in the consolidation that
    no member PR introduced.

    Comparison is by set, so byte-identical duplicate additions collapse. That
    weakens only the ``missing`` side -- re-adding already-approved text
    introduces no new unreviewed content -- so the security-relevant ``extra``
    side is unaffected.
    """
    expected: set[str] = set()
    for diff in member_diffs:
        expected |= added_lines(diff)
    actual = added_lines(combined_diff)
    missing = expected - actual
    extra = actual - expected
    return (not missing and not extra, missing, extra)


def branch_name(family: str, version: str) -> str:
    """Build the consolidation branch name for a family and target version.

    Only ``family`` is slugified; ``version`` is assumed to already be a plain
    release identifier as parsed from a bump title.
    """
    slug = _SLUG.sub("-", family.lower()).strip("-")
    return f"dep-consolidate/{slug}-{version}"
