#!/bin/bash
#
# Project Aura - DNS Blocklist Update Script
#
# Generates and deploys DNS blocklists from threat intelligence feeds.
# Can run locally or as part of CI/CD pipeline.
#
# Usage:
#   ./update-dnsmasq-blocklist.sh [OPTIONS]
#
# Options:
#   -e, --environment   Environment (dev, qa, prod) [default: dev]
#   -d, --dry-run       Generate blocklist but don't deploy
#   -k, --update-k8s    Update Kubernetes ConfigMap
#   -s, --update-s3     Upload to S3 bucket
#   -l, --local-only    Generate local file only
#   -v, --verbose       Enable verbose output
#   -h, --help          Show this help message
#
# Examples:
#   ./update-dnsmasq-blocklist.sh -e dev --dry-run
#   ./update-dnsmasq-blocklist.sh -e prod -k -s
#   ./update-dnsmasq-blocklist.sh --local-only
#

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Defaults
ENVIRONMENT="dev"
PROJECT_NAME="aura"
DRY_RUN=false
UPDATE_K8S=false
UPDATE_S3=false
LOCAL_ONLY=false
VERBOSE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Show help
show_help() {
    head -30 "$0" | tail -n +3 | sed 's/^#//'
    exit 0
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -k|--update-k8s)
                UPDATE_K8S=true
                shift
                ;;
            -s|--update-s3)
                UPDATE_S3=true
                shift
                ;;
            -l|--local-only)
                LOCAL_ONLY=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                ;;
        esac
    done
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        dev|qa|prod)
            log_info "Environment: $ENVIRONMENT"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT (must be dev, qa, or prod)"
            exit 1
            ;;
    esac
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    # Python 3
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    log_verbose "Python 3: $(python3 --version)"

    # AWS CLI (if S3 update enabled)
    if [[ "$UPDATE_S3" == "true" ]]; then
        if ! command -v aws &> /dev/null; then
            log_error "AWS CLI is required for S3 updates but not installed"
            exit 1
        fi
        log_verbose "AWS CLI: $(aws --version)"
    fi

    # kubectl (if K8s update enabled)
    if [[ "$UPDATE_K8S" == "true" ]]; then
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl is required for Kubernetes updates but not installed"
            exit 1
        fi
        log_verbose "kubectl: $(kubectl version --client --short 2>/dev/null || echo 'unknown')"
    fi
}

# Generate blocklist using Python service
generate_blocklist() {
    log_info "Generating DNS blocklist from threat intelligence feeds..."

    local output_file="${PROJECT_ROOT}/deploy/config/dnsmasq/blocklist-${ENVIRONMENT}.conf"
    local temp_file="/tmp/aura-blocklist-$$.conf"

    # Run Python script
    cd "$PROJECT_ROOT"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Dry run mode - using mock data"
    fi

    python3 -c "
import asyncio
import sys
sys.path.insert(0, '${PROJECT_ROOT}')

from src.services.dns_blocklist_service import BlocklistConfig, create_blocklist_service

async def main():
    config = BlocklistConfig(
        enable_nvd=True,
        enable_cisa_kev=True,
        enable_github=True,
        enable_urlhaus=True,
        enable_abuse_ch=True,
        min_severity='medium',
        block_ransomware=True,
        max_entries=10000,
        include_comments=True,
        include_metadata_header=True,
    )

    # Use mock mode for dry run or if httpx not available
    use_mock = ${DRY_RUN:+True}${DRY_RUN:-False}
    service = create_blocklist_service(config=config, use_mock=use_mock)

    print('Fetching threat intelligence...', file=sys.stderr)
    entries = await service.generate_blocklist()
    stats = service.get_stats()

    print(f'Generated {len(entries)} blocklist entries', file=sys.stderr)
    print(f'Sources: {stats[\"entries_by_source\"]}', file=sys.stderr)
    print(f'Categories: {stats[\"entries_by_category\"]}', file=sys.stderr)
    print(f'Severity: {stats[\"entries_by_severity\"]}', file=sys.stderr)

    # Render config
    config_content = service.render_dnsmasq_config(entries)
    print(config_content)

    await service.threat_client.close()

asyncio.run(main())
" > "$temp_file" 2>&1 || {
        log_error "Failed to generate blocklist"
        cat "$temp_file"
        rm -f "$temp_file"
        exit 1
    }

    # Check if output is valid
    if [[ ! -s "$temp_file" ]]; then
        log_error "Generated blocklist is empty"
        exit 1
    fi

    # Copy to output location
    mkdir -p "$(dirname "$output_file")"
    mv "$temp_file" "$output_file"

    log_success "Blocklist generated: $output_file"
    log_info "File size: $(wc -c < "$output_file") bytes"
    log_info "Entry count: $(grep -c '^address=' "$output_file" || echo 0)"

    export BLOCKLIST_FILE="$output_file"
}

# Upload to S3
upload_to_s3() {
    if [[ "$UPDATE_S3" != "true" ]]; then
        log_verbose "S3 update skipped (not enabled)"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "Dry run - S3 upload skipped"
        return 0
    fi

    local bucket="${PROJECT_NAME}-config-${ENVIRONMENT}"
    local key="dnsmasq/blocklist-${ENVIRONMENT}.conf"

    log_info "Uploading blocklist to S3..."
    log_verbose "Bucket: $bucket, Key: $key"

    # Check if bucket exists
    if ! aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
        log_error "S3 bucket does not exist: $bucket"
        return 1
    fi

    # Upload with metadata
    aws s3 cp "$BLOCKLIST_FILE" "s3://${bucket}/${key}" \
        --content-type "text/plain" \
        --metadata "generator=aura-blocklist-script,environment=${ENVIRONMENT}" \
        || {
            log_error "S3 upload failed"
            return 1
        }

    log_success "Uploaded to s3://${bucket}/${key}"
}

# Update Kubernetes ConfigMap
update_kubernetes() {
    if [[ "$UPDATE_K8S" != "true" ]]; then
        log_verbose "Kubernetes update skipped (not enabled)"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "Dry run - Kubernetes update skipped"
        return 0
    fi

    local namespace="aura-network-services"
    local configmap_name="dnsmasq-blocklist"

    log_info "Updating Kubernetes ConfigMap..."
    log_verbose "Namespace: $namespace, ConfigMap: $configmap_name"

    # Check if namespace exists
    if ! kubectl get namespace "$namespace" &>/dev/null; then
        log_warn "Namespace $namespace does not exist, creating..."
        kubectl create namespace "$namespace" || true
    fi

    # Create or update ConfigMap
    kubectl create configmap "$configmap_name" \
        --namespace="$namespace" \
        --from-file="blocklist.conf=$BLOCKLIST_FILE" \
        --dry-run=client -o yaml | kubectl apply -f - || {
            log_error "Failed to update ConfigMap"
            return 1
        }

    log_success "ConfigMap updated: $namespace/$configmap_name"

    # Trigger dnsmasq reload by annotating the DaemonSet
    log_info "Triggering dnsmasq reload..."
    kubectl annotate daemonset dnsmasq \
        --namespace="$namespace" \
        "blocklist.aura.local/last-updated=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --overwrite 2>/dev/null || {
            log_warn "Could not annotate DaemonSet (may not exist yet)"
        }
}

# Main execution
main() {
    echo "============================================="
    echo "Project Aura - DNS Blocklist Updater"
    echo "============================================="

    parse_args "$@"
    validate_environment
    check_dependencies

    echo ""
    log_info "Configuration:"
    log_info "  Environment: $ENVIRONMENT"
    log_info "  Dry Run: $DRY_RUN"
    log_info "  Update S3: $UPDATE_S3"
    log_info "  Update K8s: $UPDATE_K8S"
    log_info "  Local Only: $LOCAL_ONLY"
    echo ""

    # Generate blocklist
    generate_blocklist

    if [[ "$LOCAL_ONLY" == "true" ]]; then
        log_success "Local-only mode - deployment skipped"
        echo ""
        log_info "Generated blocklist: $BLOCKLIST_FILE"
        exit 0
    fi

    # Deploy
    upload_to_s3
    update_kubernetes

    echo ""
    echo "============================================="
    log_success "Blocklist update complete!"
    echo "============================================="
}

main "$@"
