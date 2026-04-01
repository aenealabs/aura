# Guardrails

Institutional memory for Project Aura's specialized agents. This document captures lessons learned, patterns to follow, and anti-patterns to avoid.

> **Purpose:** Provide structured context for AI agents to avoid repeating mistakes and maintain consistency across the codebase.

---

## How to Use This Document

### For AI Agents
1. **Before implementation:** Query relevant guardrails by domain tag (e.g., `[CICD]`, `[IAM]`, `[SECURITY]`)
2. **During implementation:** Reference specific guardrail IDs when making decisions
3. **After failures:** Check if a guardrail already exists; if not, propose a new entry

### For Human Engineers
1. **Add new guardrails:** After significant debugging sessions or pattern discoveries
2. **Review periodically:** Ensure guardrails remain relevant as architecture evolves
3. **Cross-reference:** Link guardrails to ADRs for architectural context

---

## Guardrail Format

```
## GR-{DOMAIN}-{NUMBER}: {Title}

**Domain:** {Domain Tag}
**Severity:** Critical | High | Medium | Low
**Date Added:** YYYY-MM-DD
**Related:** {ADR links, file paths, external docs}

### Context
{What situation triggers this guardrail}

### Lesson Learned
{What went wrong or what was discovered}

### Required Pattern
{Exact pattern to follow with code examples}

### Anti-Pattern
{What NOT to do with examples}

### Verification
{How to confirm compliance}
```

---

## Active Guardrails

### GR-CICD-001: CodeBuild Buildspec Pattern Compliance

**Domain:** [CICD]
**Severity:** Critical
**Date Added:** 2025-12-04
**Related:** `deploy/buildspecs/buildspec-data.yml`, `deploy/buildspecs/buildspec-foundation.yml`, ADR-021

#### Context
When modifying or creating CodeBuild buildspec files for CloudFormation deployments.

#### Lesson Learned
CodeBuild's YAML parser is stricter than standard YAML parsers. Attempting to create new patterns (shell script libraries, single-line commands, custom branching logic) without checking existing patterns leads to `YAML_FILE_ERROR` failures and significant rework.

#### Required Pattern
**Always check existing buildspec files first.** The established patterns in this codebase are:

1. **Multiline block pattern** (`- |`) for complex deployment logic:
```yaml
      - |
        echo "Deploying Stack..."
        STACK_NAME="${PROJECT_NAME}-service-${ENVIRONMENT}"

        # Check if stack exists
        STACK_EXISTS=false
        if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_DEFAULT_REGION 2>/dev/null; then
          STACK_EXISTS=true
        fi

        # Create or update logic here
```

2. **Simple deploy pattern** (preferred when no conditional logic needed):
```yaml
      - aws cloudformation deploy \
          --stack-name ${PROJECT_NAME}-service-${ENVIRONMENT} \
          --template-file deploy/cloudformation/template.yaml \
          --parameter-overrides Environment=$ENVIRONMENT ProjectName=$PROJECT_NAME \
          --capabilities CAPABILITY_NAMED_IAM \
          --tags Project=$PROJECT_NAME Environment=$ENVIRONMENT \
          --no-fail-on-empty-changeset
```

3. **Comment boxes for phase separation** (preserves readability):
```yaml
      # ============================================
      # PHASE 1: Deploy First Resource
      # ============================================
```

#### Anti-Pattern
**Do NOT:**
- Create new shell script libraries for buildspec commands
- Use single-line commands where multiline blocks are established
- Mix patterns within the same buildspec
- Assume CodeBuild YAML parsing matches standard YAML tools

```yaml
# WRONG: Mixing patterns, creating new approaches
      - echo "Simple command"
      - source deploy/scripts/lib/cfn-deploy.sh  # Don't create new libraries
      - deploy_stack "my-stack" "template.yaml"   # Don't create new functions
```

#### Verification
1. Before modifying: `grep -A 20 "build:" deploy/buildspecs/buildspec-*.yml`
2. After modifying: Trigger CodeBuild and verify no YAML_FILE_ERROR
3. Pattern match: Compare your changes against `buildspec-data.yml` structure

---

### GR-IAM-001: No Wildcard Resources

**Domain:** [IAM]
**Severity:** Critical
**Date Added:** 2025-12-04
**Related:** `docs/security/GOVCLOUD_REMEDIATION_COMPLETE.md`, CMMC Level 2 requirements

#### Context
When creating or modifying IAM policies in CloudFormation templates.

#### Lesson Learned
Wildcard resources (`Resource: '*'`) violate CMMC Level 2 requirements and create security vulnerabilities. All IAM policies must be scoped to specific resources.

#### Required Pattern
```yaml
# CORRECT: Scoped to specific resources
Resource:
  - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-${Environment}'
  - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*-${Environment}/*'

# CORRECT: Using conditions to limit scope
Condition:
  StringEquals:
    aws:RequestedRegion: !Ref AWS::Region
```

#### Anti-Pattern
```yaml
# WRONG: Wildcard resource
Resource: '*'

# WRONG: Overly broad scope
Resource: 'arn:aws:s3:::*'
```

#### Verification
```bash
grep -r "Resource: '\*'" deploy/cloudformation/
grep -r 'Resource: "\*"' deploy/cloudformation/
```

---

### GR-CFN-001: GovCloud ARN Partitions

**Domain:** [CLOUDFORMATION]
**Severity:** High
**Date Added:** 2025-12-04
**Related:** `docs/cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md`

#### Context
When referencing AWS ARNs in CloudFormation templates.

#### Lesson Learned
Hardcoded `arn:aws` prefixes break deployments in AWS GovCloud (`arn:aws-us-gov`). Always use dynamic partition references.

#### Required Pattern
```yaml
# CORRECT: Dynamic partition
!Sub 'arn:${AWS::Partition}:service:${AWS::Region}:${AWS::AccountId}:resource'

# CORRECT: For managed policies, use Mappings
Mappings:
  PartitionMap:
    aws:
      EC2ReadOnly: arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess
    aws-us-gov:
      EC2ReadOnly: arn:aws-us-gov:iam::aws:policy/AmazonEC2ReadOnlyAccess
```

#### Anti-Pattern
```yaml
# WRONG: Hardcoded partition
Resource: 'arn:aws:s3:::my-bucket'
```

#### Verification
```bash
grep -r "arn:aws:" deploy/cloudformation/ | grep -v "aws:policy\|aws:partition\|aws:RequestedRegion"
```

---

### GR-CFN-002: CloudFormation Description Standards

**Domain:** [CLOUDFORMATION]
**Severity:** Medium
**Date Added:** 2025-12-04
**Related:** `CLAUDE.md#cloudformation-description-standards`

#### Context
When creating or modifying CloudFormation template descriptions.

#### Lesson Learned
Inconsistent descriptions make it difficult to understand stack purposes and deployment order. Standardized layer-based descriptions enable clear infrastructure organization.

#### Required Pattern
```yaml
# CodeBuild templates:
Description: 'Project Aura - {LayerName} Layer CodeBuild Project (Layer N: Major Services)'

# Infrastructure templates:
Description: 'Project Aura - Layer N - ServiceName (Brief Purpose)'
```

**Layer Reference:**
| Layer | Name | Major Services |
|-------|------|----------------|
| 1 | Foundation | VPC, IAM, WAF |
| 2 | Data | Neptune, OpenSearch, DynamoDB |
| 3 | Compute | EKS, ECR |
| 4 | Application | API Services |
| 5 | Observability | Monitoring, Secrets |
| 6 | Serverless | Lambda, Step Functions |
| 7 | Sandbox | Test Environments |
| 8 | Security | Config, GuardDuty |

#### Anti-Pattern
```yaml
# WRONG: Multi-line descriptions
Description: |
  This is a long description
  that spans multiple lines

# WRONG: Missing layer reference
Description: 'VPC Configuration'

# WRONG: Developer notes in description
Description: 'VPC - TODO: add more subnets later'
```

#### Verification
```bash
grep -A 1 "^Description:" deploy/cloudformation/*.yaml
```

---

### GR-SEC-001: SSM Parameter Store for Configuration

**Domain:** [SECURITY]
**Severity:** High
**Date Added:** 2025-12-04
**Related:** `CLAUDE.md#configuration--secrets-management`, `docs/PREREQUISITES_RUNBOOK.md`

#### Context
When storing configuration values (ARNs, endpoints, non-secret settings).

#### Lesson Learned
Hardcoded configuration values (account IDs, role ARNs, resource names) break across environments and create security/compliance issues. SSM Parameter Store provides free, centralized configuration management.

#### Required Pattern
```yaml
# SSM Naming Convention:
# Global: /aura/global/{parameter}
# Environment-specific: /aura/{env}/{parameter}
# Service-specific: /aura/{env}/{service}/{parameter}

# In buildspec:
env:
  parameter-store:
    ADMIN_ROLE_ARN: /aura/${ENVIRONMENT}/admin-role-arn

# In CloudFormation:
Resource: '{{resolve:ssm:/aura/global/codeconnections-arn}}'
```

#### Anti-Pattern
```yaml
# WRONG: Hardcoded ARN
AdminRoleArn: 'arn:aws:iam::123456789012:role/AdminRole'

# WRONG: Hardcoded account ID
AccountId: '123456789012'
```

#### Verification
```bash
grep -rE "[0-9]{12}" deploy/buildspecs/ deploy/cloudformation/
```

---

## Proposed Guardrails (Pending Review)

_None currently pending._

---

## Archived Guardrails

_Guardrails that are no longer applicable due to architecture changes._

_None currently archived._

---

## Changelog

| Date | Guardrail | Action | Author |
|------|-----------|--------|--------|
| 2025-12-04 | GR-CICD-001 | Added | Engineering |
| 2025-12-04 | GR-IAM-001 | Added | Engineering |
| 2025-12-04 | GR-CFN-001 | Added | Engineering |
| 2025-12-04 | GR-CFN-002 | Added | Engineering |
| 2025-12-04 | GR-SEC-001 | Added | Engineering |
