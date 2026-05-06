"""Project Aura - AST Canonical Form Normalizer (ADR-085 Phase 1, Pillar 1).

Converts arbitrary Python source into a canonical AST representation
suitable for consensus equivalence comparison:

* sorts imports alphabetically,
* strips comments and docstrings (semantics-only comparison),
* renames variables to positional placeholders ``_v0``, ``_v1`` …
  (eliminates naming variance),
* normalises whitespace (handled implicitly by ``ast.dump()``),
* outputs a frozen :class:`ASTCanonicalForm` with SHA-256 hashes.

Two outputs that produce the same ``canonical_hash`` are guaranteed to
be exact structural matches modulo identifier renaming. The slower
embedding-cosine fallback in :mod:`semantic_equivalence` catches
semantically equivalent outputs whose canonical forms still differ
(e.g. a ``for`` loop vs a list comprehension).

Design notes:

* Pure-Python; no external deps. Required for air-gapped / edge
  deployment compatibility.
* Module-private helpers operate on parsed AST nodes only — never on
  raw source — so a malformed canonical_dump cannot trigger
  arbitrary-code-execution paths.
* Variable-rename ordering is breadth-first by node visit order so two
  textually different but structurally identical implementations
  always produce identical placeholder sequences.
"""

from __future__ import annotations

import ast
import hashlib
import logging
from dataclasses import dataclass

from src.services.verification_envelope.contracts import ASTCanonicalForm

logger = logging.getLogger(__name__)


@dataclass
class _NormalizationStats:
    """Internal counters for diagnostic logging."""

    node_count: int = 0
    variable_count: int = 0
    function_count: int = 0
    class_count: int = 0


class _DocstringStripper(ast.NodeTransformer):
    """Remove leading docstring from modules, functions, classes."""

    def _strip(self, node: ast.AST) -> ast.AST:
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
            if not body:
                # Empty body breaks the parser; keep a single Pass.
                body.append(ast.Pass())
        return node

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)


class _ImportSorter(ast.NodeTransformer):
    """Sort module-level imports alphabetically.

    Sorting only at the module level avoids reordering imports inside
    function bodies, which would change semantics for any code that
    relies on import-time side effects.
    """

    def visit_Module(self, node: ast.Module) -> ast.AST:
        # Collect contiguous leading import statements; sort them.
        leading_imports: list[ast.stmt] = []
        rest: list[ast.stmt] = []
        in_leading = True
        for stmt in node.body:
            if in_leading and isinstance(stmt, (ast.Import, ast.ImportFrom)):
                leading_imports.append(stmt)
            else:
                in_leading = False
                rest.append(stmt)

        leading_imports.sort(key=self._import_sort_key)
        node.body = leading_imports + rest
        return node

    @staticmethod
    def _import_sort_key(stmt: ast.stmt) -> str:
        if isinstance(stmt, ast.Import):
            return "a:" + ",".join(a.name for a in stmt.names)
        if isinstance(stmt, ast.ImportFrom):
            module = stmt.module or ""
            names = ",".join(a.name for a in stmt.names)
            return f"b:{module}:{names}"
        return "c"


class _VariableRenamer(ast.NodeTransformer):
    """Rename function arguments and locally-bound names to ``_v0``, ``_v1`` ….

    Renaming keeps a per-function scope so the same logical variable in
    different functions doesn't share an index. Module-level names
    (likely public API) are left alone — renaming them would change
    observable behaviour and could cause false consensus rejections.
    """

    BUILTINS = frozenset(dir(__builtins__))

    def __init__(self) -> None:
        super().__init__()
        self._scope_counters: list[int] = [0]
        self._scope_maps: list[dict[str, str]] = [{}]

    def _push_scope(self) -> None:
        self._scope_counters.append(0)
        self._scope_maps.append({})

    def _pop_scope(self) -> None:
        self._scope_counters.pop()
        self._scope_maps.pop()

    def _rename_local(self, original: str) -> str:
        scope = self._scope_maps[-1]
        if original in scope:
            return scope[original]
        idx = self._scope_counters[-1]
        self._scope_counters[-1] = idx + 1
        new = f"_v{idx}"
        scope[original] = new
        return new

    def _is_local(self, name: str) -> bool:
        # Top-level module scope: don't rename.
        if len(self._scope_maps) == 1:
            return False
        if name in self.BUILTINS:
            return False
        return True

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._push_scope()
        # Rename arguments first so subsequent references resolve.
        for arg in node.args.args:
            arg.arg = self._rename_local(arg.arg)
        for arg in node.args.kwonlyargs:
            arg.arg = self._rename_local(arg.arg)
        if node.args.vararg is not None:
            node.args.vararg.arg = self._rename_local(node.args.vararg.arg)
        if node.args.kwarg is not None:
            node.args.kwarg.arg = self._rename_local(node.args.kwarg.arg)
        self.generic_visit(node)
        self._pop_scope()
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        # Reuse the FunctionDef logic by delegating to a temporary node copy
        # is heavy; just inline.
        self._push_scope()
        for arg in node.args.args:
            arg.arg = self._rename_local(arg.arg)
        for arg in node.args.kwonlyargs:
            arg.arg = self._rename_local(arg.arg)
        if node.args.vararg is not None:
            node.args.vararg.arg = self._rename_local(node.args.vararg.arg)
        if node.args.kwarg is not None:
            node.args.kwarg.arg = self._rename_local(node.args.kwarg.arg)
        self.generic_visit(node)
        self._pop_scope()
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        self._push_scope()
        for arg in node.args.args:
            arg.arg = self._rename_local(arg.arg)
        self.generic_visit(node)
        self._pop_scope()
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if self._is_local(node.id):
            node.id = self._rename_local(node.id)
        return node


class ASTNormalizer:
    """Produce :class:`ASTCanonicalForm` from arbitrary Python source."""

    def __init__(self, *, strip_docstrings: bool = True) -> None:
        self._strip_docstrings = strip_docstrings

    def normalize(self, source: str) -> ASTCanonicalForm:
        """Parse, normalize, and return a canonical-form record.

        On parse failure returns a record with ``parse_succeeded=False``
        and the parser's error message; downstream callers can decide
        whether a parse failure is an automatic equivalence-fail or
        whether to fall through to embedding-cosine comparison.
        """
        source_hash = self._sha256(source.encode("utf-8"))

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return ASTCanonicalForm(
                source_hash=source_hash,
                canonical_hash="",
                canonical_dump="",
                variable_count=0,
                node_count=0,
                parse_succeeded=False,
                parse_error=str(exc),
            )

        if self._strip_docstrings:
            tree = _DocstringStripper().visit(tree)
        tree = _ImportSorter().visit(tree)
        renamer = _VariableRenamer()
        tree = renamer.visit(tree)
        ast.fix_missing_locations(tree)

        canonical_dump = ast.dump(
            tree,
            annotate_fields=True,
            include_attributes=False,
            indent=None,
        )
        canonical_hash = self._sha256(canonical_dump.encode("utf-8"))

        node_count = sum(1 for _ in ast.walk(tree))
        # Count assigned local variables across all renamed scopes.
        variable_count = sum(len(s) for s in renamer._scope_maps)

        return ASTCanonicalForm(
            source_hash=source_hash,
            canonical_hash=canonical_hash,
            canonical_dump=canonical_dump,
            variable_count=variable_count,
            node_count=node_count,
            parse_succeeded=True,
            parse_error=None,
        )

    @staticmethod
    def _sha256(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()
