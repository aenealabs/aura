# System Requirements

**Last Updated:** January 2026

This document outlines the technical requirements for deploying and using Project Aura across different deployment models.

---

## Deployment Models Overview

Project Aura supports three deployment models, each with different infrastructure requirements:

| Model | Infrastructure Owner | Best For |
|-------|---------------------|----------|
| **Cloud (SaaS)** | Aenea Labs | Fastest setup, minimal IT overhead |
| **Self-Hosted (Kubernetes)** | Customer | Data residency, GovCloud, enterprise scale |
| **Self-Hosted (Podman)** | Customer | Air-gapped, small teams, single-node |

---

## Cloud (SaaS) Requirements

For the cloud deployment model, requirements are minimal since Aenea Labs manages the infrastructure.

### Browser Compatibility

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| Google Chrome | 100+ | Recommended |
| Mozilla Firefox | 100+ | Full support |
| Microsoft Edge | 100+ | Chromium-based |
| Safari | 15+ | macOS and iOS |

**Not Supported:**
- Internet Explorer (any version)
- Safari 14 and earlier

### Network Requirements

| Requirement | Details |
|-------------|---------|
| **Internet Access** | HTTPS (443) outbound to `*.aenealabs.com` |
| **WebSocket Support** | Required for real-time updates |
| **Minimum Bandwidth** | 1 Mbps per concurrent user |

**Firewall Allowlist (if applicable):**

```
# Aura Cloud Endpoints
app.aenealabs.com         (Application)
api.aenealabs.com         (API)
ws.aenealabs.com          (WebSocket)
auth.aenealabs.com        (Authentication)
static.aenealabs.com      (Static assets)
```

### Source Control Integration

Aura requires network connectivity to your source control provider:

| Provider | Endpoints | Authentication |
|----------|-----------|----------------|
| **GitHub Cloud** | `github.com`, `api.github.com` | OAuth App or GitHub App |
| **GitHub Enterprise** | Your GHE URL | OAuth App |
| **GitLab SaaS** | `gitlab.com` | OAuth |
| **GitLab Self-Managed** | Your GitLab URL | OAuth or Personal Access Token |
| **Bitbucket Cloud** | `bitbucket.org` | OAuth |
| **Azure DevOps** | `dev.azure.com` | OAuth |

---

## Self-Hosted (Kubernetes) Requirements

For organizations deploying Aura in their own infrastructure.

### Kubernetes Cluster Requirements

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| **Kubernetes Version** | 1.27 | 1.29+ | EKS, GKE, AKS, or vanilla K8s |
| **Worker Nodes** | 3 | 5+ | Across multiple availability zones |
| **Node CPU** | 4 vCPU | 8 vCPU | Per worker node |
| **Node Memory** | 16 GB | 32 GB | Per worker node |
| **Node Storage** | 100 GB SSD | 200 GB SSD | Per worker node |

### AWS EKS Specific Requirements

For AWS deployments, the following managed services are required:

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **Amazon EKS** | Container orchestration | EC2 managed node groups |
| **Amazon Neptune** | Graph database | db.r5.large or higher |
| **Amazon OpenSearch** | Vector search | m5.large.search, 3 nodes |
| **Amazon DynamoDB** | State management | On-demand capacity |
| **Amazon S3** | Object storage | Standard storage class |
| **AWS Bedrock** | LLM inference | Claude 3.5 Sonnet access |
| **Amazon ECR** | Container registry | Private repositories |
| **AWS KMS** | Encryption | Customer-managed keys |

**AWS GovCloud Requirements:**

For government workloads, deploy to AWS GovCloud (US-East or US-West):

| Consideration | Implementation |
|---------------|----------------|
| **EKS Fargate** | Not available - use EC2 managed node groups |
| **Neptune Serverless** | Not available - use provisioned Neptune |
| **Bedrock** | FedRAMP High authorized |
| **FIPS 140-2** | Enable FIPS endpoints |

### Compute Requirements

**Control Plane (Aura Services):**

| Service | CPU Request | Memory Request | Replicas |
|---------|-------------|----------------|----------|
| API Gateway | 500m | 1 GB | 2 |
| Orchestrator | 1000m | 2 GB | 2 |
| Context Service | 500m | 1 GB | 2 |
| Agent Workers | 2000m | 4 GB | 3 |
| Frontend | 250m | 512 MB | 2 |

**Sandbox Environments:**

Each active sandbox requires temporary compute resources:

| Resource | Allocation | Duration |
|----------|------------|----------|
| CPU | 500m - 2000m | 5-30 minutes |
| Memory | 1-4 GB | 5-30 minutes |
| Storage | 10-50 GB ephemeral | Auto-cleanup |

Plan for 3-5 concurrent sandboxes per 100 daily vulnerability remediations.

### Storage Requirements

| Storage Type | Minimum | Purpose |
|--------------|---------|---------|
| **Neptune** | 100 GB | Code graph storage |
| **OpenSearch** | 200 GB | Vector embeddings |
| **S3** | 50 GB | Artifacts, logs, backups |
| **DynamoDB** | On-demand | State, configuration |
| **EBS (per node)** | 100 GB gp3 | Container images, local storage |

Storage grows with codebase size. Plan approximately:
- 1 GB Neptune per 100K lines of code
- 2 GB OpenSearch per 100K lines of code

### Network Requirements

**VPC Configuration:**

| Component | Requirement |
|-----------|-------------|
| **CIDR Block** | /16 or larger (65,536 IP addresses) |
| **Availability Zones** | 3 minimum |
| **Private Subnets** | Required for all Aura components |
| **NAT Gateway** | For outbound internet (package downloads) |
| **VPC Endpoints** | Required for AWS service access |

**Required VPC Endpoints:**

```
com.amazonaws.{region}.ecr.api
com.amazonaws.{region}.ecr.dkr
com.amazonaws.{region}.s3
com.amazonaws.{region}.dynamodb
com.amazonaws.{region}.ssm
com.amazonaws.{region}.secretsmanager
com.amazonaws.{region}.bedrock-runtime
com.amazonaws.{region}.logs
com.amazonaws.{region}.monitoring
```

**Ingress Requirements:**

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 443 | HTTPS | Users | Web interface and API |
| 443 | WSS | Users | Real-time updates |

**Egress Requirements:**

| Destination | Port | Purpose |
|-------------|------|---------|
| Source control (GitHub, etc.) | 443 | Repository access |
| Package registries (npm, PyPI) | 443 | Sandbox dependencies |
| AWS services | 443 | Via VPC endpoints |

---

## Self-Hosted (Podman) Requirements

For single-node deployments without Kubernetes.

### Operating System

| OS | Version | Support Level |
|----|---------|---------------|
| **Ubuntu** | 22.04 LTS, 24.04 LTS | Full support |
| **RHEL** | 8.x, 9.x | Full support |
| **Amazon Linux** | 2023 | Full support |
| **macOS** | 13+ (Ventura) | Development only |
| **Windows** | Server 2022, Windows 11 | Full support (via WSL2 or native) |

### Hardware Requirements

**Minimum (Small Team, < 500K LOC):**

| Resource | Specification |
|----------|---------------|
| CPU | 8 cores / 16 threads |
| Memory | 32 GB RAM |
| Storage | 500 GB SSD |
| Network | 1 Gbps |

**Recommended (Enterprise, < 2M LOC):**

| Resource | Specification |
|----------|---------------|
| CPU | 16 cores / 32 threads |
| Memory | 64 GB RAM |
| Storage | 1 TB NVMe SSD |
| Network | 10 Gbps |

**High Performance (Large Codebase, 2M+ LOC):**

| Resource | Specification |
|----------|---------------|
| CPU | 32 cores / 64 threads |
| Memory | 128 GB RAM |
| Storage | 2 TB NVMe SSD |
| Network | 10 Gbps |

### Container Runtime

| Runtime | Version | Notes |
|---------|---------|-------|
| **Podman** | 4.0+ | Recommended (rootless) |
| **Docker** | 24.0+ | Alternative |

Podman is preferred for:
- Rootless container execution
- No daemon requirement
- Better security posture
- No licensing fees

### Database Requirements (Self-Hosted)

For Podman deployments, you can use containerized or external databases:

**Option 1: Containerized (Development/Small Teams)**

| Component | Container Image | Resources |
|-----------|-----------------|-----------|
| Neo4j | `neo4j:5.15` | 4 GB RAM, 50 GB storage |
| PostgreSQL | `postgres:16` | 2 GB RAM, 20 GB storage |
| Redis | `redis:7` | 1 GB RAM |

**Option 2: External Services (Production)**

| Service | Purpose | Minimum Tier |
|---------|---------|--------------|
| Neo4j Aura | Graph database | Professional |
| PostgreSQL (RDS, Cloud SQL) | Relational data | db.t3.medium |
| Redis (ElastiCache, Memorystore) | Caching | cache.t3.small |

---

## Source Control System Requirements

### Supported Platforms

| Platform | Version | Features |
|----------|---------|----------|
| **GitHub Cloud** | Current | Full support |
| **GitHub Enterprise Server** | 3.8+ | Full support |
| **GitLab SaaS** | Current | Full support |
| **GitLab Self-Managed** | 15.0+ | Full support |
| **Bitbucket Cloud** | Current | Full support |
| **Bitbucket Data Center** | 8.0+ | Full support |
| **Azure DevOps Services** | Current | Full support |
| **Azure DevOps Server** | 2022+ | Full support |

### Required Permissions

**GitHub (OAuth App or GitHub App):**

| Scope | Purpose |
|-------|---------|
| `repo` | Repository read/write access |
| `read:org` | Organization membership |
| `workflow` | CI/CD trigger (optional) |

**GitLab:**

| Scope | Purpose |
|-------|---------|
| `api` | Full API access |
| `read_repository` | Clone repositories |
| `write_repository` | Push patches |

**Bitbucket:**

| Scope | Purpose |
|-------|---------|
| `repository` | Repository read/write |
| `pullrequest` | Create pull requests |
| `webhook` | Configure webhooks |

### Repository Size Limits

| Metric | Recommended Maximum | Notes |
|--------|---------------------|-------|
| **Lines of Code** | 10M lines | Per repository |
| **Files** | 100,000 files | Per repository |
| **Repository Size** | 5 GB | Git repository |
| **Single File Size** | 100 MB | Individual files |

Larger repositories may require:
- Increased scan timeouts
- Additional compute resources
- Incremental scanning strategy

---

## LLM Provider Requirements

### AWS Bedrock (Primary)

Aura uses AWS Bedrock for LLM inference. Ensure you have:

| Requirement | Details |
|-------------|---------|
| **Model Access** | Claude 3.5 Sonnet enabled in Bedrock console |
| **Region** | us-east-1, us-west-2, or GovCloud equivalent |
| **Service Quota** | Default quotas sufficient for most workloads |
| **IAM Permissions** | `bedrock:InvokeModel`, `bedrock:ApplyGuardrail` |

**GovCloud Consideration:** Bedrock is FedRAMP High authorized in AWS GovCloud.

### Alternative Providers (Self-Hosted)

For air-gapped or multi-provider deployments:

| Provider | Configuration | Use Case |
|----------|---------------|----------|
| **OpenAI API** | API key configuration | Alternative provider |
| **Azure OpenAI** | Azure subscription | Microsoft environments |
| **Local LLMs** | Ollama, vLLM | Air-gapped deployments |

---

## Security Requirements

### Authentication

| Method | Requirement | Notes |
|--------|-------------|-------|
| **SAML 2.0** | IdP with SAML support | Recommended for enterprise |
| **OIDC** | OpenID Connect provider | Alternative SSO |
| **Local Auth** | Argon2id password hashing | Available but not recommended for enterprise |

**Supported Identity Providers:**
- Okta
- Azure AD / Entra ID
- PingIdentity
- OneLogin
- Google Workspace
- AWS IAM Identity Center

### TLS Certificates

| Deployment | Certificate Requirement |
|------------|------------------------|
| **Cloud SaaS** | Managed by Aenea Labs |
| **Self-Hosted** | Customer-provided or Let's Encrypt |

For self-hosted deployments, provide:
- Valid TLS certificate for your domain
- Private key (RSA 2048+ or ECDSA P-256+)
- Full certificate chain

### Network Security

| Control | Requirement |
|---------|-------------|
| **Encryption in Transit** | TLS 1.2+ (1.3 recommended) |
| **Encryption at Rest** | AES-256 |
| **WAF** | Recommended for public endpoints |
| **DDoS Protection** | AWS Shield or equivalent |

---

## Compliance Prerequisites

### CMMC Level 2/3

Organizations pursuing CMMC certification should verify:

| Control Area | Aura Capability |
|--------------|-----------------|
| **Access Control (AC)** | RBAC, MFA, audit logging |
| **Audit (AU)** | Immutable audit logs, 7-year retention |
| **Configuration Management (CM)** | Infrastructure as code |
| **Identification (IA)** | SSO integration, MFA |
| **System Protection (SC)** | Encryption, network isolation |

### FedRAMP

For federal deployments:

| Requirement | Implementation |
|-------------|----------------|
| **Deployment Location** | AWS GovCloud (US) |
| **Encryption** | FIPS 140-2 validated modules |
| **Audit Logging** | CloudTrail, CloudWatch Logs |
| **Boundary Protection** | VPC, security groups, WAF |

### SOX Compliance

For financial services:

| Control | Aura Feature |
|---------|--------------|
| **Change Management** | HITL approval workflows |
| **Audit Trail** | Immutable decision logs |
| **Access Control** | RBAC with separation of duties |
| **Data Integrity** | Checksums, tamper detection |

---

## Pre-Installation Checklist

Before beginning installation, verify the following:

### Cloud (SaaS)

- [ ] Modern browser available (Chrome, Firefox, Edge, Safari)
- [ ] Network access to `*.aenealabs.com`
- [ ] Source control provider accessible
- [ ] Aura account created and activated

### Self-Hosted (Kubernetes)

- [ ] Kubernetes cluster running (1.27+)
- [ ] kubectl configured with cluster access
- [ ] Helm 3.x installed
- [ ] AWS services provisioned (Neptune, OpenSearch, etc.)
- [ ] VPC endpoints configured
- [ ] TLS certificate available
- [ ] DNS configured for Aura hostname
- [ ] Bedrock model access enabled

### Self-Hosted (Podman)

- [ ] Operating system meets requirements
- [ ] Hardware meets minimum specifications
- [ ] Podman or Docker installed
- [ ] Sufficient disk space available
- [ ] Network access to source control and LLM provider
- [ ] TLS certificate available (for production)

---

## Next Steps

Once you have verified that your environment meets the requirements:

- **[Installation Guide](./installation.md)** - Step-by-step deployment instructions
- **[Quick Start Guide](./quick-start.md)** - Connect your first repository
- **[First Project Walkthrough](./first-project.md)** - Complete tutorial

---

## Getting Help

For questions about system requirements or capacity planning:

- **Documentation:** [docs.aenealabs.com/requirements](https://docs.aenealabs.com/requirements)
- **Support Portal:** [support.aenealabs.com](https://support.aenealabs.com)
- **Sales Engineering:** Contact your account representative for enterprise sizing guidance
