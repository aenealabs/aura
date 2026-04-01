# QA Deployment Checklist

**Last Updated:** 2026-01-11
**Environment:** QA (Commercial AWS)
**Region:** us-east-1
**Validation:** Image account validation enabled (PR #275)

---

## Pre-Deployment Prerequisites

### AWS Account Setup

- [ ] QA AWS account created and configured
- [ ] IAM roles for deployment created (AdministratorAccess or equivalent)
- [ ] AWS CLI configured with QA account credentials
- [ ] Verify correct account: `aws sts get-caller-identity`

### GitHub/Source Control

- [ ] Code merged to main branch
- [ ] All CI checks passing
- [ ] No blocking security vulnerabilities

### Tools Required

- [ ] AWS CLI v2 installed
- [ ] kubectl installed and configured
- [ ] Helm v3 installed
- [ ] jq installed (`brew install jq` or `apt install jq`)
- [ ] Docker/Podman available for image builds

---

## Phase 1: Account Bootstrap

### 1.1 Create GitHub CodeConnection

- [ ] Navigate to AWS Console → Developer Tools → Connections
- [ ] Create connection to GitHub repository
- [ ] Authorize and confirm connection
- [ ] Copy Connection ARN

### 1.2 Store CodeConnection ARN

```bash
aws ssm put-parameter \
  --name /aura/global/codeconnections-arn \
  --value "arn:aws:codeconnections:us-east-1:QA_ACCOUNT_ID:connection/xxx" \
  --type String \
  --region us-east-1
```

- [ ] SSM parameter created successfully

### 1.3 Deploy Account Bootstrap Stack

```bash
aws cloudformation deploy \
  --template-file deploy/cloudformation/account-bootstrap.yaml \
  --stack-name aura-account-bootstrap-qa \
  --parameter-overrides \
    Environment=qa \
    AdminRoleArn=arn:aws:iam::QA_ACCOUNT_ID:role/AWSAdministratorAccess \
    AlertEmail=alerts-qa@aenealabs.com \
    CodeConnectionsArn=arn:aws:codeconnections:us-east-1:QA_ACCOUNT_ID:connection/xxx \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

- [ ] Account bootstrap stack deployed successfully

---

## Phase 2: Infrastructure Layers (CodeBuild)

### 2.1 Bootstrap CodeBuild Projects

```bash
./deploy/scripts/bootstrap-fresh-account.sh qa us-east-1
```

- [ ] 20 CodeBuild projects created (including k8s-deploy and integration-test)

### 2.2 Deploy Foundation Layer (Layer 1)

```bash
aws codebuild start-build --project-name aura-foundation-deploy-qa
```

- [ ] Networking stack deployed (VPC, subnets, NAT gateways)
- [ ] Security stack deployed (security groups, KMS keys)
- [ ] IAM stack deployed (roles, policies)
- [ ] WAF stack deployed
- [ ] VPC Endpoints deployed

### 2.3 Deploy Data Layer (Layer 2)

```bash
aws codebuild start-build --project-name aura-data-deploy-qa
```

- [ ] Neptune cluster deployed
- [ ] OpenSearch domain deployed
- [ ] DynamoDB tables deployed
- [ ] S3 buckets deployed
- [ ] ElastiCache Redis deployed
- [ ] SSM parameters populated (verify below)

```bash
# Verify SSM parameters
aws ssm get-parameter --name /aura/qa/neptune-endpoint
aws ssm get-parameter --name /aura/qa/opensearch-endpoint
aws ssm get-parameter --name /aura/qa/redis-endpoint
```

### 2.4 Deploy Compute Layer (Layer 3)

```bash
aws codebuild start-build --project-name aura-compute-deploy-qa
```

- [ ] EKS cluster deployed
- [ ] Node groups deployed
- [ ] ECR repositories created
- [ ] IRSA roles configured

### 2.5 Deploy Application Layer (Layer 4)

```bash
aws codebuild start-build --project-name aura-application-deploy-qa
```

- [ ] API service infrastructure deployed
- [ ] Bedrock integration configured

### 2.6 Deploy Observability Layer (Layer 5)

```bash
aws codebuild start-build --project-name aura-observability-deploy-qa
```

- [ ] Secrets Manager configured
- [ ] CloudWatch dashboards deployed
- [ ] Cost alerts configured

### 2.7 Deploy Serverless Layer (Layer 6)

```bash
aws codebuild start-build --project-name aura-serverless-deploy-qa
```

- [ ] Lambda functions deployed
- [ ] Step Functions deployed
- [ ] EventBridge rules configured

### 2.8 Deploy Sandbox Layer (Layer 7)

```bash
aws codebuild start-build --project-name aura-sandbox-deploy-qa
```

- [ ] Sandbox infrastructure deployed
- [ ] HITL workflow configured

### 2.9 Deploy Security Layer (Layer 8)

```bash
aws codebuild start-build --project-name aura-security-deploy-qa
```

- [ ] AWS Config enabled
- [ ] GuardDuty enabled
- [ ] Security alerting configured

### 2.10 Deploy Deployment Pipeline (Step Functions)

```bash
./deploy/scripts/deploy-pipeline-infrastructure.sh qa us-east-1
```

- [ ] K8s Deploy CodeBuild project created (Layer 3.5)
- [ ] Integration Test CodeBuild project created (Layer 3.6)
- [ ] Step Functions state machine created
- [ ] SNS notification topic created

**Alternative: Use Pipeline for Remaining Phases**

Once the pipeline is deployed, you can trigger it to automate Phases 3-6:

```bash
# Get the pipeline ARN
PIPELINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name aura-deployment-pipeline-qa \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# Trigger full deployment (Phases 3-6 automated)
aws stepfunctions start-execution \
  --state-machine-arn ${PIPELINE_ARN} \
  --input '{"environment": "qa", "region": "us-east-1"}'
```

- [ ] Pipeline execution started
- [ ] Monitor in AWS Console: Step Functions > aura-deployment-pipeline-qa

> **Note:** If using the pipeline, skip to Phase 6 (Verification) after execution completes.

---

## Phase 3: Kubernetes Configuration (Manual Alternative)

### 3.1 Configure kubectl

```bash
aws eks update-kubeconfig --name aura-cluster-qa --region us-east-1
```

- [ ] kubectl configured for QA cluster
- [ ] Verify: `kubectl get nodes`

### 3.2 Generate Kubernetes Configs

```bash
./deploy/scripts/generate-k8s-config.sh qa us-east-1
```

- [ ] Script completed successfully
- [ ] Overlays generated for all services:
  - [ ] `deploy/kubernetes/aura-api/overlays/qa/`
  - [ ] `deploy/kubernetes/agent-orchestrator/overlays/qa/`
  - [ ] `deploy/kubernetes/memory-service/overlays/qa/`
  - [ ] `deploy/kubernetes/meta-orchestrator/overlays/qa/`
  - [ ] `deploy/kubernetes/aura-frontend/overlays/qa/`
  - [ ] `deploy/kubernetes/alb-controller/overlays/qa/`
  - [ ] `deploy/kubernetes/dnsmasq-blocklist-sync/overlays/qa/`
  - [ ] `deploy/kubernetes/test-configs/integration-test-config-qa.yaml`

### 3.3 Create ACM Certificate (Manual Step)

- [ ] Navigate to AWS ACM console
- [ ] Request certificate for QA domain (e.g., `qa.aura.aenealabs.com`, `qa.api.aenealabs.com`)
- [ ] Validate domain ownership (DNS or email)
- [ ] Copy certificate ARN
- [ ] Update ALB ingress manifests with certificate ARN:
  - `deploy/kubernetes/alb-controller/aura-api-ingress.yaml`
  - `deploy/kubernetes/alb-controller/aura-frontend-ingress.yaml`

---

## Phase 4: Container Images

### 4.1 Build and Push Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin QA_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push each service (or use CodeBuild)
# aura-api
docker build -t aura-api:latest -f deploy/docker/api/Dockerfile.api .
docker tag aura-api:latest QA_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/aura-api-qa:latest
docker push QA_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/aura-api-qa:latest
```

- [ ] aura-api image pushed
- [ ] agent-orchestrator image pushed
- [ ] memory-service image pushed
- [ ] meta-orchestrator image pushed
- [ ] aura-frontend image pushed

---

## Phase 5: Kubernetes Deployment

### 5.1 Install ALB Controller

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  -f deploy/kubernetes/alb-controller/overlays/qa/values.yaml
```

- [ ] ALB controller installed
- [ ] Verify: `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller`

### 5.2 Deploy Core Services

```bash
# Apply integration test config first
kubectl apply -f deploy/kubernetes/test-configs/integration-test-config-qa.yaml

# Deploy services
kubectl apply -k deploy/kubernetes/aura-api/overlays/qa/
kubectl apply -k deploy/kubernetes/agent-orchestrator/overlays/qa/
kubectl apply -k deploy/kubernetes/memory-service/overlays/qa/
kubectl apply -k deploy/kubernetes/meta-orchestrator/overlays/qa/
kubectl apply -k deploy/kubernetes/aura-frontend/overlays/qa/
```

- [ ] aura-api deployed and running
- [ ] agent-orchestrator deployed and running
- [ ] memory-service deployed and running
- [ ] meta-orchestrator deployed and running
- [ ] aura-frontend deployed and running

### 5.3 Deploy Network Services

```bash
kubectl apply -k deploy/kubernetes/dnsmasq-blocklist-sync/overlays/qa/
```

- [ ] dnsmasq-blocklist-sync deployed

### 5.4 Apply Ingress Rules

```bash
kubectl apply -f deploy/kubernetes/alb-controller/aura-api-ingress.yaml
kubectl apply -f deploy/kubernetes/alb-controller/aura-frontend-ingress.yaml
```

- [ ] ALB created in AWS
- [ ] Target groups healthy
- [ ] DNS records updated (Route 53)

---

## Phase 6: Verification

### 6.1 Health Checks

```bash
# Check all pods are running
kubectl get pods -A | grep -E 'aura|memory|orchestrator|frontend'

# Check services
kubectl get svc -A | grep -E 'aura|memory|orchestrator|frontend'

# Check ingress
kubectl get ingress -A
```

- [ ] All pods in Running state
- [ ] All services have endpoints
- [ ] Ingress has valid ALB address

**Note:** The k8s-deploy buildspec includes automatic image account validation (PR #275). If deployment failed with "Image account validation failed", verify overlays were generated with correct account ID. See `docs/deployment/CICD_SETUP_GUIDE.md#k8s-deploy-image-account-validation-pr-275` for troubleshooting.

### 6.2 Connectivity Tests

```bash
# Apply connectivity test pod
kubectl apply -f deploy/kubernetes/connectivity-test-pod.yaml

# Check results
kubectl logs connectivity-test -n aura -f

# Cleanup
kubectl delete pod connectivity-test -n aura
```

- [ ] Neptune connectivity: OK
- [ ] OpenSearch connectivity: OK

### 6.3 Integration Tests

```bash
# Run integration tests
kubectl apply -f deploy/kubernetes/integration-test-job.yaml

# Check results
kubectl logs job/aura-integration-tests -n aura

# Cleanup
kubectl delete job aura-integration-tests -n aura
```

- [ ] All integration tests passing

### 6.4 API Health

```bash
# Port forward to test locally
kubectl port-forward svc/aura-api 8080:8080

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/health/detailed
```

- [ ] `/health` returns 200
- [ ] `/health/detailed` shows all dependencies healthy

### 6.5 External Access

- [ ] `https://qa.api.aenealabs.com/health` accessible
- [ ] `https://qa.aura.aenealabs.com` accessible
- [ ] SSL certificate valid

---

## Phase 7: Security Verification

### 7.1 Security Scans

- [ ] No critical CVEs in container images
- [ ] GuardDuty findings reviewed
- [ ] AWS Config rules compliant

### 7.2 Access Controls

- [ ] IRSA roles properly scoped
- [ ] Network policies applied
- [ ] Security groups properly configured

### 7.3 Secrets Management

- [ ] No hardcoded secrets in ConfigMaps
- [ ] Secrets Manager integration working
- [ ] KMS encryption enabled

---

## Post-Deployment

### Documentation Updates

- [ ] Update `docs/PROJECT_STATUS.md` with QA deployment status
- [ ] Document any QA-specific configuration
- [ ] Update runbooks with QA endpoints

### Monitoring Setup

- [ ] CloudWatch alarms configured
- [ ] SNS notifications tested
- [ ] Dashboard accessible

### Handoff

- [ ] QA team notified
- [ ] Access credentials shared securely
- [ ] Known issues documented

---

## Rollback Procedure

If deployment fails:

```bash
# Delete Kubernetes resources
kubectl delete -k deploy/kubernetes/aura-api/overlays/qa/
kubectl delete -k deploy/kubernetes/agent-orchestrator/overlays/qa/
# ... repeat for other services

# For CloudFormation rollback, delete stacks in reverse order
aws cloudformation delete-stack --stack-name aura-security-qa
aws cloudformation delete-stack --stack-name aura-sandbox-qa
# ... continue in reverse layer order
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Pods stuck in Pending | Check node capacity: `kubectl describe nodes` |
| ImagePullBackOff | Verify ECR permissions and image exists |
| CrashLoopBackOff | Check logs: `kubectl logs <pod> --previous` |
| ALB not creating | Check ALB controller logs and IAM permissions |
| Neptune connection refused | Verify security groups and VPC endpoints |

### Useful Commands

```bash
# Get all events
kubectl get events --sort-by='.lastTimestamp'

# Describe problematic pod
kubectl describe pod <pod-name>

# Check ALB controller logs
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller

# Check IRSA configuration
kubectl describe serviceaccount <sa-name>
```

---

## References

- [QA_DEPLOYMENT_AUTOMATION.md](./QA_DEPLOYMENT_AUTOMATION.md) - Automation details
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - General deployment guide
- [MULTI_ACCOUNT_SETUP.md](./MULTI_ACCOUNT_SETUP.md) - Multi-account configuration
- [CICD_SETUP_GUIDE.md](./CICD_SETUP_GUIDE.md) - CI/CD pipeline documentation
