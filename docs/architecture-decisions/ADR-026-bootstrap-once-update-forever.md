# ADR-026: Bootstrap Once, Update Forever Pattern for Security Groups

**Status:** Deployed
**Date:** 2025-12-07
**Deciders:** Platform Engineering Team

## Context

CloudFormation security group stacks present a unique lifecycle challenge. Once security groups are attached to Elastic Network Interfaces (ENIs) from services like EKS, Neptune, and OpenSearch, they cannot be deleted without first terminating those dependent services.

The previous CI/CD logic in `buildspec-foundation.yml` would automatically attempt to delete stacks in `ROLLBACK_COMPLETE` state before recreating them. This approach works for most stacks but is dangerous for security groups:

```
Initial Bootstrap → Security Groups Created → EKS/Neptune Attach ENIs →
Template Update Fails → Stack enters ROLLBACK_COMPLETE →
CI/CD attempts delete → Delete hangs indefinitely (ENI dependencies) →
Security groups become orphaned from CloudFormation
```

This creates orphaned security groups that exist in AWS but are not managed by any CloudFormation stack, breaking infrastructure-as-code principles and complicating future deployments.

## Decision

Implement the **"Bootstrap Once, Update Forever"** pattern with an ENI dependency check before any deletion attempt:

### State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CloudFormation State Machine                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  DOES_NOT_EXIST ─────────────────────────────────────────→ CREATE      │
│                                                                         │
│  *_COMPLETE states ──────────────────────────────────────→ UPDATE      │
│    - CREATE_COMPLETE                                       (deploy)     │
│    - UPDATE_COMPLETE                                                    │
│    - UPDATE_ROLLBACK_COMPLETE                                          │
│                                                                         │
│  ROLLBACK_COMPLETE ──→ Check ENIs ──┬─→ ENIs=0 ────────→ DELETE+CREATE │
│  ROLLBACK_FAILED                    │                                   │
│                                     └─→ ENIs>0 ────────→ EXIT (error)  │
│                                                           + recovery    │
│                                                             guidance    │
│                                                                         │
│  *_IN_PROGRESS states ───────────────────────────────────→ EXIT (wait) │
│    - CREATE_IN_PROGRESS                                                 │
│    - UPDATE_IN_PROGRESS                                                 │
│    - UPDATE_ROLLBACK_IN_PROGRESS                                       │
│                                                                         │
│  DELETE_IN_PROGRESS ─────────────────────────────────────→ EXIT (wait) │
│  DELETE_FAILED ──────────────────────────────────────────→ EXIT+import │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### ENI Dependency Check

Before attempting to delete a security stack in `ROLLBACK_COMPLETE` state, query for attached ENIs:

```bash
ENI_COUNT=$(aws ec2 describe-network-interfaces \
  --filters "Name=group-name,Values=${PROJECT_NAME}-*-sg-${ENVIRONMENT}" \
  --query 'length(NetworkInterfaces)' \
  --output text)

if [ "$ENI_COUNT" != "0" ]; then
  # EXIT with error and recovery guidance
  # Never attempt deletion when ENIs exist
fi
```

### Recovery Guidance

When ENI dependencies exist, the CI/CD pipeline provides clear recovery options:

1. **RECOMMENDED:** Import orphaned security groups into a new CloudFormation stack:
   ```bash
   ./deploy/scripts/import-security-groups.sh
   ```

2. **DESTRUCTIVE:** Delete dependent services first (requires significant downtime):
   - Delete EKS cluster
   - Delete Neptune cluster
   - Delete OpenSearch domain
   - Then delete the security stack
   - Redeploy everything

## Consequences

### Positive

1. **Prevents orphaned resources:** Security groups never become orphaned from CloudFormation
2. **Maintains IaC principles:** All infrastructure remains under CloudFormation management
3. **Clear error messages:** Operators know exactly what went wrong and how to fix it
4. **Safe by default:** Never attempts destructive operations without checking dependencies
5. **Actionable guidance:** Error messages include specific commands for recovery

### Negative

1. **Manual intervention required:** When ENIs exist, the pipeline cannot auto-recover
2. **Slightly more complex logic:** The state machine has more branches to maintain

### Neutral

1. **Import script dependency:** Requires the `import-security-groups.sh` script to be maintained
2. **Documentation requirement:** Operators must understand the recovery process

## Implementation

### Files Modified

- `deploy/buildspecs/buildspec-foundation.yml` - Added ENI dependency check and comprehensive state machine

### Files Referenced

- `deploy/scripts/import-security-groups.sh` - CloudFormation resource import script for recovery
- `deploy/scripts/migrate-sg-references.sh` - Security group migration helper script

### Key Code Changes

1. **Added IN_PROGRESS state handling** - Exits with guidance to wait
2. **Added DELETE_* state handling** - Exits with import script reference
3. **Added ENI dependency check** - Queries `describe-network-interfaces` before deletion
4. **Enhanced error messages** - Include specific AWS CLI commands for diagnosis
5. **Maintained deploy command** - Continues using `aws cloudformation deploy --no-fail-on-empty-changeset`

## Verification

To verify the implementation:

1. **Happy path (no ENIs):** If stack is in ROLLBACK_COMPLETE with no ENIs, it deletes and recreates successfully
2. **ENI protection (with ENIs):** If stack is in ROLLBACK_COMPLETE with ENIs, it exits with error and guidance
3. **Normal updates:** If stack is in *_COMPLETE state, it updates via deploy command

### Test Commands

```bash
# Check current stack status
aws cloudformation describe-stacks \
  --stack-name aura-security-dev \
  --query 'Stacks[0].StackStatus'

# Check for ENI dependencies
aws ec2 describe-network-interfaces \
  --filters 'Name=group-name,Values=aura-*-sg-dev' \
  --query 'NetworkInterfaces[*].[NetworkInterfaceId,Description,Groups[0].GroupName]' \
  --output table
```

## Related Decisions

- **ADR-020:** Private ECR Base Images (controlled supply chain)
- **ADR-022:** GitOps with ArgoCD (deployment patterns)
- **GUARDRAILS.md:** GR-CICD-001 CodeBuild Buildspec Pattern Compliance

## References

- [CloudFormation Stack Statuses](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-describing-stacks.html#w2ab1c23c15c17c11)
- [CloudFormation Resource Import](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resource-import.html)
- [Security Group ENI Dependencies](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html#deleting-security-group)
