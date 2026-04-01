# Diagram Service Configuration Guide

## Overview

The Project Aura Diagram Generation Service produces architecture diagrams, data flow visualizations, and technical documentation. The service supports two operational modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Mock Mode** | Uses pre-generated mock data for fast responses | Development, testing, demos |
| **Real API Mode** | Uses AI providers (Bedrock, OpenAI, Vertex) for professional output | QA, staging, production |

Real API mode produces **professional-quality diagrams** with:
- Official AWS, Azure, and GCP cloud provider icons
- AI-powered natural language diagram generation
- Intelligent layout via ELK.js constraint-based engine
- Multi-provider routing with automatic failover

---

## Environment Variables

### DOCUMENTATION_USE_MOCK

Controls whether the documentation service uses mock data or real AI APIs.

| Value | Behavior |
|-------|----------|
| `true` | Force mock mode regardless of environment |
| `false` | Force real API mode regardless of environment |
| *(not set)* | Auto-detect based on `AURA_ENVIRONMENT` |

**Example:**
```bash
# Force real API mode in any environment
export DOCUMENTATION_USE_MOCK=false

# Force mock mode (useful for local development)
export DOCUMENTATION_USE_MOCK=true
```

### AURA_ENVIRONMENT

Specifies the deployment environment. Used for auto-detection when `DOCUMENTATION_USE_MOCK` is not explicitly set.

| Value | Default Mock Behavior | Reason |
|-------|----------------------|--------|
| `dev` | `use_mock=true` | Faster iteration, no API costs |
| `qa` | `use_mock=false` | Test real diagram quality |
| `prod` | `use_mock=false` | Production-quality output |

**Example:**
```bash
export AURA_ENVIRONMENT=qa  # Will use real APIs by default
```

---

## Environment-Specific Defaults

### Development Environment

**Default:** Mock mode enabled

```
AURA_ENVIRONMENT=dev
DOCUMENTATION_USE_MOCK=(not set) → resolves to true
```

**Rationale:**
- Faster feedback loop during development
- No API costs for iterative testing
- No dependency on external services being available
- Diagrams use basic shapes (sufficient for UI/UX development)

**To test real diagrams in dev:**
```bash
export DOCUMENTATION_USE_MOCK=false
```

### QA Environment

**Default:** Real API mode enabled

```
AURA_ENVIRONMENT=qa
DOCUMENTATION_USE_MOCK=(not set) → resolves to false
```

**Rationale:**
- QA should validate actual diagram quality
- Tests the full AI generation pipeline
- Verifies cloud provider icons render correctly
- Ensures layout engine produces professional output

### Production Environment

**Default:** Real API mode enabled

```
AURA_ENVIRONMENT=prod
DOCUMENTATION_USE_MOCK=(not set) → resolves to false
```

**Rationale:**
- Customers expect professional-quality diagrams
- Official cloud provider icons required
- AI-powered generation for accurate representations

---

## Mock Mode vs Real API Mode

### Visual Comparison

| Aspect | Mock Mode | Real API Mode |
|--------|-----------|---------------|
| **Icons** | Generic shapes (rectangles, cylinders) | Official AWS/Azure/GCP icons |
| **Layout** | Basic hierarchical | ELK.js constraint-based (professional) |
| **Generation** | Template-based | AI natural language processing |
| **Response Time** | ~50ms | ~2-5 seconds |
| **API Cost** | $0 | Varies by provider |
| **Accuracy** | Static mock data | Context-aware from codebase |

### When to Use Each Mode

**Use Mock Mode when:**
- Developing UI components that display diagrams
- Running unit tests that don't need real content
- Demonstrating the application without API credentials
- Iterating quickly on layout/styling changes
- Running in CI/CD pipelines for basic smoke tests

**Use Real API Mode when:**
- Testing diagram quality before release
- Validating AI generation accuracy
- Performing QA on the full pipeline
- Running in staging/production environments
- Generating documentation for customers

---

## AI Provider Configuration

When running in Real API mode, the service routes requests to AI providers based on task type and data classification.

### Provider Hierarchy

| Task | Primary Provider | Fallback |
|------|-----------------|----------|
| DSL Generation | AWS Bedrock (Claude 3.5 Sonnet) | OpenAI GPT-4-turbo |
| Intent Extraction | AWS Bedrock (Claude 3.5 Sonnet) | OpenAI GPT-4-turbo |
| Image Understanding | Google Vertex (Gemini 1.5 Pro Vision) | OpenAI GPT-4 Vision |
| Creative Generation | OpenAI DALL-E 3 | Google Vertex Imagen |

### Data Classification Enforcement

For compliance (FedRAMP, CMMC), data classification affects provider routing:

| Classification | Allowed Providers |
|----------------|-------------------|
| CUI (Controlled Unclassified) | AWS Bedrock only |
| Internal | All providers |
| Public | All providers |

### Required AWS Permissions

For Bedrock access, the service requires:
```yaml
- bedrock:InvokeModel
- bedrock:InvokeModelWithResponseStream
```

See `deploy/cloudformation/iam-diagram-service.yaml` for the complete IAM policy.

---

## SSM Parameters

The diagram service reads configuration from AWS SSM Parameter Store:

| Parameter | Description | Type |
|-----------|-------------|------|
| `/aura/{env}/diagram-service/openai-api-key` | OpenAI API key | SecureString |
| `/aura/{env}/diagram-service/vertex-credentials` | GCP service account JSON | SecureString |
| `/aura/{env}/diagram-service/allowed-git-hosts` | Allowlisted Git hosts for GovCloud | String |
| `/aura/{env}/diagram-service/daily-budget-usd` | Daily API cost budget | String |
| `/aura/{env}/diagram-service/monthly-budget-usd` | Monthly API cost budget | String |

---

## Troubleshooting

### Diagrams Show Basic Shapes Instead of Cloud Icons

**Symptom:** Generated diagrams display generic rectangles instead of AWS/Azure/GCP icons.

**Cause:** Service is running in mock mode.

**Solution:**
1. Check environment: `echo $AURA_ENVIRONMENT`
2. If in dev, explicitly enable real APIs: `export DOCUMENTATION_USE_MOCK=false`
3. Verify by checking application logs for: `Documentation service mode: real API`

### API Calls Failing in QA/Prod

**Symptom:** Diagram generation returns errors about API connectivity.

**Possible Causes:**
1. Missing IAM permissions for Bedrock
2. SSM parameters not configured
3. VPC endpoints not available

**Solution:**
1. Verify IAM role has Bedrock permissions
2. Check SSM parameters exist: `aws ssm get-parameters-by-path --path /aura/qa/diagram-service/`
3. Verify VPC endpoint for Bedrock is deployed

### Slow Response Times

**Symptom:** Diagram generation takes 10+ seconds.

**Possible Causes:**
1. First request initializes model connections
2. Complex diagrams with many nodes
3. Provider rate limiting

**Solution:**
1. First request is expected to be slower (cold start)
2. Use `max_services` parameter to limit complexity
3. Check CloudWatch for rate limit errors

---

## Related Documentation

- [ADR-056: Documentation Agent](../architecture-decisions/ADR-056-documentation-agent.md) - Original architecture
- [ADR-060: Enterprise Diagram Generation](../architecture-decisions/ADR-060-enterprise-diagram-generation.md) - Professional diagram features
- [Icon Library Reference](../reference/ICON_LIBRARY_REFERENCE.md) - Available cloud provider icons
- [API Reference: Documentation Endpoints](../reference/API_DOCUMENTATION_ENDPOINTS.md) - REST API documentation

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-01-18 | Initial documentation - made use_mock configurable | Project Aura Team |
