"""
Project Aura - License Compliance Engine

Provides license identification, compliance checking, and attribution generation
for software supply chain security.

Usage:
    from src.services.supply_chain import (
        LicenseComplianceEngine,
        get_license_compliance_engine,
    )

    engine = get_license_compliance_engine()
    report = engine.check_compliance(sbom, policy)

    if report.status == ComplianceStatus.VIOLATION:
        for violation in report.violations:
            print(f"VIOLATION: {violation.component_name} - {violation.detected_license}")

Compliance:
- SPDX License List: Standard license identifiers
- OSI Approved: Open Source Initiative approved licenses
- FSF Free: Free Software Foundation approved licenses
- NTIA SBOM: License information requirements
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .config import LicenseComplianceConfig, get_supply_chain_config
from .contracts import (
    ComplianceReport,
    ComplianceStatus,
    LicenseCategory,
    LicenseInfo,
    LicensePolicy,
    LicenseViolation,
    RiskLevel,
    SBOMComponent,
    SBOMDocument,
)
from .exceptions import LicenseIdentificationError, PolicyViolationError
from .metrics import MetricsTimer, get_supply_chain_metrics

logger = logging.getLogger(__name__)


@dataclass
class SPDXLicense:
    """SPDX license metadata."""

    id: str
    name: str
    category: LicenseCategory
    osi_approved: bool = False
    fsf_free: bool = False
    copyleft: bool = False
    patent_grant: bool = False
    attribution_required: bool = True
    share_alike: bool = False
    url: Optional[str] = None


# SPDX License Database (subset of most common licenses)
SPDX_LICENSES: dict[str, SPDXLicense] = {
    # Permissive Licenses
    "MIT": SPDXLicense(
        id="MIT",
        name="MIT License",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        url="https://opensource.org/licenses/MIT",
    ),
    "Apache-2.0": SPDXLicense(
        id="Apache-2.0",
        name="Apache License 2.0",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        patent_grant=True,
        url="https://opensource.org/licenses/Apache-2.0",
    ),
    "BSD-2-Clause": SPDXLicense(
        id="BSD-2-Clause",
        name="BSD 2-Clause License",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        url="https://opensource.org/licenses/BSD-2-Clause",
    ),
    "BSD-3-Clause": SPDXLicense(
        id="BSD-3-Clause",
        name="BSD 3-Clause License",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        url="https://opensource.org/licenses/BSD-3-Clause",
    ),
    "ISC": SPDXLicense(
        id="ISC",
        name="ISC License",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        url="https://opensource.org/licenses/ISC",
    ),
    "Unlicense": SPDXLicense(
        id="Unlicense",
        name="The Unlicense",
        category=LicenseCategory.PUBLIC_DOMAIN,
        osi_approved=True,
        fsf_free=True,
        attribution_required=False,
        url="https://unlicense.org/",
    ),
    "CC0-1.0": SPDXLicense(
        id="CC0-1.0",
        name="Creative Commons Zero v1.0 Universal",
        category=LicenseCategory.PUBLIC_DOMAIN,
        osi_approved=False,
        fsf_free=True,
        attribution_required=False,
        url="https://creativecommons.org/publicdomain/zero/1.0/",
    ),
    "0BSD": SPDXLicense(
        id="0BSD",
        name="BSD Zero Clause License",
        category=LicenseCategory.PUBLIC_DOMAIN,
        osi_approved=True,
        fsf_free=True,
        attribution_required=False,
        url="https://opensource.org/licenses/0BSD",
    ),
    "Zlib": SPDXLicense(
        id="Zlib",
        name="zlib License",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        url="https://opensource.org/licenses/Zlib",
    ),
    "BSL-1.0": SPDXLicense(
        id="BSL-1.0",
        name="Boost Software License 1.0",
        category=LicenseCategory.PERMISSIVE,
        osi_approved=True,
        fsf_free=True,
        url="https://opensource.org/licenses/BSL-1.0",
    ),
    # Weak Copyleft Licenses
    "LGPL-2.1-only": SPDXLicense(
        id="LGPL-2.1-only",
        name="GNU Lesser General Public License v2.1 only",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        url="https://opensource.org/licenses/LGPL-2.1",
    ),
    "LGPL-2.1-or-later": SPDXLicense(
        id="LGPL-2.1-or-later",
        name="GNU Lesser General Public License v2.1 or later",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        url="https://opensource.org/licenses/LGPL-2.1",
    ),
    "LGPL-3.0-only": SPDXLicense(
        id="LGPL-3.0-only",
        name="GNU Lesser General Public License v3.0 only",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        url="https://opensource.org/licenses/LGPL-3.0",
    ),
    "LGPL-3.0-or-later": SPDXLicense(
        id="LGPL-3.0-or-later",
        name="GNU Lesser General Public License v3.0 or later",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        url="https://opensource.org/licenses/LGPL-3.0",
    ),
    "MPL-2.0": SPDXLicense(
        id="MPL-2.0",
        name="Mozilla Public License 2.0",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        patent_grant=True,
        share_alike=True,
        url="https://opensource.org/licenses/MPL-2.0",
    ),
    "EPL-2.0": SPDXLicense(
        id="EPL-2.0",
        name="Eclipse Public License 2.0",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        patent_grant=True,
        url="https://opensource.org/licenses/EPL-2.0",
    ),
    "CDDL-1.0": SPDXLicense(
        id="CDDL-1.0",
        name="Common Development and Distribution License 1.0",
        category=LicenseCategory.WEAK_COPYLEFT,
        osi_approved=True,
        fsf_free=False,
        copyleft=True,
        patent_grant=True,
        url="https://opensource.org/licenses/CDDL-1.0",
    ),
    # Strong Copyleft Licenses
    "GPL-2.0-only": SPDXLicense(
        id="GPL-2.0-only",
        name="GNU General Public License v2.0 only",
        category=LicenseCategory.STRONG_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        share_alike=True,
        url="https://opensource.org/licenses/GPL-2.0",
    ),
    "GPL-2.0-or-later": SPDXLicense(
        id="GPL-2.0-or-later",
        name="GNU General Public License v2.0 or later",
        category=LicenseCategory.STRONG_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        share_alike=True,
        url="https://opensource.org/licenses/GPL-2.0",
    ),
    "GPL-3.0-only": SPDXLicense(
        id="GPL-3.0-only",
        name="GNU General Public License v3.0 only",
        category=LicenseCategory.STRONG_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        patent_grant=True,
        share_alike=True,
        url="https://opensource.org/licenses/GPL-3.0",
    ),
    "GPL-3.0-or-later": SPDXLicense(
        id="GPL-3.0-or-later",
        name="GNU General Public License v3.0 or later",
        category=LicenseCategory.STRONG_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        patent_grant=True,
        share_alike=True,
        url="https://opensource.org/licenses/GPL-3.0",
    ),
    "AGPL-3.0-only": SPDXLicense(
        id="AGPL-3.0-only",
        name="GNU Affero General Public License v3.0 only",
        category=LicenseCategory.STRONG_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        patent_grant=True,
        share_alike=True,
        url="https://opensource.org/licenses/AGPL-3.0",
    ),
    "AGPL-3.0-or-later": SPDXLicense(
        id="AGPL-3.0-or-later",
        name="GNU Affero General Public License v3.0 or later",
        category=LicenseCategory.STRONG_COPYLEFT,
        osi_approved=True,
        fsf_free=True,
        copyleft=True,
        patent_grant=True,
        share_alike=True,
        url="https://opensource.org/licenses/AGPL-3.0",
    ),
    # Proprietary / Commercial
    "BUSL-1.1": SPDXLicense(
        id="BUSL-1.1",
        name="Business Source License 1.1",
        category=LicenseCategory.PROPRIETARY,
        osi_approved=False,
        fsf_free=False,
        url="https://mariadb.com/bsl11/",
    ),
    "Proprietary": SPDXLicense(
        id="Proprietary",
        name="Proprietary License",
        category=LicenseCategory.PROPRIETARY,
        osi_approved=False,
        fsf_free=False,
    ),
    # Unknown
    "NOASSERTION": SPDXLicense(
        id="NOASSERTION",
        name="No License Assertion",
        category=LicenseCategory.UNKNOWN,
        osi_approved=False,
        fsf_free=False,
    ),
}

# License aliases and common variations
LICENSE_ALIASES: dict[str, str] = {
    "MIT License": "MIT",
    "The MIT License": "MIT",
    "Apache License 2.0": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "Apache License, Version 2.0": "Apache-2.0",
    "BSD": "BSD-3-Clause",
    "BSD License": "BSD-3-Clause",
    "BSD-2": "BSD-2-Clause",
    "BSD-3": "BSD-3-Clause",
    "Simplified BSD": "BSD-2-Clause",
    "New BSD": "BSD-3-Clause",
    "GPL": "GPL-3.0-only",
    "GPL v2": "GPL-2.0-only",
    "GPL v3": "GPL-3.0-only",
    "GPLv2": "GPL-2.0-only",
    "GPLv3": "GPL-3.0-only",
    "LGPL": "LGPL-3.0-only",
    "LGPLv2": "LGPL-2.1-only",
    "LGPLv2.1": "LGPL-2.1-only",
    "LGPLv3": "LGPL-3.0-only",
    "AGPL": "AGPL-3.0-only",
    "AGPLv3": "AGPL-3.0-only",
    "MPL": "MPL-2.0",
    "Mozilla Public License": "MPL-2.0",
    "ISC License": "ISC",
    "CC0": "CC0-1.0",
    "Public Domain": "Unlicense",
    "Zlib License": "Zlib",
}

# Pre-computed lowercase lookup dicts for O(1) case-insensitive matching
_SPDX_LOWER: dict[str, str] = {k.lower(): k for k in SPDX_LICENSES}
_ALIAS_LOWER: dict[str, str] = {k.lower(): v for k, v in LICENSE_ALIASES.items()}


@dataclass
class CompatibilityResult:
    """Result of license compatibility check."""

    compatible: bool
    primary_license: str
    secondary_license: str
    reason: str
    allows_proprietary: bool = False


# License compatibility matrix (simplified)
# True = compatible, False = incompatible, None = requires review
COMPATIBILITY_MATRIX: dict[LicenseCategory, dict[LicenseCategory, Optional[bool]]] = {
    LicenseCategory.PUBLIC_DOMAIN: {
        LicenseCategory.PUBLIC_DOMAIN: True,
        LicenseCategory.PERMISSIVE: True,
        LicenseCategory.WEAK_COPYLEFT: True,
        LicenseCategory.STRONG_COPYLEFT: True,
        LicenseCategory.PROPRIETARY: True,
        LicenseCategory.UNKNOWN: None,
    },
    LicenseCategory.PERMISSIVE: {
        LicenseCategory.PUBLIC_DOMAIN: True,
        LicenseCategory.PERMISSIVE: True,
        LicenseCategory.WEAK_COPYLEFT: True,
        LicenseCategory.STRONG_COPYLEFT: True,
        LicenseCategory.PROPRIETARY: True,
        LicenseCategory.UNKNOWN: None,
    },
    LicenseCategory.WEAK_COPYLEFT: {
        LicenseCategory.PUBLIC_DOMAIN: True,
        LicenseCategory.PERMISSIVE: True,
        LicenseCategory.WEAK_COPYLEFT: True,
        LicenseCategory.STRONG_COPYLEFT: None,  # Depends on specific licenses
        LicenseCategory.PROPRIETARY: False,
        LicenseCategory.UNKNOWN: None,
    },
    LicenseCategory.STRONG_COPYLEFT: {
        LicenseCategory.PUBLIC_DOMAIN: True,
        LicenseCategory.PERMISSIVE: True,
        LicenseCategory.WEAK_COPYLEFT: None,  # Depends on specific licenses
        LicenseCategory.STRONG_COPYLEFT: None,  # GPL-2 vs GPL-3 issues
        LicenseCategory.PROPRIETARY: False,
        LicenseCategory.UNKNOWN: None,
    },
    LicenseCategory.PROPRIETARY: {
        LicenseCategory.PUBLIC_DOMAIN: True,
        LicenseCategory.PERMISSIVE: True,
        LicenseCategory.WEAK_COPYLEFT: False,
        LicenseCategory.STRONG_COPYLEFT: False,
        LicenseCategory.PROPRIETARY: None,  # Depends on specific terms
        LicenseCategory.UNKNOWN: None,
    },
    LicenseCategory.UNKNOWN: {
        LicenseCategory.PUBLIC_DOMAIN: None,
        LicenseCategory.PERMISSIVE: None,
        LicenseCategory.WEAK_COPYLEFT: None,
        LicenseCategory.STRONG_COPYLEFT: None,
        LicenseCategory.PROPRIETARY: None,
        LicenseCategory.UNKNOWN: None,
    },
}


class LicenseComplianceEngine:
    """
    Engine for checking license compliance in software supply chains.

    Provides:
    - License identification from SPDX identifiers
    - Policy-based compliance checking
    - Attribution file generation
    - License compatibility analysis
    """

    def __init__(
        self,
        config: Optional[LicenseComplianceConfig] = None,
    ):
        """Initialize the engine.

        Args:
            config: License compliance configuration
        """
        if config is None:
            config = get_supply_chain_config().license
        self.config = config

        # License cache
        self._license_cache: dict[str, LicenseInfo] = {}

        logger.info(
            f"LicenseComplianceEngine initialized "
            f"(enabled={config.enabled}, policy={config.default_policy})"
        )

    # -------------------------------------------------------------------------
    # Main Compliance Methods
    # -------------------------------------------------------------------------

    def check_compliance(
        self,
        sbom: SBOMDocument,
        policy: Optional[LicensePolicy] = None,
    ) -> ComplianceReport:
        """Check license compliance for all components in an SBOM.

        Args:
            sbom: SBOM document to check
            policy: License policy (uses default if None)

        Returns:
            Compliance report with violations and status
        """
        if not self.config.enabled:
            logger.debug("License compliance checking disabled")
            return ComplianceReport(
                report_id=f"report-disabled-{sbom.sbom_id}",
                repository_id=sbom.repository_id,
                sbom_id=sbom.sbom_id,
                status=ComplianceStatus.UNKNOWN,
                components_analyzed=0,
                violations=[],
                components_compliant=0,
                policy_applied=None,
            )

        if policy is None:
            policy = self._get_default_policy()

        metrics = get_supply_chain_metrics()
        violations: list[LicenseViolation] = []
        compliant_count = 0
        unknown_count = 0

        with MetricsTimer() as timer:
            for component in sbom.components:
                try:
                    violation = self._check_component_compliance(component, policy)
                    if violation:
                        violations.append(violation)
                    else:
                        # Check if license is unknown
                        license_info = self.identify_license(
                            component.licenses[0] if component.licenses else None
                        )
                        if license_info.category == LicenseCategory.UNKNOWN:
                            unknown_count += 1
                        else:
                            compliant_count += 1
                except LicenseIdentificationError:
                    unknown_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to check compliance for {component.name}: {e}"
                    )
                    unknown_count += 1

        # Determine overall status
        if violations:
            status = ComplianceStatus.VIOLATION
        elif unknown_count > 0 and not self.config.allow_unknown_licenses:
            status = ComplianceStatus.WARNING
        else:
            status = ComplianceStatus.COMPLIANT

        # Record metrics
        metrics.record_license_check(
            component_count=len(sbom.components),
            violations_found=len(violations),
            compliance_status=status.value,
            latency_ms=timer.elapsed_ms,
        )

        # Record individual violations
        for violation in violations:
            metrics.record_license_violation(
                license_id=violation.detected_license,
                violation_type=violation.violation_type,
                severity=violation.severity,
            )

        logger.info(
            f"Compliance check complete: {status.value} "
            f"({compliant_count} compliant, {len(violations)} violations, "
            f"{unknown_count} unknown)"
        )

        return ComplianceReport(
            report_id=f"report-{sbom.sbom_id}",
            repository_id=sbom.repository_id,
            sbom_id=sbom.sbom_id,
            status=status,
            violations=violations,
            components_analyzed=len(sbom.components),
            components_compliant=compliant_count,
            policy_applied=policy.name if policy else None,
        )

    def identify_license(
        self,
        license_text: Optional[str],
    ) -> LicenseInfo:
        """Identify and categorize a license from its SPDX identifier or text.

        Args:
            license_text: SPDX identifier or license text

        Returns:
            LicenseInfo with identified license details
        """
        if not license_text:
            return LicenseInfo(
                spdx_id="NOASSERTION",
                name="No License Specified",
                category=LicenseCategory.UNKNOWN,
                osi_approved=False,
                fsf_free=False,
            )

        # Check cache
        if license_text in self._license_cache:
            return self._license_cache[license_text]

        # Normalize and look up
        normalized = self._normalize_license_id(license_text)

        # Check SPDX database
        if normalized in SPDX_LICENSES:
            spdx = SPDX_LICENSES[normalized]
            info = LicenseInfo(
                spdx_id=spdx.id,
                name=spdx.name,
                category=spdx.category,
                osi_approved=spdx.osi_approved,
                fsf_free=spdx.fsf_free,
                copyleft=spdx.copyleft,
                url=spdx.url,
            )
            self._license_cache[license_text] = info
            return info

        # Check aliases
        if normalized in LICENSE_ALIASES:
            aliased = LICENSE_ALIASES[normalized]
            return self.identify_license(aliased)

        # Check if it's a license expression (e.g., "MIT OR Apache-2.0")
        if " OR " in license_text.upper() or " AND " in license_text.upper():
            return self._parse_license_expression(license_text)

        # Unknown license
        return LicenseInfo(
            spdx_id=license_text,
            name=license_text,
            category=LicenseCategory.UNKNOWN,
            osi_approved=False,
            fsf_free=False,
        )

    def generate_attribution(
        self,
        sbom: SBOMDocument,
        format: str = "markdown",
    ) -> str:
        """Generate an attribution/NOTICE file for the SBOM.

        Args:
            sbom: SBOM document
            format: Output format (markdown, text, html)

        Returns:
            Attribution text in requested format
        """
        metrics = get_supply_chain_metrics()

        with MetricsTimer() as timer:
            if format == "markdown":
                result = self._generate_markdown_attribution(sbom)
            elif format == "html":
                result = self._generate_html_attribution(sbom)
            else:
                result = self._generate_text_attribution(sbom)

        metrics.record_attribution_generated(
            component_count=len(sbom.components),
            format_type=format,
            latency_ms=timer.elapsed_ms,
        )

        return result

    def check_compatibility(
        self,
        licenses: list[str],
        target_license: Optional[str] = None,
    ) -> CompatibilityResult:
        """Check if a set of licenses are compatible with each other.

        Args:
            licenses: List of SPDX license identifiers
            target_license: Target license for the combined work (optional)

        Returns:
            CompatibilityResult with compatibility assessment
        """
        if not licenses:
            return CompatibilityResult(
                compatible=True,
                primary_license="None",
                secondary_license="None",
                reason="No licenses to check",
                allows_proprietary=True,
            )

        # Identify all licenses
        license_infos = [self.identify_license(lic) for lic in licenses]

        # Find the most restrictive category
        categories = [info.category for info in license_infos]
        category_order = [
            LicenseCategory.PUBLIC_DOMAIN,
            LicenseCategory.PERMISSIVE,
            LicenseCategory.WEAK_COPYLEFT,
            LicenseCategory.STRONG_COPYLEFT,
            LicenseCategory.PROPRIETARY,
            LicenseCategory.UNKNOWN,
        ]

        most_restrictive = max(categories, key=lambda c: category_order.index(c))

        # Check compatibility matrix - group by category to reduce pairwise checks
        from collections import defaultdict

        by_category: dict[LicenseCategory, list] = defaultdict(list)
        for info in license_infos:
            by_category[info.category].append(info)

        # Only check cross-category pairs (same category is always compatible)
        incompatible_pairs: list[tuple[str, str]] = []
        category_list = list(by_category.keys())
        for ci, cat1 in enumerate(category_list):
            for cat2 in category_list[ci + 1 :]:
                compat = COMPATIBILITY_MATRIX.get(cat1, {}).get(cat2, None)
                if compat is False:
                    # Report first incompatible pair from these categories
                    info1 = by_category[cat1][0]
                    info2 = by_category[cat2][0]
                    incompatible_pairs.append((info1.spdx_id, info2.spdx_id))

        if incompatible_pairs:
            pair = incompatible_pairs[0]
            return CompatibilityResult(
                compatible=False,
                primary_license=pair[0],
                secondary_license=pair[1],
                reason=f"Incompatible licenses: {pair[0]} and {pair[1]}",
                allows_proprietary=False,
            )

        # Check if allows proprietary
        allows_proprietary = most_restrictive in (
            LicenseCategory.PUBLIC_DOMAIN,
            LicenseCategory.PERMISSIVE,
        )

        return CompatibilityResult(
            compatible=True,
            primary_license=licenses[0] if licenses else "None",
            secondary_license=licenses[1] if len(licenses) > 1 else "None",
            reason=f"All licenses compatible (most restrictive: {most_restrictive.value})",
            allows_proprietary=allows_proprietary,
        )

    def enforce_policy(
        self,
        component: SBOMComponent,
        policy: LicensePolicy,
    ) -> Optional[LicenseViolation]:
        """Enforce license policy on a component.

        Args:
            component: SBOM component to check
            policy: License policy to enforce

        Returns:
            LicenseViolation if policy violated, None otherwise

        Raises:
            PolicyViolationError: If policy violation is critical and blocking enabled
        """
        violation = self._check_component_compliance(component, policy)

        if violation and violation.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if self.config.enabled:
                raise PolicyViolationError(
                    message=f"License policy violation: {violation.description}",
                    component=component.name,
                    license_id=violation.detected_license,
                    policy_rule=violation.policy_rule,
                    details={"violation": violation.to_dict()},
                )

        return violation

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _get_default_policy(self) -> LicensePolicy:
        """Get the default license policy from configuration."""
        return LicensePolicy(
            name=self.config.default_policy,
            allowed_categories=self.config.allowed_categories.copy(),
            prohibited_licenses=self.config.prohibited_licenses.copy(),
            require_osi_approved=self.config.require_osi_approved,
            allow_unknown=self.config.allow_unknown_licenses,
        )

    def _normalize_license_id(self, license_id: str) -> str:
        """Normalize a license identifier for lookup."""
        # Trim whitespace
        normalized = license_id.strip()

        # Check direct match first
        if normalized in SPDX_LICENSES:
            return normalized

        # O(1) case-insensitive match via pre-computed lowercase dicts
        lower = normalized.lower()
        spdx_match = _SPDX_LOWER.get(lower)
        if spdx_match is not None:
            return spdx_match

        alias_match = _ALIAS_LOWER.get(lower)
        if alias_match is not None:
            return alias_match

        return normalized

    def _parse_license_expression(self, expression: str) -> LicenseInfo:
        """Parse SPDX license expression (e.g., "MIT OR Apache-2.0").

        Args:
            expression: License expression

        Returns:
            LicenseInfo representing the expression
        """
        # Simple parsing - in production would use license-expression library
        expression_upper = expression.upper()

        if " OR " in expression_upper:
            # Disjunction - use most permissive
            parts = re.split(r"\s+OR\s+", expression, flags=re.IGNORECASE)
            infos = [self.identify_license(p.strip()) for p in parts]

            # Find most permissive
            category_order = [
                LicenseCategory.PUBLIC_DOMAIN,
                LicenseCategory.PERMISSIVE,
                LicenseCategory.WEAK_COPYLEFT,
                LicenseCategory.STRONG_COPYLEFT,
                LicenseCategory.PROPRIETARY,
                LicenseCategory.UNKNOWN,
            ]
            most_permissive = min(infos, key=lambda i: category_order.index(i.category))

            return LicenseInfo(
                spdx_id=expression,
                name=f"Choice of: {', '.join(p.strip() for p in parts)}",
                category=most_permissive.category,
                osi_approved=any(i.osi_approved for i in infos),
                fsf_free=any(i.fsf_free for i in infos),
            )

        if " AND " in expression_upper:
            # Conjunction - use most restrictive
            parts = re.split(r"\s+AND\s+", expression, flags=re.IGNORECASE)
            infos = [self.identify_license(p.strip()) for p in parts]

            category_order = [
                LicenseCategory.PUBLIC_DOMAIN,
                LicenseCategory.PERMISSIVE,
                LicenseCategory.WEAK_COPYLEFT,
                LicenseCategory.STRONG_COPYLEFT,
                LicenseCategory.PROPRIETARY,
                LicenseCategory.UNKNOWN,
            ]
            most_restrictive = max(
                infos, key=lambda i: category_order.index(i.category)
            )

            return LicenseInfo(
                spdx_id=expression,
                name=f"All of: {', '.join(p.strip() for p in parts)}",
                category=most_restrictive.category,
                osi_approved=all(i.osi_approved for i in infos),
                fsf_free=all(i.fsf_free for i in infos),
            )

        # Not an expression
        return LicenseInfo(
            spdx_id=expression,
            name=expression,
            category=LicenseCategory.UNKNOWN,
            osi_approved=False,
            fsf_free=False,
        )

    def _check_component_compliance(
        self,
        component: SBOMComponent,
        policy: LicensePolicy,
    ) -> Optional[LicenseViolation]:
        """Check a single component against the policy.

        Args:
            component: Component to check
            policy: Policy to apply

        Returns:
            LicenseViolation if non-compliant, None otherwise
        """
        # Get component license
        license_text = component.licenses[0] if component.licenses else None
        license_info = self.identify_license(license_text)

        # Check prohibited licenses
        if license_info.spdx_id in policy.prohibited_licenses:
            return LicenseViolation(
                violation_id=f"v-{component.name}-prohibited",
                component_name=component.name,
                component_version=component.version,
                detected_license=license_info.spdx_id,
                violation_type="prohibited_license",
                description=f"License '{license_info.spdx_id}' is in prohibited list",
                policy_rule="prohibited_licenses",
                severity=RiskLevel.HIGH,
                recommendation=f"Replace {component.name} with an alternative using a permitted license",
            )

        # Check allowed categories
        if license_info.category not in policy.allowed_categories:
            return LicenseViolation(
                violation_id=f"v-{component.name}-category",
                component_name=component.name,
                component_version=component.version,
                detected_license=license_info.spdx_id,
                violation_type="category_not_allowed",
                description=f"Category '{license_info.category.value}' not in allowed list",
                policy_rule="allowed_categories",
                severity=RiskLevel.MEDIUM,
                recommendation=f"Review {component.name} license compatibility with project requirements",
            )

        # Check OSI requirement
        if policy.require_osi_approved and not license_info.osi_approved:
            return LicenseViolation(
                violation_id=f"v-{component.name}-osi",
                component_name=component.name,
                component_version=component.version,
                detected_license=license_info.spdx_id,
                violation_type="not_osi_approved",
                description="License is not OSI approved",
                policy_rule="require_osi_approved",
                severity=RiskLevel.MEDIUM,
                recommendation=f"Replace {component.name} with an OSI-approved alternative",
            )

        # Check unknown handling
        if (
            license_info.category == LicenseCategory.UNKNOWN
            and not policy.allow_unknown
        ):
            return LicenseViolation(
                violation_id=f"v-{component.name}-unknown",
                component_name=component.name,
                component_version=component.version,
                detected_license=license_info.spdx_id,
                violation_type="unknown_license",
                description="Unknown license not allowed by policy",
                policy_rule="allow_unknown",
                severity=RiskLevel.MEDIUM,
                recommendation=f"Identify and document the license for {component.name}",
            )

        return None

    def _generate_markdown_attribution(self, sbom: SBOMDocument) -> str:
        """Generate markdown format attribution."""
        lines = [
            "# Third-Party Software Attribution",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Components",
            "",
        ]

        for component in sorted(sbom.components, key=lambda c: c.name.lower()):
            license_text = component.licenses[0] if component.licenses else "Unknown"
            license_info = self.identify_license(license_text)

            lines.extend(
                [
                    f"### {component.name} ({component.version})",
                    "",
                    f"- **License:** {license_info.name} ({license_info.spdx_id})",
                ]
            )

            if component.supplier:
                lines.append(f"- **Author/Supplier:** {component.supplier}")

            if license_info.url:
                lines.append(f"- **License URL:** {license_info.url}")

            if component.purl:
                lines.append(f"- **Package URL:** {component.purl}")

            lines.extend(["", "---", ""])

        return "\n".join(lines)

    def _generate_text_attribution(self, sbom: SBOMDocument) -> str:
        """Generate plain text format attribution."""
        lines = [
            "THIRD-PARTY SOFTWARE ATTRIBUTION",
            "=" * 40,
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "COMPONENTS",
            "-" * 40,
            "",
        ]

        for component in sorted(sbom.components, key=lambda c: c.name.lower()):
            license_text = component.licenses[0] if component.licenses else "Unknown"
            license_info = self.identify_license(license_text)

            lines.extend(
                [
                    f"{component.name} ({component.version})",
                    f"  License: {license_info.name} ({license_info.spdx_id})",
                ]
            )

            if component.supplier:
                lines.append(f"  Author/Supplier: {component.supplier}")

            lines.append("")

        return "\n".join(lines)

    def _generate_html_attribution(self, sbom: SBOMDocument) -> str:
        """Generate HTML format attribution."""
        components_html = []

        for component in sorted(sbom.components, key=lambda c: c.name.lower()):
            license_text = component.licenses[0] if component.licenses else "Unknown"
            license_info = self.identify_license(license_text)

            license_link = ""
            if license_info.url:
                license_link = f' (<a href="{license_info.url}">view license</a>)'

            components_html.append(
                f"""
        <tr>
            <td>{component.name}</td>
            <td>{component.version}</td>
            <td>{license_info.name}{license_link}</td>
            <td>{component.supplier or "Unknown"}</td>
        </tr>"""
            )

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Third-Party Software Attribution</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 2rem; }}
        h1 {{ color: #1a1a1a; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 0.75rem; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        .generated {{ color: #666; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <h1>Third-Party Software Attribution</h1>
    <p class="generated">Generated: {datetime.now(timezone.utc).isoformat()}</p>
    <table>
        <thead>
            <tr>
                <th>Component</th>
                <th>Version</th>
                <th>License</th>
                <th>Author/Supplier</th>
            </tr>
        </thead>
        <tbody>
{"".join(components_html)}
        </tbody>
    </table>
</body>
</html>"""


# Singleton instance
_engine_instance: Optional[LicenseComplianceEngine] = None


def get_license_compliance_engine() -> LicenseComplianceEngine:
    """Get singleton engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LicenseComplianceEngine()
    return _engine_instance


def reset_license_compliance_engine() -> None:
    """Reset engine singleton (for testing)."""
    global _engine_instance
    _engine_instance = None
