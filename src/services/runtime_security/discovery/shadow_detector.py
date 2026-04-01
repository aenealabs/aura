"""
Project Aura - Shadow Agent Detector

Detects unregistered (shadow) agents by analyzing traffic patterns
against the ADR-066 Capability Governance registry.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 CA-7: Continuous monitoring
- NIST 800-53 IR-4: Incident handling
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .agent_discovery import AgentDiscoveryService, AgentRegistration

logger = logging.getLogger(__name__)


class ShadowAlertSeverity(Enum):
    """Severity levels for shadow agent alerts."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ShadowAlert:
    """Immutable alert for a detected shadow agent or MCP server."""

    alert_id: str
    timestamp: datetime
    agent_id: str
    agent_type: str
    severity: ShadowAlertSeverity
    reason: str
    first_seen: datetime
    event_count: int
    tools_observed: tuple[str, ...]
    mcp_servers_observed: tuple[str, ...]
    recommended_action: str
    quarantined: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "severity": self.severity.value,
            "reason": self.reason,
            "first_seen": self.first_seen.isoformat(),
            "event_count": self.event_count,
            "tools_observed": list(self.tools_observed),
            "mcp_servers_observed": list(self.mcp_servers_observed),
            "recommended_action": self.recommended_action,
            "quarantined": self.quarantined,
        }


class ShadowDetector:
    """
    Detects and classifies shadow agents.

    Analyzes discovered agents against the registered set and generates
    severity-classified alerts based on the agent's behavior patterns.

    Severity Classification:
    - INFO: Agent seen once, no tool usage (may be transient)
    - WARNING: Agent seen multiple times or using SAFE tools
    - HIGH: Agent using MONITORING or DANGEROUS tools
    - CRITICAL: Agent using CRITICAL tools or accessing multiple MCP servers

    Usage:
        detector = ShadowDetector(
            discovery=get_agent_discovery(),
            critical_tools={"deploy_to_production", "modify_iam_policy"},
            dangerous_tools={"execute_code", "write_file"},
        )

        alerts = detector.scan()
        for alert in alerts:
            if alert.severity == ShadowAlertSeverity.CRITICAL:
                await quarantine(alert.agent_id)
    """

    def __init__(
        self,
        discovery: Optional[AgentDiscoveryService] = None,
        critical_tools: Optional[set[str]] = None,
        dangerous_tools: Optional[set[str]] = None,
        monitoring_tools: Optional[set[str]] = None,
        auto_quarantine_threshold: ShadowAlertSeverity = ShadowAlertSeverity.CRITICAL,
    ):
        self.discovery = discovery or AgentDiscoveryService()
        self.critical_tools = critical_tools or {
            "deploy_to_production",
            "modify_iam_policy",
            "delete_resource",
            "access_secrets",
            "modify_security_group",
        }
        self.dangerous_tools = dangerous_tools or {
            "execute_code",
            "write_file",
            "create_sandbox",
            "invoke_llm",
            "modify_configuration",
        }
        self.monitoring_tools = monitoring_tools or {
            "read_logs",
            "query_database",
            "scan_repository",
            "list_resources",
        }
        self.auto_quarantine_threshold = auto_quarantine_threshold

        self._alerts: list[ShadowAlert] = []
        self._quarantined_agents: set[str] = set()

    def scan(self) -> list[ShadowAlert]:
        """
        Scan all discovered agents and generate alerts for shadows.

        Returns:
            List of shadow agent alerts, sorted by severity (critical first).
        """
        new_alerts: list[ShadowAlert] = []
        shadow_agents = self.discovery.get_shadow_agents()

        for agent in shadow_agents:
            if agent.agent_id in self._quarantined_agents:
                continue

            alert = self._classify_shadow(agent)
            new_alerts.append(alert)

            if self._should_quarantine(alert):
                self._quarantined_agents.add(agent.agent_id)
                alert = ShadowAlert(
                    alert_id=alert.alert_id,
                    timestamp=alert.timestamp,
                    agent_id=alert.agent_id,
                    agent_type=alert.agent_type,
                    severity=alert.severity,
                    reason=alert.reason,
                    first_seen=alert.first_seen,
                    event_count=alert.event_count,
                    tools_observed=alert.tools_observed,
                    mcp_servers_observed=alert.mcp_servers_observed,
                    recommended_action=alert.recommended_action,
                    quarantined=True,
                )
                new_alerts[-1] = alert

        self._alerts.extend(new_alerts)

        return sorted(
            new_alerts, key=lambda a: self._severity_rank(a.severity), reverse=True
        )

    def get_all_alerts(self) -> list[ShadowAlert]:
        """Get all historical alerts."""
        return list(self._alerts)

    def get_alerts_by_severity(
        self, severity: ShadowAlertSeverity
    ) -> list[ShadowAlert]:
        """Get alerts filtered by severity."""
        return [a for a in self._alerts if a.severity == severity]

    def is_quarantined(self, agent_id: str) -> bool:
        """Check if an agent has been quarantined."""
        return agent_id in self._quarantined_agents

    def release_quarantine(self, agent_id: str) -> bool:
        """Release an agent from quarantine (after investigation)."""
        if agent_id in self._quarantined_agents:
            self._quarantined_agents.discard(agent_id)
            logger.info("Agent %s released from quarantine", agent_id)
            return True
        return False

    @property
    def total_alerts(self) -> int:
        """Total number of alerts generated."""
        return len(self._alerts)

    @property
    def quarantined_count(self) -> int:
        """Number of quarantined agents."""
        return len(self._quarantined_agents)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _classify_shadow(self, agent: AgentRegistration) -> ShadowAlert:
        """Classify a shadow agent and generate an alert."""
        tools_set = set(agent.tool_capabilities)
        mcp_set = set(agent.mcp_servers)

        severity = self._determine_severity(agent, tools_set, mcp_set)
        reason = self._build_reason(agent, tools_set, mcp_set)
        action = self._recommend_action(severity)

        return ShadowAlert(
            alert_id=f"sa-{uuid.uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc),
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            severity=severity,
            reason=reason,
            first_seen=agent.first_seen,
            event_count=agent.event_count,
            tools_observed=agent.tool_capabilities,
            mcp_servers_observed=agent.mcp_servers,
            recommended_action=action,
        )

    def _determine_severity(
        self,
        agent: AgentRegistration,
        tools: set[str],
        mcp_servers: set[str],
    ) -> ShadowAlertSeverity:
        """Determine alert severity based on agent behavior."""
        critical_overlap = tools & self.critical_tools
        dangerous_overlap = tools & self.dangerous_tools

        if critical_overlap or len(mcp_servers) >= 3:
            return ShadowAlertSeverity.CRITICAL
        if dangerous_overlap or len(mcp_servers) >= 2:
            return ShadowAlertSeverity.HIGH
        if agent.event_count > 1 or tools:
            return ShadowAlertSeverity.WARNING
        return ShadowAlertSeverity.INFO

    def _build_reason(
        self,
        agent: AgentRegistration,
        tools: set[str],
        mcp_servers: set[str],
    ) -> str:
        """Build human-readable reason for the alert."""
        parts = [f"Unregistered agent '{agent.agent_id}' detected"]

        critical_overlap = tools & self.critical_tools
        dangerous_overlap = tools & self.dangerous_tools

        if critical_overlap:
            parts.append(f"using critical tools: {', '.join(sorted(critical_overlap))}")
        elif dangerous_overlap:
            parts.append(
                f"using dangerous tools: {', '.join(sorted(dangerous_overlap))}"
            )
        elif tools:
            parts.append(f"using tools: {', '.join(sorted(tools))}")

        if mcp_servers:
            parts.append(f"accessing MCP servers: {', '.join(sorted(mcp_servers))}")

        parts.append(
            f"({agent.event_count} events since {agent.first_seen.isoformat()})"
        )

        return "; ".join(parts)

    def _recommend_action(self, severity: ShadowAlertSeverity) -> str:
        """Recommend action based on severity."""
        actions = {
            ShadowAlertSeverity.INFO: "Monitor - may be transient agent startup",
            ShadowAlertSeverity.WARNING: "Investigate - verify agent purpose and register in capability governance",
            ShadowAlertSeverity.HIGH: "Isolate - restrict tool access pending investigation",
            ShadowAlertSeverity.CRITICAL: "Quarantine immediately - block all tool access and escalate to security team",
        }
        return actions[severity]

    def _should_quarantine(self, alert: ShadowAlert) -> bool:
        """Determine if auto-quarantine should be triggered."""
        return self._severity_rank(alert.severity) >= self._severity_rank(
            self.auto_quarantine_threshold
        )

    @staticmethod
    def _severity_rank(severity: ShadowAlertSeverity) -> int:
        """Numeric rank for severity comparison."""
        ranks = {
            ShadowAlertSeverity.INFO: 0,
            ShadowAlertSeverity.WARNING: 1,
            ShadowAlertSeverity.HIGH: 2,
            ShadowAlertSeverity.CRITICAL: 3,
        }
        return ranks[severity]
