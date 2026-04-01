# ADR-012: OpenSearch IAM Master User Authentication

**Status:** Deployed
**Date:** 2025-11-29
**Decision Makers:** Project Aura Team

## Context

OpenSearch with Fine-Grained Access Control (FGAC) requires authentication for all operations, including the Security plugin API used to configure role mappings. We needed to decide how to authenticate the master user for administrative operations.

OpenSearch FGAC offers two master user authentication modes:

1. **Internal User Database**: Username/password stored in OpenSearch
2. **IAM Master User**: IAM role becomes the master user, authenticated via SigV4

Our deployment required initial FGAC configuration (mapping the IRSA role to `all_access`) from the CI/CD pipeline (CodeBuild → EKS pod).

## Decision

We chose **IAM Master User authentication** using the IRSA role as the OpenSearch master user.

```yaml
# deploy/cloudformation/opensearch.yaml
AdvancedSecurityOptions:
  Enabled: true
  InternalUserDatabaseEnabled: false
  MasterUserOptions:
    MasterUserARN: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-api-irsa-role-${Environment}'
```

All administrative operations use SigV4 signing with IRSA credentials—no passwords required.

## Alternatives Considered

### 1. Internal Master User (Username/Password) - Rejected

```yaml
AdvancedSecurityOptions:
  InternalUserDatabaseEnabled: true
  MasterUserOptions:
    MasterUserName: admin
    MasterUserPassword: '{{resolve:secretsmanager:...}}'
```

**Pros:**
- Simple to understand
- Works with any HTTP client (curl, etc.)

**Cons:**
- Password management overhead (rotation, storage in Secrets Manager)
- Requires both SigV4 (for resource policy) AND basic auth (for Security API)
- Password could be exposed in logs if not careful
- Additional dependency on Secrets Manager

### 2. Lambda Custom Resource for Initial Setup - Rejected

Use a CloudFormation custom resource backed by Lambda to configure role mappings during stack creation.

**Pros:**
- One-time setup during deployment
- Lambda has its own IAM role

**Cons:**
- Additional infrastructure complexity (Lambda, VPC config)
- Harder to debug and maintain
- Still requires some form of admin authentication

### 3. Disable FGAC Entirely - Rejected

Rely only on resource-based policies without fine-grained internal access control.

**Pros:**
- Simplest approach
- No authentication complexity

**Cons:**
- All-or-nothing access (no granular permissions)
- Not suitable for multi-tenant or least-privilege environments
- Doesn't meet enterprise security requirements

## Consequences

### Positive
- **No password management**: Eliminates need for Secrets Manager password storage/rotation
- **Single authentication method**: Only SigV4 signing needed (no dual auth complexity)
- **IRSA integration**: Leverages existing EKS IRSA infrastructure
- **Audit trail**: All API calls tied to IAM role (CloudTrail visibility)
- **Least privilege**: IRSA role can be scoped precisely

### Negative
- **Initial role must exist**: IRSA role must be created before OpenSearch domain
- **IAM dependency**: Authentication tied to AWS IAM (not portable)
- **Stack ordering**: Requires careful CloudFormation dependency management

### Neutral
- Resource-based policy still needed to allow the IAM role access
- Role mapping still required for non-master users (but can be done by master)

## Implementation Notes

1. **Stack Dependencies**: IRSA role stack must deploy before OpenSearch stack
2. **Access Policy**: Resource policy must include the master user IAM role
3. **Security API Calls**: Use `boto3` or `opensearch-py` with `AWSV4SignerAuth`
4. **No basic auth needed**: Remove password from Secrets Manager (optional cleanup)

## References

- [AWS OpenSearch Fine-Grained Access Control](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/fgac.html)
- [OpenSearch Security Plugin API](https://opensearch.org/docs/latest/security/access-control/api/)
- [AWS SigV4 Signing](https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html)
- [EKS IRSA Documentation](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
