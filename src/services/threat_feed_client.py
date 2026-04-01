"""
Project Aura - Threat Feed Client

Provides real HTTP client for fetching threat intelligence from external sources:
- NVD (National Vulnerability Database)
- CISA Known Exploited Vulnerabilities
- GitHub Security Advisories

Supports mock mode for testing and graceful fallback on API failures.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, cast

logger = logging.getLogger(__name__)

# Try to import httpx for async HTTP calls
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available - using mock mode for threat feeds")


class ThreatFeedMode(Enum):
    """Operating modes for threat feed client."""

    MOCK = "mock"  # Return hardcoded test data
    REAL = "real"  # Fetch from actual APIs


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_window: int = 5  # Max requests per window
    window_seconds: int = 30  # Window duration
    retry_after_seconds: int = 60  # Wait time after hitting limit


@dataclass
class ThreatFeedConfig:
    """Configuration for threat feed sources."""

    # NVD Configuration
    nvd_api_url: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    nvd_api_key: str | None = None  # Optional, increases rate limit

    # CISA Configuration
    cisa_kev_url: str = (
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )

    # GitHub Configuration
    github_advisory_url: str = "https://api.github.com/advisories"
    github_token: str | None = None  # Optional, for higher rate limits

    # General settings
    timeout_seconds: int = 30
    max_cves_per_request: int = 50
    cache_ttl_minutes: int = 60


@dataclass
class CVERecord:
    """Parsed CVE record from NVD."""

    cve_id: str
    title: str
    description: str
    cvss_score: float | None
    published_date: datetime
    affected_products: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CISAKEVRecord:
    """Parsed CISA KEV record."""

    cve_id: str
    vendor_project: str
    product: str
    vulnerability_name: str
    date_added: datetime
    due_date: datetime | None
    short_description: str
    required_action: str
    known_ransomware: bool = False


@dataclass
class GitHubAdvisory:
    """Parsed GitHub Security Advisory."""

    ghsa_id: str
    cve_id: str | None
    summary: str
    description: str
    severity: str
    published_at: datetime
    package_ecosystem: str | None
    package_name: str | None
    vulnerable_versions: str | None
    patched_versions: str | None
    references: list[str] = field(default_factory=list)


class ThreatFeedClient:
    """
    Client for fetching threat intelligence from external APIs.

    Features:
    - Async HTTP calls with proper error handling
    - Rate limiting to respect API quotas
    - In-memory caching to reduce API calls
    - Graceful fallback to mock data on failures
    - Async context manager for automatic cleanup

    Usage:
        >>> async with ThreatFeedClient(mode=ThreatFeedMode.REAL) as client:
        ...     cves = await client.fetch_nvd_cves(days_back=7)
        ...     kev = await client.fetch_cisa_kev()
        ...     advisories = await client.fetch_github_advisories(ecosystem="pip")
    """

    def __init__(
        self,
        mode: ThreatFeedMode = ThreatFeedMode.MOCK,
        config: ThreatFeedConfig | None = None,
    ):
        """
        Initialize threat feed client.

        Args:
            mode: Operating mode (MOCK or REAL)
            config: Optional configuration overrides
        """
        self.mode = mode
        self.config = config or ThreatFeedConfig(
            nvd_api_key=os.environ.get("NVD_API_KEY"),
            github_token=os.environ.get("GITHUB_TOKEN"),
        )

        # Check if we can run in REAL mode
        if self.mode == ThreatFeedMode.REAL and not HTTPX_AVAILABLE:
            logger.warning("REAL mode requested but httpx not available. Using MOCK.")
            self.mode = ThreatFeedMode.MOCK

        # Rate limiting state
        self._request_times: dict[str, list[float]] = {
            "nvd": [],
            "cisa": [],
            "github": [],
        }

        # Cache
        self._cache: dict[str, tuple[datetime, Any]] = {}

        # HTTP client (lazy initialization)
        self._http_client: httpx.AsyncClient | None = None

        logger.info(f"ThreatFeedClient initialized in {self.mode.value} mode")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                follow_redirects=True,
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "ThreatFeedClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures cleanup."""
        await self.close()

    def _check_cache(self, key: str) -> Any | None:
        """Check cache for valid entry."""
        if key in self._cache:
            cached_time, data = self._cache[key]
            if datetime.now() - cached_time < timedelta(
                minutes=self.config.cache_ttl_minutes
            ):
                logger.debug(f"Cache hit for {key}")
                return data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        """Set cache entry."""
        self._cache[key] = (datetime.now(), data)

    def _check_rate_limit(self, source: str) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        window_start = now - 30  # 30 second window

        # Clean old entries
        self._request_times[source] = [
            t for t in self._request_times[source] if t > window_start
        ]

        # Check limit (NVD: 5/30s without key, 50/30s with key)
        limit = 5
        if source == "nvd" and self.config.nvd_api_key:
            limit = 50

        return len(self._request_times[source]) < limit

    def _record_request(self, source: str) -> None:
        """Record a request for rate limiting."""
        self._request_times[source].append(time.time())

    # =========================================================================
    # NVD API
    # =========================================================================

    async def fetch_nvd_cves(
        self,
        days_back: int = 30,
        keywords: list[str] | None = None,
    ) -> list[CVERecord]:
        """
        Fetch recent CVEs from NVD.

        Args:
            days_back: Number of days to look back
            keywords: Optional keywords to filter CVEs

        Returns:
            List of CVE records
        """
        if self.mode == ThreatFeedMode.MOCK:
            return self._mock_nvd_cves()

        cache_key = f"nvd:{days_back}:{','.join(keywords or [])}"
        cached = self._check_cache(cache_key)
        if cached:
            return cast(list[CVERecord], cached)

        try:
            if not self._check_rate_limit("nvd"):
                logger.warning("NVD rate limit reached, using cached/mock data")
                return self._mock_nvd_cves()

            self._record_request("nvd")
            client = await self._get_client()

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            params = {
                "pubStartDate": start_date.strftime("%Y-%m-%dT00:00:00.000"),
                "pubEndDate": end_date.strftime("%Y-%m-%dT23:59:59.999"),
                "resultsPerPage": str(self.config.max_cves_per_request),
            }

            if keywords:
                params["keywordSearch"] = " ".join(keywords)

            headers = {}
            if self.config.nvd_api_key:
                headers["apiKey"] = self.config.nvd_api_key

            response = await client.get(
                self.config.nvd_api_url, params=params, headers=headers
            )
            response.raise_for_status()

            data = response.json()
            cves = self._parse_nvd_response(data)

            self._set_cache(cache_key, cves)
            logger.info(f"Fetched {len(cves)} CVEs from NVD")
            return cves

        except Exception as e:
            logger.error(f"NVD API error: {e}. Falling back to mock data.")
            return self._mock_nvd_cves()

    def _parse_nvd_response(self, data: dict[str, Any]) -> list[CVERecord]:
        """Parse NVD API response."""
        cves = []
        for vuln in data.get("vulnerabilities", []):
            cve_data = vuln.get("cve", {})
            cve_id = cve_data.get("id", "")

            # Get description
            descriptions = cve_data.get("descriptions", [])
            description = ""
            for desc in descriptions:
                if desc.get("lang") == "en":
                    description = desc.get("value", "")
                    break

            # Get CVSS score
            cvss_score = None
            metrics = cve_data.get("metrics", {})
            if "cvssMetricV31" in metrics:
                cvss_data = metrics["cvssMetricV31"][0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore")
            elif "cvssMetricV30" in metrics:
                cvss_data = metrics["cvssMetricV30"][0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore")
            elif "cvssMetricV2" in metrics:
                cvss_data = metrics["cvssMetricV2"][0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore")

            # Get published date
            published_str = cve_data.get("published", "")
            try:
                published_date = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            except ValueError:
                published_date = datetime.now()

            # Get affected products from configurations
            affected = []
            configs = cve_data.get("configurations", [])
            for config in configs:
                for node in config.get("nodes", []):
                    for cpe in node.get("cpeMatch", []):
                        criteria = cpe.get("criteria", "")
                        # Extract product name from CPE
                        parts = criteria.split(":")
                        if len(parts) > 4:
                            affected.append(parts[4])

            # Get references
            refs = [
                r.get("url", "") for r in cve_data.get("references", []) if r.get("url")
            ]

            cves.append(
                CVERecord(
                    cve_id=cve_id,
                    title=f"{cve_id}: {description[:100]}...",
                    description=description,
                    cvss_score=cvss_score,
                    published_date=published_date,
                    affected_products=list(set(affected)),
                    references=refs[:5],  # Limit references
                    raw_data=cve_data,
                )
            )

        return cves

    def _mock_nvd_cves(self) -> list[CVERecord]:
        """Return mock CVE data for testing."""
        return [
            CVERecord(
                cve_id="CVE-2025-0001",
                title="CVE-2025-0001: Critical RCE in requests library",
                description="Remote code execution vulnerability in Python requests library versions < 2.31.0 allows attackers to execute arbitrary code via crafted URLs.",
                cvss_score=9.8,
                published_date=datetime.now() - timedelta(days=2),
                affected_products=["requests", "python-requests"],
                references=["https://nvd.nist.gov/vuln/detail/CVE-2025-0001"],
            ),
            CVERecord(
                cve_id="CVE-2025-0002",
                title="CVE-2025-0002: OpenSearch authentication bypass",
                description="Authentication bypass in OpenSearch versions < 2.11.0 allows unauthenticated access to cluster data.",
                cvss_score=8.1,
                published_date=datetime.now() - timedelta(days=5),
                affected_products=["opensearch", "opensearch-py"],
                references=["https://nvd.nist.gov/vuln/detail/CVE-2025-0002"],
            ),
            CVERecord(
                cve_id="CVE-2025-0003",
                title="CVE-2025-0003: FastAPI SSRF vulnerability",
                description="Server-side request forgery in FastAPI < 0.109.0 via redirect handling.",
                cvss_score=7.5,
                published_date=datetime.now() - timedelta(days=3),
                affected_products=["fastapi"],
                references=["https://nvd.nist.gov/vuln/detail/CVE-2025-0003"],
            ),
        ]

    # =========================================================================
    # CISA KEV API
    # =========================================================================

    async def fetch_cisa_kev(self) -> list[CISAKEVRecord]:
        """
        Fetch CISA Known Exploited Vulnerabilities catalog.

        Returns:
            List of CISA KEV records
        """
        if self.mode == ThreatFeedMode.MOCK:
            return self._mock_cisa_kev()

        cache_key = "cisa:kev"
        cached = self._check_cache(cache_key)
        if cached:
            return cast(list[CISAKEVRecord], cached)

        try:
            if not self._check_rate_limit("cisa"):
                logger.warning("CISA rate limit reached, using cached/mock data")
                return self._mock_cisa_kev()

            self._record_request("cisa")
            client = await self._get_client()

            response = await client.get(self.config.cisa_kev_url)
            response.raise_for_status()

            data = response.json()
            records = self._parse_cisa_response(data)

            self._set_cache(cache_key, records)
            logger.info(f"Fetched {len(records)} records from CISA KEV")
            return records

        except Exception as e:
            logger.error(f"CISA API error: {e}. Falling back to mock data.")
            return self._mock_cisa_kev()

    def _parse_cisa_response(self, data: dict[str, Any]) -> list[CISAKEVRecord]:
        """Parse CISA KEV response."""
        records = []
        for vuln in data.get("vulnerabilities", []):
            try:
                date_added = datetime.strptime(vuln.get("dateAdded", ""), "%Y-%m-%d")
            except ValueError:
                date_added = datetime.now()

            try:
                due_date_str = vuln.get("dueDate", "")
                due_date = (
                    datetime.strptime(due_date_str, "%Y-%m-%d")
                    if due_date_str
                    else None
                )
            except ValueError:
                due_date = None

            records.append(
                CISAKEVRecord(
                    cve_id=vuln.get("cveID", ""),
                    vendor_project=vuln.get("vendorProject", ""),
                    product=vuln.get("product", ""),
                    vulnerability_name=vuln.get("vulnerabilityName", ""),
                    date_added=date_added,
                    due_date=due_date,
                    short_description=vuln.get("shortDescription", ""),
                    required_action=vuln.get("requiredAction", ""),
                    known_ransomware=vuln.get("knownRansomwareCampaignUse", "")
                    == "Known",
                )
            )

        # Return most recent 50
        records.sort(key=lambda r: r.date_added, reverse=True)
        return records[:50]

    def _mock_cisa_kev(self) -> list[CISAKEVRecord]:
        """Return mock CISA KEV data for testing."""
        return [
            CISAKEVRecord(
                cve_id="CVE-2025-0004",
                vendor_project="Kubernetes",
                product="Kubernetes",
                vulnerability_name="Kubernetes API Server Privilege Escalation",
                date_added=datetime.now() - timedelta(days=1),
                due_date=datetime.now() + timedelta(days=14),
                short_description="Active exploitation of Kubernetes API server privilege escalation vulnerability.",
                required_action="Apply patches per vendor instructions.",
                known_ransomware=False,
            ),
            CISAKEVRecord(
                cve_id="CVE-2025-0005",
                vendor_project="Amazon Web Services",
                product="AWS EKS",
                vulnerability_name="EKS Node IAM Role Escalation",
                date_added=datetime.now() - timedelta(days=3),
                due_date=datetime.now() + timedelta(days=21),
                short_description="IAM role assumption vulnerability in EKS node groups.",
                required_action="Update EKS node groups to latest AMI.",
                known_ransomware=False,
            ),
        ]

    # =========================================================================
    # GitHub Security Advisory API
    # =========================================================================

    async def fetch_github_advisories(
        self,
        ecosystem: str = "pip",
        severity: str | None = None,
    ) -> list[GitHubAdvisory]:
        """
        Fetch GitHub Security Advisories.

        Args:
            ecosystem: Package ecosystem (pip, npm, go, etc.)
            severity: Optional severity filter (low, medium, high, critical)

        Returns:
            List of GitHub advisory records
        """
        if self.mode == ThreatFeedMode.MOCK:
            return self._mock_github_advisories()

        cache_key = f"github:{ecosystem}:{severity or 'all'}"
        cached = self._check_cache(cache_key)
        if cached:
            return cast(list[GitHubAdvisory], cached)

        try:
            if not self._check_rate_limit("github"):
                logger.warning("GitHub rate limit reached, using cached/mock data")
                return self._mock_github_advisories()

            self._record_request("github")
            client = await self._get_client()

            params = {
                "ecosystem": ecosystem,
                "per_page": "50",
            }
            if severity:
                params["severity"] = severity

            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if self.config.github_token:
                headers["Authorization"] = f"Bearer {self.config.github_token}"

            response = await client.get(
                self.config.github_advisory_url, params=params, headers=headers
            )
            response.raise_for_status()

            data = response.json()
            advisories = self._parse_github_response(data)

            self._set_cache(cache_key, advisories)
            logger.info(f"Fetched {len(advisories)} advisories from GitHub")
            return advisories

        except Exception as e:
            logger.error(f"GitHub API error: {e}. Falling back to mock data.")
            return self._mock_github_advisories()

    def _parse_github_response(
        self, data: list[dict[str, Any]]
    ) -> list[GitHubAdvisory]:
        """Parse GitHub Advisory API response."""
        advisories = []
        for item in data:
            try:
                published_at = datetime.fromisoformat(
                    item.get("published_at", "").replace("Z", "+00:00")
                )
            except ValueError:
                published_at = datetime.now()

            # Get vulnerability info
            vulnerabilities = item.get("vulnerabilities", [])
            package_ecosystem = None
            package_name = None
            vulnerable_versions = None
            patched_versions = None

            if vulnerabilities:
                vuln = vulnerabilities[0]
                pkg = vuln.get("package", {})
                package_ecosystem = pkg.get("ecosystem")
                package_name = pkg.get("name")
                vulnerable_versions = vuln.get("vulnerable_version_range")
                patched_versions = vuln.get("patched_versions")

            # Get CVE ID from identifiers
            cve_id = None
            for identifier in item.get("identifiers", []):
                if identifier.get("type") == "CVE":
                    cve_id = identifier.get("value")
                    break

            advisories.append(
                GitHubAdvisory(
                    ghsa_id=item.get("ghsa_id", ""),
                    cve_id=cve_id,
                    summary=item.get("summary", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity", "unknown"),
                    published_at=published_at,
                    package_ecosystem=package_ecosystem,
                    package_name=package_name,
                    vulnerable_versions=vulnerable_versions,
                    patched_versions=patched_versions,
                    references=[r.get("url", "") for r in item.get("references", [])],
                )
            )

        return advisories

    def _mock_github_advisories(self) -> list[GitHubAdvisory]:
        """Return mock GitHub advisory data for testing."""
        return [
            GitHubAdvisory(
                ghsa_id="GHSA-xxxx-yyyy-zzzz",
                cve_id="CVE-2025-0006",
                summary="FastAPI dependency injection vulnerability",
                description="Improper input validation in FastAPI could allow injection attacks through dependency injection parameters.",
                severity="high",
                published_at=datetime.now() - timedelta(days=3),
                package_ecosystem="pip",
                package_name="fastapi",
                vulnerable_versions="<0.109.0",
                patched_versions=">=0.109.0",
                references=["https://github.com/advisories/GHSA-xxxx-yyyy-zzzz"],
            ),
            GitHubAdvisory(
                ghsa_id="GHSA-aaaa-bbbb-cccc",
                cve_id="CVE-2025-0007",
                summary="boto3 credential exposure",
                description="Boto3 may log sensitive credentials in debug mode under certain conditions.",
                severity="medium",
                published_at=datetime.now() - timedelta(days=7),
                package_ecosystem="pip",
                package_name="boto3",
                vulnerable_versions="<1.34.0",
                patched_versions=">=1.34.0",
                references=["https://github.com/advisories/GHSA-aaaa-bbbb-cccc"],
            ),
        ]


# Factory function
def create_threat_feed_client(
    use_mock: bool = False,
    config: ThreatFeedConfig | None = None,
) -> ThreatFeedClient:
    """
    Create and return a ThreatFeedClient instance.

    Args:
        use_mock: Force mock mode for testing
        config: Optional configuration overrides

    Returns:
        Configured ThreatFeedClient instance
    """
    if use_mock:
        mode = ThreatFeedMode.MOCK
    else:
        # Auto-detect: use REAL mode if httpx is available
        mode = ThreatFeedMode.REAL if HTTPX_AVAILABLE else ThreatFeedMode.MOCK

    return ThreatFeedClient(mode=mode, config=config)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    async def demo():
        print("Project Aura - Threat Feed Client Demo")
        print("=" * 60)

        client = create_threat_feed_client(use_mock=True)
        print(f"\nMode: {client.mode.value}")

        print("\n--- NVD CVEs ---")
        cves = await client.fetch_nvd_cves(days_back=7)
        for cve in cves[:3]:
            print(f"  {cve.cve_id}: {cve.title[:60]}... (CVSS: {cve.cvss_score})")

        print("\n--- CISA KEV ---")
        kev = await client.fetch_cisa_kev()
        for record in kev[:3]:
            print(f"  {record.cve_id}: {record.vulnerability_name[:50]}...")

        print("\n--- GitHub Advisories ---")
        advisories = await client.fetch_github_advisories(ecosystem="pip")
        for adv in advisories[:3]:
            print(f"  {adv.ghsa_id}: {adv.summary[:50]}... ({adv.severity})")

        await client.close()
        print("\n" + "=" * 60)
        print("Demo complete!")

    asyncio.run(demo())
