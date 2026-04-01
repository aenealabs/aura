# Project Aura - Production Deployment Checklist

**Last Updated:** 2026-01-15
**Target Environment:** AWS Commercial Cloud (dev/qa) → AWS GovCloud (production)

---

## Pre-Deployment Validation (REQUIRED - MUST PASS)

### Step 1: Smoke Tests (30 seconds)
```bash
pytest tests/smoke/test_platform_smoke.py -m smoke -v --tb=short -o addopts=""
```

**Exit Criteria:**
- ✅ All 10 smoke tests MUST pass
- ✅ Execution time < 30 seconds
- ❌ If ANY test fails → STOP, fix before deploying

**What's Tested:**
- AST Parser (code parsing works)
- Context Objects (data structures valid)
- Neptune Mock (graph database functional)
- MonitorAgent (metrics collection working)
- ObservabilityService (production monitoring ready)
- Performance (latency SLAs met)
- End-to-end workflow (complete analysis pipeline)

---

### Step 2: Automated Deployment Validation Script
```bash
./deploy/scripts/validate-deployment.sh [dev|qa|prod]
```

**Exit Criteria:**
- ✅ Exit code 0 (all checks passed)
- ❌ Exit code 1 → DEPLOYMENT BLOCKED

**5-Step Validation:**
1. **Smoke Tests** - Critical paths validated (30 seconds)
2. **Code Quality** - Ruff, Mypy, Bandit (10 seconds)
3. **Infrastructure** - AWS credentials, VPC exists (5 seconds)
4. **Performance Tests** - Latency SLAs met (10 seconds)
5. **Security Checks** - No secrets in repo (5 seconds)

**Total Time:** ~60 seconds

---

## Infrastructure Readiness

### AWS Prerequisites

#### Commercial Cloud (dev/qa)
- [ ] AWS credentials configured (`aws sts get-caller-identity`)
- [ ] VPC exists (vpc-0123456789abcdef0 for dev)
- [ ] IAM roles created (CloudFormation stack: aura-iam-dev)
- [ ] S3 buckets for CloudFormation templates
- [ ] Route53 hosted zone (optional for DNS)

#### GovCloud (production)
- [ ] GovCloud account setup
- [ ] FedRAMP High compliance review
- [ ] DISA STIG hardening applied
- [ ] FIPS 140-2 mode enabled
- [ ] Private EKS endpoints configured
- [ ] Bedrock (Claude) access approved (DoD IL-4/5)

---

### CloudFormation Stack Deployment Order

**Phase 1: Networking (DEPLOYED ✅)**
```bash
# Deploy VPC, subnets, security groups
aws cloudformation create-stack \
  --stack-name aura-networking-dev \
  --template-body file://deploy/cloudformation/networking.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev
```

**Phase 2: IAM Roles (DEPLOYED ✅)**
```bash
# Deploy IAM roles for EKS, Neptune, OpenSearch
aws cloudformation create-stack \
  --stack-name aura-iam-dev \
  --template-body file://deploy/cloudformation/iam.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

**Phase 3: EKS Cluster (PENDING)**
```bash
# Deploy multi-tier EKS cluster (GovCloud-compatible EC2 nodes)
aws cloudformation create-stack \
  --stack-name aura-eks-dev \
  --template-body file://deploy/cloudformation/eks-multi-tier.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=SystemNodeInstanceType,ParameterValue=t3.medium \
    ParameterKey=ApplicationNodeInstanceType,ParameterValue=t3.large \
    ParameterKey=SandboxNodeInstanceType,ParameterValue=t3.medium \
  --capabilities CAPABILITY_NAMED_IAM
```

**Phase 4: Neptune Graph Database (PENDING)**
```bash
# Deploy Neptune cluster
aws cloudformation create-stack \
  --stack-name aura-neptune-dev \
  --template-body file://deploy/cloudformation/neptune.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=InstanceClass,ParameterValue=db.r5.large
```

**Phase 5: OpenSearch Vector Database (PENDING)**
```bash
# Deploy OpenSearch cluster
aws cloudformation create-stack \
  --stack-name aura-opensearch-dev \
  --template-body file://deploy/cloudformation/opensearch.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=InstanceType,ParameterValue=r5.large.search
```

---

## Kubernetes Services Deployment

### dnsmasq Network Services (3-Tier Architecture)

**Tier 1: DaemonSet on EKS EC2 Nodes**
```bash
# Deploy dnsmasq to every EKS node (local DNS caching)
kubectl apply -f deploy/kubernetes/dnsmasq-daemonset.yaml

# Verify deployment
kubectl get daemonset dnsmasq -n kube-system
kubectl logs daemonset/dnsmasq -n kube-system --tail=20
```

**Tier 2: ECS Fargate VPC-Wide Service**
```bash
# Deploy centralized DNS service for entire VPC
aws ecs create-cluster --cluster-name aura-dnsmasq-dev

aws ecs register-task-definition \
  --cli-input-json file://deploy/ecs/dnsmasq-task-definition.json

aws ecs create-service \
  --cluster aura-dnsmasq-dev \
  --service-name dnsmasq-vpc-service \
  --task-definition dnsmasq-vpc:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

**Tier 3: Sandbox Network Orchestrator**
```bash
# Deploy sandbox DNS controller
kubectl apply -f deploy/kubernetes/sandbox-network-orchestrator.yaml

# Verify controller is running
kubectl get deployment sandbox-network-orchestrator -n aura-system
```

---

### Core Application Services

**Agent Orchestrator**
```bash
kubectl apply -f deploy/kubernetes/agent-orchestrator-deployment.yaml
kubectl get deployment agent-orchestrator -n aura

# Verify health
kubectl port-forward deployment/agent-orchestrator 8080:8080 &
curl http://localhost:8080/health
```

**Context Retrieval Service**
```bash
kubectl apply -f deploy/kubernetes/context-retrieval-deployment.yaml
kubectl get deployment context-retrieval -n aura

# Verify health
kubectl port-forward deployment/context-retrieval 8080:8080 &
curl http://localhost:8080/health/ready
```

---

## Monitoring & Observability Setup

### Prometheus Metrics Collection
```bash
# Deploy Prometheus
kubectl apply -f deploy/kubernetes/prometheus-deployment.yaml

# Deploy dnsmasq exporter (for Tier 1 monitoring)
kubectl apply -f deploy/kubernetes/dnsmasq-exporter.yaml

# Verify metrics endpoint
kubectl port-forward deployment/prometheus 9090:9090 &
curl http://localhost:9090/metrics
```

### CloudWatch Integration
```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name AuraProduction \
  --dashboard-body file://deploy/monitoring/cloudwatch-dashboard.json

# Create alarms
aws cloudwatch put-metric-alarm \
  --alarm-name AuraErrorRateHigh \
  --alarm-description "Error rate > 5%" \
  --metric-name ErrorRate \
  --namespace Aura \
  --statistic Average \
  --period 300 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789:aura-alerts
```

---

## Production Deployment Workflow

### Method 1: Canary Deployment (Netflix Style - RECOMMENDED)

**Step 1: Deploy Canary (5% traffic)**
```bash
# Scale canary deployment to 1 replica
kubectl scale deployment agent-orchestrator-canary --replicas=1

# Monitor for 10 minutes
watch -n 5 'curl -s http://agent-orchestrator/health/detailed | jq .golden_signals.errors'
```

**Step 2: Monitor Error Rate**
```bash
# Check error rate every minute
while true; do
  ERROR_RATE=$(curl -s http://agent-orchestrator/health/detailed | \
    jq '.golden_signals.errors."orchestrator.execute".error_rate')

  echo "Error rate: $ERROR_RATE"

  if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
    echo "ERROR RATE TOO HIGH - ROLLBACK"
    kubectl rollout undo deployment/agent-orchestrator
    exit 1
  fi

  sleep 60
done
```

**Step 3: Full Rollout (100% traffic)**
```bash
# If canary successful after 10 minutes
kubectl set image deployment/agent-orchestrator \
  orchestrator=aura:v2.1.0

kubectl rollout status deployment/agent-orchestrator

# Post-deployment health check
./deploy/scripts/post-deployment-health-check.sh
```

---

### Method 2: Blue-Green Deployment (Zero Downtime)

**Step 1: Deploy Green Environment**
```bash
# Deploy new version to green namespace
kubectl create namespace aura-green

kubectl apply -f deploy/kubernetes/ -n aura-green

# Wait for all pods ready
kubectl wait --for=condition=ready pod -l app=agent-orchestrator -n aura-green --timeout=300s
```

**Step 2: Smoke Test Green Environment**
```bash
# Port-forward to green environment
kubectl port-forward -n aura-green deployment/agent-orchestrator 8081:8080 &

# Run smoke tests against green
pytest tests/smoke/ -m smoke --base-url http://localhost:8081
```

**Step 3: Switch Traffic to Green**
```bash
# Update service selector to point to green deployment
kubectl patch service agent-orchestrator -n aura \
  -p '{"spec":{"selector":{"version":"green"}}}'

# Monitor for 5 minutes
curl http://agent-orchestrator.aura.local/health/detailed
```

**Step 4: Decommission Blue**
```bash
# If green is stable, delete blue namespace
kubectl delete namespace aura-blue
```

---

## Rollback Procedures

### Kubernetes Rollback (< 5 minutes)
```bash
# View deployment history
kubectl rollout history deployment/agent-orchestrator

# Rollback to previous version
kubectl rollout undo deployment/agent-orchestrator

# Rollback to specific version
kubectl rollout undo deployment/agent-orchestrator --to-revision=3

# Verify rollback successful
kubectl rollout status deployment/agent-orchestrator
curl http://agent-orchestrator.aura.local/health
```

### CloudFormation Rollback
```bash
# Rollback stack to previous template version
aws cloudformation cancel-update-stack --stack-name aura-eks-dev

# Or delete and recreate from known-good template
aws cloudformation delete-stack --stack-name aura-eks-dev
aws cloudformation wait stack-delete-complete --stack-name aura-eks-dev

# Redeploy from backup
aws cloudformation create-stack \
  --stack-name aura-eks-dev \
  --template-body file://deploy/cloudformation/eks-multi-tier.yaml.backup
```

---

## Post-Deployment Validation

### Health Check Verification
```bash
# Check all Kubernetes probes
kubectl get pods -n aura -o wide

# Check individual service health
curl http://agent-orchestrator.aura.local/health/live    # Liveness
curl http://agent-orchestrator.aura.local/health/ready   # Readiness
curl http://agent-orchestrator.aura.local/health/startup # Startup

# Detailed health metrics
curl http://agent-orchestrator.aura.local/health/detailed | jq .
```

### Performance Validation
```bash
# Run performance smoke tests
pytest tests/smoke/test_platform_smoke.py -m performance -v

# Check P95 latency
curl -s http://agent-orchestrator.aura.local/health/detailed | \
  jq '.golden_signals.latency."orchestrator.execute".p95'

# Expected: < 2s (SLA is 5s)
```

### End-to-End Workflow Test
```bash
# Submit real analysis job
curl -X POST http://agent-orchestrator.aura.local/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "https://github.com/example/test-repo",
    "branch": "main",
    "analysis_type": "security_scan"
  }'

# Monitor job progress
kubectl logs -f deployment/agent-orchestrator -n aura
```

---

## Environment Variables Validation

### Service Configuration Variables
```bash
# Verify required environment variables are set in ConfigMap
kubectl get configmap aura-service-config -n aura -o yaml

# Expected variables (production values):
# - SUPPORT_EMAIL: support@aenealabs.com
# - PRICING_PAGE_URL: https://app.aenealabs.com/pricing
# - LICENSE_RENEWAL_URL: https://app.aenealabs.com/renew
# - GPU_DASHBOARD_BASE_URL: https://app.aenealabs.com

# Verify environment variables are injected into pods
kubectl exec deployment/aura-api -n aura -- env | grep -E "(SUPPORT_EMAIL|PRICING_PAGE_URL|GPU_DASHBOARD_BASE_URL)"

# Verify AWS_ACCOUNT_ID is correctly detected
kubectl exec deployment/aura-api -n aura -- env | grep AWS_ACCOUNT_ID
```

**Environment Variables Checklist:**
- [ ] `SUPPORT_EMAIL` set to production email (NOT `support@aura.local`)
- [ ] `PRICING_PAGE_URL` set to production URL (NOT `*.aura.local`)
- [ ] `LICENSE_RENEWAL_URL` set to production URL
- [ ] `GPU_DASHBOARD_BASE_URL` set to production URL
- [ ] `AWS_ACCOUNT_ID` correctly detected via STS or environment variable

**Warning:** If any variable shows `*.aura.local` in production, update the ConfigMap immediately. These are development defaults and will cause user-facing issues.

---

## Security Validation

### Secrets Management
```bash
# Verify no secrets in git
./deploy/scripts/validate-deployment.sh prod | grep "secrets"

# Verify AWS Secrets Manager integration
aws secretsmanager get-secret-value \
  --secret-id aura/prod/neptune-credentials

# Verify IAM roles are correct
kubectl describe serviceaccount agent-orchestrator -n aura | grep "arn:aws:iam"
```

### Network Policy Verification
```bash
# Check NetworkPolicy is enforced
kubectl get networkpolicy -n aura

# Test isolation (should FAIL)
kubectl run test-pod --image=busybox -n aura -- \
  wget -O- http://169.254.169.254/latest/meta-data/

# Expected: Connection timeout (metadata service blocked)
```

---

## GovCloud-Specific Deployment Steps

### STIG Hardening
```bash
# Apply DISA STIG hardening to all EC2 nodes
./deploy/scripts/harden-eks-nodes.sh --level govcloud --cluster aura-cluster-prod

# Verify compliance
oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_stig \
  --results /tmp/stig-report.xml \
  /usr/share/xml/scap/ssg/content/ssg-rhel8-ds.xml
```

### FIPS 140-2 Mode
```bash
# Enable FIPS mode on all nodes
ansible-playbook -i inventory/govcloud-prod deploy/ansible/enable-fips.yml

# Verify FIPS mode enabled
ssh ec2-user@node-ip "cat /proc/sys/crypto/fips_enabled"
# Expected output: 1
```

### FedRAMP High Compliance
```bash
# Deploy compliance monitoring
kubectl apply -f deploy/kubernetes/fedramp-compliance-monitor.yaml

# Verify continuous monitoring
kubectl logs deployment/fedramp-compliance-monitor -n aura-compliance
```

---

## Success Criteria (Sign-Off)

### Pre-Deployment Sign-Off
- [ ] All 10 smoke tests passing (< 30 seconds)
- [ ] Deployment validation script exits 0
- [ ] Code quality checks passed (Ruff, Mypy, Bandit)
- [ ] No secrets in repository
- [ ] Infrastructure ready (VPC, IAM, credentials)
- [ ] Performance SLAs met (< 2s for parsing)

### Post-Deployment Sign-Off (Production)
- [ ] All Kubernetes pods READY (1/1)
- [ ] Health endpoints return 200 OK
- [ ] Error rate < 1% (threshold is 5%)
- [ ] P95 latency < 2s (threshold is 5s)
- [ ] Rollback tested (< 5 minutes)
- [ ] Monitoring dashboards configured
- [ ] Alerts configured (PagerDuty/Slack)
- [ ] End-to-end workflow successful
- [ ] Documentation updated

### GovCloud Production Sign-Off (ADDITIONAL)
- [ ] DISA STIG hardening applied
- [ ] FIPS 140-2 mode enabled
- [ ] FedRAMP High compliance verified
- [ ] Private EKS endpoints only
- [ ] Bedrock (Claude) access working
- [ ] Continuous compliance monitoring active
- [ ] Security audit logs enabled
- [ ] CMMC Level 3 controls documented

---

## Emergency Contact Information

### Development Team
- **Lead Engineer:** [Name] - [Email] - [Phone]
- **DevOps Lead:** [Name] - [Email] - [Phone]
- **Security Lead:** [Name] - [Email] - [Phone]

### Escalation Path
1. **On-Call Engineer** (PagerDuty)
2. **Engineering Manager**
3. **VP of Engineering**
4. **CTO**

### AWS Support
- **Support Level:** Enterprise
- **Account ID:** [AWS Account ID]
- **TAM (Technical Account Manager):** [Name] - [Email]

---

## Deployment Log Template

```markdown
# Deployment Log: [Version] to [Environment]

**Date:** YYYY-MM-DD
**Deployer:** [Name]
**Version:** v2.1.0
**Environment:** Production (GovCloud)

## Pre-Deployment Checks
- [x] Smoke tests passed (10/10) - 0.09s
- [x] Deployment validation script passed
- [x] Code quality checks passed
- [x] No secrets detected

## Deployment Timeline
- 10:00 AM - Started canary deployment (5% traffic)
- 10:10 AM - Canary stable, error rate 0.02%
- 10:15 AM - Scaling to 50% traffic
- 10:20 AM - 50% stable, error rate 0.01%
- 10:25 AM - Full rollout to 100%
- 10:30 AM - Post-deployment validation passed

## Metrics
- **Error Rate:** 0.01% (under 5% threshold) ✅
- **P95 Latency:** 1.2s (under 5s SLA) ✅
- **Uptime:** 100% during rollout ✅

## Issues Encountered
- None

## Rollback Plan
- Kubernetes rollout undo (< 5 minutes)

## Sign-Off
- [x] Engineering Lead: [Name]
- [x] DevOps Lead: [Name]
- [x] Security Lead: [Name]
```

---

## Quick Reference Commands

```bash
# Pre-deployment validation (60 seconds)
./deploy/scripts/validate-deployment.sh prod

# Deploy to production (canary)
kubectl scale deployment/agent-orchestrator-canary --replicas=1

# Monitor error rate
curl -s http://agent-orchestrator/health/detailed | jq .golden_signals.errors

# Rollback if needed
kubectl rollout undo deployment/agent-orchestrator

# Post-deployment validation
./deploy/scripts/post-deployment-health-check.sh
```

---

**Remember:** Ship early, monitor closely, rollback quickly.
