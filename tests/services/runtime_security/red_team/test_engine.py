"""
Tests for the Red Team Engine.

Covers TestOutcome enum, RedTeamResult frozen dataclass, RedTeamCampaign
frozen dataclass (with computed properties), RedTeamEngine async execution,
campaign orchestration, vulnerability tracking, and singleton lifecycle.
"""

import dataclasses
from datetime import datetime, timezone
from typing import Optional

import pytest

from src.services.runtime_security.red_team.engine import (
    RedTeamCampaign,
    RedTeamEngine,
    RedTeamResult,
    TestOutcome,
    get_red_team_engine,
    reset_red_team_engine,
)
from src.services.runtime_security.red_team.taxonomy import (
    AURA_ATTACK_TAXONOMY,
    AttackCategory,
    AttackTechnique,
    TechniqueComplexity,
    get_techniques_by_category,
)

# =========================================================================
# TestOutcome Enum
# =========================================================================


class TestTestOutcome:
    """Tests for the TestOutcome enum."""

    def test_blocked_value(self) -> None:
        assert TestOutcome.BLOCKED.value == "blocked"

    def test_detected_value(self) -> None:
        assert TestOutcome.DETECTED.value == "detected"

    def test_partial_value(self) -> None:
        assert TestOutcome.PARTIAL.value == "partial"

    def test_succeeded_value(self) -> None:
        assert TestOutcome.SUCCEEDED.value == "succeeded"

    def test_error_value(self) -> None:
        assert TestOutcome.ERROR.value == "error"

    def test_skipped_value(self) -> None:
        assert TestOutcome.SKIPPED.value == "skipped"

    def test_total_outcome_count(self) -> None:
        """There are exactly 6 outcome values."""
        assert len(TestOutcome) == 6


# =========================================================================
# RedTeamResult Frozen Dataclass
# =========================================================================


class TestRedTeamResult:
    """Tests for the RedTeamResult frozen dataclass."""

    @pytest.fixture
    def blocked_result(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> RedTeamResult:
        return RedTeamResult(
            result_id="rr-test001",
            technique=sample_technique,
            outcome=TestOutcome.BLOCKED,
            timestamp=now_utc,
            target_agent_id="coder-agent",
            payload_used="test payload",
            response_received="Attack blocked",
            detection_point="semantic_guardrails",
            latency_ms=5.0,
            notes="Unit test result",
        )

    @pytest.fixture
    def succeeded_result(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> RedTeamResult:
        return RedTeamResult(
            result_id="rr-test002",
            technique=sample_technique,
            outcome=TestOutcome.SUCCEEDED,
            timestamp=now_utc,
            target_agent_id="coder-agent",
            payload_used="malicious payload",
            response_received="Secrets revealed",
        )

    @pytest.fixture
    def partial_result(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> RedTeamResult:
        return RedTeamResult(
            result_id="rr-test003",
            technique=sample_technique,
            outcome=TestOutcome.PARTIAL,
            timestamp=now_utc,
            target_agent_id="coder-agent",
            payload_used="partial payload",
            response_received="Partial disclosure",
        )

    def test_creation_all_fields(self, blocked_result: RedTeamResult) -> None:
        """All fields are accessible after creation."""
        assert blocked_result.result_id == "rr-test001"
        assert blocked_result.outcome == TestOutcome.BLOCKED
        assert blocked_result.target_agent_id == "coder-agent"
        assert blocked_result.payload_used == "test payload"
        assert blocked_result.response_received == "Attack blocked"
        assert blocked_result.detection_point == "semantic_guardrails"
        assert blocked_result.latency_ms == 5.0
        assert blocked_result.notes == "Unit test result"

    def test_creation_default_optional_fields(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> None:
        """Default values for optional fields."""
        result = RedTeamResult(
            result_id="rr-defaults",
            technique=sample_technique,
            outcome=TestOutcome.SKIPPED,
            timestamp=now_utc,
            target_agent_id="agent-x",
            payload_used="",
            response_received="",
        )
        assert result.detection_point is None
        assert result.latency_ms == 0.0
        assert result.notes == ""

    def test_frozen_immutability_result_id(self, blocked_result: RedTeamResult) -> None:
        """result_id cannot be mutated."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            blocked_result.result_id = "rr-mutated"  # type: ignore[misc]

    def test_frozen_immutability_outcome(self, blocked_result: RedTeamResult) -> None:
        """outcome cannot be mutated."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            blocked_result.outcome = TestOutcome.SUCCEEDED  # type: ignore[misc]

    def test_frozen_immutability_technique(self, blocked_result: RedTeamResult) -> None:
        """technique cannot be mutated."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            blocked_result.technique = None  # type: ignore[misc]

    def test_frozen_immutability_payload(self, blocked_result: RedTeamResult) -> None:
        """payload_used cannot be mutated."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            blocked_result.payload_used = "changed"  # type: ignore[misc]

    def test_is_vulnerability_true_for_succeeded(
        self, succeeded_result: RedTeamResult
    ) -> None:
        """is_vulnerability is True for SUCCEEDED."""
        assert succeeded_result.is_vulnerability is True

    def test_is_vulnerability_true_for_partial(
        self, partial_result: RedTeamResult
    ) -> None:
        """is_vulnerability is True for PARTIAL."""
        assert partial_result.is_vulnerability is True

    def test_is_vulnerability_false_for_blocked(
        self, blocked_result: RedTeamResult
    ) -> None:
        """is_vulnerability is False for BLOCKED."""
        assert blocked_result.is_vulnerability is False

    def test_is_vulnerability_false_for_detected(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> None:
        """is_vulnerability is False for DETECTED."""
        result = RedTeamResult(
            result_id="rr-det",
            technique=sample_technique,
            outcome=TestOutcome.DETECTED,
            timestamp=now_utc,
            target_agent_id="agent",
            payload_used="",
            response_received="",
        )
        assert result.is_vulnerability is False

    def test_is_vulnerability_false_for_error(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> None:
        """is_vulnerability is False for ERROR."""
        result = RedTeamResult(
            result_id="rr-err",
            technique=sample_technique,
            outcome=TestOutcome.ERROR,
            timestamp=now_utc,
            target_agent_id="agent",
            payload_used="",
            response_received="",
        )
        assert result.is_vulnerability is False

    def test_is_vulnerability_false_for_skipped(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> None:
        """is_vulnerability is False for SKIPPED."""
        result = RedTeamResult(
            result_id="rr-skip",
            technique=sample_technique,
            outcome=TestOutcome.SKIPPED,
            timestamp=now_utc,
            target_agent_id="agent",
            payload_used="",
            response_received="",
        )
        assert result.is_vulnerability is False

    def test_is_blocked_true_only_for_blocked(
        self, blocked_result: RedTeamResult
    ) -> None:
        """is_blocked is True for BLOCKED outcome."""
        assert blocked_result.is_blocked is True

    def test_is_blocked_false_for_succeeded(
        self, succeeded_result: RedTeamResult
    ) -> None:
        """is_blocked is False for SUCCEEDED."""
        assert succeeded_result.is_blocked is False

    def test_is_blocked_false_for_partial(self, partial_result: RedTeamResult) -> None:
        """is_blocked is False for PARTIAL."""
        assert partial_result.is_blocked is False

    def test_is_blocked_false_for_detected(
        self, sample_technique: AttackTechnique, now_utc: datetime
    ) -> None:
        """is_blocked is False for DETECTED."""
        result = RedTeamResult(
            result_id="rr-det2",
            technique=sample_technique,
            outcome=TestOutcome.DETECTED,
            timestamp=now_utc,
            target_agent_id="agent",
            payload_used="",
            response_received="",
        )
        assert result.is_blocked is False

    def test_to_dict_contains_all_keys(self, blocked_result: RedTeamResult) -> None:
        """to_dict includes all expected keys."""
        d = blocked_result.to_dict()
        expected_keys = {
            "result_id",
            "technique_id",
            "technique_name",
            "category",
            "outcome",
            "timestamp",
            "target_agent_id",
            "payload_used",
            "response_received",
            "detection_point",
            "latency_ms",
            "is_vulnerability",
            "notes",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_serialization_values(self, blocked_result: RedTeamResult) -> None:
        """to_dict serializes enum values and technique fields correctly."""
        d = blocked_result.to_dict()
        assert d["result_id"] == "rr-test001"
        assert d["technique_id"] == "ATA-99.001"
        assert d["technique_name"] == "Test Technique"
        assert d["category"] == "ATA-01"
        assert d["outcome"] == "blocked"
        assert d["target_agent_id"] == "coder-agent"
        assert d["payload_used"] == "test payload"
        assert d["response_received"] == "Attack blocked"
        assert d["detection_point"] == "semantic_guardrails"
        assert d["latency_ms"] == 5.0
        assert d["is_vulnerability"] is False
        assert d["notes"] == "Unit test result"

    def test_to_dict_timestamp_iso_format(self, blocked_result: RedTeamResult) -> None:
        """Timestamp serializes as ISO 8601 string."""
        d = blocked_result.to_dict()
        parsed = datetime.fromisoformat(d["timestamp"])
        assert parsed == blocked_result.timestamp


# =========================================================================
# RedTeamCampaign Frozen Dataclass
# =========================================================================


class TestRedTeamCampaign:
    """Tests for the RedTeamCampaign frozen dataclass."""

    @pytest.fixture
    def make_result(self, sample_technique: AttackTechnique, now_utc: datetime):
        """Factory for creating results with specific outcomes."""

        def _make(outcome: TestOutcome, result_id: str = "rr-camp") -> RedTeamResult:
            return RedTeamResult(
                result_id=result_id,
                technique=sample_technique,
                outcome=outcome,
                timestamp=now_utc,
                target_agent_id="coder-agent",
                payload_used="test",
                response_received="response",
            )

        return _make

    @pytest.fixture
    def mixed_campaign(self, make_result, now_utc: datetime) -> RedTeamCampaign:
        """Campaign with mixed outcomes: 2 blocked, 1 detected, 1 succeeded, 1 partial."""
        results = (
            make_result(TestOutcome.BLOCKED, "rr-1"),
            make_result(TestOutcome.BLOCKED, "rr-2"),
            make_result(TestOutcome.DETECTED, "rr-3"),
            make_result(TestOutcome.SUCCEEDED, "rr-4"),
            make_result(TestOutcome.PARTIAL, "rr-5"),
        )
        return RedTeamCampaign(
            campaign_id="rc-test001",
            started_at=now_utc,
            completed_at=now_utc,
            target_agent_id="coder-agent",
            categories_tested=(AttackCategory.PROMPT_INJECTION,),
            results=results,
        )

    @pytest.fixture
    def empty_campaign(self, now_utc: datetime) -> RedTeamCampaign:
        """Campaign with no results."""
        return RedTeamCampaign(
            campaign_id="rc-empty",
            started_at=now_utc,
            completed_at=now_utc,
            target_agent_id="coder-agent",
            categories_tested=(),
            results=(),
        )

    def test_creation(self, mixed_campaign: RedTeamCampaign) -> None:
        """All fields accessible after creation."""
        assert mixed_campaign.campaign_id == "rc-test001"
        assert mixed_campaign.target_agent_id == "coder-agent"
        assert mixed_campaign.categories_tested == (AttackCategory.PROMPT_INJECTION,)
        assert len(mixed_campaign.results) == 5

    def test_frozen_immutability_campaign_id(
        self, mixed_campaign: RedTeamCampaign
    ) -> None:
        """campaign_id cannot be mutated."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            mixed_campaign.campaign_id = "rc-mutated"  # type: ignore[misc]

    def test_frozen_immutability_results(self, mixed_campaign: RedTeamCampaign) -> None:
        """results tuple cannot be reassigned."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            mixed_campaign.results = ()  # type: ignore[misc]

    def test_total_tests(self, mixed_campaign: RedTeamCampaign) -> None:
        """total_tests returns count of results."""
        assert mixed_campaign.total_tests == 5

    def test_total_tests_empty(self, empty_campaign: RedTeamCampaign) -> None:
        """total_tests is 0 for empty campaign."""
        assert empty_campaign.total_tests == 0

    def test_blocked_count(self, mixed_campaign: RedTeamCampaign) -> None:
        """blocked_count returns number of BLOCKED results."""
        assert mixed_campaign.blocked_count == 2

    def test_detected_count(self, mixed_campaign: RedTeamCampaign) -> None:
        """detected_count returns number of DETECTED results."""
        assert mixed_campaign.detected_count == 1

    def test_vulnerability_count(self, mixed_campaign: RedTeamCampaign) -> None:
        """vulnerability_count returns SUCCEEDED + PARTIAL."""
        assert mixed_campaign.vulnerability_count == 2

    def test_block_rate(self, mixed_campaign: RedTeamCampaign) -> None:
        """block_rate is blocked/total."""
        assert mixed_campaign.block_rate == pytest.approx(2 / 5)

    def test_block_rate_zero_tests(self, empty_campaign: RedTeamCampaign) -> None:
        """block_rate returns 0.0 for empty campaign."""
        assert empty_campaign.block_rate == 0.0

    def test_detection_rate(self, mixed_campaign: RedTeamCampaign) -> None:
        """detection_rate is (blocked+detected)/total."""
        assert mixed_campaign.detection_rate == pytest.approx(3 / 5)

    def test_detection_rate_zero_tests(self, empty_campaign: RedTeamCampaign) -> None:
        """detection_rate returns 0.0 for empty campaign."""
        assert empty_campaign.detection_rate == 0.0

    def test_vulnerability_rate(self, mixed_campaign: RedTeamCampaign) -> None:
        """vulnerability_rate is vulnerability_count/total."""
        assert mixed_campaign.vulnerability_rate == pytest.approx(2 / 5)

    def test_vulnerability_rate_zero_tests(
        self, empty_campaign: RedTeamCampaign
    ) -> None:
        """vulnerability_rate returns 0.0 for empty campaign."""
        assert empty_campaign.vulnerability_rate == 0.0

    def test_results_by_category(self, mixed_campaign: RedTeamCampaign) -> None:
        """results_by_category groups results correctly."""
        grouped = mixed_campaign.results_by_category()
        assert "ATA-01" in grouped
        assert len(grouped["ATA-01"]) == 5

    def test_results_by_category_empty(self, empty_campaign: RedTeamCampaign) -> None:
        """results_by_category returns empty dict for empty campaign."""
        grouped = empty_campaign.results_by_category()
        assert grouped == {}

    def test_vulnerabilities_list(self, mixed_campaign: RedTeamCampaign) -> None:
        """vulnerabilities() returns only SUCCEEDED and PARTIAL results."""
        vulns = mixed_campaign.vulnerabilities()
        assert len(vulns) == 2
        outcomes = {v.outcome for v in vulns}
        assert outcomes == {TestOutcome.SUCCEEDED, TestOutcome.PARTIAL}

    def test_vulnerabilities_empty_when_all_blocked(
        self, make_result, now_utc: datetime
    ) -> None:
        """vulnerabilities() returns empty list when all tests are blocked."""
        campaign = RedTeamCampaign(
            campaign_id="rc-allblocked",
            started_at=now_utc,
            completed_at=now_utc,
            target_agent_id="agent",
            categories_tested=(AttackCategory.TOOL_ABUSE,),
            results=(
                make_result(TestOutcome.BLOCKED, "rr-b1"),
                make_result(TestOutcome.BLOCKED, "rr-b2"),
            ),
        )
        assert campaign.vulnerabilities() == []

    def test_to_dict_contains_all_keys(self, mixed_campaign: RedTeamCampaign) -> None:
        """to_dict includes all expected keys."""
        d = mixed_campaign.to_dict()
        expected_keys = {
            "campaign_id",
            "started_at",
            "completed_at",
            "target_agent_id",
            "categories_tested",
            "total_tests",
            "blocked_count",
            "detected_count",
            "vulnerability_count",
            "block_rate",
            "detection_rate",
            "vulnerability_rate",
            "results",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_categories_as_list(self, mixed_campaign: RedTeamCampaign) -> None:
        """categories_tested serializes as list of value strings."""
        d = mixed_campaign.to_dict()
        assert d["categories_tested"] == ["ATA-01"]

    def test_to_dict_results_are_list_of_dicts(
        self, mixed_campaign: RedTeamCampaign
    ) -> None:
        """results serializes as list of dicts."""
        d = mixed_campaign.to_dict()
        assert isinstance(d["results"], list)
        assert len(d["results"]) == 5
        for r in d["results"]:
            assert isinstance(r, dict)

    def test_to_dict_rates_are_rounded(self, mixed_campaign: RedTeamCampaign) -> None:
        """Rates are rounded to 4 decimal places in to_dict."""
        d = mixed_campaign.to_dict()
        assert d["block_rate"] == round(2 / 5, 4)
        assert d["detection_rate"] == round(3 / 5, 4)
        assert d["vulnerability_rate"] == round(2 / 5, 4)


# =========================================================================
# RedTeamEngine: execute_technique
# =========================================================================


class TestExecuteTechnique:
    """Tests for RedTeamEngine.execute_technique (async)."""

    async def test_valid_technique_returns_blocked(self, engine: RedTeamEngine) -> None:
        """Default mock executor returns BLOCKED for valid technique."""
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )
        assert result.outcome == TestOutcome.BLOCKED

    async def test_valid_technique_has_correct_technique(
        self, engine: RedTeamEngine
    ) -> None:
        """Result technique matches the requested technique."""
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )
        assert result.technique.technique_id == "ATA-01.001"
        assert result.technique.name == "Direct Prompt Injection"

    async def test_unknown_technique_returns_error(self, engine: RedTeamEngine) -> None:
        """Unknown technique_id returns ERROR outcome."""
        result = await engine.execute_technique(
            technique_id="ATA-99.999",
            target_agent_id="coder-agent",
        )
        assert result.outcome == TestOutcome.ERROR
        assert "not found" in result.notes.lower()

    async def test_custom_payload_used(self, engine: RedTeamEngine) -> None:
        """Custom payload overrides the technique's example_payload."""
        custom = "My custom attack payload"
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
            custom_payload=custom,
        )
        assert result.payload_used == custom

    async def test_default_payload_from_technique(self, engine: RedTeamEngine) -> None:
        """Without custom_payload, the technique's example_payload is used."""
        technique = AURA_ATTACK_TAXONOMY[0]
        result = await engine.execute_technique(
            technique_id=technique.technique_id,
            target_agent_id="coder-agent",
        )
        assert result.payload_used == technique.example_payload

    async def test_result_stored_in_results(self, engine: RedTeamEngine) -> None:
        """Executed technique result is stored in engine._results."""
        assert engine.total_tests == 0
        await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )
        assert engine.total_tests == 1

    async def test_result_has_target_agent_id(self, engine: RedTeamEngine) -> None:
        """Result contains the correct target_agent_id."""
        result = await engine.execute_technique(
            technique_id="ATA-02.001",
            target_agent_id="reviewer-agent",
        )
        assert result.target_agent_id == "reviewer-agent"

    async def test_result_has_result_id(self, engine: RedTeamEngine) -> None:
        """Result has a non-empty result_id."""
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )
        assert result.result_id
        assert result.result_id.startswith("rr-")

    async def test_result_has_timestamp(self, engine: RedTeamEngine) -> None:
        """Result has a UTC timestamp."""
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )
        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.tzinfo is not None

    async def test_detection_point_from_technique(self, engine: RedTeamEngine) -> None:
        """Detection point is set from the technique's first detection_point."""
        result = await engine.execute_technique(
            technique_id="ATA-01.001",
            target_agent_id="coder-agent",
        )
        technique = AURA_ATTACK_TAXONOMY[0]
        assert result.detection_point == technique.detection_points[0]

    async def test_multiple_executions_accumulate(self, engine: RedTeamEngine) -> None:
        """Multiple executions increment total_tests."""
        await engine.execute_technique("ATA-01.001", "agent-1")
        await engine.execute_technique("ATA-01.002", "agent-1")
        await engine.execute_technique("ATA-02.001", "agent-2")
        assert engine.total_tests == 3


# =========================================================================
# RedTeamEngine: run_campaign
# =========================================================================


class TestRunCampaign:
    """Tests for RedTeamEngine.run_campaign (async)."""

    async def test_campaign_with_specific_categories(
        self, engine: RedTeamEngine
    ) -> None:
        """Campaign with specific categories runs correct number of techniques."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.PROMPT_INJECTION],
        )
        assert campaign.total_tests == 12

    async def test_campaign_with_multiple_categories(
        self, engine: RedTeamEngine
    ) -> None:
        """Campaign with multiple categories aggregates correctly."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.PROMPT_INJECTION, AttackCategory.TOOL_ABUSE],
        )
        assert campaign.total_tests == 22  # 12 + 10

    async def test_campaign_with_all_techniques(self, engine: RedTeamEngine) -> None:
        """Campaign with no filters runs all 75 techniques."""
        campaign = await engine.run_campaign(target_agent_id="coder-agent")
        assert campaign.total_tests == 75

    async def test_campaign_with_technique_ids(self, engine: RedTeamEngine) -> None:
        """Campaign with specific technique_ids runs only those."""
        ids = ["ATA-01.001", "ATA-02.001", "ATA-03.001"]
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            technique_ids=ids,
        )
        assert campaign.total_tests == 3

    async def test_campaign_with_invalid_technique_ids_filtered(
        self, engine: RedTeamEngine
    ) -> None:
        """Invalid technique_ids are filtered out (not found in taxonomy)."""
        ids = ["ATA-01.001", "ATA-99.999"]
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            technique_ids=ids,
        )
        assert campaign.total_tests == 1

    async def test_campaign_stored_in_campaigns(self, engine: RedTeamEngine) -> None:
        """Campaign is stored in engine._campaigns."""
        assert engine.total_campaigns == 0
        await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.EVASION],
        )
        assert engine.total_campaigns == 1

    async def test_campaign_results_also_in_engine_results(
        self, engine: RedTeamEngine
    ) -> None:
        """Campaign results are also added to engine._results."""
        await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.DENIAL_OF_SERVICE],
        )
        assert engine.total_tests == 8  # 8 DoS techniques

    async def test_categories_tested_populated(self, engine: RedTeamEngine) -> None:
        """Campaign.categories_tested reflects the tested categories."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.TOOL_ABUSE, AttackCategory.EVASION],
        )
        assert set(campaign.categories_tested) == {
            AttackCategory.TOOL_ABUSE,
            AttackCategory.EVASION,
        }

    async def test_categories_tested_sorted_by_value(
        self, engine: RedTeamEngine
    ) -> None:
        """categories_tested are sorted by their ATA-XX value."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.EVASION, AttackCategory.PROMPT_INJECTION],
        )
        values = [c.value for c in campaign.categories_tested]
        assert values == sorted(values)

    async def test_empty_categories_runs_all(self, engine: RedTeamEngine) -> None:
        """Passing categories=None runs all 75 techniques."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=None,
        )
        assert campaign.total_tests == 75

    async def test_campaign_has_campaign_id(self, engine: RedTeamEngine) -> None:
        """Campaign has a non-empty campaign_id starting with rc-."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.SUPPLY_CHAIN],
        )
        assert campaign.campaign_id
        assert campaign.campaign_id.startswith("rc-")

    async def test_campaign_target_agent_id(self, engine: RedTeamEngine) -> None:
        """Campaign target_agent_id matches the input."""
        campaign = await engine.run_campaign(
            target_agent_id="validator-agent",
            categories=[AttackCategory.AGENT_CONFUSION],
        )
        assert campaign.target_agent_id == "validator-agent"

    async def test_campaign_started_before_completed(
        self, engine: RedTeamEngine
    ) -> None:
        """Campaign started_at is <= completed_at."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.DATA_EXFILTRATION],
        )
        assert campaign.started_at <= campaign.completed_at

    async def test_all_campaign_results_are_blocked(
        self, engine: RedTeamEngine
    ) -> None:
        """Default mock executor blocks all attacks."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.PRIVILEGE_ESCALATION],
        )
        for r in campaign.results:
            assert r.outcome == TestOutcome.BLOCKED

    async def test_campaign_block_rate_is_1_for_mock(
        self, engine: RedTeamEngine
    ) -> None:
        """Mock executor yields 100% block rate."""
        campaign = await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.SUPPLY_CHAIN],
        )
        assert campaign.block_rate == pytest.approx(1.0)

    async def test_multiple_campaigns_accumulate(self, engine: RedTeamEngine) -> None:
        """Running multiple campaigns increments total_campaigns."""
        await engine.run_campaign(
            target_agent_id="agent-1",
            categories=[AttackCategory.PROMPT_INJECTION],
        )
        await engine.run_campaign(
            target_agent_id="agent-2",
            categories=[AttackCategory.TOOL_ABUSE],
        )
        assert engine.total_campaigns == 2
        assert engine.total_tests == 22  # 12 + 10


# =========================================================================
# RedTeamEngine: get_vulnerabilities
# =========================================================================


class TestVulnerabilities:
    """Tests for vulnerability retrieval on the engine."""

    async def test_get_vulnerabilities_empty_when_all_blocked(
        self, engine: RedTeamEngine
    ) -> None:
        """get_vulnerabilities returns empty list when all mock-blocked."""
        await engine.run_campaign(
            target_agent_id="coder-agent",
            categories=[AttackCategory.PROMPT_INJECTION],
        )
        assert engine.get_vulnerabilities() == []

    async def test_get_vulnerabilities_returns_succeeded_and_partial(self) -> None:
        """get_vulnerabilities includes SUCCEEDED and PARTIAL results."""
        technique = AURA_ATTACK_TAXONOMY[0]
        now = datetime.now(timezone.utc)

        class MockExecutor:
            """Executor that alternates outcomes."""

            def __init__(self):
                self.call_count = 0

            async def execute(self, t, target, payload):
                self.call_count += 1
                if self.call_count == 1:
                    outcome = TestOutcome.SUCCEEDED
                elif self.call_count == 2:
                    outcome = TestOutcome.PARTIAL
                else:
                    outcome = TestOutcome.BLOCKED
                return RedTeamResult(
                    result_id=f"rr-mock-{self.call_count}",
                    technique=t,
                    outcome=outcome,
                    timestamp=now,
                    target_agent_id=target,
                    payload_used=payload,
                    response_received="mock",
                )

        engine = RedTeamEngine(test_executor=MockExecutor())
        await engine.execute_technique("ATA-01.001", "agent")
        await engine.execute_technique("ATA-01.002", "agent")
        await engine.execute_technique("ATA-01.003", "agent")
        vulns = engine.get_vulnerabilities()
        assert len(vulns) == 2
        outcomes = {v.outcome for v in vulns}
        assert outcomes == {TestOutcome.SUCCEEDED, TestOutcome.PARTIAL}


# =========================================================================
# RedTeamEngine: Properties
# =========================================================================


class TestEngineProperties:
    """Tests for RedTeamEngine computed properties."""

    async def test_total_tests_initial(self, engine: RedTeamEngine) -> None:
        """total_tests starts at 0."""
        assert engine.total_tests == 0

    async def test_total_campaigns_initial(self, engine: RedTeamEngine) -> None:
        """total_campaigns starts at 0."""
        assert engine.total_campaigns == 0

    async def test_vulnerability_count_initial(self, engine: RedTeamEngine) -> None:
        """vulnerability_count starts at 0."""
        assert engine.vulnerability_count == 0

    async def test_total_tests_after_execute(self, engine: RedTeamEngine) -> None:
        """total_tests increments after execute_technique."""
        await engine.execute_technique("ATA-01.001", "agent")
        assert engine.total_tests == 1

    async def test_total_campaigns_after_campaign(self, engine: RedTeamEngine) -> None:
        """total_campaigns increments after run_campaign."""
        await engine.run_campaign("agent", categories=[AttackCategory.EVASION])
        assert engine.total_campaigns == 1

    async def test_vulnerability_count_zero_for_all_blocked(
        self, engine: RedTeamEngine
    ) -> None:
        """vulnerability_count is 0 when mock executor blocks all."""
        await engine.run_campaign("agent", categories=[AttackCategory.PROMPT_INJECTION])
        assert engine.vulnerability_count == 0

    async def test_get_all_results_returns_list(self, engine: RedTeamEngine) -> None:
        """get_all_results returns a list."""
        await engine.execute_technique("ATA-01.001", "agent")
        results = engine.get_all_results()
        assert isinstance(results, list)
        assert len(results) == 1

    async def test_get_all_campaigns_returns_list(self, engine: RedTeamEngine) -> None:
        """get_all_campaigns returns a list."""
        await engine.run_campaign("agent", categories=[AttackCategory.EVASION])
        campaigns = engine.get_all_campaigns()
        assert isinstance(campaigns, list)
        assert len(campaigns) == 1

    def test_sandboxed_default_true(self, engine: RedTeamEngine) -> None:
        """Engine is sandboxed by default."""
        assert engine.sandboxed is True

    def test_sandboxed_can_be_set_false(self) -> None:
        """Sandboxed can be explicitly set to False."""
        e = RedTeamEngine(sandboxed=False)
        assert e.sandboxed is False


# =========================================================================
# Singleton Lifecycle
# =========================================================================


class TestSingleton:
    """Tests for get_red_team_engine / reset_red_team_engine singleton."""

    def test_get_returns_engine_instance(self) -> None:
        """get_red_team_engine returns a RedTeamEngine."""
        engine = get_red_team_engine()
        assert isinstance(engine, RedTeamEngine)

    def test_get_same_instance(self) -> None:
        """get_red_team_engine returns the same instance on repeated calls."""
        e1 = get_red_team_engine()
        e2 = get_red_team_engine()
        assert e1 is e2

    def test_reset_creates_new_instance(self) -> None:
        """reset_red_team_engine causes next get to return a new instance."""
        e1 = get_red_team_engine()
        reset_red_team_engine()
        e2 = get_red_team_engine()
        assert e1 is not e2

    def test_reset_clears_state(self) -> None:
        """Reset engine has zero tests and campaigns."""
        engine = get_red_team_engine()
        # Contaminate state via internal list (engine was used elsewhere)
        engine._results.append(None)  # type: ignore[arg-type]
        reset_red_team_engine()
        fresh = get_red_team_engine()
        assert fresh.total_tests == 0
        assert fresh.total_campaigns == 0
