"""AST lint: detect module-collection-time ``sys.modules`` mutations.

Background
----------
Issue #194's last residual was caused by
``del sys.modules["src.services.bedrock_llm_service"]`` at MODULE-
collection time in ``tests/test_bedrock_llm_edge_cases.py``. Because
pytest collects test files in alphabetical order, that deletion ran
BEFORE later test files imported the module, leaving stale references
in any other module that had already imported it (e.g.
``bedrock_adapter``'s module-level ``BedrockMode`` reference). The
result: ``assert_called_once_with(mode=BedrockMode.AWS)`` failed with
identical reprs because the two ``BedrockMode`` enum classes had
different identities.

The fix was to remove the deletion. The prevention is this linter:
catch any future regression at collection time rather than in a
multi-hour bisection session.

Scope
-----
This module exposes ``find_violations(path)`` and a ``main()`` entry
point that can be run as a one-shot script (``python -m
tests._lint_sys_modules``) or as a ``pytest_collection_modifyitems``
hook (the conftest wires it in).

A "violation" is a call to one of:
- ``del sys.modules[...]``
- ``sys.modules.pop(...)``
- ``sys.modules[...] = ...``
- ``importlib.reload(...)``

that lives at MODULE SCOPE (top-level body) -- i.e. runs when pytest
imports the test file during collection. The same calls inside
function bodies or method bodies are FINE (they only run when the
test runs, after collection is complete).

Module-scope ``@pytest.fixture`` decorators ARE function bodies as
far as the AST is concerned -- the decorator wraps a function, the
function body doesn't execute at collection time. So those are OK.

False-positive escape hatch: prefix the offending statement with
``# noqa: AURA194`` to suppress.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SUPPRESSION_MARKER = "noqa: AURA194"


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    snippet: str
    reason: str

    def format(self) -> str:
        return f"{self.path}:{self.lineno}: {self.reason}\n    {self.snippet}"


def _is_sys_modules_subscript(node: ast.expr) -> bool:
    """``sys.modules[...]`` -- the load-bearing pattern."""
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "modules"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
    )


def _is_sys_modules_pop(node: ast.expr) -> bool:
    """``sys.modules.pop(...)`` -- equivalent destructiveness."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pop"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "modules"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "sys"
    )


def _is_importlib_reload(node: ast.expr) -> bool:
    """``importlib.reload(...)`` -- forces a re-exec of an already-imported
    module, which creates new class identities. Same class of bug as
    the sys.modules patterns above when used at module scope."""
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    # Match ``importlib.reload(x)`` and ``reload(x)`` (from-import form).
    if isinstance(f, ast.Attribute) and f.attr == "reload":
        if isinstance(f.value, ast.Name) and f.value.id == "importlib":
            return True
    if isinstance(f, ast.Name) and f.id == "reload":
        return True
    return False


def _statement_snippet(source_lines: list[str], lineno: int) -> str:
    """Return the source line for diagnostics, trimmed for display."""
    if 0 < lineno <= len(source_lines):
        return source_lines[lineno - 1].strip()
    return ""


def _is_suppressed(source_lines: list[str], lineno: int) -> bool:
    """Honor ``# noqa: AURA194`` on the offending line."""
    snippet = _statement_snippet(source_lines, lineno)
    return SUPPRESSION_MARKER in snippet


def _walk_module_body(
    body: Iterable[ast.stmt],
    path: Path,
    source_lines: list[str],
) -> Iterable[Violation]:
    """Yield violations from the TOP-LEVEL body of a module only.

    We deliberately do NOT recurse into FunctionDef / AsyncFunctionDef /
    ClassDef nor into Lambda bodies -- those execute on call, not on
    import. We DO recurse into ``if``, ``try``, ``with``, ``for``,
    ``while``, ``Match``, and ``ExceptHandler`` blocks because their
    bodies run at module-import time.
    """
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Inside a function/class definition -- safe.
            continue

        # Recurse into nested module-scope blocks.
        nested: list[Iterable[ast.stmt]] = []
        if isinstance(node, ast.If):
            nested.extend([node.body, node.orelse])
        elif isinstance(node, ast.Try):
            nested.extend([node.body, node.orelse, node.finalbody])
            for h in node.handlers:
                nested.append(h.body)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            nested.append(node.body)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            nested.extend([node.body, node.orelse])
        elif isinstance(node, ast.While):
            nested.extend([node.body, node.orelse])
        elif isinstance(node, ast.Match):
            for case in node.cases:
                nested.append(case.body)

        for sub in nested:
            yield from _walk_module_body(sub, path, source_lines)

        # Direct checks on this statement.
        if _is_suppressed(source_lines, node.lineno):
            continue

        # ``del sys.modules[...]``
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if _is_sys_modules_subscript(target):
                    yield Violation(
                        path=path,
                        lineno=node.lineno,
                        snippet=_statement_snippet(source_lines, node.lineno),
                        reason="``del sys.modules[...]`` at module-collection time (issue #194 class)",
                    )

        # ``sys.modules[...] = ...``
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_sys_modules_subscript(target):
                    yield Violation(
                        path=path,
                        lineno=node.lineno,
                        snippet=_statement_snippet(source_lines, node.lineno),
                        reason="``sys.modules[...] = ...`` at module-collection time (issue #194 class)",
                    )

        # Expression statements that call ``sys.modules.pop(...)`` or
        # ``importlib.reload(...)``.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if _is_sys_modules_pop(call):
                yield Violation(
                    path=path,
                    lineno=node.lineno,
                    snippet=_statement_snippet(source_lines, node.lineno),
                    reason="``sys.modules.pop(...)`` at module-collection time (issue #194 class)",
                )
            if _is_importlib_reload(call):
                yield Violation(
                    path=path,
                    lineno=node.lineno,
                    snippet=_statement_snippet(source_lines, node.lineno),
                    reason="``importlib.reload(...)`` at module-collection time (issue #194 class)",
                )


def find_violations(path: Path) -> list[Violation]:
    """Parse a single test file and return any top-level violations."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        # If the file doesn't parse, the test framework itself will
        # error during collection. Don't double-report here.
        return []
    source_lines = source.splitlines()
    return list(_walk_module_body(tree.body, path, source_lines))


def find_all_violations(tests_root: Path) -> list[Violation]:
    """Scan every ``test_*.py`` under ``tests_root`` (recursively)."""
    out: list[Violation] = []
    for path in tests_root.rglob("test_*.py"):
        # Skip vendored / archive paths if present.
        if any(
            part in {"archive", ".tox", ".venv", "node_modules"} for part in path.parts
        ):
            continue
        out.extend(find_violations(path))
    return out


def main() -> int:
    """One-shot CLI. Exit 0 if clean, 1 if violations, 2 if no tests dir."""
    if len(sys.argv) > 1:
        tests_root = Path(sys.argv[1])
    else:
        # Default: ``tests/`` relative to repo root (this file lives in
        # tests/, so the repo root is its parent).
        tests_root = Path(__file__).resolve().parent

    if not tests_root.is_dir():
        print(f"Error: not a directory: {tests_root}", file=sys.stderr)
        return 2

    violations = find_all_violations(tests_root)
    if not violations:
        print(
            f"Clean: no module-collection-time sys.modules mutations under {tests_root}"
        )
        return 0

    for v in violations:
        print(v.format())
    print(
        f"\nFound {len(violations)} violation(s). See ``tests/_lint_sys_modules.py`` "
        "for the suppression-marker escape hatch."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
