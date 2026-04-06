# ADR-037: AWS Agent Capability Replication

**Status:** Deployed
**Date:** 2025-12-11 | **Deployed:** 2025-12-16
**Decision Makers:** Project Aura Team
**Related:** ADR-019 (Market Intelligence), ADR-023 (AgentCore Gateway), ADR-025 (RuntimeIncidentAgent), ADR-028 (Foundry Capability Adoption)

## Context

### Strategic Imperative

At AWS re:Invent 2025, AWS announced four agent capabilities that represent significant public benchmarks for enterprise AI agents (as of December 2025):

1. **Amazon Bedrock AgentCore** - Platform for building, deploying, and operating AI agents at scale
2. **AWS Security Agent** - Frontier agent for application security throughout development lifecycle
3. **AWS DevOps Agent** - Frontier agent for incident response and operational excellence
4. **AWS Transform** - Agentic AI for legacy code modernization

This ADR defines an implementation plan for Project Aura to pursue feature parity with publicly documented capabilities of these offerings (as of their December 2025 announcements). Capabilities of both AWS and Project Aura evolve continuously; readers should verify current state before decision-making.

### Current State Analysis (as of December 2025)

| AWS Publicly Documented Capability | Aura Current State | Gap Severity |
|----------------|-------------------|--------------|
| AgentCore Runtime | EKS-based, no code upload | High |
| AgentCore Gateway | MCPGatewayClient (partial) | Medium |
| AgentCore Memory | TitanCognitiveService (planned) | High |
| AgentCore Identity | Missing | Critical |
| AgentCore Policy | Missing | Critical |
| AgentCore Evaluations | Missing | Critical |
| AgentCore Browser Tool | Missing | High |
| AgentCore Code Interpreter | Partial (Python only) | Medium |
| Security Agent | 4/4 gaps closed (ADR-019) | Low |
| DevOps Agent | RuntimeIncidentAgent (partial) | Medium |
| Transform Agent | Missing entirely | Critical |

### Competitive Positioning

As of December 2025, AWS publicly markets frontier agents as:
- **Autonomous** - Work hours/days without intervention
- **Scalable** - Deploy across application portfolios
- **Enterprise-grade** - VPC, PrivateLink, CloudFormation support

Aura's differentiators that must be preserved:
- **Hybrid GraphRAG** - Code-specific context retrieval
- **GovCloud Native** - CMMC L3, FedRAMP ready
- **Ephemeral Sandbox Testing** - Per-patch isolation
- **Domain Expertise** - Security-focused, not generic

## Decision

Implement full capability parity with AWS AgentCore, Security Agent, DevOps Agent, and Transform Agent across four phases over 22-29 sprints (approximately 9-12 months).

---

## Phase 1: AgentCore Parity (Q1 2026)

### 1.1 AgentCore Runtime Service

**Purpose:** Unified agent deployment supporting both code upload and container-based deployment with session isolation.

**AWS Parity Features:**
- Code-zip deployment for rapid prototyping
- Container-based deployment for production
- Session isolation preventing data leakage
- Support for 8-hour async workloads
- A2A (Agent-to-Agent) protocol support
- Bidirectional streaming for voice agents

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AgentRuntimeService                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     Deployment Manager                                   ││
│  │  ┌───────────────────────┐  ┌───────────────────────────────────────┐  ││
│  │  │   Code Upload Mode    │  │        Container Mode                 │  ││
│  │  │  • Lambda packaging   │  │  • ECS Fargate tasks                  │  ││
│  │  │  • ZIP extraction     │  │  • EKS pods                           │  ││
│  │  │  • Dependency install │  │  • Custom Dockerfile support          │  ││
│  │  │  • Runtime: Python,   │  │  • Multi-arch (amd64/arm64)           │  ││
│  │  │    Node.js, Go        │  │  • GPU support (optional)             │  ││
│  │  └───────────────────────┘  └───────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│  ┌─────────────────────────────────┴───────────────────────────────────────┐│
│  │                     Session Manager                                      ││
│  │  ┌───────────────────────┐  ┌───────────────────────────────────────┐  ││
│  │  │   Session Isolation   │  │        State Persistence              │  ││
│  │  │  • Unique session IDs │  │  • DynamoDB session state             │  ││
│  │  │  • Memory boundaries  │  │  • S3 artifact storage                │  ││
│  │  │  • Network isolation  │  │  • 8-hour TTL support                 │  ││
│  │  │  • Resource quotas    │  │  • Checkpoint/resume                  │  ││
│  │  └───────────────────────┘  └───────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│  ┌─────────────────────────────────┴───────────────────────────────────────┐│
│  │                     Communication Layer                                  ││
│  │  ┌───────────────────────┐  ┌───────────────────────────────────────┐  ││
│  │  │   A2A Protocol        │  │        Streaming Support              │  ││
│  │  │  • Agent discovery    │  │  • WebSocket bidirectional            │  ││
│  │  │  • Capability ads     │  │  • Server-sent events                 │  ││
│  │  │  • Request routing    │  │  • Voice agent support                │  ││
│  │  │  • Response handling  │  │  • Interruption handling              │  ││
│  │  └───────────────────────┘  └───────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

**File:** `src/services/agent_runtime_service.py`

```python
@dataclass
class AgentDeploymentConfig:
    """Configuration for agent deployment."""
    deployment_id: str
    deployment_mode: Literal["code_upload", "container"]
    runtime: Literal["python3.11", "python3.12", "nodejs20", "go1.21"] | None
    container_image: str | None
    memory_mb: int = 512
    timeout_seconds: int = 900  # 15 min default, up to 8 hours
    vpc_config: VPCConfig | None = None
    environment_variables: dict[str, str] = field(default_factory=dict)

@dataclass
class AgentSession:
    """Isolated agent execution session."""
    session_id: str
    deployment_id: str
    created_at: datetime
    expires_at: datetime
    state: dict[str, Any]
    checkpoints: list[SessionCheckpoint]

class AgentRuntimeService:
    """
    Unified agent deployment and execution runtime.

    Supports AWS AgentCore parity features:
    - Code upload and container deployment
    - Session isolation with state persistence
    - A2A protocol for agent-to-agent communication
    - Bidirectional streaming for voice agents
    """

    async def deploy_agent(
        self,
        config: AgentDeploymentConfig,
        code_artifact: bytes | None = None,
    ) -> DeploymentResult:
        """Deploy an agent with code upload or container."""

    async def create_session(
        self,
        deployment_id: str,
        ttl_hours: float = 1.0,
        initial_state: dict | None = None,
    ) -> AgentSession:
        """Create isolated execution session."""

    async def invoke_agent(
        self,
        session_id: str,
        request: AgentRequest,
        stream: bool = False,
    ) -> AgentResponse | AsyncIterator[AgentResponseChunk]:
        """Invoke agent with optional streaming."""

    async def checkpoint_session(
        self,
        session_id: str,
        checkpoint_name: str,
    ) -> SessionCheckpoint:
        """Save session state for resume capability."""
```

**Estimated Lines:** ~800
**Sprint:** 1-2

---

### 1.2 Episodic Memory Service

**Purpose:** Enable agents to learn from experiences and maintain persistent knowledge across sessions.

**AWS Parity Features:**
- Short-term memory (within session)
- Long-term memory (across sessions)
- Episodic memory (experience-based learning)
- Semantic memory (factual knowledge)
- High accuracy for memory retrieval (as publicly claimed by AWS as of December 2025)

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EpisodicMemoryService                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     Memory Types                                         ││
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────────┐ ││
│  │  │   Short-Term      │  │    Long-Term      │  │     Episodic        │ ││
│  │  │   (Working)       │  │    (Persistent)   │  │     (Experiential)  │ ││
│  │  ├───────────────────┤  ├───────────────────┤  ├─────────────────────┤ ││
│  │  │• Context window   │  │• User preferences │  │• Past interactions  │ ││
│  │  │• Current task     │  │• Learned facts    │  │• Success/failure    │ ││
│  │  │• Recent messages  │  │• Entity knowledge │  │• Pattern recognition│ ││
│  │  │• TTL: session     │  │• TTL: configurable│  │• TTL: configurable  │ ││
│  │  └───────────────────┘  └───────────────────┘  └─────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│  ┌─────────────────────────────────┴───────────────────────────────────────┐│
│  │                     Storage Backend                                      ││
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────────┐ ││
│  │  │   DynamoDB        │  │    OpenSearch     │  │     Neptune         │ ││
│  │  │   (Key-Value)     │  │    (Vector)       │  │     (Graph)         │ ││
│  │  ├───────────────────┤  ├───────────────────┤  ├─────────────────────┤ ││
│  │  │• Session state    │  │• Semantic search  │  │• Entity relations   │ ││
│  │  │• User profiles    │  │• Similarity match │  │• Knowledge graph    │ ││
│  │  │• Quick lookups    │  │• Embedding store  │  │• Reasoning paths    │ ││
│  │  └───────────────────┘  └───────────────────┘  └─────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│  ┌─────────────────────────────────┴───────────────────────────────────────┐│
│  │                     Memory Operations                                    ││
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────────┐ ││
│  │  │   Store           │  │    Retrieve       │  │     Consolidate     │ ││
│  │  ├───────────────────┤  ├───────────────────┤  ├─────────────────────┤ ││
│  │  │• Add memory       │  │• Semantic search  │  │• Short→Long transfer│ ││
│  │  │• Update memory    │  │• Temporal query   │  │• Pattern extraction │ ││
│  │  │• Tag/categorize   │  │• Relevance rank   │  │• Forgetting curve   │ ││
│  │  └───────────────────┘  └───────────────────┘  └─────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

**File:** `src/services/episodic_memory_service.py`

```python
class MemoryType(Enum):
    SHORT_TERM = "short_term"      # Within session
    LONG_TERM = "long_term"        # Across sessions
    EPISODIC = "episodic"          # Experience-based
    SEMANTIC = "semantic"          # Factual knowledge

@dataclass
class Memory:
    """A single memory unit."""
    memory_id: str
    memory_type: MemoryType
    agent_id: str
    user_id: str | None
    content: str
    embedding: list[float] | None
    metadata: dict[str, Any]
    importance_score: float  # 0.0 - 1.0
    access_count: int
    created_at: datetime
    last_accessed_at: datetime
    expires_at: datetime | None

@dataclass
class Episode:
    """A complete interaction episode for learning."""
    episode_id: str
    agent_id: str
    task_description: str
    actions_taken: list[AgentAction]
    outcome: Literal["success", "failure", "partial"]
    feedback: str | None
    learned_patterns: list[str]
    created_at: datetime

class EpisodicMemoryService:
    """
    Multi-tier memory system for agent learning and personalization.

    Implements AWS AgentCore Memory parity:
    - Short-term working memory
    - Long-term persistent memory
    - Episodic experience-based learning
    - Semantic factual knowledge
    """

    async def store_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        user_id: str | None = None,
        importance: float = 0.5,
        ttl_hours: float | None = None,
    ) -> Memory:
        """Store a new memory with automatic embedding."""

    async def retrieve_memories(
        self,
        agent_id: str,
        query: str,
        memory_types: list[MemoryType] | None = None,
        user_id: str | None = None,
        limit: int = 10,
        min_relevance: float = 0.5,
    ) -> list[Memory]:
        """Retrieve relevant memories using semantic search."""

    async def record_episode(
        self,
        agent_id: str,
        task: str,
        actions: list[AgentAction],
        outcome: str,
        feedback: str | None = None,
    ) -> Episode:
        """Record a complete interaction episode for learning."""

    async def consolidate_memories(
        self,
        agent_id: str,
    ) -> ConsolidationResult:
        """Transfer important short-term to long-term memory."""

    async def extract_patterns(
        self,
        agent_id: str,
        episode_ids: list[str] | None = None,
    ) -> list[LearnedPattern]:
        """Extract patterns from episodes for future use."""
```

**Estimated Lines:** ~600
**Sprint:** 2-3

---

### 1.3 OAuth Delegation Service

**Purpose:** Enable agents to securely act on behalf of users with third-party services.

**AWS Parity Features:**
- OAuth 2.0 authorization code flow
- Secure token vault storage
- Automatic token refresh
- Multi-tenant support with custom claims
- Native IdP integration (Cognito, Okta, Azure AD)

**File:** `src/services/oauth_delegation_service.py`

```python
@dataclass
class OAuthProvider:
    """OAuth provider configuration."""
    provider_id: str
    provider_type: Literal["cognito", "okta", "azure_ad", "google", "custom"]
    client_id: str
    client_secret_arn: str  # Secrets Manager ARN
    authorization_url: str
    token_url: str
    scopes: list[str]
    custom_claims: dict[str, str] | None = None

@dataclass
class DelegatedToken:
    """Token delegated by user to agent."""
    token_id: str
    agent_id: str
    user_id: str
    provider_id: str
    access_token_encrypted: str
    refresh_token_encrypted: str | None
    scopes: list[str]
    expires_at: datetime
    created_at: datetime

class OAuthDelegationService:
    """
    Secure OAuth delegation for agent-to-service authentication.

    Implements AWS AgentCore Identity parity:
    - OAuth 2.0 flows
    - Secure token vault
    - Auto-refresh
    - Multi-tenant custom claims
    """

    async def initiate_authorization(
        self,
        agent_id: str,
        user_id: str,
        provider_id: str,
        scopes: list[str],
        redirect_uri: str,
    ) -> AuthorizationRequest:
        """Start OAuth authorization flow."""

    async def complete_authorization(
        self,
        authorization_code: str,
        state: str,
    ) -> DelegatedToken:
        """Exchange code for tokens and store securely."""

    async def get_access_token(
        self,
        agent_id: str,
        user_id: str,
        provider_id: str,
    ) -> str:
        """Get valid access token, refreshing if needed."""

    async def revoke_delegation(
        self,
        agent_id: str,
        user_id: str,
        provider_id: str | None = None,
    ) -> bool:
        """Revoke agent's delegated access."""
```

**Estimated Lines:** ~700
**Sprint:** 3-4

---

### 1.4 Cedar Policy Engine

**Purpose:** Real-time policy enforcement for agent tool calls using natural language policy definitions.

**AWS Parity Features:**
- Cedar policy language integration
- Natural language → Cedar conversion
- Real-time tool call interception
- Policy evaluation with audit logging
- Hierarchical policy inheritance

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CedarPolicyEngine                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     Policy Definition Layer                              ││
│  │  ┌───────────────────────────────────────────────────────────────────┐  ││
│  │  │                Natural Language Policy Input                       │  ││
│  │  │  "Agents cannot access customer PII without explicit consent"     │  ││
│  │  │  "Sales agents can only modify records in their assigned region"  │  ││
│  │  └───────────────────────────────────────────────────────────────────┘  ││
│  │                                 │                                        ││
│  │                                 ▼                                        ││
│  │  ┌───────────────────────────────────────────────────────────────────┐  ││
│  │  │                   LLM Policy Translator                            │  ││
│  │  │  • Parse natural language intent                                   │  ││
│  │  │  • Generate Cedar policy syntax                                    │  ││
│  │  │  • Validate policy correctness                                     │  ││
│  │  └───────────────────────────────────────────────────────────────────┘  ││
│  │                                 │                                        ││
│  │                                 ▼                                        ││
│  │  ┌───────────────────────────────────────────────────────────────────┐  ││
│  │  │                   Cedar Policy Store                               │  ││
│  │  │  permit(                                                           │  ││
│  │  │    principal == Agent::"sales-agent",                              │  ││
│  │  │    action == Action::"modify_record",                              │  ││
│  │  │    resource                                                        │  ││
│  │  │  ) when {                                                          │  ││
│  │  │    resource.region == principal.assigned_region                    │  ││
│  │  │  };                                                                │  ││
│  │  └───────────────────────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│  ┌─────────────────────────────────┴───────────────────────────────────────┐│
│  │                     Policy Enforcement Layer                             ││
│  │  ┌───────────────────────────────────────────────────────────────────┐  ││
│  │  │                Tool Call Interceptor                               │  ││
│  │  │  • Intercept all MCP tool invocations                              │  ││
│  │  │  • Extract principal, action, resource context                     │  ││
│  │  │  • Evaluate against policy store                                   │  ││
│  │  │  • Allow/Deny with audit logging                                   │  ││
│  │  └───────────────────────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

**File:** `src/services/cedar_policy_engine.py`

```python
@dataclass
class CedarPolicy:
    """A Cedar policy definition."""
    policy_id: str
    policy_name: str
    description: str
    cedar_syntax: str
    natural_language: str | None
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class PolicyEvaluationRequest:
    """Request to evaluate a policy decision."""
    principal: str          # e.g., "Agent::coder-agent"
    action: str             # e.g., "Action::invoke_tool"
    resource: str           # e.g., "Tool::slack_post_message"
    context: dict[str, Any] # Additional context for evaluation

@dataclass
class PolicyEvaluationResult:
    """Result of policy evaluation."""
    decision: Literal["allow", "deny"]
    matched_policies: list[str]
    reasons: list[str]
    evaluation_time_ms: float

class CedarPolicyEngine:
    """
    Cedar-based policy engine for agent governance.

    Implements AWS AgentCore Policy parity:
    - Natural language policy definition
    - Cedar policy language
    - Real-time tool call interception
    - Audit logging
    """

    async def create_policy_from_natural_language(
        self,
        description: str,
        policy_name: str,
    ) -> CedarPolicy:
        """Convert natural language to Cedar policy using LLM."""

    async def create_policy(
        self,
        policy_name: str,
        cedar_syntax: str,
        description: str | None = None,
    ) -> CedarPolicy:
        """Create policy from Cedar syntax directly."""

    async def evaluate(
        self,
        request: PolicyEvaluationRequest,
    ) -> PolicyEvaluationResult:
        """Evaluate policy decision for an action."""

    def intercept_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> PolicyEvaluationResult:
        """Intercept and evaluate tool call before execution."""

    async def audit_decision(
        self,
        request: PolicyEvaluationRequest,
        result: PolicyEvaluationResult,
    ) -> None:
        """Log policy decision for compliance audit."""
```

**Estimated Lines:** ~900
**Sprint:** 4-5

---

### 1.5 Agent Evaluation Service

**Purpose:** Comprehensive evaluation framework for measuring agent quality, safety, and effectiveness.

**AWS Parity Features:**
- 13 pre-built evaluators
- Live interaction monitoring
- Correctness, safety, tool selection accuracy
- Custom evaluator support
- Continuous quality monitoring

**Built-in Evaluators:**

| # | Evaluator | Description |
|---|-----------|-------------|
| 1 | Correctness | Factual accuracy of responses |
| 2 | Helpfulness | Task completion effectiveness |
| 3 | Safety | Harmful content detection |
| 4 | Tool Selection | Appropriate tool choice |
| 5 | Tool Usage | Correct tool parameter usage |
| 6 | Goal Achievement | End-to-end task success |
| 7 | Coherence | Logical consistency |
| 8 | Relevance | Response relevance to query |
| 9 | Groundedness | Factual grounding in context |
| 10 | Latency | Response time performance |
| 11 | Cost Efficiency | Token/API cost optimization |
| 12 | User Satisfaction | Inferred user satisfaction |
| 13 | Policy Compliance | Adherence to defined policies |

**File:** `src/services/agent_evaluation_service.py`

```python
class EvaluatorType(Enum):
    CORRECTNESS = "correctness"
    HELPFULNESS = "helpfulness"
    SAFETY = "safety"
    TOOL_SELECTION = "tool_selection"
    TOOL_USAGE = "tool_usage"
    GOAL_ACHIEVEMENT = "goal_achievement"
    COHERENCE = "coherence"
    RELEVANCE = "relevance"
    GROUNDEDNESS = "groundedness"
    LATENCY = "latency"
    COST_EFFICIENCY = "cost_efficiency"
    USER_SATISFACTION = "user_satisfaction"
    POLICY_COMPLIANCE = "policy_compliance"

@dataclass
class EvaluationResult:
    """Result from a single evaluator."""
    evaluator: EvaluatorType
    score: float  # 0.0 - 1.0
    passed: bool
    details: dict[str, Any]
    recommendations: list[str]

@dataclass
class AgentEvaluationReport:
    """Complete evaluation report for an agent interaction."""
    evaluation_id: str
    agent_id: str
    session_id: str
    interaction_id: str
    results: list[EvaluationResult]
    overall_score: float
    critical_issues: list[str]
    evaluated_at: datetime

class AgentEvaluationService:
    """
    Comprehensive agent evaluation framework.

    Implements AWS AgentCore Evaluations parity:
    - 13 pre-built evaluators
    - Live monitoring
    - Custom evaluators
    - Continuous quality tracking
    """

    async def evaluate_interaction(
        self,
        agent_id: str,
        session_id: str,
        interaction: AgentInteraction,
        evaluators: list[EvaluatorType] | None = None,
    ) -> AgentEvaluationReport:
        """Evaluate a single agent interaction."""

    async def evaluate_batch(
        self,
        agent_id: str,
        interactions: list[AgentInteraction],
        evaluators: list[EvaluatorType] | None = None,
    ) -> list[AgentEvaluationReport]:
        """Evaluate multiple interactions in batch."""

    async def start_live_monitoring(
        self,
        agent_id: str,
        evaluators: list[EvaluatorType],
        alert_thresholds: dict[EvaluatorType, float],
    ) -> MonitoringSession:
        """Start continuous evaluation monitoring."""

    async def get_quality_metrics(
        self,
        agent_id: str,
        time_range: tuple[datetime, datetime],
    ) -> QualityMetrics:
        """Get aggregated quality metrics over time."""

    def register_custom_evaluator(
        self,
        name: str,
        evaluator_fn: Callable[[AgentInteraction], EvaluationResult],
    ) -> None:
        """Register a custom evaluator function."""
```

**Estimated Lines:** ~1000
**Sprint:** 5-6

---

### 1.6 Browser Tool Agent

**Purpose:** Enable agents to interact with web-based services and perform complex web automation.

**AWS Parity Features:**
- Cloud-based browser runtime
- Web page interaction (click, type, scroll)
- Screenshot capture
- Form filling
- Multi-tab support
- JavaScript execution

**File:** `src/agents/browser_tool_agent.py`

```python
@dataclass
class BrowserAction:
    """A browser automation action."""
    action_type: Literal[
        "navigate", "click", "type", "scroll", "screenshot",
        "wait", "extract", "execute_js", "new_tab", "close_tab"
    ]
    selector: str | None = None
    value: str | None = None
    timeout_ms: int = 30000

@dataclass
class BrowserState:
    """Current state of browser session."""
    session_id: str
    current_url: str
    page_title: str
    tabs: list[TabInfo]
    screenshot_base64: str | None
    dom_snapshot: str | None

class BrowserToolAgent(SpawnableAgent):
    """
    Web automation agent using cloud-based browser.

    Implements AWS AgentCore Browser Tool parity:
    - Playwright-based browser control
    - Secure isolated execution
    - Multi-tab support
    - Screenshot and DOM extraction
    """

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.BROWSER_AUTOMATION

    async def create_session(
        self,
        headless: bool = True,
        viewport: tuple[int, int] = (1920, 1080),
    ) -> str:
        """Create new browser session."""

    async def execute_action(
        self,
        session_id: str,
        action: BrowserAction,
    ) -> BrowserState:
        """Execute browser action and return state."""

    async def execute_workflow(
        self,
        session_id: str,
        actions: list[BrowserAction],
    ) -> list[BrowserState]:
        """Execute sequence of browser actions."""

    async def extract_data(
        self,
        session_id: str,
        extraction_spec: DataExtractionSpec,
    ) -> dict[str, Any]:
        """Extract structured data from page."""
```

**Estimated Lines:** ~600
**Sprint:** 7

---

### 1.7 Code Interpreter Agent

**Purpose:** Secure multi-language code execution for data analysis and visualization.

**AWS Parity Features:**
- Multi-language support (Python, JavaScript, Go, Rust, Java)
- Secure sandbox execution (Firecracker/gVisor)
- File I/O within sandbox
- Visualization output
- Package installation

**File:** `src/agents/code_interpreter_agent.py`

```python
class SupportedLanguage(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    RUBY = "ruby"

@dataclass
class CodeExecutionRequest:
    """Request to execute code."""
    code: str
    language: SupportedLanguage
    timeout_seconds: int = 60
    memory_mb: int = 256
    files: dict[str, bytes] | None = None  # Input files
    packages: list[str] | None = None  # Packages to install

@dataclass
class CodeExecutionResult:
    """Result of code execution."""
    success: bool
    stdout: str
    stderr: str
    return_value: Any | None
    output_files: dict[str, bytes]
    visualizations: list[Visualization]
    execution_time_ms: float
    memory_used_mb: float

class CodeInterpreterAgent(SpawnableAgent):
    """
    Secure multi-language code execution agent.

    Implements AWS AgentCore Code Interpreter parity:
    - Multi-language support
    - Firecracker sandbox isolation
    - File I/O and visualization
    - Package management
    """

    @property
    def capability(self) -> AgentCapability:
        return AgentCapability.CODE_EXECUTION

    async def execute(
        self,
        request: CodeExecutionRequest,
    ) -> CodeExecutionResult:
        """Execute code in secure sandbox."""

    async def install_packages(
        self,
        language: SupportedLanguage,
        packages: list[str],
    ) -> bool:
        """Install packages in sandbox environment."""

    async def create_visualization(
        self,
        code: str,
        data: dict[str, Any],
        output_format: Literal["png", "svg", "html"] = "png",
    ) -> Visualization:
        """Generate visualization from code and data."""
```

**Estimated Lines:** ~700
**Sprint:** 8

---

### 1.8 Semantic Tool Search

**Purpose:** Intelligent tool discovery using semantic similarity.

**File:** `src/services/semantic_tool_search.py`

```python
class SemanticToolSearch:
    """
    Semantic search for tool discovery.

    Enables agents to find relevant tools based on
    natural language descriptions of what they need.
    """

    async def index_tool(
        self,
        tool_definition: AuraToolDefinition,
    ) -> None:
        """Index tool for semantic search."""

    async def search_tools(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.5,
        categories: list[AuraAgentCategory] | None = None,
    ) -> list[ToolSearchResult]:
        """Find tools matching natural language query."""

    async def recommend_tools(
        self,
        task_description: str,
        current_context: dict[str, Any],
    ) -> list[ToolRecommendation]:
        """Recommend tools for a given task."""
```

**Estimated Lines:** ~400
**Sprint:** 8

---

## Phase 2: Security Agent Enhancement (Q1-Q2 2026)

### 2.1 PR Security Scanner Agent

**Purpose:** Real-time security scanning of pull requests with inline comments.

**File:** `src/agents/pr_security_scanner_agent.py`

```python
class PRSecurityScannerAgent(SpawnableAgent):
    """
    Real-time PR security scanner with GitHub/GitLab integration.

    Features:
    - Webhook-triggered scanning
    - Inline comment placement
    - Severity-based merge blocking
    - Remediation code suggestions
    """

    async def scan_pull_request(
        self,
        repo: str,
        pr_number: int,
        org_standards: OrgSecurityStandards | None = None,
    ) -> PRSecurityReport:
        """Scan PR and post findings as comments."""

    async def should_block_merge(
        self,
        report: PRSecurityReport,
        policy: MergeBlockingPolicy,
    ) -> tuple[bool, list[str]]:
        """Determine if PR should be blocked from merging."""
```

**Estimated Lines:** ~700
**Sprint:** 1-2

---

### 2.2 Dynamic Attack Planner Agent

**Purpose:** Context-aware penetration testing with adaptive attack planning.

**File:** `src/agents/dynamic_attack_planner_agent.py`

```python
class DynamicAttackPlannerAgent(SpawnableAgent):
    """
    Dynamic attack planning based on application context.

    Features:
    - Application-aware attack graphs
    - Adaptive testing based on discoveries
    - Hours-not-weeks execution
    - Business logic vulnerability detection
    """

    async def analyze_attack_surface(
        self,
        design_docs: list[str],
        source_code_paths: list[str],
        runtime_config: dict[str, Any],
    ) -> AttackSurface:
        """Analyze full application context for attack surface."""

    async def generate_attack_plan(
        self,
        attack_surface: AttackSurface,
        org_policies: OrgSecurityStandards,
        max_duration_hours: float = 4.0,
    ) -> AttackPlan:
        """Generate customized attack plan."""

    async def execute_attack_plan(
        self,
        plan: AttackPlan,
        sandbox_id: str,
    ) -> PenetrationTestReport:
        """Execute attack plan with adaptive adjustments."""
```

**Estimated Lines:** ~800
**Sprint:** 2-3

---

### 2.3 Organization Standards Validator Agent

**Purpose:** Enforce organization-wide security standards across all applications.

**File:** `src/agents/org_standards_validator_agent.py`

```python
@dataclass
class OrgSecurityStandard:
    """An organizational security standard."""
    standard_id: str
    name: str
    description: str
    rules: list[SecurityRule]
    severity: Literal["critical", "high", "medium", "low"]
    compliance_frameworks: list[str]  # CMMC, SOX, NIST

class OrgStandardsValidatorAgent(SpawnableAgent):
    """
    Organization-wide security standards enforcement.

    Features:
    - Define once, validate everywhere
    - Cross-application consistency
    - Compliance framework mapping
    - Automated remediation suggestions
    """

    async def define_standard(
        self,
        standard: OrgSecurityStandard,
    ) -> None:
        """Define an organization security standard."""

    async def validate_application(
        self,
        app_id: str,
        code_paths: list[str],
        config_paths: list[str],
    ) -> StandardsComplianceReport:
        """Validate application against all standards."""

    async def generate_remediation_plan(
        self,
        report: StandardsComplianceReport,
    ) -> RemediationPlan:
        """Generate remediation plan for violations."""
```

**Estimated Lines:** ~600
**Sprint:** 3-4

---

### 2.4 Multi-Cloud Security Connectors

**Files:**
- `src/services/azure_security_connector.py` (~400 lines)
- `src/services/gcp_security_connector.py` (~400 lines)

**Sprint:** 5

---

## Phase 3: DevOps Agent Enhancement (Q2 2026)

### 3.1 Deployment History Correlator

**Purpose:** Correlate incidents with deployment and configuration changes.

**File:** `src/services/deployment_history_correlator.py`

```python
@dataclass
class DeploymentEvent:
    """A deployment or configuration change event."""
    event_id: str
    event_type: Literal["deploy", "rollback", "config_change", "scale", "restart"]
    service: str
    environment: str
    timestamp: datetime
    git_commit: str | None
    changed_files: list[str]
    deployer: str
    ci_pipeline_id: str | None

class DeploymentHistoryCorrelator:
    """
    Correlate incidents with deployment history.

    Features:
    - Git commit correlation
    - CI/CD pipeline integration
    - Config change tracking
    - Blast radius analysis
    """

    async def ingest_deployment(
        self,
        event: DeploymentEvent,
    ) -> None:
        """Ingest deployment event for correlation."""

    async def correlate_incident(
        self,
        incident_time: datetime,
        affected_services: list[str],
        lookback_hours: float = 24.0,
    ) -> list[CorrelatedDeployment]:
        """Find deployments correlated with incident."""

    async def analyze_blast_radius(
        self,
        deployment: DeploymentEvent,
    ) -> BlastRadiusAnalysis:
        """Analyze potential blast radius of deployment."""
```

**Estimated Lines:** ~600
**Sprint:** 1

---

### 3.2 Resource Relationship Mapper

**Purpose:** Auto-discover and map relationships between infrastructure resources.

**File:** `src/services/resource_relationship_mapper.py`

```python
class ResourceRelationshipMapper:
    """
    Auto-discover infrastructure resource relationships.

    Features:
    - Service mesh discovery
    - Network topology mapping
    - Dependency chain analysis
    - Multi-cloud support
    """

    async def discover_resources(
        self,
        account_id: str,
        regions: list[str] | None = None,
    ) -> list[InfraResource]:
        """Discover all infrastructure resources."""

    async def map_relationships(
        self,
        resources: list[InfraResource],
    ) -> ResourceGraph:
        """Map relationships between resources."""

    async def get_dependency_chain(
        self,
        resource_id: str,
        direction: Literal["upstream", "downstream", "both"] = "both",
    ) -> DependencyChain:
        """Get dependency chain for a resource."""
```

**Estimated Lines:** ~700
**Sprint:** 1-2

---

### 3.3 Historical Pattern Analyzer

**Purpose:** Learn from historical incidents to predict and prevent future issues.

**File:** `src/services/historical_pattern_analyzer.py`

```python
class HistoricalPatternAnalyzer:
    """
    Learn patterns from historical incidents.

    Features:
    - Incident clustering
    - Root cause pattern extraction
    - Anomaly detection
    - Trend prediction
    """

    async def ingest_incident(
        self,
        incident: IncidentRecord,
    ) -> None:
        """Ingest historical incident for pattern learning."""

    async def find_similar_incidents(
        self,
        current_symptoms: list[str],
        limit: int = 5,
    ) -> list[SimilarIncident]:
        """Find historically similar incidents."""

    async def predict_root_cause(
        self,
        symptoms: list[str],
        affected_resources: list[str],
    ) -> list[PredictedRootCause]:
        """Predict likely root causes based on patterns."""

    async def detect_anomalies(
        self,
        metrics: list[MetricDataPoint],
    ) -> list[Anomaly]:
        """Detect anomalies in metrics."""
```

**Estimated Lines:** ~800
**Sprint:** 2-3

---

### 3.4 External Observability Connectors

**Files:**
- `src/services/dynatrace_connector.py` (~350 lines)
- `src/services/datadog_connector.py` (~350 lines)
- `src/services/newrelic_connector.py` (~350 lines)
- `src/services/splunk_connector.py` (~350 lines)

**Sprint:** 3-4

---

### 3.5 Proactive Recommendation Engine

**Purpose:** Generate proactive recommendations for operational excellence.

**File:** `src/services/proactive_recommendation_engine.py`

```python
class RecommendationCategory(Enum):
    OBSERVABILITY = "observability"
    INFRASTRUCTURE = "infrastructure"
    DEPLOYMENT_PIPELINE = "deployment_pipeline"
    APPLICATION_RESILIENCE = "application_resilience"

@dataclass
class ProactiveRecommendation:
    """A proactive operational recommendation."""
    recommendation_id: str
    category: RecommendationCategory
    title: str
    description: str
    impact: Literal["high", "medium", "low"]
    effort: Literal["high", "medium", "low"]
    evidence: list[str]
    implementation_steps: list[str]

class ProactiveRecommendationEngine:
    """
    Generate proactive operational recommendations.

    Four focus areas (AWS DevOps Agent parity):
    1. Observability enhancement
    2. Infrastructure optimization
    3. Deployment pipeline improvement
    4. Application resilience strengthening
    """

    async def analyze_observability(
        self,
        current_config: ObservabilityConfig,
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend observability improvements."""

    async def analyze_infrastructure(
        self,
        resource_graph: ResourceGraph,
        cost_data: CostData | None = None,
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend infrastructure optimizations."""

    async def analyze_deployment_pipeline(
        self,
        pipeline_config: PipelineConfig,
        deployment_history: list[DeploymentEvent],
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend pipeline improvements."""

    async def analyze_resilience(
        self,
        architecture: ArchitectureSpec,
        incident_history: list[IncidentRecord],
    ) -> list[ProactiveRecommendation]:
        """Analyze and recommend resilience improvements."""
```

**Estimated Lines:** ~900
**Sprint:** 5

---

## Phase 4: Transform Agent (Q2-Q3 2026)

### 4.1 Legacy Code Parsers

**Files:**
- `src/agents/cobol_parser_agent.py` - COBOL/JCL/BMS parsing (~1000 lines)
- `src/agents/dotnet_parser_agent.py` - .NET/C#/VB.NET parsing (~800 lines)

**Sprint:** 1-3

---

### 4.2 Business Intelligence Extraction

**Files:**
- `src/agents/business_rule_extractor_agent.py` (~700 lines)
- `src/agents/data_lineage_analyzer_agent.py` (~600 lines)

**Sprint:** 3-4

---

### 4.3 Code Transformation Engine

**File:** `src/agents/cross_language_translator_agent.py`

```python
class CrossLanguageTranslatorAgent(SpawnableAgent):
    """
    Cross-language code translation with functional equivalence.

    Supported translations:
    - COBOL → Java
    - COBOL → Python
    - VB.NET → C#
    - Classic ASP → ASP.NET Core
    - Custom → Modern
    """

    async def translate(
        self,
        source_code: str,
        source_language: str,
        target_language: str,
        preserve_comments: bool = True,
    ) -> TranslationResult:
        """Translate code from source to target language."""

    async def validate_equivalence(
        self,
        original: str,
        translated: str,
        test_cases: list[TestCase],
    ) -> EquivalenceReport:
        """Validate functional equivalence of translation."""
```

**Estimated Lines:** ~1200
**Sprint:** 5-6

---

### 4.4 Architecture Reimaginer

**File:** `src/agents/architecture_reimaginer_agent.py`

```python
class ArchitectureReimaginerAgent(SpawnableAgent):
    """
    Transform legacy architectures to modern patterns.

    Transformations:
    - Monolith → Microservices
    - Batch → Real-time/Event-driven
    - On-prem → Cloud-native
    - Synchronous → Asynchronous
    """

    async def analyze_current_architecture(
        self,
        code_paths: list[str],
        config_paths: list[str],
    ) -> ArchitectureAnalysis:
        """Analyze current system architecture."""

    async def generate_target_architecture(
        self,
        current: ArchitectureAnalysis,
        target_pattern: Literal["microservices", "event_driven", "serverless"],
        constraints: ArchitectureConstraints | None = None,
    ) -> TargetArchitecture:
        """Generate target architecture blueprint."""

    async def generate_migration_plan(
        self,
        current: ArchitectureAnalysis,
        target: TargetArchitecture,
    ) -> MigrationPlan:
        """Generate step-by-step migration plan."""
```

**Estimated Lines:** ~900
**Sprint:** 6-7

---

### 4.5 Automated Testing Suite

**Files:**
- `src/agents/test_plan_generator_agent.py` (~600 lines)
- `src/services/functional_equivalence_validator.py` (~700 lines)

**Sprint:** 7-8

---

## Infrastructure Requirements

### New CloudFormation Templates

| Template | Purpose |
|----------|---------|
| `agent-runtime.yaml` | ECS/Lambda for code upload deployment |
| `episodic-memory.yaml` | DynamoDB tables for memory storage |
| `cedar-policy.yaml` | Policy store and evaluation infrastructure |
| `browser-runtime.yaml` | ECS tasks for Playwright browsers |
| `code-interpreter.yaml` | Firecracker/gVisor sandbox infrastructure |
| `transform-pipeline.yaml` | Step Functions for transformation workflows |

### New DynamoDB Tables

| Table | Purpose | Capacity |
|-------|---------|----------|
| `aura-agent-sessions` | Session state | On-demand |
| `aura-episodic-memory` | Memory storage | On-demand |
| `aura-cedar-policies` | Policy definitions | Provisioned (25 RCU/WCU) |
| `aura-evaluations` | Evaluation results | On-demand |
| `aura-deployment-history` | Deployment correlation | On-demand |
| `aura-incident-patterns` | Historical patterns | On-demand |

### New S3 Buckets

| Bucket | Purpose |
|--------|---------|
| `aura-agent-artifacts-{env}` | Code upload storage |
| `aura-browser-screenshots-{env}` | Browser session screenshots |
| `aura-transformation-outputs-{env}` | Code transformation results |

---

## Success Metrics

### Phase 1: AgentCore Parity

| Metric | Target | Measurement |
|--------|--------|-------------|
| Code upload deployment time | <30 seconds | CloudWatch |
| Session isolation validation | 100% | Security tests |
| Memory retrieval accuracy | >90% | Benchmark tests |
| Policy evaluation latency | <10ms | P95 latency |
| Evaluator coverage | 13/13 built-in | Feature checklist |

### Phase 2: Security Agent

| Metric | Target | Measurement |
|--------|--------|-------------|
| PR scan coverage | 100% of PRs | GitHub webhook logs |
| Vulnerability detection rate | >95% | OWASP benchmark |
| False positive rate | <5% | Manual review |
| Pen test completion time | <4 hours | Execution logs |

### Phase 3: DevOps Agent

| Metric | Target | Measurement |
|--------|--------|-------------|
| RCA accuracy | >86% | Manual validation |
| Incident correlation accuracy | >90% | Historical comparison |
| Recommendation adoption rate | >50% | User feedback |
| MTTR reduction | >30% | Incident metrics |

### Phase 4: Transform Agent

| Metric | Target | Measurement |
|--------|--------|-------------|
| Translation accuracy | >95% | Test case pass rate |
| Functional equivalence | 100% | Automated validation |
| Modernization time reduction | >5x | Project benchmarks |
| Lines of code processed | >1M LOC | Processing logs |

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Cedar integration complexity | Medium | High | Start with subset of Cedar features |
| Firecracker sandbox complexity | High | Medium | Use gVisor as fallback |
| COBOL parsing accuracy | Medium | High | Partner with mainframe experts |
| Multi-cloud connector maintenance | High | Medium | Standardize on OpenTelemetry |

### Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Phase 1 scope creep | Medium | High | Strict MVP scoping |
| Transform agent complexity | High | High | Start with Python target only |
| External API changes | Medium | Medium | Version pinning, abstraction layers |

### Security Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Code interpreter escape | Low | Critical | Firecracker + network isolation |
| OAuth token exposure | Low | Critical | KMS encryption, audit logging |
| Browser session hijacking | Low | High | Session isolation, short TTLs |

---

## Alternatives Considered

### Alternative 1: Integrate AWS Agents Directly

**Description:** Use AWS Security Agent, DevOps Agent, and Transform Agent as external services.

**Pros:**
- No development cost
- Always up-to-date with AWS capabilities

**Cons:**
- Vendor lock-in
- No differentiation
- Can't customize for GovCloud/CMMC requirements
- Loses Aura's GraphRAG advantage

**Decision:** Rejected - Must maintain competitive differentiation.

### Alternative 2: Partial Replication

**Description:** Only replicate high-priority capabilities.

**Pros:**
- Faster time to market
- Lower development cost

**Cons:**
- Incomplete feature parity
- Customer comparison unfavorable
- Technical debt accumulation

**Decision:** Rejected - Full parity is considered necessary to meet anticipated enterprise customer expectations.

### Alternative 3: Partnership with AWS

**Description:** Partner with AWS to white-label their agents.

**Pros:**
- Full capabilities immediately
- AWS marketing support

**Cons:**
- Revenue sharing
- Loss of control
- GovCloud limitations
- Dependency on AWS roadmap

**Decision:** Rejected - Strategic independence required.

---

## Implementation Timeline

```
2026
Q1                          Q2                          Q3
├───────────────────────────┼───────────────────────────┼───────────────────────────┤
│                           │                           │                           │
│  PHASE 1: AgentCore       │  PHASE 2: Security Agent  │  PHASE 4: Transform       │
│  ─────────────────────    │  ────────────────────     │  ──────────────────       │
│  Sprint 1-2: Runtime      │  Sprint 1-2: PR Scanner   │  Sprint 1-3: Parsers      │
│  Sprint 2-3: Memory       │  Sprint 2-3: Attack Plan  │  Sprint 3-4: Extraction   │
│  Sprint 3-4: OAuth        │  Sprint 3-4: Org Stds     │  Sprint 5-6: Translation  │
│  Sprint 4-5: Cedar        │  Sprint 5: Multi-cloud    │  Sprint 6-7: Reimagine    │
│  Sprint 5-6: Evaluations  │                           │  Sprint 7-8: Testing      │
│  Sprint 7: Browser        │  PHASE 3: DevOps Agent    │                           │
│  Sprint 8: Code Interp    │  ───────────────────      │                           │
│                           │  Sprint 1: Deploy Hist    │                           │
│                           │  Sprint 1-2: Resource Map │                           │
│                           │  Sprint 2-3: Patterns     │                           │
│                           │  Sprint 3-4: Connectors   │                           │
│                           │  Sprint 5: Recommend      │                           │
│                           │                           │                           │
└───────────────────────────┴───────────────────────────┴───────────────────────────┘

Total: 22-29 sprints (~9-12 months)
```

---

---

*Competitive references in this ADR reflect publicly available information as of the document date. Vendor products evolve; readers should verify current capabilities before decision-making. Third-party vendor names and products referenced herein are trademarks of their respective owners. References are nominative and do not imply endorsement or partnership.*

## References

### External Sources

- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- [AWS DevOps Agent](https://aws.amazon.com/devops-agent/)
- [AWS Frontier Agents Announcement](https://www.aboutamazon.com/news/aws/amazon-ai-frontier-agents-autonomous-kiro)
- [AWS Transform Agentic Capabilities](https://www.aboutamazon.com/news/aws/aws-transform-ai-agents-windows-modern)
- [AWS Security Innovations re:Invent 2025](https://aws.amazon.com/blogs/security/aws-launches-ai-enhanced-security-innovations-at-reinvent-2025/)
- [AgentCore Policy and Evaluations](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-bedrock-agentcore-policy-evaluations-preview/)
- [Cedar Policy Language](https://www.cedarpolicy.com/)

### Internal References

- ADR-019: Market Intelligence Agent
- ADR-023: AgentCore Gateway Integration
- ADR-025: RuntimeIncidentAgent Architecture
- ADR-028: Foundry Capability Adoption
- ADR-029: Agent Optimization Roadmap

---

## Appendix A: Component Inventory

### New Files (30 total)

| Phase | File | Lines |
|-------|------|-------|
| 1 | `src/services/agent_runtime_service.py` | ~800 |
| 1 | `src/services/episodic_memory_service.py` | ~600 |
| 1 | `src/services/oauth_delegation_service.py` | ~700 |
| 1 | `src/services/cedar_policy_engine.py` | ~900 |
| 1 | `src/services/agent_evaluation_service.py` | ~1000 |
| 1 | `src/agents/browser_tool_agent.py` | ~600 |
| 1 | `src/agents/code_interpreter_agent.py` | ~700 |
| 1 | `src/services/semantic_tool_search.py` | ~400 |
| 2 | `src/agents/pr_security_scanner_agent.py` | ~700 |
| 2 | `src/agents/dynamic_attack_planner_agent.py` | ~800 |
| 2 | `src/agents/org_standards_validator_agent.py` | ~600 |
| 2 | `src/services/unified_security_context.py` | ~500 |
| 2 | `src/services/azure_security_connector.py` | ~400 |
| 2 | `src/services/gcp_security_connector.py` | ~400 |
| 3 | `src/services/deployment_history_correlator.py` | ~600 |
| 3 | `src/services/resource_relationship_mapper.py` | ~700 |
| 3 | `src/services/historical_pattern_analyzer.py` | ~800 |
| 3 | `src/services/dynatrace_connector.py` | ~350 |
| 3 | `src/services/datadog_connector.py` | ~350 |
| 3 | `src/services/newrelic_connector.py` | ~350 |
| 3 | `src/services/splunk_connector.py` | ~350 |
| 3 | `src/services/proactive_recommendation_engine.py` | ~900 |
| 4 | `src/agents/cobol_parser_agent.py` | ~1000 |
| 4 | `src/agents/dotnet_parser_agent.py` | ~800 |
| 4 | `src/agents/business_rule_extractor_agent.py` | ~700 |
| 4 | `src/agents/data_lineage_analyzer_agent.py` | ~600 |
| 4 | `src/agents/cross_language_translator_agent.py` | ~1200 |
| 4 | `src/agents/architecture_reimaginer_agent.py` | ~900 |
| 4 | `src/agents/test_plan_generator_agent.py` | ~600 |
| 4 | `src/services/functional_equivalence_validator.py` | ~700 |

**Total New Lines:** ~20,000

### New AgentCapabilities

```python
class AgentCapability(Enum):
    # Existing capabilities...

    # New Phase 1 capabilities
    BROWSER_AUTOMATION = "browser_automation"
    CODE_EXECUTION = "code_execution"
    POLICY_EVALUATION = "policy_evaluation"
    AGENT_EVALUATION = "agent_evaluation"

    # New Phase 2 capabilities
    PR_SECURITY_SCAN = "pr_security_scan"
    DYNAMIC_ATTACK_PLANNING = "dynamic_attack_planning"
    ORG_STANDARDS_VALIDATION = "org_standards_validation"

    # New Phase 3 capabilities
    DEPLOYMENT_CORRELATION = "deployment_correlation"
    RESOURCE_MAPPING = "resource_mapping"
    PATTERN_ANALYSIS = "pattern_analysis"
    PROACTIVE_RECOMMENDATION = "proactive_recommendation"

    # New Phase 4 capabilities
    LEGACY_CODE_PARSING = "legacy_code_parsing"
    BUSINESS_RULE_EXTRACTION = "business_rule_extraction"
    DATA_LINEAGE_ANALYSIS = "data_lineage_analysis"
    CROSS_LANGUAGE_TRANSLATION = "cross_language_translation"
    ARCHITECTURE_REIMAGINING = "architecture_reimagining"
    TEST_PLAN_GENERATION = "test_plan_generation"
```

---

## Appendix B: API Specifications

See separate API specification documents:
- `docs/api-specs/agentcore-api.yaml` (OpenAPI 3.0)
- `docs/api-specs/security-agent-api.yaml` (OpenAPI 3.0)
- `docs/api-specs/devops-agent-api.yaml` (OpenAPI 3.0)
- `docs/api-specs/transform-agent-api.yaml` (OpenAPI 3.0)
