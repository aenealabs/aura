"""Tests for FIPS endpoint validator (ADR-088 Phase 3.5)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.govcloud import (
    EndpointSetValidation,
    Partition,
    PartitionEnforcement,
    is_fips_endpoint,
    validate_endpoint_set,
)


class TestFIPSDetection:
    @pytest.mark.parametrize(
        "host",
        [
            "bedrock-fips.us-east-1.amazonaws.com",
            "ec2.us-gov-west-1.amazonaws.com",
            "bedrock.us-gov-west-1.amazonaws.com",
            "BEDROCK-FIPS.US-EAST-1.AMAZONAWS.COM",  # case-insensitive
            "fips.aws.example.com",
        ],
    )
    def test_fips_endpoints_accepted(self, host: str) -> None:
        assert is_fips_endpoint(host) is True

    @pytest.mark.parametrize(
        "host",
        [
            "bedrock.us-east-1.amazonaws.com",
            "evil.com",
            "bedrock-runtime.eu-central-1.amazonaws.com",
        ],
    )
    def test_non_fips_rejected(self, host: str) -> None:
        assert is_fips_endpoint(host) is False


class TestEndpointSetValidation:
    def test_all_fips_set(self) -> None:
        validation = validate_endpoint_set((
            "bedrock-fips.us-east-1.amazonaws.com",
            "bedrock.us-gov-west-1.amazonaws.com",
        ))
        assert validation.all_fips is True
        assert validation.non_fips == ()

    def test_mixed_set(self) -> None:
        validation = validate_endpoint_set((
            "bedrock-fips.us-east-1.amazonaws.com",
            "evil.com",
        ))
        assert validation.all_fips is False
        non_fips_hosts = {e.host for e in validation.non_fips}
        assert "evil.com" in non_fips_hosts

    def test_empty_set_passes(self) -> None:
        validation = validate_endpoint_set(())
        assert validation.all_fips is True


class TestPartitionEnforcement:
    def test_govcloud_default_requires_fips_and_hitl(self) -> None:
        e = PartitionEnforcement(partition=Partition.AWS_US_GOV)
        assert e.require_fips is True
        assert e.require_hitl_for_model_swap is True

    def test_assert_endpoints_acceptable_returns_validation(self) -> None:
        e = PartitionEnforcement(partition=Partition.AWS_US_GOV)
        validation = e.assert_endpoints_acceptable((
            "bedrock-fips.us-east-1.amazonaws.com",
        ))
        assert isinstance(validation, EndpointSetValidation)
        assert validation.all_fips is True

    def test_commercial_can_disable_fips_requirement(self) -> None:
        """Commercial deployments can opt out via require_fips=False."""
        e = PartitionEnforcement(
            partition=Partition.AWS, require_fips=False,
        )
        # Validator still produces the report, but caller decides.
        validation = e.assert_endpoints_acceptable((
            "bedrock.us-east-1.amazonaws.com",
        ))
        assert validation.all_fips is False  # truthful report
