# Test Environment Operations Runbook

**Date Created:** 2025-12-15
**Last Updated:** 2025-12-15
**Owner:** Platform Team
**Status:** Production

## Overview

This runbook covers operational procedures for the self-service test environment provisioning system (ADR-039). It includes common operations, troubleshooting guides, and emergency procedures.

## Quick Reference

### Key Resources

| Resource | Location |
|----------|----------|
| State Table | `aura-test-env-state-{env}` (DynamoDB) |
| Cost Tracking | `aura-test-env-cost-tracking-{env}` (DynamoDB) |
| Service Catalog Portfolio | `aura Test Environments` |
| CloudWatch Dashboard | `aura-test-environments-{env}` |
| SNS Alert Topic | `aura-test-env-alerts-{env}` |

### Key CloudFormation Stacks

| Stack | Purpose | Layer |
|-------|---------|-------|
| `aura-test-env-state-{env}` | DynamoDB state table | 7.3 |
| `aura-test-env-iam-{env}` | IAM roles and permission boundary | 7.4 |
| `aura-test-env-catalog-{env}` | Service Catalog portfolio and products | 7.4 |
| `aura-test-env-approval-{env}` | HITL approval workflow (Lambda + Step Functions) | 7.5 |
| `aura-test-env-monitoring-{env}` | CloudWatch dashboard and alarms | 7.6 |
| `aura-test-env-budgets-{env}` | AWS Budgets and cost aggregator | 7.7 |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/environments` | GET | List user's environments |
| `/api/v1/environments` | POST | Create new environment |
| `/api/v1/environments/{id}` | GET | Get environment details |
| `/api/v1/environments/{id}` | DELETE | Terminate environment |
| `/api/v1/environments/{id}/extend` | POST | Extend TTL |
| `/api/v1/environments/templates` | GET | List available templates |
| `/api/v1/environments/quota` | GET | Get user's quota status |

---

## Common Operations

### 1. View All Active Environments

```bash
# Query DynamoDB for active environments
aws dynamodb scan \
  --table-name aura-test-env-state-dev \
  --filter-expression "#s = :active" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":active": {"S": "active"}}' \
  --query "Items[*].{id: environment_id.S, name: display_name.S, user: user_id.S, expires: expires_at.S}" \
  --output table \
  --region us-east-1
```

### 2. Check User's Quota Usage

```bash
# Count active environments for a user
USER_ID="user-123"
aws dynamodb query \
  --table-name aura-test-env-state-dev \
  --index-name user-created_at-index \
  --key-condition-expression "user_id = :uid" \
  --filter-expression "#s IN (:active, :prov, :pend)" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":uid": {"S": "'$USER_ID'"}, ":active": {"S": "active"}, ":prov": {"S": "provisioning"}, ":pend": {"S": "pending_approval"}}' \
  --select COUNT \
  --region us-east-1
```

### 3. Manually Terminate an Environment

```bash
# Update status to terminating
ENV_ID="env-abc123"
aws dynamodb update-item \
  --table-name aura-test-env-state-dev \
  --key '{"environment_id": {"S": "'$ENV_ID'"}}' \
  --update-expression "SET #s = :term, metadata.terminated_by = :admin, metadata.terminated_at = :now" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":term": {"S": "terminating"}, ":admin": {"S": "admin-manual"}, ":now": {"S": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}}' \
  --region us-east-1
```

### 4. Extend Environment TTL

```bash
# Calculate new expiry (add 24 hours)
ENV_ID="env-abc123"
NEW_EXPIRY=$(date -u -d '+24 hours' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+24H +%Y-%m-%dT%H:%M:%SZ)

aws dynamodb update-item \
  --table-name aura-test-env-state-dev \
  --key '{"environment_id": {"S": "'$ENV_ID'"}}' \
  --update-expression "SET expires_at = :exp" \
  --expression-attribute-values '{":exp": {"S": "'$NEW_EXPIRY'"}}' \
  --region us-east-1
```

### 5. View Service Catalog Products

```bash
# List portfolio
aws servicecatalog list-portfolios \
  --query "PortfolioDetails[?contains(DisplayName, 'aura')]" \
  --output table \
  --region us-east-1

# Get portfolio ID and list products
PORTFOLIO_ID=$(aws servicecatalog list-portfolios \
  --query "PortfolioDetails[?contains(DisplayName, 'aura')].Id" \
  --output text \
  --region us-east-1)

aws servicecatalog search-products-as-admin \
  --portfolio-id "$PORTFOLIO_ID" \
  --query "ProductViewDetails[*].ProductViewSummary.[Name,ProductId,Type]" \
  --output table \
  --region us-east-1
```

### 6. Check HITL Approval Status

```bash
# List pending approvals in Step Functions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:aura-test-env-approval-dev \
  --status-filter RUNNING \
  --query "executions[*].{name: name, start: startDate}" \
  --output table \
  --region us-east-1
```

---

## Troubleshooting

### Issue: Environment Stuck in "Provisioning" Status

**Symptoms:**
- Environment shows "provisioning" status for > 10 minutes
- No CloudFormation stack created

**Investigation:**

```bash
# Check Lambda logs
aws logs tail /aws/lambda/aura-test-env-provision-dev --since 30m --region us-east-1

# Check Step Functions execution
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:aura-test-env-approval-dev \
  --status-filter FAILED \
  --max-results 5 \
  --region us-east-1
```

**Resolution:**
1. Check Lambda execution logs for errors
2. Verify IAM permissions for Service Catalog launch role
3. Manually update status to "failed" if provisioning cannot complete

### Issue: Environment Not Terminating

**Symptoms:**
- Environment stuck in "terminating" status
- CloudFormation stack still exists

**Investigation:**

```bash
# Check for stuck CloudFormation stack
aws cloudformation describe-stacks \
  --query "Stacks[?contains(StackName, 'testenv')].[StackName,StackStatus]" \
  --output table \
  --region us-east-1

# Check Service Catalog provisioned products
aws servicecatalog describe-provisioned-product \
  --name "testenv-{environment_id}" \
  --region us-east-1
```

**Resolution:**
1. If CloudFormation stack is in DELETE_FAILED:
   ```bash
   aws cloudformation delete-stack --stack-name SC-{stack-id} --region us-east-1
   ```
2. If Service Catalog product stuck:
   ```bash
   aws servicecatalog terminate-provisioned-product \
     --provisioned-product-name "testenv-{id}" \
     --ignore-errors \
     --region us-east-1
   ```

### Issue: User Cannot Create Environments (Quota Error)

**Symptoms:**
- API returns 429 "Quota exceeded"
- User claims they don't have active environments

**Investigation:**

```bash
# Check actual count vs what DynamoDB shows
USER_ID="user-123"
aws dynamodb query \
  --table-name aura-test-env-state-dev \
  --index-name user-created_at-index \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid": {"S": "'$USER_ID'"}}' \
  --query "Items[*].{id: environment_id.S, status: status.S}" \
  --output table \
  --region us-east-1
```

**Resolution:**
1. If orphaned "active" environments exist, manually terminate them
2. Check if environments are stuck in "terminating" status
3. Temporarily increase user's quota limit

### Issue: CloudWatch Metrics Not Appearing

**Symptoms:**
- Dashboard shows no data
- Cost aggregator not publishing metrics

**Investigation:**

```bash
# Check Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=aura-test-env-cost-aggregator-dev \
  --start-time $(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum \
  --region us-east-1

# Check Lambda errors
aws logs tail /aws/lambda/aura-test-env-cost-aggregator-dev --since 1h --region us-east-1
```

**Resolution:**
1. Verify EventBridge rule is enabled
2. Check Lambda IAM permissions for CloudWatch:PutMetricData
3. Manually invoke Lambda to test:
   ```bash
   aws lambda invoke \
     --function-name aura-test-env-cost-aggregator-dev \
     --payload '{}' \
     /tmp/output.json \
     --region us-east-1
   ```

---

## Emergency Procedures

### Emergency: Mass Environment Termination

If many environments need immediate termination (e.g., security incident):

```bash
# Get all active environments
aws dynamodb scan \
  --table-name aura-test-env-state-dev \
  --filter-expression "#s = :active" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":active": {"S": "active"}}' \
  --query "Items[*].environment_id.S" \
  --output text \
  --region us-east-1 | tr '\t' '\n' | while read ENV_ID; do
    echo "Terminating $ENV_ID..."
    aws dynamodb update-item \
      --table-name aura-test-env-state-dev \
      --key '{"environment_id": {"S": "'$ENV_ID'"}}' \
      --update-expression "SET #s = :term" \
      --expression-attribute-names '{"#s": "status"}' \
      --expression-attribute-values '{":term": {"S": "terminating"}}' \
      --region us-east-1
done
```

### Emergency: Disable New Environment Creation

To temporarily disable new environment creation:

1. **Option 1: Disable Service Catalog access**
   ```bash
   # Revoke principal association
   aws servicecatalog disassociate-principal-from-portfolio \
     --portfolio-id port-XXXXX \
     --principal-arn "arn:aws:iam::ACCOUNT_ID:role/aura-test-env-user-role-dev" \
     --region us-east-1
   ```

2. **Option 2: Set all products to DISABLED**
   ```bash
   # Get product IDs and disable
   aws servicecatalog update-product \
     --id prod-XXXXX \
     --support-description "TEMPORARILY DISABLED" \
     --region us-east-1
   ```

### Emergency: Cost Overrun Response

If test environments are causing unexpected costs:

1. **Check current spend:**
   ```bash
   aws ce get-cost-and-usage \
     --time-period Start=$(date -u -d '-7 days' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
     --granularity DAILY \
     --filter '{"Tags": {"Key": "Component", "Values": ["test-environments"]}}' \
     --metrics "UnblendedCost" \
     --region us-east-1
   ```

2. **Identify high-cost environments:**
   ```bash
   aws dynamodb scan \
     --table-name aura-test-env-state-dev \
     --filter-expression "#s = :active" \
     --expression-attribute-names '{"#s": "status"}' \
     --expression-attribute-values '{":active": {"S": "active"}}' \
     --query "Items | sort_by(@, &cost_estimate_daily.N) | reverse(@)[0:5]" \
     --output table \
     --region us-east-1
   ```

3. **Terminate high-cost environments** (see mass termination above)

---

## Monitoring and Alerts

### CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| `aura-test-env-daily-cost-{env}` | Daily cost > $50 | SNS notification |
| `aura-test-env-provisioning-errors-{env}` | > 5 errors in 10 min | SNS notification |
| `aura-test-env-provisioning-latency-{env}` | p90 > 5 min | SNS notification |
| `aura-test-env-quota-exceeded-{env}` | > 10 quota exceeded/hr | SNS notification |
| `aura-test-env-cleanup-errors-{env}` | > 3 errors/hr | SNS notification |

### Key Metrics to Monitor

- `Aura/TestEnvironments/ActiveEnvironments` - Total active environments
- `Aura/TestEnvironments/EstimatedDailyCost` - Current daily cost estimate
- `Aura/TestEnvironments/ProvisioningDuration` - Time to provision
- `Aura/TestEnvironments/ProvisioningErrors` - Provisioning failures
- `Aura/TestEnvironments/CleanupErrors` - Cleanup/termination failures

---

## Maintenance Procedures

### Weekly: Orphaned Resource Cleanup

```bash
# Find environments terminated > 7 days ago but TTL hasn't cleaned up
aws dynamodb scan \
  --table-name aura-test-env-state-dev \
  --filter-expression "#s = :term AND created_at < :cutoff" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":term": {"S": "terminated"}, ":cutoff": {"S": "'$(date -u -d '-7 days' +%Y-%m-%dT%H:%M:%SZ)'"}}' \
  --query "Items[*].environment_id.S" \
  --output text \
  --region us-east-1
```

### Monthly: Cost Review

1. Review CloudWatch dashboard for cost trends
2. Identify users with high usage patterns
3. Review and update budget thresholds if needed
4. Check for any terminated environments with orphaned resources

### Quarterly: Template Review

1. Review Service Catalog product versions
2. Update cost estimates if AWS pricing has changed
3. Review and update IAM permission boundaries
4. Test all templates in sandbox environment

---

## Related Documentation

- [ADR-039: Self-Service Test Environments](../architecture-decisions/ADR-039-self-service-test-environments.md)
- [ADR-039 Service Catalog Deployment Runbook](./ADR039_SERVICE_CATALOG_DEPLOYMENT.md)
- [Layer 7 Sandbox Runbook](./LAYER7_SANDBOX_RUNBOOK.md)
- [CI/CD Setup Guide](../deployment/CICD_SETUP_GUIDE.md)

---

## Change History

| Date | Change | Author |
|------|--------|--------|
| 2025-12-15 | Initial version | Platform Team |
