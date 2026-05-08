#!/usr/bin/env python3
"""Project Aura - Edge Label Lint (ADR-090)

Rejects string-literal edge labels that bypass the canonical
EdgeLabel enum at src/services/graph/edge_labels.py. The contract
divergence that motivated ADR-090 was that the read side queried for
edge labels the write side never produced; centralizing the label set
in one enum and enforcing it at lint time prevents recurrence.

Detection scope (targeted, not broad):
    1. String-literal arguments to NeptuneGraphService.add_relationship()
       and any other function whose signature has a parameter named
       `relationship` or `edge_label`.
    2. Returned/contained string literals inside any function whose
       name matches `_get_relationship_types*` or `*relationship_types*`
       (the read-side mapping pattern).

Allowlist (these files may contain string-literal edge labels):
    - src/services/graph/edge_labels.py: the enum module itself.
    - tests/: test fixtures may exercise unknown-label code paths.
    - docs/: documentation references labels in prose.
    - archive/: legacy code, exempt per CLAUDE.md.
    - scripts/lint_edge_labels.py: this file describes the rule.

Usage:
    python -m scripts.lint_edge_labels [paths...]

If no paths are supplied, scans src/. Exit 1 on violations, 0 on clean.

Exit codes:
    0 - No violations
    1 - Violations found

Author: Project Aura Team
Created: 2026-05-08
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable

# Filenames matching these patterns are exempt from the lint.
ALLOWLIST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"src/services/graph/edge_labels\.py$"),
    re.compile(r"^tests/"),
    re.compile(r"/tests/"),
    re.compile(r"^docs/"),
    re.compile(r"^archive/"),
    re.compile(r"scripts/lint_edge_labels\.py$"),
)

# Heuristic for "this looks like an edge label string literal".
# The lint targets the precise call patterns below; this regex is a
# secondary check that prevents false positives like docstrings or
# log-formatted entity IDs that happen to contain SCREAMING_SNAKE_CASE.
_EDGE_LABEL_HINT = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")

# Function names whose parameters carry edge labels. Calls to these
# functions with string-literal label arguments are violations.
_LABEL_BEARING_PARAMS: frozenset[str] = frozenset({"relationship", "edge_label"})

# Function name patterns that build read-side edge-label maps. Returned
# string literals inside these functions are violations.
_LABEL_MAP_PATTERN = re.compile(r"(_get_relationship_types|relationship_types)")


class Violation:
    """A single lint violation."""

    __slots__ = ("path", "line", "label", "context")

    def __init__(self, path: Path, line: int, label: str, context: str):
        self.path = path
        self.line = line
        self.label = label
        self.context = context

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line}: edge label string literal {self.label!r} "
            f"({self.context}). Use EdgeLabel.{self.label} from "
            f"src/services/graph/edge_labels.py instead."
        )


class EdgeLabelVisitor(ast.NodeVisitor):
    """Walk a module AST collecting edge-label-string-literal violations."""

    def __init__(self, path: Path):
        self.path = path
        self.violations: list[Violation] = []
        # Stack of function definitions we're inside; lets us flag string
        # literals returned/contained within edge-label-mapping functions.
        self._enclosing_funcs: list[str] = []

    def _flag(self, node: ast.AST, label: str, context: str) -> None:
        if not _EDGE_LABEL_HINT.match(label):
            return
        line = getattr(node, "lineno", 0)
        self.violations.append(Violation(self.path, line, label, context))

    def _enter_func(self, name: str) -> None:
        self._enclosing_funcs.append(name)

    def _exit_func(self) -> None:
        self._enclosing_funcs.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter_func(node.name)
        try:
            self.generic_visit(node)
        finally:
            self._exit_func()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter_func(node.name)
        try:
            self.generic_visit(node)
        finally:
            self._exit_func()

    def visit_Call(self, node: ast.Call) -> None:
        # Flag string-literal arguments passed to parameters named
        # `relationship` or `edge_label`, whether positional (when we
        # can infer from the function name) or keyword.
        for kwarg in node.keywords:
            if kwarg.arg in _LABEL_BEARING_PARAMS and isinstance(
                kwarg.value, ast.Constant
            ):
                if isinstance(kwarg.value.value, str):
                    self._flag(
                        kwarg.value,
                        kwarg.value.value,
                        f"keyword argument {kwarg.arg}=",
                    )

        # Calls to add_relationship() with positional args: third arg is
        # the relationship label by convention
        # (from_entity, to_entity, relationship).
        if self._is_add_relationship_call(node) and len(node.args) >= 3:
            label_arg = node.args[2]
            if isinstance(label_arg, ast.Constant) and isinstance(label_arg.value, str):
                self._flag(
                    label_arg,
                    label_arg.value,
                    "positional 3rd arg to add_relationship",
                )

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # If we are inside a function whose name suggests it builds a
        # read-side edge-label map, any UPPER_SNAKE_CASE string literal
        # is suspicious.
        if (
            isinstance(node.value, str)
            and self._enclosing_funcs
            and _LABEL_MAP_PATTERN.search(self._enclosing_funcs[-1])
        ):
            self._flag(
                node,
                node.value,
                f"string literal inside {self._enclosing_funcs[-1]}()",
            )
        self.generic_visit(node)

    @staticmethod
    def _is_add_relationship_call(node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "add_relationship":
            return True
        if isinstance(func, ast.Name) and func.id == "add_relationship":
            return True
        return False


def _is_allowlisted(path: Path) -> bool:
    posix = path.as_posix()
    return any(pattern.search(posix) for pattern in ALLOWLIST_PATTERNS)


def _iter_python_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        if root.is_dir():
            yield from sorted(root.rglob("*.py"))


def lint_paths(paths: Iterable[Path]) -> list[Violation]:
    """Lint the given paths; return all violations found."""
    violations: list[Violation] = []
    for path in _iter_python_files(paths):
        if _is_allowlisted(path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            # Files that won't parse (syntax errors during refactor) are
            # not the lint's problem; black/flake8 catch those.
            continue
        visitor = EdgeLabelVisitor(path)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return violations


def main(argv: list[str]) -> int:
    if argv:
        roots = [Path(arg) for arg in argv]
    else:
        roots = [Path("src")]

    violations = lint_paths(roots)

    if not violations:
        return 0

    print(
        f"Edge label lint: {len(violations)} violation(s) found.",
        file=sys.stderr,
    )
    for v in violations:
        print(str(v), file=sys.stderr)
    print(
        "\nFix: import EdgeLabel from src.services.graph.edge_labels and "
        "use EdgeLabel.<NAME> instead of the string literal.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
