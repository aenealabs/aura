"""Tests for scripts/lint_edge_labels.py (ADR-090).

Validates that the AST lint catches string-literal edge labels in the
specific call patterns defined in the ADR while leaving allowlisted
files and unrelated string literals alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lint_edge_labels import (
    EdgeLabelVisitor,
    _is_allowlisted,
    lint_paths,
)


def _write(tmp_path: Path, name: str, source: str) -> Path:
    target = tmp_path / name
    target.write_text(source, encoding="utf-8")
    return target


class TestKeywordArgumentDetection:
    """Catches `relationship="LITERAL"` and `edge_label="LITERAL"`."""

    def test_flags_keyword_relationship_literal(self, tmp_path):
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    obj.add_edge(relationship="CALLS")\n',
        )
        violations = lint_paths([path])
        assert len(violations) == 1
        assert violations[0].label == "CALLS"
        assert "keyword argument" in violations[0].context

    def test_flags_keyword_edge_label_literal(self, tmp_path):
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    obj.do_thing(edge_label="INHERITS")\n',
        )
        violations = lint_paths([path])
        assert len(violations) == 1
        assert violations[0].label == "INHERITS"

    def test_ignores_other_keyword_args(self, tmp_path):
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    obj.do_thing(name="MY_NAME", value="OTHER")\n',
        )
        assert lint_paths([path]) == []


class TestAddRelationshipPositionalDetection:
    """Catches the third positional arg to add_relationship()."""

    def test_flags_attribute_call_positional(self, tmp_path):
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    self.neptune.add_relationship("a", "b", "CALLS")\n',
        )
        violations = lint_paths([path])
        assert len(violations) == 1
        assert violations[0].label == "CALLS"
        assert "positional" in violations[0].context

    def test_flags_bare_function_call_positional(self, tmp_path):
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    add_relationship("a", "b", "IMPORTS")\n',
        )
        violations = lint_paths([path])
        assert len(violations) == 1
        assert violations[0].label == "IMPORTS"

    def test_ignores_first_two_positional_args(self, tmp_path):
        """Entity IDs in positions 1-2 must not be flagged."""
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    add_relationship("ENTITY_A", "ENTITY_B", "CALLS")\n',
        )
        violations = lint_paths([path])
        # Only one violation: the third arg
        assert len(violations) == 1
        assert violations[0].label == "CALLS"


class TestRelationshipMapFunctionDetection:
    """Flags string literals inside read-side relationship-map functions."""

    def test_flags_literal_inside_get_relationship_types(self, tmp_path):
        path = _write(
            tmp_path,
            "reader.py",
            "def _get_relationship_types(qt):\n" '    return ["CALLS", "IMPORTS"]\n',
        )
        violations = lint_paths([path])
        labels = {v.label for v in violations}
        assert "CALLS" in labels
        assert "IMPORTS" in labels

    def test_does_not_flag_literals_outside_label_map_functions(self, tmp_path):
        path = _write(
            tmp_path,
            "reader.py",
            "def some_other_function():\n" '    return ["CALLS", "IMPORTS"]\n',
        )
        # These are upper-snake-case strings but not in a labeled context
        # and not passed to add_relationship/relationship= — no violation.
        assert lint_paths([path]) == []


class TestNonViolations:
    """Patterns that look like edge labels but are not violations."""

    def test_lowercase_strings_not_flagged(self, tmp_path):
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    add_relationship("a", "b", "calls")\n',
        )
        assert lint_paths([path]) == []

    def test_short_uppercase_strings_not_flagged(self, tmp_path):
        """Two-char tokens like 'OK' are not edge label hints."""
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    obj.add_relationship("a", "b", "OK")\n',
        )
        # "OK" is too short to match the edge-label hint pattern
        assert lint_paths([path]) == []

    def test_enum_member_argument_not_flagged(self, tmp_path):
        """The expected fix — passing the enum member — is allowed."""
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    obj.add_relationship("a", "b", EdgeLabel.CALLS)\n',
        )
        assert lint_paths([path]) == []

    def test_fewer_than_three_args_not_flagged_positionally(self, tmp_path):
        """Bare add_relationship() calls with too few args are not flagged."""
        path = _write(
            tmp_path,
            "writer.py",
            "def f():\n" '    obj.add_relationship("a", "b")\n',
        )
        assert lint_paths([path]) == []


class TestAllowlist:
    """Allowlisted files are skipped entirely."""

    def test_edge_labels_module_allowlisted(self):
        # The actual enum module is allowlisted via path pattern.
        assert _is_allowlisted(Path("src/services/graph/edge_labels.py")) is True

    def test_tests_dir_allowlisted(self):
        assert _is_allowlisted(Path("tests/test_thing.py")) is True
        assert _is_allowlisted(Path("/repo/tests/sub/test_x.py")) is True

    def test_docs_dir_allowlisted(self):
        assert _is_allowlisted(Path("docs/anything.md")) is True

    def test_archive_dir_allowlisted(self):
        assert _is_allowlisted(Path("archive/old/file.py")) is True

    def test_lint_script_self_allowlisted(self):
        assert _is_allowlisted(Path("scripts/lint_edge_labels.py")) is True

    def test_normal_src_files_not_allowlisted(self):
        assert _is_allowlisted(Path("src/services/foo.py")) is False
        assert _is_allowlisted(Path("scripts/something_else.py")) is False


class TestRepoIsClean:
    """The current repository tree must pass the lint."""

    def test_src_passes_lint(self):
        violations = lint_paths([Path("src")])
        assert violations == [], "\n".join(str(v) for v in violations)


class TestVisitorDirectly:
    """Targeted unit tests of EdgeLabelVisitor for edge cases."""

    @pytest.mark.parametrize(
        "source,expected_labels",
        [
            (
                'obj.add_relationship("a", "b", "CALLS")\n',
                ["CALLS"],
            ),
            (
                'obj.add_relationship(relationship="IMPORTS", from_entity="a", to_entity="b")\n',
                ["IMPORTS"],
            ),
            (
                'obj.do_thing(edge_label="INHERITS")\n',
                ["INHERITS"],
            ),
        ],
    )
    def test_visitor_finds_labels(self, source: str, expected_labels: list[str]):
        import ast as ast_mod

        tree = ast_mod.parse(source)
        visitor = EdgeLabelVisitor(Path("test.py"))
        visitor.visit(tree)
        actual = [v.label for v in visitor.violations]
        assert actual == expected_labels
