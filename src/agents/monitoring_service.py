import time
from enum import Enum
from typing import Any


class AgentRole(Enum):
    """Defines the roles for the multi-agent system."""

    ORCHESTRATOR = "Orchestrator"
    PLANNER = "Planner"
    CONTEXT = "ContextRetrieval"
    EMBEDDING = "Embedding"
    CODER = "Coder"
    REVIEWER = "Reviewer"
    VALIDATOR = "Validator"
    MONITOR = "Monitor"


class MonitorAgent:
    """
    Tracks and aggregates metrics for the three dimensions of leadership visibility:
    Velocity, Quality/Compliance, and Cost.
    """

    # FIX: The constructor method was renamed from 'init' to '__init__'.
    def __init__(self) -> None:
        self.start_time = time.time()
        self.end_time: float | None = None
        self.total_tokens = 0
        self.vulnerabilities_found: list[dict[str, Any]] = []
        self.lines_of_code_generated = 0
        self.llm_cost_per_token = 0.0003  # Mock cost per token

    def record_agent_activity(self, tokens_used: int, loc_generated: int = 0):
        """Records token usage and generated lines of code."""
        self.total_tokens += tokens_used
        self.lines_of_code_generated += loc_generated

    def record_security_finding(
        self,
        agent: AgentRole,
        finding: str,
        severity: str = "High",
        status: str = "Detected",
    ):
        """Records security or compliance issues found by agents."""
        self.vulnerabilities_found.append(
            {
                "agent": agent.value,
                "finding": finding,
                "severity": severity,
                "status": status,
                "timestamp": time.time(),
            }
        )

    def log_activity(self, role: AgentRole, activity: str) -> None:
        """Logs agent activity for monitoring and tracking.

        Args:
            role: The agent role performing the activity
            activity: Description of the activity being performed
        """
        # For now, this is a simple logging implementation
        # In production, this could log to CloudWatch, database, etc.
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[{role.value}] {activity}")

    def finalize_report(self) -> dict[str, Any]:
        """Calculates final metrics for executive reporting."""
        self.end_time = time.time()
        total_runtime = self.end_time - self.start_time

        # Calculate cost and efficiency metrics
        llm_cost = self.total_tokens * self.llm_cost_per_token
        engineering_hours_saved = round(
            self.lines_of_code_generated / 50.0, 1
        )  # Assume 50 LOC/hour is human rate

        # Analyze security posture
        remediated_count = sum(
            1 for v in self.vulnerabilities_found if v["status"] == "Remediated"
        )

        return {
            "total_runtime_seconds": round(total_runtime, 2),
            "total_tokens_used": self.total_tokens,
            "llm_cost_usd": round(llm_cost, 4),
            "loc_generated": self.lines_of_code_generated,
            "engineering_hours_saved": engineering_hours_saved,
            "vulnerabilities_found_count": len(self.vulnerabilities_found),
            "vulnerabilities_remediated_count": remediated_count,
            "findings_log": self.vulnerabilities_found,
        }
