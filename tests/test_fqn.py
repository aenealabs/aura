"""Tests for Aura FQN construction (ADR-090 Phase 1).

Includes the pathological-case fixture set required by ADR-090's
testing strategy: nested classes, overloads, decorator-produced
duplicates, source-tree-root variations, and unknown extensions.
"""

from __future__ import annotations

import pytest

from src.services.graph.fqn import (
    FQNBuilder,
    FQNComponents,
    compute_fqn,
    derive_module_path,
    derive_scheme,
)


class TestDeriveScheme:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("src/myapp/auth.py", "python"),
            ("auth.pyi", "python"),
            ("src/auth.ts", "typescript"),
            ("src/auth.tsx", "typescript"),
            ("auth.js", "javascript"),
            ("auth.jsx", "javascript"),
            ("auth.mjs", "javascript"),
            ("auth.cjs", "javascript"),
            ("README.md", "unknown"),
            ("Makefile", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_extension_to_scheme(self, path, expected):
        assert derive_scheme(path) == expected


class TestDeriveModulePath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            # Common: src/-rooted
            ("src/myapp/auth.py", "myapp.auth"),
            ("src/myapp/api/main.py", "myapp.api.main"),
            # lib/ and app/ also stripped
            ("lib/utils.py", "utils"),
            ("app/handlers/health.py", "handlers.health"),
            # No source-tree root
            ("myapp/api/main.py", "myapp.api.main"),
            # Nested src/ under another folder is NOT stripped (only leading)
            ("frontend/src/components/Button.tsx", "frontend.src.components.Button"),
            # Top-level file
            ("module.py", "module"),
            # TypeScript
            ("src/auth.ts", "auth"),
        ],
    )
    def test_path_to_dotted_module(self, path, expected):
        assert derive_module_path(path) == expected

    def test_empty_path(self):
        assert derive_module_path("") == "<unknown>"

    def test_only_root_strips_to_unknown(self):
        # A path that becomes empty after stripping the source-tree root
        # gracefully degrades rather than producing an empty string.
        assert derive_module_path("src/") == "<unknown>"

    def test_no_extension_keeps_filename(self):
        # Files like Makefile or extensionless scripts retain their name.
        assert derive_module_path("scripts/Makefile") == "scripts.Makefile"


class TestComputeFQN:
    def test_top_level_class(self):
        fqn = compute_fqn(
            name="App",
            kind="class",
            file_path="src/myapp/api/main.py",
            repo_id="owner/repo",
        )
        assert fqn == "python:owner/repo:myapp.api.main:App#class"

    def test_method_on_class(self):
        fqn = compute_fqn(
            name="handle_request",
            kind="method",
            file_path="src/myapp/api/main.py",
            repo_id="owner/repo",
            parent_chain=("App",),
        )
        assert fqn == "python:owner/repo:myapp.api.main:App.handle_request#method"

    def test_nested_class_path(self):
        fqn = compute_fqn(
            name="timeout",
            kind="variable",
            file_path="src/myapp/api/main.py",
            repo_id="owner/repo",
            parent_chain=("Router", "Config"),
        )
        assert fqn == "python:owner/repo:myapp.api.main:Router.Config.timeout#variable"

    def test_disambiguator_appended(self):
        fqn = compute_fqn(
            name="handle_request",
            kind="method",
            file_path="src/myapp/api/main.py",
            repo_id="owner/repo",
            parent_chain=("App",),
            disambiguator=1,
        )
        assert fqn.endswith("@1")

    def test_typescript_function(self):
        fqn = compute_fqn(
            name="verifyToken",
            kind="function",
            file_path="src/auth.ts",
            repo_id="owner/repo",
        )
        assert fqn == "typescript:owner/repo:auth:verifyToken#function"

    def test_repo_scoping_distinguishes_same_symbol(self):
        a = compute_fqn(
            name="User",
            kind="class",
            file_path="src/utils.py",
            repo_id="orgA/repo",
        )
        b = compute_fqn(
            name="User",
            kind="class",
            file_path="src/utils.py",
            repo_id="orgB/repo",
        )
        assert a != b
        assert "orgA/repo" in a
        assert "orgB/repo" in b


class TestFQNBuilder:
    def test_first_emission_has_no_disambiguator(self):
        builder = FQNBuilder(repo_id="owner/repo")
        fqn = builder.build(
            name="verify",
            kind="method",
            file_path="src/auth.py",
            parent_chain=("User",),
        )
        assert fqn == "python:owner/repo:auth:User.verify#method"
        assert "@" not in fqn

    def test_overload_increments(self):
        """Two methods with same (scope, name, kind) get @1, @2."""
        builder = FQNBuilder(repo_id="owner/repo")
        first = builder.build(
            name="verify",
            kind="method",
            file_path="src/auth.py",
            parent_chain=("User",),
        )
        second = builder.build(
            name="verify",
            kind="method",
            file_path="src/auth.py",
            parent_chain=("User",),
        )
        third = builder.build(
            name="verify",
            kind="method",
            file_path="src/auth.py",
            parent_chain=("User",),
        )
        assert first.endswith("#method")
        assert second.endswith("@1")
        assert third.endswith("@2")

    def test_different_parent_chain_does_not_collide(self):
        """User.verify and Admin.verify are distinct keys."""
        builder = FQNBuilder(repo_id="owner/repo")
        a = builder.build(
            name="verify",
            kind="method",
            file_path="src/auth.py",
            parent_chain=("User",),
        )
        b = builder.build(
            name="verify",
            kind="method",
            file_path="src/auth.py",
            parent_chain=("Admin",),
        )
        # Neither should be disambiguated; they're in different scopes.
        assert "@" not in a
        assert "@" not in b
        assert a != b

    def test_different_kind_does_not_collide(self):
        """A class named 'verify' and a function named 'verify' are distinct."""
        builder = FQNBuilder(repo_id="owner/repo")
        a = builder.build(name="verify", kind="class", file_path="src/auth.py")
        b = builder.build(name="verify", kind="function", file_path="src/auth.py")
        assert "@" not in a
        assert "@" not in b
        assert a != b

    def test_different_module_does_not_collide(self):
        builder = FQNBuilder(repo_id="owner/repo")
        a = builder.build(name="User", kind="class", file_path="src/auth.py")
        b = builder.build(name="User", kind="class", file_path="src/admin.py")
        assert "@" not in a
        assert "@" not in b
        assert a != b

    def test_reset_clears_collision_state(self):
        builder = FQNBuilder(repo_id="owner/repo")
        builder.build(name="verify", kind="method", file_path="src/auth.py")
        builder.reset()
        # Second emission, post-reset, should not be disambiguated.
        fqn = builder.build(name="verify", kind="method", file_path="src/auth.py")
        assert "@" not in fqn


class TestFQNComponentsRoundTrip:
    """Components → string → reparse should be lossless for canonical inputs."""

    def test_components_to_string_basic(self):
        comp = FQNComponents(
            scheme="python",
            repo_id="owner/repo",
            module_path="myapp.auth",
            symbol_path="User.verify",
            kind="method",
        )
        assert comp.to_string() == "python:owner/repo:myapp.auth:User.verify#method"

    def test_components_to_string_with_disambiguator(self):
        comp = FQNComponents(
            scheme="python",
            repo_id="owner/repo",
            module_path="myapp.auth",
            symbol_path="User.verify",
            kind="method",
            disambiguator=2,
        )
        assert comp.to_string().endswith("@2")


class TestPathologicalFixtures:
    """ADR-090 pathological-case suite.

    These mirror the fixture set the ADR mandates for Phase 4 testing,
    but the FQN layer must already handle the relevant subset
    (nested classes, decorator duplicates, source-tree variations).
    """

    def test_three_level_nested_class(self):
        fqn = compute_fqn(
            name="leaf",
            kind="method",
            file_path="src/deep.py",
            repo_id="owner/repo",
            parent_chain=("Outer", "Mid", "Inner"),
        )
        assert fqn == "python:owner/repo:deep:Outer.Mid.Inner.leaf#method"

    def test_decorator_produced_duplicate_methods(self):
        """A decorator that emits two methods with the same name gets disambiguated."""
        builder = FQNBuilder(repo_id="owner/repo")
        first = builder.build(
            name="get",
            kind="method",
            file_path="src/api.py",
            parent_chain=("Router",),
        )
        second = builder.build(
            name="get",
            kind="method",
            file_path="src/api.py",
            parent_chain=("Router",),
        )
        # Order-preserved suffixing
        assert first.endswith("#method")
        assert second.endswith("@1")

    def test_repo_id_with_slash(self):
        fqn = compute_fqn(
            name="X",
            kind="class",
            file_path="src/x.py",
            repo_id="owner/sub-org/repo",
        )
        assert "owner/sub-org/repo" in fqn

    def test_unknown_extension_still_produces_fqn(self):
        fqn = compute_fqn(
            name="thing",
            kind="variable",
            file_path="data/config.yaml",
            repo_id="owner/repo",
        )
        # Scheme degrades to "unknown"; module path follows convention.
        assert fqn.startswith("unknown:owner/repo:")
        # The .yaml is dropped; data is not a source-tree root.
        assert "data.config" in fqn

    def test_namespace_package_path(self):
        """Namespace packages (no __init__.py) still map cleanly."""
        fqn = compute_fqn(
            name="handler",
            kind="function",
            file_path="src/myorg/myapp/handlers.py",
            repo_id="owner/repo",
        )
        assert fqn == ("python:owner/repo:myorg.myapp.handlers:handler#function")
