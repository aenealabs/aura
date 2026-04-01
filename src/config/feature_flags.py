"""
Feature Flags Configuration for Project Aura.

Provides centralized feature flag management for:
- Beta features (Phase 3 private beta)
- Premium tier features
- Customer-specific overrides
- A/B testing capabilities

Feature flags are loaded from:
1. Environment variables (AURA_FEATURE_*)
2. DynamoDB (for customer-specific overrides)
3. SSM Parameter Store (for global defaults)
4. Code defaults (as fallback)

Usage:
    from src.config.feature_flags import get_feature_flags, is_feature_enabled

    flags = get_feature_flags()
    if flags.is_enabled("advanced_analytics"):
        # Feature is enabled
        pass

    # Or with customer context
    if is_feature_enabled("multi_repo_scanning", customer_id="cust_123"):
        # Feature enabled for this customer
        pass
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FeatureTier(str, Enum):
    """Feature availability by pricing tier."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"


class FeatureStatus(str, Enum):
    """Feature lifecycle status."""

    ALPHA = "alpha"  # Internal testing only
    BETA = "beta"  # Private beta with design partners
    GA = "ga"  # Generally available
    DEPRECATED = "deprecated"  # Being phased out


@dataclass
class FeatureDefinition:
    """Definition of a single feature flag."""

    name: str
    description: str
    status: FeatureStatus = FeatureStatus.GA
    min_tier: FeatureTier = FeatureTier.FREE
    enabled_by_default: bool = True
    requires_consent: bool = False
    rollout_percentage: int = 100  # 0-100 for gradual rollout
    created_at: str = ""
    dependencies: List[str] = field(default_factory=list)


# =============================================================================
# Feature Flag Registry
# =============================================================================

# Core Platform Features
CORE_FEATURES: Dict[str, FeatureDefinition] = {
    "vulnerability_scanning": FeatureDefinition(
        name="vulnerability_scanning",
        description="Automated code vulnerability detection",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.FREE,
    ),
    "patch_generation": FeatureDefinition(
        name="patch_generation",
        description="AI-powered security patch generation",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.STARTER,
    ),
    "sandbox_testing": FeatureDefinition(
        name="sandbox_testing",
        description="Isolated environment for patch testing",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.STARTER,
    ),
    "hitl_approval": FeatureDefinition(
        name="hitl_approval",
        description="Human-in-the-loop approval workflow",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.FREE,
    ),
    "graphrag_context": FeatureDefinition(
        name="graphrag_context",
        description="Hybrid GraphRAG code understanding",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.STARTER,
    ),
}

# Beta Features (Phase 3 Private Beta)
BETA_FEATURES: Dict[str, FeatureDefinition] = {
    "advanced_analytics": FeatureDefinition(
        name="advanced_analytics",
        description="Advanced security analytics dashboard",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=False,
        rollout_percentage=100,
    ),
    "custom_agent_templates": FeatureDefinition(
        name="custom_agent_templates",
        description="Custom agent behavior templates",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        rollout_percentage=100,
    ),
    "multi_repo_scanning": FeatureDefinition(
        name="multi_repo_scanning",
        description="Scan multiple repositories simultaneously",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=True,
        rollout_percentage=100,
    ),
    "autonomous_remediation": FeatureDefinition(
        name="autonomous_remediation",
        description="Fully autonomous patch deployment",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        requires_consent=True,
        rollout_percentage=50,
    ),
    "knowledge_graph_explorer": FeatureDefinition(
        name="knowledge_graph_explorer",
        description="Interactive code knowledge graph visualization",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=True,
        rollout_percentage=100,
    ),
    "ticket_integrations": FeatureDefinition(
        name="ticket_integrations",
        description="External ticketing system integrations",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=True,
        rollout_percentage=100,
    ),
    "neural_memory": FeatureDefinition(
        name="neural_memory",
        description="Titan Neural Memory architecture (ADR-024)",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        dependencies=["graphrag_context"],
    ),
    "real_time_intervention": FeatureDefinition(
        name="real_time_intervention",
        description="Real-time agent intervention (ADR-042)",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        requires_consent=True,
    ),
}

# Upcoming Features (Alpha/Internal)
ALPHA_FEATURES: Dict[str, FeatureDefinition] = {
    "ai_code_review": FeatureDefinition(
        name="ai_code_review",
        description="AI-powered code review suggestions",
        status=FeatureStatus.ALPHA,
        min_tier=FeatureTier.PROFESSIONAL,
        enabled_by_default=False,
        rollout_percentage=0,
    ),
    "compliance_reports": FeatureDefinition(
        name="compliance_reports",
        description="Automated compliance report generation",
        status=FeatureStatus.ALPHA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        rollout_percentage=0,
    ),
    "predictive_vulnerabilities": FeatureDefinition(
        name="predictive_vulnerabilities",
        description="Predict potential vulnerabilities before they occur",
        status=FeatureStatus.ALPHA,
        min_tier=FeatureTier.ENTERPRISE,
        enabled_by_default=False,
        rollout_percentage=0,
    ),
}

# Customer Onboarding Features (ADR-047)
ONBOARDING_FEATURES: Dict[str, FeatureDefinition] = {
    "welcome_modal": FeatureDefinition(
        name="welcome_modal",
        description="First-time user welcome modal overlay",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.FREE,
        enabled_by_default=True,
    ),
    "onboarding_checklist": FeatureDefinition(
        name="onboarding_checklist",
        description="Interactive onboarding progress checklist",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.FREE,
        enabled_by_default=True,
    ),
    "welcome_tour": FeatureDefinition(
        name="welcome_tour",
        description="Guided welcome tour walkthrough (Joyride-style)",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.FREE,
        enabled_by_default=True,
        rollout_percentage=50,
    ),
    "feature_tooltips": FeatureDefinition(
        name="feature_tooltips",
        description="In-app tooltips for feature discovery",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.FREE,
        enabled_by_default=True,
    ),
    "video_onboarding": FeatureDefinition(
        name="video_onboarding",
        description="Getting-started video content",
        status=FeatureStatus.BETA,
        min_tier=FeatureTier.FREE,
        enabled_by_default=True,
    ),
    "team_invitations": FeatureDefinition(
        name="team_invitations",
        description="Team member invitation wizard",
        status=FeatureStatus.GA,
        min_tier=FeatureTier.STARTER,
        enabled_by_default=True,
    ),
}


# =============================================================================
# Feature Flags Service
# =============================================================================


@dataclass
class CustomerFeatureOverrides:
    """Customer-specific feature flag overrides."""

    customer_id: str
    tier: FeatureTier
    enabled_features: Set[str] = field(default_factory=set)
    disabled_features: Set[str] = field(default_factory=set)
    beta_participant: bool = False
    custom_flags: Dict[str, Any] = field(default_factory=dict)


class FeatureFlagsService:
    """
    Centralized feature flags management service.

    Supports:
    - Environment-based defaults
    - Customer-specific overrides
    - Tier-based feature gating
    - Gradual rollout percentages
    """

    def __init__(self) -> None:
        self._all_features: Dict[str, FeatureDefinition] = {
            **CORE_FEATURES,
            **BETA_FEATURES,
            **ALPHA_FEATURES,
            **ONBOARDING_FEATURES,
        }
        self._customer_overrides: Dict[str, CustomerFeatureOverrides] = {}
        self._env_overrides: Dict[str, bool] = {}
        self._load_env_overrides()

    def _load_env_overrides(self) -> None:
        """Load feature flag overrides from environment variables."""
        prefix = "AURA_FEATURE_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                feature_name = key[len(prefix) :].lower()
                self._env_overrides[feature_name] = value.lower() in (
                    "true",
                    "1",
                    "yes",
                    "enabled",
                )
                logger.debug(
                    f"Feature flag override from env: {feature_name}={self._env_overrides[feature_name]}"
                )

    def get_feature(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by name."""
        return self._all_features.get(name)

    def is_enabled(
        self,
        feature_name: str,
        customer_id: Optional[str] = None,
        tier: FeatureTier = FeatureTier.FREE,
    ) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature_name: Name of the feature to check
            customer_id: Optional customer ID for customer-specific checks
            tier: Customer's pricing tier

        Returns:
            True if feature is enabled, False otherwise
        """
        # Check if feature exists
        feature = self._all_features.get(feature_name)
        if not feature:
            logger.warning(f"Unknown feature flag requested: {feature_name}")
            return False

        # Check environment override (highest priority)
        if feature_name in self._env_overrides:
            return self._env_overrides[feature_name]

        # Check customer-specific override
        if customer_id and customer_id in self._customer_overrides:
            overrides = self._customer_overrides[customer_id]

            # Explicit enable
            if feature_name in overrides.enabled_features:
                return True

            # Explicit disable
            if feature_name in overrides.disabled_features:
                return False

            # Use customer's tier
            tier = overrides.tier

            # Beta features require beta participation
            if feature.status == FeatureStatus.BETA and not overrides.beta_participant:
                return False

        # Check tier requirement
        tier_order = [
            FeatureTier.FREE,
            FeatureTier.STARTER,
            FeatureTier.PROFESSIONAL,
            FeatureTier.ENTERPRISE,
            FeatureTier.GOVERNMENT,
        ]
        if tier_order.index(tier) < tier_order.index(feature.min_tier):
            return False

        # Check feature status
        if feature.status == FeatureStatus.ALPHA:
            # Alpha features require explicit environment override
            return False

        if feature.status == FeatureStatus.DEPRECATED:
            # Deprecated features are disabled by default
            return False

        # Check dependencies (with cycle detection)
        for dep in feature.dependencies:
            if not self._is_enabled_with_visited(
                dep, customer_id, tier, {feature_name}
            ):
                return False

        # Check rollout percentage
        if feature.rollout_percentage < 100:
            # Use customer_id for consistent rollout
            if customer_id:
                hash_val = hash(f"{feature_name}:{customer_id}") % 100
                if hash_val >= feature.rollout_percentage:
                    return False

        return feature.enabled_by_default

    def _is_enabled_with_visited(
        self,
        feature_name: str,
        customer_id: Optional[str],
        tier: "FeatureTier",
        visited: set[str],
    ) -> bool:
        """Check if feature is enabled with cycle detection for dependencies."""
        if feature_name in visited:
            return False  # Cycle detected, break recursion
        visited.add(feature_name)

        feature = self._all_features.get(feature_name)
        if not feature:
            return False

        # Check environment override
        if feature_name in self._env_overrides:
            return self._env_overrides[feature_name]

        # Check customer-specific override
        if customer_id and customer_id in self._customer_overrides:
            overrides = self._customer_overrides[customer_id]
            if feature_name in overrides.enabled_features:
                return True
            if feature_name in overrides.disabled_features:
                return False
            tier = overrides.tier
            if feature.status == FeatureStatus.BETA and not overrides.beta_participant:
                return False

        # Check tier requirement
        tier_order = [
            FeatureTier.FREE,
            FeatureTier.STARTER,
            FeatureTier.PROFESSIONAL,
            FeatureTier.ENTERPRISE,
            FeatureTier.GOVERNMENT,
        ]
        if tier_order.index(tier) < tier_order.index(feature.min_tier):
            return False

        if feature.status == FeatureStatus.ALPHA:
            return False
        if feature.status == FeatureStatus.DEPRECATED:
            return False

        # Check dependencies recursively with visited set
        for dep in feature.dependencies:
            if not self._is_enabled_with_visited(dep, customer_id, tier, visited):
                return False

        if feature.rollout_percentage < 100:
            if customer_id:
                hash_val = hash(f"{feature_name}:{customer_id}") % 100
                if hash_val >= feature.rollout_percentage:
                    return False

        return feature.enabled_by_default

    def set_customer_overrides(self, overrides: CustomerFeatureOverrides) -> None:
        """Set feature flag overrides for a customer."""
        self._customer_overrides[overrides.customer_id] = overrides
        logger.info(f"Set feature overrides for customer: {overrides.customer_id}")

    def get_customer_overrides(
        self, customer_id: str
    ) -> Optional[CustomerFeatureOverrides]:
        """Get feature flag overrides for a customer."""
        return self._customer_overrides.get(customer_id)

    def enable_beta_features(self, customer_id: str, tier: FeatureTier) -> None:
        """Enable all beta features for a customer (design partner)."""
        overrides = self._customer_overrides.get(
            customer_id,
            CustomerFeatureOverrides(customer_id=customer_id, tier=tier),
        )
        overrides.beta_participant = True

        # Enable all beta features for their tier
        for name, feature in BETA_FEATURES.items():
            tier_order = [
                FeatureTier.FREE,
                FeatureTier.STARTER,
                FeatureTier.PROFESSIONAL,
                FeatureTier.ENTERPRISE,
                FeatureTier.GOVERNMENT,
            ]
            if tier_order.index(tier) >= tier_order.index(feature.min_tier):
                overrides.enabled_features.add(name)

        self._customer_overrides[customer_id] = overrides
        logger.info(f"Enabled beta features for customer: {customer_id}")

    def list_features(
        self, status: Optional[FeatureStatus] = None
    ) -> List[FeatureDefinition]:
        """List all features, optionally filtered by status."""
        features = list(self._all_features.values())
        if status:
            features = [f for f in features if f.status == status]
        return sorted(features, key=lambda f: f.name)

    def list_enabled_features(
        self,
        customer_id: Optional[str] = None,
        tier: FeatureTier = FeatureTier.FREE,
    ) -> List[str]:
        """List all enabled features for a customer/tier."""
        return [
            name
            for name in self._all_features
            if self.is_enabled(name, customer_id, tier)
        ]

    def get_feature_flags_status(
        self,
        customer_id: Optional[str] = None,
        tier: FeatureTier = FeatureTier.FREE,
    ) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive feature flags status."""
        result = {}
        for name, feature in self._all_features.items():
            result[name] = {
                "enabled": self.is_enabled(name, customer_id, tier),
                "status": feature.status.value,
                "min_tier": feature.min_tier.value,
                "description": feature.description,
                "requires_consent": feature.requires_consent,
            }
        return result


# =============================================================================
# Module-level convenience functions
# =============================================================================

_service: Optional[FeatureFlagsService] = None


def get_feature_flags() -> FeatureFlagsService:
    """Get the singleton feature flags service."""
    global _service
    if _service is None:
        _service = FeatureFlagsService()
    return _service


def is_feature_enabled(
    feature_name: str,
    customer_id: Optional[str] = None,
    tier: FeatureTier = FeatureTier.FREE,
) -> bool:
    """
    Check if a feature is enabled.

    Convenience function that wraps the service.
    """
    return get_feature_flags().is_enabled(feature_name, customer_id, tier)


def get_beta_features() -> Dict[str, FeatureDefinition]:
    """Get all beta features."""
    return BETA_FEATURES.copy()


def get_onboarding_features() -> Dict[str, FeatureDefinition]:
    """Get all onboarding features (ADR-047)."""
    return ONBOARDING_FEATURES.copy()


def get_feature_definition(name: str) -> Optional[FeatureDefinition]:
    """Get a feature definition by name."""
    return get_feature_flags().get_feature(name)


# =============================================================================
# Environment-specific defaults
# =============================================================================


def get_environment_defaults() -> Dict[str, bool]:
    """
    Get environment-specific feature flag defaults.

    Returns default enabled state based on ENVIRONMENT variable.
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()

    if env == "dev":
        # Enable most features in dev
        return {
            "advanced_analytics": True,
            "custom_agent_templates": True,
            "multi_repo_scanning": True,
            "knowledge_graph_explorer": True,
            "ticket_integrations": True,
            "neural_memory": True,
            "autonomous_remediation": False,  # Still require explicit opt-in
            "real_time_intervention": False,
            # Onboarding features (ADR-047)
            "welcome_modal": True,
            "onboarding_checklist": True,
            "welcome_tour": True,
            "feature_tooltips": True,
            "video_onboarding": True,
            "team_invitations": True,
        }
    elif env == "qa":
        # Enable beta features in QA
        return {
            "advanced_analytics": True,
            "multi_repo_scanning": True,
            "knowledge_graph_explorer": True,
            "ticket_integrations": True,
            # Onboarding features (ADR-047)
            "welcome_modal": True,
            "onboarding_checklist": True,
            "welcome_tour": True,
            "feature_tooltips": True,
            "video_onboarding": True,
            "team_invitations": True,
        }
    elif env == "prod":
        # Production uses strict tier-based defaults
        return {
            # Onboarding features are GA - enabled by default in prod
            "welcome_modal": True,
            "onboarding_checklist": True,
            "feature_tooltips": True,
            "team_invitations": True,
            # Beta features use rollout percentage in prod
        }

    return {}
