# Feature Flag Edition Mapping

**Status:** Decided
**Date:** 2026-01-03
**Decision Makers:** Platform Architecture Team
**Context:** ADR-049 Phase 0 Prerequisite

---

## Executive Summary

This document maps Project Aura's existing 5-tier SaaS feature flag system to the 3-tier self-hosted edition model. It provides:

- **Tier Translation:** SaaS tiers → Self-hosted editions
- **Feature Mapping:** All 22 features categorized by edition
- **Configuration Schema:** Runtime edition detection
- **Integration Guide:** License validation integration

---

## Edition Overview

### SaaS to Self-Hosted Tier Mapping

| SaaS Tier | Self-Hosted Edition | Target Customer |
|-----------|---------------------|-----------------|
| FREE | Community | Open source users, evaluators |
| STARTER | Community | Small teams (<10 users) |
| PROFESSIONAL | Enterprise | Mid-market companies |
| ENTERPRISE | Enterprise | Large enterprises |
| GOVERNMENT | Enterprise+ | Government, defense, air-gapped |

### Edition Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SELF-HOSTED EDITION TIERS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        ENTERPRISE+                                   │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │                      ENTERPRISE                              │   │   │
│   │   │   ┌─────────────────────────────────────────────────────┐   │   │   │
│   │   │   │                    COMMUNITY                         │   │   │   │
│   │   │   │                                                      │   │   │   │
│   │   │   │   • GraphRAG code understanding                      │   │   │   │
│   │   │   │   • Multi-agent orchestration (3 agents)             │   │   │   │
│   │   │   │   • Basic vulnerability scanning                     │   │   │   │
│   │   │   │   • Onboarding UI components                         │   │   │   │
│   │   │   │   • 5 repositories, 10 users                         │   │   │   │
│   │   │   │                                                      │   │   │   │
│   │   │   └─────────────────────────────────────────────────────┘   │   │   │
│   │   │                                                              │   │   │
│   │   │   + HITL approval workflow                                   │   │   │
│   │   │   + Patch generation & sandbox testing                       │   │   │
│   │   │   + Full security scanning                                   │   │   │
│   │   │   + SSO (SAML/OIDC)                                          │   │   │
│   │   │   + Advanced analytics                                       │   │   │
│   │   │   + Multi-repo scanning                                      │   │   │
│   │   │   + Knowledge graph explorer                                 │   │   │
│   │   │   + Ticket integrations                                      │   │   │
│   │   │   + Neural memory (Titan)                                    │   │   │
│   │   │   + Custom agent templates                                   │   │   │
│   │   │   + Custom LLM models                                        │   │   │
│   │   │   + Audit logging                                            │   │   │
│   │   │   + HA clustering                                            │   │   │
│   │   │   + Compliance reports                                       │   │   │
│   │   │   + Priority support                                         │   │   │
│   │   │   + 100 repositories, 500 users, 50 agents                   │   │   │
│   │   │                                                              │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   │   + Autonomous remediation                                           │   │
│   │   + Real-time intervention                                           │   │
│   │   + Air-gapped deployment                                            │   │
│   │   + Disaster recovery                                                │   │
│   │   + Predictive vulnerabilities                                       │   │
│   │   + 24x7 premium support                                             │   │
│   │   + Dedicated TAM                                                    │   │
│   │   + Unlimited resources                                              │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Mapping by Category

### Core Features (5)

| Feature | SaaS Min Tier | Self-Hosted Edition | Notes |
|---------|---------------|---------------------|-------|
| `vulnerability_scanning` | FREE | Community (basic), Enterprise (full) | Community: OWASP Top 10 only |
| `patch_generation` | STARTER | Enterprise | AI-powered security patches |
| `sandbox_testing` | STARTER | Enterprise | Isolated patch testing |
| `hitl_approval` | FREE | Enterprise | HITL is core to enterprise value prop |
| `graphrag_context` | STARTER | Community | Core differentiator, free for all |

**Rationale:** GraphRAG is the core value proposition and should be accessible in Community to drive adoption. HITL approval is moved to Enterprise because self-hosted customers need governance controls.

### Beta Features (8)

| Feature | SaaS Min Tier | Self-Hosted Edition | Notes |
|---------|---------------|---------------------|-------|
| `advanced_analytics` | PROFESSIONAL | Enterprise | Security analytics dashboard |
| `custom_agent_templates` | ENTERPRISE | Enterprise | Custom agent behaviors |
| `multi_repo_scanning` | PROFESSIONAL | Enterprise | Multi-repository scanning |
| `autonomous_remediation` | ENTERPRISE | Enterprise+ | High-risk, requires consent |
| `knowledge_graph_explorer` | PROFESSIONAL | Enterprise | Interactive graph visualization |
| `ticket_integrations` | PROFESSIONAL | Enterprise | Jira, ServiceNow, Linear |
| `neural_memory` | ENTERPRISE | Enterprise | Titan architecture (ADR-024) |
| `real_time_intervention` | ENTERPRISE | Enterprise+ | High-risk, requires consent |

**Rationale:** Features requiring consent (`autonomous_remediation`, `real_time_intervention`) are Enterprise+ only due to liability concerns in self-hosted environments.

### Alpha Features (3)

| Feature | SaaS Min Tier | Self-Hosted Edition | Status |
|---------|---------------|---------------------|--------|
| `ai_code_review` | PROFESSIONAL | Enterprise | Becomes Enterprise when GA |
| `compliance_reports` | ENTERPRISE | Enterprise | SOX, CMMC report generation |
| `predictive_vulnerabilities` | ENTERPRISE | Enterprise+ | ML-based prediction engine |

**Rationale:** Alpha features are not exposed in self-hosted releases until GA. When promoted, they follow the mapped edition.

### Onboarding Features (6)

| Feature | SaaS Min Tier | Self-Hosted Edition | Notes |
|---------|---------------|---------------------|-------|
| `welcome_modal` | FREE | All Editions | First-run experience |
| `onboarding_checklist` | FREE | All Editions | Setup progress tracking |
| `welcome_tour` | FREE | All Editions | Guided walkthrough |
| `feature_tooltips` | FREE | All Editions | Contextual help |
| `video_onboarding` | FREE | All Editions | Getting started videos |
| `team_invitations` | STARTER | Enterprise | Team management |

**Rationale:** All onboarding features are available in Community except team invitations, which require enterprise user management.

### License-Only Features (New for Self-Hosted)

These features exist only in the self-hosted edition model and are not present in SaaS:

| Feature | Edition | Description |
|---------|---------|-------------|
| `sso_saml` | Enterprise | SAML 2.0 SSO integration |
| `sso_oidc` | Enterprise | OpenID Connect SSO |
| `audit_logging` | Enterprise | Comprehensive audit trails |
| `custom_models` | Enterprise | Bring-your-own LLM models |
| `ha_clustering` | Enterprise | High availability clustering |
| `priority_support` | Enterprise | 8x5 support SLA |
| `24x7_support` | Enterprise+ | 24x7 premium support |
| `dedicated_tam` | Enterprise+ | Dedicated Technical Account Manager |
| `disaster_recovery` | Enterprise+ | DR/backup automation |
| `air_gap_deployment` | Enterprise+ | Air-gapped installation mode |

---

## Complete Feature Matrix

### By Edition

| Feature | Community | Enterprise | Enterprise+ |
|---------|-----------|------------|-------------|
| **Core Platform** ||||
| `graphrag_context` | ✅ | ✅ | ✅ |
| `vulnerability_scanning` | ✅ (basic) | ✅ (full) | ✅ (full) |
| `patch_generation` | ❌ | ✅ | ✅ |
| `sandbox_testing` | ❌ | ✅ | ✅ |
| `hitl_approval` | ❌ | ✅ | ✅ |
| **Analytics & Visualization** ||||
| `advanced_analytics` | ❌ | ✅ | ✅ |
| `knowledge_graph_explorer` | ❌ | ✅ | ✅ |
| `compliance_reports` | ❌ | ✅ | ✅ |
| **Agents & Automation** ||||
| `multi_agent` | ✅ (3) | ✅ (50) | ✅ (∞) |
| `custom_agent_templates` | ❌ | ✅ | ✅ |
| `neural_memory` | ❌ | ✅ | ✅ |
| `autonomous_remediation` | ❌ | ❌ | ✅ |
| `real_time_intervention` | ❌ | ❌ | ✅ |
| **Integrations** ||||
| `multi_repo_scanning` | ❌ | ✅ | ✅ |
| `ticket_integrations` | ❌ | ✅ | ✅ |
| `custom_models` | ❌ | ✅ | ✅ |
| **Authentication & Security** ||||
| `sso_saml` | ❌ | ✅ | ✅ |
| `sso_oidc` | ❌ | ✅ | ✅ |
| `audit_logging` | ❌ | ✅ | ✅ |
| **Infrastructure** ||||
| `ha_clustering` | ❌ | ✅ | ✅ |
| `disaster_recovery` | ❌ | ❌ | ✅ |
| `air_gap_deployment` | ❌ | ❌ | ✅ |
| `predictive_vulnerabilities` | ❌ | ❌ | ✅ |
| **Onboarding** ||||
| `welcome_modal` | ✅ | ✅ | ✅ |
| `onboarding_checklist` | ✅ | ✅ | ✅ |
| `welcome_tour` | ✅ | ✅ | ✅ |
| `feature_tooltips` | ✅ | ✅ | ✅ |
| `video_onboarding` | ✅ | ✅ | ✅ |
| `team_invitations` | ❌ | ✅ | ✅ |
| **Support** ||||
| `priority_support` | ❌ | ✅ | ✅ |
| `24x7_support` | ❌ | ❌ | ✅ |
| `dedicated_tam` | ❌ | ❌ | ✅ |

---

## Edition Configuration Schema

### Edition Definition Files

```yaml
# config/editions/community.yaml
edition:
  name: community
  display_name: "Project Aura Community Edition"
  description: "Free, open-source code intelligence platform"

  features:
    enabled:
      - graphrag_context
      - vulnerability_scanning
      - welcome_modal
      - onboarding_checklist
      - welcome_tour
      - feature_tooltips
      - video_onboarding

    disabled:
      - patch_generation
      - sandbox_testing
      - hitl_approval
      - advanced_analytics
      - custom_agent_templates
      - multi_repo_scanning
      - autonomous_remediation
      - knowledge_graph_explorer
      - ticket_integrations
      - neural_memory
      - real_time_intervention
      - ai_code_review
      - compliance_reports
      - predictive_vulnerabilities
      - team_invitations
      - sso_saml
      - sso_oidc
      - audit_logging
      - custom_models
      - ha_clustering
      - disaster_recovery
      - air_gap_deployment
      - priority_support
      - 24x7_support
      - dedicated_tam

    limited:
      vulnerability_scanning:
        mode: "basic"
        checks:
          - "owasp_top_10"
          - "cwe_top_25"
      multi_agent:
        max_concurrent: 3

  limits:
    max_repositories: 5
    max_users: 10
    max_agents: 3
    max_nodes: 1
    retention_days: 30

  ui:
    branding: "community"
    upgrade_prompts: true
    feature_gates_visible: true
```

```yaml
# config/editions/enterprise.yaml
edition:
  name: enterprise
  display_name: "Project Aura Enterprise"
  description: "Enterprise-grade autonomous code security platform"

  features:
    enabled:
      # All Community features
      - graphrag_context
      - vulnerability_scanning
      - welcome_modal
      - onboarding_checklist
      - welcome_tour
      - feature_tooltips
      - video_onboarding
      # Enterprise features
      - patch_generation
      - sandbox_testing
      - hitl_approval
      - advanced_analytics
      - custom_agent_templates
      - multi_repo_scanning
      - knowledge_graph_explorer
      - ticket_integrations
      - neural_memory
      - ai_code_review
      - compliance_reports
      - team_invitations
      - sso_saml
      - sso_oidc
      - audit_logging
      - custom_models
      - ha_clustering
      - priority_support

    disabled:
      - autonomous_remediation
      - real_time_intervention
      - predictive_vulnerabilities
      - disaster_recovery
      - air_gap_deployment
      - 24x7_support
      - dedicated_tam

    limited:
      vulnerability_scanning:
        mode: "full"
      multi_agent:
        max_concurrent: 50

  limits:
    max_repositories: 100
    max_users: 500
    max_agents: 50
    max_nodes: 10
    retention_days: 365

  ui:
    branding: "enterprise"
    upgrade_prompts: true
    feature_gates_visible: false
```

```yaml
# config/editions/enterprise_plus.yaml
edition:
  name: enterprise_plus
  display_name: "Project Aura Enterprise+"
  description: "Maximum security for regulated industries"

  features:
    enabled:
      # All Enterprise features plus:
      - autonomous_remediation
      - real_time_intervention
      - predictive_vulnerabilities
      - disaster_recovery
      - air_gap_deployment
      - 24x7_support
      - dedicated_tam

    disabled: []

    limited:
      vulnerability_scanning:
        mode: "full"
      multi_agent:
        max_concurrent: -1  # Unlimited

  limits:
    max_repositories: -1
    max_users: -1
    max_agents: -1
    max_nodes: -1
    retention_days: -1

  ui:
    branding: "enterprise_plus"
    upgrade_prompts: false
    feature_gates_visible: false
```

---

## Runtime Edition Detection

### Edition Service Integration

```python
# src/config/edition_service.py

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set
import os
import yaml

from src.licensing.license_service import LicenseService, LicenseInfo


class Edition(str, Enum):
    """Self-hosted edition tiers."""
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
    ENTERPRISE_PLUS = "enterprise_plus"


@dataclass
class EditionConfig:
    """Runtime edition configuration."""
    name: Edition
    display_name: str
    enabled_features: Set[str]
    disabled_features: Set[str]
    feature_limits: Dict[str, Dict]
    resource_limits: Dict[str, int]


class EditionService:
    """
    Determines and caches the current edition based on license.

    Integration flow:
    1. License service validates license file
    2. Edition service reads edition from license
    3. Feature flags service uses edition for gating
    """

    _instance: Optional['EditionService'] = None
    _config_cache: Dict[Edition, EditionConfig] = {}

    def __init__(self, license_service: Optional[LicenseService] = None):
        self.license_service = license_service or LicenseService()
        self._current_edition: Optional[EditionConfig] = None
        self._load_edition_configs()

    @classmethod
    def get_instance(cls) -> 'EditionService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_edition_configs(self) -> None:
        """Load edition configuration files."""
        config_dir = os.environ.get(
            "AURA_EDITION_CONFIG_DIR",
            "/etc/aura/editions"
        )

        for edition in Edition:
            config_path = os.path.join(config_dir, f"{edition.value}.yaml")
            if os.path.exists(config_path):
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    self._config_cache[edition] = self._parse_config(
                        edition, config
                    )

    def _parse_config(
        self,
        edition: Edition,
        config: Dict
    ) -> EditionConfig:
        """Parse edition configuration from YAML."""
        ed = config.get("edition", {})
        features = ed.get("features", {})

        return EditionConfig(
            name=edition,
            display_name=ed.get("display_name", edition.value.title()),
            enabled_features=set(features.get("enabled", [])),
            disabled_features=set(features.get("disabled", [])),
            feature_limits=features.get("limited", {}),
            resource_limits=ed.get("limits", {}),
        )

    def get_current_edition(self) -> EditionConfig:
        """Get the current edition based on license."""
        if self._current_edition:
            return self._current_edition

        # Validate license
        license_info = self.license_service.validate()

        # Map license edition to enum
        edition_str = license_info.edition
        try:
            edition = Edition(edition_str)
        except ValueError:
            # Default to community on invalid edition
            edition = Edition.COMMUNITY

        # Get or create config
        if edition in self._config_cache:
            self._current_edition = self._config_cache[edition]
        else:
            self._current_edition = self._default_config(edition)

        return self._current_edition

    def _default_config(self, edition: Edition) -> EditionConfig:
        """Create default config if YAML not found."""
        if edition == Edition.ENTERPRISE_PLUS:
            return EditionConfig(
                name=edition,
                display_name="Project Aura Enterprise+",
                enabled_features=self._all_features(),
                disabled_features=set(),
                feature_limits={},
                resource_limits={
                    "max_repositories": -1,
                    "max_users": -1,
                    "max_agents": -1,
                    "max_nodes": -1,
                },
            )
        elif edition == Edition.ENTERPRISE:
            return EditionConfig(
                name=edition,
                display_name="Project Aura Enterprise",
                enabled_features=self._enterprise_features(),
                disabled_features=self._enterprise_plus_only(),
                feature_limits={"multi_agent": {"max_concurrent": 50}},
                resource_limits={
                    "max_repositories": 100,
                    "max_users": 500,
                    "max_agents": 50,
                    "max_nodes": 10,
                },
            )
        else:  # Community
            return EditionConfig(
                name=edition,
                display_name="Project Aura Community",
                enabled_features=self._community_features(),
                disabled_features=self._paid_features(),
                feature_limits={"multi_agent": {"max_concurrent": 3}},
                resource_limits={
                    "max_repositories": 5,
                    "max_users": 10,
                    "max_agents": 3,
                    "max_nodes": 1,
                },
            )

    def _community_features(self) -> Set[str]:
        return {
            "graphrag_context",
            "vulnerability_scanning",
            "welcome_modal",
            "onboarding_checklist",
            "welcome_tour",
            "feature_tooltips",
            "video_onboarding",
        }

    def _enterprise_features(self) -> Set[str]:
        return self._community_features() | {
            "patch_generation",
            "sandbox_testing",
            "hitl_approval",
            "advanced_analytics",
            "custom_agent_templates",
            "multi_repo_scanning",
            "knowledge_graph_explorer",
            "ticket_integrations",
            "neural_memory",
            "ai_code_review",
            "compliance_reports",
            "team_invitations",
            "sso_saml",
            "sso_oidc",
            "audit_logging",
            "custom_models",
            "ha_clustering",
            "priority_support",
        }

    def _enterprise_plus_only(self) -> Set[str]:
        return {
            "autonomous_remediation",
            "real_time_intervention",
            "predictive_vulnerabilities",
            "disaster_recovery",
            "air_gap_deployment",
            "24x7_support",
            "dedicated_tam",
        }

    def _all_features(self) -> Set[str]:
        return self._enterprise_features() | self._enterprise_plus_only()

    def _paid_features(self) -> Set[str]:
        return self._all_features() - self._community_features()

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if feature is enabled in current edition."""
        config = self.get_current_edition()
        return feature in config.enabled_features

    def get_feature_limit(
        self,
        feature: str,
        limit_key: str
    ) -> Optional[int]:
        """Get a feature-specific limit."""
        config = self.get_current_edition()
        feature_limits = config.feature_limits.get(feature, {})
        return feature_limits.get(limit_key)

    def check_resource_limit(
        self,
        resource: str,
        current: int
    ) -> bool:
        """Check if resource usage is within limits."""
        config = self.get_current_edition()
        limit = config.resource_limits.get(resource, 0)
        if limit == -1:  # Unlimited
            return True
        return current < limit

    def invalidate_cache(self) -> None:
        """Force re-evaluation of edition on next check."""
        self._current_edition = None


# Module-level convenience functions
def get_edition() -> Edition:
    """Get current edition enum."""
    return EditionService.get_instance().get_current_edition().name


def is_enterprise() -> bool:
    """Check if running Enterprise or higher."""
    edition = get_edition()
    return edition in (Edition.ENTERPRISE, Edition.ENTERPRISE_PLUS)


def is_enterprise_plus() -> bool:
    """Check if running Enterprise+."""
    return get_edition() == Edition.ENTERPRISE_PLUS


def is_community() -> bool:
    """Check if running Community edition."""
    return get_edition() == Edition.COMMUNITY
```

### Feature Flags Integration

Update the existing `feature_flags.py` to use edition service:

```python
# src/config/feature_flags.py (additions)

from src.config.edition_service import EditionService, Edition

class FeatureFlagsService:
    """Updated to integrate with EditionService for self-hosted."""

    def __init__(self) -> None:
        # ... existing code ...
        self._edition_service: Optional[EditionService] = None
        self._is_self_hosted = os.getenv("AURA_DEPLOYMENT_MODE") == "self_hosted"

    @property
    def edition_service(self) -> EditionService:
        if self._edition_service is None:
            self._edition_service = EditionService.get_instance()
        return self._edition_service

    def is_enabled(
        self,
        feature_name: str,
        customer_id: Optional[str] = None,
        tier: FeatureTier = FeatureTier.FREE,
    ) -> bool:
        """
        Check if feature is enabled.

        In self-hosted mode, uses EditionService instead of tier.
        """
        # Self-hosted mode uses edition-based gating
        if self._is_self_hosted:
            return self._check_edition_feature(feature_name)

        # SaaS mode uses existing tier logic
        return self._check_saas_feature(feature_name, customer_id, tier)

    def _check_edition_feature(self, feature_name: str) -> bool:
        """Check feature availability in self-hosted edition."""
        # Environment override (highest priority)
        if feature_name in self._env_overrides:
            return self._env_overrides[feature_name]

        # Check edition service
        return self.edition_service.is_feature_enabled(feature_name)

    def _check_saas_feature(
        self,
        feature_name: str,
        customer_id: Optional[str],
        tier: FeatureTier,
    ) -> bool:
        """Existing SaaS tier-based logic."""
        # ... existing implementation ...
        pass
```

---

## UI Feature Gating

### React Context Provider

```typescript
// frontend/src/context/EditionContext.tsx

import React, { createContext, useContext, useEffect, useState } from 'react';

interface EditionInfo {
  edition: 'community' | 'enterprise' | 'enterprise_plus';
  displayName: string;
  features: string[];
  limits: Record<string, number>;
  isLoading: boolean;
}

const EditionContext = createContext<EditionInfo | null>(null);

export function EditionProvider({ children }: { children: React.ReactNode }) {
  const [edition, setEdition] = useState<EditionInfo>({
    edition: 'community',
    displayName: 'Community',
    features: [],
    limits: {},
    isLoading: true,
  });

  useEffect(() => {
    async function fetchEdition() {
      try {
        const response = await fetch('/api/v1/edition');
        const data = await response.json();
        setEdition({
          ...data,
          isLoading: false,
        });
      } catch (error) {
        // Default to community on error
        setEdition({
          edition: 'community',
          displayName: 'Community',
          features: ['graphrag_context', 'vulnerability_scanning'],
          limits: { max_repositories: 5, max_users: 10 },
          isLoading: false,
        });
      }
    }
    fetchEdition();
  }, []);

  return (
    <EditionContext.Provider value={edition}>
      {children}
    </EditionContext.Provider>
  );
}

export function useEdition() {
  const context = useContext(EditionContext);
  if (!context) {
    throw new Error('useEdition must be used within EditionProvider');
  }
  return context;
}

export function useFeature(featureName: string): boolean {
  const { features, isLoading } = useEdition();
  if (isLoading) return false;
  return features.includes(featureName);
}
```

### Feature Gate Component

```typescript
// frontend/src/components/FeatureGate.tsx

import React from 'react';
import { useFeature, useEdition } from '../context/EditionContext';

interface FeatureGateProps {
  feature: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  showUpgrade?: boolean;
}

export function FeatureGate({
  feature,
  children,
  fallback,
  showUpgrade = true,
}: FeatureGateProps) {
  const isEnabled = useFeature(feature);
  const { edition } = useEdition();

  if (isEnabled) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  if (showUpgrade && edition === 'community') {
    return (
      <div className="feature-locked">
        <span className="lock-icon">🔒</span>
        <p>This feature requires Enterprise edition.</p>
        <a href="/upgrade" className="upgrade-link">
          Upgrade Now
        </a>
      </div>
    );
  }

  return null;
}

// Usage:
// <FeatureGate feature="hitl_approval">
//   <HITLApprovalPanel />
// </FeatureGate>
```

---

## Migration Path

### SaaS to Self-Hosted Tier Translation

When migrating from SaaS to self-hosted, use this mapping:

| SaaS Account Tier | Recommended Self-Hosted Edition |
|-------------------|--------------------------------|
| FREE | Community |
| STARTER (< 50 users) | Community |
| STARTER (50+ users) | Enterprise |
| PROFESSIONAL | Enterprise |
| ENTERPRISE | Enterprise |
| GOVERNMENT | Enterprise+ |

### Feature Preservation

Features enabled in SaaS should be preserved when migrating:

```python
# migration/saas_to_selfhosted.py

def generate_license_features(saas_tier: str, enabled_features: List[str]) -> List[str]:
    """
    Generate self-hosted license features based on SaaS entitlements.

    Preserves customer's existing feature access where possible.
    """
    edition = map_tier_to_edition(saas_tier)

    # Start with edition defaults
    license_features = get_edition_default_features(edition)

    # Add any SaaS features that exist in self-hosted
    for feature in enabled_features:
        if feature in SELFHOSTED_FEATURES and feature not in license_features:
            # Customer had this feature in SaaS, grant it
            license_features.append(feature)

    return license_features
```

---

## Testing Strategy

### Unit Tests

```python
# tests/config/test_edition_service.py

import pytest
from src.config.edition_service import EditionService, Edition


class TestEditionService:
    def test_community_defaults(self, community_license):
        service = EditionService(community_license)
        config = service.get_current_edition()

        assert config.name == Edition.COMMUNITY
        assert "graphrag_context" in config.enabled_features
        assert "hitl_approval" in config.disabled_features

    def test_enterprise_features(self, enterprise_license):
        service = EditionService(enterprise_license)
        config = service.get_current_edition()

        assert config.name == Edition.ENTERPRISE
        assert "hitl_approval" in config.enabled_features
        assert "autonomous_remediation" in config.disabled_features

    def test_enterprise_plus_all_features(self, enterprise_plus_license):
        service = EditionService(enterprise_plus_license)
        config = service.get_current_edition()

        assert config.name == Edition.ENTERPRISE_PLUS
        assert "autonomous_remediation" in config.enabled_features
        assert len(config.disabled_features) == 0

    def test_resource_limits_community(self, community_license):
        service = EditionService(community_license)

        assert service.check_resource_limit("max_repositories", 4) is True
        assert service.check_resource_limit("max_repositories", 5) is False

    def test_resource_limits_enterprise_plus_unlimited(self, enterprise_plus_license):
        service = EditionService(enterprise_plus_license)

        # -1 means unlimited
        assert service.check_resource_limit("max_repositories", 999999) is True


class TestFeatureFlagsEditionIntegration:
    def test_selfhosted_mode_uses_edition(self, monkeypatch, enterprise_license):
        monkeypatch.setenv("AURA_DEPLOYMENT_MODE", "self_hosted")

        from src.config.feature_flags import get_feature_flags
        flags = get_feature_flags()

        assert flags.is_enabled("hitl_approval") is True
        assert flags.is_enabled("autonomous_remediation") is False

    def test_saas_mode_uses_tier(self, monkeypatch):
        monkeypatch.delenv("AURA_DEPLOYMENT_MODE", raising=False)

        from src.config.feature_flags import get_feature_flags, FeatureTier
        flags = get_feature_flags()

        # SaaS mode still uses tier-based gating
        assert flags.is_enabled("hitl_approval", tier=FeatureTier.FREE) is True
```

---

## Related Documentation

- [LICENSE_VALIDATION_SCHEME.md](./LICENSE_VALIDATION_SCHEME.md) - Ed25519 license validation
- [RESOURCE_BASELINES.md](./RESOURCE_BASELINES.md) - HPA and resource configuration
- [ADR-049](../architecture-decisions/ADR-049-self-hosted-deployment-strategy.md) - Self-hosted strategy
- [NetworkPolicy Templates](../../deploy/self-hosted/network-policies/README.md) - Network isolation
