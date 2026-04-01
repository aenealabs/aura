"""
Runbook Generator Service

Creates new runbooks from incident context using templates and LLM enhancement.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

import boto3
from botocore.exceptions import ClientError

from .incident_detector import Incident, IncidentType

logger = logging.getLogger(__name__)


@dataclass
class GeneratedRunbook:
    """Represents a generated runbook."""

    title: str
    filename: str
    content: str
    incident_id: str
    incident_type: IncidentType
    error_signatures: list[str]
    services: list[str]
    keywords: list[str]
    confidence: float
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "title": self.title,
            "filename": self.filename,
            "incident_id": self.incident_id,
            "incident_type": self.incident_type.value,
            "error_signatures": self.error_signatures,
            "services": self.services,
            "keywords": self.keywords,
            "confidence": self.confidence,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
        }


class RunbookGenerator:
    """
    Generates runbooks from detected incidents.

    Uses a template-based approach with optional LLM enhancement
    for more natural and comprehensive documentation.
    """

    # Default runbook template
    RUNBOOK_TEMPLATE = """# Runbook: {title}

**Purpose:** {purpose}

**Audience:** {audience}

**Estimated Time:** {estimated_time}

**Last Updated:** {last_updated}

---

## Problem Description

{problem_description}

### Symptoms

```
{symptoms}
```

### Root Cause

{root_cause}

---

## Quick Resolution

{quick_resolution}

---

## Detailed Diagnostic Steps

{diagnostic_steps}

---

## Resolution Procedures

{resolution_procedures}

---

## Prevention

{prevention}

---

## Related Documentation

{related_docs}

---

## Appendix

{appendix}
"""

    # Incident type to template customization mapping
    INCIDENT_TEMPLATES = {
        IncidentType.DOCKER_BUILD_FIX: {
            "audience": "DevOps Engineers, Platform Team",
            "estimated_time": "15-30 minutes",
            "keywords": ["docker", "container", "build", "ecr"],
        },
        IncidentType.IAM_PERMISSION_FIX: {
            "audience": "DevOps Engineers, Security Team",
            "estimated_time": "15-45 minutes",
            "keywords": ["iam", "permissions", "access", "policy"],
        },
        IncidentType.CLOUDFORMATION_STACK_FIX: {
            "audience": "DevOps Engineers, Platform Team",
            "estimated_time": "10-30 minutes",
            "keywords": ["cloudformation", "stack", "infrastructure"],
        },
        IncidentType.ECR_CONFLICT_RESOLUTION: {
            "audience": "DevOps Engineers, Platform Team",
            "estimated_time": "10-20 minutes",
            "keywords": ["ecr", "repository", "conflict", "container"],
        },
        IncidentType.SHELL_SYNTAX_FIX: {
            "audience": "DevOps Engineers, Platform Team",
            "estimated_time": "10-15 minutes",
            "keywords": ["bash", "shell", "syntax", "buildspec"],
        },
        IncidentType.CODEBUILD_FAILURE_RECOVERY: {
            "audience": "DevOps Engineers, On-call Engineers",
            "estimated_time": "15-30 minutes",
            "keywords": ["codebuild", "cicd", "deployment", "build"],
        },
    }

    def __init__(
        self,
        region: str = "us-east-1",
        use_llm: bool = True,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        runbooks_dir: str = "docs/runbooks",
    ):
        """
        Initialize the runbook generator.

        Args:
            region: AWS region for Bedrock
            use_llm: Whether to use LLM for content enhancement
            model_id: Bedrock model ID for LLM generation
            runbooks_dir: Directory where runbooks are stored
        """
        self.region = region
        self.use_llm = use_llm
        self.model_id = model_id
        self.runbooks_dir = Path(runbooks_dir)

        if use_llm:
            self.bedrock_client = boto3.client("bedrock-runtime", region_name=region)

    async def generate_runbook(
        self,
        incident: Incident,
        enhance_with_llm: Optional[bool] = None,
    ) -> GeneratedRunbook:
        """
        Generate a runbook from an incident.

        Args:
            incident: The detected incident
            enhance_with_llm: Override LLM usage for this generation

        Returns:
            Generated runbook with content and metadata
        """
        use_llm = enhance_with_llm if enhance_with_llm is not None else self.use_llm

        # Get template customization for this incident type
        template_config = self.INCIDENT_TEMPLATES.get(
            incident.incident_type,
            {
                "audience": "DevOps Engineers, Platform Team, On-call Engineers",
                "estimated_time": "15-30 minutes",
                "keywords": ["infrastructure", "deployment"],
            },
        )

        # Generate base content from template
        base_content = self._generate_from_template(incident, template_config)

        # Optionally enhance with LLM
        if use_llm:
            try:
                enhanced_content = await self._enhance_with_llm(base_content, incident)
                content = enhanced_content
            except Exception as e:
                logger.warning(f"LLM enhancement failed, using base content: {e}")
                content = base_content
        else:
            content = base_content

        # Generate filename
        filename = self._generate_filename(incident)

        # Collect keywords
        keywords = list(template_config.get("keywords", []))
        keywords.extend(incident.affected_services)
        for sig in incident.error_signatures:
            keywords.extend(sig.keywords)
        keywords = list(set(keywords))

        return GeneratedRunbook(
            title=incident.title,
            filename=filename,
            content=content,
            incident_id=incident.id,
            incident_type=incident.incident_type,
            error_signatures=[sig.pattern for sig in incident.error_signatures],
            services=incident.affected_services,
            keywords=keywords,
            confidence=incident.confidence,
            metadata={
                "source": incident.source,
                "source_id": incident.source_id,
                "resolution_duration_minutes": incident.resolution_duration_minutes,
            },
        )

    def _generate_from_template(
        self,
        incident: Incident,
        template_config: dict,
    ) -> str:
        """Generate runbook content from template."""
        # Format symptoms
        symptoms = (
            "\n".join(incident.error_messages) or "No specific error messages captured."
        )

        # Format quick resolution
        quick_resolution = self._format_quick_resolution(incident)

        # Format diagnostic steps
        diagnostic_steps = self._format_diagnostic_steps(incident)

        # Format resolution procedures
        resolution_procedures = self._format_resolution_procedures(incident)

        # Format prevention
        prevention = self._format_prevention(incident)

        # Format related docs
        related_docs = self._format_related_docs(incident)

        # Format appendix
        appendix = self._format_appendix(incident)

        return self.RUNBOOK_TEMPLATE.format(
            title=incident.title,
            purpose=incident.description,
            audience=template_config.get("audience", "DevOps Engineers"),
            estimated_time=template_config.get("estimated_time", "15-30 minutes"),
            last_updated=datetime.now().strftime("%b %d, %Y"),
            problem_description=self._format_problem_description(incident),
            symptoms=symptoms,
            root_cause=incident.root_cause,
            quick_resolution=quick_resolution,
            diagnostic_steps=diagnostic_steps,
            resolution_procedures=resolution_procedures,
            prevention=prevention,
            related_docs=related_docs,
            appendix=appendix,
        )

    def _format_problem_description(self, incident: Incident) -> str:
        """Format the problem description section."""
        parts = [incident.description]

        if incident.affected_services:
            services = ", ".join(incident.affected_services)
            parts.append(f"\n**Affected Services:** {services}")

        if incident.affected_resources:
            resources = ", ".join(incident.affected_resources[:5])
            parts.append(f"\n**Affected Resources:** {resources}")

        return "\n".join(parts)

    def _format_quick_resolution(self, incident: Incident) -> str:
        """Format the quick resolution section."""
        if incident.resolution_steps:
            steps = []
            for i, step in enumerate(incident.resolution_steps[:5], 1):
                steps.append(f"### Step {i}: {step.description or 'Execute command'}")
                steps.append(f"\n```bash\n{step.command}\n```\n")
            return "\n".join(steps)

        # Generate generic quick resolution based on incident type
        quick_fixes = {
            IncidentType.DOCKER_BUILD_FIX: """### Option A: Use Explicit Platform Flag

```bash
docker build --platform linux/amd64 -t image-name .
```

### Option B: Check Base Image Architecture

```bash
docker manifest inspect base-image:tag | jq '.manifests[].platform'
```
""",
            IncidentType.IAM_PERMISSION_FIX: """### Step 1: Identify Missing Permission

```bash
aws logs filter-log-events \\
  --log-group-name /aws/codebuild/project-name \\
  --filter-pattern "AccessDenied" \\
  --query 'events[-5:].message' --output text
```

### Step 2: Update IAM Policy

Add the missing permission to the relevant IAM policy in CloudFormation.

### Step 3: Deploy Updated IAM

```bash
aws cloudformation update-stack \\
  --stack-name stack-name \\
  --template-body file://template.yaml \\
  --capabilities CAPABILITY_NAMED_IAM
```
""",
            IncidentType.CLOUDFORMATION_STACK_FIX: """### Step 1: Check Stack Status

```bash
aws cloudformation describe-stacks --stack-name stack-name \\
  --query 'Stacks[0].StackStatus' --output text
```

### Step 2: Delete Failed Stack (if ROLLBACK_COMPLETE)

```bash
aws cloudformation delete-stack --stack-name stack-name
aws cloudformation wait stack-delete-complete --stack-name stack-name
```

### Step 3: Re-deploy via CodeBuild

```bash
aws codebuild start-build --project-name project-name
```
""",
            IncidentType.ECR_CONFLICT_RESOLUTION: """### Option A: Use Existing Repository

The buildspec will automatically detect and use existing repositories.

```bash
aws ecr describe-repositories --repository-names repo-name
```

### Option B: Delete and Recreate

```bash
# WARNING: Deletes all images
aws ecr delete-repository --repository-name repo-name --force
aws codebuild start-build --project-name project-name
```
""",
            IncidentType.SHELL_SYNTAX_FIX: """### Fix: Add Bash Shell to Buildspec

Add `shell: bash` to the buildspec `env` section:

```yaml
version: 0.2

env:
  shell: bash  # Required for [[ ]] conditionals
```
""",
        }

        return quick_fixes.get(
            incident.incident_type,
            "See Detailed Diagnostic Steps below for resolution guidance.",
        )

    def _format_diagnostic_steps(self, incident: Incident) -> str:
        """Format the diagnostic steps section."""
        steps = []

        steps.append("### Step 1: Identify the Error\n")
        steps.append("```bash")
        steps.append(f"# Check {incident.source} for error details")

        if incident.source == "codebuild":
            steps.append(f"aws codebuild batch-get-builds --ids {incident.source_id}")
        elif incident.source == "cloudformation":
            steps.append(
                f"aws cloudformation describe-stack-events --stack-name {incident.source_id}"
            )
        else:
            steps.append("# Review logs for error messages")

        steps.append("```\n")

        steps.append("### Step 2: Review Error Messages\n")
        if incident.error_messages:
            steps.append("The following errors were observed:\n")
            for msg in incident.error_messages[:5]:
                steps.append(f"- `{msg[:100]}...`" if len(msg) > 100 else f"- `{msg}`")
        else:
            steps.append("Review the logs for specific error messages.\n")

        steps.append("\n### Step 3: Verify Root Cause\n")
        steps.append(f"**Identified Root Cause:** {incident.root_cause}\n")

        return "\n".join(steps)

    def _format_resolution_procedures(self, incident: Incident) -> str:
        """Format the resolution procedures section."""
        procedures = []

        procedures.append("### Procedure 1: Standard Resolution\n")
        procedures.append(self._format_quick_resolution(incident))

        procedures.append("\n### Procedure 2: Verification\n")
        procedures.append("After applying the fix, verify the resolution:\n")
        procedures.append("```bash")

        if incident.source == "codebuild":
            procedures.append("# Re-run the build")
            procedures.append("aws codebuild start-build --project-name $PROJECT_NAME")
            procedures.append("")
            procedures.append("# Monitor build status")
            procedures.append(
                "aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].buildStatus'"
            )
        elif incident.source == "cloudformation":
            procedures.append("# Check stack status")
            procedures.append(
                "aws cloudformation describe-stacks --stack-name $STACK_NAME"
            )

        procedures.append("```\n")

        return "\n".join(procedures)

    def _format_prevention(self, incident: Incident) -> str:
        """Format the prevention section."""
        prevention = []

        prevention.append("### Recommended Preventive Measures\n")

        # Add generic prevention based on incident type
        prevention_tips = {
            IncidentType.DOCKER_BUILD_FIX: [
                "Always specify `--platform linux/amd64` in Docker build commands",
                "Add architecture verification to buildspecs",
                "Use multi-platform base images where possible",
            ],
            IncidentType.IAM_PERMISSION_FIX: [
                "Review IAM policies before adding new CloudFormation resources",
                "Use a checklist for common permission requirements",
                "Implement least-privilege with specific resource ARNs",
            ],
            IncidentType.CLOUDFORMATION_STACK_FIX: [
                "Check stack status before operations",
                "Handle failed states in automation",
                "Use `--no-fail-on-empty-changeset` for updates",
            ],
            IncidentType.ECR_CONFLICT_RESOLUTION: [
                "Check for existing resources before CloudFormation creates",
                "Use `DeletionPolicy: Retain` for persistent resources",
                "Document resources created outside CloudFormation",
            ],
            IncidentType.SHELL_SYNTAX_FIX: [
                "Always set `shell: bash` in buildspecs",
                "Test scripts with `shellcheck` before committing",
                "Avoid bash-specific syntax or explicitly require bash",
            ],
        }

        tips = prevention_tips.get(
            incident.incident_type,
            [
                "Document lessons learned from this incident",
                "Add monitoring for early detection",
                "Consider automation to prevent recurrence",
            ],
        )

        for tip in tips:
            prevention.append(f"- {tip}")

        return "\n".join(prevention)

    def _format_related_docs(self, incident: Incident) -> str:
        """Format the related documentation section."""
        docs = []

        # Add links based on services
        service_docs = {
            "docker": "- [Docker Platform Documentation](https://docs.docker.com/build/building/multi-platform/)",
            "ecr": "- [AWS ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/)",
            "cloudformation": "- [AWS CloudFormation User Guide](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/)",
            "iam": "- [AWS IAM User Guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/)",
            "codebuild": "- [AWS CodeBuild User Guide](https://docs.aws.amazon.com/codebuild/latest/userguide/)",
            "bedrock": "- [AWS Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/)",
        }

        for service in incident.affected_services:
            if service in service_docs:
                docs.append(service_docs[service])

        # Add internal runbook references
        docs.append("- [Project Runbooks Index](../../docs/runbooks/)")
        docs.append(
            "- [CLAUDE.md - CI/CD Section](../../CLAUDE.md#cicd-best-practices)"
        )

        return "\n".join(docs)

    def _format_appendix(self, incident: Incident) -> str:
        """Format the appendix section."""
        appendix = []

        appendix.append("### Incident Metadata\n")
        appendix.append("| Field | Value |")
        appendix.append("|-------|-------|")
        appendix.append(f"| Incident ID | `{incident.id}` |")
        appendix.append(f"| Type | {incident.incident_type.value} |")
        appendix.append(f"| Source | {incident.source} |")
        appendix.append(
            f"| Resolution Time | {incident.resolution_duration_minutes:.1f} minutes |"
        )
        appendix.append(f"| Confidence | {incident.confidence:.0%} |")

        if incident.metadata:
            appendix.append("\n### Additional Details\n")
            for key, value in incident.metadata.items():
                appendix.append(f"- **{key}:** `{value}`")

        return "\n".join(appendix)

    def _generate_filename(self, incident: Incident) -> str:
        """Generate a filename for the runbook."""
        # Clean up title for filename
        title = incident.title.upper()
        title = re.sub(r"[^A-Z0-9\s]", "", title)
        title = re.sub(r"\s+", "_", title)
        title = title[:50]  # Limit length

        return f"{title}.md"

    async def _enhance_with_llm(
        self,
        base_content: str,
        incident: Incident,
    ) -> str:
        """Enhance runbook content using LLM."""
        prompt = f"""You are a technical writer creating operational runbooks for a DevOps team.

I have a draft runbook that was auto-generated from an incident. Please enhance it to make it more:
1. Clear and actionable
2. Complete with all necessary details
3. Following best practices for operational documentation

Here is the incident context:
- Type: {incident.incident_type.value}
- Root Cause: {incident.root_cause}
- Error Messages: {json.dumps(incident.error_messages[:5])}
- Affected Services: {incident.affected_services}

Here is the draft runbook:

{base_content}

Please enhance this runbook while:
1. Keeping the same structure and sections
2. Adding more specific commands where helpful
3. Improving clarity of explanations
4. Adding any missing important steps
5. NOT adding any AI attribution or mentions of being auto-generated

Return ONLY the enhanced runbook content in markdown format."""

        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )

            response_body = json.loads(response["body"].read())
            enhanced_content = response_body["content"][0]["text"]

            return str(enhanced_content)

        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            raise

    async def find_similar_runbooks(
        self,
        incident: Incident,
        threshold: float = 0.7,
    ) -> list[dict]:
        """
        Find existing runbooks similar to the incident.

        Args:
            incident: The incident to match
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            List of similar runbooks with similarity scores
        """
        similar = []

        # Scan existing runbooks
        if self.runbooks_dir.exists():
            for runbook_path in self.runbooks_dir.glob("*.md"):
                try:
                    content = runbook_path.read_text()

                    # Calculate similarity based on keyword matching
                    score = self._calculate_similarity(incident, content)

                    if score >= threshold:
                        similar.append(
                            {
                                "path": str(runbook_path),
                                "filename": runbook_path.name,
                                "similarity": score,
                            }
                        )
                except Exception as e:
                    logger.warning(f"Error reading {runbook_path}: {e}")

        # Sort by similarity
        similar.sort(key=lambda x: cast(float, x["similarity"]), reverse=True)

        return similar[:5]  # Return top 5

    def _calculate_similarity(self, incident: Incident, content: str) -> float:
        """Calculate similarity between incident and runbook content."""
        content_lower = content.lower()

        # Check for error signature matches
        signature_matches = sum(
            1
            for sig in incident.error_signatures
            if re.search(sig.pattern, content, re.IGNORECASE)
        )

        # Check for service matches
        service_matches = sum(
            1
            for service in incident.affected_services
            if service.lower() in content_lower
        )

        # Check for keyword matches
        all_keywords = set()
        for sig in incident.error_signatures:
            all_keywords.update(sig.keywords)

        keyword_matches = sum(1 for kw in all_keywords if kw.lower() in content_lower)

        # Calculate weighted score
        total_possible = (
            len(incident.error_signatures) * 3
            + len(incident.affected_services) * 2
            + len(all_keywords)
        )

        if total_possible == 0:
            return 0.0

        score = (
            signature_matches * 3 + service_matches * 2 + keyword_matches
        ) / total_possible

        return min(score, 1.0)
