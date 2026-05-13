#!/usr/bin/env python3
"""ADR-093 offline static schema scan.

Parses :mod:`src.services.vulnerability_scanner.parsing.neptune_taint_repository`
via Python's ``ast`` module, extracts every Gremlin bytecode property
name used in writes and reads, and asserts:

1. ``reads_set ⊆ writes_set`` -- every property the resolver reads must
   be one the writer actually persists.
2. Every Gremlin traversal entry (``V()`` / ``E()`` / ``add_v()``) is
   followed by a ``has('tenant_id', ...)`` or ``property('tenant_id',
   ...)`` predicate within the chain.

This is the **offline approximation** of ADR-093 Phase 1 / Phase 6
(live Neptune validation) for the cost-gate posture inherited from
ADR-092. It catches the one drift mode local TinkerGraph + unit tests
cannot: "we renamed ``summary_version`` to ``version`` in the writer
but forgot the reader."

Usage
=====

::

    python scripts/adr_093_taint_schema_static_scan.py
    python scripts/adr_093_taint_schema_static_scan.py --report-markdown <path>
    python scripts/adr_093_taint_schema_static_scan.py --fail-on-gap  # CI mode

Outputs
=======

- stdout: human-readable summary.
- ``--report-markdown <path>``: full markdown report (defaults to
  ``docs/assessments/ADR_093_SCHEMA_SCAN_REPORT.md``).
- exit ``1`` if ``--fail-on-gap`` is set and any drift is found.

What this catches
=================

- A property name read by the resolver but never written by
  ``persist_summaries``.
- A vertex / edge insert lacking a tenant predicate within the chain.

What this misses
================

- Semantic drift (same property name, different meaning between writer
  and reader).
- Runtime errors -- e.g., a property whose value type changed.

So this script is a **lower-bound on drift** -- a clean run does not
guarantee a clean live deploy. But any gap it finds is real and worth
fixing before Phase 6 first-prod-scan.

References
==========

- ADR-093 §Day-1 enterprise GA blockers item 7 (Kelly's required deliverable)
- ADR-092 §"Offline alternatives" -- the inherited pattern
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_REPO_PATH: Path = Path(
    "src/services/vulnerability_scanner/parsing/neptune_taint_repository.py"
)
DEFAULT_REPORT_PATH: Path = Path("docs/assessments/ADR_093_SCHEMA_SCAN_REPORT.md")

# These traversal entry methods open a chain that requires a tenant
# predicate before any data is read or written.
_TRAVERSAL_ENTRIES: frozenset[str] = frozenset({"V", "E", "add_v", "addV"})

# Properties whose reads/writes are intentionally asymmetric -- the
# writer stamps them for audit but the read path does not currently
# project them back. Each entry must point to an ADR section that
# documents the asymmetry.
_ALLOWED_WRITE_ONLY: frozenset[str] = frozenset(
    {
        # Stamped at write for audit; not used during resolver reads.
        "analyzer_version",  # ADR-093 §Schema versioning
        "taxonomy_version",  # ADR-093 §Schema versioning
        "commit_sha",  # ADR-093 §Data model -- used by future
        # incremental-scan policy, not by the v1 read path
    }
)


# ---------------------------------------------------------------------------
# Scanner state
# ---------------------------------------------------------------------------


@dataclass
class TraversalChain:
    """One Gremlin chain rooted at a traversal entry call."""

    entry_step: str  # "V", "E", "add_v"
    line: int
    # Property names visited via .property('name', ...) -- writes.
    properties_written: set[str] = field(default_factory=set)
    # Property names visited via .has('name', ...) -- read filters.
    has_filters: set[str] = field(default_factory=set)
    # Property names visited via .value_map(True|False, 'name'...) -- read projection.
    value_map_props: set[str] = field(default_factory=set)
    # Did we see a tenant predicate in this chain?
    tenant_predicate: bool = False


@dataclass
class ScanResult:
    """Aggregated scan output."""

    chains: list[TraversalChain] = field(default_factory=list)
    writes_set: set[str] = field(default_factory=set)
    reads_set: set[str] = field(default_factory=set)
    missing_tenant_predicate: list[TraversalChain] = field(default_factory=list)

    @property
    def drift(self) -> set[str]:
        """Property names read but never written (excluding the
        documented write-only asymmetric properties)."""
        return self.reads_set - self.writes_set - _ALLOWED_WRITE_ONLY


# ---------------------------------------------------------------------------
# AST walking
# ---------------------------------------------------------------------------


def _unwrap_call_chain(node: ast.AST) -> list[ast.Call]:
    """Walk back through ``a.b().c().d()`` chain, returning the calls in
    leaf-to-root order.

    Given the AST for ``g.V().has('x', 1).has('y', 2).value_map(True)``,
    returns the calls for ``V()``, ``has(...)``, ``has(...)``, ``value_map(...)``
    in that order.
    """
    chain: list[ast.Call] = []
    cur: Optional[ast.AST] = node
    # Walk outward: starting from the outermost Call, follow .func.value
    # to find the next inner Call.
    while isinstance(cur, ast.Call):
        chain.append(cur)
        if isinstance(cur.func, ast.Attribute):
            cur = cur.func.value
        else:
            cur = None
    chain.reverse()
    return chain


def _step_name(call: ast.Call) -> Optional[str]:
    """Return the step name (e.g., 'V', 'has', 'property') or None."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _str_arg(call: ast.Call, idx: int) -> Optional[str]:
    """Return the value of positional arg ``idx`` if it's a string literal."""
    if idx < len(call.args):
        arg = call.args[idx]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _classify_chain(calls: list[ast.Call]) -> Optional[TraversalChain]:
    """Build a :class:`TraversalChain` from the call list, or ``None``
    if this isn't a Gremlin traversal entry chain."""
    if not calls:
        return None
    entry = calls[0]
    entry_name = _step_name(entry)
    if entry_name not in _TRAVERSAL_ENTRIES:
        return None
    chain = TraversalChain(
        entry_step=entry_name,
        line=entry.lineno,
    )
    for call in calls:
        step = _step_name(call)
        if step is None:
            continue
        if step == "property":
            name = _str_arg(call, 0)
            if name is not None:
                chain.properties_written.add(name)
                if name == "tenant_id":
                    chain.tenant_predicate = True
        elif step == "has":
            name = _str_arg(call, 0)
            if name is not None:
                chain.has_filters.add(name)
                if name == "tenant_id":
                    chain.tenant_predicate = True
        elif step == "value_map":
            # value_map(True, 'a', 'b', 'c') -- all string args are
            # projected properties. The leading True/False is a
            # control flag; skip non-strings.
            for arg in call.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    chain.value_map_props.add(arg.value)
    return chain


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Map ``id(child)`` -> parent node so we can detect outermost Calls."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _is_inner_chain_call(node: ast.Call, parents: dict[int, ast.AST]) -> bool:
    """Return True iff this Call is the ``.func.value`` of another Call.

    Such inner-chain calls are not the OUTERMOST of their chain and
    ``ast.walk`` will also visit the outer Call, which is where we
    should classify the full chain from.
    """
    p = parents.get(id(node))
    if not isinstance(p, ast.Attribute):
        return False
    # The Attribute we're inside must itself be the .func of a Call.
    pp = parents.get(id(p))
    return isinstance(pp, ast.Call) and pp.func is p


def scan_source(source: str) -> ScanResult:
    """AST-walk ``source`` and return drift + tenant-predicate findings."""
    tree = ast.parse(source)
    parents = _build_parent_map(tree)
    result = ScanResult()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Skip Calls that are not the outermost of their chain --
        # ast.walk will visit the outer one and we'll classify the
        # full chain there.
        if _is_inner_chain_call(node, parents):
            continue
        calls = _unwrap_call_chain(node)
        chain = _classify_chain(calls)
        if chain is None:
            continue
        result.chains.append(chain)
        result.writes_set.update(chain.properties_written)
        result.reads_set.update(chain.has_filters)
        result.reads_set.update(chain.value_map_props)
        if not chain.tenant_predicate:
            result.missing_tenant_predicate.append(chain)
    # Exclude the predicate property itself from drift comparison;
    # tenant_id is always written by addV and always read by V().has().
    result.reads_set.discard("tenant_id")
    result.writes_set.discard("tenant_id")
    return result


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_markdown(result: ScanResult, source_path: Path) -> str:
    """Produce the markdown report body."""
    drift = sorted(result.drift)
    missing = result.missing_tenant_predicate
    status = "✅ PASS" if (not drift and not missing) else "❌ DRIFT FOUND"
    write_only = sorted(result.writes_set - result.reads_set)
    read_only = sorted(result.reads_set - result.writes_set)

    out: list[str] = []
    out.append("# ADR-093 Schema Scan Report")
    out.append("")
    out.append(f"**Source**: `{source_path}`")
    out.append(f"**Status**: {status}")
    out.append(f"**Chains scanned**: {len(result.chains)}")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append(f"- Write-set size: {len(result.writes_set)} properties")
    out.append(f"- Read-set size: {len(result.reads_set)} properties")
    out.append(f"- Drift (read-only, not in writes): {len(drift)}")
    out.append(
        f"- Allowed write-only (documented asymmetric): "
        f"{len(_ALLOWED_WRITE_ONLY & result.writes_set)}"
    )
    out.append(f"- Missing tenant predicate: {len(missing)} chain(s)")
    out.append("")
    if drift:
        out.append("## ❌ Drift -- properties read but never written")
        out.append("")
        for name in drift:
            out.append(f"- `{name}`")
        out.append("")
    if missing:
        out.append("## ❌ Chains missing tenant predicate")
        out.append("")
        for chain in missing:
            out.append(
                f"- Line {chain.line}: entry={chain.entry_step}; "
                f"has={sorted(chain.has_filters)!r}; "
                f"properties={sorted(chain.properties_written)!r}"
            )
        out.append("")
    out.append("## Properties written by the repository")
    out.append("")
    for name in sorted(result.writes_set):
        suffix = "  (allowed write-only)" if name in _ALLOWED_WRITE_ONLY else ""
        out.append(f"- `{name}`{suffix}")
    out.append("")
    out.append("## Properties read by the resolver")
    out.append("")
    for name in sorted(result.reads_set):
        out.append(f"- `{name}`")
    out.append("")
    if write_only:
        out.append("## Asymmetry summary (info)")
        out.append("")
        out.append(f"- Write-only: {write_only}")
        out.append(f"- Read-only: {read_only}")
        out.append("")
    out.append("---")
    out.append("")
    out.append(
        "Generated by `scripts/adr_093_taint_schema_static_scan.py`. "
        "Re-run on every change to the repository module to catch silent "
        "schema drift before Phase 6 first-prod-scan."
    )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_REPO_PATH,
        help="Path to the repository module to scan (default: %(default)s).",
    )
    p.add_argument(
        "--report-markdown",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Write a markdown report to this path (default: %(default)s).",
    )
    p.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="Exit 1 if drift or missing-tenant-predicate is found (CI mode).",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source_path: Path = args.source
    if not source_path.exists():
        print(f"ERROR: source not found: {source_path}", file=sys.stderr)
        return 2
    source = source_path.read_text(encoding="utf-8")
    result = scan_source(source)

    print(f"Chains scanned: {len(result.chains)}")
    print(f"Writes: {sorted(result.writes_set)}")
    print(f"Reads: {sorted(result.reads_set)}")
    if result.drift:
        print(f"DRIFT: {sorted(result.drift)}", file=sys.stderr)
    if result.missing_tenant_predicate:
        print(
            f"MISSING TENANT PREDICATE: {len(result.missing_tenant_predicate)} chain(s)",
            file=sys.stderr,
        )
        for chain in result.missing_tenant_predicate:
            print(
                f"  - line {chain.line}: {chain.entry_step}() chain",
                file=sys.stderr,
            )

    if args.report_markdown:
        args.report_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.report_markdown.write_text(
            render_markdown(result, source_path), encoding="utf-8"
        )
        print(f"Report written to {args.report_markdown}")

    if args.fail_on_gap and (result.drift or result.missing_tenant_predicate):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
