"""
Runbook Agent Service

Main orchestrator that coordinates incident detection, runbook generation,
and runbook updates. Provides automated documentation for break/fix events.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from .incident_detector import Incident, IncidentDetector, IncidentType
from .runbook_generator import RunbookGenerator
from .runbook_repository import RunbookMetadata, RunbookRepository
from .runbook_updater import RunbookUpdater

logger = logging.getLogger(__name__)


@dataclass
class RunbookAgentResult:
    """Result from a runbook agent operation."""

    success: bool
    action: str  # "created", "updated", "skipped", "error"
    runbook_path: Optional[str] = None
    incident_id: Optional[str] = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_new_runbook(self) -> bool:
        """Check if this result created a new runbook."""
        return self.action == "created"


@dataclass
class ProcessingStats:
    """Statistics from processing incidents."""

    incidents_detected: int = 0
    runbooks_created: int = 0
    runbooks_updated: int = 0
    runbooks_skipped: int = 0
    errors: int = 0
    processing_time_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "incidents_detected": self.incidents_detected,
            "runbooks_created": self.runbooks_created,
            "runbooks_updated": self.runbooks_updated,
            "runbooks_skipped": self.runbooks_skipped,
            "errors": self.errors,
            "processing_time_seconds": self.processing_time_seconds,
        }


class RunbookAgent:
    """
    Main orchestrator for automated runbook generation and updates.

    This agent:
    - Monitors for break/fix incidents via IncidentDetector
    - Generates new runbooks for unique incidents via RunbookGenerator
    - Updates existing runbooks with new knowledge via RunbookUpdater
    - Manages storage and indexing via RunbookRepository

    Usage:
        agent = RunbookAgent()

        # Process recent incidents automatically
        stats = await agent.process_recent_incidents(hours=24)

        # Generate from a specific incident
        result = await agent.generate_from_incident(incident)

        # Update an existing runbook
        result = await agent.update_runbook_with_incident(
            "docs/runbooks/EXAMPLE.md",
            incident
        )
    """

    def __init__(
        self,
        region: str = "us-east-1",
        project_name: str = "aura",
        environment: str = "dev",
        runbooks_dir: str = "docs/runbooks",
        use_llm: bool = True,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        auto_apply: bool = False,
        similarity_threshold: float = 0.7,
        confidence_threshold: float = 0.6,
    ):
        """
        Initialize the Runbook Agent.

        Args:
            region: AWS region for services
            project_name: Project name for resource naming
            environment: Environment (dev, qa, prod)
            runbooks_dir: Directory for storing runbooks
            use_llm: Whether to use LLM for content enhancement
            model_id: Bedrock model ID for LLM generation
            auto_apply: Whether to automatically apply changes (vs dry-run)
            similarity_threshold: Threshold for matching existing runbooks
            confidence_threshold: Minimum confidence for processing incidents
        """
        self.region = region
        self.project_name = project_name
        self.environment = environment
        self.runbooks_dir = runbooks_dir
        self.use_llm = use_llm
        self.model_id = model_id
        self.auto_apply = auto_apply
        self.similarity_threshold = similarity_threshold
        self.confidence_threshold = confidence_threshold

        # Initialize components
        self.detector = IncidentDetector(
            region=region,
            project_name=project_name,
            environment=environment,
        )

        self.generator = RunbookGenerator(
            region=region,
            use_llm=use_llm,
            model_id=model_id,
            runbooks_dir=runbooks_dir,
        )

        self.updater = RunbookUpdater(
            region=region,
            use_llm=use_llm,
            model_id=model_id,
            runbooks_dir=runbooks_dir,
        )

        self.repository = RunbookRepository(
            region=region,
            project_name=project_name,
            environment=environment,
            runbooks_dir=runbooks_dir,
        )

        # EventBridge for triggering automated runs
        self.eventbridge_client = boto3.client("events", region_name=region)

    async def process_recent_incidents(
        self,
        hours: int = 24,
        sources: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> ProcessingStats:
        """
        Process recent incidents and generate/update runbooks.

        Args:
            hours: Number of hours to look back
            sources: Sources to check (codebuild, cloudformation, cloudwatch, git)
            dry_run: If True, don't actually create/update files

        Returns:
            Statistics from the processing run
        """
        start_time = datetime.now()
        stats = ProcessingStats()

        logger.info(f"Processing incidents from the last {hours} hours")

        try:
            # Detect incidents
            incidents = await self.detector.detect_incidents(
                hours=hours,
                sources=sources,
            )
            stats.incidents_detected = len(incidents)
            logger.info(f"Detected {len(incidents)} incidents")

            # Process each incident
            for incident in incidents:
                if incident.confidence < self.confidence_threshold:
                    logger.info(
                        f"Skipping incident {incident.id} - confidence "
                        f"{incident.confidence:.0%} below threshold"
                    )
                    stats.runbooks_skipped += 1
                    continue

                try:
                    result = await self._process_incident(incident, dry_run=dry_run)

                    if result.action == "created":
                        stats.runbooks_created += 1
                    elif result.action == "updated":
                        stats.runbooks_updated += 1
                    elif result.action == "skipped":
                        stats.runbooks_skipped += 1
                    else:
                        stats.errors += 1

                except Exception as e:
                    logger.error(f"Error processing incident {incident.id}: {e}")
                    stats.errors += 1

        except Exception as e:
            logger.error(f"Error detecting incidents: {e}")
            stats.errors += 1

        stats.processing_time_seconds = (datetime.now() - start_time).total_seconds()
        logger.info(f"Processing complete: {stats.to_dict()}")

        return stats

    async def _process_incident(
        self,
        incident: Incident,
        dry_run: bool = False,
    ) -> RunbookAgentResult:
        """Process a single incident to generate or update a runbook."""
        logger.info(f"Processing incident {incident.id}: {incident.title}")

        # Check for existing similar runbooks
        similar_runbooks = await self.generator.find_similar_runbooks(
            incident,
            threshold=self.similarity_threshold,
        )

        if similar_runbooks:
            # Update the most similar runbook
            best_match = similar_runbooks[0]
            logger.info(
                f"Found similar runbook: {best_match['filename']} "
                f"(similarity: {best_match['similarity']:.0%})"
            )

            return await self._update_existing_runbook(
                best_match["path"],
                incident,
                dry_run=dry_run,
            )
        else:
            # Generate a new runbook
            logger.info("No similar runbook found, generating new one")
            return await self._generate_new_runbook(incident, dry_run=dry_run)

    async def _generate_new_runbook(
        self,
        incident: Incident,
        dry_run: bool = False,
    ) -> RunbookAgentResult:
        """Generate a new runbook from an incident."""
        try:
            # Generate runbook content
            generated = await self.generator.generate_runbook(incident)

            if dry_run:
                return RunbookAgentResult(
                    success=True,
                    action="created",
                    runbook_path=f"{self.runbooks_dir}/{generated.filename}",
                    incident_id=incident.id,
                    message=f"[DRY RUN] Would create runbook: {generated.filename}",
                    metadata={
                        "title": generated.title,
                        "incident_type": incident.incident_type.value,
                        "services": generated.services,
                    },
                )

            # Save to repository
            metadata = await self.repository.save_runbook(
                title=generated.title,
                content=generated.content,
                filename=generated.filename,
                error_signatures=generated.error_signatures,
                services=generated.services,
                keywords=generated.keywords,
                incident_types=[incident.incident_type.value],
                auto_generated=True,
                metadata={
                    "incident_id": incident.id,
                    "source": incident.source,
                    "source_id": incident.source_id,
                },
            )

            logger.info(f"Created runbook: {metadata.file_path}")

            return RunbookAgentResult(
                success=True,
                action="created",
                runbook_path=metadata.file_path,
                incident_id=incident.id,
                message=f"Created runbook: {generated.filename}",
                metadata={
                    "runbook_id": metadata.id,
                    "title": generated.title,
                    "confidence": generated.confidence,
                },
            )

        except Exception as e:
            logger.error(f"Error generating runbook: {e}")
            return RunbookAgentResult(
                success=False,
                action="error",
                incident_id=incident.id,
                message=f"Error generating runbook: {str(e)}",
            )

    async def _update_existing_runbook(
        self,
        runbook_path: str,
        incident: Incident,
        dry_run: bool = False,
    ) -> RunbookAgentResult:
        """Update an existing runbook with new incident information."""
        try:
            # Check if update is needed
            should_update, reason = await self.updater.should_update(
                runbook_path, incident
            )

            if not should_update:
                return RunbookAgentResult(
                    success=True,
                    action="skipped",
                    runbook_path=runbook_path,
                    incident_id=incident.id,
                    message=f"Skipped update: {reason}",
                )

            # Determine update type
            update_type = self._determine_update_type(incident)

            # Generate update
            update = await self.updater.update_runbook(
                runbook_path,
                incident,
                update_type=update_type,
            )

            if dry_run:
                return RunbookAgentResult(
                    success=True,
                    action="updated",
                    runbook_path=runbook_path,
                    incident_id=incident.id,
                    message=f"[DRY RUN] Would update runbook: {runbook_path}",
                    metadata={
                        "update_type": update_type,
                        "sections_modified": update.sections_modified,
                        "requires_review": update.requires_review,
                    },
                )

            # Apply update
            if self.auto_apply or not update.requires_review:
                success = await self.updater.apply_update(update)

                if success:
                    # Update repository index
                    await self.repository.update_runbook(
                        runbook_path,
                        update.updated_content,
                        additional_signatures=[
                            sig.pattern for sig in incident.error_signatures
                        ],
                        additional_keywords=incident.affected_services,
                    )

                    return RunbookAgentResult(
                        success=True,
                        action="updated",
                        runbook_path=runbook_path,
                        incident_id=incident.id,
                        message=f"Updated runbook: {runbook_path}",
                        metadata={
                            "update_type": update_type,
                            "sections_modified": update.sections_modified,
                            "diff_summary": update.diff_summary,
                        },
                    )
                else:
                    return RunbookAgentResult(
                        success=False,
                        action="error",
                        runbook_path=runbook_path,
                        incident_id=incident.id,
                        message="Failed to apply update",
                    )
            else:
                # Return pending review status
                return RunbookAgentResult(
                    success=True,
                    action="pending_review",
                    runbook_path=runbook_path,
                    incident_id=incident.id,
                    message="Update requires manual review",
                    metadata={
                        "update_type": update_type,
                        "sections_modified": update.sections_modified,
                        "requires_review": True,
                        "diff_summary": update.diff_summary,
                    },
                )

        except Exception as e:
            logger.error(f"Error updating runbook: {e}")
            return RunbookAgentResult(
                success=False,
                action="error",
                runbook_path=runbook_path,
                incident_id=incident.id,
                message=f"Error updating runbook: {str(e)}",
            )

    def _determine_update_type(self, incident: Incident) -> str:
        """Determine the appropriate update type based on incident."""
        # Check for new resolution steps
        if incident.resolution_steps:
            return "add_resolution"

        # Check for new symptoms
        if incident.error_messages:
            return "add_symptom"

        # Check for prevention patterns
        if incident.incident_type in (
            IncidentType.SECURITY_FIX,
            IncidentType.IAM_PERMISSION_FIX,
        ):
            return "add_prevention"

        # Default to general enhancement
        return "enhance"

    async def generate_from_incident(
        self,
        incident: Incident,
        force_new: bool = False,
    ) -> RunbookAgentResult:
        """
        Generate a runbook from a specific incident.

        Args:
            incident: The incident to document
            force_new: If True, create new runbook even if similar exists

        Returns:
            Result of the operation
        """
        if force_new:
            return await self._generate_new_runbook(incident)
        else:
            return await self._process_incident(incident)

    async def update_runbook_with_incident(
        self,
        runbook_path: str,
        incident: Incident,
        update_type: str = "add_resolution",
    ) -> RunbookAgentResult:
        """
        Update a specific runbook with incident information.

        Args:
            runbook_path: Path to the runbook to update
            incident: Incident with new information
            update_type: Type of update (add_resolution, add_symptom, etc.)

        Returns:
            Result of the operation
        """
        return await self._update_existing_runbook(runbook_path, incident)

    async def sync_repository(self) -> int:
        """
        Synchronize the runbook repository index with filesystem.

        Returns:
            Number of runbooks indexed
        """
        return await self.repository.sync_index()

    async def search_runbooks(
        self,
        error_pattern: Optional[str] = None,
        service: Optional[str] = None,
        keyword: Optional[str] = None,
        incident_type: Optional[str] = None,
    ) -> list[RunbookMetadata]:
        """
        Search for runbooks matching criteria.

        Args:
            error_pattern: Error pattern to match
            service: Service to filter by
            keyword: Keyword to search for
            incident_type: Incident type to filter

        Returns:
            List of matching runbook metadata
        """
        return await self.repository.search(
            error_pattern=error_pattern,
            service=service,
            keyword=keyword,
            incident_type=incident_type,
        )

    async def find_runbook_for_error(
        self,
        error_message: str,
    ) -> Optional[tuple[RunbookMetadata, float]]:
        """
        Find the best matching runbook for an error message.

        Args:
            error_message: The error message to match

        Returns:
            Tuple of (runbook metadata, confidence) or None
        """
        matches = await self.repository.find_by_error_signature(
            error_message,
            threshold=0.5,
        )

        if matches:
            return matches[0]
        return None

    async def record_resolution(
        self,
        runbook_id: str,
        resolution_time_minutes: float,
    ) -> None:
        """
        Record that a runbook was used for resolution.

        Args:
            runbook_id: ID of the runbook used
            resolution_time_minutes: Time to resolution in minutes
        """
        await self.repository.record_usage(runbook_id, resolution_time_minutes)

    async def setup_automated_trigger(
        self,
        schedule_expression: str = "rate(1 hour)",
        enabled: bool = True,
    ) -> str:
        """
        Set up an EventBridge rule for automated incident processing.

        Args:
            schedule_expression: EventBridge schedule expression
            enabled: Whether the rule is enabled

        Returns:
            ARN of the created rule
        """
        rule_name = f"{self.project_name}-runbook-agent-{self.environment}"

        try:
            # Create or update the rule
            response = self.eventbridge_client.put_rule(
                Name=rule_name,
                ScheduleExpression=schedule_expression,
                State="ENABLED" if enabled else "DISABLED",
                Description="Triggers Runbook Agent for automated incident processing",
            )

            rule_arn: str = str(response["RuleArn"])
            logger.info(f"Created EventBridge rule: {rule_name}")

            return rule_arn

        except ClientError as e:
            logger.error(f"Error creating EventBridge rule: {e}")
            raise

    async def get_stats(self) -> dict:
        """
        Get statistics about the runbook repository.

        Returns:
            Dictionary with repository statistics
        """
        all_runbooks = await self.repository.list_all()

        total_resolutions = sum(r.resolution_count for r in all_runbooks)
        auto_generated = sum(1 for r in all_runbooks if r.auto_generated)

        services = set()
        incident_types = set()
        for r in all_runbooks:
            services.update(r.services)
            incident_types.update(r.incident_types)

        return {
            "total_runbooks": len(all_runbooks),
            "auto_generated": auto_generated,
            "manually_created": len(all_runbooks) - auto_generated,
            "total_resolutions": total_resolutions,
            "unique_services": list(services),
            "incident_types": list(incident_types),
        }
