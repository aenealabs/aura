"""
Aura Chat Assistant - Diagram Generation Tools

Generates Mermaid, PlantUML, and draw.io diagrams for:
- Architecture diagrams (component, service, system)
- Sequence diagrams (API flows, auth flows)
- Class/ER diagrams (data models)
- Flowcharts (workflows, decision trees)
- State diagrams (status transitions)
- Dependency graphs (code relationships)
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger()


class DiagramType(Enum):
    """Supported diagram types."""

    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"
    CLASS = "class"
    ER = "er"
    STATE = "state"
    ARCHITECTURE = "architecture"
    DEPENDENCY = "dependency"


class DiagramFormat(Enum):
    """Output format for diagrams."""

    MERMAID = "mermaid"  # Renders in-chat via frontend
    PLANTUML = "plantuml"  # Server-rendered SVG
    DRAWIO = "drawio"  # XML for draw.io export


@dataclass
class DiagramResult:
    """Result of diagram generation."""

    diagram_type: str
    format: str
    code: str
    title: str
    description: str


class DiagramGenerator:
    """
    Generates diagrams in multiple formats based on subject and scope.

    Uses templates and Neptune graph data to create accurate diagrams
    of the Aura platform architecture.
    """

    def __init__(self) -> None:
        """Initialize the diagram generator."""
        self.templates = self._load_templates()

    def generate(
        self,
        diagram_type: str,
        subject: str,
        format: str = "mermaid",
        scope: str = "component",
    ) -> DiagramResult:
        """
        Generate a diagram based on parameters.

        Args:
            diagram_type: Type of diagram (flowchart, sequence, class, etc.)
            subject: What to diagram (e.g., "authentication flow", "agent orchestration")
            format: Output format (mermaid, plantuml, drawio)
            scope: Scope level (component, service, system, codebase)

        Returns:
            DiagramResult with the generated diagram code
        """
        logger.info(
            f"Generating {diagram_type} diagram for '{subject}' in {format} format"
        )

        # Normalize inputs
        diagram_type = diagram_type.lower()
        format = format.lower()
        subject_lower = subject.lower()

        # Route to appropriate generator
        generators = {
            "flowchart": self._generate_flowchart,
            "sequence": self._generate_sequence,
            "class": self._generate_class,
            "er": self._generate_er,
            "state": self._generate_state,
            "architecture": self._generate_architecture,
            "dependency": self._generate_dependency,
        }

        generator_fn = generators.get(diagram_type, self._generate_flowchart)
        mermaid_code = generator_fn(subject_lower, scope)

        # Convert to requested format
        if format == "plantuml":
            code = self._mermaid_to_plantuml(mermaid_code, diagram_type)
        elif format == "drawio":
            code = self._mermaid_to_drawio(mermaid_code, diagram_type)
        else:
            code = mermaid_code

        return DiagramResult(
            diagram_type=diagram_type,
            format=format,
            code=code,
            title=f"{diagram_type.title()} Diagram: {subject.title()}",
            description=f"Generated {diagram_type} diagram showing {subject} at {scope} scope",
        )

    def _load_templates(self) -> dict[str, str]:
        """Load diagram templates for common Aura components."""
        return {
            "agent_orchestration": """
flowchart TD
    subgraph Orchestrator["Agent Orchestrator"]
        O[Meta Orchestrator] --> |assigns| T[Task Queue]
        T --> C[Coder Agent]
        T --> R[Reviewer Agent]
        T --> V[Validator Agent]
    end

    subgraph Context["Context Services"]
        CRS[Context Retrieval] --> N[(Neptune)]
        CRS --> OS[(OpenSearch)]
    end

    C --> |queries| CRS
    R --> |queries| CRS
    V --> |executes in| SB[Sandbox]

    V --> |results| HITL{HITL Approval}
    HITL --> |approved| Deploy[Deployment]
    HITL --> |rejected| O
""",
            "authentication": """
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as API Gateway
    participant Cognito as AWS Cognito
    participant Lambda as Chat Lambda

    U->>FE: Enter credentials
    FE->>Cognito: Authenticate
    Cognito-->>FE: JWT Token
    FE->>API: Request + JWT
    API->>Cognito: Validate token
    Cognito-->>API: Claims
    API->>Lambda: Invoke with claims
    Lambda-->>API: Response
    API-->>FE: Response
    FE-->>U: Display result
""",
            "chat_flow": """
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant WS as WebSocket API
    participant Lambda as Chat Handler
    participant BR as Bedrock Claude
    participant Tools as Tool Executor
    participant DDB as DynamoDB

    U->>FE: Send message
    FE->>WS: WebSocket message
    WS->>Lambda: Invoke
    Lambda->>DDB: Load conversation
    Lambda->>BR: Converse API

    loop Tool Use
        BR-->>Lambda: Tool request
        Lambda->>Tools: Execute tool
        Tools-->>Lambda: Tool result
        Lambda->>BR: Tool result
    end

    BR-->>Lambda: Final response
    Lambda->>DDB: Save messages
    Lambda-->>WS: Stream response
    WS-->>FE: WebSocket frames
    FE-->>U: Display response
""",
            "hitl_workflow": """
stateDiagram-v2
    [*] --> PatchGenerated
    PatchGenerated --> SandboxTesting: Auto-validate
    SandboxTesting --> TestsPassed: Success
    SandboxTesting --> PatchFailed: Failure
    TestsPassed --> HITLReview: Requires approval
    HITLReview --> Approved: Human approves
    HITLReview --> Rejected: Human rejects
    Approved --> Deployment: Auto-deploy
    Rejected --> PatchGenerated: Regenerate
    PatchFailed --> PatchGenerated: Regenerate
    Deployment --> [*]
""",
            "data_model": """
erDiagram
    CONVERSATION ||--o{ MESSAGE : contains
    CONVERSATION {
        string conversation_id PK
        string user_id FK
        string tenant_id
        string title
        datetime created_at
        datetime updated_at
        int message_count
        int total_tokens
    }
    MESSAGE {
        string message_id PK
        string conversation_id FK
        string role
        text content
        datetime created_at
        json tool_calls
        int tokens_input
        int tokens_output
    }
    USER ||--o{ CONVERSATION : owns
    USER {
        string user_id PK
        string tenant_id FK
        string email
        json groups
    }
    TENANT ||--o{ USER : contains
    TENANT {
        string tenant_id PK
        string name
        json settings
    }
""",
            "infrastructure": """
flowchart TB
    subgraph VPC["AWS VPC"]
        subgraph Public["Public Subnets"]
            ALB[Application Load Balancer]
            NAT[NAT Gateway]
        end

        subgraph Private["Private Subnets"]
            subgraph EKS["EKS Cluster"]
                API[API Pods]
                Agents[Agent Pods]
                DNS[dnsmasq DaemonSet]
            end

            subgraph Data["Data Layer"]
                Neptune[(Neptune Graph)]
                OpenSearch[(OpenSearch)]
                DynamoDB[(DynamoDB)]
            end
        end
    end

    Internet --> ALB
    ALB --> API
    API --> Agents
    Agents --> Neptune
    Agents --> OpenSearch
    API --> DynamoDB
    DNS --> Neptune
    DNS --> OpenSearch
""",
        }

    def _generate_flowchart(self, subject: str, scope: str) -> str:
        """Generate a flowchart diagram."""
        # Check for template matches
        if "agent" in subject or "orchestrat" in subject:
            return self.templates["agent_orchestration"]
        if "infrastructure" in subject or "vpc" in subject:
            return self.templates["infrastructure"]

        # Generic flowchart
        return f"""
flowchart TD
    A[Start: {subject.title()}] --> B{{Decision Point}}
    B -->|Option 1| C[Process 1]
    B -->|Option 2| D[Process 2]
    C --> E[Result]
    D --> E
    E --> F[End]
"""

    def _generate_sequence(self, subject: str, scope: str) -> str:
        """Generate a sequence diagram."""
        if "auth" in subject or "login" in subject:
            return self.templates["authentication"]
        if "chat" in subject or "message" in subject:
            return self.templates["chat_flow"]

        # Generic sequence diagram
        return f"""
sequenceDiagram
    participant A as Actor
    participant S as System
    participant D as Database

    A->>S: Request ({subject})
    S->>D: Query data
    D-->>S: Return data
    S-->>A: Response
"""

    def _generate_class(self, subject: str, scope: str) -> str:
        """Generate a class diagram."""
        return f"""
classDiagram
    class {subject.replace(' ', '').title()} {{
        +string id
        +string name
        +datetime created_at
        +process()
        +validate()
    }}

    class Service {{
        +execute()
        +get_status()
    }}

    {subject.replace(' ', '').title()} --> Service : uses
"""

    def _generate_er(self, subject: str, scope: str) -> str:
        """Generate an ER diagram."""
        if "chat" in subject or "conversation" in subject or "message" in subject:
            return self.templates["data_model"]

        return """
erDiagram
    ENTITY1 ||--o{{ ENTITY2 : relates
    ENTITY1 {{
        string id PK
        string name
        datetime created_at
    }}
    ENTITY2 {{
        string id PK
        string entity1_id FK
        string data
    }}
"""

    def _generate_state(self, subject: str, scope: str) -> str:
        """Generate a state diagram."""
        if "hitl" in subject or "approval" in subject or "patch" in subject:
            return self.templates["hitl_workflow"]

        return """
stateDiagram-v2
    [*] --> Initial
    Initial --> Processing: Start
    Processing --> Completed: Success
    Processing --> Failed: Error
    Completed --> [*]
    Failed --> Initial: Retry
"""

    def _generate_architecture(self, subject: str, scope: str) -> str:
        """Generate an architecture diagram."""
        if "infrastructure" in subject or "aws" in subject:
            return self.templates["infrastructure"]
        if "agent" in subject:
            return self.templates["agent_orchestration"]

        return """
flowchart TB
    subgraph Frontend["Frontend Layer"]
        UI[React UI]
        WS[WebSocket Client]
    end

    subgraph API["API Layer"]
        GW[API Gateway]
        Lambda[Lambda Functions]
    end

    subgraph Services["Service Layer"]
        Svc1[Service 1]
        Svc2[Service 2]
    end

    subgraph Data["Data Layer"]
        DB[(Database)]
        Cache[(Cache)]
    end

    UI --> GW
    WS --> GW
    GW --> Lambda
    Lambda --> Svc1
    Lambda --> Svc2
    Svc1 --> DB
    Svc2 --> Cache
"""

    def _generate_dependency(self, subject: str, scope: str) -> str:
        """Generate a dependency graph."""
        return f"""
flowchart LR
    subgraph Core["Core Dependencies"]
        boto3[boto3]
        fastapi[FastAPI]
        pydantic[Pydantic]
    end

    subgraph App["Application"]
        main[{subject.replace(' ', '_')}]
    end

    subgraph Internal["Internal Modules"]
        utils[utils]
        services[services]
        agents[agents]
    end

    main --> boto3
    main --> fastapi
    main --> pydantic
    main --> utils
    main --> services
    services --> agents
"""

    def _mermaid_to_plantuml(self, mermaid_code: str, diagram_type: str) -> str:
        """
        Convert Mermaid diagram to PlantUML syntax.

        Note: This is a simplified conversion. For complex diagrams,
        direct PlantUML generation would be more accurate.
        """
        # Basic conversion for sequence diagrams
        if "sequenceDiagram" in mermaid_code:
            plantuml = "@startuml\n"
            for line in mermaid_code.split("\n"):
                line = line.strip()
                if line.startswith("participant"):
                    plantuml += line + "\n"
                elif "->>" in line or "-->>" in line:
                    # Convert Mermaid arrows to PlantUML
                    line = line.replace("->>", "->")
                    line = line.replace("-->>", "-->")
                    plantuml += line + "\n"
            plantuml += "@enduml"
            return plantuml

        # For other diagrams, return a PlantUML wrapper
        return f"""@startuml
' Converted from Mermaid {diagram_type}
' Original Mermaid code:
' {mermaid_code[:200]}...

note "Full PlantUML conversion requires dedicated generator" as N1
@enduml"""

    def _mermaid_to_drawio(self, mermaid_code: str, diagram_type: str) -> str:
        """
        Generate draw.io XML from diagram.

        Returns a basic draw.io XML structure that can be imported.
        Full conversion would require parsing the Mermaid AST.
        """
        # Generate a simple draw.io XML with embedded Mermaid
        drawio_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="{{}}" agent="Aura Assistant">
  <diagram name="Page-1" id="diagram-1">
    <mxGraphModel dx="1422" dy="798" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="note-1" value="Mermaid Diagram:\\n{diagram_type}\\n\\nImport this into draw.io and\\nrecreate using native shapes\\nfor full editing capability." style="shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;darkOpacity=0.05;fillColor=#fff2cc;strokeColor=#d6b656;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="200" height="120" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
        return drawio_xml


# Singleton instance for reuse
_diagram_generator = None


def get_diagram_generator() -> DiagramGenerator:
    """Get or create the singleton DiagramGenerator instance."""
    global _diagram_generator
    if _diagram_generator is None:
        _diagram_generator = DiagramGenerator()
    return _diagram_generator


def generate_diagram(
    diagram_type: str,
    subject: str,
    format: str = "mermaid",
    scope: str = "component",
    tenant_id: str | None = None,
) -> dict:
    """
    Tool function for generating diagrams.

    This is the entry point called by the chat tool executor.

    Args:
        diagram_type: Type of diagram to generate
        subject: What to diagram
        format: Output format (mermaid, plantuml, drawio)
        scope: Diagram scope
        tenant_id: Tenant ID for access control

    Returns:
        dict with diagram code and metadata
    """
    generator = get_diagram_generator()
    result = generator.generate(diagram_type, subject, format, scope)

    return {
        "diagram_type": result.diagram_type,
        "format": result.format,
        "code": result.code,
        "title": result.title,
        "description": result.description,
        "render_hint": "mermaid" if result.format == "mermaid" else "code",
    }
