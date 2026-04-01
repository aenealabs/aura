"""
Tests for runtime-to-code correlator service.
"""

from src.services.runtime_security import (
    CorrelationStatus,
    EventType,
    RuntimeCorrelator,
    Severity,
    get_runtime_correlator,
    reset_runtime_correlator,
)


class TestRuntimeCorrelatorInitialization:
    """Tests for runtime correlator initialization."""

    def test_initialize_correlator(self, test_config):
        """Test initializing correlator."""
        correlator = RuntimeCorrelator()
        assert correlator is not None

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        correlator1 = get_runtime_correlator()
        correlator2 = get_runtime_correlator()
        assert correlator1 is correlator2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        correlator1 = get_runtime_correlator()
        reset_runtime_correlator()
        correlator2 = get_runtime_correlator()
        assert correlator1 is not correlator2


class TestCloudTrailIngestion:
    """Tests for CloudTrail event ingestion."""

    def test_ingest_cloudtrail_event(self, test_config, sample_cloudtrail_event):
        """Test ingesting a CloudTrail event."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        assert event is not None
        assert event.event_type == EventType.CLOUDTRAIL
        assert event.event_id.startswith("ct-")
        assert event.aws_account_id == "123456789012"

    def test_cloudtrail_event_description(self, test_config, sample_cloudtrail_event):
        """Test CloudTrail event description parsing."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        assert "RunInstances" in event.description
        assert (
            "developer" in event.description.lower()
            or "role" in event.description.lower()
        )

    def test_cloudtrail_resource_extraction(self, test_config, sample_cloudtrail_event):
        """Test resource ARN extraction from CloudTrail."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        # Should extract instance ID from response
        assert event.resource_arn is not None
        assert "i-" in event.resource_arn

    def test_cloudtrail_severity_classification(self, test_config):
        """Test severity classification for CloudTrail events."""
        correlator = RuntimeCorrelator()

        # High-risk event
        critical_event = {
            "eventID": "critical-123",
            "eventName": "DeleteBucket",
            "eventSource": "s3.amazonaws.com",
            "eventTime": "2026-01-15T10:30:00Z",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "userIdentity": {"arn": "arn:aws:iam::123456789012:user/admin"},
        }
        event = correlator.ingest_cloudtrail_event(critical_event)
        assert event.severity == Severity.CRITICAL

        # Normal event
        normal_event = {
            "eventID": "normal-456",
            "eventName": "DescribeInstances",
            "eventSource": "ec2.amazonaws.com",
            "eventTime": "2026-01-15T10:30:00Z",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "userIdentity": {"arn": "arn:aws:iam::123456789012:user/reader"},
        }
        event = correlator.ingest_cloudtrail_event(normal_event)
        assert event.severity == Severity.LOW


class TestGuardDutyIngestion:
    """Tests for GuardDuty finding ingestion."""

    def test_ingest_guardduty_finding(self, test_config, sample_guardduty_finding):
        """Test ingesting a GuardDuty finding."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_guardduty_finding(sample_guardduty_finding)

        assert event is not None
        assert event.event_type == EventType.GUARDDUTY
        assert event.event_id.startswith("gd-")
        assert event.severity == Severity.CRITICAL  # Severity 8 = CRITICAL

    def test_guardduty_severity_mapping(self, test_config):
        """Test GuardDuty severity to our severity mapping."""
        correlator = RuntimeCorrelator()

        # Test different severity levels
        test_cases = [
            (9, Severity.CRITICAL),
            (7, Severity.HIGH),
            (5, Severity.MEDIUM),
            (2, Severity.LOW),
        ]

        for gd_severity, expected_severity in test_cases:
            finding = {
                "Id": f"finding-{gd_severity}",
                "Type": "Test",
                "Severity": gd_severity,
                "AccountId": "123456789012",
                "Region": "us-east-1",
                "CreatedAt": "2026-01-15T11:00:00Z",
            }
            event = correlator.ingest_guardduty_finding(finding)
            assert event.severity == expected_severity


class TestVPCFlowLogIngestion:
    """Tests for VPC Flow Log ingestion."""

    def test_ingest_vpc_flow_log(self, test_config, sample_vpc_flow_log):
        """Test ingesting a VPC Flow Log record."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_vpc_flow_log(sample_vpc_flow_log)

        assert event is not None
        assert event.event_type == EventType.VPC_FLOW
        assert event.event_id.startswith("vf-")
        assert "10.0.1.100" in event.description

    def test_vpc_flow_reject_severity(self, test_config):
        """Test that REJECT flows have higher severity."""
        correlator = RuntimeCorrelator()

        accept_log = {
            "account-id": "123456789012",
            "interface-id": "eni-12345",
            "srcaddr": "10.0.1.1",
            "dstaddr": "10.0.1.2",
            "srcport": 443,
            "dstport": 80,
            "protocol": "6",
            "action": "ACCEPT",
            "region": "us-east-1",
        }
        accept_event = correlator.ingest_vpc_flow_log(accept_log)
        assert accept_event.severity == Severity.LOW

        reject_log = {**accept_log, "action": "REJECT"}
        reject_event = correlator.ingest_vpc_flow_log(reject_log)
        assert reject_event.severity == Severity.MEDIUM


class TestEventCorrelation:
    """Tests for event-to-code correlation."""

    def test_correlate_event(self, test_config, sample_cloudtrail_event):
        """Test correlating an event to code."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        result = correlator.correlate(event)

        assert result is not None
        assert result.event_id == event.event_id
        # In mock mode, correlation should succeed
        assert result.status in (
            CorrelationStatus.CORRELATED,
            CorrelationStatus.PARTIAL,
        )

    def test_correlation_chain(self, test_config, sample_cloudtrail_event):
        """Test correlation chain is populated."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        result = correlator.correlate(event)

        assert len(result.correlation_chain) > 0
        # Chain should include AWS resource info
        assert any(
            "AWS Resource" in step or "IaC" in step for step in result.correlation_chain
        )

    def test_correlation_confidence(self, test_config, sample_cloudtrail_event):
        """Test correlation confidence is set."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        result = correlator.correlate(event)

        assert result.confidence >= 0
        assert result.confidence <= 1


class TestResourceMapping:
    """Tests for resource mapping functionality."""

    def test_register_terraform_state(self, test_config):
        """Test registering Terraform state."""
        correlator = RuntimeCorrelator()

        state_data = {
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web_server",
                    "instances": [
                        {
                            "attributes": {
                                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
                                "id": "i-12345",
                            }
                        }
                    ],
                }
            ]
        }

        count = correlator.register_terraform_state(state_data)
        assert count == 1

    def test_register_cloudformation_resources(self, test_config):
        """Test registering CloudFormation resources."""
        correlator = RuntimeCorrelator()

        resources = {
            "WebServerInstance": "i-12345678",
            "DatabaseInstance": "i-87654321",
        }

        count = correlator.register_cloudformation_resources(
            "deploy/cloudformation/ec2.yaml", resources
        )
        assert count == 2

    def test_add_resource_mapping(self, test_config, sample_resource_mapping):
        """Test adding manual resource mapping."""
        correlator = RuntimeCorrelator()
        correlator.add_resource_mapping(sample_resource_mapping)

        # Verify mapping is used in correlation
        event = correlator.ingest_cloudtrail_event(
            {
                "eventID": "map-test",
                "eventName": "DescribeInstance",
                "eventSource": "ec2.amazonaws.com",
                "eventTime": "2026-01-15T10:30:00Z",
                "awsRegion": "us-east-1",
                "recipientAccountId": "123456789012",
                "userIdentity": {"arn": "test"},
                "resources": [{"ARN": sample_resource_mapping.aws_resource_arn}],
            }
        )

        result = correlator.correlate(event)
        # Should use the registered mapping
        assert result.status in (
            CorrelationStatus.CORRELATED,
            CorrelationStatus.PARTIAL,
        )


class TestEventRetrieval:
    """Tests for event retrieval."""

    def test_get_event(self, test_config, sample_cloudtrail_event):
        """Test getting an event by ID."""
        correlator = RuntimeCorrelator()
        event = correlator.ingest_cloudtrail_event(sample_cloudtrail_event)

        retrieved = correlator.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id

    def test_get_nonexistent_event(self, test_config):
        """Test getting non-existent event."""
        correlator = RuntimeCorrelator()
        retrieved = correlator.get_event("nonexistent-id")
        assert retrieved is None


class TestAWSResourceParsing:
    """Tests for AWS resource ARN parsing."""

    def test_parse_ec2_arn(self, test_config):
        """Test parsing EC2 instance ARN."""
        correlator = RuntimeCorrelator()
        arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-12345678"

        resource = correlator._get_aws_resource(arn)
        assert resource is not None
        assert resource.region == "us-east-1"
        assert resource.aws_account_id == "123456789012"

    def test_parse_instance_id(self, test_config):
        """Test parsing bare instance ID."""
        correlator = RuntimeCorrelator()

        resource = correlator._get_aws_resource("i-12345678")
        assert resource is not None
        assert "i-12345678" in resource.name


class TestSeverityClassification:
    """Tests for CloudTrail event severity classification."""

    def test_high_risk_events(self, test_config):
        """Test high-risk event classification."""
        correlator = RuntimeCorrelator()

        high_risk_events = [
            "DeleteBucket",
            "DeleteCluster",
            "CreateAccessKey",
        ]

        for event_name in high_risk_events:
            severity = correlator._classify_cloudtrail_severity(event_name, {})
            assert severity in (Severity.CRITICAL, Severity.HIGH)

    def test_normal_events(self, test_config):
        """Test normal event classification."""
        correlator = RuntimeCorrelator()

        normal_events = [
            "DescribeInstances",
            "ListBuckets",
            "GetObject",
        ]

        for event_name in normal_events:
            severity = correlator._classify_cloudtrail_severity(event_name, {})
            assert severity == Severity.LOW

    def test_access_denied_events(self, test_config):
        """Test access denied event classification."""
        correlator = RuntimeCorrelator()

        severity = correlator._classify_cloudtrail_severity(
            "DescribeInstances", {"errorCode": "AccessDenied"}
        )
        assert severity == Severity.MEDIUM
