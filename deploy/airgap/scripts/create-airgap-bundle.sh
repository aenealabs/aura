#!/usr/bin/env bash
# Project Aura - Air-Gap Bundle Creation Script
# Creates a self-contained deployment bundle for air-gapped environments
#
# Usage:
#   ./create-airgap-bundle.sh [OPTIONS]
#
# Options:
#   --version VERSION     Bundle version (default: from Chart.yaml)
#   --output DIR          Output directory (default: ./dist)
#   --include-models      Include LLM model weights (large download)
#   --model MODEL         Model to include (default: mistral-7b-instruct-v0.3)
#   --registry REGISTRY   Source registry (default: docker.io/aenealabs)
#   --sign                Sign bundle with cosign
#   --fips                Include FIPS-enabled images
#   --help                Show this help message

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
HELM_CHART_DIR="${PROJECT_ROOT}/deploy/helm/aura"

# Default values
VERSION=""
OUTPUT_DIR="${PROJECT_ROOT}/dist"
INCLUDE_MODELS=false
MODEL_NAME="mistral-7b-instruct-v0.3"
SOURCE_REGISTRY="docker.io/aenealabs"
SIGN_BUNDLE=false
FIPS_MODE=false
TEMP_DIR=""

# Container images required for air-gap deployment
declare -A AURA_IMAGES=(
    ["aura-api"]="1.3.0"
    ["aura-frontend"]="1.3.0"
    ["aura-orchestrator"]="1.3.0"
    ["aura-chat-lambda"]="1.3.0"
)

declare -A THIRD_PARTY_IMAGES=(
    ["neo4j"]="docker.io/neo4j:5-enterprise"
    ["opensearch"]="docker.io/opensearchproject/opensearch:2.11.0"
    ["postgres"]="docker.io/postgres:16-alpine"
    ["redis"]="docker.io/redis:7-alpine"
    ["vllm"]="docker.io/vllm/vllm-openai:v0.4.0"
    ["ollama"]="docker.io/ollama/ollama:latest"
    ["minio"]="docker.io/minio/minio:latest"
    ["curl"]="docker.io/curlimages/curl:8.5.0"
)

# FIPS-enabled image variants
declare -A FIPS_IMAGES=(
    ["postgres"]="docker.io/postgres:16-alpine"  # Note: use RHEL UBI for true FIPS
    ["redis"]="docker.io/redis:7-alpine"
)

# Model configurations for air-gap
declare -A MODEL_CONFIGS=(
    ["mistral-7b-instruct-v0.3"]="https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3"
    ["qwen2.5-coder-7b"]="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct"
    ["mistral-8x7b-instruct"]="https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1"
)

# Cleanup function
cleanup() {
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        log_info "Cleaning up temporary directory..."
        rm -rf "${TEMP_DIR}"
    fi
}

trap cleanup EXIT

# Show help
show_help() {
    head -25 "$0" | tail -20
    exit 0
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --version)
                VERSION="$2"
                shift 2
                ;;
            --output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --include-models)
                INCLUDE_MODELS=true
                shift
                ;;
            --model)
                MODEL_NAME="$2"
                shift 2
                ;;
            --registry)
                SOURCE_REGISTRY="$2"
                shift 2
                ;;
            --sign)
                SIGN_BUNDLE=true
                shift
                ;;
            --fips)
                FIPS_MODE=true
                shift
                ;;
            --help)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                ;;
        esac
    done
}

# Get version from Chart.yaml if not specified
get_version() {
    if [[ -z "${VERSION}" ]]; then
        if [[ -f "${HELM_CHART_DIR}/Chart.yaml" ]]; then
            VERSION=$(grep '^appVersion:' "${HELM_CHART_DIR}/Chart.yaml" | awk '{print $2}' | tr -d '"')
        else
            VERSION="1.0.0"
        fi
    fi
    log_info "Bundle version: ${VERSION}"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    # Required tools
    for cmd in docker tar gzip sha256sum helm; do
        if ! command -v "$cmd" &> /dev/null; then
            # Try podman as docker alternative
            if [[ "$cmd" == "docker" ]] && command -v podman &> /dev/null; then
                log_info "Using podman as container runtime"
                CONTAINER_CMD="podman"
            else
                missing+=("$cmd")
            fi
        fi
    done

    CONTAINER_CMD="${CONTAINER_CMD:-docker}"

    # Optional tools
    if [[ "${SIGN_BUNDLE}" == true ]] && ! command -v cosign &> /dev/null; then
        log_warn "cosign not found - bundle will not be signed"
        SIGN_BUNDLE=false
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    # Check Helm chart exists
    if [[ ! -d "${HELM_CHART_DIR}" ]]; then
        log_error "Helm chart not found at ${HELM_CHART_DIR}"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Create bundle directory structure
create_bundle_structure() {
    log_info "Creating bundle structure..."

    TEMP_DIR=$(mktemp -d)
    BUNDLE_DIR="${TEMP_DIR}/aura-airgap-${VERSION}"

    mkdir -p "${BUNDLE_DIR}"/{images,charts,models,certs/templates,scripts,docs}

    log_success "Bundle structure created at ${BUNDLE_DIR}"
}

# Pull and save container images
save_container_images() {
    log_info "Saving container images..."

    local images_dir="${BUNDLE_DIR}/images"
    local image_list="${images_dir}/images.txt"

    # Pull and save Aura images
    for image in "${!AURA_IMAGES[@]}"; do
        local tag="${AURA_IMAGES[$image]}"
        local full_image="${SOURCE_REGISTRY}/${image}:${tag}"
        local output_file="${images_dir}/${image}-${tag}.tar.gz"

        log_info "Pulling ${full_image}..."
        if ${CONTAINER_CMD} pull "${full_image}" 2>/dev/null; then
            ${CONTAINER_CMD} save "${full_image}" | gzip > "${output_file}"
            echo "${full_image}" >> "${image_list}"
            log_success "Saved ${image}"
        else
            log_warn "Failed to pull ${full_image} - skipping"
        fi
    done

    # Pull and save third-party images
    for name in "${!THIRD_PARTY_IMAGES[@]}"; do
        local full_image="${THIRD_PARTY_IMAGES[$name]}"

        # Use FIPS variants if enabled
        if [[ "${FIPS_MODE}" == true && -n "${FIPS_IMAGES[$name]:-}" ]]; then
            full_image="${FIPS_IMAGES[$name]}"
            log_info "Using FIPS variant for ${name}"
        fi

        local image_tag=$(echo "${full_image}" | sed 's/.*://')
        local output_file="${images_dir}/${name}-${image_tag}.tar.gz"

        log_info "Pulling ${full_image}..."
        if ${CONTAINER_CMD} pull "${full_image}" 2>/dev/null; then
            ${CONTAINER_CMD} save "${full_image}" | gzip > "${output_file}"
            echo "${full_image}" >> "${image_list}"
            log_success "Saved ${name}"
        else
            log_warn "Failed to pull ${full_image} - skipping"
        fi
    done

    log_success "Container images saved"
}

# Package Helm chart
package_helm_chart() {
    log_info "Packaging Helm chart..."

    local charts_dir="${BUNDLE_DIR}/charts"

    # Update dependencies
    helm dependency update "${HELM_CHART_DIR}" 2>/dev/null || true

    # Package chart
    helm package "${HELM_CHART_DIR}" --version "${VERSION}" --destination "${charts_dir}"

    log_success "Helm chart packaged"
}

# Download and package model weights
package_model_weights() {
    if [[ "${INCLUDE_MODELS}" != true ]]; then
        log_info "Skipping model weights (use --include-models to include)"
        return
    fi

    log_info "Packaging model weights for ${MODEL_NAME}..."

    local models_dir="${BUNDLE_DIR}/models"
    local model_dir="${models_dir}/${MODEL_NAME}"

    mkdir -p "${model_dir}"

    # Check if model URL is configured
    if [[ -z "${MODEL_CONFIGS[$MODEL_NAME]:-}" ]]; then
        log_error "Unknown model: ${MODEL_NAME}"
        log_info "Available models: ${!MODEL_CONFIGS[*]}"
        exit 1
    fi

    local model_url="${MODEL_CONFIGS[$MODEL_NAME]}"

    # Check for huggingface-cli
    if command -v huggingface-cli &> /dev/null; then
        log_info "Downloading model from Hugging Face..."
        huggingface-cli download "${MODEL_NAME}" --local-dir "${model_dir}" \
            --include "*.safetensors" "*.json" "tokenizer*" || {
            log_warn "Model download failed - creating placeholder"
            echo "# Download model manually from: ${model_url}" > "${model_dir}/README.md"
        }
    else
        log_warn "huggingface-cli not found - creating placeholder"
        cat > "${model_dir}/README.md" << EOF
# ${MODEL_NAME}

Download this model manually from:
${model_url}

Required files:
- model.safetensors (or model-*.safetensors for sharded models)
- config.json
- tokenizer.json
- tokenizer_config.json
EOF
    fi

    # Create checksums for model files
    if [[ -d "${model_dir}" ]]; then
        (cd "${model_dir}" && find . -type f -name "*.safetensors" -o -name "*.json" | \
            xargs sha256sum 2>/dev/null > ../SHA256SUMS.models || true)
    fi

    log_success "Model weights packaged"
}

# Create installation scripts
create_install_scripts() {
    log_info "Creating installation scripts..."

    local scripts_dir="${BUNDLE_DIR}/scripts"

    # Load images script
    cat > "${scripts_dir}/load-images.sh" << 'SCRIPT'
#!/usr/bin/env bash
# Load container images from air-gap bundle into local registry
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="${SCRIPT_DIR}/../images"
REGISTRY="${1:-}"

if [[ -z "${REGISTRY}" ]]; then
    echo "Usage: $0 <target-registry>"
    echo "Example: $0 registry.local:5000/aura"
    exit 1
fi

# Detect container runtime
if command -v podman &> /dev/null; then
    CMD="podman"
elif command -v docker &> /dev/null; then
    CMD="docker"
else
    echo "Error: No container runtime found (docker or podman required)"
    exit 1
fi

echo "Loading images into ${REGISTRY}..."

for image_file in "${IMAGES_DIR}"/*.tar.gz; do
    [[ -e "${image_file}" ]] || continue

    echo "Loading $(basename "${image_file}")..."

    # Load image
    loaded=$($CMD load -i "${image_file}" 2>&1 | grep -oP 'Loaded image: \K.*' || \
             $CMD load -i "${image_file}" 2>&1 | grep -oP 'Loaded image\(s\): \K.*')

    if [[ -n "${loaded}" ]]; then
        # Tag for target registry
        image_name=$(basename "${image_file}" .tar.gz | sed 's/-[0-9.]*$//')
        $CMD tag "${loaded}" "${REGISTRY}/${image_name}:latest"
        $CMD push "${REGISTRY}/${image_name}:latest"
        echo "  -> Pushed to ${REGISTRY}/${image_name}:latest"
    fi
done

echo "All images loaded successfully!"
SCRIPT
    chmod +x "${scripts_dir}/load-images.sh"

    # Verify checksums script
    cat > "${scripts_dir}/verify-checksums.sh" << 'SCRIPT'
#!/usr/bin/env bash
# Verify SHA256 checksums of bundle contents
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="${SCRIPT_DIR}/.."

echo "Verifying bundle checksums..."

cd "${BUNDLE_DIR}"

if [[ -f "SHA256SUMS" ]]; then
    if sha256sum -c SHA256SUMS; then
        echo "All checksums verified!"
        exit 0
    else
        echo "Checksum verification FAILED!"
        exit 1
    fi
else
    echo "Warning: No SHA256SUMS file found"
    exit 1
fi
SCRIPT
    chmod +x "${scripts_dir}/verify-checksums.sh"

    # Main install script
    cat > "${scripts_dir}/install.sh" << 'SCRIPT'
#!/usr/bin/env bash
# Project Aura - Air-Gap Installation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="${SCRIPT_DIR}/.."

echo "==================================="
echo "  Project Aura Air-Gap Installer"
echo "==================================="
echo ""

# Parse arguments
NAMESPACE="${1:-aura}"
REGISTRY="${2:-}"
VALUES_FILE="${3:-}"

if [[ -z "${REGISTRY}" ]]; then
    echo "Usage: $0 <namespace> <registry> [values-file]"
    echo ""
    echo "Arguments:"
    echo "  namespace     Kubernetes namespace (default: aura)"
    echo "  registry      Target container registry (required)"
    echo "  values-file   Optional Helm values file"
    echo ""
    echo "Example:"
    echo "  $0 aura registry.local:5000/aura values-custom.yaml"
    exit 1
fi

# Step 1: Verify checksums
echo ""
echo "Step 1/4: Verifying bundle integrity..."
"${SCRIPT_DIR}/verify-checksums.sh"

# Step 2: Load images
echo ""
echo "Step 2/4: Loading container images..."
"${SCRIPT_DIR}/load-images.sh" "${REGISTRY}"

# Step 3: Create namespace
echo ""
echo "Step 3/4: Creating Kubernetes namespace..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Step 4: Install Helm chart
echo ""
echo "Step 4/4: Installing Helm chart..."
CHART_FILE=$(find "${BUNDLE_DIR}/charts" -name "aura-*.tgz" | head -1)

if [[ -z "${CHART_FILE}" ]]; then
    echo "Error: Helm chart not found in bundle"
    exit 1
fi

HELM_ARGS=(
    install aura "${CHART_FILE}"
    --namespace "${NAMESPACE}"
    --set global.deploymentMode=air_gapped
    --set global.imageRegistry="${REGISTRY}"
)

if [[ -n "${VALUES_FILE}" && -f "${VALUES_FILE}" ]]; then
    HELM_ARGS+=(-f "${VALUES_FILE}")
elif [[ -f "${BUNDLE_DIR}/../values-air-gapped.yaml" ]]; then
    HELM_ARGS+=(-f "${BUNDLE_DIR}/../values-air-gapped.yaml")
fi

helm "${HELM_ARGS[@]}"

echo ""
echo "==================================="
echo "  Installation Complete!"
echo "==================================="
echo ""
echo "To check the status:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo ""
echo "To access the UI (after pods are ready):"
echo "  kubectl port-forward svc/aura-frontend 8080:80 -n ${NAMESPACE}"
echo "  Open http://localhost:8080"
SCRIPT
    chmod +x "${scripts_dir}/install.sh"

    log_success "Installation scripts created"
}

# Create documentation
create_documentation() {
    log_info "Creating documentation..."

    local docs_dir="${BUNDLE_DIR}/docs"

    # Installation guide
    cat > "${docs_dir}/INSTALL.md" << 'EOF'
# Project Aura - Air-Gap Installation Guide

## Prerequisites

- Kubernetes cluster v1.25+
- Container registry accessible from cluster
- `kubectl` configured to access cluster
- `helm` v3.12+
- Container runtime (Docker or Podman)

## Quick Start

1. **Extract the bundle:**
   ```bash
   tar -xzf aura-airgap-*.tar.gz
   cd aura-airgap-*
   ```

2. **Verify integrity:**
   ```bash
   ./scripts/verify-checksums.sh
   ```

3. **Load images to your registry:**
   ```bash
   ./scripts/load-images.sh registry.local:5000/aura
   ```

4. **Install:**
   ```bash
   ./scripts/install.sh aura registry.local:5000/aura
   ```

## Custom Configuration

Create a values file for your environment:

```yaml
# custom-values.yaml
global:
  deploymentMode: air_gapped
  imageRegistry: registry.local:5000/aura

license:
  key: "YOUR_LICENSE_KEY"
  offlineValidation: true

llm:
  provider: vllm
  vllm:
    model: /models/mistral-7b-instruct-v0.3
```

Install with custom values:
```bash
helm install aura ./charts/aura-*.tgz -n aura -f custom-values.yaml
```

## LLM Model Setup

If you included models in the bundle:

1. Copy model files to a PersistentVolume or NFS share
2. Update the Helm values to point to the model path
3. Ensure the vLLM pods can access the model files

## Security Notes

- All images are verified against SHA256 checksums
- Network policies block all external egress by default
- TLS is enabled by default for all services
- Use `offlineValidation: true` for license validation

## Troubleshooting

See TROUBLESHOOTING.md for common issues and solutions.
EOF

    # Upgrade guide
    cat > "${docs_dir}/UPGRADE.md" << 'EOF'
# Project Aura - Air-Gap Upgrade Guide

## Before You Begin

1. Back up your data (see backup procedures in main documentation)
2. Download the new air-gap bundle
3. Review the release notes for breaking changes

## Upgrade Steps

1. **Extract new bundle:**
   ```bash
   tar -xzf aura-airgap-NEW_VERSION.tar.gz
   cd aura-airgap-NEW_VERSION
   ```

2. **Verify new bundle:**
   ```bash
   ./scripts/verify-checksums.sh
   ```

3. **Load new images:**
   ```bash
   ./scripts/load-images.sh registry.local:5000/aura
   ```

4. **Upgrade Helm release:**
   ```bash
   CHART_FILE=$(ls charts/aura-*.tgz)
   helm upgrade aura "${CHART_FILE}" -n aura \
     --set global.deploymentMode=air_gapped \
     --set global.imageRegistry=registry.local:5000/aura \
     -f your-values.yaml
   ```

5. **Verify upgrade:**
   ```bash
   kubectl get pods -n aura
   helm status aura -n aura
   ```

## Rollback

If the upgrade fails:
```bash
helm rollback aura -n aura
```

## Database Migrations

Database migrations run automatically during upgrade.
Check the orchestrator logs for migration status:
```bash
kubectl logs -l app.kubernetes.io/component=orchestrator -n aura
```
EOF

    # Troubleshooting guide
    cat > "${docs_dir}/TROUBLESHOOTING.md" << 'EOF'
# Project Aura - Air-Gap Troubleshooting

## Common Issues

### Images fail to load

**Symptom:** `load-images.sh` fails with permission errors

**Solution:**
```bash
# Ensure container runtime is running
systemctl status docker  # or podman

# Check registry connectivity
curl -k https://registry.local:5000/v2/_catalog
```

### Pods stuck in ImagePullBackOff

**Symptom:** Pods can't pull images from private registry

**Solution:**
1. Create registry secret:
   ```bash
   kubectl create secret docker-registry regcred \
     --docker-server=registry.local:5000 \
     --docker-username=admin \
     --docker-password=password \
     -n aura
   ```

2. Update Helm values:
   ```yaml
   global:
     imagePullSecrets:
       - name: regcred
   ```

### License validation fails

**Symptom:** API returns "License invalid" error

**Solution:**
1. Verify license key is correctly set
2. Ensure `offlineValidation: true` in values
3. Check hardware fingerprint matches license

### Network connectivity issues

**Symptom:** Services can't communicate

**Solution:**
1. Check NetworkPolicy is not blocking internal traffic
2. Verify service DNS resolution:
   ```bash
   kubectl run test --rm -it --image=busybox -- nslookup aura-api
   ```

### LLM inference fails

**Symptom:** vLLM pod crashes or model not found

**Solution:**
1. Verify model files are accessible:
   ```bash
   kubectl exec -it deploy/aura-vllm -n aura -- ls -la /models/
   ```

2. Check GPU resources:
   ```bash
   kubectl describe node | grep nvidia
   ```

## Getting Help

For enterprise support, contact support@aenealabs.com with:
- Bundle version
- `helm get values aura -n aura`
- `kubectl describe pods -n aura`
- `kubectl logs -l app.kubernetes.io/name=aura -n aura --tail=100`
EOF

    log_success "Documentation created"
}

# Generate checksums
generate_checksums() {
    log_info "Generating checksums..."

    cd "${BUNDLE_DIR}"

    # Generate checksums for all files
    find . -type f \( -name "*.tar.gz" -o -name "*.tgz" -o -name "*.sh" \) -print0 | \
        xargs -0 sha256sum > SHA256SUMS

    # Add VERSION file
    echo "${VERSION}" > VERSION

    log_success "Checksums generated"
}

# Sign bundle with cosign
sign_bundle() {
    if [[ "${SIGN_BUNDLE}" != true ]]; then
        return
    fi

    log_info "Signing bundle with cosign..."

    cd "${BUNDLE_DIR}"

    if cosign sign-blob --yes SHA256SUMS --output-signature SHA256SUMS.sig; then
        log_success "Bundle signed"
    else
        log_warn "Failed to sign bundle - continuing without signature"
    fi
}

# Create final bundle archive
create_bundle_archive() {
    log_info "Creating final bundle archive..."

    mkdir -p "${OUTPUT_DIR}"

    local bundle_name="aura-airgap-${VERSION}"
    local archive_path="${OUTPUT_DIR}/${bundle_name}.tar.gz"

    cd "${TEMP_DIR}"
    tar -czf "${archive_path}" "${bundle_name}"

    # Generate checksum for the archive
    cd "${OUTPUT_DIR}"
    sha256sum "${bundle_name}.tar.gz" > "${bundle_name}.tar.gz.sha256"

    log_success "Bundle created: ${archive_path}"

    # Show bundle contents
    echo ""
    log_info "Bundle contents:"
    tar -tzf "${archive_path}" | head -30
    echo "  ..."

    # Show bundle size
    local size=$(du -h "${archive_path}" | cut -f1)
    log_info "Bundle size: ${size}"
}

# Main function
main() {
    echo ""
    echo "======================================"
    echo "  Project Aura Air-Gap Bundle Creator"
    echo "======================================"
    echo ""

    parse_args "$@"
    get_version
    check_prerequisites
    create_bundle_structure
    save_container_images
    package_helm_chart
    package_model_weights
    create_install_scripts
    create_documentation
    generate_checksums
    sign_bundle
    create_bundle_archive

    echo ""
    log_success "Air-gap bundle creation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Transfer ${OUTPUT_DIR}/aura-airgap-${VERSION}.tar.gz to air-gapped environment"
    echo "  2. Extract: tar -xzf aura-airgap-${VERSION}.tar.gz"
    echo "  3. Run: ./aura-airgap-${VERSION}/scripts/install.sh <namespace> <registry>"
    echo ""
}

main "$@"
