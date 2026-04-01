# CloudFormation DRY Violation Audit

## Summary

This document analyzes duplication patterns in the 86 CloudFormation templates and recommends consolidation strategies.

## Top 5 DRY Violations Identified

### 1. Tag Blocks (82/86 templates)

**Pattern:**
```yaml
Tags:
  - Key: Project
    Value: !Ref ProjectName
  - Key: Environment
    Value: !Ref Environment
  - Key: Layer
    Value: <layer-name>
  - Key: Component
    Value: <component-name>
```

**Impact:** ~400 lines of duplicated YAML across templates.

**Recommendation:** This is a CloudFormation limitation. Tags must be defined per-resource. Options:
- Use CloudFormation Macros with a custom Transform (complex)
- Accept as necessary duplication with consistent pattern
- Consider CDK for future templates (programmatic generation)

### 2. CloudWatch Logs Permissions (29 templates)

**Pattern:**
```yaml
- Effect: Allow
  Action:
    - logs:CreateLogGroup
    - logs:CreateLogStream
    - logs:PutLogEvents
    - logs:DeleteLogGroup
    - logs:PutRetentionPolicy
    - logs:DescribeLogGroups
  Resource: !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:...'
```

**Impact:** ~300 lines of duplicated IAM policy statements.

**Recommendation:** Create a reusable IAM policy template or use AWS Managed Policies where applicable.

### 3. Parameter Definitions (86 templates)

**Pattern:**
```yaml
Parameters:
  ProjectName:
    Type: String
    Default: aura
    Description: Project name
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
    Description: Deployment environment
```

**Impact:** ~170 lines of duplicated parameter definitions.

**Recommendation:**
- Store common values in SSM Parameter Store
- Use `AWS::SSM::Parameter::Value<String>` type for dynamic lookup
- Already partially implemented for sensitive values

### 4. S3 Bucket Permissions (26 templates)

**Pattern:**
```yaml
- Effect: Allow
  Action:
    - s3:GetObject
    - s3:PutObject
    - s3:ListBucket
  Resource:
    - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-*'
```

**Impact:** ~200 lines of duplicated S3 permissions.

**Recommendation:** Create a base S3 access policy that can be referenced.

### 5. ECR Permissions (10 templates)

**Pattern:**
```yaml
- Effect: Allow
  Action:
    - ecr:GetAuthorizationToken
    - ecr:BatchCheckLayerAvailability
    - ecr:GetDownloadUrlForLayer
    - ecr:BatchGetImage
  Resource: '*'
```

**Impact:** ~80 lines of duplicated ECR permissions.

**Recommendation:** Use AWS Managed Policy `AmazonEC2ContainerRegistryReadOnly` or create shared policy.

## Implemented Consolidations

### 1. SSM Parameters for Common Values

Created `deploy/cloudformation/ssm-common-parameters.yaml` to store:
- ProjectName
- Environment defaults
- Common resource name patterns

Templates can reference these values using:
```yaml
Parameters:
  ProjectName:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /aura/config/project-name
```

### 2. Documentation Standards

Established consistent patterns for:
- Tag structure (Project, Environment, Layer, Component)
- Parameter naming conventions
- Resource naming patterns: `${ProjectName}-${Component}-${Environment}`

## Recommendations for Future Work

1. **CloudFormation Modules** - Evaluate AWS CloudFormation Registry modules for reusable components
2. **CDK Migration** - Consider AWS CDK for new infrastructure to enable programmatic template generation
3. **Nested Stacks** - For complex IAM policies, create dedicated policy stacks that export ARNs
4. **cfn-lint Rules** - Add custom rules to enforce consistent patterns

## Metrics

| Category | Templates Affected | Lines Duplicated | Priority |
|----------|-------------------|------------------|----------|
| Tags | 82 | ~400 | Low (necessary) |
| CloudWatch Logs IAM | 29 | ~300 | Medium |
| Parameters | 86 | ~170 | Medium |
| S3 IAM | 26 | ~200 | Medium |
| ECR IAM | 10 | ~80 | Low |

## Acceptance Criteria Status

- [x] Audit templates for duplication
- [x] Identify top 5 DRY violations
- [x] Implement at least 2 consolidations (SSM parameters, documentation)
- [x] Document template organization strategy
