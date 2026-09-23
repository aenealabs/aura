"""Shared parser for ``docs/security/DEPENDENCY_RISK_REGISTER.md``.

The register is a control input: ``dep_triage.rule_held_package`` refuses to
bump anything the register tiers At-Risk or Replace-Now, per the register's
own "pin precisely" mitigation. Two scripts used to read the file with two
independent, hand-rolled parsers -- ``dep_triage_collect._risk_tiers`` and
``dep_risk_audit._watch_tier_packages`` -- that happened to agree only by
luck, and only one of them enforced the hold. That is the same class of
hazard as having no parser at all: a markdown-parsing bug in one of them
already dropped ``image-size`` -- At-Risk with two unpatched CVEs -- so the
hold never fired, and it went unnoticed until a review caught it. This module
is the one parser both scripts import instead.

Two further weaknesses in the parser that dropped ``image-size`` are fixed
here, not just relocated:

* It hardcoded the tier's column position (``cells[2]``). Inserting a column
  before it -- an "Owner" column, say -- would have silently made every
  At-Risk hold disappear with no error. This parser reads the header row of
  each table and locates ``Tier`` (and any other column it needs) by name, so
  a reordered or widened table keeps working and a table that drops the
  column entirely raises instead of quietly returning fewer entries.
* Lookup was exact-string against a package name parsed from a PR title:
  ``Pillow`` vs ``pillow``, ``nest_asyncio`` vs ``nest-asyncio`` would miss.
  ``normalize_package`` runs both the register's key and the PR's package
  name through the same PEP 503 (pip) / lowercase (npm) normalization so they
  cannot drift apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Matches the first backticked token in a table cell, e.g. the `image-size`
# in "`image-size` (via `pptxgenjs`)". Some register rows annotate the name
# cell with its transitive source in the same cell, so the package name is
# never assumed to be the entire cell's stripped text.
_FIRST_BACKTICKED = re.compile(r"`([^`]+)`")

# A markdown table separator row, e.g. "| --- | :--- | ---: |".
_SEPARATOR_CELL = re.compile(r":?-{2,}:?")

# PEP 503 normalization: lowercase, and any run of -, _, or . collapsed to a
# single "-". This is the pip ecosystem's own canonical form (the same rule
# `pip install` and PyPI's simple index use), so "nest_asyncio" and
# "nest-asyncio" normalize to the same key.
_PEP503_RUN = re.compile(r"[-_.]+")

# Tier values the register's own Risk Tiering table defines. Anything else in
# a Tier cell (a typo, a placeholder) is not a tier this parser recognizes.
VALID_TIERS: frozenset[str] = frozenset({"at-risk", "replace-now", "watch", "healthy"})

# Tiers whose register entries say "pin precisely" -- kept here so both
# scripts' notion of "held" traces to one definition. dep_triage.py re-exports
# this rather than defining its own copy.
HELD_TIERS: frozenset[str] = frozenset({"at-risk", "replace-now"})


class RegisterFormatError(RuntimeError):
    """The register is missing, or no table in it yields usable rows.

    Raised rather than returning an empty result, in either case: an empty
    result is indistinguishable from "nothing is held", and that
    indistinguishability is exactly how the image-size hold went silently
    unenforced. Callers that can tolerate a missing register (dep_risk_audit's
    staleness check is best-effort, not a security control) catch this
    explicitly rather than receiving a silently empty list.
    """


def normalize_pip(name: str) -> str:
    """PEP 503 normalized form: lowercase, runs of ``-_.`` collapsed to ``-``."""
    return _PEP503_RUN.sub("-", name).lower()


def normalize_npm(name: str) -> str:
    """npm's own package-name canonical form is already lowercase; fold case
    defensively in case a title or register entry carries mixed case."""
    return name.lower()


def normalize_package(ecosystem: str, name: str) -> str:
    """Normalize a package name for register lookup, keyed by ecosystem.

    The register and a PR's parsed package name must run through this same
    function on both sides so a casing or separator difference -- ``Pillow``
    vs ``pillow``, ``nest_asyncio`` vs ``nest-asyncio`` -- cannot make a real
    match miss. github-actions packages are ``owner/repo`` slugs that are
    never looked up in the register by name (docker/unknown carry no register
    entries either); those and any other ecosystem fall back to a bare
    lowercase, which only ever affects a lookup that will simply not find a
    register row.
    """
    if ecosystem == "pip":
        return normalize_pip(name)
    if ecosystem == "npm":
        return normalize_npm(name)
    return (name or "").strip().lower()


@dataclass(frozen=True)
class RegisterRow:
    """One data row from a register table that carries a ``Tier`` column.

    ``columns`` holds every column of that row's table, keyed by the header
    text lowercased verbatim (so a table with a "Surface" column exposes
    ``columns["surface"]``); ``name`` and ``tier`` are pulled out separately
    because every caller needs them.
    """

    name: str
    tier: str
    columns: dict[str, str]


def _iter_table_rows(text: str):
    """Yield (header, cells) for every data row of every markdown table.

    ``header`` is the lowercased header-row cells for the table the row
    belongs to; ``cells`` is that row's own cells. A table's header is
    identified positionally -- the first ``|``-line after a run of non-table
    lines -- and stays in effect for every subsequent ``|``-line (skipping
    the ``|---|---|`` separator) until a non-table line resets it. This lets
    the same document hold many tables of different shapes; a row whose cell
    count does not match its table's header is dropped rather than
    misaligned against the wrong column names.
    """
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(_SEPARATOR_CELL.fullmatch(c) for c in cells if c):
            continue
        if len(cells) != len(header):
            continue
        yield header, cells


def _row_name(name_cell: str) -> str:
    """Extract the package name from a table's name-bearing cell.

    A name cell is usually a bare backticked package name, but some rows
    annotate it further, e.g. "`image-size` (via `pptxgenjs`)". Stripping
    backticks off the whole cell in that case yields
    "image-size` (via `pptxgenjs" -- garbage that never matches a real
    package -- so the first backticked token is extracted instead, falling
    back to the stripped cell when there is no backtick at all.
    """
    match = _FIRST_BACKTICKED.search(name_cell)
    return match.group(1) if match else name_cell.strip("`")


def load_register(register: Path) -> list[RegisterRow]:
    """Parse every table row in the register that maps a package to a tier,
    keyed by column name rather than position.

    A qualifying table must have both a ``Package`` column and a literal
    ``Tier`` column. Both are required, not just ``Tier`` alone: the
    register's own "Risk Tiering" table (``| Tier | Definition | Action |``)
    also has a column named ``Tier``, but its rows *define* what Healthy,
    Watch, At-Risk and Replace-Now mean -- they are not package rows, and
    treating them as some would read the tier-definition table itself as
    four packages named "healthy", "watch", etc. Requiring ``Package`` too
    is what tells the two tables apart.

    Raises ``RegisterFormatError`` when the register is missing, or when no
    table in it has both columns -- the table's shape changed in a way this
    parser cannot recover a tier from, and returning an empty list would read
    identically to "nothing is At-Risk". This is the fail-loud behaviour both
    callers depend on; a caller that can tolerate a missing or reshaped
    register (dep_risk_audit's best-effort staleness check) must catch this
    explicitly rather than receiving silence.
    """
    if not register.exists():
        raise RegisterFormatError(
            f"dependency risk register not found at {register}: the At-Risk "
            "holds cannot be evaluated, and an empty tier map is "
            "indistinguishable from a register in which nothing is held"
        )
    rows: list[RegisterRow] = []
    for header, cells in _iter_table_rows(register.read_text(encoding="utf-8")):
        if "tier" not in header or "package" not in header:
            continue
        name_idx = header.index("package")
        tier_idx = header.index("tier")
        name = _row_name(cells[name_idx])
        tier = cells[tier_idx].strip("*").lower()
        columns = dict(zip(header, cells))
        rows.append(RegisterRow(name=name, tier=tier, columns=columns))
    if not rows:
        raise RegisterFormatError(
            f"dependency risk register {register} has no table with both a "
            "'Package' column and a literal 'Tier' column: its shape "
            "changed, so no At-Risk hold can fire"
        )
    return rows


def _ecosystem_of_surface(surface: str) -> str:
    """Infer a register row's ecosystem from its Surface column.

    Mirrors ``dep_risk_audit``'s own Surface-based dispatch (closes #162
    there): "Frontend ..." rows are npm, "Python ..." / "Backend ..." rows
    are pip, "GitHub Action" rows are github-actions. Anything else is
    "unknown", which normalizes to a bare lowercase -- conservative, since
    the only consequence is a lookup that will not match a PR's package.
    """
    lowered = surface.lower()
    if lowered.startswith("frontend"):
        return "npm"
    if lowered.startswith("python") or lowered.startswith("backend"):
        return "pip"
    if lowered.startswith("github action"):
        return "github-actions"
    return "unknown"


def tiers_by_package(rows: list[RegisterRow]) -> dict[str, str]:
    """Reduce parsed rows to a normalized package-name -> tier map.

    Each key is normalized through ``normalize_package`` using the ecosystem
    inferred from that row's own Surface column, so a lookup from
    ``dep_triage_collect`` -- which normalizes the PR's package name through
    the same function using the PR's *known* ecosystem -- lands on the same
    key regardless of casing or separator differences. Rows whose Tier cell
    is not one of the register's own defined tiers are dropped rather than
    carried through as a made-up value.
    """
    tiers: dict[str, str] = {}
    for row in rows:
        if row.tier not in VALID_TIERS:
            continue
        ecosystem = _ecosystem_of_surface(row.columns.get("surface", ""))
        key = normalize_package(ecosystem, row.name)
        tiers[key] = row.tier
    return tiers


def load_risk_tiers(register: Path) -> dict[str, str]:
    """The normalized package-name -> tier map ``dep_triage_collect`` embeds
    in the snapshot for ``rule_held_package`` to enforce.

    Raises ``RegisterFormatError`` -- a ``RuntimeError`` subclass -- rather
    than returning an empty mapping on any register failure: an empty mapping
    is indistinguishable from "no package is At-Risk", so a moved, renamed or
    reshaped register would silently disarm the hold and let an At-Risk
    package with unpatched CVEs classify as a candidate. Failing the
    collection is the only outcome that cannot be mistaken for a clean bill
    of health.
    """
    tiers = tiers_by_package(load_register(register))
    if not tiers:
        raise RegisterFormatError(
            f"dependency risk register {register} parsed to zero package "
            "tiers: its table shape changed, so no At-Risk hold can fire"
        )
    return tiers


def tracked_surface_rows(rows: list[RegisterRow]) -> list[tuple[str, str]]:
    """(name, surface) pairs for every row that carries a Surface column.

    This is what ``dep_risk_audit``'s staleness dispatch reads: every
    package the register tracks for maintainer-staleness (Watch and At-Risk
    alike), with the raw register name -- not normalized -- because it is
    passed straight to ``pip show`` / ``npm view``, which accept the
    register's own spelling fine. Rows without a Surface column (the Healthy
    tables, which have no Tier column either and so never reach here, and any
    future table shape without one) are excluded.
    """
    return [
        (row.name, row.columns["surface"]) for row in rows if "surface" in row.columns
    ]
