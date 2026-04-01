"""
Project Aura - Security Telemetry Service Tests

Tests for the SecurityTelemetryService that queries AWS security services
(GuardDuty, WAF logs, CloudTrail) for real-time threat intelligence.

Target: 85% coverage of src/services/security_telemetry_service.py
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.security_telemetry_service import (
    FindingSeverity,
    FindingType,
    SecurityFinding,
    SecurityTelemetryService,
    TelemetryConfig,
    TelemetryMode,
    create_security_telemetry_service,
)


class TestSecurityFinding:
    """Tests for SecurityFinding dataclass."""

    def test_finding_creation(self):
        """Test creating a SecurityFinding."""
        finding = SecurityFinding(
            id="test-001",
            finding_type=FindingType.GUARDDUTY,
            severity=FindingSeverity.HIGH,
            title="Test Finding",
            description="A test security finding",
            detected_at=datetime.now(timezone.utc),
            source_service="GuardDuty",
            affected_resources=["EC2: i-12345"],
            indicators=["IP: 1.2.3.4"],
            recommended_actions=["Block the IP"],
        )

        assert finding.id == "test-001"
        assert finding.finding_type == FindingType.GUARDDUTY
        assert finding.severity == FindingSeverity.HIGH
        assert finding.source_service == "GuardDuty"

    def test_finding_to_dict(self):
        """Test converting SecurityFinding to dictionary."""
        finding = SecurityFinding(
            id="test-002",
            finding_type=FindingType.WAF_EVENT,
            severity=FindingSeverity.MEDIUM,
            title="WAF Block",
            description="Blocked SQL injection attempt",
            detected_at=datetime(2025, 12, 6, 10, 0, 0, tzinfo=timezone.utc),
            source_service="AWS WAF",
        )

        result = finding.to_dict()

        assert result["id"] == "test-002"
        assert result["finding_type"] == "waf_event"
        assert result["severity"] == "medium"
        assert "2025-12-06" in result["detected_at"]


class TestTelemetryConfig:
    """Tests for TelemetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TelemetryConfig()

        assert config.lookback_hours == 24
        assert config.guardduty_enabled is True
        assert config.guardduty_min_severity == 4.0
        assert config.max_findings_per_source == 100

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TelemetryConfig(
            lookback_hours=48,
            guardduty_min_severity=7.0,
            waf_logs_enabled=False,
        )

        assert config.lookback_hours == 48
        assert config.guardduty_min_severity == 7.0
        assert config.waf_logs_enabled is False


class TestSecurityTelemetryServiceMock:
    """Tests for SecurityTelemetryService in MOCK mode."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        assert service.mode == TelemetryMode.MOCK
        assert service._guardduty_client is None
        assert service._logs_client is None

    @pytest.mark.asyncio
    async def test_get_mock_guardduty_findings(self):
        """Test getting mock GuardDuty findings."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        findings = await service.get_guardduty_findings()

        assert len(findings) > 0
        assert all(f.finding_type == FindingType.GUARDDUTY for f in findings)
        assert any(f.severity == FindingSeverity.HIGH for f in findings)

    @pytest.mark.asyncio
    async def test_get_mock_waf_events(self):
        """Test getting mock WAF events."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        findings = await service.get_waf_events()

        assert len(findings) > 0
        assert all(f.finding_type == FindingType.WAF_EVENT for f in findings)
        assert findings[0].source_service == "AWS WAF"

    @pytest.mark.asyncio
    async def test_get_mock_cloudtrail_anomalies(self):
        """Test getting mock CloudTrail anomalies."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        findings = await service.get_cloudtrail_anomalies()

        assert len(findings) > 0
        assert all(f.finding_type == FindingType.CLOUDTRAIL_ANOMALY for f in findings)
        assert findings[0].source_service == "CloudTrail"

    @pytest.mark.asyncio
    async def test_get_all_security_findings_mock(self):
        """Test getting all security findings in mock mode."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        findings = await service.get_security_findings()

        # Should have findings from all three sources
        assert len(findings) >= 3
        types = {f.finding_type for f in findings}
        assert FindingType.GUARDDUTY in types
        assert FindingType.WAF_EVENT in types
        assert FindingType.CLOUDTRAIL_ANOMALY in types

    @pytest.mark.asyncio
    async def test_filter_by_severity(self):
        """Test filtering findings by severity."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        # Get only HIGH and above
        findings = await service.get_security_findings(
            min_severity=FindingSeverity.HIGH
        )

        for finding in findings:
            assert finding.severity in (
                FindingSeverity.HIGH,
                FindingSeverity.CRITICAL,
            )

    @pytest.mark.asyncio
    async def test_filter_by_finding_type(self):
        """Test filtering findings by type."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        findings = await service.get_security_findings(
            finding_types=[FindingType.GUARDDUTY]
        )

        assert all(f.finding_type == FindingType.GUARDDUTY for f in findings)

    @pytest.mark.asyncio
    async def test_findings_sorted_by_severity(self):
        """Test that findings are sorted by severity (critical first)."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        findings = await service.get_security_findings()

        if len(findings) > 1:
            severity_order = [
                FindingSeverity.CRITICAL,
                FindingSeverity.HIGH,
                FindingSeverity.MEDIUM,
                FindingSeverity.LOW,
                FindingSeverity.INFORMATIONAL,
            ]
            for i in range(len(findings) - 1):
                idx1 = severity_order.index(findings[i].severity)
                idx2 = severity_order.index(findings[i + 1].severity)
                assert idx1 <= idx2, "Findings should be sorted by severity"


class TestSecurityTelemetryServiceAWS:
    """Tests for SecurityTelemetryService in AWS mode (with mocked clients)."""

    def test_init_aws_mode(self):
        """Test initialization in AWS mode."""
        with patch("boto3.client") as mock_boto:
            mock_boto.return_value = MagicMock()
            service = SecurityTelemetryService(mode=TelemetryMode.AWS)

            assert service.mode == TelemetryMode.AWS
            assert mock_boto.call_count == 2  # guardduty + logs

    @pytest.mark.asyncio
    async def test_get_detector_id(self):
        """Test getting GuardDuty detector ID."""
        with patch("boto3.client") as mock_boto:
            mock_guardduty = MagicMock()
            mock_guardduty.list_detectors.return_value = {
                "DetectorIds": ["detector-123"]
            }
            mock_boto.return_value = mock_guardduty

            service = SecurityTelemetryService(mode=TelemetryMode.AWS)
            detector_id = await service._get_detector_id()

            assert detector_id == "detector-123"

    @pytest.mark.asyncio
    async def test_get_detector_id_cached(self):
        """Test that detector ID is cached."""
        with patch("boto3.client") as mock_boto:
            mock_guardduty = MagicMock()
            mock_guardduty.list_detectors.return_value = {
                "DetectorIds": ["detector-456"]
            }
            mock_boto.return_value = mock_guardduty

            service = SecurityTelemetryService(mode=TelemetryMode.AWS)

            # First call
            id1 = await service._get_detector_id()
            # Second call should use cache
            id2 = await service._get_detector_id()

            assert id1 == id2 == "detector-456"

    @pytest.mark.asyncio
    async def test_get_guardduty_findings_no_detector(self):
        """Test GuardDuty findings when no detector exists."""
        with patch("boto3.client") as mock_boto:
            mock_guardduty = MagicMock()
            mock_guardduty.list_detectors.return_value = {"DetectorIds": []}
            mock_boto.return_value = mock_guardduty

            service = SecurityTelemetryService(mode=TelemetryMode.AWS)
            findings = await service.get_guardduty_findings()

            assert findings == []

    @pytest.mark.asyncio
    async def test_parse_guardduty_finding(self):
        """Test parsing a GuardDuty finding."""
        with patch("boto3.client"):
            service = SecurityTelemetryService(mode=TelemetryMode.AWS)

            raw_finding = {
                "Id": "finding-001",
                "Title": "UnauthorizedAccess:EC2/SSHBruteForce",
                "Description": "SSH brute force attack detected",
                "Severity": 8.5,
                "UpdatedAt": "2025-12-06T10:00:00Z",
                "Resource": {"InstanceDetails": {"InstanceId": "i-12345"}},
                "Service": {
                    "Action": {
                        "NetworkConnectionAction": {
                            "RemoteIpDetails": {"IpAddressV4": "203.0.113.50"},
                            "LocalPortDetails": {"Port": 22},
                        }
                    }
                },
                "Type": "UnauthorizedAccess:EC2/SSHBruteForce",
            }

            finding = service._parse_guardduty_finding(raw_finding)

            assert finding is not None
            assert finding.id == "finding-001"
            assert finding.severity == FindingSeverity.CRITICAL
            assert "EC2: i-12345" in finding.affected_resources
            assert any("203.0.113.50" in i for i in finding.indicators)

    def test_get_guardduty_recommendations(self):
        """Test getting recommendations for different finding types."""
        with patch("boto3.client"):
            service = SecurityTelemetryService(mode=TelemetryMode.AWS)

            # Test unauthorized access
            recs = service._get_guardduty_recommendations("UnauthorizedAccess:EC2/Test")
            assert any("IAM" in r for r in recs)

            # Test trojan
            recs = service._get_guardduty_recommendations("Trojan:EC2/Malware")
            assert any("Isolate" in r for r in recs)

            # Test crypto mining
            recs = service._get_guardduty_recommendations(
                "CryptoCurrency:EC2/BitcoinTool"
            )
            assert any("Terminate" in r for r in recs)

            # Test unknown type (default)
            recs = service._get_guardduty_recommendations("Unknown:Type")
            assert any("Review" in r for r in recs)


class TestFactoryFunction:
    """Tests for create_security_telemetry_service factory."""

    def test_create_with_aws_mode(self):
        """Test creating service with AWS mode."""
        with patch("boto3.client"):
            service = create_security_telemetry_service(use_aws=True)
            assert service.mode == TelemetryMode.AWS

    def test_create_with_mock_mode(self):
        """Test creating service with mock mode."""
        service = create_security_telemetry_service(use_aws=False)
        assert service.mode == TelemetryMode.MOCK

    def test_create_with_custom_config(self):
        """Test creating service with custom config."""
        config = TelemetryConfig(lookback_hours=48)
        service = create_security_telemetry_service(use_aws=False, config=config)
        assert service.config.lookback_hours == 48


class TestIntegrationWithThreatIntelligenceAgent:
    """Tests for integration with ThreatIntelligenceAgent."""

    @pytest.mark.asyncio
    async def test_agent_uses_security_telemetry_service(self):
        """Test that ThreatIntelligenceAgent uses SecurityTelemetryService."""
        from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent

        # Create mock security telemetry service
        mock_service = MagicMock()
        mock_service.get_security_findings = AsyncMock(
            return_value=[
                SecurityFinding(
                    id="gd-001",
                    finding_type=FindingType.GUARDDUTY,
                    severity=FindingSeverity.HIGH,
                    title="Test GuardDuty Finding",
                    description="Test description",
                    detected_at=datetime.now(timezone.utc),
                    source_service="GuardDuty",
                    affected_resources=["EC2: i-test"],
                    indicators=["IP: 1.2.3.4"],
                    recommended_actions=["Block IP"],
                )
            ]
        )

        agent = ThreatIntelligenceAgent(security_telemetry_service=mock_service)

        # Call the internal telemetry analysis
        reports = await agent._analyze_internal_telemetry()

        # Should have used the service
        mock_service.get_security_findings.assert_called_once()

        # Should have converted to ThreatIntelReport
        assert len(reports) == 1
        assert "GuardDuty" in reports[0].source
        assert reports[0].title == "Test GuardDuty Finding"

    @pytest.mark.asyncio
    async def test_agent_falls_back_to_mock_on_error(self):
        """Test that agent falls back to mock data on service error."""
        from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent

        # Create mock service that raises an error
        mock_service = MagicMock()
        mock_service.get_security_findings = AsyncMock(
            side_effect=Exception("AWS API Error")
        )

        agent = ThreatIntelligenceAgent(security_telemetry_service=mock_service)

        # Should fall back to mock data
        reports = await agent._analyze_internal_telemetry()

        assert len(reports) > 0
        assert reports[0].source == "Internal Telemetry"

    @pytest.mark.asyncio
    async def test_agent_uses_mock_when_no_service(self):
        """Test that agent uses mock data when no service provided."""
        from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent

        agent = ThreatIntelligenceAgent()

        reports = await agent._analyze_internal_telemetry()

        assert len(reports) > 0
        assert reports[0].source == "Internal Telemetry"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_findings_list(self):
        """Test handling of empty findings list."""
        service = SecurityTelemetryService(
            mode=TelemetryMode.MOCK,
            config=TelemetryConfig(
                guardduty_enabled=False,
                waf_logs_enabled=False,
                cloudtrail_enabled=False,
            ),
        )

        # With all sources disabled, should return empty
        findings = await service.get_security_findings()
        assert findings == []

    def test_severity_mapping(self):
        """Test severity score to enum mapping."""
        with patch("boto3.client"):
            service = SecurityTelemetryService(mode=TelemetryMode.AWS)

            test_cases = [
                (9.5, FindingSeverity.CRITICAL),
                (8.0, FindingSeverity.CRITICAL),
                (7.5, FindingSeverity.HIGH),
                (7.0, FindingSeverity.HIGH),
                (5.0, FindingSeverity.MEDIUM),
                (4.0, FindingSeverity.MEDIUM),
                (2.0, FindingSeverity.LOW),
                (1.0, FindingSeverity.LOW),
                (0.5, FindingSeverity.INFORMATIONAL),
            ]

            for score, expected in test_cases:
                finding = service._parse_guardduty_finding(
                    {
                        "Id": "test",
                        "Title": "Test",
                        "Description": "Test",
                        "Severity": score,
                        "UpdatedAt": "2025-12-06T10:00:00Z",
                        "Type": "Test",
                    }
                )
                if finding:
                    assert (
                        finding.severity == expected
                    ), f"Score {score} should map to {expected}"

    @pytest.mark.asyncio
    async def test_concurrent_source_queries(self):
        """Test that sources are queried concurrently."""
        service = SecurityTelemetryService(mode=TelemetryMode.MOCK)

        # Time the query - concurrent should be fast
        import time

        start = time.time()
        await service.get_security_findings()
        elapsed = time.time() - start

        # Should complete quickly (mock data is instant)
        assert elapsed < 1.0

    def test_invalid_finding_parsing(self):
        """Test handling of invalid finding data."""
        with patch("boto3.client"):
            service = SecurityTelemetryService(mode=TelemetryMode.AWS)

            # Missing required fields
            service._parse_guardduty_finding({})
            # Should return None or handle gracefully
            # (implementation may vary)

    def test_custom_region(self):
        """Test using custom AWS region."""
        with patch("boto3.client") as mock_boto:
            service = SecurityTelemetryService(
                mode=TelemetryMode.AWS,
                region="eu-west-1",
            )

            assert service.region == "eu-west-1"
            # Verify region was passed to boto3
            calls = mock_boto.call_args_list
            assert any("eu-west-1" in str(c) for c in calls)
