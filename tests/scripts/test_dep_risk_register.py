"""Tests for the shared dependency-risk-register parser.

``dep_risk_register`` replaces two independent, hand-rolled parsers of
``docs/security/DEPENDENCY_RISK_REGISTER.md`` -- one in
``dep_triage_collect.py``, one in ``dep_risk_audit.py`` -- that happened to
agree only by luck. The golden test at the bottom of this file is the one
that would have caught the original defect: a markdown-parsing bug dropped
`image-size` from the register's At-Risk holds, and it went unnoticed until a
human review caught it, because an empty (or wrong) tier map reads exactly
like "nothing is held". Fixture-based tests exercise edge cases in isolation;
this one reads the real document so it fails the moment the document's shape
changes underneath the parser.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.security import dep_risk_register as reg

LIVE_REGISTER = Path("docs/security/DEPENDENCY_RISK_REGISTER.md")


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------


def test_normalize_pip_is_pep_503():
    """PEP 503: lowercase, runs of -_. collapsed to a single -."""
    assert reg.normalize_pip("Pillow") == "pillow"
    assert reg.normalize_pip("nest_asyncio") == "nest-asyncio"
    assert reg.normalize_pip("nest-asyncio") == "nest-asyncio"
    assert reg.normalize_pip("Foo..Bar__Baz") == "foo-bar-baz"


def test_normalize_npm_is_lowercase_only():
    assert reg.normalize_npm("Eslint-Plugin-React") == "eslint-plugin-react"
    assert reg.normalize_npm("pptxgenjs") == "pptxgenjs"


def test_normalize_package_dispatches_by_ecosystem():
    assert reg.normalize_package("pip", "Nest_Asyncio") == "nest-asyncio"
    assert reg.normalize_package("npm", "ESLint-Plugin-React") == "eslint-plugin-react"


def test_normalize_package_falls_back_to_bare_lowercase_for_other_ecosystems():
    """github-actions packages are owner/repo slugs never looked up in the
    register by name; docker/unknown carry no register entries either. Both
    fall back to a bare lowercase rather than raising, since the only
    consequence is a lookup that will not find a register row."""
    assert reg.normalize_package("github-actions", "Owner/Repo") == "owner/repo"
    assert reg.normalize_package("docker", "Some-Image") == "some-image"


# --------------------------------------------------------------------------
# load_register: fail-loud behaviour
# --------------------------------------------------------------------------


def test_load_register_raises_when_file_missing(tmp_path):
    with pytest.raises(reg.RegisterFormatError, match="not found"):
        reg.load_register(tmp_path / "absent.md")


def test_load_register_raises_when_no_table_has_both_columns(tmp_path):
    register = tmp_path / "register.md"
    register.write_text("# Register\n\nNo tables here.\n", encoding="utf-8")
    with pytest.raises(reg.RegisterFormatError, match="no table with both"):
        reg.load_register(register)


def test_load_register_does_not_mistake_the_tier_definition_table_for_data(
    tmp_path,
):
    """The register's own 'Risk Tiering' table (`| Tier | Definition |
    Action |`) has a column literally named 'Tier' too, but its rows define
    what Healthy/Watch/At-Risk/Replace-Now *mean* -- they are not package
    rows. A parser that keys on 'Tier' alone reads that table as four
    packages named 'healthy', 'watch', etc. Requiring a 'Package' column as
    well is what tells the two tables apart. This is a regression test: an
    earlier draft of this exact parser had precisely this bug."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "## Risk Tiering\n\n"
        "| Tier | Definition | Action |\n"
        "| --- | --- | --- |\n"
        "| **Healthy** | corporate backing | no action |\n"
        "| **At-Risk** | visible long-term risk | pin precisely |\n\n"
        "## At-Risk and Replace-Now Items\n\n"
        "| Package | Surface | Tier | Reason | Mitigation |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| `gremlinpython` | Python (API runtime) | **At-Risk** | r | m |\n",
        encoding="utf-8",
    )
    rows = reg.load_register(register)
    names = {row.name for row in rows}
    assert names == {"gremlinpython"}
    assert "healthy" not in names
    assert "at-risk" not in names


def test_load_register_locates_columns_by_name_not_position(tmp_path):
    """Inserting a column before Tier must not disarm the parse -- the
    defect this fix closes. The prior version hardcoded `cells[2]`, so an
    inserted 'Owner' column would have silently made every At-Risk hold
    disappear with no error."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Owner | Surface | Tier | Reason |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| `gremlinpython` | Platform Eng | Python (API runtime) | **At-Risk** | r |\n",
        encoding="utf-8",
    )
    rows = reg.load_register(register)
    assert len(rows) == 1
    assert rows[0].name == "gremlinpython"
    assert rows[0].tier == "at-risk"


def test_row_name_extracts_first_backticked_token_from_annotated_cell(tmp_path):
    """ "`image-size` (via `pptxgenjs`)" must resolve to `image-size`, not to
    the whole cell with backticks stripped (which yields garbage like
    "image-size` (via `pptxgenjs")."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `image-size` (via `pptxgenjs`) | Frontend | **At-Risk** |\n",
        encoding="utf-8",
    )
    rows = reg.load_register(register)
    assert rows[0].name == "image-size"


# --------------------------------------------------------------------------
# tiers_by_package: ecosystem-aware normalization
# --------------------------------------------------------------------------


def test_tiers_by_package_normalizes_keys_per_ecosystem(tmp_path):
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `Nest_Asyncio` | Python (API runtime) | **At-Risk** |\n"
        "| `ESLint-Plugin-React` | Frontend (devDep) | **At-Risk** |\n",
        encoding="utf-8",
    )
    tiers = reg.tiers_by_package(reg.load_register(register))
    assert tiers["nest-asyncio"] == "at-risk"
    assert tiers["eslint-plugin-react"] == "at-risk"


def test_tiers_by_package_drops_rows_with_an_unrecognized_tier_value(tmp_path):
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `foo` | Python (API runtime) | **Deprecated** |\n",
        encoding="utf-8",
    )
    tiers = reg.tiers_by_package(reg.load_register(register))
    assert tiers == {}


def test_load_risk_tiers_raises_on_missing_register(tmp_path):
    with pytest.raises(reg.RegisterFormatError):
        reg.load_risk_tiers(tmp_path / "absent.md")


def test_load_risk_tiers_raises_when_rows_exist_but_no_tier_value_is_valid(
    tmp_path,
):
    """A table can have both 'Package' and 'Tier' columns -- so
    ``load_register`` returns rows -- and still yield zero holds if every
    Tier cell is something other than the register's own four defined
    values (a typo, a placeholder). That must fail the same way an entirely
    missing register does, not silently disarm every hold."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `foo` | Python (API runtime) | **Deprecated** |\n",
        encoding="utf-8",
    )
    with pytest.raises(reg.RegisterFormatError, match="zero package"):
        reg.load_risk_tiers(register)


def test_tiers_by_package_normalizes_github_action_rows(tmp_path):
    """A 'GitHub Action' Surface value routes through the github-actions
    branch of `_ecosystem_of_surface`, which normalize_package then falls
    back to a bare lowercase for -- there is no dedicated github-actions
    normalizer, since those packages are owner/repo slugs never looked up
    in the register by name today."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `Owner/Repo` | GitHub Action | **At-Risk** |\n",
        encoding="utf-8",
    )
    tiers = reg.tiers_by_package(reg.load_register(register))
    assert tiers == {"owner/repo": "at-risk"}


def test_ecosystem_of_surface_unrecognized_prefix_falls_back_to_unknown(tmp_path):
    """A Surface value this repo has not seen yet (an 'Infra' row, say) must
    not raise or silently drop the row -- it normalizes as a bare lowercase,
    which only affects a lookup that will not find a register row, which is
    the conservative direction."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `some-tool` | Infra (build-time) | **Watch** |\n",
        encoding="utf-8",
    )
    tiers = reg.tiers_by_package(reg.load_register(register))
    assert tiers == {"some-tool": "watch"}


# --------------------------------------------------------------------------
# tracked_surface_rows: dep_risk_audit's staleness dispatch
# --------------------------------------------------------------------------


def test_tracked_surface_rows_returns_raw_unnormalized_names(tmp_path):
    """Names here are passed straight to `pip show` / `npm view`, which
    accept the register's own spelling fine -- normalizing them would be
    pointless and would not match what dep_risk_audit's tests expect."""
    register = tmp_path / "register.md"
    register.write_text(
        "# Register\n\n"
        "| Package | Surface | Tier |\n"
        "| --- | --- | --- |\n"
        "| `ESLint-Plugin-React` | Frontend (devDep) | **At-Risk** |\n",
        encoding="utf-8",
    )
    rows = reg.tracked_surface_rows(reg.load_register(register))
    assert rows == [("ESLint-Plugin-React", "Frontend (devDep)")]


# --------------------------------------------------------------------------
# Golden test against the live register -- not a fixture.
# --------------------------------------------------------------------------


def test_golden_live_register_holds_the_known_at_risk_and_watch_packages():
    """Parses the real `docs/security/DEPENDENCY_RISK_REGISTER.md`, not a
    fixture, and pins the packages this project's own review process has
    already confirmed must be held: `image-size`, `gremlinpython` and
    `eslint-plugin-react` at `at-risk`, and `pptxgenjs` at `watch`.

    This is the test that would have caught the original defect -- a
    fixture cannot drift out of sync with the document it is supposed to
    stand in for, but a fixture also cannot notice when the real document's
    shape changes under the parser. Reading the live file means this test
    fails, rather than staying silently green, the moment that happens.
    """
    tiers = reg.load_risk_tiers(LIVE_REGISTER)
    assert tiers["image-size"] == "at-risk"
    assert tiers["gremlinpython"] == "at-risk"
    assert tiers["eslint-plugin-react"] == "at-risk"
    assert tiers["pptxgenjs"] == "watch"
