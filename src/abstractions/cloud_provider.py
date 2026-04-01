"""
Project Aura - Cloud Provider Abstraction

Defines cloud provider types and regions for multi-cloud deployment.
Supports AWS GovCloud and Azure Government as primary targets.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CloudProvider(Enum):
    """Supported cloud providers for Project Aura deployment."""

    AWS = "aws"
    AWS_GOVCLOUD = "aws_govcloud"
    AZURE = "azure"
    AZURE_GOVERNMENT = "azure_government"
    MOCK = "mock"  # For testing and local development
    SELF_HOSTED = (
        "self_hosted"  # ADR-049: Self-hosted deployment (Neo4j, PostgreSQL, vLLM)
    )

    @property
    def is_govcloud(self) -> bool:
        """Check if this is a government cloud region."""
        return self in (CloudProvider.AWS_GOVCLOUD, CloudProvider.AZURE_GOVERNMENT)

    @property
    def is_self_hosted(self) -> bool:
        """Check if this is a self-hosted deployment (ADR-049)."""
        return self == CloudProvider.SELF_HOSTED

    @property
    def partition(self) -> str:
        """Get the AWS partition or Azure environment identifier."""
        if self == CloudProvider.AWS_GOVCLOUD:
            return "aws-us-gov"
        elif self in (CloudProvider.AWS, CloudProvider.MOCK):
            return "aws"
        elif self == CloudProvider.AZURE_GOVERNMENT:
            return "usgovernment"
        elif self == CloudProvider.AZURE:
            return "public"
        elif self == CloudProvider.SELF_HOSTED:
            return "self_hosted"
        return "unknown"


@dataclass
class CloudRegion:
    """Cloud region configuration."""

    provider: CloudProvider
    region_code: str  # e.g., "us-gov-west-1" or "usgovvirginia"
    display_name: str

    @property
    def is_govcloud(self) -> bool:
        """Check if this region is in a government cloud."""
        return self.provider.is_govcloud


# Pre-defined regions for government clouds
AWS_GOVCLOUD_REGIONS = {
    "us-gov-west-1": CloudRegion(
        provider=CloudProvider.AWS_GOVCLOUD,
        region_code="us-gov-west-1",
        display_name="AWS GovCloud (US-West)",
    ),
    "us-gov-east-1": CloudRegion(
        provider=CloudProvider.AWS_GOVCLOUD,
        region_code="us-gov-east-1",
        display_name="AWS GovCloud (US-East)",
    ),
}

AZURE_GOVERNMENT_REGIONS = {
    "usgovvirginia": CloudRegion(
        provider=CloudProvider.AZURE_GOVERNMENT,
        region_code="usgovvirginia",
        display_name="Azure Government Virginia",
    ),
    "usgovarizona": CloudRegion(
        provider=CloudProvider.AZURE_GOVERNMENT,
        region_code="usgovarizona",
        display_name="Azure Government Arizona",
    ),
    "usgovtexas": CloudRegion(
        provider=CloudProvider.AZURE_GOVERNMENT,
        region_code="usgovtexas",
        display_name="Azure Government Texas",
    ),
}


class CloudConfig:
    """Configuration for cloud provider services."""

    def __init__(
        self,
        provider: CloudProvider,
        region: str,
        credentials: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ):
        self.provider = provider
        self.region = region
        self.credentials = credentials or {}
        self.options = options or {}

    @classmethod
    def from_environment(cls) -> "CloudConfig":
        """Create cloud config from environment variables."""
        import os

        provider_str = os.environ.get("CLOUD_PROVIDER", "aws").lower()
        region = os.environ.get(
            "CLOUD_REGION", os.environ.get("AWS_REGION", "us-east-1")
        )

        provider_map = {
            "aws": CloudProvider.AWS,
            "aws_govcloud": CloudProvider.AWS_GOVCLOUD,
            "azure": CloudProvider.AZURE,
            "azure_government": CloudProvider.AZURE_GOVERNMENT,
            "mock": CloudProvider.MOCK,
            "self_hosted": CloudProvider.SELF_HOSTED,
        }

        provider = provider_map.get(provider_str, CloudProvider.AWS)

        return cls(provider=provider, region=region)

    def get_service_endpoint(self, service: str) -> str | None:
        """Get the endpoint URL for a specific service."""
        endpoints: dict[str, str] = self.options.get("endpoints", {})
        return endpoints.get(service)
