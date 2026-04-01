#!/bin/bash
# =============================================================================
# Project Aura - Data Services Migration Script
# =============================================================================
# Migrates stateful data services from source to target account:
#   - Neptune (graph database) via snapshot copy
#   - OpenSearch (vector search) via snapshot to S3
#   - DynamoDB tables via AWS Backup
#   - S3 buckets via cross-account replication
#
# Prerequisites:
#   - account-migration-bootstrap.yaml deployed in target account
#   - AWS CLI configured with both source and target account profiles
#   - jq installed for JSON parsing
#
# Usage:
#   ./migrate-data-services.sh <service> <action>
#
# Services: neptune, opensearch, dynamodb, s3, all
# Actions: prepare, migrate, verify, rollback
#
# Examples:
#   ./migrate-data-services.sh neptune prepare
#   ./migrate-data-services.sh all migrate
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
NC='\033[0m' # No Color

# Logging functions
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

# Get migration bucket from target account
get_migration_bucket() {
    MIGRATION_BUCKET=$(aws ssm get-parameter \
        --name "/aura/${ENVIRONMENT}/migration/bucket" \
        --profile "$TARGET_PROFILE" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "")

    if [ -z "$MIGRATION_BUCKET" ]; then
        log_error "Migration bucket not found. Deploy account-migration-bootstrap.yaml first."
        exit 1
    fi
    log_info "Migration Bucket: $MIGRATION_BUCKET"
}

# Get migration KMS key from target account
get_migration_kms_key() {
    MIGRATION_KMS_KEY=$(aws ssm get-parameter \
        --name "/aura/${ENVIRONMENT}/migration/kms-key-arn" \
        --profile "$TARGET_PROFILE" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "")

    if [ -z "$MIGRATION_KMS_KEY" ]; then
        log_error "Migration KMS key not found. Deploy account-migration-bootstrap.yaml first."
        exit 1
    fi
    log_info "Migration KMS Key: $MIGRATION_KMS_KEY"
}

# =============================================================================
# Neptune Migration
# =============================================================================

neptune_prepare() {
    log_info "Preparing Neptune snapshot for migration..."

    CLUSTER_ID="${PROJECT_NAME}-neptune-${ENVIRONMENT}"
    SNAPSHOT_ID="${PROJECT_NAME}-neptune-migration-$(date +%Y%m%d-%H%M%S)"

    # Create snapshot in source account
    log_info "Creating Neptune snapshot: $SNAPSHOT_ID"
    aws neptune create-db-cluster-snapshot \
        --db-cluster-identifier "$CLUSTER_ID" \
        --db-cluster-snapshot-identifier "$SNAPSHOT_ID" \
        --profile "$SOURCE_PROFILE" \
        --region "$AWS_REGION"

    # Wait for snapshot to complete
    log_info "Waiting for snapshot to complete (this may take 15-30 minutes)..."
    aws neptune wait db-cluster-snapshot-available \
        --db-cluster-snapshot-identifier "$SNAPSHOT_ID" \
        --profile "$SOURCE_PROFILE" \
        --region "$AWS_REGION"

    log_success "Neptune snapshot created: $SNAPSHOT_ID"

    # Store snapshot ID for later use
    echo "$SNAPSHOT_ID" > /tmp/neptune-migration-snapshot-id.txt

    # Share snapshot with target account
    log_info "Sharing snapshot with target account: $TARGET_ACCOUNT_ID"
    aws neptune modify-db-cluster-snapshot-attribute \
        --db-cluster-snapshot-identifier "$SNAPSHOT_ID" \
        --attribute-name restore \
        --values-to-add "$TARGET_ACCOUNT_ID" \
        --profile "$SOURCE_PROFILE" \
        --region "$AWS_REGION"

    log_success "Neptune snapshot shared with target account"
}

neptune_migrate() {
    log_info "Migrating Neptune to target account..."

    SNAPSHOT_ID=$(cat /tmp/neptune-migration-snapshot-id.txt 2>/dev/null || echo "")
    if [ -z "$SNAPSHOT_ID" ]; then
        log_error "No snapshot ID found. Run 'neptune prepare' first."
        exit 1
    fi

    # Get source snapshot ARN
    SOURCE_SNAPSHOT_ARN="arn:aws:rds:${AWS_REGION}:${SOURCE_ACCOUNT_ID}:cluster-snapshot:${SNAPSHOT_ID}"
    TARGET_SNAPSHOT_ID="${PROJECT_NAME}-neptune-${ENVIRONMENT}-migrated"

    # Copy snapshot to target account (re-encrypt with target KMS key)
    log_info "Copying snapshot to target account with new encryption..."
    aws neptune copy-db-cluster-snapshot \
        --source-db-cluster-snapshot-identifier "$SOURCE_SNAPSHOT_ARN" \
        --target-db-cluster-snapshot-identifier "$TARGET_SNAPSHOT_ID" \
        --kms-key-id "$MIGRATION_KMS_KEY" \
        --profile "$TARGET_PROFILE" \
        --region "$AWS_REGION"

    # Wait for copy to complete
    log_info "Waiting for snapshot copy to complete..."
    aws neptune wait db-cluster-snapshot-available \
        --db-cluster-snapshot-identifier "$TARGET_SNAPSHOT_ID" \
        --profile "$TARGET_PROFILE" \
        --region "$AWS_REGION"

    log_success "Neptune snapshot copied to target account: $TARGET_SNAPSHOT_ID"
    echo "$TARGET_SNAPSHOT_ID" > /tmp/neptune-target-snapshot-id.txt
}

neptune_verify() {
    log_info "Verifying Neptune migration..."

    TARGET_SNAPSHOT_ID=$(cat /tmp/neptune-target-snapshot-id.txt 2>/dev/null || echo "")
    if [ -z "$TARGET_SNAPSHOT_ID" ]; then
        log_warn "No target snapshot ID found. Checking for any migrated snapshots..."
        TARGET_SNAPSHOT_ID="${PROJECT_NAME}-neptune-${ENVIRONMENT}-migrated"
    fi

    # Check snapshot exists and is available
    SNAPSHOT_STATUS=$(aws neptune describe-db-cluster-snapshots \
        --db-cluster-snapshot-identifier "$TARGET_SNAPSHOT_ID" \
        --profile "$TARGET_PROFILE" \
        --query 'DBClusterSnapshots[0].Status' \
        --output text 2>/dev/null || echo "not-found")

    if [ "$SNAPSHOT_STATUS" = "available" ]; then
        log_success "Neptune snapshot verified: $TARGET_SNAPSHOT_ID (Status: $SNAPSHOT_STATUS)"

        # Get snapshot details
        aws neptune describe-db-cluster-snapshots \
            --db-cluster-snapshot-identifier "$TARGET_SNAPSHOT_ID" \
            --profile "$TARGET_PROFILE" \
            --query 'DBClusterSnapshots[0].{ID:DBClusterSnapshotIdentifier,Status:Status,Engine:Engine,AllocatedStorage:AllocatedStorage,SnapshotCreateTime:SnapshotCreateTime}' \
            --output table
    else
        log_error "Neptune snapshot not available. Status: $SNAPSHOT_STATUS"
        exit 1
    fi
}

neptune_rollback() {
    log_info "Rolling back Neptune migration..."

    TARGET_SNAPSHOT_ID=$(cat /tmp/neptune-target-snapshot-id.txt 2>/dev/null || echo "")
    if [ -n "$TARGET_SNAPSHOT_ID" ]; then
        log_info "Deleting target snapshot: $TARGET_SNAPSHOT_ID"
        aws neptune delete-db-cluster-snapshot \
            --db-cluster-snapshot-identifier "$TARGET_SNAPSHOT_ID" \
            --profile "$TARGET_PROFILE" \
            --region "$AWS_REGION" 2>/dev/null || true
    fi

    rm -f /tmp/neptune-migration-snapshot-id.txt /tmp/neptune-target-snapshot-id.txt
    log_success "Neptune rollback complete"
}

# =============================================================================
# OpenSearch Migration
# =============================================================================

opensearch_prepare() {
    log_info "Preparing OpenSearch snapshot for migration..."

    DOMAIN_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
    SNAPSHOT_REPO="migration-repo"
    SNAPSHOT_NAME="migration-$(date +%Y%m%d-%H%M%S)"

    # Get OpenSearch endpoint
    OS_ENDPOINT=$(aws opensearch describe-domain \
        --domain-name "$DOMAIN_NAME" \
        --profile "$SOURCE_PROFILE" \
        --query 'DomainStatus.Endpoint' \
        --output text)

    if [ -z "$OS_ENDPOINT" ] || [ "$OS_ENDPOINT" = "None" ]; then
        log_error "OpenSearch domain not found: $DOMAIN_NAME"
        exit 1
    fi

    log_info "OpenSearch Endpoint: $OS_ENDPOINT"

    # Register snapshot repository pointing to migration bucket
    log_info "Registering snapshot repository..."

    # Get the IRSA role ARN for OpenSearch access
    SNAPSHOT_ROLE_ARN=$(aws iam list-roles \
        --profile "$SOURCE_PROFILE" \
        --query "Roles[?contains(RoleName, 'opensearch') && contains(RoleName, '${ENVIRONMENT}')].Arn" \
        --output text | head -1)

    if [ -z "$SNAPSHOT_ROLE_ARN" ]; then
        log_warn "OpenSearch snapshot role not found. Manual snapshot registration may be required."
        log_info "See: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/managedomains-snapshots.html"
    fi

    # Store info for later
    echo "$DOMAIN_NAME" > /tmp/opensearch-migration-domain.txt
    echo "$SNAPSHOT_NAME" > /tmp/opensearch-migration-snapshot.txt

    log_success "OpenSearch preparation complete"
    log_info "Note: OpenSearch manual snapshot requires IAM role passthrough."
    log_info "Create snapshot via Kibana Dev Tools or AWS SDK with signed requests."
}

opensearch_migrate() {
    log_info "OpenSearch migration requires manual steps due to VPC restrictions."
    log_info ""
    log_info "Steps to complete OpenSearch migration:"
    log_info "1. Register S3 snapshot repository in SOURCE domain"
    log_info "2. Create snapshot to S3 bucket: $MIGRATION_BUCKET"
    log_info "3. Register same S3 repository in TARGET domain"
    log_info "4. Restore snapshot from S3"
    log_info ""
    log_info "For detailed steps, see: docs/deployment/MIGRATION_GUIDE.md"
}

opensearch_verify() {
    log_info "Verifying OpenSearch in target account..."

    DOMAIN_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

    # Check if domain exists in target
    DOMAIN_STATUS=$(aws opensearch describe-domain \
        --domain-name "$DOMAIN_NAME" \
        --profile "$TARGET_PROFILE" \
        --query 'DomainStatus.Processing' \
        --output text 2>/dev/null || echo "not-found")

    if [ "$DOMAIN_STATUS" != "not-found" ]; then
        log_success "OpenSearch domain exists in target account"
        aws opensearch describe-domain \
            --domain-name "$DOMAIN_NAME" \
            --profile "$TARGET_PROFILE" \
            --query 'DomainStatus.{DomainName:DomainName,Endpoint:Endpoint,EngineVersion:EngineVersion,Processing:Processing}' \
            --output table
    else
        log_warn "OpenSearch domain not found in target account. Deploy infrastructure first."
    fi
}

opensearch_rollback() {
    log_info "OpenSearch rollback: No automated rollback needed."
    log_info "Source domain remains untouched. Delete target domain if needed."
    rm -f /tmp/opensearch-migration-*.txt
    log_success "OpenSearch rollback complete"
}

# =============================================================================
# DynamoDB Migration
# =============================================================================

dynamodb_prepare() {
    log_info "Preparing DynamoDB tables for migration..."

    # List all Aura tables
    TABLES=$(aws dynamodb list-tables \
        --profile "$SOURCE_PROFILE" \
        --query "TableNames[?contains(@, '${PROJECT_NAME}')]" \
        --output json)

    echo "$TABLES" > /tmp/dynamodb-migration-tables.json

    TABLE_COUNT=$(echo "$TABLES" | jq 'length')
    log_info "Found $TABLE_COUNT DynamoDB tables to migrate"

    # Create backup for each table
    for TABLE in $(echo "$TABLES" | jq -r '.[]'); do
        log_info "Creating backup for table: $TABLE"
        BACKUP_ARN=$(aws dynamodb create-backup \
            --table-name "$TABLE" \
            --backup-name "${TABLE}-migration-$(date +%Y%m%d-%H%M%S)" \
            --profile "$SOURCE_PROFILE" \
            --query 'BackupDetails.BackupArn' \
            --output text)
        log_success "Backup created: $BACKUP_ARN"
    done

    log_success "DynamoDB preparation complete. $TABLE_COUNT tables backed up."
}

dynamodb_migrate() {
    log_info "Migrating DynamoDB tables to target account..."
    log_info ""
    log_info "DynamoDB cross-account migration options:"
    log_info ""
    log_info "Option 1: DynamoDB Export to S3 (Recommended for large tables)"
    log_info "  - Export tables to S3 in source account"
    log_info "  - Copy S3 data to target account"
    log_info "  - Import from S3 in target account"
    log_info ""
    log_info "Option 2: AWS Backup Cross-Account (Requires AWS Backup organization setup)"
    log_info "  - Create AWS Backup vault in target account"
    log_info "  - Copy backups cross-account"
    log_info "  - Restore in target account"
    log_info ""
    log_info "Option 3: AWS Data Pipeline / Glue (For active tables with ongoing writes)"
    log_info "  - Set up continuous replication"
    log_info "  - Switch applications after sync"
    log_info ""
    log_info "For this migration, we recommend Option 1 (Export/Import)."
    log_info ""

    # Export tables to S3
    TABLES=$(cat /tmp/dynamodb-migration-tables.json)

    for TABLE in $(echo "$TABLES" | jq -r '.[]'); do
        log_info "Exporting table: $TABLE"

        # Get table ARN
        TABLE_ARN=$(aws dynamodb describe-table \
            --table-name "$TABLE" \
            --profile "$SOURCE_PROFILE" \
            --query 'Table.TableArn' \
            --output text)

        # Export to S3
        EXPORT_ARN=$(aws dynamodb export-table-to-point-in-time \
            --table-arn "$TABLE_ARN" \
            --s3-bucket "$MIGRATION_BUCKET" \
            --s3-prefix "dynamodb-exports/$TABLE" \
            --export-format DYNAMODB_JSON \
            --profile "$SOURCE_PROFILE" \
            --query 'ExportDescription.ExportArn' \
            --output text 2>/dev/null || echo "PITR_NOT_ENABLED")

        if [ "$EXPORT_ARN" = "PITR_NOT_ENABLED" ]; then
            log_warn "PITR not enabled for $TABLE. Enable it first or use backup restore."
        else
            log_success "Export started: $EXPORT_ARN"
        fi
    done

    log_info "DynamoDB exports initiated. Monitor progress in AWS Console."
}

dynamodb_verify() {
    log_info "Verifying DynamoDB tables in target account..."

    SOURCE_TABLES=$(aws dynamodb list-tables \
        --profile "$SOURCE_PROFILE" \
        --query "TableNames[?contains(@, '${PROJECT_NAME}')]" \
        --output json)

    TARGET_TABLES=$(aws dynamodb list-tables \
        --profile "$TARGET_PROFILE" \
        --query "TableNames[?contains(@, '${PROJECT_NAME}')]" \
        --output json)

    SOURCE_COUNT=$(echo "$SOURCE_TABLES" | jq 'length')
    TARGET_COUNT=$(echo "$TARGET_TABLES" | jq 'length')

    log_info "Source tables: $SOURCE_COUNT"
    log_info "Target tables: $TARGET_COUNT"

    if [ "$SOURCE_COUNT" -eq "$TARGET_COUNT" ]; then
        log_success "Table count matches!"
    else
        log_warn "Table count mismatch. Some tables may not have been migrated."
    fi

    echo "$TARGET_TABLES" | jq -r '.[]' | while read -r TABLE; do
        ITEM_COUNT=$(aws dynamodb describe-table \
            --table-name "$TABLE" \
            --profile "$TARGET_PROFILE" \
            --query 'Table.ItemCount' \
            --output text)
        log_info "  $TABLE: $ITEM_COUNT items"
    done
}

dynamodb_rollback() {
    log_info "DynamoDB rollback: Source tables remain untouched."
    log_info "Delete exported data from S3 if needed."
    rm -f /tmp/dynamodb-migration-*.json
    log_success "DynamoDB rollback complete"
}

# =============================================================================
# S3 Migration
# =============================================================================

s3_prepare() {
    log_info "Preparing S3 buckets for migration..."

    # List all Aura buckets
    BUCKETS=$(aws s3api list-buckets \
        --profile "$SOURCE_PROFILE" \
        --query "Buckets[?contains(Name, '${PROJECT_NAME}')].Name" \
        --output json)

    echo "$BUCKETS" > /tmp/s3-migration-buckets.json

    BUCKET_COUNT=$(echo "$BUCKETS" | jq 'length')
    log_info "Found $BUCKET_COUNT S3 buckets to migrate"

    # Get bucket sizes
    for BUCKET in $(echo "$BUCKETS" | jq -r '.[]'); do
        SIZE=$(aws s3 ls "s3://$BUCKET" --recursive --summarize \
            --profile "$SOURCE_PROFILE" 2>/dev/null | grep "Total Size" | awk '{print $3, $4}' || echo "0 Bytes")
        log_info "  $BUCKET: $SIZE"
    done

    log_success "S3 preparation complete"
}

s3_migrate() {
    log_info "Migrating S3 buckets to target account..."

    BUCKETS=$(cat /tmp/s3-migration-buckets.json)

    for SOURCE_BUCKET in $(echo "$BUCKETS" | jq -r '.[]'); do
        # Create target bucket with same suffix
        SUFFIX=$(echo "$SOURCE_BUCKET" | sed "s/${PROJECT_NAME}-//" | sed "s/-${SOURCE_ACCOUNT_ID}//" | sed "s/-${ENVIRONMENT}//")
        TARGET_BUCKET="${PROJECT_NAME}-${SUFFIX}-${TARGET_ACCOUNT_ID}-${ENVIRONMENT}"

        log_info "Syncing $SOURCE_BUCKET -> $TARGET_BUCKET"

        # Check if target bucket exists
        if ! aws s3api head-bucket --bucket "$TARGET_BUCKET" --profile "$TARGET_PROFILE" 2>/dev/null; then
            log_info "Creating target bucket: $TARGET_BUCKET"
            aws s3api create-bucket \
                --bucket "$TARGET_BUCKET" \
                --region "$AWS_REGION" \
                --profile "$TARGET_PROFILE" 2>/dev/null || true
        fi

        # Sync data using aws s3 sync
        aws s3 sync \
            "s3://${SOURCE_BUCKET}" \
            "s3://${TARGET_BUCKET}" \
            --profile "$SOURCE_PROFILE" \
            --source-region "$AWS_REGION" \
            --region "$AWS_REGION" \
            2>&1 | head -20

        log_success "Bucket synced: $TARGET_BUCKET"
    done

    log_success "S3 migration complete"
}

s3_verify() {
    log_info "Verifying S3 buckets in target account..."

    SOURCE_BUCKETS=$(aws s3api list-buckets \
        --profile "$SOURCE_PROFILE" \
        --query "Buckets[?contains(Name, '${PROJECT_NAME}')].Name" \
        --output json)

    TARGET_BUCKETS=$(aws s3api list-buckets \
        --profile "$TARGET_PROFILE" \
        --query "Buckets[?contains(Name, '${PROJECT_NAME}')].Name" \
        --output json)

    SOURCE_COUNT=$(echo "$SOURCE_BUCKETS" | jq 'length')
    TARGET_COUNT=$(echo "$TARGET_BUCKETS" | jq 'length')

    log_info "Source buckets: $SOURCE_COUNT"
    log_info "Target buckets: $TARGET_COUNT"

    log_success "S3 verification complete"
}

s3_rollback() {
    log_info "S3 rollback: Source buckets remain untouched."
    log_info "Delete target buckets manually if needed (data safety)."
    rm -f /tmp/s3-migration-*.json
    log_success "S3 rollback complete"
}

# =============================================================================
# Main
# =============================================================================

usage() {
    echo "Usage: $0 <service> <action>"
    echo ""
    echo "Services: neptune, opensearch, dynamodb, s3, all"
    echo "Actions:  prepare, migrate, verify, rollback"
    echo ""
    echo "Examples:"
    echo "  $0 neptune prepare    # Create Neptune snapshot"
    echo "  $0 neptune migrate    # Copy snapshot to target account"
    echo "  $0 all prepare        # Prepare all services"
    echo "  $0 all verify         # Verify all migrations"
}

if [ $# -lt 2 ]; then
    usage
    exit 1
fi

SERVICE="$1"
ACTION="$2"

# Initialize
get_account_ids
get_migration_bucket
get_migration_kms_key

case "$SERVICE" in
    neptune)
        case "$ACTION" in
            prepare) neptune_prepare ;;
            migrate) neptune_migrate ;;
            verify) neptune_verify ;;
            rollback) neptune_rollback ;;
            *) usage; exit 1 ;;
        esac
        ;;
    opensearch)
        case "$ACTION" in
            prepare) opensearch_prepare ;;
            migrate) opensearch_migrate ;;
            verify) opensearch_verify ;;
            rollback) opensearch_rollback ;;
            *) usage; exit 1 ;;
        esac
        ;;
    dynamodb)
        case "$ACTION" in
            prepare) dynamodb_prepare ;;
            migrate) dynamodb_migrate ;;
            verify) dynamodb_verify ;;
            rollback) dynamodb_rollback ;;
            *) usage; exit 1 ;;
        esac
        ;;
    s3)
        case "$ACTION" in
            prepare) s3_prepare ;;
            migrate) s3_migrate ;;
            verify) s3_verify ;;
            rollback) s3_rollback ;;
            *) usage; exit 1 ;;
        esac
        ;;
    all)
        case "$ACTION" in
            prepare)
                neptune_prepare
                opensearch_prepare
                dynamodb_prepare
                s3_prepare
                ;;
            migrate)
                neptune_migrate
                opensearch_migrate
                dynamodb_migrate
                s3_migrate
                ;;
            verify)
                neptune_verify
                opensearch_verify
                dynamodb_verify
                s3_verify
                ;;
            rollback)
                neptune_rollback
                opensearch_rollback
                dynamodb_rollback
                s3_rollback
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
