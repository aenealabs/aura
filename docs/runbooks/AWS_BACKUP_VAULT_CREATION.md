# AWS Backup Vault Creation Troubleshooting

## Overview

This runbook documents the resolution of AccessDenied errors when creating AWS Backup vaults via CloudFormation, specifically the `aura-disaster-recovery-dev` stack.

## Problem Statement

**Error Message:**
```
Insufficient privileges to create a backup vault. Creating a backup vault requires
backup-storage and KMS permissions. (Service: Backup, Status Code: 403)
```

**Affected Stack:** `aura-disaster-recovery-dev`

**Root Cause:** The CodeBuild IAM role (`aura-observability-codebuild-role-dev`) was missing the `backup-storage:MountCapsule` permission required for AWS Backup vault creation.

## Required IAM Permissions

### Backup Storage Permissions

AWS Backup vault creation requires specific backup-storage permissions. These are service-level actions that require `Resource: '*'`:

```yaml
- Effect: Allow
  Action:
    - backup-storage:MountCapsule      # CRITICAL: Required for vault creation
    - backup-storage:MountBackupStorage
    - backup-storage:StartObject
    - backup-storage:PutObject
    - backup-storage:GetChunk
    - backup-storage:ListChunks
    - backup-storage:GetObjectMetadata
    - backup-storage:NotifyObjectComplete
  Resource: '*'
```

### KMS Permissions

When using customer-managed KMS keys for vault encryption, the following permissions are required:

```yaml
- Effect: Allow
  Action:
    - kms:DescribeKey
    - kms:GenerateDataKey
    - kms:GenerateDataKeyWithoutPlaintext
    - kms:Encrypt
    - kms:Decrypt
    - kms:RetireGrant          # Required for vault creation
    - kms:CreateGrant          # Required (with GrantIsForAWSResource condition)
  Resource:
    - !Sub 'arn:${AWS::Partition}:kms:${AWS::Region}:${AWS::AccountId}:key/*'
  Condition:
    StringEquals:
      'kms:CallerAccount': !Ref AWS::AccountId
```

### KMS Key Policy

The KMS key used for backup encryption must also grant permissions to:

1. **AWS Backup service principal** (`backup.amazonaws.com`)
2. **CodeBuild role** creating the vault
3. **Backup service role** that will use the vault

Example key policy statement for AWS Backup service:

```json
{
  "Sid": "AllowBackupService",
  "Effect": "Allow",
  "Principal": {
    "Service": "backup.amazonaws.com"
  },
  "Action": [
    "kms:Encrypt",
    "kms:Decrypt",
    "kms:ReEncrypt*",
    "kms:GenerateDataKey*",
    "kms:DescribeKey",
    "kms:CreateGrant"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "kms:CallerAccount": "ACCOUNT_ID"
    }
  }
}
```

## Resolution Steps

### Step 1: Update CodeBuild IAM Policy

Edit `deploy/cloudformation/codebuild-observability.yaml` to add the missing permissions:

```yaml
# Add backup-storage:MountCapsule
- backup-storage:MountCapsule

# Add kms:RetireGrant
- kms:RetireGrant
```

### Step 2: Update the CodeBuild Stack

```bash
export AWS_PROFILE=aura-admin

aws cloudformation update-stack \
  --stack-name aura-codebuild-observability-dev \
  --template-body file://deploy/cloudformation/codebuild-observability.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=GitHubRepository,ParameterValue=https://github.com/aenealabs/aura \
    ParameterKey=GitHubBranch,ParameterValue=main \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-update-complete \
  --stack-name aura-codebuild-observability-dev \
  --region us-east-1
```

### Step 3: Delete Failed ROLLBACK_COMPLETE Stack

If the DR stack is in ROLLBACK_COMPLETE state, delete it before retrying:

```bash
aws cloudformation delete-stack \
  --stack-name aura-disaster-recovery-dev \
  --region us-east-1

aws cloudformation wait stack-delete-complete \
  --stack-name aura-disaster-recovery-dev \
  --region us-east-1
```

### Step 4: Trigger New Deployment

```bash
aws codebuild start-build \
  --project-name aura-observability-deploy-dev \
  --region us-east-1
```

## Verification

### Verify Backup Vault Creation

```bash
aws backup list-backup-vaults \
  --region us-east-1 \
  --query 'BackupVaultList[?contains(BackupVaultName, `aura`)].[BackupVaultName,EncryptionKeyArn]' \
  --output table
```

Expected output:
```
+----------------+--------------------------------------------------------------------------------+
|  aura-vault-dev|  arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID                                   |
+----------------+--------------------------------------------------------------------------------+
```

### Verify Stack Status

```bash
aws cloudformation describe-stacks \
  --stack-name aura-disaster-recovery-dev \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus' \
  --output text
```

Expected: `CREATE_COMPLETE` or `UPDATE_COMPLETE`

## References

- [AWS re:Post: Resolve Access Denied errors when creating backup vaults](https://repost.aws/knowledge-center/backup-vault-access-denied)
- [AWS Backup Vault CloudFormation Documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-backup-backupvault.html)
- [AWS Backup Troubleshooting Guide](https://docs.aws.amazon.com/aws-backup/latest/devguide/troubleshooting.html)

## Related Files

- `deploy/cloudformation/codebuild-observability.yaml` - CodeBuild IAM role with backup permissions
- `deploy/cloudformation/disaster-recovery.yaml` - AWS Backup vault and plan definitions
- `deploy/cloudformation/kms.yaml` - KMS key definitions including backup encryption key

## Incident History

| Date | Issue | Resolution |
|------|-------|------------|
| 2025-12-09 | AccessDenied creating backup vault | Added `backup-storage:MountCapsule` and `kms:RetireGrant` permissions |
