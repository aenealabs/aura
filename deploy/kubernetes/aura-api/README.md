# Aura API Kubernetes Deployment

Kubernetes manifests for deploying the Project Aura FastAPI application to EKS.

## Architecture Decision

This deployment follows [ADR-011: VPC Access via EKS Deployment](../../../docs/architecture-decisions/ADR-011-vpc-access-via-eks-deployment.md), which chose EKS deployment over bastion hosts for secure VPC resource access.

## Prerequisites

1. **EKS Cluster**: `aura-cluster-${ENV}` deployed and accessible
2. **ECR Repository**: `aura-api-${ENV}` repository created
3. **kubectl**: Configured with EKS cluster access
4. **Docker/Podman**: For building container images

## Quick Start

### 1. Generate Environment Config

```bash
# Generate Kustomize overlays from CloudFormation outputs
./deploy/scripts/generate-k8s-config.sh ${ENV} ${REGION}

# Examples:
./deploy/scripts/generate-k8s-config.sh dev us-east-1
./deploy/scripts/generate-k8s-config.sh qa us-east-1
./deploy/scripts/generate-k8s-config.sh prod us-gov-west-1
```

### 2. Configure kubectl

```bash
aws eks update-kubeconfig --name aura-cluster-${ENV} --region ${AWS_REGION} --profile aura-admin
```

### 3. Build and Push Docker Image

```bash
# From repository root
cd /path/to/aura

# Login to ECR (replace with your account/region)
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build image
docker build -t aura-api:latest -f deploy/docker/api/Dockerfile.api .

# Tag and push
docker tag aura-api:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-api-${ENV}:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-api-${ENV}:latest
```

### 4. Deploy to EKS

```bash
# Deploy using environment overlay
kubectl apply -k deploy/kubernetes/aura-api/overlays/${ENV}/

# Verify deployment
kubectl get pods -l app=aura-api
kubectl get svc aura-api
```

### 4. Access API Locally

```bash
# Port forward to localhost
kubectl port-forward svc/aura-api 8080:8080

# In another terminal, test the API
curl http://localhost:8080/health
curl http://localhost:8080/health/detailed
```

## Files

| File | Description |
|------|-------------|
| `configmap.yaml` | Database endpoints and application configuration |
| `deployment.yaml` | API pod specification with health checks |
| `service.yaml` | ClusterIP service for internal access |
| `serviceaccount.yaml` | Service account for IRSA (IAM Roles for Service Accounts) |
| `kustomization.yaml` | Kustomize configuration for easy deployment |

## Configuration

Environment variables are managed via ConfigMap. Update `configmap.yaml` for:

- Database endpoints (Neptune, OpenSearch)
- AWS region and environment
- Application settings (log level, clone path)

For secrets (API keys, passwords), use:
- Kubernetes Secrets, or
- AWS Secrets Manager with IRSA

## IRSA Setup (IAM Roles for Service Accounts)

To enable AWS service access from the API pod:

1. Create IAM role with trust policy for the service account
2. Attach policies for DynamoDB, Bedrock, Secrets Manager
3. Update `serviceaccount.yaml` with the role ARN annotation

Example trust policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/oidc.eks.${AWS_REGION}.amazonaws.com/id/${OIDC_PROVIDER_ID}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.${AWS_REGION}.amazonaws.com/id/${OIDC_PROVIDER_ID}:sub": "system:serviceaccount:default:aura-api"
        }
      }
    }
  ]
}
```

## Troubleshooting

### View Logs

```bash
kubectl logs -f deployment/aura-api
```

### Check Pod Status

```bash
kubectl describe pod -l app=aura-api
```

### Restart Deployment

```bash
kubectl rollout restart deployment/aura-api
```

### Delete and Redeploy

```bash
kubectl delete -k deploy/kubernetes/aura-api/
kubectl apply -k deploy/kubernetes/aura-api/
```

## Security

- Runs as non-root user (UID 1000)
- No privilege escalation allowed
- All capabilities dropped
- Health checks enabled for automatic recovery
- IRSA for AWS credentials (no static credentials)
