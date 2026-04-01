"""Titan Neural Memory gRPC Server.

This server exposes the TitanMemoryService over gRPC for use by
other services in the Aura platform (agents, orchestrator, etc.).

Reference: ADR-024 - Titan Neural Memory Architecture Integration
"""

import asyncio
import logging
import os
import signal
import sys
from concurrent import futures
from typing import Any

import grpc
import torch
from prometheus_client import Counter, Histogram, start_http_server

# Add src to path for imports
sys.path.insert(0, "/app")

from aiohttp import web

from src.config.memory_service_config import MemoryServiceConfig, get_cached_config
from src.services.memory_backends import BackendConfig, BackendType
from src.services.titan_memory_service import (
    TitanMemoryService,
    TitanMemoryServiceConfig,
)

# Configure structured logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("memory-service")

# Prometheus metrics
REQUESTS = Counter(
    "memory_service_requests_total",
    "Total memory service requests",
    ["method", "status"],
)
LATENCY = Histogram(
    "memory_service_latency_seconds",
    "Memory service request latency",
    ["method"],
)
GPU_MEMORY = Counter(
    "memory_service_gpu_memory_bytes",
    "GPU memory usage",
)


class HealthServer:
    """HTTP server for Kubernetes health probes."""

    def __init__(self):
        self.ready = False
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/ready", self.readiness_check)
        self.app.router.add_get("/live", self.liveness_check)

    async def health_check(self, request):
        """Combined health check endpoint."""
        status = {
            "status": "healthy",
            "gpu_available": torch.cuda.is_available(),
            "ready": self.ready,
        }
        return web.json_response(status, status=200)

    async def readiness_check(self, request):
        """Kubernetes readiness probe."""
        if self.ready:
            return web.json_response({"ready": True}, status=200)
        return web.json_response({"ready": False}, status=503)

    async def liveness_check(self, request):
        """Kubernetes liveness probe."""
        return web.json_response({"alive": True}, status=200)

    def set_ready(self, ready: bool):
        """Set readiness state."""
        self.ready = ready
        logger.info(f"Health server readiness: {ready}")

    async def start(self, port: int = 8080):
        """Start the health HTTP server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)  # nosec B104 - container binding
        await site.start()
        logger.info(f"Health server started on port {port}")
        return runner


class MemoryServicer:
    """gRPC servicer for Titan Memory operations."""

    def __init__(self, memory_service: TitanMemoryService):
        self.memory_service = memory_service
        logger.info("MemoryServicer initialized")

    async def Store(self, request, context):
        """Store data in neural memory."""
        with LATENCY.labels(method="store").time():
            try:
                # Convert request to tensor
                key_tensor = torch.tensor(request.key, dtype=torch.float32)
                value_tensor = torch.tensor(request.value, dtype=torch.float32)

                # Store in memory
                result = self.memory_service.update(key_tensor, value_tensor)

                REQUESTS.labels(method="store", status="success").inc()
                return {
                    "success": True,
                    "surprise_score": result.get("surprise", 0.0),
                    "was_memorized": result.get("memorized", False),
                }
            except Exception as e:
                logger.error(f"Store failed: {e}")
                REQUESTS.labels(method="store", status="error").inc()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
                return {"success": False}

    async def Retrieve(self, request, context):
        """Retrieve data from neural memory."""
        with LATENCY.labels(method="retrieve").time():
            try:
                # Convert request to tensor
                query_tensor = torch.tensor(request.query, dtype=torch.float32)

                # Retrieve from memory
                result = self.memory_service.retrieve(query_tensor)

                REQUESTS.labels(method="retrieve", status="success").inc()
                return {
                    "success": True,
                    "content": result.content.tolist(),
                    "confidence": result.confidence,
                    "surprise": result.surprise,
                }
            except Exception as e:
                logger.error(f"Retrieve failed: {e}")
                REQUESTS.labels(method="retrieve", status="error").inc()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
                return {"success": False}

    async def GetMetrics(self, request, context):
        """Get memory service metrics."""
        try:
            metrics = self.memory_service.get_metrics()
            return {
                "memory_usage_mb": metrics.get("memory_usage_mb", 0),
                "total_updates": metrics.get("total_updates", 0),
                "total_retrievals": metrics.get("total_retrievals", 0),
                "avg_latency_ms": metrics.get("avg_latency_ms", 0),
            }
        except Exception as e:
            logger.error(f"GetMetrics failed: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return {}


def detect_gpu() -> tuple[bool, str]:
    """Detect available GPU and return configuration."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logger.info(f"GPU detected: {gpu_name} ({gpu_memory:.1f} GB)")
        return True, BackendType.CUDA
    else:
        logger.warning("No GPU detected, falling back to CPU")
        return False, BackendType.CPU


def create_memory_service() -> TitanMemoryService:
    """Create and configure the memory service."""
    environment = os.getenv("ENVIRONMENT", "dev")

    # Load configuration using the config module
    try:
        service_config = get_cached_config()
        logger.info(
            f"Loaded configuration for environment: {service_config.environment.value}"
        )
    except Exception as e:
        logger.warning(f"Failed to load config file: {e}, using defaults")
        service_config = None

    # Detect GPU availability
    has_gpu, backend_type = detect_gpu()

    # Map service config to TitanMemoryServiceConfig
    if service_config:
        config = TitanMemoryServiceConfig(
            memory_dim=service_config.memory.architecture.dimension,
            memory_depth=service_config.memory.architecture.layers,
            hidden_multiplier=4,
            persistent_memory_size=64,
            miras_preset="enterprise_standard",
            backend_config=BackendConfig(
                backend_type=backend_type,
                device_id=0 if has_gpu else None,
            ),
            enable_ttt=service_config.memory.ttt.enabled,
            ttt_learning_rate=service_config.memory.ttt.learning_rate,
            max_ttt_steps=service_config.memory.ttt.steps_per_update,
            memorization_threshold=service_config.memory.surprise.threshold,
            max_memory_size_mb=100.0,
            enable_size_limit_enforcement=True,
            enable_metrics=True,
            enable_audit_logging=True,
            environment=environment,
        )
        logger.info(
            f"Configuration: dim={config.memory_dim}, depth={config.memory_depth}, TTT={config.enable_ttt}"
        )
    else:
        # Use defaults with GPU detection
        config = TitanMemoryServiceConfig(
            memory_dim=512,
            memory_depth=3,
            hidden_multiplier=4,
            persistent_memory_size=64,
            miras_preset="enterprise_standard",
            backend_config=BackendConfig(
                backend_type=backend_type,
                device_id=0 if has_gpu else None,
            ),
            enable_ttt=True,
            ttt_learning_rate=0.001,
            max_ttt_steps=3,
            memorization_threshold=0.7,
            max_memory_size_mb=100.0,
            enable_size_limit_enforcement=True,
            enable_metrics=True,
            enable_audit_logging=True,
            environment=environment,
        )
        logger.info("Using default configuration with GPU detection")

    return TitanMemoryService(config)


async def serve():
    """Start the gRPC server."""
    # Start Prometheus metrics server
    metrics_port = int(os.getenv("METRICS_PORT", "9090"))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")

    # Start health check HTTP server
    health_port = int(os.getenv("HEALTH_PORT", "8080"))
    health_server = HealthServer()
    await health_server.start(health_port)

    # Create memory service
    memory_service = create_memory_service()

    # Mark health as ready after memory service is created
    health_server.set_ready(True)

    # Create gRPC server
    # Use GRPC_PORT to avoid conflict with Kubernetes auto-generated MEMORY_SERVICE_PORT
    grpc_port = int(os.getenv("GRPC_PORT", "50051"))
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),  # 50MB
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),  # 50MB
        ],
    )

    # Register servicer
    servicer = MemoryServicer(memory_service)
    # Note: In production, generate proper gRPC stubs from .proto files
    # For now, using reflection or manual registration

    server.add_insecure_port(f"[::]:{grpc_port}")

    logger.info(f"Starting gRPC server on port {grpc_port}")
    await server.start()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Wait for shutdown
    await stop_event.wait()

    logger.info("Shutting down gracefully...")
    await server.stop(grace=30)
    logger.info("Server stopped")


if __name__ == "__main__":
    logger.info("Starting Titan Neural Memory Service")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'dev')}")
    logger.info(f"PyTorch version: {torch.__version__}")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")

    asyncio.run(serve())
