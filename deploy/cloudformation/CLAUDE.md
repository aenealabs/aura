# CloudFormation Development Guide

> Universal security rules (secrets, container images, GovCloud ARNs) are in the root `CLAUDE.md`. This file covers CloudFormation-specific conventions.

---

## Stack Description Standards

**Stack Descriptions vs Resource Descriptions:**
- **Stack Description** (line 2 of template): Use the layer-based pattern below
- **Resource Description** (inside AWS resources): Use functional descriptions explaining what the resource does

**Patterns:**

CodeBuild Templates:
```
'Project Aura - {LayerName} Layer CodeBuild Project (Layer N.S: Major Services)'
```

Infrastructure Templates:
```
'Project Aura - Layer N.S - ServiceName (Brief Purpose)'
```

Where `N` = layer number (1-8) and `S` = sub-layer number within that layer.

**Layer Name Reference:**

| Layer | Name | Major Services |
|-------|------|----------------|
| 1 | Foundation | VPC, IAM, WAF, VPC Endpoints, Network Services |
| 2 | Data | Neptune, OpenSearch, DynamoDB, S3 |
| 3 | Compute | EKS, Node Groups, ECR, IRSA |
| 4 | Application | API Services, Bedrock Integration, Frontend |
| 5 | Observability | Secrets, Monitoring, Cost Alerts, Disaster Recovery |
| 6 | Serverless | Lambda, Step Functions, EventBridge, Chat, Runbook, Incident Response |
| 7 | Sandbox | Ephemeral Test Environments, HITL Workflow |
| 8 | Security | AWS Config, GuardDuty, Drift Detection, Red Team |

**Rules:**
- Single-line descriptions only (no multi-line `|` blocks)
- No developer notes, cost analysis, or implementation details
- Brief purpose in parentheses (2-4 words)
- Each infrastructure template has a unique sub-layer number
- Sub-layer numbers reflect deployment order within a layer (e.g., 6.1 -> 6.2 -> ... -> 6.10)
- Integer portion determines layer name (6.1 through 6.10 all use "Serverless" layer name)

**Sub-Layer Reference:** See `archive/documentation-audits/CLAUDE_MD_ARCHIVED_SECTIONS_2025-12-13.md` or grep `deploy/cloudformation/*.yaml` Description fields.

---

## GovCloud Compatibility - ARN Partitions

- Never hardcode `arn:aws` - always use `${AWS::Partition}`
- Use PartitionMap for managed policy ARNs
- Example: `!Sub 'arn:${AWS::Partition}:service:...'`
- See `deploy/cloudformation/iam.yaml:4-9` for implementation

---

## IAM Policy Size Limit - 10KB Maximum

AWS enforces a **hard 10,240 byte limit** on inline IAM policies.

**Check policy size BEFORE adding new permissions:**
- Read the existing template and count approximate bytes in the inline policy
- If adding permissions to a large policy (>300 lines), proactively create a managed policy
- Never add permissions to inline policies that are already close to the limit

**Managed policy pattern (REQUIRED when inline policy is large):**
```yaml
NewPermissionsManagedPolicy:
  Type: AWS::IAM::ManagedPolicy
  Properties:
    ManagedPolicyName: !Sub '${ProjectName}-descriptive-name-${Environment}'
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Action: [action:One, action:Two]
          Resource: [!Sub 'arn:...']
# Then add !Ref NewPermissionsManagedPolicy to role's ManagedPolicyArns
```

**Optimization techniques:**
- Use inline array syntax: `Action: [s3:GetObject, s3:PutObject]` not multi-line
- Combine resources with wildcards: `${ProjectName}-*-${Environment}` not individual ARNs
- Use single CloudFormation wildcard: `stack/${ProjectName}-*-${Environment}/*`
- Avoid duplicate ARN patterns across statements

**When limit is hit:** Do NOT disable features - split into managed policies attached to the role.
See `deploy/cloudformation/codebuild-observability.yaml` for managed policy pattern example.

---

## IAM Policies - Least Privilege

- All `Resource` fields must be scoped to specific resources
- Use `${ProjectName}-*` naming patterns for resources
- Add conditions to limit scope (region, tags, service)
- Example: `Resource: !Sub 'arn:aws:s3:::${ProjectName}-*-${Environment}'`
- **AWS-Required Wildcards:** Some AWS APIs require `Resource: '*'` (e.g., `ecr:GetAuthorizationToken`, `cloudwatch:PutMetricData`). See ADR-041 for defense-in-depth compensating controls.

---

## Never Hardcode Environment-Specific Values

- **NEVER hardcode** AWS account IDs, endpoints, cluster names, or other environment-specific values
- **Always use** CloudFormation intrinsic functions: `${AWS::AccountId}`, `${AWS::Region}`, `!Sub`, `!Ref`
- **For cross-environment data:** Store defaults in Python code, not in CloudFormation
- **CloudFormation should only reference** the current deployment environment via parameters and intrinsics

---

## Encryption - KMS Customer-Managed Keys

- All databases must use customer-managed KMS keys (not AWS-managed)
- Enable automatic key rotation (`EnableKeyRotation: true`)
- Scope key policies to specific services via `kms:ViaService` condition
- Example: See `deploy/cloudformation/neptune.yaml:37-88`

---

## Logging - Extended Retention

- VPC Flow Logs: 365 days (prod), 90 days (dev/qa) minimum
- CloudWatch Logs: 90 days minimum for application logs
- WAF Logs: 90 days minimum
- All logs must use KMS encryption where supported

---

## cfn-lint Validation

**Configuration:**
- `.cfnlintrc` - Global configuration (ignores W3002, W1020)
- `scripts/cfn-lint-wrapper.sh` - Wrapper script for consistent exit code handling
- `scripts/validate_iam_actions.py` - IAM action validator for W3037 warnings

**Exit Code Handling:**
| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | No errors/warnings | Pass |
| 4 | Warnings only | Non-blocking (pass) |
| 2, 6, 8 | Errors found | Fail build |

**Usage:**
```bash
# Use wrapper script (recommended)
./scripts/cfn-lint-wrapper.sh deploy/cloudformation/template.yaml

# Validate IAM actions (W3037 warnings)
python scripts/validate_iam_actions.py --report

# In buildspecs, always use graceful fallback pattern:
cfn-lint template.yaml || echo "cfn-lint warnings (non-blocking)"
```

**Known Valid IAM Actions:**
When cfn-lint reports W3037 for actions not in its database, add verified actions to `scripts/validate_iam_actions.py` KNOWN_VALID_ACTIONS set after confirming they exist in AWS documentation.

**Nightly Validation:**
`.github/workflows/nightly-iam-validation.yml` runs daily at 2 AM UTC to validate all templates and IAM actions.

---

## Fork-Join Parallelism

All 155 CloudFormation templates are independently validatable. When batch-validating templates, each can be linted in an isolated worktree without cross-template dependencies. Use parallel agent work for bulk template updates (e.g., description format migrations, parameter standardization).
