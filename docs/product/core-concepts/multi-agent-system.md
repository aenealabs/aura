# Multi-Agent System

**Version:** 1.1
**Last Updated:** October 2026

---

## Overview

Project Aura uses a multi-agent architecture where specialized AI agents collaborate to detect, remediate, and validate security vulnerabilities. Rather than relying on a single monolithic AI model, Aura orchestrates multiple purpose-built agents that work together like a security engineering team.

This document explains the agent architecture, individual agent responsibilities, communication patterns, and how agents learn from their experiences.

> **Implementation status (October 2026).** The Coder, Reviewer, and Validator agents call the configured Bedrock model when an LLM client is present; with no client (or after an LLM error) they fall back to fixed templates and pattern checks. In the production job server (`src/agents/orchestrator_server.py`) these agents run in-process inside `System2Orchestrator`, not as separate services. Today the workflow patches the configured sample project (`get_sample_project_path()`, `src/config/paths.py:26`), not a customer repository selected per job; jobs carry a free-text prompt only. The sandbox step and the post-approval pull request are not yet connected end to end (see [HITL Workflow and the Job Server](#hitl-workflow-and-the-job-server)). Sections below that describe planned behavior are marked as such.

---

## Why Multi-Agent Architecture

A single AI model attempting to handle all aspects of security remediation faces several challenges:

| Challenge | Single Model | Multi-Agent |
|-----------|--------------|-------------|
| **Specialization** | Jack of all trades | Purpose-built experts |
| **Explainability** | Opaque decisions | Clear responsibility chains |
| **Robustness** | Single point of failure | Graceful degradation |
| **Scalability** | Vertical scaling only | Horizontal agent scaling |
| **Auditability** | Difficult to trace | Clear decision trails |

Aura's multi-agent approach provides:

- **Separation of concerns**: Each agent has a focused responsibility
- **Checks and balances**: Agents validate each other's work
- **Transparent decisions**: Clear audit trail of which agent made what decision
- **Flexible scaling**: Scale individual agents based on workload

---

## Agent Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AGENT ORCHESTRATOR                          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Workflow State Machine                   │    │
│  │                                                             │    │
│  │  INIT → PLANNING → CONTEXT → CODE_GEN → REVIEW → VALIDATE   │    │
│  │                                                    ↓        │    │
│  │                                              REMEDIATION    │    │
│  │                                                    ↓        │    │
│  │                                               COMPLETED     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Context Retrieval Service                │  │
│  │  (Hybrid GraphRAG: Neptune + OpenSearch + Three-Way Fusion)   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  CODER AGENT  │           │REVIEWER AGENT │           │VALIDATOR AGENT│
│               │           │               │           │               │
│ - Patch gen   │    ──▶    │ - Security    │    ──▶    │ - Syntax      │
│ - Code syn    │           │   review      │           │ - Sandbox     │
│ - Fix gen     │           │ - Policy      │           │ - Regression  │
│               │           │   compliance  │           │               │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │ MONITOR AGENT │
                            │               │
                            │ - Health      │
                            │ - Metrics     │
                            │ - Cost        │
                            └───────────────┘
```

---

## Agent Orchestrator

The Orchestrator is the central coordinator that manages the remediation workflow.

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Workflow Management** | Progress through remediation phases |
| **Task Assignment** | Delegate work to appropriate agents |
| **State Management** | Track progress and handle checkpoints |
| **Error Handling** | Recover from agent failures |
| **Resource Allocation** | Manage compute and token budgets |

### Workflow Phases

```python
class WorkflowPhase(Enum):
    INIT = "init"                              # Initialize workflow
    PLANNING = "planning"                      # Analyze task requirements
    MEMORY_LOAD = "memory_load"                # Load relevant memories
    CONTEXT_RETRIEVAL = "context_retrieval"    # Retrieve code context
    CODE_GENERATION = "code_generation"        # Generate patch
    SECURITY_REVIEW = "security_review"        # Security review
    VALIDATION = "validation"                  # Static validation
    REMEDIATION = "remediation"                # Feed findings back to the Coder
    MEMORY_STORE = "memory_store"              # Store learnings
    COMPLETED = "completed"                    # Success
    FAILED = "failed"                          # Failure
```

### Checkpoint and Resume

Long-running workflows can be interrupted and resumed with `execute_request_with_checkpoints` and `resume_from_checkpoint`:

```python
# Checkpoint captures workflow state (src/agents/agent_orchestrator.py)
checkpoint = AgentCheckpoint(
    workflow_id="wf-123456",
    phase=WorkflowPhase.SECURITY_REVIEW,
    user_prompt="Replace SHA1 with SHA256 in DataProcessor",
    generated_code="...",
    attempt_number=1,
)

# Later, resume from checkpoint
result = await orchestrator.resume_from_checkpoint(checkpoint)
```

The production job server calls `execute_request_with_hitl`, which does not write checkpoints; checkpointing is used only when a caller invokes the checkpoint methods directly.

### Repair Loop

A patch is accepted only when it passes both the Reviewer's security review and the Validator's checks. When either fails, the orchestrator feeds the findings back to the Coder as remediation context (validation issues include line numbers) and the Coder tries again.

| Option | Default | Effect |
|--------|---------|--------|
| `max_remediation_attempts` | 3 | Coding attempts per run (review + validation must both pass) |
| `max_sandbox_repairs` | 1 | Extra runs in the HITL workflow after a patch fails its sandbox tests; each repair run shows the Coder the failing tests and errors |
| `agentic_coder` | `True` | Gives the Coder read-only project tools (see below); takes effect only with an LLM client that supports tool use |

### HITL Workflow and the Job Server

`execute_request_with_hitl` runs the standard workflow, then sandbox testing, then creates an approval request. The production job server (`src/agents/orchestrator_server.py`) runs this full HITL workflow for each job rather than the plain workflow, so patches it produces are sandbox-tested and then queued for human approval. A patch that fails its sandbox tests (after any repair runs) gets no approval request. If no sandbox orchestrator is configured, the sandbox step is reported as `SKIPPED` and the approval request shows that the patch was not runtime-tested.

Current limits of this path:

- The sandbox orchestrator is built only when `SANDBOX_ENABLED=true` (`src/services/service_adapters.py:511`). The orchestrator's Kubernetes ConfigMap does not set it, so deployed jobs report the sandbox step as `SKIPPED` unless an operator adds it.
- When enabled, `ValidatorAgent.validate_in_sandbox` launches an ECS task but does not pass the patched code into it (`src/agents/validator_agent.py:701`), so the task cannot test the patch. Shipping the patch into the sandbox is planned.
- Approving a request records the decision and sends a notification; it does not open a pull request or deploy. Pull-request creation exists in `PatchValidationWorkflow` and `GitHubPRService`, which the job server does not call yet.
- Approval decisions made through the approvals API are not fed back into agent memory: `process_approval_decision` has no caller outside tests.

---

## Coder Agent

The Coder Agent generates security patches based on vulnerability information and code context.

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Patch Generation** | Create fixes for identified vulnerabilities |
| **Code Synthesis** | Generate new code following security patterns |
| **Context Integration** | Incorporate structural and semantic context |
| **Confidence Scoring** | Planned: the Coder does not yet return a confidence score |

### Input/Output

In the orchestrator workflow the Coder receives the planner's task description and the hybrid context (`CoderAgent.generate_code(context, task_description)`). The structured vulnerability input below is the target shape for scanner-driven remediation, which is planned; the current `generate_code` result carries `code`, `language`, `has_remediation`, and `tokens_used` only.

**Input (planned shape):**
```python
{
    "vulnerability": {
        "id": "vuln-789",
        "type": "SQL_INJECTION",
        "severity": "CRITICAL",
        "file": "src/services/user_service.py",
        "line": 47,
        "description": "User input passed directly to SQL query"
    },
    "context": HybridContext(
        structural=[...],  # Graph-based context
        semantic=[...],    # Vector-based context
        memory=[...]       # Neural memory context
    ),
    "security_policies": [
        "Use parameterized queries for all database operations",
        "Validate all user inputs before processing"
    ]
}
```

**Output (planned shape; `confidence` and `changes_made` are not yet returned):**
```python
{
    "code": "def get_user(user_id: str) -> User:\n    # Parameterized query (security fix)\n    return db.query(User).filter(User.id == user_id).first()",
    "language": "python",
    "has_remediation": True,
    "tokens_used": 4000,
    "confidence": 0.92,
    "changes_made": "Replaced string concatenation with SQLAlchemy ORM parameterized query"
}
```

### Agentic Mode (Tool Use)

With `agentic_coder` enabled, the Coder works as a Claude tool-use agent. Before submitting, it can call read-only tools to gather its own context instead of relying only on the retrieval made before it starts:

| Tool | Purpose |
|------|---------|
| `search_code` | Hybrid GraphRAG search (call graph + semantic) through the orchestrator's context retrieval |
| `read_file` | Reads a project file with line numbers, optionally a line range |
| `list_directory` | Lists the entries of a project directory |

All paths are confined to the project root, output is size-capped, and nothing is written. The Coder's only output is the code it submits through the `submit_code` tool, which then goes through security review, validation, sandbox tests, and human approval. If the tool loop does not produce a valid submission (or the LLM client has no tool use), the Coder falls back to a single `submit_code` call, then to a plain text response.

### Chain of Draft Prompting

The Coder Agent uses Chain of Draft (CoD) prompting for efficiency:

```python
# Traditional approach: ~5000 tokens
# CoD approach: ~400 tokens (92% reduction)

prompt = build_cod_prompt(
    "coder",
    vulnerability=task_description,
    context=context_str,
    code="(see context above)"
)
```

### Neural Memory Integration

The Coder Agent leverages past experiences. Neural memory guidance (ADR-029 Phase 2.1) is included in the Coder's prompt, and the orchestrator also passes the hybrid context to the Reviewer so its prompt carries the same guidance:

```python
# Check for similar past remediations
memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
if memory_items:
    high_confidence = any(item.confidence > 0.7 for item in memory_items)
    if high_confidence:
        # Apply learned patterns from similar fixes
        memory_guidance = extract_patterns(memory_items)
```

---

## Reviewer Agent

The Reviewer Agent validates code against security policies and best practices.

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Security Review** | Check for vulnerabilities (OWASP Top 10) |
| **Policy Compliance** | Verify CMMC, SOX, NIST 800-53 compliance |
| **Best Practices** | Ensure code quality standards |
| **Regression Check** | Verify patches do not introduce new issues |

### Security Policies

The Reviewer Agent enforces built-in security policies:

```python
SECURITY_POLICIES = {
    "crypto": {
        "prohibited": ["sha1", "md5", "des", "rc4"],
        "required": ["sha256", "sha384", "sha512", "sha3", "aes"],
        "message": "Cryptographic operations must use FIPS-compliant algorithms"
    },
    "secrets": {
        "patterns": ["password=", "api_key=", "secret=", "token=", "credential"],
        "message": "Hardcoded secrets detected - use environment variables or Secrets Manager"
    },
    "injection": {
        "patterns": ["eval(", "exec(", "subprocess.call(", "os.system(", "shell=True"],
        "message": "Potential code injection vulnerability - sanitize inputs"
    }
}
```

### Self-Reflection

The Reviewer Agent can critique its own analysis:

```python
# Initial review
initial_result = await self._review_code_llm(code)

# Self-reflection (if enabled)
if self.enable_reflection:
    reflection_result = await self.reflection.reflect_and_refine(
        initial_output=initial_result,
        context=f"Code being reviewed:\n{code}",
        reflection_prompt=REVIEWER_REFLECTION_PROMPT
    )
    # Up to 3 reflection iterations (ReflectionModule.MAX_ITERATIONS).
    # The "30% fewer false positives" figure is a design target from
    # ADR-029, not a measurement of Aura's workloads.
```

### Structured Output

The Reviewer reports its verdict through a `report_security_review` tool (Claude tool use), so the status, findings, and recommendations arrive as structured fields rather than parsed text. A text-parsing fallback remains for responses without a tool call.

### Review Output

```python
{
    "status": "FAIL_SECURITY",
    "finding": "Weak cryptographic algorithm detected: SHA1",
    "severity": "High",
    "vulnerabilities": [
        {
            "type": "WEAK_CRYPTOGRAPHY",
            "description": "hashlib.sha1() is not FIPS-compliant",
            "line": 15
        }
    ],
    "recommendations": [
        "Replace SHA1 with SHA256 or SHA3-512 for FIPS compliance"
    ],
    "memory_informed": True,
    "reflection_applied": True,
    "reflection_confidence": 0.94
}
```

---

## Validator Agent

The Validator Agent performs comprehensive code validation including sandbox testing.

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Syntax Validation** | AST parsing and syntax checking |
| **Structure Validation** | Verify expected elements present |
| **Type Checking** | Validate type hints and annotations |
| **Security Analysis** | Static security scanning |
| **Sandbox Testing** | Runtime validation in isolation |

### Validation Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     VALIDATION PIPELINE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Syntax Validation                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ AST Parsing → Syntax Errors → Line/Column Location  │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                 │
│                    Pass?  ▼  Fail → Stop                    │
│                                                             │
│  Layer 2: Structure Validation                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Expected Elements → Function Count → Class Count    │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                 │
│                    Pass?  ▼  Fail → Continue with warnings  │
│                                                             │
│  Layer 3: Type Validation                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Return Types → Argument Types → Variable Types      │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                 │
│                    Pass?  ▼  Fail → Continue with warnings  │
│                                                             │
│  Layer 4: Security Validation                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Dangerous Patterns → Hardcoded Secrets → Injection  │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                 │
│                    Pass?  ▼  Fail → Stop (blocking)         │
│                                                             │
│  Layer 5: Sandbox Validation (Optional)                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Unit Tests → Integration Tests → Performance Tests  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Dangerous Pattern Detection

```python
dangerous_patterns = [
    (r"\beval\s*\(", "EVAL_USAGE", "Use of eval() is dangerous"),
    (r"\bexec\s*\(", "EXEC_USAGE", "Use of exec() is dangerous"),
    (r"subprocess\.call\([^)]*shell\s*=\s*True", "SHELL_INJECTION", "shell=True is vulnerable"),
    (r"os\.system\s*\(", "OS_SYSTEM", "os.system() is vulnerable"),
    (r"pickle\.loads?\s*\(", "PICKLE_USAGE", "pickle can execute arbitrary code"),
    (r"yaml\.load\s*\([^)]*\)", "YAML_UNSAFE", "Use yaml.safe_load() instead"),
]
```

### Validation Output

```python
{
    "valid": True,
    "syntax_valid": True,
    "structure_valid": True,
    "type_hints_valid": True,
    "security_valid": True,
    "issues": [],
    "warnings": [
        {
            "type": "MISSING_RETURN_TYPE",
            "message": "Function 'process_data' lacks return type annotation",
            "severity": "warning"
        }
    ]
}
```

---

## Monitor Agent

The Monitor Agent tracks system health, performance, and costs.

> **Implementation status.** `MonitorAgent` (`src/agents/monitoring_service.py:19`) is an in-process counter: it records token estimates, lines of code generated, and security findings for one run, and `finalize_report()` returns them in the job result. It does not publish to CloudWatch, track health, or raise alerts. Token counts are fixed per-call estimates (for example 4000 per coder call), and `llm_cost_usd` uses a placeholder rate of 0.0003 per token. The health, alerting, and CloudWatch items below are planned.

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Health Tracking** | Monitor agent availability and status |
| **Performance Metrics** | Track latency, throughput, error rates |
| **Cost Management** | Monitor token usage and compute costs |
| **Alerting** | Trigger alerts for anomalies |

### Tracked Metrics

```python
# Agent Activity
monitor.record_agent_activity(
    tokens_used=4000,
    loc_generated=15,
)

# Security Findings
monitor.record_security_finding(
    agent=AgentRole.REVIEWER,
    finding="Weak cryptographic algorithm",
    severity="High",
    status="Detected"
)

# Run summary returned in the job result
report = monitor.finalize_report()
```

### CloudWatch Integration

Planned: publish these metrics to CloudWatch for monitoring and alerting. The orchestrator does not publish them today:

| Metric Namespace | Metrics |
|------------------|---------|
| `Aura/Agents` | TokensUsed, ExecutionTime, ErrorRate |
| `Aura/Security` | FindingsDetected, SeverityDistribution |
| `Aura/Cost` | TokenCost, ComputeCost, TotalCost |
| `Aura/Health` | AgentAvailability, Latency, QueueDepth |

---

## Agent Communication Patterns

In the production job server the Coder, Reviewer, and Validator are called in-process as Python methods of `System2Orchestrator`; there is no message bus between them. An SQS-based path exists (`dispatch_task_async`, `src/agents/agent_worker.py`, schemas in `src/agents/messaging/`), but it runs only when `use_async_messaging=True`, which no deployed entry point sets, and the agent worker has no deployment manifest. The request/response and event examples below illustrate the planned message shapes; `AgentEvent` broadcasting is not implemented.

### Request/Response Pattern

```python
# Orchestrator requests code generation
request = AgentRequest(
    request_id="req-123",
    source_agent=AgentRole.ORCHESTRATOR,
    target_agent=AgentRole.CODER,
    action="generate_patch",
    payload={
        "vulnerability": vulnerability_data,
        "context": hybrid_context
    }
)

# Coder responds with generated code
response = AgentResponse(
    request_id="req-123",
    source_agent=AgentRole.CODER,
    status="success",
    payload={
        "code": generated_code,
        "confidence": 0.92
    }
)
```

### Event Broadcasting

Agents broadcast events for observability:

```python
# Broadcast security finding
event = AgentEvent(
    event_type="security_finding",
    source_agent=AgentRole.REVIEWER,
    timestamp="2026-01-15T10:30:00Z",
    payload={
        "finding": "SQL Injection detected",
        "severity": "CRITICAL",
        "file": "user_service.py"
    }
)
```

### Agent-to-Agent (A2A) Security

The core agents call each other in-process, so there is no inter-agent network traffic to secure in the job server. Agent inputs are screened by the A2AS injection filter (`enable_a2as=True` by default), which blocks HIGH and CRITICAL threat assessments before planning.

Planned for networked and external agents (the A2A gateway and registry in `src/services/a2a_*` are in-memory stubs whose router is not mounted):

- **Authentication**: JWT-based agent identity verification
- **Authorization**: Role-based permission enforcement
- **Encryption**: TLS 1.3 for all inter-agent communication
- **Audit**: All messages logged for compliance

---

## Agent Memory and Learning

Agents improve over time through shared memory systems.

> **Implementation status.** Titan memory is off in the job server (`ENABLE_TITAN_MEMORY=false` in the orchestrator ConfigMap). When enabled through `create_system2_orchestrator(enable_titan_memory=True)`, the episodic, semantic, and procedural stores and the embedding service are `AsyncMock` placeholders (`src/agents/agent_orchestrator.py`, "Create mock stores for now"), so nothing persists between runs. Human approval decisions are recorded to memory only through `process_approval_decision`, which the approvals API does not call. Persistent cross-run learning is planned.

### Memory Types

| Memory Type | Duration | Use Case |
|-------------|----------|----------|
| **Episodic** | Session | Current workflow context |
| **Semantic** | Persistent | Security policies, patterns |
| **Procedural** | Persistent | Successful remediation sequences |
| **Neural** | Adaptive | Learned patterns from experience |

### Experience Storage

```python
# Store successful remediation
experience = RemediationExperience(
    vulnerability_type="SQL_INJECTION",
    fix_pattern="parameterized_query",
    context_features=extracted_features,
    outcome="success",
    confidence=0.95
)

# Compute surprise (novelty)
surprise = memory.compute_surprise(experience)

# Store if novel
if surprise > MEMORIZATION_THRESHOLD:
    memory.store(experience)
```

### Cross-Agent Learning

Agents share learnings through the Cognitive Memory Service:

```python
# Reviewer learns from Coder patterns
reviewer_context = cognitive_service.load_cognitive_context(
    task="security_review",
    domain="sql_injection",
    include_procedural=True  # Include Coder's fix patterns
)
```

---

## Constitutional AI Integration

Constitutional AI is designed to review agent outputs against explicit safety, compliance, and quality principles.

> **Implementation status.** `ConstitutionalMixin` (`src/agents/constitutional_mixin.py`) exists and is tested, but no agent class in the remediation workflow inherits it: `CoderAgent`, `ReviewerAgent`, and `ValidatorAgent` are plain classes, and `System2Orchestrator` does not call the critique service. Wiring critique-revision into the Coder and Reviewer outputs is planned. The example below shows the intended integration.

### ConstitutionalMixin

Agents integrate Constitutional AI through the `ConstitutionalMixin` class:

```python
class CoderAgent(ConstitutionalMixin, BaseAgent):
    """Coder with Constitutional AI integration."""

    def generate_patch(self, vulnerability, context):
        # Generate raw patch
        raw_patch = self._generate_raw_patch(vulnerability, context)

        # Apply Constitutional AI critique-revision
        result = self.process_with_constitutional(
            output=raw_patch,
            context=ConstitutionalContext(
                domain_tags=["code_generation", "security"],
                severity_threshold="high"
            )
        )

        return result.final_output
```

### Agent-Specific Principle Sets

Each agent type has domain tags that determine which principles apply:

| Agent | Domain Tags | Primary Principles |
|-------|-------------|-------------------|
| **Coder Agent** | `code_generation`, `security` | Security-First, Minimal Change, Pattern Consistency |
| **Reviewer Agent** | `review`, `analysis` | Independent Judgment, Constructive Pushback, Uncertainty Expression |
| **Security Agent** | `security`, `compliance` | Regulatory Alignment, Audit Trail, Non-Destructive Defaults |
| **Validator Agent** | `validation`, `testing` | Sandbox Containment, Reasoning Chain |

### Critique-Revision Flow

```
Agent Output
     │
     ▼
┌─────────────────────────────────────┐
│         CRITIQUE PHASE              │
│                                     │
│  Evaluate against applicable        │
│  principles (filtered by domain)    │
│                                     │
│  Model: Claude Haiku (fast)         │
└─────────────────────────────────────┘
     │
     ├── No Issues ──▶ Pass through
     │
     ▼
┌─────────────────────────────────────┐
│         REVISION PHASE              │
│                                     │
│  Revise output to address           │
│  identified principle violations    │
│                                     │
│  Model: Claude Sonnet (capable)     │
└─────────────────────────────────────┘
     │
     ▼
Revised Output (with audit trail)
```

### Benefits

- **Consistent behavior**: All agents follow the same constitutional principles
- **Transparent decisions**: Critique reasoning is logged for audit
- **Graceful handling**: Issues are revised, not just blocked
- **Cost-efficient**: Haiku for critique, Sonnet only when revision needed

[Learn more about Constitutional AI](./constitutional-ai.md)

---

## Key Takeaways

> **Specialized agents outperform monolithic models.** Each agent is optimized for its specific task, resulting in better overall performance.

> **Agents validate each other's work.** The Reviewer checks the Coder's output and the Validator statically checks the reviewed patch; failures from either are fed back to the Coder.

> **Constitutional AI is planned for agent outputs.** The mixin exists; the remediation agents do not use it yet.

> **Agent results are structured.** Each run returns the review, validation, sandbox status, and metrics in the job result; approval decisions are written to the HITL audit log.

> **Memory is designed for continuous improvement.** Neural memory guidance reaches the Coder and Reviewer prompts when a memory service is configured; persistent memory stores are planned.

---

## Related Concepts

- [Autonomous Security Intelligence](./autonomous-security-intelligence.md) - AI foundations
- [Hybrid GraphRAG](./hybrid-graphrag.md) - Context retrieval for agents
- [Constitutional AI](./constitutional-ai.md) - Principled AI safety and alignment
- [HITL Workflows](./hitl-workflows.md) - Human oversight of agent decisions
- [Sandbox Security](./sandbox-security.md) - Validator Agent sandbox testing

---

## Technical References

- ADR-018: MetaOrchestrator Dynamic Agent Spawning
- ADR-029: Agent Optimization Strategies (CoD, Self-Reflection)
- ADR-037: AWS Agent Parity (27 services)
- ADR-063: Constitutional AI Integration
