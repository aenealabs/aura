"""
Tests for path configuration module.

Tests the path resolution logic for test fixtures and workspaces
across different environments (local, container, CI/CD).
"""

import os
from pathlib import Path
from unittest.mock import patch

from src.config.paths import (
    DEFAULT_FIXTURE_DIR,
    get_repo_root,
    get_sample_project_path,
    get_workspace_root,
)


class TestGetRepoRoot:
    """Tests for get_repo_root function."""

    def test_returns_path_object(self):
        """Test that repo root returns a Path object."""
        root = get_repo_root()
        assert isinstance(root, Path)

    def test_repo_root_contains_src(self):
        """Test repo root contains src directory."""
        root = get_repo_root()
        assert (root / "src").exists()

    def test_repo_root_contains_tests(self):
        """Test repo root contains tests directory."""
        root = get_repo_root()
        assert (root / "tests").exists()


class TestGetSampleProjectPath:
    """Tests for get_sample_project_path function."""

    def test_default_local_path(self):
        """Test default local development path."""
        # Clear any env vars that might interfere
        with patch.dict(os.environ, {}, clear=True):
            # Re-import to clear any cached env
            os.environ.pop("AURA_SAMPLE_PROJECT_PATH", None)
            os.environ.pop("AURA_WORKSPACE_ROOT", None)

            path = get_sample_project_path()
            assert isinstance(path, Path)
            assert str(path).endswith(DEFAULT_FIXTURE_DIR)

    def test_explicit_override_path(self):
        """Test AURA_SAMPLE_PROJECT_PATH env var takes priority."""
        with patch.dict(
            os.environ, {"AURA_SAMPLE_PROJECT_PATH": "/custom/sample/path"}
        ):
            path = get_sample_project_path()
            assert path == Path("/custom/sample/path")

    def test_workspace_root_path(self):
        """Test AURA_WORKSPACE_ROOT creates container-style path."""
        with patch.dict(
            os.environ,
            {"AURA_WORKSPACE_ROOT": "/app/workspace", "AURA_SAMPLE_PROJECT_PATH": ""},
            clear=False,
        ):
            # Need to ensure AURA_SAMPLE_PROJECT_PATH is not set
            os.environ.pop("AURA_SAMPLE_PROJECT_PATH", None)
            path = get_sample_project_path()
            assert path == Path("/app/workspace/sample_project")

    def test_explicit_override_takes_priority_over_workspace(self):
        """Test explicit path takes priority over workspace root."""
        with patch.dict(
            os.environ,
            {
                "AURA_SAMPLE_PROJECT_PATH": "/explicit/path",
                "AURA_WORKSPACE_ROOT": "/app/workspace",
            },
        ):
            path = get_sample_project_path()
            assert path == Path("/explicit/path")


class TestGetWorkspaceRoot:
    """Tests for get_workspace_root function."""

    def test_default_is_repo_root(self):
        """Test default workspace root is repository root."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AURA_WORKSPACE_ROOT", None)
            path = get_workspace_root()
            assert path == get_repo_root()

    def test_env_var_override(self):
        """Test AURA_WORKSPACE_ROOT env var override."""
        with patch.dict(os.environ, {"AURA_WORKSPACE_ROOT": "/sandbox/workspace"}):
            path = get_workspace_root()
            assert path == Path("/sandbox/workspace")


class TestDefaultFixtureDir:
    """Tests for DEFAULT_FIXTURE_DIR constant."""

    def test_default_fixture_dir_value(self):
        """Test DEFAULT_FIXTURE_DIR has expected value."""
        assert DEFAULT_FIXTURE_DIR == "tests/fixtures/sample_project"
