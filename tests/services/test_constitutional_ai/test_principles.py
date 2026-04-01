"""Tests for Constitutional AI principles YAML configuration.

This module tests the constitution.yaml file to ensure all principles
are properly defined, valid, and correctly structured.
"""

from pathlib import Path

import pytest
import yaml

from src.services.constitutional_ai.models import PrincipleCategory, PrincipleSeverity

# Path to the actual constitution file
CONSTITUTION_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "src"
    / "services"
    / "constitutional_ai"
    / "constitution.yaml"
)


@pytest.fixture
def constitution_data():
    """Load the constitution YAML file."""
    if not CONSTITUTION_PATH.exists():
        pytest.skip(f"Constitution file not found at {CONSTITUTION_PATH}")
    with open(CONSTITUTION_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# =============================================================================
# Constitution Structure Tests
# =============================================================================


class TestConstitutionStructure:
    """Tests for the overall constitution file structure."""

    def test_constitution_file_exists(self):
        """Test that constitution.yaml file exists."""
        assert (
            CONSTITUTION_PATH.exists()
        ), f"Constitution file not found at {CONSTITUTION_PATH}"

    def test_constitution_has_version(self, constitution_data):
        """Test that constitution has a version field."""
        assert "version" in constitution_data
        assert constitution_data["version"] == "1.0.0"

    def test_constitution_has_effective_date(self, constitution_data):
        """Test that constitution has an effective_date field."""
        assert "effective_date" in constitution_data

    def test_constitution_has_principles(self, constitution_data):
        """Test that constitution has principles section."""
        assert "principles" in constitution_data
        assert isinstance(constitution_data["principles"], dict)

    def test_constitution_has_16_principles(self, constitution_data):
        """Test that constitution defines exactly 16 principles."""
        principles = constitution_data["principles"]
        assert len(principles) == 16, f"Expected 16 principles, found {len(principles)}"


# =============================================================================
# Principle Field Validation Tests
# =============================================================================


class TestPrincipleFields:
    """Tests for individual principle field validation."""

    def test_all_principles_have_required_fields(self, constitution_data):
        """Test that all principles have required fields."""
        required_fields = [
            "name",
            "severity",
            "category",
            "critique_prompt",
            "revision_prompt",
        ]
        for principle_id, principle in constitution_data["principles"].items():
            for field in required_fields:
                assert (
                    field in principle
                ), f"Principle '{principle_id}' missing required field '{field}'"

    def test_all_severities_are_valid(self, constitution_data):
        """Test that all principle severities are valid."""
        valid_severities = {s.value for s in PrincipleSeverity}
        for principle_id, principle in constitution_data["principles"].items():
            severity = principle["severity"]
            assert (
                severity in valid_severities
            ), f"Principle '{principle_id}' has invalid severity '{severity}'"

    def test_all_categories_are_valid(self, constitution_data):
        """Test that all principle categories are valid."""
        valid_categories = {c.value for c in PrincipleCategory}
        for principle_id, principle in constitution_data["principles"].items():
            category = principle["category"]
            assert (
                category in valid_categories
            ), f"Principle '{principle_id}' has invalid category '{category}'"

    def test_critique_prompts_are_non_empty(self, constitution_data):
        """Test that all critique prompts are non-empty."""
        for principle_id, principle in constitution_data["principles"].items():
            critique_prompt = principle["critique_prompt"]
            assert (
                critique_prompt and critique_prompt.strip()
            ), f"Principle '{principle_id}' has empty critique_prompt"

    def test_revision_prompts_are_non_empty(self, constitution_data):
        """Test that all revision prompts are non-empty."""
        for principle_id, principle in constitution_data["principles"].items():
            revision_prompt = principle["revision_prompt"]
            assert (
                revision_prompt and revision_prompt.strip()
            ), f"Principle '{principle_id}' has empty revision_prompt"

    def test_principle_names_are_unique(self, constitution_data):
        """Test that all principle names are unique."""
        names = [p["name"] for p in constitution_data["principles"].values()]
        assert len(names) == len(set(names)), "Principle names are not unique"

    def test_principle_ids_follow_convention(self, constitution_data):
        """Test that principle IDs follow naming convention."""
        for principle_id in constitution_data["principles"].keys():
            assert principle_id.startswith(
                "principle_"
            ), f"Principle ID '{principle_id}' should start with 'principle_'"


# =============================================================================
# Category Distribution Tests
# =============================================================================


class TestCategoryDistribution:
    """Tests for principle category distribution."""

    def test_has_safety_principles(self, constitution_data):
        """Test that safety category has principles."""
        safety_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "safety"
        ]
        assert len(safety_principles) >= 2, "Should have at least 2 safety principles"

    def test_has_compliance_principles(self, constitution_data):
        """Test that compliance category has principles."""
        compliance_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "compliance"
        ]
        assert (
            len(compliance_principles) >= 1
        ), "Should have at least 1 compliance principle"

    def test_has_transparency_principles(self, constitution_data):
        """Test that transparency category has principles."""
        transparency_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "transparency"
        ]
        assert (
            len(transparency_principles) >= 1
        ), "Should have at least 1 transparency principle"

    def test_has_helpfulness_principles(self, constitution_data):
        """Test that helpfulness category has principles."""
        helpfulness_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "helpfulness"
        ]
        assert (
            len(helpfulness_principles) >= 1
        ), "Should have at least 1 helpfulness principle"

    def test_has_anti_sycophancy_principles(self, constitution_data):
        """Test that anti_sycophancy category has principles."""
        anti_syc_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "anti_sycophancy"
        ]
        assert (
            len(anti_syc_principles) >= 1
        ), "Should have at least 1 anti-sycophancy principle"

    def test_has_code_quality_principles(self, constitution_data):
        """Test that code_quality category has principles."""
        quality_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "code_quality"
        ]
        assert (
            len(quality_principles) >= 1
        ), "Should have at least 1 code quality principle"

    def test_has_meta_principle(self, constitution_data):
        """Test that meta category has at least one principle."""
        meta_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["category"] == "meta"
        ]
        assert len(meta_principles) >= 1, "Should have at least 1 meta principle"


# =============================================================================
# Severity Distribution Tests
# =============================================================================


class TestSeverityDistribution:
    """Tests for principle severity distribution."""

    def test_has_critical_severity_principles(self, constitution_data):
        """Test that some principles have critical severity."""
        critical_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["severity"] == "critical"
        ]
        assert (
            len(critical_principles) >= 2
        ), "Should have at least 2 critical principles"

    def test_has_high_severity_principles(self, constitution_data):
        """Test that some principles have high severity."""
        high_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["severity"] == "high"
        ]
        assert (
            len(high_principles) >= 2
        ), "Should have at least 2 high severity principles"

    def test_has_medium_severity_principles(self, constitution_data):
        """Test that some principles have medium severity."""
        medium_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["severity"] == "medium"
        ]
        assert (
            len(medium_principles) >= 2
        ), "Should have at least 2 medium severity principles"

    def test_has_low_severity_principles(self, constitution_data):
        """Test that some principles have low severity."""
        low_principles = [
            p
            for p in constitution_data["principles"].values()
            if p["severity"] == "low"
        ]
        assert len(low_principles) >= 1, "Should have at least 1 low severity principle"


# =============================================================================
# Domain Tags Tests
# =============================================================================


class TestDomainTags:
    """Tests for principle domain tags."""

    def test_domain_tags_are_lists(self, constitution_data):
        """Test that domain_tags are always lists."""
        for principle_id, principle in constitution_data["principles"].items():
            if "domain_tags" in principle:
                assert isinstance(
                    principle["domain_tags"], list
                ), f"Principle '{principle_id}' domain_tags should be a list"

    def test_security_tagged_principles(self, constitution_data):
        """Test that security-related principles have security tag."""
        security_tagged = [
            p
            for p in constitution_data["principles"].values()
            if "domain_tags" in p and "security" in p["domain_tags"]
        ]
        assert len(security_tagged) >= 1, "Should have security-tagged principles"

    def test_compliance_tagged_principles(self, constitution_data):
        """Test that compliance-related principles have relevant tags."""
        compliance_tagged = [
            p
            for p in constitution_data["principles"].values()
            if "domain_tags" in p
            and any(
                tag in p["domain_tags"] for tag in ["compliance", "cmmc", "sox", "nist"]
            )
        ]
        assert len(compliance_tagged) >= 1, "Should have compliance-tagged principles"


# =============================================================================
# Specific Principle Tests
# =============================================================================


class TestSpecificPrinciples:
    """Tests for specific required principles."""

    def test_security_first_principle_exists(self, constitution_data):
        """Test that security-first principle exists and is critical."""
        security_principles = {
            pid: p
            for pid, p in constitution_data["principles"].items()
            if "security" in pid.lower() and p["severity"] == "critical"
        }
        assert (
            len(security_principles) >= 1
        ), "Should have a critical security principle"

    def test_conflict_resolution_principle_exists(self, constitution_data):
        """Test that conflict resolution principle exists."""
        conflict_principles = {
            pid: p
            for pid, p in constitution_data["principles"].items()
            if "conflict" in pid.lower() or p["category"] == "meta"
        }
        assert (
            len(conflict_principles) >= 1
        ), "Should have a conflict resolution principle"

    def test_honest_disagreement_principle_exists(self, constitution_data):
        """Test that honest disagreement principle exists."""
        honesty_principles = {
            pid: p
            for pid, p in constitution_data["principles"].items()
            if p["category"] == "anti_sycophancy"
        }
        assert len(honesty_principles) >= 1, "Should have anti-sycophancy principles"
