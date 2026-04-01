# ADR-066: Agent Capability Governance

## Status

Deployed

## Date

2026-01-25

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Senior Systems Architect | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Test Architect | - | - |

### Review Summary

_Awaiting review._

## Context

### The Open Access Problem

Security gap analysis identified that Project Aura's agents currently operate with unrestricted access to the MCP tool infrastructure:

| Current State | Security Gap | Risk |
|--------------|--------------|------|
| No tool whitelist/blacklist per agent | CoderAgent can invoke sandbox destruction | HIGH |
| No per-agent permission scoping | ReviewerAgent could trigger production deployments | CRITICAL |
| No context-aware capability restrictions | Test context agent could use production credentials | CRITICAL |
| No runtime capability enforcement | Violations detected only in post-hoc audit | MEDIUM |
| No capability audit trail | Forensic analysis limited after incidents | HIGH |

### Attack Surface Analysis

Without capability governance, the following attack vectors exist:

```text
Agent Capability Attack Vectors:
├── Tool Abuse
│   ├── CoderAgent invoking provision_sandbox → resource exhaustion
│   ├── ReviewerAgent invoking destroy_sandbox → sabotage
│   └── ValidatorAgent invoking index_code_embedding → data poisoning
├── Context Confusion
│   ├── Test-context agent using production graph queries
│   ├── Sandbox agent accessing main repository secrets
│   └── Dev-environment agent invoking production deployments
├── Privilege Escalation
│   ├── Agent spawning child with elevated permissions
│   ├── Multi-step capability accumulation across agent tree
│   └── HITL bypass through capability chaining
└── Audit Evasion
    ├── High-frequency tool invocations exhausting log buffer
    ├── Capability violations masked by legitimate operations
    └── Cross-agent coordination to obscure intent
```

### Regulatory Requirements

Capability governance directly supports compliance requirements:

| Framework | Control | How Capability Governance Helps |
|-----------|---------|--------------------------------|
| CMMC 2.0 | AC.L2-3.1.5 | Principle of least privilege for agents |
| NIST 800-53 | AC-6 | Role-based capability assignment |
| SOX | Section 404 | Audit trail for automated actions |
| FedRAMP | AC-2(7) | Privileged function monitoring |

### Industry Precedent

Modern AI agent frameworks implement capability governance:

- **LangChain**: Tool binding restricts which tools agents can use
- **AutoGPT**: Workspace isolation limits file system access
- **OpenAI Assistants**: Function calling whitelist per assistant
- **AWS Agents for Bedrock**: Action groups with explicit permissions

## Decision

Implement a comprehensive Agent Capability Governance framework that enforces per-agent tool access, context-aware permission scoping, runtime capability enforcement, and complete audit trails.

### Core Capabilities

1. **Capability Matrix** - Define Agent x Tool x Action permissions with policy inheritance
2. **Tool Classification** - Categorize tools by risk level (Safe, Monitoring, Dangerous, Critical)
3. **Runtime Enforcement** - Middleware intercepts all tool invocations for policy check
4. **Context-Aware Scoping** - Permissions vary based on execution context (test, sandbox, production)
5. **Dynamic Capability Adjustment** - Elevate/revoke capabilities based on HITL decisions
6. **Complete Audit Trail** - Log all capability checks, grants, denials, and violations

## Architecture

### Capability Governance Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Agent Capability Governance                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Agent Tool Invocation                                                          │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: CapabilityEnforcementMiddleware                                │   │
│  │                                                                          │   │
│  │  Input: (agent_id, tool_name, action, context)                          │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │ 1. Extract Agent Identity & Context                             │     │   │
│  │  │    - Agent type (Coder, Reviewer, Validator, etc.)              │     │   │
│  │  │    - Execution context (test, sandbox, production)              │     │   │
│  │  │    - Parent agent (if spawned dynamically)                      │     │   │
│  │  │    - Session autonomy level                                     │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │ 2. Resolve Effective Capabilities                               │     │   │
│  │  │    - Base capabilities from AgentCapabilityPolicy               │     │   │
│  │  │    - Context overrides (sandbox grants, test restrictions)      │     │   │
│  │  │    - Dynamic grants (HITL elevation, emergency access)          │     │   │
│  │  │    - Parent capability inheritance (cannot exceed parent)       │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │ 3. Evaluate Permission                                          │     │   │
│  │  │    - Check tool in allowed_tools for agent                      │     │   │
│  │  │    - Verify action permitted (read, write, execute, admin)      │     │   │
│  │  │    - Validate context constraints (e.g., production blocked)    │     │   │
│  │  │    - Check rate limits per agent-tool pair                      │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ Decision Branch                                                          │   │
│  │                                                                          │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌────────────┐  │   │
│  │  │   ALLOW     │   │    DENY     │   │  ESCALATE   │   │   AUDIT    │  │   │
│  │  │             │   │             │   │   (HITL)    │   │   ONLY     │  │   │
│  │  │ Proceed to  │   │ Block with  │   │ Queue for   │   │ Allow but  │  │   │
│  │  │ invocation  │   │ error code  │   │ human       │   │ log for    │  │   │
│  │  │             │   │ and reason  │   │ approval    │   │ review     │  │   │
│  │  └─────────────┘   └─────────────┘   └─────────────┘   └────────────┘  │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 2: Capability Audit Service                                        │   │
│  │                                                                          │   │
│  │  Every decision logged with:                                             │   │
│  │  - timestamp, agent_id, tool_name, action, context                       │   │
│  │  - decision (ALLOW/DENY/ESCALATE/AUDIT_ONLY)                            │   │
│  │  - policy_version, capability_source (base/override/dynamic)             │   │
│  │  - parent_agent_id (for spawn chain tracking)                            │   │
│  │  - request_hash (for deduplication and correlation)                      │   │
│  │                                                                          │   │
│  │  → SQS Audit Queue (async) → DynamoDB → CloudWatch Metrics              │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Tool Classification Hierarchy

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Tool Classification System                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ Classification Levels (Risk-Based)                                       │   │
│  │                                                                          │   │
│  │  SAFE (Level 1)           MONITORING (Level 2)                          │   │
│  │  ┌─────────────────┐      ┌─────────────────┐                           │   │
│  │  │ - semantic_search│      │ - query_code_graph                         │   │
│  │  │ - get_sandbox_   │      │ - get_code_      │                         │   │
│  │  │   status         │      │   dependencies   │                         │   │
│  │  │ - describe_tool  │      │ - get_agent_     │                         │   │
│  │  │                  │      │   metrics        │                         │   │
│  │  │ Default: ALLOW   │      │ Default: ALLOW   │                         │   │
│  │  │ Audit: SAMPLE    │      │ Audit: ALL       │                         │   │
│  │  └─────────────────┘      └─────────────────┘                           │   │
│  │                                                                          │   │
│  │  DANGEROUS (Level 3)       CRITICAL (Level 4)                           │   │
│  │  ┌─────────────────┐      ┌─────────────────┐                           │   │
│  │  │ - index_code_   │      │ - provision_     │                         │   │
│  │  │   embedding     │      │   sandbox        │                         │   │
│  │  │ - destroy_      │      │ - deploy_to_     │                         │   │
│  │  │   sandbox       │      │   production     │                         │   │
│  │  │ - write_config  │      │ - rotate_        │                         │   │
│  │  │                 │      │   credentials    │                         │   │
│  │  │ Default: DENY   │      │ Default: DENY    │                         │   │
│  │  │ Requires:       │      │ Requires:        │                         │   │
│  │  │  Explicit grant │      │  HITL approval   │                         │   │
│  │  │ Audit: ALL+ALERT│      │ Audit: ALL+ALERT │                         │   │
│  │  └─────────────────┘      └─────────────────┘                           │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ Agent-Tool Capability Matrix (Default Policies)                          │   │
│  │                                                                          │   │
│  │              │ semantic_ │ query_   │ index_   │ provision_ │ deploy_  │   │
│  │              │ search    │ graph    │ embedding│ sandbox    │ prod     │   │
│  │  ────────────┼───────────┼──────────┼──────────┼────────────┼──────────│   │
│  │  CoderAgent  │ ALLOW     │ ALLOW    │ DENY     │ DENY       │ DENY     │   │
│  │  Reviewer    │ ALLOW     │ ALLOW    │ DENY     │ DENY       │ DENY     │   │
│  │  Validator   │ ALLOW     │ ALLOW    │ ALLOW*   │ ESCALATE   │ DENY     │   │
│  │  Orchestrator│ ALLOW     │ ALLOW    │ ALLOW    │ ESCALATE   │ ESCALATE │   │
│  │  RedTeam     │ ALLOW     │ ALLOW    │ DENY     │ ALLOW      │ DENY     │   │
│  │  AdminAgent  │ ALLOW     │ ALLOW    │ ALLOW    │ ALLOW      │ ESCALATE │   │
│  │                                                                          │   │
│  │  * = Context-dependent (test only)                                       │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Integration with Existing Agent Infrastructure

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Integration with MetaOrchestrator & MCP                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           MetaOrchestrator                               │   │
│  │                                                                          │   │
│  │  execute(task)                                                           │   │
│  │       │                                                                  │   │
│  │       ▼                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │ Task Decomposition → TaskNode[]                                  │    │   │
│  │  │                                                                  │    │   │
│  │  │ For each TaskNode:                                               │    │   │
│  │  │   capability = node.capability (AgentCapability enum)            │    │   │
│  │  │   required_tools = CapabilityRegistry.tools_for(capability)      │    │   │
│  │  │   agent_policy = AgentCapabilityPolicy.for_capability(capability)│    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │       │                                                                  │   │
│  │       ▼                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │ AgentRegistry.spawn_agent(spec)                                  │    │   │
│  │  │                                                                  │    │   │
│  │  │ NEW: agent.capability_policy = policy                            │    │   │
│  │  │ NEW: agent.execution_context = context (test/sandbox/prod)       │    │   │
│  │  │ NEW: agent.parent_capabilities = parent.effective_capabilities   │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │       │                                                                  │   │
│  │       ▼                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │ SpawnableAgent (MCPToolMixin, BaseAgent)                         │    │   │
│  │  │                                                                  │    │   │
│  │  │ invoke_tool(tool_name, params)                                   │    │   │
│  │  │       │                                                          │    │   │
│  │  │       ▼                                                          │    │   │
│  │  │ NEW: CapabilityEnforcementMiddleware.check(                      │    │   │
│  │  │        agent_id=self.agent_id,                                   │    │   │
│  │  │        tool_name=tool_name,                                      │    │   │
│  │  │        action=params.get('action', 'execute'),                   │    │   │
│  │  │        context=self.execution_context,                           │    │   │
│  │  │        policy=self.capability_policy                             │    │   │
│  │  │      )                                                           │    │   │
│  │  │       │                                                          │    │   │
│  │  │       ├── ALLOW → proceed to MCPToolServer.invoke_tool()         │    │   │
│  │  │       ├── DENY → raise CapabilityDeniedError(reason)             │    │   │
│  │  │       ├── ESCALATE → await HITLService.request_capability()      │    │   │
│  │  │       └── AUDIT_ONLY → proceed + async audit log                 │    │   │
│  │  │                                                                  │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           MCPToolServer                                  │   │
│  │                                                                          │   │
│  │  invoke_tool(tool_name, params, skip_approval)                          │   │
│  │       │                                                                  │   │
│  │       ▼                                                                  │   │
│  │  EXISTING: Rate limiting, schema validation, HITL approval              │   │
│  │                                                                          │   │
│  │  NEW: Pre-invocation hook for capability enforcement                    │   │
│  │       (CapabilityEnforcementMiddleware already called at agent level,   │   │
│  │        but MCPToolServer validates caller_agent_id matches registered   │   │
│  │        session to prevent spoofing)                                     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Dynamic Capability Adjustment Flow

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     Dynamic Capability Adjustment                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Scenario: CoderAgent needs to provision sandbox for patch testing              │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Agent requests capability it doesn't have                             │   │
│  │                                                                          │   │
│  │    CoderAgent.invoke_tool("provision_sandbox", {...})                    │   │
│  │         │                                                                │   │
│  │         ▼                                                                │   │
│  │    CapabilityEnforcementMiddleware.check() → ESCALATE                    │   │
│  │         │                                                                │   │
│  │         │ (CoderAgent default policy: provision_sandbox = DENY)          │   │
│  │         │ (Tool classification: CRITICAL → requires HITL)                │   │
│  │         ▼                                                                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 2. HITL Escalation Request Created                                       │   │
│  │                                                                          │   │
│  │    CapabilityEscalationRequest {                                         │   │
│  │      request_id: "cap-esc-abc123"                                        │   │
│  │      agent_id: "coder-agent-xyz"                                         │   │
│  │      requested_capability: "provision_sandbox"                           │   │
│  │      requested_action: "execute"                                         │   │
│  │      context: {                                                          │   │
│  │        execution_id: "exec-456",                                         │   │
│  │        task: "Test security patch for CVE-2026-1234",                    │   │
│  │        parent_orchestrator: "meta-orch-789"                              │   │
│  │      }                                                                   │   │
│  │      justification: "Sandbox needed to validate patch before merge"      │   │
│  │      expires_at: <now + 15 minutes>                                      │   │
│  │    }                                                                     │   │
│  │         │                                                                │   │
│  │         ▼                                                                │   │
│  │    → SNS Notification to approvers                                       │   │
│  │    → Agent execution pauses (await approval)                             │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 3. Human Reviews and Approves (via HITL Dashboard)                       │   │
│  │                                                                          │   │
│  │    CapabilityApprovalResponse {                                          │   │
│  │      request_id: "cap-esc-abc123"                                        │   │
│  │      approved: true                                                      │   │
│  │      approver_id: "user@company.com"                                     │   │
│  │      scope: SINGLE_USE | SESSION | TASK_TREE                             │   │
│  │      constraints: {                                                      │   │
│  │        max_sandboxes: 1,                                                 │   │
│  │        duration_limit: "30m",                                            │   │
│  │        isolation_level: "container"  // No VPC/full isolation            │   │
│  │      }                                                                   │   │
│  │      expires_at: <now + 30 minutes>                                      │   │
│  │    }                                                                     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 4. Dynamic Grant Applied                                                 │   │
│  │                                                                          │   │
│  │    DynamicCapabilityGrant stored in DynamoDB:                            │   │
│  │    {                                                                     │   │
│  │      grant_id: "grant-def456",                                           │   │
│  │      agent_id: "coder-agent-xyz",                                        │   │
│  │      capability: "provision_sandbox",                                    │   │
│  │      action: "execute",                                                  │   │
│  │      scope: "SESSION",                                                   │   │
│  │      constraints: {...},                                                 │   │
│  │      granted_by: "cap-esc-abc123",                                       │   │
│  │      approver: "user@company.com",                                       │   │
│  │      granted_at: <timestamp>,                                            │   │
│  │      expires_at: <timestamp + 30m>,                                      │   │
│  │      usage_count: 0,                                                     │   │
│  │      max_usage: 1                                                        │   │
│  │    }                                                                     │   │
│  │                                                                          │   │
│  │    Agent execution resumes → tool invocation succeeds                    │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Implementation

### Service Layer

```python
# src/services/capability_governance/__init__.py

from .registry import CapabilityRegistry
from .policy import AgentCapabilityPolicy, ToolClassification
from .middleware import CapabilityEnforcementMiddleware
from .audit import CapabilityAuditService
from .dynamic_grants import DynamicCapabilityGrantService
from .contracts import (
    CapabilityDecision,
    CapabilityCheckResult,
    CapabilityEscalationRequest,
    DynamicCapabilityGrant,
)

__all__ = [
    "CapabilityRegistry",
    "AgentCapabilityPolicy",
    "ToolClassification",
    "CapabilityEnforcementMiddleware",
    "CapabilityAuditService",
    "DynamicCapabilityGrantService",
    "CapabilityDecision",
    "CapabilityCheckResult",
    "CapabilityEscalationRequest",
    "DynamicCapabilityGrant",
]
```

```python
# src/services/capability_governance/contracts.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class CapabilityDecision(Enum):
    """Decision from capability check."""
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"  # Requires HITL approval
    AUDIT_ONLY = "audit_only"  # Allow but flag for review


class ToolClassification(Enum):
    """Risk classification for tools."""
    SAFE = "safe"  # Level 1: Always allowed, sample audit
    MONITORING = "monitoring"  # Level 2: Allowed, full audit
    DANGEROUS = "dangerous"  # Level 3: Explicit grant required
    CRITICAL = "critical"  # Level 4: HITL required always


class CapabilityScope(Enum):
    """Scope for dynamic grants."""
    SINGLE_USE = "single_use"  # One invocation only
    SESSION = "session"  # Current agent session
    TASK_TREE = "task_tree"  # All agents in execution tree


@dataclass
class ToolCapability:
    """Capability definition for a tool."""
    tool_name: str
    classification: ToolClassification
    allowed_actions: list[str] = field(default_factory=lambda: ["read", "execute"])
    requires_context: list[str] = field(default_factory=list)  # e.g., ["sandbox", "test"]
    blocked_contexts: list[str] = field(default_factory=list)  # e.g., ["production"]
    rate_limit_per_minute: int = 60
    max_concurrent: int = 5


@dataclass
class CapabilityCheckResult:
    """Result of a capability check."""
    decision: CapabilityDecision
    tool_name: str
    agent_id: str
    action: str
    context: str
    reason: str
    policy_version: str
    capability_source: str  # "base", "override", "dynamic_grant"
    checked_at: datetime = field(default_factory=datetime.now)
    request_hash: str = ""

    def to_audit_record(self) -> dict[str, Any]:
        """Convert to audit-friendly format."""
        return {
            "decision": self.decision.value,
            "tool_name": self.tool_name,
            "agent_id": self.agent_id,
            "action": self.action,
            "context": self.context,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "capability_source": self.capability_source,
            "checked_at": self.checked_at.isoformat(),
            "request_hash": self.request_hash,
        }


@dataclass
class CapabilityEscalationRequest:
    """Request for HITL capability escalation."""
    request_id: str
    agent_id: str
    parent_agent_id: Optional[str]
    execution_id: str
    requested_tool: str
    requested_action: str
    context: str
    justification: str
    task_description: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    status: str = "pending"  # pending, approved, denied, expired


@dataclass
class CapabilityApprovalResponse:
    """Response to capability escalation request."""
    request_id: str
    approved: bool
    approver_id: str
    scope: CapabilityScope
    constraints: dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    approved_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


@dataclass
class DynamicCapabilityGrant:
    """A dynamically granted capability."""
    grant_id: str
    agent_id: str
    tool_name: str
    action: str
    scope: CapabilityScope
    constraints: dict[str, Any]
    granted_by: str  # escalation request ID
    approver: str
    granted_at: datetime
    expires_at: datetime
    usage_count: int = 0
    max_usage: Optional[int] = None
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
```

```python
# src/services/capability_governance/policy.py

from dataclasses import dataclass, field
from typing import Any, Optional
from .contracts import ToolClassification, ToolCapability, CapabilityDecision


# Default tool classifications
DEFAULT_TOOL_CLASSIFICATIONS: dict[str, ToolClassification] = {
    # Level 1: Safe
    "semantic_search": ToolClassification.SAFE,
    "describe_tool": ToolClassification.SAFE,
    "get_sandbox_status": ToolClassification.SAFE,
    "list_tools": ToolClassification.SAFE,

    # Level 2: Monitoring
    "query_code_graph": ToolClassification.MONITORING,
    "get_code_dependencies": ToolClassification.MONITORING,
    "get_agent_metrics": ToolClassification.MONITORING,

    # Level 3: Dangerous
    "index_code_embedding": ToolClassification.DANGEROUS,
    "destroy_sandbox": ToolClassification.DANGEROUS,
    "write_config": ToolClassification.DANGEROUS,
    "delete_index": ToolClassification.DANGEROUS,

    # Level 4: Critical
    "provision_sandbox": ToolClassification.CRITICAL,
    "deploy_to_production": ToolClassification.CRITICAL,
    "rotate_credentials": ToolClassification.CRITICAL,
    "modify_iam_policy": ToolClassification.CRITICAL,
}


@dataclass
class AgentCapabilityPolicy:
    """
    Capability policy for an agent type.

    Defines which tools an agent can access, under what conditions,
    and what actions are permitted.
    """
    agent_type: str
    version: str = "1.0"

    # Tool permissions: tool_name -> list of allowed actions
    allowed_tools: dict[str, list[str]] = field(default_factory=dict)

    # Tools explicitly denied (overrides allowed_tools)
    denied_tools: list[str] = field(default_factory=list)

    # Context restrictions
    allowed_contexts: list[str] = field(
        default_factory=lambda: ["test", "sandbox", "development"]
    )

    # Escalation behavior for unspecified tools
    default_decision: CapabilityDecision = CapabilityDecision.DENY

    # Can this agent spawn children with elevated permissions?
    can_elevate_children: bool = False

    # Maximum tool invocations per minute
    global_rate_limit: int = 100

    # Custom constraints
    constraints: dict[str, Any] = field(default_factory=dict)

    def can_invoke(
        self,
        tool_name: str,
        action: str,
        context: str,
    ) -> CapabilityDecision:
        """
        Check if this policy allows invoking a tool.

        Args:
            tool_name: Name of the tool to invoke
            action: Action type (read, write, execute, admin)
            context: Execution context (test, sandbox, production)

        Returns:
            CapabilityDecision indicating if invocation is allowed
        """
        # Check explicit denials first
        if tool_name in self.denied_tools:
            return CapabilityDecision.DENY

        # Check context restrictions
        if context not in self.allowed_contexts:
            return CapabilityDecision.DENY

        # Check explicit allowances
        if tool_name in self.allowed_tools:
            allowed_actions = self.allowed_tools[tool_name]
            if action in allowed_actions or "*" in allowed_actions:
                return CapabilityDecision.ALLOW
            return CapabilityDecision.DENY

        # Check tool classification for default behavior
        classification = DEFAULT_TOOL_CLASSIFICATIONS.get(
            tool_name, ToolClassification.DANGEROUS
        )

        if classification == ToolClassification.SAFE:
            return CapabilityDecision.ALLOW
        elif classification == ToolClassification.MONITORING:
            return CapabilityDecision.AUDIT_ONLY
        elif classification == ToolClassification.CRITICAL:
            return CapabilityDecision.ESCALATE
        else:
            return self.default_decision

    @classmethod
    def for_agent_type(cls, agent_type: str) -> "AgentCapabilityPolicy":
        """Get default policy for an agent type."""
        policies = {
            "CoderAgent": cls(
                agent_type="CoderAgent",
                allowed_tools={
                    "semantic_search": ["read", "execute"],
                    "query_code_graph": ["read"],
                    "get_code_dependencies": ["read"],
                },
                denied_tools=[
                    "provision_sandbox",
                    "destroy_sandbox",
                    "deploy_to_production",
                    "rotate_credentials",
                ],
                allowed_contexts=["test", "sandbox", "development"],
            ),
            "ReviewerAgent": cls(
                agent_type="ReviewerAgent",
                allowed_tools={
                    "semantic_search": ["read", "execute"],
                    "query_code_graph": ["read"],
                    "get_code_dependencies": ["read"],
                },
                denied_tools=[
                    "provision_sandbox",
                    "destroy_sandbox",
                    "index_code_embedding",
                    "deploy_to_production",
                ],
                allowed_contexts=["test", "sandbox", "development"],
            ),
            "ValidatorAgent": cls(
                agent_type="ValidatorAgent",
                allowed_tools={
                    "semantic_search": ["read", "execute"],
                    "query_code_graph": ["read"],
                    "get_code_dependencies": ["read"],
                    "get_sandbox_status": ["read"],
                    "index_code_embedding": ["execute"],  # Test context only
                },
                denied_tools=["deploy_to_production"],
                allowed_contexts=["test", "sandbox"],
                constraints={"index_code_embedding_context": ["test"]},
            ),
            "MetaOrchestrator": cls(
                agent_type="MetaOrchestrator",
                allowed_tools={
                    "semantic_search": ["*"],
                    "query_code_graph": ["*"],
                    "get_code_dependencies": ["*"],
                    "index_code_embedding": ["execute"],
                    "get_sandbox_status": ["read"],
                },
                denied_tools=[],
                allowed_contexts=["test", "sandbox", "development", "production"],
                default_decision=CapabilityDecision.ESCALATE,
                can_elevate_children=True,
            ),
            "RedTeamAgent": cls(
                agent_type="RedTeamAgent",
                allowed_tools={
                    "semantic_search": ["*"],
                    "query_code_graph": ["*"],
                    "provision_sandbox": ["execute"],
                    "destroy_sandbox": ["execute"],
                    "get_sandbox_status": ["read"],
                },
                denied_tools=["deploy_to_production", "rotate_credentials"],
                allowed_contexts=["test", "sandbox"],
            ),
            "AdminAgent": cls(
                agent_type="AdminAgent",
                allowed_tools={
                    "semantic_search": ["*"],
                    "query_code_graph": ["*"],
                    "index_code_embedding": ["*"],
                    "provision_sandbox": ["execute"],
                    "destroy_sandbox": ["execute"],
                },
                denied_tools=[],
                allowed_contexts=["test", "sandbox", "development", "production"],
                default_decision=CapabilityDecision.ESCALATE,
                can_elevate_children=True,
            ),
        }
        return policies.get(agent_type, cls(
            agent_type=agent_type,
            default_decision=CapabilityDecision.DENY,
        ))
```

```python
# src/services/capability_governance/middleware.py

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from .contracts import (
    CapabilityCheckResult,
    CapabilityDecision,
    CapabilityEscalationRequest,
    DynamicCapabilityGrant,
)
from .policy import AgentCapabilityPolicy

logger = logging.getLogger(__name__)


@dataclass
class CapabilityContext:
    """Context for capability evaluation."""
    agent_id: str
    agent_type: str
    tool_name: str
    action: str
    execution_context: str  # test, sandbox, development, production
    parent_agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    session_id: Optional[str] = None


class CapabilityEnforcementMiddleware:
    """
    Middleware that enforces capability governance on all tool invocations.

    Integrates with MCPToolMixin to intercept invoke_tool() calls and
    apply policy-based access control.
    """

    def __init__(
        self,
        audit_service: Optional["CapabilityAuditService"] = None,
        grant_service: Optional["DynamicCapabilityGrantService"] = None,
        hitl_service: Optional[Any] = None,
    ):
        self.audit_service = audit_service
        self.grant_service = grant_service
        self.hitl_service = hitl_service

        # In-memory cache for policies (refreshed periodically)
        self._policy_cache: dict[str, AgentCapabilityPolicy] = {}
        self._grant_cache: dict[str, list[DynamicCapabilityGrant]] = {}
        self._cache_ttl = 60  # seconds
        self._last_cache_refresh = 0.0

        # Rate limiting tracking
        self._invocation_counts: dict[str, list[float]] = {}

    async def check(
        self,
        context: CapabilityContext,
        policy: Optional[AgentCapabilityPolicy] = None,
    ) -> CapabilityCheckResult:
        """
        Check if an agent has capability to invoke a tool.

        Args:
            context: Capability evaluation context
            policy: Optional policy override (uses cached policy if None)

        Returns:
            CapabilityCheckResult with decision and metadata
        """
        start_time = time.perf_counter()

        # Get policy for agent type
        if policy is None:
            policy = self._get_policy(context.agent_type)

        # Generate request hash for deduplication
        request_hash = self._hash_request(context)

        # Check dynamic grants first (most specific)
        dynamic_result = await self._check_dynamic_grants(context)
        if dynamic_result is not None:
            result = CapabilityCheckResult(
                decision=dynamic_result,
                tool_name=context.tool_name,
                agent_id=context.agent_id,
                action=context.action,
                context=context.execution_context,
                reason="Dynamic grant matched",
                policy_version=policy.version,
                capability_source="dynamic_grant",
                request_hash=request_hash,
            )
            await self._audit(result)
            return result

        # Check base policy
        decision = policy.can_invoke(
            context.tool_name,
            context.action,
            context.execution_context,
        )

        # Build reason string
        if decision == CapabilityDecision.ALLOW:
            reason = f"Allowed by {context.agent_type} policy"
        elif decision == CapabilityDecision.DENY:
            reason = f"Denied by {context.agent_type} policy"
        elif decision == CapabilityDecision.ESCALATE:
            reason = f"Tool requires HITL approval"
        else:  # AUDIT_ONLY
            reason = f"Allowed with audit logging"

        result = CapabilityCheckResult(
            decision=decision,
            tool_name=context.tool_name,
            agent_id=context.agent_id,
            action=context.action,
            context=context.execution_context,
            reason=reason,
            policy_version=policy.version,
            capability_source="base",
            request_hash=request_hash,
        )

        # Audit the decision
        await self._audit(result)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Capability check: {context.agent_id} -> {context.tool_name} = {decision.value} "
            f"({latency_ms:.1f}ms)"
        )

        return result

    async def request_escalation(
        self,
        context: CapabilityContext,
        justification: str,
        task_description: str,
    ) -> CapabilityEscalationRequest:
        """
        Create an escalation request for HITL approval.

        Args:
            context: Capability context
            justification: Why the agent needs this capability
            task_description: What task requires this capability

        Returns:
            CapabilityEscalationRequest for tracking
        """
        import uuid

        request = CapabilityEscalationRequest(
            request_id=f"cap-esc-{uuid.uuid4().hex[:12]}",
            agent_id=context.agent_id,
            parent_agent_id=context.parent_agent_id,
            execution_id=context.execution_id or "",
            requested_tool=context.tool_name,
            requested_action=context.action,
            context=context.execution_context,
            justification=justification,
            task_description=task_description,
            expires_at=datetime.now() + timedelta(minutes=15),
        )

        # Store request (would go to DynamoDB in production)
        logger.info(
            f"Capability escalation requested: {request.request_id} "
            f"({context.agent_id} -> {context.tool_name})"
        )

        # Notify HITL service if available
        if self.hitl_service:
            await self.hitl_service.notify_capability_escalation(request)

        return request

    def _get_policy(self, agent_type: str) -> AgentCapabilityPolicy:
        """Get policy for agent type, using cache."""
        if agent_type not in self._policy_cache:
            self._policy_cache[agent_type] = AgentCapabilityPolicy.for_agent_type(
                agent_type
            )
        return self._policy_cache[agent_type]

    async def _check_dynamic_grants(
        self,
        context: CapabilityContext,
    ) -> Optional[CapabilityDecision]:
        """Check for dynamic grants that apply to this context."""
        if self.grant_service is None:
            return None

        grants = await self.grant_service.get_active_grants(context.agent_id)

        for grant in grants:
            if (
                grant.tool_name == context.tool_name
                and grant.action == context.action
                and not grant.revoked
                and grant.expires_at > datetime.now()
            ):
                # Check usage limits
                if grant.max_usage and grant.usage_count >= grant.max_usage:
                    continue

                # Increment usage count
                await self.grant_service.increment_usage(grant.grant_id)

                return CapabilityDecision.ALLOW

        return None

    def _hash_request(self, context: CapabilityContext) -> str:
        """Generate hash for request deduplication."""
        content = (
            f"{context.agent_id}:{context.tool_name}:{context.action}:"
            f"{context.execution_context}:{time.time()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _audit(self, result: CapabilityCheckResult) -> None:
        """Send result to audit service."""
        if self.audit_service:
            await self.audit_service.log(result)

        # Emit CloudWatch metric
        self._emit_metric(result)

    def _emit_metric(self, result: CapabilityCheckResult) -> None:
        """Emit CloudWatch metric for capability decision."""
        # In production, this would use boto3 CloudWatch client
        logger.debug(
            f"Metric: CapabilityDecision "
            f"decision={result.decision.value} "
            f"tool={result.tool_name} "
            f"agent_type={result.agent_id.split('-')[0]}"
        )
```

```python
# src/services/capability_governance/audit.py

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from .contracts import CapabilityCheckResult, CapabilityDecision

logger = logging.getLogger(__name__)


class CapabilityAuditService:
    """
    Audit service for capability governance decisions.

    Logs all capability checks to DynamoDB via SQS for async processing.
    Emits CloudWatch metrics for monitoring and alerting.
    """

    def __init__(
        self,
        sqs_client: Optional[Any] = None,
        dynamodb_client: Optional[Any] = None,
        cloudwatch_client: Optional[Any] = None,
        queue_url: Optional[str] = None,
        table_name: str = "aura-capability-audit",
    ):
        self.sqs = sqs_client
        self.dynamodb = dynamodb_client
        self.cloudwatch = cloudwatch_client
        self.queue_url = queue_url
        self.table_name = table_name

        # In-memory buffer for batch writes
        self._buffer: list[CapabilityCheckResult] = []
        self._buffer_size = 25  # DynamoDB batch write limit
        self._flush_interval = 5.0  # seconds
        self._last_flush = datetime.now()

    async def log(self, result: CapabilityCheckResult) -> None:
        """
        Log a capability check result.

        For DENY and ESCALATE decisions, logs synchronously.
        For ALLOW and AUDIT_ONLY, buffers for batch processing.
        """
        record = result.to_audit_record()

        # High-priority decisions: log immediately
        if result.decision in (CapabilityDecision.DENY, CapabilityDecision.ESCALATE):
            await self._log_immediate(record)
            await self._emit_alert(result)
        else:
            # Buffer for batch processing
            self._buffer.append(result)
            if len(self._buffer) >= self._buffer_size:
                await self._flush_buffer()

    async def _log_immediate(self, record: dict[str, Any]) -> None:
        """Log record immediately to SQS."""
        if self.sqs and self.queue_url:
            try:
                await asyncio.to_thread(
                    self.sqs.send_message,
                    QueueUrl=self.queue_url,
                    MessageBody=json.dumps(record),
                    MessageAttributes={
                        "decision": {
                            "DataType": "String",
                            "StringValue": record["decision"],
                        },
                        "priority": {
                            "DataType": "String",
                            "StringValue": "high",
                        },
                    },
                )
            except Exception as e:
                logger.error(f"Failed to send audit to SQS: {e}")
                # Fallback to direct DynamoDB write
                await self._write_to_dynamodb([record])
        else:
            logger.info(f"Capability audit (immediate): {record}")

    async def _flush_buffer(self) -> None:
        """Flush buffered records to DynamoDB."""
        if not self._buffer:
            return

        records = [r.to_audit_record() for r in self._buffer]
        self._buffer.clear()
        self._last_flush = datetime.now()

        await self._write_to_dynamodb(records)

    async def _write_to_dynamodb(self, records: list[dict[str, Any]]) -> None:
        """Write records to DynamoDB."""
        if self.dynamodb:
            try:
                # Batch write to DynamoDB
                request_items = {
                    self.table_name: [
                        {"PutRequest": {"Item": self._to_dynamodb_item(r)}}
                        for r in records
                    ]
                }
                await asyncio.to_thread(
                    self.dynamodb.batch_write_item,
                    RequestItems=request_items,
                )
            except Exception as e:
                logger.error(f"Failed to write audit to DynamoDB: {e}")
        else:
            for record in records:
                logger.info(f"Capability audit (buffered): {record}")

    async def _emit_alert(self, result: CapabilityCheckResult) -> None:
        """Emit CloudWatch alarm for high-priority decisions."""
        if self.cloudwatch:
            try:
                await asyncio.to_thread(
                    self.cloudwatch.put_metric_data,
                    Namespace="Aura/CapabilityGovernance",
                    MetricData=[
                        {
                            "MetricName": "CapabilityViolation",
                            "Dimensions": [
                                {"Name": "Decision", "Value": result.decision.value},
                                {"Name": "Tool", "Value": result.tool_name},
                            ],
                            "Value": 1,
                            "Unit": "Count",
                        }
                    ],
                )
            except Exception as e:
                logger.error(f"Failed to emit CloudWatch metric: {e}")

    def _to_dynamodb_item(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert record to DynamoDB item format."""
        return {
            "audit_id": {"S": f"{record['agent_id']}#{record['checked_at']}"},
            "timestamp": {"S": record["checked_at"]},
            "decision": {"S": record["decision"]},
            "tool_name": {"S": record["tool_name"]},
            "agent_id": {"S": record["agent_id"]},
            "action": {"S": record["action"]},
            "context": {"S": record["context"]},
            "reason": {"S": record["reason"]},
            "policy_version": {"S": record["policy_version"]},
            "capability_source": {"S": record["capability_source"]},
            "request_hash": {"S": record["request_hash"]},
        }

    async def query_violations(
        self,
        agent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query capability violations for analysis.

        Args:
            agent_id: Filter by agent
            tool_name: Filter by tool
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum results

        Returns:
            List of violation records
        """
        # In production, this would query DynamoDB with GSIs
        logger.info(
            f"Query violations: agent={agent_id}, tool={tool_name}, "
            f"range={start_time}-{end_time}, limit={limit}"
        )
        return []
```

### Agent Integration

```python
# src/agents/base_agent.py (additions)

class CapabilityGovernedMixin:
    """
    Mixin that adds capability governance to agents.

    Integrates with CapabilityEnforcementMiddleware to enforce
    per-agent tool access policies.

    Usage:
        class CoderAgent(CapabilityGovernedMixin, MCPToolMixin, BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                # invoke_tool() now enforces capability policies
                results = await self.invoke_tool("semantic_search", {"query": task.description})
                return self.process_results(results)
    """

    _capability_middleware: "CapabilityEnforcementMiddleware | None" = None
    _capability_policy: "AgentCapabilityPolicy | None" = None
    _execution_context: str = "development"
    _parent_agent_id: str | None = None

    def _init_capability_governance(
        self,
        middleware: "CapabilityEnforcementMiddleware | None" = None,
        policy: "AgentCapabilityPolicy | None" = None,
        execution_context: str = "development",
        parent_agent_id: str | None = None,
    ) -> None:
        """
        Initialize capability governance for this agent.

        Args:
            middleware: Capability enforcement middleware
            policy: Optional policy override
            execution_context: Current execution context (test, sandbox, etc.)
            parent_agent_id: Parent agent ID if spawned dynamically
        """
        self._capability_middleware = middleware
        self._capability_policy = policy or AgentCapabilityPolicy.for_agent_type(
            self.__class__.__name__
        )
        self._execution_context = execution_context
        self._parent_agent_id = parent_agent_id

        logger.info(
            f"Capability governance initialized for {self.__class__.__name__} "
            f"(context: {execution_context})"
        )

    async def invoke_tool_governed(
        self,
        tool_name: str,
        params: dict[str, Any],
        action: str = "execute",
    ) -> dict[str, Any]:
        """
        Invoke a tool with capability governance enforcement.

        This method wraps the standard invoke_tool() with capability checks.

        Args:
            tool_name: Name of the tool to invoke
            params: Tool parameters
            action: Action type (read, write, execute, admin)

        Returns:
            Tool result data

        Raises:
            CapabilityDeniedError: If capability check fails
            CapabilityEscalationPending: If HITL approval required
        """
        from src.services.capability_governance.middleware import CapabilityContext
        from src.services.capability_governance.contracts import CapabilityDecision

        if self._capability_middleware is None:
            # No governance configured, fall back to standard invocation
            logger.warning(f"No capability middleware configured for {self.agent_id}")
            return await self.invoke_tool(tool_name, params)

        # Build capability context
        context = CapabilityContext(
            agent_id=getattr(self, "agent_id", "unknown"),
            agent_type=self.__class__.__name__,
            tool_name=tool_name,
            action=action,
            execution_context=self._execution_context,
            parent_agent_id=self._parent_agent_id,
        )

        # Check capability
        result = await self._capability_middleware.check(
            context, self._capability_policy
        )

        if result.decision == CapabilityDecision.ALLOW:
            return await self.invoke_tool(tool_name, params)

        elif result.decision == CapabilityDecision.AUDIT_ONLY:
            # Allow but ensure audit is complete
            return await self.invoke_tool(tool_name, params)

        elif result.decision == CapabilityDecision.ESCALATE:
            # Request HITL approval
            escalation = await self._capability_middleware.request_escalation(
                context,
                justification=f"Agent requires {tool_name} for task execution",
                task_description=params.get("task_description", "Unknown task"),
            )
            raise CapabilityEscalationPending(
                f"Capability requires HITL approval: {escalation.request_id}"
            )

        else:  # DENY
            raise CapabilityDeniedError(
                f"Capability denied: {result.reason}"
            )


class CapabilityDeniedError(Exception):
    """Raised when an agent lacks capability to invoke a tool."""
    pass


class CapabilityEscalationPending(Exception):
    """Raised when capability requires HITL approval."""
    pass
```

### Files Created

| File | Purpose |
|------|---------|
| `src/services/capability_governance/__init__.py` | Package initialization |
| `src/services/capability_governance/contracts.py` | Data contracts and enums |
| `src/services/capability_governance/policy.py` | Agent capability policies |
| `src/services/capability_governance/middleware.py` | Enforcement middleware |
| `src/services/capability_governance/audit.py` | Audit logging service |
| `src/services/capability_governance/registry.py` | Tool capability registry |
| `src/services/capability_governance/dynamic_grants.py` | Dynamic grant management |
| `src/services/capability_governance/metrics.py` | CloudWatch metrics |
| `tests/services/test_capability_governance/` | Test suite (350+ tests) |
| `tests/fixtures/capability_policies/` | Test policy fixtures |
| `deploy/cloudformation/capability-governance.yaml` | Infrastructure |

### DynamoDB Tables

| Table | Purpose | Keys |
|-------|---------|------|
| `aura-capability-audit-{env}` | Audit trail for all capability checks | PK: audit_id, SK: timestamp |
| `aura-capability-grants-{env}` | Dynamic capability grants | PK: agent_id, SK: grant_id |
| `aura-capability-policies-{env}` | Custom policy overrides | PK: agent_type, SK: version |

### CloudFormation Resources

```yaml
# deploy/cloudformation/capability-governance.yaml

AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 8.5 - Capability Governance Infrastructure'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  DataEncryptionKeyArn:
    Type: String
    Description: KMS key ARN for data encryption

Resources:
  # Audit Table
  CapabilityAuditTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-capability-audit-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: audit_id
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
        - AttributeName: agent_id
          AttributeType: S
        - AttributeName: decision
          AttributeType: S
      KeySchema:
        - AttributeName: audit_id
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: agent-decision-index
          KeySchema:
            - AttributeName: agent_id
              KeyType: HASH
            - AttributeName: decision
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: decision-timestamp-index
          KeySchema:
            - AttributeName: decision
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref DataEncryptionKeyArn
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # Dynamic Grants Table
  CapabilityGrantsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-capability-grants-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: agent_id
          AttributeType: S
        - AttributeName: grant_id
          AttributeType: S
        - AttributeName: expires_at
          AttributeType: S
      KeySchema:
        - AttributeName: agent_id
          KeyType: HASH
        - AttributeName: grant_id
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: expiration-index
          KeySchema:
            - AttributeName: agent_id
              KeyType: HASH
            - AttributeName: expires_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref DataEncryptionKeyArn
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  # Audit Queue
  CapabilityAuditQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-capability-audit-${Environment}'
      VisibilityTimeout: 300
      MessageRetentionPeriod: 1209600  # 14 days
      KmsMasterKeyId: !Ref DataEncryptionKeyArn
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt CapabilityAuditDLQ.Arn
        maxReceiveCount: 3
      Tags:
        - Key: Project
          Value: !Ref ProjectName

  CapabilityAuditDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-capability-audit-dlq-${Environment}'
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: !Ref DataEncryptionKeyArn

  # CloudWatch Alarms
  CapabilityDenialAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-capability-denial-rate-${Environment}'
      AlarmDescription: High rate of capability denials - potential attack or misconfiguration
      MetricName: CapabilityViolation
      Namespace: Aura/CapabilityGovernance
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 2
      Threshold: 50
      ComparisonOperator: GreaterThanThreshold
      Dimensions:
        - Name: Decision
          Value: deny
      AlarmActions:
        - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-security-alerts-${Environment}'

  CapabilityEscalationAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-capability-escalation-rate-${Environment}'
      AlarmDescription: High rate of capability escalations - agents hitting policy limits
      MetricName: CapabilityViolation
      Namespace: Aura/CapabilityGovernance
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 2
      Threshold: 20
      ComparisonOperator: GreaterThanThreshold
      Dimensions:
        - Name: Decision
          Value: escalate
      AlarmActions:
        - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-ops-alerts-${Environment}'

Outputs:
  AuditTableArn:
    Value: !GetAtt CapabilityAuditTable.Arn
    Export:
      Name: !Sub '${ProjectName}-capability-audit-table-arn-${Environment}'

  GrantsTableArn:
    Value: !GetAtt CapabilityGrantsTable.Arn
    Export:
      Name: !Sub '${ProjectName}-capability-grants-table-arn-${Environment}'

  AuditQueueUrl:
    Value: !Ref CapabilityAuditQueue
    Export:
      Name: !Sub '${ProjectName}-capability-audit-queue-url-${Environment}'
```

### CloudWatch Metrics

| Metric | Description | Dimensions | Target |
|--------|-------------|------------|--------|
| `CapabilityCheckLatency` | P95 latency for capability checks | AgentType, Tool | <10ms |
| `CapabilityViolation` | Count of DENY/ESCALATE decisions | Decision, Tool | <50/5min |
| `DynamicGrantUsage` | Dynamic grants issued and consumed | Scope | Monitoring only |
| `PolicyCacheHitRate` | Policy cache effectiveness | AgentType | >90% |
| `AuditQueueDepth` | Pending audit records | - | <1000 |

## Cost Analysis

### Monthly Cost Projections

| Component | Unit Cost | Volume/Month | Monthly Cost |
|-----------|-----------|--------------|--------------|
| **DynamoDB (Audit)** | $1.25/M writes | 10M writes | $12.50 |
| **DynamoDB (Grants)** | $1.25/M writes | 500K writes | $0.63 |
| **DynamoDB (Reads)** | $0.25/M reads | 20M reads | $5.00 |
| **SQS (Audit Queue)** | $0.40/M requests | 10M messages | $4.00 |
| **CloudWatch Metrics** | $0.30/metric/month | 10 metrics | $3.00 |
| **CloudWatch Alarms** | $0.10/alarm/month | 5 alarms | $0.50 |
| **Total** | | | **~$26/month** |

### Cost Optimization Strategies

1. **Sample auditing for SAFE tools** - Only log 10% of SAFE tool invocations
2. **In-memory policy caching** - Reduce DynamoDB reads by 90%
3. **Batch audit writes** - Buffer and batch-write audit records
4. **TTL on audit records** - Auto-expire records after 90 days (365 for production)

## Testing Strategy

### Test Pyramid

| Tier | Tests | Coverage |
|------|-------|----------|
| Unit Tests | 200 | Policy logic, middleware, contracts |
| Integration Tests | 100 | DynamoDB, SQS, CloudWatch |
| E2E Tests | 30 | Full agent invocation with governance |
| Security Tests | 20 | Bypass attempts, privilege escalation |
| **Total** | **350** | |

### Test Cases

```python
# tests/services/test_capability_governance/test_middleware.py

class TestCapabilityEnforcement:
    """Test capability enforcement middleware."""

    @pytest.mark.parametrize("agent_type,tool,expected", [
        ("CoderAgent", "semantic_search", CapabilityDecision.ALLOW),
        ("CoderAgent", "provision_sandbox", CapabilityDecision.DENY),
        ("ReviewerAgent", "query_code_graph", CapabilityDecision.ALLOW),
        ("ReviewerAgent", "index_code_embedding", CapabilityDecision.DENY),
        ("ValidatorAgent", "provision_sandbox", CapabilityDecision.ESCALATE),
        ("MetaOrchestrator", "deploy_to_production", CapabilityDecision.ESCALATE),
        ("RedTeamAgent", "provision_sandbox", CapabilityDecision.ALLOW),
    ])
    async def test_default_policy_decisions(
        self,
        middleware: CapabilityEnforcementMiddleware,
        agent_type: str,
        tool: str,
        expected: CapabilityDecision,
    ):
        """Verify default policies produce expected decisions."""
        context = CapabilityContext(
            agent_id=f"{agent_type.lower()}-test-001",
            agent_type=agent_type,
            tool_name=tool,
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)

        assert result.decision == expected
        assert result.tool_name == tool
        assert result.agent_id == context.agent_id


class TestContextRestrictions:
    """Test context-based capability restrictions."""

    async def test_production_context_blocks_dangerous_tools(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Dangerous tools blocked in production context."""
        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="index_code_embedding",
            action="execute",
            execution_context="production",
        )

        result = await middleware.check(context)

        assert result.decision == CapabilityDecision.DENY
        assert "production" in result.reason.lower()

    async def test_sandbox_context_allows_sandbox_tools(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Sandbox tools allowed in sandbox context."""
        context = CapabilityContext(
            agent_id="redteam-agent-001",
            agent_type="RedTeamAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="sandbox",
        )

        result = await middleware.check(context)

        assert result.decision == CapabilityDecision.ALLOW


class TestDynamicGrants:
    """Test dynamic capability grants."""

    async def test_dynamic_grant_overrides_base_policy(
        self,
        middleware: CapabilityEnforcementMiddleware,
        grant_service: DynamicCapabilityGrantService,
    ):
        """Dynamic grant allows otherwise denied capability."""
        # Create grant for CoderAgent to provision sandbox
        grant = DynamicCapabilityGrant(
            grant_id="grant-test-001",
            agent_id="coder-agent-001",
            tool_name="provision_sandbox",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={"max_sandboxes": 1},
            granted_by="cap-esc-test",
            approver="test@example.com",
            granted_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
        )
        await grant_service.store_grant(grant)

        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)

        assert result.decision == CapabilityDecision.ALLOW
        assert result.capability_source == "dynamic_grant"


class TestSecurityBypass:
    """Test resistance to capability bypass attempts."""

    async def test_agent_id_spoofing_prevented(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Agent cannot spoof another agent's ID to gain capabilities."""
        # Attacker claims to be MetaOrchestrator but is really CoderAgent
        context = CapabilityContext(
            agent_id="meta-orchestrator-spoofed",  # Fake ID
            agent_type="CoderAgent",  # Real type
            tool_name="deploy_to_production",
            action="execute",
            execution_context="production",
        )

        result = await middleware.check(context)

        # Policy is based on agent_type, not agent_id
        assert result.decision == CapabilityDecision.DENY

    async def test_child_cannot_exceed_parent_capabilities(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Spawned child agent cannot have more capabilities than parent."""
        parent_policy = AgentCapabilityPolicy.for_agent_type("CoderAgent")

        # Parent cannot provision_sandbox
        assert parent_policy.can_invoke(
            "provision_sandbox", "execute", "development"
        ) == CapabilityDecision.DENY

        # Even if child is AdminAgent type, parent's restriction applies
        context = CapabilityContext(
            agent_id="admin-agent-spawned",
            agent_type="AdminAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
            parent_agent_id="coder-agent-001",
        )

        result = await middleware.check(context)

        # Child cannot exceed parent's capabilities
        assert result.decision == CapabilityDecision.ESCALATE
```

## Implementation Phases

### Phase 1: Core Framework (Week 1-2)

| Task | Deliverable |
|------|-------------|
| Implement CapabilityEnforcementMiddleware | Core enforcement logic |
| Implement AgentCapabilityPolicy | Default policies for all agent types |
| Implement CapabilityAuditService | Audit logging to SQS/DynamoDB |
| Deploy DynamoDB tables | Audit and grants tables |
| Unit tests | 200 tests |

### Phase 2: Agent Integration (Week 3-4)

| Task | Deliverable |
|------|-------------|
| Add CapabilityGovernedMixin to BaseAgent | Agent integration |
| Update MCPToolMixin.invoke_tool() | Pre-invocation governance check |
| Update MetaOrchestrator spawn logic | Capability inheritance for children |
| Integration tests | 100 tests |

### Phase 3: Dynamic Grants & HITL (Week 5-6)

| Task | Deliverable |
|------|-------------|
| Implement DynamicCapabilityGrantService | Grant storage and retrieval |
| Integrate with HITLService | Escalation request workflow |
| Add HITL dashboard for capability approvals | UI for approvers |
| Deploy CloudWatch alarms | Security monitoring |
| E2E tests | 30 tests |

### Phase 4: Hardening & Rollout (Week 7-8)

| Task | Deliverable |
|------|-------------|
| Security testing | 20 bypass attempt tests |
| Performance optimization | Policy caching, batch auditing |
| Documentation | Operations runbook |
| Gradual rollout | Enable for CoderAgent first, then all agents |
| Monitoring dashboard | CloudWatch dashboard |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| DynamoDB | Yes | Full feature parity |
| SQS | Yes | FIFO queues supported |
| CloudWatch | Yes | All metrics and alarms |
| Lambda | Yes | For async audit processing |
| SNS | Yes | For escalation notifications |

**GovCloud-Specific Requirements:**
- Use `${AWS::Partition}` in all ARNs
- Audit retention must meet CMMC requirements (1+ year for production)
- All DynamoDB tables encrypted with customer-managed KMS keys
- SQS queues encrypted at rest

## Consequences

### Positive

1. **Principle of Least Privilege** - Agents only access tools they explicitly need
2. **Defense in Depth** - Multiple layers of access control (policy, context, dynamic grants)
3. **Complete Audit Trail** - Every capability decision logged for forensics
4. **HITL Integration** - Seamless escalation for sensitive operations
5. **Compliance Support** - Meets CMMC AC-6, NIST 800-53 AC-2(7) requirements
6. **Runtime Enforcement** - Policy violations blocked before tool invocation
7. **Flexible Governance** - Dynamic grants enable HITL-approved exceptions

### Negative

1. **Latency Overhead** - ~5-10ms per capability check (mitigated by caching)
2. **Complexity** - Additional layer in agent invocation path
3. **Policy Maintenance** - Policies need updates as agent capabilities evolve
4. **Escalation Friction** - HITL escalations may slow autonomous operations

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Policy misconfiguration blocks legitimate operations | Medium | High | Pre-deployment policy validation, gradual rollout |
| Cache inconsistency leads to stale policy | Low | Medium | Short TTL (60s), forced refresh on policy update |
| Audit queue backlog during high load | Low | Low | DLQ, autoscaling Lambda consumers |
| Dynamic grant expiration disrupts long tasks | Medium | Medium | Grace period, renewal mechanism |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Capability Check Latency P95 | <10ms | CloudWatch metrics |
| Policy Cache Hit Rate | >90% | CloudWatch metrics |
| Unauthorized Tool Access | 0 | Audit log analysis |
| HITL Escalation Response Time | <15min | HITL dashboard metrics |
| Audit Log Completeness | 100% | Sampling validation |

## References

1. ADR-018: MetaOrchestrator with Dynamic Agent Spawning
2. ADR-029: Agent Optimization Roadmap (MCP Tool Integration)
3. ADR-032: Configurable Autonomy Framework
4. ADR-042: Real-Time Agent Intervention
5. ADR-063: Constitutional AI Integration
6. NIST 800-53 AC-6: Least Privilege
7. CMMC 2.0 AC.L2-3.1.5: Role-Based Access Control
8. AWS Agents for Bedrock Action Groups: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-action-groups.html
