# Infrastructure Deployment Runbooks

**Complete operational guides for Project Aura's modular CI/CD pipeline**

---

## Quick Reference

| Runbook | Purpose | Audience | Time Required |
|---------|---------|----------|---------------|
| [01-initial-setup.md](./01-initial-setup.md) | First-time CodeBuild setup | DevOps Engineers | 30-45 min |
| [02-routine-deployments.md](./02-routine-deployments.md) | Day-to-day infrastructure changes | All Engineers | 5-45 min |
| [03-troubleshooting.md](./03-troubleshooting.md) | Diagnose and fix deployment issues | DevOps, On-call | 5-60 min |
| [04-phase2-migration.md](./04-phase2-migration.md) | Scale to multi-team setup | Platform Team Lead | 2-4 hours |

---

## Getting Started

### New to Project Aura Infrastructure?

**Start here:**
1. Read [MODULAR_DEPLOYMENT.md](../MODULAR_DEPLOYMENT.md) - Understand the architecture
2. Follow [01-initial-setup.md](./01-initial-setup.md) - Set up CodeBuild pipeline
3. Practice with [02-routine-deployments.md](./02-routine-deployments.md) - Make your first change

### Existing Team Member?

**Common tasks:**
- **Deploy a change:** [02-routine-deployments.md](./02-routine-deployments.md)
- **Build failed:** [03-troubleshooting.md](./03-troubleshooting.md)
- **Scale team:** [04-phase2-migration.md](./04-phase2-migration.md)

---

## Runbook Details

### 01. Initial Setup

**When to use:** First time setting up infrastructure CI/CD

**What it covers:**
- Installing prerequisites (AWS CLI, cfn-lint)
- Creating SSM parameters
- Deploying CodeBuild stack
- Confirming email subscriptions
- Testing change detection
- Triggering first deployment
- Verifying infrastructure

**Prerequisites:**
- AWS account with admin access
- GitHub repository
- Valid email for alerts

**Success criteria:**
- CodeBuild project deployed
- All infrastructure stacks created
- Change detection working
- Email notifications confirmed

---

### 02. Routine Deployments

**When to use:** Day-to-day infrastructure changes

**What it covers:**
- Making infrastructure changes
- Testing change detection locally
- Committing and pushing changes
- Monitoring deployments
- Verifying changes

**Common scenarios:**
- Increase EKS node capacity
- Add new DynamoDB table
- Update Neptune instance size
- Multiple layer changes
- Emergency rollbacks
- Testing changes locally
- Force redeployment
- Multi-environment deployments

**Best practices:**
- Always test change detection first
- Use meaningful commit messages
- Make small, incremental changes
- Tag releases
- Monitor costs after changes

---

### 03. Troubleshooting

**When to use:** Builds failing or behaving unexpectedly

**What it covers:**
- Quick diagnostic commands
- Issue-by-issue troubleshooting
- Emergency procedures
- Common error messages

**Issues covered:**
1. Build fails in INSTALL phase
2. Build fails in PRE_BUILD phase (validation)
3. Change detection not working
4. CloudFormation stack update fails
5. Build times out
6. Webhook not triggering
7. Layer deploys in wrong order
8. IAM permission errors
9. Cost budget alerts failing

**For each issue:**
- Symptoms
- Diagnostic steps
- Common causes
- Resolution procedure

---

### 04. Phase 2 Migration

**When to use:** Team has grown, need separate projects per team

**What it covers:**
- When to migrate (and when not to)
- Pre-migration checklist
- Defining ownership model
- Backup procedures
- Updating CloudFormation template
- Testing new projects
- Configuring GitHub triggers
- Team-specific IAM roles
- Rollback procedures

**Migration benefits:**
- Team autonomy
- Parallel deployments
- Granular permissions
- Independent schedules

**Migration timeline:**
- Planning: 1-2 hours
- Execution: 2-3 hours
- Validation: 1 week
- Stabilization: 2-4 weeks

---

## Common Commands

### Check Build Status

```bash
# Latest build
aws codebuild list-builds-for-project \
  --project-name aura-infra-deploy-dev \
  --query 'ids[0]' --output text

# Build details
BUILD_ID=<build-id>
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase}'
```

### View Logs

```bash
# Real-time logs
aws logs tail /aws/codebuild/aura-infra-deploy-dev --follow

# Search errors
aws logs filter-log-events \
  --log-group-name /aws/codebuild/aura-infra-deploy-dev \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '30 minutes ago' +%s)000
```

### Stack Status

```bash
# List all stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'aura-')].{Name:StackName,Status:StackStatus}" \
  --output table

# Stack events
aws cloudformation describe-stack-events \
  --stack-name aura-networking-dev \
  --max-items 10
```

### Test Change Detection

```bash
# See what will deploy
python3 deploy/scripts/detect_changes.py

# Force all layers
python3 deploy/scripts/detect_changes.py --force-all
```

### Trigger Build

```bash
# Manual trigger
aws codebuild start-build \
  --project-name aura-infra-deploy-dev

# With environment override
aws codebuild start-build \
  --project-name aura-infra-deploy-dev \
  --environment-variables-override \
    name=ENVIRONMENT,value=dev,type=PLAINTEXT
```

---

## Decision Tree

### "Which runbook do I need?"

```
┌─────────────────────────────────────────┐
│ First time setting up infrastructure?   │
│              YES → 01-initial-setup     │
│              NO ↓                        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Is something broken?                     │
│              YES → 03-troubleshooting   │
│              NO ↓                        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Need to scale to multiple teams?        │
│              YES → 04-phase2-migration  │
│              NO ↓                        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Making routine changes?                  │
│              YES → 02-routine-deployments│
└─────────────────────────────────────────┘
```

---

## Infrastructure Layers Reference

Quick reference for which templates belong to which layer:

### Foundation Layer
- `networking.yaml` - VPC, subnets, NAT gateways
- `security.yaml` - Security groups
- `iam.yaml` - IAM roles and policies

**Owner:** Platform Team
**Deploy Time:** ~10 minutes
**Dependencies:** None

### Data Layer
- `neptune.yaml` - Graph database
- `opensearch.yaml` - Vector search
- `dynamodb.yaml` - NoSQL tables
- `s3.yaml` - Object storage

**Owner:** Data Engineering Team
**Deploy Time:** ~20 minutes
**Dependencies:** Foundation

### Compute Layer
- `eks.yaml` - Kubernetes cluster

**Owner:** DevOps Team
**Deploy Time:** ~15 minutes
**Dependencies:** Foundation

### Application Layer
- `aura-bedrock-infrastructure.yaml` - Bedrock LLM

**Owner:** Application Team
**Deploy Time:** ~5 minutes
**Dependencies:** Foundation, Data, Compute

### Observability Layer
- `secrets.yaml` - Secrets Manager
- `monitoring.yaml` - CloudWatch
- `aura-cost-alerts.yaml` - Budget alerts

**Owner:** SRE Team
**Deploy Time:** ~5 minutes
**Dependencies:** Foundation, Data

---

## Best Practices

### Before Every Deployment

1. **Test locally:** `python3 deploy/scripts/detect_changes.py`
2. **Validate templates:** `cfn-lint deploy/cloudformation/*.yaml`
3. **Review changes:** `git diff origin/main`
4. **Check permissions:** Ensure IAM roles have required permissions

### During Deployment

1. **Monitor logs:** `aws logs tail --follow`
2. **Watch for errors:** Check CloudFormation events
3. **Verify progress:** Check build phases
4. **Be ready to rollback:** Keep git revert ready

### After Deployment

1. **Verify resources:** Check stack outputs
2. **Test functionality:** Confirm apps work
3. **Monitor costs:** Check AWS Cost Explorer
4. **Update docs:** Document any changes
5. **Notify team:** Share deployment results

---

## Emergency Contacts

**For deployment issues:**
- **Slack:** #infrastructure-alerts
- **On-call:** See PagerDuty rotation
- **Email:** devops-team@example.com

**For AWS service outages:**
- **AWS Health Dashboard:** https://health.aws.amazon.com/health/status

---

## Additional Resources

### Documentation
- [MODULAR_DEPLOYMENT.md](../MODULAR_DEPLOYMENT.md) - Architecture and design
- [README.md](../README.md) - Deployment directory overview
- [AWS CloudFormation Docs](https://docs.aws.amazon.com/cloudformation/)
- [AWS CodeBuild Docs](https://docs.aws.amazon.com/codebuild/)

### Tools
- [cfn-lint](https://github.com/aws-cloudformation/cfn-lint) - Template validation
- [AWS CLI](https://aws.amazon.com/cli/) - Command line interface
- [jq](https://stedolan.github.io/jq/) - JSON processing

### Scripts
- `deploy/scripts/detect_changes.py` - Change detection
- `deploy/scripts/deploy-*.sh` - Layer deployment scripts
- `deploy/scripts/execute_buildspec.py` - BuildSpec executor

---

## Feedback and Improvements

Found an issue or have a suggestion?

1. **Create GitHub issue:** [Issues](https://github.com/aenealabs/aura/issues)
2. **Submit PR:** Improve runbooks and share with team
3. **Slack discussion:** #infrastructure channel
4. **Team meeting:** Bring up in weekly sync

---

## Changelog

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-11-11 | Initial runbook creation | Platform Team |

---

**Maintained By:** Platform Engineering Team
**Last Updated:** 2025-11-11
**Review Frequency:** Quarterly
