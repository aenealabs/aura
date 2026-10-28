# Diagram Service Configuration Guide

## Overview

The Project Aura Diagram Generation Service produces architecture diagrams, data flow visualizations, and technical documentation through `POST /api/v1/documentation/generate` (`src/api/documentation_endpoints.py`). The endpoint has two generation modes:

| Generation mode | What it does | Rendering |
|-----------------|--------------|-----------|
| `CODE_ANALYSIS` | Detects service boundaries (Louvain community detection) and builds Mermaid diagrams plus a templated technical report | Mermaid.js in the browser |
| `AI_PROMPT` | Converts a natural-language prompt into Aura diagram DSL with AWS Bedrock Claude models, then lays it out and renders SVG | Built-in SVG renderer (`aura_svg`) or Eraser.io (`eraser_api`, user-supplied key) |

Independently of the generation mode, the service runs in one of two operational modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Mock Mode** | Canned diagram DSL for `AI_PROMPT`, in-memory feedback storage, no CloudWatch calibration metrics | Development, testing, demos |
| **Real API Mode** | Bedrock-backed `AI_PROMPT` generation, DynamoDB feedback storage, CloudWatch calibration metrics | Default in every environment |

Real API mode provides:

- Embedded SVG cloud-provider icons drawn in each provider's palette: 44 of 44 registered AWS icons, 3 of 12 Azure icons, 4 of 10 GCP icons, 4 of 7 Kubernetes icons, and 5 of 5 generic icons have embedded artwork; the remaining 18 registered icons render as a placeholder
- AI-powered natural language diagram generation with an LLM critique-and-refine loop
- Layout by the built-in Python layered/grid layout engine (an ELK.js backend exists in `src/services/diagrams/layout_engine.py` but is not enabled on the API path)
- Bedrock-only model routing with model-tier fallback, per-provider circuit breakers, and a daily cost budget

### Current Limitations

- **`CODE_ANALYSIS` does not yet read the customer's code graph.** The API creates the documentation agent without a Neptune client, so the service boundary detector falls back to a built-in demo graph of the Aura codebase for every `repository_id`. The Neptune edge query in `service_boundary_detector.py` is also a placeholder that returns no edges, and the agent passes no data flows to the diagram and report generators.
- **`AI_PROMPT` does not use codebase context.** Diagrams reflect the prompt only.
- **The web UI repository picker uses a built-in list.** `DocumentationDashboard` falls back to `MOCK_REPOSITORIES` because no repository list is passed to it.
- **Diagram export and Git sync are libraries only.** `diagram_export_service.py` (SVG, PNG, PDF, draw.io) and `diagram_git_sync.py` (GitHub/GitLab commit or pull request) have no API endpoint; the web UI exports diagrams client-side.

---

## Environment Variables

### DOCUMENTATION_USE_MOCK

Controls whether the documentation service uses mock data or real AI APIs.

| Value | Behavior |
|-------|----------|
| `true` | Force mock mode |
| `false` | Force real API mode |
| *(not set)* | Real API mode in every environment |

**Example:**

```bash
# Force mock mode (useful for local development without AWS credentials)
export DOCUMENTATION_USE_MOCK=true

# Real API mode (same as leaving the variable unset)
export DOCUMENTATION_USE_MOCK=false
```

### AURA_ENVIRONMENT

Specifies the deployment environment. It does not change the mock/real default (see `_should_use_mock()` in `src/api/documentation_endpoints.py`); it is logged with the selected mode, passed to the diagram model router, and gates the unauthenticated `POST /api/v1/documentation/diagram-test` endpoint, which is only available when `AURA_ENVIRONMENT` is `dev` or `test` (or unset, which defaults to `dev`).

| Value | Default Mock Behavior |
|-------|----------------------|
| `dev` | `use_mock=false` |
| `qa` | `use_mock=false` |
| `prod` | `use_mock=false` |

**Example:**

```bash
export AURA_ENVIRONMENT=qa
```

---

## Environment-Specific Defaults

### Development Environment

**Default:** Real API mode

```text
AURA_ENVIRONMENT=dev
DOCUMENTATION_USE_MOCK=(not set) → resolves to false
```

**To use mock mode in dev:**

```bash
export DOCUMENTATION_USE_MOCK=true
```

Mock mode is useful when:

- Iterating on UI components without AWS credentials
- Avoiding Bedrock costs during repeated local testing

### QA Environment

**Default:** Real API mode

```text
AURA_ENVIRONMENT=qa
DOCUMENTATION_USE_MOCK=(not set) → resolves to false
```

**Rationale:**

- QA should validate actual diagram quality
- Tests the full AI generation pipeline
- Verifies cloud provider icons render correctly

### Production Environment

**Default:** Real API mode

```text
AURA_ENVIRONMENT=prod
DOCUMENTATION_USE_MOCK=(not set) → resolves to false
```

**Rationale:**

- AI-powered generation from the customer's prompt
- Feedback persisted to DynamoDB for confidence calibration

---

## Mock Mode vs Real API Mode

### Visual Comparison

| Aspect | Mock Mode | Real API Mode |
|--------|-----------|---------------|
| **Icons (`AI_PROMPT`)** | Same embedded icon set and SVG renderer | Same embedded icon set and SVG renderer |
| **Layout** | Built-in Python layout engine | Built-in Python layout engine |
| **`AI_PROMPT` generation** | One of two canned Aura diagrams, chosen by prompt keywords, reported with a fixed 0.94 confidence | Bedrock Claude intent extraction, DSL generation, and critique |
| **`CODE_ANALYSIS` graph** | Built-in Aura demo graph | Built-in Aura demo graph (see Current Limitations) |
| **Feedback storage** | In memory | DynamoDB |
| **Response Time** | Not benchmarked | Not benchmarked; depends on Bedrock latency and critique iterations |
| **API Cost** | $0 | Bedrock usage |

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

When running in Real API mode, `DiagramModelRouter` (`src/services/diagrams/diagram_model_router.py`) routes every LLM task through AWS Bedrock. OpenAI and Vertex AI client modules exist under `src/services/diagrams/providers/`, but the router refuses to create them (Bedrock is the single gateway per ADR-060).

### Provider Hierarchy

Model tiers resolve through `src/config/claude_models.py` (`fast`, `accurate`).

| Task | Primary Model | Fallback |
|------|---------------|----------|
| DSL Generation | Bedrock Claude, `fast` tier | None |
| Intent Extraction | Bedrock Claude, `fast` tier | None |
| Diagram Critique | Bedrock Claude, `accurate` tier | Bedrock Claude, `fast` tier |
| Image Understanding | Bedrock Claude, `accurate` tier | Bedrock Claude, `fast` tier |
| Creative Generation | Not supported | None |
| Layout Optimization | No LLM (layout engine) | None |

Image understanding is implemented in `AIDiagramGenerator.generate_from_image()` but is not exposed through an API endpoint.

### Data Classification Enforcement

The router enforces data classification before routing:

| Classification | Routing behavior |
|----------------|------------------|
| CUI, Restricted | Bedrock only, restricted to models listed as GovCloud-available |
| Internal | Bedrock (only provider enabled) |
| Public | Bedrock (only provider enabled) |

The `/generate` endpoint currently passes `Internal` for every request; there is no request field for selecting a classification.

### Required AWS Permissions

For Bedrock access, the service requires:

```yaml
- bedrock:InvokeModel
- bedrock:InvokeModelWithResponseStream
```

See `deploy/cloudformation/iam-diagram-service.yaml` for the complete IAM policy.

---

## SSM Parameters

`deploy/cloudformation/diagram-service-ssm.yaml` defines the following parameters:

| Parameter | Description | Type | Read by code today |
|-----------|-------------|------|--------------------|
| `/aura/{env}/providers/openai/enabled` | OpenAI provider toggle | String | No (provider disabled in router) |
| `/aura/{env}/providers/openai/api-key` | OpenAI API key placeholder | String | No |
| `/aura/{env}/providers/vertex/enabled` | Vertex AI provider toggle | String | No (provider disabled in router) |
| `/aura/{env}/providers/vertex/service-account` | GCP service account placeholder | String | No |
| `/aura/{env}/providers/diagram/daily-budget-usd` | Daily API cost budget (`100.0`) | String | No; the router uses an in-code default of $100/day |
| `/aura/{env}/providers/diagram/monthly-budget-usd` | Monthly API cost budget (`2000.0`) | String | No; the router uses an in-code default of $2000/month |

The Git sync library (`src/services/diagrams/diagram_git_sync.py`) reads `/aura/{env}/git/allowed-hosts` (comma-separated allowlist; defaults to `github.com` and `gitlab.com` when missing) and an enterprise-hosts JSON parameter when it is enabled for GovCloud.

---

## Troubleshooting

### Diagrams Show Basic Shapes Instead of Cloud Icons

**Symptom:** Generated diagrams display generic rectangles instead of AWS/Azure/GCP icons.

**Possible Causes:**

1. The request used `CODE_ANALYSIS` mode, which renders Mermaid diagrams without cloud icons
2. The diagram references an icon that has no embedded artwork (most Azure and GCP icons), which renders as a placeholder

**Solution:**

1. Use `mode=AI_PROMPT` for icon-based SVG diagrams
2. Check the selected mode in application logs: `Documentation service mode: real API`

### API Calls Failing in QA/Prod

**Symptom:** Diagram generation returns errors about API connectivity.

**Possible Causes:**

1. Missing IAM permissions for Bedrock
2. Bedrock model not enabled in the account or region
3. VPC endpoints not available

**Solution:**

1. Verify IAM role has Bedrock permissions
2. Verify the configured Claude model tiers are enabled in Bedrock for the region
3. Verify VPC endpoint for Bedrock is deployed

### Slow Response Times

**Symptom:** Diagram generation takes 10+ seconds.

**Possible Causes:**

1. Critique-and-refine iterations add Bedrock round trips
2. Complex diagrams with many nodes
3. Provider rate limiting

**Solution:**

1. First request is expected to be slower (client initialization)
2. Use `max_services` parameter to limit complexity in `CODE_ANALYSIS` mode
3. Check CloudWatch for rate limit errors

---

## Related Documentation

- [ADR-056: Documentation Agent](../architecture-decisions/ADR-056-documentation-agent.md) - Original architecture
- [ADR-060: Enterprise Diagram Generation](../architecture-decisions/ADR-060-enterprise-diagram-generation.md) - Professional diagram features
- Icon library source: `src/services/diagrams/icon_library.py` - Available cloud provider icons
- [API Reference](../reference/API_REFERENCE.md) - REST API documentation

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-01-18 | Initial documentation - made use_mock configurable | Project Aura Team |
| 2026-10-26 | Aligned with code: real API mode is the default in all environments, Bedrock-only routing, actual SSM parameter names, embedded icon coverage, and current `CODE_ANALYSIS` limitations | Project Aura Team |
