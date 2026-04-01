#!/bin/bash
# =============================================================================
# Project Aura - Lambda Packaging Utility
# =============================================================================
# Shared utility functions for packaging Lambda functions and uploading to S3.
# Handles dependency installation, zip creation, and S3 upload.
#
# USAGE:
#   source deploy/scripts/package-lambdas.sh
#   package_lambda "function-name" "src/lambdas/function" "s3://bucket/path"
#
# FUNCTIONS:
#   package_lambda           - Package a Lambda function and upload to S3
#   package_lambda_layer     - Package a Lambda layer
#   get_lambda_code_hash     - Calculate SHA256 hash for Lambda code
#   upload_to_s3             - Upload a file to S3 with content hash
#   check_s3_object_exists   - Check if S3 object exists with matching hash
#
# PREREQUISITES:
#   - Python 3.11+ installed
#   - pip installed
#   - AWS CLI configured with S3 access
#   - Required environment variables: AWS_DEFAULT_REGION (or AWS_REGION)
#
# =============================================================================

# Fail on error and pipe failures (unless already set)
if [[ "${LAMBDA_HELPERS_SOURCED:-}" != "true" ]]; then
    set -o pipefail
    LAMBDA_HELPERS_SOURCED=true
fi

# =============================================================================
# Configuration
# =============================================================================
LAMBDA_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}"
LAMBDA_BUILD_DIR="${LAMBDA_BUILD_DIR:-/tmp/lambda-builds}"
LAMBDA_PYTHON_VERSION="${LAMBDA_PYTHON_VERSION:-python3.11}"

# Colors for output
readonly LAMBDA_RED='\033[0;31m'
readonly LAMBDA_GREEN='\033[0;32m'
readonly LAMBDA_YELLOW='\033[1;33m'
readonly LAMBDA_BLUE='\033[0;34m'
readonly LAMBDA_NC='\033[0m'

# =============================================================================
# Logging Functions
# =============================================================================

lambda_log_info() {
    echo -e "${LAMBDA_BLUE}[LAMBDA]${LAMBDA_NC} $1" >&2
}

lambda_log_success() {
    echo -e "${LAMBDA_GREEN}[LAMBDA]${LAMBDA_NC} $1" >&2
}

lambda_log_warning() {
    echo -e "${LAMBDA_YELLOW}[LAMBDA]${LAMBDA_NC} $1" >&2
}

lambda_log_error() {
    echo -e "${LAMBDA_RED}[LAMBDA]${LAMBDA_NC} $1" >&2
}

# =============================================================================
# Hash Functions
# =============================================================================

# Calculate SHA256 hash for a directory (Lambda source code)
# Arguments: source_dir
# Outputs: SHA256 hash string
get_lambda_code_hash() {
    local source_dir="$1"

    # Hash all Python files and requirements.txt
    find "$source_dir" -type f \( -name "*.py" -o -name "requirements.txt" \) \
        -exec sha256sum {} \; 2>/dev/null | \
        sort | \
        sha256sum | \
        awk '{print $1}'
}

# Calculate SHA256 hash for a file
# Arguments: file_path
# Outputs: SHA256 hash string
get_file_hash() {
    local file_path="$1"
    sha256sum "$file_path" | awk '{print $1}'
}

# =============================================================================
# S3 Functions
# =============================================================================

# Check if S3 object exists with matching hash
# Arguments: s3_uri code_hash
# Returns: 0 if exists with matching hash, 1 otherwise
check_s3_object_exists() {
    local s3_uri="$1"
    local expected_hash="$2"

    # Get object metadata
    local metadata
    metadata=$(aws s3api head-object \
        --bucket "$(echo "$s3_uri" | sed 's|s3://||' | cut -d/ -f1)" \
        --key "$(echo "$s3_uri" | sed 's|s3://[^/]*/||')" \
        --query 'Metadata.codehash' \
        --output text 2>/dev/null) || return 1

    if [[ "$metadata" == "$expected_hash" ]]; then
        return 0
    else
        return 1
    fi
}

# Upload a file to S3 with metadata
# Arguments: local_file s3_uri code_hash
upload_to_s3() {
    local local_file="$1"
    local s3_uri="$2"
    local code_hash="${3:-}"

    local metadata_args=""
    if [[ -n "$code_hash" ]]; then
        metadata_args="--metadata codehash=$code_hash"
    fi

    lambda_log_info "Uploading to $s3_uri"
    aws s3 cp "$local_file" "$s3_uri" $metadata_args --region "$LAMBDA_REGION"
}

# =============================================================================
# Package Functions
# =============================================================================

# Package a Lambda function and upload to S3
# Arguments:
#   function_name   - Name of the Lambda function
#   source_dir      - Directory containing Lambda source code
#   s3_bucket       - S3 bucket name for deployment packages
#   s3_prefix       - S3 key prefix (optional, defaults to "lambdas/")
#   skip_if_exists  - Skip upload if hash matches (default: true)
# Outputs: S3 URI of the uploaded package
package_lambda() {
    local function_name="$1"
    local source_dir="$2"
    local s3_bucket="$3"
    local s3_prefix="${4:-lambdas}"
    local skip_if_exists="${5:-true}"

    lambda_log_info "Packaging Lambda: $function_name"

    # Validate source directory
    if [[ ! -d "$source_dir" ]]; then
        lambda_log_error "Source directory not found: $source_dir"
        return 1
    fi

    # Calculate code hash for change detection
    local code_hash
    code_hash=$(get_lambda_code_hash "$source_dir")
    lambda_log_info "Code hash: $code_hash"

    # Build S3 URI
    local s3_key="${s3_prefix}/${function_name}/${code_hash}.zip"
    local s3_uri="s3://${s3_bucket}/${s3_key}"

    # Check if already uploaded
    if [[ "$skip_if_exists" == "true" ]] && check_s3_object_exists "$s3_uri" "$code_hash"; then
        lambda_log_info "Package already exists with matching hash, skipping upload"
        echo "$s3_uri"
        return 0
    fi

    # Create build directory
    local build_dir="${LAMBDA_BUILD_DIR}/${function_name}"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"

    # Copy source files
    lambda_log_info "Copying source files..."
    cp -r "$source_dir"/* "$build_dir/"

    # Install dependencies if requirements.txt exists
    if [[ -f "$build_dir/requirements.txt" ]]; then
        lambda_log_info "Installing dependencies..."
        pip install \
            --target "$build_dir" \
            --requirement "$build_dir/requirements.txt" \
            --quiet \
            --no-cache-dir \
            --platform manylinux2014_x86_64 \
            --implementation cp \
            --python-version 3.11 \
            --only-binary=:all: \
            --upgrade 2>/dev/null || \
        pip install \
            --target "$build_dir" \
            --requirement "$build_dir/requirements.txt" \
            --quiet \
            --no-cache-dir
    fi

    # Remove unnecessary files to reduce package size
    lambda_log_info "Cleaning build directory..."
    find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$build_dir" -type f -name "*.pyo" -delete 2>/dev/null || true

    # Create zip package
    local zip_file="${LAMBDA_BUILD_DIR}/${function_name}.zip"
    lambda_log_info "Creating deployment package..."
    (cd "$build_dir" && zip -q -r "$zip_file" .)

    # Report package size
    local package_size
    package_size=$(ls -lh "$zip_file" | awk '{print $5}')
    lambda_log_info "Package size: $package_size"

    # Upload to S3
    upload_to_s3 "$zip_file" "$s3_uri" "$code_hash"

    # Cleanup
    rm -rf "$build_dir" "$zip_file"

    lambda_log_success "Package uploaded: $s3_uri"
    echo "$s3_uri"
}

# Package a Lambda layer and upload to S3
# Arguments:
#   layer_name      - Name of the Lambda layer
#   requirements    - Path to requirements.txt
#   s3_bucket       - S3 bucket name
#   s3_prefix       - S3 key prefix (optional)
# Outputs: S3 URI of the uploaded layer
package_lambda_layer() {
    local layer_name="$1"
    local requirements="$2"
    local s3_bucket="$3"
    local s3_prefix="${4:-layers}"

    lambda_log_info "Packaging Lambda layer: $layer_name"

    # Validate requirements file
    if [[ ! -f "$requirements" ]]; then
        lambda_log_error "Requirements file not found: $requirements"
        return 1
    fi

    # Calculate hash from requirements
    local code_hash
    code_hash=$(sha256sum "$requirements" | awk '{print $1}')
    lambda_log_info "Requirements hash: $code_hash"

    # Build S3 URI
    local s3_key="${s3_prefix}/${layer_name}/${code_hash}.zip"
    local s3_uri="s3://${s3_bucket}/${s3_key}"

    # Check if already uploaded
    if check_s3_object_exists "$s3_uri" "$code_hash"; then
        lambda_log_info "Layer already exists with matching hash, skipping upload"
        echo "$s3_uri"
        return 0
    fi

    # Create build directory with Lambda layer structure
    local build_dir="${LAMBDA_BUILD_DIR}/${layer_name}/python"
    rm -rf "${LAMBDA_BUILD_DIR}/${layer_name}"
    mkdir -p "$build_dir"

    # Install dependencies
    lambda_log_info "Installing dependencies..."
    pip install \
        --target "$build_dir" \
        --requirement "$requirements" \
        --quiet \
        --no-cache-dir \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.11 \
        --only-binary=:all: \
        --upgrade 2>/dev/null || \
    pip install \
        --target "$build_dir" \
        --requirement "$requirements" \
        --quiet \
        --no-cache-dir

    # Clean up unnecessary files
    lambda_log_info "Cleaning build directory..."
    find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

    # Create zip package
    local zip_file="${LAMBDA_BUILD_DIR}/${layer_name}.zip"
    lambda_log_info "Creating layer package..."
    (cd "${LAMBDA_BUILD_DIR}/${layer_name}" && zip -q -r "$zip_file" .)

    # Report package size
    local package_size
    package_size=$(ls -lh "$zip_file" | awk '{print $5}')
    lambda_log_info "Layer size: $package_size"

    # Warn if layer is too large (250MB unzipped limit, but check zip size)
    local zip_size_bytes
    zip_size_bytes=$(stat -f%z "$zip_file" 2>/dev/null || stat -c%s "$zip_file" 2>/dev/null)
    if [[ $zip_size_bytes -gt 52428800 ]]; then  # 50MB warning threshold
        lambda_log_warning "Layer package is large (>50MB). Consider splitting dependencies."
    fi

    # Upload to S3
    upload_to_s3 "$zip_file" "$s3_uri" "$code_hash"

    # Cleanup
    rm -rf "${LAMBDA_BUILD_DIR}/${layer_name}" "$zip_file"

    lambda_log_success "Layer uploaded: $s3_uri"
    echo "$s3_uri"
}

# Package all Lambda functions in a directory
# Arguments:
#   source_root     - Root directory containing Lambda function subdirectories
#   s3_bucket       - S3 bucket name
#   s3_prefix       - S3 key prefix
# Outputs: Space-separated list of S3 URIs
package_all_lambdas() {
    local source_root="$1"
    local s3_bucket="$2"
    local s3_prefix="${3:-lambdas}"

    lambda_log_info "Packaging all Lambdas in: $source_root"

    local results=()

    # Find all directories with handler.py or lambda_function.py
    while IFS= read -r -d '' handler; do
        local func_dir
        func_dir=$(dirname "$handler")
        local func_name
        func_name=$(basename "$func_dir")

        lambda_log_info "Found Lambda: $func_name"
        local s3_uri
        s3_uri=$(package_lambda "$func_name" "$func_dir" "$s3_bucket" "$s3_prefix")
        results+=("$s3_uri")
    done < <(find "$source_root" -maxdepth 2 \( -name "handler.py" -o -name "lambda_function.py" \) -print0)

    echo "${results[*]}"
}

# =============================================================================
# Export functions for use in buildspecs
# =============================================================================
export -f lambda_log_info lambda_log_success lambda_log_warning lambda_log_error
export -f get_lambda_code_hash get_file_hash
export -f check_s3_object_exists upload_to_s3
export -f package_lambda package_lambda_layer package_all_lambdas
