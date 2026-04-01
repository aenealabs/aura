# ADR-077: Cloud Runtime Security Integration

## Status

Deployed

## Date

2026-02-03

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

### Market Opportunity

Cloud runtime security represents a $12B+ market opportunity, with organizations increasingly recognizing that static analysis alone cannot protect cloud-native workloads. The gap between "shift-left" security (code scanning) and runtime protection creates blind spots that attackers exploit.

**Target Markets:**
- **Wiz** - Cloud security posture management
- **Google Cloud Security** - Container and Kubernetes security
- **Microsoft Defender for Cloud** - Runtime protection integration

**Market Opportunity:** Strong demand from enterprise customers requiring runtime-to-code correlation

### Current State

Project Aura excels at static code analysis through its hybrid GraphRAG architecture. However, several gaps exist for runtime security:

| Current Capability | Gap | Business Impact |
|-------------------|-----|-----------------|
| Static vulnerability detection | No runtime exploit correlation | Cannot prioritize actively exploited vulns |
| Code-level remediation | No Kubernetes admission control | Patches not enforced at deployment |
| Sandbox testing | No container escape detection | Limited protection in production |
| Graph-based code analysis | No runtime-to-code tracing | Cannot identify code causing alerts |

### Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| R1 | Kubernetes admission webhook for policy enforcement | Wiz/Google parity |
| R2 | Correlate CloudTrail/GuardDuty alerts to source code | Customer demand |
| R3 | Detect container escape attempts using eBPF | Security best practice |
| R4 | Integrate with Falco for runtime threat detection | Industry standard |
| R5 | Link IaC (Terraform/CloudFormation) to runtime state | DevSecOps workflow |
| R6 | Block deployment of vulnerable container images | CI/CD gate |
| R7 | Trace runtime behavior to git blame for attribution | Incident response |

## Decision

Implement a Cloud Runtime Security service cluster that bridges the gap between Aura's code intelligence and runtime protection, enabling organizations to correlate runtime threats to source code and enforce policies at deployment time.

### Core Services

### 1. Kubernetes Admission Controller

**Responsibilities:**
- Validating webhook for Pod, Deployment, and StatefulSet resources
- Policy enforcement based on SBOM attestation (ADR-076)
- Image signature verification using Sigstore/cosign
- Deny deployments with CRITICAL/HIGH vulnerabilities
- Integration with OPA/Gatekeeper for custom policies
- Audit mode for gradual policy rollout

**Enforcement Points:**
- Container image must have valid SBOM attestation
- No known CRITICAL CVEs in container dependencies
- Base image must be from approved registry (ADR private ECR)
- Resource limits must be specified (prevent resource exhaustion)
- Pod security standards (baseline/restricted) enforced

### 2. Runtime-to-Code Correlator

**Responsibilities:**
- Ingest CloudTrail events for AWS API activity
- Ingest GuardDuty findings for threat detection
- Ingest VPC Flow Logs for network anomalies
- Map runtime events to IaC resources (Terraform/CloudFormation)
- Trace IaC resources to source files via git blame
- Identify code owner responsible for vulnerable resources
- Generate remediation recommendations with code context

**Correlation Chain:**
```
Runtime Event → AWS Resource ARN → IaC Resource Definition →
Git File Path → Git Blame → Developer Attribution →
Neptune Code Graph → Related Vulnerabilities
```

### 3. Container Escape Detector

**Responsibilities:**
- Deploy eBPF-based monitoring agents to EKS nodes
- Detect privilege escalation attempts (setuid, capabilities)
- Monitor for container breakout syscalls (ptrace, mount namespace)
- Integrate with Falco for rule-based detection
- Correlate escape attempts to container image and code
- Real-time alerting via SNS/EventBridge

**Detection Categories:**
- Privilege escalation (CAP_SYS_ADMIN abuse)
- Namespace escape (mount, PID, network)
- Kernel exploits (dirty pipe, overlayfs)
- Symlink attacks (CVE-style container escapes)
- Resource abuse (cgroups escape)

## Architecture

### Cloud Runtime Security Architecture

```
+-----------------------------------------------------------------------------+
|                    Cloud Runtime Security Architecture                       |
+-----------------------------------------------------------------------------+
|                                                                              |
|  +--------------------------+    +---------------------------+               |
|  |    EKS Cluster          |    |     AWS Control Plane     |               |
|  |                          |    |                           |               |
|  |  +------------------+    |    |  +-------------------+    |               |
|  |  | Workload Pods    |    |    |  | CloudTrail        |----+--+           |
|  |  +------------------+    |    |  +-------------------+    |  |           |
|  |         |                |    |                           |  |           |
|  |         v                |    |  +-------------------+    |  |           |
|  |  +------------------+    |    |  | GuardDuty         |----+--+           |
|  |  | eBPF Agents      |----|----+  +-------------------+    |  |           |
|  |  | (Container       |    |    |                           |  |           |
|  |  |  Escape Detector)|    |    |  +-------------------+    |  |           |
|  |  +------------------+    |    |  | VPC Flow Logs     |----+--+           |
|  |                          |    |  +-------------------+    |  |           |
|  +--------------------------+    +---------------------------+  |           |
|         |                                                        |           |
|         v                                                        v           |
|  +----------------------------------------------------------------------+   |
|  |                    Event Ingestion Layer                              |   |
|  |                                                                       |   |
|  |  +---------------+  +---------------+  +---------------+              |   |
|  |  | Kinesis       |  | EventBridge   |  | SQS Queues    |              |   |
|  |  | Data Streams  |  | Event Bus     |  | (DLQ backed)  |              |   |
|  |  +---------------+  +---------------+  +---------------+              |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                   Runtime-to-Code Correlator                          |   |
|  |                                                                       |   |
|  |  +-------------------+    +-------------------+    +----------------+ |   |
|  |  | Event Parser      |    | Resource Mapper   |    | Code Tracer    | |   |
|  |  | - CloudTrail      |    | - ARN to IaC      |    | - IaC to Git   | |   |
|  |  | - GuardDuty       |--->| - IaC to Resource |--->| - Git Blame    | |   |
|  |  | - VPC Flow        |    | - State File      |    | - Neptune Link | |   |
|  |  +-------------------+    +-------------------+    +----------------+ |   |
|  |                                    |                       |          |   |
|  |                                    v                       v          |   |
|  |                           +----------------------------------+        |   |
|  |                           |    Correlation Store             |        |   |
|  |                           |    (DynamoDB + Neptune)          |        |   |
|  |                           +----------------------------------+        |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                  Kubernetes Admission Controller                      |   |
|  |                                                                       |   |
|  |  +---------------------------+    +-----------------------------+     |   |
|  |  | Validating Webhook        |    | Policy Engine               |     |   |
|  |  |                           |    |                             |     |   |
|  |  | - Image verification      |    | - OPA/Rego policies         |     |   |
|  |  | - SBOM attestation check  |--->| - CVE threshold rules       |     |   |
|  |  | - License compliance      |    | - Custom org policies       |     |   |
|  |  | - Resource limits         |    | - Audit mode support        |     |   |
|  |  +---------------------------+    +-----------------------------+     |   |
|  |         |                                                             |   |
|  |         v                                                             |   |
|  |  +---------------------------+                                        |   |
|  |  | Admission Decision        |                                        |   |
|  |  | ALLOW / DENY / WARN       |                                        |   |
|  |  +---------------------------+                                        |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
|  +----------------------------------------------------------------------+   |
|  |                Integration with Existing Aura Services               |   |
|  |                                                                       |   |
|  |  +----------------+  +----------------+  +------------------+         |   |
|  |  | SBOM Service   |  | Semantic       |  | Context          |         |   |
|  |  | (ADR-076)      |  | Guardrails     |  | Provenance       |         |   |
|  |  |                |  | (ADR-065)      |  | (ADR-067)        |         |   |
|  |  +----------------+  +----------------+  +------------------+         |   |
|  |                                                                       |   |
|  |  +----------------+  +----------------+  +------------------+         |   |
|  |  | Capability     |  | Neptune        |  | OpenSearch       |         |   |
|  |  | Governance     |  | Code Graph     |  | Vector Index     |         |   |
|  |  | (ADR-066)      |  |                |  |                  |         |   |
|  |  +----------------+  +----------------+  +------------------+         |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### eBPF Container Escape Detection

```
+-----------------------------------------------------------------------------+
|                    Container Escape Detection Architecture                   |
+-----------------------------------------------------------------------------+
|                                                                              |
|  EKS Worker Node                                                            |
|  +----------------------------------------------------------------------+   |
|  |                                                                       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |  | Container Workload       |    | Container Workload        |       |   |
|  |  | (Pod A)                  |    | (Pod B)                   |       |   |
|  |  +---------------------------+    +---------------------------+       |   |
|  |         |                              |                              |   |
|  |         | syscalls                     | syscalls                     |   |
|  |         v                              v                              |   |
|  |  +----------------------------------------------------------------------+|
|  |  |                    Linux Kernel                                       ||
|  |  |                                                                       ||
|  |  |  +---------------------+    +------------------------+                ||
|  |  |  | eBPF Probes         |    | Falco Rules Engine     |                ||
|  |  |  |                     |    |                        |                ||
|  |  |  | - kprobe/setuid     |    | - MITRE ATT&CK mapped  |                ||
|  |  |  | - kprobe/ptrace     |    | - Container escape     |                ||
|  |  |  | - kprobe/mount      |--->| - Privilege escalation |                ||
|  |  |  | - tracepoint/sched  |    | - Network anomaly      |                ||
|  |  |  | - LSM hooks         |    | - File integrity       |                ||
|  |  |  +---------------------+    +------------------------+                ||
|  |  +----------------------------------------------------------------------+|
|  |                   |                                                       |
|  +-------------------|-------------------------------------------------------+
|                      v                                                       |
|  +----------------------------------------------------------------------+   |
|  | Container Escape Detector Service                                    |   |
|  |                                                                       |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |  | Event Collector  |  | Threat Analyzer   |  | Alert Generator   |   |   |
|  |  |                  |  |                   |  |                   |   |   |
|  |  | - eBPF ringbuf   |  | - Pattern match   |  | - SNS publish     |   |   |
|  |  | - Falco gRPC     |->| - ML anomaly      |->| - EventBridge     |   |   |
|  |  | - Audit logs     |  | - Signature       |  | - Slack/PagerDuty |   |   |
|  |  +------------------+  +-------------------+  +-------------------+   |   |
|  |                                |                                      |   |
|  |                                v                                      |   |
|  |                       +-------------------+                           |   |
|  |                       | Container-to-Code |                           |   |
|  |                       | Correlator        |                           |   |
|  |                       |                   |                           |   |
|  |                       | Image -> SBOM ->  |                           |   |
|  |                       | Repo -> Git Blame |                           |   |
|  |                       +-------------------+                           |   |
|  +----------------------------------------------------------------------+   |
|                                                                              |
+-----------------------------------------------------------------------------+
```

## Data Models

### Neptune Graph Schema Extensions

```gremlin
// New Vertex Types

g.addV('RuntimeEvent')
  .property('id', event_id)
  .property('event_type', 'CloudTrail|GuardDuty|VPCFlow|Falco')
  .property('severity', 'LOW|MEDIUM|HIGH|CRITICAL')
  .property('aws_account_id', account)
  .property('region', region)
  .property('timestamp', event_time)
  .property('raw_event', json_blob)

g.addV('AWSResource')
  .property('id', resource_arn)
  .property('resource_type', 'EC2|EKS|Lambda|S3|...')
  .property('name', resource_name)
  .property('created_at', timestamp)
  .property('last_seen', timestamp)

g.addV('IaCResource')
  .property('id', iac_resource_id)
  .property('resource_type', 'aws_instance|aws_eks_cluster|...')
  .property('provider', 'terraform|cloudformation')
  .property('file_path', 'deploy/terraform/main.tf')
  .property('line_number', 42)
  .property('module', 'compute')

g.addV('ContainerImage')
  .property('id', image_digest)
  .property('repository', 'account.dkr.ecr.region.amazonaws.com/repo')
  .property('tag', 'v1.2.3')
  .property('sbom_id', sbom_reference)
  .property('signed', true)
  .property('scanned_at', timestamp)

g.addV('AdmissionDecision')
  .property('id', decision_id)
  .property('cluster', 'eks-cluster-name')
  .property('namespace', 'production')
  .property('resource_kind', 'Deployment')
  .property('resource_name', 'my-app')
  .property('decision', 'ALLOW|DENY|WARN')
  .property('policy_violations', ['CVE-2026-1234', 'missing-limits'])
  .property('timestamp', decision_time)

// New Edge Types

g.addE('TRIGGERED_BY').from(runtime_event).to(aws_resource)
  .property('correlation_confidence', 0.95)

g.addE('DEFINED_IN').from(aws_resource).to(iac_resource)
  .property('state_file', 'terraform.tfstate')
  .property('last_applied', timestamp)

g.addE('SOURCE_CODE').from(iac_resource).to(code_file)
  .property('line_start', 42)
  .property('line_end', 85)

g.addE('RUNS_IMAGE').from(kubernetes_pod).to(container_image)

g.addE('ESCAPE_ATTEMPT_FROM').from(escape_event).to(container_image)
  .property('technique', 'privilege_escalation')
  .property('mitre_id', 'T1611')

g.addE('ADMISSION_FOR').from(admission_decision).to(container_image)
```

### DynamoDB Tables

**aura-runtime-events-{env}:**
- PK: `event_id`
- GSI1: `resource_arn + timestamp` (query events by resource)
- GSI2: `severity + timestamp` (query by severity)
- Attributes: event_type, raw_event, correlation_status, code_path

**aura-resource-mappings-{env}:**
- PK: `aws_resource_arn`
- GSI: `iac_file_path + resource_name`
- Attributes: iac_provider, iac_resource_id, terraform_state_key, git_commit

**aura-admission-decisions-{env}:**
- PK: `cluster_name#namespace`
- SK: `timestamp#decision_id`
- Attributes: resource_kind, resource_name, decision, policy_violations, image_digest

**aura-escape-events-{env}:**
- PK: `cluster_name#node_id`
- SK: `timestamp#event_id`
- Attributes: container_id, image_digest, technique, syscall, blocked

### OpenSearch Indices

```json
{
  "aura-runtime-events": {
    "mappings": {
      "properties": {
        "event_id": { "type": "keyword" },
        "event_type": { "type": "keyword" },
        "severity": { "type": "keyword" },
        "resource_arn": { "type": "keyword" },
        "code_path": { "type": "keyword" },
        "description": { "type": "text" },
        "raw_event": { "type": "object", "enabled": false },
        "timestamp": { "type": "date" },
        "embedding": {
          "type": "knn_vector",
          "dimension": 1024,
          "method": { "name": "hnsw", "space_type": "cosinesimil" }
        }
      }
    }
  }
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/runtime/events` | Ingest runtime event |
| GET | `/api/v1/runtime/events/{id}` | Get event with correlations |
| GET | `/api/v1/runtime/events/by-resource/{arn}` | Events for AWS resource |
| POST | `/api/v1/runtime/correlate` | Trigger correlation for event |
| GET | `/api/v1/runtime/trace/{event_id}` | Full trace from event to code |
| POST | `/api/v1/admission/validate` | Kubernetes admission webhook |
| GET | `/api/v1/admission/policies` | List admission policies |
| POST | `/api/v1/admission/policies` | Create/update policy |
| GET | `/api/v1/admission/decisions` | Query admission decisions |
| GET | `/api/v1/escape/events` | List container escape events |
| GET | `/api/v1/escape/events/{id}` | Get escape event with context |
| POST | `/api/v1/escape/rules` | Configure detection rules |

## Implementation Plan

### Phase 1: Kubernetes Admission Controller (Weeks 1-4)

| Task | Effort | Deliverables |
|------|--------|--------------|
| Implement ValidatingWebhookConfiguration | 1 week | Webhook server, TLS setup |
| SBOM attestation verification | 1 week | Integration with ADR-076 |
| Image signature validation | 0.5 week | Cosign/Sigstore verification |
| OPA policy integration | 1 week | Rego policy engine |
| Audit mode and dry-run | 0.5 week | Non-blocking validation |

**Estimated LOC:** 4,500 lines Python + 800 lines Rego policies
**Tests:** 180 tests

### Phase 2: Runtime-to-Code Correlator (Weeks 5-7)

| Task | Effort | Deliverables |
|------|--------|--------------|
| CloudTrail event ingestion | 1 week | Kinesis consumer, parser |
| GuardDuty finding ingestion | 0.5 week | EventBridge integration |
| Resource-to-IaC mapping | 1 week | Terraform state parser |
| IaC-to-Git tracing | 0.5 week | Git blame integration |

**Estimated LOC:** 3,800 lines Python
**Tests:** 145 tests

### Phase 3: Container Escape Detector (Weeks 8-10)

| Task | Effort | Deliverables |
|------|--------|--------------|
| eBPF agent deployment | 1 week | DaemonSet, eBPF programs |
| Falco integration | 1 week | Falco sidecar, rule sync |
| Escape pattern detection | 0.5 week | Signature database |
| Container-to-code correlation | 0.5 week | Image SBOM lookup |

**Estimated LOC:** 3,200 lines (Python + eBPF C)
**Tests:** 95 tests

## Infrastructure Requirements

### CloudFormation Templates

| Template | Layer | Description |
|----------|-------|-------------|
| `runtime-security-data.yaml` | 2.9 | DynamoDB tables, Kinesis streams |
| `runtime-security-compute.yaml` | 3.6 | Lambda functions, EKS add-ons |
| `admission-controller.yaml` | 3.7 | Webhook deployment, certificates |
| `escape-detector.yaml` | 3.8 | DaemonSet, Falco configuration |
| `runtime-security-observability.yaml` | 5.7 | CloudWatch dashboards, alarms |

### EKS Requirements

- **Node IAM Role:** Additional permissions for eBPF agent
- **Pod Security Standards:** Privileged pods for eBPF (isolated namespace)
- **Webhook Certificates:** Managed by cert-manager or AWS ACM
- **Network Policy:** Allow webhook traffic from API server

## Security Considerations

### Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Webhook bypass via API server config | Low | Critical | Audit webhook configuration, alerting |
| False negative on CVE detection | Medium | High | Multiple vulnerability databases, regular updates |
| eBPF agent compromise | Low | Critical | Minimal privileges, signed eBPF programs |
| Correlation data poisoning | Medium | Medium | Source validation, provenance checks |
| Denial of service via webhook | Medium | High | Rate limiting, timeout configuration |

### Integration with Existing Security Controls

- **Semantic Guardrails (ADR-065):** Validate policy configurations against injection
- **Capability Governance (ADR-066):** Restrict admission controller agent permissions
- **Context Provenance (ADR-067):** Verify IaC source integrity before correlation
- **SBOM Attestation (ADR-076):** Attestation verification in admission webhook

### Compliance Alignment

| Framework | Control | Implementation |
|-----------|---------|----------------|
| CMMC 2.0 | SI.L2-3.14.6 | Container escape detection, alerting |
| NIST 800-53 | SI-4 | Runtime monitoring via eBPF |
| NIST 800-53 | CM-3 | Admission control for configuration changes |
| SOC 2 | CC6.1 | Audit trail for admission decisions |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Admission webhook latency P95 | <100ms | CloudWatch metrics |
| Event-to-code correlation accuracy | >90% | Sampled validation |
| Container escape detection rate | >95% | Red team exercises |
| False positive rate (admission) | <5% | Audit mode analysis |
| Time to correlate runtime event | <30 seconds | End-to-end testing |
| Admission webhook availability | 99.9% | CloudWatch alarms |

## Alternatives Considered

### Alternative 1: Use Wiz/Orca as Runtime Layer

Integrate with existing CSPM tools instead of building custom runtime security.

**Pros:**
- Faster time to market
- Proven technology
- Lower development cost

**Cons:**
- No differentiation - commodity feature
- Limited code correlation (Aura's strength)
- Vendor lock-in and licensing costs
- Cannot integrate with Neptune code graph

**Decision:** Rejected - runtime-to-code correlation is key differentiator

### Alternative 2: Falco-Only Detection (No Custom eBPF)

Use Falco as the sole runtime detection mechanism without custom eBPF agents.

**Pros:**
- Mature, community-supported project
- Extensive rule library
- Easier deployment

**Cons:**
- Less control over detection logic
- Cannot add custom Aura-specific detections
- Dependency on external project roadmap

**Decision:** Hybrid approach - use Falco for standard rules, custom eBPF for Aura-specific detection

### Alternative 3: Mutating Webhook Instead of Validating

Use mutating webhooks to auto-remediate issues instead of blocking.

**Pros:**
- Less friction for developers
- Automatic fixes applied

**Cons:**
- Security risk - auto-changes may introduce vulnerabilities
- Compliance concerns - unauthorized modifications
- Debugging complexity

**Decision:** Rejected - validating webhook with clear deny/allow is more secure and auditable

## Consequences

### Positive

1. **Runtime-to-Code Intelligence** - Unique capability to trace production issues to source
2. **Proactive Security** - Block vulnerable deployments before they reach production
3. **Incident Response** - Faster root cause analysis with code context
4. **Market Differentiation** - Bridges gap between SAST and runtime security
5. **Compliance** - Meets CMMC/NIST runtime monitoring requirements
6. **Developer Experience** - Clear feedback on why deployments are blocked

### Negative

1. **Latency Impact** - Admission webhook adds ~50-100ms to deployments
2. **Operational Complexity** - eBPF agents require privileged access
3. **False Positives** - Initial tuning period for policies
4. **Infrastructure Cost** - Additional compute for agents and correlation

### Migration Path

1. **Audit Mode First** - Deploy admission webhook in warn-only mode
2. **Gradual Enforcement** - Enable blocking for CRITICAL CVEs only
3. **Policy Expansion** - Add policies based on observed patterns
4. **Full Enforcement** - Block all policy violations after tuning

## Cost Estimate

### Monthly Infrastructure Cost

| Component | Unit Cost | Quantity | Monthly Cost |
|-----------|-----------|----------|--------------|
| Kinesis Data Streams | $0.015/shard-hour | 4 shards | $44 |
| Lambda (event processing) | $0.20/1M invocations | 50M | $10 |
| DynamoDB (on-demand) | $1.25/M writes | 100M writes | $125 |
| DynamoDB (reads) | $0.25/M reads | 500M reads | $125 |
| EC2 (webhook server) | $0.0416/hour (t3.medium) | 3 instances | $91 |
| EKS Add-on (Falco) | - | included | - |
| CloudWatch | $0.30/GB ingested | 50 GB | $15 |
| **Total** | | | **~$410/month** |

### Development Cost

| Phase | Weeks | Engineers | Total Cost |
|-------|-------|-----------|------------|
| Admission Controller | 4 | 2 | $80,000 |
| Runtime Correlator | 3 | 2 | $60,000 |
| Escape Detector | 3 | 2 | $60,000 |
| **Total** | 10 | | **$200,000** |

## GovCloud Compatibility

| Service | GovCloud Available | Notes |
|---------|-------------------|-------|
| EKS | Yes | Admission webhooks supported |
| Kinesis Data Streams | Yes | Full feature parity |
| Lambda | Yes | All runtimes available |
| DynamoDB | Yes | Full feature parity |
| GuardDuty | Yes | All finding types |
| CloudTrail | Yes | Required for compliance |
| VPC Flow Logs | Yes | Full feature parity |

**GovCloud-Specific Considerations:**
- Use `${AWS::Partition}` for all ARNs
- eBPF agents must use FIPS-validated crypto for signing
- Falco rules must not contain classified indicators
- Admission decisions logged for CMMC audit requirements

## References

- [Kubernetes Admission Controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Falco - Cloud Native Runtime Security](https://falco.org/)
- [eBPF for Security Monitoring](https://ebpf.io/applications/)
- [Sigstore Cosign](https://docs.sigstore.dev/cosign/overview/)
- [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/)
- [ADR-076: SBOM Attestation and Supply Chain Security](/docs/architecture-decisions/ADR-076-sbom-attestation-supply-chain.md)
- [ADR-065: Semantic Guardrails Engine](/docs/architecture-decisions/ADR-065-semantic-guardrails-engine.md)
- [ADR-066: Agent Capability Governance](/docs/architecture-decisions/ADR-066-agent-capability-governance.md)
- [ADR-067: Context Provenance and Integrity](/docs/architecture-decisions/ADR-067-context-provenance-integrity.md)
