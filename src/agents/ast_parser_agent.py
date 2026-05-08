#!/usr/bin/env python3
"""
Aura Platform - AST Parser Agent
Structural Context Extraction from Source Code

This agent parses source code into Abstract Syntax Trees (AST) to extract
structural context including classes, methods, variables, and dependencies.

Author: MiniMax Agent
Version: 2.0
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.paths import get_sample_project_path
from src.services.graph.edge_labels import EdgeLabel

from .agent_orchestrator import InputSanitizer

logger = logging.getLogger(__name__)

# Phase 3 (ADR-090): tree-sitter is the canonical JS/TS parser. The
# regex implementation below is retained only as a fallback for
# environments where tree-sitter or its language bindings cannot be
# imported (constrained CI images, local sandboxes that strip the
# native bindings). Production deployments pin both packages.
try:
    import tree_sitter
    import tree_sitter_javascript

    _JS_LANGUAGE = tree_sitter.Language(tree_sitter_javascript.language())
    _TREE_SITTER_JS_AVAILABLE = True
except Exception:  # pragma: no cover - defensive at import time
    _JS_LANGUAGE = None
    _TREE_SITTER_JS_AVAILABLE = False
    logger.info(
        "tree-sitter JavaScript bindings unavailable; "
        "JS/TS parsing will fall back to regex"
    )


@dataclass
class CodeEntity:
    """Represents a parsed code entity (class, method, function, variable)"""

    name: str
    entity_type: str  # 'class', 'method', 'function', 'variable', 'import'
    file_path: str
    line_number: int
    parent_entity: str | None = None
    parent_chain: tuple[str, ...] = ()
    dependencies: list[str] | None = None
    attributes: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.dependencies is None:
            self.dependencies = []
        if self.attributes is None:
            self.attributes = {}


@dataclass
class CodeRelationship:
    """An edge between two code entities, emitted by the parser.

    Per ADR-090 Phase 2, parsers emit relationships alongside entities
    so the ingestion pipeline can write canonical edge labels rather
    than reconstructing them from the entity-level ``dependencies``
    field. Source is always intra-file and identified by name plus
    enclosing scope chain. Target may be intra-file (resolvable to a
    same-file entity) or cross-file (a bare name to be resolved by
    Phase 4).
    """

    source_name: str
    source_parent_chain: tuple[str, ...]
    target_name: str
    relationship: str  # EdgeLabel value: CALLS, INHERITS, IMPORTS
    properties: dict[str, Any] = field(default_factory=dict)
    file_path: str = ""


class ASTParserAgent:
    """
    AST Parser Agent for Aura Platform

    Parses source code files to extract structural context, including:
    - Class and method definitions
    - Variable declarations and usage
    - Import statements and dependencies
    - Function call relationships

    The extracted information is used to build the knowledge graph
    and provide structural context for AI agents.
    """

    def __init__(self) -> None:
        self.supported_extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}
        self.parsed_files: list[str] = []
        self.code_entities: list[CodeEntity] = []

        logger.info("ASTParserAgent initialized")

    def parse_file(self, file_path: str | Path) -> list[CodeEntity]:
        """
        Parse a single source code file.

        Args:
            file_path: Path to the source file

        Returns:
            List of CodeEntity objects representing parsed elements.
            For richer output (entities + relationships) use
            :meth:`parse_file_with_relationships`.
        """
        entities, _ = self.parse_file_with_relationships(file_path)
        return entities

    def parse_file_with_relationships(
        self, file_path: str | Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Parse a file and emit both entities and relationships.

        Per ADR-090 Phase 2, the parser is the source of truth for the
        canonical edge labels (CALLS, INHERITS, IMPORTS) that the
        ingestion pipeline writes to Neptune. Source entities are
        always intra-file and identified by name plus enclosing scope
        chain. Targets may be intra-file or unresolved cross-file
        references; Phase 4 cross-file resolution turns the latter
        into qualified targets.
        """
        try:
            path: Path = Path(file_path) if isinstance(file_path, str) else file_path
            if not path.exists():
                logger.error(f"File not found: {path}")
                return [], []

            if path.suffix not in self.supported_extensions:
                logger.warning(f"Unsupported file extension: {path.suffix}")
                return [], []

            logger.info(f"Parsing file: {path}")

            content = path.read_text(encoding="utf-8")

            if path.suffix == ".py":
                entities, relationships = self._parse_python_with_relationships(
                    content, str(path)
                )
            elif path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
                entities, relationships = self._parse_js_with_relationships(
                    content, str(path)
                )
            else:
                entities, relationships = [], []

            self.parsed_files.append(str(path))
            self.code_entities.extend(entities)

            logger.info(
                f"Parsed {len(entities)} entities and {len(relationships)} "
                f"relationships from {path}"
            )
            return entities, relationships

        except Exception as e:
            logger.error(f"Error parsing file {path}: {e!s}")
            return [], []

    def _parse_python_file(self, content: str, file_path: str) -> list[CodeEntity]:
        """Parse Python source code, returning entities only.

        Backward-compat shim that delegates to the relationship-aware
        parser and discards the relationship output.
        """
        entities, _ = self._parse_python_with_relationships(content, file_path)
        return entities

    def _parse_python_with_relationships(
        self, content: str, file_path: str
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Parse Python source and emit canonical Phase 2 edges.

        Uses a proper :class:`ast.NodeVisitor` so the enclosing scope
        chain is tracked accurately for nested classes, methods, and
        call sites within methods. The visitor populates two parallel
        lists in declaration order: entities and relationships. The
        relationship list contains:

        - One ``INHERITS`` per class base (``kind`` extends).
        - One ``IMPORTS`` per ``import`` / ``from-import`` alias.
        - One ``CALLS`` per ``ast.Call`` whose enclosing function or
          method is a known entity, with the call-site line as a
          property.
        """
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.error(f"Syntax error in Python file {file_path}: {e!s}")
            return [], []

        visitor = _PythonScopeVisitor(file_path=file_path, agent=self)
        visitor.visit(tree)
        return visitor.entities, visitor.relationships

    # The original _parse_python_file body is preserved below for
    # tests that exercise the (now-shimmed) entity-only path. New code
    # should call _parse_python_with_relationships.
    def _parse_python_file_legacy(
        self, content: str, file_path: str
    ) -> list[CodeEntity]:  # noqa: PLR0912 - retained for diff continuity
        try:
            tree = ast.parse(content)
            entities = []

            # PERFORMANCE: Build class method set and process all nodes in SINGLE walk
            # This reduces AST traversal from 2x to 1x (50% faster on large codebases)
            class_method_nodes = set()

            # OPTIMIZED: Single pass through the tree - collect class methods first
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Mark all functions in the class body as methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            class_method_nodes.add(id(item))

            # OPTIMIZED: Second single pass - process all node types
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Add the class entity
                    entity = self._create_class_entity(node, file_path)
                    entities.append(entity)

                elif isinstance(node, ast.FunctionDef):
                    # FIX: Check if this function is in our set of class methods
                    if id(node) not in class_method_nodes:
                        # This is a standalone function, not a method
                        entity = self._create_function_entity(node, file_path)
                        entities.append(entity)

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        entity = self._create_import_entity(alias, node, file_path)
                        entities.append(entity)

                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    for alias in node.names:
                        entity = self._create_import_entity(
                            alias, node, file_path, module_name
                        )
                        entities.append(entity)

                elif isinstance(node, ast.Assign):
                    # Extract variable assignments
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            entity = self._create_variable_entity(
                                target, node, file_path
                            )
                            entities.append(entity)

            return entities

        except SyntaxError as e:
            logger.error(f"Syntax error in Python file {file_path}: {e!s}")
            return []

    def _parse_js_with_relationships(
        self, content: str, file_path: str
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Parse JS/TS source via tree-sitter, falling back to regex.

        Per ADR-090 Phase 3, tree-sitter is the canonical JS/TS parser
        and emits the same CodeEntity / CodeRelationship shape as the
        Python visitor. The regex parser remains a degraded-mode
        fallback for environments without the native bindings; in that
        mode no relationships are emitted (the regex matcher cannot
        track scope).

        ``.ts`` and ``.tsx`` files are parsed with the JavaScript
        grammar. TypeScript-specific shapes (type annotations,
        interfaces, generic parameters) are absorbed by the parser as
        ERROR nodes and ignored; the structural skeleton (classes,
        methods, functions, imports, calls) parses correctly.
        """
        if _TREE_SITTER_JS_AVAILABLE:
            try:
                return self._parse_js_tree_sitter(content, file_path)
            except Exception as e:
                logger.warning(
                    f"tree-sitter parse failed for {file_path}, "
                    f"falling back to regex: {e}"
                )
        return self._parse_js_file(content, file_path), []

    def _parse_js_tree_sitter(
        self, content: str, file_path: str
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        parser = tree_sitter.Parser(_JS_LANGUAGE)
        tree = parser.parse(content.encode("utf-8"))
        visitor = _TreeSitterJSVisitor(file_path=file_path)
        visitor.visit(tree.root_node)
        return visitor.entities, visitor.relationships

    def _parse_js_file(self, content: str, file_path: str) -> list[CodeEntity]:
        """Parse JavaScript/TypeScript source code using regex (simplified)"""
        entities = []

        # Extract class definitions
        class_pattern = r"class\s+(\w+)(?:\s+extends\s+(\w+))?"
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            extends = match.group(2) if match.group(2) else None

            entity = CodeEntity(
                name=sanitize_for_graph_id(class_name),
                entity_type="class",
                file_path=file_path,
                line_number=content[: match.start()].count("\n") + 1,
                attributes={
                    "extends": sanitize_for_graph_id(extends) if extends else None
                },
            )
            entities.append(entity)

        # Extract function definitions
        function_pattern = r"function\s+(\w+)\s*\("
        for match in re.finditer(function_pattern, content):
            func_name = match.group(1)

            entity = CodeEntity(
                name=sanitize_for_graph_id(func_name),
                entity_type="function",
                file_path=file_path,
                line_number=content[: match.start()].count("\n") + 1,
            )
            entities.append(entity)

        # Extract arrow functions
        arrow_pattern = r"const\s+(\w+)\s*=\s*\([^)]*\)\s*=>"
        for match in re.finditer(arrow_pattern, content):
            func_name = match.group(1)

            entity = CodeEntity(
                name=sanitize_for_graph_id(func_name),
                entity_type="function",
                file_path=file_path,
                line_number=content[: match.start()].count("\n") + 1,
                attributes={"arrow_function": True},
            )
            entities.append(entity)

        # Extract imports
        import_pattern = r'import\s+(?:{[^}]*}|[^;\s]+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            module_path = match.group(1)

            entity = CodeEntity(
                name=sanitize_for_graph_id(Path(module_path).name),
                entity_type="import",
                file_path=file_path,
                line_number=content[: match.start()].count("\n") + 1,
                attributes={"module_path": module_path},
            )
            entities.append(entity)

        return entities

    def _create_class_entity(self, node: ast.ClassDef, file_path: str) -> CodeEntity:
        """Create CodeEntity for a Python class"""
        # Extract base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)

        # Extract methods
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)

        # Extract class variables
        class_vars = []
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        class_vars.append(target.id)

        sanitized_name = InputSanitizer.sanitize_for_graph_id(node.name)

        return CodeEntity(
            name=sanitized_name,
            entity_type="class",
            file_path=file_path,
            line_number=node.lineno,
            dependencies=[
                InputSanitizer.sanitize_for_graph_id(base) for base in base_classes
            ],
            attributes={
                "base_classes": [
                    InputSanitizer.sanitize_for_graph_id(base) for base in base_classes
                ],
                "methods": methods,
                "class_variables": class_vars,
                "docstring": ast.get_docstring(node),
            },
        )

    def _create_function_entity(
        self, node: ast.FunctionDef, file_path: str
    ) -> CodeEntity:
        """Create CodeEntity for a Python function"""
        # Extract parameters
        parameters = []
        for arg in node.args.args:
            parameters.append(arg.arg)

        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                decorators.append(
                    f"{decorator.value.id}.{decorator.attr}"
                    if hasattr(decorator.value, "id")
                    else str(decorator.attr)
                )

        sanitized_name = InputSanitizer.sanitize_for_graph_id(node.name)

        return CodeEntity(
            name=sanitized_name,
            entity_type="function",
            file_path=file_path,
            line_number=node.lineno,
            attributes={
                "parameters": parameters,
                "decorators": decorators,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "docstring": ast.get_docstring(node),
                "return_type": (
                    getattr(node.returns, "id", None) if node.returns else None
                ),
            },
        )

    def _create_import_entity(
        self,
        alias: ast.alias,
        node: Any,
        file_path: str,
        module_name: str | None = None,
    ) -> CodeEntity:
        """Create CodeEntity for an import statement"""
        import_name = alias.asname if alias.asname else alias.name
        source_module = module_name or alias.name

        sanitized_name = InputSanitizer.sanitize_for_graph_id(import_name)

        return CodeEntity(
            name=sanitized_name,
            entity_type="import",
            file_path=file_path,
            line_number=node.lineno,
            attributes={
                "source_module": source_module,
                "alias": alias.asname,
                "original_name": alias.name,
            },
        )

    def _create_variable_entity(
        self, target: ast.Name, node: ast.Assign, file_path: str
    ) -> CodeEntity:
        """Create CodeEntity for a variable assignment"""
        sanitized_name = InputSanitizer.sanitize_for_graph_id(target.id)

        # Extract value type if possible
        value_type = "unknown"
        if isinstance(node.value, ast.Constant):
            value_type = type(node.value.value).__name__
        elif isinstance(node.value, ast.Name):
            value_type = f"variable:{node.value.id}"
        elif isinstance(node.value, ast.Call):
            if hasattr(node.value.func, "id"):
                value_type = f"call:{node.value.func.id}"
            elif hasattr(node.value.func, "attr"):
                value_type = f"method:{node.value.func.attr}"

        return CodeEntity(
            name=sanitized_name,
            entity_type="variable",
            file_path=file_path,
            line_number=node.lineno,
            attributes={
                "value_type": value_type,
                "is_constant": target.id.isupper(),
                "is_private": target.id.startswith("_"),
                "is_magic": target.id.startswith("__") and target.id.endswith("__"),
            },
        )

    def parse_directory(
        self, directory_path: str, recursive: bool = True
    ) -> list[CodeEntity]:
        """
        Parse all supported files in a directory

        Args:
            directory_path: Path to directory to parse
            recursive: Whether to parse subdirectories

        Returns:
            List of all CodeEntity objects from parsed files
        """
        directory = Path(directory_path)
        if not directory.exists():
            logger.error(f"Directory not found: {directory_path}")
            return []

        all_entities = []

        # Find all supported files
        pattern = "**/*" if recursive else "*"
        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix in self.supported_extensions:
                entities = self.parse_file(str(file_path))
                all_entities.extend(entities)

        logger.info(
            f"Parsed {len(all_entities)} entities from directory: {directory_path}"
        )
        return all_entities

    def get_codebase_summary(self) -> dict[str, Any]:
        """Generate summary statistics of parsed codebase"""
        entities_by_type: dict[str, int] = {}
        files_by_extension: dict[str, int] = {}

        summary = {
            "total_files_parsed": len(self.parsed_files),
            "total_entities": len(self.code_entities),
            "entities_by_type": entities_by_type,
            "files_by_extension": files_by_extension,
            "top_dependencies": [],
            "complexity_metrics": {},
        }

        # Count entities by type
        for entity in self.code_entities:
            entity_type = entity.entity_type
            entities_by_type[entity_type] = entities_by_type.get(entity_type, 0) + 1

        # Count files by extension
        for file_path in self.parsed_files:
            ext = Path(file_path).suffix
            files_by_extension[ext] = files_by_extension.get(ext, 0) + 1

        # Extract top dependencies (import statements)
        imports = [e for e in self.code_entities if e.entity_type == "import"]
        dependency_counts: dict[str, int] = {}
        for import_entity in imports:
            source = (
                import_entity.attributes.get("source_module", "unknown")
                if import_entity.attributes
                else "unknown"
            )
            dependency_counts[source] = dependency_counts.get(source, 0) + 1

        summary["top_dependencies"] = sorted(
            dependency_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Calculate complexity metrics
        classes = [e for e in self.code_entities if e.entity_type == "class"]
        functions = [
            e for e in self.code_entities if e.entity_type in ["function", "method"]
        ]

        summary["complexity_metrics"] = {
            "total_classes": len(classes),
            "total_functions": len(functions),
            "avg_methods_per_class": sum(
                len(e.attributes.get("methods", [])) if e.attributes else 0
                for e in classes
            )
            / max(len(classes), 1),
            "total_imports": len(imports),
        }

        return summary


def sanitize_for_graph_id(input_string: str) -> str:
    """Legacy compatibility function for external usage"""
    return InputSanitizer.sanitize_for_graph_id(input_string)


class _TreeSitterJSVisitor:
    """Walks a tree-sitter JavaScript/TypeScript parse tree.

    Emits entities and relationships matching the Phase 2 Python
    visitor's shape, so the ingestion pipeline can treat both
    languages uniformly. Scope is tracked via class and function
    stacks; CALLS are attributed to the innermost enclosing function
    or method; INHERITS edges come from `class_heritage`; IMPORTS
    edges come from `import_statement` source strings.

    The visitor is conservative: nodes whose target name cannot be
    rendered as a single dotted identifier (subscripts, call-chain
    heads, complex destructuring) are skipped rather than guessed.
    Phase 4 cross-file resolution will turn the unresolved targets
    into qualified references.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.entities: list[CodeEntity] = []
        self.relationships: list[CodeRelationship] = []
        self._class_stack: list[str] = []
        self._function_stack: list[tuple[str, tuple[str, ...]]] = []

    # -- Public entry ----------------------------------------------------

    def visit(self, node) -> None:
        if node is None:
            return
        method = getattr(self, f"visit_{node.type}", None)
        if method is not None:
            method(node)
            return
        # Default traversal: visit every named child.
        for child in node.named_children:
            self.visit(child)

    # -- Class / method / function definitions ---------------------------

    def visit_class_declaration(self, node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            for child in node.named_children:
                self.visit(child)
            return
        class_name = self._text(name_node)
        sanitized = InputSanitizer.sanitize_for_graph_id(class_name)
        parent_chain = tuple(self._class_stack)

        entity = CodeEntity(
            name=sanitized,
            entity_type="class",
            file_path=self.file_path,
            line_number=self._line(node),
            parent_entity=parent_chain[-1] if parent_chain else None,
            parent_chain=parent_chain,
            attributes={"language": "javascript"},
        )
        self.entities.append(entity)

        # INHERITS edges from `class_heritage` (the `extends X` clause).
        # tree-sitter-javascript represents this as an unnamed
        # `extends_clause` containing an identifier or member expression.
        heritage = self._first_child_of_type(node, "class_heritage")
        if heritage is not None:
            for base in self._iter_heritage_targets(heritage):
                self.relationships.append(
                    CodeRelationship(
                        source_name=sanitized,
                        source_parent_chain=parent_chain,
                        target_name=_sanitize_dotted_name(base),
                        relationship=EdgeLabel.INHERITS.value,
                        properties={"kind": "extends", "line": self._line(node)},
                        file_path=self.file_path,
                    )
                )

        # Recurse into the class body so methods see the right parent.
        body = node.child_by_field_name("body")
        if body is not None:
            self._class_stack.append(sanitized)
            try:
                for child in body.named_children:
                    self.visit(child)
            finally:
                self._class_stack.pop()

    def visit_method_definition(self, node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        method_name = self._text(name_node)
        sanitized = InputSanitizer.sanitize_for_graph_id(method_name)
        parent_chain = tuple(self._class_stack)

        entity = CodeEntity(
            name=sanitized,
            entity_type="method",
            file_path=self.file_path,
            line_number=self._line(node),
            parent_entity=parent_chain[-1] if parent_chain else None,
            parent_chain=parent_chain,
            attributes={"language": "javascript"},
        )
        self.entities.append(entity)

        body = node.child_by_field_name("body")
        if body is not None:
            self._function_stack.append((sanitized, parent_chain))
            try:
                self._walk_body(body)
            finally:
                self._function_stack.pop()

    def visit_function_declaration(self, node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        func_name = self._text(name_node)
        sanitized = InputSanitizer.sanitize_for_graph_id(func_name)
        parent_chain = tuple(self._class_stack)

        entity = CodeEntity(
            name=sanitized,
            entity_type="function",
            file_path=self.file_path,
            line_number=self._line(node),
            parent_chain=parent_chain,
            attributes={"language": "javascript"},
        )
        self.entities.append(entity)

        body = node.child_by_field_name("body")
        if body is not None:
            self._function_stack.append((sanitized, parent_chain))
            try:
                self._walk_body(body)
            finally:
                self._function_stack.pop()

    def visit_lexical_declaration(self, node) -> None:
        # const/let bindings; declarators may hold arrow_function values
        # which we treat as function entities. Module-scope plain values
        # become variable entities; in-function variables are ignored to
        # match the Python visitor's behaviour.
        for declarator in node.named_children:
            if declarator.type != "variable_declarator":
                continue
            self._handle_variable_declarator(declarator)

    def visit_variable_declaration(self, node) -> None:
        # `var` declarations follow the same shape as lexical_declaration.
        self.visit_lexical_declaration(node)

    def _handle_variable_declarator(self, declarator) -> None:
        name_node = declarator.child_by_field_name("name")
        value_node = declarator.child_by_field_name("value")
        if name_node is None:
            return
        var_name = self._text(name_node)
        sanitized = InputSanitizer.sanitize_for_graph_id(var_name)

        # Arrow function bindings produce a function entity rather than
        # a variable, matching `const f = () => {}` semantics.
        if value_node is not None and value_node.type == "arrow_function":
            parent_chain = tuple(self._class_stack)
            entity = CodeEntity(
                name=sanitized,
                entity_type="function",
                file_path=self.file_path,
                line_number=self._line(declarator),
                parent_chain=parent_chain,
                attributes={"language": "javascript", "arrow_function": True},
            )
            self.entities.append(entity)

            body = value_node.child_by_field_name("body")
            if body is not None:
                self._function_stack.append((sanitized, parent_chain))
                try:
                    self._walk_body(body)
                finally:
                    self._function_stack.pop()
            return

        # Module-scope variables only.
        if not self._class_stack and not self._function_stack:
            self.entities.append(
                CodeEntity(
                    name=sanitized,
                    entity_type="variable",
                    file_path=self.file_path,
                    line_number=self._line(declarator),
                    attributes={"language": "javascript"},
                )
            )

    # -- Imports ---------------------------------------------------------

    def visit_import_statement(self, node) -> None:
        # The source is the string literal. Specifiers expand to one
        # entity per imported binding, with a shared IMPORTS edge per
        # specifier targeting the source module. Module specifiers
        # are JS-style path strings (``./foo``, ``react``,
        # ``@scope/pkg``) and are preserved verbatim as edge targets;
        # the dots they contain are path components, not identifier
        # separators.
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return
        source_module = self._strip_quotes(self._text(source_node))
        if not source_module:
            return

        names = list(self._iter_import_specifiers(node))
        if not names:
            # Side-effect-only import: ``import "./polyfills";``
            entity = CodeEntity(
                name=InputSanitizer.sanitize_for_graph_id(
                    self._import_entity_name(source_module)
                ),
                entity_type="import",
                file_path=self.file_path,
                line_number=self._line(node),
                attributes={
                    "language": "javascript",
                    "source_module": source_module,
                    "side_effect_only": True,
                },
            )
            self.entities.append(entity)
            self.relationships.append(
                CodeRelationship(
                    source_name=entity.name,
                    source_parent_chain=(),
                    target_name=source_module,
                    relationship=EdgeLabel.IMPORTS.value,
                    properties={"line": self._line(node)},
                    file_path=self.file_path,
                )
            )
            return

        for binding_name in names:
            entity = CodeEntity(
                name=InputSanitizer.sanitize_for_graph_id(binding_name),
                entity_type="import",
                file_path=self.file_path,
                line_number=self._line(node),
                attributes={
                    "language": "javascript",
                    "source_module": source_module,
                    "original_name": binding_name,
                },
            )
            self.entities.append(entity)
            self.relationships.append(
                CodeRelationship(
                    source_name=entity.name,
                    source_parent_chain=(),
                    target_name=source_module,
                    relationship=EdgeLabel.IMPORTS.value,
                    properties={"line": self._line(node)},
                    file_path=self.file_path,
                )
            )

    @staticmethod
    def _import_entity_name(source_module: str) -> str:
        """Derive a stable entity name for a side-effect-only import.

        ``./polyfills`` produces ``polyfills``; ``@scope/pkg`` produces
        ``pkg``; ``react`` stays ``react``. The full source string
        remains on the IMPORTS edge target and the entity attributes.
        """
        cleaned = source_module.lstrip("./@")
        # Take the trailing path segment.
        if "/" in cleaned:
            cleaned = cleaned.rsplit("/", 1)[-1]
        return cleaned or source_module

    # -- Function bodies / call sites -----------------------------------

    def _walk_body(self, body_node) -> None:
        """Walk a statement_block (or expression body) collecting calls."""
        for child in body_node.named_children:
            self._walk_for_calls(child)
            # Also let other handlers recurse into nested classes /
            # functions defined inside this body.
            if child.type in {
                "class_declaration",
                "function_declaration",
                "lexical_declaration",
                "variable_declaration",
                "method_definition",
            }:
                self.visit(child)

    def _walk_for_calls(self, node) -> None:
        if node is None:
            return
        if node.type == "call_expression":
            self._record_call(node)
        for child in node.named_children:
            # Don't recurse into nested function definitions; their
            # bodies are visited via their own scope frame.
            if child.type in {
                "function_declaration",
                "method_definition",
                "arrow_function",
                "function_expression",
            }:
                continue
            self._walk_for_calls(child)

    def _record_call(self, node) -> None:
        if not self._function_stack:
            return
        callee_node = node.child_by_field_name("function")
        if callee_node is None:
            return
        target = self._render_callee(callee_node)
        if not target:
            return
        caller_name, caller_parent_chain = self._function_stack[-1]
        self.relationships.append(
            CodeRelationship(
                source_name=caller_name,
                source_parent_chain=caller_parent_chain,
                target_name=_sanitize_dotted_name(target),
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": self._line(node)},
                file_path=self.file_path,
            )
        )

    # -- Helpers ---------------------------------------------------------

    def _text(self, node) -> str:
        try:
            return node.text.decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def _line(node) -> int:
        # tree-sitter is 0-indexed; align with Python ast (1-indexed).
        return node.start_point[0] + 1

    @staticmethod
    def _first_child_of_type(node, type_name: str):
        for child in node.named_children:
            if child.type == type_name:
                return child
        return None

    def _iter_heritage_targets(self, heritage_node):
        """Yield heritage target names from a class_heritage node."""
        for child in heritage_node.named_children:
            text = self._render_callee(child)
            if text:
                yield text

    def _render_callee(self, node) -> str | None:
        if node.type == "identifier":
            return self._text(node)
        if node.type == "member_expression":
            obj = node.child_by_field_name("object")
            prop = node.child_by_field_name("property")
            if obj is None or prop is None:
                return None
            obj_text = self._render_callee(obj)
            prop_text = self._text(prop)
            if obj_text and prop_text:
                return f"{obj_text}.{prop_text}"
            return None
        return None

    def _iter_import_specifiers(self, node):
        """Yield local binding names from an import_statement.

        Covers default, named, and namespace imports.
        """
        clause = self._first_child_of_type(node, "import_clause")
        if clause is None:
            return
        for child in clause.named_children:
            if child.type == "identifier":
                # `import Foo from "./foo";`
                yield self._text(child)
            elif child.type == "namespace_import":
                # `import * as Foo from "./foo";`
                ident = self._first_child_of_type(child, "identifier")
                if ident is not None:
                    yield self._text(ident)
            elif child.type == "named_imports":
                # `import { Foo, Bar as Baz } from "./foo";`
                for specifier in child.named_children:
                    if specifier.type == "import_specifier":
                        alias = specifier.child_by_field_name("alias")
                        name = specifier.child_by_field_name("name")
                        if alias is not None:
                            yield self._text(alias)
                        elif name is not None:
                            yield self._text(name)

    @staticmethod
    def _strip_quotes(s: str) -> str:
        if len(s) >= 2 and s[0] == s[-1] and s[0] in {"'", '"', "`"}:
            return s[1:-1]
        return s


def _sanitize_dotted_name(name: str) -> str:
    """Sanitize a possibly-dotted name without collapsing the dots.

    Edge target names carry semantic meaning when they contain dots
    (``module.Submodule.Class``, ``self.method``); the dot is the
    boundary between identifiers, not part of any single one. This
    helper sanitizes each segment with the standard graph-id rules
    while preserving the dotted structure.
    """
    if not name:
        return name
    parts = name.split(".")
    return ".".join(InputSanitizer.sanitize_for_graph_id(part) for part in parts)


class _PythonScopeVisitor(ast.NodeVisitor):
    """Scope-aware visitor that emits Phase 2 entities and relationships.

    Tracks the enclosing class chain so methods land with the right
    parent, and the enclosing function so call sites can name their
    caller. The visitor is single-pass; declaration order is
    preserved, which is important for the integer-suffix
    disambiguation strategy in :class:`src.services.graph.fqn.FQNBuilder`.
    """

    def __init__(self, file_path: str, agent: "ASTParserAgent"):
        self.file_path = file_path
        self.agent = agent
        self.entities: list[CodeEntity] = []
        self.relationships: list[CodeRelationship] = []
        # Stack of enclosing class names, root-most first.
        self._class_stack: list[str] = []
        # Current enclosing function/method, if any. Used to attribute
        # CALLS edges to their caller.
        self._function_stack: list[tuple[str, tuple[str, ...]]] = []

    # -- Class definitions -----------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        sanitized = InputSanitizer.sanitize_for_graph_id(node.name)
        parent_chain = tuple(self._class_stack)

        entity = self.agent._create_class_entity(node, self.file_path)
        entity.parent_entity = parent_chain[-1] if parent_chain else None
        entity.parent_chain = parent_chain
        self.entities.append(entity)

        # INHERITS edges, one per declared base. Bare ast.Name bases are
        # the common shape (``class Foo(Bar):``); ast.Attribute covers
        # ``class Foo(module.Base):`` patterns. Other base shapes
        # (subscripted generics, calls) are skipped — they cannot be
        # rendered as a single target name and are better resolved
        # by Phase 4 cross-file resolution. Target names preserve any
        # dots in the attribute chain because they carry semantic
        # meaning (module path) that downstream FQN matching depends
        # on; only the per-segment identifiers are sanitized.
        for base in node.bases:
            base_name = self._render_base_name(base)
            if not base_name:
                continue
            self.relationships.append(
                CodeRelationship(
                    source_name=sanitized,
                    source_parent_chain=parent_chain,
                    target_name=_sanitize_dotted_name(base_name),
                    relationship=EdgeLabel.INHERITS.value,
                    properties={"kind": "extends", "line": node.lineno},
                    file_path=self.file_path,
                )
            )

        # Recurse into the class body with this class on the stack so
        # nested classes and methods see the right parent chain.
        self._class_stack.append(sanitized)
        try:
            for item in node.body:
                self.visit(item)
        finally:
            self._class_stack.pop()

    # -- Function/method definitions -------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        sanitized = InputSanitizer.sanitize_for_graph_id(node.name)
        parent_chain = tuple(self._class_stack)

        if self._class_stack:
            entity = self.agent._create_function_entity(node, self.file_path)
            entity.entity_type = "method"
            entity.parent_entity = parent_chain[-1]
        else:
            entity = self.agent._create_function_entity(node, self.file_path)
        entity.parent_chain = parent_chain
        self.entities.append(entity)

        self._function_stack.append((sanitized, parent_chain))
        try:
            for item in node.body:
                self.visit(item)
        finally:
            self._function_stack.pop()

    # -- Imports ---------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            entity = self.agent._create_import_entity(alias, node, self.file_path)
            self.entities.append(entity)
            target_module = alias.name
            self.relationships.append(
                CodeRelationship(
                    source_name=entity.name,
                    source_parent_chain=(),
                    target_name=_sanitize_dotted_name(target_module),
                    relationship=EdgeLabel.IMPORTS.value,
                    properties={"line": node.lineno},
                    file_path=self.file_path,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = node.module or ""
        for alias in node.names:
            entity = self.agent._create_import_entity(
                alias, node, self.file_path, module_name
            )
            self.entities.append(entity)
            # The IMPORTS edge target is the source module being
            # imported from, not the leaf symbol.
            target_module = module_name or alias.name
            if not target_module:
                continue
            self.relationships.append(
                CodeRelationship(
                    source_name=entity.name,
                    source_parent_chain=(),
                    target_name=_sanitize_dotted_name(target_module),
                    relationship=EdgeLabel.IMPORTS.value,
                    properties={"line": node.lineno},
                    file_path=self.file_path,
                )
            )

    # -- Module-level assignments ----------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        # Only emit variable entities at module scope to match the
        # legacy parser's behaviour. Class/function-local assignments
        # are noise for the graph today.
        if not self._class_stack and not self._function_stack:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    entity = self.agent._create_variable_entity(
                        target, node, self.file_path
                    )
                    self.entities.append(entity)
        self.generic_visit(node)

    # -- Call sites ------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        if self._function_stack:
            caller_name, caller_parent_chain = self._function_stack[-1]
            target = self._render_call_target(node.func)
            if target:
                self.relationships.append(
                    CodeRelationship(
                        source_name=caller_name,
                        source_parent_chain=caller_parent_chain,
                        target_name=_sanitize_dotted_name(target),
                        relationship=EdgeLabel.CALLS.value,
                        properties={"call_site_line": node.lineno},
                        file_path=self.file_path,
                    )
                )
        # Recurse so nested calls (`f(g(x))`) attribute correctly to
        # the same caller.
        self.generic_visit(node)

    # -- Helpers ---------------------------------------------------------

    @staticmethod
    def _render_base_name(node: ast.expr) -> str | None:
        """Render a class-base AST node as a single name string.

        Returns None for shapes the parser cannot represent as a
        deterministic target (e.g. ``Generic[T]``). These are skipped
        rather than guessed.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return _PythonScopeVisitor._render_attribute_chain(node)
        return None

    @staticmethod
    def _render_call_target(node: ast.expr) -> str | None:
        """Render the callee of an ``ast.Call`` as a name string.

        Bare names (``foo(...)``) and dotted accesses (``obj.method(...)``,
        ``module.func(...)``) produce a name; expressions whose head is
        a more complex shape (a call, a subscript) are skipped because
        a single edge target name would be misleading.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return _PythonScopeVisitor._render_attribute_chain(node)
        return None

    @staticmethod
    def _render_attribute_chain(node: ast.Attribute) -> str | None:
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
        return None


def main():
    """Demonstration of ASTParserAgent capabilities"""
    print("🔍 Aura Platform - AST Parser Agent Demo")
    print("=" * 50)

    # Initialize parser
    parser = ASTParserAgent()

    # Parse the sample project directory
    sample_dir = get_sample_project_path()
    if sample_dir.exists():
        entities = parser.parse_directory(str(sample_dir))

        print("📊 Parse Results:")
        print(f"  • Total entities parsed: {len(entities)}")

        # Show entities by type
        summary = parser.get_codebase_summary()
        print("\n📈 Codebase Summary:")
        for entity_type, count in summary["entities_by_type"].items():
            print(f"  • {entity_type.title()}: {count}")

        print("\n📁 Files by Extension:")
        for ext, count in summary["files_by_extension"].items():
            print(f"  • {ext}: {count} files")

        print("\n🔗 Top Dependencies:")
        for dep, count in summary["top_dependencies"][:5]:
            print(f"  • {dep}: {count} imports")

        print("\n📏 Complexity Metrics:")
        metrics = summary["complexity_metrics"]
        for metric, value in metrics.items():
            print(f"  • {metric.replace('_', ' ').title()}: {value}")

    else:
        print("Sample project directory not found. Creating sample files...")

        # Create sample directory and files
        sample_dir.mkdir(parents=True, exist_ok=True)

        sample_code = '''import hashlib
import logging

class DataProcessor:
    """Data processing utility"""

    def calculate_checksum(self, data: str) -> str:
        """Calculate checksum using SHA-1"""
        return hashlib.sha1(data.encode()).hexdigest()

    def process_data(self, input_data: str) -> dict:
        """Process input data"""
        checksum = self.calculate_checksum(input_data)
        return {"processed": True, "checksum": checksum}

def main():
    processor = DataProcessor()
    result = processor.process_data("test data")
    print(result)

if __name__ == "__main__":
    main()
'''

        main_file = sample_dir / "main.py"
        main_file.write_text(sample_code)

        print(f"Created sample file: {main_file}")

        # Parse the sample file
        entities = parser.parse_file(str(main_file))
        print(f"Parsed {len(entities)} entities from sample file")

        # Show parsed entities
        for entity in entities:
            print(
                f"  • {entity.entity_type.title()}: {entity.name} (line {entity.line_number})"
            )

    print("\n" + "=" * 50)
    print("AST Parser Agent demonstration completed!")


if __name__ == "__main__":
    main()
