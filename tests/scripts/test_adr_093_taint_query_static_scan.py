"""Unit tests for the ADR-093 Phase 5.2 query-shape static scan."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from scripts.adr_093_taint_query_static_scan import main, render_markdown, scan_files


def _write(path: Path, body: str) -> Path:
    path.write_text(dedent(body), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tenant-predicate AST gate
# ---------------------------------------------------------------------------


def test_chain_with_tenant_has_predicate_passes(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "good.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .has_label("VulnCodeUnit")
                .value_map(True, "code_unit_id")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert r.is_clean


def test_chain_without_tenant_predicate_flagged(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "bad.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.V()
                .has_label("VulnCodeUnit")
                .value_map(True, "code_unit_id")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert len(r.chain_findings) == 1
    assert r.chain_findings[0].reason == "no_tenant_predicate"
    assert r.chain_findings[0].entry_step == "V"


def test_add_v_with_property_tenant_predicate_passes(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "good.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("tenant_id", "t1")
                .property("code_unit_id", "u1")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert r.is_clean


def test_add_v_without_property_tenant_predicate_flagged(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "bad.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .property("code_unit_id", "u1")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert len(r.chain_findings) == 1
    assert r.chain_findings[0].entry_step == "add_v"


def test_add_v_with_has_predicate_only_flagged(tmp_path: Path) -> None:
    """An addV chain with .has('tenant_id') (wrong shape for writes) is still
    flagged -- addV must use .property('tenant_id', ...) per the runtime
    contract."""
    p = _write(
        tmp_path / "bad.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.add_v("VulnCodeUnit")
                .has("tenant_id", "t1")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert len(r.chain_findings) == 1


def test_tenant_predicate_outside_window_flagged(tmp_path: Path) -> None:
    """Predicate must appear within the first 6 chain steps; deeper is rejected."""
    p = _write(
        tmp_path / "bad.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.V()
                .has_label("VulnCodeUnit")
                .has("scan_id", "s1")
                .has("file_path", "x")
                .has("qualified_name", "y")
                .has("commit_sha", "z")
                .has("content_hash", "h")
                .has("tenant_id", "t1")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert len(r.chain_findings) == 1


# ---------------------------------------------------------------------------
# Partition-templated ARN check
# ---------------------------------------------------------------------------


def test_hardcoded_arn_in_code_flagged(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "bad.py",
        """
        def f():
            return "arn:aws:s3:::my-bucket"
        """,
    )
    r = scan_files([p])
    assert len(r.arn_findings) == 1


def test_arn_in_docstring_not_flagged(tmp_path: Path) -> None:
    """Documenting example ARNs in docstrings is fine."""
    p = _write(
        tmp_path / "good.py",
        '''
        def f():
            """Example: arn:aws:s3:::my-bucket"""
            return None
        ''',
    )
    r = scan_files([p])
    assert r.arn_findings == []


def test_arn_in_comment_not_flagged(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "good.py",
        """
        def f():
            # Real ARN form in commercial: arn:aws:kms:...
            return None
        """,
    )
    r = scan_files([p])
    assert r.arn_findings == []


def test_partition_templated_arn_passes(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "good.py",
        """
        def f():
            return f"arn:${'{'}AWS::Partition{'}'}:kms:us-east-1:123:key/abcd"
        """,
    )
    r = scan_files([p])
    assert r.is_clean


def test_govcloud_arn_in_string_intentionally_uses_govcloud_partition(
    tmp_path: Path,
) -> None:
    """``arn:aws-us-gov:`` is intentional in GovCloud-specific code -- not flagged."""
    p = _write(
        tmp_path / "good.py",
        """
        def f():
            return "arn:aws-us-gov:kms:us-gov-west-1:111:key/x"
        """,
    )
    r = scan_files([p])
    assert r.is_clean


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------


def test_clean_module_produces_clean_report(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "clean.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .has_label("VulnCodeUnit")
                .value_map(True, "code_unit_id")
            ).bytecode
        """,
    )
    r = scan_files([p])
    assert r.is_clean
    md = render_markdown(r, [p])
    assert "PASS" in md
    assert "VIOLATIONS" not in md


def test_violations_render_in_report(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "bad.py",
        """
        def f(self):
            arn = "arn:aws:kms:us-east-1:111:key/abcd"
            g = self.client.traversal()
            return g.V().value_map(True, "code_unit_id").bytecode
        """,
    )
    r = scan_files([p])
    md = render_markdown(r, [p])
    assert "VIOLATIONS" in md
    assert "arn:aws:" in md


# ---------------------------------------------------------------------------
# Real source modules: smoke-test
# ---------------------------------------------------------------------------


def test_live_modules_pass_query_scan() -> None:
    """The Phase 2-4 modules must pass the query scan clean.

    This is the Phase 5 acceptance criterion for the query gate.
    """
    sources = [
        Path("src/services/vulnerability_scanner/parsing/neptune_taint_repository.py"),
        Path("src/services/vulnerability_scanner/parsing/neptune_taint_aws_deps.py"),
        Path(
            "src/services/vulnerability_scanner/parsing/tenant_scoped_gremlin_client.py"
        ),
        Path("src/services/vulnerability_scanner/parsing/taint_context_factory.py"),
    ]
    r = scan_files(sources)
    assert (
        r.is_clean
    ), f"chain findings={r.chain_findings!r}; arn findings={r.arn_findings!r}"


# ---------------------------------------------------------------------------
# CLI: --fail-on-gap returns 1 on violations
# ---------------------------------------------------------------------------


def test_cli_fail_on_gap_returns_one_on_violation(tmp_path: Path) -> None:
    bad = _write(
        tmp_path / "bad.py",
        """
        def f(self):
            g = self.client.traversal()
            return g.V().value_map(True, "code_unit_id").bytecode
        """,
    )
    rc = main(
        [
            "--source",
            str(bad),
            "--report-markdown",
            str(tmp_path / "r.md"),
            "--fail-on-gap",
        ]
    )
    assert rc == 1


def test_cli_returns_zero_on_clean(tmp_path: Path) -> None:
    good = _write(
        tmp_path / "good.py",
        """
        def f(self):
            g = self.client.traversal()
            return (
                g.V()
                .has("tenant_id", "t1")
                .value_map(True, "code_unit_id")
            ).bytecode
        """,
    )
    rc = main(
        [
            "--source",
            str(good),
            "--report-markdown",
            str(tmp_path / "r.md"),
            "--fail-on-gap",
        ]
    )
    assert rc == 0


def test_cli_missing_source_is_warned_not_fatal(
    tmp_path: Path,
) -> None:
    """A missing path logs but doesn't crash; clean files still pass."""
    good = _write(
        tmp_path / "good.py",
        """
        def f(self):
            g = self.client.traversal()
            return g.V().has("tenant_id", "t1").value_map(True, "x").bytecode
        """,
    )
    missing = tmp_path / "absent.py"
    rc = main(
        [
            "--source",
            str(good),
            "--source",
            str(missing),
            "--report-markdown",
            str(tmp_path / "r.md"),
        ]
    )
    assert rc == 0
