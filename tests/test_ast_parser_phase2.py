"""Phase 2 tests for ASTParserAgent: CALLS, INHERITS, IMPORTS edges.

Covers the pathological-fixture set required by ADR-090 Phase 2:
nested classes, decorator-produced overload duplicates, circular
imports, dynamic dispatch (target unresolvable, edge skipped),
class bases via attribute access (``module.Base``), and async function
call sites.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.agents.ast_parser_agent import ASTParserAgent, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel


@pytest.fixture
def parser() -> ASTParserAgent:
    return ASTParserAgent()


def _parse_source(parser: ASTParserAgent, tmp_path: Path, source: str) -> tuple:
    file_path = tmp_path / "module.py"
    file_path.write_text(textwrap.dedent(source))
    return parser.parse_file_with_relationships(file_path)


def _of_kind(rels: list[CodeRelationship], label: str) -> list[CodeRelationship]:
    return [r for r in rels if r.relationship == label]


class TestInherits:
    def test_simple_base_class(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            class Base: ...
            class Derived(Base): ...
            """,
        )
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        assert len(inherits) == 1
        assert inherits[0].source_name == "Derived"
        assert inherits[0].target_name == "Base"
        assert inherits[0].properties.get("kind") == "extends"

    def test_attribute_base(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            from collections import abc

            class Mapper(abc.MutableMapping): ...
            """,
        )
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        assert any(r.target_name == "abc.MutableMapping" for r in inherits)

    def test_multiple_bases(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            class A: ...
            class B: ...
            class C(A, B): ...
            """,
        )
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        targets = {r.target_name for r in inherits if r.source_name == "C"}
        assert targets == {"A", "B"}

    def test_nested_class_parent_chain(self, parser, tmp_path):
        entities, rels = _parse_source(
            parser,
            tmp_path,
            """
            class Outer:
                class Inner:
                    class Leaf: ...
            """,
        )
        # Find the Leaf entity by name and assert its parent chain.
        leaf = next(e for e in entities if e.name == "Leaf")
        assert leaf.parent_chain == ("Outer", "Inner")
        assert leaf.parent_entity == "Inner"

    def test_parametric_base_skipped(self, parser, tmp_path):
        """A subscripted base like Generic[T] is skipped: no single name."""
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            from typing import Generic, TypeVar
            T = TypeVar("T")

            class Wrapper(Generic[T]): ...
            """,
        )
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        # No INHERITS edge for Wrapper -> Generic[T].
        assert all(r.source_name != "Wrapper" for r in inherits)


class TestImports:
    def test_plain_import(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            import os
            """,
        )
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        assert any(r.target_name == "os" for r in imports)

    def test_from_import_targets_source_module(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            from collections import OrderedDict, defaultdict
            """,
        )
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        targets = {r.target_name for r in imports}
        # Both aliases produce IMPORTS edges to the same source module.
        assert targets == {"collections"}
        assert len(imports) == 2

    def test_relative_import_no_module(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            from . import sibling
            """,
        )
        # Relative imports without an explicit module name fall back to
        # alias.name; we accept that as the best-effort target.
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        assert any(r.target_name == "sibling" for r in imports)


class TestCalls:
    def test_intra_function_call(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            def helper(): ...
            def main():
                helper()
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        assert any(r.source_name == "main" and r.target_name == "helper" for r in calls)
        # call_site_line is set to the call AST node's line.
        for r in calls:
            assert r.properties.get("call_site_line") is not None

    def test_method_call_attribute_target(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            class App:
                def run(self):
                    self.handle()
                def handle(self): ...
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        # Method scope is preserved on the source side.
        run_calls = [r for r in calls if r.source_name == "run"]
        assert run_calls
        assert run_calls[0].source_parent_chain == ("App",)
        # Target is rendered as the dotted attribute chain.
        assert run_calls[0].target_name == "self.handle"

    def test_async_function_calls(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            async def fetch(): ...
            async def driver():
                await fetch()
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        assert any(
            r.source_name == "driver" and r.target_name == "fetch" for r in calls
        )

    def test_module_level_calls_not_attributed(self, parser, tmp_path):
        """Calls at module scope have no enclosing function caller.

        Phase 2 emits CALLS only when an enclosing function/method is
        on the scope stack. Module-level calls are not yet attributed
        because they cannot reference a single caller entity.
        """
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            def helper(): ...
            helper()
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        assert not calls

    def test_complex_callee_skipped(self, parser, tmp_path):
        """Subscripted or call-chain heads produce no target name."""
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            def thing():
                callbacks[0]()
                lookup()()
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        # The subscript head and the call-chain head are skipped, but
        # ``lookup`` itself is a Name call and IS recorded for the
        # inner expression of `lookup()()`.
        target_names = {r.target_name for r in calls}
        assert "lookup" in target_names


class TestPathologicalFixtures:
    def test_decorator_overload_methods(self, parser, tmp_path):
        """Two same-named methods on the same class produce two entities.

        Order is preserved; FQN disambiguation happens at write time
        via FQNBuilder. The parser itself emits both entities with
        identical (name, parent_chain, kind) tuples, which is exactly
        what FQNBuilder needs to assign declaration-order suffixes.
        """
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            from typing import overload

            class App:
                @overload
                def get(self, x: int) -> int: ...
                @overload
                def get(self, x: str) -> str: ...
                def get(self, x): return x
            """,
        )
        gets = [e for e in entities if e.name == "get" and e.parent_chain == ("App",)]
        assert len(gets) == 3

    def test_circular_imports_emit_edges_for_each(self, parser, tmp_path):
        # Two files importing each other; parser emits IMPORTS edges
        # from each side independently.
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("from b import thing\n")
        b.write_text("from a import other\n")
        _, rels_a = parser.parse_file_with_relationships(a)
        _, rels_b = parser.parse_file_with_relationships(b)
        targets_a = {r.target_name for r in _of_kind(rels_a, EdgeLabel.IMPORTS.value)}
        targets_b = {r.target_name for r in _of_kind(rels_b, EdgeLabel.IMPORTS.value)}
        assert "b" in targets_a
        assert "a" in targets_b

    def test_call_site_inside_nested_method(self, parser, tmp_path):
        """A call deep inside a method nested in nested classes attributes correctly."""
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            class Outer:
                class Inner:
                    def deep(self):
                        helper()
            def helper(): ...
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        deep_calls = [r for r in calls if r.source_name == "deep"]
        assert deep_calls
        assert deep_calls[0].source_parent_chain == ("Outer", "Inner")


class TestBackwardCompatibility:
    """parse_file (the legacy entry point) still returns just entities."""

    def test_parse_file_returns_list(self, parser, tmp_path):
        file_path = tmp_path / "x.py"
        file_path.write_text("class X: pass\n")
        result = parser.parse_file(file_path)
        assert isinstance(result, list)
        assert any(e.name == "X" for e in result)

    def test_parse_file_with_relationships_returns_tuple(self, parser, tmp_path):
        file_path = tmp_path / "x.py"
        file_path.write_text("class X: pass\n")
        result = parser.parse_file_with_relationships(file_path)
        assert isinstance(result, tuple)
        entities, rels = result
        assert isinstance(entities, list)
        assert isinstance(rels, list)
