# ADR-070: Policy-as-Code with GitOps for Capability Governance

## Status

Deployed

## Date

2026-01-27

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

### Current State

ADR-066 implemented Agent Capability Governance with runtime enforcement, but capability policies are currently:

| Aspect | Current State | Gap |
|--------|---------------|-----|
| Policy storage | Python code in `capability_governance/policy.py` | No version history |
| Change management | Code PR review | No policy-specific validation |
| Deployment | Application deployment | Cannot update policies independently |
| Audit trail | Git history only | No structured policy change log |
| Testing | Unit tests | No policy simulation/dry-run |
| Rollback | Git revert | No instant policy rollback |

### Compliance Requirements

CMMC Level 3 and SOX require documented change management for security controls:

- **AC.L2-3.1.5**: Least privilege must be verifiable and auditable
- **CM.L2-3.4.3**: Configuration change control must be documented
- **AU.L2-3.3.1**: Audit records must capture security-relevant events

### Industry Best Practice

Modern DevSecOps treats security policies as code:

- HashiCorp Sentinel (Terraform policy)
- Open Policy Agent (OPA/Rego)
- AWS Service Control Policies (SCPs)
- Kubernetes Admission Controllers

## Decision

Implement Policy-as-Code for Agent Capability Governance with GitOps-based deployment, enabling version-controlled, auditable, and testable capability policies.

## Architecture

### Repository Structure

```
capability-policies/
├── README.md
├── schema/
│   ├── agent-policy.schema.json
│   ├── tool-classification.schema.json
│   └── grant.schema.json
├── agents/
│   ├── coder-agent.yaml
│   ├── reviewer-agent.yaml
│   ├── validator-agent.yaml
│   ├── orchestrator-agent.yaml
│   └── ... (10+ agent policies)
├── tool-classifications/
│   └── tool-tiers.yaml
├── grants/
│   ├── temporary-elevations.yaml
│   └── emergency-access.yaml
├── contexts/
│   ├── production.yaml
│   ├── sandbox.yaml
│   └── test.yaml
└── tests/
    ├── test_policy_validation.py
    ├── test_escalation_paths.py
    └── scenarios/
        ├── normal_workflow.yaml
        └── attack_simulation.yaml
```

### Policy Schema

```yaml
# capability-policies/agents/coder-agent.yaml
apiVersion: aura.capability/v1
kind: AgentCapabilityPolicy
metadata:
  name: coder-agent
  version: "1.2.0"
  labels:
    tier: standard
    compliance: [cmmc-l3, sox]
  annotations:
    last-reviewed: "2026-01-27"
    reviewed-by: security-team
spec:
  inheritsFrom: base-agent

  allowedTools:
    safe:
      - semantic_search
      - list_agents
      - get_documentation
      - describe_schema
    monitoring:
      - query_code_graph
      - get_code_dependencies
      - analyze_code_complexity
    dangerous:
      - create_branch
      - commit_changes
      - index_code_embedding

  deniedTools:
    - deploy_to_production
    - access_secrets
    - modify_iam_policy
    - destroy_sandbox

  contextConstraints:
    commit_changes:
      environments: [sandbox, test]
      requiresApproval: false
      maxInvocationsPerHour: 50
    index_code_embedding:
      environments: [sandbox, test, production]
      requiresApproval: true
      approvalTimeout: 300

  rateLimits:
    dangerous:
      perMinute: 10
      perHour: 50
    monitoring:
      perMinute: 100
      perHour: 1000
```

### GitOps Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POLICY-AS-CODE GITOPS WORKFLOW                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Developer submits PR to capability-policies/                            │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CI Pipeline (CodeBuild)                                              │   │
│  │                                                                      │   │
│  │  Stage 1: Validation                                                 │   │
│  │  ├── JSON Schema validation                                         │   │
│  │  ├── YAML lint                                                      │   │
│  │  ├── Policy syntax check                                            │   │
│  │  └── Reference integrity (all tools exist)                          │   │
│  │                                                                      │   │
│  │  Stage 2: Security Analysis                                          │   │
│  │  ├── Privilege escalation path detection                            │   │
│  │  ├── Circular inheritance check                                     │   │
│  │  ├── Toxic capability combination detection                         │   │
│  │  └── Compliance requirement verification                            │   │
│  │                                                                      │   │
│  │  Stage 3: Simulation                                                 │   │
│  │  ├── Dry-run against test scenarios                                 │   │
│  │  ├── Regression check (no unintended denials)                       │   │
│  │  └── Performance impact assessment                                  │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Required Approvals                                                   │   │
│  │                                                                      │   │
│  │  ☐ Security team member (required)                                  │   │
│  │  ☐ Code owner for affected agent (required)                         │   │
│  │  ☐ Compliance officer (if CRITICAL tier changes)                    │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Deployment (CodePipeline)                                            │   │
│  │                                                                      │   │
│  │  1. Merge to main triggers deployment                               │   │
│  │  2. Policy artifacts uploaded to S3 (versioned)                     │   │
│  │  3. DynamoDB policy table updated atomically                        │   │
│  │  4. Neptune capability graph refreshed                              │   │
│  │  5. Cache invalidation across EKS pods                              │   │
│  │  6. Audit log entry with commit SHA                                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Post-Deployment Verification                                         │   │
│  │                                                                      │   │
│  │  ├── Smoke tests against live policy                                │   │
│  │  ├── Metric baseline comparison                                     │   │
│  │  └── Automatic rollback on anomaly detection                        │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Policy Validation Service

```python
# src/services/capability_governance/policy_validator.py

@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    escalation_paths: list[EscalationPath]
    coverage_gaps: list[CoverageGap]

class PolicyValidator:
    """Validates capability policies before deployment."""

    async def validate_policy(
        self,
        policy: AgentCapabilityPolicy,
        context: ValidationContext,
    ) -> ValidationResult:
        """
        Comprehensive policy validation.

        Checks:
        1. Schema compliance
        2. Reference integrity (all tools exist)
        3. No circular inheritance
        4. No privilege escalation paths
        5. No toxic capability combinations
        6. Compliance requirements met
        """
        errors = []
        warnings = []

        # Schema validation
        schema_result = self._validate_schema(policy)
        errors.extend(schema_result.errors)

        # Reference integrity
        ref_result = await self._validate_references(policy)
        errors.extend(ref_result.errors)

        # Inheritance validation
        inheritance_result = await self._validate_inheritance(policy)
        errors.extend(inheritance_result.errors)

        # Privilege escalation detection
        escalation_paths = await self._detect_escalation_paths(policy)
        if escalation_paths:
            errors.append(ValidationError(
                code="PRIVILEGE_ESCALATION",
                message=f"Found {len(escalation_paths)} privilege escalation paths",
                paths=escalation_paths,
            ))

        # Toxic combinations
        toxic_result = await self._detect_toxic_combinations(policy)
        errors.extend(toxic_result.errors)
        warnings.extend(toxic_result.warnings)

        # Coverage gaps
        coverage_gaps = await self._detect_coverage_gaps(policy)
        for gap in coverage_gaps:
            warnings.append(ValidationWarning(
                code="COVERAGE_GAP",
                message=gap.description,
            ))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            escalation_paths=escalation_paths,
            coverage_gaps=coverage_gaps,
        )
```

### Policy Simulation

```python
# src/services/capability_governance/simulator.py

class PolicySimulator:
    """Simulate policy changes before deployment."""

    async def simulate_workflow(
        self,
        workflow: list[ToolInvocation],
        current_policy: AgentCapabilityPolicy,
        proposed_policy: AgentCapabilityPolicy,
    ) -> SimulationResult:
        """
        Compare workflow execution under current vs proposed policy.

        Identifies:
        - Newly denied operations (potential breakage)
        - Newly allowed operations (security review needed)
        - Changed escalation requirements
        """
        current_results = []
        proposed_results = []

        for invocation in workflow:
            current_decision = await self._evaluate(invocation, current_policy)
            proposed_decision = await self._evaluate(invocation, proposed_policy)

            current_results.append(current_decision)
            proposed_results.append(proposed_decision)

        return SimulationResult(
            workflow=workflow,
            current_results=current_results,
            proposed_results=proposed_results,
            newly_denied=[
                (w, c, p) for w, c, p in zip(workflow, current_results, proposed_results)
                if c.allowed and not p.allowed
            ],
            newly_allowed=[
                (w, c, p) for w, c, p in zip(workflow, current_results, proposed_results)
                if not c.allowed and p.allowed
            ],
            escalation_changes=[
                (w, c, p) for w, c, p in zip(workflow, current_results, proposed_results)
                if c.requires_approval != p.requires_approval
            ],
        )
```

### Neptune Graph Synchronization

Policy deployments must synchronize with ADR-071's capability graph. This event-driven mechanism ensures the Neptune graph reflects current policies.

```python
# src/services/capability_governance/graph_sync.py

class PolicyGraphSynchronizer:
    """Synchronize policy deployments with Neptune capability graph."""

    def __init__(
        self,
        neptune_client: NeptuneGraphService,
        eventbridge_client,
    ):
        self.neptune = neptune_client
        self.eventbridge = eventbridge_client

    async def on_policy_deployed(self, event: PolicyDeployedEvent) -> SyncResult:
        """
        Handle PolicyDeployed event from CodePipeline.

        Triggered via EventBridge rule on successful policy deployment.
        Updates Neptune capability graph to reflect new policy state.
        """
        sync_start = datetime.utcnow()

        try:
            # Parse deployed policies
            policies = await self._fetch_policies_from_s3(event.artifact_location)

            # Update Neptune graph atomically
            async with self.neptune.transaction() as tx:
                # Clear existing policy edges for affected agents
                for policy in policies:
                    await tx.execute(f"""
                        g.V().hasLabel('Agent').has('name', '{policy.agent_name}')
                          .outE('HAS_CAPABILITY').where(inV().has('granted_by', 'policy'))
                          .drop()
                    """)

                # Create new capability edges from policy
                for policy in policies:
                    for tool_name, classification in policy.allowed_tools.items():
                        await tx.execute(f"""
                            g.V().hasLabel('Agent').has('name', '{policy.agent_name}')
                              .addE('HAS_CAPABILITY')
                              .to(g.V().hasLabel('Capability').has('name', '{tool_name}'))
                              .property('granted_by', 'policy')
                              .property('policy_version', '{policy.version}')
                              .property('grant_time', '{sync_start.isoformat()}')
                        """)

            sync_duration = (datetime.utcnow() - sync_start).total_seconds()

            # Publish sync completion event
            await self.eventbridge.put_events(
                Entries=[{
                    'Source': 'aura.capability-governance',
                    'DetailType': 'PolicyGraphSyncCompleted',
                    'Detail': json.dumps({
                        'policy_version': event.commit_sha,
                        'agents_updated': len(policies),
                        'sync_duration_seconds': sync_duration,
                    }),
                }]
            )

            return SyncResult(
                success=True,
                agents_updated=len(policies),
                sync_duration_seconds=sync_duration,
            )

        except Exception as e:
            # Alert on sync failure - graph may be stale
            await self._alert_sync_failure(event, e)
            raise


# EventBridge rule (CloudFormation)
# deploy/cloudformation/policy-graph-sync.yaml
"""
PolicyDeployedRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-policy-deployed-${Environment}'
    EventPattern:
      source:
        - aws.codepipeline
      detail-type:
        - CodePipeline Stage Execution State Change
      detail:
        pipeline:
          - !Sub '${ProjectName}-policy-pipeline-${Environment}'
        stage:
          - Deploy
        state:
          - SUCCEEDED
    Targets:
      - Id: PolicyGraphSyncLambda
        Arn: !GetAtt PolicyGraphSyncFunction.Arn
"""
```

### Daily Reconciliation Job

In addition to event-driven sync, a daily reconciliation job detects and alerts on any drift between policies and the Neptune graph.

```python
# src/services/capability_governance/reconciliation.py

class PolicyGraphReconciler:
    """Detect drift between policy repository and Neptune graph."""

    async def reconcile(self) -> ReconciliationResult:
        """
        Compare policies in DynamoDB with Neptune graph state.

        Runs daily via EventBridge scheduled rule.
        """
        drifts = []

        # Get all policies from DynamoDB
        policies = await self._get_all_policies()

        # Get all agent capabilities from Neptune
        graph_state = await self._get_graph_capabilities()

        for policy in policies:
            agent_name = policy.agent_name
            expected_caps = set(policy.get_all_capabilities())
            actual_caps = set(graph_state.get(agent_name, []))

            if expected_caps != actual_caps:
                drifts.append(DriftRecord(
                    agent_name=agent_name,
                    missing_in_graph=expected_caps - actual_caps,
                    extra_in_graph=actual_caps - expected_caps,
                ))

        if drifts:
            await self._alert_drift_detected(drifts)

        return ReconciliationResult(
            checked_agents=len(policies),
            drifts_detected=len(drifts),
            drifts=drifts,
        )
```

## Implementation

### Phase 1: Schema and Repository (Week 1-2)

| Task | Deliverable |
|------|-------------|
| Define JSON Schema for policies | `schema/*.schema.json` |
| Create repository structure | `capability-policies/` |
| Migrate existing policies to YAML | `agents/*.yaml` |
| Implement schema validation | `PolicyValidator._validate_schema()` |

### Phase 2: CI Pipeline (Week 2-3)

| Task | Deliverable |
|------|-------------|
| CodeBuild validation stage | `buildspec-policy-validate.yml` |
| Escalation path detection | `PolicyValidator._detect_escalation_paths()` |
| Policy simulation framework | `PolicySimulator` class |
| GitHub Actions integration | `.github/workflows/policy-validation.yml` |

### Phase 3: Deployment Pipeline (Week 3-4)

| Task | Deliverable |
|------|-------------|
| CodePipeline for policy deployment | `deploy/cloudformation/policy-pipeline.yaml` |
| S3 versioned artifact storage | Policy artifact bucket |
| DynamoDB atomic updates | `PolicyDeployer` class |
| Cache invalidation mechanism | EKS ConfigMap or Redis invalidation |

### Phase 4: Observability (Week 4)

| Task | Deliverable |
|------|-------------|
| Policy change audit logging | CloudWatch Logs + DynamoDB |
| Deployment metrics | CloudWatch dashboard |
| Rollback automation | Step Functions workflow |
| Alerting on policy violations | SNS + PagerDuty |

## AWS Services

| Service | Purpose |
|---------|---------|
| **S3** | Versioned policy artifact storage |
| **CodePipeline** | Deployment orchestration |
| **CodeBuild** | Validation and testing |
| **DynamoDB** | Runtime policy storage |
| **Neptune** | Capability graph (existing) |
| **CloudWatch** | Metrics and alerting |
| **AWS Config** | Policy drift detection |
| **Secrets Manager** | Approval tokens |

## Consequences

### Positive

- **Auditability**: Complete history of policy changes with commit SHAs
- **Safety**: Validation prevents deploying broken policies
- **Speed**: Policy updates without application deployment
- **Compliance**: Meets CMMC/SOX change management requirements
- **Collaboration**: Security team can review policies without code context

### Negative

- **Complexity**: Additional CI/CD pipeline to maintain
- **Learning curve**: Teams must learn policy schema
- **Latency**: Policy changes require PR + deployment (not instant)

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Policy deployment breaks agents | Simulation testing, canary deployment, instant rollback |
| Schema becomes too complex | Start simple, iterate based on real needs |
| Drift between repo and runtime | AWS Config drift detection, periodic reconciliation |

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Policy deployment latency | <5 minutes | Time from PR merge to live policy |
| Zero broken deployments | 0 rollbacks in first month | Rollback count in CloudWatch |
| Graph sync latency | <30 seconds | Time from deploy to Neptune update |
| Validation coverage | 100% of policies | All policies pass schema validation |
| Drift detection | <24 hours | Max time to detect policy/graph drift |

## Related ADRs

- **ADR-066**: Agent Capability Governance (foundation)
- **ADR-071**: Cross-Agent Capability Graph Analysis (consumes policies)
- **ADR-072**: ML-Based Anomaly Detection (uses policy as baseline)

## References

- [MI9: Runtime Governance Framework for Agentic AI](https://arxiv.org/abs/2508.03858) - Conformance engine with FSM-based temporal pattern matching
- [Open Policy Agent](https://www.openpolicyagent.org/)
- [HashiCorp Sentinel](https://www.hashicorp.com/sentinel)
- [AWS Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [GitOps Principles](https://opengitops.dev/)
