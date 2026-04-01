# Installation and Configuration

**Last Updated:** January 2026

This guide provides detailed instructions for deploying Project Aura across all supported deployment models.

---

## Table of Contents

1. [Cloud (SaaS) Setup](#cloud-saas-setup)
2. [Self-Hosted Kubernetes Deployment](#self-hosted-kubernetes-deployment)
3. [Self-Hosted Podman Deployment](#self-hosted-podman-deployment)
4. [Initial Configuration](#initial-configuration)
5. [Environment Variables Reference](#environment-variables-reference)
6. [CI/CD Integration](#cicd-integration)
7. [Post-Installation Verification](#post-installation-verification)

---

## Cloud (SaaS) Setup

The fastest path to deploying Aura. Aenea Labs manages all infrastructure components.

### Step 1: Create Your Organization

1. Navigate to [aenealabs.com/signup](https://aenealabs.com/signup)

2. Enter your organization details:
   - Organization name
   - Primary contact email
   - Industry vertical (for compliance presets)

3. Select your subscription tier:
   - **Starter** - Small teams, basic features
   - **Professional** - HITL workflows, sandbox testing
   - **Enterprise** - Custom integrations, dedicated support
   - **Government** - GovCloud deployment, CMMC support

4. Complete payment information and accept terms of service.

5. Check your email for activation link.

### Step 2: Configure SSO (Recommended)

For enterprise deployments, configure single sign-on:

1. Navigate to **Settings > Authentication**

2. Click **Configure SSO**

3. Select your identity provider:
   - Okta
   - Azure AD / Entra ID
   - PingIdentity
   - Google Workspace
   - Custom SAML 2.0

4. For SAML configuration, provide:

   | Field | Description |
   |-------|-------------|
   | **IdP Entity ID** | Unique identifier from your IdP |
   | **SSO URL** | IdP single sign-on endpoint |
   | **Certificate** | X.509 signing certificate |

5. Download the Aura SAML metadata and configure your IdP:

   | Aura Configuration | Value |
   |--------------------|-------|
   | **SP Entity ID** | `https://app.aenealabs.com/saml/metadata` |
   | **ACS URL** | `https://app.aenealabs.com/saml/acs` |
   | **SLO URL** | `https://app.aenealabs.com/saml/slo` |

6. Test SSO login before enforcing for all users.

### Step 3: Connect Source Control

1. Navigate to **Settings > Integrations**

2. Click **Add Integration**

3. Select your source control provider and follow the OAuth flow

4. For GitHub Enterprise or GitLab Self-Managed, provide your server URL

Your cloud setup is complete. Proceed to [Initial Configuration](#initial-configuration).

---

## Self-Hosted Kubernetes Deployment

For organizations requiring on-premises or private cloud deployment.

### Prerequisites

Before beginning, ensure you have:

- [ ] Kubernetes cluster 1.27+ running
- [ ] `kubectl` configured with cluster admin access
- [ ] Helm 3.x installed
- [ ] AWS CLI configured (for AWS deployments)
- [ ] Domain name and TLS certificate

### Step 1: Provision AWS Infrastructure

Deploy required AWS services using CloudFormation or Terraform.

**Option A: CloudFormation (Recommended)**

```bash
# Clone the Aura deployment repository
git clone https://github.com/aenealabs/aura-deployment.git
cd aura-deployment

# Set environment variables
export AWS_REGION=us-east-1
export ENVIRONMENT=production
export PROJECT_NAME=aura

# Deploy foundation layer (VPC, IAM, security groups)
aws cloudformation deploy \
  --template-file cloudformation/foundation.yaml \
  --stack-name ${PROJECT_NAME}-foundation-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy data layer (Neptune, OpenSearch, DynamoDB)
aws cloudformation deploy \
  --template-file cloudformation/data.yaml \
  --stack-name ${PROJECT_NAME}-data-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy compute layer (EKS)
aws cloudformation deploy \
  --template-file cloudformation/compute.yaml \
  --stack-name ${PROJECT_NAME}-compute-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM
```

**Option B: Terraform**

```bash
cd terraform/

# Initialize Terraform
terraform init

# Review planned changes
terraform plan -var="environment=production"

# Apply infrastructure
terraform apply -var="environment=production"
```

### Step 2: Configure kubectl

After EKS cluster creation, configure kubectl access:

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --region ${AWS_REGION} \
  --name ${PROJECT_NAME}-cluster-${ENVIRONMENT}

# Verify connectivity
kubectl get nodes
```

### Step 3: Install Aura via Helm

Add the Aura Helm repository and install:

```bash
# Add Helm repository
helm repo add aura https://charts.aenealabs.com
helm repo update

# Create namespace
kubectl create namespace aura-system

# Create secrets for sensitive configuration
kubectl create secret generic aura-secrets \
  --namespace aura-system \
  --from-literal=db-password='YOUR_DB_PASSWORD' \
  --from-literal=jwt-secret='YOUR_JWT_SECRET' \
  --from-literal=encryption-key='YOUR_ENCRYPTION_KEY'

# Install Aura
helm install aura aura/aura \
  --namespace aura-system \
  --values values-production.yaml \
  --set global.domain=aura.yourcompany.com \
  --set global.environment=production
```

**Sample values-production.yaml:**

```yaml
global:
  domain: aura.yourcompany.com
  environment: production
  tlsSecretName: aura-tls

# Replica counts for high availability
api:
  replicas: 2
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi

orchestrator:
  replicas: 2
  resources:
    requests:
      cpu: 1000m
      memory: 2Gi

agents:
  replicas: 3
  resources:
    requests:
      cpu: 2000m
      memory: 4Gi

# AWS service configuration
aws:
  region: us-east-1
  neptune:
    endpoint: ${NEPTUNE_ENDPOINT}
    port: 8182
  opensearch:
    endpoint: ${OPENSEARCH_ENDPOINT}
  bedrock:
    modelId: anthropic.claude-3-5-sonnet-20241022-v2:0

# Ingress configuration
ingress:
  enabled: true
  className: alb
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/certificate-arn: ${ACM_CERTIFICATE_ARN}
```

### Step 4: Configure Ingress and TLS

**Using AWS ALB Ingress Controller:**

```bash
# Install ALB Ingress Controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName=${PROJECT_NAME}-cluster-${ENVIRONMENT} \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

# Verify ingress is created
kubectl get ingress -n aura-system
```

**Using NGINX Ingress:**

```bash
# Install NGINX Ingress Controller
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace

# Create TLS secret
kubectl create secret tls aura-tls \
  --namespace aura-system \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key
```

### Step 5: Configure DNS

Point your domain to the load balancer:

```bash
# Get load balancer address
kubectl get ingress aura-ingress -n aura-system -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

Create a CNAME record in your DNS provider:

| Record Type | Name | Value |
|-------------|------|-------|
| CNAME | aura.yourcompany.com | [load-balancer-hostname] |

### Step 6: Verify Deployment

```bash
# Check pod status
kubectl get pods -n aura-system

# Expected output:
# NAME                            READY   STATUS    RESTARTS   AGE
# aura-api-xxxxx-xxxxx            1/1     Running   0          5m
# aura-api-xxxxx-xxxxx            1/1     Running   0          5m
# aura-orchestrator-xxxxx-xxxxx   1/1     Running   0          5m
# aura-agents-xxxxx-xxxxx         1/1     Running   0          5m
# aura-frontend-xxxxx-xxxxx       1/1     Running   0          5m

# Check service health
kubectl logs -n aura-system deployment/aura-api --tail=50

# Access health endpoint
curl https://aura.yourcompany.com/health
```

---

## Self-Hosted Podman Deployment

For single-node deployments without Kubernetes.

### Prerequisites

- [ ] Linux, macOS, or Windows with Podman 4.0+
- [ ] 32 GB RAM minimum
- [ ] 500 GB storage
- [ ] Domain name and TLS certificate (for production)

### Step 1: Install Podman

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y podman podman-compose
```

**RHEL/CentOS:**

```bash
sudo dnf install -y podman podman-compose
```

**macOS:**

```bash
brew install podman
podman machine init
podman machine start
```

**Windows:**

Download and install Podman Desktop from [podman.io](https://podman.io/getting-started/installation).

### Step 2: Create Configuration Directory

```bash
mkdir -p ~/aura/{config,data,logs}
cd ~/aura
```

### Step 3: Create Environment File

Create `~/aura/.env` with your configuration:

```bash
# Aura Self-Hosted Configuration
AURA_ENVIRONMENT=production
AURA_DOMAIN=aura.yourcompany.com

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aura
POSTGRES_USER=aura
POSTGRES_PASSWORD=your_secure_password

# Neo4j Configuration
NEO4J_HOST=neo4j
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# LLM Provider Configuration
# Option 1: AWS Bedrock
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Option 2: OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_openai_key

# Option 3: Local LLM (Ollama)
# LLM_PROVIDER=ollama
# OLLAMA_HOST=http://localhost:11434

# Security Configuration
JWT_SECRET=your_jwt_secret_at_least_32_characters
ENCRYPTION_KEY=your_encryption_key_32_characters

# TLS Configuration (for production)
TLS_CERT_PATH=/config/tls.crt
TLS_KEY_PATH=/config/tls.key
```

### Step 4: Create Podman Compose File

Create `~/aura/podman-compose.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: docker.io/library/postgres:16
    container_name: aura-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Neo4j Graph Database
  neo4j:
    image: docker.io/library/neo4j:5.15
    container_name: aura-neo4j
    environment:
      NEO4J_AUTH: ${NEO4J_USER}/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - ./data/neo4j:/data
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: docker.io/library/redis:7
    container_name: aura-redis
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Aura API Server
  api:
    image: ghcr.io/aenealabs/aura-api:latest
    container_name: aura-api
    env_file: .env
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./config:/config:ro
      - ./logs/api:/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Aura Orchestrator
  orchestrator:
    image: ghcr.io/aenealabs/aura-orchestrator:latest
    container_name: aura-orchestrator
    env_file: .env
    depends_on:
      api:
        condition: service_healthy
    volumes:
      - ./logs/orchestrator:/logs

  # Aura Agent Workers
  agents:
    image: ghcr.io/aenealabs/aura-agents:latest
    container_name: aura-agents
    env_file: .env
    depends_on:
      orchestrator:
        condition: service_started
    volumes:
      - ./logs/agents:/logs

  # Aura Frontend
  frontend:
    image: ghcr.io/aenealabs/aura-frontend:latest
    container_name: aura-frontend
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./config/tls.crt:/etc/nginx/ssl/tls.crt:ro
      - ./config/tls.key:/etc/nginx/ssl/tls.key:ro
    depends_on:
      api:
        condition: service_healthy
```

### Step 5: Add TLS Certificates

For production deployments, place your TLS certificates:

```bash
cp /path/to/your/certificate.crt ~/aura/config/tls.crt
cp /path/to/your/private.key ~/aura/config/tls.key
chmod 600 ~/aura/config/tls.key
```

For development, generate self-signed certificates:

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/aura/config/tls.key \
  -out ~/aura/config/tls.crt \
  -subj "/CN=localhost"
```

### Step 6: Start Aura

```bash
cd ~/aura

# Pull latest images
podman-compose pull

# Start all services
podman-compose up -d

# Check status
podman-compose ps

# View logs
podman-compose logs -f api
```

### Step 7: Verify Installation

```bash
# Check all containers are running
podman ps

# Test API health
curl -k https://localhost/health

# Expected response:
# {"status":"healthy","version":"1.0.0","services":{"database":"healthy","graph":"healthy","cache":"healthy"}}
```

---

## Initial Configuration

After installation, complete these configuration steps.

### Create Admin Account

**Cloud SaaS:** Admin account created during signup.

**Self-Hosted:**

```bash
# For Kubernetes deployment
kubectl exec -it deployment/aura-api -n aura-system -- \
  aura-cli user create \
    --email admin@yourcompany.com \
    --role admin \
    --password 'YourSecurePassword'

# For Podman deployment
podman exec -it aura-api \
  aura-cli user create \
    --email admin@yourcompany.com \
    --role admin \
    --password 'YourSecurePassword'
```

### Configure Organization Settings

1. Sign in to Aura at your configured domain

2. Navigate to **Settings > Organization**

3. Configure essential settings:

   | Setting | Description |
   |---------|-------------|
   | **Organization Name** | Display name for your organization |
   | **Default Autonomy Level** | HITL policy for new repositories |
   | **Notification Email** | Default email for alerts |
   | **Timezone** | Organization timezone for scheduling |

### Configure Security Policies

1. Navigate to **Settings > Security Policies**

2. Set your HITL approval policy:

   | Policy | When to Use |
   |--------|-------------|
   | **FULL_HITL** | Maximum oversight (CMMC Level 3) |
   | **HITL_FINAL** | Trust testing, approve deployment |
   | **HITL_CRITICAL** | Balance automation and control |
   | **FULL_AUTONOMOUS** | Development environments only |

3. Configure approval timeouts:
   - Default: 24 hours
   - Critical vulnerabilities: Consider shorter timeouts

4. Set escalation contacts for timeout scenarios

### Connect Source Control

1. Navigate to **Settings > Integrations**

2. Click **Add Source Control**

3. Follow provider-specific setup:

   **GitHub:**
   - Create OAuth App or GitHub App in GitHub Settings
   - Configure callback URL: `https://your-domain.com/auth/github/callback`
   - Add Client ID and Secret to Aura

   **GitLab:**
   - Create Application in GitLab Admin
   - Configure redirect URI
   - Add Application ID and Secret

4. Authorize and test the connection

---

## Environment Variables Reference

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AURA_ENVIRONMENT` | Yes | - | Deployment environment (dev, staging, production) |
| `AURA_DOMAIN` | Yes | - | Public domain for Aura |
| `AURA_LOG_LEVEL` | No | `info` | Logging level (debug, info, warn, error) |
| `AURA_LOG_FORMAT` | No | `json` | Log format (json, text) |

### Database Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_HOST` | Yes | - | PostgreSQL hostname |
| `POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `POSTGRES_DB` | Yes | - | Database name |
| `POSTGRES_USER` | Yes | - | Database user |
| `POSTGRES_PASSWORD` | Yes | - | Database password |
| `POSTGRES_SSL_MODE` | No | `require` | SSL mode (disable, require, verify-full) |

### Graph Database (Neo4j or Neptune)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GRAPH_PROVIDER` | No | `neptune` | Graph provider (neptune, neo4j) |
| `NEO4J_HOST` | Conditional | - | Neo4j hostname (if using Neo4j) |
| `NEO4J_PORT` | No | `7687` | Neo4j Bolt port |
| `NEO4J_USER` | Conditional | - | Neo4j username |
| `NEO4J_PASSWORD` | Conditional | - | Neo4j password |
| `NEPTUNE_ENDPOINT` | Conditional | - | Neptune cluster endpoint (if using Neptune) |
| `NEPTUNE_PORT` | No | `8182` | Neptune port |

### LLM Provider Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `bedrock` | LLM provider (bedrock, openai, azure, ollama) |
| `AWS_REGION` | Conditional | - | AWS region for Bedrock |
| `BEDROCK_MODEL_ID` | No | `anthropic.claude-3-5-sonnet` | Bedrock model identifier |
| `OPENAI_API_KEY` | Conditional | - | OpenAI API key (if using OpenAI) |
| `AZURE_OPENAI_ENDPOINT` | Conditional | - | Azure OpenAI endpoint |
| `AZURE_OPENAI_KEY` | Conditional | - | Azure OpenAI key |
| `OLLAMA_HOST` | Conditional | - | Ollama server URL (if using local LLM) |

### Security Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | Yes | - | Secret for JWT signing (min 32 chars) |
| `JWT_EXPIRY` | No | `24h` | JWT token expiry duration |
| `ENCRYPTION_KEY` | Yes | - | Key for data encryption (32 chars) |
| `SESSION_SECRET` | No | auto | Session cookie secret |
| `ALLOWED_ORIGINS` | No | `*` | CORS allowed origins |

### Notification Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | No | - | SMTP server for email |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | No | - | SMTP username |
| `SMTP_PASSWORD` | No | - | SMTP password |
| `SMTP_FROM` | No | - | From email address |
| `SLACK_WEBHOOK_URL` | No | - | Slack incoming webhook |
| `TEAMS_WEBHOOK_URL` | No | - | Microsoft Teams webhook |

### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_SANDBOX` | No | `true` | Enable sandbox testing |
| `ENABLE_SEMANTIC_CACHE` | No | `true` | Enable LLM response caching |
| `ENABLE_SELF_REFLECTION` | No | `true` | Enable agent self-validation |
| `SANDBOX_TIMEOUT_MINUTES` | No | `30` | Maximum sandbox runtime |
| `MAX_CONCURRENT_SCANS` | No | `5` | Concurrent scan limit |

---

## CI/CD Integration

Integrate Aura with your existing CI/CD pipelines.

### GitHub Actions

Add Aura scanning to your GitHub workflow:

```yaml
# .github/workflows/aura-scan.yml
name: Aura Security Scan

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Aura Scan
        uses: aenealabs/aura-action@v1
        with:
          aura-url: ${{ secrets.AURA_URL }}
          aura-token: ${{ secrets.AURA_API_TOKEN }}
          fail-on: critical,high
          scan-type: full

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: aura-results
          path: aura-results.json
```

### GitLab CI

```yaml
# .gitlab-ci.yml
aura-scan:
  stage: test
  image: ghcr.io/aenealabs/aura-cli:latest
  script:
    - aura scan
        --url ${AURA_URL}
        --token ${AURA_API_TOKEN}
        --fail-on critical,high
        --output aura-results.json
  artifacts:
    reports:
      security: aura-results.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

### Jenkins

```groovy
// Jenkinsfile
pipeline {
    agent any

    environment {
        AURA_URL = credentials('aura-url')
        AURA_TOKEN = credentials('aura-api-token')
    }

    stages {
        stage('Security Scan') {
            steps {
                sh '''
                    aura scan \
                        --url ${AURA_URL} \
                        --token ${AURA_TOKEN} \
                        --fail-on critical,high
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'aura-results.json', fingerprint: true
        }
    }
}
```

### AWS CodeBuild

```yaml
# buildspec.yml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - pip install aura-cli

  build:
    commands:
      - |
        aura scan \
          --url ${AURA_URL} \
          --token ${AURA_API_TOKEN} \
          --fail-on critical,high \
          --output aura-results.json

artifacts:
  files:
    - aura-results.json
```

---

## Post-Installation Verification

Complete these checks to verify your installation.

### Health Check

```bash
# API health
curl https://your-domain.com/api/v1/health

# Expected response
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "graph": "healthy",
    "search": "healthy",
    "cache": "healthy",
    "llm": "healthy"
  }
}
```

### Connectivity Tests

```bash
# Test source control connectivity
curl https://your-domain.com/api/v1/integrations/github/test \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test LLM connectivity
curl https://your-domain.com/api/v1/llm/test \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Functional Test

1. Connect a test repository
2. Run a scan
3. Verify vulnerabilities are detected
4. Generate a patch
5. Verify sandbox testing completes
6. Approve or reject the patch

### Performance Baseline

Document initial performance metrics:

| Metric | Target | Your Result |
|--------|--------|-------------|
| API response (P95) | < 200ms | |
| Scan time (100K LOC) | < 5 min | |
| Patch generation | < 5 min | |
| Dashboard load | < 2 sec | |

---

## Troubleshooting

### Common Issues

**Database Connection Failed**

```
Error: FATAL: password authentication failed
```

Solution: Verify database credentials in environment variables and ensure the database user has appropriate permissions.

**Graph Database Timeout**

```
Error: Connection timeout to Neptune/Neo4j
```

Solution: Check VPC security groups allow traffic on port 8182 (Neptune) or 7687 (Neo4j). Verify VPC endpoints are configured.

**LLM Provider Error**

```
Error: Bedrock access denied
```

Solution: Ensure AWS credentials have `bedrock:InvokeModel` permission and the model is enabled in the Bedrock console.

**TLS Certificate Error**

```
Error: SSL certificate problem
```

Solution: Verify certificate chain is complete and the certificate matches the configured domain.

### Getting Help

- **Documentation:** [docs.aenealabs.com](https://docs.aenealabs.com)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Community Forum:** [community.aenealabs.com](https://community.aenealabs.com)

---

## Next Steps

- **[Quick Start Guide](./quick-start.md)** - Connect your first repository
- **[First Project Walkthrough](./first-project.md)** - Complete hands-on tutorial
- **[Platform Overview](./index.md)** - Understand Aura capabilities
