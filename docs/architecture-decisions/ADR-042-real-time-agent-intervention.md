# ADR-042: Real-Time Agent Intervention Architecture

## Status
**Deployed** | December 17, 2025 (Phase 1: CloudTrail, IAM Security Alerting, Checkpoint Infrastructure)

## Context

### Current State

Aura's existing Human-in-the-Loop (HITL) architecture (ADR-005, ADR-032) provides **pre-flight batch approval** where operators review and approve entire remediation plans before execution begins. Once approved, agents execute autonomously without further human interaction.

### Gap Identified

Modern AI coding assistants like Claude Code and Google's Antigravity IDE demonstrate a more granular **real-time intervention model** where:

1. **Per-Tool Approval**: Each tool invocation can require explicit approval
2. **Mid-Execution Control**: Operators can pause, modify, or cancel actions during execution
3. **Trust Escalation**: Frequently-approved actions can be auto-approved based on trust settings
4. **Undo Capability**: Recent actions can be rolled back when safe

### Business Drivers

- **Safety**: Critical infrastructure operations require granular control
- **Transparency**: Operators need visibility into each action before execution
- **Compliance**: CMMC/SOX requirements for explicit authorization of changes
- **User Experience**: Match industry expectations set by modern AI assistants

## Decision

**Implement a checkpoint-based real-time intervention system** that:

1. Creates approval checkpoints before each significant agent action
2. Streams real-time execution state via WebSocket
3. Supports action modification before execution
4. Integrates with ADR-032 autonomy levels for configurable intervention
5. Provides keyboard-driven approval workflow (A/D/M keys)

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ RealTimeExecution│  │ ActionApproval   │  │ ExecutionTimeline│   │
│  │ Panel            │  │ Card             │  │                  │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │
│           │                     │                     │             │
│           └─────────────────────┼─────────────────────┘             │
│                                 │                                    │
│                    ┌────────────┴────────────┐                       │
│                    │    ExecutionContext     │                       │
│                    │    (State + WebSocket)  │                       │
│                    └────────────┬────────────┘                       │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │ WebSocket + REST
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     API Gateway (WebSocket)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ ws_connect   │  │ ws_message   │  │ ws_disconnect│               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Backend Services (EKS)                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              ExecutionCheckpointService                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │ │
│  │  │ Checkpoint   │  │ Approval     │  │ Trust        │          │ │
│  │  │ Creation     │  │ Gates        │  │ Evaluation   │          │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              RealtimeEventPublisher                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │ │
│  │  │ WebSocket    │  │ State        │  │ Event        │          │ │
│  │  │ Broadcast    │  │ Serialization│  │ Filtering    │          │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Data Layer (DynamoDB)                            │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │ aura-checkpoints-{env}       │  │ aura-ws-connections-{env}    │ │
│  │ • checkpoint_id (PK)         │  │ • connection_id (PK)         │ │
│  │ • execution_id (GSI)         │  │ • execution_id (GSI)         │ │
│  │ • status, action, timestamp  │  │ • user_id, connected_at      │ │
│  └──────────────────────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Checkpoint State Machine

```
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │ checkpoint_created
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ AUTO_APPROVED │  │   AWAITING    │  │   SKIPPED     │
│ (trust match) │  │   APPROVAL    │  │ (non-critical)│
└───────┬───────┘  └───────┬───────┘  └───────────────┘
        │                  │
        │          ┌───────┴───────┐
        │          │               │
        ▼          ▼               ▼
┌───────────────┐  ┌───────────────┐
│   APPROVED    │  │    DENIED     │
└───────┬───────┘  └───────────────┘
        │
        ▼
┌───────────────┐
│   EXECUTING   │
└───────┬───────┘
        │
   ┌────┴────┐
   │         │
   ▼         ▼
┌─────────┐ ┌─────────┐
│COMPLETED│ │ FAILED  │
└─────────┘ └─────────┘
```

### Core Service: ExecutionCheckpointService

```python
@dataclass
class CheckpointAction:
    """Represents an action awaiting approval."""
    checkpoint_id: str
    execution_id: str
    agent_id: str
    action_type: str  # tool_call, file_write, api_request, command_exec
    action_name: str
    parameters: Dict[str, Any]
    risk_level: str  # low, medium, high, critical
    reversible: bool
    estimated_duration_seconds: int
    context: Dict[str, Any]  # surrounding context for informed decision

class ExecutionCheckpointService:
    """Manages real-time approval gates for agent actions."""

    async def create_checkpoint(
        self,
        execution_id: str,
        agent_id: str,
        action: CheckpointAction
    ) -> str:
        """Create checkpoint and determine if approval needed."""

        # Check trust settings for auto-approval
        if await self._should_auto_approve(action):
            await self._mark_auto_approved(checkpoint_id)
            return checkpoint_id

        # Publish to WebSocket for UI display
        await self.event_publisher.publish_checkpoint_created(action)

        # Wait for approval (with timeout)
        approved = await self._wait_for_approval(
            checkpoint_id,
            timeout_seconds=action.timeout or 300
        )

        return checkpoint_id

    async def approve_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str,
        modifications: Optional[Dict] = None
    ) -> None:
        """Approve a pending checkpoint, optionally with modifications."""

    async def deny_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str,
        reason: str
    ) -> None:
        """Deny a pending checkpoint and halt execution."""
```

### ADR-032 Integration

The intervention mode maps directly to ADR-032 autonomy levels:

| Autonomy Level | Intervention Mode | Behavior |
|---------------|------------------|----------|
| 0 - Manual | ALL_ACTIONS | Every action requires approval |
| 1 - Observe | ALL_ACTIONS | All actions paused for review |
| 2 - Assisted | WRITE_ACTIONS | File/DB writes require approval |
| 3 - Supervised | HIGH_RISK | High/critical risk actions only |
| 4 - Guided | CRITICAL_ONLY | Critical actions only |
| 5 - Autonomous | NONE | No intervention (emergency stop available) |

### API Endpoints

**REST Endpoints:**
```
POST   /api/v1/checkpoints/{id}/approve
POST   /api/v1/checkpoints/{id}/deny
POST   /api/v1/checkpoints/{id}/modify
GET    /api/v1/executions/{id}/checkpoints
PUT    /api/v1/executions/{id}/trust-settings
POST   /api/v1/executions/{id}/emergency-stop
```

**WebSocket Events:**
```
→ checkpoint.created     - New action awaiting approval
→ checkpoint.updated     - Status changed
→ execution.progress     - Execution progress update
→ execution.log          - Log message from agent
← checkpoint.approve     - Client approves action
← checkpoint.deny        - Client denies action
← checkpoint.modify      - Client modifies parameters
← execution.pause        - Client pauses execution
← execution.resume       - Client resumes execution
← execution.stop         - Client stops execution
```

### DynamoDB Schema

**Checkpoints Table:**
```yaml
TableName: aura-checkpoints-{env}
KeySchema:
  - AttributeName: checkpoint_id
    KeyType: HASH
GlobalSecondaryIndexes:
  - IndexName: execution-status-index
    KeySchema:
      - AttributeName: execution_id
        KeyType: HASH
      - AttributeName: status
        KeyType: RANGE
Attributes:
  - checkpoint_id: S (ULID)
  - execution_id: S
  - agent_id: S
  - action_type: S
  - action_name: S
  - parameters: M
  - risk_level: S
  - status: S (PENDING|AWAITING_APPROVAL|APPROVED|DENIED|EXECUTING|COMPLETED|FAILED)
  - created_at: S (ISO8601)
  - decided_at: S
  - decided_by: S
  - modifications: M
  - result: M
  - ttl: N (7 days)
```

**WebSocket Connections Table:**
```yaml
TableName: aura-ws-connections-{env}
KeySchema:
  - AttributeName: connection_id
    KeyType: HASH
GlobalSecondaryIndexes:
  - IndexName: execution-index
    KeySchema:
      - AttributeName: execution_id
        KeyType: HASH
Attributes:
  - connection_id: S
  - execution_id: S
  - user_id: S
  - connected_at: S
  - ttl: N (2 hours)
```

### Frontend Components

| Component | Purpose |
|-----------|---------|
| `RealTimeExecutionPanel` | Main container with timeline, approval queue, logs |
| `ActionApprovalCard` | Claude Code-style card with Approve/Deny/Modify buttons |
| `ActionModifyModal` | Parameter modification before execution |
| `ExecutionTimeline` | Visual timeline showing action sequence and status |
| `TrustSettingsPanel` | Configure auto-approval rules per action type |
| `ExecutionContext` | Global state management with WebSocket connection |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `A` | Approve current action |
| `D` | Deny current action |
| `M` | Open modify modal |
| `T` | Toggle trust settings |
| `Esc` | Cancel/close modal |
| `↑/↓` | Navigate approval queue |

## Alternatives Considered

### 1. Polling-Based Approval (Rejected)
- Simpler implementation
- Higher latency (seconds vs milliseconds)
- Poor UX for real-time intervention
- Rejected due to responsiveness requirements

### 2. Server-Sent Events (Rejected)
- Unidirectional (server → client only)
- Would require separate REST calls for approvals
- WebSocket provides better bidirectional support
- Rejected for architectural simplicity

### 3. gRPC Streaming (Rejected)
- Better performance characteristics
- Requires infrastructure changes
- Limited browser support without proxy
- Rejected for compatibility reasons

### 4. Full Undo System (Deferred)
- Complex state management
- Not all actions are reversible
- Deferred to Phase 2 implementation
- Will implement for reversible actions only

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)
- ExecutionCheckpointService with approval gates
- DynamoDB tables for checkpoints and connections
- WebSocket API Gateway and Lambda handlers
- Basic REST endpoints for approval operations

### Phase 2: Frontend Integration (Week 2-3)
- ExecutionContext with WebSocket connection
- RealTimeExecutionPanel component
- ActionApprovalCard with keyboard shortcuts
- ExecutionTimeline visualization

### Phase 3: Trust System (Week 3-4)
- Trust settings configuration UI
- Auto-approval rule engine
- Action pattern matching
- Trust escalation workflow

### Phase 4: Advanced Features (Week 4-5)
- Action modification before execution
- Partial undo for reversible actions
- Execution pause/resume
- Multi-user collaboration (shared sessions)

## Consequences

### Positive
- **Granular Control**: Per-action approval vs batch approval
- **Transparency**: Full visibility into agent operations
- **Safety**: Prevent unintended actions in real-time
- **Compliance**: Explicit authorization trail for audits
- **UX Parity**: Match expectations from Claude Code/Antigravity

### Negative
- **Latency**: Each checkpoint adds approval wait time
- **Complexity**: WebSocket infrastructure and state management
- **User Burden**: Frequent approvals may cause fatigue
- **Cost**: Additional DynamoDB and API Gateway charges

### Mitigations
- Trust settings reduce approval fatigue for routine actions
- Autonomy level 5 bypasses intervention for trusted contexts
- Checkpoint TTL (7 days) limits storage costs
- Connection TTL (2 hours) manages WebSocket state

## Security Considerations

1. **Authentication**: WebSocket connections require valid JWT
2. **Authorization**: Users can only approve executions they have access to
3. **Audit Trail**: All approvals logged with user ID and timestamp
4. **Rate Limiting**: Checkpoint creation limited to prevent DoS
5. **Encryption**: WebSocket traffic encrypted via TLS

## Metrics and Monitoring

| Metric | Description |
|--------|-------------|
| `checkpoint.created` | Count of checkpoints created |
| `checkpoint.approval_time_ms` | Time from creation to decision |
| `checkpoint.auto_approved_rate` | Percentage auto-approved by trust |
| `checkpoint.denied_rate` | Percentage of denials |
| `websocket.connections` | Active WebSocket connections |
| `websocket.message_latency_ms` | Round-trip message time |

## References

- [ADR-005: HITL Sandbox Architecture](ADR-005-hitl-sandbox-architecture.md)
- [ADR-032: Configurable Autonomy Framework](ADR-032-configurable-autonomy-framework.md)
- [Claude Code Approval Model](https://docs.anthropic.com/claude-code)
- [Google Antigravity IDE](https://github.com/nickhirakawa/antigravity)
- [AWS API Gateway WebSocket APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html)
