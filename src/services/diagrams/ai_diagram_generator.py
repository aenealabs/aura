"""
AI Diagram Generator (ADR-060 Phase 2).

Generates diagram DSL from natural language descriptions using:
- Multi-provider model routing for optimal AI selection
- Intent extraction and diagram planning
- DSL generation with validation
- Iterative refinement with critique

Security:
- Prompt injection prevention via InputSanitizer
- Data classification enforcement for compliance
- All outputs validated against DSL schema
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .diagram_dsl import DiagramDSLParser, DSLParseError
from .diagram_model_router import (
    DataClassification,
    DiagramModelRouter,
    DiagramTask,
    ModelProvider,
    SecurityError,
)
from .models import DiagramDefinition

logger = logging.getLogger(__name__)


class GenerationStatus(Enum):
    """Status of diagram generation."""

    PENDING = "pending"
    EXTRACTING_INTENT = "extracting_intent"
    GENERATING_DSL = "generating_dsl"
    VALIDATING = "validating"
    REFINING = "refining"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DiagramIntent:
    """Extracted intent from natural language description."""

    title: str
    diagram_type: str  # architecture, sequence, flowchart, erd
    components: list[str]
    relationships: list[dict[str, str]]
    style_hints: list[str]
    cloud_provider: Optional[str] = None  # aws, azure, gcp
    confidence: float = 0.0


@dataclass
class GenerationResult:
    """Result of diagram generation."""

    status: GenerationStatus
    diagram: Optional[DiagramDefinition] = None
    dsl_text: str = ""
    intent: Optional[DiagramIntent] = None
    error: Optional[str] = None
    iterations: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    provider_used: Optional[ModelProvider] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AIDiagramGenerator:
    """
    AI-powered diagram generator from natural language.

    Workflow:
    1. Extract intent from user description
    2. Generate initial DSL
    3. Validate against schema
    4. Optionally critique and refine
    5. Return validated diagram
    """

    # System prompts for different tasks
    INTENT_EXTRACTION_PROMPT = """You are an expert at understanding diagram requirements.
Extract the following from the user's description:
- Title for the diagram
- Type of diagram (architecture, sequence, flowchart, erd, network)
- Key components/nodes that should appear
- Relationships between components
- Style hints (colors, groupings, layout direction)
- Cloud provider if mentioned (aws, azure, gcp)

Respond in JSON format:
{
    "title": "string",
    "diagram_type": "architecture|sequence|flowchart|erd|network",
    "components": ["component1", "component2"],
    "relationships": [{"from": "a", "to": "b", "label": "optional"}],
    "style_hints": ["hint1"],
    "cloud_provider": "aws|azure|gcp|null",
    "confidence": 0.0-1.0
}"""

    DSL_GENERATION_PROMPT = """You are an expert at creating Eraser-style diagram DSL.
Generate a complete diagram definition in YAML format based on the provided intent.

DSL Format:
```yaml
title: Diagram Title
direction: TB  # TB (top-bottom), LR (left-right), RL, BT
groups:
  - id: group_id
    label: Group Label
    children: [node1, node2]
nodes:
  - id: node_id
    label: Display Label
    icon: provider:service  # e.g., aws:lambda, azure:functions
    shape: rectangle  # rectangle, cylinder, diamond, ellipse
connections:
  - source: node_a
    target: node_b
    label: Connection Label
    style: solid  # solid, dashed, dotted
    arrow: forward  # forward, backward, both, none
```

IMPORTANT YAML Rules:
- Labels containing colons, quotes, or special characters MUST be quoted with double quotes
- Example: label: "IAM Role: DynamoDB Access" (NOT label: IAM Role: DynamoDB Access)
- Use simple, descriptive labels without special characters when possible

Use official cloud provider icons when applicable:
- AWS: aws:ec2, aws:lambda, aws:s3, aws:rds, aws:dynamodb, aws:api-gateway, aws:cloudfront, aws:vpc, aws:eks, aws:ecs, aws:alb, aws:bedrock, aws:neptune, aws:opensearch
- Azure: azure:vm, azure:functions, azure:blob, azure:sql, azure:cosmos
- GCP: gcp:compute, gcp:functions, gcp:storage, gcp:bigquery

Return ONLY the YAML content, no markdown code blocks or explanations."""

    CRITIQUE_PROMPT = """You are a diagram design expert. Review this diagram DSL for:
1. Completeness - are all mentioned components included?
2. Relationships - are connections logical and complete?
3. Layout - is the direction and grouping optimal?
4. Icons - are the correct cloud provider icons used?
5. Clarity - is the diagram easy to understand?

Provide specific suggestions for improvement in JSON format:
{
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1"],
    "score": 0.0-1.0
}

If score >= 0.8, the diagram is acceptable."""

    def __init__(
        self,
        router: DiagramModelRouter,
        max_iterations: int = 3,
        min_acceptable_score: float = 0.8,
    ):
        """
        Initialize the AI diagram generator.

        Args:
            router: Model router for AI provider selection
            max_iterations: Maximum refinement iterations
            min_acceptable_score: Minimum critique score to accept
        """
        self.router = router
        self.max_iterations = max_iterations
        self.min_acceptable_score = min_acceptable_score
        self.parser = DiagramDSLParser()

        logger.info(
            f"AIDiagramGenerator initialized with max_iterations={max_iterations}"
        )

    async def generate(
        self,
        description: str,
        classification: DataClassification = DataClassification.INTERNAL,
        enable_critique: bool = True,
        context: Optional[dict[str, Any]] = None,
    ) -> GenerationResult:
        """
        Generate diagram from natural language description.

        Args:
            description: Natural language description of desired diagram
            classification: Data classification for compliance
            enable_critique: Whether to enable iterative refinement
            context: Optional context (existing codebase info, etc.)

        Returns:
            GenerationResult with diagram or error
        """
        result = GenerationResult(status=GenerationStatus.PENDING)

        try:
            # Sanitize input
            sanitized_description = self.router.sanitize_prompt(description)

            # Step 1: Extract intent
            result.status = GenerationStatus.EXTRACTING_INTENT
            intent = await self._extract_intent(sanitized_description, classification)
            result.intent = intent
            logger.info(
                f"Extracted intent: {intent.diagram_type} with {len(intent.components)} components"
            )

            # Step 2: Generate initial DSL
            result.status = GenerationStatus.GENERATING_DSL
            dsl_text = await self._generate_dsl(intent, classification, context)
            result.dsl_text = dsl_text
            result.iterations = 1

            # Step 3: Validate DSL
            result.status = GenerationStatus.VALIDATING
            diagram = self._validate_dsl(dsl_text)

            # Step 4: Optional critique and refinement
            if enable_critique and result.iterations < self.max_iterations:
                result.status = GenerationStatus.REFINING
                diagram, dsl_text, iterations = await self._refine_diagram(
                    dsl_text, intent, classification
                )
                result.dsl_text = dsl_text
                result.iterations += iterations

            result.diagram = diagram
            result.status = GenerationStatus.COMPLETED
            logger.info(
                f"Diagram generation completed in {result.iterations} iterations"
            )

        except SecurityError as e:
            result.status = GenerationStatus.FAILED
            result.error = f"Security error: {e}"
            logger.warning(f"Diagram generation blocked: {e}")

        except DSLParseError as e:
            result.status = GenerationStatus.FAILED
            result.error = f"DSL validation error: {e}"
            logger.error(f"DSL validation failed: {e}")

        except Exception as e:
            result.status = GenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"Diagram generation failed: {e}")

        return result

    async def _extract_intent(
        self,
        description: str,
        classification: DataClassification,
    ) -> DiagramIntent:
        """Extract structured intent from description."""
        provider, model_id, client = await self.router.route_task(
            DiagramTask.INTENT_EXTRACTION,
            classification=classification,
        )

        if not client:
            raise ValueError("No provider available for intent extraction")

        response = await client.invoke(
            model_id=model_id,
            messages=[{"role": "user", "content": description}],
            system_prompt=self.INTENT_EXTRACTION_PROMPT,
            temperature=0.3,  # Lower temperature for structured extraction
        )

        # Track costs
        usage = response.get("usage", {})
        self.router.record_cost(
            provider,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )

        # Parse JSON response
        content = response.get("content", "{}")
        intent_data = self._parse_json_response(content)

        return DiagramIntent(
            title=intent_data.get("title", "Untitled Diagram"),
            diagram_type=intent_data.get("diagram_type", "architecture"),
            components=intent_data.get("components", []),
            relationships=intent_data.get("relationships", []),
            style_hints=intent_data.get("style_hints", []),
            cloud_provider=intent_data.get("cloud_provider"),
            confidence=intent_data.get("confidence", 0.5),
        )

    async def _generate_dsl(
        self,
        intent: DiagramIntent,
        classification: DataClassification,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate DSL from extracted intent."""
        provider, model_id, client = await self.router.route_task(
            DiagramTask.DSL_GENERATION,
            classification=classification,
        )

        if not client:
            raise ValueError("No provider available for DSL generation")

        # Build prompt with intent details
        intent_description = self._format_intent_for_prompt(intent)
        if context:
            intent_description += f"\n\nAdditional context:\n{context}"

        response = await client.invoke(
            model_id=model_id,
            messages=[{"role": "user", "content": intent_description}],
            system_prompt=self.DSL_GENERATION_PROMPT,
            temperature=0.7,
        )

        # Track costs
        usage = response.get("usage", {})
        self.router.record_cost(
            provider,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )

        dsl_text = response.get("content", "")

        # Clean up response (remove any markdown formatting)
        dsl_text = self._clean_dsl_response(dsl_text)

        return dsl_text

    async def _refine_diagram(
        self,
        dsl_text: str,
        intent: DiagramIntent,
        classification: DataClassification,
    ) -> tuple[DiagramDefinition, str, int]:
        """Refine diagram through critique and regeneration."""
        iterations = 0
        current_dsl = dsl_text

        while iterations < self.max_iterations - 1:
            # Get critique
            critique = await self._critique_diagram(current_dsl, intent, classification)

            if critique.get("score", 0) >= self.min_acceptable_score:
                logger.info(f"Diagram accepted with score {critique.get('score')}")
                break

            # Apply suggestions
            suggestions = critique.get("suggestions", [])
            if not suggestions:
                break

            logger.info(f"Refining diagram based on {len(suggestions)} suggestions")

            # Regenerate with feedback
            current_dsl = await self._regenerate_with_feedback(
                current_dsl, suggestions, intent, classification
            )
            iterations += 1

        # Final validation
        diagram = self._validate_dsl(current_dsl)
        return diagram, current_dsl, iterations

    async def _critique_diagram(
        self,
        dsl_text: str,
        intent: DiagramIntent,
        classification: DataClassification,
    ) -> dict[str, Any]:
        """Get critique of diagram quality."""
        provider, model_id, client = await self.router.route_task(
            DiagramTask.DIAGRAM_CRITIQUE,
            classification=classification,
        )

        if not client:
            return {"score": 1.0, "issues": [], "suggestions": []}

        prompt = f"""Original request: {intent.title}
Components expected: {', '.join(intent.components)}

Generated DSL:
```yaml
{dsl_text}
```

Review this diagram."""

        response = await client.invoke(
            model_id=model_id,
            messages=[{"role": "user", "content": prompt}],
            system_prompt=self.CRITIQUE_PROMPT,
            temperature=0.3,
        )

        # Track costs
        usage = response.get("usage", {})
        self.router.record_cost(
            provider,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )

        content = response.get("content", "{}")
        return self._parse_json_response(content)

    async def _regenerate_with_feedback(
        self,
        current_dsl: str,
        suggestions: list[str],
        intent: DiagramIntent,
        classification: DataClassification,
    ) -> str:
        """Regenerate DSL incorporating feedback."""
        provider, model_id, client = await self.router.route_task(
            DiagramTask.DSL_GENERATION,
            classification=classification,
        )

        if not client:
            return current_dsl

        feedback_text = "\n".join(f"- {s}" for s in suggestions)
        prompt = f"""Current diagram DSL:
```yaml
{current_dsl}
```

Please improve the diagram based on this feedback:
{feedback_text}

Original requirements:
- Title: {intent.title}
- Components: {', '.join(intent.components)}

Return the improved YAML DSL only."""

        response = await client.invoke(
            model_id=model_id,
            messages=[{"role": "user", "content": prompt}],
            system_prompt=self.DSL_GENERATION_PROMPT,
            temperature=0.5,
        )

        # Track costs
        usage = response.get("usage", {})
        self.router.record_cost(
            provider,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )

        dsl_text = response.get("content", current_dsl)
        return self._clean_dsl_response(dsl_text)

    def _validate_dsl(self, dsl_text: str) -> DiagramDefinition:
        """Validate DSL and return parsed diagram definition."""
        result = self.parser.parse(dsl_text)
        return result.definition

    def _format_intent_for_prompt(self, intent: DiagramIntent) -> str:
        """Format intent as prompt text."""
        lines = [
            f"Create a {intent.diagram_type} diagram titled '{intent.title}'",
            "",
            "Components to include:",
        ]
        for component in intent.components:
            lines.append(f"- {component}")

        if intent.relationships:
            lines.append("")
            lines.append("Relationships:")
            for rel in intent.relationships:
                label = f" ({rel.get('label')})" if rel.get("label") else ""
                lines.append(f"- {rel.get('from')} -> {rel.get('to')}{label}")

        if intent.cloud_provider:
            lines.append("")
            lines.append(
                f"Use {intent.cloud_provider.upper()} service icons where applicable."
            )

        if intent.style_hints:
            lines.append("")
            lines.append("Style preferences:")
            for hint in intent.style_hints:
                lines.append(f"- {hint}")

        return "\n".join(lines)

    def _clean_dsl_response(self, text: str) -> str:
        """Remove markdown code blocks and clean up DSL text."""
        # Remove markdown code blocks
        text = re.sub(r"```ya?ml\n?", "", text)
        text = re.sub(r"```\n?", "", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling common issues."""
        import json

        # Remove markdown code blocks
        text = re.sub(r"```json\n?", "", text)
        text = re.sub(r"```\n?", "", text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse JSON response: {text[:200]}")
            return {}

    async def generate_from_image(
        self,
        image_data: bytes,
        image_format: str = "png",
        description: str = "",
        classification: DataClassification = DataClassification.INTERNAL,
    ) -> GenerationResult:
        """
        Generate diagram DSL from an existing image.

        Args:
            image_data: Raw image bytes
            image_format: Image format (png, jpeg)
            description: Optional description/instructions
            classification: Data classification

        Returns:
            GenerationResult with extracted diagram
        """
        result = GenerationResult(status=GenerationStatus.PENDING)

        try:
            # Route to vision-capable model
            provider, model_id, client = await self.router.route_task(
                DiagramTask.IMAGE_UNDERSTANDING,
                classification=classification,
            )

            if not client:
                raise ValueError("No provider available for image understanding")

            prompt = description or "Analyze this diagram and extract its structure."
            prompt += """

Extract the diagram as YAML DSL with:
- title
- nodes (id, label, icon if identifiable)
- connections (source, target, label)
- groups if visible

Return only the YAML content."""

            result.status = GenerationStatus.EXTRACTING_INTENT

            # Use vision API
            response = await client.invoke_with_image(
                model_id=model_id,
                messages=[{"role": "user", "content": f"{prompt}\n\n{{IMAGE}}"}],
                image_data=image_data,
                image_format=image_format,
            )

            # Track costs
            usage = response.get("usage", {})
            self.router.record_cost(
                provider,
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0),
            )

            dsl_text = self._clean_dsl_response(response.get("content", ""))
            result.dsl_text = dsl_text

            # Validate
            result.status = GenerationStatus.VALIDATING
            result.diagram = self._validate_dsl(dsl_text)
            result.status = GenerationStatus.COMPLETED
            result.provider_used = provider

        except Exception as e:
            result.status = GenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"Image-to-diagram generation failed: {e}")

        return result
