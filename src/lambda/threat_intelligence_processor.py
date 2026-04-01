"""
Project Aura - Threat Intelligence Pipeline Processor

Scheduled Lambda function that runs the threat intelligence pipeline daily.
Triggered by CloudWatch Events Rule (daily at 6 AM UTC).

Implements ADR-010: Autonomous ADR Generation Pipeline - Phase 1 (Intelligence Foundation)

Pipeline Stages:
1. ThreatIntelligenceAgent - Gather CVE/CISA/GitHub advisories
2. AdaptiveIntelligenceAgent - Analyze codebase impact and generate recommendations
3. ArchitectureReviewAgent - Detect ADR-worthy decisions
4. ADRGeneratorAgent - Generate draft ADRs (future)

This Lambda handles the daily scheduled execution of stages 1-3.
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import services (available when deployed with proper packaging)
try:
    from src.agents.threat_intelligence_agent import (
        ThreatIntelConfig,
        ThreatIntelligenceAgent,
        ThreatSeverity,
    )
    from src.services.notification_service import NotificationMode, NotificationService
    from src.services.threat_feed_client import (
        ThreatFeedClient,
        ThreatFeedConfig,
        ThreatFeedMode,
    )

    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False
    logger.warning("Services not available - using stub mode")


@dataclass
class PipelineResult:
    """Result of threat intelligence pipeline execution."""

    execution_id: str
    timestamp: str
    threats_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    recommendations_generated: int
    adr_triggers: int
    notifications_sent: int
    errors: list[str] = field(default_factory=list)
    threat_summaries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for daily threat intelligence pipeline.

    This function is triggered by CloudWatch Events daily at 6 AM UTC.
    It orchestrates the threat intelligence gathering and analysis pipeline.

    Args:
        event: CloudWatch Events scheduled event
        context: Lambda context

    Returns:
        Pipeline execution result summary
    """
    logger.info("Starting threat intelligence pipeline")
    logger.info(f"Event: {json.dumps(event)}")

    # Generate execution ID
    execution_id = f"threat-intel-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Get configuration from environment
    use_mock = os.environ.get("USE_MOCK", "false").lower() == "true"
    nvd_api_key = os.environ.get("NVD_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN", "")
    severity_threshold = os.environ.get("SEVERITY_THRESHOLD", "MEDIUM")
    max_cve_age_days = int(os.environ.get("MAX_CVE_AGE_DAYS", "30"))

    if not SERVICES_AVAILABLE:
        logger.error("Services not available - cannot run pipeline")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Services not available",
                    "execution_id": execution_id,
                }
            ),
        }

    try:
        # Initialize result tracking
        result = PipelineResult(
            execution_id=execution_id,
            timestamp=datetime.now().isoformat(),
            threats_found=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            recommendations_generated=0,
            adr_triggers=0,
            notifications_sent=0,
        )

        # Initialize notification service
        notification_service = NotificationService(
            mode=NotificationMode.MOCK if use_mock else NotificationMode.AWS,
            sns_topic_arn=sns_topic_arn,
        )

        # Initialize threat feed client
        feed_config = ThreatFeedConfig(
            nvd_api_key=nvd_api_key if nvd_api_key else None,
            github_token=github_token if github_token else None,
            max_cves_per_request=50,
            cache_ttl_minutes=60,
        )
        threat_feed_client = ThreatFeedClient(
            mode=ThreatFeedMode.MOCK if use_mock else ThreatFeedMode.REAL,
            config=feed_config,
        )

        # Initialize threat intelligence agent
        intel_config = ThreatIntelConfig(
            nvd_api_key=nvd_api_key if nvd_api_key else None,
            max_cve_age_days=max_cve_age_days,
            severity_threshold=ThreatSeverity[severity_threshold],
        )
        threat_agent = ThreatIntelligenceAgent(
            config=intel_config,
            threat_feed_client=threat_feed_client,
        )

        # Stage 1: Gather threat intelligence
        logger.info("Stage 1: Gathering threat intelligence...")
        threat_reports = asyncio.run(threat_agent.gather_intelligence())
        result.threats_found = len(threat_reports)

        # Count by severity
        for report in threat_reports:
            if report.severity == ThreatSeverity.CRITICAL:
                result.critical_count += 1
            elif report.severity == ThreatSeverity.HIGH:
                result.high_count += 1
            elif report.severity == ThreatSeverity.MEDIUM:
                result.medium_count += 1
            else:
                result.low_count += 1

            # Add summary for each threat
            result.threat_summaries.append(
                {
                    "id": report.id,
                    "title": report.title,
                    "severity": report.severity.value,
                    "category": report.category.value,
                    "cve_ids": report.cve_ids,
                    "source": report.source,
                }
            )

        logger.info(
            f"Found {result.threats_found} threats: "
            f"{result.critical_count} critical, {result.high_count} high, "
            f"{result.medium_count} medium, {result.low_count} low"
        )

        # Stage 2: Send notifications for critical/high threats
        if result.critical_count > 0 or result.high_count > 0:
            logger.info("Stage 2: Sending notifications for critical/high threats...")

            # Group critical and high threats for notification
            critical_high_threats = [
                t
                for t in threat_reports
                if t.severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH)
            ]

            for threat in critical_high_threats:
                try:
                    notification_service.send_threat_alert(
                        threat_id=threat.id,
                        title=threat.title,
                        severity=threat.severity.value,
                        description=threat.description,
                        cve_ids=threat.cve_ids,
                        affected_components=threat.affected_components,
                        recommended_actions=threat.recommended_actions,
                    )
                    result.notifications_sent += 1
                except Exception as e:
                    error_msg = f"Failed to send notification for {threat.id}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Stage 3: Generate recommendations (placeholder for AdaptiveIntelligenceAgent)
        # This will be expanded when the full pipeline is implemented
        logger.info("Stage 3: Generating recommendations...")
        result.recommendations_generated = result.threats_found  # 1:1 for now

        # Stage 4: Detect ADR triggers (placeholder for ArchitectureReviewAgent)
        # Security CVEs affecting deployed components trigger ADR consideration
        adr_triggers = [
            t
            for t in threat_reports
            if t.severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH)
            and t.affected_components
        ]
        result.adr_triggers = len(adr_triggers)

        if result.adr_triggers > 0:
            logger.info(
                f"Stage 4: {result.adr_triggers} potential ADR triggers identified"
            )

        # Log summary
        logger.info(f"Pipeline complete: {json.dumps(result.to_dict())}")

        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps(result.to_dict()),
        }

    except Exception as e:
        logger.error(f"Threat intelligence pipeline failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(e),
                    "execution_id": execution_id,
                }
            ),
        }


# Local testing support
if __name__ == "__main__":
    # Set up local environment for testing
    os.environ["USE_MOCK"] = "true"
    os.environ["SEVERITY_THRESHOLD"] = "MEDIUM"
    os.environ["MAX_CVE_AGE_DAYS"] = "30"

    # Simulate CloudWatch Events scheduled event
    test_event = {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2025-12-02T06:00:00Z",
        "region": "us-east-1",
        "resources": [
            "arn:aws:events:us-east-1:123456789012:rule/aura-threat-intel-pipeline"
        ],
        "detail": {},
    }

    # Run handler
    result = handler(test_event, None)
    print(f"Result: {json.dumps(result, indent=2)}")
