# ADR-017: Dynamic Sandbox Resource Allocation by Specialized Agents

**Status:** Deployed
**Date:** 2025-12-02
**Decision Makers:** Project Aura Team

## Context

The sandbox infrastructure (Layer 7) supports ephemeral testing environments for HITL patch validation. Initially, the CloudFormation template included static parameters for sandbox compute constraints:

- `SandboxTaskCpu` (256/512/1024 vCPU units)
- `SandboxTaskMemory` (512/1024/2048 MB)
- `ApprovalTimeoutHours` (1-168 hours)
- `SandboxMaxRuntimeMinutes` (5-120 minutes)
- `PrivateSubnetIds` (subnet placement)

The question: **Should sandbox compute resources be statically configured in infrastructure, or dynamically specified by agents at runtime?**

This decision impacts:
- Agent flexibility (one-size-fits-all vs. task-specific resources)
- Cost efficiency (over-provisioning vs. right-sizing)
- Infrastructure complexity (CloudFormation parameters vs. runtime configuration)
- Security (guardrails enforcement mechanism)

## Decision

We chose **dynamic resource allocation** where specialized agents specify their sandbox compute requirements at runtime, rather than hardcoding constraints in CloudFormation.

**Architecture:**

```
┌─────────────────────┐
│  Specialized Agent  │
│  (Security/Perf/...)│
└──────────┬──────────┘
           │ Specifies: cpu, memory, timeout
           ▼
┌─────────────────────┐
│  Sandbox Orchestrator│
│  (Step Functions)   │
└──────────┬──────────┘
           │ Validates against guardrails
           ▼
┌─────────────────────┐
│  ECS Fargate Task   │
│  (Dynamic Config)   │
└─────────────────────┘
```

**Key Design Decisions:**

1. **No static Task Definitions** - ECS cluster created without pre-defined task definitions
2. **Runtime task registration** - Agents register task definitions with specific CPU/memory
3. **Guardrails via IAM** - `SandboxTaskRole` limits what containers can do
4. **Fargate limits** - AWS enforces maximum CPU (4 vCPU) and memory (30 GB)
5. **Step Functions timeout** - Workflow enforces maximum sandbox runtime programmatically

**Example Agent Configuration:**

```python
# Security Agent - Lightweight static analysis
sandbox_config = {
    "cpu": 256,
    "memory": 512,
    "timeout_minutes": 10,
    "task_type": "security_scan"
}

# Performance Agent - Load testing
sandbox_config = {
    "cpu": 1024,
    "memory": 2048,
    "timeout_minutes": 60,
    "task_type": "performance_test"
}

# Coder Agent - Compilation and unit tests
sandbox_config = {
    "cpu": 512,
    "memory": 1024,
    "timeout_minutes": 30,
    "task_type": "patch_validation"
}
```

## Alternatives Considered

### Alternative 1: Static CloudFormation Parameters

Pre-define fixed sandbox configurations in CloudFormation template.

**Pros:**
- Simple infrastructure (no runtime decisions)
- All sandboxes identical (predictable behavior)
- Easy to audit (fixed resource allocations)

**Cons:**
- Over-provisioning for simple tasks (cost waste)
- Under-provisioning for complex tasks (failures)
- Requires infrastructure changes to adjust
- One-size-fits-all doesn't match agent diversity

**Why rejected:** Agents have fundamentally different resource needs. Static allocation forces compromise.

### Alternative 2: Predefined T-Shirt Sizes

Create 3-4 predefined profiles (small/medium/large/xlarge) that agents select.

**Pros:**
- Limited choices (easier governance)
- Predictable cost tiers
- Balance between flexibility and control

**Cons:**
- Still may not match exact needs
- Requires maintenance of multiple task definitions
- Agents must map their needs to predefined sizes

**Why rejected:** Adds complexity without full flexibility. Agents already know their exact requirements.

### Alternative 3: Fully Dynamic (Chosen)

Agents specify exact resource requirements; guardrails enforce limits.

**Pros:**
- Right-sizing for every task (cost optimal)
- Agents are domain experts on their resource needs
- No infrastructure changes needed for new agent types
- Fargate provides natural upper bounds
- IAM policies enforce security boundaries

**Cons:**
- Agents could request excessive resources (mitigated by guardrails)
- Slightly more complex agent implementation
- Cost unpredictability (mitigated by AWS Budgets)

## Consequences

### Positive

1. **Cost Efficiency** - Security scans use 256 CPU instead of 1024 (75% savings)
2. **Flexibility** - New agent types don't require infrastructure changes
3. **Performance** - Complex tasks get adequate resources without waiting
4. **Simplicity** - No ECS Task Definition management in CloudFormation

### Negative

1. **Agent Responsibility** - Agents must correctly estimate resource needs
2. **Monitoring Complexity** - Variable resource usage harder to predict
3. **Cost Governance** - Requires AWS Budgets and alerts for runaway costs

### Mitigations

| Risk | Mitigation |
|------|------------|
| Excessive resource requests | IAM policy limits, Fargate max bounds |
| Runaway costs | AWS Budgets ($15/day, $400/month alerts) |
| Long-running sandboxes | Step Functions workflow timeout |
| Resource estimation errors | CloudWatch metrics for right-sizing feedback |

## Implementation Details

**Infrastructure Created (sandbox.yaml):**
- `SandboxCluster` - ECS cluster with FARGATE/FARGATE_SPOT capacity
- `SandboxTaskExecutionRole` - Pull images, write logs
- `SandboxTaskRole` - DynamoDB, S3, CloudWatch access only
- `StepFunctionsExecutionRole` - Orchestrate ECS tasks

**Agent Interface (future):**
```python
class SandboxConfig:
    cpu: int           # 256, 512, 1024, 2048, 4096
    memory: int        # 512 to 30720 MB
    timeout: int       # Minutes (max enforced by workflow)
    isolation: str     # "container", "vpc", "full"

def request_sandbox(config: SandboxConfig) -> SandboxId:
    """Agents call this to provision sandbox with specific resources."""
    pass
```

## Related Decisions

- **ADR-005**: HITL Sandbox Architecture (establishes sandbox workflow)
- **ADR-007**: Modular CI/CD Strategy (Layer 7 sandbox deployment)
- **ADR-008**: Bedrock LLM Cost Controls (cost governance patterns)

## References

- [AWS Fargate Task Size](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size)
- [ECS Task Definition Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/task-definition.html)
- `deploy/cloudformation/sandbox.yaml` - Infrastructure implementation
