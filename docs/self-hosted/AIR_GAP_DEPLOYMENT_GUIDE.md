# Project Aura - Air-Gap Deployment Guide

This guide covers deploying Project Aura in air-gapped (disconnected) environments for government, defense, and regulated industries.

## Overview

Air-gapped deployments are fully isolated from the internet, suitable for:

- **Government/Defense**: Classified networks, FedRAMP High, CMMC Level 3
- **Healthcare**: HIPAA-compliant environments with PHI
- **Financial Services**: SOX-compliant trading systems
- **Critical Infrastructure**: SCADA/ICS networks

## Prerequisites

### Infrastructure Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Kubernetes | v1.25+ | v1.28+ |
| Container Runtime | Docker 24+ or Podman 4+ | Podman 4+ |
| Private Registry | Any OCI-compliant | Harbor 2.x |
| Storage | 500GB | 2TB |
| Memory | 32GB per node | 64GB per node |
| GPU (for LLM) | NVIDIA T4 | NVIDIA A100 |

### Network Requirements

- Internal DNS (CoreDNS or dnsmasq)
- No external internet access (validated at install)
- Internal CA for TLS certificates

## Creating the Air-Gap Bundle

On an internet-connected system, create the bundle:

```bash
# Clone the repository
git clone https://github.com/aenealabs/aura.git
cd project-aura

# Create bundle with models (large download)
./deploy/airgap/scripts/create-airgap-bundle.sh \
  --version 1.3.0 \
  --include-models \
  --model mistral-7b-instruct-v0.3 \
  --sign

# Or create bundle without models (smaller)
./deploy/airgap/scripts/create-airgap-bundle.sh --version 1.3.0
```

### Bundle Contents

```
aura-airgap-1.3.0.tar.gz
├── images/           # Container images (tar.gz)
├── charts/           # Helm chart package
├── models/           # LLM model weights (optional)
├── scripts/          # Installation scripts
├── docs/             # Offline documentation
├── SHA256SUMS        # File checksums
└── SHA256SUMS.sig    # Cosign signature (if --sign)
```

## Installation Steps

### Step 1: Transfer Bundle

Transfer the bundle to the air-gapped environment using approved methods:

- Physical media (DVD, USB) with chain-of-custody
- Cross-domain solution (CDS)
- Data diode

### Step 2: Verify Bundle Integrity

```bash
# Extract bundle
tar -xzf aura-airgap-1.3.0.tar.gz
cd aura-airgap-1.3.0

# Verify checksums
./scripts/verify-checksums.sh

# Verify signature (if signed)
cosign verify-blob --signature SHA256SUMS.sig SHA256SUMS
```

### Step 3: Load Container Images

```bash
# Load images to private registry
./scripts/load-images.sh registry.local:5000/aura

# Verify images loaded
curl -k https://registry.local:5000/v2/_catalog
```

### Step 4: Configure LLM Models

If models were included in the bundle:

```bash
# Copy models to shared storage (NFS or PV)
cp -r models/* /mnt/models/

# Verify model checksums
sha256sum -c models/SHA256SUMS
```

### Step 5: Create Custom Values

Create a values file for your environment:

```yaml
# values-airgap-custom.yaml
global:
  deploymentMode: air_gapped
  edition: enterprise_plus
  imageRegistry: registry.local:5000/aura
  imagePullSecrets:
    - name: registry-credentials

  tls:
    enabled: true
    certManager:
      enabled: false
    existingSecret: aura-tls-cert

license:
  key: "YOUR_OFFLINE_LICENSE_KEY"
  offlineValidation: true

llm:
  provider: vllm
  vllm:
    enabled: true
    model: /models/mistral-7b-instruct-v0.3
    resources:
      requests:
        nvidia.com/gpu: 1
      limits:
        nvidia.com/gpu: 1

databases:
  graph:
    neo4j:
      enabled: true
      edition: enterprise
  vector:
    opensearch:
      enabled: true
      tls:
        enabled: true

networkPolicy:
  enabled: true
  defaultDeny: true

# Block all external egress
airGap:
  enabled: true
  validateEgress: true
```

### Step 6: Install

```bash
# Create namespace
kubectl create namespace aura

# Create registry secret
kubectl create secret docker-registry registry-credentials \
  --docker-server=registry.local:5000 \
  --docker-username=admin \
  --docker-password="${REGISTRY_PASSWORD}" \
  -n aura

# Create TLS secret from your CA
kubectl create secret tls aura-tls-cert \
  --cert=/path/to/tls.crt \
  --key=/path/to/tls.key \
  -n aura

# Install with Helm
helm install aura ./charts/aura-1.3.0.tgz \
  --namespace aura \
  -f values-airgap-custom.yaml
```

## Offline License Activation

Air-gapped deployments require offline license validation:

### Step 1: Generate License Request

```bash
# Run on the air-gapped system
kubectl exec -it deploy/aura-api -n aura -- \
  python -m src.services.licensing.offline_validator generate_request > license-request.json
```

### Step 2: Process License Request

Transfer `license-request.json` to an internet-connected system and submit to:

- **Portal**: https://aenealabs.com/license-portal
- **Email**: licensing@aenealabs.com

### Step 3: Install License

Transfer the license key file back to the air-gapped environment:

```bash
# Update the license secret
kubectl create secret generic aura-license \
  --from-literal=license-key="${LICENSE_KEY}" \
  -n aura --dry-run=client -o yaml | kubectl apply -f -

# Restart API to pick up new license
kubectl rollout restart deploy/aura-api -n aura
```

## FIPS 140-2 Compliance

For FIPS-compliant deployments:

### Enable FIPS Mode

```yaml
# values-fips.yaml
global:
  fips:
    enabled: true

# Use RHEL UBI images with FIPS-enabled OpenSSL
api:
  image:
    repository: registry.local:5000/aura/aura-api-fips
```

### Verify FIPS Mode

```bash
# Check FIPS status
kubectl exec -it deploy/aura-api -n aura -- \
  python -c "from src.services.licensing.fips_compliance import get_fips_crypto; print(get_fips_crypto().get_status())"
```

## Network Isolation Validation

Aura validates network isolation at startup:

```bash
# Check egress validation status
kubectl logs deploy/aura-api -n aura | grep -i egress

# Manual validation
kubectl exec -it deploy/aura-api -n aura -- \
  python -c "from src.services.airgap.egress_validator import validate_air_gap_mode; print(validate_air_gap_mode().to_dict())"
```

### Expected Output (Compliant)

```json
{
  "is_air_gapped": true,
  "is_compliant": true,
  "tests_passed": 14,
  "tests_failed": 0,
  "violations": []
}
```

## Model Weight Verification

Verify LLM model integrity:

```bash
# Verify model checksums
kubectl exec -it deploy/aura-vllm -n aura -- \
  python -c "from src.services.airgap.model_verifier import verify_model_checksums; print(verify_model_checksums('mistral-7b-instruct-v0.3').to_dict())"
```

## Inference Audit Logging

Air-gapped deployments include comprehensive audit logging:

### Log Location

```bash
# Audit logs are stored at:
/var/log/aura/audit/inference_audit.jsonl

# View recent audit events
kubectl exec -it deploy/aura-api -n aura -- tail -100 /var/log/aura/audit/inference_audit.jsonl
```

### Log Format

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "inference_request",
  "timestamp": "2026-01-03T12:00:00Z",
  "user_id": "user-123",
  "model_name": "mistral-7b",
  "prompt_hash": "a1b2c3d4...",
  "prompt_length": 150,
  "input_tokens": 45,
  "output_tokens": 120
}
```

### SIEM Integration

Export logs to your SIEM:

```yaml
# Configure syslog export
inference_audit:
  syslog:
    enabled: true
    address: "syslog.internal:514"
    facility: LOCAL0
```

## Upgrading

### Step 1: Download New Bundle

On internet-connected system:

```bash
./deploy/airgap/scripts/create-airgap-bundle.sh --version 1.4.0
```

### Step 2: Transfer and Verify

```bash
tar -xzf aura-airgap-1.4.0.tar.gz
cd aura-airgap-1.4.0
./scripts/verify-checksums.sh
```

### Step 3: Load New Images

```bash
./scripts/load-images.sh registry.local:5000/aura
```

### Step 4: Upgrade Helm Release

```bash
helm upgrade aura ./charts/aura-1.4.0.tgz \
  --namespace aura \
  -f values-airgap-custom.yaml
```

## Troubleshooting

### Images Won't Pull

```bash
# Check image exists in registry
curl -k https://registry.local:5000/v2/aura/aura-api/tags/list

# Verify imagePullSecrets
kubectl get secret registry-credentials -n aura -o yaml
```

### License Validation Fails

```bash
# Check license status
kubectl exec -it deploy/aura-api -n aura -- \
  python -c "from src.services.licensing import get_license_service; print(get_license_service().get_status())"

# Verify hardware fingerprint matches
kubectl exec -it deploy/aura-api -n aura -- \
  python -c "from src.services.licensing.hardware_fingerprint import get_fingerprint_details; print(get_fingerprint_details())"
```

### Egress Violations Detected

```bash
# List violations
kubectl logs deploy/aura-api -n aura | grep "violation"

# Check NetworkPolicy
kubectl get networkpolicy -n aura -o yaml
```

### LLM Not Responding

```bash
# Check vLLM status
kubectl logs deploy/aura-vllm -n aura

# Verify GPU allocation
kubectl describe pod -l app.kubernetes.io/component=vllm -n aura | grep nvidia
```

## Security Considerations

1. **Chain of Custody**: Maintain audit trail for all media transfers
2. **Checksum Verification**: Always verify SHA256SUMS before installation
3. **License Security**: Treat offline license keys as secrets
4. **Model Provenance**: Verify model checksums match official releases
5. **Network Isolation**: Run egress validation regularly
6. **Audit Logs**: Forward to SIEM and retain per compliance requirements

## Support

For air-gapped deployment support:

- **Enterprise Support Portal**: https://support.aenealabs.com (from connected system)
- **Email**: airgap-support@aenealabs.com
- **Phone**: +1-888-AURA-SEC (for P1 issues)

Include with support requests:

- Bundle version
- `helm get values aura -n aura`
- `kubectl describe pods -n aura`
- Egress validation results
- License validation status
