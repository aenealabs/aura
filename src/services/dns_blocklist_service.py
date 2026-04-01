"""
Project Aura - DNS Blocklist Service

Generates dnsmasq-compatible blocklists from threat intelligence feeds.
Integrates with ThreatFeedClient for CVE data and external blocklist sources.

Features:
- Fetches malicious domains from multiple threat intelligence sources
- Maps CVE references to potentially malicious domains
- Generates dnsmasq configuration format
- Supports whitelisting to prevent false positives
- Provides metrics and audit logging for compliance
"""

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.services.threat_feed_client import (
    CISAKEVRecord,
    CVERecord,
    GitHubAdvisory,
    ThreatFeedClient,
    create_threat_feed_client,
)

logger = logging.getLogger(__name__)


class BlocklistSource(Enum):
    """Sources for DNS blocklist entries."""

    NVD_CVE = "nvd_cve"
    CISA_KEV = "cisa_kev"
    GITHUB_ADVISORY = "github_advisory"
    URLHAUS = "urlhaus"
    ABUSE_CH = "abuse_ch"
    CUSTOM = "custom"


class ThreatCategory(Enum):
    """Categories of threats for blocking."""

    MALWARE = "malware"
    PHISHING = "phishing"
    C2_COMMAND_CONTROL = "c2"
    CRYPTOMINER = "cryptominer"
    RANSOMWARE = "ransomware"
    BOTNET = "botnet"
    SPAM = "spam"
    ADWARE = "adware"


@dataclass
class BlocklistEntry:
    """A single domain blocklist entry with metadata."""

    domain: str
    source: BlocklistSource
    category: ThreatCategory
    threat_id: str | None = None  # CVE ID, GHSA ID, etc.
    severity: str = "medium"  # low, medium, high, critical
    added_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_date: datetime | None = None
    notes: str = ""

    def to_dnsmasq_entry(self) -> str:
        """Generate dnsmasq address directive."""
        return f"address=/{self.domain}/0.0.0.0"

    def to_dnsmasq_comment(self) -> str:
        """Generate dnsmasq comment with metadata."""
        return f"# [{self.severity.upper()}] {self.category.value}: {self.domain} (source: {self.source.value}, id: {self.threat_id or 'N/A'})"


@dataclass
class BlocklistConfig:
    """Configuration for blocklist generation."""

    # Sources to enable
    enable_nvd: bool = True
    enable_cisa_kev: bool = True
    enable_github: bool = True
    enable_urlhaus: bool = True
    enable_abuse_ch: bool = True

    # Filtering
    min_severity: str = "medium"  # Only block medium+ severity threats
    block_ransomware: bool = True  # Always block ransomware regardless of severity
    max_entries: int = 10000  # Maximum blocklist entries

    # URLhaus settings
    urlhaus_url: str = "https://urlhaus.abuse.ch/downloads/text/"
    urlhaus_recent_url: str = "https://urlhaus.abuse.ch/downloads/text_recent/"

    # Abuse.ch settings (Feodo Tracker for C2)
    abuse_ch_feodo_url: str = (
        "https://feodotracker.abuse.ch/downloads/domainblocklist.txt"
    )
    abuse_ch_ssl_url: str = "https://sslbl.abuse.ch/blacklist/sslipblacklist.txt"

    # Custom entries file
    custom_blocklist_file: str | None = None
    whitelist_file: str | None = None

    # Output settings
    include_comments: bool = True
    include_metadata_header: bool = True


@dataclass
class BlocklistStats:
    """Statistics about generated blocklist."""

    total_entries: int = 0
    entries_by_source: dict[str, int] = field(default_factory=dict)
    entries_by_category: dict[str, int] = field(default_factory=dict)
    entries_by_severity: dict[str, int] = field(default_factory=dict)
    whitelisted_count: int = 0
    duplicate_count: int = 0
    generation_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    config_hash: str = ""


class DNSBlocklistService:
    """
    Service for generating DNS blocklists from threat intelligence.

    Integrates with existing ThreatFeedClient and external blocklist sources
    to generate dnsmasq-compatible configuration files.

    Usage:
        >>> service = DNSBlocklistService()
        >>> blocklist = await service.generate_blocklist()
        >>> config_content = service.render_dnsmasq_config(blocklist)
        >>> service.write_config(config_content, "/etc/dnsmasq.d/blocklist.conf")
    """

    # Domain validation regex
    DOMAIN_REGEX = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+" r"[a-zA-Z]{2,}$"
    )

    # Known malicious domain patterns from CVE references
    MALICIOUS_INDICATORS = [
        "malware",
        "exploit",
        "payload",
        "c2",
        "command-and-control",
        "botnet",
        "ransomware",
        "phishing",
        "dropper",
    ]

    def __init__(
        self,
        config: BlocklistConfig | None = None,
        threat_client: ThreatFeedClient | None = None,
    ):
        """
        Initialize DNS blocklist service.

        Args:
            config: Optional blocklist configuration
            threat_client: Optional threat feed client (created if not provided)
        """
        self.config = config or BlocklistConfig()
        self.threat_client = threat_client or create_threat_feed_client(use_mock=False)

        # Whitelist domains (never block these)
        self.whitelist: set[str] = self._load_whitelist()

        # Statistics
        self.stats = BlocklistStats()

        logger.info("DNSBlocklistService initialized")

    def _load_whitelist(self) -> set[str]:
        """Load whitelisted domains from file or defaults."""
        whitelist = {
            # Critical infrastructure - never block
            "google.com",
            "googleapis.com",
            "amazon.com",
            "amazonaws.com",
            "aws.amazon.com",
            "microsoft.com",
            "azure.com",
            "github.com",
            "cloudflare.com",
            # Project Aura domains
            "aura.local",
            "aenealabs.com",
            # Common CDNs
            "cloudfront.net",
            "akamai.com",
            "fastly.com",
            # DNS providers
            "quad9.net",
        }

        if self.config.whitelist_file and os.path.exists(self.config.whitelist_file):
            try:
                with open(self.config.whitelist_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            whitelist.add(line.lower())
                logger.info(
                    f"Loaded {len(whitelist)} whitelist entries from {self.config.whitelist_file}"
                )
            except OSError as e:
                logger.warning(f"Failed to load whitelist file: {e}")

        return whitelist

    def _is_valid_domain(self, domain: str) -> bool:
        """Validate domain format."""
        if not domain or len(domain) > 253:
            return False
        return bool(self.DOMAIN_REGEX.match(domain))

    def _is_whitelisted(self, domain: str) -> bool:
        """Check if domain or parent domain is whitelisted."""
        domain_lower = domain.lower()

        # Direct match
        if domain_lower in self.whitelist:
            return True

        # Check parent domains
        parts = domain_lower.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[i:])
            if parent in self.whitelist:
                return True

        return False

    def _severity_to_int(self, severity: str) -> int:
        """Convert severity string to integer for comparison."""
        mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return mapping.get(severity.lower(), 0)

    def _meets_severity_threshold(self, severity: str) -> bool:
        """Check if severity meets minimum threshold."""
        return self._severity_to_int(severity) >= self._severity_to_int(
            self.config.min_severity
        )

    async def generate_blocklist(self) -> list[BlocklistEntry]:
        """
        Generate blocklist from all enabled sources.

        Returns:
            List of BlocklistEntry objects
        """
        entries: list[BlocklistEntry] = []
        seen_domains: set[str] = set()

        logger.info("Starting blocklist generation...")

        # Collect from all sources in parallel
        tasks = []
        if self.config.enable_nvd:
            tasks.append(self._collect_from_nvd())
        if self.config.enable_cisa_kev:
            tasks.append(self._collect_from_cisa_kev())
        if self.config.enable_github:
            tasks.append(self._collect_from_github())
        if self.config.enable_urlhaus:
            tasks.append(self._collect_from_urlhaus())
        if self.config.enable_abuse_ch:
            tasks.append(self._collect_from_abuse_ch())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error collecting blocklist entries: {result}")
                continue
            if isinstance(result, list):
                entries.extend(result)

        # Add custom entries
        custom_entries = self._load_custom_entries()
        entries.extend(custom_entries)

        # Deduplicate and filter
        filtered_entries = []
        for entry in entries:
            domain_lower = entry.domain.lower()

            # Skip invalid domains
            if not self._is_valid_domain(domain_lower):
                continue

            # Skip whitelisted
            if self._is_whitelisted(domain_lower):
                self.stats.whitelisted_count += 1
                continue

            # Skip duplicates
            if domain_lower in seen_domains:
                self.stats.duplicate_count += 1
                continue

            # Check severity threshold (ransomware always blocked)
            if not self._meets_severity_threshold(entry.severity):
                if not (
                    self.config.block_ransomware
                    and entry.category == ThreatCategory.RANSOMWARE
                ):
                    continue

            seen_domains.add(domain_lower)
            entry.domain = domain_lower
            filtered_entries.append(entry)

        # Limit entries
        if len(filtered_entries) > self.config.max_entries:
            # Sort by severity (highest first) and take top N
            filtered_entries.sort(
                key=lambda e: self._severity_to_int(e.severity), reverse=True
            )
            filtered_entries = filtered_entries[: self.config.max_entries]

        # Update statistics
        self._update_stats(filtered_entries)

        logger.info(f"Generated blocklist with {len(filtered_entries)} entries")
        return filtered_entries

    async def _collect_from_nvd(self) -> list[BlocklistEntry]:
        """Extract potentially malicious domains from NVD CVE references."""
        entries = []

        try:
            cves = await self.threat_client.fetch_nvd_cves(days_back=30)

            for cve in cves:
                domains = self._extract_domains_from_cve(cve)
                for domain, category in domains:
                    severity = self._cvss_to_severity(cve.cvss_score)
                    entries.append(
                        BlocklistEntry(
                            domain=domain,
                            source=BlocklistSource.NVD_CVE,
                            category=category,
                            threat_id=cve.cve_id,
                            severity=severity,
                            notes=cve.title[:100] if cve.title else "",
                        )
                    )

            logger.info(f"Collected {len(entries)} entries from NVD")
        except Exception as e:
            logger.error(f"NVD collection failed: {e}")

        return entries

    async def _collect_from_cisa_kev(self) -> list[BlocklistEntry]:
        """Extract domains from CISA KEV records."""
        entries = []

        try:
            kev_records = await self.threat_client.fetch_cisa_kev()

            for record in kev_records:
                domains = self._extract_domains_from_kev(record)
                for domain, category in domains:
                    entries.append(
                        BlocklistEntry(
                            domain=domain,
                            source=BlocklistSource.CISA_KEV,
                            category=category,
                            threat_id=record.cve_id,
                            severity="critical" if record.known_ransomware else "high",
                            notes=record.short_description[:100],
                        )
                    )

            logger.info(f"Collected {len(entries)} entries from CISA KEV")
        except Exception as e:
            logger.error(f"CISA KEV collection failed: {e}")

        return entries

    async def _collect_from_github(self) -> list[BlocklistEntry]:
        """Extract domains from GitHub Security Advisories."""
        entries = []

        try:
            advisories = await self.threat_client.fetch_github_advisories(
                ecosystem="pip", severity="critical"
            )
            advisories.extend(
                await self.threat_client.fetch_github_advisories(
                    ecosystem="npm", severity="critical"
                )
            )

            for advisory in advisories:
                domains = self._extract_domains_from_advisory(advisory)
                for domain, category in domains:
                    entries.append(
                        BlocklistEntry(
                            domain=domain,
                            source=BlocklistSource.GITHUB_ADVISORY,
                            category=category,
                            threat_id=advisory.ghsa_id,
                            severity=advisory.severity,
                            notes=advisory.summary[:100],
                        )
                    )

            logger.info(f"Collected {len(entries)} entries from GitHub")
        except Exception as e:
            logger.error(f"GitHub collection failed: {e}")

        return entries

    async def _collect_from_urlhaus(self) -> list[BlocklistEntry]:
        """Fetch malware distribution domains from URLhaus."""
        entries = []

        try:
            # Use httpx if available for async HTTP
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.config.urlhaus_recent_url)
                response.raise_for_status()

                for line in response.text.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # URLhaus format: URLs, extract domain
                        domain = self._extract_domain_from_url(line)
                        if domain:
                            entries.append(
                                BlocklistEntry(
                                    domain=domain,
                                    source=BlocklistSource.URLHAUS,
                                    category=ThreatCategory.MALWARE,
                                    severity="high",
                                    notes="URLhaus malware distribution",
                                )
                            )

            logger.info(f"Collected {len(entries)} entries from URLhaus")
        except ImportError:
            logger.warning("httpx not available for URLhaus fetch")
        except Exception as e:
            logger.error(f"URLhaus collection failed: {e}")

        return entries

    async def _collect_from_abuse_ch(self) -> list[BlocklistEntry]:
        """Fetch C2 domains from Abuse.ch Feodo Tracker."""
        entries = []

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.config.abuse_ch_feodo_url)
                response.raise_for_status()

                for line in response.text.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        domain = line
                        if self._is_valid_domain(domain):
                            entries.append(
                                BlocklistEntry(
                                    domain=domain,
                                    source=BlocklistSource.ABUSE_CH,
                                    category=ThreatCategory.C2_COMMAND_CONTROL,
                                    severity="critical",
                                    notes="Feodo Tracker C2 botnet",
                                )
                            )

            logger.info(f"Collected {len(entries)} entries from Abuse.ch")
        except ImportError:
            logger.warning("httpx not available for Abuse.ch fetch")
        except Exception as e:
            logger.error(f"Abuse.ch collection failed: {e}")

        return entries

    def _load_custom_entries(self) -> list[BlocklistEntry]:
        """Load custom blocklist entries from file."""
        entries: list[BlocklistEntry] = []

        if not self.config.custom_blocklist_file:
            return entries

        if not os.path.exists(self.config.custom_blocklist_file):
            return entries

        try:
            with open(self.config.custom_blocklist_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Format: domain,category,severity,notes
                        parts = line.split(",")
                        domain = parts[0].strip()

                        category = ThreatCategory.MALWARE
                        if len(parts) > 1:
                            try:
                                category = ThreatCategory(parts[1].strip().lower())
                            except ValueError:
                                pass

                        severity = "medium"
                        if len(parts) > 2:
                            severity = parts[2].strip().lower()

                        notes = ""
                        if len(parts) > 3:
                            notes = parts[3].strip()

                        entries.append(
                            BlocklistEntry(
                                domain=domain,
                                source=BlocklistSource.CUSTOM,
                                category=category,
                                severity=severity,
                                notes=notes,
                            )
                        )

            logger.info(
                f"Loaded {len(entries)} custom entries from {self.config.custom_blocklist_file}"
            )
        except OSError as e:
            logger.warning(f"Failed to load custom blocklist: {e}")

        return entries

    def _extract_domains_from_cve(
        self, cve: CVERecord
    ) -> list[tuple[str, ThreatCategory]]:
        """Extract potentially malicious domains from CVE references."""
        domains = []

        # Check references for malicious indicators
        for ref in cve.references:
            domain = self._extract_domain_from_url(ref)
            if domain and self._has_malicious_indicator(ref, cve.description):
                category = self._categorize_threat(cve.description)
                domains.append((domain, category))

        return domains

    def _extract_domains_from_kev(
        self, record: CISAKEVRecord
    ) -> list[tuple[str, ThreatCategory]]:
        """Extract domains from CISA KEV record."""
        # KEV records typically don't contain direct domain references
        # This is a placeholder for future IOC extraction
        return []

    def _extract_domains_from_advisory(
        self, advisory: GitHubAdvisory
    ) -> list[tuple[str, ThreatCategory]]:
        """Extract domains from GitHub advisory references."""
        domains = []

        for ref in advisory.references:
            domain = self._extract_domain_from_url(ref)
            if domain and self._has_malicious_indicator(ref, advisory.description):
                category = self._categorize_threat(advisory.description)
                domains.append((domain, category))

        return domains

    def _extract_domain_from_url(self, url: str) -> str | None:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if parsed.netloc:
                # Remove port if present
                domain = parsed.netloc.split(":")[0]
                return domain.lower() if self._is_valid_domain(domain) else None
        except Exception:
            pass
        return None

    def _has_malicious_indicator(self, url: str, description: str) -> bool:
        """Check if URL or description contains malicious indicators."""
        combined = f"{url} {description}".lower()
        return any(indicator in combined for indicator in self.MALICIOUS_INDICATORS)

    def _categorize_threat(self, description: str) -> ThreatCategory:
        """Categorize threat based on description."""
        desc_lower = description.lower()

        if "ransomware" in desc_lower:
            return ThreatCategory.RANSOMWARE
        if "phishing" in desc_lower:
            return ThreatCategory.PHISHING
        if "c2" in desc_lower or "command" in desc_lower:
            return ThreatCategory.C2_COMMAND_CONTROL
        if "cryptomin" in desc_lower or "mining" in desc_lower:
            return ThreatCategory.CRYPTOMINER
        if "botnet" in desc_lower:
            return ThreatCategory.BOTNET

        return ThreatCategory.MALWARE

    def _cvss_to_severity(self, cvss_score: float | None) -> str:
        """Convert CVSS score to severity string."""
        if cvss_score is None:
            return "medium"
        if cvss_score >= 9.0:
            return "critical"
        if cvss_score >= 7.0:
            return "high"
        if cvss_score >= 4.0:
            return "medium"
        return "low"

    def _update_stats(self, entries: list[BlocklistEntry]) -> None:
        """Update statistics from generated entries."""
        self.stats = BlocklistStats(
            total_entries=len(entries),
            entries_by_source={},
            entries_by_category={},
            entries_by_severity={},
            whitelisted_count=self.stats.whitelisted_count,
            duplicate_count=self.stats.duplicate_count,
            generation_time=datetime.now(timezone.utc),
        )

        for entry in entries:
            # By source
            source = entry.source.value
            self.stats.entries_by_source[source] = (
                self.stats.entries_by_source.get(source, 0) + 1
            )

            # By category
            category = entry.category.value
            self.stats.entries_by_category[category] = (
                self.stats.entries_by_category.get(category, 0) + 1
            )

            # By severity
            severity = entry.severity
            self.stats.entries_by_severity[severity] = (
                self.stats.entries_by_severity.get(severity, 0) + 1
            )

        # Generate config hash for change detection
        config_str = str(sorted(e.domain for e in entries))
        self.stats.config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def render_dnsmasq_config(
        self, entries: list[BlocklistEntry], include_stats: bool = True
    ) -> str:
        """
        Render blocklist entries as dnsmasq configuration.

        Args:
            entries: List of blocklist entries
            include_stats: Include statistics header

        Returns:
            dnsmasq configuration content as string
        """
        lines = []

        if self.config.include_metadata_header:
            lines.extend(
                [
                    "# ==========================================================================",
                    "# Project Aura - DNS Blocklist (Auto-Generated)",
                    "# ==========================================================================",
                    "#",
                    f"# Generated: {datetime.now(timezone.utc).isoformat()}",
                    f"# Config Hash: {self.stats.config_hash}",
                    f"# Total Entries: {self.stats.total_entries}",
                    "#",
                    "# Sources:",
                ]
            )

            for source, count in sorted(self.stats.entries_by_source.items()):
                lines.append(f"#   - {source}: {count}")

            lines.extend(
                [
                    "#",
                    "# Categories:",
                ]
            )

            for category, count in sorted(self.stats.entries_by_category.items()):
                lines.append(f"#   - {category}: {count}")

            lines.extend(
                [
                    "#",
                    "# Severity Distribution:",
                ]
            )

            for severity, count in sorted(
                self.stats.entries_by_severity.items(),
                key=lambda x: self._severity_to_int(x[0]),
                reverse=True,
            ):
                lines.append(f"#   - {severity}: {count}")

            lines.extend(
                [
                    "#",
                    f"# Whitelisted (excluded): {self.stats.whitelisted_count}",
                    f"# Duplicates (removed): {self.stats.duplicate_count}",
                    "#",
                    "# WARNING: This file is auto-generated. Do not edit manually.",
                    "# To add custom entries, use the custom blocklist file.",
                    "# To whitelist domains, add them to the whitelist file.",
                    "#",
                    "# ==========================================================================",
                    "",
                ]
            )

        # Group entries by category for readability
        entries_by_category: dict[ThreatCategory, list[BlocklistEntry]] = {}
        for entry in entries:
            if entry.category not in entries_by_category:
                entries_by_category[entry.category] = []
            entries_by_category[entry.category].append(entry)

        # Render each category section
        for category_enum in ThreatCategory:
            category_entries = entries_by_category.get(category_enum, [])
            if not category_entries:
                continue

            lines.extend(
                [
                    f"# --- {category_enum.value.upper()} ({len(category_entries)} entries) ---",
                ]
            )

            # Sort by severity within category
            category_entries.sort(
                key=lambda e: self._severity_to_int(e.severity), reverse=True
            )

            for entry in category_entries:
                if self.config.include_comments:
                    lines.append(entry.to_dnsmasq_comment())
                lines.append(entry.to_dnsmasq_entry())

            lines.append("")

        return "\n".join(lines)

    def write_config(self, content: str, output_path: str) -> bool:
        """
        Write dnsmasq configuration to file.

        Args:
            content: Configuration content
            output_path: Output file path

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write atomically via temp file
            temp_path = f"{output_path}.tmp"
            with open(temp_path, "w") as f:
                f.write(content)

            # Atomic rename
            os.rename(temp_path, output_path)

            logger.info(f"Wrote blocklist config to {output_path}")
            return True

        except OSError as e:
            logger.error(f"Failed to write config: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get current blocklist statistics as dictionary."""
        return {
            "total_entries": self.stats.total_entries,
            "entries_by_source": self.stats.entries_by_source,
            "entries_by_category": self.stats.entries_by_category,
            "entries_by_severity": self.stats.entries_by_severity,
            "whitelisted_count": self.stats.whitelisted_count,
            "duplicate_count": self.stats.duplicate_count,
            "generation_time": self.stats.generation_time.isoformat(),
            "config_hash": self.stats.config_hash,
        }


# Factory function
def create_blocklist_service(
    config: BlocklistConfig | None = None,
    use_mock: bool = False,
) -> DNSBlocklistService:
    """
    Create and return a DNSBlocklistService instance.

    Args:
        config: Optional blocklist configuration
        use_mock: Force mock mode for threat feed client

    Returns:
        Configured DNSBlocklistService instance
    """
    threat_client = create_threat_feed_client(use_mock=use_mock)
    return DNSBlocklistService(config=config, threat_client=threat_client)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    async def demo():
        print("Project Aura - DNS Blocklist Service Demo")
        print("=" * 60)

        # Create service with mock data
        service = create_blocklist_service(use_mock=True)
        print(f"\nWhitelist: {len(service.whitelist)} domains")

        # Generate blocklist
        print("\nGenerating blocklist...")
        entries = await service.generate_blocklist()
        print(f"Generated {len(entries)} entries")

        # Show stats
        stats = service.get_stats()
        print("\nStatistics:")
        print(f"  Total: {stats['total_entries']}")
        print(f"  By Source: {stats['entries_by_source']}")
        print(f"  By Category: {stats['entries_by_category']}")
        print(f"  By Severity: {stats['entries_by_severity']}")

        # Render config
        print("\n--- dnsmasq Configuration Preview ---")
        config = service.render_dnsmasq_config(entries)
        print(config[:2000])
        if len(config) > 2000:
            print(f"... ({len(config)} total characters)")

        # Close threat client
        await service.threat_client.close()

        print("\n" + "=" * 60)
        print("Demo complete!")

    asyncio.run(demo())
