"""Path configuration for test fixtures and workspaces.

This module provides centralized path resolution for test fixtures and sample
projects used by Aura agents. It supports multiple environments:
- Local development (repository-relative paths)
- Container deployments (workspace root configuration)
- CI/CD pipelines (explicit path overrides)
"""

import os
from pathlib import Path

# Default fixture location (relative to repo root)
DEFAULT_FIXTURE_DIR = "tests/fixtures/sample_project"


def get_repo_root() -> Path:
    """Get the repository root directory.

    Returns:
        Path to the repository root (parent of src/)
    """
    return Path(__file__).parent.parent.parent


def get_sample_project_path() -> Path:
    """Get the sample project path for agent testing.

    Resolution order:
    1. AURA_SAMPLE_PROJECT_PATH env var (explicit override)
    2. AURA_WORKSPACE_ROOT + /sample_project (container deployment)
    3. Repository-relative default (local development)

    Returns:
        Path to sample project directory

    Example:
        >>> path = get_sample_project_path()
        >>> # Local dev: /path/to/repo/tests/fixtures/sample_project
        >>> # Container: /app/workspace/sample_project
        >>> # CI/CD: /codebuild/output/sample_project (if env var set)
    """
    # Explicit override (highest priority)
    if explicit := os.environ.get("AURA_SAMPLE_PROJECT_PATH"):
        return Path(explicit)

    # Container workspace (production sandboxes)
    if workspace_root := os.environ.get("AURA_WORKSPACE_ROOT"):
        return Path(workspace_root) / "sample_project"

    # Local development (repository-relative)
    return get_repo_root() / DEFAULT_FIXTURE_DIR


def get_workspace_root() -> Path:
    """Get the workspace root for agent operations.

    This is the root directory where agents can read/write code.
    In production sandboxes, this is an isolated workspace.
    In development, this defaults to the repository root.

    Returns:
        Path to workspace root directory
    """
    if workspace_root := os.environ.get("AURA_WORKSPACE_ROOT"):
        return Path(workspace_root)

    return get_repo_root()
