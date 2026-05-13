#!/usr/bin/env python3
"""ADR-093 offline query-shape static scan.

Two CI-gate checks composed in one script:

1. **Tenant-predicate AST gate** -- walks every ``.V()`` / ``.E()`` /
   ``.add_v()`` chain entry across the scanned files; fails if any
   chain lacks a ``.has('tenant_id', ...)`` (read) or
   ``.property('tenant_id', ...)`` (write) within the first
   :data:`_TENANT_WINDOW` chain steps.

2. **Partition-templated ARN check** -- greps the scanned files for
   hardcoded ``arn:aws:`` (commercial-partition) ARNs; fails if any
   appear in code (Sub strings excluded; docstrings excluded).
   GovCloud partitions use ``arn:aws-us-gov:`` so ARNs in code must
   be partition-templated via ``arn:${AWS::Partition}:...`` (CFN) or
   constructed at runtime from ``boto3.Session.region_name``.

Both checks are the offline counterpart to live-AWS validation per
ADR-093 §Day-1 enterprise GA blockers items 1, 7 and Tara's required
network architecture changes. They run in CI on every PR touching the
scanned files.

Usage
=====

::

    python scripts/adr_093_taint_query_static_scan.py
    python scripts/adr_093_taint_query_static_scan.py --report-markdown <path>
    python scripts/adr_093_taint_query_static_scan.py --fail-on-gap

Scanned modules (default set):

- ``src/services/vulnerability_scanner/parsing/neptune_taint_repository.py``
- ``src/services/vulnerability_scanner/parsing/neptune_taint_aws_deps.py``
- ``src/services/vulnerability_scanner/parsing/tenant_scoped_gremlin_client.py``
- ``src/services/vulnerability_scanner/parsing/taint_context_factory.py``

Pass ``--source <path>`` to override (one or more times).

References
==========

- ADR-093 §Day-1 enterprise GA blockers item 1 (TenantScopedGremlinClient hardening)
- ADR-093 §Day-1 enterprise GA blockers item 7 (static schema scan in CI)
- Tara R2 in §Three-agent review (Network architecture / partition-templated ARNs)
- ADR-092 §"Offline alternatives" -- the inherited pattern
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_SOURCES: tuple[Path, ...] = (
    Path("src/services/vulnerability_scanner/parsing/neptune_taint_repository.py"),
    Path("src/services/vulnerability_scanner/parsing/neptune_taint_aws_deps.py"),
    Path("src/services/vulnerability_scanner/parsing/tenant_scoped_gremlin_client.py"),
    Path("src/services/vulnerability_scanner/parsing/taint_context_factory.py"),
)
DEFAULT_REPORT_PATH: Path = Path("docs/assessments/ADR_093_QUERY_SCAN_REPORT.md")

_TRAVERSAL_ENTRIES: frozenset[str] = frozenset({"V", "E", "add_v", "addV"})
_TENANT_WINDOW: int = 6

# Pattern for hardcoded commercial ARNs. We allow the templated form
# ``arn:${AWS::Partition}:...``, the GovCloud-specific
# ``arn:aws-us-gov:...`` (intentional when documenting cross-partition
# behaviour), and quoted examples in docstrings.
_HARDCODED_ARN_RE = re.compile(r"arn:aws:")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass
class ChainFinding:
    file_path: Path
    line: int
    entry_step: str
    reason: str  # "no_tenant_predicate" | "entry_not_allowed"


@dataclass
class ArnFinding:
    file_path: Path
    line: int
    text: str


@dataclass
class ScanResult:
    chains_scanned: int = 0
    files_scanned: int = 0
    chain_findings: list[ChainFinding] = field(default_factory=list)
    arn_findings: list[ArnFinding] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.chain_findings and not self.arn_findings


# ---------------------------------------------------------------------------
# AST helpers (copies of the schema scanner so this script stands alone)
# ---------------------------------------------------------------------------


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _is_inner_chain_call(node: ast.Call, parents: dict[int, ast.AST]) -> bool:
    p = parents.get(id(node))
    if not isinstance(p, ast.Attribute):
        return False
    pp = parents.get(id(p))
    return isinstance(pp, ast.Call) and pp.func is p


def _step_name(call: ast.Call) -> Optional[str]:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _str_arg(call: ast.Call, idx: int) -> Optional[str]:
    if idx < len(call.args):
        arg = call.args[idx]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _unwrap_call_chain(node: ast.Call) -> list[ast.Call]:
    chain: list[ast.Call] = []
    cur: Optional[ast.AST] = node
    while isinstance(cur, ast.Call):
        chain.append(cur)
        if isinstance(cur.func, ast.Attribute):
            cur = cur.func.value
        else:
            cur = None
    chain.reverse()
    return chain


# ---------------------------------------------------------------------------
# Tenant-predicate AST gate
# ---------------------------------------------------------------------------


def _check_tenant_predicate(path: Path, source: str, result: ScanResult) -> None:
    """Append findings for any Gremlin chain in ``source`` that lacks the
    required tenant predicate."""
    tree = ast.parse(source)
    parents = _build_parent_map(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_inner_chain_call(node, parents):
            continue
        calls = _unwrap_call_chain(node)
        if not calls:
            continue
        entry_name = _step_name(calls[0])
        if entry_name not in _TRAVERSAL_ENTRIES:
            continue
        result.chains_scanned += 1
        # Inspect first _TENANT_WINDOW + 1 steps (window includes entry).
        window = calls[: _TENANT_WINDOW + 1]
        if entry_name == "add_v" or entry_name == "addV":
            predicate_step = "property"
        else:
            predicate_step = "has"
        has_tenant = False
        for call in window:
            step = _step_name(call)
            if step == predicate_step and _str_arg(call, 0) == "tenant_id":
                has_tenant = True
                break
        if not has_tenant:
            result.chain_findings.append(
                ChainFinding(
                    file_path=path,
                    line=calls[0].lineno,
                    entry_step=entry_name,
                    reason="no_tenant_predicate",
                )
            )


# ---------------------------------------------------------------------------
# Partition-templated ARN check
# ---------------------------------------------------------------------------


def _check_partition_arns(path: Path, source: str, result: ScanResult) -> None:
    """Flag any ``arn:aws:`` occurrence in code (excluding docstrings/comments)."""
    # We do a line-by-line scan but ignore lines whose ARN appears
    # inside a triple-quoted docstring -- documenting example ARNs is
    # legitimate. The simplest approximation: skip lines inside
    # multi-line string literals via AST.
    tree = ast.parse(source)
    docstring_line_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc is None or not node.body:
                continue
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstring_line_ranges.append(
                    (first.lineno, getattr(first, "end_lineno", first.lineno))
                )
    lines = source.splitlines()
    for i, line_text in enumerate(lines, start=1):
        if not _HARDCODED_ARN_RE.search(line_text):
            continue
        if any(start <= i <= end for start, end in docstring_line_ranges):
            continue
        # Skip pure-comment lines (after stripping leading whitespace).
        stripped = line_text.lstrip()
        if stripped.startswith("#"):
            continue
        result.arn_findings.append(
            ArnFinding(file_path=path, line=i, text=stripped.rstrip())
        )


# ---------------------------------------------------------------------------
# Top-level scan
# ---------------------------------------------------------------------------


def scan_files(paths: list[Path]) -> ScanResult:
    result = ScanResult()
    for path in paths:
        if not path.exists():
            print(f"WARNING: source not found, skipping: {path}", file=sys.stderr)
            continue
        source = path.read_text(encoding="utf-8")
        result.files_scanned += 1
        _check_tenant_predicate(path, source, result)
        _check_partition_arns(path, source, result)
    return result


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_markdown(result: ScanResult, sources: list[Path]) -> str:
    status = "✅ PASS" if result.is_clean else "❌ VIOLATIONS"
    out: list[str] = []
    out.append("# ADR-093 Query Scan Report")
    out.append("")
    out.append(f"**Status**: {status}")
    out.append(f"**Files scanned**: {result.files_scanned}")
    out.append(f"**Gremlin chains scanned**: {result.chains_scanned}")
    out.append("")
    out.append("## Sources")
    out.append("")
    for src in sources:
        out.append(f"- `{src}`")
    out.append("")
    if result.chain_findings:
        out.append("## ❌ Chains missing tenant predicate")
        out.append("")
        for f in result.chain_findings:
            out.append(
                f"- `{f.file_path}:{f.line}` -- entry={f.entry_step!r}, "
                f"reason={f.reason!r}"
            )
        out.append("")
    if result.arn_findings:
        out.append("## ❌ Hardcoded commercial-partition ARNs")
        out.append("")
        for f in result.arn_findings:
            out.append(f"- `{f.file_path}:{f.line}` -- `{f.text}`")
        out.append("")
    if result.is_clean:
        out.append("All Gremlin chains carry a tenant predicate; no hardcoded")
        out.append("commercial-partition ARNs found in scanned source.")
        out.append("")
    out.append("---")
    out.append("")
    out.append(
        "Generated by `scripts/adr_093_taint_query_static_scan.py`. "
        "Run in CI on every PR touching the scanned files; failure "
        "blocks the merge."
    )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--source",
        action="append",
        type=Path,
        help=(
            "Path to a source file to scan (may be repeated). "
            "Defaults to the ADR-093 Phase 2-4 modules."
        ),
    )
    p.add_argument(
        "--report-markdown",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Write a markdown report (default: %(default)s).",
    )
    p.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="Exit 1 if any violation is found (CI mode).",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    sources: list[Path] = list(args.source) if args.source else list(DEFAULT_SOURCES)
    result = scan_files(sources)
    print(f"Files scanned: {result.files_scanned}")
    print(f"Chains scanned: {result.chains_scanned}")
    print(f"Chain findings: {len(result.chain_findings)}")
    print(f"ARN findings: {len(result.arn_findings)}")
    for f in result.chain_findings:
        print(
            f"  CHAIN: {f.file_path}:{f.line} entry={f.entry_step} {f.reason}",
            file=sys.stderr,
        )
    for f in result.arn_findings:
        print(
            f"  ARN: {f.file_path}:{f.line} {f.text}",
            file=sys.stderr,
        )

    if args.report_markdown:
        args.report_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.report_markdown.write_text(
            render_markdown(result, sources), encoding="utf-8"
        )
        print(f"Report written to {args.report_markdown}")

    if args.fail_on_gap and not result.is_clean:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
