"""Unit tests for the ADR-093 Phase 5.1 schema-drift static scan."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from scripts.adr_093_taint_schema_static_scan import (
    main,
    render_markdown,
    scan_source,
)

# ---------------------------------------------------------------------------
# Happy path: a clean repository module
# ---------------------------------------------------------------------------


def test_clean_repository_produces_no_drift_and_no_missing_predicates() -> None:
    source = dedent("""
        def preload(self, scan_id):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", self.tenant_id)
                .has("scan_id", scan_id)
                .has_label("VulnCodeUnit")
                .value_map(True, "code_unit_id", "qualified_name")
            ).bytecode

        def persist(self, scan_id):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", self.tenant_id)
                .property("scan_id", scan_id)
                .property("code_unit_id", "u1")
                .property("qualified_name", "mod.fn")
            ).bytecode
        """)
    r = scan_source(source)
    assert r.drift == set()
    assert r.missing_tenant_predicate == []
    assert len(r.chains) == 2


# ---------------------------------------------------------------------------
# Drift: a property read but never written
# ---------------------------------------------------------------------------


def test_drift_detected_when_read_property_missing_from_writes() -> None:
    source = dedent("""
        def preload(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .has_label("VulnCodeUnit")
                .value_map(True, "code_unit_id", "DRIFTED_NAME")
            ).bytecode

        def persist(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", "t1")
                .property("code_unit_id", "u1")
            ).bytecode
        """)
    r = scan_source(source)
    assert "DRIFTED_NAME" in r.drift


def test_drift_detected_via_has_filter_on_unwritten_property() -> None:
    source = dedent("""
        def lookup(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .has("UNWRITTEN_FIELD", "x")
                .value_map(True, "code_unit_id")
            ).bytecode

        def persist(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", "t1")
                .property("code_unit_id", "u1")
            ).bytecode
        """)
    r = scan_source(source)
    assert "UNWRITTEN_FIELD" in r.drift


# ---------------------------------------------------------------------------
# Allowed write-only properties don't surface as drift
# ---------------------------------------------------------------------------


def test_documented_write_only_properties_not_flagged_as_drift() -> None:
    source = dedent("""
        def persist(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", "t1")
                .property("analyzer_version", "0.3")
                .property("taxonomy_version", "0.1")
                .property("commit_sha", "abc")
                .property("code_unit_id", "u1")
            ).bytecode
        """)
    r = scan_source(source)
    # No reads at all -> no drift; the write-only properties are
    # documented in _ALLOWED_WRITE_ONLY.
    assert r.drift == set()


# ---------------------------------------------------------------------------
# Missing tenant predicate detection
# ---------------------------------------------------------------------------


def test_missing_tenant_predicate_on_read_chain_flagged() -> None:
    source = dedent("""
        def lookup(self):
            g = self.client.traversal()
            return (
                g.V()
                .has_label("VulnCodeUnit")
                .has("qualified_name", "x")
                .value_map(True, "code_unit_id")
            ).bytecode
        """)
    r = scan_source(source)
    assert len(r.missing_tenant_predicate) == 1
    assert r.missing_tenant_predicate[0].entry_step == "V"


def test_missing_tenant_predicate_on_write_chain_flagged() -> None:
    source = dedent("""
        def persist(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("code_unit_id", "u1")
                .property("qualified_name", "x")
            ).bytecode
        """)
    r = scan_source(source)
    assert len(r.missing_tenant_predicate) == 1
    assert r.missing_tenant_predicate[0].entry_step == "add_v"


def test_tenant_predicate_on_E_entry_satisfies_check() -> None:
    source = dedent("""
        def edges(self):
            g = self.client.traversal()
            return (
                g.E()
                .has("tenant_id", "t1")
                .has_label("SINKS_PARAM")
            ).bytecode
        """)
    r = scan_source(source)
    assert r.missing_tenant_predicate == []


# ---------------------------------------------------------------------------
# Outer-call deduplication: we only classify the OUTERMOST chain call
# ---------------------------------------------------------------------------


def test_outer_call_deduplication() -> None:
    """ast.walk visits every Call; the scan must process each chain once."""
    source = dedent("""
        def f(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .has_label("VulnCodeUnit")
                .value_map(True, "code_unit_id")
            ).bytecode
        """)
    r = scan_source(source)
    assert len(r.chains) == 1


# ---------------------------------------------------------------------------
# Real repository: smoke-test against the live module
# ---------------------------------------------------------------------------


def test_live_repository_module_passes_static_scan() -> None:
    """The current repository module must pass the schema scan clean.

    This is the Phase 5 acceptance criterion: the scanner produces a
    clean report against the code we already shipped in Phases 2-3.
    """
    repo_path = Path(
        "src/services/vulnerability_scanner/parsing/neptune_taint_repository.py"
    )
    assert repo_path.exists(), "repository module not found"
    source = repo_path.read_text(encoding="utf-8")
    r = scan_source(source)
    assert r.drift == set(), f"unexpected drift: {sorted(r.drift)}"
    assert r.missing_tenant_predicate == [], (
        "chain missing tenant predicate at "
        f"{[c.line for c in r.missing_tenant_predicate]}"
    )


# ---------------------------------------------------------------------------
# Markdown report rendering
# ---------------------------------------------------------------------------


def test_markdown_report_renders_pass_status_on_clean_input() -> None:
    source = dedent("""
        def persist(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", "t1")
                .property("code_unit_id", "u1")
            ).bytecode
        """)
    r = scan_source(source)
    rendered = render_markdown(r, Path("test.py"))
    assert "PASS" in rendered
    assert "DRIFT FOUND" not in rendered


def test_markdown_report_renders_failure_on_drift() -> None:
    source = dedent("""
        def lookup(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .value_map(True, "DRIFTED")
            ).bytecode

        def persist(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", "t1")
            ).bytecode
        """)
    r = scan_source(source)
    rendered = render_markdown(r, Path("test.py"))
    assert "DRIFT FOUND" in rendered
    assert "DRIFTED" in rendered


# ---------------------------------------------------------------------------
# CLI: --fail-on-gap returns 1 on drift, 0 on clean
# ---------------------------------------------------------------------------


def test_cli_fail_on_gap_returns_one_on_drift(tmp_path: Path) -> None:
    bad_source = tmp_path / "bad.py"
    bad_source.write_text(dedent("""
            def lookup(self):
                g = self.client.traversal()
                return (
                    g.V()
                    .has("tenant_id", "t1")
                    .value_map(True, "DRIFTED")
                ).bytecode
            """))
    report = tmp_path / "report.md"
    rc = main(
        [
            "--source",
            str(bad_source),
            "--report-markdown",
            str(report),
            "--fail-on-gap",
        ]
    )
    assert rc == 1
    assert report.exists()


def test_cli_returns_zero_on_clean_input(tmp_path: Path) -> None:
    good_source = tmp_path / "good.py"
    good_source.write_text(dedent("""
            def persist(self):
                g = self.client.traversal()
                return (
                    g.add_v("VulnCodeUnit")
                    .property("tenant_id", "t1")
                    .property("code_unit_id", "u1")
                ).bytecode
            """))
    report = tmp_path / "report.md"
    rc = main(
        [
            "--source",
            str(good_source),
            "--report-markdown",
            str(report),
            "--fail-on-gap",
        ]
    )
    assert rc == 0
    assert report.exists()


def test_cli_returns_two_when_source_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.py"
    rc = main(["--source", str(missing)])
    assert rc == 2
