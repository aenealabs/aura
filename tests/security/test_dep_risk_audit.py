"""Tests for scripts/security/dep_risk_audit.py.

Focused on the parser that #162 fixed: `_watch_tier_packages` now reads
the register's Surface column to dispatch staleness checks correctly.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from scripts.security.dep_risk_audit import _watch_tier_packages


def _write_register(tmp_path: Path, body: str) -> Path:
    register = tmp_path / "DEPENDENCY_RISK_REGISTER.md"
    register.write_text(textwrap.dedent(body).lstrip("\n"))
    return register


def test_watch_tier_packages_returns_name_and_surface(tmp_path: Path) -> None:
    register = _write_register(
        tmp_path,
        """
        # Register

        ## At-Risk and Replace-Now Items (act on these)

        | Package | Surface | Tier | Reason | Mitigation |
        | --- | --- | --- | --- | --- |
        | `gremlinpython` | Python (API runtime) | **At-Risk** | reason | mitigation |
        | `eslint-plugin-react` | Frontend (devDep) | **At-Risk** | reason | mitigation |
        | `pptxgenjs` | Frontend (runtime) | **Watch** | reason | mitigation |

        ## Healthy Tier
        """,
    )

    rows = _watch_tier_packages(register)

    assert rows == [
        ("gremlinpython", "Python (API runtime)"),
        ("eslint-plugin-react", "Frontend (devDep)"),
        ("pptxgenjs", "Frontend (runtime)"),
    ]


def test_watch_tier_packages_handles_missing_register(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.md"
    assert _watch_tier_packages(missing) == []


def test_watch_tier_packages_handles_register_without_anchor(tmp_path: Path) -> None:
    register = _write_register(
        tmp_path,
        """
        # Register

        ## Healthy Tier

        Nothing to track.
        """,
    )
    assert _watch_tier_packages(register) == []


def test_watch_tier_packages_skips_header_and_separator_rows(tmp_path: Path) -> None:
    """Header row "| Package | Surface | ..." has no backticks; separator
    row "| --- | --- | ..." starts with `---`. Both must be filtered."""
    register = _write_register(
        tmp_path,
        """
        # Register

        ## At-Risk and Replace-Now Items

        | Package | Surface | Tier |
        | --- | --- | --- |
        | `only-real-row` | Python (runtime) | **Watch** |
        """,
    )

    rows = _watch_tier_packages(register)

    assert rows == [("only-real-row", "Python (runtime)")]


def test_watch_tier_packages_stops_at_next_section(tmp_path: Path) -> None:
    """The parser slices on `\\n## ` to bound the table. Any subsequent
    `## ` heading must terminate parsing, not bleed in."""
    register = _write_register(
        tmp_path,
        """
        # Register

        ## At-Risk and Replace-Now Items

        | Package | Surface | Tier |
        | --- | --- | --- |
        | `inside-table` | Frontend (runtime) | **Watch** |

        ## Some Other Section

        | should-not-appear | x | y |
        """,
    )

    rows = _watch_tier_packages(register)

    assert rows == [("inside-table", "Frontend (runtime)")]


def test_watch_tier_packages_handles_github_action_surface(tmp_path: Path) -> None:
    """GitHub Action entries are tracked by SHA pinning, not staleness;
    they should still be returned by the parser (the dispatcher in main()
    decides what to skip). The parser is purely a parser."""
    register = _write_register(
        tmp_path,
        """
        # Register

        ## At-Risk and Replace-Now Items

        | Package | Surface | Tier |
        | --- | --- | --- |
        | `tj-actions/changed-files` | GitHub Action | **At-Risk** |
        """,
    )

    rows = _watch_tier_packages(register)

    assert rows == [("tj-actions/changed-files", "GitHub Action")]
