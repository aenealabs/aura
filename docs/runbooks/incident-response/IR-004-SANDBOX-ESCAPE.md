# IR-004: Sandbox Escape Incident Response Playbook

**Version:** 1.0
**Last Updated:** January 25, 2026
**Owner:** Security Team
**Classification:** Public

---

## 1. Overview

### 1.1 Purpose
This playbook provides procedures for responding to sandbox escape attempts including container breakouts, network isolation bypasses, and privilege escalation within Aura's HITL sandbox environments.

### 1.2 Scope
Applies to escape attempts from:
- EKS pod containers (patch validation sandboxes)
- Ephemeral test environments
- Code execution sandboxes (Code Interpreter Agent)
- Network-isolated validation environments
- Agent execution contexts

### 1.3 MITRE ATT&CK Mapping
| Technique | ID | Description |
|-----------|-----|-------------|
| Escape to Host | T1611 | Container escape via vulnerabilities |
| Exploitation for Privilege Escalation | T1068 | Exploit to gain elevated privileges |
| Network Service Discovery | T1046 | Scanning for accessible services |
| Exploitation of Remote Services | T1210 | Exploiting services outside sandbox |

---

## 2. Severity Classification

| Severity | Criteria | Response Time |
|----------|----------|---------------|
| **Critical** | Confirmed escape to host or production network | Immediate (< 15 min) |
| **High** | Attempted escape with partial success | < 1 hour |
| **Medium** | Blocked escape attempt with IOCs | < 4 hours |
| **Low** | Anomalous sandbox behavior (no escape evidence) | < 24 hours |

---

## 3. Detection

### 3.1 Detection Sources

| Source | Alert Type | SNS Topic |
|--------|------------|-----------|
| Falco | Container syscall anomaly | `aura-security-alerts-{env}` |
| GuardDuty | Container threat detection | `aura-iam-security-alerts-{env}` |
| VPC Flow Logs | Unexpected network egress | `aura-security-alerts-{env}` |
| CloudTrail | API calls from sandbox IAM | `aura-security-alerts-{env}` |
| EKS Audit Logs | Pod privilege escalation | `aura-security-alerts-{env}` |

### 3.2 Indicators of Compromise (IOCs)

**Container Escape Indicators:**
- Syscalls: `mount`, `ptrace`, `setns`, `unshare` from sandbox pods
- Access to `/proc/1/root` or host filesystem paths
- Docker socket access attempts (`/var/run/docker.sock`)
- Privileged capability requests (`CAP_SYS_ADMIN`, `CAP_NET_ADMIN`)
- cgroup escape patterns (`release_agent` writes)

**Network Isolation Bypass:**
- Traffic to production VPC CIDRs from sandbox
- DNS queries for internal service endpoints
- Attempts to reach Neptune/OpenSearch from sandbox
- Traffic on ports not in sandbox allowlist
- ARP spoofing or VLAN hopping attempts

**Privilege Escalation:**
- ServiceAccount token access attempts
- IMDS (169.254.169.254) queries from restricted pods
- Kubernetes API server requests from sandboxes
- IAM role assumption from sandbox contexts

### 3.3 Detection Queries

**Falco Rules for Sandbox Escape:**
```yaml
# /etc/falco/rules.d/aura-sandbox.yaml
- rule: Sandbox Container Escape Attempt
  desc: Detect container escape techniques from sandbox pods
  condition: >
    container.name startswith "sandbox-" and
    (evt.type in (mount, ptrace, setns, unshare) or
     fd.name startswith "/proc/1" or
     fd.name = "/var/run/docker.sock")
  output: >
    Sandbox escape attempt (user=%user.name command=%proc.cmdline
    container=%container.name pod=%k8s.pod.name)
  priority: CRITICAL
  tags: [container, escape, aura]
```

**CloudWatch Logs Insights - Sandbox Network Anomalies:**
```
fields @timestamp, srcAddr, dstAddr, dstPort, action
| filter logGroup like /vpc-flow-logs/
| filter srcAddr like /10\.100\./ # Sandbox CIDR
| filter dstAddr not like /10\.100\./ # Traffic leaving sandbox
| filter action = "ACCEPT"
| stats count(*) as attempts by dstAddr, dstPort
| sort attempts desc
| limit 50
```

**GuardDuty Finding Types:**
- `Execution:Container/MaliciousFile`
- `PrivilegeEscalation:Container/SuspiciousCommands`
- `Persistence:Container/ContainerBackdoor`
- `Discovery:Container/ServiceDiscovery`

---

## 4. Containment

### 4.1 Immediate Actions (First 15 Minutes)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Isolate affected sandbox (network policy) | On-Call Engineer |
| 2 | Terminate compromised pods | On-Call Engineer |
| 3 | Block sandbox IAM role | On-Call Engineer |
| 4 | Capture forensic evidence | On-Call Engineer |
| 5 | Alert security team | On-Call Engineer |

### 4.2 Network Isolation

**Apply Emergency Network Policy:**
```bash
# Create deny-all network policy for sandbox namespace
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: emergency-isolate-sandbox
  namespace: aura-sandbox-${ENV}
spec:
  podSelector: {}  # All pods in namespace
  policyTypes:
  - Ingress
  - Egress
  # No ingress/egress rules = deny all
EOF
```

**Block Sandbox Security Group:**
```bash
# Get sandbox security group
SANDBOX_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=aura-sandbox-*" \
  --query 'SecurityGroups[0].GroupId' --output text)

# Revoke all egress (nuclear option)
aws ec2 revoke-security-group-egress \
  --group-id ${SANDBOX_SG} \
  --ip-permissions '[{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]'
```

### 4.3 Pod Termination

**Force terminate compromised pods:**
```bash
# Identify sandbox pods
kubectl get pods -n aura-sandbox-${ENV} \
  -l sandbox-session-id=${SESSION_ID} -o name

# Force delete (no grace period)
kubectl delete pods -n aura-sandbox-${ENV} \
  -l sandbox-session-id=${SESSION_ID} \
  --grace-period=0 --force
```

**Cordon the node (prevent scheduling):**
```bash
# Get node running compromised pod
NODE=$(kubectl get pod ${POD_NAME} -n aura-sandbox-${ENV} \
  -o jsonpath='{.spec.nodeName}')

# Cordon to prevent new pods
kubectl cordon ${NODE}

# Drain existing pods if needed
kubectl drain ${NODE} --ignore-daemonsets --delete-emptydir-data
```

### 4.4 IAM Containment

**Revoke sandbox role sessions:**
```bash
# Add inline policy to deny all actions for existing sessions
aws iam put-role-policy \
  --role-name aura-sandbox-execution-role-${ENV} \
  --policy-name EmergencyDenyAll \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "DateLessThan": {"aws:TokenIssueTime": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
      }
    }]
  }'
```

### 4.5 Evidence Preservation

**Capture pod state before termination:**
```bash
# Create forensics directory
FORENSICS_DIR="/tmp/ir004-${SESSION_ID}-$(date +%Y%m%d%H%M%S)"
mkdir -p ${FORENSICS_DIR}

# Capture pod description
kubectl describe pod ${POD_NAME} -n aura-sandbox-${ENV} \
  > ${FORENSICS_DIR}/pod-describe.txt

# Capture pod logs
kubectl logs ${POD_NAME} -n aura-sandbox-${ENV} --all-containers \
  > ${FORENSICS_DIR}/pod-logs.txt

# Capture events
kubectl get events -n aura-sandbox-${ENV} \
  --field-selector involvedObject.name=${POD_NAME} \
  > ${FORENSICS_DIR}/events.txt

# Export to forensics bucket
aws s3 cp ${FORENSICS_DIR} \
  s3://aura-security-forensics-${ENV}/ir004/$(date +%Y%m%d)/ \
  --recursive
```

**Capture Falco alerts:**
```bash
# Export Falco alerts for the pod
kubectl logs -n falco -l app=falco \
  --since=1h | grep ${POD_NAME} \
  > ${FORENSICS_DIR}/falco-alerts.txt
```

---

## 5. Eradication

### 5.1 Root Cause Analysis

| Question | Investigation Method |
|----------|---------------------|
| What vulnerability was exploited? | Falco alerts, container logs |
| Was the escape successful? | Host-level audit logs, CloudTrail |
| What resources were accessed? | VPC Flow Logs, CloudTrail |
| Was malware deployed? | Container image scan, filesystem analysis |
| Are other sandboxes affected? | Falco alert correlation |

### 5.2 Vulnerability Remediation

**If container image vulnerability:**
```bash
# Scan container image
aws ecr start-image-scan \
  --repository-name aura-sandbox-base \
  --image-id imageTag=latest

# Get scan results
aws ecr describe-image-scan-findings \
  --repository-name aura-sandbox-base \
  --image-id imageTag=latest
```

**If Kubernetes misconfiguration:**
```bash
# Audit pod security standards
kubectl get pods -n aura-sandbox-${ENV} \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.securityContext}{"\n"}{end}'

# Check for privileged containers
kubectl get pods -n aura-sandbox-${ENV} \
  -o json | jq '.items[].spec.containers[].securityContext'
```

### 5.3 Sandbox Hardening

**Verify Pod Security Standards:**
```yaml
# Enforce restricted PSS for sandbox namespace
apiVersion: v1
kind: Namespace
metadata:
  name: aura-sandbox-${ENV}
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

**Update sandbox security context:**
```yaml
# Required security context for sandbox pods
securityContext:
  runAsNonRoot: true
  runAsUser: 65534  # nobody
  runAsGroup: 65534
  fsGroup: 65534
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
```

### 5.4 Node Remediation

**If escape to host confirmed:**
```bash
# Terminate and replace the node
aws ec2 terminate-instances --instance-ids ${NODE_INSTANCE_ID}

# EKS will auto-scale replacement node
# Verify new node is clean
kubectl get nodes -o wide
```

---

## 6. Recovery

### 6.1 Service Restoration

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Deploy patched sandbox image | ECR scan clean |
| 2 | Restore network policies | kubectl get networkpolicy |
| 3 | Remove IAM deny policy | IAM policy check |
| 4 | Uncordon nodes | kubectl get nodes |
| 5 | Resume sandbox provisioning | Sandbox creation test |

### 6.2 Restore Sandbox Capability

**Remove emergency policies:**
```bash
# Remove emergency network policy
kubectl delete networkpolicy emergency-isolate-sandbox \
  -n aura-sandbox-${ENV}

# Remove IAM deny policy
aws iam delete-role-policy \
  --role-name aura-sandbox-execution-role-${ENV} \
  --policy-name EmergencyDenyAll

# Uncordon nodes
kubectl uncordon ${NODE}
```

**Validate sandbox functionality:**
```bash
# Create test sandbox
curl -X POST https://api.aura.local/sandbox/create \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"type": "validation", "timeout": 300}'

# Verify isolation
kubectl exec -it ${TEST_POD} -n aura-sandbox-${ENV} -- \
  curl --connect-timeout 5 http://neptune.aura.local:8182 || \
  echo "Network isolation verified"
```

### 6.3 Enhanced Monitoring

**Deploy enhanced Falco rules:**
```yaml
# Additional rules post-incident
- rule: Sandbox Process Ancestry Anomaly
  desc: Detect unusual process ancestry in sandbox
  condition: >
    container.name startswith "sandbox-" and
    proc.pname not in (bash, sh, python, node)
  output: Unusual process ancestry in sandbox (proc=%proc.name parent=%proc.pname)
  priority: WARNING
```

---

## 7. Escalation Matrix

| Severity | Primary | Secondary | Executive |
|----------|---------|-----------|-----------|
| Critical | On-Call Engineer | Security Lead + Platform Lead | CTO + CISO (within 30 min) |
| High | On-Call Engineer | Security Lead | CTO (within 2 hours) |
| Medium | On-Call Engineer | Security Lead | Weekly report |
| Low | On-Call Engineer | - | Monthly report |

**External Notification:**
- If customer data potentially accessed: Legal team immediately
- If CMMC-regulated workloads affected: Compliance officer within 24 hours

---

## 8. Post-Incident Activities

### 8.1 Incident Report
- [ ] Timeline of escape attempt and detection
- [ ] Attack vector and techniques used
- [ ] Evidence of successful/unsuccessful escape
- [ ] Resources accessed (if any)
- [ ] Containment and eradication actions
- [ ] Root cause and prevention measures

### 8.2 Prevention Measures
- [ ] Update container base images
- [ ] Review and tighten Pod Security Standards
- [ ] Enhance network policies
- [ ] Add Falco rules for detected technique
- [ ] Review sandbox IAM permissions
- [ ] Update threat model

### 8.3 Sandbox Architecture Review
- [ ] Audit all sandbox security contexts
- [ ] Review IRSA (IAM Roles for Service Accounts) bindings
- [ ] Validate network segmentation
- [ ] Test isolation with red team exercises
- [ ] Update HITL sandbox documentation

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│           SANDBOX ESCAPE - QUICK REFERENCE                  │
├─────────────────────────────────────────────────────────────┤
│ 1. ISOLATE  - Apply emergency NetworkPolicy (deny all)     │
│ 2. TERMINATE- Force delete compromised pods                │
│ 3. BLOCK    - Revoke sandbox IAM role sessions             │
│ 4. CAPTURE  - Export pod logs, Falco alerts, events        │
│ 5. CORDON   - Cordon affected node if escape confirmed     │
│ 6. ANALYZE  - Determine escape vector and success          │
│ 7. PATCH    - Update images, security contexts, policies   │
│ 8. RESTORE  - Remove emergency policies, validate function │
├─────────────────────────────────────────────────────────────┤
│ CRITICAL: Preserve evidence BEFORE terminating pods        │
│ CRITICAL: If escape confirmed, terminate affected node     │
└─────────────────────────────────────────────────────────────┘
```

## Appendix B: Sandbox Security Checklist

| Control | Check Command | Expected |
|---------|---------------|----------|
| Non-root user | `kubectl get pod -o jsonpath='{.spec.securityContext.runAsNonRoot}'` | `true` |
| Read-only root | `kubectl get pod -o jsonpath='{.spec.containers[*].securityContext.readOnlyRootFilesystem}'` | `true` |
| No privilege escalation | `kubectl get pod -o jsonpath='{.spec.containers[*].securityContext.allowPrivilegeEscalation}'` | `false` |
| Capabilities dropped | `kubectl get pod -o jsonpath='{.spec.containers[*].securityContext.capabilities.drop}'` | `["ALL"]` |
| Network policy exists | `kubectl get networkpolicy -n aura-sandbox-${ENV}` | Policy listed |
| IRSA configured | `kubectl get sa -o jsonpath='{.metadata.annotations}'` | eks.amazonaws.com/role-arn |

## Appendix C: Related Resources

- [HITL Sandbox Architecture](../../design/HITL_SANDBOX_ARCHITECTURE.md)
- [EKS Security Best Practices](https://aws.github.io/aws-eks-best-practices/security/docs/)
- [Falco Container Security](https://falco.org/docs/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
