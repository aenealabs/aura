"""Tests for the sandbox egress policy (ADR-088 Phase 2.4)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.sandbox import (
    DEFAULT_EGRESS_ALLOWLIST,
    EgressDecision,
    EgressPolicy,
    SandboxSpec,
    validate_egress_endpoints,
)


def _spec(region: str = "us-east-1") -> SandboxSpec:
    return SandboxSpec(
        sandbox_id="sb-1",
        candidate_model_id="m1",
        egress_policy=EgressPolicy(region=region),
    )


class TestDefaultAllowlist:
    def test_two_default_endpoints(self) -> None:
        assert len(DEFAULT_EGRESS_ALLOWLIST) == 2

    def test_default_endpoints_are_bedrock(self) -> None:
        for ep in DEFAULT_EGRESS_ALLOWLIST:
            assert "bedrock" in ep.host.lower()


class TestRegionTemplating:
    @pytest.mark.parametrize(
        "region",
        ["us-east-1", "us-west-2", "us-gov-west-1", "eu-central-1"],
    )
    def test_bedrock_runtime_for_region_allowed(self, region: str) -> None:
        policy = EgressPolicy(region=region)
        host = f"bedrock-runtime.{region}.amazonaws.com"
        assert policy.validate_destination(host, 443) is EgressDecision.ALLOW

    def test_bedrock_for_wrong_region_denied(self) -> None:
        policy = EgressPolicy(region="us-east-1")
        # Region in URL doesn't match policy region
        assert policy.validate_destination(
            "bedrock-runtime.eu-central-1.amazonaws.com", 443,
        ) in (EgressDecision.DENY, EgressDecision.SUSPICIOUS)


class TestEndpointValidation:
    def test_unknown_destination_denied(self) -> None:
        policy = EgressPolicy(region="us-east-1")
        assert policy.validate_destination("evil.com", 443) is EgressDecision.DENY

    def test_aws_namespace_but_wrong_service_suspicious(self) -> None:
        policy = EgressPolicy(region="us-east-1")
        assert (
            policy.validate_destination("s3.us-east-1.amazonaws.com", 443)
            is EgressDecision.SUSPICIOUS
        )

    def test_wrong_port_denied(self) -> None:
        policy = EgressPolicy(region="us-east-1")
        # Bedrock is HTTPS only
        assert (
            policy.validate_destination(
                "bedrock-runtime.us-east-1.amazonaws.com", 80,
            )
            is EgressDecision.SUSPICIOUS
        )

    def test_case_insensitive_match(self) -> None:
        policy = EgressPolicy(region="us-east-1")
        assert (
            policy.validate_destination(
                "BEDROCK-RUNTIME.US-EAST-1.AMAZONAWS.COM", 443,
            )
            is EgressDecision.ALLOW
        )


class TestPreFlightCheck:
    def test_all_allowed(self) -> None:
        denied = validate_egress_endpoints(
            _spec(),
            [
                ("bedrock-runtime.us-east-1.amazonaws.com", 443),
                ("bedrock.us-east-1.amazonaws.com", 443),
            ],
        )
        assert denied == ()

    def test_partial_denial_returns_just_the_denied(self) -> None:
        denied = validate_egress_endpoints(
            _spec(),
            [
                ("bedrock-runtime.us-east-1.amazonaws.com", 443),
                ("evil.com", 443),
                ("attacker-controlled.example.com", 80),
            ],
        )
        assert "evil.com:443" in denied
        assert "attacker-controlled.example.com:80" in denied
        assert len(denied) == 2

    def test_empty_destinations_pass(self) -> None:
        denied = validate_egress_endpoints(_spec(), [])
        assert denied == ()


class TestImmutability:
    def test_with_region_returns_new_policy(self) -> None:
        original = EgressPolicy(region="us-east-1")
        new = original.with_region("us-gov-west-1")
        assert original.region == "us-east-1"
        assert new.region == "us-gov-west-1"

    def test_egress_policy_is_frozen(self) -> None:
        policy = EgressPolicy()
        with pytest.raises((AttributeError, TypeError)):
            policy.region = "x"  # type: ignore[misc]
