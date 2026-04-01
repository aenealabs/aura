"""System 2 AI Orchestrator Simulation (V7 - Agent Integration)
=================================================================

Orchestrates the multi-agent workflow for autonomous code remediation.
Uses extracted agent classes (CoderAgent, ReviewerAgent, ValidatorAgent)
for better modularity and testability.

Includes checkpoint/resume support for long-running workflows.
"""

import ast
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config.paths import get_sample_project_path

from .coder_agent import CoderAgent
from .context_objects import ContextSource, HybridContext
from .monitoring_service import AgentRole, MonitorAgent
from .reviewer_agent import ReviewerAgent
from .validator_agent import ValidatorAgent


class WorkflowPhase(Enum):
    """Phases of the agent workflow for checkpointing."""

    INIT = "init"
    PLANNING = "planning"
    MEMORY_LOAD = "memory_load"
    CONTEXT_RETRIEVAL = "context_retrieval"
    CODE_GENERATION = "code_generation"
    SECURITY_REVIEW = "security_review"
    VALIDATION = "validation"
    REMEDIATION = "remediation"
    MEMORY_STORE = "memory_store"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentCheckpoint:
    """
    Checkpoint for resumable agent workflows.

    Captures the complete state of a workflow at a specific phase,
    enabling recovery from failures or interruptions.

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint
        workflow_id: Identifier for the parent workflow
        phase: Current workflow phase
        user_prompt: Original user request
        tasks: Planner output (target_entity, task_description)
        hybrid_context_data: Serialized HybridContext
        generated_code: Code output from coder agent
        review_result: Security review output
        validation_result: Validation output
        attempt_number: Current remediation attempt
        max_attempts: Maximum remediation attempts
        created_at: Checkpoint creation timestamp
        metadata: Additional workflow metadata
    """

    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    phase: WorkflowPhase = WorkflowPhase.INIT
    user_prompt: str = ""
    tasks: dict[str, str] = field(default_factory=dict)
    hybrid_context_data: dict[str, Any] = field(default_factory=dict)
    generated_code: str = ""
    review_result: dict[str, Any] = field(default_factory=dict)
    validation_result: dict[str, Any] = field(default_factory=dict)
    attempt_number: int = 1
    max_attempts: int = 2
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert checkpoint to dictionary for serialization."""
        data = asdict(self)
        data["phase"] = self.phase.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCheckpoint":
        """Create checkpoint from dictionary."""
        data["phase"] = WorkflowPhase(data["phase"])
        return cls(**data)


if TYPE_CHECKING:
    from src.services.a2as_security_service import A2ASSecurityService
    from src.services.agent_queue_service import AgentQueueService
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.checkpoint_persistence_service import CheckpointPersistenceService
    from src.services.hitl_approval_service import HITLApprovalService
    from src.services.mcp_gateway_client import MCPGatewayClient
    from src.services.mcp_tool_server import MCPToolServer
    from src.services.notification_service import NotificationService
    from src.services.titan_cognitive_integration import TitanCognitiveService

logger = logging.getLogger(__name__)

# Constants
SIMILARITY_THRESHOLD = 50  # Minimum similarity score threshold

"""--- Configuration & Utility Setup ---
Simulate reading environment variables (Secure practice for CMMC/SOX)
In a real environment, these would be loaded from AWS Secrets Manager
"""

LLM_API_KEY = os.environ.get("LLM_API_KEY", "mock-llm-key-123")
NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "mock.neptune.aws")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "mock.opensearch.aws")


# FIX: Corrected indentation for the class and its method.
class InputSanitizer:
    """
    HIGH-Severity Security Patch: Prevents Graph Injection and SQL Injection
    by escaping critical characters used in Gremlin, OpenCypher, and SQL.
    This protects the Neptune and OpenSearch data stores.
    """

    @staticmethod
    def sanitize_for_graph_id(text: str) -> str:
        """
        Escapes characters critical to graph query languages.

        FIX: Properly escape quotes and special characters for graph database safety.
        """
        if not text:
            return "empty"

        # FIX: For security, we REMOVE quotes entirely rather than escaping
        # This prevents ANY possibility of injection attacks
        text = text.replace(
            "\\", "\\\\"
        )  # Backslash → double backslash (preserve but escape)
        text = text.replace('"', "")  # FIX: Remove double quotes entirely for security
        text = text.replace("'", "")  # FIX: Remove single quotes entirely for security

        # Escape Gremlin/OpenCypher specific characters
        text = text.replace(":", "_colon")
        text = text.replace(".", "_dot_")  # FIX: Add trailing underscore for clarity

        # Remove dangerous characters that can't be safely escaped
        text = text.replace("(", "")
        text = text.replace(")", "")

        return text.strip()[:255]


# FIX: Corrected indentation for the class and its methods.
class GraphBuilderAgent:
    """
    Simulates the structural storage layer (Amazon Neptune) and AST parsing.
    Stores code entities as Nodes and relationships as Edges.
    """

    # FIX: Corrected method definition from 'init' to '__init__'.
    def __init__(self) -> None:
        self.ckge_graph: dict[str, dict[str, Any]] = {}

    def parse_source_code(
        self, _code_content: str, filename: str | Path
    ) -> dict[str, Any]:
        """Simulates AST parsing and structural data extraction.

        Args:
            _code_content: Source code content (unused in mock mode)
            filename: Name of file being parsed
        """
        filename_str = str(filename)
        print(
            f"[{AgentRole.PLANNER.value}] Parsing code structure for {filename_str}..."
        )

        parsed_data = {
            "file": filename_str,
            # FIX: Aligned mock parsing with the actual mock file content.
            # The 'process_data' method does not exist in the test's MOCK_CODE_CONTENT.
            "classes": [
                {"name": "DataProcessor", "methods": ["calculate_checksum"]},
                {"name": "ResultStore", "methods": ["save_data"]},
            ],
            # FIX: Removed phantom dependency. The mock 'calculate_checksum' does not call 'save_data'.
            "dependencies": [
                {"source": "DataProcessor", "target": "hashlib", "type": "imports"}
            ],
        }

        self._build_graph(parsed_data)
        return parsed_data

    def _build_graph(self, parsed_data: dict[str, Any]):
        """Builds the in-memory graph structure for retrieval."""
        filename = parsed_data["file"]
        self.add_node(InputSanitizer.sanitize_for_graph_id(filename), "FILE")

        for cls in parsed_data["classes"]:
            cls_id = InputSanitizer.sanitize_for_graph_id(cls["name"])
            self.add_node(cls_id, "CLASS", file=filename)
            self.add_edge(
                InputSanitizer.sanitize_for_graph_id(filename), cls_id, "CONTAINS"
            )

            for method_name in cls["methods"]:
                method_id = InputSanitizer.sanitize_for_graph_id(
                    f"{cls['name']}.{method_name}"
                )
                self.add_node(method_id, "METHOD", class_name=cls["name"])
                self.add_edge(cls_id, method_id, "CONTAINS")

        print(
            f"[{AgentRole.PLANNER.value}] Graph built successfully with {len(self.ckge_graph)} entities."
        )

    def add_node(self, node_id: str, label: str, **_properties):
        """Adds a node to the mock graph.

        Args:
            node_id: Unique identifier for the node
            label: Node type label
            _properties: Additional properties (stored but unused in mock)
        """
        if node_id not in self.ckge_graph:
            self.ckge_graph[node_id] = {
                "label": label,
                "properties": _properties,
                "edges": {},
            }

    def add_edge(self, source_id: str, target_id: str, type: str, **_properties):
        """Adds an edge to the mock graph."""
        # Note: properties parameter reserved for future edge metadata storage
        if source_id in self.ckge_graph and target_id in self.ckge_graph:
            self.ckge_graph[source_id]["edges"].setdefault(type, []).append(target_id)

    def run_gremlin_query(self, source_entity: str) -> list[str]:
        """Simulates a structural (Gremlin) query on the graph."""
        sanitized_entity = InputSanitizer.sanitize_for_graph_id(source_entity)
        if sanitized_entity in self.ckge_graph:
            edges = self.ckge_graph[sanitized_entity]["edges"]
            dependencies = [
                f"Dependency: {t} via {e}"
                for e, targets in edges.items()
                for t in targets
            ]
            return [
                f"Structural Context (Graph): {sanitized_entity} must integrate with: {', '.join(dependencies)}"
            ]
        return [
            f"Structural Context (Graph): No direct dependencies found for {source_entity}."
        ]


# FIX: Corrected indentation for the class and its methods.
class OpenSearchVectorStore:
    """
    Simulates the semantic storage layer (OpenSearch Vector Store) and k-NN index.
    """

    # FIX: Corrected method definition from 'init' to '__init__'.
    def __init__(self) -> None:
        self.vector_store_index: dict[str, str] = {
            "crypto_policy_101_vector": "Security Policy: All new code must use SHA256 or SHA3-512. SHA1 is prohibited by SOX/CMMC standards.",
            "data_processor_doc_vector": "DataProcessor class handles data pre-processing and checksum generation before saving.",
        }

    def run_knn_search(self, query: str) -> list[str]:
        """Simulates a semantic (k-NN) search."""
        print(
            f"[{AgentRole.CONTEXT.value}] Searching Vector Store for relevant policies: '{query}'"
        )
        if "checksum" in query or "hash" in query:
            return [self.vector_store_index["crypto_policy_101_vector"]]
        return [self.vector_store_index["data_processor_doc_vector"]]


# FIX: Corrected indentation for the class and its method.
class EmbeddingAgent:
    """
    Simulates the ingestion agent for chunking and vectorizing content.
    """

    @staticmethod
    def chunk_and_embed(content: str, source_type: str) -> bool:
        """Simulates AST-aware chunking and vectorization."""
        if not content or len(content) < SIMILARITY_THRESHOLD:
            print(
                f"[{AgentRole.EMBEDDING.value}] ERROR: Content too short for embedding."
            )
            return False
        print(
            f"[{AgentRole.EMBEDDING.value}] Successfully chunked and indexed {source_type} content."
        )
        return True


# FIX: Corrected indentation for the class and its methods.
class ContextRetrievalService:
    """The Hybrid RAG orchestrator."""

    # FIX: Corrected method definition from 'init' to '__init__'.
    def __init__(
        self, graph_agent: GraphBuilderAgent, vector_store: OpenSearchVectorStore
    ):
        self.graph = graph_agent
        self.vectors = vector_store

    def get_hybrid_context(
        self, target_entity: str, user_query: str, session_id: str | None = None
    ) -> HybridContext:
        """
        Performs structural (Graph) and semantic (Vector) search fusion.

        Returns a HybridContext object with structured, traceable context items.
        """
        # Create the hybrid context container
        context = HybridContext(
            items=[],
            query=user_query,
            target_entity=target_entity,
            session_id=session_id,
        )

        # Add structural context from graph
        structural_results = self.graph.run_gremlin_query(target_entity)
        for result in structural_results:
            context.add_item(
                content=result,
                source=ContextSource.GRAPH_STRUCTURAL,
                confidence=0.95,
                entity_id=target_entity,
            )

        # Add semantic context from vector store
        semantic_results = self.vectors.run_knn_search(user_query)
        for result in semantic_results:
            # Determine if this is a security policy based on content
            source = (
                ContextSource.SECURITY_POLICY
                if "Security Policy" in result
                else ContextSource.VECTOR_SEMANTIC
            )
            context.add_item(content=result, source=source, confidence=0.90)

        return context


# FIX: Corrected indentation for the class and its methods.
class System2Orchestrator:
    """The main control plane for the multi-agent workflow.

    Orchestrates CoderAgent, ReviewerAgent, and ValidatorAgent to perform
    autonomous code remediation with security policy enforcement.

    Attributes:
        llm: Bedrock LLM service for agent operations.
        monitor: MonitorAgent for metrics tracking.
        coder_agent: CoderAgent for code generation.
        reviewer_agent: ReviewerAgent for security review.
        validator_agent: ValidatorAgent for code validation.
        graph_agent: GraphBuilderAgent for structural context.
        vector_store: OpenSearchVectorStore for semantic context.
        context_service: ContextRetrievalService for hybrid retrieval.
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        hitl_approval_service: "HITLApprovalService | None" = None,
        notification_service: "NotificationService | None" = None,
        mcp_server: "MCPToolServer | None" = None,
        mcp_client: "MCPGatewayClient | None" = None,
        titan_memory: "TitanCognitiveService | None" = None,
        enable_reflection: bool = True,
        a2as_service: "A2ASSecurityService | None" = None,
        queue_service: "AgentQueueService | None" = None,
        use_async_messaging: bool = False,
        checkpoint_service: "CheckpointPersistenceService | None" = None,
    ):
        """Initialize the System2Orchestrator.

        Args:
            llm_client: Optional Bedrock LLM service. If None, agents use fallback mode.
            hitl_approval_service: Optional HITL approval service for approval workflow.
            notification_service: Optional notification service for alerts.
            mcp_server: Optional MCP tool server for internal tools (Neptune, OpenSearch).
            mcp_client: Optional MCP gateway client for external tools (Slack, Jira).
            titan_memory: Optional Titan cognitive service for neural memory (ADR-029 Phase 2.1).
            enable_reflection: Enable self-reflection for ReviewerAgent (ADR-029 Phase 2.2).
            a2as_service: Optional A2AS security service for input validation (ADR-029 Phase 2.3).
            queue_service: Optional agent queue service for async messaging (Issue #19).
            use_async_messaging: Enable async dispatch via SQS queues (Issue #19).
            checkpoint_service: Optional checkpoint persistence service for DynamoDB storage.
        """
        self.llm = llm_client
        self.checkpoint_service = checkpoint_service
        self.monitor = MonitorAgent()

        # MCP tool integration (ADR-029 Phase 1.4)
        self.mcp_server = mcp_server
        self.mcp_client = mcp_client

        # Titan Memory integration (ADR-029 Phase 2.1)
        self.titan_memory = titan_memory

        # A2AS Security integration (ADR-029 Phase 2.3)
        self.a2as_service = a2as_service

        # Async messaging integration (Issue #19 - Microservices Messaging)
        self.queue_service = queue_service
        self.use_async_messaging = use_async_messaging

        # Initialize extracted agent classes
        self.coder_agent = CoderAgent(llm_client=llm_client, monitor=self.monitor)
        self.reviewer_agent = ReviewerAgent(
            llm_client=llm_client,
            monitor=self.monitor,
            enable_reflection=enable_reflection,
        )
        self.validator_agent = ValidatorAgent(
            llm_client=llm_client, monitor=self.monitor
        )

        # HITL services (optional - enables approval workflow)
        self.hitl_approval_service = hitl_approval_service
        self.notification_service = notification_service

        # Initialize context retrieval components using factory pattern
        # Auto-detects real vs mock based on environment variables:
        #   - NEPTUNE_ENDPOINT: If set, uses real Neptune adapter
        #   - OPENSEARCH_ENDPOINT: If set, uses real OpenSearch adapter
        #   - USE_MOCK_SERVICES=true: Forces mock mode even if endpoints are set
        from src.services.service_adapters import (
            create_graph_agent,
            create_vector_store,
        )

        self.graph_agent = create_graph_agent()
        self.vector_store = create_vector_store()
        self.context_service = ContextRetrievalService(  # type: ignore[call-arg]
            self.graph_agent, self.vector_store  # type: ignore[arg-type]
        )

        self.initial_code = ""
        self.final_code = ""
        self.initialize_ckge_data()

        # Log MCP status
        mcp_status = []
        if self.mcp_server:
            mcp_status.append(f"internal tools: {len(self.mcp_server.list_tools())}")
        if self.mcp_client:
            mcp_status.append("external gateway: connected")
        mcp_info = f" MCP: {', '.join(mcp_status)}" if mcp_status else ""

        # Log Titan Memory status (ADR-029 Phase 2.1)
        titan_info = " TitanMemory: enabled" if self.titan_memory else ""

        # Log reflection status (ADR-029 Phase 2.2)
        reflection_info = " Reflection: enabled" if enable_reflection else ""

        # Log A2AS status (ADR-029 Phase 2.3)
        a2as_info = " A2AS: enabled" if self.a2as_service else ""

        # Log async messaging status (Issue #19)
        async_info = " AsyncMessaging: enabled" if self.use_async_messaging else ""

        logger.info(
            f"Initialized System2Orchestrator with agent classes.{mcp_info}{titan_info}{reflection_info}{a2as_info}{async_info}"
        )

    def initialize_ckge_data(self):
        """
        Simulates initial ingestion of existing codebase and docs.

        PERFORMANCE FIX: Eliminated redundant file I/O (write-then-read pattern).
        Now reads from disk if exists, otherwise uses in-memory data directly.
        """
        print("\n--- Initializing CKGE Data Stores (Neptune & OpenSearch) ---")

        # Get the sample project path from configuration
        # Supports local dev, CI/CD, and container deployments
        mock_project = get_sample_project_path()
        code_path = mock_project / "main.py"
        mock_project.mkdir(parents=True, exist_ok=True)

        # FIX: Use the same mock code as the test suite to ensure consistency.
        # This prevents race conditions where the test setup and orchestrator create different files.
        mock_code_content = "import hashlib\n\nclass DataProcessor:\n    def calculate_checksum(self, data):\n        # VULNERABILITY: Insecure hash function used\n        return hashlib.sha1(data.encode()).hexdigest()\n\nclass ResultStore:\n    def save_data(self, checksum, result):\n        pass\n"

        # PERFORMANCE FIX: Avoid redundant disk I/O
        # Old pattern: write to disk, then immediately read back
        # New pattern: read from disk if exists, else use in-memory data
        if code_path.exists():
            # File exists - read from disk
            self.initial_code = code_path.read_text()
        else:
            # File doesn't exist - use in-memory data and persist
            self.initial_code = mock_code_content
            code_path.write_text(mock_code_content)

        self.graph_agent.parse_source_code(self.initial_code, code_path)

        doc_content = "Enterprise Security Policy: Use only FIPS-compliant algorithms. SHA1 is unauthorized."
        EmbeddingAgent.chunk_and_embed(doc_content, "Compliance Policy Doc")

    # =========================================================================
    # Checkpoint/Resume Methods for Long-Running Workflows
    # =========================================================================

    def save_checkpoint(
        self,
        checkpoint: AgentCheckpoint,
        storage_path: str | Path | None = None,
    ) -> str:
        """
        Save workflow checkpoint for resumption after failures.

        Uses DynamoDB when checkpoint_service is configured (production).
        Falls back to local filesystem for development/testing.

        Args:
            checkpoint: AgentCheckpoint containing workflow state
            storage_path: Optional path for filesystem storage (fallback only)

        Returns:
            Checkpoint ID (DynamoDB) or path where checkpoint was saved (filesystem)
        """
        checkpoint_data = checkpoint.to_dict()

        # Use DynamoDB persistence when available (production)
        if self.checkpoint_service is not None:
            try:
                checkpoint_id = self.checkpoint_service.save_checkpoint(checkpoint_data)
                logger.info(
                    f"Saved checkpoint {checkpoint.checkpoint_id} "
                    f"at phase {checkpoint.phase.value} to DynamoDB"
                )
                return checkpoint_id
            except Exception as e:
                logger.warning(f"DynamoDB save failed, falling back to filesystem: {e}")

        # Fallback to filesystem (development/testing)
        if storage_path is None:
            storage_dir = Path("/tmp/aura/checkpoints")  # nosec B108 - dev fallback
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_path = storage_dir / f"{checkpoint.checkpoint_id}.json"
        else:
            storage_path = Path(storage_path)

        with open(storage_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info(
            f"Saved checkpoint {checkpoint.checkpoint_id} "
            f"at phase {checkpoint.phase.value} to {storage_path}"
        )
        return str(storage_path)

    def load_checkpoint(
        self,
        checkpoint_id: str | None = None,
        storage_path: str | Path | None = None,
    ) -> AgentCheckpoint | None:
        """
        Load a workflow checkpoint for resumption.

        Uses DynamoDB when checkpoint_service is configured (production).
        Falls back to local filesystem for development/testing.

        Args:
            checkpoint_id: Checkpoint ID to load
            storage_path: Explicit path to checkpoint file (filesystem fallback)

        Returns:
            AgentCheckpoint if found, None otherwise
        """
        if checkpoint_id is None and storage_path is None:
            logger.error("Must provide checkpoint_id or storage_path")
            return None

        # Use DynamoDB persistence when available (production)
        if self.checkpoint_service is not None and checkpoint_id is not None:
            try:
                data = self.checkpoint_service.load_checkpoint(checkpoint_id)
                if data is not None:
                    checkpoint = AgentCheckpoint.from_dict(data)
                    logger.info(
                        f"Loaded checkpoint {checkpoint.checkpoint_id} "
                        f"at phase {checkpoint.phase.value} from DynamoDB"
                    )
                    return checkpoint
                logger.warning(f"Checkpoint not found in DynamoDB: {checkpoint_id}")
            except Exception as e:
                logger.warning(f"DynamoDB load failed, falling back to filesystem: {e}")

        # Fallback to filesystem (development/testing)
        if storage_path is not None:
            path = Path(storage_path)
        elif checkpoint_id is not None:
            path = Path(f"/tmp/aura/checkpoints/{checkpoint_id}.json")  # nosec B108
        else:
            return None

        if not path.exists():
            logger.warning(f"Checkpoint not found: {path}")
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            checkpoint = AgentCheckpoint.from_dict(data)
            logger.info(
                f"Loaded checkpoint {checkpoint.checkpoint_id} "
                f"at phase {checkpoint.phase.value}"
            )
            return checkpoint
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def _create_checkpoint(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        user_prompt: str,
        tasks: dict[str, str] | None = None,
        hybrid_context: HybridContext | None = None,
        generated_code: str = "",
        review_result: dict[str, Any] | None = None,
        validation_result: dict[str, Any] | None = None,
        attempt_number: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> AgentCheckpoint:
        """
        Create a checkpoint from current workflow state.

        Args:
            workflow_id: Parent workflow identifier
            phase: Current workflow phase
            user_prompt: Original user request
            tasks: Planner output
            hybrid_context: Current context (will be serialized)
            generated_code: Code from coder agent
            review_result: Security review output
            validation_result: Validation output
            attempt_number: Current remediation attempt
            metadata: Additional metadata

        Returns:
            AgentCheckpoint capturing current state
        """
        # Serialize HybridContext
        context_data: dict[str, Any] = {}
        if hybrid_context:
            context_data = {
                "items": [
                    {
                        "content": item.content,
                        "source": item.source.value,
                        "confidence": item.confidence,
                        "entity_id": item.entity_id,
                    }
                    for item in hybrid_context.items
                ],
                "query": hybrid_context.query,
                "target_entity": hybrid_context.target_entity,
                "session_id": hybrid_context.session_id,
            }

        return AgentCheckpoint(
            workflow_id=workflow_id,
            phase=phase,
            user_prompt=user_prompt,
            tasks=tasks or {},
            hybrid_context_data=context_data,
            generated_code=generated_code,
            review_result=review_result or {},
            validation_result=validation_result or {},
            attempt_number=attempt_number,
            metadata=metadata or {},
        )

    def _restore_context_from_checkpoint(
        self, checkpoint: AgentCheckpoint
    ) -> HybridContext | None:
        """
        Restore HybridContext from checkpoint data.

        Args:
            checkpoint: Checkpoint containing serialized context

        Returns:
            Restored HybridContext or None if not available
        """
        context_data = checkpoint.hybrid_context_data
        if not context_data:
            return None

        context = HybridContext(
            items=[],
            query=context_data.get("query", ""),
            target_entity=context_data.get("target_entity", ""),
            session_id=context_data.get("session_id"),
        )

        # Restore items
        for item_data in context_data.get("items", []):
            source = ContextSource(item_data["source"])
            context.add_item(
                content=item_data["content"],
                source=source,
                confidence=item_data.get("confidence", 0.5),
                entity_id=item_data.get("entity_id"),
            )

        return context

    async def resume_from_checkpoint(
        self,
        checkpoint: AgentCheckpoint,
        save_checkpoints: bool = True,
    ) -> dict[str, Any]:
        """
        Resume workflow execution from a checkpoint.

        Skips completed phases and continues from the checkpoint phase.

        Args:
            checkpoint: Checkpoint to resume from
            save_checkpoints: Whether to save new checkpoints during execution

        Returns:
            Workflow result dict
        """
        logger.info(
            f"Resuming workflow {checkpoint.workflow_id} "
            f"from phase {checkpoint.phase.value}"
        )

        self.monitor.start_time = time.time()
        workflow_id = checkpoint.workflow_id

        # Restore state from checkpoint
        user_prompt = checkpoint.user_prompt
        tasks = checkpoint.tasks
        hybrid_context = self._restore_context_from_checkpoint(checkpoint)
        self.final_code = checkpoint.generated_code
        review_result = checkpoint.review_result or None
        attempt_number = checkpoint.attempt_number

        # Skip to appropriate phase based on checkpoint
        phase = checkpoint.phase

        # Phase 1: PLANNING - Skip if already done
        if phase.value in ("init", "planning"):
            if not tasks:
                tasks = await self._planner_agent(user_prompt)
            if save_checkpoints:
                cp = self._create_checkpoint(
                    workflow_id, WorkflowPhase.PLANNING, user_prompt, tasks
                )
                self.save_checkpoint(cp)
            phase = WorkflowPhase.CONTEXT_RETRIEVAL

        # Phase 2: CONTEXT - Skip if already done
        if phase == WorkflowPhase.CONTEXT_RETRIEVAL:
            if not hybrid_context:
                hybrid_context = self.context_service.get_hybrid_context(
                    tasks["target_entity"], user_prompt
                )
            if save_checkpoints:
                cp = self._create_checkpoint(
                    workflow_id,
                    WorkflowPhase.CONTEXT_RETRIEVAL,
                    user_prompt,
                    tasks,
                    hybrid_context,
                )
                self.save_checkpoint(cp)
            phase = WorkflowPhase.CODE_GENERATION

        # Phases 3-5: CODE -> REVIEW -> VALIDATE loop
        max_attempts = checkpoint.max_attempts
        for attempt in range(attempt_number, max_attempts + 1):
            print(f"\n--- Development Cycle {attempt} ---")

            # Phase 3: CODE
            if phase in (WorkflowPhase.CODE_GENERATION, WorkflowPhase.REMEDIATION):
                coder_result = await self.coder_agent.generate_code(
                    hybrid_context, tasks["task_description"]
                )
                self.final_code = coder_result["code"]

                if save_checkpoints:
                    cp = self._create_checkpoint(
                        workflow_id,
                        WorkflowPhase.CODE_GENERATION,
                        user_prompt,
                        tasks,
                        hybrid_context,
                        self.final_code,
                        attempt_number=attempt,
                    )
                    self.save_checkpoint(cp)
                phase = WorkflowPhase.SECURITY_REVIEW

            # Phase 4: REVIEW
            if phase == WorkflowPhase.SECURITY_REVIEW:
                review_result = await self.reviewer_agent.review_code(self.final_code)

                if save_checkpoints:
                    cp = self._create_checkpoint(
                        workflow_id,
                        WorkflowPhase.SECURITY_REVIEW,
                        user_prompt,
                        tasks,
                        hybrid_context,
                        self.final_code,
                        review_result,
                        attempt_number=attempt,
                    )
                    self.save_checkpoint(cp)

                if review_result["status"] == "PASS":
                    phase = WorkflowPhase.VALIDATION
                    break

                # Remediate if vulnerabilities found
                print(
                    f"[{AgentRole.ORCHESTRATOR.value}] VULNERABILITY DETECTED. "
                    "Forcing Coder Agent to self-correct..."
                )
                self.monitor.record_security_finding(
                    AgentRole.ORCHESTRATOR,
                    review_result["finding"],
                    review_result.get("severity", "High"),
                    "Remediated",
                )

                # Add remediation context
                remediation_text = (
                    "Security Remediation Required: FIX: Use SHA256 instead of SHA1."
                )
                hybrid_context.add_remediation(remediation_text, confidence=1.0)
                phase = WorkflowPhase.REMEDIATION

                if attempt == max_attempts:
                    print(
                        f"[{AgentRole.ORCHESTRATOR.value}] "
                        "Correction failed after max attempts. Handoff to human."
                    )

        # Phase 5: VALIDATE
        validation_result = await self.validator_agent.validate_code(
            self.final_code,
            expected_elements=["import hashlib", "calculate_checksum"],
        )
        is_valid = validation_result["valid"]

        if save_checkpoints:
            final_phase = (
                WorkflowPhase.COMPLETED
                if is_valid and review_result and review_result["status"] == "PASS"
                else WorkflowPhase.FAILED
            )
            cp = self._create_checkpoint(
                workflow_id,
                final_phase,
                user_prompt,
                tasks,
                hybrid_context,
                self.final_code,
                review_result,
                validation_result,
            )
            self.save_checkpoint(cp)

        metrics = self.monitor.finalize_report()
        is_success = (
            is_valid and review_result is not None and review_result["status"] == "PASS"
        )

        return {
            "status": "SUCCESS" if is_success else "FAILURE",
            "final_code": self.final_code,
            "metrics": metrics,
            "handover": self.generate_handover_report(metrics),
            "validation": validation_result,
            "review": review_result,
            "resumed_from": checkpoint.checkpoint_id,
        }

    async def execute_request_with_checkpoints(
        self,
        user_prompt: str,
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute request with automatic checkpointing for recovery.

        Creates checkpoints at each phase boundary to enable resumption
        if the workflow fails or is interrupted.

        Args:
            user_prompt: High-level user request
            workflow_id: Optional workflow ID (generated if not provided)

        Returns:
            Workflow result dict with checkpoint information
        """
        workflow_id = workflow_id or str(uuid.uuid4())
        logger.info(f"Starting checkpointed workflow: {workflow_id}")

        self.monitor.start_time = time.time()

        # Phase 0: INIT
        init_checkpoint = self._create_checkpoint(
            workflow_id, WorkflowPhase.INIT, user_prompt
        )
        self.save_checkpoint(init_checkpoint)

        # Phase 1: PLAN
        tasks = await self._planner_agent(user_prompt)
        plan_checkpoint = self._create_checkpoint(
            workflow_id, WorkflowPhase.PLANNING, user_prompt, tasks
        )
        self.save_checkpoint(plan_checkpoint)

        # Phase 2: CONTEXT
        hybrid_context = self.context_service.get_hybrid_context(
            tasks["target_entity"], user_prompt
        )
        context_checkpoint = self._create_checkpoint(
            workflow_id,
            WorkflowPhase.CONTEXT_RETRIEVAL,
            user_prompt,
            tasks,
            hybrid_context,
        )
        self.save_checkpoint(context_checkpoint)

        # Phases 3-5: CODE -> REVIEW -> VALIDATE loop
        review_result = None
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            print(f"\n--- Development Cycle {attempt} ---")

            # Phase 3: CODE
            coder_result = await self.coder_agent.generate_code(
                hybrid_context, tasks["task_description"]
            )
            self.final_code = coder_result["code"]

            code_checkpoint = self._create_checkpoint(
                workflow_id,
                WorkflowPhase.CODE_GENERATION,
                user_prompt,
                tasks,
                hybrid_context,
                self.final_code,
                attempt_number=attempt,
            )
            self.save_checkpoint(code_checkpoint)

            # Phase 4: REVIEW
            review_result = await self.reviewer_agent.review_code(self.final_code)

            review_checkpoint = self._create_checkpoint(
                workflow_id,
                WorkflowPhase.SECURITY_REVIEW,
                user_prompt,
                tasks,
                hybrid_context,
                self.final_code,
                review_result,
                attempt_number=attempt,
            )
            self.save_checkpoint(review_checkpoint)

            if review_result["status"] == "PASS":
                break

            # Remediate
            print(
                f"[{AgentRole.ORCHESTRATOR.value}] VULNERABILITY DETECTED. "
                "Forcing Coder Agent to self-correct..."
            )
            self.monitor.record_security_finding(
                AgentRole.ORCHESTRATOR,
                review_result["finding"],
                review_result.get("severity", "High"),
                "Remediated",
            )

            remediation_text = (
                "Security Remediation Required: FIX: Use SHA256 instead of SHA1."
            )
            hybrid_context.add_remediation(remediation_text, confidence=1.0)

            if attempt == max_attempts:
                print(
                    f"[{AgentRole.ORCHESTRATOR.value}] "
                    "Correction failed after max attempts."
                )

        # Phase 5: VALIDATE
        validation_result = await self.validator_agent.validate_code(
            self.final_code,
            expected_elements=["import hashlib", "calculate_checksum"],
        )
        is_valid = validation_result["valid"]

        # Final checkpoint
        final_phase = (
            WorkflowPhase.COMPLETED
            if is_valid and review_result and review_result["status"] == "PASS"
            else WorkflowPhase.FAILED
        )
        final_checkpoint = self._create_checkpoint(
            workflow_id,
            final_phase,
            user_prompt,
            tasks,
            hybrid_context,
            self.final_code,
            review_result,
            validation_result,
        )
        self.save_checkpoint(final_checkpoint)

        metrics = self.monitor.finalize_report()
        is_success = (
            is_valid and review_result is not None and review_result["status"] == "PASS"
        )

        return {
            "status": "SUCCESS" if is_success else "FAILURE",
            "final_code": self.final_code,
            "metrics": metrics,
            "handover": self.generate_handover_report(metrics),
            "validation": validation_result,
            "review": review_result,
            "workflow_id": workflow_id,
            "checkpoint_id": final_checkpoint.checkpoint_id,
        }

    async def _planner_agent(self, user_prompt: str) -> dict[str, str]:
        """Breaks down the high-level prompt into actionable sub-tasks."""
        print(
            f"\n[{AgentRole.PLANNER.value}] Decomposing user prompt into sub-tasks..."
        )
        self.monitor.record_agent_activity(tokens_used=500)

        if self.llm:
            try:
                return await self._planner_agent_llm(user_prompt)
            except Exception as e:
                logger.warning(f"LLM planner failed, using fallback: {e}")
                return self._planner_agent_fallback(user_prompt)
        return self._planner_agent_fallback(user_prompt)

    async def _planner_agent_llm(self, user_prompt: str) -> dict[str, str]:
        """LLM-powered task decomposition."""
        if self.llm is None:
            return self._planner_agent_fallback(user_prompt)

        prompt = f"""You are a task decomposition agent for a code security remediation system.

Analyze the following user prompt and decompose it into actionable tasks.

User Prompt: {user_prompt}

Respond with a JSON object containing:
- "target_entity": The specific code entity to modify (e.g., "ClassName.method_name")
- "task_description": A detailed description of the task to perform

Response (JSON only):"""

        response = await self.llm.generate(prompt, agent="Planner")
        try:
            result = json.loads(response)
            return {
                "target_entity": result.get(
                    "target_entity", "DataProcessor.calculate_checksum"
                ),
                "task_description": result.get("task_description", user_prompt),
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse planner LLM response, using fallback")
            return self._planner_agent_fallback(user_prompt)

    def _planner_agent_fallback(self, user_prompt: str) -> dict[str, str]:
        """Fallback planner when LLM is unavailable."""
        return {
            "target_entity": "DataProcessor.calculate_checksum",
            "task_description": f"Refactor checksum method in DataProcessor to use a secure hash algorithm. Goal: {user_prompt}",
        }

    async def _coder_agent(self, context: HybridContext, task_description: str) -> str:
        """Generates the code based on the context."""
        print(f"\n[{AgentRole.CODER.value}] Generating code based on hybrid context...")
        self.monitor.record_agent_activity(tokens_used=4000, loc_generated=15)

        if self.llm:
            try:
                return await self._coder_agent_llm(context, task_description)
            except Exception as e:
                logger.warning(f"LLM coder failed, using fallback: {e}")
                return self._coder_agent_fallback(context)
        return self._coder_agent_fallback(context)

    async def _coder_agent_llm(
        self, context: HybridContext, task_description: str
    ) -> str:
        """LLM-powered code generation."""
        if self.llm is None:
            return self._coder_agent_fallback(context)

        context_str = context.to_prompt_string()
        has_remediation = (
            len(context.get_items_by_source(ContextSource.REMEDIATION)) > 0
        )

        prompt = f"""You are a secure code generation agent.

Task: {task_description}

Context:
{context_str}

{"IMPORTANT: Security remediation is required. Previous code had vulnerabilities that must be fixed." if has_remediation else "Generate initial implementation."}

Requirements:
- Follow all security policies mentioned in the context
- Use FIPS-compliant algorithms (SHA256 or SHA3-512, never SHA1)
- Include appropriate comments

Generate ONLY the Python code, no explanations:"""

        response = await self.llm.generate(prompt, agent="Coder")

        # Extract code from response (handle markdown code blocks)
        code: str = response.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    def _coder_agent_fallback(self, context: HybridContext) -> str:
        """Fallback code generation when LLM is unavailable."""
        # Convert context to prompt string for processing
        context.to_prompt_string()

        # Check if remediation context exists
        has_remediation = (
            len(context.get_items_by_source(ContextSource.REMEDIATION)) > 0
        )

        if has_remediation:
            # This block is executed on the self-correction attempt.
            return """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        # Security Policy Enforced: Using SHA256
        return hashlib.sha256(data.encode()).hexdigest()
"""
        # This block is executed on the initial attempt, creating the vulnerability.
        return """import hashlib

class DataProcessor:
    def calculate_checksum(self, data):
        # VULNERABILITY: Insecure hash function used
        return hashlib.sha1(data.encode()).hexdigest()
"""

    async def _reviewer_agent(self, code: str) -> dict[str, str]:
        """Reviews code for security flaws and adherence to policy."""
        print(
            f"\n[{AgentRole.REVIEWER.value}] Reviewing code for security and policy violations..."
        )
        self.monitor.record_agent_activity(tokens_used=1000)

        if self.llm:
            try:
                return await self._reviewer_agent_llm(code)
            except Exception as e:
                logger.warning(f"LLM reviewer failed, using fallback: {e}")
                return self._reviewer_agent_fallback(code)
        return self._reviewer_agent_fallback(code)

    async def _reviewer_agent_llm(self, code: str) -> dict[str, str]:
        """LLM-powered security review."""
        if self.llm is None:
            return self._reviewer_agent_fallback(code)

        prompt = f"""You are a security code reviewer for enterprise software.

Review the following code for security vulnerabilities and policy compliance.

Code:
```python
{code}
```

Security Policies:
- All cryptographic operations must use FIPS-compliant algorithms
- SHA1 is prohibited (use SHA256 or SHA3-512)
- No hardcoded credentials or secrets
- Input must be validated and sanitized

Respond with a JSON object containing:
- "status": "PASS" if code is secure, "FAIL_SECURITY" if vulnerabilities found
- "finding": Description of the issue or "Code is secure and compliant"
- "severity": "High", "Medium", or "Low" (only if status is FAIL_SECURITY)

Response (JSON only):"""

        response = await self.llm.generate(prompt, agent="Reviewer")
        try:
            result = json.loads(response)
            status = result.get("status", "PASS")
            finding = result.get("finding", "Code review completed")

            if status == "FAIL_SECURITY":
                severity = result.get("severity", "High")
                self.monitor.record_security_finding(
                    AgentRole.REVIEWER, finding, severity, "Detected"
                )
                return {"status": status, "finding": finding, "severity": severity}
            return {"status": "PASS", "finding": finding}
        except json.JSONDecodeError:
            logger.warning("Failed to parse reviewer LLM response, using fallback")
            return self._reviewer_agent_fallback(code)

    def _reviewer_agent_fallback(self, code: str) -> dict[str, str]:
        """Fallback security review when LLM is unavailable."""
        if "hashlib.sha1" in code:
            finding = "High-Severity: Weak cryptographic hash (SHA1) detected. Violates CMMC/SOX policy."
            self.monitor.record_security_finding(
                AgentRole.REVIEWER, finding, "High", "Detected"
            )
            return {"status": "FAIL_SECURITY", "finding": finding, "severity": "High"}

        return {"status": "PASS", "finding": "Code is secure and compliant (SHA256)."}

    def _validator_agent(self, code: str) -> bool:
        """
        Runs basic structural and syntax validation tests.

        FIX: Actually validate Python syntax using ast.parse() instead of just string matching.
        """
        print(f"\n[{AgentRole.VALIDATOR.value}] Running structural and unit tests...")
        self.monitor.record_agent_activity(tokens_used=500)

        # FIX: First check syntax validity using AST parsing
        try:
            ast.parse(code)
        except SyntaxError:
            print(
                f"[{AgentRole.VALIDATOR.value}] Syntax error detected in generated code."
            )
            return False

        # Then check for required structural elements
        return bool("import hashlib" in code and "calculate_checksum" in code)

    async def execute_request(self, user_prompt: str) -> dict[str, Any]:
        """The main, autonomous System 2 execution loop.

        Orchestrates the following workflow:
        0. SECURITY: A2AS input validation (ADR-029 Phase 2.3)
        1. PLAN: Decompose user prompt into actionable tasks
        2. MEMORY: Load cognitive context from Titan Memory (ADR-029 Phase 2.1)
        3. CONTEXT: Retrieve hybrid context (graph + vector)
        4. CODE: Generate code using CoderAgent
        5. REVIEW: Security review using ReviewerAgent
        6. VALIDATE: Comprehensive validation using ValidatorAgent
        7. REMEDIATE: Self-correct if vulnerabilities found (up to max_attempts)
        8. LEARN: Store successful experience in Titan Memory

        Args:
            user_prompt: High-level user request for code changes.

        Returns:
            Dict containing status, final_code, metrics, and handover report.
        """
        self.monitor.start_time = time.time()

        # Phase 0: A2AS Security - Validate input (ADR-029 Phase 2.3)
        if self.a2as_service:
            try:
                from src.services.a2as_security_service import ThreatLevel

                security_assessment = await self.a2as_service.assess_agent_input(
                    input_text=user_prompt,
                    source="orchestrator",
                )

                if security_assessment.threat_level in (
                    ThreatLevel.HIGH,
                    ThreatLevel.CRITICAL,
                ):
                    # Create a summary from findings
                    summary = (
                        "; ".join(f.description for f in security_assessment.findings)
                        if security_assessment.findings
                        else "Security threat detected"
                    )
                    logger.warning(
                        f"A2AS blocked request: {summary} "
                        f"(threat_level={security_assessment.threat_level.value})"
                    )
                    return {
                        "status": "BLOCKED",
                        "reason": "A2AS security assessment blocked request",
                        "threat_level": security_assessment.threat_level.value,
                        "security_summary": summary,
                        "blocked_patterns": [
                            f.attack_vector.value for f in security_assessment.findings
                        ],
                        "metrics": self.monitor.finalize_report(),
                    }
                elif security_assessment.threat_level == ThreatLevel.MEDIUM:
                    summary = (
                        "; ".join(f.description for f in security_assessment.findings)
                        if security_assessment.findings
                        else "Medium threat detected"
                    )
                    logger.info(f"A2AS warning: {summary} - proceeding with caution")
            except Exception as e:
                logger.warning(f"A2AS validation failed (non-blocking): {e}")

        # Phase 1: PLAN - Decompose user prompt
        tasks = await self._planner_agent(user_prompt)

        # Phase 2: MEMORY - Load cognitive context from Titan Memory (ADR-029 Phase 2.1)
        memory_context = None
        neural_confidence = 0.5  # Default confidence
        if self.titan_memory:
            try:
                memory_context = await self.titan_memory.load_cognitive_context(
                    task_description=user_prompt,
                    domain="security_remediation",
                )
                neural_confidence = memory_context.get("neural_memory", {}).get(
                    "neural_confidence", 0.5
                )
                logger.info(
                    f"Loaded Titan memory context (neural_confidence={neural_confidence:.2f})"
                )
            except Exception as e:
                logger.warning(f"Failed to load Titan memory context: {e}")

        # Phase 3: CONTEXT - Retrieve hybrid context
        hybrid_context = self.context_service.get_hybrid_context(
            tasks["target_entity"], user_prompt
        )

        # Augment context with memory if available
        if memory_context:
            hybrid_context.add_memory_context(memory_context, neural_confidence)

        # Phase 3-5: CODE → REVIEW → VALIDATE loop with remediation
        review_result = None
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            print(f"\n--- Development Cycle {attempt} ---")

            # Phase 3: CODE - Generate using CoderAgent
            coder_result = await self.coder_agent.generate_code(
                hybrid_context, tasks["task_description"]
            )
            self.final_code = coder_result["code"]

            # Phase 4: REVIEW - Security review using ReviewerAgent
            review_result = await self.reviewer_agent.review_code(self.final_code)

            if review_result["status"] == "PASS":
                break

            # Remediate if vulnerabilities found
            print(
                f"[{AgentRole.ORCHESTRATOR.value}] VULNERABILITY DETECTED. Forcing Coder Agent to self-correct..."
            )
            self.monitor.record_security_finding(
                AgentRole.ORCHESTRATOR,
                review_result["finding"],
                review_result.get("severity", "High"),
                "Remediated",
            )

            # Add remediation context for next iteration
            remediation_text = (
                "Security Remediation Required: FIX: Use SHA256 instead of SHA1."
            )
            hybrid_context.add_remediation(remediation_text, confidence=1.0)

            if attempt == max_attempts:
                print(
                    f"[{AgentRole.ORCHESTRATOR.value}] Correction failed after max attempts. Handoff to human."
                )

        # Phase 5: VALIDATE - Comprehensive validation using ValidatorAgent
        validation_result = await self.validator_agent.validate_code(
            self.final_code,
            expected_elements=["import hashlib", "calculate_checksum"],
        )
        is_valid = validation_result["valid"]

        metrics = self.monitor.finalize_report()

        # Determine success: valid code + passed review
        is_success = (
            is_valid and review_result is not None and review_result["status"] == "PASS"
        )

        # Phase 8: LEARN - Store successful experience in Titan Memory (ADR-029 Phase 2.1)
        if is_success and self.titan_memory:
            try:
                await self._store_experience_in_memory(
                    task=user_prompt,
                    context=hybrid_context,
                    result={
                        "code": self.final_code,
                        "review": review_result,
                        "validation": validation_result,
                    },
                )
                logger.info("Stored successful experience in Titan memory")
            except Exception as e:
                logger.warning(f"Failed to store experience in Titan memory: {e}")

        return {
            "status": "SUCCESS" if is_success else "FAILURE",
            "final_code": self.final_code,
            "metrics": metrics,
            "handover": self.generate_handover_report(metrics),
            "validation": validation_result,
            "review": review_result,
            "neural_confidence": neural_confidence if memory_context else None,
        }

    def generate_handover_report(self, metrics: dict[str, Any]) -> str:
        """Creates the actionable report for the human developer."""
        # FIX: F-strings for multiline text need triple quotes.
        return f"""
        ========================================
        AI Autonomous Development Handover Report
        ========================================
        Feature: Secure Hash Function Implementation
        Status: READY FOR HUMAN REVIEW AND DEPLOYMENT

        --- Key Metrics for Leadership (Monitoring Service) ---
        Total Autonomous Time: {metrics["total_runtime_seconds"]} seconds
        Estimated Engineering Hours Saved: {metrics["engineering_hours_saved"]} hours
        LLM Cost (per feature): ${metrics["llm_cost_usd"]}
        Vulnerabilities Fixed by AI (Critical/High): {metrics["vulnerabilities_remediated_count"]}

        --- Final Code Changes ---
        ```python
        {self.final_code.strip()}
        ```

        --- Human Developer Next Steps (The Critical 20%) ---
        1.  **Performance Testing:** Manually benchmark the SHA256 function against production data latency requirements.
        2.  **Integration Test:** Verify that the new checksum integrates correctly with the downstream ResultStore API.
        3.  **CI/CD Review:** Verify the committed code passes all SAST/SCA security gates in the CodePipeline before merge to 'main'.
        """

    # =========================================================================
    # MCP Tool Integration Methods (ADR-029 Phase 1.4)
    # =========================================================================

    def get_available_mcp_tools(self) -> dict[str, Any]:
        """Get all available MCP tools from server and client.

        Returns:
            Dict mapping tool names to their metadata (description, schema, etc.)
        """
        tools: dict[str, Any] = {}

        if self.mcp_server:
            for tool in self.mcp_server.list_tools():
                tools[tool.name] = {
                    "source": "internal",
                    "description": tool.description,
                    "category": tool.category.value,
                    "requires_approval": tool.requires_approval,
                }

        # External tools would be discovered via mcp_client.list_tools()
        # This is async in production but synchronous metadata could be cached

        return tools

    async def invoke_mcp_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        skip_approval: bool = False,
    ) -> dict[str, Any]:
        """Invoke an MCP tool by name.

        Args:
            tool_name: Name of the tool to invoke
            params: Tool parameters
            skip_approval: Skip HITL approval for sensitive tools

        Returns:
            Tool result data

        Raises:
            ValueError: If tool is not available
            RuntimeError: If tool invocation fails
        """
        # Check internal tools first
        if self.mcp_server:
            internal_tools = {t.name for t in self.mcp_server.list_tools()}
            if tool_name in internal_tools:
                result = await self.mcp_server.invoke_tool(
                    tool_name, params, skip_approval=skip_approval
                )
                if not result.success:
                    raise RuntimeError(f"Tool invocation failed: {result.error}")
                return result.data

        # Check external tools via gateway
        if self.mcp_client:
            # External tool invocation would go here
            pass

        raise ValueError(f"Tool '{tool_name}' not available")

    def has_mcp_tool(self, tool_name: str) -> bool:
        """Check if an MCP tool is available.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is available, False otherwise
        """
        if self.mcp_server:
            internal_tools = {t.name for t in self.mcp_server.list_tools()}
            if tool_name in internal_tools:
                return True
        return False

    # =========================================================================
    # Async Messaging Methods (Issue #19 - Microservices Messaging)
    # =========================================================================

    async def dispatch_task_async(
        self,
        agent_type: str,
        task_description: str,
        context: dict[str, Any],
        correlation_id: str | None = None,
        priority: int = 5,
        timeout_seconds: int = 600,
    ) -> str | None:
        """Dispatch a task to an agent via SQS queue.

        Args:
            agent_type: Target agent ("coder", "reviewer", "validator").
            task_description: Description of the task to perform.
            context: Context dict containing code, policies, etc.
            correlation_id: Optional ID to track the workflow.
            priority: Task priority (1-10, higher = more urgent).
            timeout_seconds: Maximum time for agent to process task.

        Returns:
            Message ID if dispatched successfully, None otherwise.
        """
        if not self.queue_service:
            logger.warning("Queue service not configured, cannot dispatch async")
            return None

        if not self.use_async_messaging:
            logger.debug("Async messaging disabled, skipping queue dispatch")
            return None

        import uuid

        from src.agents.messaging import AgentTaskMessage, MessageType

        # Create task message
        task_id = str(uuid.uuid4())
        message = AgentTaskMessage(
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            source_agent="orchestrator",
            target_agent=agent_type,
            message_type=MessageType.TASK,
            payload={"task_description": task_description},
            correlation_id=correlation_id or str(uuid.uuid4()),
            priority=priority,
            context=context,
            timeout_seconds=timeout_seconds,
            autonomy_level="standard",
        )

        try:
            message_id = await self.queue_service.send_task(agent_type, message)

            # Publish EventBridge event for tracking
            from src.services.eventbridge_publisher import EventType

            if self.queue_service.eventbridge:
                await self.queue_service.eventbridge.publish_async(
                    event_type=EventType.AGENT_TASK_DISPATCHED,
                    detail={
                        "task_id": task_id,
                        "agent_type": agent_type,
                        "correlation_id": message.correlation_id,
                        "priority": priority,
                    },
                )

            logger.info(
                f"Dispatched task {task_id} to {agent_type} queue (message_id={message_id})"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to dispatch task to {agent_type}: {e}")
            return None

    async def await_agent_responses(
        self,
        task_ids: list[str],
        timeout_seconds: int = 300,
        poll_interval_seconds: int = 5,
    ) -> dict[str, dict[str, Any]]:
        """Poll responses queue for completed agent tasks.

        Args:
            task_ids: List of task IDs to wait for.
            timeout_seconds: Maximum time to wait for all responses.
            poll_interval_seconds: Interval between queue polls.

        Returns:
            Dict mapping task_id to result data.
        """
        if not self.queue_service:
            logger.warning("Queue service not configured, cannot await responses")
            return {}

        results: dict[str, dict[str, Any]] = {}
        pending_ids = set(task_ids)
        start_time = time.time()

        while pending_ids and (time.time() - start_time) < timeout_seconds:
            try:
                messages = await self.queue_service.receive_responses(max_messages=10)

                for msg, receipt_handle in messages:
                    if msg.task_id in pending_ids:
                        results[msg.task_id] = {
                            "success": msg.success,
                            "data": msg.data,
                            "error": msg.error,
                            "execution_time_ms": msg.execution_time_ms,
                            "tokens_used": msg.tokens_used,
                        }
                        pending_ids.remove(msg.task_id)

                        # Acknowledge the message
                        await self.queue_service.ack_message(
                            "responses", receipt_handle
                        )

                        # Publish completion event
                        from src.services.eventbridge_publisher import EventType

                        event_type = (
                            EventType.AGENT_TASK_COMPLETED
                            if msg.success
                            else EventType.AGENT_TASK_FAILED
                        )
                        if self.queue_service.eventbridge:
                            await self.queue_service.eventbridge.publish_async(
                                event_type=event_type,
                                detail={
                                    "task_id": msg.task_id,
                                    "success": msg.success,
                                    "execution_time_ms": msg.execution_time_ms,
                                },
                            )

                if pending_ids:
                    await asyncio.sleep(poll_interval_seconds)

            except Exception as e:
                logger.warning(f"Error polling responses: {e}")
                await asyncio.sleep(poll_interval_seconds)

        if pending_ids:
            logger.warning(
                f"Timeout waiting for {len(pending_ids)} tasks: {pending_ids}"
            )

        return results

    async def execute_request_async(
        self,
        user_prompt: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute request using async messaging (SQS-based dispatch).

        Alternative to execute_request() that uses queue-based task dispatch
        for better scalability and decoupling.

        Args:
            user_prompt: High-level user request.
            correlation_id: Optional ID to track the entire workflow.

        Returns:
            Dict with status, task_ids, and tracking info.
        """
        if not self.use_async_messaging or not self.queue_service:
            logger.info("Async messaging not enabled, falling back to sync")
            return await self.execute_request(user_prompt)

        import uuid

        self.monitor.start_time = time.time()
        correlation_id = correlation_id or str(uuid.uuid4())

        # Phase 1: PLAN - Decompose user prompt
        tasks = await self._planner_agent(user_prompt)

        # Phase 2: CONTEXT - Retrieve hybrid context
        hybrid_context = self.context_service.get_hybrid_context(
            tasks["target_entity"], user_prompt
        )

        # Phase 3: Dispatch to coder agent via queue
        context_dict = {
            "items": [
                {"content": item.content, "source": item.source.value}
                for item in hybrid_context.items
            ],
            "target_entity": hybrid_context.target_entity,
            "query": hybrid_context.query,
        }

        coder_message_id = await self.dispatch_task_async(
            agent_type="coder",
            task_description=tasks["task_description"],
            context=context_dict,
            correlation_id=correlation_id,
            priority=7,
            timeout_seconds=900,
        )

        if not coder_message_id:
            return {
                "status": "DISPATCH_FAILED",
                "error": "Failed to dispatch task to coder queue",
                "correlation_id": correlation_id,
            }

        return {
            "status": "DISPATCHED",
            "correlation_id": correlation_id,
            "tasks_dispatched": 1,
            "agent_type": "coder",
            "message_id": coder_message_id,
            "next_step": "Poll responses queue or wait for webhook callback",
        }

    async def execute_request_with_hitl(
        self,
        user_prompt: str,
        vulnerability_id: str,
        reviewer_emails: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute request with full HITL approval workflow.

        Extended workflow that adds sandbox testing and human approval after
        successful code generation and validation:
        1. PLAN → CONTEXT → CODE → REVIEW → VALIDATE (standard flow)
        2. If valid → Run sandbox testing
        3. If sandbox passes → Create approval request
        4. Send notifications to reviewers
        5. Return status "AWAITING_APPROVAL" with approval_id

        Args:
            user_prompt: High-level user request for code changes.
            vulnerability_id: Identifier of the vulnerability being patched.
            reviewer_emails: List of reviewer email addresses for notifications.

        Returns:
            Dict containing status, approval_id (if pending), and result details.
        """
        # Phase 1-5: Execute standard workflow
        result = await self.execute_request(user_prompt)

        # If standard workflow failed, return early
        if result["status"] != "SUCCESS":
            logger.warning("Standard workflow failed, skipping HITL")
            return {
                **result,
                "hitl_status": "SKIPPED",
                "hitl_reason": "Standard workflow failed - manual intervention required",
            }

        # Check if HITL services are available
        if not self.hitl_approval_service:
            logger.info("HITL services not configured, returning standard result")
            return {
                **result,
                "hitl_status": "DISABLED",
                "hitl_reason": "HITL approval service not configured",
            }

        # Phase 6: Sandbox Testing (simulated - uses validation results)
        # In production, this would call ValidatorAgent.validate_in_sandbox()
        sandbox_results = {
            "tests_passed": result["validation"].get("tests_passed", 0),
            "tests_failed": result["validation"].get("tests_failed", 0),
            "coverage": result["validation"].get("coverage", 0),
            "sandbox_id": f"sandbox-{int(time.time())}-mock",
            "status": "PASSED" if result["validation"]["valid"] else "FAILED",
        }

        if sandbox_results["status"] != "PASSED":
            logger.warning("Sandbox testing failed, skipping approval request")
            return {
                **result,
                "hitl_status": "SANDBOX_FAILED",
                "sandbox_results": sandbox_results,
                "hitl_reason": "Sandbox testing failed - cannot proceed to approval",
            }

        # Phase 7: Create HITL Approval Request
        try:
            # Map review severity to patch severity
            from src.services.hitl_approval_service import PatchSeverity

            severity_map = {
                "High": PatchSeverity.HIGH,
                "Critical": PatchSeverity.CRITICAL,
                "Medium": PatchSeverity.MEDIUM,
                "Low": PatchSeverity.LOW,
            }
            review_severity = result.get("review", {}).get("severity", "Medium")
            patch_severity = severity_map.get(review_severity, PatchSeverity.MEDIUM)

            approval_request = self.hitl_approval_service.create_approval_request(
                patch_id=f"patch-{vulnerability_id}-{int(time.time())}",
                vulnerability_id=vulnerability_id,
                severity=patch_severity,
                patch_diff=self._generate_patch_diff(result["final_code"]),
                original_code=self.initial_code,
                sandbox_results=sandbox_results,
                reviewer_email=reviewer_emails[0] if reviewer_emails else None,
                metadata={
                    "user_prompt": user_prompt,
                    "metrics": result["metrics"],
                },
            )

            logger.info(f"Created approval request: {approval_request.approval_id}")

        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            return {
                **result,
                "hitl_status": "APPROVAL_CREATION_FAILED",
                "hitl_error": str(e),
            }

        # Phase 8: Send Notifications
        notification_results = []
        if self.notification_service and reviewer_emails:
            try:
                notification_results = (
                    self.notification_service.send_approval_notification(
                        approval_id=approval_request.approval_id,
                        patch_id=approval_request.patch_id,
                        vulnerability_id=vulnerability_id,
                        severity=patch_severity.value,
                        created_at=approval_request.created_at,
                        expires_at=approval_request.expires_at,
                        sandbox_results=sandbox_results,
                        patch_diff=approval_request.patch_diff,
                        recipients=reviewer_emails,
                    )
                )
                logger.info(f"Sent {len(notification_results)} notifications")
            except Exception as e:
                logger.warning(f"Failed to send notifications: {e}")
                # Non-fatal - continue with approval workflow

        return {
            **result,
            "status": "AWAITING_APPROVAL",
            "hitl_status": "PENDING",
            "approval_id": approval_request.approval_id,
            "approval_expires_at": approval_request.expires_at,
            "sandbox_results": sandbox_results,
            "notifications_sent": len(notification_results),
            "reviewer_emails": reviewer_emails,
        }

    async def _store_experience_in_memory(
        self,
        task: str,
        context: HybridContext,
        result: dict[str, Any],
    ) -> None:
        """Store successful experience in Titan neural memory (ADR-029 Phase 2.1).

        This method records completed tasks in neural memory for future retrieval,
        enabling the system to learn from successful patterns and avoid repeating
        mistakes.

        Args:
            task: The original task description (user prompt)
            context: The HybridContext used during execution
            result: The result dict containing code, review, and validation info
        """
        if not self.titan_memory:
            return

        from src.services.cognitive_memory_service import OutcomeStatus

        # Determine outcome based on result
        review_status = result.get("review", {}).get("status", "UNKNOWN")
        validation_valid = result.get("validation", {}).get("valid", False)

        if review_status == "PASS" and validation_valid:
            outcome = OutcomeStatus.SUCCESS
            outcome_details = "Code generated, reviewed, and validated successfully"
        elif review_status == "PASS":
            outcome = OutcomeStatus.SUCCESS
            outcome_details = "Code passed security review"
        else:
            outcome = OutcomeStatus.PARTIAL
            outcome_details = f"Review: {review_status}, Valid: {validation_valid}"

        # Extract reasoning from context
        remediation_items = context.get_items_by_source(ContextSource.REMEDIATION)
        security_items = context.get_items_by_source(ContextSource.SECURITY_POLICY)

        reasoning_parts = []
        if security_items:
            reasoning_parts.append(
                f"Applied security policies: {len(security_items)} items"
            )
        if remediation_items:
            reasoning_parts.append(
                f"Performed remediation: {len(remediation_items)} fixes"
            )

        reasoning = (
            "; ".join(reasoning_parts) if reasoning_parts else "Standard workflow"
        )

        # Record the episode with neural memory consolidation
        await self.titan_memory.record_episode(
            task_description=task,
            domain="security_remediation",
            decision=f"Generated code using {context.target_entity}",
            reasoning=reasoning,
            outcome=outcome,
            outcome_details=outcome_details,
            confidence_at_decision=0.8,  # Could be enhanced with actual confidence tracking
        )

        logger.debug(f"Stored experience in Titan memory: {outcome.value}")

    def _generate_patch_diff(self, new_code: str) -> str:
        """Generate a simple diff between original and new code."""
        original_lines = self.initial_code.split("\n")
        new_lines = new_code.split("\n")

        diff_lines = []
        for _i, (old, new) in enumerate(zip(original_lines, new_lines)):
            if old != new:
                diff_lines.append(f"- {old}")
                diff_lines.append(f"+ {new}")

        # Handle length differences
        if len(new_lines) > len(original_lines):
            for line in new_lines[len(original_lines) :]:
                diff_lines.append(f"+ {line}")
        elif len(original_lines) > len(new_lines):
            for line in original_lines[len(new_lines) :]:
                diff_lines.append(f"- {line}")

        return "\n".join(diff_lines) if diff_lines else "(no changes)"

    async def process_approval_decision(
        self,
        approval_id: str,
        decision: str,
        reviewer_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Process an approval decision from a human reviewer.

        Args:
            approval_id: The approval request ID.
            decision: "APPROVE" or "REJECT".
            reviewer_id: Identity of the reviewer.
            reason: Optional reason for the decision.

        Returns:
            Dict with status and next steps.
        """
        if not self.hitl_approval_service:
            return {
                "status": "ERROR",
                "error": "HITL approval service not configured",
            }

        try:
            if decision.upper() == "APPROVE":
                success = self.hitl_approval_service.approve_request(
                    approval_id=approval_id,
                    reviewer_id=reviewer_id,
                    reason=reason,
                )
                if success:
                    return {
                        "status": "APPROVED",
                        "approval_id": approval_id,
                        "next_step": "DEPLOY_TO_PRODUCTION",
                        "message": "Patch approved - ready for production deployment",
                    }

            elif decision.upper() == "REJECT":
                if not reason:
                    return {
                        "status": "ERROR",
                        "error": "Rejection reason is required",
                    }
                success = self.hitl_approval_service.reject_request(
                    approval_id=approval_id,
                    reviewer_id=reviewer_id,
                    reason=reason,
                )
                if success:
                    return {
                        "status": "REJECTED",
                        "approval_id": approval_id,
                        "next_step": "MANUAL_REMEDIATION",
                        "message": f"Patch rejected: {reason}",
                    }

            else:
                return {
                    "status": "ERROR",
                    "error": f"Invalid decision: {decision}. Must be APPROVE or REJECT",
                }

            return {
                "status": "ERROR",
                "error": "Failed to process decision",
            }

        except Exception as e:
            logger.error(f"Failed to process approval decision: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
            }


def create_system2_orchestrator(
    use_mock: bool = False,
    enable_mcp: bool = False,
    enable_titan_memory: bool = False,
    enable_semantic_cache: bool = True,
    enable_reflection: bool = True,
    enable_a2as: bool = True,
    enable_async_messaging: bool = False,
) -> "System2Orchestrator":
    """Factory function to create a System2Orchestrator.

    Args:
        use_mock: If True, use a mock LLM for testing. If False, use real Bedrock.
        enable_mcp: If True, initialize MCP tool server for internal tools.
        enable_titan_memory: If True, initialize Titan neural memory (ADR-029 Phase 2.1).
        enable_semantic_cache: If True, enable semantic caching for LLM (ADR-029 Phase 1.3).
        enable_reflection: If True, enable self-reflection for ReviewerAgent (ADR-029 Phase 2.2).
        enable_a2as: If True, enable A2AS input security (ADR-029 Phase 2.3).
        enable_async_messaging: If True, enable SQS-based async messaging (Issue #19).

    Returns:
        System2Orchestrator: Configured orchestrator instance.
    """
    mcp_server = None
    mcp_client = None
    titan_memory = None
    a2as_service = None
    queue_service = None

    # Initialize MCP tool server if enabled (ADR-029 Phase 1.4)
    if enable_mcp:
        from src.services.mcp_tool_server import create_mcp_tool_server

        mcp_server = create_mcp_tool_server()
        logger.info(
            f"MCP tool server initialized with {len(mcp_server.list_tools())} tools"
        )

    # Initialize Titan memory if enabled (ADR-029 Phase 2.1)
    if enable_titan_memory:
        try:
            from unittest.mock import AsyncMock

            from src.services.titan_cognitive_integration import (
                TitanCognitiveService,
                TitanIntegrationConfig,
            )

            # Create mock stores for now (in production, use real DynamoDB stores)
            mock_episodic = AsyncMock()
            mock_semantic = AsyncMock()
            mock_procedural = AsyncMock()
            mock_embedding = AsyncMock()
            mock_embedding.embed.return_value = [0.1] * 512

            config = TitanIntegrationConfig(
                enable_titan_memory=True,
                miras_preset="enterprise_standard",
                memory_dim=512,
            )

            titan_memory = TitanCognitiveService(
                episodic_store=mock_episodic,
                semantic_store=mock_semantic,
                procedural_store=mock_procedural,
                embedding_service=mock_embedding,
                integration_config=config,
            )
            logger.info("Titan memory service created (requires async initialization)")
        except ImportError as e:
            logger.warning(f"Titan memory not available (missing dependencies): {e}")
        except Exception as e:
            logger.warning(f"Failed to create Titan memory service: {e}")

    # Initialize A2AS security service if enabled (ADR-029 Phase 2.3)
    if enable_a2as:
        try:
            from src.services.a2as_security_service import (
                A2ASInjectionFilter,
                A2ASSecurityService,
            )

            injection_filter = A2ASInjectionFilter()
            a2as_service = A2ASSecurityService(
                injection_filter=injection_filter,
                enable_ai_analysis=False,
            )
            logger.info("A2AS security service initialized")
        except ImportError as e:
            logger.warning(f"A2AS security not available (missing dependencies): {e}")
        except Exception as e:
            logger.warning(f"Failed to create A2AS security service: {e}")

    # Initialize async messaging queue service if enabled (Issue #19)
    if enable_async_messaging:
        try:
            from src.services.agent_queue_service import AgentQueueService

            queue_service = AgentQueueService()
            logger.info("Agent queue service initialized for async messaging")
        except ImportError as e:
            logger.warning(f"Queue service not available (missing dependencies): {e}")
        except Exception as e:
            logger.warning(f"Failed to create queue service: {e}")

    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "target_entity": "DataProcessor.calculate_checksum",
                "task_description": "Refactor to use SHA256",
                "status": "PASS",
                "finding": "Code is secure and compliant",
            }
        )
        logger.info("Created System2Orchestrator with mock LLM")
        return System2Orchestrator(
            llm_client=mock_llm,
            mcp_server=mcp_server,
            mcp_client=mcp_client,
            titan_memory=titan_memory,
            enable_reflection=enable_reflection,
            a2as_service=a2as_service,
            queue_service=queue_service,
            use_async_messaging=enable_async_messaging,
        )
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service(enable_semantic_cache=enable_semantic_cache)
        logger.info(
            f"Created System2Orchestrator with Bedrock LLM (semantic_cache={enable_semantic_cache})"
        )
        return System2Orchestrator(
            llm_client=llm_service,
            mcp_server=mcp_server,
            mcp_client=mcp_client,
            titan_memory=titan_memory,
            enable_reflection=enable_reflection,
            a2as_service=a2as_service,
            queue_service=queue_service,
            use_async_messaging=enable_async_messaging,
        )


async def main():
    """Main entry point for the orchestrator."""
    user_prompt = "Refactor the DataProcessor's checksum method to be fully FIPS compliant and use the most secure standard hash."

    orchestrator = System2Orchestrator()
    result = await orchestrator.execute_request(user_prompt)

    print("\n" + "=" * 80)
    print(f"SYSTEM EXECUTION RESULT: {result['status']}")
    print("=" * 80)
    print(result["handover"])
    print("=" * 80)
    print("MONITORING METRICS LOG:")
    print(json.dumps(result["metrics"], indent=4))


if __name__ == "__main__":
    asyncio.run(main())
