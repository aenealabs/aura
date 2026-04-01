"""
Data Flow Report Generator
==========================

ADR-056 Phase 3: Data Flow Analysis

Generates comprehensive data flow reports with:
- Executive summary
- Database connection analysis
- Queue/event flow diagrams
- API call chains
- PII inventory with compliance mapping
- Mermaid.js diagrams
"""

import hashlib
import logging
from datetime import datetime, timezone

from src.services.data_flow.types import (
    APIEndpoint,
    ComplianceFramework,
    DatabaseConnection,
    DatabaseType,
    DataClassification,
    DataFlow,
    DataFlowReport,
    DataFlowResult,
    DataFlowType,
    PIICategory,
    PIIField,
    QueueConnection,
    QueueType,
)

logger = logging.getLogger(__name__)


class DataFlowReportGenerator:
    """Generates comprehensive data flow reports.

    Creates:
    - Executive summary with key metrics
    - Database connection inventory
    - Queue/event flow analysis
    - API endpoint catalog
    - PII field inventory
    - Mermaid.js diagrams for visualization
    - Compliance and security recommendations

    Attributes:
        use_mock: If True, returns mock report for testing
    """

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize DataFlowReportGenerator.

        Args:
            use_mock: If True, returns mock data instead of real generation
        """
        self.use_mock = use_mock

    async def generate_report(
        self,
        result: DataFlowResult,
        include_diagrams: bool = True,
        include_recommendations: bool = True,
    ) -> DataFlowReport:
        """Generate comprehensive data flow report.

        Args:
            result: DataFlowResult from analysis
            include_diagrams: If True, generate Mermaid diagrams
            include_recommendations: If True, include security recommendations

        Returns:
            Generated DataFlowReport
        """
        if self.use_mock:
            return self._get_mock_report(result.repository_id)

        report_id = self._generate_report_id(result.repository_id)

        # Generate sections
        summary = self._generate_summary(result)
        database_section = self._generate_database_section(result.database_connections)
        queue_section = self._generate_queue_section(result.queue_connections)
        api_section = self._generate_api_section(result.api_endpoints)
        pii_section = self._generate_pii_section(result.pii_fields)
        compliance_section = self._generate_compliance_section(result)

        # Generate diagrams
        diagrams: dict[str, str] = {}
        if include_diagrams:
            diagrams = self._generate_diagrams(result)

        # Generate recommendations
        recommendations: list[str] = []
        if include_recommendations:
            recommendations = self._generate_recommendations(result)

        # Assemble full report content
        content = self._assemble_report(
            summary=summary,
            database_section=database_section,
            queue_section=queue_section,
            api_section=api_section,
            pii_section=pii_section,
            compliance_section=compliance_section,
            diagrams=diagrams,
            recommendations=recommendations,
            result=result,
        )

        return DataFlowReport(
            report_id=report_id,
            repository_id=result.repository_id,
            title=f"Data Flow Analysis Report - {result.repository_id}",
            generated_at=datetime.now(timezone.utc),
            summary=summary,
            database_section=database_section,
            queue_section=queue_section,
            api_section=api_section,
            pii_section=pii_section,
            compliance_section=compliance_section,
            diagrams=diagrams,
            recommendations=recommendations,
            export_format="markdown",
            content=content,
        )

    def _generate_summary(self, result: DataFlowResult) -> str:
        """Generate executive summary section.

        Args:
            result: Analysis result

        Returns:
            Summary markdown text
        """
        db_count = len(result.database_connections)
        queue_count = len(result.queue_connections)
        api_count = len(result.api_endpoints)
        pii_count = len(result.pii_fields)
        flow_count = len(result.data_flows)
        cross_boundary = len(result.cross_boundary_flows)
        pii_flows = len(result.pii_data_flows)

        # Calculate risk metrics
        restricted_pii = sum(
            1
            for f in result.pii_fields
            if f.classification == DataClassification.RESTRICTED
        )
        unencrypted_pii = sum(1 for f in result.pii_fields if not f.is_encrypted)

        summary = f"""## Executive Summary

This report analyzes data flows within repository `{result.repository_id}`.

### Key Metrics

| Metric | Count |
|--------|-------|
| Database Connections | {db_count} |
| Message Queues | {queue_count} |
| API Endpoints | {api_count} |
| PII Fields Detected | {pii_count} |
| Data Flows Mapped | {flow_count} |
| Cross-Boundary Flows | {cross_boundary} |
| PII Data Flows | {pii_flows} |

### Risk Assessment

| Risk Factor | Status |
|------------|--------|
| Restricted PII Fields | {restricted_pii} |
| Unencrypted PII Fields | {unencrypted_pii} |
| Files Analyzed | {result.files_analyzed} |
| Analysis Duration | {result.analysis_time_ms:.2f}ms |

"""
        if result.warnings:
            summary += "### Warnings\n\n"
            for warning in result.warnings:
                summary += f"- ⚠️ {warning}\n"
            summary += "\n"

        if result.errors:
            summary += "### Errors\n\n"
            for error in result.errors:
                summary += f"- ❌ {error}\n"
            summary += "\n"

        return summary

    def _generate_database_section(self, connections: list[DatabaseConnection]) -> str:
        """Generate database connections section.

        Args:
            connections: List of database connections

        Returns:
            Database section markdown text
        """
        if not connections:
            return "## Database Connections\n\nNo database connections detected.\n"

        section = "## Database Connections\n\n"

        # Group by database type
        by_type: dict[DatabaseType, list[DatabaseConnection]] = {}
        for conn in connections:
            if conn.database_type not in by_type:
                by_type[conn.database_type] = []
            by_type[conn.database_type].append(conn)

        for db_type, conns in by_type.items():
            section += f"### {db_type.value.title()} ({len(conns)} connections)\n\n"
            section += "| File | Line | Tables | Read | Write | Confidence |\n"
            section += "|------|------|--------|------|-------|------------|\n"

            for conn in conns:
                tables = ", ".join(conn.tables_accessed[:3])
                if len(conn.tables_accessed) > 3:
                    tables += f" (+{len(conn.tables_accessed) - 3} more)"
                read = "✓" if conn.is_read else ""
                write = "✓" if conn.is_write else ""

                section += f"| `{conn.source_file}` | {conn.source_line} | {tables or 'N/A'} | {read} | {write} | {conn.confidence:.0%} |\n"

            section += "\n"

        return section

    def _generate_queue_section(self, connections: list[QueueConnection]) -> str:
        """Generate queue connections section.

        Args:
            connections: List of queue connections

        Returns:
            Queue section markdown text
        """
        if not connections:
            return "## Message Queues\n\nNo message queue connections detected.\n"

        section = "## Message Queues\n\n"

        # Group by queue type
        by_type: dict[QueueType, list[QueueConnection]] = {}
        for conn in connections:
            if conn.queue_type not in by_type:
                by_type[conn.queue_type] = []
            by_type[conn.queue_type].append(conn)

        for queue_type, conns in by_type.items():
            section += f"### {queue_type.value.upper()} ({len(conns)} queues)\n\n"
            section += "| Queue | File | Line | Producer | Consumer | DLQ |\n"
            section += "|-------|------|------|----------|----------|-----|\n"

            for conn in conns:
                producer = "✓" if conn.is_producer else ""
                consumer = "✓" if conn.is_consumer else ""
                dlq = conn.dlq_name or ""

                section += f"| `{conn.queue_name}` | `{conn.source_file}` | {conn.source_line} | {producer} | {consumer} | {dlq} |\n"

            section += "\n"

        return section

    def _generate_api_section(self, endpoints: list[APIEndpoint]) -> str:
        """Generate API endpoints section.

        Args:
            endpoints: List of API endpoints

        Returns:
            API section markdown text
        """
        if not endpoints:
            return "## API Endpoints\n\nNo API endpoints detected.\n"

        section = "## API Endpoints\n\n"

        # Separate internal and external
        internal = [e for e in endpoints if e.is_internal]
        external = [e for e in endpoints if e.is_external]

        if internal:
            section += f"### Internal Endpoints ({len(internal)})\n\n"
            section += "| Method | Path | File | Line | Auth | Rate Limit |\n"
            section += "|--------|------|------|------|------|------------|\n"

            for endpoint in internal:
                auth = endpoint.auth_type or "None"
                rate = ""
                if endpoint.rate_limit:
                    rate = f"{endpoint.rate_limit.get('requests', '?')}/{endpoint.rate_limit.get('period', '?')}"

                section += f"| `{endpoint.method}` | `{endpoint.url_pattern}` | `{endpoint.source_file}` | {endpoint.source_line} | {auth} | {rate} |\n"

            section += "\n"

        if external:
            section += f"### External API Calls ({len(external)})\n\n"
            section += "| Method | URL | File | Line | Timeout |\n"
            section += "|--------|-----|------|------|--------|\n"

            for endpoint in external:
                timeout = (
                    f"{endpoint.timeout_ms}ms" if endpoint.timeout_ms else "Default"
                )
                url = endpoint.url_pattern
                if len(url) > 50:
                    url = url[:47] + "..."

                section += f"| `{endpoint.method}` | `{url}` | `{endpoint.source_file}` | {endpoint.source_line} | {timeout} |\n"

            section += "\n"

        return section

    def _generate_pii_section(self, fields: list[PIIField]) -> str:
        """Generate PII fields section.

        Args:
            fields: List of PII fields

        Returns:
            PII section markdown text
        """
        if not fields:
            return "## PII Inventory\n\nNo PII fields detected.\n"

        section = "## PII Inventory\n\n"

        # Group by category
        by_category: dict[PIICategory, list[PIIField]] = {}
        for field in fields:
            if field.pii_category not in by_category:
                by_category[field.pii_category] = []
            by_category[field.pii_category].append(field)

        section += f"**Total PII Fields:** {len(fields)}\n\n"

        # Summary by classification
        section += "### Classification Summary\n\n"
        by_classification: dict[DataClassification, int] = {}
        for field in fields:
            if field.classification not in by_classification:
                by_classification[field.classification] = 0
            by_classification[field.classification] += 1

        section += "| Classification | Count |\n"
        section += "|---------------|-------|\n"
        for classification in [
            DataClassification.RESTRICTED,
            DataClassification.CONFIDENTIAL,
            DataClassification.INTERNAL,
            DataClassification.PUBLIC,
        ]:
            count = by_classification.get(classification, 0)
            if count > 0:
                section += f"| {classification.value.title()} | {count} |\n"
        section += "\n"

        # Detail by category
        for category, category_fields in sorted(
            by_category.items(), key=lambda x: len(x[1]), reverse=True
        ):
            section += f"### {category.value.replace('_', ' ').title()} ({len(category_fields)} fields)\n\n"
            section += "| Field | Entity | File | Line | Encrypted | Masked | Classification |\n"
            section += "|-------|--------|------|------|-----------|--------|----------------|\n"

            for field in category_fields[:10]:  # Limit to 10 per category
                encrypted = "✓" if field.is_encrypted else "✗"
                masked = "✓" if field.is_masked else "✗"

                section += f"| `{field.field_name}` | {field.entity_name or 'N/A'} | `{field.source_file}` | {field.source_line} | {encrypted} | {masked} | {field.classification.value} |\n"

            if len(category_fields) > 10:
                section += f"\n*...and {len(category_fields) - 10} more fields*\n"

            section += "\n"

        return section

    def _generate_compliance_section(self, result: DataFlowResult) -> str:
        """Generate compliance analysis section.

        Args:
            result: Analysis result

        Returns:
            Compliance section markdown text
        """
        section = "## Compliance Analysis\n\n"

        if not result.pii_fields:
            section += (
                "No PII fields detected. Compliance requirements may be minimal.\n"
            )
            return section

        # Group PII by compliance framework
        by_framework: dict[ComplianceFramework, list[PIIField]] = {}
        for field in result.pii_fields:
            for framework in field.compliance_tags:
                if framework not in by_framework:
                    by_framework[framework] = []
                by_framework[framework].append(field)

        for framework in [
            ComplianceFramework.GDPR,
            ComplianceFramework.HIPAA,
            ComplianceFramework.PCI_DSS,
            ComplianceFramework.SOX,
            ComplianceFramework.CCPA,
            ComplianceFramework.NIST_800_53,
        ]:
            if framework not in by_framework:
                continue

            fields = by_framework[framework]
            unencrypted = sum(1 for f in fields if not f.is_encrypted)
            unmasked = sum(1 for f in fields if not f.is_masked)

            section += f"### {framework.value.upper()}\n\n"
            section += f"- **Applicable Fields:** {len(fields)}\n"
            section += f"- **Unencrypted:** {unencrypted}\n"
            section += f"- **Unmasked in Logs:** {unmasked}\n"

            if unencrypted > 0 or unmasked > 0:
                section += "- **Status:** ⚠️ **Action Required**\n"
            else:
                section += "- **Status:** ✅ Compliant\n"

            section += "\n"

        return section

    def _generate_diagrams(self, result: DataFlowResult) -> dict[str, str]:
        """Generate Mermaid.js diagrams.

        Args:
            result: Analysis result

        Returns:
            Dict of diagram name to Mermaid content
        """
        diagrams: dict[str, str] = {}

        # Database architecture diagram
        if result.database_connections:
            diagrams["database_architecture"] = self._generate_database_diagram(
                result.database_connections
            )

        # Queue flow diagram
        if result.queue_connections:
            diagrams["queue_flows"] = self._generate_queue_diagram(
                result.queue_connections
            )

        # API dependency diagram
        if result.api_endpoints:
            diagrams["api_dependencies"] = self._generate_api_diagram(
                result.api_endpoints
            )

        # Data flow diagram
        if result.data_flows:
            diagrams["data_flows"] = self._generate_flow_diagram(result.data_flows)

        return diagrams

    def _generate_database_diagram(self, connections: list[DatabaseConnection]) -> str:
        """Generate database architecture Mermaid diagram.

        Args:
            connections: Database connections

        Returns:
            Mermaid diagram string
        """
        diagram = "graph LR\n"

        # Group services (files) to databases
        services: set[str] = set()
        databases: set[str] = set()

        for conn in connections:
            # Extract service name from file path
            service = (
                conn.source_file.split("/")[-2] if "/" in conn.source_file else "app"
            )
            service = service.replace("-", "_").replace(".", "_")
            services.add(service)

            # Use database type as node
            db_name = f"{conn.database_type.value}"
            databases.add(db_name)

            # Add edge
            direction = "-->" if conn.is_write else "-.->|read|"
            diagram += f"    {service}[{service}] {direction} {db_name}[({conn.database_type.value})]\n"

        return diagram

    def _generate_queue_diagram(self, connections: list[QueueConnection]) -> str:
        """Generate queue flow Mermaid diagram.

        Args:
            connections: Queue connections

        Returns:
            Mermaid diagram string
        """
        diagram = "graph LR\n"

        for conn in connections:
            service = (
                conn.source_file.split("/")[-2] if "/" in conn.source_file else "app"
            )
            service = service.replace("-", "_").replace(".", "_")
            queue = conn.queue_name.replace("-", "_").replace(".", "_")

            if conn.is_producer:
                diagram += f"    {service}[{service}] -->|produce| {queue}[/{conn.queue_name}/]\n"
            if conn.is_consumer:
                diagram += f"    {queue}[/{conn.queue_name}/] -->|consume| {service}[{service}]\n"

            if conn.dlq_name:
                dlq = conn.dlq_name.replace("-", "_").replace(".", "_")
                diagram += f"    {queue} -.->|DLQ| {dlq}[/{conn.dlq_name}/]\n"

        return diagram

    def _generate_api_diagram(self, endpoints: list[APIEndpoint]) -> str:
        """Generate API dependency Mermaid diagram.

        Args:
            endpoints: API endpoints

        Returns:
            Mermaid diagram string
        """
        diagram = "graph TD\n"

        internal = [e for e in endpoints if e.is_internal]
        external = [e for e in endpoints if e.is_external]

        # Add internal endpoints
        for endpoint in internal[:15]:  # Limit for readability
            service = (
                endpoint.source_file.split("/")[-2]
                if "/" in endpoint.source_file
                else "api"
            )
            service = service.replace("-", "_").replace(".", "_")
            path = (
                endpoint.url_pattern.replace("/", "_").replace("{", "").replace("}", "")
            )
            node_id = f"{service}_{endpoint.method}_{path}"[:30]

            diagram += f"    {node_id}[{endpoint.method} {endpoint.url_pattern}]\n"

        # Add external calls
        for endpoint in external[:10]:
            service = (
                endpoint.source_file.split("/")[-2]
                if "/" in endpoint.source_file
                else "client"
            )
            service = service.replace("-", "_").replace(".", "_")

            # Extract domain from URL
            url = endpoint.url_pattern
            if "://" in url:
                domain = url.split("://")[1].split("/")[0]
            else:
                domain = "external"
            domain = domain.replace(".", "_").replace("-", "_")

            diagram += (
                f"    {service}[{service}] --> {domain}{{{{fa:fa-cloud {domain}}}}}\n"
            )

        return diagram

    def _generate_flow_diagram(self, flows: list[DataFlow]) -> str:
        """Generate data flow Mermaid diagram.

        Args:
            flows: Data flows

        Returns:
            Mermaid diagram string
        """
        diagram = "flowchart LR\n"

        for flow in flows[:20]:  # Limit for readability
            source = flow.source_entity.replace("-", "_").replace(".", "_")
            target = flow.target_entity.replace("-", "_").replace(".", "_")

            # Style based on flow type
            if flow.flow_type in {
                DataFlowType.DATABASE_READ,
                DataFlowType.DATABASE_WRITE,
            }:
                style = "-->|DB|"
            elif flow.flow_type in {
                DataFlowType.QUEUE_PRODUCE,
                DataFlowType.QUEUE_CONSUME,
            }:
                style = "-->|Queue|"
            elif flow.flow_type in {DataFlowType.API_CALL, DataFlowType.API_RECEIVE}:
                style = "-->|API|"
            else:
                style = "-->"

            # Mark PII flows
            if flow.pii_fields:
                style = f"--PII:{len(flow.pii_fields)}-->"

            diagram += f"    {source}[{flow.source_entity}] {style} {target}[{flow.target_entity}]\n"

        return diagram

    def _generate_recommendations(self, result: DataFlowResult) -> list[str]:
        """Generate security and architecture recommendations.

        Args:
            result: Analysis result

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []

        # Check for unencrypted PII
        unencrypted_pii = [f for f in result.pii_fields if not f.is_encrypted]
        if unencrypted_pii:
            restricted = [
                f
                for f in unencrypted_pii
                if f.classification == DataClassification.RESTRICTED
            ]
            if restricted:
                recommendations.append(
                    f"**CRITICAL:** {len(restricted)} restricted PII fields are unencrypted. "
                    "Implement field-level encryption for SSN, credit card, and medical data."
                )
            else:
                recommendations.append(
                    f"**HIGH:** {len(unencrypted_pii)} PII fields are unencrypted. "
                    "Consider implementing encryption at rest."
                )

        # Check for unmasked PII in logs
        unmasked_pii = [f for f in result.pii_fields if not f.is_masked]
        if unmasked_pii:
            recommendations.append(
                f"**HIGH:** {len(unmasked_pii)} PII fields may appear in logs without masking. "
                "Implement log sanitization for sensitive fields."
            )

        # Check for cross-boundary flows
        cross_boundary = result.cross_boundary_flows
        if cross_boundary:
            recommendations.append(
                f"**MEDIUM:** {len(cross_boundary)} data flows cross service boundaries. "
                "Ensure TLS encryption and authentication for inter-service communication."
            )

        # Check for external API calls without timeout
        no_timeout = [
            e for e in result.api_endpoints if e.is_external and not e.timeout_ms
        ]
        if no_timeout:
            recommendations.append(
                f"**MEDIUM:** {len(no_timeout)} external API calls have no explicit timeout. "
                "Set appropriate timeouts to prevent cascading failures."
            )

        # Check for queues without DLQ
        no_dlq = [q for q in result.queue_connections if not q.dlq_name]
        if no_dlq:
            recommendations.append(
                f"**LOW:** {len(no_dlq)} queues have no dead letter queue configured. "
                "Configure DLQ for failed message handling."
            )

        # Check for missing rate limiting
        no_rate_limit = [
            e for e in result.api_endpoints if e.is_internal and not e.rate_limit
        ]
        if no_rate_limit:
            recommendations.append(
                f"**LOW:** {len(no_rate_limit)} internal endpoints have no rate limiting. "
                "Consider implementing rate limiting for DoS protection."
            )

        return recommendations

    def _assemble_report(
        self,
        summary: str,
        database_section: str,
        queue_section: str,
        api_section: str,
        pii_section: str,
        compliance_section: str,
        diagrams: dict[str, str],
        recommendations: list[str],
        result: DataFlowResult,
    ) -> str:
        """Assemble full report content.

        Args:
            summary: Executive summary
            database_section: Database section
            queue_section: Queue section
            api_section: API section
            pii_section: PII section
            compliance_section: Compliance section
            diagrams: Generated diagrams
            recommendations: Recommendations list
            result: Original analysis result

        Returns:
            Full report markdown content
        """
        content = f"""# Data Flow Analysis Report

**Repository:** `{result.repository_id}`
**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Analysis Duration:** {result.analysis_time_ms:.2f}ms
**Files Analyzed:** {result.files_analyzed}

---

{summary}

---

{database_section}

---

{queue_section}

---

{api_section}

---

{pii_section}

---

{compliance_section}

---

## Architecture Diagrams

"""
        # Add diagrams
        for name, diagram in diagrams.items():
            title = name.replace("_", " ").title()
            content += f"### {title}\n\n"
            content += f"```mermaid\n{diagram}```\n\n"

        # Add recommendations
        if recommendations:
            content += "---\n\n## Security Recommendations\n\n"
            for i, rec in enumerate(recommendations, 1):
                content += f"{i}. {rec}\n\n"

        content += """---

*Report generated by Project Aura Data Flow Analyzer*
"""
        return content

    def _generate_report_id(self, repository_id: str) -> str:
        """Generate unique report ID.

        Args:
            repository_id: Repository identifier

        Returns:
            Unique report identifier
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        content = f"{repository_id}:{timestamp}"
        return f"report-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _get_mock_report(self, repository_id: str) -> DataFlowReport:
        """Return mock report for testing.

        Args:
            repository_id: Repository ID

        Returns:
            Mock DataFlowReport
        """
        return DataFlowReport(
            report_id="report-mock-001",
            repository_id=repository_id,
            title=f"Data Flow Analysis Report - {repository_id}",
            generated_at=datetime.now(timezone.utc),
            summary="## Executive Summary\n\nMock summary for testing.",
            database_section="## Database Connections\n\n5 connections detected.",
            queue_section="## Message Queues\n\n3 queues detected.",
            api_section="## API Endpoints\n\n10 endpoints detected.",
            pii_section="## PII Inventory\n\n15 PII fields detected.",
            compliance_section="## Compliance Analysis\n\nGDPR, HIPAA requirements identified.",
            diagrams={
                "database_architecture": "graph LR\n    app --> db[(PostgreSQL)]",
                "queue_flows": "graph LR\n    producer --> queue[/SQS/] --> consumer",
            },
            recommendations=[
                "**HIGH:** 3 PII fields are unencrypted.",
                "**MEDIUM:** Configure DLQ for message queues.",
            ],
            export_format="markdown",
            content="# Mock Report Content",
        )
