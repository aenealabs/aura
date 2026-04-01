# Deployment Issues

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document covers infrastructure and deployment problems for Project Aura, including CloudFormation failures, EKS issues, container problems, and CI/CD pipeline errors. These issues primarily affect self-hosted deployments but some topics apply to SaaS customers using connected infrastructure.

---

## CloudFormation Issues

### AURA-INF-001: Stack Deployment Failed

**Symptoms:**
- CloudFormation stack shows `CREATE_FAILED` or `UPDATE_ROLLBACK_COMPLETE`
- Deployment pipeline fails with stack error
- Individual resources fail to create

**Common Failure Reasons:**

| Failure Reason | Description | Resolution |
|----------------|-------------|------------|
| Resource limit exceeded | AWS service quota reached | Request quota increase |
| Invalid parameter | Parameter value incorrect | Validate parameter |
| Dependency failed | Dependent resource failed | Fix dependency first |
| IAM permission denied | Insufficient deployment permissions | Add IAM permissions |
| Resource already exists | Naming conflict | Change resource name or import |

**Diagnostic Steps:**

```bash
# Get stack events (most recent first)
aws cloudformation describe-stack-events \
  --stack-name aura-${LAYER}-${ENV} \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table

# Get detailed stack status
aws cloudformation describe-stacks \
  --stack-name aura-${LAYER}-${ENV} \
  --query 'Stacks[0].[StackStatus,StackStatusReason]'

# View template validation errors
aws cloudformation validate-template \
  --template-body file://deploy/cloudformation/template.yaml
```

**Resolution by Error Type:**

**1. Resource Limit Exceeded:**

```bash
# Check current service quotas
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-1216C47A  # VPCs per Region

# Request quota increase
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-1216C47A \
  --desired-value 10
```

**2. IAM Permission Denied:**

```bash
# Check what permissions are needed
aws cloudformation describe-stack-events \
  --stack-name aura-${LAYER}-${ENV} \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].ResourceStatusReason'

# Common missing permissions for Aura deployment:
# - cloudformation:CreateStack
# - cloudformation:UpdateStack
# - iam:CreateRole
# - iam:AttachRolePolicy
# - ec2:CreateVpc
# - eks:CreateCluster
```

**3. Resource Already Exists:**

```bash
# Option 1: Import existing resource into stack
aws cloudformation create-change-set \
  --stack-name aura-${LAYER}-${ENV} \
  --change-set-name import-existing \
  --change-set-type IMPORT \
  --resources-to-import ResourceType=AWS::S3::Bucket,LogicalResourceId=AuraBucket,ResourceIdentifier='{\"BucketName\":\"existing-bucket\"}' \
  --template-body file://template.yaml

# Option 2: Delete existing resource (if safe)
aws s3 rb s3://conflicting-bucket-name --force

# Option 3: Change resource name in template
# Edit template to use different naming convention
```

**4. Rollback Stuck:**

```bash
# Continue rollback for stuck stacks
aws cloudformation continue-update-rollback \
  --stack-name aura-${LAYER}-${ENV} \
  --resources-to-skip FailedResource1 FailedResource2

# Delete stack if unrecoverable
aws cloudformation delete-stack \
  --stack-name aura-${LAYER}-${ENV}
```

---

### AURA-INF-002: Stack Update Blocked

**Symptoms:**
- Stack shows `UPDATE_IN_PROGRESS` for extended period
- Error: "Stack is in UPDATE_IN_PROGRESS state"
- Unable to make changes to stack

**Diagnostic Steps:**

```bash
# Check current stack status
aws cloudformation describe-stacks \
  --stack-name aura-${LAYER}-${ENV} \
  --query 'Stacks[0].StackStatus'

# Check ongoing operations
aws cloudformation describe-stack-events \
  --stack-name aura-${LAYER}-${ENV} \
  --max-items 10 \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,LogicalResourceId]' \
  --output table

# Check for drift
aws cloudformation detect-stack-drift \
  --stack-name aura-${LAYER}-${ENV}
```

**Resolution:**

```bash
# Wait for current operation to complete (recommended)
aws cloudformation wait stack-update-complete \
  --stack-name aura-${LAYER}-${ENV}

# If stuck >1 hour, cancel update (may cause rollback)
aws cloudformation cancel-update-stack \
  --stack-name aura-${LAYER}-${ENV}
```

---

## EKS Cluster Issues

### AURA-INF-003: EKS Node Not Ready

**Symptoms:**
- Nodes show `NotReady` status
- Pods stuck in `Pending` state
- Node conditions show failures

**Diagnostic Steps:**

```bash
# Check node status
kubectl get nodes -o wide

# Get node conditions
kubectl describe node ${NODE_NAME} | grep -A20 "Conditions:"

# Check node events
kubectl get events --field-selector involvedObject.kind=Node

# Check kubelet logs (requires SSH access)
journalctl -u kubelet -n 100 --no-pager

# Check EC2 instance status
aws ec2 describe-instance-status \
  --instance-ids ${INSTANCE_ID} \
  --query 'InstanceStatuses[0].[InstanceState.Name,SystemStatus.Status,InstanceStatus.Status]'
```

**Common Conditions and Fixes:**

| Condition | Status | Cause | Resolution |
|-----------|--------|-------|------------|
| Ready | False | Node unhealthy | Check kubelet, network |
| MemoryPressure | True | Memory exhausted | Add memory or evict pods |
| DiskPressure | True | Disk full | Clean disk or expand volume |
| PIDPressure | True | Too many processes | Restart node or reduce pods |
| NetworkUnavailable | True | CNI plugin issue | Restart aws-node daemonset |

**Resolution:**

```bash
# Drain and restart unhealthy node
kubectl drain ${NODE_NAME} --ignore-daemonsets --delete-emptydir-data
kubectl uncordon ${NODE_NAME}

# Force restart node group (EKS managed)
aws eks update-nodegroup-config \
  --cluster-name aura-cluster-${ENV} \
  --nodegroup-name aura-general-${ENV} \
  --scaling-config minSize=0,maxSize=0,desiredSize=0

# Wait, then scale back up
aws eks update-nodegroup-config \
  --cluster-name aura-cluster-${ENV} \
  --nodegroup-name aura-general-${ENV} \
  --scaling-config minSize=2,maxSize=10,desiredSize=2

# Restart CNI plugin
kubectl rollout restart daemonset/aws-node -n kube-system
```

---

### AURA-INF-004: EKS API Server Unreachable

**Symptoms:**
- `kubectl` commands fail with connection errors
- Error: "Unable to connect to the server"
- EKS console shows cluster healthy

**Causes:**
- Network connectivity issues
- Expired kubeconfig credentials
- VPN or firewall blocking access
- Cluster endpoint access settings

**Diagnostic Steps:**

```bash
# Check kubeconfig context
kubectl config current-context

# Verify cluster endpoint
aws eks describe-cluster \
  --name aura-cluster-${ENV} \
  --query 'cluster.endpoint'

# Test network connectivity
curl -k https://${CLUSTER_ENDPOINT}/healthz

# Check endpoint access configuration
aws eks describe-cluster \
  --name aura-cluster-${ENV} \
  --query 'cluster.resourcesVpcConfig.[endpointPublicAccess,endpointPrivateAccess]'
```

**Resolution:**

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name aura-cluster-${ENV} \
  --region ${AWS_REGION}

# If private endpoint only, ensure VPN/DirectConnect is active
# Or update to allow public access temporarily:
aws eks update-cluster-config \
  --name aura-cluster-${ENV} \
  --resources-vpc-config endpointPublicAccess=true

# Check security group allows your IP
aws ec2 describe-security-groups \
  --group-ids ${CLUSTER_SG} \
  --query 'SecurityGroups[0].IpPermissions'
```

---

## Container Issues

### AURA-INF-005: Image Pull Failed

**Symptoms:**
- Pods stuck in `ImagePullBackOff` or `ErrImagePull`
- Error: "Failed to pull image"
- Container registry authentication errors

**Diagnostic Steps:**

```bash
# Get pod events
kubectl describe pod ${POD_NAME} -n aura-system | grep -A10 "Events:"

# Check image name and tag
kubectl get pod ${POD_NAME} -n aura-system -o jsonpath='{.spec.containers[*].image}'

# Test ECR authentication
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# List available image tags
aws ecr list-images \
  --repository-name aura-api \
  --query 'imageIds[*].imageTag'
```

**Common Errors and Fixes:**

| Error | Cause | Resolution |
|-------|-------|------------|
| `repository does not exist` | Wrong ECR repo name | Verify repository name |
| `denied: Your authorization token has expired` | ECR token expired | Refresh ECR credentials |
| `manifest unknown` | Tag does not exist | Verify image tag |
| `x509: certificate signed by unknown authority` | TLS issue | Configure trusted CA |

**Resolution:**

```bash
# Refresh ECR credentials for EKS
kubectl delete secret ecr-credentials -n aura-system --ignore-not-found
kubectl create secret docker-registry ecr-credentials \
  --docker-server=${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-login-password --region ${AWS_REGION}) \
  -n aura-system

# Ensure IRSA is configured for ECR access
kubectl describe serviceaccount aura-api -n aura-system | grep Annotations

# Force pod restart to pull new image
kubectl rollout restart deployment/aura-api -n aura-system
```

---

### AURA-INF-006: Container Crash Loop

**Symptoms:**
- Pod status shows `CrashLoopBackOff`
- Container restarts repeatedly
- Application fails to start

**Diagnostic Steps:**

```bash
# Get pod status and restart count
kubectl get pods -n aura-system -o wide

# Check container logs (current and previous)
kubectl logs ${POD_NAME} -n aura-system --tail=100
kubectl logs ${POD_NAME} -n aura-system --previous --tail=100

# Check resource usage
kubectl top pod ${POD_NAME} -n aura-system

# Check for OOMKilled
kubectl describe pod ${POD_NAME} -n aura-system | grep -A5 "Last State:"
```

**Common Causes and Resolutions:**

**1. OOMKilled (Out of Memory):**

```bash
# Increase memory limits
kubectl patch deployment ${DEPLOYMENT} -n aura-system --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "4Gi"}]'
```

**2. Readiness/Liveness Probe Failure:**

```bash
# Check probe configuration
kubectl get deployment ${DEPLOYMENT} -n aura-system -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}'

# Adjust probe timing if startup is slow
kubectl patch deployment ${DEPLOYMENT} -n aura-system --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds", "value": 60}]'
```

**3. Configuration Error:**

```bash
# Check environment variables
kubectl exec ${POD_NAME} -n aura-system -- env | sort

# Check mounted secrets/configmaps
kubectl describe pod ${POD_NAME} -n aura-system | grep -A20 "Mounts:"
```

**4. Dependency Not Ready:**

```bash
# Check init containers
kubectl logs ${POD_NAME} -n aura-system -c init-check-db

# Check service dependencies
kubectl exec ${POD_NAME} -n aura-system -- nslookup neptune.aura.local
kubectl exec ${POD_NAME} -n aura-system -- nc -zv opensearch.aura.local 9200
```

---

## CI/CD Pipeline Issues

### AURA-INF-007: CodeBuild Failed

**Symptoms:**
- CodeBuild project shows FAILED status
- Deployment pipeline stopped
- Build logs show errors

**Diagnostic Steps:**

```bash
# Get recent build status
aws codebuild batch-get-builds \
  --ids $(aws codebuild list-builds-for-project \
    --project-name aura-${LAYER}-deploy-${ENV} \
    --max-items 5 \
    --query 'ids' --output text) \
  --query 'builds[*].[id,buildStatus,phases[-1].phaseStatus]' \
  --output table

# Get build logs
aws codebuild batch-get-builds \
  --ids ${BUILD_ID} \
  --query 'builds[0].logs.deepLink'

# Check for running builds (to avoid conflicts)
aws codebuild list-builds-for-project \
  --project-name aura-${LAYER}-deploy-${ENV} \
  --query 'ids[0]'
```

**Common Failures:**

| Phase | Error | Resolution |
|-------|-------|------------|
| PROVISIONING | Insufficient capacity | Retry or use different compute type |
| DOWNLOAD_SOURCE | Git authentication failed | Update CodeBuild service role |
| INSTALL | Dependency resolution failed | Check buildspec install commands |
| PRE_BUILD | cfn-lint validation failed | Fix CloudFormation template errors |
| BUILD | CloudFormation deployment failed | See AURA-INF-001 |
| POST_BUILD | Test failure | Review test output in logs |

**Resolution:**

```bash
# Retry failed build
aws codebuild start-build \
  --project-name aura-${LAYER}-deploy-${ENV} \
  --environment-variables-override name=FORCE_REDEPLOY,value=true

# Check and fix buildspec
cat deploy/buildspecs/buildspec-${LAYER}.yml

# Update service role permissions if needed
aws iam attach-role-policy \
  --role-name aura-codebuild-${LAYER}-role \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess  # Example, use least privilege
```

---

### AURA-INF-008: Concurrent Build Conflict

**Symptoms:**
- Build fails with "Stack update in progress"
- Multiple builds attempting same stack
- Inconsistent deployment state

**Diagnostic Steps:**

```bash
# Check for concurrent builds
aws codebuild list-builds-for-project \
  --project-name aura-${LAYER}-deploy-${ENV} \
  --query 'ids[:5]' \
  --output text | xargs -I{} aws codebuild batch-get-builds \
    --ids {} \
    --query 'builds[*].[id,currentPhase,buildStatus]' \
    --output table

# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name aura-${LAYER}-${ENV} \
  --query 'Stacks[0].StackStatus'
```

**Resolution:**

```bash
# Wait for in-progress build to complete
aws codebuild batch-get-builds --ids ${IN_PROGRESS_BUILD_ID} \
  --query 'builds[0].currentPhase'

# Stop conflicting build if needed
aws codebuild stop-build --id ${CONFLICTING_BUILD_ID}

# Wait for CloudFormation to stabilize
aws cloudformation wait stack-update-complete \
  --stack-name aura-${LAYER}-${ENV}
```

**Prevention:**

1. Always check for running builds before starting new ones
2. Use build queuing in CodePipeline
3. Implement build locks using DynamoDB or S3

---

## Kubernetes Manifest Issues

### AURA-INF-009: Invalid Manifest Syntax

**Symptoms:**
- kubectl apply fails with syntax error
- ArgoCD shows "OutOfSync" with error
- Kustomize build fails

**Diagnostic Steps:**

```bash
# Validate YAML syntax
yamllint deploy/kubernetes/aura-api/base/deployment.yaml

# Dry-run apply
kubectl apply --dry-run=client -f deploy/kubernetes/aura-api/base/

# Validate with kustomize
kustomize build deploy/kubernetes/aura-api/overlays/${ENV}

# Check for unexpanded variables
grep -r '\${' deploy/kubernetes/aura-api/
```

**Common Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| "unknown field" | API version mismatch | Update apiVersion |
| "invalid type" | Wrong value type | Check schema |
| "unmarshal error" | YAML syntax error | Fix indentation |
| "duplicate key" | Repeated key | Remove duplicate |

**Resolution:**

```bash
# Fix YAML syntax issues
# Common issue: tabs vs spaces (use spaces)
sed -i 's/\t/  /g' deploy/kubernetes/aura-api/base/deployment.yaml

# Validate against Kubernetes schema
kubectl apply --dry-run=server -f manifest.yaml

# Use kustomize properly (don't store expanded manifests)
# Deploy using overlays, not duplicated base files
kustomize build deploy/kubernetes/aura-api/overlays/${ENV} | kubectl apply -f -
```

---

### AURA-INF-010: Resource Quota Exceeded

**Symptoms:**
- Pods stuck in Pending
- Error: "exceeded quota"
- Namespace resource limits reached

**Diagnostic Steps:**

```bash
# Check namespace resource quota
kubectl get resourcequota -n aura-system

# Check current usage
kubectl describe resourcequota -n aura-system

# Check pod resource requests
kubectl get pods -n aura-system -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources.requests}{"\n"}{end}'
```

**Resolution:**

```bash
# Increase namespace quota (requires admin)
kubectl edit resourcequota aura-resource-quota -n aura-system

# Or delete low-priority pods to free resources
kubectl delete pod ${LOW_PRIORITY_POD} -n aura-system

# Scale down non-critical deployments
kubectl scale deployment monitoring-agent -n aura-system --replicas=1
```

---

## Network Issues

### AURA-INF-011: VPC Endpoint Unreachable

**Symptoms:**
- AWS service calls timeout
- Error: "Could not connect to the endpoint URL"
- Services work via NAT but not VPC endpoint

**Diagnostic Steps:**

```bash
# List VPC endpoints
aws ec2 describe-vpc-endpoints \
  --filters Name=vpc-id,Values=${VPC_ID} \
  --query 'VpcEndpoints[*].[ServiceName,State,VpcEndpointId]' \
  --output table

# Check endpoint security groups
aws ec2 describe-vpc-endpoints \
  --vpc-endpoint-ids ${ENDPOINT_ID} \
  --query 'VpcEndpoints[0].Groups'

# Test connectivity from pod
kubectl exec -it ${POD_NAME} -n aura-system -- \
  nc -zv vpce-xxx.s3.us-east-1.vpce.amazonaws.com 443
```

**Resolution:**

```bash
# Verify security group allows traffic
aws ec2 authorize-security-group-ingress \
  --group-id ${ENDPOINT_SG} \
  --protocol tcp \
  --port 443 \
  --source-group ${POD_SG}

# Check route tables include endpoint
aws ec2 describe-route-tables \
  --route-table-ids ${ROUTE_TABLE_ID} \
  --query 'RouteTables[0].Routes'

# Verify DNS resolution works
kubectl exec -it ${POD_NAME} -n aura-system -- \
  nslookup s3.us-east-1.amazonaws.com
```

---

### AURA-INF-012: DNS Resolution Failed

**Symptoms:**
- Service names not resolving
- Error: "Name or service not known"
- External DNS works but internal fails

**Diagnostic Steps:**

```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check dnsmasq pods (if deployed)
kubectl get pods -n kube-system -l app=dnsmasq

# Test DNS resolution
kubectl run -it --rm dns-test --image=busybox --restart=Never -- \
  nslookup kubernetes.default.svc.cluster.local

kubectl run -it --rm dns-test --image=busybox --restart=Never -- \
  nslookup neptune.aura.local

# Check DNS configuration
kubectl run -it --rm dns-test --image=busybox --restart=Never -- \
  cat /etc/resolv.conf
```

**Resolution:**

```bash
# Restart CoreDNS
kubectl rollout restart deployment/coredns -n kube-system

# Restart dnsmasq if deployed
kubectl rollout restart daemonset/dnsmasq -n kube-system

# Verify CoreDNS ConfigMap
kubectl get configmap coredns -n kube-system -o yaml

# Check for DNS policy issues in pods
kubectl get pod ${POD_NAME} -n aura-system -o jsonpath='{.spec.dnsPolicy}'
```

---

## Quick Reference: Deployment Commands

### Stack Deployment

```bash
# Deploy single stack
aws cloudformation deploy \
  --stack-name aura-${LAYER}-${ENV} \
  --template-file deploy/cloudformation/${TEMPLATE}.yaml \
  --parameter-overrides Environment=${ENV} \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

# Trigger CodeBuild deployment (recommended)
aws codebuild start-build \
  --project-name aura-${LAYER}-deploy-${ENV}
```

### Kubernetes Deployment

```bash
# Deploy using kustomize
kustomize build deploy/kubernetes/aura-api/overlays/${ENV} | kubectl apply -f -

# Deploy using kubectl
kubectl apply -k deploy/kubernetes/aura-api/overlays/${ENV}

# Rollback deployment
kubectl rollout undo deployment/aura-api -n aura-system

# Check rollout status
kubectl rollout status deployment/aura-api -n aura-system
```

### Container Operations

```bash
# Build and push image
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

docker build -t aura-api:${TAG} -f Dockerfile .
docker tag aura-api:${TAG} ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-api:${TAG}
docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-api:${TAG}
```

---

## Related Documentation

- [Troubleshooting Index](./index.md)
- [Common Issues](./common-issues.md)
- [Performance Issues](./performance-issues.md)
- [Operations Guide](../operations/index.md)
- [Architecture Overview](../architecture/system-overview.md)

---

*Last updated: January 2026 | Version 1.0*
