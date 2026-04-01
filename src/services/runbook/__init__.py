"""
Runbook Agent Service

Automated incident documentation system that detects break/fix resolutions
and generates or updates runbooks following project standards.

Components:
- RunbookAgent: Main orchestrator for runbook lifecycle
- IncidentDetector: Monitors logs and events for break/fix patterns
- RunbookGenerator: Creates new runbooks from incident context
- RunbookUpdater: Maintains existing runbooks with new knowledge
- RunbookRepository: Storage, indexing, and retrieval of runbooks

Usage:
    from src.services.runbook import RunbookAgent

    agent = RunbookAgent()

    # Auto-detect and generate from recent incidents
    runbooks = await agent.process_recent_incidents(hours=24)

    # Generate from specific incident
    runbook = await agent.generate_from_incident(incident_id="abc123")

    # Update existing runbook with new resolution
    updated = await agent.update_runbook(
        runbook_path="docs/runbooks/EXAMPLE.md",
        new_resolution="Additional fix steps..."
    )
"""

from .incident_detector import Incident, IncidentDetector, IncidentType
from .runbook_agent import RunbookAgent
from .runbook_generator import GeneratedRunbook, RunbookGenerator
from .runbook_repository import RunbookMetadata, RunbookRepository
from .runbook_updater import RunbookUpdate, RunbookUpdater

__all__ = [
    "RunbookAgent",
    "IncidentDetector",
    "Incident",
    "IncidentType",
    "RunbookGenerator",
    "GeneratedRunbook",
    "RunbookUpdater",
    "RunbookUpdate",
    "RunbookRepository",
    "RunbookMetadata",
]

__version__ = "1.0.0"
