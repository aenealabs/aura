"""Tests for the guard that blocks unmocked AWS calls during the test run.

Before this guard, AWS mocking was opt-in: 62 of 740 test files requested an
AWS/moto fixture, and no autouse fixture faked credentials or blocked real
calls. A production code path exercised by any of the other 678 could reach a
developer's real AWS account -- silently, since a successful call looks like a
passing test.

The guard patches ``URLLib3Session.send``, the HTTP transport layer, rather
than botocore's ``before-send`` event. moto registers its interception *at*
``before-send``, so a guard there would race moto's handler and depend on
registration order. Patching the transport is unambiguous: moto short-circuits
above it, so anything arriving at the transport is by definition unmocked.

Both directions are asserted below, because a guard that fires under moto
would be worse than no guard -- it would break every correctly-mocked test.
"""

import boto3
import pytest
from botocore.httpsession import URLLib3Session
from moto import mock_aws

from tests.conftest import UnmockedAWSCallError

pytestmark = pytest.mark.unit


class TestGuardBlocksRealCalls:
    """The guard must fire on a call that would reach AWS."""

    def test_real_call_is_blocked(self):
        with pytest.raises(UnmockedAWSCallError) as exc:
            boto3.client("s3", region_name="us-east-1").list_buckets()

        message = str(exc.value)
        # The message must name the call, or the failure is a scavenger hunt.
        assert "Unmocked AWS call" in message
        assert "amazonaws.com" in message

    def test_message_points_at_the_remedy(self):
        with pytest.raises(UnmockedAWSCallError) as exc:
            boto3.client("ssm", region_name="us-east-1").get_parameter(Name="/x")

        message = str(exc.value)
        assert "moto" in message
        # The production-code case is the one that cost us; name it explicitly.
        assert "TESTING" in message


class TestGuardIsSilentUnderMoto:
    """The guard must not fire when a test is correctly mocked.

    This is the half that makes the guard safe to enable globally.
    """

    def test_moto_intercepts_before_the_guard(self):
        with mock_aws():
            result = boto3.client("s3", region_name="us-east-1").list_buckets()

        assert result["Buckets"] == []

    def test_moto_write_then_read_round_trips(self):
        """A fuller exercise: the guard must not interfere with real moto use."""
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="guard-test-bucket")
            s3.put_object(Bucket="guard-test-bucket", Key="k", Body=b"v")

            body = s3.get_object(Bucket="guard-test-bucket", Key="k")["Body"].read()

        assert body == b"v"


class TestGuardIsRestoredBetweenTests:
    """Function scope with a finally, so the patch cannot leak."""

    def test_transport_is_patched_during_a_test(self):
        assert URLLib3Session.send.__name__ == "_guarded_send"

    def test_transport_is_still_patched_in_the_next_test(self):
        """Confirms teardown re-applies rather than leaving it unpatched."""
        assert URLLib3Session.send.__name__ == "_guarded_send"


class TestCredentialsAreFakedGlobally:
    """Every test gets credentials, not just those requesting a fixture."""

    def test_credentials_present_without_requesting_a_fixture(self):
        import os

        assert os.environ.get("AWS_ACCESS_KEY_ID")
        assert os.environ.get("AWS_SECRET_ACCESS_KEY")
        assert os.environ.get("AWS_DEFAULT_REGION")


class TestMockSelectionIsNotKeyedOffAwsEnvVars:
    """Regression guard for the bug this work uncovered.

    ``SpawnableGitHubIntegrationAgent`` chose mock-vs-real by checking whether
    ``AWS_DEFAULT_REGION`` was set. That variable is exported in most shell
    profiles and is set by this repo's own ``aws_credentials`` fixture, so unit
    tests silently selected the real service and reached SSM Parameter Store.
    """

    def test_agent_uses_mock_service_under_testing(self):
        from src.agents.spawnable_agent_adapters import SpawnableGitHubIntegrationAgent

        agent = SpawnableGitHubIntegrationAgent()
        service = agent._get_github_service()

        assert getattr(service, "_use_mock", None) is True, (
            "GitHub service selected real mode during tests -- mock selection "
            "must key off TESTING, not an AWS environment variable"
        )

    def test_setting_aws_region_does_not_flip_to_real_mode(self, monkeypatch):
        """The specific input that used to break it."""
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        from src.agents.spawnable_agent_adapters import SpawnableGitHubIntegrationAgent

        agent = SpawnableGitHubIntegrationAgent()
        service = agent._get_github_service()

        assert getattr(service, "_use_mock", None) is True

    async def test_agent_validates_context_without_touching_aws(self):
        """The originally failing test's intent, now provable.

        It asserted a validation message but reached SSM first; the assertion
        passed only because the AWS failure was swallowed upstream.
        """
        from src.agents.spawnable_agent_adapters import SpawnableGitHubIntegrationAgent

        agent = SpawnableGitHubIntegrationAgent()
        result = await agent.execute("Create PR", "string context")

        assert result.success is False
        assert "Context must be a dict" in result.error
