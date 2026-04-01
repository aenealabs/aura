"""Observability MCP Adapters for RuntimeIncidentAgent (ADR-025 Phase 5).

Provides MCP-compatible adapters for multi-vendor observability platforms:
- Datadog APM traces
- Prometheus metrics
- CloudWatch Insights

These adapters enable RuntimeIncidentAgent to query observability data
in Enterprise mode deployments.
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional, cast

import aiohttp
from aiohttp import ClientTimeout

from src.config import require_enterprise_mode

logger = logging.getLogger(__name__)


class ObservabilityMCPAdapters:
    """MCP adapters for observability platforms (Enterprise mode only)."""

    def __init__(self) -> None:
        """Initialize observability MCP adapters."""
        self.datadog_api_key = os.getenv("DATADOG_API_KEY")
        self.datadog_app_key = os.getenv("DATADOG_APP_KEY")
        self.datadog_site = os.getenv("DATADOG_SITE", "datadoghq.com")
        self.prometheus_url = os.getenv(
            "PROMETHEUS_URL", "http://prometheus.aura.local:9090"
        )

        logger.info("ObservabilityMCPAdapters initialized")

    def is_enterprise_mode(self) -> bool:
        """Check if running in Enterprise mode."""
        from src.config import get_integration_config

        config = get_integration_config()
        return str(config.mode).lower() in ["enterprise", "hybrid"]

    @require_enterprise_mode
    async def datadog_query_traces(
        self,
        service: str,
        time_range: tuple[datetime, datetime],
        error_only: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query Datadog APM traces for incident correlation.

        Args:
            service: Service name (e.g., "aura-api")
            time_range: (start_time, end_time) tuple
            error_only: Filter to error traces only
            limit: Maximum number of traces to return

        Returns:
            List of trace spans with error context
        """
        if not self.datadog_api_key or not self.datadog_app_key:
            logger.warning(
                "Datadog API credentials not configured, returning empty traces"
            )
            return []

        start, end = time_range
        query = f"service:{service}"
        if error_only:
            query += " status:error"

        headers = {
            "DD-API-KEY": self.datadog_api_key,
            "DD-APPLICATION-KEY": self.datadog_app_key,
        }

        params: dict[str, str | int] = {
            "query": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "limit": limit,
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.{self.datadog_site}/api/v2/spans/events/search"
                async with session.get(
                    url, headers=headers, params=params, timeout=ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        traces = data.get("data", [])
                        logger.info(
                            f"Retrieved {len(traces)} Datadog traces for {service}"
                        )
                        return cast(list[dict[str, Any]], traces)
                    else:
                        logger.error(f"Datadog API error: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Failed to query Datadog traces: {e}")
            return []

    @require_enterprise_mode
    async def datadog_query_logs(
        self,
        service: str,
        time_range: tuple[datetime, datetime],
        query: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query Datadog logs for incident analysis.

        Args:
            service: Service name filter
            time_range: (start_time, end_time) tuple
            query: Additional Datadog query syntax
            limit: Maximum number of logs

        Returns:
            List of log events
        """
        if not self.datadog_api_key or not self.datadog_app_key:
            logger.warning("Datadog API credentials not configured")
            return []

        start, end = time_range
        full_query = f"service:{service}"
        if query:
            full_query += f" {query}"

        headers = {
            "DD-API-KEY": self.datadog_api_key,
            "DD-APPLICATION-KEY": self.datadog_app_key,
        }

        body = {
            "filter": {
                "query": full_query,
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
            "page": {
                "limit": limit,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.{self.datadog_site}/api/v2/logs/events/search"
                async with session.post(
                    url, headers=headers, json=body, timeout=ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logs = data.get("data", [])
                        logger.info(f"Retrieved {len(logs)} Datadog logs for {service}")
                        return cast(list[dict[str, Any]], logs)
                    else:
                        logger.error(f"Datadog logs API error: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Failed to query Datadog logs: {e}")
            return []

    @require_enterprise_mode
    async def prometheus_query_range(
        self, query: str, start_time: datetime, end_time: datetime, step: str = "1m"
    ) -> dict[str, Any]:
        """
        Query Prometheus metrics for incident analysis.

        Args:
            query: PromQL query (e.g., "rate(http_requests_total[5m])")
            start_time: Query start time
            end_time: Query end time
            step: Resolution step (e.g., "1m", "5m")

        Returns:
            Time series data with metric values
        """
        params: dict[str, str] = {
            "query": query,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "step": step,
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.prometheus_url}/api/v1/query_range"
                async with session.get(
                    url, params=params, timeout=ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Retrieved Prometheus metrics: {query}")
                        return cast(dict[str, Any], data)
                    else:
                        logger.error(f"Prometheus API error: {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Failed to query Prometheus: {e}")
            return {}

    @require_enterprise_mode
    async def prometheus_query_instant(
        self, query: str, time: Optional[datetime] = None
    ) -> dict[str, Any]:
        """
        Query Prometheus instant metrics at a specific time.

        Args:
            query: PromQL query
            time: Query time (defaults to now)

        Returns:
            Instant metric value
        """
        params: dict[str, str] = {"query": query}
        if time:
            params["time"] = time.isoformat()

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.prometheus_url}/api/v1/query"
                async with session.get(
                    url, params=params, timeout=ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Retrieved instant Prometheus metric: {query}")
                        return cast(dict[str, Any], data)
                    else:
                        logger.error(f"Prometheus API error: {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Failed to query Prometheus instant: {e}")
            return {}
