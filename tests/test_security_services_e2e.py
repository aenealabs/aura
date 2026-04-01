"""
Project Aura - Security Services End-to-End Integration Tests
==============================================================

This test suite validates REAL AWS service integrations for security services:
- SNS Alert Notifications
- EventBridge Security Event Routing
- CloudWatch Security Metrics
- Security Audit Logging

IMPORTANT: These tests make REAL API calls to AWS services.
They require:
1. AWS credentials with appropriate permissions
2. Environment variable: RUN_AWS_E2E_TESTS=1
3. Deployed security infrastructure (EventBridge, SNS, CloudWatch)

Run with:
    RUN_AWS_E2E_TESTS=1 AWS_PROFILE=aura-admin python3 -m pytest tests/test_security_services_e2e.py -v
"""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3
import pytest

# Environment flag for E2E tests
RUN_E2E = os.environ.get("RUN_AWS_E2E_TESTS", "").lower() in ("1", "true", "yes")
SKIP_REASON = "Set RUN_AWS_E2E_TESTS=1 to run AWS E2E integration tests"

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")


def _get_aws_account_id() -> str:
    """Get AWS account ID dynamically from STS."""
    try:
        sts = boto3.client("sts", region_name=AWS_REGION)
        return sts.get_caller_identity()["Account"]
    except Exception:
        # Fallback to dev account if STS call fails
        return "123456789012"


AWS_ACCOUNT_ID = _get_aws_account_id()

# Resource names
SECURITY_EVENT_BUS = f"{PROJECT_NAME}-security-events-{ENVIRONMENT}"
SECURITY_SNS_TOPIC = f"arn:aws:sns:{AWS_REGION}:{AWS_ACCOUNT_ID}:{PROJECT_NAME}-security-alerts-{ENVIRONMENT}"
SECURITY_LOG_GROUP = f"/aura/{ENVIRONMENT}/security-audit"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def eventbridge_client():
    """Create EventBridge client for E2E tests."""
    if not RUN_E2E:
        pytest.skip(SKIP_REASON)
    return boto3.client("events", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def sns_client():
    """Create SNS client for E2E tests."""
    if not RUN_E2E:
        pytest.skip(SKIP_REASON)
    return boto3.client("sns", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def cloudwatch_client():
    """Create CloudWatch client for E2E tests."""
    if not RUN_E2E:
        pytest.skip(SKIP_REASON)
    return boto3.client("cloudwatch", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def logs_client():
    """Create CloudWatch Logs client for E2E tests."""
    if not RUN_E2E:
        pytest.skip(SKIP_REASON)
    return boto3.client("logs", region_name=AWS_REGION)


# =============================================================================
# EventBridge Security Event Bus Tests
# =============================================================================


@pytest.mark.skipif(not RUN_E2E, reason=SKIP_REASON)
class TestEventBridgeSecurityE2E:
    """E2E tests for EventBridge security event routing."""

    def test_security_event_bus_exists(self, eventbridge_client):
        """Verify security event bus is deployed."""
        response = eventbridge_client.describe_event_bus(Name=SECURITY_EVENT_BUS)

        assert response["Name"] == SECURITY_EVENT_BUS
        assert "Arn" in response
        print(f"✓ Security event bus exists: {response['Arn']}")

    def test_publish_security_event(self, eventbridge_client):
        """Test publishing a security event to the bus."""
        test_event_id = str(uuid.uuid4())

        response = eventbridge_client.put_events(
            Entries=[
                {
                    "Source": "aura.security.e2e-test",
                    "DetailType": "Security Event",
                    "Detail": json.dumps(
                        {
                            "event_id": test_event_id,
                            "event_type": "security.test.e2e",
                            "severity": "LOW",
                            "message": "E2E test security event",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "test": True,
                                "environment": ENVIRONMENT,
                            },
                        }
                    ),
                    "EventBusName": SECURITY_EVENT_BUS,
                }
            ]
        )

        assert response["FailedEntryCount"] == 0
        print(f"✓ Published security event: {test_event_id}")

    def test_publish_critical_security_event(self, eventbridge_client):
        """Test publishing a CRITICAL security event."""
        test_event_id = str(uuid.uuid4())

        response = eventbridge_client.put_events(
            Entries=[
                {
                    "Source": "aura.security.alerts",
                    "DetailType": "Security Alert",
                    "Detail": json.dumps(
                        {
                            "alert_id": test_event_id,
                            "event_type": "security.injection.command",
                            "severity": "CRITICAL",
                            "priority": "P1",
                            "title": "E2E Test: Command Injection Detected",
                            "description": "This is an E2E test alert - ignore",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source_ip": "192.168.1.100",
                            "user_id": "test-user",
                            "remediation_steps": [
                                "Block IP address",
                                "Review logs",
                                "Rotate credentials",
                            ],
                        }
                    ),
                    "EventBusName": SECURITY_EVENT_BUS,
                }
            ]
        )

        assert response["FailedEntryCount"] == 0
        print(f"✓ Published CRITICAL security alert: {test_event_id}")

    def test_list_security_event_rules(self, eventbridge_client):
        """Verify EventBridge rules are configured on security bus."""
        response = eventbridge_client.list_rules(EventBusName=SECURITY_EVENT_BUS)

        rule_names = [r["Name"] for r in response.get("Rules", [])]
        print(f"✓ Found {len(rule_names)} rules on security bus: {rule_names}")

        # We expect at least the alert and audit logging rules
        assert len(rule_names) >= 1, "Expected at least 1 rule on security event bus"


# =============================================================================
# SNS Security Alerts Tests
# =============================================================================


@pytest.mark.skipif(not RUN_E2E, reason=SKIP_REASON)
class TestSNSSecurityAlertsE2E:
    """E2E tests for SNS security alert notifications."""

    def test_sns_topic_exists(self, sns_client):
        """Verify SNS security alerts topic exists."""
        response = sns_client.get_topic_attributes(TopicArn=SECURITY_SNS_TOPIC)

        assert "Attributes" in response
        print(f"✓ SNS topic exists: {SECURITY_SNS_TOPIC}")
        print(
            f"  - Subscriptions: {response['Attributes'].get('SubscriptionsConfirmed', 0)}"
        )

    def test_sns_topic_has_subscriptions(self, sns_client):
        """Verify SNS topic has at least one subscription."""
        # Use list_subscriptions with pagination and filter by topic ARN
        # (more reliable than list_subscriptions_by_topic which can return empty)
        subscriptions = []
        paginator = sns_client.get_paginator("list_subscriptions")
        for page in paginator.paginate():
            for sub in page.get("Subscriptions", []):
                if sub.get("TopicArn") == SECURITY_SNS_TOPIC:
                    subscriptions.append(sub)

        print(f"✓ Found {len(subscriptions)} subscriptions")

        for sub in subscriptions:
            endpoint = sub.get("Endpoint", "N/A")
            print(
                f"  - {sub['Protocol']}: {endpoint[:30] if len(endpoint) > 30 else endpoint}..."
            )

        # In dev/qa, subscriptions may not be configured (AlertEmail parameter optional)
        # Only require subscriptions in production environments
        if ENVIRONMENT in ("dev", "qa"):
            if len(subscriptions) == 0:
                pytest.skip(
                    "No subscriptions configured (optional in dev/qa - AlertEmail not set)"
                )
        else:
            assert (
                len(subscriptions) >= 1
            ), "Expected at least 1 subscription in production"

    def test_publish_test_notification(self, sns_client):
        """Test publishing a notification (won't send if no confirmed subscriptions)."""
        test_message = {
            "alert_type": "E2E_TEST",
            "severity": "LOW",
            "message": "This is an E2E test notification - please ignore",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test": True,
        }

        response = sns_client.publish(
            TopicArn=SECURITY_SNS_TOPIC,
            Subject="[E2E TEST] Security Alert Test",
            Message=json.dumps(test_message),
            MessageAttributes={
                "severity": {"DataType": "String", "StringValue": "LOW"},
                "test": {"DataType": "String", "StringValue": "true"},
            },
        )

        assert "MessageId" in response
        print(f"✓ Published test notification: {response['MessageId']}")


# =============================================================================
# CloudWatch Security Metrics Tests
# =============================================================================


@pytest.mark.skipif(not RUN_E2E, reason=SKIP_REASON)
class TestCloudWatchSecurityMetricsE2E:
    """E2E tests for CloudWatch security metrics."""

    def test_put_security_metric(self, cloudwatch_client):
        """Test publishing a security metric."""
        _response = cloudwatch_client.put_metric_data(
            Namespace="Aura/Security",
            MetricData=[
                {
                    "MetricName": "E2ETestSecurityEvent",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Environment", "Value": ENVIRONMENT},
                        {"Name": "EventType", "Value": "e2e_test"},
                    ],
                }
            ],
        )

        # put_metric_data returns empty dict on success
        print("✓ Published security metric to Aura/Security namespace")

    def test_put_injection_attempt_metric(self, cloudwatch_client):
        """Test publishing injection attempt metric."""
        cloudwatch_client.put_metric_data(
            Namespace="Aura/Security",
            MetricData=[
                {
                    "MetricName": "InjectionAttempt",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Environment", "Value": ENVIRONMENT},
                        {"Name": "InjectionType", "Value": "sql"},
                        {"Name": "Blocked", "Value": "true"},
                    ],
                }
            ],
        )
        print("✓ Published injection attempt metric")

    def test_put_secrets_exposure_metric(self, cloudwatch_client):
        """Test publishing secrets exposure metric."""
        cloudwatch_client.put_metric_data(
            Namespace="Aura/Security",
            MetricData=[
                {
                    "MetricName": "SecretsExposure",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Environment", "Value": ENVIRONMENT},
                        {"Name": "SecretType", "Value": "api_key"},
                        {"Name": "Severity", "Value": "HIGH"},
                    ],
                }
            ],
        )
        print("✓ Published secrets exposure metric")

    def test_list_security_alarms(self, cloudwatch_client):
        """Verify security alarms are configured."""
        # Paginate through all alarms to find security-related ones
        # (security alarms may be beyond the first 50 alphabetically)
        all_alarms = []
        paginator = cloudwatch_client.get_paginator("describe_alarms")
        for page in paginator.paginate(AlarmNamePrefix=f"{PROJECT_NAME}-"):
            all_alarms.extend(page.get("MetricAlarms", []))

        response = {"MetricAlarms": all_alarms}

        alarms = response.get("MetricAlarms", [])
        security_alarms = [
            a
            for a in alarms
            if any(
                x in a["AlarmName"].lower()
                for x in ["security", "injection", "secrets", "prompt", "rate-limit"]
            )
        ]

        print(f"✓ Found {len(security_alarms)} security-related alarms:")
        for alarm in security_alarms:
            print(f"  - {alarm['AlarmName']}: {alarm['StateValue']}")

        assert len(security_alarms) >= 1, "Expected at least 1 security alarm"


# =============================================================================
# CloudWatch Logs Security Tests
# =============================================================================


@pytest.mark.skipif(not RUN_E2E, reason=SKIP_REASON)
class TestCloudWatchLogsSecurityE2E:
    """E2E tests for CloudWatch Logs security audit logging."""

    def test_security_log_group_exists(self, logs_client):
        """Verify security audit log group exists."""
        response = logs_client.describe_log_groups(
            logGroupNamePrefix=f"/aura/{ENVIRONMENT}/security"
        )

        log_groups = response.get("logGroups", [])
        [lg["logGroupName"] for lg in log_groups]

        print(f"✓ Found {len(log_groups)} security log groups:")
        for lg in log_groups:
            retention = lg.get("retentionInDays", "unlimited")
            print(f"  - {lg['logGroupName']} (retention: {retention} days)")

        assert len(log_groups) >= 1, "Expected at least 1 security log group"

    def test_write_security_audit_log(self, logs_client):
        """Test writing a security audit log entry."""
        log_group = SECURITY_LOG_GROUP
        log_stream = f"e2e-test-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

        # Ensure log stream exists
        try:
            logs_client.create_log_stream(
                logGroupName=log_group,
                logStreamName=log_stream,
            )
        except logs_client.exceptions.ResourceAlreadyExistsException:
            pass  # Stream already exists

        # Write test log entry
        test_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "security.e2e.test",
            "severity": "INFO",
            "message": "E2E test security audit log entry",
            "user_id": "e2e-test-user",
            "ip_address": "10.0.0.1",
            "action": "test_audit_logging",
            "result": "success",
        }

        response = logs_client.put_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            logEvents=[
                {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "message": json.dumps(test_event),
                }
            ],
        )

        assert (
            "nextSequenceToken" in response
            or response.get("rejectedLogEventsInfo") is None
        )
        print(f"✓ Wrote security audit log to {log_group}/{log_stream}")


# =============================================================================
# Full Security Pipeline E2E Tests
# =============================================================================


@pytest.mark.skipif(not RUN_E2E, reason=SKIP_REASON)
class TestSecurityPipelineE2E:
    """E2E tests for the full security event pipeline."""

    def test_full_security_event_flow(
        self, eventbridge_client, cloudwatch_client, logs_client
    ):
        """Test complete security event flow: Event → Metrics → Logs."""
        test_id = str(uuid.uuid4())[:8]

        # Step 1: Publish security event to EventBridge
        print(f"\n[1/3] Publishing security event {test_id}...")
        eventbridge_client.put_events(
            Entries=[
                {
                    "Source": "aura.security.e2e-pipeline",
                    "DetailType": "Security Pipeline Test",
                    "Detail": json.dumps(
                        {
                            "test_id": test_id,
                            "event_type": "security.pipeline.test",
                            "severity": "MEDIUM",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    "EventBusName": SECURITY_EVENT_BUS,
                }
            ]
        )
        print("  ✓ Event published")

        # Step 2: Record metric
        print("[2/3] Recording security metric...")
        cloudwatch_client.put_metric_data(
            Namespace="Aura/Security",
            MetricData=[
                {
                    "MetricName": "PipelineTestEvent",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "TestId", "Value": test_id},
                        {"Name": "Environment", "Value": ENVIRONMENT},
                    ],
                }
            ],
        )
        print("  ✓ Metric recorded")

        # Step 3: Write audit log
        print("[3/3] Writing audit log...")
        log_stream = f"e2e-pipeline-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

        try:
            logs_client.create_log_stream(
                logGroupName=SECURITY_LOG_GROUP,
                logStreamName=log_stream,
            )
        except logs_client.exceptions.ResourceAlreadyExistsException:
            pass

        logs_client.put_log_events(
            logGroupName=SECURITY_LOG_GROUP,
            logStreamName=log_stream,
            logEvents=[
                {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "message": json.dumps(
                        {
                            "test_id": test_id,
                            "event_type": "security.pipeline.complete",
                            "message": "E2E pipeline test completed successfully",
                        }
                    ),
                }
            ],
        )
        print("  ✓ Audit log written")

        print(f"\n✓ Full security pipeline test {test_id} completed successfully!")


# =============================================================================
# Summary Tests
# =============================================================================


@pytest.mark.skipif(not RUN_E2E, reason=SKIP_REASON)
def test_security_infrastructure_summary(
    eventbridge_client, sns_client, cloudwatch_client, logs_client
):
    """Print summary of deployed security infrastructure."""
    print("\n" + "=" * 60)
    print("SECURITY INFRASTRUCTURE SUMMARY")
    print("=" * 60)

    # EventBridge
    try:
        eb_response = eventbridge_client.describe_event_bus(Name=SECURITY_EVENT_BUS)
        rules = eventbridge_client.list_rules(EventBusName=SECURITY_EVENT_BUS)
        print(f"\n✓ EventBridge Security Bus: {eb_response['Name']}")
        print(f"  Rules: {len(rules.get('Rules', []))}")
    except Exception as e:
        print(f"\n✗ EventBridge: {e}")

    # SNS
    try:
        _sns_response = sns_client.get_topic_attributes(TopicArn=SECURITY_SNS_TOPIC)
        subs = sns_client.list_subscriptions_by_topic(TopicArn=SECURITY_SNS_TOPIC)
        print(f"\n✓ SNS Security Topic: {SECURITY_SNS_TOPIC.split(':')[-1]}")
        print(f"  Subscriptions: {len(subs.get('Subscriptions', []))}")
    except Exception as e:
        print(f"\n✗ SNS: {e}")

    # CloudWatch Alarms
    try:
        alarms = cloudwatch_client.describe_alarms(AlarmNamePrefix=f"{PROJECT_NAME}-")
        security_alarms = [
            a
            for a in alarms.get("MetricAlarms", [])
            if any(
                x in a["AlarmName"].lower()
                for x in ["security", "injection", "secrets", "prompt"]
            )
        ]
        print(f"\n✓ Security Alarms: {len(security_alarms)}")
        for alarm in security_alarms[:5]:
            print(f"  - {alarm['AlarmName']}: {alarm['StateValue']}")
    except Exception as e:
        print(f"\n✗ CloudWatch Alarms: {e}")

    # CloudWatch Log Groups
    try:
        logs = logs_client.describe_log_groups(
            logGroupNamePrefix=f"/aura/{ENVIRONMENT}/security"
        )
        print(f"\n✓ Security Log Groups: {len(logs.get('logGroups', []))}")
        for lg in logs.get("logGroups", []):
            print(f"  - {lg['logGroupName']}")
    except Exception as e:
        print(f"\n✗ CloudWatch Logs: {e}")

    print("\n" + "=" * 60)
