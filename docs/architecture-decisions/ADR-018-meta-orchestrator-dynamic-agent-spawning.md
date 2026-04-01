# ADR-018: MetaOrchestrator with Dynamic Agent Spawning

**Status:** Deployed
**Date:** 2025-12-03
**Decision Makers:** Project Aura Team
**Related:** ADR-005 (HITL Sandbox Architecture), ADR-010 (Autonomous ADR Generation Pipeline), ADR-015 (Tiered LLM Model Strategy), ADR-016 (HITL Auto-Escalation Strategy)

## Context

### Competitive Landscape

AWS and other major cloud providers are developing security agents capable of:
- **Dynamic agent spawning** - Creating sub-agents on-demand for complex tasks
- **Recursive task decomposition** - Breaking complex problems into smaller sub-tasks handled by specialized agents
- **80-85% autonomous operation** - Minimal human oversight for routine security operations

### Current Project Aura Limitations

Project Aura's current `System2Orchestrator` uses a **static pipeline architecture**:

```
PLAN → CONTEXT → CODE → REVIEW → VALIDATE → REMEDIATE (loop)
```

**Limitations:**
1. **Fixed agent composition** - Cannot dynamically spawn specialized agents
2. **Limited parallelism** - Sequential execution except for context retrieval
3. **HITL-mandatory for HIGH/CRITICAL** - No configurable autonomy levels
4. **2-iteration cap** - Cannot recursively decompose complex problems
5. **Single-level orchestration** - Agents cannot delegate to sub-agents

### Business Requirements

| Requirement | Description |
|-------------|-------------|
| **Dual-Mode Operation** | Support both HITL-required (regulated industries) and fully autonomous (trusted environments) |
| **Scalable Complexity** | Handle arbitrarily complex security tasks via recursive decomposition |
| **Competitive Parity** | Match AWS agent capabilities (80-85% autonomous operation) |
| **Enterprise Flexibility** | Per-organization, per-repository, per-severity autonomy configuration |

### Key Question

How should Project Aura evolve to support dynamic agent spawning, recursive task decomposition, and configurable autonomy levels while maintaining security and compliance guarantees?

## Decision

We chose a **MetaOrchestrator Architecture** with three core capabilities:

1. **Dynamic Agent Spawning** - LLM-driven agent instantiation based on task requirements
2. **Recursive Task Decomposition** - Hierarchical breakdown with depth limits
3. **Configurable Autonomy Levels** - Organization-defined HITL policies

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MetaOrchestrator                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      TaskDecomposer (LLM)                             │  │
│  │  Input: Complex task description                                       │  │
│  │  Output: DAG of sub-tasks with agent assignments                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                    ┌───────────────┼───────────────┐                       │
│                    ▼               ▼               ▼                       │
│             ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│             │ Agent A  │    │ Agent B  │    │ Agent C  │                   │
│             │ (can     │    │ (leaf    │    │ (can     │                   │
│             │  spawn)  │    │  agent)  │    │  spawn)  │                   │
│             └────┬─────┘    └──────────┘    └────┬─────┘                   │
│                  │                               │                          │
│           ┌──────┴──────┐                 ┌──────┴──────┐                   │
│           ▼             ▼                 ▼             ▼                   │
│      ┌────────┐    ┌────────┐        ┌────────┐    ┌────────┐              │
│      │Agent A1│    │Agent A2│        │Agent C1│    │Agent C2│              │
│      └────────┘    └────────┘        └────────┘    └────────┘              │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      ResultAggregator                                 │  │
│  │  - Collects results from all agents (leaf + intermediate)             │  │
│  │  - Resolves conflicts and contradictions                              │  │
│  │  - Applies autonomy policy (HITL check or auto-approve)               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Dynamic Agent Spawning

#### Agent Registry Pattern

```python
class AgentCapability(Enum):
    CODE_GENERATION = "code_generation"
    SECURITY_REVIEW = "security_review"
    VULNERABILITY_SCAN = "vulnerability_scan"
    PATCH_VALIDATION = "patch_validation"
    THREAT_ANALYSIS = "threat_analysis"
    DEPENDENCY_AUDIT = "dependency_audit"
    COMPLIANCE_CHECK = "compliance_check"
    ARCHITECTURE_REVIEW = "architecture_review"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"

@dataclass
class AgentSpec:
    """Specification for dynamically spawned agent."""
    capability: AgentCapability
    task_description: str
    context_requirements: list[str]
    max_depth: int = 2  # How deep this agent can spawn sub-agents
    timeout_seconds: int = 300
    can_spawn_children: bool = True

class AgentRegistry:
    """Registry of available agent types for dynamic spawning."""

    AGENT_MAP: dict[AgentCapability, type] = {
        AgentCapability.CODE_GENERATION: CoderAgent,
        AgentCapability.SECURITY_REVIEW: ReviewerAgent,
        AgentCapability.PATCH_VALIDATION: ValidatorAgent,
        AgentCapability.THREAT_ANALYSIS: ThreatIntelligenceAgent,
        AgentCapability.COMPLIANCE_CHECK: ComplianceAgent,
        # ... additional mappings
    }

    def spawn_agent(self, spec: AgentSpec, llm_client, context) -> BaseAgent:
        """Dynamically instantiate agent based on specification."""
        agent_class = self.AGENT_MAP.get(spec.capability)
        if not agent_class:
            raise UnknownAgentCapabilityError(spec.capability)

        return agent_class(
            llm_client=llm_client,
            context=context,
            max_spawn_depth=spec.max_depth,
            can_spawn=spec.can_spawn_children,
        )
```

#### Spawn Protocol

```python
class SpawnableAgent(BaseAgent):
    """Base class for agents that can spawn sub-agents."""

    def __init__(self, llm_client, max_spawn_depth: int = 2, can_spawn: bool = True):
        super().__init__(llm_client)
        self.max_spawn_depth = max_spawn_depth
        self.can_spawn = can_spawn and max_spawn_depth > 0
        self.children: list[SpawnableAgent] = []
        self.registry = AgentRegistry()

    async def spawn_child(self, spec: AgentSpec) -> BaseAgent:
        """Spawn a child agent for delegated work."""
        if not self.can_spawn:
            raise SpawnNotAllowedError("Agent has reached max spawn depth")

        child_spec = AgentSpec(
            capability=spec.capability,
            task_description=spec.task_description,
            context_requirements=spec.context_requirements,
            max_depth=self.max_spawn_depth - 1,  # Decrement depth
            can_spawn_children=self.max_spawn_depth > 1,
        )

        child = self.registry.spawn_agent(child_spec, self.llm, self.context)
        self.children.append(child)
        return child

    async def delegate_task(self, task: str, capability: AgentCapability) -> AgentResult:
        """Delegate a sub-task to a dynamically spawned agent."""
        spec = AgentSpec(
            capability=capability,
            task_description=task,
            context_requirements=self._extract_context_needs(task),
        )
        child = await self.spawn_child(spec)
        return await child.execute(task)
```

### 2. Recursive Task Decomposition

#### TaskDecomposer

```python
@dataclass
class TaskNode:
    """Node in the task decomposition DAG."""
    task_id: str
    description: str
    capability: AgentCapability
    dependencies: list[str]  # task_ids this depends on
    estimated_complexity: float  # 0.0-1.0
    can_parallelize: bool
    requires_hitl: bool  # Based on autonomy policy

class TaskDecomposer:
    """LLM-powered task decomposition into agent-assignable sub-tasks."""

    DECOMPOSITION_PROMPT = '''
    Analyze this security task and decompose it into sub-tasks.

    Task: {task_description}
    Context: {context_summary}

    For each sub-task, specify:
    1. Description (what needs to be done)
    2. Required capability (from: {capabilities})
    3. Dependencies (which sub-tasks must complete first)
    4. Complexity (0.0-1.0, where >0.7 may need further decomposition)
    5. Can parallelize (true if no dependencies on sibling tasks)

    Rules:
    - Maximum 10 sub-tasks per decomposition
    - Tasks with complexity >0.7 should be flagged for recursive decomposition
    - Security-critical tasks must be marked appropriately

    Output as JSON array of TaskNode objects.
    '''

    MAX_RECURSION_DEPTH = 4  # Safety limit
    COMPLEXITY_THRESHOLD = 0.7  # Above this, consider further decomposition

    async def decompose(
        self,
        task: str,
        context: HybridContext,
        depth: int = 0
    ) -> list[TaskNode]:
        """Recursively decompose task into executable sub-tasks."""
        if depth >= self.MAX_RECURSION_DEPTH:
            # Force leaf node at max depth
            return [self._create_leaf_node(task)]

        # LLM decomposition
        prompt = self.DECOMPOSITION_PROMPT.format(
            task_description=task,
            context_summary=context.summary,
            capabilities=list(AgentCapability),
        )

        response = await self.llm.generate(
            prompt=prompt,
            operation="task_decomposition",
            model_tier=ModelTier.ACCURATE,
        )

        nodes = self._parse_task_nodes(response)

        # Recursively decompose complex sub-tasks
        final_nodes = []
        for node in nodes:
            if node.estimated_complexity > self.COMPLEXITY_THRESHOLD and depth < self.MAX_RECURSION_DEPTH - 1:
                # Recurse on complex tasks
                sub_nodes = await self.decompose(node.description, context, depth + 1)
                final_nodes.extend(sub_nodes)
            else:
                final_nodes.append(node)

        return final_nodes
```

### 3. Configurable Autonomy Levels

#### Autonomy Policy

```python
class AutonomyLevel(Enum):
    """Defines how much human oversight is required."""
    FULL_HITL = "full_hitl"           # All actions require approval
    CRITICAL_HITL = "critical_hitl"   # Only CRITICAL/HIGH severity requires approval
    AUDIT_ONLY = "audit_only"         # No approval needed, but all actions logged
    FULL_AUTONOMOUS = "full_autonomous"  # No approval, minimal logging

@dataclass
class AutonomyPolicy:
    """Organization-specific autonomy configuration."""
    organization_id: str
    default_level: AutonomyLevel

    # Override by severity
    severity_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)

    # Override by repository
    repository_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)

    # Override by operation type
    operation_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)

    # Guardrails (cannot be overridden)
    always_require_hitl: list[str] = field(default_factory=lambda: [
        "production_deployment",
        "credential_modification",
        "access_control_change",
    ])

    def get_autonomy_level(
        self,
        severity: str,
        repository: str,
        operation: str,
    ) -> AutonomyLevel:
        """Determine autonomy level for a specific action."""
        # Check guardrails first (cannot be bypassed)
        if operation in self.always_require_hitl:
            return AutonomyLevel.FULL_HITL

        # Check operation-specific override
        if operation in self.operation_overrides:
            return self.operation_overrides[operation]

        # Check repository-specific override
        if repository in self.repository_overrides:
            return self.repository_overrides[repository]

        # Check severity-specific override
        if severity in self.severity_overrides:
            return self.severity_overrides[severity]

        # Fall back to default
        return self.default_level

# Example configurations for different industries
AUTONOMY_PRESETS = {
    "defense_contractor": AutonomyPolicy(
        organization_id="defense",
        default_level=AutonomyLevel.FULL_HITL,
        severity_overrides={"LOW": AutonomyLevel.CRITICAL_HITL},
    ),
    "fintech_startup": AutonomyPolicy(
        organization_id="fintech",
        default_level=AutonomyLevel.CRITICAL_HITL,
        severity_overrides={
            "LOW": AutonomyLevel.AUDIT_ONLY,
            "MEDIUM": AutonomyLevel.AUDIT_ONLY,
        },
    ),
    "internal_tools": AutonomyPolicy(
        organization_id="internal",
        default_level=AutonomyLevel.FULL_AUTONOMOUS,
        operation_overrides={
            "credential_modification": AutonomyLevel.FULL_HITL,
        },
    ),
}
```

### 4. MetaOrchestrator Implementation

```python
class MetaOrchestrator:
    """
    Advanced orchestrator with dynamic agent spawning and configurable autonomy.

    Capabilities:
    - Decomposes complex tasks into sub-task DAGs
    - Dynamically spawns specialized agents
    - Supports recursive problem-solving (depth-limited)
    - Applies organization-specific autonomy policies
    - Aggregates and validates results from agent tree
    """

    def __init__(
        self,
        llm_client: BedrockLLMService,
        autonomy_policy: AutonomyPolicy,
        context_service: ContextRetrievalService,
        hitl_service: HITLApprovalService | None = None,
        notification_service: NotificationService | None = None,
        max_spawn_depth: int = 3,
        max_parallel_agents: int = 10,
    ):
        self.llm = llm_client
        self.autonomy_policy = autonomy_policy
        self.context_service = context_service
        self.hitl_service = hitl_service
        self.notification_service = notification_service
        self.max_spawn_depth = max_spawn_depth
        self.max_parallel_agents = max_parallel_agents

        self.decomposer = TaskDecomposer(llm_client)
        self.registry = AgentRegistry()
        self.monitor = MonitorAgent()

        # Execution state
        self.active_agents: list[SpawnableAgent] = []
        self.results: dict[str, AgentResult] = {}

    async def execute(
        self,
        task: str,
        repository: str,
        severity: str = "MEDIUM",
    ) -> MetaOrchestratorResult:
        """Execute a complex task with dynamic agent orchestration."""
        execution_id = self._generate_execution_id()

        try:
            # Phase 1: Retrieve context
            context = await self.context_service.get_hybrid_context(task)

            # Phase 2: Decompose task into sub-tasks
            task_dag = await self.decomposer.decompose(task, context)

            # Phase 3: Determine autonomy level
            autonomy = self.autonomy_policy.get_autonomy_level(
                severity=severity,
                repository=repository,
                operation=self._classify_operation(task),
            )

            # Phase 4: Execute task DAG with dynamic agent spawning
            results = await self._execute_dag(task_dag, context, autonomy)

            # Phase 5: Aggregate results
            aggregated = await self._aggregate_results(results)

            # Phase 6: Apply autonomy policy (HITL check if required)
            final_result = await self._apply_autonomy(
                aggregated,
                autonomy,
                severity,
                repository,
            )

            return final_result

        except Exception as e:
            logger.error(f"MetaOrchestrator execution failed: {e}")
            raise
        finally:
            # Cleanup spawned agents
            await self._cleanup_agents()

    async def _execute_dag(
        self,
        dag: list[TaskNode],
        context: HybridContext,
        autonomy: AutonomyLevel,
    ) -> dict[str, AgentResult]:
        """Execute task DAG with parallel and sequential phases."""
        results = {}
        pending = {node.task_id: node for node in dag}

        while pending:
            # Find executable tasks (dependencies satisfied)
            executable = [
                node for node in pending.values()
                if all(dep in results for dep in node.dependencies)
            ]

            if not executable:
                raise CyclicDependencyError("Task DAG contains cycles")

            # Group parallelizable tasks
            parallel_batch = [n for n in executable if n.can_parallelize][:self.max_parallel_agents]
            sequential = [n for n in executable if not n.can_parallelize]

            # Execute parallel batch
            if parallel_batch:
                batch_results = await asyncio.gather(*[
                    self._execute_task_node(node, context, results)
                    for node in parallel_batch
                ])
                for node, result in zip(parallel_batch, batch_results):
                    results[node.task_id] = result
                    del pending[node.task_id]

            # Execute sequential tasks
            for node in sequential:
                result = await self._execute_task_node(node, context, results)
                results[node.task_id] = result
                del pending[node.task_id]

        return results

    async def _execute_task_node(
        self,
        node: TaskNode,
        context: HybridContext,
        prior_results: dict[str, AgentResult],
    ) -> AgentResult:
        """Execute a single task node by spawning appropriate agent."""
        # Spawn agent for this task
        spec = AgentSpec(
            capability=node.capability,
            task_description=node.description,
            context_requirements=[],
            max_depth=self.max_spawn_depth,
        )

        agent = self.registry.spawn_agent(spec, self.llm, context)
        self.active_agents.append(agent)

        # Inject prior results as context
        enriched_context = self._enrich_context(context, prior_results, node.dependencies)

        # Execute agent
        result = await agent.execute(node.description, enriched_context)

        return result

    async def _apply_autonomy(
        self,
        result: AggregatedResult,
        autonomy: AutonomyLevel,
        severity: str,
        repository: str,
    ) -> MetaOrchestratorResult:
        """Apply autonomy policy to determine if HITL is needed."""

        if autonomy == AutonomyLevel.FULL_AUTONOMOUS:
            # Auto-approve, minimal logging
            return MetaOrchestratorResult(
                status="completed",
                result=result,
                hitl_required=False,
                auto_approved=True,
            )

        elif autonomy == AutonomyLevel.AUDIT_ONLY:
            # Auto-approve, full audit logging
            await self._log_audit_trail(result, repository, severity)
            return MetaOrchestratorResult(
                status="completed",
                result=result,
                hitl_required=False,
                auto_approved=True,
                audit_logged=True,
            )

        elif autonomy == AutonomyLevel.CRITICAL_HITL:
            # Only require HITL for HIGH/CRITICAL
            if severity in ("HIGH", "CRITICAL"):
                return await self._request_hitl_approval(result, severity, repository)
            else:
                await self._log_audit_trail(result, repository, severity)
                return MetaOrchestratorResult(
                    status="completed",
                    result=result,
                    hitl_required=False,
                    auto_approved=True,
                )

        else:  # FULL_HITL
            # Always require HITL approval
            return await self._request_hitl_approval(result, severity, repository)
```

## Spawn Trigger Reference

This section documents the specific conditions that cause the MetaOrchestrator to spawn agents.

### Trigger Overview

| Trigger | Entry Point | Condition | Spawn Rate |
|---------|-------------|-----------|------------|
| **Task Decomposition** | `execute()` Phase 2 | Complex task received | 1-10 agents per task |
| **DAG Execution** | `_execute_dag()` | TaskNode ready to execute | 1 agent per node |
| **Child Delegation** | `spawn_child()` | Parent agent needs sub-agent | 1 agent per delegation |

### Trigger 1: Task Decomposition (Primary)

**When:** A complex task is submitted to `MetaOrchestrator.execute()`

**Flow:**
```
User Request
    │
    ▼
MetaOrchestrator.execute()
    │
    ├─► Phase 1: Retrieve context (HybridContext)
    │
    ├─► Phase 2: TaskDecomposer.decompose(task, context)
    │       │
    │       ├─► LLM analyzes task complexity
    │       │
    │       ├─► If complexity > 0.7: Recursive decomposition
    │       │       └─► Max recursion depth: 4
    │       │
    │       └─► Output: DAG of TaskNodes
    │
    └─► Phase 3+: Execute DAG (see Trigger 2)
```

**Configuration:**
```python
COMPLEXITY_THRESHOLD = 0.7   # Tasks above this get further decomposed
MAX_RECURSION_DEPTH = 4      # Safety limit for decomposition
MAX_SUBTASKS_PER_DECOMPOSITION = 10  # Cap per LLM call
```

### Trigger 2: DAG Execution (Dynamic)

**When:** TaskNodes are ready for execution (dependencies satisfied)

**Flow:**
```
TaskNode DAG
    │
    ▼
_execute_dag()
    │
    ├─► Find executable nodes (all dependencies complete)
    │
    ├─► Separate into parallel vs sequential batches
    │       │
    │       ├─► Parallel: can_parallelize=True, no dependency conflicts
    │       │       └─► Execute up to max_parallel_agents (10) concurrently
    │       │
    │       └─► Sequential: has dependencies or can_parallelize=False
    │               └─► Execute one at a time
    │
    └─► For each executable node:
            │
            └─► _execute_task_node(node)
                    │
                    ├─► Create AgentSpec from TaskNode.capability
                    │
                    ├─► registry.spawn_agent(spec, llm, context)
                    │       └─► Returns SpawnableAgent instance
                    │
                    └─► agent.execute(task_description)
```

**Configuration:**
```python
max_parallel_agents = 10  # Concurrent agent limit
max_spawn_depth = 3       # How deep spawned agents can spawn
```

### Trigger 3: Child Delegation (Hierarchical)

**When:** A running agent determines it needs specialized help

**Flow:**
```
SpawnableAgent.execute()
    │
    ├─► Agent determines sub-task needed
    │       (e.g., CoderAgent needs SecurityReview)
    │
    ├─► Check: self.can_spawn == True?
    │       │
    │       ├─► No: Raise SpawnNotAllowedError
    │       │       └─► Fallback: Handle internally or fail
    │       │
    │       └─► Yes: Proceed to spawn
    │
    └─► spawn_child(AgentSpec)
            │
            ├─► Create child spec with:
            │       max_depth = self.max_spawn_depth - 1
            │       can_spawn = (max_spawn_depth > 1)
            │
            ├─► registry.spawn_agent(child_spec)
            │
            └─► child.execute(delegated_task)
```

**Depth Limits:**
```
Level 0: MetaOrchestrator (spawns Level 1)
    └─► Level 1: Primary agents (can spawn Level 2)
            └─► Level 2: Sub-agents (can spawn Level 3)
                    └─► Level 3: Leaf agents (cannot spawn)
```

### Spawn Decision Flowchart

```
                    ┌─────────────────────────┐
                    │   Task/Request Received │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  Is this a new task to  │
                    │    MetaOrchestrator?    │
                    └───────────┬─────────────┘
                                │
              ┌────────────Yes──┴───No────────────┐
              │                                    │
              ▼                                    ▼
    ┌─────────────────────┐           ┌─────────────────────┐
    │ TRIGGER 1:          │           │ Is this a running   │
    │ Task Decomposition  │           │ agent needing help? │
    │ - LLM decomposes    │           └──────────┬──────────┘
    │ - Creates TaskDAG   │                      │
    └─────────┬───────────┘          ┌───Yes─────┴────No────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────────┐  ┌─────────────────┐   ┌──────────────┐
    │ TRIGGER 2:          │  │ TRIGGER 3:      │   │ No spawn     │
    │ DAG Execution       │  │ Child Delegation│   │ (existing    │
    │ - Spawn per node    │  │ - Check depth   │   │  agent runs) │
    │ - Parallel batches  │  │ - Spawn child   │   └──────────────┘
    └─────────────────────┘  └─────────────────┘
```

### Spawn Failure Scenarios

| Scenario | Detection | Fallback |
|----------|-----------|----------|
| Unknown capability | `AgentRegistry.spawn_agent()` raises `UnknownAgentCapabilityError` | Log error, skip task, continue DAG |
| Max depth exceeded | `spawn_child()` raises `SpawnNotAllowedError` | Agent handles task internally |
| Max parallel reached | DAG executor waits | Queue excess tasks, execute when slot opens |
| LLM decomposition fails | `TaskDecomposer` returns empty/invalid | Fall back to single-agent execution |
| Cyclic dependency | `_execute_dag()` raises `CyclicDependencyError` | Abort execution, return error |
| Agent timeout | Configurable per `AgentSpec.timeout_seconds` | Terminate agent, mark task failed |

### Registered Agent Capabilities

The following capabilities trigger spawning of specific agent types:

| Capability | Agent Class | Typical Trigger |
|------------|-------------|-----------------|
| `CODE_GENERATION` | SpawnableCoderAgent | Patch generation needed |
| `SECURITY_REVIEW` | SpawnableReviewerAgent | Code review requested |
| `PATCH_VALIDATION` | SpawnableValidatorAgent | Patch needs testing |
| `VULNERABILITY_SCAN` | SpawnableVulnerabilityScanAgent | Security scan needed |
| `THREAT_ANALYSIS` | SpawnableThreatAnalysisAgent | Threat intel required |
| `ARCHITECTURE_REVIEW` | SpawnableArchitectureReviewAgent | Design review needed |
| `DEPENDENCY_AUDIT` | SpawnableDependencyAuditAgent | Dependency check |
| `COMPLIANCE_CHECK` | SpawnableComplianceCheckAgent | Compliance validation |
| `TEST_GENERATION` | SpawnableTestGenerationAgent | Tests needed |
| `DOCUMENTATION` | SpawnableDocumentationAgent | Docs needed |
| `GITHUB_INTEGRATION` | SpawnableGitHubIntegrationAgent | GitHub operations |
| `DESIGN_SECURITY_REVIEW` | SpawnableDesignSecurityReviewAgent | Design-level security |
| `BUSINESS_LOGIC_ANALYSIS` | SpawnableBusinessLogicAnalyzerAgent | Logic analysis |
| `PENETRATION_TESTING` | SpawnablePenetrationTestingAgent | Pentest operations |

### Autonomy Gate

All spawning is subject to autonomy policy checks:

```python
# Before any spawn, check autonomy level
autonomy = self.autonomy_policy.get_autonomy_level(
    severity=severity,
    repository=repository,
    operation=self._classify_operation(task),
)

# Guardrails cannot be bypassed (always HITL):
always_require_hitl = [
    "production_deployment",
    "credential_modification",
    "access_control_change",
]
```

## Alternatives Considered

### Alternative 1: Static Agent Pool with Load Balancing

**Description:** Pre-instantiate all agent types, route tasks via load balancer.

**Pros:**
- Simpler implementation
- Predictable resource usage
- No spawn latency

**Cons:**
- Cannot scale to complex tasks requiring many sub-agents
- Wasted resources for unused agent types
- No recursive decomposition capability

**Rejected because:** Does not address competitive gap (dynamic spawning).

### Alternative 2: Serverless Agent Functions (Lambda)

**Description:** Each agent type as a Lambda function, invoked on-demand.

**Pros:**
- True on-demand scaling
- Pay-per-use cost model
- Isolation between agents

**Cons:**
- Cold start latency (1-3s per spawn)
- Complex state management across functions
- Network overhead for inter-agent communication
- Lambda timeout limits (15 min max)

**Rejected because:** Latency and complexity outweigh benefits for this use case.

### Alternative 3: Fixed Autonomy Levels (No Configuration)

**Description:** Single autonomy policy for all organizations.

**Pros:**
- Simpler implementation
- Consistent behavior

**Cons:**
- Cannot serve diverse customer requirements
- Loses enterprise flexibility value proposition
- May over-restrict or under-restrict different industries

**Rejected because:** Business requirement for dual-mode operation.

## Consequences

### Positive

1. **Competitive parity** with AWS security agents
2. **Scalable complexity handling** via recursive decomposition
3. **Enterprise flexibility** through configurable autonomy
4. **Improved throughput** via parallel agent execution
5. **Future-proof architecture** for additional agent types

### Negative

1. **Increased complexity** in orchestration layer
2. **Resource management overhead** for spawned agents
3. **Potential for runaway spawning** (mitigated by depth limits)
4. **Testing complexity** for dynamic agent combinations

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent spawn explosion | Resource exhaustion | Hard limits: max_spawn_depth=3, max_parallel_agents=10 |
| Recursive loops | Infinite decomposition | MAX_RECURSION_DEPTH=4, cycle detection in DAG |
| Autonomy misconfiguration | Unauthorized actions | Guardrails list (cannot be overridden), audit logging |
| LLM decomposition failures | Invalid task DAGs | Validation layer, fallback to static orchestration |

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Implement `AgentRegistry` and `AgentSpec`
- [ ] Implement `SpawnableAgent` base class
- [ ] Implement `TaskDecomposer` with LLM integration
- [ ] Unit tests for spawning and decomposition

### Phase 2: MetaOrchestrator (Week 2-3)
- [ ] Implement `MetaOrchestrator` class
- [ ] Implement DAG execution engine
- [ ] Implement result aggregation
- [ ] Integration tests with mock agents

### Phase 3: Autonomy System (Week 3-4)
- [ ] Implement `AutonomyPolicy` and presets
- [ ] Integrate with existing HITL service
- [ ] Add audit logging for autonomous operations
- [ ] End-to-end tests for all autonomy levels

### Phase 4: Migration (Week 4-5)
- [ ] Migrate existing workflows to MetaOrchestrator
- [ ] Performance benchmarking
- [ ] Documentation and runbooks

## References

- ADR-005: HITL Sandbox Architecture
- ADR-010: Autonomous ADR Generation Pipeline
- ADR-015: Tiered LLM Model Strategy
- ADR-016: HITL Auto-Escalation Strategy
- AWS Security Agent capabilities (competitive analysis)
- Project Aura System Architecture (`SYSTEM_ARCHITECTURE.md`)
