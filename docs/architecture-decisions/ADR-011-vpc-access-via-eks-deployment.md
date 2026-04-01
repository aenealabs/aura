# ADR-011: VPC Resource Access via EKS Deployment over Bastion Hosts

**Status:** Deployed
**Date:** 2025-11-29
**Decision Makers:** Project Aura Team

## Context

Project Aura's data services (Neptune, OpenSearch) are deployed in private VPC subnets with no public endpoints, following security best practices established in ADR-002. Developers need secure access to these VPC-only resources for:

- Local development and testing against real databases
- Debugging database connectivity issues
- Running integration tests with production-like data
- Validating database schemas and queries

We evaluated five approaches for providing secure developer access to VPC-only resources while maintaining CMMC Level 3 compliance posture.

## Decision

We chose **EKS Deployment with kubectl port-forward** as our VPC access strategy.

**Implementation:**
1. Deploy the Aura API as a Kubernetes pod in the existing EKS cluster
2. API pod has direct VPC access to Neptune, OpenSearch, and DynamoDB
3. Developers use `kubectl port-forward` to access the API locally
4. No additional infrastructure required (uses existing EKS nodes)

**Access Pattern:**
```bash
# Connect to EKS cluster
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1

# Port forward API to localhost
kubectl port-forward svc/aura-api 8080:8080

# Access API locally
curl http://localhost:8080/health
```

## Alternatives Considered

### Alternative 1: SSM Session Manager with Port Forwarding

Deploy a lightweight EC2 instance (t3.micro) in a private subnet with SSM Agent. Use SSM Session Manager to establish secure tunnels for port forwarding.

**Pros:**
- Zero inbound ports (no SSH, no security group ingress)
- Full CloudTrail audit logging
- IAM-based authentication (no SSH keys)
- GovCloud compatible

**Cons:**
- Additional monthly cost (~$23-30/month including SSM VPC endpoints)
- Additional infrastructure to manage
- Requires 3 VPC endpoints (ssm, ssmmessages, ec2messages)
- Another attack surface (even if minimal)

**Cost:** ~$23-30/month

### Alternative 2: EC2 Bastion Host with SSH

Traditional bastion/jump box with SSH access.

**Pros:**
- Familiar pattern for most developers
- Low complexity
- Low cost (~$8/month for t3.micro)

**Cons:**
- Requires inbound port 22 (security group exposure)
- SSH key management overhead
- Limited audit trail (requires custom logging)
- Higher risk of credential compromise
- Does NOT meet CMMC Level 3 requirements for remote access (AC.L3-3.1.12)
- Potential for lateral movement via SSH agent forwarding

**Cost:** ~$8/month
**Security Rating:** ⚠️ Not recommended for compliance-focused projects

### Alternative 3: AWS Client VPN

Enterprise VPN solution with certificate-based authentication.

**Pros:**
- Full network access to VPC
- Supports MFA via SAML integration
- Enterprise-grade security
- GovCloud compatible

**Cons:**
- High complexity (certificate management, SAML setup)
- Higher cost (~$75-150/month for endpoint + connections)
- Overkill for small team development
- Requires client software installation

**Cost:** ~$75-150/month

### Alternative 4: AWS Cloud9

Browser-based IDE running inside the VPC.

**Pros:**
- Zero local setup
- Automatic hibernation (cost optimization)
- Full VPC access
- Good for quick debugging

**Cons:**
- Limited GovCloud availability
- Browser-based workflow may not suit all developers
- Cannot use local IDE preferences/plugins
- Limited to AWS console access

**Cost:** ~$5-10/month (auto-hibernate)

### Alternative 5: EKS Deployment (Chosen)

Deploy API to existing EKS cluster, use kubectl port-forward for local access.

**Pros:**
- **$0 incremental cost** (uses existing EKS infrastructure)
- No additional attack surface
- Production-like testing environment
- Full audit trail via Kubernetes audit logs
- kubectl uses IAM authentication (via aws-iam-authenticator)
- GovCloud compatible
- Simplest architecture (no new components)

**Cons:**
- Requires deploying API container to test changes
- Slightly longer feedback loop vs. direct database access
- Depends on EKS cluster availability

**Cost:** $0/month (incremental)

## Consequences

### Positive

1. **Zero Additional Cost**
   - Uses existing EKS cluster (already paid: ~$73/month for control plane)
   - Uses existing EC2 nodes (already paid: 2× t3.medium)
   - No new VPC endpoints required
   - Annual savings vs. SSM: ~$276-360

2. **Minimal Attack Surface**
   - No new EC2 instances exposed
   - No new security group rules
   - No SSH keys to manage
   - No additional VPC endpoints

3. **Production Parity**
   - API runs in same environment as production
   - Same IAM roles, same network policies
   - Catches environment-specific issues early
   - More realistic integration testing

4. **Security Compliance**
   - CMMC Level 3: Meets AC.L3-3.1.12 (Remote Access)
   - Full audit trail via CloudTrail + Kubernetes audit logs
   - IAM-based authentication via kubectl
   - No persistent credentials on developer machines

5. **Operational Simplicity**
   - Single deployment target (EKS)
   - No separate infrastructure to maintain
   - Standard Kubernetes workflow
   - Team already familiar with kubectl

### Negative

1. **Deployment Required for Testing**
   - Cannot test code changes without building and deploying container
   - Adds ~2-5 minutes to feedback loop for database-related changes
   - Mitigation: Use mock mode for rapid local iteration, deploy for integration testing

2. **EKS Dependency**
   - If EKS cluster is unavailable, cannot access VPC resources
   - Mitigation: EKS has 99.95% SLA; cluster issues are rare

3. **Container Build Requirement**
   - Requires Docker image build for each deployment
   - Mitigation: CI/CD pipeline handles builds; local builds take ~30 seconds

### Mitigation Strategies

1. **Rapid Local Development**
   - Use MOCK mode for fast iteration (no database needed)
   - Only deploy to EKS for integration testing
   - Mock services replicate production behavior

2. **CI/CD Integration**
   - Automated builds on git push
   - Automatic deployment to dev cluster
   - Developers can trigger manual builds when needed

3. **Fallback Option**
   - SSM Session Manager can be added later if needed (~5 minute setup)
   - Decision is not irreversible

## Implementation

### Kubernetes Resources Required

1. **Deployment** - API pods with environment-aware database connections
2. **Service** - ClusterIP service for internal access
3. **ConfigMap** - Database endpoints and configuration
4. **ServiceAccount** - IAM role for DynamoDB, Bedrock access (IRSA)

### Developer Workflow

```bash
# One-time setup: Configure kubectl
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1

# Start port forwarding (runs in background)
kubectl port-forward svc/aura-api 8080:8080 &

# Test API locally
curl http://localhost:8080/health/detailed

# View logs
kubectl logs -f deployment/aura-api

# Stop port forwarding
pkill -f "port-forward.*aura-api"
```

## Security Controls

| Control | Implementation |
|---------|----------------|
| **Authentication** | IAM via aws-iam-authenticator |
| **Authorization** | Kubernetes RBAC + IAM policies |
| **Encryption in Transit** | TLS for kubectl, TLS for database connections |
| **Audit Logging** | CloudTrail + Kubernetes audit logs |
| **Network Isolation** | VPC private subnets, no public endpoints |
| **Credential Management** | No persistent credentials (IAM temporary tokens) |

## References

- [ADR-002](ADR-002-vpc-endpoints-strategy.md) - VPC Endpoints over NAT Gateways
- [ADR-003](ADR-003-eks-ec2-nodes-for-govcloud.md) - EKS EC2 Nodes for GovCloud
- `deploy/kubernetes/aura-api/` - Kubernetes manifests
- `deploy/config/.env.example` - Environment configuration
