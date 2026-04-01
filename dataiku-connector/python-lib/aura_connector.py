"""
Aura Code Intelligence Dataiku Connector

Provides data connectors and recipes for integrating Aura vulnerability
findings and code patterns with Dataiku DSS for analytics and visualization.

ADR-048 Phase 4: Dataiku Connector
"""

import logging
from datetime import datetime
from enum import Enum

import requests

logger = logging.getLogger(__name__)


class FindingSeverity(Enum):
    """Vulnerability finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AuraApiClient:
    """Client for communicating with Aura API server."""

    def __init__(self, server_url: str, api_key: str | None = None):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

        self.session.headers["Content-Type"] = "application/json"

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request."""
        url = f"{self.server_url}/api/v1{endpoint}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def get_all_findings(
        self,
        severity: str | None = None,
        category: str | None = None,
        since: datetime | None = None,
    ) -> list[dict]:
        """Get all vulnerability findings."""
        params = {}
        if severity:
            params["severity"] = severity
        if category:
            params["category"] = category

        data = self._request("GET", "/extension/findings", params=params)
        findings = data.get("findings", [])

        # Filter by date if specified
        if since:
            findings = [
                f
                for f in findings
                if datetime.fromisoformat(f.get("created_at", "2000-01-01")) >= since
            ]

        return findings

    def get_findings_by_file(self, file_path: str) -> list[dict]:
        """Get findings for a specific file."""
        data = self._request("GET", f"/extension/findings/{file_path}")
        return data.get("findings", [])

    def get_graph_context(
        self,
        file_path: str,
        depth: int = 2,
        line_number: int | None = None,
    ) -> dict:
        """Get GraphRAG context for a file."""
        payload = {
            "file_path": file_path,
            "depth": depth,
        }
        if line_number:
            payload["line_number"] = line_number

        return self._request("POST", "/extension/graph/context", json=payload)

    def get_code_patterns(
        self,
        pattern_type: str | None = None,
        min_occurrences: int = 1,
    ) -> list[dict]:
        """Get code patterns from GraphRAG."""
        data = self._request("GET", "/analytics/code-patterns")
        patterns = data.get("patterns", [])

        # Filter by type and occurrences
        if pattern_type:
            patterns = [p for p in patterns if p.get("type") == pattern_type]

        patterns = [p for p in patterns if p.get("occurrences", 0) >= min_occurrences]

        return patterns

    def health_check(self) -> bool:
        """Check server connectivity."""
        try:
            self._request("GET", "/../health")
            return True
        except Exception:
            return False


class AuraFindingsConnector:
    """
    Dataiku connector for Aura vulnerability findings.

    Exports findings data to Dataiku datasets for analysis.
    """

    def __init__(self, config: dict):
        self.server_url = config.get("server_url", "http://localhost:8080")
        self.api_key = config.get("api_key")
        self.client = AuraApiClient(self.server_url, self.api_key)

    def get_schema(self) -> list[dict]:
        """Return the dataset schema."""
        return [
            {"name": "finding_id", "type": "string"},
            {"name": "file_path", "type": "string"},
            {"name": "line_start", "type": "int"},
            {"name": "line_end", "type": "int"},
            {"name": "severity", "type": "string"},
            {"name": "category", "type": "string"},
            {"name": "title", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "cwe_id", "type": "string"},
            {"name": "owasp_category", "type": "string"},
            {"name": "has_patch", "type": "boolean"},
            {"name": "created_at", "type": "date"},
            {"name": "severity_score", "type": "double"},
        ]

    def get_rows(self, severity: str | None = None) -> list[dict]:
        """Fetch findings and convert to rows."""
        findings = self.client.get_all_findings(severity=severity)

        severity_scores = {
            "critical": 10.0,
            "high": 8.0,
            "medium": 5.0,
            "low": 2.0,
            "info": 1.0,
        }

        rows = []
        for finding in findings:
            rows.append(
                {
                    "finding_id": finding.get("id"),
                    "file_path": finding.get("file_path"),
                    "line_start": finding.get("line_start"),
                    "line_end": finding.get("line_end"),
                    "severity": finding.get("severity"),
                    "category": finding.get("category"),
                    "title": finding.get("title"),
                    "description": finding.get("description"),
                    "cwe_id": finding.get("cwe_id"),
                    "owasp_category": finding.get("owasp_category"),
                    "has_patch": finding.get("has_patch", False),
                    "created_at": finding.get("created_at"),
                    "severity_score": severity_scores.get(
                        finding.get("severity", "info"), 1.0
                    ),
                }
            )

        return rows


class AuraCodePatternsConnector:
    """
    Dataiku connector for Aura code patterns (GraphRAG).

    Exports code relationships and patterns for visualization.
    """

    def __init__(self, config: dict):
        self.server_url = config.get("server_url", "http://localhost:8080")
        self.api_key = config.get("api_key")
        self.client = AuraApiClient(self.server_url, self.api_key)

    def get_nodes_schema(self) -> list[dict]:
        """Return schema for nodes dataset."""
        return [
            {"name": "node_id", "type": "string"},
            {"name": "node_type", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "file_path", "type": "string"},
            {"name": "line_start", "type": "int"},
            {"name": "line_end", "type": "int"},
            {"name": "complexity", "type": "double"},
        ]

    def get_edges_schema(self) -> list[dict]:
        """Return schema for edges dataset."""
        return [
            {"name": "source_id", "type": "string"},
            {"name": "target_id", "type": "string"},
            {"name": "edge_type", "type": "string"},
            {"name": "weight", "type": "double"},
        ]

    def get_graph_data(self, file_path: str, depth: int = 2) -> tuple[list, list]:
        """Get nodes and edges for a file's code context."""
        context = self.client.get_graph_context(file_path, depth)

        nodes = [
            {
                "node_id": node.get("id"),
                "node_type": node.get("type"),
                "name": node.get("name"),
                "file_path": node.get("file_path"),
                "line_start": node.get("line_start"),
                "line_end": node.get("line_end"),
                "complexity": node.get("metadata", {}).get("complexity", 0.0),
            }
            for node in context.get("nodes", [])
        ]

        edges = [
            {
                "source_id": edge.get("source_id"),
                "target_id": edge.get("target_id"),
                "edge_type": edge.get("type"),
                "weight": edge.get("weight", 1.0),
            }
            for edge in context.get("edges", [])
        ]

        return nodes, edges


class AuraTrendAnalysis:
    """
    Trend analysis utilities for vulnerability data.

    Provides methods for computing trends and metrics.
    """

    @staticmethod
    def compute_severity_distribution(findings: list[dict]) -> dict[str, int]:
        """Compute distribution of findings by severity."""
        distribution: dict[str, int] = {}
        for finding in findings:
            severity = finding.get("severity", "unknown")
            distribution[severity] = distribution.get(severity, 0) + 1
        return distribution

    @staticmethod
    def compute_category_distribution(findings: list[dict]) -> dict[str, int]:
        """Compute distribution of findings by category."""
        distribution: dict[str, int] = {}
        for finding in findings:
            category = finding.get("category", "unknown")
            distribution[category] = distribution.get(category, 0) + 1
        return distribution

    @staticmethod
    def compute_file_risk_scores(findings: list[dict]) -> list[dict]:
        """Compute risk scores per file."""
        severity_weights = {
            "critical": 10.0,
            "high": 8.0,
            "medium": 5.0,
            "low": 2.0,
            "info": 1.0,
        }

        file_scores: dict[str, float] = {}
        file_counts: dict[str, int] = {}

        for finding in findings:
            file_path = finding.get("file_path", "unknown")
            severity = finding.get("severity", "info")
            weight = severity_weights.get(severity, 1.0)

            file_scores[file_path] = file_scores.get(file_path, 0) + weight
            file_counts[file_path] = file_counts.get(file_path, 0) + 1

        return [
            {
                "file_path": path,
                "risk_score": score,
                "finding_count": file_counts[path],
            }
            for path, score in sorted(file_scores.items(), key=lambda x: -x[1])
        ]

    @staticmethod
    def compute_cwe_summary(findings: list[dict]) -> list[dict]:
        """Compute CWE distribution summary."""
        cwe_counts: dict[str, int] = {}
        for finding in findings:
            cwe = finding.get("cwe_id")
            if cwe:
                cwe_counts[cwe] = cwe_counts.get(cwe, 0) + 1

        return [
            {"cwe_id": cwe, "count": count}
            for cwe, count in sorted(cwe_counts.items(), key=lambda x: -x[1])
        ]
