# Deployment Options

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

Project Aura supports multiple deployment models to meet diverse enterprise requirements, from fully managed SaaS to air-gapped on-premises installations. This guide covers each deployment option, including prerequisites, configuration, and operational considerations.

---

## Deployment Model Comparison

| Feature | SaaS | Self-Hosted K8s | Self-Hosted Podman | Hybrid | GovCloud |
|---------|------|-----------------|-------------------|--------|----------|
| **Management** | Fully managed | Customer managed | Customer managed | Shared | Customer managed |
| **Time to Deploy** | Minutes | Hours | 30 minutes | Days | Days |
| **Data Location** | Aenea Labs cloud | Customer infrastructure | Customer infrastructure | On-premises | AWS GovCloud |
| **Scaling** | Automatic | Customer configured | Manual | Customer configured | Customer configured |
| **Compliance** | SOC 2, ISO 27001 | Customer responsibility | Customer responsibility | Shared responsibility | FedRAMP, CMMC |
| **LLM Access** | AWS Bedrock | Configurable | Configurable | Configurable | Bedrock GovCloud |
| **Cost Model** | Subscription | Infrastructure + License | Infrastructure + License | Infrastructure + License | Infrastructure + License |

---

## Option 1: SaaS (Fully Managed)

The SaaS deployment is the recommended option for most organizations. Aenea Labs manages all infrastructure, scaling, updates, and security.

### Features

- Zero infrastructure management
- Automatic scaling and high availability
- Managed upgrades with zero downtime
- SOC 2 Type II certified infrastructure
- 99.9% uptime SLA (Enterprise tier)

### Getting Started

1. **Create Account**

   Navigate to [aenealabs.com/signup](https://aenealabs.com/signup) and complete registration.

2. **Select Subscription Tier**

   | Tier | Users | Features | Support |
   |------|-------|----------|---------|
   | Starter | Up to 10 | Core scanning, basic HITL | Community |
   | Professional | Up to 100 | Full HITL, sandbox testing | Email (8h) |
   | Enterprise | Unlimited | SSO, advanced RBAC, audit logs | Dedicated (1h) |
   | Government | Unlimited | GovCloud, FedRAMP | Dedicated (1h) |

3. **Configure Organization**

   - Set organization name and primary contact
   - Select compliance profile (enterprise standard, financial, healthcare, etc.)
   - Configure default HITL policy

4. **Connect Integrations**

   - Source control: GitHub, GitLab, Bitbucket
   - Notifications: Slack, Microsoft Teams, email
   - Ticketing: Jira, ServiceNow

### Data Residency

SaaS deployments support regional data residency:

| Region | Data Center | Availability |
|--------|-------------|--------------|
| US East | AWS us-east-1 | General availability |
| US West | AWS us-west-2 | General availability |
| EU (Frankfurt) | AWS eu-central-1 | General availability |
| Asia Pacific | AWS ap-southeast-1 | Coming Q2 2026 |

---

## Option 2: Self-Hosted Kubernetes (EKS)

For organizations requiring full control over their infrastructure, data sovereignty, or specific compliance requirements.

> **Reference:** This deployment model implements ADR-049 (Self-Hosted Deployment Strategy). See the architecture decision record for detailed rationale and design decisions.

### Prerequisites

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Kubernetes | 1.27+ | 1.29+ |
| Nodes | 3 (m5.xlarge) | 5 (m5.2xlarge) |
| RAM per node | 16 GB | 32 GB |
| Storage | 500 GB SSD | 1 TB SSD |
| Network | Private subnets | Multi-AZ VPC |

### Infrastructure Components

```
+-----------------------------------------------------------------------------+
|                    SELF-HOSTED KUBERNETES ARCHITECTURE                       |
+-----------------------------------------------------------------------------+

    +-------------------------+     +-------------------------+
    |       INGRESS           |     |    EXTERNAL SERVICES    |
    |  +-------------------+  |     |  +-------------------+  |
    |  |   ALB / NGINX     |  |     |  |   AWS Bedrock     |  |
    |  |   TLS Termination |  |     |  |   (via PrivateLink|  |
    |  +-------------------+  |     |  |    or Internet)   |  |
    +------------+------------+     |  +-------------------+  |
                 |                  +-------------------------+
                 v
+-----------------------------------------------------------------------------+
|                        KUBERNETES CLUSTER (EKS)                              |
|                                                                              |
|  +-------------------+  +-------------------+  +-------------------+        |
|  |   aura-api        |  |   orchestrator    |  |   agents          |        |
|  |   replicas: 2     |  |   replicas: 2     |  |   replicas: 3     |        |
|  +-------------------+  +-------------------+  +-------------------+        |
|                                                                              |
|  +-------------------+  +-------------------+  +-------------------+        |
|  |   frontend        |  |   context-svc     |  |   hitl-svc        |        |
|  |   replicas: 2     |  |   replicas: 2     |  |   replicas: 2     |        |
|  +-------------------+  +-------------------+  +-------------------+        |
|                                                                              |
+-----------------------------------------------------------------------------+
                 |
    +------------+------------+
    |            |            |
    v            v            v
+-----------------------------------------------------------------------------+
|                           DATA SERVICES                                      |
|                                                                              |
|  +-------------------+  +-------------------+  +-------------------+        |
|  |   Neptune Cluster |  |   OpenSearch      |  |   DynamoDB        |        |
|  |   (or Neo4j)      |  |   Domain          |  |   (or PostgreSQL) |        |
|  +-------------------+  +-------------------+  +-------------------+        |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### Deployment Steps

#### Step 1: Provision AWS Infrastructure

Deploy foundation infrastructure using CloudFormation:

```bash
# Set environment variables
export AWS_REGION=us-east-1
export ENVIRONMENT=production
export PROJECT_NAME=aura

# Deploy VPC and networking
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

# Deploy EKS cluster
aws cloudformation deploy \
  --template-file cloudformation/compute.yaml \
  --stack-name ${PROJECT_NAME}-compute-${ENVIRONMENT} \
  --parameter-overrides Environment=${ENVIRONMENT} \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Step 2: Configure kubectl

```bash
# Update kubeconfig for EKS
aws eks update-kubeconfig \
  --region ${AWS_REGION} \
  --name ${PROJECT_NAME}-cluster-${ENVIRONMENT}

# Verify connectivity
kubectl get nodes
```

#### Step 3: Install via Helm

```bash
# Add Aura Helm repository
helm repo add aura https://charts.aenealabs.com
helm repo update

# Create namespace
kubectl create namespace aura-system

# Create secrets
kubectl create secret generic aura-secrets \
  --namespace aura-system \
  --from-literal=jwt-secret='YOUR_JWT_SECRET_MIN_32_CHARS' \
  --from-literal=encryption-key='YOUR_ENCRYPTION_KEY_32_CHARS'

# Install Aura
helm install aura aura/aura \
  --namespace aura-system \
  --values values-production.yaml
```

#### Sample values-production.yaml

```yaml
global:
  domain: aura.yourcompany.com
  environment: production
  edition: enterprise  # community or enterprise

# API Server
api:
  replicas: 2
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi

# Agent Orchestrator
orchestrator:
  replicas: 2
  resources:
    requests:
      cpu: 1000m
      memory: 2Gi
    limits:
      cpu: 4000m
      memory: 8Gi

# Agent Workers
agents:
  replicas: 3
  resources:
    requests:
      cpu: 2000m
      memory: 4Gi
    limits:
      cpu: 4000m
      memory: 8Gi

# AWS Service Configuration
aws:
  region: us-east-1
  neptune:
    endpoint: ${NEPTUNE_ENDPOINT}
    port: 8182
  opensearch:
    endpoint: ${OPENSEARCH_ENDPOINT}
  bedrock:
    enabled: true
    modelId: anthropic.claude-3-5-sonnet-20241022-v2:0

# Ingress Configuration
ingress:
  enabled: true
  className: alb
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/certificate-arn: ${ACM_CERT_ARN}
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06

# Security Settings
security:
  podSecurityPolicy: restricted
  networkPolicy:
    enabled: true
    defaultDeny: true
  serviceAccount:
    create: true
    annotations:
      eks.amazonaws.com/role-arn: ${IRSA_ROLE_ARN}
```

#### Step 4: Configure DNS

Point your domain to the load balancer:

```bash
# Get ALB hostname
kubectl get ingress aura-ingress -n aura-system \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

Create a CNAME record in Route 53 or your DNS provider.

#### Step 5: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n aura-system

# Test health endpoint
curl -k https://aura.yourcompany.com/api/v1/health

# Expected response:
# {"status":"healthy","version":"1.6.0","services":{...}}
```

### High Availability Configuration

For production deployments, configure high availability:

| Component | HA Configuration |
|-----------|------------------|
| API | 2+ replicas, PodDisruptionBudget |
| Orchestrator | 2+ replicas, leader election |
| Agents | 3+ replicas, queue-based distribution |
| Neptune | Multi-AZ cluster, read replicas |
| OpenSearch | 3-node cluster, dedicated masters |

```yaml
# PodDisruptionBudget for API
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: aura-api-pdb
  namespace: aura-system
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: aura-api
```

---

## Option 3: Self-Hosted Podman

For development environments, evaluation, or small teams without Kubernetes.

### Prerequisites

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 8 cores | 16 cores |
| RAM | 32 GB | 64 GB |
| Storage | 500 GB SSD | 1 TB NVMe |
| OS | Linux, macOS, Windows | Linux (Ubuntu 22.04, RHEL 9) |
| Podman | 4.0+ | 5.0+ |

### Installation

#### Linux (Ubuntu/Debian)

```bash
# Install Podman
sudo apt-get update
sudo apt-get install -y podman podman-compose

# Verify installation
podman --version
```

#### Linux (RHEL/CentOS)

```bash
# Install Podman
sudo dnf install -y podman podman-compose

# Verify installation
podman --version
```

#### macOS

```bash
# Install via Homebrew
brew install podman

# Initialize and start Podman machine
podman machine init --cpus 4 --memory 8192 --disk-size 100
podman machine start
```

#### Windows

Download and install [Podman Desktop](https://podman-desktop.io/) for Windows.

### Deployment

#### Step 1: Create Directory Structure

```bash
mkdir -p ~/aura/{config,data,logs}
cd ~/aura
```

#### Step 2: Create Environment File

Create `~/aura/.env`:

```bash
# Aura Self-Hosted Configuration
AURA_ENVIRONMENT=development
AURA_DOMAIN=localhost
AURA_EDITION=community

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aura
POSTGRES_USER=aura
POSTGRES_PASSWORD=secure_password_here

# Graph Database (Neo4j)
NEO4J_HOST=neo4j
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secure_password_here

# Redis Cache
REDIS_HOST=redis
REDIS_PORT=6379

# LLM Configuration
# Option 1: AWS Bedrock (recommended)
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Option 2: OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-key

# Option 3: Azure OpenAI
# LLM_PROVIDER=azure
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
# AZURE_OPENAI_KEY=your-key
# AZURE_OPENAI_DEPLOYMENT=gpt-4

# Option 4: Local LLM (Ollama) - for air-gapped
# LLM_PROVIDER=ollama
# OLLAMA_HOST=http://localhost:11434
# OLLAMA_MODEL=codellama:34b

# Security Configuration
JWT_SECRET=your_jwt_secret_at_least_32_characters_long
ENCRYPTION_KEY=your_encryption_key_exactly_32chars

# Feature Flags
ENABLE_SANDBOX=true
ENABLE_SEMANTIC_CACHE=true
```

#### Step 3: Create Compose File

Create `~/aura/podman-compose.yml`:

```yaml
version: '3.8'

services:
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
    networks:
      - aura-network

  neo4j:
    image: docker.io/library/neo4j:5.15-community
    container_name: aura-neo4j
    environment:
      NEO4J_AUTH: ${NEO4J_USER}/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*,gds.*"
    volumes:
      - ./data/neo4j:/data
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - aura-network

  redis:
    image: docker.io/library/redis:7-alpine
    container_name: aura-redis
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - aura-network

  opensearch:
    image: docker.io/opensearchproject/opensearch:2.11.0
    container_name: aura-opensearch
    environment:
      discovery.type: single-node
      DISABLE_SECURITY_PLUGIN: "true"
      OPENSEARCH_JAVA_OPTS: "-Xms1g -Xmx1g"
    volumes:
      - ./data/opensearch:/usr/share/opensearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200 | grep -q 'cluster_name'"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - aura-network

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
      opensearch:
        condition: service_healthy
    volumes:
      - ./config:/config:ro
      - ./logs/api:/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - aura-network

  orchestrator:
    image: ghcr.io/aenealabs/aura-orchestrator:latest
    container_name: aura-orchestrator
    env_file: .env
    depends_on:
      api:
        condition: service_healthy
    volumes:
      - ./logs/orchestrator:/logs
    networks:
      - aura-network

  agents:
    image: ghcr.io/aenealabs/aura-agents:latest
    container_name: aura-agents
    env_file: .env
    depends_on:
      orchestrator:
        condition: service_started
    volumes:
      - ./logs/agents:/logs
    networks:
      - aura-network

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
    networks:
      - aura-network

networks:
  aura-network:
    driver: bridge
```

#### Step 4: Start Services

```bash
cd ~/aura

# Pull images
podman-compose pull

# Start all services
podman-compose up -d

# Check status
podman-compose ps

# View logs
podman-compose logs -f api
```

#### Step 5: Verify Installation

```bash
# Check all containers are running
podman ps

# Test API health
curl http://localhost:8080/health

# Access web interface
open https://localhost  # macOS
xdg-open https://localhost  # Linux
```

---

## Option 4: Hybrid Deployment

For organizations that require data to remain on-premises while leveraging cloud compute resources.

### Architecture

```
+-----------------------------------------------------------------------------+
|                       HYBRID DEPLOYMENT ARCHITECTURE                         |
+-----------------------------------------------------------------------------+

    ON-PREMISES NETWORK                         CLOUD (AWS)
    +---------------------------+               +---------------------------+
    |                           |               |                           |
    |  +---------------------+  |    VPN/DX     |  +---------------------+  |
    |  |   Neptune/Neo4j     |<-+---------------+->|   EKS Cluster       |  |
    |  |   (Graph Data)      |  |               |  |   - API             |  |
    |  +---------------------+  |               |  |   - Orchestrator    |  |
    |                           |               |  |   - Agents          |  |
    |  +---------------------+  |               |  +---------------------+  |
    |  |   OpenSearch        |<-+---------------+->|                       |  |
    |  |   (Vector Data)     |  |               |  |   AWS Bedrock       |  |
    |  +---------------------+  |               |  |   (LLM Service)     |  |
    |                           |               |  |                       |  |
    |  +---------------------+  |               |  +---------------------+  |
    |  |   Source Code       |  |               |                           |
    |  |   Repositories      |  |               |                           |
    |  +---------------------+  |               |                           |
    |                           |               |                           |
    +---------------------------+               +---------------------------+
```

### Use Cases

- **Data Residency:** Code and vulnerability data must remain in specific geographic locations
- **Compliance:** Regulatory requirements prohibit cloud storage of source code
- **Security:** Air-gapped or restricted network environments
- **Existing Infrastructure:** Leverage existing on-premises database investments

### Configuration

#### Network Connectivity

Establish secure connectivity between on-premises and cloud:

| Option | Latency | Bandwidth | Cost |
|--------|---------|-----------|------|
| AWS Direct Connect | 1-5ms | 1-100 Gbps | $$$$ |
| Site-to-Site VPN | 10-50ms | Up to 1.25 Gbps | $$ |
| AWS PrivateLink | 1-5ms | Service-dependent | $$$ |

#### Database Configuration

Configure cloud services to connect to on-premises databases:

```yaml
# values-hybrid.yaml
databases:
  # On-premises Neptune-compatible endpoint
  graph:
    provider: neptune  # or neo4j
    endpoint: neptune.internal.yourcompany.com
    port: 8182
    ssl: true

  # On-premises OpenSearch endpoint
  vector:
    provider: opensearch
    endpoint: https://opensearch.internal.yourcompany.com:9200
    ssl: true
    auth:
      type: basic
      secretName: opensearch-credentials

  # On-premises PostgreSQL for documents
  document:
    provider: postgresql
    host: postgres.internal.yourcompany.com
    port: 5432
    database: aura
    ssl: true
    secretName: postgres-credentials
```

#### Security Considerations

> **Security Best Practice:** Encrypt all data in transit between on-premises and cloud using TLS 1.3. Never expose database ports directly to the internet.

| Control | Implementation |
|---------|----------------|
| Network encryption | TLS 1.3 for all database connections |
| Authentication | mTLS certificates or strong credentials |
| Access control | Restrict cloud IPs to VPN/Direct Connect only |
| Audit logging | Log all cross-boundary data access |

---

## Option 5: GovCloud Deployment

For federal government customers and contractors requiring FedRAMP, CMMC, or ITAR compliance.

### Compliance Certifications

| Framework | Status | Authorization Level |
|-----------|--------|---------------------|
| FedRAMP | In Progress | Moderate (targeting High) |
| CMMC | Level 3 Ready | Infrastructure controls deployed |
| NIST 800-171 | Compliant | Full control implementation |
| ITAR | Supported | GovCloud isolation |

### GovCloud Architecture

```
+-----------------------------------------------------------------------------+
|                    AWS GOVCLOUD (US) ARCHITECTURE                            |
+-----------------------------------------------------------------------------+

    +-------------------------+
    |   GOVCLOUD BOUNDARY     |
    |   (FedRAMP High)        |
    +-------------------------+
              |
              v
    +-------------------------+     +-------------------------+
    |       INGRESS           |     |    SECURITY SERVICES    |
    |  +-------------------+  |     |  +-------------------+  |
    |  |   AWS WAF         |  |     |  |   AWS CloudTrail  |  |
    |  |   (GovCloud)      |  |     |  |   AWS Config      |  |
    |  +-------------------+  |     |  |   GuardDuty       |  |
    +-------------------------+     |  +-------------------+  |
              |                     +-------------------------+
              v
    +-------------------------+
    |     VPC (Isolated)      |
    |  +-------------------+  |
    |  |   EKS GovCloud    |  |
    |  |   - FIPS 140-2    |  |
    |  |   - Encrypted EBS |  |
    |  +-------------------+  |
    |                         |
    |  +-------------------+  |
    |  |   Neptune         |  |
    |  |   (Provisioned)   |  |
    |  +-------------------+  |
    |                         |
    |  +-------------------+  |
    |  |   Bedrock         |  |
    |  |   (GovCloud)      |  |
    |  +-------------------+  |
    +-------------------------+
```

### GovCloud-Specific Configuration

```yaml
# values-govcloud.yaml
global:
  domain: aura.govcloud.yourorg.gov
  environment: production
  region: us-gov-west-1
  partition: aws-us-gov

aws:
  region: us-gov-west-1
  # Use provisioned Neptune (serverless not available in GovCloud)
  neptune:
    serverless: false
    instanceClass: db.r5.xlarge

  # Bedrock GovCloud configuration
  bedrock:
    enabled: true
    endpoint: bedrock-runtime.us-gov-west-1.amazonaws.com
    modelId: anthropic.claude-3-5-sonnet-20241022-v2:0

security:
  # FIPS 140-2 compliant encryption
  fips:
    enabled: true

  # Customer-managed KMS keys
  kms:
    keyArn: arn:aws-us-gov:kms:us-gov-west-1:123456789012:key/your-key-id

  # CloudTrail for audit logging
  cloudTrail:
    enabled: true
    s3Bucket: aura-audit-logs-govcloud

  # Enhanced logging for compliance
  auditLog:
    retention: 7  # years
    encryption: true
```

### GovCloud Deployment Steps

1. **Obtain GovCloud Access**
   - Complete AWS GovCloud access request
   - Establish organizational account structure

2. **Deploy Infrastructure**
   ```bash
   # Set GovCloud region
   export AWS_REGION=us-gov-west-1
   export AWS_DEFAULT_REGION=us-gov-west-1

   # Deploy using GovCloud-specific templates
   aws cloudformation deploy \
     --template-file cloudformation/govcloud/foundation.yaml \
     --stack-name aura-foundation-prod \
     --capabilities CAPABILITY_NAMED_IAM
   ```

3. **Configure FIPS Compliance**
   ```bash
   # Enable FIPS endpoints
   export AWS_USE_FIPS_ENDPOINT=true
   ```

4. **Deploy Application**
   ```bash
   helm install aura aura/aura \
     --namespace aura-system \
     --values values-govcloud.yaml
   ```

### GovCloud Limitations

| Feature | Commercial | GovCloud |
|---------|-----------|----------|
| Neptune Serverless | Available | Not available |
| OpenSearch Serverless | Available | Not available |
| All Bedrock Models | Available | Limited models |
| Some AWS Services | Available | May not be available |

---

## Upgrades

### SaaS Upgrades

SaaS deployments are automatically upgraded by Aenea Labs with zero downtime. Major version upgrades are announced 30 days in advance.

### Self-Hosted Upgrades

#### Helm Upgrade

```bash
# Update Helm repository
helm repo update

# Check available versions
helm search repo aura/aura --versions

# Upgrade to latest
helm upgrade aura aura/aura \
  --namespace aura-system \
  --values values-production.yaml

# Upgrade to specific version
helm upgrade aura aura/aura \
  --namespace aura-system \
  --values values-production.yaml \
  --version 1.7.0
```

#### Podman Upgrade

```bash
cd ~/aura

# Pull new images
podman-compose pull

# Recreate containers with new images
podman-compose up -d --force-recreate

# Verify upgrade
curl http://localhost:8080/health
```

### Rollback Procedures

```bash
# Helm rollback
helm rollback aura 1 --namespace aura-system

# Podman rollback (requires image tags)
# Edit podman-compose.yml to use previous version tag
podman-compose up -d --force-recreate
```

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Resolution |
|-------|---------|------------|
| Database connection failed | API returns 503 | Check database endpoints in configuration |
| LLM timeout | Patch generation fails | Verify Bedrock/OpenAI credentials and quotas |
| TLS certificate error | Browser security warning | Verify certificate chain and domain match |
| Pod crash loop | Pods restart repeatedly | Check logs with `kubectl logs`, verify resources |
| Insufficient resources | OOM errors, slow response | Increase node/container resources |

### Diagnostic Commands

```bash
# Kubernetes diagnostics
kubectl get pods -n aura-system
kubectl describe pod <pod-name> -n aura-system
kubectl logs <pod-name> -n aura-system --tail=100

# Podman diagnostics
podman ps -a
podman logs aura-api --tail=100
podman stats

# Health check
curl -s https://your-domain.com/api/v1/health | jq
```

---

## Related Documentation

- [Administration Guide](./index.md)
- [Configuration Reference](./configuration-reference.md)
- [Installation Guide](../getting-started/installation.md)
- [System Requirements](../getting-started/system-requirements.md)
- [Security Architecture](../../support/architecture/security-architecture.md)

---

*Last updated: January 2026 | Version 1.0*
