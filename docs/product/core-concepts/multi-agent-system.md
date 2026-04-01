# Multi-Agent System

**Version:** 1.0
**Last Updated:** January 2026

---

## Overview

Project Aura uses a multi-agent architecture where specialized AI agents collaborate to detect, remediate, and validate security vulnerabilities. Rather than relying on a single monolithic AI model, Aura orchestrates multiple purpose-built agents that work together like a security engineering team.

This document explains the agent architecture, individual agent responsibilities, communication patterns, and how agents learn from their experiences.

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

![Multi-Agent Architecture](../images/placeholder-agent-architecture.png)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AGENT ORCHESTRATOR                           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Workflow State Machine                    │    │
│  │                                                              │    │
│  │  INIT → PLANNING → CONTEXT → CODE_GEN → REVIEW → VALIDATE   │    │
│  │                                                    ↓         │    │
│  │                                              REMEDIATION     │    │
│  │                                                    ↓         │    │
│  │                                               COMPLETED      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Context Retrieval Service                 │  │
│  │  (Hybrid GraphRAG: Neptune + OpenSearch + Three-Way Fusion)   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
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
    INIT = "init"                    # Initialize workflow
    PLANNING = "planning"            # Analyze task requirements
    MEMORY_LOAD = "memory_load"      # Load relevant memories
    CONTEXT_RETRIEVAL = "context"    # Retrieve code context
    CODE_GENERATION = "code_gen"     # Generate patch
    SECURITY_REVIEW = "review"       # Security validation
    VALIDATION = "validation"        # Sandbox testing
    REMEDIATION = "remediation"      # Apply fixes
    MEMORY_STORE = "memory_store"    # Store learnings
    COMPLETED = "completed"          # Success
    FAILED = "failed"                # Failure
```

### Checkpoint and Resume

Long-running workflows can be interrupted and resumed:

```python
# Checkpoint captures workflow state
checkpoint = AgentCheckpoint(
    workflow_id="wf-123456",
    phase=WorkflowPhase.SECURITY_REVIEW,
    created_at="2026-01-15T10:30:00Z",
    context={
        "vulnerability_id": "vuln-789",
        "generated_patch": "...",
        "coder_confidence": 0.85
    }
)

# Later, resume from checkpoint
orchestrator.resume_from_checkpoint(checkpoint)
```

---

## Coder Agent

The Coder Agent generates security patches based on vulnerability information and code context.

### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Patch Generation** | Create fixes for identified vulnerabilities |
| **Code Synthesis** | Generate new code following security patterns |
| **Context Integration** | Incorporate structural and semantic context |
| **Confidence Scoring** | Assess quality of generated patches |

### Input/Output

**Input:**
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

**Output:**
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

The Coder Agent leverages past experiences:

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
        "patterns": ["password=", "api_key=", "secret=", "token="],
        "message": "Hardcoded secrets detected - use Secrets Manager"
    },
    "injection": {
        "patterns": ["eval(", "exec(", "subprocess.call(", "shell=True"],
        "message": "Potential code injection vulnerability"
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
    # 30% fewer false positives with self-reflection
```

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
│                     VALIDATION PIPELINE                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: Syntax Validation                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ AST Parsing → Syntax Errors → Line/Column Location  │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                    Pass?  ▼  Fail → Stop                    │
│                                                              │
│  Layer 2: Structure Validation                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Expected Elements → Function Count → Class Count    │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                    Pass?  ▼  Fail → Continue with warnings  │
│                                                              │
│  Layer 3: Type Validation                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Return Types → Argument Types → Variable Types      │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                    Pass?  ▼  Fail → Continue with warnings  │
│                                                              │
│  Layer 4: Security Validation                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Dangerous Patterns → Hardcoded Secrets → Injection  │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                    Pass?  ▼  Fail → Stop (blocking)         │
│                                                              │
│  Layer 5: Sandbox Validation (Optional)                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Unit Tests → Integration Tests → Performance Tests  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
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
    execution_time_ms=2500
)

# Security Findings
monitor.record_security_finding(
    agent=AgentRole.REVIEWER,
    finding="Weak cryptographic algorithm",
    severity="High",
    status="Detected"
)

# System Health
monitor.record_health_check(
    agent=AgentRole.CODER,
    status="healthy",
    latency_ms=45
)
```

### CloudWatch Integration

Metrics are published to CloudWatch for monitoring and alerting:

| Metric Namespace | Metrics |
|------------------|---------|
| `Aura/Agents` | TokensUsed, ExecutionTime, ErrorRate |
| `Aura/Security` | FindingsDetected, SeverityDistribution |
| `Aura/Cost` | TokenCost, ComputeCost, TotalCost |
| `Aura/Health` | AgentAvailability, Latency, QueueDepth |

---

## Agent Communication Patterns

Agents communicate through structured message passing.

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

All agent communication is secured:

- **Authentication**: JWT-based agent identity verification
- **Authorization**: Role-based permission enforcement
- **Encryption**: TLS 1.3 for all inter-agent communication
- **Audit**: All messages logged for compliance

---

## Agent Memory and Learning

Agents improve over time through shared memory systems.

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

All agent outputs pass through Constitutional AI before reaching users or downstream systems. This ensures outputs align with explicit safety, compliance, and quality principles.

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

> **Agents validate each other's work.** The Reviewer checks the Coder's output; the Validator tests the Reviewer's conclusions.

> **Constitutional AI ensures principled behavior.** All agent outputs pass through critique-revision before reaching users.

> **Communication is structured and auditable.** All agent interactions are logged and can be traced for compliance.

> **Memory enables continuous improvement.** Agents learn from every remediation and share knowledge across the system.

---

## Related Concepts

- [Autonomous Code Intelligence](./autonomous-code-intelligence.md) - AI foundations
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
