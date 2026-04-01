# Project Aura - Deployment Scripts

This directory contains automation scripts for deploying and managing Project Aura infrastructure.

## Scripts Overview

### AMI Management

#### `update-eks-node-ami.sh`

Automates AMI updates for EKS managed node groups with zero-downtime rolling updates.

**Usage:**
```bash
# Update all node groups (interactive)
./update-eks-node-ami.sh --cluster aura-cluster-dev --nodegroup all

# Update specific node group (automated)
./update-eks-node-ami.sh \
  --cluster aura-cluster-dev \
  --nodegroup aura-application-dev \
  --force

# Dry run to preview changes
./update-eks-node-ami.sh \
  --cluster aura-cluster-dev \
  --nodegroup all \
  --dry-run
```

**Scheduled Automation:**
```bash
# Add to crontab for weekly Sunday 2 AM updates
0 2 * * 0 /opt/aura/scripts/update-eks-node-ami.sh \
  --cluster aura-cluster-dev \
  --nodegroup all \
  --force
```

**Requirements:**
- AWS CLI installed and configured
- `jq` installed
- IAM permissions: `eks:DescribeCluster`, `eks:DescribeNodegroup`, `eks:UpdateNodegroupVersion`, `eks:DescribeUpdate`, `ssm:GetParameter`

---

### Security Hardening

#### `harden-eks-nodes.sh`

Applies security hardening to EKS worker nodes with two levels: commercial (dev/qa) and govcloud (production).

**Usage:**
```bash
# Commercial Cloud hardening (dev/qa)
sudo ./harden-eks-nodes.sh --level commercial

# GovCloud hardening (production - includes STIG + FIPS)
sudo ./harden-eks-nodes.sh --level govcloud

# Dry run to preview changes
sudo ./harden-eks-nodes.sh --level govcloud --dry-run

# Skip FIPS mode (GovCloud only)
sudo ./harden-eks-nodes.sh --level govcloud --skip-fips

# Skip STIG hardening (GovCloud only)
sudo ./harden-eks-nodes.sh --level govcloud --skip-stig
```

**Hardening Levels:**

**Commercial (dev/qa):**
- IMDSv2 enforcement
- SSH hardening (disable root, password auth)
- Automatic security updates
- CloudWatch logging and auditd
- Kernel parameter hardening
- File permission hardening

**GovCloud (production):**
- All commercial hardening +
- DISA STIG compliance
- FIPS 140-2 mode
- Enhanced password policies
- Account lockout enforcement
- Session timeout
- USB storage disabled
- FIPS-compliant cryptography

**Use in CloudFormation User Data:**
```yaml
UserData:
  Fn::Base64: !Sub |
    #!/bin/bash
    # Bootstrap EKS node
    /etc/eks/bootstrap.sh ${EKSCluster}

    # Apply security hardening
    if [ "${IsGovCloud}" == "true" ]; then
      /opt/aura/scripts/harden-eks-nodes.sh --level govcloud
    else
      /opt/aura/scripts/harden-eks-nodes.sh --level commercial
    fi
```

**Requirements:**
- Run as root (use `sudo`)
- Amazon Linux 2 or compatible OS
- Network connectivity for package installation

**Important Notes:**
- GovCloud hardening with FIPS mode requires system reboot to take effect
- Scripts are idempotent (safe to run multiple times)
- Test in dev environment before applying to production

---

### dnsmasq Network Services

#### `deploy-network-services.sh`

Deploys the 3-tier dnsmasq network services architecture to AWS.

**Usage:**
```bash
# Deploy to dev environment (2 AZs)
./deploy-network-services.sh dev 2

# Deploy to production (4 AZs)
./deploy-network-services.sh prod 4
```

**See:** `DNSMASQ_QUICK_START.md` for detailed deployment instructions.

---

## Deployment Workflow

### Initial Setup (Commercial Cloud - Dev/QA)

1. **Deploy Phase 1 Infrastructure**
   ```bash
   # Already deployed: VPC, Security Groups, IAM Roles
   aws cloudformation describe-stacks --stack-name aura-networking-dev
   ```

2. **Deploy EKS Cluster with Multi-Tier Node Groups**
   ```bash
   aws cloudformation create-stack \
     --stack-name aura-eks-dev \
     --template-body file://deploy/cloudformation/eks-multi-tier.yaml \
     --parameters \
       ParameterKey=Environment,ParameterValue=dev \
       ParameterKey=IsGovCloud,ParameterValue=false \
       ParameterKey=AppNodeCapacityType,ParameterValue=SPOT \
     --capabilities CAPABILITY_NAMED_IAM
   ```

3. **Configure kubectl**
   ```bash
   aws eks update-kubeconfig \
     --region us-east-1 \
     --name aura-cluster-dev
   ```

4. **Apply Security Hardening to Nodes**
   ```bash
   # Use Systems Manager Run Command to execute on all nodes
   aws ssm send-command \
     --document-name "AWS-RunShellScript" \
     --targets "Key=tag:NodeGroup,Values=aura-*-dev" \
     --parameters 'commands=["/opt/aura/scripts/harden-eks-nodes.sh --level commercial"]'
   ```

5. **Deploy dnsmasq Network Services**
   ```bash
   ./deploy/scripts/deploy-network-services.sh dev 2
   ```

6. **Set Up Automated AMI Updates**
   ```bash
   # Add to crontab
   crontab -e
   # Add: 0 2 * * 0 /opt/aura/scripts/update-eks-node-ami.sh --cluster aura-cluster-dev --nodegroup all --force
   ```

### GovCloud Migration (Production)

1. **Obtain AWS GovCloud Account**
   - Contact AWS Sales or use existing GovCloud account

2. **Deploy Phase 1 Infrastructure to GovCloud**
   ```bash
   aws cloudformation create-stack \
     --stack-name aura-networking-prod \
     --template-body file://deploy/cloudformation/networking.yaml \
     --region us-gov-west-1
   ```

3. **Deploy EKS Cluster to GovCloud**
   ```bash
   aws cloudformation create-stack \
     --stack-name aura-eks-prod \
     --template-body file://deploy/cloudformation/eks-multi-tier.yaml \
     --parameters \
       ParameterKey=Environment,ParameterValue=prod \
       ParameterKey=IsGovCloud,ParameterValue=true \
       ParameterKey=AppNodeCapacityType,ParameterValue=ON_DEMAND \
     --capabilities CAPABILITY_NAMED_IAM \
     --region us-gov-west-1
   ```

4. **Apply GovCloud Security Hardening**
   ```bash
   # Use Systems Manager Run Command
   aws ssm send-command \
     --document-name "AWS-RunShellScript" \
     --targets "Key=tag:NodeGroup,Values=aura-*-prod" \
     --parameters 'commands=["/opt/aura/scripts/harden-eks-nodes.sh --level govcloud"]' \
     --region us-gov-west-1
   ```

5. **Reboot Nodes to Activate FIPS Mode**
   ```bash
   # Drain nodes before reboot
   kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

   # Reboot via Systems Manager
   aws ssm send-command \
     --document-name "AWS-RunShellScript" \
     --targets "Key=tag:NodeGroup,Values=aura-*-prod" \
     --parameters 'commands=["reboot"]' \
     --region us-gov-west-1

   # Wait for nodes to come back online, then uncordon
   kubectl uncordon <node-name>
   ```

6. **Verify FIPS Mode**
   ```bash
   # SSH into node and check
   cat /proc/sys/crypto/fips_enabled
   # Should output: 1
   ```

---

## Troubleshooting

### AMI Update Script

**Issue:** Update fails with "No latest AMI version found"
**Solution:** Check SSM Parameter Store access, ensure node group has valid AMI type

**Issue:** Update times out
**Solution:** Increase `max_attempts` in script or run with `--force` flag

**Issue:** Nodes fail health checks after update
**Solution:** Check CloudWatch logs, verify security group rules, check pod readiness

### Security Hardening Script

**Issue:** FIPS mode enablement fails
**Solution:** Ensure `dracut-fips` package is available, check internet connectivity

**Issue:** SSH service fails to restart
**Solution:** Check `/etc/ssh/sshd_config` syntax with `sshd -t`

**Issue:** Application pods fail after hardening
**Solution:** Review kernel parameters, check if FIPS libraries are compatible

### General Debugging

**Check Node Status:**
```bash
kubectl get nodes
kubectl describe node <node-name>
```

**Check CloudWatch Logs:**
```bash
aws logs tail /aws/eks/aura-cluster-dev/cluster --follow
```

**Check Systems Manager Command Status:**
```bash
aws ssm list-command-invocations \
  --command-id <command-id> \
  --details
```

---

## Cost Optimization

### Development Environment

1. **Auto-scale to zero during off-hours**
   ```bash
   # Set desired capacity to 0 for non-system node groups
   aws eks update-nodegroup-config \
     --cluster-name aura-cluster-dev \
     --nodegroup-name aura-sandbox-dev \
     --scaling-config minSize=0,maxSize=10,desiredSize=0
   ```

2. **Use Spot instances**
   - Already configured in `eks-multi-tier.yaml` for dev environment
   - 70% cost savings vs On-Demand

3. **Schedule weekend shutdowns**
   ```bash
   # Friday 6 PM: Scale down
   0 18 * * 5 aws eks update-nodegroup-config ... --scaling-config desiredSize=0

   # Monday 6 AM: Scale up
   0 6 * * 1 aws eks update-nodegroup-config ... --scaling-config desiredSize=3
   ```

### Production Environment

1. **Purchase Savings Plans**
   - 3-year commitment: 50-60% savings
   - Target: $765/month vs $1,276 On-Demand

2. **Right-size instances**
   - Monitor CloudWatch metrics
   - Use AWS Compute Optimizer recommendations

3. **Use Graviton2 instances**
   - 20% better price/performance vs x86
   - Example: m6g.xlarge vs m5.xlarge

---

## Security Best Practices

1. **Least Privilege IAM Roles**
   - Only grant necessary permissions
   - Use IRSA (IAM Roles for Service Accounts) for pod-level permissions

2. **Network Isolation**
   - Use NetworkPolicy to restrict pod-to-pod communication
   - Private EKS endpoint in GovCloud

3. **Encryption at Rest**
   - EBS volumes encrypted with KMS
   - EKS secrets encrypted with KMS

4. **Encryption in Transit**
   - TLS 1.2+ for all communications
   - FIPS-approved algorithms in GovCloud

5. **Audit Logging**
   - EKS control plane logging enabled
   - CloudWatch Logs for all nodes
   - auditd for system-level auditing

6. **Regular Updates**
   - Weekly automated AMI updates
   - Security patch monitoring
   - CVE scanning

---

## Additional Resources

- **Cost Analysis:** `docs/EKS_COST_ANALYSIS.md`
- **GovCloud Migration:** `docs/cloud-strategy/GOVCLOUD_MIGRATION_SUMMARY.md`
- **CloudFormation Templates:** `deploy/cloudformation/`
- **Project Status:** `PROJECT_STATUS.md`
- **Architecture Guide:** `Claude.md`

---

**Last Updated:** November 17, 2025
**Maintained By:** Project Aura DevOps Team
