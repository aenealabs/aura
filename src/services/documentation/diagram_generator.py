"""
Diagram Generator for Mermaid.js Output
========================================

Generates high-quality Mermaid.js diagram code from service boundaries and data flows.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

Supported diagram types:
- ARCHITECTURE: System architecture with service boundaries and layers
- DATA_FLOW: Data movement between components with flow types
- DEPENDENCY: Module and package dependencies with relationships
- SEQUENCE: Request/response flows between services
- COMPONENT: Component hierarchy within services
"""

import logging
import re
from typing import TYPE_CHECKING

from src.services.documentation.exceptions import DiagramGenerationError
from src.services.documentation.types import (
    DataFlow,
    DiagramComponent,
    DiagramResult,
    DiagramType,
    ServiceBoundary,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService


class DiagramGenerator:
    """
    Generates high-quality Mermaid.js diagrams from code analysis.

    Produces professional diagrams with:
    - Logical layer grouping (Frontend, API, Services, Data, External)
    - Styled nodes with semantic colors
    - Clear connections with labels
    - Consistent formatting
    """

    # Layer classification keywords for automatic service grouping
    LAYER_KEYWORDS = {
        "api": ["api", "endpoint", "route", "router", "handler", "controller"],
        "service": ["service", "manager", "processor", "worker", "agent"],
        "data": [
            "database",
            "db",
            "repository",
            "store",
            "cache",
            "redis",
            "dynamo",
            "neptune",
            "opensearch",
            "s3",
            "storage",
        ],
        "external": ["external", "client", "sdk", "bedrock", "cognito", "third"],
        "frontend": ["frontend", "ui", "web", "app", "dashboard", "component"],
        "security": ["auth", "security", "token", "jwt", "permission", "guard"],
    }

    # Layer display configuration - macOS Tahoe inspired (per design system)
    # Dark fills with bright accent strokes for visual hierarchy
    LAYER_CONFIG = {
        "frontend": {
            "name": "Frontend Layer",
            "fill": "#1e3a5f",
            "stroke": "#3b82f6",
            "text": "#e0f2fe",
            "shape": "([{}])",  # Stadium/pill shape
        },
        "api": {
            "name": "API Gateway",
            "fill": "#1e3a4d",
            "stroke": "#06b6d4",
            "text": "#cffafe",
            "shape": "([{}])",  # Stadium/pill shape
        },
        "security": {
            "name": "Security Layer",
            "fill": "#2d1f3d",
            "stroke": "#a855f7",
            "text": "#f3e8ff",
            "shape": "[[{}]]",  # Subroutine (double border)
        },
        "service": {
            "name": "Services Layer",
            "fill": "#1a2e35",
            "stroke": "#14b8a6",
            "text": "#ccfbf1",
            "shape": "[[{}]]",  # Subroutine (double border)
        },
        "data": {
            "name": "Data Layer",
            "fill": "#1f2937",
            "stroke": "#6366f1",
            "text": "#e0e7ff",
            "shape": "[({})]]",  # Cylinder for databases
        },
        "external": {
            "name": "External Services",
            "fill": "#1c1c1e",
            "stroke": "#71717a",
            "text": "#e4e4e7",
            "shape": "{{{{{}}}}}",  # Hexagon
        },
    }

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        include_styles: bool = True,
    ):
        """Initialize the diagram generator."""
        self.llm = llm_client
        self.include_styles = include_styles

    def generate(
        self,
        diagram_type: DiagramType,
        boundaries: list[ServiceBoundary] | None = None,
        data_flows: list[DataFlow] | None = None,
        components: list[DiagramComponent] | None = None,
    ) -> DiagramResult:
        """Generate a diagram of the specified type."""
        try:
            if diagram_type == DiagramType.ARCHITECTURE:
                return self._generate_architecture(boundaries or [])
            elif diagram_type == DiagramType.DATA_FLOW:
                return self._generate_data_flow(boundaries or [], data_flows or [])
            elif diagram_type == DiagramType.DEPENDENCY:
                if not components and boundaries:
                    components = self._boundaries_to_components(boundaries)
                return self._generate_dependency(components or [], boundaries or [])
            elif diagram_type == DiagramType.COMPONENT:
                return self._generate_component(boundaries or [])
            elif diagram_type == DiagramType.SEQUENCE:
                return self._generate_sequence(boundaries or [], data_flows or [])
            else:
                raise DiagramGenerationError(
                    f"Unsupported diagram type: {diagram_type}",
                    diagram_type=diagram_type.value,
                )
        except DiagramGenerationError:
            raise
        except Exception as e:
            raise DiagramGenerationError(
                f"Failed to generate {diagram_type.value} diagram: {e}",
                diagram_type=diagram_type.value,
                details={"error": str(e)},
            )

    def _classify_service_layer(self, name: str, description: str = "") -> str:
        """Classify a service into a logical layer based on name and description."""
        text = f"{name} {description}".lower()

        # Check in priority order (security before service since "service" is common)
        priority_order = ["security", "data", "external", "api", "frontend", "service"]
        for layer in priority_order:
            keywords = self.LAYER_KEYWORDS[layer]
            if any(kw in text for kw in keywords):
                return layer

        return "service"  # Default layer

    def _boundaries_to_components(
        self, boundaries: list[ServiceBoundary]
    ) -> list[DiagramComponent]:
        """Convert service boundaries to diagram components."""
        return [
            DiagramComponent(
                component_id=b.boundary_id,
                label=b.name,
                component_type=self._classify_service_layer(b.name, b.description),
                entity_ids=b.node_ids[:10],
                confidence=b.confidence,
            )
            for b in boundaries
        ]

    def _generate_architecture(
        self, boundaries: list[ServiceBoundary]
    ) -> DiagramResult:
        """Generate high-quality architecture diagram with layer grouping."""
        lines = ["graph TB"]
        components: list[DiagramComponent] = []
        connections: list[tuple[str, str, str]] = []
        warnings: list[str] = []

        if not boundaries:
            warnings.append("No service boundaries provided")
            lines.append("    empty[No services detected]")
            return DiagramResult(
                diagram_type=DiagramType.ARCHITECTURE,
                mermaid_code="\n".join(lines),
                components=[],
                connections=[],
                confidence=0.3,
                warnings=warnings,
            )

        # Group boundaries by layer
        layers: dict[str, list[ServiceBoundary]] = {}
        for boundary in boundaries:
            layer = self._classify_service_layer(boundary.name, boundary.description)
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(boundary)

        # Define layer order for visual hierarchy
        layer_order = ["frontend", "api", "security", "service", "data", "external"]
        node_to_layer: dict[str, str] = {}

        # Generate subgraphs for each layer
        for layer in layer_order:
            if layer not in layers:
                continue

            config = self.LAYER_CONFIG.get(layer, self.LAYER_CONFIG["service"])
            layer_id = f"Layer_{layer}"

            lines.append("")
            lines.append(f'    subgraph {layer_id}["{config["name"]}"]')

            for boundary in layers[layer]:
                safe_id = self._safe_id(boundary.boundary_id)
                label = self._format_service_name(boundary.name)
                # Use rounded shape from config (macOS Tahoe style)
                shape = config.get("shape", "[{}]").format(label)
                lines.append(f"        {safe_id}{shape}")
                node_to_layer[safe_id] = layer

                components.append(
                    DiagramComponent(
                        component_id=boundary.boundary_id,
                        label=boundary.name,
                        component_type=layer,
                        entity_ids=boundary.node_ids,
                        confidence=boundary.confidence,
                    )
                )

            lines.append("    end")

        # Add inter-layer connections
        lines.append("")
        lines.append("    %% Service connections")
        self._add_layer_connections(lines, layers, layer_order, connections)

        # Add style definitions
        lines.append("")
        lines.append("    %% Styling")
        for layer in layer_order:
            if layer in layers:
                config = self.LAYER_CONFIG.get(layer, self.LAYER_CONFIG["service"])
                style = (
                    f"fill:{config['fill']},stroke:{config['stroke']},"
                    f"stroke-width:1px,color:{config['text']}"
                )
                lines.append(f"    classDef {layer} {style}")

        # Apply styles to nodes
        for layer in layer_order:
            if layer in layers:
                node_ids = [self._safe_id(b.boundary_id) for b in layers[layer]]
                if node_ids:
                    lines.append(f"    class {','.join(node_ids)} {layer}")

        avg_confidence = (
            sum(b.confidence for b in boundaries) / len(boundaries)
            if boundaries
            else 0.5
        )

        return DiagramResult(
            diagram_type=DiagramType.ARCHITECTURE,
            mermaid_code="\n".join(lines),
            components=components,
            connections=connections,
            confidence=avg_confidence,
            warnings=warnings,
        )

    def _add_layer_connections(
        self,
        lines: list[str],
        layers: dict[str, list[ServiceBoundary]],
        layer_order: list[str],
        connections: list[tuple[str, str, str]],
    ) -> None:
        """Add logical connections between layers."""
        # Define typical connection patterns
        connection_patterns = [
            ("frontend", "api", "HTTP requests"),
            ("api", "security", "Auth check"),
            ("api", "service", "Business logic"),
            ("security", "service", "Authorized"),
            ("service", "data", "Read/Write"),
            ("service", "external", "API calls"),
        ]

        for source_layer, target_layer, label in connection_patterns:
            if source_layer in layers and target_layer in layers:
                # Connect first service in each layer
                source = layers[source_layer][0]
                target = layers[target_layer][0]
                source_id = self._safe_id(source.boundary_id)
                target_id = self._safe_id(target.boundary_id)
                lines.append(f"    {source_id} -->|{label}| {target_id}")
                connections.append((source.boundary_id, target.boundary_id, label))

    def _generate_data_flow(
        self,
        boundaries: list[ServiceBoundary],
        data_flows: list[DataFlow],
    ) -> DiagramResult:
        """Generate data flow diagram showing data movement."""
        lines = ["flowchart LR"]
        components: list[DiagramComponent] = []
        connections: list[tuple[str, str, str]] = []
        warnings: list[str] = []

        if not data_flows and not boundaries:
            warnings.append("No data flows or boundaries provided")
            lines.append("    empty[No data flows detected]")
            return DiagramResult(
                diagram_type=DiagramType.DATA_FLOW,
                mermaid_code="\n".join(lines),
                components=[],
                connections=[],
                confidence=0.3,
                warnings=warnings,
            )

        # If no explicit data flows, generate from boundaries
        if not data_flows and boundaries:
            return self._generate_inferred_data_flow(boundaries)

        # Process explicit data flows
        nodes: set[str] = set()
        edges: list[tuple[str, str, str]] = []

        for flow in data_flows:
            nodes.add(flow.source_id)
            nodes.add(flow.target_id)

            label = flow.flow_type
            if flow.data_types:
                label = f"{label}\\n[{', '.join(flow.data_types[:2])}]"

            edges.append((flow.source_id, flow.target_id, label))
            connections.append((flow.source_id, flow.target_id, flow.flow_type))

        # Add nodes with shapes based on type
        lines.append("")
        for node_id in nodes:
            safe_id = self._safe_id(node_id)
            label = self._format_service_name(node_id)
            node_type = self._infer_node_type(node_id)
            shape = self._get_node_shape(node_type)
            lines.append(f"    {safe_id}{shape.format(label)}")

            components.append(
                DiagramComponent(
                    component_id=node_id,
                    label=label,
                    component_type=node_type,
                    entity_ids=[node_id],
                    confidence=0.8,
                )
            )

        # Add edges
        lines.append("")
        for source, target, label in edges:
            source_safe = self._safe_id(source)
            target_safe = self._safe_id(target)
            safe_label = self._escape_label(label)
            lines.append(f"    {source_safe} -->|{safe_label}| {target_safe}")

        # Add styles
        self._add_flow_styles(lines)

        avg_confidence = (
            sum(f.confidence for f in data_flows) / len(data_flows)
            if data_flows
            else 0.7
        )

        return DiagramResult(
            diagram_type=DiagramType.DATA_FLOW,
            mermaid_code="\n".join(lines),
            components=components,
            connections=connections,
            confidence=avg_confidence,
            warnings=warnings,
        )

    def _generate_inferred_data_flow(
        self, boundaries: list[ServiceBoundary]
    ) -> DiagramResult:
        """Generate data flow diagram inferred from service boundaries."""
        lines = ["flowchart LR"]
        components: list[DiagramComponent] = []
        connections: list[tuple[str, str, str]] = []

        # Create flow stages based on service layers
        stages = {
            "input": [],
            "processing": [],
            "storage": [],
            "output": [],
        }

        for boundary in boundaries:
            layer = self._classify_service_layer(boundary.name, boundary.description)
            if layer in ["frontend", "api"]:
                stages["input"].append(boundary)
            elif layer in ["data"]:
                stages["storage"].append(boundary)
            elif layer in ["external"]:
                stages["output"].append(boundary)
            else:
                stages["processing"].append(boundary)

        # Generate subgraphs for each stage - macOS Tahoe palette
        stage_config = {
            "input": ("Input", "#1e3a5f", "#3b82f6", "#e0f2fe", "([{}])"),
            "processing": ("Processing", "#1a2e35", "#14b8a6", "#ccfbf1", "[[{}]]"),
            "storage": ("Storage", "#1f2937", "#6366f1", "#e0e7ff", "[({})]]"),
            "output": ("Output", "#1c1c1e", "#71717a", "#e4e4e7", "{{{{{}}}}}"),
        }

        for stage, (name, _fill, _stroke, _text, shape) in stage_config.items():
            if stages[stage]:
                lines.append("")
                lines.append(f'    subgraph {stage}["{name}"]')
                for boundary in stages[stage]:
                    safe_id = self._safe_id(boundary.boundary_id)
                    label = self._format_service_name(boundary.name)
                    node_shape = shape.format(label)
                    lines.append(f"        {safe_id}{node_shape}")
                    components.append(
                        DiagramComponent(
                            component_id=boundary.boundary_id,
                            label=boundary.name,
                            component_type=stage,
                            entity_ids=boundary.node_ids,
                            confidence=boundary.confidence,
                        )
                    )
                lines.append("    end")

        # Add flow connections between stages
        lines.append("")
        stage_order = ["input", "processing", "storage", "output"]
        for i, stage in enumerate(stage_order[:-1]):
            next_stage = stage_order[i + 1]
            if stages[stage] and stages[next_stage]:
                source = stages[stage][0]
                target = stages[next_stage][0]
                source_id = self._safe_id(source.boundary_id)
                target_id = self._safe_id(target.boundary_id)
                flow_labels = {
                    "input": "Validate",
                    "processing": "Transform",
                    "storage": "Persist",
                }
                label = flow_labels.get(stage, "Flow")
                lines.append(f"    {source_id} -->|{label}| {target_id}")
                connections.append((source.boundary_id, target.boundary_id, label))

        # Add styles
        lines.append("")
        lines.append("    %% Styling")
        for stage, (_, fill, stroke, text, _shape) in stage_config.items():
            if stages[stage]:
                lines.append(
                    f"    classDef {stage} fill:{fill},stroke:{stroke},"
                    f"stroke-width:1.5px,color:{text}"
                )
                node_ids = [self._safe_id(b.boundary_id) for b in stages[stage]]
                lines.append(f"    class {','.join(node_ids)} {stage}")

        avg_confidence = (
            sum(b.confidence for b in boundaries) / len(boundaries)
            if boundaries
            else 0.5
        )

        return DiagramResult(
            diagram_type=DiagramType.DATA_FLOW,
            mermaid_code="\n".join(lines),
            components=components,
            connections=connections,
            confidence=avg_confidence * 0.8,  # Slightly lower for inferred
            warnings=["Data flows inferred from service boundaries"],
        )

    def _generate_dependency(
        self,
        components: list[DiagramComponent],
        boundaries: list[ServiceBoundary],
    ) -> DiagramResult:
        """Generate dependency diagram showing service relationships."""
        lines = ["graph TD"]
        output_components: list[DiagramComponent] = []
        connections: list[tuple[str, str, str]] = []
        warnings: list[str] = []

        if not components and not boundaries:
            warnings.append("No components provided")
            lines.append("    empty[No dependencies detected]")
            return DiagramResult(
                diagram_type=DiagramType.DEPENDENCY,
                mermaid_code="\n".join(lines),
                components=[],
                connections=[],
                confidence=0.3,
                warnings=warnings,
            )

        # Group by layer
        layers: dict[str, list[DiagramComponent]] = {}
        for comp in components:
            layer = comp.component_type
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(comp)

        # Layer order for dependency hierarchy
        layer_order = ["api", "security", "service", "data", "external"]
        layer_names = {
            "api": "API Layer",
            "security": "Security",
            "service": "Services",
            "data": "Data Access",
            "external": "External",
        }

        # Generate subgraphs
        for layer in layer_order:
            if layer not in layers:
                continue

            layer_label = layer_names.get(layer, layer.title())
            lines.append("")
            lines.append(f'    subgraph {layer}["{layer_label}"]')
            for comp in layers[layer]:
                safe_id = self._safe_id(comp.component_id)
                label = self._format_service_name(comp.label)
                lines.append(f"        {safe_id}[{label}]")
                output_components.append(comp)
            lines.append("    end")

        # Add dependency arrows between layers
        lines.append("")
        lines.append("    %% Dependencies")
        dependency_pairs = [
            ("api", "security"),
            ("api", "service"),
            ("security", "data"),
            ("service", "data"),
            ("service", "external"),
        ]

        for source_layer, target_layer in dependency_pairs:
            if source_layer in layers and target_layer in layers:
                for source in layers[source_layer]:
                    for target in layers[target_layer]:
                        source_id = self._safe_id(source.component_id)
                        target_id = self._safe_id(target.component_id)
                        lines.append(f"    {source_id} --> {target_id}")
                        connections.append(
                            (source.component_id, target.component_id, "depends")
                        )
                        break  # Only one connection per source
                    break

        # Add styles
        self._add_dependency_styles(lines, layers)

        avg_confidence = (
            sum(c.confidence for c in components) / len(components)
            if components
            else 0.5
        )

        return DiagramResult(
            diagram_type=DiagramType.DEPENDENCY,
            mermaid_code="\n".join(lines),
            components=output_components,
            connections=connections,
            confidence=avg_confidence,
            warnings=warnings,
        )

    def _generate_component(self, boundaries: list[ServiceBoundary]) -> DiagramResult:
        """Generate component hierarchy diagram."""
        lines = ["graph TB"]
        components: list[DiagramComponent] = []
        connections: list[tuple[str, str, str]] = []
        warnings: list[str] = []

        if not boundaries:
            warnings.append("No boundaries provided")
            lines.append("    empty[No components detected]")
            return DiagramResult(
                diagram_type=DiagramType.COMPONENT,
                mermaid_code="\n".join(lines),
                components=[],
                connections=[],
                confidence=0.3,
                warnings=warnings,
            )

        # Group by layer
        layers: dict[str, list[ServiceBoundary]] = {}
        for boundary in boundaries:
            layer = self._classify_service_layer(boundary.name, boundary.description)
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(boundary)

        # Create main service subgraph
        lines.append('    subgraph System["System Components"]')
        lines.append("        direction TB")

        for layer, layer_boundaries in layers.items():
            layer_id = f"layer_{layer}"
            layer_name = self.LAYER_CONFIG.get(layer, {}).get("name", layer.title())
            lines.append("")
            lines.append(f'        subgraph {layer_id}["{layer_name}"]')

            for boundary in layer_boundaries:
                safe_id = self._safe_id(boundary.boundary_id)
                label = self._format_service_name(boundary.name)
                lines.append(f"            {safe_id}[{label}]")

                components.append(
                    DiagramComponent(
                        component_id=boundary.boundary_id,
                        label=boundary.name,
                        component_type=layer,
                        entity_ids=boundary.node_ids,
                        confidence=boundary.confidence,
                    )
                )

            lines.append("        end")

        lines.append("    end")

        # Add component relationships
        lines.append("")
        lines.append("    %% Component relationships")
        layer_order = ["api", "security", "service", "data", "external"]
        for i, layer in enumerate(layer_order[:-1]):
            next_layer = layer_order[i + 1]
            if layer in layers and next_layer in layers:
                source = layers[layer][0]
                target = layers[next_layer][0]
                source_id = self._safe_id(source.boundary_id)
                target_id = self._safe_id(target.boundary_id)
                lines.append(f"    {source_id} --> {target_id}")
                connections.append((source.boundary_id, target.boundary_id, "uses"))

        # Add styles
        self._add_component_styles(lines, layers)

        avg_confidence = (
            sum(b.confidence for b in boundaries) / len(boundaries)
            if boundaries
            else 0.5
        )

        return DiagramResult(
            diagram_type=DiagramType.COMPONENT,
            mermaid_code="\n".join(lines),
            components=components,
            connections=connections,
            confidence=avg_confidence,
            warnings=warnings,
        )

    def _generate_sequence(
        self,
        boundaries: list[ServiceBoundary],
        data_flows: list[DataFlow],
    ) -> DiagramResult:
        """Generate sequence diagram showing request/response flows."""
        lines = ["sequenceDiagram"]
        components: list[DiagramComponent] = []
        connections: list[tuple[str, str, str]] = []
        warnings: list[str] = []

        if not boundaries:
            warnings.append("No service boundaries provided")
            lines.append("    Note over Client: No sequence flows detected")
            return DiagramResult(
                diagram_type=DiagramType.SEQUENCE,
                mermaid_code="\n".join(lines),
                components=[],
                connections=[],
                confidence=0.3,
                warnings=warnings,
            )

        lines.append("    autonumber")
        lines.append("")

        # Group and order boundaries by layer
        layers: dict[str, list[ServiceBoundary]] = {}
        for boundary in boundaries:
            layer = self._classify_service_layer(boundary.name, boundary.description)
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(boundary)

        # Define participants in order
        layer_order = ["frontend", "api", "security", "service", "data", "external"]
        participants = []

        # Add User as first participant if we have API layer
        if "api" in layers or "frontend" in layers:
            lines.append("    participant U as User")
            participants.append(("U", "User"))

        for layer in layer_order:
            if layer in layers:
                for boundary in layers[layer][:2]:  # Max 2 per layer
                    safe_id = self._safe_id(boundary.name)
                    label = self._format_service_name(boundary.name)
                    lines.append(f"    participant {safe_id} as {label}")
                    participants.append((safe_id, label))
                    components.append(
                        DiagramComponent(
                            component_id=boundary.boundary_id,
                            label=boundary.name,
                            component_type="participant",
                            entity_ids=boundary.node_ids,
                            confidence=boundary.confidence,
                        )
                    )

        # Generate sequence flows
        lines.append("")

        # Create realistic flow patterns
        if len(participants) >= 2:
            self._add_sequence_flows(lines, layers, layer_order, connections)

        avg_confidence = (
            sum(b.confidence for b in boundaries) / len(boundaries)
            if boundaries
            else 0.5
        )

        return DiagramResult(
            diagram_type=DiagramType.SEQUENCE,
            mermaid_code="\n".join(lines),
            components=components,
            connections=connections,
            confidence=avg_confidence,
            warnings=warnings,
        )

    def _add_sequence_flows(
        self,
        lines: list[str],
        layers: dict[str, list[ServiceBoundary]],
        layer_order: list[str],
        connections: list[tuple[str, str, str]],
    ) -> None:
        """Add realistic sequence flows between services."""
        # Get first service from each layer
        service_map: dict[str, str] = {}
        for layer in layer_order:
            if layer in layers:
                boundary = layers[layer][0]
                service_map[layer] = self._safe_id(boundary.name)

        # User -> API flow
        if "api" in service_map:
            api = service_map["api"]
            lines.append(f"    U->>+{api}: HTTP Request")

            # API -> Auth check
            if "security" in service_map:
                auth = service_map["security"]
                lines.append(f"    {api}->>+{auth}: Validate Token")
                lines.append(f"    {auth}-->>-{api}: Token Valid")

            # API -> Service
            if "service" in service_map:
                svc = service_map["service"]
                lines.append(f"    {api}->>+{svc}: Process Request")

                # Service -> Data
                if "data" in service_map:
                    data = service_map["data"]
                    lines.append(f"    {svc}->>+{data}: Query Data")
                    lines.append(f"    {data}-->>-{svc}: Return Results")

                # Service -> External
                if "external" in service_map:
                    ext = service_map["external"]
                    lines.append(f"    {svc}->>+{ext}: External Call")
                    lines.append(f"    {ext}-->>-{svc}: Response")

                lines.append(f"    {svc}-->>-{api}: Processed Result")

            lines.append(f"    {api}-->>-U: HTTP Response")

        elif "service" in service_map:
            # Direct service flow without API
            svc = service_map["service"]
            lines.append(f"    U->>+{svc}: Request")

            if "data" in service_map:
                data = service_map["data"]
                lines.append(f"    {svc}->>+{data}: Query")
                lines.append(f"    {data}-->>-{svc}: Data")

            lines.append(f"    {svc}-->>-U: Response")

    # Helper methods

    def _safe_id(self, identifier: str) -> str:
        """Convert identifier to Mermaid-safe ID."""
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", identifier)
        if safe and not safe[0].isalpha():
            safe = "n_" + safe
        return safe[:40]

    def _escape_label(self, label: str) -> str:
        """Escape label for Mermaid."""
        label = label.replace('"', "'")
        label = label.replace("[", "(")
        label = label.replace("]", ")")
        label = label.replace("{", "(")
        label = label.replace("}", ")")
        return label[:80]

    def _format_service_name(self, name: str) -> str:
        """Format service name for display."""
        # Handle common patterns
        name = re.sub(r"[-_]", " ", name)
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)

        # Title case
        words = name.split()
        formatted = " ".join(w.capitalize() for w in words)

        # Handle common abbreviations
        abbreviations = ["API", "DB", "UI", "AWS", "S3", "SQS", "JWT", "HTTP"]
        for abbr in abbreviations:
            formatted = re.sub(
                rf"\b{abbr.lower()}\b|\b{abbr.capitalize()}\b",
                abbr,
                formatted,
                flags=re.IGNORECASE,
            )

        return formatted[:50]

    def _infer_node_type(self, node_id: str) -> str:
        """Infer node type from ID patterns."""
        lower_id = node_id.lower()

        if any(
            kw in lower_id for kw in ["database", "db", "dynamo", "neptune", "postgres"]
        ):
            return "database"
        if any(kw in lower_id for kw in ["queue", "sqs", "kafka", "sns"]):
            return "queue"
        if any(kw in lower_id for kw in ["api", "endpoint", "gateway"]):
            return "api"
        if any(kw in lower_id for kw in ["external", "bedrock", "cognito"]):
            return "external"
        if any(kw in lower_id for kw in ["cache", "redis"]):
            return "cache"

        return "service"

    def _get_node_shape(self, node_type: str) -> str:
        """Get Mermaid shape for node type."""
        shapes = {
            "service": '["{}"]',
            "database": "[({})]]",
            "queue": "{{{{{}}}}}",
            "api": "(({}))",
            "external": ">{}]",
            "cache": "[({})]",
        }
        return shapes.get(node_type, '["{}"]')

    def _add_flow_styles(self, lines: list[str]) -> None:
        """Add style definitions for flow diagrams - macOS Tahoe palette."""
        lines.append("")
        lines.append("    %% Styling")
        lines.append(
            "    classDef input fill:#1e3a5f,stroke:#3b82f6,stroke-width:1.5px,color:#e0f2fe"
        )
        lines.append(
            "    classDef process fill:#1a2e35,stroke:#14b8a6,stroke-width:1.5px,color:#ccfbf1"
        )
        lines.append(
            "    classDef storage fill:#1f2937,stroke:#6366f1,stroke-width:1.5px,color:#e0e7ff"
        )
        lines.append(
            "    classDef output fill:#1c1c1e,stroke:#71717a,stroke-width:1.5px,color:#e4e4e7"
        )

    def _add_dependency_styles(self, lines: list[str], layers: dict[str, list]) -> None:
        """Add style definitions for dependency diagrams - macOS Tahoe palette."""
        lines.append("")
        lines.append("    %% Styling")

        style_map = {
            "api": "fill:#1e3a4d,stroke:#06b6d4,stroke-width:1.5px,color:#cffafe",
            "security": "fill:#2d1f3d,stroke:#a855f7,stroke-width:1.5px,color:#f3e8ff",
            "service": "fill:#1a2e35,stroke:#14b8a6,stroke-width:1.5px,color:#ccfbf1",
            "data": "fill:#1f2937,stroke:#6366f1,stroke-width:1.5px,color:#e0e7ff",
            "external": "fill:#1c1c1e,stroke:#71717a,stroke-width:1.5px,color:#e4e4e7",
        }

        for layer, comps in layers.items():
            if layer in style_map:
                lines.append(f"    classDef {layer} {style_map[layer]}")
                node_ids = [self._safe_id(c.component_id) for c in comps]
                if node_ids:
                    lines.append(f"    class {','.join(node_ids)} {layer}")

    def _add_component_styles(self, lines: list[str], layers: dict[str, list]) -> None:
        """Add style definitions for component diagrams."""
        lines.append("")
        lines.append("    %% Styling")

        for layer, boundaries in layers.items():
            config = self.LAYER_CONFIG.get(layer, self.LAYER_CONFIG["service"])
            style = (
                f"fill:{config['fill']},stroke:{config['stroke']},"
                f"stroke-width:1px,color:{config['text']}"
            )
            lines.append(f"    classDef {layer} {style}")
            node_ids = [self._safe_id(b.boundary_id) for b in boundaries]
            if node_ids:
                lines.append(f"    class {','.join(node_ids)} {layer}")


# Factory function
def create_diagram_generator(
    llm_client: "BedrockLLMService | None" = None,
) -> DiagramGenerator:
    """Factory function to create a DiagramGenerator."""
    return DiagramGenerator(llm_client=llm_client)
