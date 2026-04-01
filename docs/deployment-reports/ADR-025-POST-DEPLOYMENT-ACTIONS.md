# ADR-025 Post-Deployment Actions

**Date**: December 7, 2025
**Status**: Connectivity RESOLVED, minor cleanup needed for IaC compliance
**Priority**: Low (non-blocking)

---

## Quick Summary

ADR-025 RuntimeIncidentAgent deployment is **functionally complete** with connectivity issue resolved. The following actions ensure full Infrastructure-as-Code compliance and optimal performance.

---

## Action Items

### 1. Remove Manual Security Group Rule (IaC Compliance)

**What**: The S3 prefix list egress rule was added manually via CLI for urgent testing.

**Why**: Manual rules break IaC single-source-of-truth principle (CLAUDE.md standard).

**When**: After confirming template deployment works in next Foundation layer update.

**How**:
```bash
# Remove manually-added S3 egress rule
aws ec2 revoke-security-group-egress \
  --group-id sg-0example000000014 \
  --security-group-rule-ids sgr-0example000000002 \
  --region us-east-1

# Then redeploy via CodeBuild to add it properly via CloudFormation
aws codebuild start-build \
  --project-name aura-foundation-deploy-dev \
  --region us-east-1
```

**Verification**:
```bash
# Verify rule exists in CloudFormation stack (not just AWS)
aws cloudformation describe-stack-resources \
  --stack-name aura-security-dev \
  --query 'StackResources[?LogicalResourceId==`ECSWorkloadToS3`]' \
  --output table
```

---

### 2. Agent Execution Timeout Tuning (Performance)

**Issue**: RuntimeIncidentAgent takes 15+ minutes (expected 2-4 minutes).

**Tracking**: GitHub Issue #10

**Likely Causes**:
1. Neptune/OpenSearch queries slow or timing out (connectivity exists, performance issue)
2. Bedrock API calls taking very long
3. Missing error handling causing silent waits

**Investigation Steps**:
```bash
# Add instrumentation to agent code
# Check logs for bottleneck:
aws logs tail /ecs/aura-runtime-incident-dev --since 20m --filter-pattern "INFO"

# Test Neptune connectivity from ECS task
kubectl run neptune-test --rm -it --image=amazonlinux:2 -- bash -c \
  "yum install -y telnet && telnet neptune.aura.local 8182"

# Test OpenSearch connectivity
kubectl run opensearch-test --rm -it --image=curlimages/curl -- \
  curl -v http://opensearch.aura.local:9200
```

**Fix Candidates**:
- Add timeout parameters to Neptune/OpenSearch clients
- Add retry logic with exponential backoff
- Add progress logging to identify slow operations
- Consider mocking Neptune/OpenSearch for test data (use real for production)

---

### 3. Add Missing IAM Permission

**Issue**: `AccessDeniedException` for `logs:FilterLogEvents` (seen in agent logs).

**Impact**: Low - agent continues without CloudWatch Logs query ability.

**Fix**:
Add to `deploy/cloudformation/incident-investigation-workflow.yaml` ECSTaskRole:

```yaml
ECSTaskRole:
  Properties:
    Policies:
      - PolicyName: IncidentAgentPolicy
        PolicyDocument:
          Statement:
            # Add this statement
            - Effect: Allow
              Action:
                - 'logs:FilterLogEvents'
                - 'logs:GetLogEvents'
              Resource:
                - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/ecs/*'
```

**Deploy**: Via `./deploy/scripts/deploy-incident-investigation-workflow.sh`

---

### 4. Investigate CloudFormation Template Sync Issue

**Observation**: `ECSWorkloadToS3` resource exists in security.yaml but not in deployed stack.

**Hypothesis**: CloudFormation detected manually-added rule and reported "no changes".

**Resolution**: After removing manual rule (Action #1), resource should deploy properly.

**Verification**:
```bash
# Check Build #39 or #40 logs for "No updates are to be performed"
aws codebuild batch-get-builds \
  --ids aura-foundation-deploy-dev:<BUILD_ID> \
  --query 'builds[0].logs.deepLink'
```

**If still not deploying**:
- Validate template syntax around line 414-422
- Check for duplicate resource name in template
- Try deploying to a test stack from scratch

---

## Success Criteria

- [ ] Manual S3 egress rule (sgr-0example000000002) removed
- [ ] CloudFormation stack has `ECSWorkloadToS3` resource (not just manual rule)
- [ ] Agent investigation completes in <5 minutes
- [ ] `logs:FilterLogEvents` permission added to task role
- [ ] 100% Infrastructure-as-Code compliance (no manual rules)

---

## Current State (As of Dec 7, 2025)

### What's Working

✅ ECS Fargate tasks pull images from ECR successfully
✅ RuntimeIncidentAgent container starts and executes
✅ Centralized security group architecture deployed
✅ Step Functions workflow configured correctly

### Manual Changes (Temporary)

⚠️ S3 prefix list egress rule (sgr-0example000000002) added via CLI - needs CloudFormation sync

### Pending Optimization

⏳ Agent execution time (Issue #10)
⏳ IAM permissions (logs:FilterLogEvents)

---

##Timeline Estimate

| Action | Duration | Priority |
|--------|----------|----------|
| Remove manual rule + redeploy | 15 min | Low (works as-is) |
| Add IAM permission | 10 min | Low (agent works without it) |
| Debug agent timeout | 1-2 hours | Medium (Issue #10) |

**Total**: 2-3 hours (can be done over multiple sessions)

---

## References

- **Session Report**: docs/deployment-reports/ADR-025-DEPLOYMENT-SESSION-2025-12-07.md
- **GitHub Issue**: https://github.com/aenealabs/aura/issues/10
- **Template File**: deploy/cloudformation/security.yaml (lines 414-422)
- **Deployment Script**: deploy/scripts/deploy-incident-investigation-workflow.sh
- **Architecture Analysis**: Provided S3 prefix list diagnosis and resolution strategy

---

**Priority**: All items are **non-blocking** for core platform development. Complete when convenient to maintain IaC best practices.
