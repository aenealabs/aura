# ADR-027: Security Group Management Pattern for Zero-Downtime Updates

## Status

Deployed

## Date

2025-12-07

## Context

Project Aura's security groups are foundational infrastructure that get attached to long-running services (EKS, Neptune, OpenSearch, VPC Endpoints). When CloudFormation needs to update a security group, it may trigger a resource replacement if certain properties are modified.

The challenge is that security groups attached to running services cannot be deleted - AWS protects against this because it would disconnect the Elastic Network Interfaces (ENIs). This creates a deployment deadlock:

1. CloudFormation tries to create a new security group
2. CloudFormation tries to delete the old security group
3. Deletion fails because ENIs are still attached
4. Stack update fails and rolls back
5. Or worse: stack gets stuck in DELETE_IN_PROGRESS indefinitely

This issue manifested when updating `security.yaml` to add new ingress rules for the RuntimeIncidentAgent (ADR-025).

## Decision

We will adopt the following security group management pattern across all CloudFormation templates:

### Pattern 1: Separate Ingress/Egress Resources

All security group ingress and egress rules must be defined as separate `AWS::EC2::SecurityGroupIngress` and `AWS::EC2::SecurityGroupEgress` resources, not inline within the security group definition.

**Before (Anti-pattern):**

```yaml
MySecurityGroup:
  Type: AWS::EC2::SecurityGroup
  Properties:
    GroupName: !Sub '${ProjectName}-my-sg-${Environment}'
    SecurityGroupIngress:
      - IpProtocol: tcp
        FromPort: 443
        ToPort: 443
        SourceSecurityGroupId: !Ref OtherSecurityGroup
```

**After (Correct pattern):**

```yaml
MySecurityGroup:
  Type: AWS::EC2::SecurityGroup
  Properties:
    GroupName: !Sub '${ProjectName}-my-sg-${Environment}'
    # No inline ingress/egress

MySecurityGroupIngressFromOther:
  Type: AWS::EC2::SecurityGroupIngress
  Properties:
    GroupId: !Ref MySecurityGroup
    IpProtocol: tcp
    FromPort: 443
    ToPort: 443
    SourceSecurityGroupId: !Ref OtherSecurityGroup
    Description: Allow HTTPS from OtherSecurityGroup
```

### Pattern 2: Use `aws cloudformation deploy`

Buildspecs should use `aws cloudformation deploy` instead of manually branching between `create-stack` and `update-stack`:

```bash
aws cloudformation deploy \
  --stack-name $STACK_NAME \
  --template-file deploy/cloudformation/security.yaml \
  --parameter-overrides Environment=$ENVIRONMENT ProjectName=$PROJECT_NAME VpcId=$VPC_ID \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --region $AWS_DEFAULT_REGION
```

Benefits:

- Automatically determines create vs update
- `--no-fail-on-empty-changeset` handles "no updates needed" gracefully
- Simpler error handling

### Pattern 3: Handle All Stack States

Buildspecs must explicitly handle these CloudFormation states:

| State | Action |
|-------|--------|
| `CREATE_COMPLETE` | Update via deploy |
| `UPDATE_COMPLETE` | Update via deploy |
| `UPDATE_ROLLBACK_COMPLETE` | Update via deploy (previous update failed, but deployable) |
| `ROLLBACK_COMPLETE` | Delete then create (initial creation failed) |
| `ROLLBACK_FAILED` | Delete then create (initial creation failed badly) |
| `DELETE_IN_PROGRESS` | **EXIT with error** - cannot proceed |
| `DELETE_FAILED` | **EXIT with error** - manual intervention required |

### Pattern 4: Never Delete Security Stacks with Active Dependencies

The buildspec should refuse to delete the security stack if other stacks depend on it. The only safe time to delete security groups is before dependent infrastructure is deployed (initial failures) or after all dependent infrastructure is deleted.

## Consequences

### Positive

1. **Zero-downtime updates**: Security group rules can be added, modified, or removed without service disruption
2. **Predictable deployments**: CloudFormation updates succeed reliably
3. **Clear error handling**: Stuck states produce actionable error messages
4. **Recovery guidance**: Recovery script helps diagnose and resolve issues

### Negative

1. **More verbose templates**: Each rule requires its own resource definition
2. **More resources to manage**: Template has more logical resources (though they're lightweight)

### Neutral

1. **No performance impact**: Separate ingress/egress resources create identical security group rules at runtime
2. **No cost impact**: Security group rules are free regardless of how they're defined

## Implementation

### Files Modified

1. **`deploy/cloudformation/security.yaml`**
   - All inline `SecurityGroupIngress` properties removed
   - Separate `AWS::EC2::SecurityGroupIngress` resources created for each rule
   - Comments added explaining the pattern

2. **`deploy/buildspecs/buildspec-foundation.yml`**
   - Security stack deployment now uses `aws cloudformation deploy`
   - Added handling for `DELETE_IN_PROGRESS`, `DELETE_FAILED`, `UPDATE_ROLLBACK_COMPLETE`
   - Added descriptive error messages with resolution guidance

3. **`deploy/scripts/recover-stuck-security-stack.sh`** (new)
   - Diagnostic script for troubleshooting stuck stacks
   - Provides resolution options based on stack state

## References

- [AWS CloudFormation Best Practices - Security Groups](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-security-group.html)
- [CloudFormation Resource Replacement Behavior](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html)
- ADR-025: RuntimeIncidentAgent (triggered this investigation)
