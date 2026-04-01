# ADR-041: AWS-Required Wildcards with Defense-in-Depth Compensating Controls

## Status
**Accepted** | December 16, 2025

## Context

During an IAM security audit (December 2025), several `Resource: '*'` patterns were identified in our CloudFormation templates. While these patterns appear to violate least-privilege principles, investigation revealed that many are **required by AWS** due to API limitations.

### Audit Findings

The following patterns use wildcards due to AWS API constraints:

| Resource Type | Location | AWS Requirement |
|--------------|----------|-----------------|
| ECR GetAuthorizationToken | VPC Endpoints, Permission Boundaries | Token is account-level, no resource scoping possible |
| CloudWatch PutMetricData | Multiple roles | Metrics API operates at namespace level, not resource |
| Service Catalog APIs | Test Environment IAM | Products/portfolios accessed by ID, not ARN |
| EKS AccessKubernetesApi | Test Environment IAM | Cluster access is cluster-scoped, not namespace |
| STS GetCallerIdentity | Lambda roles | Identity check has no resource scope |
| Logs resource policies | Step Functions | AWS requires `Resource: '*'` for log delivery |

### Security Concern

Unrestricted wildcards could enable:
- Cross-resource access within the account
- Privilege escalation via overly broad permissions
- Lateral movement if credentials are compromised

## Decision

**Accept AWS-required wildcards where technically necessary, but implement defense-in-depth compensating controls.**

We will NOT:
- Add restrictive resource policies that break functionality
- Implement blanket deny rules that prevent legitimate operations
- Create complex workarounds that add operational burden

We WILL:
- Document each wildcard with justification
- Implement compensating controls at other layers
- Use conditions where AWS supports them (e.g., `cloudwatch:namespace`)

## Compensating Controls

### 1. Permission Boundaries (Primary Defense)
All roles use permission boundaries that restrict access to test environment resources only:
- `${ProjectName}-testenv-*-${Environment}` patterns
- Explicit DENY for production resources
- Cross-region restrictions

### 2. VPC Endpoint Policies (Network Layer)
Gateway endpoints restrict traffic to scoped resources:
- S3: Only project buckets + ECR system buckets
- DynamoDB: Only project tables

### 3. Resource Tagging and Conditions
Where possible, conditions limit scope:
```yaml
Condition:
  StringEquals:
    'cloudwatch:namespace': !Sub '${ProjectName}/TestEnvironments'
```

### 4. Explicit DENY Statements
Critical resources are protected by explicit deny:
```yaml
- Sid: DenyProductionResources
  Effect: Deny
  Action: '*'
  Resource:
    - !Sub 'arn:${AWS::Partition}:dynamodb:*:*:table/${ProjectName}-*-prod'
    - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-prod'
```

### 5. IAM Policy Evaluation Order
AWS evaluates policies in this order:
1. Explicit DENY (highest priority)
2. Organization SCPs
3. Permission boundaries
4. Session policies
5. Identity policies

Our explicit DENY statements and permission boundaries provide effective containment even when action wildcards are used.

### 6. CloudTrail Audit Logging
All API calls are logged to CloudTrail with:
- 90-day retention (dev/qa), 365-day (prod)
- KMS encryption
- Tamper-evident storage in S3

### 7. GuardDuty Threat Detection
Anomalous API activity triggers alerts:
- Unusual credential usage patterns
- Geographic anomalies
- High-risk API calls

## Affected Templates

| Template | Wildcard Location | Compensating Control |
|----------|------------------|---------------------|
| `vpc-endpoints.yaml` | ECR GetAuthorizationToken | VPC endpoint policies, scoped S3/DynamoDB |
| `test-env-iam.yaml` | CloudWatch PutMetricData | Namespace condition |
| `test-env-iam.yaml` | Service Catalog APIs | Permission boundary, explicit deny |
| `test-env-iam.yaml` | STS GetCallerIdentity | Read-only, no risk |
| `iam.yaml` | Infrastructure wildcards | Region condition, resource naming |

## Alternatives Considered

### 1. Remove All Wildcards (Rejected)
- Would break AWS service functionality
- ECR authentication would fail
- CloudWatch metrics would not be published
- Service Catalog provisioning would fail

### 2. Custom Resource Policies (Rejected)
- Operational complexity too high
- Would require constant maintenance
- Limited AWS support for such patterns

### 3. Separate Accounts (Partial)
- Already implemented via environment separation (dev/qa/prod)
- GovCloud for production workloads
- Defense-in-depth at account boundary

## Consequences

### Positive
- AWS services function correctly
- Clear documentation of security rationale
- Multiple layers of compensating controls
- Audit trail for compliance reviews

### Negative
- Wildcards visible in IAM policy analyzer
- May trigger automated security scanning alerts
- Requires explanation during compliance audits

## Compliance Mapping

| Framework | Control | Status |
|-----------|---------|--------|
| CMMC AC.L2-3.1.3 | Control information flow | Compensated (VPC endpoints, boundaries) |
| NIST AC-3 | Access enforcement | Compensated (explicit deny, boundaries) |
| NIST AC-6 | Least privilege | Partial (documented exceptions) |
| SOC 2 CC6.1 | Logical access | Compensated (multi-layer controls) |

## References

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/)
- [VPC Endpoint Policies](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-access.html)
- [Permission Boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)
- IAM Security Audit (December 2025)
- Architecture Review (December 2025)
