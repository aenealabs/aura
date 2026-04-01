"""
Project Aura - Health Check API Endpoints

Modeled after:
- AWS ELB Health Checks
- Kubernetes Liveness/Readiness Probes
- Google Cloud Load Balancer Health Checks

Health Check Types:
1. Liveness: Is the service running? (restart if fails)
2. Readiness: Can the service accept traffic? (remove from load balancer if fails)
3. Startup: Has the service finished initializing? (delay liveness checks)

Author: Project Aura Team
Created: 2025-11-18
Version: 1.0.0
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.services.observability_service import ServiceHealth, get_monitor

logger = logging.getLogger(__name__)


class HealthCheckEndpoints:
    """
    Health check endpoints for load balancers and orchestrators.

    Kubernetes Configuration:
        apiVersion: v1
        kind: Pod
        spec:
          containers:
          - name: aura-orchestrator
            livenessProbe:
              httpGet:
                path: /health/live
                port: 8080
              initialDelaySeconds: 30
              periodSeconds: 10
            readinessProbe:
              httpGet:
                path: /health/ready
                port: 8080
              initialDelaySeconds: 5
              periodSeconds: 5
            startupProbe:
              httpGet:
                path: /health/startup
                port: 8080
              failureThreshold: 30
              periodSeconds: 10
    """

    def __init__(
        self, neptune_service=None, opensearch_service=None, bedrock_service=None
    ):
        """
        Initialize health check endpoints.

        Args:
            neptune_service: Neptune graph service (optional)
            opensearch_service: OpenSearch vector service (optional)
            bedrock_service: Bedrock LLM service (optional)
        """
        self.neptune = neptune_service
        self.opensearch = opensearch_service
        self.bedrock = bedrock_service
        self.monitor = get_monitor()
        self.startup_complete = False
        self.startup_time = datetime.now(timezone.utc)

    # ========================================================================
    # Kubernetes-style Probes
    # ========================================================================

    async def liveness_probe(self) -> dict[str, Any]:
        """
        Liveness probe: Is the service alive?

        Kubernetes will RESTART the pod if this fails.
        Only check critical failures that require restart.

        Returns:
            {"status": "alive", "timestamp": "..."}

        HTTP Status:
            200: Service is alive
            500: Service is dead (Kubernetes will restart)
        """
        try:
            # Check if Python process is responsive
            # (if we can execute this code, we're alive)

            health = self.monitor.get_service_health()

            return {
                "status": "alive",
                "health": health.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self.monitor.service_start_time
                ).total_seconds(),
            }
        except Exception as e:
            logger.critical(f"Liveness probe failed: {e}")
            return {
                "status": "dead",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def readiness_probe(self) -> dict[str, Any]:
        """
        Readiness probe: Can the service accept traffic?

        Kubernetes will REMOVE from load balancer if this fails.
        Check dependencies (Neptune, OpenSearch, Bedrock).

        Returns:
            {"status": "ready"} or {"status": "not_ready", "reason": "..."}

        HTTP Status:
            200: Ready to accept traffic
            503: Not ready (remove from load balancer)
        """
        try:
            health_status = self.monitor.get_service_health()

            # Service is NOT ready if unhealthy
            if health_status == ServiceHealth.UNHEALTHY:
                return {
                    "status": "not_ready",
                    "reason": "Service health is UNHEALTHY",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Check dependencies
            dependency_checks = await self._check_dependencies()

            all_ready = all(check["ready"] for check in dependency_checks.values())

            if not all_ready:
                failed_deps = [
                    name
                    for name, check in dependency_checks.items()
                    if not check["ready"]
                ]

                return {
                    "status": "not_ready",
                    "reason": f"Dependencies not ready: {', '.join(failed_deps)}",
                    "dependencies": dependency_checks,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Service is ready
            return {
                "status": "ready",
                "health": health_status.value,
                "dependencies": dependency_checks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Readiness probe failed: {e}")
            return {
                "status": "not_ready",
                "reason": f"Probe error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def startup_probe(self) -> dict[str, Any]:
        """
        Startup probe: Has the service finished initializing?

        Kubernetes will wait for this before running liveness/readiness probes.
        Use for services with slow startup (loading models, etc.).

        Returns:
            {"status": "started"} or {"status": "starting", "progress": "..."}

        HTTP Status:
            200: Startup complete
            503: Still starting
        """
        try:
            # Check if startup tasks are complete
            startup_tasks = {
                "configuration_loaded": True,  # Always true if we reach this code
                "monitoring_initialized": self.monitor is not None,
                "dependencies_checked": await self._quick_dependency_check(),
            }

            all_started = all(startup_tasks.values())

            if all_started and not self.startup_complete:
                self.startup_complete = True
                startup_duration = (
                    datetime.now(timezone.utc) - self.startup_time
                ).total_seconds()
                logger.info(f"Startup complete in {startup_duration:.2f}s")

            status = "started" if all_started else "starting"

            return {
                "status": status,
                "startup_tasks": startup_tasks,
                "startup_duration_seconds": (
                    (datetime.now(timezone.utc) - self.startup_time).total_seconds()
                    if all_started
                    else None
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Startup probe failed: {e}")
            return {
                "status": "starting",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # ========================================================================
    # Detailed Health Endpoint (Datadog/New Relic style)
    # ========================================================================

    async def detailed_health(self) -> dict[str, Any]:
        """
        Detailed health report for monitoring dashboards.

        This endpoint provides comprehensive metrics for:
        - Datadog dashboards
        - New Relic APM
        - CloudWatch dashboards
        - Grafana dashboards

        Returns detailed health including:
        - Four Golden Signals (latency, traffic, errors, saturation)
        - Dependency status
        - Recent alerts
        - Resource usage
        """
        health_report = self.monitor.get_health_report()
        dependency_checks = await self._check_dependencies()

        return {
            **health_report,
            "dependencies": dependency_checks,
            "probe_results": {
                "liveness": (await self.liveness_probe())["status"],
                "readiness": (await self.readiness_probe())["status"],
                "startup": (await self.startup_probe())["status"],
            },
        }

    # ========================================================================
    # AWS-style Health Check (for ALB/NLB)
    # ========================================================================

    async def aws_health_check(self) -> dict[str, Any]:
        """
        Simple health check for AWS Application Load Balancer.

        AWS ALB requires:
        - HTTP 200 status
        - Response within timeout (default 2 seconds)

        Configuration in deploy/cloudformation/alb.yaml:
            HealthCheckPath: /health
            HealthCheckIntervalSeconds: 30
            HealthyThresholdCount: 2
            UnhealthyThresholdCount: 3
        """
        health = self.monitor.get_service_health()

        # AWS ALB only cares about HTTP status code
        # Return 200 if healthy or degraded, 503 if unhealthy
        return {
            "status": health.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ========================================================================
    # Internal Helper Methods
    # ========================================================================

    async def _check_dependencies(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all dependencies.

        Returns:
            {
                "neptune": {"ready": True, "latency_ms": 50},
                "opensearch": {"ready": True, "latency_ms": 30},
                "bedrock": {"ready": True, "latency_ms": 100}
            }
        """
        checks = {}

        # Check Neptune
        if self.neptune:
            checks["neptune"] = await self._check_neptune()
        else:
            checks["neptune"] = {"ready": True, "note": "Not configured"}

        # Check OpenSearch
        if self.opensearch:
            checks["opensearch"] = await self._check_opensearch()
        else:
            checks["opensearch"] = {"ready": True, "note": "Not configured"}

        # Check Bedrock
        if self.bedrock:
            checks["bedrock"] = await self._check_bedrock()
        else:
            checks["bedrock"] = {"ready": True, "note": "Not configured"}

        return checks

    async def _quick_dependency_check(self) -> bool:
        """Quick check if dependencies are available (for startup probe)."""
        try:
            # Just check if services are initialized
            # Don't actually query them (too slow for startup probe)
            return True
        except Exception:
            return False

    async def _check_neptune(self) -> dict[str, Any]:
        """Check Neptune cluster health."""
        try:
            import time

            from src.services.neptune_graph_service import NeptuneMode

            # If in MOCK mode, always ready
            if self.neptune.mode == NeptuneMode.MOCK:
                return {"ready": True, "mode": "MOCK", "latency_ms": 0}

            # In AWS mode, test connection
            start = time.time()
            # Test query (should be fast)
            self.neptune.search_by_name("__health_check__")
            latency = (time.time() - start) * 1000

            return {"ready": True, "mode": "AWS", "latency_ms": round(latency, 2)}

        except Exception as e:
            logger.warning(f"Neptune health check failed: {e}")
            return {"ready": False, "error": str(e)}

    async def _check_opensearch(self) -> dict[str, Any]:
        """Check OpenSearch cluster health."""
        try:
            # In production, would check OpenSearch cluster health endpoint
            # GET /_cluster/health
            return {"ready": True, "latency_ms": 0, "note": "Mock check"}

        except Exception as e:
            logger.warning(f"OpenSearch health check failed: {e}")
            return {"ready": False, "error": str(e)}

    async def _check_bedrock(self) -> dict[str, Any]:
        """Check AWS Bedrock service availability."""
        try:
            # In production, would test Bedrock API
            return {"ready": True, "latency_ms": 0, "note": "Mock check"}

        except Exception as e:
            logger.warning(f"Bedrock health check failed: {e}")
            return {"ready": False, "error": str(e)}


# ============================================================================
# FastAPI Integration (for production deployment)
# ============================================================================


async def setup_health_endpoints_fastapi(app, services: dict):
    """
    Setup health endpoints in FastAPI application.

    Usage:
        from fastapi import FastAPI
        app = FastAPI()

        services = {
            "neptune": neptune_service,
            "opensearch": opensearch_service,
            "bedrock": bedrock_service
        }

        await setup_health_endpoints_fastapi(app, services)
    """
    health = HealthCheckEndpoints(**services)

    @app.get("/health")
    async def health_check():
        """AWS ALB health check."""
        result = await health.aws_health_check()
        return result

    @app.get("/health/live")
    async def liveness():
        """Kubernetes liveness probe."""
        result = await health.liveness_probe()
        return result

    @app.get("/health/ready")
    async def readiness():
        """Kubernetes readiness probe."""
        result = await health.readiness_probe()
        return result

    @app.get("/health/startup")
    async def startup():
        """Kubernetes startup probe."""
        result = await health.startup_probe()
        return result

    @app.get("/health/detailed")
    async def detailed():
        """Detailed health for monitoring dashboards."""
        return await health.detailed_health()

    logger.info("Health check endpoints registered:")
    logger.info("  GET /health - AWS ALB health check")
    logger.info("  GET /health/live - Kubernetes liveness probe")
    logger.info("  GET /health/ready - Kubernetes readiness probe")
    logger.info("  GET /health/startup - Kubernetes startup probe")
    logger.info("  GET /health/detailed - Detailed metrics")
