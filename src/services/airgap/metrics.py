"""
Project Aura - Air-Gapped and Edge Deployment Metrics

CloudWatch metrics publisher for air-gap orchestration, firmware security analysis,
and tactical edge runtime services.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_airgap_config


class AirGapMetricsPublisher:
    """Publishes metrics for air-gap services to CloudWatch."""

    def __init__(self, namespace: Optional[str] = None):
        """Initialize metrics publisher."""
        config = get_airgap_config()
        self._namespace = namespace or config.metrics.namespace
        self._buffer: list[dict[str, Any]] = []
        self._buffer_size = config.metrics.buffer_size
        self._flush_interval = config.metrics.flush_interval_seconds
        self._enabled = config.metrics.enabled
        self._persist_when_offline = config.metrics.persist_when_offline
        self._metrics_file = config.metrics.metrics_file
        self._lock = threading.Lock()
        self._cloudwatch_client = None
        self._use_mock = True  # Default to mock for testing

    def _get_client(self) -> Any:
        """Get CloudWatch client (lazy initialization)."""
        if self._cloudwatch_client is None and not self._use_mock:
            try:
                import boto3

                self._cloudwatch_client = boto3.client("cloudwatch")
            except Exception:
                self._use_mock = True
        return self._cloudwatch_client

    def _create_metric_data(
        self,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: dict[str, str],
        timestamp: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Create metric data structure."""
        metric_data = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()],
        }
        return metric_data

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a metric to the buffer."""
        if not self._enabled:
            return

        dimensions = dimensions or {}
        dimensions.setdefault("Environment", get_airgap_config().environment)

        metric_data = self._create_metric_data(
            metric_name, value, unit, dimensions, timestamp
        )

        with self._lock:
            self._buffer.append(metric_data)
            if len(self._buffer) >= self._buffer_size:
                self._flush()

    def _flush(self) -> None:
        """Flush metrics buffer to CloudWatch or file."""
        if not self._buffer:
            return

        metrics_to_send = self._buffer.copy()
        self._buffer.clear()

        if self._use_mock:
            if self._persist_when_offline:
                self._persist_to_file(metrics_to_send)
            return

        client = self._get_client()
        if client is None:
            if self._persist_when_offline:
                self._persist_to_file(metrics_to_send)
            return

        try:
            # CloudWatch accepts max 1000 metrics per call
            for i in range(0, len(metrics_to_send), 1000):
                batch = metrics_to_send[i : i + 1000]
                # Convert timestamps back to datetime for boto3
                for m in batch:
                    if isinstance(m.get("Timestamp"), str):
                        m["Timestamp"] = datetime.fromisoformat(
                            m["Timestamp"].replace("Z", "+00:00")
                        )
                client.put_metric_data(
                    Namespace=self._namespace,
                    MetricData=batch,
                )
        except Exception:
            # If CloudWatch fails, persist locally
            if self._persist_when_offline:
                self._persist_to_file(metrics_to_send)

    def _persist_to_file(self, metrics: list[dict[str, Any]]) -> None:
        """Persist metrics to local file when offline."""
        try:
            os.makedirs(os.path.dirname(self._metrics_file), exist_ok=True)

            existing = []
            if os.path.exists(self._metrics_file):
                try:
                    with open(self._metrics_file) as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, IOError):
                    existing = []

            existing.extend(metrics)

            with open(self._metrics_file, "w") as f:
                json.dump(existing, f)
        except Exception:
            pass  # Best effort persistence

    def flush(self) -> None:
        """Public method to flush metrics buffer."""
        with self._lock:
            self._flush()

    def close(self) -> None:
        """Flush remaining metrics and close."""
        self.flush()

    # =========================================================================
    # Bundle Metrics
    # =========================================================================

    def record_bundle_created(
        self,
        bundle_id: str,
        bundle_type: str,
        size_bytes: int,
        component_count: int,
    ) -> None:
        """Record bundle creation metrics."""
        dimensions = {
            "BundleType": bundle_type,
        }
        self.put_metric("BundleCreated", 1, "Count", dimensions)
        self.put_metric("BundleSizeBytes", size_bytes, "Bytes", dimensions)
        self.put_metric("BundleComponentCount", component_count, "Count", dimensions)

    def record_bundle_signed(
        self,
        bundle_id: str,
        algorithm: str,
        duration_ms: float,
    ) -> None:
        """Record bundle signing metrics."""
        dimensions = {
            "Algorithm": algorithm,
        }
        self.put_metric("BundleSigned", 1, "Count", dimensions)
        self.put_metric("SigningDurationMs", duration_ms, "Milliseconds", dimensions)

    def record_bundle_verified(
        self,
        bundle_id: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record bundle verification metrics."""
        dimensions = {
            "Result": "Success" if success else "Failure",
        }
        self.put_metric("BundleVerification", 1, "Count", dimensions)
        self.put_metric(
            "VerificationDurationMs", duration_ms, "Milliseconds", dimensions
        )

    def record_bundle_deployed(
        self,
        bundle_id: str,
        node_id: str,
        duration_seconds: float,
    ) -> None:
        """Record bundle deployment metrics."""
        dimensions = {
            "NodeId": node_id,
        }
        self.put_metric("BundleDeployed", 1, "Count", dimensions)
        self.put_metric(
            "DeploymentDurationSeconds", duration_seconds, "Seconds", dimensions
        )

    def record_delta_update(
        self,
        delta_id: str,
        source_version: str,
        target_version: str,
        size_bytes: int,
        patch_count: int,
    ) -> None:
        """Record delta update metrics."""
        self.put_metric("DeltaUpdateCreated", 1, "Count")
        self.put_metric("DeltaSizeBytes", size_bytes, "Bytes")
        self.put_metric("DeltaPatchCount", patch_count, "Count")

    # =========================================================================
    # Transfer Metrics
    # =========================================================================

    def record_transfer_started(
        self,
        transfer_id: str,
        medium_type: str,
        size_bytes: int,
    ) -> None:
        """Record transfer start metrics."""
        dimensions = {
            "MediumType": medium_type,
        }
        self.put_metric("TransferStarted", 1, "Count", dimensions)
        self.put_metric("TransferSizeBytes", size_bytes, "Bytes", dimensions)

    def record_transfer_completed(
        self,
        transfer_id: str,
        medium_type: str,
        duration_seconds: float,
        success: bool,
    ) -> None:
        """Record transfer completion metrics."""
        dimensions = {
            "MediumType": medium_type,
            "Result": "Success" if success else "Failure",
        }
        self.put_metric("TransferCompleted", 1, "Count", dimensions)
        self.put_metric(
            "TransferDurationSeconds", duration_seconds, "Seconds", dimensions
        )

    def record_quarantine_event(
        self,
        file_path: str,
        reason: str,
    ) -> None:
        """Record quarantine event metrics."""
        dimensions = {
            "Reason": reason[:50],  # Truncate reason for dimension
        }
        self.put_metric("QuarantineEvent", 1, "Count", dimensions)

    # =========================================================================
    # Firmware Analysis Metrics
    # =========================================================================

    def record_firmware_analysis_started(
        self,
        analysis_id: str,
        image_format: str,
        architecture: str,
        size_bytes: int,
    ) -> None:
        """Record firmware analysis start metrics."""
        dimensions = {
            "Format": image_format,
            "Architecture": architecture,
        }
        self.put_metric("FirmwareAnalysisStarted", 1, "Count", dimensions)
        self.put_metric("FirmwareSizeBytes", size_bytes, "Bytes", dimensions)

    def record_firmware_analysis_completed(
        self,
        analysis_id: str,
        duration_seconds: float,
        issue_count: int,
        critical_count: int,
        high_count: int,
        passed: bool,
    ) -> None:
        """Record firmware analysis completion metrics."""
        dimensions = {
            "Result": "Passed" if passed else "Failed",
        }
        self.put_metric("FirmwareAnalysisCompleted", 1, "Count", dimensions)
        self.put_metric(
            "AnalysisDurationSeconds", duration_seconds, "Seconds", dimensions
        )
        self.put_metric("FirmwareIssueCount", issue_count, "Count", dimensions)
        self.put_metric("FirmwareCriticalCount", critical_count, "Count", dimensions)
        self.put_metric("FirmwareHighCount", high_count, "Count", dimensions)

    def record_rtos_detected(
        self,
        analysis_id: str,
        rtos_type: str,
        task_count: int,
    ) -> None:
        """Record RTOS detection metrics."""
        dimensions = {
            "RTOSType": rtos_type,
        }
        self.put_metric("RTOSDetected", 1, "Count", dimensions)
        self.put_metric("RTOSTaskCount", task_count, "Count", dimensions)

    def record_vulnerability_found(
        self,
        analysis_id: str,
        vulnerability_type: str,
        severity: str,
        cwe_id: Optional[str] = None,
    ) -> None:
        """Record vulnerability detection metrics."""
        dimensions = {
            "VulnerabilityType": vulnerability_type,
            "Severity": severity,
        }
        if cwe_id:
            dimensions["CWE"] = cwe_id
        self.put_metric("VulnerabilityFound", 1, "Count", dimensions)

    # =========================================================================
    # Edge Runtime Metrics
    # =========================================================================

    def record_node_registered(
        self,
        node_id: str,
        mode: str,
        architecture: str,
        ram_mb: int,
    ) -> None:
        """Record edge node registration metrics."""
        dimensions = {
            "Mode": mode,
            "Architecture": architecture,
        }
        self.put_metric("NodeRegistered", 1, "Count", dimensions)
        self.put_metric("NodeRamMB", ram_mb, "Megabytes", dimensions)

    def record_node_heartbeat(
        self,
        node_id: str,
        sync_status: str,
        ram_usage_percent: float,
        storage_usage_percent: float,
    ) -> None:
        """Record edge node heartbeat metrics."""
        dimensions = {
            "NodeId": node_id,
            "SyncStatus": sync_status,
        }
        self.put_metric("NodeHeartbeat", 1, "Count", dimensions)
        self.put_metric("NodeRamUsagePercent", ram_usage_percent, "Percent", dimensions)
        self.put_metric(
            "NodeStorageUsagePercent", storage_usage_percent, "Percent", dimensions
        )

    # =========================================================================
    # Model Metrics
    # =========================================================================

    def record_model_loaded(
        self,
        model_id: str,
        quantization: str,
        format: str,
        size_mb: float,
        load_time_ms: float,
    ) -> None:
        """Record model loading metrics."""
        dimensions = {
            "Quantization": quantization,
            "Format": format,
        }
        self.put_metric("ModelLoaded", 1, "Count", dimensions)
        self.put_metric("ModelSizeMB", size_mb, "Megabytes", dimensions)
        self.put_metric("ModelLoadTimeMs", load_time_ms, "Milliseconds", dimensions)

    def record_inference_request(
        self,
        model_id: str,
        node_id: str,
        prompt_tokens: int,
        max_tokens: int,
    ) -> None:
        """Record inference request metrics."""
        dimensions = {
            "ModelId": model_id,
            "NodeId": node_id,
        }
        self.put_metric("InferenceRequest", 1, "Count", dimensions)
        self.put_metric("PromptTokens", prompt_tokens, "Count", dimensions)
        self.put_metric("MaxTokens", max_tokens, "Count", dimensions)

    def record_inference_completed(
        self,
        model_id: str,
        node_id: str,
        tokens_generated: int,
        generation_time_ms: float,
        cached: bool,
        success: bool,
    ) -> None:
        """Record inference completion metrics."""
        dimensions = {
            "ModelId": model_id,
            "NodeId": node_id,
            "Cached": str(cached),
            "Result": "Success" if success else "Failure",
        }
        self.put_metric("InferenceCompleted", 1, "Count", dimensions)
        self.put_metric("TokensGenerated", tokens_generated, "Count", dimensions)
        self.put_metric(
            "GenerationTimeMs", generation_time_ms, "Milliseconds", dimensions
        )
        if generation_time_ms > 0:
            tokens_per_second = (tokens_generated / generation_time_ms) * 1000
            self.put_metric(
                "TokensPerSecond", tokens_per_second, "Count/Second", dimensions
            )

    # =========================================================================
    # Graph Metrics
    # =========================================================================

    def record_graph_query(
        self,
        query_id: str,
        query_type: str,
        execution_time_ms: float,
        result_count: int,
        success: bool,
    ) -> None:
        """Record graph query metrics."""
        dimensions = {
            "QueryType": query_type,
            "Result": "Success" if success else "Failure",
        }
        self.put_metric("GraphQuery", 1, "Count", dimensions)
        self.put_metric(
            "GraphQueryTimeMs", execution_time_ms, "Milliseconds", dimensions
        )
        self.put_metric("GraphQueryResultCount", result_count, "Count", dimensions)

    def record_graph_storage(
        self,
        database_size_mb: float,
        vertex_count: int,
        edge_count: int,
    ) -> None:
        """Record graph storage metrics."""
        self.put_metric("GraphDatabaseSizeMB", database_size_mb, "Megabytes")
        self.put_metric("GraphVertexCount", vertex_count, "Count")
        self.put_metric("GraphEdgeCount", edge_count, "Count")

    # =========================================================================
    # Cache Metrics
    # =========================================================================

    def record_cache_operation(
        self,
        cache_id: str,
        operation: str,
        hit: bool,
    ) -> None:
        """Record cache operation metrics."""
        dimensions = {
            "CacheId": cache_id,
            "Operation": operation,
        }
        if operation == "get":
            self.put_metric("CacheHit" if hit else "CacheMiss", 1, "Count", dimensions)
        else:
            self.put_metric(f"Cache{operation.capitalize()}", 1, "Count", dimensions)

    def record_cache_stats(
        self,
        cache_id: str,
        hit_rate: float,
        usage_percent: float,
        entry_count: int,
        eviction_count: int,
    ) -> None:
        """Record cache statistics metrics."""
        dimensions = {
            "CacheId": cache_id,
        }
        self.put_metric("CacheHitRate", hit_rate * 100, "Percent", dimensions)
        self.put_metric("CacheUsagePercent", usage_percent, "Percent", dimensions)
        self.put_metric("CacheEntryCount", entry_count, "Count", dimensions)
        self.put_metric("CacheEvictionCount", eviction_count, "Count", dimensions)

    # =========================================================================
    # Sync Metrics
    # =========================================================================

    def record_sync_started(
        self,
        node_id: str,
        pending_changes: int,
    ) -> None:
        """Record sync start metrics."""
        dimensions = {
            "NodeId": node_id,
        }
        self.put_metric("SyncStarted", 1, "Count", dimensions)
        self.put_metric("SyncPendingChanges", pending_changes, "Count", dimensions)

    def record_sync_completed(
        self,
        node_id: str,
        duration_seconds: float,
        bytes_transferred: int,
        success: bool,
        conflict_count: int = 0,
    ) -> None:
        """Record sync completion metrics."""
        dimensions = {
            "NodeId": node_id,
            "Result": "Success" if success else "Failure",
        }
        self.put_metric("SyncCompleted", 1, "Count", dimensions)
        self.put_metric("SyncDurationSeconds", duration_seconds, "Seconds", dimensions)
        self.put_metric("SyncBytesTransferred", bytes_transferred, "Bytes", dimensions)
        if conflict_count > 0:
            self.put_metric("SyncConflicts", conflict_count, "Count", dimensions)


# Singleton instance
_metrics_instance: Optional[AirGapMetricsPublisher] = None


def get_airgap_metrics() -> AirGapMetricsPublisher:
    """Get singleton metrics publisher instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = AirGapMetricsPublisher()
    return _metrics_instance


def reset_airgap_metrics() -> None:
    """Reset metrics publisher singleton (for testing)."""
    global _metrics_instance
    if _metrics_instance is not None:
        _metrics_instance.close()
    _metrics_instance = None
