# E2E Testing Runbook

This document provides operational procedures for running end-to-end integration tests against real AWS services in Project Aura.

## Overview

E2E tests validate real AWS service integrations:

| Service | Test Coverage | Connectivity Required |
|---------|---------------|----------------------|
| **Neptune Graph** | Entity CRUD, relationships, traversals | VPC (private subnet) |
| **OpenSearch Vector** | Vector indexing, semantic search | VPC (private subnet) |
| **Bedrock LLM** | Text generation, code analysis | Public AWS API |
| **Full Pipeline** | Ingest → Query → Generate | VPC + Public |

**Test File:** `tests/test_aws_services_e2e.py` (15 tests)

---

## Quick Reference

### Run E2E Tests

```bash
# All E2E tests (requires VPC connectivity for Neptune/OpenSearch)
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py -v

# Bedrock tests only (works from anywhere with AWS credentials)
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py::TestBedrockLLME2E -v

# Skip coverage check (faster for debugging)
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py -v --no-cov
```

### Check Test Status

```bash
# Collect tests without running (verify test discovery)
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py --collect-only

# Run with verbose skip reasons
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py -v -rs
```

---

## Environment Options

### Option 1: From EKS Pod (Recommended)

Run tests from within the EKS cluster where pods have VPC connectivity and IAM via IRSA.

**Prerequisites:**
- kubectl configured with cluster access
- Service account with IRSA permissions for Neptune, OpenSearch, Bedrock

**Procedure:**

```bash
# 1. Create a debug pod with test dependencies
kubectl run e2e-test-runner \
  --image=python:3.12-slim \
  --restart=Never \
  --serviceaccount=aura-api-sa \
  -it --rm -- bash

# 2. Inside the pod, install dependencies
pip install pytest boto3 gremlinpython opensearch-py

# 3. Clone repo or copy test files
# (In production, use a pre-built test image)

# 4. Run E2E tests
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py -v
```

**Alternative: Use existing API pod:**

```bash
# 1. Find API pod
kubectl get pods -l app=aura-api

# 2. Exec into pod
kubectl exec -it <pod-name> -- bash

# 3. Run tests (if pytest installed)
RUN_AWS_E2E_TESTS=1 python -m pytest tests/test_aws_services_e2e.py -v
```

**Why this works:**
- EKS pods are in VPC private subnets
- Can reach Neptune/OpenSearch endpoints directly
- IAM authentication via IRSA (IAM Roles for Service Accounts)
- No VPN or bastion required

---

### Option 2: Via AWS CodeBuild (CI/CD)

Run tests as part of the CI/CD pipeline with VPC access configured.

**Prerequisites:**
- CodeBuild project with VPC configuration
- IAM role with Neptune, OpenSearch, Bedrock permissions

**Procedure:**

1. **Add E2E test stage to buildspec:**

```yaml
# deploy/buildspecs/buildspec-e2e-tests.yml
version: 0.2

env:
  variables:
    RUN_AWS_E2E_TESTS: "1"

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - pip install -r requirements.txt
      - pip install pytest

  build:
    commands:
      - echo "Running E2E integration tests..."
      - pytest tests/test_aws_services_e2e.py -v --tb=short --no-cov

reports:
  e2e-test-reports:
    files:
      - "test-results.xml"
    file-format: JUNITXML
```

2. **Trigger manually or via pipeline:**

```bash
# Start E2E test build
aws codebuild start-build --project-name aura-e2e-tests-dev

# Monitor build
aws codebuild batch-get-builds --ids <build-id> \
  --query 'builds[0].{status:buildStatus,phase:currentPhase}'
```

**Why this works:**
- CodeBuild runs in VPC with private subnet access
- IAM role provides Neptune/OpenSearch/Bedrock permissions
- Isolated from local machine networking issues

---

### Option 3: Via VPN (Local Development)

Connect your local machine to the VPC to reach private endpoints.

**Prerequisites:**
- AWS Client VPN or similar VPN solution configured
- VPN endpoint with routes to private subnets
- AWS credentials configured locally

**Procedure:**

1. **Connect to VPN:**

```bash
# Using AWS Client VPN (example)
# Download client configuration from AWS Console
# Import into VPN client and connect

# Verify connectivity to Neptune
nc -zv aura-neptune-dev.cluster-EXAMPLE.us-east-1.neptune.amazonaws.com 8182

# Verify connectivity to OpenSearch
nc -zv vpc-aura-dev-EXAMPLE.us-east-1.es.amazonaws.com 443
```

2. **Set AWS credentials:**

```bash
# Using SSO
aws sso login --profile aura-admin
export AWS_PROFILE=aura-admin

# Verify identity
aws sts get-caller-identity
```

3. **Run tests:**

```bash
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py -v
```

**Why this works:**
- VPN routes traffic through VPC
- Local machine appears to be "inside" the VPC
- AWS credentials provide IAM authentication

**Note:** VPN setup is outside the scope of this runbook. Consult your network administrator for VPN configuration.

---

### Option 4: Bedrock Only (No VPC Required)

Run Bedrock tests from anywhere with AWS credentials. Useful for validating LLM integration without VPC access.

**Prerequisites:**
- AWS credentials with Bedrock permissions
- No VPC connectivity required

**Procedure:**

```bash
# 1. Set AWS credentials
export AWS_PROFILE=aura-admin
# or
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1

# 2. Verify Bedrock access
aws bedrock list-foundation-models --query 'modelSummaries[0].modelId'

# 3. Run Bedrock tests only
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py::TestBedrockLLME2E -v --no-cov
```

**Expected Output:**

```
tests/test_aws_services_e2e.py::TestBedrockLLME2E::test_connection_health PASSED
tests/test_aws_services_e2e.py::TestBedrockLLME2E::test_simple_generation PASSED
tests/test_aws_services_e2e.py::TestBedrockLLME2E::test_code_analysis PASSED
tests/test_aws_services_e2e.py::TestBedrockLLME2E::test_cost_tracking PASSED
```

**Why this works:**
- Bedrock is a public AWS API (not VPC-bound)
- Only requires IAM credentials, not network access to VPC

---

## Service Endpoints

| Service | Endpoint | Port | Auth |
|---------|----------|------|------|
| Neptune | `aura-neptune-dev.cluster-EXAMPLE.us-east-1.neptune.amazonaws.com` | 8182 | IAM |
| OpenSearch | `vpc-aura-dev-EXAMPLE.us-east-1.es.amazonaws.com` | 443 | IAM |
| Bedrock | `bedrock-runtime.us-east-1.amazonaws.com` | 443 | IAM |

**Override endpoints via environment variables:**

```bash
export NEPTUNE_ENDPOINT=custom-neptune.example.com
export OPENSEARCH_ENDPOINT=custom-opensearch.example.com
```

---

## Troubleshooting

### Tests Skip with "VPC connectivity required"

**Symptom:**
```
SKIPPED [1] tests/test_aws_services_e2e.py:175: Neptune not reachable - VPC connectivity required
```

**Cause:** Local machine cannot reach Neptune/OpenSearch in private subnets.

**Solution:** Use Option 1 (EKS pod), Option 2 (CodeBuild), or Option 3 (VPN).

---

### Bedrock Throttling Error

**Symptom:**
```
ThrottlingException: Too many requests, please wait before trying again.
```

**Cause:** Too many Bedrock API calls in rapid succession.

**Solution:** Wait 60 seconds and retry, or reduce test parallelism:

```bash
RUN_AWS_E2E_TESTS=1 pytest tests/test_aws_services_e2e.py::TestBedrockLLME2E -v -x
```

---

### Model Requires Inference Profile

**Symptom:**
```
ValidationException: Invocation of model ID anthropic.claude-sonnet-4-5-20250929-v1:0
with on-demand throughput isn't supported.
```

**Cause:** Newer Claude models require inference profiles for on-demand access.

**Solution:** Use Claude 3.5 Sonnet v1 which supports on-demand:
- Dev config uses: `anthropic.claude-3-5-sonnet-20240620-v1:0`
- See `src/config/bedrock_config.py` for model configuration

---

### IAM Permission Denied

**Symptom:**
```
AccessDeniedException: User is not authorized to perform neptune-db:* on resource
```

**Cause:** IAM role/user lacks required permissions.

**Solution:** Verify IAM permissions include:
- `neptune-db:*` for Neptune
- `es:*` for OpenSearch
- `bedrock:InvokeModel` for Bedrock

---

### Connection Timeout

**Symptom:**
```
socket.timeout: timed out
```

**Cause:** Network cannot reach the endpoint (firewall, routing, security group).

**Solution:**
1. Verify security group allows inbound from your source
2. Check VPC route tables
3. Verify endpoint is in the same region

---

## Cost Estimates

Running E2E tests incurs AWS costs:

| Service | Cost per Test Run | Notes |
|---------|-------------------|-------|
| Neptune | ~$0.10/hour | db.t3.medium instance |
| OpenSearch | ~$0.036/hour | t3.small.search |
| Bedrock | ~$0.01-0.05 | Depends on token usage |

**Estimated cost per full E2E run:** $0.05-0.10

**Cost optimization:**
- Run Bedrock-only tests for quick validation
- Use unit tests (mocked) for development iteration
- Reserve E2E tests for pre-merge validation

---

## Related Documentation

- **Testing Strategy:** `docs/reference/TESTING_STRATEGY.md`
- **Bedrock Configuration:** `src/config/bedrock_config.py`
- **Neptune Service:** `src/services/neptune_graph_service.py`
- **OpenSearch Service:** `src/services/opensearch_vector_service.py`
- **CI/CD Setup:** `docs/deployment/CICD_SETUP_GUIDE.md`
