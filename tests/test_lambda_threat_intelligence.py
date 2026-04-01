"""
Project Aura - Threat Intelligence Processor Lambda Tests

Tests for the Lambda handler that runs the threat intelligence pipeline.
Uses moto fixtures from conftest.py for AWS service mocking.

Target: 85% coverage of src/lambda/threat_intelligence_processor.py
"""

import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Set environment before importing Lambda
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

# Clear module from cache to ensure fresh import with correct environment
_module_name = "src.lambda.threat_intelligence_processor"
if _module_name in sys.modules:
    del sys.modules[_module_name]

# Import the lambda module using importlib (lambda is a reserved keyword)
threat_intel = importlib.import_module(_module_name)


class TestPipelineResult:
    """Tests for the PipelineResult dataclass."""

    def test_pipeline_result_creation(self):
        """Test creating a PipelineResult."""
        result = threat_intel.PipelineResult(
            execution_id="test-123",
            timestamp="2025-12-06T10:00:00",
            threats_found=5,
            critical_count=1,
            high_count=2,
            medium_count=1,
            low_count=1,
            recommendations_generated=5,
            adr_triggers=2,
            notifications_sent=3,
        )

        assert result.execution_id == "test-123"
        assert result.threats_found == 5
        assert result.critical_count == 1
        assert result.errors == []
        assert result.threat_summaries == []

    def test_pipeline_result_to_dict(self):
        """Test converting PipelineResult to dictionary."""
        result = threat_intel.PipelineResult(
            execution_id="test-123",
            timestamp="2025-12-06T10:00:00",
            threats_found=3,
            critical_count=1,
            high_count=1,
            medium_count=1,
            low_count=0,
            recommendations_generated=3,
            adr_triggers=1,
            notifications_sent=2,
            errors=["error1"],
            threat_summaries=[{"id": "CVE-2025-1234"}],
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["execution_id"] == "test-123"
        assert result_dict["threats_found"] == 3
        assert result_dict["errors"] == ["error1"]
        assert result_dict["threat_summaries"] == [{"id": "CVE-2025-1234"}]


class TestThreatIntelHandler:
    """Tests for the main handler function."""

    def test_handler_services_not_available(self):
        """Test handler returns 500 when services unavailable."""
        original = threat_intel.SERVICES_AVAILABLE
        threat_intel.SERVICES_AVAILABLE = False

        try:
            event = {"detail-type": "Scheduled Event"}
            response = threat_intel.handler(event, None)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert "error" in body
            assert "execution_id" in body
        finally:
            threat_intel.SERVICES_AVAILABLE = original

    def test_handler_success_no_threats(self):
        """Test handler succeeds when no threats found."""
        os.environ["USE_MOCK"] = "true"
        os.environ["SEVERITY_THRESHOLD"] = "MEDIUM"

        with patch.object(threat_intel, "NotificationService"):
            with patch.object(threat_intel, "ThreatFeedClient"):
                with patch.object(
                    threat_intel, "ThreatIntelligenceAgent"
                ) as mock_agent_class:
                    mock_agent = MagicMock()
                    # Use AsyncMock for the async gather_intelligence method
                    mock_agent.gather_intelligence = AsyncMock(return_value=[])
                    mock_agent_class.return_value = mock_agent

                    original = threat_intel.SERVICES_AVAILABLE
                    threat_intel.SERVICES_AVAILABLE = True

                    try:
                        response = threat_intel.handler({}, None)

                        assert response["statusCode"] == 200
                        body = json.loads(response["body"])
                        assert body["threats_found"] == 0
                        assert body["notifications_sent"] == 0
                    finally:
                        threat_intel.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]
        if "SEVERITY_THRESHOLD" in os.environ:
            del os.environ["SEVERITY_THRESHOLD"]

    def test_handler_with_threats_found(self):
        """Test handler processes threats correctly."""
        os.environ["USE_MOCK"] = "true"
        os.environ["SEVERITY_THRESHOLD"] = "MEDIUM"

        # Create mock threat reports
        mock_threat_critical = MagicMock()
        mock_threat_critical.id = "THREAT-001"
        mock_threat_critical.title = "Critical Vulnerability"
        mock_threat_critical.severity = threat_intel.ThreatSeverity.CRITICAL
        mock_threat_critical.category = MagicMock(value="vulnerability")
        mock_threat_critical.cve_ids = ["CVE-2025-1234"]
        mock_threat_critical.source = "NVD"
        mock_threat_critical.description = "Critical issue"
        mock_threat_critical.affected_components = ["component1"]
        mock_threat_critical.recommended_actions = ["Update immediately"]

        mock_threat_high = MagicMock()
        mock_threat_high.id = "THREAT-002"
        mock_threat_high.title = "High Severity Issue"
        mock_threat_high.severity = threat_intel.ThreatSeverity.HIGH
        mock_threat_high.category = MagicMock(value="security")
        mock_threat_high.cve_ids = []
        mock_threat_high.source = "CISA"
        mock_threat_high.description = "High issue"
        mock_threat_high.affected_components = []
        mock_threat_high.recommended_actions = []

        mock_threat_medium = MagicMock()
        mock_threat_medium.id = "THREAT-003"
        mock_threat_medium.title = "Medium Issue"
        mock_threat_medium.severity = threat_intel.ThreatSeverity.MEDIUM
        mock_threat_medium.category = MagicMock(value="advisory")
        mock_threat_medium.cve_ids = []
        mock_threat_medium.source = "GitHub"

        mock_threat_low = MagicMock()
        mock_threat_low.id = "THREAT-004"
        mock_threat_low.title = "Low Issue"
        mock_threat_low.severity = threat_intel.ThreatSeverity.LOW
        mock_threat_low.category = MagicMock(value="info")
        mock_threat_low.cve_ids = []
        mock_threat_low.source = "Other"

        threats = [
            mock_threat_critical,
            mock_threat_high,
            mock_threat_medium,
            mock_threat_low,
        ]

        with patch.object(threat_intel, "NotificationService") as mock_notif_class:
            mock_notif = MagicMock()
            mock_notif_class.return_value = mock_notif

            with patch.object(threat_intel, "ThreatFeedClient"):
                with patch.object(
                    threat_intel, "ThreatIntelligenceAgent"
                ) as mock_agent_class:
                    mock_agent = MagicMock()
                    # Use AsyncMock for the async gather_intelligence method
                    mock_agent.gather_intelligence = AsyncMock(return_value=threats)
                    mock_agent_class.return_value = mock_agent

                    original = threat_intel.SERVICES_AVAILABLE
                    threat_intel.SERVICES_AVAILABLE = True

                    try:
                        response = threat_intel.handler({}, None)

                        assert response["statusCode"] == 200
                        body = json.loads(response["body"])
                        assert body["threats_found"] == 4
                        assert body["critical_count"] == 1
                        assert body["high_count"] == 1
                        assert body["medium_count"] == 1
                        assert body["low_count"] == 1
                        assert body["recommendations_generated"] == 4
                        assert (
                            body["adr_triggers"] == 1
                        )  # Only critical with components
                        assert len(body["threat_summaries"]) == 4
                    finally:
                        threat_intel.SERVICES_AVAILABLE = original

        for key in ["USE_MOCK", "SEVERITY_THRESHOLD"]:
            if key in os.environ:
                del os.environ[key]

    def test_handler_exception_handling(self):
        """Test handler returns 500 on exception."""
        os.environ["USE_MOCK"] = "true"

        with patch.object(threat_intel, "NotificationService") as mock_notif:
            mock_notif.side_effect = Exception("Connection failed")

            original = threat_intel.SERVICES_AVAILABLE
            threat_intel.SERVICES_AVAILABLE = True

            try:
                response = threat_intel.handler({}, None)

                assert response["statusCode"] == 500
                body = json.loads(response["body"])
                assert "Connection failed" in body["error"]
                assert "execution_id" in body
            finally:
                threat_intel.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]

    def test_handler_notification_failure_captured(self):
        """Test that notification failures are captured in errors."""
        os.environ["USE_MOCK"] = "true"
        os.environ["SEVERITY_THRESHOLD"] = "MEDIUM"

        mock_threat = MagicMock()
        mock_threat.id = "THREAT-001"
        mock_threat.title = "Critical"
        mock_threat.severity = threat_intel.ThreatSeverity.CRITICAL
        mock_threat.category = MagicMock(value="vulnerability")
        mock_threat.cve_ids = ["CVE-2025-0001"]
        mock_threat.source = "NVD"
        mock_threat.description = "Test"
        mock_threat.affected_components = []
        mock_threat.recommended_actions = []

        with patch.object(threat_intel, "NotificationService") as mock_notif_class:
            mock_notif = MagicMock()
            mock_notif.send_threat_alert.side_effect = Exception("SNS error")
            mock_notif_class.return_value = mock_notif

            with patch.object(threat_intel, "ThreatFeedClient"):
                with patch.object(
                    threat_intel, "ThreatIntelligenceAgent"
                ) as mock_agent_class:
                    mock_agent = MagicMock()
                    # Use AsyncMock for the async gather_intelligence method
                    mock_agent.gather_intelligence = AsyncMock(
                        return_value=[mock_threat]
                    )
                    mock_agent_class.return_value = mock_agent

                    original = threat_intel.SERVICES_AVAILABLE
                    threat_intel.SERVICES_AVAILABLE = True

                    try:
                        response = threat_intel.handler({}, None)

                        assert response["statusCode"] == 200
                        body = json.loads(response["body"])
                        assert body["notifications_sent"] == 0
                        assert len(body["errors"]) == 1
                        assert "SNS error" in body["errors"][0]
                    finally:
                        threat_intel.SERVICES_AVAILABLE = original

        for key in ["USE_MOCK", "SEVERITY_THRESHOLD"]:
            if key in os.environ:
                del os.environ[key]


class TestEnvironmentConfiguration:
    """Tests for environment variable handling."""

    def test_default_severity_threshold(self):
        """Test default severity threshold is MEDIUM."""
        os.environ["USE_MOCK"] = "true"
        # Don't set SEVERITY_THRESHOLD

        with patch.object(threat_intel, "NotificationService"):
            with patch.object(threat_intel, "ThreatFeedClient"):
                with patch.object(
                    threat_intel, "ThreatIntelligenceAgent"
                ) as mock_agent_class:
                    with patch.object(threat_intel, "ThreatIntelConfig") as mock_config:
                        mock_agent = MagicMock()
                        mock_agent.gather_intelligence = AsyncMock(return_value=[])
                        mock_agent_class.return_value = mock_agent

                        original = threat_intel.SERVICES_AVAILABLE
                        threat_intel.SERVICES_AVAILABLE = True

                        try:
                            threat_intel.handler({}, None)

                            # Check config was created with MEDIUM threshold
                            call_kwargs = mock_config.call_args.kwargs
                            assert (
                                call_kwargs["severity_threshold"]
                                == threat_intel.ThreatSeverity.MEDIUM
                            )
                        finally:
                            threat_intel.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]

    def test_custom_max_cve_age(self):
        """Test custom MAX_CVE_AGE_DAYS is used."""
        os.environ["USE_MOCK"] = "true"
        os.environ["MAX_CVE_AGE_DAYS"] = "60"

        with patch.object(threat_intel, "NotificationService"):
            with patch.object(threat_intel, "ThreatFeedClient"):
                with patch.object(
                    threat_intel, "ThreatIntelligenceAgent"
                ) as mock_agent_class:
                    with patch.object(threat_intel, "ThreatIntelConfig") as mock_config:
                        mock_agent = MagicMock()
                        mock_agent.gather_intelligence = AsyncMock(return_value=[])
                        mock_agent_class.return_value = mock_agent

                        original = threat_intel.SERVICES_AVAILABLE
                        threat_intel.SERVICES_AVAILABLE = True

                        try:
                            threat_intel.handler({}, None)

                            call_kwargs = mock_config.call_args.kwargs
                            assert call_kwargs["max_cve_age_days"] == 60
                        finally:
                            threat_intel.SERVICES_AVAILABLE = original

        for key in ["USE_MOCK", "MAX_CVE_AGE_DAYS"]:
            if key in os.environ:
                del os.environ[key]

    def test_api_keys_passed_to_config(self):
        """Test that API keys are passed to configuration."""
        os.environ["USE_MOCK"] = "true"
        os.environ["NVD_API_KEY"] = "test-nvd-key"
        os.environ["GITHUB_TOKEN"] = "test-github-token"

        with patch.object(threat_intel, "NotificationService"):
            with patch.object(threat_intel, "ThreatFeedClient") as _mock_feed_class:
                with patch.object(threat_intel, "ThreatFeedConfig") as mock_feed_config:
                    with patch.object(
                        threat_intel, "ThreatIntelligenceAgent"
                    ) as mock_agent_class:
                        mock_agent = MagicMock()
                        mock_agent.gather_intelligence = AsyncMock(return_value=[])
                        mock_agent_class.return_value = mock_agent

                        original = threat_intel.SERVICES_AVAILABLE
                        threat_intel.SERVICES_AVAILABLE = True

                        try:
                            threat_intel.handler({}, None)

                            # Check feed config got the API keys
                            feed_call_kwargs = mock_feed_config.call_args.kwargs
                            assert feed_call_kwargs["nvd_api_key"] == "test-nvd-key"
                            assert (
                                feed_call_kwargs["github_token"] == "test-github-token"
                            )
                        finally:
                            threat_intel.SERVICES_AVAILABLE = original

        for key in ["USE_MOCK", "NVD_API_KEY", "GITHUB_TOKEN"]:
            if key in os.environ:
                del os.environ[key]


class TestExecutionId:
    """Tests for execution ID generation."""

    def test_execution_id_format(self):
        """Test execution ID has expected format."""
        os.environ["USE_MOCK"] = "true"

        with patch.object(threat_intel, "NotificationService"):
            with patch.object(threat_intel, "ThreatFeedClient"):
                with patch.object(
                    threat_intel, "ThreatIntelligenceAgent"
                ) as mock_agent_class:
                    mock_agent = MagicMock()
                    mock_agent.gather_intelligence = AsyncMock(return_value=[])
                    mock_agent_class.return_value = mock_agent

                    original = threat_intel.SERVICES_AVAILABLE
                    threat_intel.SERVICES_AVAILABLE = True

                    try:
                        response = threat_intel.handler({}, None)

                        body = json.loads(response["body"])
                        assert body["execution_id"].startswith("threat-intel-")
                        # Should have date format YYYYMMDD-HHMMSS
                        assert len(body["execution_id"]) > len("threat-intel-")
                    finally:
                        threat_intel.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]
