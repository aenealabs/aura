"""
Runbook Updater Service

Maintains existing runbooks with new knowledge from incidents.
Handles non-destructive updates, version tracking, and merge logic.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .incident_detector import Incident

logger = logging.getLogger(__name__)


@dataclass
class RunbookUpdate:
    """Represents an update to an existing runbook."""

    runbook_path: str
    original_content: str
    updated_content: str
    incident_id: str
    update_type: str  # "add_resolution", "add_symptom", "add_prevention", "enhance"
    sections_modified: list[str]
    diff_summary: str
    confidence: float
    requires_review: bool
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_significant_changes(self) -> bool:
        """Check if the update has significant changes."""
        return len(self.sections_modified) > 2 or self.update_type == "enhance"


class RunbookUpdater:
    """
    Updates existing runbooks with new incident knowledge.

    Features:
    - Non-destructive updates (adds sections, doesn't remove)
    - Version tracking via git or metadata
    - Smart merging of resolution steps
    - Review workflow integration
    """

    # Section markers for parsing runbooks
    SECTION_PATTERNS = {
        "symptoms": r"##\s*Symptoms?\s*\n",
        "root_cause": r"##\s*Root\s+Cause\s*\n",
        "quick_resolution": r"##\s*Quick\s+Resolution\s*\n",
        "diagnostic_steps": r"##\s*(?:Detailed\s+)?Diagnostic\s+Steps?\s*\n",
        "resolution_procedures": r"##\s*Resolution\s+Procedures?\s*\n",
        "prevention": r"##\s*Prevention\s*\n",
        "related_docs": r"##\s*Related\s+Documentation\s*\n",
        "appendix": r"##\s*Appendix\s*\n",
    }

    def __init__(
        self,
        region: str = "us-east-1",
        use_llm: bool = True,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        runbooks_dir: str = "docs/runbooks",
        require_review_threshold: float = 0.5,
    ):
        """
        Initialize the runbook updater.

        Args:
            region: AWS region for Bedrock
            use_llm: Whether to use LLM for content enhancement
            model_id: Bedrock model ID
            runbooks_dir: Directory where runbooks are stored
            require_review_threshold: Confidence below this requires review
        """
        self.region = region
        self.use_llm = use_llm
        self.model_id = model_id
        self.runbooks_dir = Path(runbooks_dir)
        self.require_review_threshold = require_review_threshold

        if use_llm:
            self.bedrock_client = boto3.client("bedrock-runtime", region_name=region)

    async def update_runbook(
        self,
        runbook_path: str,
        incident: Incident,
        update_type: str = "add_resolution",
    ) -> RunbookUpdate:
        """
        Update an existing runbook with new incident information.

        Args:
            runbook_path: Path to the runbook file
            incident: The incident with new information
            update_type: Type of update to perform

        Returns:
            RunbookUpdate with the changes
        """
        path = Path(runbook_path)
        if not path.exists():
            raise FileNotFoundError(f"Runbook not found: {runbook_path}")

        original_content = path.read_text()

        # Parse the runbook into sections
        sections = self._parse_runbook_sections(original_content)

        # Determine what needs updating
        updates_needed = self._analyze_update_needs(sections, incident)

        # Apply updates based on type
        if update_type == "add_resolution":
            updated_content, modified_sections = await self._add_resolution(
                original_content, sections, incident
            )
        elif update_type == "add_symptom":
            updated_content, modified_sections = await self._add_symptom(
                original_content, sections, incident
            )
        elif update_type == "add_prevention":
            updated_content, modified_sections = await self._add_prevention(
                original_content, sections, incident
            )
        elif update_type == "enhance":
            updated_content, modified_sections = await self._enhance_runbook(
                original_content, incident
            )
        else:
            raise ValueError(f"Unknown update type: {update_type}")

        # Update the "Last Updated" date
        updated_content = self._update_metadata(updated_content)

        # Generate diff summary
        diff_summary = self._generate_diff_summary(
            original_content, updated_content, modified_sections
        )

        # Determine if review is required
        requires_review = (
            incident.confidence < self.require_review_threshold
            or len(modified_sections) > 3
            or update_type == "enhance"
        )

        return RunbookUpdate(
            runbook_path=runbook_path,
            original_content=original_content,
            updated_content=updated_content,
            incident_id=incident.id,
            update_type=update_type,
            sections_modified=modified_sections,
            diff_summary=diff_summary,
            confidence=incident.confidence,
            requires_review=requires_review,
            metadata={
                "incident_source": incident.source,
                "incident_type": incident.incident_type.value,
                "updates_needed": updates_needed,
            },
        )

    def _parse_runbook_sections(self, content: str) -> dict[str, str]:
        """Parse runbook content into sections."""
        sections = {}

        # Find all section boundaries
        section_positions = []
        for name, pattern in self.SECTION_PATTERNS.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                section_positions.append((match.start(), name, match.end()))

        # Sort by position
        section_positions.sort(key=lambda x: x[0])

        # Extract section content
        for i, (_start, name, content_start) in enumerate(section_positions):
            if i + 1 < len(section_positions):
                next_start = section_positions[i + 1][0]
                sections[name] = content[content_start:next_start].strip()
            else:
                sections[name] = content[content_start:].strip()

        return sections

    def _analyze_update_needs(
        self,
        sections: dict[str, str],
        incident: Incident,
    ) -> list[str]:
        """Analyze what sections need updating based on incident."""
        needs = []

        # Check for new error messages not in symptoms
        symptoms = sections.get("symptoms", "")
        for msg in incident.error_messages:
            if msg[:50] not in symptoms:
                needs.append("new_symptom")
                break

        # Check for new resolution steps
        resolution = sections.get("quick_resolution", "") + sections.get(
            "resolution_procedures", ""
        )
        for step in incident.resolution_steps:
            if step.command not in resolution:
                needs.append("new_resolution")
                break

        # Check if root cause adds new information
        root_cause = sections.get("root_cause", "")
        if incident.root_cause and incident.root_cause not in root_cause:
            needs.append("root_cause_detail")

        return list(set(needs))

    async def _add_resolution(
        self,
        content: str,
        sections: dict[str, str],
        incident: Incident,
    ) -> tuple[str, list[str]]:
        """Add new resolution steps to the runbook."""
        modified = []

        # Find the resolution procedures section
        pattern = self.SECTION_PATTERNS["resolution_procedures"]
        match = re.search(pattern, content, re.IGNORECASE)

        if not match:
            # Add resolution procedures section if missing
            content = self._add_section(
                content,
                "Resolution Procedures",
                self._format_new_resolution(incident),
            )
            modified.append("resolution_procedures")
        else:
            # Find where to insert new procedure
            insert_pos = self._find_section_end(content, match.end())

            # Format new resolution
            new_procedure = (
                f"\n\n### Alternative Resolution (from incident {incident.id})\n\n"
            )
            new_procedure += self._format_new_resolution(incident)

            # Insert
            content = content[:insert_pos] + new_procedure + content[insert_pos:]
            modified.append("resolution_procedures")

        return content, modified

    async def _add_symptom(
        self,
        content: str,
        sections: dict[str, str],
        incident: Incident,
    ) -> tuple[str, list[str]]:
        """Add new symptoms to the runbook."""
        modified: list[str] = []

        if not incident.error_messages:
            return content, modified

        pattern = self.SECTION_PATTERNS["symptoms"]
        match = re.search(pattern, content, re.IGNORECASE)

        if match:
            # Find where to insert new symptoms
            insert_pos = self._find_section_end(content, match.end())

            # Format new symptoms
            new_symptoms = "\n\nAdditional symptoms observed:\n```\n"
            new_symptoms += "\n".join(incident.error_messages[:3])
            new_symptoms += "\n```\n"

            content = content[:insert_pos] + new_symptoms + content[insert_pos:]
            modified.append("symptoms")

        return content, modified

    async def _add_prevention(
        self,
        content: str,
        sections: dict[str, str],
        incident: Incident,
    ) -> tuple[str, list[str]]:
        """Add new prevention measures to the runbook."""
        modified = []

        pattern = self.SECTION_PATTERNS["prevention"]
        match = re.search(pattern, content, re.IGNORECASE)

        if match:
            insert_pos = self._find_section_end(content, match.end())

            # Generate prevention from incident
            prevention = (
                f"\n\n### Additional Prevention (from incident {incident.id})\n\n"
            )
            prevention += f"- Monitor for similar patterns: `{incident.error_signatures[0].pattern if incident.error_signatures else 'N/A'}`\n"
            prevention += (
                f"- Affected services: {', '.join(incident.affected_services)}\n"
            )

            content = content[:insert_pos] + prevention + content[insert_pos:]
            modified.append("prevention")

        return content, modified

    async def _enhance_runbook(
        self,
        content: str,
        incident: Incident,
    ) -> tuple[str, list[str]]:
        """Use LLM to enhance the entire runbook with incident knowledge."""
        if not self.use_llm:
            return content, []

        prompt = f"""You are enhancing an existing operational runbook with new incident information.

Here is the current runbook:

{content}

Here is the new incident information:
- Type: {incident.incident_type.value}
- Root Cause: {incident.root_cause}
- Error Messages: {json.dumps(incident.error_messages[:5])}
- Resolution Duration: {incident.resolution_duration_minutes:.1f} minutes

Please enhance the runbook by:
1. Adding any new symptoms or error patterns
2. Adding alternative resolution steps if different from existing
3. Improving clarity based on the incident details
4. Adding any relevant prevention measures

Rules:
- Keep the existing structure
- Don't remove any existing content
- Don't add AI attribution
- Mark new additions clearly with comments like "(Added from incident analysis)"

Return ONLY the enhanced runbook content."""

        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 8192,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )

            response_body = json.loads(response["body"].read())
            enhanced = response_body["content"][0]["text"]

            # Determine which sections changed
            modified = self._detect_modified_sections(content, enhanced)

            return enhanced, modified

        except ClientError as e:
            logger.error(f"LLM enhancement failed: {e}")
            return content, []

    def _find_section_end(self, content: str, start_pos: int) -> int:
        """Find the end of a section (before next ## header or end of file)."""
        # Look for next section header
        next_header = re.search(r"\n##\s+", content[start_pos:])

        if next_header:
            return start_pos + next_header.start()
        else:
            return len(content)

    def _add_section(
        self,
        content: str,
        section_title: str,
        section_content: str,
    ) -> str:
        """Add a new section to the runbook."""
        # Find a good place to insert (before Related Documentation or at end)
        related_match = re.search(
            self.SECTION_PATTERNS["related_docs"], content, re.IGNORECASE
        )

        new_section = f"\n\n## {section_title}\n\n{section_content}\n"

        if related_match:
            return (
                content[: related_match.start()]
                + new_section
                + content[related_match.start() :]
            )
        else:
            return content + new_section

    def _format_new_resolution(self, incident: Incident) -> str:
        """Format resolution steps from incident."""
        if incident.resolution_steps:
            steps = []
            for i, step in enumerate(incident.resolution_steps, 1):
                steps.append(f"**Step {i}:** {step.description or 'Execute command'}")
                steps.append(f"```bash\n{step.command}\n```")
                if step.output:
                    steps.append(f"Expected output: `{step.output[:100]}...`")
            return "\n".join(steps)

        # Generic resolution based on incident type
        return f"""Based on incident {incident.id}:

1. Identify the issue using the error signatures
2. Apply the root cause fix: {incident.root_cause}
3. Verify resolution via {incident.source}
"""

    def _update_metadata(self, content: str) -> str:
        """Update the Last Updated date in the runbook."""
        today = datetime.now().strftime("%b %d, %Y")

        # Try to update existing date
        updated = re.sub(
            r"\*\*Last Updated:\*\*\s*.+",
            f"**Last Updated:** {today}",
            content,
        )

        return updated

    def _generate_diff_summary(
        self,
        original: str,
        updated: str,
        modified_sections: list[str],
    ) -> str:
        """Generate a human-readable diff summary."""
        original_lines = len(original.split("\n"))
        updated_lines = len(updated.split("\n"))
        lines_added = max(0, updated_lines - original_lines)

        summary = f"Modified sections: {', '.join(modified_sections)}\n"
        summary += f"Lines added: ~{lines_added}\n"

        return summary

    def _detect_modified_sections(
        self,
        original: str,
        updated: str,
    ) -> list[str]:
        """Detect which sections were modified between versions."""
        original_sections = self._parse_runbook_sections(original)
        updated_sections = self._parse_runbook_sections(updated)

        modified = []
        for name in set(original_sections.keys()) | set(updated_sections.keys()):
            orig = original_sections.get(name, "")
            upd = updated_sections.get(name, "")

            if orig != upd:
                modified.append(name)

        return modified

    async def apply_update(
        self,
        update: RunbookUpdate,
        backup: bool = True,
    ) -> bool:
        """
        Apply a runbook update to disk.

        Args:
            update: The update to apply
            backup: Whether to create a backup before updating

        Returns:
            True if successful
        """
        path = Path(update.runbook_path)

        try:
            if backup:
                # Create backup
                backup_path = path.with_suffix(
                    f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                )
                backup_path.write_text(update.original_content)
                logger.info(f"Created backup: {backup_path}")

            # Write updated content
            path.write_text(update.updated_content)
            logger.info(f"Updated runbook: {path}")

            return True

        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            return False

    async def should_update(
        self,
        runbook_path: str,
        incident: Incident,
    ) -> tuple[bool, str]:
        """
        Determine if a runbook should be updated with incident info.

        Args:
            runbook_path: Path to the runbook
            incident: The incident to potentially add

        Returns:
            Tuple of (should_update, reason)
        """
        path = Path(runbook_path)
        if not path.exists():
            return False, "Runbook does not exist"

        content = path.read_text()
        sections = self._parse_runbook_sections(content)

        # Check if incident adds new information
        updates_needed = self._analyze_update_needs(sections, incident)

        if not updates_needed:
            return False, "No new information to add"

        if incident.confidence < 0.5:
            return False, f"Incident confidence too low: {incident.confidence:.0%}"

        return True, f"Updates needed: {', '.join(updates_needed)}"
