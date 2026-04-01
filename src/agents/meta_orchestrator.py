"""
Project Aura - MetaOrchestrator with Dynamic Agent Spawning

Advanced orchestration system that enables:
- Dynamic agent spawning based on task requirements
- Recursive task decomposition for complex problems
- Configurable autonomy levels (HITL required vs fully autonomous)
- Parallel execution of independent sub-tasks

Implements ADR-018: MetaOrchestrator with Dynamic Agent Spawning

Usage:
    >>> from src.agents.meta_orchestrator import MetaOrchestrator, AutonomyPolicy
    >>> policy = AutonomyPolicy.from_preset("fintech_startup")
    >>> orchestrator = MetaOrchestrator(llm_client, policy, context_service)
    >>> result = await orchestrator.execute(
    ...     task="Analyze and fix SQL injection vulnerabilities",
    ...     repository="https://github.com/org/app",
    ...     severity="HIGH"
    ... )
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class AgentCapability(Enum):
    """Capabilities that agents can provide."""

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
    CONTEXT_RETRIEVAL = "context_retrieval"
    CODE_ANALYSIS = "code_analysis"
    # AWS Security Agent capability parity (ADR-019)
    GITHUB_INTEGRATION = "github_integration"
    DESIGN_SECURITY_REVIEW = "design_security_review"
    PENETRATION_TESTING = "penetration_testing"
    BUSINESS_LOGIC_ANALYSIS = "business_logic_analysis"
    # Market Intelligence capability (ADR-019)
    MARKET_INTELLIGENCE = "market_intelligence"
    COMPETITOR_WATCH = "competitor_watch"
    TREND_ANALYSIS = "trend_analysis"
    DOCUMENTATION_AGGREGATION = "documentation_aggregation"


class AutonomyLevel(Enum):
    """Defines how much human oversight is required."""

    FULL_HITL = "full_hitl"  # All actions require approval
    CRITICAL_HITL = "critical_hitl"  # Only CRITICAL/HIGH severity requires approval
    AUDIT_ONLY = "audit_only"  # No approval needed, but all actions logged
    FULL_AUTONOMOUS = "full_autonomous"  # No approval, minimal logging


class TaskStatus(Enum):
    """Status of a task in the execution DAG."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    AWAITING_HITL = "awaiting_hitl"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AgentSpec:
    """Specification for dynamically spawned agent."""

    capability: AgentCapability
    task_description: str
    context_requirements: list[str] = field(default_factory=list)
    max_depth: int = 2  # How deep this agent can spawn sub-agents
    timeout_seconds: int = 300
    can_spawn_children: bool = True
    priority: int = 5  # 1-10, higher = more important


@dataclass
class TaskNode:
    """Node in the task decomposition DAG."""

    task_id: str
    description: str
    capability: AgentCapability
    dependencies: list[str] = field(default_factory=list)  # task_ids this depends on
    estimated_complexity: float = 0.5  # 0.0-1.0
    can_parallelize: bool = True
    requires_hitl: bool = False  # Based on autonomy policy
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        description: str,
        capability: AgentCapability,
        dependencies: list[str] | None = None,
        complexity: float = 0.5,
    ) -> "TaskNode":
        """Factory method to create a TaskNode with generated ID."""
        return cls(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            description=description,
            capability=capability,
            dependencies=dependencies or [],
            estimated_complexity=complexity,
        )


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_id: str
    capability: AgentCapability
    success: bool
    output: Any
    execution_time_seconds: float
    tokens_used: int = 0
    children_results: list["AgentResult"] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedResult:
    """Aggregated results from all agents in the execution tree."""

    execution_id: str
    task_count: int
    successful_tasks: int
    failed_tasks: int
    total_execution_time: float
    total_tokens_used: int
    outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    agent_tree: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetaOrchestratorResult:
    """Final result from MetaOrchestrator execution."""

    execution_id: str
    status: str  # "completed", "awaiting_hitl", "failed"
    result: AggregatedResult | None = None
    hitl_required: bool = False
    hitl_request_id: str | None = None
    auto_approved: bool = False
    audit_logged: bool = False
    autonomy_level: AutonomyLevel | None = None
    execution_time_seconds: float = 0.0
    error: str | None = None


@dataclass
class AutonomyPolicy:
    """Organization-specific autonomy configuration."""

    organization_id: str
    default_level: AutonomyLevel = AutonomyLevel.CRITICAL_HITL

    # Override by severity
    severity_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)

    # Override by repository
    repository_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)

    # Override by operation type
    operation_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)

    # Guardrails (cannot be overridden)
    always_require_hitl: list[str] = field(
        default_factory=lambda: [
            "production_deployment",
            "credential_modification",
            "access_control_change",
            "database_migration",
            "infrastructure_change",
        ]
    )

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
        if severity.upper() in self.severity_overrides:
            return self.severity_overrides[severity.upper()]

        # Fall back to default
        return self.default_level

    @classmethod
    def from_preset(cls, preset_name: str) -> "AutonomyPolicy":
        """Create an AutonomyPolicy from a named preset."""
        presets = {
            "defense_contractor": cls(
                organization_id="defense",
                default_level=AutonomyLevel.FULL_HITL,
                severity_overrides={"LOW": AutonomyLevel.CRITICAL_HITL},
            ),
            "financial_services": cls(
                organization_id="financial",
                default_level=AutonomyLevel.FULL_HITL,
                severity_overrides={
                    "LOW": AutonomyLevel.AUDIT_ONLY,
                },
            ),
            "fintech_startup": cls(
                organization_id="fintech",
                default_level=AutonomyLevel.CRITICAL_HITL,
                severity_overrides={
                    "LOW": AutonomyLevel.AUDIT_ONLY,
                    "MEDIUM": AutonomyLevel.AUDIT_ONLY,
                },
            ),
            "enterprise_standard": cls(
                organization_id="enterprise",
                default_level=AutonomyLevel.CRITICAL_HITL,
                severity_overrides={
                    "LOW": AutonomyLevel.FULL_AUTONOMOUS,
                    "MEDIUM": AutonomyLevel.AUDIT_ONLY,
                },
            ),
            "internal_tools": cls(
                organization_id="internal",
                default_level=AutonomyLevel.FULL_AUTONOMOUS,
                operation_overrides={
                    "credential_modification": AutonomyLevel.FULL_HITL,
                    "production_deployment": AutonomyLevel.CRITICAL_HITL,
                },
            ),
            "fully_autonomous": cls(
                organization_id="autonomous",
                default_level=AutonomyLevel.FULL_AUTONOMOUS,
                # Guardrails still apply
            ),
        }

        if preset_name not in presets:
            raise ValueError(
                f"Unknown preset: {preset_name}. Available: {list(presets.keys())}"
            )

        return presets[preset_name]


# =============================================================================
# Exceptions
# =============================================================================


class MetaOrchestratorError(Exception):
    """Base exception for MetaOrchestrator errors."""


class SpawnNotAllowedError(MetaOrchestratorError):
    """Raised when agent spawning is not allowed."""


class UnknownAgentCapabilityError(MetaOrchestratorError):
    """Raised when an unknown agent capability is requested."""


class CyclicDependencyError(MetaOrchestratorError):
    """Raised when task DAG contains cycles."""


class MaxDepthExceededError(MetaOrchestratorError):
    """Raised when recursion depth limit is exceeded."""


class TaskDecompositionError(MetaOrchestratorError):
    """Raised when task decomposition fails."""


# =============================================================================
# Base Agent Classes
# =============================================================================


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(
        self,
        llm_client: Any = None,
        agent_id: str | None = None,
    ):
        self.llm = llm_client
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now()

    @abstractmethod
    async def execute(self, task: str, context: Any = None) -> AgentResult:
        """Execute the agent's primary task."""

    @property
    @abstractmethod
    def capability(self) -> AgentCapability:
        """Return the agent's capability."""


class SpawnableAgent(BaseAgent):
    """Base class for agents that can spawn sub-agents."""

    def __init__(
        self,
        llm_client: Any = None,
        agent_id: str | None = None,
        max_spawn_depth: int = 2,
        can_spawn: bool = True,
        registry: "AgentRegistry | None" = None,
    ):
        super().__init__(llm_client, agent_id)
        self.max_spawn_depth = max_spawn_depth
        self.can_spawn = can_spawn and max_spawn_depth > 0
        self.children: list[SpawnableAgent] = []
        self.registry = registry or AgentRegistry()

    async def spawn_child(self, spec: AgentSpec) -> BaseAgent:
        """Spawn a child agent for delegated work."""
        if not self.can_spawn:
            raise SpawnNotAllowedError(
                f"Agent {self.agent_id} has reached max spawn depth or spawning disabled"
            )

        child_spec = AgentSpec(
            capability=spec.capability,
            task_description=spec.task_description,
            context_requirements=spec.context_requirements,
            max_depth=self.max_spawn_depth - 1,  # Decrement depth
            can_spawn_children=self.max_spawn_depth > 1,
            timeout_seconds=spec.timeout_seconds,
            priority=spec.priority,
        )

        child = self.registry.spawn_agent(child_spec, self.llm)
        self.children.append(child)

        logger.info(
            f"Agent {self.agent_id} spawned child {child.agent_id} "
            f"(capability: {spec.capability.value}, depth: {child_spec.max_depth})"
        )

        return child

    async def delegate_task(
        self, task: str, capability: AgentCapability, context: Any = None
    ) -> AgentResult:
        """Delegate a sub-task to a dynamically spawned agent."""
        spec = AgentSpec(
            capability=capability,
            task_description=task,
            context_requirements=[],
        )
        child = await self.spawn_child(spec)
        return await child.execute(task, context)

    def get_spawn_tree(self) -> dict[str, Any]:
        """Get the tree of spawned agents."""
        return {
            "agent_id": self.agent_id,
            "capability": self.capability.value,
            "children": [child.get_spawn_tree() for child in self.children],
        }


# =============================================================================
# Agent Registry
# =============================================================================


class AgentRegistry:
    """Registry of available agent types for dynamic spawning."""

    def __init__(self) -> None:
        self._agent_factories: dict[AgentCapability, Callable] = {}
        self._register_default_agents()

    def _register_default_agents(self):
        """Register default agent factories."""
        # These will be overridden when real agents are registered
        for capability in AgentCapability:
            self._agent_factories[capability] = self._create_generic_agent_factory(
                capability
            )

    def _create_generic_agent_factory(
        self, capability: AgentCapability
    ) -> Callable[..., SpawnableAgent]:
        """Create a generic agent factory for a capability."""
        # Capture capability in closure
        cap = capability

        def factory(
            llm_client: Any = None,
            max_spawn_depth: int = 2,
            can_spawn: bool = True,
            registry: "AgentRegistry | None" = None,
        ) -> SpawnableAgent:
            # Create agent class dynamically with captured capability
            class GenericAgent(SpawnableAgent):
                _capability = cap

                @property
                def capability(self) -> AgentCapability:
                    return self._capability

                async def execute(self, task: str, context: Any = None) -> AgentResult:
                    start_time = datetime.now()

                    # Generic execution - subclasses should override
                    output = {
                        "task": task,
                        "capability": self.capability.value,
                        "status": "executed",
                        "message": f"Generic {self.capability.value} agent executed task",
                    }

                    # If LLM available, use it
                    if self.llm:
                        try:
                            response = await self.llm.generate(
                                prompt=f"Execute {self.capability.value} task: {task}",
                                operation=self.capability.value,
                            )
                            output["llm_response"] = response
                        except Exception as e:
                            logger.warning(f"LLM call failed: {e}")
                            output["llm_error"] = str(e)

                    execution_time = (datetime.now() - start_time).total_seconds()

                    return AgentResult(
                        agent_id=self.agent_id,
                        capability=self.capability,
                        success=True,
                        output=output,
                        execution_time_seconds=execution_time,
                        children_results=[],
                    )

            return GenericAgent(
                llm_client=llm_client,
                max_spawn_depth=max_spawn_depth,
                can_spawn=can_spawn,
                registry=registry,
            )

        return factory

    def register_agent(
        self,
        capability: AgentCapability,
        factory: Callable[..., SpawnableAgent],
    ) -> None:
        """Register an agent factory for a capability."""
        self._agent_factories[capability] = factory
        logger.debug(f"Registered agent factory for {capability.value}")

    def spawn_agent(
        self,
        spec: AgentSpec,
        llm_client: Any = None,
    ) -> SpawnableAgent:
        """Dynamically instantiate agent based on specification."""
        factory = self._agent_factories.get(spec.capability)

        if not factory:
            raise UnknownAgentCapabilityError(
                f"No agent registered for capability: {spec.capability}"
            )

        agent: SpawnableAgent = factory(
            llm_client=llm_client,
            max_spawn_depth=spec.max_depth,
            can_spawn=spec.can_spawn_children,
            registry=self,
        )

        logger.info(
            f"Spawned agent {agent.agent_id} with capability {spec.capability.value}"
        )

        return agent

    def get_available_capabilities(self) -> list[AgentCapability]:
        """Get list of available agent capabilities."""
        return list(self._agent_factories.keys())


# =============================================================================
# Task Decomposer
# =============================================================================


class TaskDecomposer:
    """LLM-powered task decomposition into agent-assignable sub-tasks."""

    DECOMPOSITION_PROMPT = """Analyze this security task and decompose it into sub-tasks.

Task: {task_description}
Context Summary: {context_summary}

Available Agent Capabilities:
{capabilities}

For each sub-task, provide:
1. description: What needs to be done (be specific)
2. capability: Which agent capability is needed (from the list above)
3. dependencies: List of sub-task numbers this depends on (e.g., [1, 2])
4. complexity: Estimated complexity 0.0-1.0 (>0.7 may need further decomposition)
5. can_parallelize: true if no dependencies on sibling tasks

Rules:
- Maximum 8 sub-tasks per decomposition
- Tasks with complexity >0.7 should be flagged for recursive decomposition
- Security-critical tasks must be clearly identified
- Order tasks logically based on dependencies
- Each task should be atomic and completable by a single agent

Output as a JSON array with this exact format:
[
  {{
    "description": "task description here",
    "capability": "capability_name",
    "dependencies": [],
    "complexity": 0.5,
    "can_parallelize": true
  }}
]

Return ONLY the JSON array, no other text."""

    MAX_RECURSION_DEPTH = 4  # Safety limit
    COMPLEXITY_THRESHOLD = 0.7  # Above this, consider further decomposition
    MAX_TASKS_PER_DECOMPOSITION = 8

    def __init__(self, llm_client: Any = None) -> None:
        self.llm = llm_client

    async def decompose(
        self,
        task: str,
        context: Any = None,
        depth: int = 0,
    ) -> list[TaskNode]:
        """Recursively decompose task into executable sub-tasks."""
        if depth >= self.MAX_RECURSION_DEPTH:
            logger.warning(f"Max recursion depth reached for task: {task[:50]}...")
            return [self._create_leaf_node(task)]

        # Get context summary
        context_summary = self._get_context_summary(context)

        # Format capabilities for prompt
        capabilities_str = "\n".join(
            f"- {cap.value}: {self._get_capability_description(cap)}"
            for cap in AgentCapability
        )

        # Generate decomposition via LLM
        if self.llm:
            try:
                prompt = self.DECOMPOSITION_PROMPT.format(
                    task_description=task,
                    context_summary=context_summary,
                    capabilities=capabilities_str,
                )

                response = await self.llm.generate(
                    prompt=prompt,
                    operation="task_decomposition",
                )

                nodes = self._parse_task_nodes(response)

            except Exception as e:
                logger.warning(f"LLM decomposition failed: {e}, using fallback")
                nodes = self._fallback_decomposition(task)
        else:
            # Fallback without LLM
            nodes = self._fallback_decomposition(task)

        # Recursively decompose complex sub-tasks
        final_nodes = []
        for node in nodes:
            if (
                node.estimated_complexity > self.COMPLEXITY_THRESHOLD
                and depth < self.MAX_RECURSION_DEPTH - 1
            ):
                logger.debug(
                    f"Recursively decomposing complex task: {node.description[:50]}..."
                )
                sub_nodes = await self.decompose(node.description, context, depth + 1)

                # Update dependencies for sub-nodes
                for sub_node in sub_nodes:
                    # Inherit parent dependencies
                    sub_node.dependencies.extend(node.dependencies)

                final_nodes.extend(sub_nodes)
            else:
                final_nodes.append(node)

        return final_nodes

    def _create_leaf_node(self, task: str) -> TaskNode:
        """Create a leaf node when max depth is reached."""
        # Guess capability based on task keywords
        capability = self._guess_capability(task)

        return TaskNode.create(
            description=task,
            capability=capability,
            complexity=0.5,  # Assume medium complexity
        )

    def _guess_capability(self, task: str) -> AgentCapability:
        """Guess the required capability based on task description."""
        task_lower = task.lower()

        keyword_map = {
            AgentCapability.CODE_GENERATION: [
                "generate",
                "create",
                "write",
                "implement",
            ],
            AgentCapability.SECURITY_REVIEW: [
                "review",
                "audit",
                "check security",
                "analyze security",
            ],
            AgentCapability.VULNERABILITY_SCAN: [
                "scan",
                "vulnerability",
                "cve",
                "exploit",
            ],
            AgentCapability.PATCH_VALIDATION: ["validate", "verify", "test patch"],
            AgentCapability.THREAT_ANALYSIS: ["threat", "risk", "attack"],
            AgentCapability.DEPENDENCY_AUDIT: ["dependency", "package", "library"],
            AgentCapability.COMPLIANCE_CHECK: ["compliance", "regulation", "policy"],
            AgentCapability.ARCHITECTURE_REVIEW: [
                "architecture",
                "design",
                "structure",
            ],
            AgentCapability.TEST_GENERATION: ["test", "coverage", "unit test"],
            AgentCapability.DOCUMENTATION: ["document", "readme", "comment"],
        }

        for capability, keywords in keyword_map.items():
            if any(kw in task_lower for kw in keywords):
                return capability

        # Default to code analysis
        return AgentCapability.CODE_ANALYSIS

    def _get_capability_description(self, capability: AgentCapability) -> str:
        """Get human-readable description of a capability."""
        descriptions = {
            AgentCapability.CODE_GENERATION: "Generate or modify source code",
            AgentCapability.SECURITY_REVIEW: "Review code for security issues",
            AgentCapability.VULNERABILITY_SCAN: "Scan for known vulnerabilities (CVEs)",
            AgentCapability.PATCH_VALIDATION: "Validate security patches work correctly",
            AgentCapability.THREAT_ANALYSIS: "Analyze potential threats and attack vectors",
            AgentCapability.DEPENDENCY_AUDIT: "Audit third-party dependencies",
            AgentCapability.COMPLIANCE_CHECK: "Check compliance with regulations",
            AgentCapability.ARCHITECTURE_REVIEW: "Review system architecture",
            AgentCapability.TEST_GENERATION: "Generate test cases",
            AgentCapability.DOCUMENTATION: "Generate or update documentation",
            AgentCapability.CONTEXT_RETRIEVAL: "Retrieve relevant code context",
            AgentCapability.CODE_ANALYSIS: "General code analysis",
        }
        return descriptions.get(capability, "Perform agent task")

    def _get_context_summary(self, context: Any) -> str:
        """Extract summary from context object."""
        if context is None:
            return "No additional context provided"

        if hasattr(context, "summary"):
            return cast(str, context.summary)

        if isinstance(context, dict):
            return str(context.get("summary", context))[:500]

        return str(context)[:500]

    def _parse_task_nodes(self, response: str) -> list[TaskNode]:
        """Parse LLM response into TaskNode objects."""
        import json

        try:
            # Try to extract JSON from response
            response = response.strip()

            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            tasks_data = json.loads(response)

            if not isinstance(tasks_data, list):
                raise ValueError("Expected JSON array")

            nodes = []
            task_ids = {}  # Map index to task_id for dependency resolution

            for i, task_data in enumerate(
                tasks_data[: self.MAX_TASKS_PER_DECOMPOSITION]
            ):
                # Parse capability
                cap_str = task_data.get("capability", "code_analysis")
                try:
                    capability = AgentCapability(cap_str)
                except ValueError:
                    capability = AgentCapability.CODE_ANALYSIS

                node = TaskNode.create(
                    description=task_data.get("description", f"Task {i + 1}"),
                    capability=capability,
                    complexity=float(task_data.get("complexity", 0.5)),
                )
                node.can_parallelize = task_data.get("can_parallelize", True)

                task_ids[i] = node.task_id
                nodes.append(node)

            # Resolve dependencies (convert indices to task_ids)
            for i, task_data in enumerate(tasks_data[: len(nodes)]):
                deps = task_data.get("dependencies", [])
                nodes[i].dependencies = [
                    task_ids[d] for d in deps if d in task_ids and d != i
                ]

            return nodes

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._fallback_decomposition(response)

    def _fallback_decomposition(self, task: str) -> list[TaskNode]:
        """Fallback decomposition when LLM is unavailable or fails."""
        # Simple rule-based decomposition
        nodes = []

        # Always start with context retrieval
        nodes.append(
            TaskNode.create(
                description=f"Retrieve relevant code context for: {task}",
                capability=AgentCapability.CONTEXT_RETRIEVAL,
                complexity=0.3,
            )
        )

        # Add main task
        main_capability = self._guess_capability(task)
        main_node = TaskNode.create(
            description=task,
            capability=main_capability,
            dependencies=[nodes[0].task_id],
            complexity=0.6,
        )
        nodes.append(main_node)

        # Add validation if it's a code change
        if main_capability in (
            AgentCapability.CODE_GENERATION,
            AgentCapability.SECURITY_REVIEW,
        ):
            nodes.append(
                TaskNode.create(
                    description=f"Validate changes from: {task}",
                    capability=AgentCapability.PATCH_VALIDATION,
                    dependencies=[main_node.task_id],
                    complexity=0.4,
                )
            )

        return nodes


# =============================================================================
# MetaOrchestrator
# =============================================================================


class MetaOrchestrator:
    """
    Advanced orchestrator with dynamic agent spawning and configurable autonomy.

    Capabilities:
    - Decomposes complex tasks into sub-task DAGs
    - Dynamically spawns specialized agents
    - Supports recursive problem-solving (depth-limited)
    - Applies organization-specific autonomy policies
    - Aggregates and validates results from agent tree

    Example:
        >>> policy = AutonomyPolicy.from_preset("fintech_startup")
        >>> orchestrator = MetaOrchestrator(
        ...     llm_client=bedrock_service,
        ...     autonomy_policy=policy,
        ...     context_service=context_retrieval_service,
        ... )
        >>> result = await orchestrator.execute(
        ...     task="Fix SQL injection in user authentication",
        ...     repository="https://github.com/org/app",
        ...     severity="HIGH"
        ... )
    """

    def __init__(
        self,
        llm_client: Any = None,
        autonomy_policy: AutonomyPolicy | None = None,
        context_service: Any = None,
        hitl_service: Any = None,
        notification_service: Any = None,
        max_spawn_depth: int = 3,
        max_parallel_agents: int = 10,
    ):
        self.llm = llm_client
        self.autonomy_policy = autonomy_policy or AutonomyPolicy.from_preset(
            "enterprise_standard"
        )
        self.context_service = context_service
        self.hitl_service = hitl_service
        self.notification_service = notification_service
        self.max_spawn_depth = max_spawn_depth
        self.max_parallel_agents = max_parallel_agents

        self.decomposer = TaskDecomposer(llm_client)
        self.registry = AgentRegistry()

        # Execution state
        self.active_agents: list[SpawnableAgent] = []
        self.results: dict[str, AgentResult] = {}
        self.audit_log: list[dict[str, Any]] = []

    async def execute(
        self,
        task: str,
        repository: str = "",
        severity: str = "MEDIUM",
        context: Any = None,
    ) -> MetaOrchestratorResult:
        """Execute a complex task with dynamic agent orchestration."""
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        logger.info(
            f"MetaOrchestrator starting execution {execution_id} "
            f"(severity: {severity}, repo: {repository})"
        )

        try:
            # Phase 1: Retrieve context (if service available)
            if self.context_service and context is None:
                try:
                    context = await self._get_context(task)
                except Exception as e:
                    logger.warning(f"Context retrieval failed: {e}")
                    context = None

            # Phase 2: Decompose task into sub-tasks
            logger.info(f"[{execution_id}] Decomposing task...")
            task_dag = await self.decomposer.decompose(task, context)
            logger.info(f"[{execution_id}] Decomposed into {len(task_dag)} sub-tasks")

            # Phase 3: Determine autonomy level
            operation = self._classify_operation(task)
            autonomy = self.autonomy_policy.get_autonomy_level(
                severity=severity,
                repository=repository,
                operation=operation,
            )
            logger.info(f"[{execution_id}] Autonomy level: {autonomy.value}")

            # Phase 4: Execute task DAG with dynamic agent spawning
            logger.info(f"[{execution_id}] Executing task DAG...")
            results = await self._execute_dag(task_dag, context, autonomy)

            # Phase 5: Aggregate results
            aggregated = self._aggregate_results(execution_id, task_dag, results)

            # Phase 6: Apply autonomy policy (HITL check if required)
            final_result = await self._apply_autonomy(
                aggregated,
                autonomy,
                severity,
                repository,
                execution_id,
            )

            final_result.execution_time_seconds = (
                datetime.now() - start_time
            ).total_seconds()

            logger.info(
                f"[{execution_id}] Execution completed in "
                f"{final_result.execution_time_seconds:.2f}s "
                f"(status: {final_result.status})"
            )

            return final_result

        except Exception as e:
            logger.error(f"[{execution_id}] MetaOrchestrator execution failed: {e}")
            return MetaOrchestratorResult(
                execution_id=execution_id,
                status="failed",
                error=str(e),
                execution_time_seconds=(datetime.now() - start_time).total_seconds(),
            )
        finally:
            # Cleanup spawned agents
            await self._cleanup_agents()

    async def _get_context(self, task: str) -> Any:
        """Retrieve context for the task."""
        if hasattr(self.context_service, "get_hybrid_context"):
            return await self.context_service.get_hybrid_context(task)
        elif hasattr(self.context_service, "retrieve"):
            return await self.context_service.retrieve(task)
        return None

    # Pre-built keyword -> operation mapping for O(k) single-pass classification
    _OPERATION_KEYWORDS: dict[str, str] = {
        "deploy": "production_deployment",
        "production": "production_deployment",
        "release": "production_deployment",
        "credential": "credential_modification",
        "password": "credential_modification",
        "secret": "credential_modification",
        "key": "credential_modification",
        "access": "access_control_change",
        "permission": "access_control_change",
        "role": "access_control_change",
        "iam": "access_control_change",
        "database": "database_migration",
        "migration": "database_migration",
        "schema": "database_migration",
        "infrastructure": "infrastructure_change",
        "terraform": "infrastructure_change",
        "cloudformation": "infrastructure_change",
        "patch": "security_patch",
        "fix": "security_patch",
        "vulnerability": "security_patch",
        "security": "security_patch",
    }

    def _classify_operation(self, task: str) -> str:
        """Classify the operation type from task description."""
        task_lower = task.lower()

        for keyword, operation in self._OPERATION_KEYWORDS.items():
            if keyword in task_lower:
                return operation

        return "general_operation"

    async def _execute_dag(
        self,
        dag: list[TaskNode],
        context: Any,
        autonomy: AutonomyLevel,
    ) -> dict[str, AgentResult]:
        """Execute task DAG with parallel and sequential phases using Kahn's algorithm."""
        from collections import deque

        results: dict[str, AgentResult] = {}
        nodes_by_id = {node.task_id: node for node in dag}

        # Build in-degree map and reverse dependency graph
        in_degree = {node.task_id: 0 for node in dag}
        reverse_deps: dict[str, list[str]] = {node.task_id: [] for node in dag}
        for node in dag:
            for dep in node.dependencies:
                if dep in nodes_by_id:
                    in_degree[node.task_id] += 1
                    reverse_deps[dep].append(node.task_id)

        # Initialize queue with zero-degree tasks
        ready = deque([tid for tid, deg in in_degree.items() if deg == 0])

        if not ready and dag:
            blocked_ids = list(nodes_by_id.keys())
            logger.error(f"Tasks blocked with unresolvable dependencies: {blocked_ids}")
            raise CyclicDependencyError(
                f"Task DAG contains cycles or unresolvable dependencies: {blocked_ids}"
            )

        while ready:
            # Drain all currently ready tasks into executable batch
            executable = [nodes_by_id[ready.popleft()] for _ in range(len(ready))]
            if not executable:
                break

            # Group parallelizable tasks
            parallel_batch = [n for n in executable if n.can_parallelize][
                : self.max_parallel_agents
            ]
            sequential = [n for n in executable if not n.can_parallelize]
            # Re-queue excess parallel tasks
            excess = [n for n in executable if n.can_parallelize][
                self.max_parallel_agents :
            ]
            for n in excess:
                ready.appendleft(n.task_id)

            # Execute parallel batch
            if parallel_batch:
                logger.debug(f"Executing {len(parallel_batch)} tasks in parallel")
                batch_results = await asyncio.gather(
                    *[
                        self._execute_task_node(node, context, results)
                        for node in parallel_batch
                    ],
                    return_exceptions=True,
                )

                for node, result in zip(parallel_batch, batch_results):
                    if isinstance(result, Exception):
                        results[node.task_id] = AgentResult(
                            agent_id="error",
                            capability=node.capability,
                            success=False,
                            output=None,
                            execution_time_seconds=0,
                            error=str(result),
                        )
                    else:
                        results[node.task_id] = cast(AgentResult, result)
                    # Update in-degrees for dependents
                    for dependent in reverse_deps.get(node.task_id, []):
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            ready.append(dependent)

            # Execute sequential tasks
            for node in sequential:
                try:
                    result = await self._execute_task_node(node, context, results)
                    results[node.task_id] = result
                except Exception as e:
                    results[node.task_id] = AgentResult(
                        agent_id="error",
                        capability=node.capability,
                        success=False,
                        output=None,
                        execution_time_seconds=0,
                        error=str(e),
                    )
                # Update in-degrees for dependents
                for dependent in reverse_deps.get(node.task_id, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        ready.append(dependent)

        # Check for unprocessed tasks (cycle detection)
        unprocessed = [tid for tid in nodes_by_id if tid not in results]
        if unprocessed:
            logger.error(f"Tasks blocked with unresolvable dependencies: {unprocessed}")
            raise CyclicDependencyError(
                f"Task DAG contains cycles or unresolvable dependencies: {unprocessed}"
            )

        return results

    async def _execute_task_node(
        self,
        node: TaskNode,
        context: Any,
        prior_results: dict[str, AgentResult],
    ) -> AgentResult:
        """Execute a single task node by spawning appropriate agent."""
        logger.debug(f"Executing task: {node.task_id} ({node.capability.value})")

        # Spawn agent for this task
        spec = AgentSpec(
            capability=node.capability,
            task_description=node.description,
            context_requirements=[],
            max_depth=self.max_spawn_depth,
        )

        agent = self.registry.spawn_agent(spec, self.llm)
        self.active_agents.append(agent)

        # Inject prior results as enriched context
        enriched_context = self._enrich_context(
            context, prior_results, node.dependencies
        )

        # Execute agent
        result = await agent.execute(node.description, enriched_context)

        # Collect children results if agent spawned sub-agents
        if isinstance(agent, SpawnableAgent) and agent.children:
            result.children_results = [
                AgentResult(
                    agent_id=child.agent_id,
                    capability=child.capability,
                    success=True,
                    output=None,
                    execution_time_seconds=0,
                )
                for child in agent.children
            ]

        return result

    def _enrich_context(
        self,
        context: Any,
        prior_results: dict[str, AgentResult],
        dependencies: list[str],
    ) -> dict[str, Any]:
        """Enrich context with results from dependency tasks."""
        enriched = {
            "original_context": context,
            "dependency_results": {},
        }

        for dep_id in dependencies:
            if dep_id in prior_results:
                enriched["dependency_results"][dep_id] = {
                    "success": prior_results[dep_id].success,
                    "output": prior_results[dep_id].output,
                }

        return enriched

    def _aggregate_results(
        self,
        execution_id: str,
        task_dag: list[TaskNode],
        results: dict[str, AgentResult],
    ) -> AggregatedResult:
        """Aggregate results from all agents."""
        successful = sum(1 for r in results.values() if r.success)
        failed = sum(1 for r in results.values() if not r.success)
        total_time = sum(r.execution_time_seconds for r in results.values())
        total_tokens = sum(r.tokens_used for r in results.values())

        outputs = {}
        errors = []

        for task_id, result in results.items():
            outputs[task_id] = result.output
            if result.error:
                errors.append(f"{task_id}: {result.error}")

        # Build agent tree
        agent_tree = {
            "root": "meta_orchestrator",
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "capability": agent.capability.value,
                    "children": (
                        agent.get_spawn_tree()["children"]
                        if isinstance(agent, SpawnableAgent)
                        else []
                    ),
                }
                for agent in self.active_agents
            ],
        }

        return AggregatedResult(
            execution_id=execution_id,
            task_count=len(task_dag),
            successful_tasks=successful,
            failed_tasks=failed,
            total_execution_time=total_time,
            total_tokens_used=total_tokens,
            outputs=outputs,
            errors=errors,
            agent_tree=agent_tree,
        )

    async def _apply_autonomy(
        self,
        result: AggregatedResult,
        autonomy: AutonomyLevel,
        severity: str,
        repository: str,
        execution_id: str,
    ) -> MetaOrchestratorResult:
        """Apply autonomy policy to determine if HITL is needed."""

        if autonomy == AutonomyLevel.FULL_AUTONOMOUS:
            # Auto-approve, minimal logging
            logger.info(f"[{execution_id}] Auto-approved (FULL_AUTONOMOUS)")
            return MetaOrchestratorResult(
                execution_id=execution_id,
                status="completed",
                result=result,
                hitl_required=False,
                auto_approved=True,
                autonomy_level=autonomy,
            )

        elif autonomy == AutonomyLevel.AUDIT_ONLY:
            # Auto-approve, full audit logging
            await self._log_audit_trail(result, repository, severity, execution_id)
            logger.info(f"[{execution_id}] Auto-approved with audit (AUDIT_ONLY)")
            return MetaOrchestratorResult(
                execution_id=execution_id,
                status="completed",
                result=result,
                hitl_required=False,
                auto_approved=True,
                audit_logged=True,
                autonomy_level=autonomy,
            )

        elif autonomy == AutonomyLevel.CRITICAL_HITL:
            # Only require HITL for HIGH/CRITICAL
            if severity.upper() in ("HIGH", "CRITICAL"):
                logger.info(
                    f"[{execution_id}] HITL required (CRITICAL_HITL, severity={severity})"
                )
                return await self._request_hitl_approval(
                    result, severity, repository, execution_id
                )
            else:
                await self._log_audit_trail(result, repository, severity, execution_id)
                logger.info(
                    f"[{execution_id}] Auto-approved (CRITICAL_HITL, severity={severity})"
                )
                return MetaOrchestratorResult(
                    execution_id=execution_id,
                    status="completed",
                    result=result,
                    hitl_required=False,
                    auto_approved=True,
                    audit_logged=True,
                    autonomy_level=autonomy,
                )

        else:  # FULL_HITL
            # Always require HITL approval
            logger.info(f"[{execution_id}] HITL required (FULL_HITL)")
            return await self._request_hitl_approval(
                result, severity, repository, execution_id
            )

    async def _request_hitl_approval(
        self,
        result: AggregatedResult,
        severity: str,
        repository: str,
        execution_id: str,
    ) -> MetaOrchestratorResult:
        """Request HITL approval for the execution result."""
        hitl_request_id = None

        if self.hitl_service:
            try:
                # Create approval request
                request = await self.hitl_service.create_approval_request(
                    patch_id=execution_id,
                    vulnerability_id=f"meta-{execution_id}",
                    severity=severity,
                    metadata={
                        "repository": repository,
                        "task_count": result.task_count,
                        "successful_tasks": result.successful_tasks,
                        "outputs": result.outputs,
                    },
                )
                hitl_request_id = request.approval_id

                # Send notification if service available
                if self.notification_service:
                    await self.notification_service.send_approval_notification(
                        approval_id=hitl_request_id,
                        patch_id=execution_id,
                        vulnerability_id=f"meta-{execution_id}",
                        severity=severity,
                        created_at=datetime.now().isoformat(),
                        expires_at="",
                        sandbox_results={},
                        patch_diff="",
                        recipients=[],
                    )

            except Exception as e:
                logger.error(f"Failed to create HITL request: {e}")

        return MetaOrchestratorResult(
            execution_id=execution_id,
            status="awaiting_hitl",
            result=result,
            hitl_required=True,
            hitl_request_id=hitl_request_id,
            auto_approved=False,
            autonomy_level=AutonomyLevel.FULL_HITL,
        )

    async def _log_audit_trail(
        self,
        result: AggregatedResult,
        repository: str,
        severity: str,
        execution_id: str,
    ) -> None:
        """Log audit trail for autonomous execution."""
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": execution_id,
            "repository": repository,
            "severity": severity,
            "task_count": result.task_count,
            "successful_tasks": result.successful_tasks,
            "failed_tasks": result.failed_tasks,
            "total_execution_time": result.total_execution_time,
            "agent_tree": result.agent_tree,
        }

        self.audit_log.append(audit_entry)
        logger.info(f"Audit logged for execution {execution_id}")

    async def _cleanup_agents(self) -> None:
        """Cleanup spawned agents."""
        agent_count = len(self.active_agents)
        self.active_agents.clear()
        self.results.clear()
        logger.debug(f"Cleaned up {agent_count} agents")

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get the audit log for this orchestrator."""
        return self.audit_log.copy()


# =============================================================================
# Factory Functions
# =============================================================================


def create_meta_orchestrator(
    llm_client: Any = None,
    autonomy_preset: str = "enterprise_standard",
    context_service: Any = None,
    hitl_service: Any = None,
    notification_service: Any = None,
    max_spawn_depth: int = 3,
    max_parallel_agents: int = 10,
) -> MetaOrchestrator:
    """
    Create a MetaOrchestrator with the specified configuration.

    Args:
        llm_client: LLM service for agent operations
        autonomy_preset: Name of autonomy preset to use
        context_service: Service for context retrieval
        hitl_service: Service for HITL approval workflow
        notification_service: Service for notifications
        max_spawn_depth: Maximum agent spawning depth
        max_parallel_agents: Maximum concurrent agents

    Returns:
        Configured MetaOrchestrator instance
    """
    policy = AutonomyPolicy.from_preset(autonomy_preset)

    return MetaOrchestrator(
        llm_client=llm_client,
        autonomy_policy=policy,
        context_service=context_service,
        hitl_service=hitl_service,
        notification_service=notification_service,
        max_spawn_depth=max_spawn_depth,
        max_parallel_agents=max_parallel_agents,
    )


# =============================================================================
# Demo / Test
# =============================================================================


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def demo():
        print("=" * 60)
        print("Project Aura - MetaOrchestrator Demo")
        print("=" * 60)

        # Create orchestrator with enterprise policy
        orchestrator = create_meta_orchestrator(
            autonomy_preset="enterprise_standard",
        )

        print(f"\nAutonomy Policy: {orchestrator.autonomy_policy.organization_id}")
        print(f"Default Level: {orchestrator.autonomy_policy.default_level.value}")
        print(f"Max Spawn Depth: {orchestrator.max_spawn_depth}")

        # Test task decomposition
        print("\n--- Testing Task Decomposition ---")
        decomposer = TaskDecomposer()
        task = "Analyze SQL injection vulnerabilities and generate security patches"
        nodes = await decomposer.decompose(task)

        print(f"Task: {task}")
        print(f"Decomposed into {len(nodes)} sub-tasks:")
        for node in nodes:
            print(f"  - [{node.capability.value}] {node.description[:60]}...")

        # Test autonomy levels
        print("\n--- Testing Autonomy Levels ---")
        test_cases = [
            ("CRITICAL", "https://github.com/org/app", "security_patch"),
            ("LOW", "https://github.com/org/app", "security_patch"),
            ("MEDIUM", "https://github.com/org/app", "production_deployment"),
        ]

        for severity, repo, operation in test_cases:
            level = orchestrator.autonomy_policy.get_autonomy_level(
                severity, repo, operation
            )
            print(f"  {severity} / {operation}: {level.value}")

        # Test execution (without real LLM)
        print("\n--- Testing Execution (Mock) ---")
        result = await orchestrator.execute(
            task="Fix XSS vulnerability in user input handling",
            repository="https://github.com/org/app",
            severity="MEDIUM",
        )

        print(f"Execution ID: {result.execution_id}")
        print(f"Status: {result.status}")
        print(f"HITL Required: {result.hitl_required}")
        print(f"Auto Approved: {result.auto_approved}")
        print(f"Execution Time: {result.execution_time_seconds:.2f}s")

        if result.result:
            print(f"Tasks Executed: {result.result.task_count}")
            print(f"Successful: {result.result.successful_tasks}")

        print("\n" + "=" * 60)
        print("Demo complete!")

    asyncio.run(demo())
