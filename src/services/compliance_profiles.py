"""
Compliance Profile Management for Aura Platform.

Provides configurable security scanning behavior based on compliance requirements.
Supports CMMC Level 3, SOX, PCI-DSS, and development profiles.

Author: Aura Platform Team
Date: 2025-12-06
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ComplianceLevel(str, Enum):
    """Compliance profile types."""

    CMMC_LEVEL_3 = "CMMC_LEVEL_3"
    CMMC_LEVEL_2 = "CMMC_LEVEL_2"
    SOX = "SOX"
    PCI_DSS = "PCI_DSS"
    NIST_800_53 = "NIST_800_53"
    DEVELOPMENT = "DEVELOPMENT"
    CUSTOM = "CUSTOM"


class SeverityLevel(str, Enum):
    """Security finding severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class ScanningPolicy:
    """Defines what gets scanned and how."""

    # File path patterns to scan (glob patterns)
    included_paths: List[str] = field(default_factory=list)

    # File path patterns to exclude (glob patterns)
    excluded_paths: List[str] = field(default_factory=list)

    # Scan all changes regardless of path
    scan_all_changes: bool = True

    # Scan infrastructure code (CloudFormation, Terraform, Dockerfiles)
    scan_infrastructure: bool = True

    # Scan documentation files (*.md, *.rst)
    scan_documentation: bool = False

    # Scan configuration files (*.yaml, *.json, *.toml)
    scan_configuration: bool = True

    # Scan test files
    scan_tests: bool = True


@dataclass
class ReviewPolicy:
    """Defines manual review requirements."""

    # File types requiring manual HITL review
    require_manual_review: Set[str] = field(default_factory=set)

    # Block deployment on critical findings
    block_on_critical: bool = True

    # Block deployment on high findings
    block_on_high: bool = False

    # Minimum reviewers required for security changes
    min_reviewers: int = 1

    # Require security team approval for specific changes
    require_security_approval: Set[str] = field(default_factory=set)


@dataclass
class AuditPolicy:
    """Defines audit trail requirements."""

    # Log all scanning decisions
    log_scan_decisions: bool = True

    # Log all security findings
    log_findings: bool = True

    # Log manual review actions
    log_manual_reviews: bool = True

    # Retention period for audit logs (days)
    log_retention_days: int = 90

    # Include compliance profile in audit trail
    include_profile_metadata: bool = True


@dataclass
class ComplianceProfile:
    """Complete compliance profile configuration."""

    name: ComplianceLevel
    display_name: str
    description: str
    scanning: ScanningPolicy
    review: ReviewPolicy
    audit: AuditPolicy

    # CMMC/NIST/SOX control mappings
    control_mappings: Dict[str, List[str]] = field(default_factory=dict)

    # Additional metadata
    version: str = "1.0.0"
    last_updated: str = "2025-12-06"


class ComplianceProfileRegistry:
    """Registry of predefined compliance profiles."""

    @staticmethod
    def get_cmmc_level_3() -> ComplianceProfile:
        """
        CMMC Level 3 Profile.

        Most stringent security requirements for DoD contractors.
        Comprehensive scanning with strict review requirements.
        """
        return ComplianceProfile(
            name=ComplianceLevel.CMMC_LEVEL_3,
            display_name="CMMC Level 3 (Advanced/Progressive)",
            description="DoD CMMC Level 3 compliance - comprehensive security scanning for CUI protection",
            scanning=ScanningPolicy(
                included_paths=["**/*"],  # Scan everything
                excluded_paths=[
                    "archive/**",
                    "*.log",
                    "node_modules/**",
                    ".git/**",
                ],
                scan_all_changes=True,
                scan_infrastructure=True,
                scan_documentation=True,  # Docs can leak security info
                scan_configuration=True,
                scan_tests=True,
            ),
            review=ReviewPolicy(
                require_manual_review={
                    "iam_policies",
                    "network_configs",
                    "encryption_keys",
                    "access_controls",
                    "authentication",
                    "authorization",
                },
                block_on_critical=True,
                block_on_high=True,  # CMMC L3 blocks on high severity
                min_reviewers=2,  # Require 2 reviewers for CMMC L3
                require_security_approval={
                    "deploy/cloudformation/iam.yaml",
                    "deploy/cloudformation/vpc.yaml",
                    "deploy/cloudformation/security-*.yaml",
                },
            ),
            audit=AuditPolicy(
                log_scan_decisions=True,
                log_findings=True,
                log_manual_reviews=True,
                log_retention_days=365,  # CMMC requires 1 year retention
                include_profile_metadata=True,
            ),
            control_mappings={
                "AC": ["AC-3.1.1", "AC-3.1.2", "AC-3.1.3"],  # Access Control
                "CA": ["CA-3.12.1", "CA-3.12.2", "CA-3.12.4"],  # Assessment
                "CM": ["CM-3.4.7", "CM-3.4.9"],  # Configuration Management
                "IA": ["IA-3.5.1", "IA-3.5.2"],  # Identification & Authentication
                "RA": ["RA-3.11.2", "RA-3.11.3"],  # Risk Assessment
                "SI": ["SI-3.14.4", "SI-3.14.5"],  # System & Info Integrity
            },
        )

    @staticmethod
    def get_cmmc_level_2() -> ComplianceProfile:
        """
        CMMC Level 2 Profile.

        Moderate security requirements for basic CUI protection.
        """
        return ComplianceProfile(
            name=ComplianceLevel.CMMC_LEVEL_2,
            display_name="CMMC Level 2 (Managed)",
            description="DoD CMMC Level 2 compliance - moderate security scanning",
            scanning=ScanningPolicy(
                included_paths=["src/**", "deploy/**", "tests/**"],
                excluded_paths=["archive/**", "*.log", "node_modules/**"],
                scan_all_changes=True,
                scan_infrastructure=True,
                scan_documentation=False,  # Docs not required for L2
                scan_configuration=True,
                scan_tests=True,
            ),
            review=ReviewPolicy(
                require_manual_review={"iam_policies", "network_configs"},
                block_on_critical=True,
                block_on_high=False,
                min_reviewers=1,
                require_security_approval={"deploy/cloudformation/iam.yaml"},
            ),
            audit=AuditPolicy(
                log_scan_decisions=True,
                log_findings=True,
                log_manual_reviews=True,
                log_retention_days=90,
                include_profile_metadata=True,
            ),
            control_mappings={
                "AC": ["AC-2.1.1", "AC-2.1.2"],
                "CM": ["CM-2.4.7"],
                "IA": ["IA-2.5.1"],
            },
        )

    @staticmethod
    def get_sox() -> ComplianceProfile:
        """
        SOX Compliance Profile.

        Focus on financial data integrity and change management.
        """
        return ComplianceProfile(
            name=ComplianceLevel.SOX,
            display_name="SOX (Sarbanes-Oxley)",
            description="SOX compliance - financial controls and audit trails",
            scanning=ScanningPolicy(
                included_paths=[
                    "src/**",
                    "deploy/**",
                    "tests/**",
                    "database/**",
                ],
                excluded_paths=["archive/**", "*.log"],
                scan_all_changes=True,
                scan_infrastructure=True,
                scan_documentation=False,
                scan_configuration=True,
                scan_tests=True,
            ),
            review=ReviewPolicy(
                require_manual_review={
                    "database_schemas",
                    "financial_calculations",
                    "audit_logging",
                    "access_controls",
                },
                block_on_critical=True,
                block_on_high=True,  # SOX requires strict change control
                min_reviewers=2,  # SOX requires segregation of duties
                require_security_approval={
                    "src/services/billing/**",
                    "src/services/reporting/**",
                    "database/migrations/**",
                },
            ),
            audit=AuditPolicy(
                log_scan_decisions=True,
                log_findings=True,
                log_manual_reviews=True,
                log_retention_days=2555,  # SOX requires 7 years retention
                include_profile_metadata=True,
            ),
            control_mappings={
                "SOX-302": ["CEO/CFO Certification"],
                "SOX-404": ["Internal Controls Assessment"],
                "SOX-409": ["Real-time Disclosure"],
            },
        )

    @staticmethod
    def get_pci_dss() -> ComplianceProfile:
        """
        PCI-DSS Compliance Profile.

        Payment card industry data security standard.
        """
        return ComplianceProfile(
            name=ComplianceLevel.PCI_DSS,
            display_name="PCI-DSS v4.0",
            description="PCI-DSS compliance - payment card data protection",
            scanning=ScanningPolicy(
                included_paths=["src/**", "deploy/**", "tests/**"],
                excluded_paths=["archive/**", "*.log"],
                scan_all_changes=True,
                scan_infrastructure=True,
                scan_documentation=False,
                scan_configuration=True,
                scan_tests=True,
            ),
            review=ReviewPolicy(
                require_manual_review={
                    "payment_processing",
                    "cardholder_data",
                    "encryption_keys",
                    "network_configs",
                },
                block_on_critical=True,
                block_on_high=True,
                min_reviewers=1,
                require_security_approval={
                    "src/services/payment/**",
                    "deploy/cloudformation/pci-*.yaml",
                },
            ),
            audit=AuditPolicy(
                log_scan_decisions=True,
                log_findings=True,
                log_manual_reviews=True,
                log_retention_days=365,  # PCI requires 1 year retention
                include_profile_metadata=True,
            ),
            control_mappings={
                "PCI-1": ["Network Security Controls"],
                "PCI-2": ["Secure Configurations"],
                "PCI-3": ["Protect Cardholder Data"],
                "PCI-6": ["Secure Systems and Applications"],
            },
        )

    @staticmethod
    def get_nist_800_53() -> ComplianceProfile:
        """
        NIST 800-53 Compliance Profile.

        Federal information security standard.
        """
        return ComplianceProfile(
            name=ComplianceLevel.NIST_800_53,
            display_name="NIST 800-53 Rev 5",
            description="NIST 800-53 compliance - federal security controls",
            scanning=ScanningPolicy(
                included_paths=["**/*"],
                excluded_paths=["archive/**", "*.log", "node_modules/**"],
                scan_all_changes=True,
                scan_infrastructure=True,
                scan_documentation=True,
                scan_configuration=True,
                scan_tests=True,
            ),
            review=ReviewPolicy(
                require_manual_review={
                    "iam_policies",
                    "network_configs",
                    "encryption",
                    "access_controls",
                },
                block_on_critical=True,
                block_on_high=True,
                min_reviewers=2,
                require_security_approval={
                    "deploy/cloudformation/iam.yaml",
                    "deploy/cloudformation/security-*.yaml",
                },
            ),
            audit=AuditPolicy(
                log_scan_decisions=True,
                log_findings=True,
                log_manual_reviews=True,
                log_retention_days=365,
                include_profile_metadata=True,
            ),
            control_mappings={
                "AC": ["AC-1", "AC-2", "AC-3"],
                "AU": ["AU-1", "AU-2", "AU-3"],
                "CM": ["CM-1", "CM-2", "CM-3"],
                "IA": ["IA-1", "IA-2", "IA-3"],
                "RA": ["RA-1", "RA-2", "RA-3"],
                "SI": ["SI-1", "SI-2", "SI-3"],
            },
        )

    @staticmethod
    def get_development() -> ComplianceProfile:
        """
        Development Profile.

        Lightweight scanning for development environments.
        Optimizes for speed while maintaining basic security.
        """
        return ComplianceProfile(
            name=ComplianceLevel.DEVELOPMENT,
            display_name="Development (Fast)",
            description="Development profile - optimized for speed with basic security",
            scanning=ScanningPolicy(
                included_paths=["src/**/*.py", "tests/**/*.py"],
                excluded_paths=[
                    "archive/**",
                    "docs/**",
                    "*.md",
                    "*.log",
                    "node_modules/**",
                ],
                scan_all_changes=False,  # Only scan code changes
                scan_infrastructure=False,  # Skip infrastructure in dev
                scan_documentation=False,
                scan_configuration=False,
                scan_tests=False,  # Skip test files in dev
            ),
            review=ReviewPolicy(
                require_manual_review=set(),  # No manual reviews in dev
                block_on_critical=False,  # Warn only
                block_on_high=False,
                min_reviewers=0,
                require_security_approval=set(),
            ),
            audit=AuditPolicy(
                log_scan_decisions=False,
                log_findings=True,  # Still log findings for visibility
                log_manual_reviews=False,
                log_retention_days=30,
                include_profile_metadata=False,
            ),
            control_mappings={},
        )

    @classmethod
    def get_profile(cls, profile_name: ComplianceLevel) -> ComplianceProfile:
        """
        Retrieve a compliance profile by name.

        Args:
            profile_name: ComplianceLevel enum value

        Returns:
            ComplianceProfile instance

        Raises:
            ValueError: If profile name is not recognized
        """
        profile_map = {
            ComplianceLevel.CMMC_LEVEL_3: cls.get_cmmc_level_3,
            ComplianceLevel.CMMC_LEVEL_2: cls.get_cmmc_level_2,
            ComplianceLevel.SOX: cls.get_sox,
            ComplianceLevel.PCI_DSS: cls.get_pci_dss,
            ComplianceLevel.NIST_800_53: cls.get_nist_800_53,
            ComplianceLevel.DEVELOPMENT: cls.get_development,
        }

        if profile_name not in profile_map:
            raise ValueError(
                f"Unknown compliance profile: {profile_name}. "
                f"Available profiles: {list(profile_map.keys())}"
            )

        logger.info(f"Loading compliance profile: {profile_name}")
        return profile_map[profile_name]()

    @classmethod
    def list_profiles(cls) -> List[Dict[str, str]]:
        """
        List all available compliance profiles.

        Returns:
            List of profile metadata dictionaries
        """
        profiles = [
            cls.get_cmmc_level_3(),
            cls.get_cmmc_level_2(),
            cls.get_sox(),
            cls.get_pci_dss(),
            cls.get_nist_800_53(),
            cls.get_development(),
        ]

        return [
            {
                "name": profile.name.value,
                "display_name": profile.display_name,
                "description": profile.description,
                "version": profile.version,
            }
            for profile in profiles
        ]


class ComplianceProfileManager:
    """
    Manages compliance profile selection and application.

    Handles profile loading, validation, and custom overrides.
    """

    def __init__(self, profile_name: Optional[ComplianceLevel] = None) -> None:
        """
        Initialize ComplianceProfileManager.

        Args:
            profile_name: Default compliance profile to use
        """
        self.default_profile = (
            profile_name or ComplianceLevel.CMMC_LEVEL_3
        )  # Default to most stringent
        self._current_profile: Optional[ComplianceProfile] = None
        self._custom_overrides: Dict = {}

    def load_profile(
        self, profile_name: Optional[ComplianceLevel] = None
    ) -> ComplianceProfile:
        """
        Load a compliance profile.

        Args:
            profile_name: Profile to load (uses default if None)

        Returns:
            ComplianceProfile instance
        """
        name = profile_name or self.default_profile
        self._current_profile = ComplianceProfileRegistry.get_profile(name)
        logger.info(f"Loaded compliance profile: {self._current_profile.display_name}")
        return self._current_profile

    def apply_overrides(self, overrides: Dict) -> None:
        """
        Apply custom overrides to the current profile.

        Args:
            overrides: Dictionary of profile overrides

        Example:
            manager.apply_overrides({
                'scanning.scan_documentation': True,
                'review.min_reviewers': 3
            })
        """
        if not self._current_profile:
            raise RuntimeError("No profile loaded. Call load_profile() first.")

        self._custom_overrides = overrides
        logger.info(f"Applied {len(overrides)} custom overrides to profile")

        # Apply overrides to current profile
        for key, value in overrides.items():
            parts = key.split(".")
            if len(parts) != 2:
                logger.warning(f"Invalid override key: {key}")
                continue

            section, field = parts
            if hasattr(self._current_profile, section):
                section_obj = getattr(self._current_profile, section)
                if hasattr(section_obj, field):
                    setattr(section_obj, field, value)
                    logger.debug(f"Override applied: {key} = {value}")

    def get_current_profile(self) -> ComplianceProfile:
        """
        Get the currently active compliance profile.

        Returns:
            Active ComplianceProfile instance

        Raises:
            RuntimeError: If no profile is loaded
        """
        if not self._current_profile:
            # Auto-load default profile
            self.load_profile()

        if self._current_profile is None:
            raise RuntimeError("No compliance profile loaded")
        return self._current_profile

    def should_scan_file(self, file_path: str) -> bool:
        """
        Determine if a file should be scanned based on the current profile.

        Args:
            file_path: Path to the file

        Returns:
            True if file should be scanned
        """
        profile = self.get_current_profile()
        scanning = profile.scanning

        # Check if scan_all_changes is enabled
        if scanning.scan_all_changes:
            # Check exclusions
            for pattern in scanning.excluded_paths:
                # Simple glob matching (can be enhanced with fnmatch)
                if pattern.replace("**", "") in file_path:
                    return False
            return True

        # Check inclusions
        for pattern in scanning.included_paths:
            if pattern.replace("**", "") in file_path:
                # Check exclusions
                for exclude_pattern in scanning.excluded_paths:
                    if exclude_pattern.replace("**", "") in file_path:
                        return False
                return True

        return False

    def get_severity_threshold(self) -> SeverityLevel:
        """
        Get the severity threshold for blocking deployments.

        Returns:
            Minimum severity level that blocks deployment
        """
        profile = self.get_current_profile()
        review = profile.review

        if review.block_on_critical:
            if review.block_on_high:
                return SeverityLevel.HIGH
            return SeverityLevel.CRITICAL

        return SeverityLevel.CRITICAL  # Default to critical only

    def requires_manual_review(self, change_type: str) -> bool:
        """
        Check if a change type requires manual HITL review.

        Args:
            change_type: Type of change (e.g., 'iam_policies', 'network_configs')

        Returns:
            True if manual review is required
        """
        profile = self.get_current_profile()
        return change_type in profile.review.require_manual_review

    def get_audit_metadata(self) -> Dict[str, Any]:
        """
        Get audit trail metadata for the current profile.

        Returns:
            Dictionary of audit metadata
        """
        profile = self.get_current_profile()

        if not profile.audit.include_profile_metadata:
            return {}

        return {
            "compliance_profile": profile.name.value,
            "profile_display_name": profile.display_name,
            "profile_version": profile.version,
            "control_mappings": profile.control_mappings,
            "scan_all_changes": profile.scanning.scan_all_changes,
            "block_on_critical": profile.review.block_on_critical,
            "block_on_high": profile.review.block_on_high,
            "min_reviewers": profile.review.min_reviewers,
            "custom_overrides": self._custom_overrides,
        }
