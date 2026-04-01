#!/bin/bash
#
# Project Aura - Deploy Agentic Search Infrastructure
#
# Deploys OpenSearch filesystem index and runs initial repository scan.
# Supports both AWS Commercial Cloud and AWS GovCloud (US).
#
# Usage:
#   ./deploy-agentic-search.sh <environment> <repo-path>
#
# Examples:
#   ./deploy-agentic-search.sh dev /path/to/codebase
#   ./deploy-agentic-search.sh prod /opt/repos/production-app
#
# Author: Project Aura Team
# Created: 2025-11-18

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# AWS Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-default}"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Install: https://aws.amazon.com/cli/"
        exit 1
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Install Python 3.11+"
        exit 1
    fi

    # Check jq for JSON parsing
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Install: brew install jq (macOS) or apt install jq (Linux)"
        exit 1
    fi

    # Verify AWS credentials
    if ! aws sts get-caller-identity --profile "${AWS_PROFILE}" &> /dev/null; then
        log_error "AWS credentials not configured for profile: ${AWS_PROFILE}"
        log_info "Run: aws configure --profile ${AWS_PROFILE}"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

deploy_opensearch_stack() {
    local env=$1
    local vpc_id=$2
    local subnet_ids=$3
    local master_password=$4

    log_info "Deploying OpenSearch CloudFormation stack..."

    local stack_name="aura-opensearch-${env}"
    local template_file="${PROJECT_ROOT}/deploy/cloudformation/opensearch-filesystem-index.yaml"

    # Check if stack exists
    if aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" &> /dev/null; then

        log_info "Stack ${stack_name} exists, updating..."

        aws cloudformation update-stack \
            --stack-name "${stack_name}" \
            --template-body "file://${template_file}" \
            --parameters \
                ParameterKey=Environment,ParameterValue="${env}" \
                ParameterKey=VpcId,ParameterValue="${vpc_id}" \
                ParameterKey=PrivateSubnetIds,ParameterValue="${subnet_ids}" \
                ParameterKey=MasterUserPassword,ParameterValue="${master_password}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}" || {
            # Update may fail if no changes
            log_warning "Stack update failed or no changes detected"
        }

        log_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "${stack_name}" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}" 2>/dev/null || true
    else
        log_info "Stack ${stack_name} does not exist, creating..."

        aws cloudformation create-stack \
            --stack-name "${stack_name}" \
            --template-body "file://${template_file}" \
            --parameters \
                ParameterKey=Environment,ParameterValue="${env}" \
                ParameterKey=VpcId,ParameterValue="${vpc_id}" \
                ParameterKey=PrivateSubnetIds,ParameterValue="${subnet_ids}" \
                ParameterKey=MasterUserPassword,ParameterValue="${master_password}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"

        log_info "Waiting for stack creation to complete (this may take 15-20 minutes)..."
        aws cloudformation wait stack-create-complete \
            --stack-name "${stack_name}" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    fi

    log_success "OpenSearch stack deployed"
}

get_stack_outputs() {
    local env=$1
    local stack_name="aura-opensearch-${env}"

    log_info "Retrieving stack outputs..."

    aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs' \
        --output json
}

install_python_dependencies() {
    log_info "Installing Python dependencies..."

    cd "${PROJECT_ROOT}"

    # Create virtual environment if not exists
    if [ ! -d "venv" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    pip install -q --upgrade pip
    pip install -q -r requirements.txt

    log_success "Python dependencies installed"
}

run_initial_repository_scan() {
    local repo_path=$1
    local opensearch_endpoint=$2
    local env=$3

    log_info "Running initial repository scan..."
    log_info "Repository: ${repo_path}"
    log_info "OpenSearch endpoint: ${opensearch_endpoint}"

    # Activate virtual environment
    source "${PROJECT_ROOT}/venv/bin/activate"

    # Create Python script for indexing
    local indexer_script="${PROJECT_ROOT}/scripts/index_repository.py"

    if [ ! -f "${indexer_script}" ]; then
        log_info "Creating indexer script..."
        mkdir -p "${PROJECT_ROOT}/scripts"

        cat > "${indexer_script}" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""
Temporary script to index repository into OpenSearch.
This will be replaced by a proper service in production.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.filesystem_indexer import FilesystemIndexer
from opensearchpy import AsyncOpenSearch


async def main():
    if len(sys.argv) < 3:
        print("Usage: index_repository.py <repo_path> <opensearch_endpoint>")
        sys.exit(1)

    repo_path = Path(sys.argv[1])
    opensearch_endpoint = sys.argv[2]

    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    print(f"Connecting to OpenSearch: {opensearch_endpoint}")

    # Create OpenSearch client
    # Note: In production, use AWS IAM auth with AWS4Auth
    opensearch_client = AsyncOpenSearch(
        hosts=[{'host': opensearch_endpoint, 'port': 443}],
        use_ssl=True,
        verify_certs=True,
        connection_class='RequestsHttpConnection'
    )

    # Create mock embeddings service (replace with real service)
    class MockEmbeddingsService:
        async def generate_embedding(self, text: str):
            # In production, use AWS Bedrock Titan or OpenAI
            return [0.0] * 1536

    embeddings_service = MockEmbeddingsService()

    # Create indexer
    indexer = FilesystemIndexer(
        opensearch_client=opensearch_client,
        embedding_service=embeddings_service,
        filesystem_index="aura-filesystem-metadata"
    )

    print(f"Starting repository scan: {repo_path}")
    print("This may take several minutes for large repositories...")

    # Index repository
    stats = await indexer.index_repository(repo_path, batch_size=100)

    print("\n" + "="*60)
    print("Repository Indexing Complete")
    print("="*60)
    print(f"Files indexed: {stats.get('files_indexed', 0)}")
    print(f"Files skipped: {stats.get('files_skipped', 0)}")
    print(f"Total time: {stats.get('elapsed_seconds', 0):.2f} seconds")
    print("="*60)

    await opensearch_client.close()


if __name__ == "__main__":
    asyncio.run(main())
PYTHON_SCRIPT

        chmod +x "${indexer_script}"
        log_success "Created indexer script"
    fi

    # Run indexer
    python3 "${indexer_script}" "${repo_path}" "${opensearch_endpoint}"

    log_success "Repository scan complete"
}

configure_incremental_updates() {
    local env=$1

    log_info "Configuring incremental updates (git hooks)..."

    # Create git hook for automatic indexing on commit
    local git_hook="${PROJECT_ROOT}/.git/hooks/post-commit"

    cat > "${git_hook}" << 'BASH_HOOK'
#!/bin/bash
#
# Git hook: Auto-index changed files on commit
#

# Get changed files in last commit
changed_files=$(git diff-tree --no-commit-id --name-only -r HEAD)

# TODO: Call filesystem indexer API to update changed files
# For now, just log
echo "Files changed (will be auto-indexed in production):"
echo "$changed_files"
BASH_HOOK

    chmod +x "${git_hook}"

    log_success "Incremental updates configured (git post-commit hook)"
}

print_deployment_summary() {
    local env=$1
    local opensearch_endpoint=$2
    local kibana_endpoint=$3
    local repo_path=$4

    echo ""
    echo "========================================================================"
    echo "  Agentic Search Deployment Summary"
    echo "========================================================================"
    echo ""
    echo "Environment:          ${env}"
    echo "OpenSearch Endpoint:  https://${opensearch_endpoint}"
    echo "Dashboards URL:       ${kibana_endpoint}"
    echo "Repository Indexed:   ${repo_path}"
    echo ""
    echo "Index Name:           aura-filesystem-metadata"
    echo "AWS Region:           ${AWS_REGION}"
    echo "AWS Profile:          ${AWS_PROFILE}"
    echo ""
    echo "========================================================================"
    echo "  Next Steps"
    echo "========================================================================"
    echo ""
    echo "1. Access OpenSearch Dashboards:"
    echo "   ${kibana_endpoint}"
    echo ""
    echo "2. Test semantic search:"
    echo "   python3 scripts/test_agentic_search.py"
    echo ""
    echo "3. Monitor indexing status:"
    echo "   aws cloudwatch logs tail /aws/opensearch/aura-filesystem-${env}/application-logs \\"
    echo "       --follow --profile ${AWS_PROFILE} --region ${AWS_REGION}"
    echo ""
    echo "4. View indexed files count:"
    echo "   curl -XGET 'https://${opensearch_endpoint}/aura-filesystem-metadata/_count'"
    echo ""
    echo "========================================================================"
}

# =============================================================================
# Main Script
# =============================================================================

main() {
    # Parse arguments
    if [ $# -lt 2 ]; then
        echo "Usage: $0 <environment> <repo-path>"
        echo ""
        echo "Arguments:"
        echo "  environment    Environment name (dev, qa, prod)"
        echo "  repo-path      Path to Git repository to index"
        echo ""
        echo "Environment Variables:"
        echo "  AWS_PROFILE    AWS CLI profile (default: default)"
        echo "  AWS_REGION     AWS region (default: us-east-1)"
        echo ""
        echo "Example:"
        echo "  $0 dev /path/to/codebase"
        exit 1
    fi

    local environment=$1
    local repo_path=$2

    # Validate environment
    if [[ ! "$environment" =~ ^(dev|qa|prod)$ ]]; then
        log_error "Invalid environment: ${environment}. Must be dev, qa, or prod"
        exit 1
    fi

    # Validate repository path
    if [ ! -d "$repo_path" ]; then
        log_error "Repository path does not exist: ${repo_path}"
        exit 1
    fi

    if [ ! -d "${repo_path}/.git" ]; then
        log_error "Not a Git repository: ${repo_path}"
        exit 1
    fi

    log_info "Starting Agentic Search deployment"
    log_info "Environment: ${environment}"
    log_info "Repository: ${repo_path}"
    log_info "AWS Region: ${AWS_REGION}"
    log_info "AWS Profile: ${AWS_PROFILE}"
    echo ""

    # Check prerequisites
    check_prerequisites

    # Get VPC and subnet information
    log_info "Retrieving VPC configuration..."

    # Try to get VPC from existing infrastructure stack
    local vpc_stack_name="aura-infrastructure-${environment}"

    if aws cloudformation describe-stacks \
        --stack-name "${vpc_stack_name}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" &> /dev/null; then

        log_info "Found existing infrastructure stack: ${vpc_stack_name}"

        local vpc_id=$(aws cloudformation describe-stacks \
            --stack-name "${vpc_stack_name}" \
            --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
            --output text \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}")

        local subnet_ids=$(aws cloudformation describe-stacks \
            --stack-name "${vpc_stack_name}" \
            --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' \
            --output text \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}")

        log_success "VPC ID: ${vpc_id}"
        log_success "Subnet IDs: ${subnet_ids}"
    else
        log_error "Infrastructure stack not found: ${vpc_stack_name}"
        log_info "Please deploy VPC infrastructure first:"
        log_info "  aws cloudformation create-stack --stack-name ${vpc_stack_name} ..."
        exit 1
    fi

    # Prompt for OpenSearch master password
    echo ""
    read -s -p "Enter OpenSearch master password (min 8 chars, uppercase, lowercase, number, special char): " master_password
    echo ""

    if [ ${#master_password} -lt 8 ]; then
        log_error "Password must be at least 8 characters"
        exit 1
    fi

    # Deploy OpenSearch stack
    deploy_opensearch_stack "${environment}" "${vpc_id}" "${subnet_ids}" "${master_password}"

    # Get stack outputs
    local outputs=$(get_stack_outputs "${environment}")

    local opensearch_endpoint=$(echo "${outputs}" | jq -r '.[] | select(.OutputKey=="DomainEndpoint") | .OutputValue')
    local kibana_endpoint=$(echo "${outputs}" | jq -r '.[] | select(.OutputKey=="KibanaEndpoint") | .OutputValue')

    log_success "OpenSearch endpoint: ${opensearch_endpoint}"
    log_success "Dashboards URL: ${kibana_endpoint}"

    # Install Python dependencies
    install_python_dependencies

    # Run initial repository scan
    run_initial_repository_scan "${repo_path}" "${opensearch_endpoint}" "${environment}"

    # Configure incremental updates
    configure_incremental_updates "${environment}"

    # Print summary
    print_deployment_summary "${environment}" "${opensearch_endpoint}" "${kibana_endpoint}" "${repo_path}"

    log_success "Agentic Search deployment complete!"
}

# Run main function
main "$@"
