"""
Pytest fixtures for supply chain security tests.

Provides common fixtures for testing SBOM attestation, dependency confusion
detection, and license compliance services.
"""

from datetime import datetime, timezone

import pytest

from src.services.supply_chain import (
    LicenseCategory,
    LicensePolicy,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    SupplyChainConfig,
    reset_dependency_confusion_detector,
    reset_license_compliance_engine,
    reset_sbom_attestation_service,
    reset_supply_chain_config,
    reset_supply_chain_graph_service,
    reset_supply_chain_metrics,
    set_supply_chain_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton instances before and after each test."""
    # Reset before test
    reset_supply_chain_config()
    reset_supply_chain_metrics()
    reset_sbom_attestation_service()
    reset_dependency_confusion_detector()
    reset_license_compliance_engine()
    reset_supply_chain_graph_service()

    yield

    # Reset after test
    reset_supply_chain_config()
    reset_supply_chain_metrics()
    reset_sbom_attestation_service()
    reset_dependency_confusion_detector()
    reset_license_compliance_engine()
    reset_supply_chain_graph_service()


@pytest.fixture
def test_config() -> SupplyChainConfig:
    """Create a test configuration with mock storage."""
    config = SupplyChainConfig.for_testing()
    set_supply_chain_config(config)
    return config


@pytest.fixture
def sample_components() -> list[SBOMComponent]:
    """Create sample SBOM components for testing."""
    return [
        SBOMComponent(
            name="requests",
            version="2.31.0",
            purl="pkg:pypi/requests@2.31.0",
            component_type="library",
            supplier="Kenneth Reitz",
            licenses=["Apache-2.0"],
            hashes={"sha256": "abc123def456"},
            is_direct=True,
        ),
        SBOMComponent(
            name="urllib3",
            version="2.0.7",
            purl="pkg:pypi/urllib3@2.0.7",
            component_type="library",
            licenses=["MIT"],
            is_direct=False,
        ),
        SBOMComponent(
            name="certifi",
            version="2023.11.17",
            purl="pkg:pypi/certifi@2023.11.17",
            component_type="library",
            licenses=["MPL-2.0"],
            is_direct=False,
        ),
        SBOMComponent(
            name="charset-normalizer",
            version="3.3.2",
            purl="pkg:pypi/charset-normalizer@3.3.2",
            component_type="library",
            licenses=["MIT"],
            is_direct=False,
        ),
        SBOMComponent(
            name="idna",
            version="3.6",
            purl="pkg:pypi/idna@3.6",
            component_type="library",
            licenses=["BSD-3-Clause"],
            is_direct=False,
        ),
    ]


@pytest.fixture
def sample_sbom(sample_components: list[SBOMComponent]) -> SBOMDocument:
    """Create a sample SBOM document for testing."""
    return SBOMDocument(
        sbom_id="sbom-test-12345",
        name="test-project",
        version="1.0.0",
        format=SBOMFormat.CYCLONEDX_1_5_JSON,
        spec_version="1.5",
        repository_id="repo-test-001",
        created_at=datetime.now(timezone.utc),
        components=sample_components,
        hash_value="sha256:abc123def456789",
    )


@pytest.fixture
def small_sbom() -> SBOMDocument:
    """Create a small SBOM for simple tests."""
    return SBOMDocument(
        sbom_id="sbom-small-001",
        name="small-project",
        version="0.1.0",
        format=SBOMFormat.INTERNAL,
        spec_version="1.0",
        repository_id="repo-small",
        created_at=datetime.now(timezone.utc),
        components=[
            SBOMComponent(
                name="flask",
                version="3.0.0",
                purl="pkg:pypi/flask@3.0.0",
                component_type="library",
                licenses=["BSD-3-Clause"],
                is_direct=True,
            ),
        ],
    )


@pytest.fixture
def permissive_policy() -> LicensePolicy:
    """Create a permissive license policy."""
    return LicensePolicy(
        name="permissive-only",
        allowed_categories=[
            LicenseCategory.PERMISSIVE,
            LicenseCategory.PUBLIC_DOMAIN,
        ],
        prohibited_licenses=[
            "GPL-3.0-only",
            "AGPL-3.0-only",
        ],
        require_osi_approved=False,
        allow_unknown=False,
    )


@pytest.fixture
def strict_policy() -> LicensePolicy:
    """Create a strict license policy."""
    return LicensePolicy(
        name="strict-enterprise",
        allowed_categories=[
            LicenseCategory.PERMISSIVE,
            LicenseCategory.PUBLIC_DOMAIN,
        ],
        prohibited_licenses=[
            "GPL-2.0-only",
            "GPL-2.0-or-later",
            "GPL-3.0-only",
            "GPL-3.0-or-later",
            "AGPL-3.0-only",
            "AGPL-3.0-or-later",
            "LGPL-2.1-only",
            "LGPL-3.0-only",
        ],
        require_osi_approved=True,
        allow_unknown=False,
    )


@pytest.fixture
def internal_namespaces() -> list[str]:
    """List of internal namespace prefixes for testing."""
    return [
        "aura-",
        "internal-",
        "@aenea/",
        "mycompany-",
    ]


@pytest.fixture
def typosquatting_packages() -> list[tuple[str, str]]:
    """Packages that look like typosquatting attempts."""
    return [
        ("requets", "pypi"),  # typo of 'requests'
        ("reqeusts", "pypi"),  # typo of 'requests'
        ("lodashs", "npm"),  # typo of 'lodash'
        ("reacts", "npm"),  # typo of 'react'
        ("flaks", "pypi"),  # typo of 'flask'
    ]


@pytest.fixture
def legitimate_packages() -> list[tuple[str, str]]:
    """Legitimate packages that shouldn't trigger false positives."""
    return [
        ("requests", "pypi"),
        ("flask", "pypi"),
        ("django", "pypi"),
        ("lodash", "npm"),
        ("react", "npm"),
        ("express", "npm"),
    ]
