"""
Project Aura - Monitoring Service Tests

Comprehensive tests for agent monitoring and metrics tracking.
"""

# ruff: noqa: PLR2004

import time
from unittest.mock import patch

from src.agents.monitoring_service import AgentRole, MonitorAgent


class TestAgentRole:
    """Test suite for AgentRole enum."""

    def test_agent_role_values(self):
        """Test that all agent roles are defined."""
        assert AgentRole.ORCHESTRATOR.value == "Orchestrator"
        assert AgentRole.PLANNER.value == "Planner"
        assert AgentRole.CONTEXT.value == "ContextRetrieval"
        assert AgentRole.EMBEDDING.value == "Embedding"
        assert AgentRole.CODER.value == "Coder"
        assert AgentRole.REVIEWER.value == "Reviewer"
        assert AgentRole.VALIDATOR.value == "Validator"
        assert AgentRole.MONITOR.value == "Monitor"


class TestMonitorAgent:
    """Test suite for MonitorAgent."""

    def test_initialization(self):
        """Test MonitorAgent initialization."""
        before = time.time()
        monitor = MonitorAgent()
        after = time.time()

        assert before <= monitor.start_time <= after
        assert monitor.end_time is None
        assert monitor.total_tokens == 0
        assert monitor.vulnerabilities_found == []
        assert monitor.lines_of_code_generated == 0
        assert monitor.llm_cost_per_token == 0.0003

    def test_record_agent_activity_tokens_only(self):
        """Test recording agent activity with only tokens."""
        monitor = MonitorAgent()

        monitor.record_agent_activity(tokens_used=100)

        assert monitor.total_tokens == 100
        assert monitor.lines_of_code_generated == 0

    def test_record_agent_activity_tokens_and_loc(self):
        """Test recording agent activity with tokens and LOC."""
        monitor = MonitorAgent()

        monitor.record_agent_activity(tokens_used=250, loc_generated=50)

        assert monitor.total_tokens == 250
        assert monitor.lines_of_code_generated == 50

    def test_record_agent_activity_multiple_calls(self):
        """Test multiple record_agent_activity calls accumulate."""
        monitor = MonitorAgent()

        monitor.record_agent_activity(tokens_used=100, loc_generated=10)
        monitor.record_agent_activity(tokens_used=200, loc_generated=20)
        monitor.record_agent_activity(tokens_used=150, loc_generated=15)

        assert monitor.total_tokens == 450
        assert monitor.lines_of_code_generated == 45

    def test_record_security_finding_minimal(self):
        """Test recording security finding with minimal parameters."""
        monitor = MonitorAgent()

        monitor.record_security_finding(
            agent=AgentRole.REVIEWER,
            finding="SQL injection vulnerability",
        )

        assert len(monitor.vulnerabilities_found) == 1
        finding = monitor.vulnerabilities_found[0]
        assert finding["agent"] == "Reviewer"
        assert finding["finding"] == "SQL injection vulnerability"
        assert finding["severity"] == "High"  # Default
        assert finding["status"] == "Detected"  # Default
        assert "timestamp" in finding
        assert isinstance(finding["timestamp"], float)

    def test_record_security_finding_full_parameters(self):
        """Test recording security finding with all parameters."""
        monitor = MonitorAgent()

        before = time.time()
        monitor.record_security_finding(
            agent=AgentRole.CODER,
            finding="XSS vulnerability in user input",
            severity="Critical",
            status="Remediated",
        )
        after = time.time()

        finding = monitor.vulnerabilities_found[0]
        assert finding["agent"] == "Coder"
        assert finding["finding"] == "XSS vulnerability in user input"
        assert finding["severity"] == "Critical"
        assert finding["status"] == "Remediated"
        assert before <= finding["timestamp"] <= after

    def test_record_multiple_security_findings(self):
        """Test recording multiple security findings."""
        monitor = MonitorAgent()

        monitor.record_security_finding(
            AgentRole.REVIEWER, "Finding 1", severity="High"
        )
        monitor.record_security_finding(
            AgentRole.VALIDATOR, "Finding 2", severity="Medium"
        )
        monitor.record_security_finding(AgentRole.CODER, "Finding 3", severity="Low")

        assert len(monitor.vulnerabilities_found) == 3
        assert monitor.vulnerabilities_found[0]["finding"] == "Finding 1"
        assert monitor.vulnerabilities_found[1]["finding"] == "Finding 2"
        assert monitor.vulnerabilities_found[2]["finding"] == "Finding 3"

    def test_finalize_report_basic(self):
        """Test finalizing report with basic activity."""
        # Mock time.time() to simulate elapsed time without actual sleep
        mock_times = [0.0, 0.5]  # start_time=0, end_time=0.5
        with patch("src.agents.monitoring_service.time.time", side_effect=mock_times):
            monitor = MonitorAgent()
            monitor.record_agent_activity(tokens_used=1000, loc_generated=100)
            report = monitor.finalize_report()

        assert "total_runtime_seconds" in report
        assert report["total_runtime_seconds"] == 0.5
        assert report["total_tokens_used"] == 1000
        assert "llm_cost_usd" in report
        assert report["loc_generated"] == 100
        assert "engineering_hours_saved" in report
        assert report["vulnerabilities_found_count"] == 0
        assert report["vulnerabilities_remediated_count"] == 0
        assert report["findings_log"] == []

    def test_finalize_report_sets_end_time(self):
        """Test that finalize_report sets end_time."""
        monitor = MonitorAgent()

        assert monitor.end_time is None

        monitor.finalize_report()

        assert monitor.end_time is not None
        # Use >= because on fast systems, both timestamps can be identical
        # (sub-microsecond execution completes within time.time() precision)
        assert monitor.end_time >= monitor.start_time

    def test_finalize_report_llm_cost_calculation(self):
        """Test LLM cost calculation."""
        monitor = MonitorAgent()

        monitor.record_agent_activity(tokens_used=10000)

        report = monitor.finalize_report()

        expected_cost = 10000 * 0.0003
        assert abs(report["llm_cost_usd"] - expected_cost) < 0.0001

    def test_finalize_report_engineering_hours_calculation(self):
        """Test engineering hours saved calculation."""
        monitor = MonitorAgent()

        # 500 LOC generated
        monitor.record_agent_activity(tokens_used=0, loc_generated=500)

        report = monitor.finalize_report()

        # 500 LOC / 50 LOC per hour = 10 hours
        expected_hours = 10.0
        assert report["engineering_hours_saved"] == expected_hours

    def test_finalize_report_engineering_hours_rounding(self):
        """Test engineering hours rounding to 1 decimal."""
        monitor = MonitorAgent()

        # 123 LOC generated
        monitor.record_agent_activity(tokens_used=0, loc_generated=123)

        report = monitor.finalize_report()

        # 123 / 50 = 2.46, rounded to 2.5
        assert abs(report["engineering_hours_saved"] - 2.5) < 0.1

    def test_finalize_report_with_vulnerabilities(self):
        """Test finalize_report includes vulnerability counts."""
        monitor = MonitorAgent()

        monitor.record_security_finding(
            AgentRole.REVIEWER, "Finding 1", status="Detected"
        )
        monitor.record_security_finding(
            AgentRole.CODER, "Finding 2", status="Remediated"
        )
        monitor.record_security_finding(
            AgentRole.VALIDATOR, "Finding 3", status="Remediated"
        )
        monitor.record_security_finding(
            AgentRole.REVIEWER, "Finding 4", status="Detected"
        )

        report = monitor.finalize_report()

        assert report["vulnerabilities_found_count"] == 4
        assert report["vulnerabilities_remediated_count"] == 2
        assert len(report["findings_log"]) == 4

    def test_finalize_report_findings_log(self):
        """Test that findings_log includes all vulnerability details."""
        monitor = MonitorAgent()

        monitor.record_security_finding(
            AgentRole.REVIEWER,
            "Critical bug",
            severity="Critical",
            status="Remediated",
        )

        report = monitor.finalize_report()

        assert len(report["findings_log"]) == 1
        finding = report["findings_log"][0]
        assert finding["agent"] == "Reviewer"
        assert finding["finding"] == "Critical bug"
        assert finding["severity"] == "Critical"
        assert finding["status"] == "Remediated"

    def test_finalize_report_runtime_accuracy(self):
        """Test runtime calculation accuracy."""
        # Mock time.time() to simulate exactly 0.2 seconds elapsed
        mock_times = [0.0, 0.2]  # start_time=0, end_time=0.2
        with patch("src.agents.monitoring_service.time.time", side_effect=mock_times):
            monitor = MonitorAgent()
            report = monitor.finalize_report()

        # Should be exactly 0.2 seconds
        assert report["total_runtime_seconds"] == 0.2

    def test_zero_tokens_cost(self):
        """Test cost calculation with zero tokens."""
        monitor = MonitorAgent()

        report = monitor.finalize_report()

        assert report["llm_cost_usd"] == 0.0

    def test_zero_loc_engineering_hours(self):
        """Test engineering hours with zero LOC."""
        monitor = MonitorAgent()

        report = monitor.finalize_report()

        assert report["engineering_hours_saved"] == 0.0

    def test_mixed_vulnerability_statuses(self):
        """Test vulnerability counting with mixed statuses."""
        monitor = MonitorAgent()

        monitor.record_security_finding(AgentRole.REVIEWER, "F1", status="Detected")
        monitor.record_security_finding(AgentRole.CODER, "F2", status="In Progress")
        monitor.record_security_finding(AgentRole.VALIDATOR, "F3", status="Remediated")
        monitor.record_security_finding(AgentRole.REVIEWER, "F4", status="Remediated")
        monitor.record_security_finding(AgentRole.CODER, "F5", status="False Positive")

        report = monitor.finalize_report()

        # Only status="Remediated" should count
        assert report["vulnerabilities_found_count"] == 5
        assert report["vulnerabilities_remediated_count"] == 2

    def test_large_numbers(self):
        """Test with large token and LOC counts."""
        monitor = MonitorAgent()

        monitor.record_agent_activity(tokens_used=1000000, loc_generated=10000)

        report = monitor.finalize_report()

        assert report["total_tokens_used"] == 1000000
        assert report["llm_cost_usd"] == 1000000 * 0.0003
        assert report["loc_generated"] == 10000
        assert report["engineering_hours_saved"] == 200.0  # 10000 / 50

    def test_report_rounding_precision(self):
        """Test that report values are rounded to appropriate precision."""
        # Mock time.time() to simulate 0.123 seconds (will round to 0.12)
        mock_times = [0.0, 0.123]  # start_time=0, end_time=0.123
        with patch("src.agents.monitoring_service.time.time", side_effect=mock_times):
            monitor = MonitorAgent()
            monitor.record_agent_activity(tokens_used=12345, loc_generated=678)
            report = monitor.finalize_report()

        # Runtime should be rounded to 2 decimals
        assert isinstance(report["total_runtime_seconds"], float)
        assert report["total_runtime_seconds"] == 0.12  # 0.123 rounded to 2 decimals
        # LLM cost should be rounded to 4 decimals
        assert len(str(report["llm_cost_usd"]).split(".")[-1]) <= 4
        # Engineering hours should be rounded to 1 decimal
        assert len(str(report["engineering_hours_saved"]).split(".")[-1]) <= 1

    def test_multiple_agents_recording(self):
        """Test findings from different agent roles."""
        monitor = MonitorAgent()

        monitor.record_security_finding(AgentRole.ORCHESTRATOR, "Finding O")
        monitor.record_security_finding(AgentRole.PLANNER, "Finding P")
        monitor.record_security_finding(AgentRole.CONTEXT, "Finding C")
        monitor.record_security_finding(AgentRole.EMBEDDING, "Finding E")
        monitor.record_security_finding(AgentRole.CODER, "Finding CD")
        monitor.record_security_finding(AgentRole.REVIEWER, "Finding R")
        monitor.record_security_finding(AgentRole.VALIDATOR, "Finding V")
        monitor.record_security_finding(AgentRole.MONITOR, "Finding M")

        assert len(monitor.vulnerabilities_found) == 8

        agents = [f["agent"] for f in monitor.vulnerabilities_found]
        assert "Orchestrator" in agents
        assert "Planner" in agents
        assert "ContextRetrieval" in agents
        assert "Embedding" in agents
        assert "Coder" in agents
        assert "Reviewer" in agents
        assert "Validator" in agents
        assert "Monitor" in agents

    def test_timestamp_ordering(self):
        """Test that findings are recorded in chronological order."""
        monitor = MonitorAgent()

        monitor.record_security_finding(AgentRole.REVIEWER, "First")
        time.sleep(0.01)
        monitor.record_security_finding(AgentRole.CODER, "Second")
        time.sleep(0.01)
        monitor.record_security_finding(AgentRole.VALIDATOR, "Third")

        timestamps = [f["timestamp"] for f in monitor.vulnerabilities_found]
        # Timestamps should be in ascending order
        assert timestamps[0] < timestamps[1] < timestamps[2]

    def test_independent_monitor_instances(self):
        """Test that multiple monitor instances don't interfere."""
        monitor1 = MonitorAgent()
        monitor2 = MonitorAgent()

        monitor1.record_agent_activity(tokens_used=100)
        monitor2.record_agent_activity(tokens_used=200)

        assert monitor1.total_tokens == 100
        assert monitor2.total_tokens == 200

    def test_severity_values_preserved(self):
        """Test that different severity levels are preserved."""
        monitor = MonitorAgent()

        monitor.record_security_finding(AgentRole.REVIEWER, "F1", severity="Critical")
        monitor.record_security_finding(AgentRole.REVIEWER, "F2", severity="High")
        monitor.record_security_finding(AgentRole.REVIEWER, "F3", severity="Medium")
        monitor.record_security_finding(AgentRole.REVIEWER, "F4", severity="Low")
        monitor.record_security_finding(AgentRole.REVIEWER, "F5", severity="Info")

        severities = [f["severity"] for f in monitor.vulnerabilities_found]
        assert "Critical" in severities
        assert "High" in severities
        assert "Medium" in severities
        assert "Low" in severities
        assert "Info" in severities
