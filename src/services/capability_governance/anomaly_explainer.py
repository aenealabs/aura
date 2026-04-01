"""
Project Aura - Anomaly Explainer

Generate human-readable explanations for detected anomalies using Amazon Bedrock.
Provides natural language descriptions of what behavior was detected, why it's
concerning, and recommended next steps.

Implements ADR-072 for ML-based anomaly detection.
"""

import logging
from typing import Any

from .anomaly_contracts import (
    AgentContext,
    AlertSeverity,
    AnomalyResult,
    AnomalyType,
    CapabilityInvocation,
)

logger = logging.getLogger(__name__)


# Prompt templates for different anomaly types
ANOMALY_TEMPLATES: dict[AnomalyType, str] = {
    AnomalyType.VOLUME: """You are a security analyst explaining an anomaly detected in an AI agent's behavior.

Agent: {agent_name} (type: {agent_type})
Anomaly Type: Unusual invocation volume
Anomaly Score: {score:.2f}

Detection Details:
- Current invocation count: {current_count}
- Expected mean: {expected_mean:.1f}
- Z-score: {z_score:.2f} (threshold: {threshold})
- Window: {window_hours} hour(s)

Recent Activity (last 10 invocations):
{recent_activity}

Provide a brief (2-3 sentence) explanation of:
1. What unusual behavior was detected
2. Why this might be concerning
3. Recommended next steps

Be concise and actionable. Do not speculate beyond the data provided.""",
    AnomalyType.SEQUENCE: """You are a security analyst explaining an anomaly detected in an AI agent's behavior.

Agent: {agent_name} (type: {agent_type})
Anomaly Type: Unusual tool invocation sequence
Anomaly Score: {score:.2f}

Detection Details:
- Unseen n-grams: {unseen_ngrams} of {total_ngrams}
- Unseen ratio: {unseen_ratio:.1%}
- Examples of unusual sequences: {unseen_examples}

Recent Activity (last 10 invocations):
{recent_activity}

Provide a brief (2-3 sentence) explanation of:
1. What unusual behavior was detected
2. Why this might be concerning
3. Recommended next steps

Be concise and actionable. Do not speculate beyond the data provided.""",
    AnomalyType.TEMPORAL: """You are a security analyst explaining an anomaly detected in an AI agent's behavior.

Agent: {agent_name} (type: {agent_type})
Anomaly Type: Activity outside normal hours
Anomaly Score: {score:.2f}

Detection Details:
- Current hour (UTC): {current_hour}:00
- Typical active hours: {typical_hours}

Recent Activity (last 10 invocations):
{recent_activity}

Provide a brief (2-3 sentence) explanation of:
1. What unusual behavior was detected
2. Why this might be concerning
3. Recommended next steps

Be concise and actionable. Do not speculate beyond the data provided.""",
    AnomalyType.HONEYPOT: """You are a security analyst explaining a CRITICAL security alert.

Agent: {agent_name} (type: {agent_type})
Anomaly Type: HONEYPOT TRIGGERED
Severity: P1 - IMMEDIATE ACTION REQUIRED

Detection Details:
- Honeypot capability accessed: {honeypot_name}
- This capability has NO legitimate use case
- Any access indicates: prompt injection, agent confusion, or malicious activity

Recent Activity (last 10 invocations):
{recent_activity}

Provide a brief (3-4 sentence) explanation of:
1. The critical nature of this security incident
2. What this access indicates about the agent's state
3. Immediate containment actions taken
4. Required follow-up investigation steps

Be direct and urgent. This is a confirmed security incident.""",
    AnomalyType.CROSS_AGENT: """You are a security analyst explaining an anomaly detected across multiple AI agents.

Anomaly Type: Coordinated suspicious behavior
Anomaly Score: {score:.2f}

Detection Details:
- Unique agents involved: {unique_agents}
- Total accesses to shared resource: {total_accesses}
- Clustered accesses: {clustered_accesses}
- Shared resource: {shared_resource}
- Correlation window: {correlation_window}s

Provide a brief (2-3 sentence) explanation of:
1. What coordinated behavior was detected
2. Why this pattern is concerning
3. Recommended investigation steps

Be concise and actionable. Do not speculate beyond the data provided.""",
}


DEFAULT_TEMPLATE = """You are a security analyst explaining an anomaly detected in an AI agent's behavior.

Agent: {agent_name} (type: {agent_type})
Anomaly Type: {anomaly_type}
Anomaly Score: {score:.2f}
Detection Details: {details}

Recent Activity (last 10 invocations):
{recent_activity}

Provide a brief (2-3 sentence) explanation of:
1. What unusual behavior was detected
2. Why this might be concerning
3. Recommended next steps

Be concise and actionable. Do not speculate beyond the data provided."""


class AnomalyExplainer:
    """
    Generate human-readable explanations for anomalies using Bedrock.

    This service transforms technical anomaly detection results into
    actionable explanations that security teams can understand and act on.
    """

    def __init__(
        self,
        bedrock_client: Any | None = None,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_tokens: int = 300,
    ):
        """
        Initialize the anomaly explainer.

        Args:
            bedrock_client: Boto3 Bedrock runtime client (optional)
            model_id: Bedrock model ID to use
            max_tokens: Maximum tokens in response
        """
        self.bedrock = bedrock_client
        self.model_id = model_id
        self.max_tokens = max_tokens

    async def explain_anomaly(
        self,
        anomaly: AnomalyResult,
        agent_context: AgentContext | None = None,
        recent_history: list[CapabilityInvocation] | None = None,
    ) -> str:
        """
        Generate natural language explanation of detected anomaly.

        Args:
            anomaly: The anomaly detection result
            agent_context: Context about the agent
            recent_history: Recent invocation history for context

        Returns:
            Human-readable explanation string
        """
        # Format recent activity
        recent_activity = self._format_history(recent_history or [])

        # Get template for anomaly type
        template = ANOMALY_TEMPLATES.get(anomaly.anomaly_type, DEFAULT_TEMPLATE)

        # Build context dict
        context = {
            "agent_name": (
                agent_context.agent_name if agent_context else "Unknown Agent"
            ),
            "agent_type": agent_context.agent_type if agent_context else "unknown",
            "score": anomaly.score,
            "anomaly_type": anomaly.anomaly_type.value,
            "details": str(anomaly.details),
            "recent_activity": recent_activity,
        }

        # Add anomaly-specific details
        context.update(anomaly.details)

        # Format the prompt
        try:
            prompt = template.format(**context)
        except KeyError as e:
            logger.warning(f"Missing template key: {e}, using default template")
            prompt = DEFAULT_TEMPLATE.format(**context)

        # If no Bedrock client, return a structured fallback
        if self.bedrock is None:
            return self._generate_fallback_explanation(anomaly, agent_context)

        # Call Bedrock
        try:
            response = await self._invoke_bedrock(prompt)
            return response
        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            return self._generate_fallback_explanation(anomaly, agent_context)

    def _format_history(
        self, history: list[CapabilityInvocation], max_entries: int = 10
    ) -> str:
        """Format invocation history for the prompt."""
        if not history:
            return "No recent activity recorded."

        entries = []
        for inv in history[-max_entries:]:
            timestamp = inv.timestamp.strftime("%H:%M:%S")
            entries.append(
                f"  {timestamp} | {inv.tool_name} ({inv.classification}) -> {inv.decision}"
            )

        return "\n".join(entries)

    async def _invoke_bedrock(self, prompt: str) -> str:
        """Invoke Bedrock model for explanation."""
        import asyncio
        import json

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
            ),
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    def _generate_fallback_explanation(
        self,
        anomaly: AnomalyResult,
        agent_context: AgentContext | None,
    ) -> str:
        """Generate a structured fallback explanation without Bedrock."""
        agent_name = agent_context.agent_name if agent_context else "Unknown agent"
        agent_type = agent_context.agent_type if agent_context else "unknown"

        severity_descriptions = {
            AlertSeverity.INFO: "low-severity",
            AlertSeverity.SUSPICIOUS: "suspicious",
            AlertSeverity.ALERT: "significant",
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.P1: "CRITICAL P1",
        }
        severity_desc = severity_descriptions.get(anomaly.severity, "notable")

        type_descriptions = {
            AnomalyType.VOLUME: (
                f"invocation volume anomaly detected. The agent's invocation count "
                f"deviates significantly from the baseline (score: {anomaly.score:.2f}). "
                f"This could indicate runaway processing, prompt injection causing "
                f"excessive tool calls, or legitimate but unusual workload spike."
            ),
            AnomalyType.SEQUENCE: (
                f"unusual tool invocation sequence detected. The pattern of tool calls "
                f"differs from learned behavior (score: {anomaly.score:.2f}). "
                f"This could indicate confused reasoning, prompt manipulation, "
                f"or a legitimate new workflow not yet in the baseline."
            ),
            AnomalyType.TEMPORAL: (
                f"activity outside normal hours detected (score: {anomaly.score:.2f}). "
                f"The agent is operating at an unusual time. This could indicate "
                f"unauthorized access, timezone issues, or legitimate off-hours work."
            ),
            AnomalyType.HONEYPOT: (
                "HONEYPOT CAPABILITY ACCESSED. The agent attempted to access a "
                "capability that has no legitimate use case. This definitively "
                "indicates prompt injection, agent confusion, or malicious activity. "
                "The agent has been automatically quarantined."
            ),
            AnomalyType.CROSS_AGENT: (
                f"coordinated behavior across multiple agents detected "
                f"(score: {anomaly.score:.2f}). Multiple agents accessed the same "
                f"resource in close temporal proximity. This could indicate a "
                f"coordinated attack or legitimate parallel processing."
            ),
            AnomalyType.CONTEXT: (
                f"context anomaly detected (score: {anomaly.score:.2f}). The agent's "
                f"behavior doesn't match its expected environment context. This could "
                f"indicate environment confusion or misconfiguration."
            ),
            AnomalyType.ML_ENSEMBLE: (
                f"ensemble anomaly detected (score: {anomaly.score:.2f}). Multiple "
                f"detection methods flagged unusual behavior. Review the component "
                f"scores for specific concerns."
            ),
        }

        description = type_descriptions.get(
            anomaly.anomaly_type,
            f"anomaly detected with score {anomaly.score:.2f}.",
        )

        return (
            f"A {severity_desc} {anomaly.anomaly_type.value} {description} "
            f"Agent: {agent_name} (type: {agent_type}). "
            f"Details: {anomaly.details}"
        )

    async def explain_batch(
        self,
        anomalies: list[tuple[AnomalyResult, AgentContext | None]],
    ) -> list[str]:
        """
        Generate explanations for multiple anomalies.

        Args:
            anomalies: List of (anomaly_result, agent_context) tuples

        Returns:
            List of explanation strings
        """
        import asyncio

        tasks = [
            self.explain_anomaly(anomaly, context) for anomaly, context in anomalies
        ]

        return await asyncio.gather(*tasks)


# Singleton instance
_explainer_instance: AnomalyExplainer | None = None


def get_anomaly_explainer() -> AnomalyExplainer:
    """Get or create the singleton anomaly explainer instance."""
    global _explainer_instance
    if _explainer_instance is None:
        _explainer_instance = AnomalyExplainer()
    return _explainer_instance


def reset_anomaly_explainer() -> None:
    """Reset the singleton instance (for testing)."""
    global _explainer_instance
    _explainer_instance = None
