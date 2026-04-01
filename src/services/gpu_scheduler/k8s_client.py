"""Kubernetes client for GPU workload management.

Handles creation, deletion, and monitoring of Kubernetes Job resources
for GPU workloads in the aura-gpu-workloads namespace.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

from src.services.gpu_scheduler.exceptions import K8sJobCreationError
from src.services.gpu_scheduler.models import GPUJob, GPUJobStatus

logger = logging.getLogger(__name__)

# Default namespace for GPU workloads
GPU_WORKLOADS_NAMESPACE = "aura-gpu-workloads"

# Job template with placeholders
JOB_TEMPLATE = """
apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
  namespace: {namespace}
  labels:
    app: gpu-worker
    aura.io/job-id: "{job_id}"
    aura.io/job-type: "{job_type}"
    aura.io/user-id: "{user_id}"
    aura.io/organization-id: "{organization_id}"
    aura.io/priority: "{priority}"
    aura.io/gpu-count: "{gpu_count}"
spec:
  ttlSecondsAfterFinished: 3600
  backoffLimit: 2
  activeDeadlineSeconds: {active_deadline_seconds}
  template:
    metadata:
      labels:
        app: gpu-worker
        aura.io/job-id: "{job_id}"
    spec:
      serviceAccountName: gpu-scheduler
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
        - key: workload-type
          operator: Equal
          value: gpu-compute
          effect: NoSchedule
      containers:
        - name: gpu-worker
          image: {ecr_repo}/aura-gpu-worker-{environment}:{image_tag}
          resources:
            limits:
              nvidia.com/gpu: "{gpu_count}"
              memory: "{memory_limit}"
            requests:
              nvidia.com/gpu: "{gpu_count}"
              memory: "{memory_request}"
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          env:
            - name: JOB_ID
              value: "{job_id}"
            - name: JOB_TYPE
              value: "{job_type}"
            - name: JOB_CONFIG
              value: '{job_config_json}'
            - name: CHECKPOINT_S3_PATH
              value: "{checkpoint_s3_path}"
            - name: AWS_REGION
              value: "{aws_region}"
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: cache
              mountPath: /home/aura/.cache
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 2Gi
        - name: cache
          emptyDir:
            sizeLimit: 5Gi
      nodeSelector:
        kubernetes.io/os: linux
        kubernetes.io/arch: amd64
"""


class GPUJobK8sClient:
    """Kubernetes client for managing GPU workload Jobs.

    Handles:
    - Creating Kubernetes Jobs from GPU job specifications
    - Deleting Jobs (for cancellation)
    - Querying Job status
    - Streaming pod logs
    """

    def __init__(
        self,
        namespace: str = GPU_WORKLOADS_NAMESPACE,
        ecr_repo: str | None = None,
        image_tag: str | None = None,
    ):
        """Initialize the K8s client.

        Args:
            namespace: Kubernetes namespace for GPU workloads.
            ecr_repo: ECR repository URL for GPU worker image.
            image_tag: Docker image tag to use.
        """
        self.namespace = namespace
        self.ecr_repo = ecr_repo or os.environ.get(
            "ECR_REPO",
            f"{os.environ.get('AWS_ACCOUNT_ID', '')}.dkr.ecr."
            f"{os.environ.get('AWS_REGION', 'us-east-1')}.amazonaws.com",
        )
        self.image_tag = image_tag or os.environ.get("IMAGE_TAG", "latest")
        self.environment = os.environ.get("ENVIRONMENT", "dev")
        self.aws_region = os.environ.get("AWS_REGION", "us-east-1")

        # Lazy-loaded K8s clients
        self._core_v1 = None
        self._batch_v1 = None
        self._k8s_configured = False

    def _configure_k8s(self) -> None:
        """Configure Kubernetes client (lazy initialization)."""
        if self._k8s_configured:
            return

        try:
            from kubernetes import client, config

            # Try in-cluster config first, then kubeconfig
            try:
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes config")
            except config.ConfigException:
                config.load_kube_config()
                logger.info("Loaded kubeconfig")

            self._core_v1 = client.CoreV1Api()
            self._batch_v1 = client.BatchV1Api()
            self._k8s_configured = True

        except Exception as e:
            logger.error(f"Failed to configure Kubernetes client: {e}")
            raise K8sJobCreationError("", f"Failed to configure K8s: {e}")

    @property
    def core_v1(self):
        """Get CoreV1Api client (lazy-loaded)."""
        self._configure_k8s()
        return self._core_v1

    @property
    def batch_v1(self):
        """Get BatchV1Api client (lazy-loaded)."""
        self._configure_k8s()
        return self._batch_v1

    def _generate_job_name(self, job_id: str) -> str:
        """Generate Kubernetes Job name from GPU job ID."""
        # K8s names must be lowercase and max 63 chars
        return f"gpu-job-{job_id[:8]}"

    def _render_job_manifest(self, job: GPUJob) -> str:
        """Render Kubernetes Job manifest from GPU job spec."""
        job_name = self._generate_job_name(job.job_id)

        # Convert GPU memory to Kubernetes format
        memory_gb = job.gpu_memory_gb
        memory_limit = f"{memory_gb + 8}Gi"  # Add buffer for system overhead
        memory_request = f"{memory_gb}Gi"

        # Convert max runtime to seconds
        active_deadline_seconds = job.max_runtime_hours * 3600

        # Serialize config to JSON
        job_config_json = json.dumps(job.config.model_dump())

        # Get GPU count (default to 1 for backwards compatibility)
        gpu_count = getattr(job, "gpu_count", 1)

        return JOB_TEMPLATE.format(
            job_name=job_name,
            namespace=self.namespace,
            job_id=job.job_id,
            job_type=job.job_type.value,
            user_id=job.user_id,
            organization_id=job.organization_id,
            priority=job.priority.value,
            active_deadline_seconds=active_deadline_seconds,
            ecr_repo=self.ecr_repo,
            environment=self.environment,
            image_tag=self.image_tag,
            gpu_count=gpu_count,
            memory_limit=memory_limit,
            memory_request=memory_request,
            job_config_json=job_config_json,
            checkpoint_s3_path=job.checkpoint_s3_path or "",
            aws_region=self.aws_region,
        )

    async def create_job(self, job: GPUJob) -> str:
        """Create a Kubernetes Job for a GPU workload.

        Args:
            job: GPU job specification.

        Returns:
            Kubernetes Job name.

        Raises:
            K8sJobCreationError: If job creation fails.
        """
        import yaml

        job_name = self._generate_job_name(job.job_id)

        try:
            # Render and parse manifest
            manifest_yaml = self._render_job_manifest(job)
            manifest = yaml.safe_load(manifest_yaml)

            # Create the Job
            self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=manifest,
            )

            logger.info(
                "Created Kubernetes Job",
                extra={
                    "job_name": job_name,
                    "gpu_job_id": job.job_id,
                    "namespace": self.namespace,
                },
            )

            return job_name

        except Exception as e:
            logger.error(f"Failed to create Kubernetes Job: {e}")
            raise K8sJobCreationError(job.job_id, str(e))

    async def delete_job(self, job_id: str) -> bool:
        """Delete a Kubernetes Job.

        Args:
            job_id: GPU job ID.

        Returns:
            True if deleted, False if not found.
        """
        from kubernetes.client import V1DeleteOptions

        job_name = self._generate_job_name(job_id)

        try:
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                body=V1DeleteOptions(
                    propagation_policy="Background",  # Delete pods too
                ),
            )

            logger.info(
                "Deleted Kubernetes Job",
                extra={
                    "job_name": job_name,
                    "gpu_job_id": job_id,
                },
            )

            return True

        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                logger.warning(f"Kubernetes Job not found: {job_name}")
                return False
            logger.error(f"Failed to delete Kubernetes Job: {e}")
            raise

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get Kubernetes Job status.

        Args:
            job_id: GPU job ID.

        Returns:
            Job status dictionary.
        """
        job_name = self._generate_job_name(job_id)

        try:
            k8s_job = self.batch_v1.read_namespaced_job_status(
                name=job_name,
                namespace=self.namespace,
            )

            status = {
                "job_name": job_name,
                "active": k8s_job.status.active or 0,
                "succeeded": k8s_job.status.succeeded or 0,
                "failed": k8s_job.status.failed or 0,
                "start_time": (
                    k8s_job.status.start_time.isoformat()
                    if k8s_job.status.start_time
                    else None
                ),
                "completion_time": (
                    k8s_job.status.completion_time.isoformat()
                    if k8s_job.status.completion_time
                    else None
                ),
            }

            # Determine GPU job status from K8s status
            if k8s_job.status.succeeded and k8s_job.status.succeeded > 0:
                status["gpu_status"] = GPUJobStatus.COMPLETED.value
            elif k8s_job.status.failed and k8s_job.status.failed > 0:
                status["gpu_status"] = GPUJobStatus.FAILED.value
            elif k8s_job.status.active and k8s_job.status.active > 0:
                status["gpu_status"] = GPUJobStatus.RUNNING.value
            else:
                status["gpu_status"] = GPUJobStatus.STARTING.value

            return status

        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return {"job_name": job_name, "error": "not_found"}
            logger.error(f"Failed to get Kubernetes Job status: {e}")
            raise

    async def stream_pod_logs(
        self,
        job_id: str,
        follow: bool = False,
        tail_lines: int = 100,
    ) -> AsyncIterator[str]:
        """Stream logs from the pod running a GPU job.

        Args:
            job_id: GPU job ID.
            follow: Whether to follow (stream) logs.
            tail_lines: Number of lines to tail if not following.

        Yields:
            Log lines.
        """
        try:
            # Find pod for this job
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"aura.io/job-id={job_id}",
            )

            if not pods.items:
                yield f"No pods found for job {job_id}"
                return

            pod = pods.items[0]
            pod_name = pod.metadata.name

            # Stream logs
            if follow:
                # For following, use the watch API
                logs = self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=self.namespace,
                    follow=True,
                    tail_lines=tail_lines,
                    _preload_content=False,
                )
                for line in logs.stream():
                    yield line.decode("utf-8")
            else:
                logs = self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=self.namespace,
                    tail_lines=tail_lines,
                )
                for line in logs.split("\n"):
                    yield line

        except Exception as e:
            logger.error(f"Failed to stream pod logs: {e}")
            yield f"Error streaming logs: {e}"

    async def list_jobs(
        self,
        label_selector: str | None = None,
    ) -> list[dict[str, Any]]:
        """List Kubernetes Jobs in the GPU workloads namespace.

        Args:
            label_selector: Optional label selector to filter jobs.

        Returns:
            List of job status dictionaries.
        """
        try:
            jobs = self.batch_v1.list_namespaced_job(
                namespace=self.namespace,
                label_selector=label_selector or "app=gpu-worker",
            )

            return [
                {
                    "job_name": job.metadata.name,
                    "gpu_job_id": job.metadata.labels.get("aura.io/job-id"),
                    "active": job.status.active or 0,
                    "succeeded": job.status.succeeded or 0,
                    "failed": job.status.failed or 0,
                    "created_at": (
                        job.metadata.creation_timestamp.isoformat()
                        if job.metadata.creation_timestamp
                        else None
                    ),
                }
                for job in jobs.items
            ]

        except Exception as e:
            logger.error(f"Failed to list Kubernetes Jobs: {e}")
            return []

    async def get_gpu_node_count(self) -> int:
        """Get the number of GPU nodes in the cluster.

        Returns:
            Number of nodes with nvidia.com/gpu resource.
        """
        try:
            nodes = self.core_v1.list_node(
                label_selector="nvidia.com/gpu=true",
            )
            return len(nodes.items)

        except Exception as e:
            logger.warning(f"Failed to get GPU node count: {e}")
            return 0

    async def get_available_gpus(self) -> tuple[int, int]:
        """Get available and total GPUs in the cluster.

        Returns:
            Tuple of (available_gpus, total_gpus).
        """
        try:
            nodes = self.core_v1.list_node(
                label_selector="nvidia.com/gpu=true",
            )

            total_gpus = 0
            allocatable_gpus = 0

            for node in nodes.items:
                # Get GPU capacity
                capacity = node.status.capacity or {}
                allocatable = node.status.allocatable or {}

                gpu_capacity = int(capacity.get("nvidia.com/gpu", 0))
                gpu_allocatable = int(allocatable.get("nvidia.com/gpu", 0))

                total_gpus += gpu_capacity
                allocatable_gpus += gpu_allocatable

            return allocatable_gpus, total_gpus

        except Exception as e:
            logger.warning(f"Failed to get GPU availability: {e}")
            return 0, 0

    # =========================================================================
    # Phase 2: Checkpoint Support (ADR-061)
    # =========================================================================

    async def signal_checkpoint(self, job_id: str) -> bool:
        """Signal a running job to save its checkpoint.

        Uses pod annotation to trigger checkpoint save in the worker.

        Args:
            job_id: GPU job ID to signal.

        Returns:
            True if signal was sent successfully.
        """
        try:
            # Find pod for this job
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"aura.io/job-id={job_id}",
            )

            if not pods.items:
                logger.warning(f"No pods found for job {job_id}")
                return False

            pod = pods.items[0]
            pod_name = pod.metadata.name

            # Patch pod with checkpoint annotation
            patch_body = {
                "metadata": {
                    "annotations": {
                        "aura.io/checkpoint-requested": "true",
                        "aura.io/checkpoint-timestamp": str(
                            int(__import__("time").time())
                        ),
                    }
                }
            }

            self.core_v1.patch_namespaced_pod(
                name=pod_name,
                namespace=self.namespace,
                body=patch_body,
            )

            logger.info(
                "Signaled checkpoint for GPU job",
                extra={"job_id": job_id, "pod_name": pod_name},
            )

            return True

        except Exception as e:
            logger.error(f"Failed to signal checkpoint for job {job_id}: {e}")
            return False

    async def check_checkpoint_marker(self, job: "GPUJob") -> bool:
        """Check if a checkpoint marker exists in S3.

        The GPU worker writes a marker file after saving checkpoint.

        Args:
            job: GPUJob to check checkpoint for.

        Returns:
            True if checkpoint marker exists.
        """
        if not job.checkpoint_s3_path:
            return False

        try:
            import boto3

            # Parse S3 path
            # Format: s3://bucket/org_id/job_id/
            path = job.checkpoint_s3_path
            if path.startswith("s3://"):
                path = path[5:]

            parts = path.split("/", 1)
            if len(parts) < 2:
                return False

            bucket = parts[0]
            prefix = parts[1].rstrip("/")
            marker_key = f"{prefix}/checkpoint_complete.marker"

            # Check if marker exists
            s3_client = boto3.client("s3", region_name=self.aws_region)

            try:
                s3_client.head_object(Bucket=bucket, Key=marker_key)
                logger.info(
                    "Checkpoint marker found",
                    extra={"job_id": job.job_id, "marker_key": marker_key},
                )
                return True
            except s3_client.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

        except Exception as e:
            logger.warning(
                f"Failed to check checkpoint marker for job {job.job_id}: {e}"
            )
            return False


# Singleton instance
_k8s_client: GPUJobK8sClient | None = None


def get_k8s_client() -> GPUJobK8sClient:
    """Get or create the K8s client singleton."""
    global _k8s_client
    if _k8s_client is None:
        _k8s_client = GPUJobK8sClient()
    return _k8s_client
