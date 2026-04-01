"""
Project Aura - Semantic Guardrails Layer 5: Multi-Turn Session Tracking

Tracks cumulative threat scores across conversation turns to detect
gradual escalation attacks that evade single-turn detection.
Target latency: P50 <20ms.

Architecture:
- DynamoDB table for session state persistence
- Exponential decay scoring: Σ(turn_threat × 0.9^n)
- HITL escalation when cumulative score > 2.5
- 24-hour session TTL

Security Rationale:
- Multi-turn attacks gradually escalate to bypass defenses
- Each benign-looking turn contributes to cumulative attack
- Session tracking catches "boiling frog" attacks

Author: Project Aura Team
Created: 2026-01-25
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import SessionTrackingConfig, get_guardrails_config
from .contracts import SessionThreatScore, ThreatLevel

logger = logging.getLogger(__name__)


class DynamoDBClient(Protocol):
    """Protocol for DynamoDB client."""

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        """Get item from table."""
        ...

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        """Put item to table."""
        ...

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        """Update item in table."""
        ...


class MultiTurnTracker:
    """
    Layer 5: Multi-Turn Session Tracking.

    Tracks threat scores across conversation turns and triggers HITL
    escalation when cumulative score exceeds threshold.

    Scoring Formula:
        cumulative_score = Σ(turn_threat_score × decay_factor^(current_turn - turn_n))

    Where decay_factor defaults to 0.9, so recent turns weight more heavily.

    Usage:
        tracker = MultiTurnTracker()
        score = tracker.record_turn(
            session_id="sess-123",
            turn_score=0.7,
            threat_level=ThreatLevel.HIGH,
        )
        if score.needs_hitl_review:
            escalate_to_human(score)

    Thread-safe: Yes (with thread-safe DynamoDB client)
    Target Latency: P50 <20ms
    """

    def __init__(
        self,
        dynamodb_client: Optional[DynamoDBClient] = None,
        config: Optional[SessionTrackingConfig] = None,
    ):
        """
        Initialize the multi-turn tracker.

        Args:
            dynamodb_client: DynamoDB client for persistence (uses mock if None)
            config: Session tracking configuration (uses global config if None)
        """
        if config is None:
            global_config = get_guardrails_config()
            config = global_config.session
        self.config = config

        self._dynamodb = dynamodb_client
        self._mock_mode = dynamodb_client is None

        # In-memory store for mock mode
        self._mock_sessions: dict[str, dict[str, Any]] = {}

        if self._mock_mode:
            logger.info("MultiTurnTracker initialized in MOCK mode")
        else:
            logger.info(
                f"MultiTurnTracker initialized "
                f"(table={config.table_name}, decay={config.decay_factor})"
            )

    def record_turn(
        self,
        session_id: str,
        turn_score: float,
        threat_level: ThreatLevel,
        metadata: Optional[dict[str, Any]] = None,
    ) -> SessionThreatScore:
        """
        Record a turn's threat score and update cumulative score.

        Args:
            session_id: Unique session identifier
            turn_score: Threat score for current turn (0.0 to 1.0)
            threat_level: Threat level for current turn
            metadata: Optional metadata to store with turn

        Returns:
            SessionThreatScore with updated cumulative score
        """
        start_time = time.perf_counter()

        # Clamp turn_score to valid range
        turn_score = max(0.0, min(1.0, turn_score))

        # Get or create session
        session = self._get_session(session_id)

        # Update turn number
        turn_number = session.get("turn_number", 0) + 1
        turn_history = session.get("turn_history", [])
        needs_full_recalc = False

        if turn_number > self.config.max_turns_tracked:
            # Truncate old history to prevent unbounded growth
            if len(turn_history) > self.config.max_turns_tracked:
                turn_history = turn_history[-self.config.max_turns_tracked :]
                session["turn_history"] = turn_history
                needs_full_recalc = True

        # Calculate cumulative score with decay
        turn_history.append(turn_score)

        if needs_full_recalc:
            # Truncation occurred -- full recalculation required
            cumulative_score = self._calculate_cumulative_score(turn_history)
        else:
            # Incremental update: new_cumulative = old_cumulative * decay + new_score
            old_cumulative = session.get("cumulative_score", 0.0)
            cumulative_score = old_cumulative * self.config.decay_factor + turn_score

        # Check for escalation
        escalation_triggered = cumulative_score > self.config.hitl_threshold
        previous_escalation = session.get("escalation_triggered", False)

        # Determine overall threat level based on cumulative score
        if cumulative_score > self.config.hitl_threshold:
            overall_threat_level = ThreatLevel.HIGH
        elif cumulative_score > self.config.hitl_threshold * 0.6:
            overall_threat_level = ThreatLevel.MEDIUM
        elif cumulative_score > self.config.hitl_threshold * 0.3:
            overall_threat_level = ThreatLevel.LOW
        else:
            overall_threat_level = threat_level  # Use turn's threat level

        # Update session
        session.update(
            {
                "session_id": session_id,
                "turn_number": turn_number,
                "turn_history": turn_history,
                "cumulative_score": cumulative_score,
                "escalation_triggered": escalation_triggered or previous_escalation,
                "last_threat_level": threat_level.name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        if metadata:
            session["metadata"] = metadata

        # Persist session
        self._save_session(session_id, session)

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        result = SessionThreatScore(
            session_id=session_id,
            turn_number=turn_number,
            current_turn_score=turn_score,
            cumulative_score=cumulative_score,
            escalation_triggered=escalation_triggered and not previous_escalation,
            turn_history=turn_history[-10:],  # Return last 10 turns
            threat_level=overall_threat_level,
            processing_time_ms=processing_time_ms,
        )

        if result.escalation_triggered:
            logger.warning(
                f"Session {session_id} escalation triggered: "
                f"cumulative_score={cumulative_score:.2f} > threshold={self.config.hitl_threshold}"
            )
        elif result.needs_hitl_review:
            logger.info(
                f"Session {session_id} needs HITL review: "
                f"cumulative_score={cumulative_score:.2f}"
            )

        return result

    def get_session_score(self, session_id: str) -> Optional[SessionThreatScore]:
        """
        Get current session threat score without recording a turn.

        Args:
            session_id: Session identifier

        Returns:
            SessionThreatScore or None if session not found
        """
        session = self._get_session(session_id)

        if not session or "turn_number" not in session:
            return None

        turn_history = session.get("turn_history", [])
        cumulative_score = session.get("cumulative_score", 0.0)

        # Determine threat level
        if cumulative_score > self.config.hitl_threshold:
            threat_level = ThreatLevel.HIGH
        elif cumulative_score > self.config.hitl_threshold * 0.6:
            threat_level = ThreatLevel.MEDIUM
        else:
            threat_level = ThreatLevel.SAFE

        return SessionThreatScore(
            session_id=session_id,
            turn_number=session.get("turn_number", 0),
            current_turn_score=turn_history[-1] if turn_history else 0.0,
            cumulative_score=cumulative_score,
            escalation_triggered=session.get("escalation_triggered", False),
            turn_history=turn_history[-10:],
            threat_level=threat_level,
            processing_time_ms=0.0,
        )

    def reset_session(self, session_id: str) -> bool:
        """
        Reset a session's threat tracking.

        Args:
            session_id: Session identifier

        Returns:
            True if session was reset, False if not found
        """
        if self._mock_mode:
            if session_id in self._mock_sessions:
                del self._mock_sessions[session_id]
                logger.info(f"Session {session_id} reset")
                return True
            return False
        else:
            return self._delete_session(session_id)

    def _calculate_cumulative_score(self, turn_history: list[float]) -> float:
        """
        Calculate cumulative score with exponential decay.

        Formula: Σ(turn_score × decay^(n - turn_index))
        Where n = current turn number (0-indexed)

        Recent turns have higher weight.
        """
        if not turn_history:
            return 0.0

        cumulative = 0.0
        n = len(turn_history) - 1  # Current turn index

        for i, score in enumerate(turn_history):
            # Decay factor: more recent turns weighted higher
            decay_power = n - i
            weight = self.config.decay_factor**decay_power
            cumulative += score * weight

        return cumulative

    def _get_session(self, session_id: str) -> dict[str, Any]:
        """Get session from storage."""
        if self._mock_mode:
            return self._mock_sessions.get(session_id, {})

        if not self._dynamodb:
            return {}

        try:
            response = self._dynamodb.get_item(
                TableName=self.config.table_name,
                Key={"session_id": {"S": session_id}},
            )
            item = response.get("Item", {})
            return self._deserialize_item(item) if item else {}
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return {}

    # Maximum number of sessions to track in mock mode
    _MAX_MOCK_SESSIONS = 10000

    def _save_session(self, session_id: str, session: dict[str, Any]) -> None:
        """Save session to storage."""
        if self._mock_mode:
            # Enforce max session count to prevent unbounded growth
            if (
                session_id not in self._mock_sessions
                and len(self._mock_sessions) >= self._MAX_MOCK_SESSIONS
            ):
                oldest_key = next(iter(self._mock_sessions))
                del self._mock_sessions[oldest_key]
            self._mock_sessions[session_id] = session
            return

        if not self._dynamodb:
            return

        try:
            # Calculate TTL (epoch seconds)
            ttl = int(time.time()) + (self.config.ttl_hours * 3600)

            item = self._serialize_item(session)
            item["ttl"] = {"N": str(ttl)}

            self._dynamodb.put_item(
                TableName=self.config.table_name,
                Item=item,
            )
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")

    def _delete_session(self, session_id: str) -> bool:
        """Delete session from storage."""
        if not self._dynamodb:
            return False

        try:
            self._dynamodb.delete_item(
                TableName=self.config.table_name,
                Key={"session_id": {"S": session_id}},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def _serialize_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """Serialize dict to DynamoDB item format."""
        item = {}
        for key, value in data.items():
            if isinstance(value, str):
                item[key] = {"S": value}
            elif isinstance(value, (int, float)):
                item[key] = {"N": str(value)}
            elif isinstance(value, bool):
                item[key] = {"BOOL": value}
            elif isinstance(value, list):
                if all(isinstance(v, (int, float)) for v in value):
                    item[key] = {"L": [{"N": str(v)} for v in value]}
                else:
                    item[key] = {"L": [{"S": str(v)} for v in value]}
            elif isinstance(value, dict):
                item[key] = {"M": self._serialize_item(value)}
        return item

    def _deserialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Deserialize DynamoDB item to dict."""
        data = {}
        for key, value in item.items():
            if "S" in value:
                data[key] = value["S"]
            elif "N" in value:
                num_str = value["N"]
                data[key] = float(num_str) if "." in num_str else int(num_str)
            elif "BOOL" in value:
                data[key] = value["BOOL"]
            elif "L" in value:
                data[key] = [
                    float(v.get("N", 0)) if "N" in v else v.get("S", "")
                    for v in value["L"]
                ]
            elif "M" in value:
                data[key] = self._deserialize_item(value["M"])
        return data

    def get_active_sessions_count(self) -> int:
        """Get count of active sessions (mock mode only)."""
        if self._mock_mode:
            return len(self._mock_sessions)
        return -1  # Would require scan in DynamoDB

    def create_session_id(self) -> str:
        """Generate a new unique session ID."""
        return f"sess-{uuid.uuid4().hex[:16]}"


# =============================================================================
# Module-level convenience functions
# =============================================================================

_tracker_instance: Optional[MultiTurnTracker] = None


def get_multi_turn_tracker() -> MultiTurnTracker:
    """Get singleton MultiTurnTracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = MultiTurnTracker()
    return _tracker_instance


def record_session_turn(
    session_id: str,
    turn_score: float,
    threat_level: ThreatLevel,
) -> SessionThreatScore:
    """
    Convenience function to record a session turn.

    Args:
        session_id: Session identifier
        turn_score: Threat score for current turn
        threat_level: Threat level for current turn

    Returns:
        SessionThreatScore with cumulative assessment
    """
    return get_multi_turn_tracker().record_turn(
        session_id=session_id,
        turn_score=turn_score,
        threat_level=threat_level,
    )


def reset_multi_turn_tracker() -> None:
    """Reset multi-turn tracker singleton (for testing)."""
    global _tracker_instance
    _tracker_instance = None
