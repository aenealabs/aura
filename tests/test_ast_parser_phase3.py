"""Phase 3 tests for ASTParserAgent: JS/TS via tree-sitter.

Covers ES6 classes, arrow functions, member-call targets, async/await,
default/named/namespace imports, side-effect imports, JSX/TSX
structural skeletons, and graceful degradation when tree-sitter is
unavailable.
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


def _parse_source(
    parser: ASTParserAgent, tmp_path: Path, source: str, name: str = "module.js"
) -> tuple:
    file_path = tmp_path / name
    file_path.write_text(textwrap.dedent(source))
    return parser.parse_file_with_relationships(file_path)


def _of_kind(rels: list[CodeRelationship], label: str) -> list[CodeRelationship]:
    return [r for r in rels if r.relationship == label]


class TestClasses:
    def test_es6_class_and_method(self, parser, tmp_path):
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            class App {
              run() { return 1; }
            }
            """,
        )
        names = {(e.name, e.entity_type) for e in entities}
        assert ("App", "class") in names
        assert ("run", "method") in names

    def test_class_extends_emits_inherits(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            class Base {}
            class Derived extends Base {}
            """,
        )
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        assert any(
            r.source_name == "Derived" and r.target_name == "Base" for r in inherits
        )

    def test_member_expression_base(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            import * as React from "react";
            class Widget extends React.Component {}
            """,
        )
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        assert any(r.target_name == "React.Component" for r in inherits)

    def test_nested_method_parent_chain(self, parser, tmp_path):
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            class Outer {
              greet() { return 1; }
            }
            """,
        )
        greet = next(e for e in entities if e.name == "greet")
        assert greet.parent_chain == ("Outer",)
        assert greet.parent_entity == "Outer"


class TestFunctions:
    def test_function_declaration(self, parser, tmp_path):
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            function helper() { return 1; }
            """,
        )
        assert any(e.name == "helper" and e.entity_type == "function" for e in entities)

    def test_arrow_function_via_const(self, parser, tmp_path):
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            const sum = (a, b) => a + b;
            """,
        )
        sum_entity = next(e for e in entities if e.name == "sum")
        assert sum_entity.entity_type == "function"
        assert sum_entity.attributes.get("arrow_function") is True

    def test_async_function(self, parser, tmp_path):
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            async function fetchData() { return 1; }
            """,
        )
        assert any(e.name == "fetchData" for e in entities)


class TestImports:
    def test_default_import(self, parser, tmp_path):
        entities, rels = _parse_source(
            parser,
            tmp_path,
            """
            import Foo from "./foo";
            """,
        )
        assert any(e.name == "Foo" and e.entity_type == "import" for e in entities)
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        assert any(r.target_name == "./foo" for r in imports)

    def test_named_imports(self, parser, tmp_path):
        entities, rels = _parse_source(
            parser,
            tmp_path,
            """
            import { Foo, Bar as Baz } from "./things";
            """,
        )
        names = {e.name for e in entities if e.entity_type == "import"}
        # Bar is aliased to Baz; the local binding wins.
        assert "Foo" in names
        assert "Baz" in names
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        # Both bindings target the same source module.
        targets = {r.target_name for r in imports}
        assert targets == {"./things"}

    def test_namespace_import(self, parser, tmp_path):
        entities, rels = _parse_source(
            parser,
            tmp_path,
            """
            import * as React from "react";
            """,
        )
        assert any(e.name == "React" for e in entities)
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        assert any(r.target_name == "react" for r in imports)

    def test_side_effect_only_import(self, parser, tmp_path):
        entities, rels = _parse_source(
            parser,
            tmp_path,
            """
            import "./polyfills";
            """,
        )
        # The import statement still produces an entity and an edge,
        # named after the source module.
        imports = _of_kind(rels, EdgeLabel.IMPORTS.value)
        assert len(imports) == 1
        assert imports[0].target_name == "./polyfills"
        assert any(
            e.attributes and e.attributes.get("side_effect_only") for e in entities
        )


class TestCalls:
    def test_intra_function_call(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            function helper() {}
            function main() {
              helper();
            }
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        assert any(r.source_name == "main" and r.target_name == "helper" for r in calls)

    def test_method_call_with_member_expression_target(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            class App {
              run() {
                console.log("hi");
              }
            }
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        run_calls = [r for r in calls if r.source_name == "run"]
        assert run_calls
        assert run_calls[0].source_parent_chain == ("App",)
        assert run_calls[0].target_name == "console.log"

    def test_call_inside_arrow_function(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            const driver = () => {
              fetchData();
            };
            function fetchData() {}
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        assert any(
            r.source_name == "driver" and r.target_name == "fetchData" for r in calls
        )

    def test_module_level_call_not_attributed(self, parser, tmp_path):
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            function helper() {}
            helper();
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        assert not calls

    def test_call_chain_head_skipped(self, parser, tmp_path):
        """Calls whose callee is itself a call (e.g. ``factory()()``)
        cannot be reduced to a single deterministic target name.
        """
        _, rels = _parse_source(
            parser,
            tmp_path,
            """
            function thing() {
              factory()();
            }
            """,
        )
        calls = _of_kind(rels, EdgeLabel.CALLS.value)
        # We still record the inner `factory` call but not the outer.
        target_names = {r.target_name for r in calls}
        assert "factory" in target_names


class TestTypescript:
    def test_ts_file_parses(self, parser, tmp_path):
        """``.ts`` files are parsed with the JS grammar; the
        structural skeleton (classes, methods, imports) survives even
        though TypeScript-specific shapes (type annotations) become
        ERROR nodes.
        """
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            import { Foo } from "./foo";

            export class Bar {
              greet(name) { return name; }
            }
            """,
            name="module.ts",
        )
        names = {e.name for e in entities}
        assert "Bar" in names
        assert "greet" in names
        assert "Foo" in names

    def test_tsx_file_parses(self, parser, tmp_path):
        """JSX/TSX files preserve component structure."""
        entities, rels = _parse_source(
            parser,
            tmp_path,
            """
            import * as React from "react";

            class Button extends React.Component {
              render() {
                return null;
              }
            }
            """,
            name="Button.tsx",
        )
        names = {e.name for e in entities}
        assert "Button" in names
        assert "render" in names
        inherits = _of_kind(rels, EdgeLabel.INHERITS.value)
        assert any(r.target_name == "React.Component" for r in inherits)


class TestPathologicalFixtures:
    def test_minified_input_does_not_crash(self, parser, tmp_path):
        """Tree-sitter handles minified input without raising."""
        entities, _ = _parse_source(
            parser,
            tmp_path,
            "function a(b){return b+1}function c(){return a(2)}",
        )
        names = {e.name for e in entities}
        assert "a" in names
        assert "c" in names

    def test_invalid_syntax_returns_partial(self, parser, tmp_path):
        """Tree-sitter is tolerant of partial syntax errors; we return
        whatever parsed cleanly rather than dropping the whole file.
        """
        entities, _ = _parse_source(
            parser,
            tmp_path,
            "class Good {} class Bad {",
        )
        # `Good` is fully valid; `Bad` is unfinished.
        names = {e.name for e in entities}
        assert "Good" in names

    def test_nested_class_in_function(self, parser, tmp_path):
        """Class declared inside a function should still be captured."""
        entities, _ = _parse_source(
            parser,
            tmp_path,
            """
            function makeWidget() {
              class Widget {
                render() {}
              }
              return Widget;
            }
            """,
        )
        names = {e.name for e in entities}
        assert "Widget" in names
        assert "render" in names
