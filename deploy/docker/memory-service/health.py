"""Health check server for Memory Service.

Provides HTTP endpoints for Kubernetes liveness and readiness probes.
"""

import asyncio
import json
import logging
import os

import torch
from aiohttp import web

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("health")


class HealthServer:
    """HTTP server for health checks."""

    def __init__(self):
        self.ready = False
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/ready", self.readiness_check)
        self.app.router.add_get("/live", self.liveness_check)

    async def health_check(self, request):
        """Combined health check endpoint."""
        gpu_ok = self._check_gpu()
        status = {
            "status": "healthy" if gpu_ok else "degraded",
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "ready": self.ready,
        }

        if torch.cuda.is_available():
            try:
                status["gpu_memory_allocated_mb"] = torch.cuda.memory_allocated() / (
                    1024 * 1024
                )
                status["gpu_memory_reserved_mb"] = torch.cuda.memory_reserved() / (
                    1024 * 1024
                )
            except Exception:
                pass

        return web.json_response(status, status=200 if gpu_ok else 503)

    async def readiness_check(self, request):
        """Kubernetes readiness probe."""
        if self.ready:
            return web.json_response({"ready": True}, status=200)
        return web.json_response({"ready": False}, status=503)

    async def liveness_check(self, request):
        """Kubernetes liveness probe."""
        # Simple liveness - just verify the process is responding
        return web.json_response({"alive": True}, status=200)

    def _check_gpu(self) -> bool:
        """Check GPU health."""
        if not torch.cuda.is_available():
            # CPU-only mode is acceptable
            return True

        try:
            # Try a simple GPU operation
            x = torch.zeros(1, device="cuda")
            del x
            return True
        except Exception as e:
            logger.error(f"GPU health check failed: {e}")
            return False

    def set_ready(self, ready: bool):
        """Set readiness state."""
        self.ready = ready
        logger.info(f"Readiness set to: {ready}")

    async def run(self, port: int = 8080):
        """Start the health server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)  # nosec B104 - container binding
        await site.start()
        logger.info(f"Health server started on port {port}")
        return runner


async def main():
    """Run health server standalone."""
    port = int(os.getenv("HEALTH_PORT", "8080"))
    server = HealthServer()
    server.set_ready(True)  # Assume ready when run standalone
    runner = await server.run(port)

    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
