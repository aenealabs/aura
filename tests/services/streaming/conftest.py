"""
Pytest fixtures for streaming analysis service tests.
"""

import pytest

from src.services.streaming import (
    AnalysisScope,
    CIProvider,
    DiffType,
    FileChange,
    StreamingAnalysisEngine,
    StreamingAnalysisRequest,
    StreamingConfig,
    reset_streaming_config,
    reset_streaming_engine,
    reset_streaming_metrics,
    set_streaming_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test."""
    reset_streaming_config()
    reset_streaming_engine()
    reset_streaming_metrics()
    yield
    reset_streaming_config()
    reset_streaming_engine()
    reset_streaming_metrics()


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = StreamingConfig.for_testing()
    set_streaming_config(config)
    return config


@pytest.fixture
def engine(test_config):
    """Create streaming analysis engine."""
    return StreamingAnalysisEngine(test_config)


@pytest.fixture
def sample_request():
    """Create sample analysis request."""
    return StreamingAnalysisRequest(
        request_id="req-001",
        repository_id="repo-001",
        commit_sha="abc123",
        base_sha="def456",
        changed_files=[
            FileChange(
                file_path="src/auth/login.py",
                diff_type=DiffType.MODIFIED,
                additions=50,
                deletions=10,
                language="python",
            ),
            FileChange(
                file_path="src/api/users.py",
                diff_type=DiffType.ADDED,
                additions=100,
                language="python",
            ),
        ],
        analysis_scope=AnalysisScope.INCREMENTAL,
        ci_provider=CIProvider.GITHUB_ACTIONS,
    )


@pytest.fixture
def sample_file_changes():
    """Create sample file changes."""
    return [
        FileChange(
            file_path="src/main.py",
            diff_type=DiffType.MODIFIED,
            additions=20,
            deletions=5,
        ),
        FileChange(
            file_path="src/utils.py",
            diff_type=DiffType.ADDED,
            additions=50,
        ),
        FileChange(
            file_path="tests/test_main.py",
            diff_type=DiffType.MODIFIED,
            additions=30,
        ),
    ]
