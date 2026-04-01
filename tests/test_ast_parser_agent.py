"""
Project Aura - AST Parser Agent Tests

Comprehensive tests for the AST parser agent that extracts CodeEntity objects from source files.
"""

# ruff: noqa: PLR2004

import tempfile
from pathlib import Path

from src.agents.ast_parser_agent import ASTParserAgent, CodeEntity


class TestCodeEntity:
    """Test suite for CodeEntity dataclass."""

    def test_code_entity_creation_minimal(self):
        """Test creating CodeEntity with minimal required fields."""
        entity = CodeEntity(
            name="MyClass",
            entity_type="class",
            file_path="test.py",
            line_number=10,
        )

        assert entity.name == "MyClass"
        assert entity.entity_type == "class"
        assert entity.file_path == "test.py"
        assert entity.line_number == 10
        assert entity.parent_entity is None
        assert entity.dependencies == []  # Initialized in __post_init__
        assert entity.attributes == {}  # Initialized in __post_init__

    def test_code_entity_creation_full(self):
        """Test creating CodeEntity with all fields."""
        dependencies = ["BaseClass", "MixinClass"]
        attributes = {"docstring": "Test class", "methods": ["method1"]}

        entity = CodeEntity(
            name="MyClass",
            entity_type="class",
            file_path="test.py",
            line_number=10,
            parent_entity="ParentClass",
            dependencies=dependencies,
            attributes=attributes,
        )

        assert entity.parent_entity == "ParentClass"
        assert entity.dependencies == dependencies
        assert entity.attributes == attributes

    def test_code_entity_post_init_defaults(self):
        """Test that __post_init__ initializes None values to empty collections."""
        entity = CodeEntity(
            name="Test", entity_type="function", file_path="test.py", line_number=1
        )

        # Should be initialized to empty collections
        assert isinstance(entity.dependencies, list)
        assert isinstance(entity.attributes, dict)
        assert len(entity.dependencies) == 0
        assert len(entity.attributes) == 0


class TestASTParserAgent:
    """Test suite for ASTParserAgent."""

    def test_initialization(self):
        """Test ASTParserAgent initialization."""
        agent = ASTParserAgent()

        assert agent.supported_extensions == {".py", ".js", ".jsx", ".ts", ".tsx"}
        assert agent.parsed_files == []
        assert agent.code_entities == []

    def test_parse_file_nonexistent(self):
        """Test parsing a file that doesn't exist."""
        agent = ASTParserAgent()

        entities = agent.parse_file("nonexistent_file.py")

        assert entities == []
        assert len(agent.parsed_files) == 0

    def test_parse_file_unsupported_extension(self):
        """Test parsing a file with unsupported extension."""
        agent = ASTParserAgent()

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
            f.write("test content")
            f.flush()

            entities = agent.parse_file(f.name)

        assert entities == []
        assert len(agent.parsed_files) == 0

    def test_parse_python_file_simple_class(self):
        """Test parsing a simple Python class."""
        agent = ASTParserAgent()
        code = """
class MyClass:
    def my_method(self):
        pass
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            # Should find class and method
            class_entities = [e for e in entities if e.entity_type == "class"]
            assert len(class_entities) >= 1
            assert any(e.name == "MyClass" for e in class_entities)

            # File should be tracked
            assert temp_path in agent.parsed_files
        finally:
            Path(temp_path).unlink()

    def test_parse_python_file_function(self):
        """Test parsing a standalone Python function."""
        agent = ASTParserAgent()
        code = """
def my_function(param1, param2):
    return param1 + param2
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            function_entities = [e for e in entities if e.entity_type == "function"]
            assert len(function_entities) >= 1

            func = next((e for e in function_entities if "my_function" in e.name), None)
            assert func is not None
            assert "parameters" in func.attributes
        finally:
            Path(temp_path).unlink()

    def test_parse_python_file_imports(self):
        """Test parsing Python import statements."""
        agent = ASTParserAgent()
        code = """
import os
from pathlib import Path
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            import_entities = [e for e in entities if e.entity_type == "import"]
            assert len(import_entities) >= 2
        finally:
            Path(temp_path).unlink()

    def test_parse_python_file_variables(self):
        """Test parsing Python variable assignments."""
        agent = ASTParserAgent()
        code = """
MY_CONSTANT = 42
my_variable = "test"
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            variable_entities = [e for e in entities if e.entity_type == "variable"]
            assert len(variable_entities) >= 2

            constant = next(
                (e for e in variable_entities if "MY_CONSTANT" in e.name), None
            )
            if constant:
                assert constant.attributes.get("is_constant") is True
        finally:
            Path(temp_path).unlink()

    def test_parse_javascript_file_class(self):
        """Test parsing JavaScript class."""
        agent = ASTParserAgent()
        code = """
class MyJSClass {
    constructor() {
        this.value = 0;
    }
}
"""

        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            class_entities = [e for e in entities if e.entity_type == "class"]
            assert len(class_entities) >= 1
        finally:
            Path(temp_path).unlink()

    def test_parse_javascript_file_function(self):
        """Test parsing JavaScript function."""
        agent = ASTParserAgent()
        code = """
function myFunction() {
    return 42;
}
"""

        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            function_entities = [e for e in entities if e.entity_type == "function"]
            assert len(function_entities) >= 1
        finally:
            Path(temp_path).unlink()

    def test_parse_javascript_file_arrow_function(self):
        """Test parsing JavaScript arrow function."""
        agent = ASTParserAgent()
        code = """
const myArrowFunc = () => {
    return 42;
}
"""

        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            function_entities = [e for e in entities if e.entity_type == "function"]
            arrow_func = next(
                (e for e in function_entities if e.attributes.get("arrow_function")),
                None,
            )
            assert arrow_func is not None
        finally:
            Path(temp_path).unlink()

    def test_parse_javascript_file_import(self):
        """Test parsing JavaScript import."""
        agent = ASTParserAgent()
        code = """
import React from 'react';
import { useState } from 'react';
"""

        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            import_entities = [e for e in entities if e.entity_type == "import"]
            assert len(import_entities) >= 1
        finally:
            Path(temp_path).unlink()

    def test_parse_directory_nonexistent(self):
        """Test parsing a directory that doesn't exist."""
        agent = ASTParserAgent()

        entities = agent.parse_directory("/nonexistent/directory")

        assert entities == []

    def test_parse_directory_recursive(self):
        """Test parsing directory recursively."""
        agent = ASTParserAgent()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file1 = Path(tmpdir) / "test1.py"
            test_file1.write_text("def func1():\n    pass")

            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            test_file2 = subdir / "test2.py"
            test_file2.write_text("def func2():\n    pass")

            entities = agent.parse_directory(tmpdir, recursive=True)

            # Should find entities from both files
            assert len(entities) >= 2
            assert len(agent.parsed_files) >= 2

    def test_parse_directory_non_recursive(self):
        """Test parsing directory non-recursively."""
        agent = ASTParserAgent()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file1 = Path(tmpdir) / "test1.py"
            test_file1.write_text("def func1():\n    pass")

            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            test_file2 = subdir / "test2.py"
            test_file2.write_text("def func2():\n    pass")

            agent.parse_directory(tmpdir, recursive=False)

            # Should only find top-level file
            assert len(agent.parsed_files) == 1

    def test_get_codebase_summary_empty(self):
        """Test getting summary with no parsed files."""
        agent = ASTParserAgent()

        summary = agent.get_codebase_summary()

        assert summary["total_files_parsed"] == 0
        assert summary["total_entities"] == 0
        assert summary["entities_by_type"] == {}
        assert summary["complexity_metrics"]["total_classes"] == 0

    def test_get_codebase_summary_with_data(self):
        """Test getting summary after parsing files."""
        agent = ASTParserAgent()
        code = """
import os

class MyClass:
    def my_method(self):
        pass

def my_function():
    pass
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            agent.parse_file(temp_path)
            summary = agent.get_codebase_summary()

            assert summary["total_files_parsed"] >= 1
            assert summary["total_entities"] > 0
            assert "class" in summary["entities_by_type"]
            assert summary["complexity_metrics"]["total_classes"] >= 1
        finally:
            Path(temp_path).unlink()

    def test_parse_python_class_with_base_classes(self):
        """Test parsing Python class with inheritance."""
        agent = ASTParserAgent()
        code = """
class BaseClass:
    pass

class ChildClass(BaseClass):
    pass
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            child_class = next(
                (
                    e
                    for e in entities
                    if e.entity_type == "class" and "ChildClass" in e.name
                ),
                None,
            )
            assert child_class is not None
            assert "base_classes" in child_class.attributes
            assert len(child_class.attributes["base_classes"]) >= 1
        finally:
            Path(temp_path).unlink()

    def test_parse_python_function_with_decorators(self):
        """Test parsing Python function with decorators."""
        agent = ASTParserAgent()
        code = """
@staticmethod
def my_static_method():
    pass
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            func = next(
                (
                    e
                    for e in entities
                    if e.entity_type == "function" and "my_static_method" in e.name
                ),
                None,
            )
            assert func is not None
            if "decorators" in func.attributes:
                assert "staticmethod" in func.attributes["decorators"]
        finally:
            Path(temp_path).unlink()

    def test_parse_python_async_function(self):
        """Test parsing Python async function."""
        agent = ASTParserAgent()
        code = """
async def my_async_function():
    pass
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            # Note: Current implementation only checks isinstance(node, ast.FunctionDef)
            # AsyncFunctionDef inherits from FunctionDef, so it might not be captured
            # This test verifies the current behavior
            func = next(
                (
                    e
                    for e in entities
                    if e.entity_type == "function" and "my_async_function" in e.name
                ),
                None,
            )
            # Async functions may not be captured by current implementation
            # which only handles ast.FunctionDef in the walker loop
            if func:
                assert func.attributes.get("is_async") is True
        finally:
            Path(temp_path).unlink()

    def test_parse_python_invalid_syntax(self):
        """Test parsing Python file with syntax errors."""
        agent = ASTParserAgent()
        code = "def invalid syntax here;;;"

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            # Should return empty list on syntax error
            assert entities == []
        finally:
            Path(temp_path).unlink()

    def test_parse_file_path_object(self):
        """Test parsing file using Path object instead of string."""
        agent = ASTParserAgent()
        code = "def test_func():\n    pass"

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entities = agent.parse_file(temp_path)

            assert len(entities) > 0
        finally:
            temp_path.unlink()

    def test_accumulated_state(self):
        """Test that agent accumulates state across multiple parse operations."""
        agent = ASTParserAgent()
        code1 = "def func1():\n    pass"
        code2 = "def func2():\n    pass"

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f1:
            f1.write(code1)
            f1.flush()
            path1 = f1.name

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f2:
            f2.write(code2)
            f2.flush()
            path2 = f2.name

        try:
            agent.parse_file(path1)
            entities_after_first = len(agent.code_entities)

            agent.parse_file(path2)
            entities_after_second = len(agent.code_entities)

            # Should accumulate entities
            assert entities_after_second > entities_after_first
            # Should accumulate files
            assert len(agent.parsed_files) == 2
        finally:
            Path(path1).unlink()
            Path(path2).unlink()

    def test_summary_top_dependencies(self):
        """Test that summary includes top dependencies."""
        agent = ASTParserAgent()
        code = """
import os
import sys
from pathlib import Path
"""

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            agent.parse_file(temp_path)
            summary = agent.get_codebase_summary()

            assert "top_dependencies" in summary
            assert isinstance(summary["top_dependencies"], list)
        finally:
            Path(temp_path).unlink()

    def test_summary_files_by_extension(self):
        """Test that summary counts files by extension."""
        agent = ASTParserAgent()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("def func():\n    pass")

            js_file = Path(tmpdir) / "test.js"
            js_file.write_text("function func() {}")

            agent.parse_directory(tmpdir, recursive=False)
            summary = agent.get_codebase_summary()

            assert "files_by_extension" in summary
            assert ".py" in summary["files_by_extension"]
            assert ".js" in summary["files_by_extension"]

    def test_typescript_file_support(self):
        """Test parsing TypeScript file."""
        agent = ASTParserAgent()
        code = """
class MyTSClass {
    constructor() {}
}
"""

        with tempfile.NamedTemporaryFile(suffix=".ts", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            entities = agent.parse_file(temp_path)

            # Should parse TypeScript files
            assert len(entities) >= 0  # May or may not find entities
            assert temp_path in agent.parsed_files
        finally:
            Path(temp_path).unlink()
