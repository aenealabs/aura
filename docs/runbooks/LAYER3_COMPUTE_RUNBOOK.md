# Layer 3: Compute Runbook

**Layer:** 3 - Compute
**CodeBuild Project:** `aura-compute-deploy-{env}`
**Buildspec:** `deploy/buildspecs/buildspec-compute.yml`
**Estimated Deploy Time:** 15-20 minutes (EKS cluster creation)

---

## Overview

The Compute layer provisions the EKS (Elastic Kubernetes Service) cluster with managed node groups. This is the core container orchestration platform for all application workloads.

---

## Resources Deployed

| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-eks-{env}` | eks.yaml | EKS Cluster (K8s 1.34), OIDC Provider, Managed Node Group (t3.medium, 2-5 nodes), EKS Access Entries, CloudWatch Container Insights | 15-20 min |

### Planned Additions (per BUILDSPEC_COMPLEXITY_ANALYSIS.md)
| Stack Name | Template | Resources | Deploy Time |
|------------|----------|-----------|-------------|
| `aura-acm-certificate-{env}` | acm-certificate.yaml | ACM Certificate (aenealabs.com) | 2-5 min |
| `aura-alb-controller-{env}` | alb-controller.yaml | ALB Controller IRSA Role | 1-2 min |

---

## Dependencies

### Prerequisites (Must exist before deployment)
- Layer 1 (Foundation): VPC, Subnets, Security Groups, IAM Roles
- Security Group: `aura-eks-sg-{env}`, `aura-eks-nodes-sg-{env}`
- IAM Role: `aura-eks-cluster-role-{env}`, `aura-eks-node-role-{env}`

### Downstream Dependencies
- Layer 4 (Application): Requires EKS cluster, OIDC provider
- Layer 7 (Sandbox): May use EKS for sandbox workloads
- Frontend/API Services: Deployed to EKS

---

## Deployment

### Trigger Deployment
```bash
aws codebuild start-build --project-name aura-compute-deploy-dev --region us-east-1
```

### Monitor Progress
```bash
# Get latest build ID
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name aura-compute-deploy-dev \
  --query 'ids[0]' --output text)

# Check build status
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,Phase:currentPhase}' --output table

# Stream logs
aws logs tail /aws/codebuild/aura-compute-deploy-dev --follow
```

### Verify Deployment
```bash
# Check EKS stack status
aws cloudformation describe-stacks --stack-name aura-eks-dev \
  --query 'Stacks[0].StackStatus' --output text

# Check EKS cluster status
aws eks describe-cluster --name aura-cluster-dev \
  --query 'cluster.status' --output text

# Check node group status
aws eks describe-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev \
  --query 'nodegroup.status' --output text
```

---

## Troubleshooting

### Issue: EKS Cluster Creation Timeout

**Symptoms:**
- Stack stuck in CREATE_IN_PROGRESS for >25 minutes
- Cluster status: "CREATING"

**Root Cause:** EKS cluster creation takes 10-15 minutes normally. If >20 min, there may be a capacity issue.

**Resolution:**
```bash
# Check cluster creation progress
aws eks describe-cluster --name aura-cluster-dev \
  --query 'cluster.{Status:status,CreatedAt:createdAt}'

# Check CloudFormation events for errors
aws cloudformation describe-stack-events --stack-name aura-eks-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' --output table

# If truly stuck, delete and recreate
aws cloudformation delete-stack --stack-name aura-eks-dev
aws cloudformation wait stack-delete-complete --stack-name aura-eks-dev
aws codebuild start-build --project-name aura-compute-deploy-dev
```

---

### Issue: Node Group Launch Failure

**Symptoms:**
```
CREATE_FAILED - Instances failed to join the kubernetes cluster
```

**Root Cause:** Security group rules, IAM permissions, or AMI issues.

**Resolution:**
```bash
# Check node group details
aws eks describe-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev \
  --query 'nodegroup.{Status:status,Health:health}'

# Check EC2 instances
aws ec2 describe-instances \
  --filters "Name=tag:eks:cluster-name,Values=aura-cluster-dev" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name,LaunchTime]' --output table

# Check instance system logs
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:eks:cluster-name,Values=aura-cluster-dev" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)

aws ec2 get-console-output --instance-id $INSTANCE_ID --output text | tail -100
```

---

### Issue: kubectl Cannot Connect to Cluster

**Symptoms:**
```
Unable to connect to the server: dial tcp: lookup ... on ...: no such host
```

**Root Cause:** kubeconfig not configured or VPC endpoint issues.

**Resolution:**
```bash
# Update kubeconfig
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1

# Verify config
kubectl config current-context

# Test connection
kubectl cluster-info

# If private cluster, ensure you're connected to VPC
# Check VPC endpoints for eks and eks-auth
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=*eks*" \
  --query 'VpcEndpoints[*].[ServiceName,State]' --output table
```

---

### Issue: OIDC Provider Not Created

**Symptoms:**
- IRSA roles fail with "AssumeRoleWithWebIdentity" errors
- No OIDC provider in IAM

**Root Cause:** OIDC provider creation failed or was skipped.

**Resolution:**
```bash
# Check if OIDC provider exists
aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[*].Arn' --output table

# Get EKS OIDC issuer URL
OIDC_URL=$(aws eks describe-cluster --name aura-cluster-dev \
  --query 'cluster.identity.oidc.issuer' --output text)

echo "OIDC URL: $OIDC_URL"

# If missing, create manually
eksctl utils associate-iam-oidc-provider \
  --cluster aura-cluster-dev \
  --approve
```

---

### Issue: Container Insights Not Collecting Metrics

**Symptoms:**
- No EKS metrics in CloudWatch
- Container Insights dashboard empty

**Root Cause:** amazon-cloudwatch-observability addon not installed or misconfigured.

**Resolution:**
```bash
# Check addon status
aws eks describe-addon \
  --cluster-name aura-cluster-dev \
  --addon-name amazon-cloudwatch-observability \
  --query 'addon.{Status:status,Version:addonVersion}'

# If missing, install
aws eks create-addon \
  --cluster-name aura-cluster-dev \
  --addon-name amazon-cloudwatch-observability \
  --addon-version v2.6.0-eksbuild.1

# Verify pods are running
kubectl get pods -n amazon-cloudwatch
```

---

### Issue: Node Capacity Insufficient

**Symptoms:**
```
Pods pending with "Insufficient cpu" or "Insufficient memory"
```

**Root Cause:** Node group at maximum capacity.

**Resolution:**
```bash
# Check current node count
kubectl get nodes

# Check node group scaling config
aws eks describe-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev \
  --query 'nodegroup.scalingConfig'

# Scale up manually
aws eks update-nodegroup-config \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev \
  --scaling-config minSize=2,maxSize=8,desiredSize=4
```

---

## Recovery Procedures

### Full Cluster Recovery

**WARNING:** This will delete the EKS cluster and all workloads.

```bash
# 1. Delete workloads first (optional - preserves configs)
kubectl delete all --all -n default
kubectl delete all --all -n aura-network-services

# 2. Delete node group (takes 5-10 min)
aws eks delete-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev

aws eks wait nodegroup-deleted \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev

# 3. Delete cluster (takes 5-10 min)
aws eks delete-cluster --name aura-cluster-dev
aws eks wait cluster-deleted --name aura-cluster-dev

# 4. Delete CloudFormation stack
aws cloudformation delete-stack --stack-name aura-eks-dev
aws cloudformation wait stack-delete-complete --stack-name aura-eks-dev

# 5. Redeploy
aws codebuild start-build --project-name aura-compute-deploy-dev
```

### Node Group Recovery Only

```bash
# Delete and recreate node group via CloudFormation
aws eks delete-nodegroup \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev

aws eks wait nodegroup-deleted \
  --cluster-name aura-cluster-dev \
  --nodegroup-name aura-system-ng-dev

# Redeploy (CloudFormation will recreate node group)
aws codebuild start-build --project-name aura-compute-deploy-dev
```

---

## Post-Deployment Verification

### 1. Verify Cluster Health

```bash
# Check cluster status
aws eks describe-cluster --name aura-cluster-dev \
  --query 'cluster.{Status:status,Version:version,Endpoint:endpoint}'

# Check nodes
kubectl get nodes -o wide

# Check system pods
kubectl get pods -n kube-system
```

### 2. Verify OIDC Provider

```bash
# Get OIDC provider ARN
aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[?contains(Arn, `eks`)]' --output table
```

### 3. Verify Container Insights

```bash
# Check CloudWatch agent pods
kubectl get pods -n amazon-cloudwatch

# Check Fluent Bit pods
kubectl get daemonset -n amazon-cloudwatch
```

### 4. Test kubectl Access

```bash
# Update kubeconfig
aws eks update-kubeconfig --name aura-cluster-dev

# Verify access
kubectl get namespaces
kubectl get nodes
kubectl cluster-info
```

---

## Stack Outputs Reference

### aura-eks-{env}
| Output | Description | Used By |
|--------|-------------|---------|
| ClusterName | EKS cluster name | Application, Frontend |
| ClusterEndpoint | EKS API endpoint | kubectl, CI/CD |
| ClusterSecurityGroupId | Cluster SG | Security rules |
| OIDCProviderArn | OIDC provider ARN | IRSA roles |
| OIDCProviderURL | OIDC issuer URL | IRSA roles |
| NodeGroupName | Node group name | Scaling |

---

## Kubernetes Cluster Access

### Configure kubectl
```bash
aws eks update-kubeconfig --name aura-cluster-dev --region us-east-1
```

### Verify Access
```bash
kubectl cluster-info
kubectl get nodes
kubectl get pods --all-namespaces
```

---

## K8s Deployment Issues

### Issue: Image Account Validation Failed (k8s-deploy)

**Symptoms:**
```
ERROR: deploy/kubernetes/aura-api/overlays/qa/kustomization.yaml uses account 123456789012 but expected 123456789012
FATAL: Image account validation failed - aborting deployment
```

**Root Cause:** Kubernetes overlay kustomization.yaml files contain ECR image references pointing to the wrong AWS account. This happens when `generate-k8s-config.sh` runs in the wrong account context.

**Resolution:**
```bash
# 1. Verify current account
aws sts get-caller-identity --query Account --output text

# 2. Regenerate configs with correct environment
./deploy/scripts/generate-k8s-config.sh qa us-east-1  # or prod us-gov-west-1

# 3. Verify overlays have correct account
grep "dkr.ecr" deploy/kubernetes/*/overlays/qa/kustomization.yaml | head -5

# 4. Re-trigger k8s-deploy
aws codebuild start-build --project-name aura-k8s-deploy-qa
```

**Prevention:** The k8s-deploy buildspec (PR #275) includes automatic validation. See `docs/deployment/CICD_SETUP_GUIDE.md#k8s-deploy-image-account-validation-pr-275` for details.

---

### Issue: ImagePullBackOff After k8s-deploy

**Symptoms:**
```
Warning  Failed     pod/aura-api-xxx  Failed to pull image: 403 Forbidden
```

**Root Cause:** Pod is trying to pull from wrong account's ECR, or ECR repository doesn't exist in target account.

**Resolution:**
```bash
# 1. Check which image pod is trying to pull
kubectl describe pod -l app=aura-api | grep Image

# 2. Verify ECR repo exists in target account
aws ecr describe-repositories --repository-names aura-api-qa

# 3. If missing, trigger docker-build
aws codebuild start-build \
  --project-name aura-docker-deploy-qa \
  --environment-variables-override name=BUILD_TARGET,value=aura-api

# 4. If image exists in wrong account, regenerate configs
./deploy/scripts/generate-k8s-config.sh qa us-east-1
```

---

## Related Documentation

- [LAYER1_FOUNDATION_RUNBOOK.md](./LAYER1_FOUNDATION_RUNBOOK.md) - Foundation dependencies
- [LAYER4_APPLICATION_RUNBOOK.md](./LAYER4_APPLICATION_RUNBOOK.md) - Application deployments
- [ARGOCD_RUNBOOK.md](../ARGOCD_RUNBOOK.md) - GitOps operations
- [CICD_SETUP_GUIDE.md](../deployment/CICD_SETUP_GUIDE.md) - K8s deploy validation details

---

**Document Version:** 1.1
**Last Updated:** 2026-01-11
