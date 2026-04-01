#!/bin/bash
# =============================================================================
# Project Aura - CI/CD Pipeline Migration Script
# =============================================================================
# Migrates CodeBuild projects, ECR repositories, and CI/CD infrastructure
# from source to target account.
#
# This script handles:
#   - ECR repository creation and image replication
#   - CodeBuild project deployment via CloudFormation
#   - Secrets Manager secrets migration
#   - SSM parameters migration
#   - GitHub CodeConnections setup guidance
#
# Prerequisites:
#   - account-migration-bootstrap.yaml deployed in target account
#   - account-bootstrap.yaml deployed in target account
#   - AWS CLI configured with both source and target account profiles
#   - jq installed for JSON parsing
#
# Usage:
#   ./migrate-cicd-pipeline.sh <component> <action>
#
# Components: ecr, secrets, ssm, codebuild, all
# Actions: prepare, migrate, verify
# =============================================================================

set -euo pipefail

# Configuration
PROJECT_NAME="aura"
ENVIRONMENT="${ENVIRONMENT:-dev}"
SOURCE_PROFILE="${SOURCE_PROFILE:-aura-admin}"
TARGET_PROFILE="${TARGET_PROFILE:-aura-admin-target}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get account IDs
get_account_ids() {
    SOURCE_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$SOURCE_PROFILE" --query 'Account' --output text)
    TARGET_ACCOUNT_ID=$(aws sts get-caller-identity --profile "$TARGET_PROFILE" --query 'Account' --output text)
    log_info "Source Account: $SOURCE_ACCOUNT_ID"
    log_info "Target Account: $TARGET_ACCOUNT_ID"
}

# =============================================================================
# ECR Migration
# =============================================================================

ecr_prepare() {
    log_info "Preparing ECR repositories for migration..."

    # List all ECR repositories
    REPOS=$(aws ecr describe-repositories \
        --profile "$SOURCE_PROFILE" \
        --query "repositories[?contains(repositoryName, '${PROJECT_NAME}')].repositoryName" \
        --output json)

    echo "$REPOS" > /tmp/ecr-migration-repos.json

    REPO_COUNT=$(echo "$REPOS" | jq 'length')
    log_info "Found $REPO_COUNT ECR repositories to migrate"

    # Get image counts for each repo
    for REPO in $(echo "$REPOS" | jq -r '.[]'); do
        IMAGE_COUNT=$(aws ecr list-images \
            --repository-name "$REPO" \
            --profile "$SOURCE_PROFILE" \
            --query 'length(imageIds)' \
            --output text 2>/dev/null || echo "0")
        log_info "  $REPO: $IMAGE_COUNT images"
    done

    log_success "ECR preparation complete"
}

ecr_migrate() {
    log_info "Migrating ECR repositories to target account..."

    REPOS=$(cat /tmp/ecr-migration-repos.json)

    for REPO in $(echo "$REPOS" | jq -r '.[]'); do
        log_info "Migrating repository: $REPO"

        # Create repository in target account (ignore if exists)
        aws ecr create-repository \
            --repository-name "$REPO" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=KMS \
            --profile "$TARGET_PROFILE" \
            --region "$AWS_REGION" 2>/dev/null || log_warn "Repository $REPO already exists"

        # Get source repository URI
        SOURCE_URI="${SOURCE_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO}"
        TARGET_URI="${TARGET_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO}"

        # Get all image tags
        IMAGES=$(aws ecr list-images \
            --repository-name "$REPO" \
            --profile "$SOURCE_PROFILE" \
            --query 'imageIds[?imageTag!=`null`].imageTag' \
            --output json 2>/dev/null || echo "[]")

        IMAGE_COUNT=$(echo "$IMAGES" | jq 'length')

        if [ "$IMAGE_COUNT" -gt 0 ]; then
            log_info "  Replicating $IMAGE_COUNT images..."

            # Login to source ECR
            aws ecr get-login-password --profile "$SOURCE_PROFILE" --region "$AWS_REGION" | \
                docker login --username AWS --password-stdin "$SOURCE_URI" 2>/dev/null

            # Login to target ECR
            aws ecr get-login-password --profile "$TARGET_PROFILE" --region "$AWS_REGION" | \
                docker login --username AWS --password-stdin "$TARGET_URI" 2>/dev/null

            # Replicate each image (limit to last 5 for migration)
            for TAG in $(echo "$IMAGES" | jq -r '.[]' | head -5); do
                log_info "    Replicating: $REPO:$TAG"
                docker pull "${SOURCE_URI}:${TAG}" 2>/dev/null || continue
                docker tag "${SOURCE_URI}:${TAG}" "${TARGET_URI}:${TAG}"
                docker push "${TARGET_URI}:${TAG}" 2>/dev/null || log_warn "Failed to push $TAG"
                docker rmi "${SOURCE_URI}:${TAG}" "${TARGET_URI}:${TAG}" 2>/dev/null || true
            done
        fi

        log_success "Repository migrated: $REPO"
    done

    log_success "ECR migration complete"
}

ecr_verify() {
    log_info "Verifying ECR repositories in target account..."

    SOURCE_REPOS=$(aws ecr describe-repositories \
        --profile "$SOURCE_PROFILE" \
        --query "repositories[?contains(repositoryName, '${PROJECT_NAME}')].repositoryName" \
        --output json)

    TARGET_REPOS=$(aws ecr describe-repositories \
        --profile "$TARGET_PROFILE" \
        --query "repositories[?contains(repositoryName, '${PROJECT_NAME}')].repositoryName" \
        --output json 2>/dev/null || echo "[]")

    SOURCE_COUNT=$(echo "$SOURCE_REPOS" | jq 'length')
    TARGET_COUNT=$(echo "$TARGET_REPOS" | jq 'length')

    log_info "Source repositories: $SOURCE_COUNT"
    log_info "Target repositories: $TARGET_COUNT"

    if [ "$SOURCE_COUNT" -eq "$TARGET_COUNT" ]; then
        log_success "Repository count matches!"
    else
        log_warn "Repository count mismatch"
    fi
}

# =============================================================================
# Secrets Manager Migration
# =============================================================================

secrets_prepare() {
    log_info "Preparing Secrets Manager secrets for migration..."

    # List all Aura secrets
    SECRETS=$(aws secretsmanager list-secrets \
        --profile "$SOURCE_PROFILE" \
        --filter Key="name",Values="${PROJECT_NAME}" \
        --query 'SecretList[].Name' \
        --output json)

    echo "$SECRETS" > /tmp/secrets-migration-list.json

    SECRET_COUNT=$(echo "$SECRETS" | jq 'length')
    log_info "Found $SECRET_COUNT secrets to migrate"

    echo "$SECRETS" | jq -r '.[]' | while read -r SECRET; do
        log_info "  $SECRET"
    done

    log_success "Secrets preparation complete"
}

secrets_migrate() {
    log_info "Migrating Secrets Manager secrets to target account..."

    # Get target KMS key for encryption
    TARGET_KMS_KEY=$(aws ssm get-parameter \
        --name "/aura/${ENVIRONMENT}/kms-key-arn" \
        --profile "$TARGET_PROFILE" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "")

    SECRETS=$(cat /tmp/secrets-migration-list.json)

    for SECRET_NAME in $(echo "$SECRETS" | jq -r '.[]'); do
        log_info "Migrating secret: $SECRET_NAME"

        # Get secret value from source
        SECRET_VALUE=$(aws secretsmanager get-secret-value \
            --secret-id "$SECRET_NAME" \
            --profile "$SOURCE_PROFILE" \
            --query 'SecretString' \
            --output text 2>/dev/null)

        if [ -n "$SECRET_VALUE" ]; then
            # Create or update secret in target
            if aws secretsmanager describe-secret \
                --secret-id "$SECRET_NAME" \
                --profile "$TARGET_PROFILE" 2>/dev/null; then
                # Update existing
                aws secretsmanager put-secret-value \
                    --secret-id "$SECRET_NAME" \
                    --secret-string "$SECRET_VALUE" \
                    --profile "$TARGET_PROFILE"
            else
                # Create new
                aws secretsmanager create-secret \
                    --name "$SECRET_NAME" \
                    --secret-string "$SECRET_VALUE" \
                    --kms-key-id "$TARGET_KMS_KEY" \
                    --profile "$TARGET_PROFILE" 2>/dev/null || log_warn "Failed to create secret"
            fi
            log_success "Secret migrated: $SECRET_NAME"
        else
            log_warn "Could not retrieve secret value for: $SECRET_NAME"
        fi
    done

    log_success "Secrets migration complete"
}

secrets_verify() {
    log_info "Verifying Secrets Manager secrets in target account..."

    SOURCE_SECRETS=$(aws secretsmanager list-secrets \
        --profile "$SOURCE_PROFILE" \
        --filter Key="name",Values="${PROJECT_NAME}" \
        --query 'SecretList[].Name' \
        --output json)

    TARGET_SECRETS=$(aws secretsmanager list-secrets \
        --profile "$TARGET_PROFILE" \
        --filter Key="name",Values="${PROJECT_NAME}" \
        --query 'SecretList[].Name' \
        --output json 2>/dev/null || echo "[]")

    SOURCE_COUNT=$(echo "$SOURCE_SECRETS" | jq 'length')
    TARGET_COUNT=$(echo "$TARGET_SECRETS" | jq 'length')

    log_info "Source secrets: $SOURCE_COUNT"
    log_info "Target secrets: $TARGET_COUNT"

    if [ "$SOURCE_COUNT" -eq "$TARGET_COUNT" ]; then
        log_success "Secret count matches!"
    else
        log_warn "Secret count mismatch"
    fi
}

# =============================================================================
# SSM Parameters Migration
# =============================================================================

ssm_prepare() {
    log_info "Preparing SSM parameters for migration..."

    # List all Aura parameters
    PARAMS=$(aws ssm describe-parameters \
        --profile "$SOURCE_PROFILE" \
        --parameter-filters Key="Name",Option="BeginsWith",Values="/aura/" \
        --query 'Parameters[].Name' \
        --output json)

    echo "$PARAMS" > /tmp/ssm-migration-params.json

    PARAM_COUNT=$(echo "$PARAMS" | jq 'length')
    log_info "Found $PARAM_COUNT SSM parameters to migrate"

    log_success "SSM preparation complete"
}

ssm_migrate() {
    log_info "Migrating SSM parameters to target account..."

    PARAMS=$(cat /tmp/ssm-migration-params.json)

    for PARAM_NAME in $(echo "$PARAMS" | jq -r '.[]'); do
        # Skip account-specific parameters that will be different
        if echo "$PARAM_NAME" | grep -qE "(account-id|vpc-id|subnet|security-group|arn)"; then
            log_info "Skipping account-specific parameter: $PARAM_NAME"
            continue
        fi

        log_info "Migrating parameter: $PARAM_NAME"

        # Get parameter from source
        PARAM=$(aws ssm get-parameter \
            --name "$PARAM_NAME" \
            --with-decryption \
            --profile "$SOURCE_PROFILE" \
            --output json 2>/dev/null)

        PARAM_VALUE=$(echo "$PARAM" | jq -r '.Parameter.Value')
        PARAM_TYPE=$(echo "$PARAM" | jq -r '.Parameter.Type')

        # Create in target
        aws ssm put-parameter \
            --name "$PARAM_NAME" \
            --value "$PARAM_VALUE" \
            --type "$PARAM_TYPE" \
            --overwrite \
            --profile "$TARGET_PROFILE" 2>/dev/null || log_warn "Failed to create parameter"

        log_success "Parameter migrated: $PARAM_NAME"
    done

    log_success "SSM migration complete"
}

ssm_verify() {
    log_info "Verifying SSM parameters in target account..."

    SOURCE_PARAMS=$(aws ssm describe-parameters \
        --profile "$SOURCE_PROFILE" \
        --parameter-filters Key="Name",Option="BeginsWith",Values="/aura/" \
        --query 'Parameters[].Name' \
        --output json)

    TARGET_PARAMS=$(aws ssm describe-parameters \
        --profile "$TARGET_PROFILE" \
        --parameter-filters Key="Name",Option="BeginsWith",Values="/aura/" \
        --query 'Parameters[].Name' \
        --output json 2>/dev/null || echo "[]")

    SOURCE_COUNT=$(echo "$SOURCE_PARAMS" | jq 'length')
    TARGET_COUNT=$(echo "$TARGET_PARAMS" | jq 'length')

    log_info "Source parameters: $SOURCE_COUNT"
    log_info "Target parameters: $TARGET_COUNT"
}

# =============================================================================
# CodeBuild Migration
# =============================================================================

codebuild_prepare() {
    log_info "Preparing CodeBuild projects for migration..."

    # List all Aura CodeBuild projects
    PROJECTS=$(aws codebuild list-projects \
        --profile "$SOURCE_PROFILE" \
        --query "projects[?contains(@, '${PROJECT_NAME}')]" \
        --output json)

    echo "$PROJECTS" > /tmp/codebuild-migration-projects.json

    PROJECT_COUNT=$(echo "$PROJECTS" | jq 'length')
    log_info "Found $PROJECT_COUNT CodeBuild projects to migrate"

    echo "$PROJECTS" | jq -r '.[]' | while read -r PROJECT; do
        log_info "  $PROJECT"
    done

    log_success "CodeBuild preparation complete"

    log_info ""
    log_warn "IMPORTANT: CodeBuild projects should NOT be migrated directly."
    log_warn "Instead, deploy the CodeBuild CloudFormation stacks in the target account:"
    log_warn ""
    log_warn "  1. Deploy codebuild-bootstrap.yaml (creates all CodeBuild projects)"
    log_warn "  2. Trigger: aws codebuild start-build --project-name aura-bootstrap-deploy-dev"
    log_warn "  3. This will deploy all 16 CodeBuild projects via CloudFormation"
    log_warn ""
}

codebuild_migrate() {
    log_info "CodeBuild migration: Deploy via CloudFormation..."
    log_info ""
    log_info "Execute these commands in target account context:"
    log_info ""
    log_info "  export AWS_PROFILE=$TARGET_PROFILE"
    log_info ""
    log_info "  # Step 1: Create GitHub CodeConnections (Console)"
    log_info "  #   - Go to Developer Tools > Settings > Connections"
    log_info "  #   - Create new GitHub connection: aura-github-${ENVIRONMENT}"
    log_info "  #   - Store ARN in SSM"
    log_info ""
    log_info "  # Step 2: Deploy Bootstrap CodeBuild project"
    log_info "  aws cloudformation deploy \\"
    log_info "    --template-file deploy/cloudformation/codebuild-bootstrap.yaml \\"
    log_info "    --stack-name ${PROJECT_NAME}-codebuild-bootstrap-${ENVIRONMENT} \\"
    log_info "    --parameter-overrides Environment=${ENVIRONMENT} \\"
    log_info "    --capabilities CAPABILITY_NAMED_IAM"
    log_info ""
    log_info "  # Step 3: Run Bootstrap to deploy all CodeBuild projects"
    log_info "  aws codebuild start-build --project-name ${PROJECT_NAME}-bootstrap-deploy-${ENVIRONMENT}"
    log_info ""
    log_info "  # Step 4: Deploy infrastructure layers"
    log_info "  aws codebuild start-build --project-name ${PROJECT_NAME}-foundation-deploy-${ENVIRONMENT}"
    log_info "  # ... then data, compute, application, etc."
    log_info ""
}

codebuild_verify() {
    log_info "Verifying CodeBuild projects in target account..."

    SOURCE_PROJECTS=$(aws codebuild list-projects \
        --profile "$SOURCE_PROFILE" \
        --query "projects[?contains(@, '${PROJECT_NAME}')]" \
        --output json)

    TARGET_PROJECTS=$(aws codebuild list-projects \
        --profile "$TARGET_PROFILE" \
        --query "projects[?contains(@, '${PROJECT_NAME}')]" \
        --output json 2>/dev/null || echo "[]")

    SOURCE_COUNT=$(echo "$SOURCE_PROJECTS" | jq 'length')
    TARGET_COUNT=$(echo "$TARGET_PROJECTS" | jq 'length')

    log_info "Source CodeBuild projects: $SOURCE_COUNT"
    log_info "Target CodeBuild projects: $TARGET_COUNT"

    if [ "$SOURCE_COUNT" -eq "$TARGET_COUNT" ]; then
        log_success "CodeBuild project count matches!"
    else
        log_warn "CodeBuild project count mismatch"
    fi
}

# =============================================================================
# Main
# =============================================================================

usage() {
    echo "Usage: $0 <component> <action>"
    echo ""
    echo "Components: ecr, secrets, ssm, codebuild, all"
    echo "Actions:    prepare, migrate, verify"
    echo ""
    echo "Examples:"
    echo "  $0 ecr prepare     # List ECR repos to migrate"
    echo "  $0 ecr migrate     # Replicate ECR images"
    echo "  $0 all prepare     # Prepare all components"
}

if [ $# -lt 2 ]; then
    usage
    exit 1
fi

COMPONENT="$1"
ACTION="$2"

# Initialize
get_account_ids

case "$COMPONENT" in
    ecr)
        case "$ACTION" in
            prepare) ecr_prepare ;;
            migrate) ecr_migrate ;;
            verify) ecr_verify ;;
            *) usage; exit 1 ;;
        esac
        ;;
    secrets)
        case "$ACTION" in
            prepare) secrets_prepare ;;
            migrate) secrets_migrate ;;
            verify) secrets_verify ;;
            *) usage; exit 1 ;;
        esac
        ;;
    ssm)
        case "$ACTION" in
            prepare) ssm_prepare ;;
            migrate) ssm_migrate ;;
            verify) ssm_verify ;;
            *) usage; exit 1 ;;
        esac
        ;;
    codebuild)
        case "$ACTION" in
            prepare) codebuild_prepare ;;
            migrate) codebuild_migrate ;;
            verify) codebuild_verify ;;
            *) usage; exit 1 ;;
        esac
        ;;
    all)
        case "$ACTION" in
            prepare)
                ecr_prepare
                secrets_prepare
                ssm_prepare
                codebuild_prepare
                ;;
            migrate)
                ecr_migrate
                secrets_migrate
                ssm_migrate
                codebuild_migrate
                ;;
            verify)
                ecr_verify
                secrets_verify
                ssm_verify
                codebuild_verify
                ;;
            *) usage; exit 1 ;;
        esac
        ;;
    *)
        usage
        exit 1
        ;;
esac

log_success "Done!"
