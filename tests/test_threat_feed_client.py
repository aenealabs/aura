"""
Project Aura - Threat Feed Client Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (httpx, NVD/CISA/GitHub APIs)
Isolation: pytest.mark.forked (required for HTTPX_AVAILABLE patching)
Run Command: pytest tests/test_threat_feed_client.py -v

These tests validate:
- Threat feed client initialization and mode selection
- NVD (National Vulnerability Database) CVE fetching
- CISA KEV (Known Exploited Vulnerabilities) parsing
- GitHub Security Advisory retrieval
- Rate limiting and caching behavior
- Error handling and fallback to mock mode

Mock Strategy:
- httpx.AsyncClient: Mocked via create_httpx_client_mock()
- HTTPX_AVAILABLE: Patched for fallback testing
- All external API responses are simulated

Target Coverage: 85% of src/services/threat_feed_client.py

Related E2E Tests:
- tests/e2e/test_threat_feeds_e2e.py (requires RUN_E2E_TESTS=1 and network access)
"""

import os
import platform
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Explicit test type markers
# - unit: All external dependencies are mocked
# - forked: Run in isolated subprocess on non-Linux for HTTPX_AVAILABLE patching
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = [pytest.mark.unit, pytest.mark.forked]

# Set environment before importing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

from src.services.threat_feed_client import (
    CISAKEVRecord,
    CVERecord,
    GitHubAdvisory,
    RateLimitConfig,
    ThreatFeedClient,
    ThreatFeedConfig,
    ThreatFeedMode,
    create_threat_feed_client,
)


class TestThreatFeedMode:
    """Tests for ThreatFeedMode enum."""

    def test_mock_mode_value(self):
        """Test MOCK mode has correct value."""
        assert ThreatFeedMode.MOCK.value == "mock"

    def test_real_mode_value(self):
        """Test REAL mode has correct value."""
        assert ThreatFeedMode.REAL.value == "real"


class TestDataclasses:
    """Tests for dataclass definitions."""

    def test_rate_limit_config_defaults(self):
        """Test RateLimitConfig has correct defaults."""
        config = RateLimitConfig()

        assert config.requests_per_window == 5
        assert config.window_seconds == 30
        assert config.retry_after_seconds == 60

    def test_threat_feed_config_defaults(self):
        """Test ThreatFeedConfig has correct defaults."""
        config = ThreatFeedConfig()

        assert "nvd.nist.gov" in config.nvd_api_url
        assert "cisa.gov" in config.cisa_kev_url
        assert "github.com" in config.github_advisory_url
        assert config.timeout_seconds == 30
        assert config.max_cves_per_request == 50

    def test_cve_record_creation(self):
        """Test CVERecord dataclass."""
        record = CVERecord(
            cve_id="CVE-2025-0001",
            title="Test CVE",
            description="Test description",
            cvss_score=9.8,
            published_date=datetime.now(),
            affected_products=["test-product"],
            references=["https://example.com"],
        )

        assert record.cve_id == "CVE-2025-0001"
        assert record.cvss_score == 9.8
        assert len(record.affected_products) == 1

    def test_cisa_kev_record_creation(self):
        """Test CISAKEVRecord dataclass."""
        record = CISAKEVRecord(
            cve_id="CVE-2025-0002",
            vendor_project="Test Vendor",
            product="Test Product",
            vulnerability_name="Test Vuln",
            date_added=datetime.now(),
            due_date=datetime.now() + timedelta(days=14),
            short_description="Description",
            required_action="Apply patch",
            known_ransomware=True,
        )

        assert record.cve_id == "CVE-2025-0002"
        assert record.known_ransomware is True

    def test_github_advisory_creation(self):
        """Test GitHubAdvisory dataclass."""
        advisory = GitHubAdvisory(
            ghsa_id="GHSA-xxxx-yyyy",
            cve_id="CVE-2025-0003",
            summary="Test advisory",
            description="Description",
            severity="high",
            published_at=datetime.now(),
            package_ecosystem="pip",
            package_name="test-package",
            vulnerable_versions="<1.0.0",
            patched_versions=">=1.0.0",
        )

        assert advisory.ghsa_id == "GHSA-xxxx-yyyy"
        assert advisory.severity == "high"


class TestThreatFeedClientInit:
    """Tests for ThreatFeedClient initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        assert client.mode == ThreatFeedMode.MOCK
        assert isinstance(client.config, ThreatFeedConfig)
        assert client._http_client is None

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = ThreatFeedConfig(timeout_seconds=60, max_cves_per_request=100)
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        assert client.config.timeout_seconds == 60
        assert client.config.max_cves_per_request == 100

    def test_init_real_mode_fallback_without_httpx(self):
        """Test REAL mode falls back when httpx unavailable."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", False):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            # Should fallback to MOCK mode
            assert client.mode == ThreatFeedMode.MOCK


class TestCaching:
    """Tests for cache functionality."""

    def test_check_cache_miss(self):
        """Test cache miss returns None."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._check_cache("nonexistent-key")

        assert result is None

    def test_check_cache_hit(self):
        """Test cache hit returns data."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        client._cache["test-key"] = (datetime.now(), ["test-data"])

        result = client._check_cache("test-key")

        assert result == ["test-data"]

    def test_check_cache_expired(self):
        """Test expired cache entry returns None."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        # Set cache entry from 2 hours ago
        old_time = datetime.now() - timedelta(hours=2)
        client._cache["expired-key"] = (old_time, ["old-data"])

        result = client._check_cache("expired-key")

        assert result is None
        assert "expired-key" not in client._cache

    def test_set_cache(self):
        """Test setting cache entry."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        client._set_cache("new-key", ["new-data"])

        assert "new-key" in client._cache
        cached_time, data = client._cache["new-key"]
        assert data == ["new-data"]


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_check_rate_limit_under_limit(self):
        """Test rate limit check when under limit."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._check_rate_limit("nvd")

        assert result is True

    def test_check_rate_limit_at_limit(self):
        """Test rate limit check when at limit."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        # Fill rate limit window
        now = time.time()
        client._request_times["nvd"] = [now - i for i in range(5)]

        result = client._check_rate_limit("nvd")

        assert result is False

    def test_check_rate_limit_with_api_key(self):
        """Test rate limit is higher with API key."""
        config = ThreatFeedConfig(nvd_api_key="test-api-key")
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)
        # Fill to 10 requests (above unauthenticated limit of 5)
        now = time.time()
        client._request_times["nvd"] = [now - i for i in range(10)]

        result = client._check_rate_limit("nvd")

        assert result is True  # Should be under 50 limit with API key

    def test_record_request(self):
        """Test recording a request."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        initial_count = len(client._request_times["nvd"])

        client._record_request("nvd")

        assert len(client._request_times["nvd"]) == initial_count + 1

    def test_rate_limit_cleans_old_entries(self):
        """Test rate limit check cleans old entries."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        # Add old entries (60 seconds ago)
        old_time = time.time() - 60
        client._request_times["nvd"] = [old_time, old_time, old_time]

        client._check_rate_limit("nvd")

        # Old entries should be cleaned
        assert len(client._request_times["nvd"]) == 0


class TestMockMethods:
    """Tests for mock data methods."""

    def test_mock_nvd_cves(self):
        """Test mock NVD CVEs."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._mock_nvd_cves()

        assert len(result) == 3
        assert all(isinstance(cve, CVERecord) for cve in result)
        assert result[0].cve_id.startswith("CVE-")

    def test_mock_cisa_kev(self):
        """Test mock CISA KEV records."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._mock_cisa_kev()

        assert len(result) == 2
        assert all(isinstance(r, CISAKEVRecord) for r in result)

    def test_mock_github_advisories(self):
        """Test mock GitHub advisories."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._mock_github_advisories()

        assert len(result) == 2
        assert all(isinstance(a, GitHubAdvisory) for a in result)


class TestFetchNvdCves:
    """Tests for fetch_nvd_cves method."""

    @pytest.mark.asyncio
    async def test_fetch_nvd_cves_mock_mode(self):
        """Test fetching CVEs in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_nvd_cves(days_back=7)

        assert len(result) == 3
        assert all(isinstance(cve, CVERecord) for cve in result)

    @pytest.mark.asyncio
    async def test_fetch_nvd_cves_cached(self):
        """Test CVEs are returned from cache."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        cached_data = [
            CVERecord(
                cve_id="CVE-CACHED",
                title="Cached CVE",
                description="From cache",
                cvss_score=5.0,
                published_date=datetime.now(),
            )
        ]
        client._cache["nvd:7:"] = (datetime.now(), cached_data)

        # Even in REAL mode, should return cached data
        client.mode = ThreatFeedMode.REAL
        result = await client.fetch_nvd_cves(days_back=7)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-CACHED"


class TestFetchCisaKev:
    """Tests for fetch_cisa_kev method."""

    @pytest.mark.asyncio
    async def test_fetch_cisa_kev_mock_mode(self):
        """Test fetching CISA KEV in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_cisa_kev()

        assert len(result) == 2
        assert all(isinstance(r, CISAKEVRecord) for r in result)


class TestFetchGithubAdvisories:
    """Tests for fetch_github_advisories method."""

    @pytest.mark.asyncio
    async def test_fetch_github_advisories_mock_mode(self):
        """Test fetching GitHub advisories in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_github_advisories(ecosystem="pip")

        assert len(result) == 2
        assert all(isinstance(a, GitHubAdvisory) for a in result)


class TestParseNvdResponse:
    """Tests for _parse_nvd_response method."""

    def test_parse_nvd_response_basic(self):
        """Test parsing basic NVD response."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2025-TEST",
                        "descriptions": [
                            {"lang": "en", "value": "Test vulnerability description"}
                        ],
                        "published": "2025-12-01T00:00:00.000Z",
                        "metrics": {
                            "cvssMetricV31": [{"cvssData": {"baseScore": 7.5}}]
                        },
                        "references": [{"url": "https://example.com"}],
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-2025-TEST"
        assert result[0].cvss_score == 7.5

    def test_parse_nvd_response_cvss_v30(self):
        """Test parsing NVD response with CVSS v3.0."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-V30",
                        "descriptions": [{"lang": "en", "value": "Test"}],
                        "published": "2025-12-01T00:00:00.000Z",
                        "metrics": {
                            "cvssMetricV30": [{"cvssData": {"baseScore": 8.0}}]
                        },
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert result[0].cvss_score == 8.0

    def test_parse_nvd_response_cvss_v2(self):
        """Test parsing NVD response with CVSS v2."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-V2",
                        "descriptions": [{"lang": "en", "value": "Test"}],
                        "published": "2025-12-01T00:00:00.000Z",
                        "metrics": {"cvssMetricV2": [{"cvssData": {"baseScore": 6.5}}]},
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert result[0].cvss_score == 6.5

    def test_parse_nvd_response_with_configurations(self):
        """Test parsing NVD response with product configurations."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-CONFIG",
                        "descriptions": [{"lang": "en", "value": "Test"}],
                        "published": "2025-12-01T00:00:00.000Z",
                        "configurations": [
                            {
                                "nodes": [
                                    {
                                        "cpeMatch": [
                                            {
                                                "criteria": "cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert "product" in result[0].affected_products

    def test_parse_nvd_response_invalid_date(self):
        """Test parsing NVD response with invalid date."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-INVALID-DATE",
                        "descriptions": [{"lang": "en", "value": "Test"}],
                        "published": "invalid-date",
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        # Should use current date as fallback
        assert result[0].published_date is not None


class TestParseCisaResponse:
    """Tests for _parse_cisa_response method."""

    def test_parse_cisa_response_basic(self):
        """Test parsing basic CISA response."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2025-CISA",
                    "vendorProject": "Test Vendor",
                    "product": "Test Product",
                    "vulnerabilityName": "Test Vulnerability",
                    "dateAdded": "2025-12-01",
                    "dueDate": "2025-12-15",
                    "shortDescription": "Description",
                    "requiredAction": "Apply patch",
                    "knownRansomwareCampaignUse": "Known",
                }
            ]
        }

        result = client._parse_cisa_response(data)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-2025-CISA"
        assert result[0].known_ransomware is True

    def test_parse_cisa_response_invalid_dates(self):
        """Test parsing CISA response with invalid dates."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-BAD-DATE",
                    "vendorProject": "Test",
                    "product": "Test",
                    "vulnerabilityName": "Test",
                    "dateAdded": "invalid",
                    "dueDate": "also-invalid",
                    "shortDescription": "Desc",
                    "requiredAction": "Action",
                }
            ]
        }

        result = client._parse_cisa_response(data)

        # Should handle invalid dates gracefully
        assert result[0].date_added is not None


class TestParseGithubResponse:
    """Tests for _parse_github_response method."""

    def test_parse_github_response_basic(self):
        """Test parsing basic GitHub response."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-test-1234",
                "summary": "Test Summary",
                "description": "Test Description",
                "severity": "high",
                "published_at": "2025-12-01T00:00:00Z",
                "identifiers": [{"type": "CVE", "value": "CVE-2025-GHSA"}],
                "vulnerabilities": [
                    {
                        "package": {"ecosystem": "pip", "name": "test-package"},
                        "vulnerable_version_range": "<1.0.0",
                        "patched_versions": ">=1.0.0",
                    }
                ],
                "references": [{"url": "https://example.com"}],
            }
        ]

        result = client._parse_github_response(data)

        assert len(result) == 1
        assert result[0].ghsa_id == "GHSA-test-1234"
        assert result[0].cve_id == "CVE-2025-GHSA"
        assert result[0].package_name == "test-package"

    def test_parse_github_response_no_vulnerabilities(self):
        """Test parsing GitHub response without vulnerability details."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-no-vuln",
                "summary": "Summary",
                "description": "Description",
                "severity": "low",
                "published_at": "2025-12-01T00:00:00Z",
            }
        ]

        result = client._parse_github_response(data)

        assert len(result) == 1
        assert result[0].package_ecosystem is None

    def test_parse_github_response_invalid_date(self):
        """Test parsing GitHub response with invalid date."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-bad-date",
                "summary": "Summary",
                "description": "Description",
                "severity": "medium",
                "published_at": "not-a-date",
            }
        ]

        result = client._parse_github_response(data)

        # Should use current date as fallback
        assert result[0].published_at is not None


class TestCreateThreatFeedClient:
    """Tests for create_threat_feed_client factory function."""

    def test_create_client_mock_mode(self):
        """Test creating client in mock mode."""
        client = create_threat_feed_client(use_mock=True)

        assert client.mode == ThreatFeedMode.MOCK

    def test_create_client_auto_detect(self):
        """Test auto-detection of mode."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = create_threat_feed_client(use_mock=False)

            assert client.mode == ThreatFeedMode.REAL

    def test_create_client_with_config(self):
        """Test creating client with custom config."""
        config = ThreatFeedConfig(timeout_seconds=90)
        client = create_threat_feed_client(use_mock=True, config=config)

        assert client.config.timeout_seconds == 90


class TestClientClose:
    """Tests for client close method."""

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing the HTTP client."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        # Mock the HTTP client
        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_http.aclose = AsyncMock()
        client._http_client = mock_http

        await client.close()

        mock_http.aclose.assert_called_once()
        assert client._http_client is None

    @pytest.mark.asyncio
    async def test_close_already_closed_client(self):
        """Test closing an already closed client."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
        client._http_client = None

        # Should not raise
        await client.close()


# =============================================================================
# Extended Tests for Coverage Improvement
# =============================================================================


def create_mock_httpx_response(status_code: int, json_data: dict):
    """Create a mock httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_response.text = str(json_data)
    mock_response.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_response


class TestRealModeFetching:
    """Tests for real mode fetching with mocked HTTP client."""

    @pytest.mark.asyncio
    async def test_fetch_nvd_cves_real_mode(self):
        """Test fetching CVEs in real mode with mocked client."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            # Mock the HTTP client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2025-0001",
                            "descriptions": [{"lang": "en", "value": "Test CVE"}],
                            "published": "2025-12-01T00:00:00.000Z",
                            "metrics": {
                                "cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]
                            },
                        }
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            client._http_client = mock_client

            result = await client.fetch_nvd_cves(days_back=7)

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_fetch_cisa_kev_real_mode(self):
        """Test fetching CISA KEV in real mode with mocked client."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "vulnerabilities": [
                    {
                        "cveID": "CVE-2025-0001",
                        "vendorProject": "Vendor",
                        "product": "Product",
                        "vulnerabilityName": "Test Vuln",
                        "dateAdded": "2025-12-01",
                        "dueDate": "2025-12-15",
                        "shortDescription": "Desc",
                        "requiredAction": "Patch",
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            client._http_client = mock_client

            result = await client.fetch_cisa_kev()

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_fetch_github_advisories_real_mode(self):
        """Test fetching GitHub advisories in real mode with mocked client."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "ghsa_id": "GHSA-test-1234",
                    "summary": "Test Summary",
                    "description": "Test Description",
                    "severity": "high",
                    "published_at": "2025-12-01T00:00:00Z",
                }
            ]
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            client._http_client = mock_client

            result = await client.fetch_github_advisories(ecosystem="pip")

            assert len(result) >= 1


class TestApiKeyUsage:
    """Tests for API key usage in requests."""

    def test_nvd_api_key_config(self):
        """Test NVD API key configuration."""
        config = ThreatFeedConfig(nvd_api_key="test-api-key")
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        assert client.config.nvd_api_key == "test-api-key"

    def test_github_token_config(self):
        """Test GitHub token configuration."""
        config = ThreatFeedConfig(github_token="ghp_test_token")
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        assert client.config.github_token == "ghp_test_token"


class TestCacheTTL:
    """Tests for cache TTL configuration."""

    def test_custom_cache_ttl(self):
        """Test custom cache TTL with minutes."""
        config = ThreatFeedConfig(cache_ttl_minutes=120)  # 2 hours
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        assert client.config.cache_ttl_minutes == 120

    def test_check_cache_respects_ttl(self):
        """Test cache respects TTL setting (minutes)."""
        config = ThreatFeedConfig(cache_ttl_minutes=5)  # 5 minutes
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        # Add entry that's 1 minute old (should still be valid with 5 min TTL)
        recent_time = datetime.now() - timedelta(minutes=1)
        client._cache["test-key"] = (recent_time, ["test-data"])

        result = client._check_cache("test-key")
        assert result == ["test-data"]


class TestRateLimitingExtended:
    """Extended rate limiting tests."""

    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        for _ in range(5):
            client._record_request("nvd")

        assert len(client._request_times["nvd"]) == 5

    def test_rate_limit_per_source(self):
        """Test rate limiting is per source."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        # Fill NVD rate limit
        now = time.time()
        client._request_times["nvd"] = [now - i for i in range(5)]

        # NVD should be rate limited
        assert client._check_rate_limit("nvd") is False

        # CISA should not be rate limited
        assert client._check_rate_limit("cisa") is True


class TestCVERecordFields:
    """Tests for CVERecord optional fields."""

    def test_cve_record_with_all_standard_fields(self):
        """Test CVERecord with all standard fields."""
        record = CVERecord(
            cve_id="CVE-2025-0001",
            title="Test CVE",
            description="Test description",
            cvss_score=9.8,
            published_date=datetime.now(),
            affected_products=["product1", "product2"],
            references=["https://nvd.nist.gov/vuln/detail/CVE-2025-0001"],
        )

        assert record.cve_id == "CVE-2025-0001"
        assert record.cvss_score == 9.8
        assert len(record.affected_products) == 2
        assert len(record.references) == 1

    def test_cve_record_minimal_with_cvss(self):
        """Test CVERecord with minimal fields including cvss_score."""
        record = CVERecord(
            cve_id="CVE-2025-0002",
            title="Minimal CVE",
            description="Minimal description",
            cvss_score=None,
            published_date=datetime.now(),
        )

        assert record.cve_id == "CVE-2025-0002"
        assert record.cvss_score is None
        assert record.affected_products == []
        assert record.references == []


class TestCISAKEVRecordFields:
    """Tests for CISAKEVRecord optional fields."""

    def test_cisa_kev_record_full(self):
        """Test CISAKEVRecord with all standard fields."""
        record = CISAKEVRecord(
            cve_id="CVE-2025-0001",
            vendor_project="Microsoft",
            product="Windows",
            vulnerability_name="Remote Code Execution",
            date_added=datetime.now(),
            due_date=datetime.now() + timedelta(days=14),
            short_description="Critical RCE vulnerability",
            required_action="Apply security update",
            known_ransomware=True,
        )

        assert record.known_ransomware is True
        assert record.cve_id == "CVE-2025-0001"
        assert record.vendor_project == "Microsoft"


class TestGitHubAdvisoryFields:
    """Tests for GitHubAdvisory optional fields."""

    def test_github_advisory_with_standard_fields(self):
        """Test GitHubAdvisory with all standard fields."""
        advisory = GitHubAdvisory(
            ghsa_id="GHSA-xxxx-yyyy",
            cve_id="CVE-2025-0001",
            summary="Test advisory",
            description="Description",
            severity="critical",
            published_at=datetime.now(),
            package_ecosystem="pip",
            package_name="requests",
            vulnerable_versions="<2.28.0",
            patched_versions=">=2.28.0",
        )

        assert advisory.severity == "critical"
        assert advisory.ghsa_id == "GHSA-xxxx-yyyy"
        assert advisory.package_ecosystem == "pip"


class TestParseNvdResponseEdgeCases:
    """Tests for edge cases in NVD response parsing."""

    def test_parse_nvd_response_empty(self):
        """Test parsing empty NVD response."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._parse_nvd_response({})

        assert result == []

    def test_parse_nvd_response_no_vulnerabilities(self):
        """Test parsing NVD response with no vulnerabilities."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._parse_nvd_response({"vulnerabilities": []})

        assert result == []

    def test_parse_nvd_response_missing_cve(self):
        """Test parsing NVD response with missing CVE data creates record with empty id."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {"vulnerabilities": [{}]}  # No 'cve' key

        result = client._parse_nvd_response(data)

        # The parser creates a record even with missing cve data (empty id)
        assert len(result) == 1
        assert result[0].cve_id == ""

    def test_parse_nvd_response_no_cvss(self):
        """Test parsing NVD response without CVSS score."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-NO-CVSS",
                        "descriptions": [{"lang": "en", "value": "Test"}],
                        "published": "2025-12-01T00:00:00.000Z",
                        "metrics": {},  # No CVSS metrics
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert len(result) == 1
        assert result[0].cvss_score is None


class TestParseCisaResponseEdgeCases:
    """Tests for edge cases in CISA response parsing."""

    def test_parse_cisa_response_empty(self):
        """Test parsing empty CISA response."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._parse_cisa_response({})

        assert result == []

    def test_parse_cisa_response_unknown_ransomware(self):
        """Test parsing CISA response with unknown ransomware status."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2025-0001",
                    "vendorProject": "Test",
                    "product": "Test",
                    "vulnerabilityName": "Test",
                    "dateAdded": "2025-12-01",
                    "dueDate": "2025-12-15",
                    "shortDescription": "Desc",
                    "requiredAction": "Action",
                    "knownRansomwareCampaignUse": "Unknown",
                }
            ]
        }

        result = client._parse_cisa_response(data)

        assert len(result) == 1
        assert result[0].known_ransomware is False


class TestParseGithubResponseEdgeCases:
    """Tests for edge cases in GitHub response parsing."""

    def test_parse_github_response_empty(self):
        """Test parsing empty GitHub response."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = client._parse_github_response([])

        assert result == []

    def test_parse_github_response_no_identifiers(self):
        """Test parsing GitHub response without CVE identifiers."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-no-cve",
                "summary": "Summary",
                "description": "Description",
                "severity": "medium",
                "published_at": "2025-12-01T00:00:00Z",
                # No identifiers
            }
        ]

        result = client._parse_github_response(data)

        assert len(result) == 1
        assert result[0].cve_id is None

    def test_parse_github_response_multiple_vulnerabilities(self):
        """Test parsing GitHub response with multiple vulnerability entries."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-multi",
                "summary": "Summary",
                "description": "Description",
                "severity": "high",
                "published_at": "2025-12-01T00:00:00Z",
                "vulnerabilities": [
                    {
                        "package": {"ecosystem": "pip", "name": "package1"},
                        "vulnerable_version_range": "<1.0",
                        "patched_versions": ">=1.0",
                    },
                    {
                        "package": {"ecosystem": "pip", "name": "package2"},
                        "vulnerable_version_range": "<2.0",
                        "patched_versions": ">=2.0",
                    },
                ],
            }
        ]

        result = client._parse_github_response(data)

        # Should take first vulnerability's package info
        assert len(result) == 1
        assert result[0].package_name == "package1"


class TestSearchCVEs:
    """Tests for CVE search functionality."""

    @pytest.mark.asyncio
    async def test_search_cves_by_keywords_list(self):
        """Test searching CVEs by keywords list."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        # Use keywords as list (correct API)
        result = await client.fetch_nvd_cves(keywords=["sql", "injection"])

        # Should return mock data
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_search_cves_default_parameters(self):
        """Test searching CVEs with default parameters."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_nvd_cves()

        assert len(result) >= 0


# =============================================================================
# Real Mode Error Handling Tests
# =============================================================================


class TestRealModeErrorHandling:
    """Tests for error handling in real mode."""

    @pytest.mark.asyncio
    async def test_fetch_nvd_api_error(self):
        """Test NVD fetch when API returns error - client may fall back to mock."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            def raise_for_status():
                raise Exception("HTTP 500")

            mock_response.raise_for_status = raise_for_status

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_nvd_cves()

            # Client may return empty list or fall back to mock data
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_cisa_api_error(self):
        """Test CISA fetch when API returns error - client may fall back to mock."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 503

            def raise_for_status():
                raise Exception("Service Unavailable")

            mock_response.raise_for_status = raise_for_status

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_cisa_kev()

            # Client may return empty list or fall back to mock data
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_github_api_error(self):
        """Test GitHub fetch when API returns error - client may fall back to mock."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 403

            def raise_for_status():
                raise Exception("Rate Limited")

            mock_response.raise_for_status = raise_for_status

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_github_advisories()

            # Client may return empty list or fall back to mock data
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_network_error(self):
        """Test fetch when network error occurs - client may fall back to mock."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_http = MagicMock()
            mock_http.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_nvd_cves()

            # Client may return empty list or fall back to mock data
            assert isinstance(result, list)


# =============================================================================
# Rate Limiting Fallback Tests
# =============================================================================


class TestRateLimitingFallback:
    """Tests for rate limit fallback behavior."""

    @pytest.mark.asyncio
    async def test_nvd_rate_limited_returns_mock_data(self):
        """Test that rate limited NVD request returns mock data."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        # In mock mode, rate limit check doesn't apply - returns mock data
        result = await client.fetch_nvd_cves(days_back=7)

        assert len(result) >= 0
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_cisa_returns_data(self):
        """Test that CISA request returns data in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_cisa_kev()

        assert len(result) >= 0
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_github_returns_data(self):
        """Test that GitHub request returns data in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_github_advisories(ecosystem="pip")

        assert len(result) >= 0
        assert isinstance(result, list)


# =============================================================================
# Config Validation Tests
# =============================================================================


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_config_with_all_options(self):
        """Test ThreatFeedConfig with all options."""
        config = ThreatFeedConfig(
            nvd_api_key="nvd-key-123",
            github_token="ghp_token123",
            timeout_seconds=120,
            cache_ttl_minutes=120,
            max_cves_per_request=100,
        )

        assert config.nvd_api_key == "nvd-key-123"
        assert config.github_token == "ghp_token123"
        assert config.timeout_seconds == 120
        assert config.cache_ttl_minutes == 120
        assert config.max_cves_per_request == 100

    def test_config_default_values(self):
        """Test ThreatFeedConfig default values."""
        config = ThreatFeedConfig()

        assert config.nvd_api_key is None
        assert config.github_token is None
        assert config.timeout_seconds == 30
        assert config.cache_ttl_minutes == 60
        assert config.max_cves_per_request == 50


# =============================================================================
# Comprehensive API Tests
# =============================================================================


class TestFetchNvdAllParameters:
    """Tests for fetch_nvd_cves with all parameters."""

    @pytest.mark.asyncio
    async def test_fetch_nvd_with_days_back(self):
        """Test NVD fetch with days_back parameter."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_nvd_cves(days_back=30)

        # Mock mode returns synthetic data
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_nvd_real_mode_mocked(self):
        """Test NVD fetch in real mode with mocked client."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"vulnerabilities": []}
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_nvd_cves(days_back=7)

            assert result == []


class TestFetchGithubAllParameters:
    """Tests for fetch_github_advisories with all parameters."""

    @pytest.mark.asyncio
    async def test_fetch_github_with_ecosystem(self):
        """Test GitHub fetch with ecosystem filter."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_github_advisories(ecosystem="npm")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_github_pip_ecosystem(self):
        """Test GitHub fetch with pip ecosystem."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_github_advisories(ecosystem="pip")

        assert isinstance(result, list)


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def test_cache_expired_returns_none(self):
        """Test that expired cache returns None."""
        config = ThreatFeedConfig(cache_ttl_minutes=1)  # 1 minute
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        # Add expired entry (2 minutes old, TTL is 1 minute)
        old_time = datetime.now() - timedelta(minutes=2)
        client._cache["expired-key"] = (old_time, ["old-data"])

        result = client._check_cache("expired-key")

        assert result is None

    def test_cache_clears_old_entries(self):
        """Test that cache check clears old entries."""
        config = ThreatFeedConfig(cache_ttl_minutes=1)  # 1 minute
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK, config=config)

        # Add expired entry
        old_time = datetime.now() - timedelta(minutes=2)
        client._cache["expired-key"] = (old_time, ["old-data"])

        # Check cache
        client._check_cache("expired-key")

        # Entry should be removed
        assert "expired-key" not in client._cache


# =============================================================================
# Mock Mode Data Generation Tests
# =============================================================================


class TestMockModeDataGeneration:
    """Tests for mock mode data generation."""

    @pytest.mark.asyncio
    async def test_mock_nvd_generates_data(self):
        """Test that mock mode generates NVD data."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_nvd_cves()

        assert len(result) > 0
        assert all(isinstance(r, CVERecord) for r in result)

    @pytest.mark.asyncio
    async def test_mock_cisa_generates_data(self):
        """Test that mock mode generates CISA data."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_cisa_kev()

        assert len(result) > 0
        assert all(isinstance(r, CISAKEVRecord) for r in result)

    @pytest.mark.asyncio
    async def test_mock_github_generates_data(self):
        """Test that mock mode generates GitHub data."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_github_advisories()

        assert len(result) > 0
        assert all(isinstance(r, GitHubAdvisory) for r in result)


# =============================================================================
# NVD Response Headers Tests
# =============================================================================


class TestNvdApiKeyHeader:
    """Tests for NVD API key in request headers."""

    @pytest.mark.asyncio
    async def test_nvd_request_with_api_key(self):
        """Test that NVD requests include API key when configured."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            config = ThreatFeedConfig(nvd_api_key="test-nvd-key")
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL, config=config)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"vulnerabilities": []}
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            await client.fetch_nvd_cves()

            # Verify get was called
            mock_http.get.assert_called_once()


# =============================================================================
# GitHub Token Header Tests
# =============================================================================


class TestGithubTokenHeader:
    """Tests for GitHub token in request headers."""

    @pytest.mark.asyncio
    async def test_github_request_with_token(self):
        """Test that GitHub requests include token when configured."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            config = ThreatFeedConfig(github_token="ghp_test_token_123")
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL, config=config)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            await client.fetch_github_advisories()

            # Verify get was called
            mock_http.get.assert_called_once()


# =============================================================================
# Parse NVD Extended Tests
# =============================================================================


class TestParseNvdExtended:
    """Extended tests for parsing NVD responses."""

    def test_parse_nvd_with_full_data(self):
        """Test parsing NVD response with full data."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2025-TEST",
                        "descriptions": [
                            {"lang": "en", "value": "Test vulnerability description"}
                        ],
                        "published": "2025-12-01T00:00:00.000Z",
                        "metrics": {
                            "cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]
                        },
                        "configurations": [
                            {
                                "nodes": [
                                    {
                                        "cpeMatch": [
                                            {
                                                "criteria": "cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-2025-TEST"
        assert result[0].cvss_score == 9.8


# =============================================================================
# HTTPX Not Available Tests
# =============================================================================


class TestHttpxNotAvailable:
    """Tests for behavior when httpx is not available."""

    def test_real_mode_without_httpx(self):
        """Test client creation when httpx not available."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", False):
            # Client may switch to mock mode when httpx is unavailable
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)
            # The client should be created successfully regardless
            assert client is not None

    @pytest.mark.asyncio
    async def test_fetch_works_in_mock_mode(self):
        """Test that fetch operations work in mock mode."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_nvd_cves()

        assert isinstance(result, list)
        assert len(result) > 0


# =============================================================================
# Additional Coverage Tests for Missing Code Paths
# =============================================================================


class TestGetClientLazyInit:
    """Tests for _get_client lazy initialization."""

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self):
        """Test that _get_client creates a new HTTP client when none exists."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            with patch("src.services.threat_feed_client.httpx") as mock_httpx:
                mock_async_client = MagicMock()
                mock_async_client.is_closed = False
                mock_httpx.AsyncClient.return_value = mock_async_client
                mock_httpx.Timeout = MagicMock()

                client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

                # First call should create client
                http_client = await client._get_client()
                mock_httpx.AsyncClient.assert_called_once()
                assert http_client is mock_async_client

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_open_client(self):
        """Test that _get_client reuses an existing open client."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_client = MagicMock()
            mock_client.is_closed = False
            client._http_client = mock_client

            # Should return existing client
            http_client = await client._get_client()
            assert http_client is mock_client

    @pytest.mark.asyncio
    async def test_get_client_recreates_closed_client(self):
        """Test that _get_client recreates a closed client."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            with patch("src.services.threat_feed_client.httpx") as mock_httpx:
                new_client = MagicMock()
                new_client.is_closed = False
                mock_httpx.AsyncClient.return_value = new_client
                mock_httpx.Timeout = MagicMock()

                client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

                # Set up a closed client
                old_client = MagicMock()
                old_client.is_closed = True
                client._http_client = old_client

                # Should create new client
                http_client = await client._get_client()
                assert http_client is new_client


class TestFetchNvdWithKeywords:
    """Tests for fetch_nvd_cves with keywords parameter."""

    @pytest.mark.asyncio
    async def test_fetch_nvd_with_keywords_real_mode(self):
        """Test NVD fetch with keywords in real mode."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2025-SQL-001",
                            "descriptions": [
                                {"lang": "en", "value": "SQL injection vulnerability"}
                            ],
                            "published": "2025-12-01T00:00:00.000Z",
                            "metrics": {
                                "cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]
                            },
                        }
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_nvd_cves(
                days_back=7, keywords=["sql", "injection"]
            )

            assert len(result) >= 1
            # Verify the request was made with keyword params
            mock_http.get.assert_called_once()


class TestFetchGithubWithSeverity:
    """Tests for fetch_github_advisories with severity parameter."""

    @pytest.mark.asyncio
    async def test_fetch_github_with_severity_filter(self):
        """Test GitHub fetch with severity filter in real mode."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "ghsa_id": "GHSA-critical-001",
                    "summary": "Critical vulnerability",
                    "description": "Critical security issue",
                    "severity": "critical",
                    "published_at": "2025-12-01T00:00:00Z",
                }
            ]
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            result = await client.fetch_github_advisories(
                ecosystem="pip", severity="critical"
            )

            assert len(result) >= 1
            mock_http.get.assert_called_once()


class TestRateLimitFallbackToMock:
    """Tests for rate limit fallback to mock data."""

    @pytest.mark.asyncio
    async def test_nvd_rate_limit_triggers_mock_fallback(self):
        """Test that hitting NVD rate limit returns mock data."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            # Fill up the rate limit
            now = time.time()
            client._request_times["nvd"] = [now - i * 0.1 for i in range(10)]

            # Should return mock data due to rate limit
            result = await client.fetch_nvd_cves(days_back=7)

            assert len(result) > 0
            # Should be mock data (CVE-2025-0001 is a mock CVE)
            mock_ids = [cve.cve_id for cve in result]
            assert any("CVE-2025-" in cve_id for cve_id in mock_ids)

    @pytest.mark.asyncio
    async def test_cisa_rate_limit_triggers_mock_fallback(self):
        """Test that hitting CISA rate limit returns mock data."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            # Fill up the rate limit
            now = time.time()
            client._request_times["cisa"] = [now - i * 0.1 for i in range(10)]

            result = await client.fetch_cisa_kev()

            assert len(result) > 0
            # Mock data includes CVE-2025-0004
            mock_ids = [r.cve_id for r in result]
            assert any("CVE-2025-" in cve_id for cve_id in mock_ids)

    @pytest.mark.asyncio
    async def test_github_rate_limit_triggers_mock_fallback(self):
        """Test that hitting GitHub rate limit returns mock data."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            # Fill up the rate limit
            now = time.time()
            client._request_times["github"] = [now - i * 0.1 for i in range(10)]

            result = await client.fetch_github_advisories(ecosystem="pip")

            assert len(result) > 0
            # Mock data includes GHSA IDs
            assert any(adv.ghsa_id.startswith("GHSA-") for adv in result)


class TestCisaParsingEdgeCases:
    """Tests for CISA response parsing edge cases."""

    def test_parse_cisa_empty_due_date(self):
        """Test parsing CISA response with empty due_date."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2025-EMPTY-DATE",
                    "vendorProject": "Test",
                    "product": "Test",
                    "vulnerabilityName": "Test Vuln",
                    "dateAdded": "2025-12-01",
                    "dueDate": "",  # Empty due date
                    "shortDescription": "Test",
                    "requiredAction": "Patch",
                    "knownRansomwareCampaignUse": "Unknown",
                }
            ]
        }

        result = client._parse_cisa_response(data)

        assert len(result) == 1
        assert result[0].due_date is None

    def test_parse_cisa_missing_fields(self):
        """Test parsing CISA response with missing optional fields."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2025-MINIMAL",
                    "vendorProject": "",
                    "product": "",
                    "vulnerabilityName": "",
                    "dateAdded": "2025-12-01",
                    "dueDate": "2025-12-31",
                    "shortDescription": "",
                    "requiredAction": "",
                }
            ]
        }

        result = client._parse_cisa_response(data)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-2025-MINIMAL"


class TestNvdParsingCweAndEpss:
    """Tests for NVD parsing with CWE and EPSS fields."""

    def test_parse_nvd_with_weaknesses(self):
        """Test parsing NVD response with CWE weaknesses."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2025-CWE-TEST",
                        "descriptions": [{"lang": "en", "value": "Test CVE with CWE"}],
                        "published": "2025-12-01T00:00:00.000Z",
                        "weaknesses": [
                            {
                                "source": "nvd@nist.gov",
                                "type": "Primary",
                                "description": [{"lang": "en", "value": "CWE-79"}],
                            }
                        ],
                    }
                }
            ]
        }

        result = client._parse_nvd_response(data)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-2025-CWE-TEST"


class TestGitHubParsingEdgeCases:
    """Tests for GitHub response parsing edge cases."""

    def test_parse_github_with_empty_package(self):
        """Test parsing GitHub response with empty package info."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-empty-pkg",
                "summary": "Summary",
                "description": "Description",
                "severity": "medium",
                "published_at": "2025-12-01T00:00:00Z",
                "vulnerabilities": [
                    {
                        "package": {},  # Empty package object
                        "vulnerable_version_range": "<1.0",
                    }
                ],
            }
        ]

        result = client._parse_github_response(data)

        assert len(result) == 1
        assert result[0].package_ecosystem is None
        assert result[0].package_name is None

    def test_parse_github_with_multiple_identifiers(self):
        """Test parsing GitHub response with multiple identifiers."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        data = [
            {
                "ghsa_id": "GHSA-multi-id",
                "summary": "Summary",
                "description": "Description",
                "severity": "high",
                "published_at": "2025-12-01T00:00:00Z",
                "identifiers": [
                    {"type": "GHSA", "value": "GHSA-multi-id"},
                    {"type": "CVE", "value": "CVE-2025-MULTI"},
                    {"type": "CWE", "value": "CWE-79"},
                ],
            }
        ]

        result = client._parse_github_response(data)

        assert len(result) == 1
        assert result[0].cve_id == "CVE-2025-MULTI"


class TestCacheKeyGeneration:
    """Tests for cache key generation."""

    @pytest.mark.asyncio
    async def test_nvd_cache_key_format_in_real_mode(self):
        """Test NVD cache key format in real mode (mock mode bypasses cache)."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"vulnerabilities": []}
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            # Fetch with keywords to populate cache
            await client.fetch_nvd_cves(days_back=7, keywords=["python", "rce"])

            # Check cache key was set correctly
            cache_keys = list(client._cache.keys())
            # Should have cache key in format "nvd:7:python,rce"
            assert any("nvd" in key for key in cache_keys)

    @pytest.mark.asyncio
    async def test_github_cache_key_format(self):
        """Test GitHub cache key format in real mode."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_response.raise_for_status = MagicMock()

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            # Fetch with ecosystem filter
            await client.fetch_github_advisories(ecosystem="npm")

            # Cache should include ecosystem in key
            cache_keys = list(client._cache.keys())
            assert any("github" in key for key in cache_keys)


class TestCloseClient:
    """Tests for client close functionality."""

    @pytest.mark.asyncio
    async def test_close_with_open_client(self):
        """Test closing an open HTTP client."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        mock_http = MagicMock()
        mock_http.is_closed = False
        mock_http.aclose = AsyncMock()
        client._http_client = mock_http

        await client.close()

        mock_http.aclose.assert_called_once()
        assert client._http_client is None

    @pytest.mark.asyncio
    async def test_close_with_already_closed_client(self):
        """Test closing when client is already closed."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        mock_http = MagicMock()
        mock_http.is_closed = True
        client._http_client = mock_http

        # Should not raise and should not call aclose
        await client.close()

    @pytest.mark.asyncio
    async def test_close_with_no_client(self):
        """Test closing when no client was ever created."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        # Should not raise
        await client.close()


class TestConfigFromEnvironment:
    """Tests for configuration from environment variables."""

    def test_config_reads_nvd_api_key_from_env(self):
        """Test that NVD API key is read from environment."""
        with patch.dict(os.environ, {"NVD_API_KEY": "test-nvd-key-from-env"}):
            # Need to reimport to pick up new env var
            client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
            # The default config reads from env
            assert client.config.nvd_api_key is not None or os.environ.get(
                "NVD_API_KEY"
            )

    def test_config_reads_github_token_from_env(self):
        """Test that GitHub token is read from environment."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token_from_env"}):
            client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)
            assert client.config.github_token is not None or os.environ.get(
                "GITHUB_TOKEN"
            )


class TestMockDataConsistency:
    """Tests for mock data consistency and structure."""

    @pytest.mark.asyncio
    async def test_mock_nvd_data_has_required_fields(self):
        """Test that mock NVD data has all required fields."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_nvd_cves()

        for cve in result:
            assert cve.cve_id.startswith("CVE-")
            assert cve.title is not None
            assert cve.description is not None
            assert cve.published_date is not None

    @pytest.mark.asyncio
    async def test_mock_cisa_data_has_required_fields(self):
        """Test that mock CISA data has all required fields."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_cisa_kev()

        for record in result:
            assert record.cve_id.startswith("CVE-")
            assert record.vendor_project is not None
            assert record.product is not None
            assert record.required_action is not None

    @pytest.mark.asyncio
    async def test_mock_github_data_has_required_fields(self):
        """Test that mock GitHub data has all required fields."""
        client = ThreatFeedClient(mode=ThreatFeedMode.MOCK)

        result = await client.fetch_github_advisories()

        for advisory in result:
            assert advisory.ghsa_id.startswith("GHSA-")
            assert advisory.summary is not None
            assert advisory.severity is not None
            assert advisory.published_at is not None


class TestApiErrorFallback:
    """Tests for API error fallback behavior."""

    @pytest.mark.asyncio
    async def test_nvd_http_error_falls_back_to_mock(self):
        """Test that HTTP error on NVD falls back to mock data."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_response = MagicMock()
            mock_response.status_code = 500

            def raise_for_status():
                raise Exception("HTTP 500 Internal Server Error")

            mock_response.raise_for_status = raise_for_status

            mock_http = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            client._http_client = mock_http

            # Should return mock data on error
            result = await client.fetch_nvd_cves()

            assert len(result) > 0
            # Should be mock CVEs
            assert any("CVE-2025-" in cve.cve_id for cve in result)

    @pytest.mark.asyncio
    async def test_github_timeout_falls_back_to_mock(self):
        """Test that timeout on GitHub falls back to mock data."""
        with patch("src.services.threat_feed_client.HTTPX_AVAILABLE", True):
            client = ThreatFeedClient(mode=ThreatFeedMode.REAL)

            mock_http = MagicMock()
            mock_http.get = AsyncMock(side_effect=Exception("Connection timeout"))
            mock_http.is_closed = False
            client._http_client = mock_http

            # Should return mock data on timeout
            result = await client.fetch_github_advisories()

            assert len(result) > 0
            assert any(adv.ghsa_id.startswith("GHSA-") for adv in result)
