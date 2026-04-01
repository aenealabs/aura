# Configuration Reference

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document provides a complete reference for all configuration options in Project Aura. Configuration can be managed through environment variables, configuration files, or the administrative dashboard depending on your deployment model.

---

## Configuration Hierarchy

Configuration values are resolved in the following order (highest priority first):

1. **Runtime Overrides** - API calls or dashboard changes
2. **Environment Variables** - Container/process environment
3. **Configuration Files** - YAML/JSON files mounted in containers
4. **Helm Values** - Kubernetes deployments
5. **Default Values** - Built-in defaults

---

## Environment Variables

All Project Aura environment variables use the `AURA_` prefix. Variables are grouped by functional area.

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_ENVIRONMENT` | Yes | - | Deployment environment: `development`, `staging`, `production` |
| `AURA_DOMAIN` | Yes | - | Public domain for Aura (e.g., `aura.yourcompany.com`) |
| `AURA_EDITION` | No | `community` | License edition: `community`, `enterprise` |
| `AURA_LOG_LEVEL` | No | `info` | Logging level: `debug`, `info`, `warn`, `error` |
| `AURA_LOG_FORMAT` | No | `json` | Log format: `json`, `text` |
| `AURA_LOG_OUTPUT` | No | `stdout` | Log destination: `stdout`, `file`, `both` |
| `AURA_LOG_FILE_PATH` | No | `/var/log/aura/app.log` | Log file path (if `LOG_OUTPUT` includes `file`) |
| `AURA_TIMEZONE` | No | `UTC` | Default timezone for scheduling and display |

### Database Configuration

#### PostgreSQL (Document Store)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_POSTGRES_HOST` | Yes | - | PostgreSQL hostname |
| `AURA_POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `AURA_POSTGRES_DB` | Yes | - | Database name |
| `AURA_POSTGRES_USER` | Yes | - | Database username |
| `AURA_POSTGRES_PASSWORD` | Yes | - | Database password |
| `AURA_POSTGRES_SSL_MODE` | No | `require` | SSL mode: `disable`, `require`, `verify-ca`, `verify-full` |
| `AURA_POSTGRES_SSL_CERT` | No | - | Path to client certificate |
| `AURA_POSTGRES_SSL_KEY` | No | - | Path to client private key |
| `AURA_POSTGRES_SSL_ROOT_CERT` | No | - | Path to CA certificate |
| `AURA_POSTGRES_MAX_CONNECTIONS` | No | `20` | Maximum connection pool size |
| `AURA_POSTGRES_MIN_CONNECTIONS` | No | `5` | Minimum connection pool size |

#### Graph Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_GRAPH_PROVIDER` | No | `neptune` | Graph provider: `neptune`, `neo4j` |
| `AURA_NEPTUNE_ENDPOINT` | Conditional | - | Neptune cluster endpoint (if using Neptune) |
| `AURA_NEPTUNE_PORT` | No | `8182` | Neptune port |
| `AURA_NEPTUNE_SSL` | No | `true` | Enable SSL for Neptune |
| `AURA_NEO4J_HOST` | Conditional | - | Neo4j hostname (if using Neo4j) |
| `AURA_NEO4J_PORT` | No | `7687` | Neo4j Bolt port |
| `AURA_NEO4J_USER` | Conditional | - | Neo4j username |
| `AURA_NEO4J_PASSWORD` | Conditional | - | Neo4j password |
| `AURA_NEO4J_DATABASE` | No | `neo4j` | Neo4j database name |
| `AURA_NEO4J_SSL` | No | `true` | Enable SSL for Neo4j |

#### Vector Database (OpenSearch)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_OPENSEARCH_ENDPOINT` | Yes | - | OpenSearch endpoint URL |
| `AURA_OPENSEARCH_PORT` | No | `9200` | OpenSearch port |
| `AURA_OPENSEARCH_SSL` | No | `true` | Enable SSL for OpenSearch |
| `AURA_OPENSEARCH_AUTH_TYPE` | No | `iam` | Auth type: `iam`, `basic`, `none` |
| `AURA_OPENSEARCH_USER` | Conditional | - | OpenSearch username (if basic auth) |
| `AURA_OPENSEARCH_PASSWORD` | Conditional | - | OpenSearch password (if basic auth) |
| `AURA_OPENSEARCH_INDEX_PREFIX` | No | `aura` | Index name prefix |

#### Cache (Redis)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_REDIS_HOST` | No | `localhost` | Redis hostname |
| `AURA_REDIS_PORT` | No | `6379` | Redis port |
| `AURA_REDIS_PASSWORD` | No | - | Redis password (if authentication enabled) |
| `AURA_REDIS_DB` | No | `0` | Redis database number |
| `AURA_REDIS_SSL` | No | `false` | Enable SSL for Redis |
| `AURA_REDIS_CLUSTER_MODE` | No | `false` | Enable Redis cluster mode |

### LLM Provider Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_LLM_PROVIDER` | No | `bedrock` | LLM provider: `bedrock`, `openai`, `azure`, `ollama` |
| `AURA_LLM_MODEL` | No | Provider default | Default model identifier |
| `AURA_LLM_TIMEOUT_SECONDS` | No | `120` | LLM request timeout |
| `AURA_LLM_MAX_TOKENS` | No | `4096` | Maximum output tokens |
| `AURA_LLM_TEMPERATURE` | No | `0.1` | Model temperature (0.0-1.0) |
| `AURA_LLM_MAX_RETRIES` | No | `3` | Maximum retry attempts |

#### AWS Bedrock

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_AWS_REGION` | Conditional | - | AWS region for Bedrock |
| `AURA_AWS_ACCESS_KEY_ID` | Conditional | - | AWS access key (if not using IAM roles) |
| `AURA_AWS_SECRET_ACCESS_KEY` | Conditional | - | AWS secret key (if not using IAM roles) |
| `AURA_BEDROCK_MODEL_ID` | No | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Bedrock model identifier |
| `AURA_BEDROCK_GUARDRAIL_ID` | No | - | Bedrock Guardrail identifier |
| `AURA_BEDROCK_GUARDRAIL_VERSION` | No | `DRAFT` | Guardrail version |

#### OpenAI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_OPENAI_API_KEY` | Conditional | - | OpenAI API key |
| `AURA_OPENAI_ORG_ID` | No | - | OpenAI organization ID |
| `AURA_OPENAI_MODEL` | No | `gpt-4-turbo-preview` | OpenAI model name |
| `AURA_OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | OpenAI API base URL |

#### Azure OpenAI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_AZURE_OPENAI_ENDPOINT` | Conditional | - | Azure OpenAI endpoint |
| `AURA_AZURE_OPENAI_KEY` | Conditional | - | Azure OpenAI API key |
| `AURA_AZURE_OPENAI_DEPLOYMENT` | Conditional | - | Deployment name |
| `AURA_AZURE_OPENAI_API_VERSION` | No | `2024-02-01` | API version |

#### Ollama (Local LLM)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_OLLAMA_HOST` | Conditional | `http://localhost:11434` | Ollama server URL |
| `AURA_OLLAMA_MODEL` | No | `codellama:34b` | Ollama model name |

### Security Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_JWT_SECRET` | Yes | - | JWT signing secret (minimum 32 characters) |
| `AURA_JWT_EXPIRY` | No | `24h` | JWT token expiry duration |
| `AURA_JWT_REFRESH_EXPIRY` | No | `7d` | Refresh token expiry duration |
| `AURA_ENCRYPTION_KEY` | Yes | - | Data encryption key (exactly 32 characters) |
| `AURA_SESSION_SECRET` | No | Auto-generated | Session cookie secret |
| `AURA_ALLOWED_ORIGINS` | No | `*` | CORS allowed origins (comma-separated) |
| `AURA_CSRF_ENABLED` | No | `true` | Enable CSRF protection |
| `AURA_RATE_LIMIT_ENABLED` | No | `true` | Enable API rate limiting |
| `AURA_RATE_LIMIT_REQUESTS` | No | `100` | Requests per window |
| `AURA_RATE_LIMIT_WINDOW` | No | `60` | Rate limit window in seconds |

### Authentication Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_AUTH_MODE` | No | `local` | Authentication mode: `local`, `sso`, `hybrid` |
| `AURA_MFA_REQUIRED` | No | `false` | Require MFA for all users |
| `AURA_PASSWORD_MIN_LENGTH` | No | `12` | Minimum password length |
| `AURA_PASSWORD_REQUIRE_SPECIAL` | No | `true` | Require special characters in passwords |
| `AURA_SESSION_TIMEOUT_MINUTES` | No | `60` | Inactive session timeout |
| `AURA_MAX_LOGIN_ATTEMPTS` | No | `5` | Maximum failed login attempts |
| `AURA_LOCKOUT_DURATION_MINUTES` | No | `30` | Account lockout duration |

### Notification Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_SMTP_HOST` | No | - | SMTP server hostname |
| `AURA_SMTP_PORT` | No | `587` | SMTP server port |
| `AURA_SMTP_USER` | No | - | SMTP username |
| `AURA_SMTP_PASSWORD` | No | - | SMTP password |
| `AURA_SMTP_FROM` | No | - | Default from email address |
| `AURA_SMTP_TLS` | No | `true` | Enable TLS for SMTP |
| `AURA_SLACK_WEBHOOK_URL` | No | - | Slack incoming webhook URL |
| `AURA_TEAMS_WEBHOOK_URL` | No | - | Microsoft Teams webhook URL |
| `AURA_PAGERDUTY_INTEGRATION_KEY` | No | - | PagerDuty integration key |

---

## Feature Flags

Feature flags control optional functionality. All feature flags use the `AURA_ENABLE_` or `AURA_DISABLE_` prefix.

### Agent Features

| Flag | Default | Description |
|------|---------|-------------|
| `AURA_ENABLE_SANDBOX` | `true` | Enable sandbox testing for patches |
| `AURA_ENABLE_SEMANTIC_CACHE` | `true` | Cache LLM responses for similar queries |
| `AURA_ENABLE_SELF_REFLECTION` | `true` | Enable agent self-validation loops |
| `AURA_ENABLE_A2A_SECURITY` | `true` | Agent-to-Agent security validation |
| `AURA_ENABLE_CONSTITUTIONAL_AI` | `true` | Constitutional AI critique-revision |
| `AURA_ENABLE_NEURAL_MEMORY` | `true` | Titan neural memory architecture |

### Platform Features

| Flag | Default | Description |
|------|---------|-------------|
| `AURA_ENABLE_GRAPHQL` | `true` | Enable GraphQL API endpoint |
| `AURA_ENABLE_WEBHOOKS` | `true` | Enable webhook notifications |
| `AURA_ENABLE_API_DOCS` | `true` | Enable Swagger/OpenAPI documentation |
| `AURA_ENABLE_METRICS` | `true` | Enable Prometheus metrics endpoint |
| `AURA_ENABLE_TRACING` | `true` | Enable distributed tracing (X-Ray) |
| `AURA_ENABLE_AUDIT_LOG` | `true` | Enable detailed audit logging |

### Enterprise Features (Enterprise Edition Only)

| Flag | Default | Description |
|------|---------|-------------|
| `AURA_ENABLE_SSO` | `false` | Enable Single Sign-On |
| `AURA_ENABLE_ADVANCED_RBAC` | `false` | Enable fine-grained RBAC |
| `AURA_ENABLE_MULTI_TENANT` | `false` | Enable multi-tenant mode |
| `AURA_ENABLE_COMPLIANCE_REPORTS` | `false` | Enable compliance reporting |
| `AURA_ENABLE_AIR_GAP_MODE` | `false` | Enable air-gapped operation |

---

## Agent Configuration

### Autonomy Levels

Configure default agent autonomy for your organization:

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_DEFAULT_AUTONOMY_LEVEL` | `HITL_CRITICAL` | Default autonomy: `FULL_HITL`, `HITL_CRITICAL`, `AUDIT_ONLY`, `FULL_AUTONOMOUS` |
| `AURA_HITL_TIMEOUT_HOURS` | `24` | Default HITL approval timeout |
| `AURA_HITL_ESCALATION_HOURS` | `12` | Time before escalation |
| `AURA_HITL_MAX_ESCALATIONS` | `2` | Maximum escalation attempts |

### Agent Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_AGENT_MAX_CONCURRENT` | `10` | Maximum concurrent agent executions |
| `AURA_AGENT_TIMEOUT_SECONDS` | `600` | Agent execution timeout |
| `AURA_AGENT_MAX_RETRIES` | `3` | Maximum retry attempts |
| `AURA_AGENT_MEMORY_LIMIT_MB` | `4096` | Memory limit per agent |

### Model Selection

Configure LLM model selection for different agent types:

```yaml
# config/agents.yaml
agents:
  coder:
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    temperature: 0.1
    maxTokens: 8192

  reviewer:
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    temperature: 0.0
    maxTokens: 4096

  validator:
    model: anthropic.claude-3-5-sonnet-20241022-v2:0
    temperature: 0.0
    maxTokens: 2048
```

Environment variable overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_CODER_MODEL` | Platform default | Model for Coder agent |
| `AURA_REVIEWER_MODEL` | Platform default | Model for Reviewer agent |
| `AURA_VALIDATOR_MODEL` | Platform default | Model for Validator agent |

---

## Integration Settings

### Source Control

#### GitHub

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_GITHUB_APP_ID` | Conditional | - | GitHub App ID |
| `AURA_GITHUB_APP_PRIVATE_KEY` | Conditional | - | GitHub App private key (PEM) |
| `AURA_GITHUB_CLIENT_ID` | Conditional | - | OAuth App client ID |
| `AURA_GITHUB_CLIENT_SECRET` | Conditional | - | OAuth App client secret |
| `AURA_GITHUB_WEBHOOK_SECRET` | No | - | Webhook signature secret |
| `AURA_GITHUB_ENTERPRISE_URL` | No | - | GitHub Enterprise Server URL |

#### GitLab

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_GITLAB_APP_ID` | Conditional | - | GitLab OAuth application ID |
| `AURA_GITLAB_APP_SECRET` | Conditional | - | GitLab OAuth application secret |
| `AURA_GITLAB_WEBHOOK_SECRET` | No | - | Webhook signature secret |
| `AURA_GITLAB_URL` | No | `https://gitlab.com` | GitLab instance URL |

#### Bitbucket

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_BITBUCKET_CLIENT_ID` | Conditional | - | Bitbucket OAuth consumer key |
| `AURA_BITBUCKET_CLIENT_SECRET` | Conditional | - | Bitbucket OAuth consumer secret |
| `AURA_BITBUCKET_WEBHOOK_SECRET` | No | - | Webhook signature secret |

### Issue Tracking

#### Jira

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_JIRA_URL` | Conditional | - | Jira instance URL |
| `AURA_JIRA_USER` | Conditional | - | Jira username or email |
| `AURA_JIRA_API_TOKEN` | Conditional | - | Jira API token |
| `AURA_JIRA_PROJECT_KEY` | No | - | Default project key |

#### ServiceNow

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_SERVICENOW_INSTANCE` | Conditional | - | ServiceNow instance name |
| `AURA_SERVICENOW_USER` | Conditional | - | ServiceNow username |
| `AURA_SERVICENOW_PASSWORD` | Conditional | - | ServiceNow password |

---

## Performance Tuning

### API Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_API_WORKERS` | `4` | Number of API worker processes |
| `AURA_API_THREADS` | `2` | Threads per worker |
| `AURA_API_MAX_REQUEST_SIZE` | `10485760` | Maximum request body size (bytes) |
| `AURA_API_REQUEST_TIMEOUT` | `30` | Request timeout (seconds) |
| `AURA_API_KEEPALIVE_TIMEOUT` | `65` | Keep-alive timeout (seconds) |

### Database Connection Pools

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_DB_POOL_SIZE` | `20` | Database connection pool size |
| `AURA_DB_POOL_TIMEOUT` | `30` | Pool connection timeout (seconds) |
| `AURA_DB_POOL_RECYCLE` | `3600` | Connection recycle time (seconds) |
| `AURA_DB_POOL_OVERFLOW` | `10` | Maximum overflow connections |

### Cache Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_CACHE_TTL_SECONDS` | `300` | Default cache TTL |
| `AURA_CACHE_MAX_SIZE_MB` | `512` | Maximum cache size |
| `AURA_SEMANTIC_CACHE_TTL` | `3600` | Semantic cache TTL (seconds) |
| `AURA_SEMANTIC_CACHE_SIMILARITY` | `0.95` | Similarity threshold for cache hits |

### Sandbox Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AURA_SANDBOX_TIMEOUT_MINUTES` | `30` | Maximum sandbox execution time |
| `AURA_SANDBOX_MAX_CONCURRENT` | `5` | Maximum concurrent sandboxes |
| `AURA_SANDBOX_MEMORY_LIMIT_MB` | `2048` | Sandbox memory limit |
| `AURA_SANDBOX_CPU_LIMIT` | `1.0` | Sandbox CPU limit (cores) |
| `AURA_SANDBOX_NETWORK_ENABLED` | `false` | Allow sandbox network access |

---

## Configuration Files

### YAML Configuration

For complex configurations, use YAML files mounted in containers:

```yaml
# config/aura.yaml
environment: production
domain: aura.yourcompany.com

database:
  postgres:
    host: postgres.internal
    port: 5432
    database: aura
    sslMode: verify-full

  graph:
    provider: neptune
    endpoint: neptune-cluster.us-east-1.neptune.amazonaws.com
    port: 8182

  vector:
    endpoint: https://opensearch.internal:9200
    authType: iam

llm:
  provider: bedrock
  model: anthropic.claude-3-5-sonnet-20241022-v2:0
  temperature: 0.1
  maxTokens: 4096

agents:
  autonomy:
    defaultLevel: HITL_CRITICAL
    timeoutHours: 24
    escalationHours: 12

  limits:
    maxConcurrent: 10
    timeoutSeconds: 600
    maxRetries: 3

security:
  corsOrigins:
    - https://aura.yourcompany.com
    - https://admin.yourcompany.com
  rateLimiting:
    enabled: true
    requests: 100
    windowSeconds: 60

features:
  sandbox: true
  semanticCache: true
  selfReflection: true
  auditLog: true
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: aura-system
data:
  aura.yaml: |
    environment: production
    domain: aura.yourcompany.com
    # ... rest of configuration
```

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aura-secrets
  namespace: aura-system
type: Opaque
stringData:
  JWT_SECRET: "your-jwt-secret-at-least-32-characters"
  ENCRYPTION_KEY: "your-encryption-key-exactly-32ch"
  POSTGRES_PASSWORD: "your-database-password"
```

---

## Configuration Validation

### Health Check Endpoint

The `/api/v1/health` endpoint validates configuration:

```bash
curl -s https://aura.yourcompany.com/api/v1/health | jq
```

```json
{
  "status": "healthy",
  "version": "1.6.0",
  "configuration": {
    "environment": "production",
    "edition": "enterprise",
    "features": {
      "sandbox": true,
      "semanticCache": true,
      "sso": true
    }
  },
  "services": {
    "database": "healthy",
    "graph": "healthy",
    "vector": "healthy",
    "llm": "healthy",
    "cache": "healthy"
  }
}
```

### Configuration Validation Command

```bash
# Kubernetes
kubectl exec -it deployment/aura-api -n aura-system -- \
  aura-cli config validate

# Podman
podman exec aura-api aura-cli config validate
```

---

## Environment-Specific Configuration

### Development

```bash
AURA_ENVIRONMENT=development
AURA_LOG_LEVEL=debug
AURA_LOG_FORMAT=text
AURA_ENABLE_API_DOCS=true
AURA_RATE_LIMIT_ENABLED=false
AURA_CSRF_ENABLED=false
```

### Staging

```bash
AURA_ENVIRONMENT=staging
AURA_LOG_LEVEL=info
AURA_ENABLE_API_DOCS=true
AURA_RATE_LIMIT_ENABLED=true
```

### Production

```bash
AURA_ENVIRONMENT=production
AURA_LOG_LEVEL=warn
AURA_LOG_FORMAT=json
AURA_ENABLE_API_DOCS=false
AURA_RATE_LIMIT_ENABLED=true
AURA_CSRF_ENABLED=true
AURA_MFA_REQUIRED=true
```

---

## Troubleshooting Configuration

### Common Issues

| Issue | Symptom | Resolution |
|-------|---------|------------|
| Invalid JWT secret | Auth failures | Ensure secret is at least 32 characters |
| Database connection | 503 errors | Verify endpoint, credentials, and SSL settings |
| LLM timeout | Patch generation fails | Increase `AURA_LLM_TIMEOUT_SECONDS` |
| Rate limiting | 429 errors | Adjust `AURA_RATE_LIMIT_REQUESTS` |
| CORS errors | Browser console errors | Add domain to `AURA_ALLOWED_ORIGINS` |

### Configuration Dump

Export current configuration for debugging:

```bash
# Kubernetes
kubectl exec -it deployment/aura-api -n aura-system -- \
  aura-cli config dump --format yaml

# Podman
podman exec aura-api aura-cli config dump --format yaml
```

> **Security Best Practice:** Never log or expose sensitive configuration values (passwords, API keys, secrets). Use the `--redact` flag when sharing configuration dumps.

---

## Related Documentation

- [Administration Guide](./index.md)
- [Deployment Options](./deployment-options.md)
- [SSO Integration](./sso-integration.md)
- [HITL Workflows](../core-concepts/hitl-workflows.md)
- [Security Architecture](../../support/architecture/security-architecture.md)

---

*Last updated: January 2026 | Version 1.0*
