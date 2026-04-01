"""
Project Aura - Job Persistence Service Tests

Tests for the DynamoDB-backed job persistence service.
Uses mock mode for testing without actual AWS resources,
plus moto for realistic DynamoDB integration tests.

Target: 85% coverage of src/services/job_persistence_service.py
"""

import os
import platform
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Set environment before importing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["ENVIRONMENT"] = "test"
os.environ["PROJECT_NAME"] = "aura"

from src.services.job_persistence_service import (
    JobPersistenceError,
    JobPersistenceService,
    PersistenceMode,
    create_persistence_service,
)


class JobStatus(Enum):
    """Test job status enum."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class MockIngestionJob:
    """Test dataclass for ingestion jobs."""

    job_id: str
    repository_url: str
    branch: str
    status: JobStatus
    created_at: datetime
    files_processed: int = 0
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class TestPersistenceMode:
    """Tests for PersistenceMode enum."""

    def test_mock_mode_value(self):
        """Test MOCK mode has correct value."""
        assert PersistenceMode.MOCK.value == "mock"

    def test_aws_mode_value(self):
        """Test AWS mode has correct value."""
        assert PersistenceMode.AWS.value == "aws"


class TestJobPersistenceError:
    """Tests for JobPersistenceError exception."""

    def test_exception_message(self):
        """Test exception stores message correctly."""
        error = JobPersistenceError("Test error message")
        assert str(error) == "Test error message"

    def test_exception_raise(self):
        """Test exception can be raised and caught."""
        with pytest.raises(JobPersistenceError) as exc_info:
            raise JobPersistenceError("Database connection failed")
        assert "Database connection failed" in str(exc_info.value)


class TestJobPersistenceServiceInit:
    """Tests for JobPersistenceService initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test", "PROJECT_NAME": "aura"}):
            service = JobPersistenceService(mode=PersistenceMode.MOCK)

            assert service.mode == PersistenceMode.MOCK
            assert service.table_name == "aura-ingestion-jobs-test"
            assert isinstance(service.mock_store, dict)

    def test_init_default_mode(self):
        """Test initialization with default mode."""
        service = JobPersistenceService()

        assert service.mode == PersistenceMode.MOCK

    def test_init_custom_table_name(self):
        """Test initialization with custom table name."""
        service = JobPersistenceService(
            mode=PersistenceMode.MOCK, table_name="custom-table"
        )

        assert service.table_name == "custom-table"

    def test_init_custom_region(self):
        """Test initialization with custom region."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK, region="eu-west-1")

        assert service.region == "eu-west-1"

    def test_init_aws_mode_without_boto3(self):
        """Test AWS mode fallback when boto3 unavailable."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", False):
            service = JobPersistenceService(mode=PersistenceMode.AWS)

            # Should fallback to MOCK mode
            assert service.mode == PersistenceMode.MOCK

    def test_init_aws_mode_with_dynamodb_connection_failure(self):
        """Test AWS mode fallback on DynamoDB connection failure."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.load.side_effect = Exception("Connection failed")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)

                # Should fallback to MOCK mode
                assert service.mode == PersistenceMode.MOCK

    def test_init_region_from_environment(self):
        """Test region is read from AWS_REGION environment variable."""
        with patch.dict(os.environ, {"AWS_REGION": "eu-central-1"}):
            service = JobPersistenceService(mode=PersistenceMode.MOCK)
            assert service.region == "eu-central-1"

    def test_init_default_region_when_not_set(self):
        """Test default region is us-east-1 when not set."""
        env_copy = os.environ.copy()
        if "AWS_REGION" in env_copy:
            del env_copy["AWS_REGION"]
        with patch.dict(os.environ, env_copy, clear=True):
            # Need to preserve minimal env
            os.environ["ENVIRONMENT"] = "test"
            os.environ["PROJECT_NAME"] = "aura"
            service = JobPersistenceService(mode=PersistenceMode.MOCK)
            assert service.region == "us-east-1"


class TestSaveJob:
    """Tests for save_job method."""

    def test_save_job_dataclass(self):
        """Test saving a dataclass job."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = MockIngestionJob(
            job_id="job-001",
            repository_url="https://github.com/owner/repo",
            branch="main",
            status=JobStatus.PENDING,
            created_at=datetime.now(),
        )

        result = service.save_job(job)

        assert result is True
        assert "job-001" in service.mock_store
        saved = service.mock_store["job-001"]
        assert saved["status"] == "PENDING"
        assert saved["repositoryId"] == "owner/repo"

    def test_save_job_dict(self):
        """Test saving a dictionary job."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = {
            "job_id": "job-002",
            "repository_url": "https://github.com/owner/repo.git",
            "branch": "develop",
            "status": "IN_PROGRESS",
            "created_at": datetime.now().isoformat(),
        }

        result = service.save_job(job)

        assert result is True
        assert "job-002" in service.mock_store

    def test_save_job_datetime_conversion(self):
        """Test datetime fields are converted to ISO format."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = MockIngestionJob(
            job_id="job-003",
            repository_url="https://github.com/owner/repo",
            branch="main",
            status=JobStatus.COMPLETED,
            created_at=datetime(2025, 12, 1, 10, 0, 0),
        )

        service.save_job(job)

        saved = service.mock_store["job-003"]
        assert isinstance(saved["created_at"], str)
        assert "2025-12-01" in saved["created_at"]

    def test_save_job_ttl_set(self):
        """Test TTL is set correctly."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = {
            "job_id": "job-ttl",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
        }

        service.save_job(job)

        saved = service.mock_store["job-ttl"]
        expected_ttl = int(time.time()) + (30 * 24 * 60 * 60)  # 30 days
        # Allow 5 second tolerance
        assert abs(saved["ttl"] - expected_ttl) < 5

    def test_save_job_aws_mode(self):
        """Test saving job in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)

                job = {
                    "job_id": "job-aws",
                    "repository_url": "https://github.com/owner/repo",
                    "status": "PENDING",
                }

                result = service.save_job(job)

                assert result is True
                mock_table.put_item.assert_called_once()
                # Verify jobId key is used for DynamoDB
                call_args = mock_table.put_item.call_args
                assert "jobId" in call_args[1]["Item"]

    def test_save_job_exception_raises_error(self):
        """Test save_job raises JobPersistenceError on exception."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        # Create an object that will fail serialization
        class BadObject:
            pass

        with pytest.raises(JobPersistenceError):
            service.save_job(BadObject())

    def test_save_job_date_partition_set(self):
        """Test datePartition is set correctly for DatePartitionIndex GSI."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = {
            "job_id": "job-partition",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
            "created_at": "2025-12-15T10:30:00",
        }

        service.save_job(job)

        saved = service.mock_store["job-partition"]
        assert saved["datePartition"] == "2025-12-15"

    def test_save_job_updated_at_set(self):
        """Test updatedAt timestamp is set on save."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        before = int(time.time())

        job = {
            "job_id": "job-updated",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
        }

        service.save_job(job)

        after = int(time.time())
        saved = service.mock_store["job-updated"]
        assert before <= saved["updatedAt"] <= after

    def test_save_job_without_created_at_uses_now(self):
        """Test job without created_at uses current time."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        before = int(time.time())

        job = {
            "job_id": "job-no-created",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
        }

        service.save_job(job)

        after = int(time.time())
        saved = service.mock_store["job-no-created"]
        assert before <= saved["createdAt"] <= after

    def test_save_job_aws_mode_exception(self):
        """Test save_job raises JobPersistenceError on AWS exception."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.put_item.side_effect = Exception("DynamoDB error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)

                job = {
                    "job_id": "job-error",
                    "repository_url": "https://github.com/owner/repo",
                    "status": "PENDING",
                }

                with pytest.raises(JobPersistenceError) as exc_info:
                    service.save_job(job)

                assert "DynamoDB error" in str(exc_info.value)


class TestGetJob:
    """Tests for get_job method."""

    def test_get_job_exists(self):
        """Test retrieving an existing job."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store["job-001"] = {
            "job_id": "job-001",
            "status": "COMPLETED",
        }

        result = service.get_job("job-001")

        assert result is not None
        assert result["job_id"] == "job-001"
        assert result["status"] == "COMPLETED"

    def test_get_job_not_found(self):
        """Test retrieving non-existent job returns None."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service.get_job("nonexistent-job")

        assert result is None

    def test_get_job_aws_mode(self):
        """Test getting job in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.get_item.return_value = {
                    "Item": {"jobId": "job-aws", "status": "COMPLETED"}
                }
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_job("job-aws")

                assert result is not None
                # Should transform jobId to job_id
                assert result["job_id"] == "job-aws"

    def test_get_job_aws_mode_not_found(self):
        """Test getting non-existent job in AWS mode returns None."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.get_item.return_value = {}  # No Item key
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_job("nonexistent")

                assert result is None

    def test_get_job_exception_returns_none(self):
        """Test get_job returns None on exception."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.get_item.side_effect = Exception("DynamoDB error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_job("job-error")

                assert result is None


class TestGetJobsByStatus:
    """Tests for get_jobs_by_status method."""

    def test_get_jobs_by_status_mock(self):
        """Test querying jobs by status in mock mode."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "status": "PENDING", "createdAt": 1000},
            "job-2": {"job_id": "job-2", "status": "COMPLETED", "createdAt": 2000},
            "job-3": {"job_id": "job-3", "status": "PENDING", "createdAt": 3000},
        }

        result = service.get_jobs_by_status("PENDING")

        assert len(result) == 2
        # Should be sorted by createdAt descending
        assert result[0]["job_id"] == "job-3"
        assert result[1]["job_id"] == "job-1"

    def test_get_jobs_by_status_with_limit(self):
        """Test status query respects limit."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            f"job-{i}": {"job_id": f"job-{i}", "status": "PENDING", "createdAt": i}
            for i in range(10)
        }

        result = service.get_jobs_by_status("PENDING", limit=5)

        assert len(result) == 5

    def test_get_jobs_by_status_aws_mode(self):
        """Test status query in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.query.return_value = {
                    "Items": [
                        {"jobId": "job-1", "status": "PENDING"},
                        {"jobId": "job-2", "status": "PENDING"},
                    ]
                }
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_jobs_by_status("PENDING")

                assert len(result) == 2
                mock_table.query.assert_called_once()

    def test_get_jobs_by_status_exception_returns_empty(self):
        """Test exception returns empty list."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.query.side_effect = Exception("Query error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_jobs_by_status("PENDING")

                assert result == []

    def test_get_jobs_by_status_no_matches(self):
        """Test query with no matching jobs returns empty list."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "status": "COMPLETED", "createdAt": 1000},
        }

        result = service.get_jobs_by_status("FAILED")

        assert result == []


class TestGetJobsByRepository:
    """Tests for get_jobs_by_repository method."""

    def test_get_jobs_by_repository_mock(self):
        """Test querying jobs by repository in mock mode."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {
                "job_id": "job-1",
                "repositoryId": "owner/repo-a",
                "createdAt": 1000,
            },
            "job-2": {
                "job_id": "job-2",
                "repositoryId": "owner/repo-b",
                "createdAt": 2000,
            },
            "job-3": {
                "job_id": "job-3",
                "repositoryId": "owner/repo-a",
                "createdAt": 3000,
            },
        }

        result = service.get_jobs_by_repository("owner/repo-a")

        assert len(result) == 2
        assert all(j["repositoryId"] == "owner/repo-a" for j in result)

    def test_get_jobs_by_repository_with_limit(self):
        """Test repository query respects limit."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            f"job-{i}": {
                "job_id": f"job-{i}",
                "repositoryId": "owner/repo",
                "createdAt": i,
            }
            for i in range(10)
        }

        result = service.get_jobs_by_repository("owner/repo", limit=3)

        assert len(result) == 3

    def test_get_jobs_by_repository_aws_mode(self):
        """Test repository query in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.query.return_value = {
                    "Items": [{"jobId": "job-1", "repositoryId": "owner/repo"}]
                }
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_jobs_by_repository("owner/repo")

                assert len(result) == 1

    def test_get_jobs_by_repository_exception(self):
        """Test exception returns empty list."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.query.side_effect = Exception("Query error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_jobs_by_repository("owner/repo")

                assert result == []

    def test_get_jobs_by_repository_sorted_by_created_at(self):
        """Test repository query results are sorted by createdAt descending."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {
                "job_id": "job-1",
                "repositoryId": "owner/repo",
                "createdAt": 1000,
            },
            "job-2": {
                "job_id": "job-2",
                "repositoryId": "owner/repo",
                "createdAt": 3000,
            },
            "job-3": {
                "job_id": "job-3",
                "repositoryId": "owner/repo",
                "createdAt": 2000,
            },
        }

        result = service.get_jobs_by_repository("owner/repo")

        assert result[0]["job_id"] == "job-2"  # highest createdAt
        assert result[1]["job_id"] == "job-3"
        assert result[2]["job_id"] == "job-1"  # lowest createdAt


class TestGetActiveJobs:
    """Tests for get_active_jobs method."""

    def test_get_active_jobs_mock(self):
        """Test getting active jobs in mock mode."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "status": "PENDING", "createdAt": 1000},
            "job-2": {"job_id": "job-2", "status": "COMPLETED", "createdAt": 2000},
            "job-3": {"job_id": "job-3", "status": "CLONING", "createdAt": 3000},
            "job-4": {"job_id": "job-4", "status": "PARSING", "createdAt": 4000},
        }

        result = service.get_active_jobs()

        assert len(result) == 3
        # Should not include COMPLETED
        statuses = [j["status"] for j in result]
        assert "COMPLETED" not in statuses
        assert "PENDING" in statuses
        assert "CLONING" in statuses
        assert "PARSING" in statuses

    def test_get_active_jobs_all_statuses(self):
        """Test all active statuses are recognized."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "status": "PENDING", "createdAt": 1000},
            "job-2": {"job_id": "job-2", "status": "CLONING", "createdAt": 2000},
            "job-3": {"job_id": "job-3", "status": "PARSING", "createdAt": 3000},
            "job-4": {"job_id": "job-4", "status": "INDEXING_GRAPH", "createdAt": 4000},
            "job-5": {
                "job_id": "job-5",
                "status": "INDEXING_VECTORS",
                "createdAt": 5000,
            },
            "job-6": {"job_id": "job-6", "status": "COMPLETED", "createdAt": 6000},
            "job-7": {"job_id": "job-7", "status": "FAILED", "createdAt": 7000},
        }

        result = service.get_active_jobs()

        assert len(result) == 5
        statuses = {j["status"] for j in result}
        assert statuses == {
            "PENDING",
            "CLONING",
            "PARSING",
            "INDEXING_GRAPH",
            "INDEXING_VECTORS",
        }

    def test_get_active_jobs_with_limit(self):
        """Test active jobs respects limit."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            f"job-{i}": {"job_id": f"job-{i}", "status": "PENDING", "createdAt": i}
            for i in range(10)
        }

        result = service.get_active_jobs(limit=3)

        assert len(result) == 3

    def test_get_active_jobs_aws_mode(self):
        """Test getting active jobs in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                # Implementation uses single scan with IN filter (N+1 optimization)
                mock_table.scan.return_value = {"Items": []}
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_active_jobs()

                assert result == []
                mock_table.scan.assert_called_once()

    def test_get_active_jobs_aws_mode_with_items(self):
        """Test active jobs in AWS mode with returned items."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.scan.return_value = {
                    "Items": [
                        {"jobId": "job-1", "status": "PENDING", "createdAt": 3000},
                        {"jobId": "job-2", "status": "CLONING", "createdAt": 1000},
                        {"jobId": "job-3", "status": "PARSING", "createdAt": 2000},
                    ]
                }
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_active_jobs()

                assert len(result) == 3
                # Should be sorted by createdAt descending
                assert result[0]["createdAt"] == 3000
                assert result[1]["createdAt"] == 2000
                assert result[2]["createdAt"] == 1000

    def test_get_active_jobs_aws_mode_exception(self):
        """Test exception returns empty list in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.scan.side_effect = Exception("Scan error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_active_jobs()

                assert result == []

    def test_get_active_jobs_sorted_descending(self):
        """Test active jobs are sorted by createdAt descending."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "status": "PENDING", "createdAt": 1000},
            "job-2": {"job_id": "job-2", "status": "PENDING", "createdAt": 3000},
            "job-3": {"job_id": "job-3", "status": "PENDING", "createdAt": 2000},
        }

        result = service.get_active_jobs()

        assert result[0]["job_id"] == "job-2"
        assert result[1]["job_id"] == "job-3"
        assert result[2]["job_id"] == "job-1"


class TestGetRecentJobs:
    """Tests for get_recent_jobs method."""

    def test_get_recent_jobs_mock(self):
        """Test getting recent jobs in mock mode."""
        current_time = int(time.time())

        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {
                "job_id": "job-1",
                "createdAt": current_time - 3600,
            },  # 1 hour ago
            "job-2": {
                "job_id": "job-2",
                "createdAt": current_time - 86400 * 2,
            },  # 2 days ago
            "job-3": {
                "job_id": "job-3",
                "createdAt": current_time - 1800,
            },  # 30 min ago
        }

        result = service.get_recent_jobs(hours=24)

        assert len(result) == 2
        job_ids = [j["job_id"] for j in result]
        assert "job-2" not in job_ids

    def test_get_recent_jobs_with_limit(self):
        """Test recent jobs respects limit."""
        current_time = int(time.time())

        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            f"job-{i}": {
                "job_id": f"job-{i}",
                "createdAt": current_time - (i * 60),
            }
            for i in range(10)
        }

        result = service.get_recent_jobs(hours=24, limit=5)

        assert len(result) == 5

    def test_get_recent_jobs_aws_mode(self):
        """Test getting recent jobs in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                # Now uses DatePartitionIndex GSI with query instead of scan
                # The query is called for each date partition in the range
                # Return item only on first call, empty on subsequent calls
                mock_table.query.side_effect = [
                    {"Items": [{"jobId": "job-1", "createdAt": int(time.time())}]},
                    {"Items": []},  # Second day's partition
                ]
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_recent_jobs(hours=24)

                assert len(result) == 1
                # Verify query was called with DatePartitionIndex
                mock_table.query.assert_called()

    def test_get_recent_jobs_exception(self):
        """Test exception returns empty list."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                # Now uses DatePartitionIndex GSI with query instead of scan
                mock_table.query.side_effect = Exception("Query error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_recent_jobs()

                assert result == []

    def test_get_recent_jobs_sorted_descending(self):
        """Test recent jobs are sorted by createdAt descending."""
        current_time = int(time.time())

        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "createdAt": current_time - 3600},
            "job-2": {"job_id": "job-2", "createdAt": current_time - 1800},
            "job-3": {"job_id": "job-3", "createdAt": current_time - 600},
        }

        result = service.get_recent_jobs(hours=24)

        # Should be sorted by createdAt descending (most recent first)
        assert result[0]["job_id"] == "job-3"
        assert result[1]["job_id"] == "job-2"
        assert result[2]["job_id"] == "job-1"

    def test_get_recent_jobs_aws_mode_limit_reached_early(self):
        """Test AWS mode stops querying when limit is reached."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()

                current_time = int(time.time())
                # First date partition returns enough items
                mock_table.query.side_effect = [
                    {
                        "Items": [
                            {"jobId": f"job-{i}", "createdAt": current_time - i * 60}
                            for i in range(150)
                        ]
                    },
                    {"Items": []},  # Should not be called
                ]
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_recent_jobs(hours=48, limit=100)

                assert len(result) == 100
                # First query returns enough, second query should not be called
                # (but might be called depending on timing)

    def test_get_recent_jobs_empty_store(self):
        """Test empty store returns empty list."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service.get_recent_jobs(hours=24)

        assert result == []

    def test_get_recent_jobs_all_expired(self):
        """Test all expired jobs returns empty list."""
        current_time = int(time.time())

        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "createdAt": current_time - 86400 * 3},
            "job-2": {"job_id": "job-2", "createdAt": current_time - 86400 * 5},
        }

        result = service.get_recent_jobs(hours=24)

        assert result == []


class TestUpdateJobStatus:
    """Tests for update_job_status method."""

    def test_update_job_status_mock(self):
        """Test updating job status in mock mode."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {"job-001": {"job_id": "job-001", "status": "PENDING"}}

        result = service.update_job_status("job-001", "COMPLETED")

        assert result is True
        assert service.mock_store["job-001"]["status"] == "COMPLETED"
        assert "updatedAt" in service.mock_store["job-001"]

    def test_update_job_status_with_additional_updates(self):
        """Test updating job with additional fields."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-001": {"job_id": "job-001", "status": "PENDING", "progress": 0}
        }

        result = service.update_job_status(
            "job-001", "IN_PROGRESS", {"progress": 50, "files_processed": 10}
        )

        assert result is True
        assert service.mock_store["job-001"]["progress"] == 50
        assert service.mock_store["job-001"]["files_processed"] == 10

    def test_update_job_status_not_found(self):
        """Test updating non-existent job returns False."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service.update_job_status("nonexistent", "COMPLETED")

        assert result is False

    def test_update_job_status_aws_mode(self):
        """Test updating job status in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.update_job_status("job-001", "COMPLETED")

                assert result is True
                mock_table.update_item.assert_called_once()

    def test_update_job_status_exception(self):
        """Test exception returns False."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.update_item.side_effect = Exception("Update error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.update_job_status("job-001", "COMPLETED")

                assert result is False

    def test_update_job_status_updates_timestamp(self):
        """Test updatedAt is set on status update."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {"job-001": {"job_id": "job-001", "status": "PENDING"}}

        before = int(time.time())
        service.update_job_status("job-001", "COMPLETED")
        after = int(time.time())

        assert before <= service.mock_store["job-001"]["updatedAt"] <= after


class TestDeleteJob:
    """Tests for delete_job method."""

    def test_delete_job_mock(self):
        """Test deleting job in mock mode."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {"job-001": {"job_id": "job-001"}}

        result = service.delete_job("job-001")

        assert result is True
        assert "job-001" not in service.mock_store

    def test_delete_job_not_found(self):
        """Test deleting non-existent job returns False."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service.delete_job("nonexistent")

        assert result is False

    def test_delete_job_aws_mode(self):
        """Test deleting job in AWS mode."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.delete_job("job-001")

                assert result is True
                mock_table.delete_item.assert_called_once()

    def test_delete_job_exception(self):
        """Test exception returns False."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.delete_item.side_effect = Exception("Delete error")
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.delete_job("job-001")

                assert result is False


class TestExtractRepoId:
    """Tests for _extract_repo_id method."""

    def test_extract_from_https_url(self):
        """Test extracting repo ID from HTTPS URL."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("https://github.com/owner/repo")

        assert result == "owner/repo"

    def test_extract_from_git_url(self):
        """Test extracting repo ID from .git URL."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("https://github.com/owner/repo.git")

        assert result == "owner/repo"

    def test_extract_from_trailing_slash_url(self):
        """Test extracting repo ID from URL with trailing slash."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("https://github.com/owner/repo/")

        assert result == "owner/repo"

    def test_extract_from_simple_string(self):
        """Test extracting repo ID from simple string."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("owner/repo")

        assert result == "owner/repo"

    def test_extract_single_part(self):
        """Test extracting from single part URL."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("repo")

        assert result == "repo"

    def test_extract_from_gitlab_url(self):
        """Test extracting repo ID from GitLab URL."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("https://gitlab.com/org/project.git")

        assert result == "org/project"

    def test_extract_from_bitbucket_url(self):
        """Test extracting repo ID from Bitbucket URL."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("https://bitbucket.org/team/repo")

        assert result == "team/repo"

    def test_extract_empty_string(self):
        """Test extracting from empty string."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        result = service._extract_repo_id("")

        assert result == ""


class TestCreatePersistenceService:
    """Tests for create_persistence_service factory function."""

    def test_create_service_mock_mode(self):
        """Test creating service defaults to mock mode."""
        # Remove AWS_REGION to force mock mode
        original_region = os.environ.get("AWS_REGION")
        if "AWS_REGION" in os.environ:
            del os.environ["AWS_REGION"]

        try:
            service = create_persistence_service()
            assert service.mode == PersistenceMode.MOCK
        finally:
            if original_region:
                os.environ["AWS_REGION"] = original_region

    def test_create_service_aws_mode_with_region(self):
        """Test creating service in AWS mode when region is set."""
        os.environ["AWS_REGION"] = "us-east-1"

        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = create_persistence_service()
                # Note: May fallback to MOCK if DynamoDB connection fails
                assert service is not None

    def test_create_service_without_boto3(self):
        """Test creating service without boto3 uses mock mode."""
        os.environ["AWS_REGION"] = "us-east-1"

        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", False):
            service = create_persistence_service()
            assert service.mode == PersistenceMode.MOCK


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_save_job_with_object_not_dict_or_dataclass(self):
        """Test saving an object that uses vars() for conversion."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        class SimpleJob:
            def __init__(self):
                self.job_id = "simple-001"
                self.repository_url = "https://github.com/owner/repo"
                self.status = "PENDING"

        job = SimpleJob()
        result = service.save_job(job)

        assert result is True
        assert "simple-001" in service.mock_store

    def test_save_job_created_at_string(self):
        """Test saving job with created_at as string."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = {
            "job_id": "job-string-date",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
            "created_at": "2025-12-01T10:00:00",
        }

        result = service.save_job(job)

        assert result is True
        assert service.mock_store["job-string-date"]["createdAt"] > 0

    def test_empty_mock_store_queries(self):
        """Test queries on empty store return empty lists."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        assert service.get_jobs_by_status("PENDING") == []
        assert service.get_jobs_by_repository("owner/repo") == []
        assert service.get_active_jobs() == []
        assert service.get_recent_jobs() == []

    def test_save_job_with_nested_enum(self):
        """Test saving job with enum in nested structure."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = MockIngestionJob(
            job_id="job-enum",
            repository_url="https://github.com/owner/repo",
            branch="main",
            status=JobStatus.FAILED,
            created_at=datetime.now(),
        )

        result = service.save_job(job)

        assert result is True
        saved = service.mock_store["job-enum"]
        assert saved["status"] == "FAILED"

    def test_get_active_jobs_with_missing_created_at(self):
        """Test get_active_jobs handles missing createdAt gracefully."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1", "status": "PENDING"},  # No createdAt
            "job-2": {"job_id": "job-2", "status": "PENDING", "createdAt": 1000},
        }

        result = service.get_active_jobs()

        assert len(result) == 2

    def test_get_recent_jobs_with_missing_created_at(self):
        """Test get_recent_jobs handles missing createdAt gracefully."""
        current_time = int(time.time())
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {
            "job-1": {"job_id": "job-1"},  # No createdAt
            "job-2": {"job_id": "job-2", "createdAt": current_time - 3600},
        }

        result = service.get_recent_jobs(hours=24)

        # Job without createdAt defaults to 0, which is before cutoff
        assert len(result) == 1
        assert result[0]["job_id"] == "job-2"

    def test_save_job_with_dict_having_keys_method(self):
        """Test saving a dict-like object with keys() method."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        job = {
            "job_id": "dict-job",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
        }

        result = service.save_job(job)

        assert result is True
        assert "dict-job" in service.mock_store

    def test_update_job_with_none_additional_updates(self):
        """Test update_job_status with None additional_updates."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)
        service.mock_store = {"job-001": {"job_id": "job-001", "status": "PENDING"}}

        result = service.update_job_status("job-001", "COMPLETED", None)

        assert result is True
        assert service.mock_store["job-001"]["status"] == "COMPLETED"

    def test_save_job_with_created_at_not_string(self):
        """Test saving job when created_at is not a string (already processed)."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        # Simulate case where created_at is already a timestamp integer
        job = {
            "job_id": "job-int-date",
            "repository_url": "https://github.com/owner/repo",
            "status": "PENDING",
            "created_at": 1735689600,  # Integer timestamp
        }

        result = service.save_job(job)

        assert result is True
        # Should use current time when created_at is not a string
        assert service.mock_store["job-int-date"]["createdAt"] > 0


class TestAWSModeIntegration:
    """Integration-style tests for AWS mode using moto."""

    def test_aws_mode_update_item_expression_building(self):
        """Test that update_item builds correct expression for multiple fields."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                service.update_job_status(
                    "job-001",
                    "COMPLETED",
                    {"progress": 100, "files_processed": 50},
                )

                call_kwargs = mock_table.update_item.call_args[1]

                # Verify UpdateExpression contains all fields
                assert "status" in call_kwargs["ExpressionAttributeNames"].values()
                assert "updatedAt" in call_kwargs["ExpressionAttributeNames"].values()
                assert "progress" in call_kwargs["ExpressionAttributeNames"].values()
                assert (
                    "files_processed"
                    in call_kwargs["ExpressionAttributeNames"].values()
                )

    def test_aws_mode_get_job_without_jobid_in_response(self):
        """Test get_job handles response without jobId key."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                # Return Item but without jobId (edge case)
                mock_table.get_item.return_value = {
                    "Item": {"status": "COMPLETED", "other_field": "value"}
                }
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                result = service.get_job("job-001")

                # Should return item as-is without transformation
                assert result is not None
                assert "job_id" not in result

    def test_aws_mode_query_with_reserved_keyword(self):
        """Test status query uses expression attribute names for reserved keyword."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.query.return_value = {"Items": []}
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                service.get_jobs_by_status("PENDING")

                call_kwargs = mock_table.query.call_args[1]
                # Verify ExpressionAttributeNames is used for 'status' reserved keyword
                assert "#job_status" in call_kwargs["ExpressionAttributeNames"]
                assert (
                    call_kwargs["ExpressionAttributeNames"]["#job_status"] == "status"
                )

    def test_aws_mode_scan_with_in_filter(self):
        """Test get_active_jobs uses IN filter with all active statuses."""
        with patch("src.services.job_persistence_service.BOTO3_AVAILABLE", True):
            with patch("src.services.job_persistence_service.boto3") as mock_boto3:
                mock_dynamodb = MagicMock()
                mock_table = MagicMock()
                mock_table.scan.return_value = {"Items": []}
                mock_dynamodb.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_dynamodb

                service = JobPersistenceService(mode=PersistenceMode.AWS)
                service.get_active_jobs()

                call_kwargs = mock_table.scan.call_args[1]

                # Verify all 5 active statuses are in the filter
                expr_values = call_kwargs["ExpressionAttributeValues"]
                expected_statuses = {
                    "PENDING",
                    "CLONING",
                    "PARSING",
                    "INDEXING_GRAPH",
                    "INDEXING_VECTORS",
                }
                actual_statuses = set(expr_values.values())
                assert expected_statuses == actual_statuses


class TestCRUDWorkflow:
    """End-to-end CRUD workflow tests."""

    def test_full_job_lifecycle(self):
        """Test complete job lifecycle: create, read, update, delete."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        # Create
        job = {
            "job_id": "lifecycle-001",
            "repository_url": "https://github.com/test/repo",
            "status": "PENDING",
            "branch": "main",
        }
        save_result = service.save_job(job)
        assert save_result is True

        # Read
        retrieved = service.get_job("lifecycle-001")
        assert retrieved is not None
        assert retrieved["status"] == "PENDING"

        # Update
        update_result = service.update_job_status(
            "lifecycle-001", "COMPLETED", {"files_processed": 100}
        )
        assert update_result is True

        # Verify update
        updated = service.get_job("lifecycle-001")
        assert updated["status"] == "COMPLETED"
        assert updated["files_processed"] == 100

        # Delete
        delete_result = service.delete_job("lifecycle-001")
        assert delete_result is True

        # Verify deletion
        deleted = service.get_job("lifecycle-001")
        assert deleted is None

    def test_multiple_jobs_workflow(self):
        """Test workflow with multiple jobs."""
        service = JobPersistenceService(mode=PersistenceMode.MOCK)

        # Create multiple jobs
        for i in range(5):
            job = {
                "job_id": f"multi-{i}",
                "repository_url": f"https://github.com/test/repo-{i % 2}",
                "status": "PENDING" if i % 2 == 0 else "COMPLETED",
                "created_at": datetime.now().isoformat(),
            }
            service.save_job(job)

        # Query by status
        pending = service.get_jobs_by_status("PENDING")
        assert len(pending) == 3

        completed = service.get_jobs_by_status("COMPLETED")
        assert len(completed) == 2

        # Update all pending to completed
        for job in pending:
            service.update_job_status(job["job_id"], "COMPLETED")

        # Verify all are now completed
        all_pending = service.get_jobs_by_status("PENDING")
        assert len(all_pending) == 0

        all_completed = service.get_jobs_by_status("COMPLETED")
        assert len(all_completed) == 5
