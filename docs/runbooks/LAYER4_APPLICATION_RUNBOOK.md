# Layer 4: Application Runbook

**Layer:** 4 - Application
**CodeBuild Project:** `aura-application-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-application.yml`
**Estimated Deploy Time:** 20-30 minutes (includes Docker builds)

---

## Overview

The Application layer deploys ECR repositories, Bedrock integration, IRSA roles, and Kubernetes workloads (dnsmasq, API service).

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-ecr-dnsmasq-{env}` | ecr-dnsmasq.yaml | ECR Repository for dnsmasq | 1-2 min |
| `aura-ecr-api-{env}` | ecr-api.yaml | ECR Repository for API | 1-2 min |
| `aura-bedrock-infrastructure-{env}` | aura-bedrock-infrastructure.yaml | Bedrock IAM Role, SNS Topic | 2-3 min |
| `aura-irsa-api-{env}` | irsa-aura-api.yaml | IRSA Role for aura-api ServiceAccount | 1-2 min |

### Kubernetes Resources
| Manifest | Namespace | Type |
|----------|-----------|------|
| dnsmasq-daemonset.yaml | aura-network-services | DaemonSet |
| dnsmasq-networkpolicy.yaml | aura-network-services | NetworkPolicy |
| aura-api/* | default | Deployment, Service, ConfigMap, ServiceAccount |

### Planned Additions
| Stack Name | Template | Resources |
|------------|----------|-----------|
| `aura-cognito-{env}` | cognito.yaml | User Pool, App Client, Groups |
| `aura-bedrock-guardrails-{env}` | bedrock-guardrails.yaml | Bedrock Guardrail |

---

## Dependencies

### Prerequisites
- Layer 1: VPC, Security Groups, ECR Base Images
- Layer 2: Neptune endpoint, OpenSearch endpoint (for ConfigMap)
- Layer 3: EKS cluster, OIDC provider

### Downstream Dependencies
- Frontend Service: Uses API endpoints
- HITL Workflow: Uses API for approvals

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-application-deploy-dev --region us-east-1
```

### Monitor Progress
```bash
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-application-deploy-dev \
  --query 'ids[0]' --output text)

aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase}' --output table

aws logs tail /aws/codebuild/aura-application-deploy-dev --follow
```

### Verify Deployment
```bash
# Check CloudFormation stacks
for STACK in aura-ecr-dnsmasq-dev aura-ecr-api-dev aura-bedrock-infrastructure-dev aura-irsa-api-dev; do
  STATUS=$(aws cloudformation describe-stacks --stack-name $STACK \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  echo "$STACK: $STATUS"
done

# Check Kubernetes resources
kubectl get pods -n aura-network-services
kubectl get pods -l app=aura-api
```

---

## Troubleshooting

### Issue: Docker Build Fails

**Symptoms:**
```
ERROR: failed to solve: failed to fetch oauth token
```

**Root Cause:** ECR login expired or not performed.

**Resolution:**
```bash
# Re-authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Retry build
aws codebuild start-build --project-name aura-application-deploy-dev
```

---

### Issue: Image Platform Mismatch (exec format error)

**Symptoms:**
```
exec format error
standard_init_linux.go: exec user process caused: exec format error
```

**Root Cause:** Image built for ARM (Apple Silicon) but EKS runs AMD64.

**Resolution:**
```bash
# Rebuild with correct platform (Podman-first per ADR-049)
podman build --platform linux/amd64 \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api-dev:latest \
  -f deploy/docker/api/Dockerfile.api .

podman push 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api-dev:latest

# Restart pods
kubectl rollout restart deployment/aura-api
```

---

### Issue: IRSA Role AssumeRoleWithWebIdentity Fails

**Symptoms:**
```
An error occurred (InvalidIdentityToken) when calling AssumeRoleWithWebIdentity
```

**Root Cause:** OIDC provider not configured or trust policy mismatch.

**Resolution:**
```bash
# Verify OIDC provider exists
aws iam list-open-id-connect-providers

# Check IRSA role trust policy
aws iam get-role --role-name aura-api-role-dev \
  --query 'Role.AssumeRolePolicyDocument'

# Verify service account annotation
kubectl get sa aura-api -o yaml | grep eks.amazonaws.com/role-arn
```

---

### Issue: dnsmasq DaemonSet Pods Not Starting

**Symptoms:**
```
CrashLoopBackOff or ImagePullBackOff for dnsmasq pods
```

**Root Cause:** Image not pushed to ECR or permissions issue.

**Resolution:**
```bash
# Check pod events
kubectl describe pod -l app=dnsmasq -n aura-network-services

# Verify image exists in ECR
aws ecr describe-images \
  --repository-name aura-dnsmasq-dev \
  --query 'imageDetails[*].[imageTags,imagePushedAt]' --output table

# If missing, rebuild and push (Podman-first per ADR-049)
podman build --platform linux/amd64 \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-dnsmasq-dev:latest \
  -f deploy/docker/dnsmasq/Dockerfile.alpine .

podman push 123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-dnsmasq-dev:latest

# Restart DaemonSet
kubectl rollout restart daemonset/dnsmasq -n aura-network-services
```

---

### Issue: Bedrock API Access Denied

**Symptoms:**
```
AccessDeniedException: User is not authorized to perform bedrock:InvokeModel
```

**Root Cause:** IAM role missing Bedrock permissions or model not enabled.

**Resolution:**
```bash
# Check Bedrock model access
aws bedrock list-foundation-models \
  --query 'modelSummaries[?contains(modelId, `claude`)].modelId'

# Check IAM role permissions
aws iam list-attached-role-policies \
  --role-name aura-bedrock-role-dev

# Verify model is enabled in Bedrock console
# Go to: AWS Console > Bedrock > Model access > Request access
```

---

## Recovery Procedures

### Redeploy Kubernetes Resources Only

```bash
# Delete and reapply K8s manifests
kubectl delete -k deploy/kubernetes/aura-api/
kubectl apply -k deploy/kubernetes/aura-api/

kubectl delete -f deploy/kubernetes/dnsmasq-daemonset.yaml
kubectl apply -f deploy/kubernetes/dnsmasq-daemonset.yaml
```

### Full Layer Recovery

```bash
# Delete CloudFormation stacks
for STACK in aura-irsa-api-dev aura-bedrock-infrastructure-dev aura-ecr-api-dev aura-ecr-dnsmasq-dev; do
  aws cloudformation delete-stack --stack-name $STACK
done

# Wait for deletions
for STACK in aura-irsa-api-dev aura-bedrock-infrastructure-dev aura-ecr-api-dev aura-ecr-dnsmasq-dev; do
  aws cloudformation wait stack-delete-complete --stack-name $STACK
done

# Redeploy
aws codebuild start-build --project-name aura-application-deploy-dev
```

---

## Post-Deployment Verification

### 1. Verify ECR Repositories
```bash
aws ecr describe-repositories \
  --query 'repositories[?starts_with(repositoryName, `aura-`)].repositoryName' --output table
```

### 2. Verify Kubernetes Pods
```bash
kubectl get pods -n aura-network-services
kubectl get pods -l app=aura-api
kubectl get pods -l app=aura-frontend
```

### 3. Verify IRSA
```bash
# Check service account has role annotation
kubectl get sa aura-api -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}'

# Test from pod
kubectl exec -it deploy/aura-api -- aws sts get-caller-identity
```

### 4. Test API Health
```bash
kubectl port-forward svc/aura-api 8080:80 &
curl http://localhost:8080/health
```

---

## Related Documentation

- [LAYER3_COMPUTE_RUNBOOK.md](./LAYER3_COMPUTE_RUNBOOK.md) - EKS dependencies
- [ARGOCD_RUNBOOK.md](../ARGOCD_RUNBOOK.md) - GitOps for K8s resources

---

**Document Version:** 1.0
**Last Updated:** 2025-12-09
