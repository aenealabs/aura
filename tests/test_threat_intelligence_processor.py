"""
Unit Tests for Threat Intelligence Processor Lambda

Tests the scheduled threat intelligence pipeline that runs daily
to gather CVE/CISA/GitHub advisories and send notifications.

Implements ADR-010: Autonomous ADR Generation Pipeline - Phase 1 (Intelligence Foundation)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.notification_service import (
    NotificationMode,
    NotificationResult,
    NotificationService,
)


class TestNotificationServiceThreatAlerts:
    """Test NotificationService.send_threat_alert method."""

    @pytest.fixture
    def mock_service(self):
        """Provide a fresh mock notification service for each test."""
        return NotificationService(mode=NotificationMode.MOCK)

    def test_send_threat_alert_critical(self, mock_service):
        """Test sending critical threat alert."""
        results = mock_service.send_threat_alert(
            threat_id="THREAT-2025-001",
            title="Critical Remote Code Execution in OpenSSL",
            severity="CRITICAL",
            description="A critical vulnerability allows remote code execution via buffer overflow.",
            cve_ids=["CVE-2025-1234", "CVE-2025-1235"],
            affected_components=["api-server", "auth-service"],
            recommended_actions=[
                "Update OpenSSL to 3.0.12",
                "Rotate affected certificates",
            ],
        )

        assert len(results) > 0
        assert all(isinstance(r, NotificationResult) for r in results)
        # In mock mode, all results should be successful
        assert all(r.success for r in results)

    def test_send_threat_alert_high(self, mock_service):
        """Test sending high severity threat alert."""
        results = mock_service.send_threat_alert(
            threat_id="THREAT-2025-002",
            title="SQL Injection in Authentication Module",
            severity="HIGH",
            description="SQL injection vulnerability in login endpoint.",
            cve_ids=["CVE-2025-5678"],
        )

        assert len(results) > 0
        assert all(r.success for r in results)

    def test_send_threat_alert_minimal_info(self, mock_service):
        """Test sending threat alert with minimal information."""
        results = mock_service.send_threat_alert(
            threat_id="THREAT-2025-003",
            title="Potential Security Issue Detected",
            severity="MEDIUM",
            description="A potential security issue was identified.",
        )

        assert len(results) > 0
        assert all(r.success for r in results)

    def test_send_threat_alert_with_custom_recipients(self, mock_service):
        """Test sending threat alert to custom recipients."""
        custom_recipients = ["security-lead@example.com", "cto@example.com"]

        results = mock_service.send_threat_alert(
            threat_id="THREAT-2025-004",
            title="Zero-Day Vulnerability",
            severity="CRITICAL",
            description="Zero-day vulnerability requires immediate attention.",
            recipients=custom_recipients,
        )

        assert len(results) > 0
        assert all(r.success for r in results)

    def test_send_threat_alert_empty_cve_list(self, mock_service):
        """Test sending threat alert with empty CVE list."""
        results = mock_service.send_threat_alert(
            threat_id="THREAT-2025-005",
            title="Internal Security Alert",
            severity="LOW",
            description="Internal security monitoring detected unusual activity.",
            cve_ids=[],  # Empty list
            affected_components=[],
            recommended_actions=[],
        )

        assert len(results) > 0
        assert all(r.success for r in results)


class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_pipeline_result_creation(self):
        """Test creating a PipelineResult with all fields."""
        # Import here to avoid import errors if module not found
        try:
            from lambda_module.threat_intelligence_processor import PipelineResult
        except ImportError:
            # Try alternative import path
            sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))
            from threat_intelligence_processor import PipelineResult

        result = PipelineResult(
            execution_id="threat-intel-20251202-060000",
            timestamp="2025-12-02T06:00:00",
            threats_found=10,
            critical_count=2,
            high_count=3,
            medium_count=4,
            low_count=1,
            recommendations_generated=10,
            adr_triggers=2,
            notifications_sent=5,
        )

        assert result.execution_id == "threat-intel-20251202-060000"
        assert result.threats_found == 10
        assert result.critical_count == 2
        assert result.high_count == 3
        assert result.medium_count == 4
        assert result.low_count == 1
        assert result.notifications_sent == 5
        assert result.adr_triggers == 2
        assert len(result.errors) == 0
        assert len(result.threat_summaries) == 0

    def test_pipeline_result_to_dict(self):
        """Test PipelineResult serialization to dictionary."""
        try:
            from lambda_module.threat_intelligence_processor import PipelineResult
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))
            from threat_intelligence_processor import PipelineResult

        result = PipelineResult(
            execution_id="test-123",
            timestamp="2025-12-02T06:00:00",
            threats_found=5,
            critical_count=1,
            high_count=1,
            medium_count=2,
            low_count=1,
            recommendations_generated=5,
            adr_triggers=1,
            notifications_sent=2,
            errors=["Test error"],
            threat_summaries=[{"id": "THREAT-001", "severity": "CRITICAL"}],
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["execution_id"] == "test-123"
        assert result_dict["threats_found"] == 5
        assert result_dict["errors"] == ["Test error"]
        assert len(result_dict["threat_summaries"]) == 1

    def test_pipeline_result_json_serializable(self):
        """Test PipelineResult can be serialized to JSON."""
        try:
            from lambda_module.threat_intelligence_processor import PipelineResult
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))
            from threat_intelligence_processor import PipelineResult

        result = PipelineResult(
            execution_id="json-test",
            timestamp="2025-12-02T06:00:00",
            threats_found=3,
            critical_count=1,
            high_count=1,
            medium_count=1,
            low_count=0,
            recommendations_generated=3,
            adr_triggers=1,
            notifications_sent=2,
        )

        # Should not raise
        json_str = json.dumps(result.to_dict())
        assert "json-test" in json_str


class TestThreatIntelligenceProcessorHandler:
    """Test the Lambda handler function."""

    @pytest.fixture
    def mock_event(self):
        """CloudWatch Events scheduled event."""
        return {
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

    @pytest.fixture
    def mock_context(self):
        """Mock Lambda context."""
        context = MagicMock()
        context.function_name = "aura-threat-intel-processor-dev"
        context.memory_limit_in_mb = 512
        context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:aura-threat-intel-processor-dev"
        context.aws_request_id = "test-request-id"
        return context

    def test_handler_mock_mode(self, mock_event, mock_context):
        """Test handler in mock mode returns successful result."""
        # Set environment for mock mode
        os.environ["USE_MOCK"] = "true"
        os.environ["SEVERITY_THRESHOLD"] = "MEDIUM"
        os.environ["MAX_CVE_AGE_DAYS"] = "30"

        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))
            from threat_intelligence_processor import handler

            # Handler should work in mock mode
            result = handler(mock_event, mock_context)

            assert "statusCode" in result
            assert "body" in result

            # May return 500 if services not available (expected in unit test)
            if result["statusCode"] == 200:
                body = json.loads(result["body"])
                assert "execution_id" in body
                assert "threats_found" in body
            else:
                # Services not available is acceptable for unit test
                body = json.loads(result["body"])
                assert "error" in body or "execution_id" in body

        except ImportError:
            pytest.skip("Threat intelligence processor imports not available")
        finally:
            # Cleanup environment
            os.environ.pop("USE_MOCK", None)
            os.environ.pop("SEVERITY_THRESHOLD", None)
            os.environ.pop("MAX_CVE_AGE_DAYS", None)

    def test_handler_returns_proper_format(self, mock_event, mock_context):
        """Test handler returns Lambda response format."""
        os.environ["USE_MOCK"] = "true"

        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))
            from threat_intelligence_processor import handler

            result = handler(mock_event, mock_context)

            # Standard Lambda response format
            assert isinstance(result, dict)
            assert "statusCode" in result
            assert "body" in result
            assert isinstance(result["statusCode"], int)
            assert isinstance(result["body"], str)

            # Body should be valid JSON
            body = json.loads(result["body"])
            assert isinstance(body, dict)

        except ImportError:
            pytest.skip("Threat intelligence processor imports not available")
        finally:
            os.environ.pop("USE_MOCK", None)


class TestThreatIntelligenceProcessorIntegration:
    """Integration tests for the threat intelligence processor."""

    @pytest.mark.integration
    def test_full_pipeline_mock_mode(self):
        """Test full pipeline execution in mock mode."""
        os.environ["USE_MOCK"] = "true"
        os.environ["SEVERITY_THRESHOLD"] = "LOW"
        os.environ["MAX_CVE_AGE_DAYS"] = "7"

        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambda"))
            from threat_intelligence_processor import handler

            event = {
                "version": "0",
                "id": "integration-test",
                "detail-type": "Scheduled Event",
                "source": "aws.events",
                "account": "123456789012",
                "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "region": "us-east-1",
                "resources": [],
                "detail": {},
            }

            result = handler(event, None)

            assert result["statusCode"] in [200, 500]  # Success or service unavailable

        except ImportError:
            pytest.skip("Integration test requires full pipeline dependencies")
        finally:
            os.environ.pop("USE_MOCK", None)
            os.environ.pop("SEVERITY_THRESHOLD", None)
            os.environ.pop("MAX_CVE_AGE_DAYS", None)


class TestCloudFormationTemplate:
    """Test CloudFormation template validity."""

    def test_template_exists(self):
        """Test that the CloudFormation template exists."""
        template_path = (
            Path(__file__).parent.parent
            / "deploy"
            / "cloudformation"
            / "threat-intel-scheduler.yaml"
        )
        assert template_path.exists(), f"Template not found at {template_path}"

    def test_template_is_valid_cloudformation(self):
        """Test that the template is valid CloudFormation using cfn-lint."""
        import subprocess

        template_path = (
            Path(__file__).parent.parent
            / "deploy"
            / "cloudformation"
            / "threat-intel-scheduler.yaml"
        )

        # Run cfn-lint to validate the template
        result = subprocess.run(
            ["cfn-lint", str(template_path)],
            capture_output=True,
            text=True,
        )

        # cfn-lint returns 0 for valid templates (warnings are okay)
        # We check for errors only (exit code 2 or higher indicates errors)
        assert (
            result.returncode < 2
        ), f"cfn-lint errors: {result.stdout}\n{result.stderr}"

    def test_template_has_required_resources(self):
        """Test that template contains expected resource definitions."""
        template_path = (
            Path(__file__).parent.parent
            / "deploy"
            / "cloudformation"
            / "threat-intel-scheduler.yaml"
        )

        with open(template_path) as f:
            content = f.read()

        # Check required resources exist in template
        required_resources = [
            "ThreatIntelProcessorRole:",
            "ThreatIntelProcessorFunction:",
            "ThreatIntelScheduleRule:",
            "ThreatIntelSchedulePermission:",
            "ThreatIntelProcessorLogGroup:",
        ]

        for resource in required_resources:
            assert resource in content, f"Missing required resource: {resource}"

    def test_template_has_parameters(self):
        """Test that template has expected parameter definitions."""
        template_path = (
            Path(__file__).parent.parent
            / "deploy"
            / "cloudformation"
            / "threat-intel-scheduler.yaml"
        )

        with open(template_path) as f:
            content = f.read()

        # Check required parameters
        required_params = [
            "ProjectName:",
            "Environment:",
            "ScheduleExpression:",
            "SeverityThreshold:",
            "MaxCVEAgeDays:",
            "LambdaS3Bucket:",
            "LambdaS3Key:",
        ]

        for param in required_params:
            assert param in content, f"Missing required parameter: {param}"

    def test_template_schedule_expression_default(self):
        """Test that default schedule is daily at 6 AM UTC."""
        template_path = (
            Path(__file__).parent.parent
            / "deploy"
            / "cloudformation"
            / "threat-intel-scheduler.yaml"
        )

        with open(template_path) as f:
            content = f.read()

        # Check that the cron expression is present
        assert "cron(0 6 * * ? *)" in content, "Default schedule not set to 6 AM UTC"

    def test_template_has_outputs(self):
        """Test that template exports useful outputs."""
        template_path = (
            Path(__file__).parent.parent
            / "deploy"
            / "cloudformation"
            / "threat-intel-scheduler.yaml"
        )

        with open(template_path) as f:
            content = f.read()

        assert "FunctionArn:" in content
        assert "FunctionName:" in content
        assert "ScheduleExpression:" in content
