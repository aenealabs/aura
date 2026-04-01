"""Tests for GPU Scheduler Kubernetes client."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.gpu_scheduler.exceptions import K8sJobCreationError
from src.services.gpu_scheduler.k8s_client import (
    GPU_WORKLOADS_NAMESPACE,
    GPUJobK8sClient,
    get_k8s_client,
)
from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
)

# Check if kubernetes module is available
try:
    import kubernetes  # noqa: F401

    HAS_KUBERNETES = True
except ImportError:
    HAS_KUBERNETES = False

# Skip K8s operation tests if kubernetes module not available
requires_kubernetes = pytest.mark.skipif(
    not HAS_KUBERNETES,
    reason="kubernetes module not installed",
)


class TestGPUJobK8sClientInit:
    """Tests for K8s client initialization."""

    def test_init_defaults(self):
        """Test client initializes with default values."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            assert client.namespace == GPU_WORKLOADS_NAMESPACE
            assert client.environment == "dev"
            assert client.aws_region == "us-east-1"
            assert "123456789012" in client.ecr_repo

    def test_init_custom_values(self):
        """Test client initializes with custom values."""
        client = GPUJobK8sClient(
            namespace="custom-namespace",
            ecr_repo="custom.ecr.repo/images",
            image_tag="v1.0.0",
        )
        assert client.namespace == "custom-namespace"
        assert client.ecr_repo == "custom.ecr.repo/images"
        assert client.image_tag == "v1.0.0"


class TestGenerateJobName:
    """Tests for _generate_job_name method."""

    def test_generate_job_name(self):
        """Test job name generation."""
        client = GPUJobK8sClient()
        job_name = client._generate_job_name("job-12345678-abcd-1234")
        assert job_name == "gpu-job-job-1234"
        assert len(job_name) <= 63  # K8s name limit

    def test_generate_job_name_short_id(self):
        """Test job name generation with short ID."""
        client = GPUJobK8sClient()
        job_name = client._generate_job_name("abc")
        assert job_name == "gpu-job-abc"


class TestRenderJobManifest:
    """Tests for _render_job_manifest method."""

    @pytest.fixture
    def sample_gpu_job(self):
        """Create sample GPU job for testing."""
        config = EmbeddingJobConfig(
            repository_id="test-repo-123",
            branch="main",
            model="codebert-base",
        )
        return GPUJob(
            job_id="job-12345678",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.HIGH,
            config=config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            checkpoint_s3_path="s3://bucket/checkpoints/job-12345678/",
            created_at=datetime.now(timezone.utc),
        )

    def test_render_job_manifest(self, sample_gpu_job):
        """Test job manifest rendering."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            manifest = client._render_job_manifest(sample_gpu_job)

            assert "apiVersion: batch/v1" in manifest
            assert "kind: Job" in manifest
            assert "gpu-job-job-1234" in manifest
            assert sample_gpu_job.job_id in manifest
            assert sample_gpu_job.organization_id in manifest
            assert "nvidia.com/gpu" in manifest
            assert "16Gi" in manifest  # 8 + 8 buffer
            assert "8Gi" in manifest  # request
            assert "7200" in manifest  # 2 hours * 3600

    def test_render_job_manifest_config_json(self, sample_gpu_job):
        """Test job config is properly serialized to JSON."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            manifest = client._render_job_manifest(sample_gpu_job)

            # Verify config is valid JSON in manifest
            assert "repository_id" in manifest
            assert "test-repo-123" in manifest


@requires_kubernetes
class TestK8sClientOperations:
    """Tests for K8s client operations with mocked K8s API."""

    @pytest.fixture
    def mock_k8s(self):
        """Mock kubernetes client."""
        with patch("kubernetes.config.load_incluster_config"):
            with patch("kubernetes.config.load_kube_config"):
                with patch("kubernetes.client.CoreV1Api") as mock_core:
                    with patch("kubernetes.client.BatchV1Api") as mock_batch:
                        yield {
                            "core_v1": mock_core.return_value,
                            "batch_v1": mock_batch.return_value,
                        }

    @pytest.fixture
    def sample_gpu_job(self):
        """Create sample GPU job for testing."""
        config = EmbeddingJobConfig(
            repository_id="test-repo-123",
            branch="main",
        )
        return GPUJob(
            job_id="job-12345678",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            checkpoint_s3_path="s3://bucket/checkpoints/job-12345678/",
            created_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_create_job_success(self, mock_k8s, sample_gpu_job):
        """Test successful job creation."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            job_name = await client.create_job(sample_gpu_job)

            assert job_name == "gpu-job-job-1234"
            mock_k8s["batch_v1"].create_namespaced_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_failure(self, mock_k8s, sample_gpu_job):
        """Test job creation failure."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True
            mock_k8s["batch_v1"].create_namespaced_job.side_effect = Exception(
                "API error"
            )

            with pytest.raises(K8sJobCreationError):
                await client.create_job(sample_gpu_job)

    @pytest.mark.asyncio
    async def test_delete_job_success(self, mock_k8s):
        """Test successful job deletion."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            result = await client.delete_job("job-12345678")

            assert result is True
            mock_k8s["batch_v1"].delete_namespaced_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, mock_k8s):
        """Test job deletion when not found."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True
            mock_k8s["batch_v1"].delete_namespaced_job.side_effect = Exception(
                "404 not found"
            )

            result = await client.delete_job("job-12345678")

            assert result is False

    @pytest.mark.asyncio
    async def test_get_job_status_running(self, mock_k8s):
        """Test getting status of running job."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            # Mock K8s job status
            mock_job = MagicMock()
            mock_job.status.active = 1
            mock_job.status.succeeded = 0
            mock_job.status.failed = 0
            mock_job.status.start_time = datetime.now(timezone.utc)
            mock_job.status.completion_time = None
            mock_k8s["batch_v1"].read_namespaced_job_status.return_value = mock_job

            status = await client.get_job_status("job-12345678")

            assert status["gpu_status"] == "running"
            assert status["active"] == 1

    @pytest.mark.asyncio
    async def test_get_job_status_completed(self, mock_k8s):
        """Test getting status of completed job."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            # Mock K8s job status
            mock_job = MagicMock()
            mock_job.status.active = 0
            mock_job.status.succeeded = 1
            mock_job.status.failed = 0
            mock_job.status.start_time = datetime.now(timezone.utc)
            mock_job.status.completion_time = datetime.now(timezone.utc)
            mock_k8s["batch_v1"].read_namespaced_job_status.return_value = mock_job

            status = await client.get_job_status("job-12345678")

            assert status["gpu_status"] == "completed"
            assert status["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_get_job_status_failed(self, mock_k8s):
        """Test getting status of failed job."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            # Mock K8s job status
            mock_job = MagicMock()
            mock_job.status.active = 0
            mock_job.status.succeeded = 0
            mock_job.status.failed = 1
            mock_job.status.start_time = datetime.now(timezone.utc)
            mock_job.status.completion_time = datetime.now(timezone.utc)
            mock_k8s["batch_v1"].read_namespaced_job_status.return_value = mock_job

            status = await client.get_job_status("job-12345678")

            assert status["gpu_status"] == "failed"
            assert status["failed"] == 1

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, mock_k8s):
        """Test getting status when job not found."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True
            mock_k8s["batch_v1"].read_namespaced_job_status.side_effect = Exception(
                "404 not found"
            )

            status = await client.get_job_status("job-12345678")

            assert status["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_jobs(self, mock_k8s):
        """Test listing jobs."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            # Mock K8s jobs list
            mock_job = MagicMock()
            mock_job.metadata.name = "gpu-job-job-1234"
            mock_job.metadata.labels = {"aura.io/job-id": "job-12345678"}
            mock_job.metadata.creation_timestamp = datetime.now(timezone.utc)
            mock_job.status.active = 1
            mock_job.status.succeeded = 0
            mock_job.status.failed = 0

            mock_jobs = MagicMock()
            mock_jobs.items = [mock_job]
            mock_k8s["batch_v1"].list_namespaced_job.return_value = mock_jobs

            jobs = await client.list_jobs()

            assert len(jobs) == 1
            assert jobs[0]["job_name"] == "gpu-job-job-1234"
            assert jobs[0]["gpu_job_id"] == "job-12345678"

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, mock_k8s):
        """Test listing jobs when none exist."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._batch_v1 = mock_k8s["batch_v1"]
            client._k8s_configured = True

            mock_jobs = MagicMock()
            mock_jobs.items = []
            mock_k8s["batch_v1"].list_namespaced_job.return_value = mock_jobs

            jobs = await client.list_jobs()

            assert jobs == []


@requires_kubernetes
class TestStreamPodLogs:
    """Tests for stream_pod_logs method."""

    @pytest.fixture
    def mock_k8s(self):
        """Mock kubernetes client."""
        with patch("kubernetes.config.load_incluster_config"):
            with patch("kubernetes.config.load_kube_config"):
                with patch("kubernetes.client.CoreV1Api") as mock_core:
                    with patch("kubernetes.client.BatchV1Api") as mock_batch:
                        yield {
                            "core_v1": mock_core.return_value,
                            "batch_v1": mock_batch.return_value,
                        }

    @pytest.mark.asyncio
    async def test_stream_pod_logs_no_pods(self, mock_k8s):
        """Test streaming logs when no pods found."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True

            mock_pods = MagicMock()
            mock_pods.items = []
            mock_k8s["core_v1"].list_namespaced_pod.return_value = mock_pods

            logs = []
            async for line in client.stream_pod_logs("job-12345678"):
                logs.append(line)

            assert len(logs) == 1
            assert "No pods found" in logs[0]

    @pytest.mark.asyncio
    async def test_stream_pod_logs_success(self, mock_k8s):
        """Test streaming logs successfully."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True

            # Mock pod
            mock_pod = MagicMock()
            mock_pod.metadata.name = "gpu-job-job-1234-xyz"

            mock_pods = MagicMock()
            mock_pods.items = [mock_pod]
            mock_k8s["core_v1"].list_namespaced_pod.return_value = mock_pods

            # Mock logs
            mock_k8s["core_v1"].read_namespaced_pod_log.return_value = (
                "Log line 1\nLog line 2\nLog line 3"
            )

            logs = []
            async for line in client.stream_pod_logs("job-12345678"):
                logs.append(line)

            assert len(logs) == 3
            assert logs[0] == "Log line 1"
            assert logs[1] == "Log line 2"
            assert logs[2] == "Log line 3"


@requires_kubernetes
class TestGetAvailableGPUs:
    """Tests for get_available_gpus method."""

    @pytest.fixture
    def mock_k8s(self):
        """Mock kubernetes client."""
        with patch("kubernetes.config.load_incluster_config"):
            with patch("kubernetes.config.load_kube_config"):
                with patch("kubernetes.client.CoreV1Api") as mock_core:
                    with patch("kubernetes.client.BatchV1Api") as mock_batch:
                        yield {
                            "core_v1": mock_core.return_value,
                            "batch_v1": mock_batch.return_value,
                        }

    @pytest.mark.asyncio
    async def test_get_available_gpus(self, mock_k8s):
        """Test getting available GPUs."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True

            # Mock nodes with GPUs
            mock_node1 = MagicMock()
            mock_node1.status.capacity = {"nvidia.com/gpu": "2"}
            mock_node1.status.allocatable = {"nvidia.com/gpu": "1"}

            mock_node2 = MagicMock()
            mock_node2.status.capacity = {"nvidia.com/gpu": "2"}
            mock_node2.status.allocatable = {"nvidia.com/gpu": "2"}

            mock_nodes = MagicMock()
            mock_nodes.items = [mock_node1, mock_node2]
            mock_k8s["core_v1"].list_node.return_value = mock_nodes

            available, total = await client.get_available_gpus()

            assert available == 3  # 1 + 2
            assert total == 4  # 2 + 2

    @pytest.mark.asyncio
    async def test_get_available_gpus_no_nodes(self, mock_k8s):
        """Test getting available GPUs when no GPU nodes."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True

            mock_nodes = MagicMock()
            mock_nodes.items = []
            mock_k8s["core_v1"].list_node.return_value = mock_nodes

            available, total = await client.get_available_gpus()

            assert available == 0
            assert total == 0

    @pytest.mark.asyncio
    async def test_get_available_gpus_error(self, mock_k8s):
        """Test getting available GPUs on error."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True
            mock_k8s["core_v1"].list_node.side_effect = Exception("API error")

            available, total = await client.get_available_gpus()

            assert available == 0
            assert total == 0


@requires_kubernetes
class TestGetGPUNodeCount:
    """Tests for get_gpu_node_count method."""

    @pytest.fixture
    def mock_k8s(self):
        """Mock kubernetes client."""
        with patch("kubernetes.config.load_incluster_config"):
            with patch("kubernetes.config.load_kube_config"):
                with patch("kubernetes.client.CoreV1Api") as mock_core:
                    with patch("kubernetes.client.BatchV1Api") as mock_batch:
                        yield {
                            "core_v1": mock_core.return_value,
                            "batch_v1": mock_batch.return_value,
                        }

    @pytest.mark.asyncio
    async def test_get_gpu_node_count(self, mock_k8s):
        """Test getting GPU node count."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True

            mock_nodes = MagicMock()
            mock_nodes.items = [MagicMock(), MagicMock()]  # 2 nodes
            mock_k8s["core_v1"].list_node.return_value = mock_nodes

            count = await client.get_gpu_node_count()

            assert count == 2

    @pytest.mark.asyncio
    async def test_get_gpu_node_count_error(self, mock_k8s):
        """Test getting GPU node count on error."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client = GPUJobK8sClient()
            client._core_v1 = mock_k8s["core_v1"]
            client._k8s_configured = True
            mock_k8s["core_v1"].list_node.side_effect = Exception("API error")

            count = await client.get_gpu_node_count()

            assert count == 0


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_get_k8s_client_singleton(self):
        """Test get_k8s_client returns singleton."""
        import src.services.gpu_scheduler.k8s_client as k8s_module

        # Reset singleton
        k8s_module._k8s_client = None

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
                "ENVIRONMENT": "dev",
            },
        ):
            client1 = get_k8s_client()
            client2 = get_k8s_client()

            assert client1 is client2
