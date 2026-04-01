"""
Tests for DNS Blocklist Service

Tests the threat intelligence to DNS blocklist conversion pipeline.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.dns_blocklist_service import (
    BlocklistConfig,
    BlocklistEntry,
    BlocklistSource,
    BlocklistStats,
    DNSBlocklistService,
    ThreatCategory,
    create_blocklist_service,
)
from src.services.threat_feed_client import CVERecord, ThreatFeedClient, ThreatFeedMode


class TestBlocklistEntry:
    """Tests for BlocklistEntry dataclass."""

    def test_to_dnsmasq_entry(self):
        """Test dnsmasq address directive generation."""
        entry = BlocklistEntry(
            domain="malware.evil.com",
            source=BlocklistSource.NVD_CVE,
            category=ThreatCategory.MALWARE,
            severity="high",
        )

        assert entry.to_dnsmasq_entry() == "address=/malware.evil.com/0.0.0.0"

    def test_to_dnsmasq_comment(self):
        """Test dnsmasq comment generation with metadata."""
        entry = BlocklistEntry(
            domain="c2.botnet.io",
            source=BlocklistSource.ABUSE_CH,
            category=ThreatCategory.C2_COMMAND_CONTROL,
            threat_id="FEODO-12345",
            severity="critical",
        )

        comment = entry.to_dnsmasq_comment()
        assert "[CRITICAL]" in comment
        assert "c2" in comment
        assert "c2.botnet.io" in comment
        assert "abuse_ch" in comment
        assert "FEODO-12345" in comment

    def test_entry_defaults(self):
        """Test default values for BlocklistEntry."""
        entry = BlocklistEntry(
            domain="test.com",
            source=BlocklistSource.CUSTOM,
            category=ThreatCategory.MALWARE,
        )

        assert entry.severity == "medium"
        assert entry.threat_id is None
        assert entry.notes == ""
        assert entry.expires_date is None
        assert isinstance(entry.added_date, datetime)


class TestBlocklistConfig:
    """Tests for BlocklistConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BlocklistConfig()

        assert config.enable_nvd is True
        assert config.enable_cisa_kev is True
        assert config.enable_github is True
        assert config.enable_urlhaus is True
        assert config.enable_abuse_ch is True
        assert config.min_severity == "medium"
        assert config.block_ransomware is True
        assert config.max_entries == 10000
        assert config.include_comments is True
        assert config.include_metadata_header is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = BlocklistConfig(
            enable_nvd=False,
            enable_urlhaus=False,
            min_severity="high",
            max_entries=5000,
        )

        assert config.enable_nvd is False
        assert config.enable_urlhaus is False
        assert config.min_severity == "high"
        assert config.max_entries == 5000


class TestDNSBlocklistService:
    """Tests for DNSBlocklistService."""

    @pytest.fixture
    def mock_threat_client(self):
        """Create mock threat feed client."""
        client = MagicMock(spec=ThreatFeedClient)
        client.mode = ThreatFeedMode.MOCK
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def service(self, mock_threat_client):
        """Create service with mock client."""
        config = BlocklistConfig(
            enable_urlhaus=False,  # Disable external feeds for unit tests
            enable_abuse_ch=False,
        )
        return DNSBlocklistService(config=config, threat_client=mock_threat_client)

    def test_init(self, service):
        """Test service initialization."""
        assert service.config is not None
        assert service.threat_client is not None
        assert len(service.whitelist) > 0
        assert "google.com" in service.whitelist
        assert "amazonaws.com" in service.whitelist

    def test_is_valid_domain(self, service):
        """Test domain validation."""
        # Valid domains
        assert service._is_valid_domain("example.com") is True
        assert service._is_valid_domain("sub.example.com") is True
        assert service._is_valid_domain("deep.sub.example.com") is True
        assert service._is_valid_domain("example-hyphen.com") is True

        # Invalid domains
        assert service._is_valid_domain("") is False
        assert service._is_valid_domain("invalid") is False
        assert service._is_valid_domain("http://example.com") is False
        assert service._is_valid_domain("-invalid.com") is False
        assert service._is_valid_domain("a" * 300 + ".com") is False  # Too long

    def test_is_whitelisted(self, service):
        """Test whitelist checking."""
        # Direct match
        assert service._is_whitelisted("google.com") is True
        assert service._is_whitelisted("amazonaws.com") is True

        # Subdomain of whitelisted domain
        assert service._is_whitelisted("maps.google.com") is True
        assert service._is_whitelisted("s3.amazonaws.com") is True

        # Not whitelisted
        assert service._is_whitelisted("malware.evil.com") is False
        assert service._is_whitelisted("not-google.com") is False

    def test_severity_to_int(self, service):
        """Test severity string to integer conversion."""
        assert service._severity_to_int("low") == 1
        assert service._severity_to_int("medium") == 2
        assert service._severity_to_int("high") == 3
        assert service._severity_to_int("critical") == 4
        assert service._severity_to_int("unknown") == 0

    def test_meets_severity_threshold(self, service):
        """Test severity threshold checking."""
        # Default threshold is 'medium'
        assert service._meets_severity_threshold("critical") is True
        assert service._meets_severity_threshold("high") is True
        assert service._meets_severity_threshold("medium") is True
        assert service._meets_severity_threshold("low") is False

    def test_cvss_to_severity(self, service):
        """Test CVSS score to severity conversion."""
        assert service._cvss_to_severity(None) == "medium"
        assert service._cvss_to_severity(9.5) == "critical"
        assert service._cvss_to_severity(9.0) == "critical"
        assert service._cvss_to_severity(8.0) == "high"
        assert service._cvss_to_severity(7.0) == "high"
        assert service._cvss_to_severity(5.0) == "medium"
        assert service._cvss_to_severity(4.0) == "medium"
        assert service._cvss_to_severity(3.0) == "low"
        assert service._cvss_to_severity(0.0) == "low"

    def test_categorize_threat(self, service):
        """Test threat categorization from description."""
        assert (
            service._categorize_threat("Ransomware attack detected")
            == ThreatCategory.RANSOMWARE
        )
        assert (
            service._categorize_threat("Phishing campaign targeting users")
            == ThreatCategory.PHISHING
        )
        assert (
            service._categorize_threat("C2 command and control server")
            == ThreatCategory.C2_COMMAND_CONTROL
        )
        assert (
            service._categorize_threat("Cryptomining malware")
            == ThreatCategory.CRYPTOMINER
        )
        # Note: "Botnet infrastructure" matches botnet before c2/command
        assert (
            service._categorize_threat("Botnet infrastructure detected")
            == ThreatCategory.BOTNET
        )
        # "command server" matches C2 check before botnet (order matters)
        assert (
            service._categorize_threat("Botnet command server")
            == ThreatCategory.C2_COMMAND_CONTROL
        )
        assert (
            service._categorize_threat("Generic malicious activity")
            == ThreatCategory.MALWARE
        )

    def test_extract_domain_from_url(self, service):
        """Test domain extraction from URLs."""
        assert (
            service._extract_domain_from_url("https://malware.com/path")
            == "malware.com"
        )
        assert (
            service._extract_domain_from_url("http://evil.net:8080/page") == "evil.net"
        )
        assert (
            service._extract_domain_from_url("https://sub.domain.org")
            == "sub.domain.org"
        )
        assert service._extract_domain_from_url("invalid-url") is None
        assert service._extract_domain_from_url("") is None

    def test_has_malicious_indicator(self, service):
        """Test malicious indicator detection."""
        assert service._has_malicious_indicator(
            "https://malware.com", "Downloads malware payload"
        )
        assert service._has_malicious_indicator(
            "https://exploit.com", "Remote code execution exploit"
        )
        assert service._has_malicious_indicator(
            "https://c2.evil.com", "Command and control server"
        )
        assert not service._has_malicious_indicator(
            "https://safe.com", "Normal website description"
        )

    @pytest.mark.asyncio
    async def test_generate_blocklist_empty(self, service, mock_threat_client):
        """Test blocklist generation with no threats."""
        mock_threat_client.fetch_nvd_cves = AsyncMock(return_value=[])
        mock_threat_client.fetch_cisa_kev = AsyncMock(return_value=[])
        mock_threat_client.fetch_github_advisories = AsyncMock(return_value=[])

        entries = await service.generate_blocklist()

        assert isinstance(entries, list)
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_generate_blocklist_with_cves(self, service, mock_threat_client):
        """Test blocklist generation from CVE data."""
        mock_cve = CVERecord(
            cve_id="CVE-2025-0001",
            title="Malware distribution vulnerability",
            description="Remote code execution via malware payload download",
            cvss_score=9.8,
            published_date=datetime.now(timezone.utc),
            affected_products=["vulnerable-lib"],
            references=["https://malware-payload.evil.com/exploit"],
        )

        mock_threat_client.fetch_nvd_cves = AsyncMock(return_value=[mock_cve])
        mock_threat_client.fetch_cisa_kev = AsyncMock(return_value=[])
        mock_threat_client.fetch_github_advisories = AsyncMock(return_value=[])

        entries = await service.generate_blocklist()

        # Should extract domain from reference if malicious indicators present
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_generate_blocklist_deduplication(self, service, mock_threat_client):
        """Test that duplicate domains are removed."""
        mock_cves = [
            CVERecord(
                cve_id="CVE-2025-0001",
                title="First CVE",
                description="Malware payload",
                cvss_score=9.0,
                published_date=datetime.now(timezone.utc),
                references=["https://malware.evil.com/1"],
            ),
            CVERecord(
                cve_id="CVE-2025-0002",
                title="Second CVE",
                description="Also malware payload",
                cvss_score=8.0,
                published_date=datetime.now(timezone.utc),
                references=["https://malware.evil.com/2"],  # Same domain
            ),
        ]

        mock_threat_client.fetch_nvd_cves = AsyncMock(return_value=mock_cves)
        mock_threat_client.fetch_cisa_kev = AsyncMock(return_value=[])
        mock_threat_client.fetch_github_advisories = AsyncMock(return_value=[])

        entries = await service.generate_blocklist()

        # Same domain should appear only once
        domains = [e.domain for e in entries]
        assert len(domains) == len(set(domains))

    @pytest.mark.asyncio
    async def test_generate_blocklist_whitelisting(self, service, mock_threat_client):
        """Test that whitelisted domains are excluded."""
        # Mock CVE with reference to whitelisted domain
        mock_cve = CVERecord(
            cve_id="CVE-2025-0001",
            title="False positive",
            description="Malware affecting Google services",
            cvss_score=9.0,
            published_date=datetime.now(timezone.utc),
            references=["https://googleapis.com/malware"],  # Whitelisted
        )

        mock_threat_client.fetch_nvd_cves = AsyncMock(return_value=[mock_cve])
        mock_threat_client.fetch_cisa_kev = AsyncMock(return_value=[])
        mock_threat_client.fetch_github_advisories = AsyncMock(return_value=[])

        entries = await service.generate_blocklist()

        # googleapis.com should not be in blocklist
        domains = [e.domain for e in entries]
        assert "googleapis.com" not in domains

    def test_render_dnsmasq_config(self, service):
        """Test dnsmasq configuration rendering."""
        entries = [
            BlocklistEntry(
                domain="malware.com",
                source=BlocklistSource.NVD_CVE,
                category=ThreatCategory.MALWARE,
                threat_id="CVE-2025-0001",
                severity="critical",
            ),
            BlocklistEntry(
                domain="phishing.net",
                source=BlocklistSource.CISA_KEV,
                category=ThreatCategory.PHISHING,
                severity="high",
            ),
        ]

        service._update_stats(entries)
        config = service.render_dnsmasq_config(entries)

        # Check header
        assert "Project Aura - DNS Blocklist" in config
        assert "Auto-Generated" in config
        assert "Total Entries: 2" in config

        # Check entries
        assert "address=/malware.com/0.0.0.0" in config
        assert "address=/phishing.net/0.0.0.0" in config

        # Check comments
        assert "[CRITICAL]" in config
        assert "[HIGH]" in config
        assert "malware" in config.lower()
        assert "phishing" in config.lower()

    def test_render_dnsmasq_config_no_comments(self, service):
        """Test rendering without comments."""
        service.config.include_comments = False
        service.config.include_metadata_header = False

        entries = [
            BlocklistEntry(
                domain="test.com",
                source=BlocklistSource.CUSTOM,
                category=ThreatCategory.MALWARE,
            ),
        ]

        service._update_stats(entries)
        config = service.render_dnsmasq_config(entries)

        # Should have category header comment + address directive
        # (only per-entry comments are controlled by include_comments)
        lines = [line for line in config.strip().split("\n") if line.strip()]
        assert len(lines) == 2
        assert "MALWARE" in lines[0]  # Category header
        assert lines[1] == "address=/test.com/0.0.0.0"

    def test_get_stats(self, service):
        """Test statistics retrieval."""
        entries = [
            BlocklistEntry(
                domain="a.com",
                source=BlocklistSource.NVD_CVE,
                category=ThreatCategory.MALWARE,
                severity="critical",
            ),
            BlocklistEntry(
                domain="b.com",
                source=BlocklistSource.NVD_CVE,
                category=ThreatCategory.PHISHING,
                severity="high",
            ),
            BlocklistEntry(
                domain="c.com",
                source=BlocklistSource.ABUSE_CH,
                category=ThreatCategory.C2_COMMAND_CONTROL,
                severity="critical",
            ),
        ]

        service._update_stats(entries)
        stats = service.get_stats()

        assert stats["total_entries"] == 3
        assert stats["entries_by_source"]["nvd_cve"] == 2
        assert stats["entries_by_source"]["abuse_ch"] == 1
        assert stats["entries_by_category"]["malware"] == 1
        assert stats["entries_by_category"]["phishing"] == 1
        assert stats["entries_by_category"]["c2"] == 1
        assert stats["entries_by_severity"]["critical"] == 2
        assert stats["entries_by_severity"]["high"] == 1
        assert "config_hash" in stats
        assert "generation_time" in stats


class TestCreateBlocklistService:
    """Tests for factory function."""

    def test_create_with_defaults(self):
        """Test creating service with defaults."""
        service = create_blocklist_service(use_mock=True)

        assert service is not None
        assert isinstance(service, DNSBlocklistService)
        assert service.threat_client.mode == ThreatFeedMode.MOCK

    def test_create_with_custom_config(self):
        """Test creating service with custom config."""
        config = BlocklistConfig(
            min_severity="high",
            max_entries=1000,
        )

        service = create_blocklist_service(config=config, use_mock=True)

        assert service.config.min_severity == "high"
        assert service.config.max_entries == 1000


class TestBlocklistStats:
    """Tests for BlocklistStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = BlocklistStats()

        assert stats.total_entries == 0
        assert stats.entries_by_source == {}
        assert stats.entries_by_category == {}
        assert stats.entries_by_severity == {}
        assert stats.whitelisted_count == 0
        assert stats.duplicate_count == 0
        assert stats.config_hash == ""
        assert isinstance(stats.generation_time, datetime)


# Integration test (requires httpx)
class TestBlocklistServiceIntegration:
    """Integration tests for blocklist service with mock HTTP."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mock_mode(self):
        """Test complete blocklist generation pipeline in mock mode."""
        service = create_blocklist_service(use_mock=True)

        # Generate blocklist
        entries = await service.generate_blocklist()
        assert isinstance(entries, list)

        # Render config
        config = service.render_dnsmasq_config(entries)
        assert "Project Aura" in config

        # Get stats
        stats = service.get_stats()
        assert "total_entries" in stats

        # Cleanup
        await service.threat_client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
