# Deployment Guide for Users

This guide explains how Aura Platform deployments work, including environment types, test environments, and how to interact with the deployment system.

---

## Deployment Overview

Aura provides several deployment contexts to ensure your code changes are safe before reaching production.

```
Development --> Test Environment --> Sandbox --> HITL Approval --> Production
```

---

## Environment Types

### Production Environment

The live environment where approved changes are deployed.

| Characteristic | Description |
|----------------|-------------|
| Access | Restricted to approved deployments |
| Isolation | Fully isolated from test environments |
| Monitoring | Full observability and alerting |
| Changes | Require HITL approval (always) |

### Test Environments

Self-service environments for validating changes before production.

| Environment Type | TTL | Cost/Day | Approval |
|------------------|-----|----------|----------|
| **Quick Test** | 4 hours | $0.10 | Auto-approved |
| **Standard** | 24 hours | $0.30-$1.20 | Auto-approved |
| **Extended** | 7 days | $0.80 | HITL required |
| **Compliance** | 24 hours | $2.50 | HITL required |

### Sandbox Environments

Isolated environments where Aura tests generated patches:

| Feature | Description |
|---------|-------------|
| Purpose | Validate patches before approval |
| Lifecycle | Automatic creation and cleanup |
| Isolation | Network-isolated from production |
| Duration | Until validation completes |

---

## Self-Service Test Environments

### Creating a Test Environment

1. Navigate to **Environments** in the sidebar
2. Click **Create Environment**
3. Select a template:

| Template | Description | Cost |
|----------|-------------|------|
| **Quick Test** | EKS namespace for rapid testing | $0.10/day |
| **Python FastAPI** | Python API development | $0.50/day |
| **React Frontend** | Frontend development | $0.30/day |
| **Full Stack** | Complete API + UI | $1.20/day |
| **Data Pipeline** | Extended data processing | $0.80/day |

4. Configure options:
   - Environment name
   - TTL (time-to-live)
   - Resource allocation
5. Click **Create**

### Environment Workflow

```
Request Submitted
       |
       v
+----------------+
| Quota Check    |  <-- Verify within limits
+----------------+
       |
       v
+----------------+
| HITL Check     |  <-- Based on env type
+----------------+
       |
       v
+----------------+
| Provisioning   |  <-- Create resources
+----------------+
       |
       v
+----------------+
| Ready          |  <-- Environment available
+----------------+
       |
       v
+----------------+
| TTL Expires    |  <-- Auto-cleanup
+----------------+
```

### Viewing Your Environments

The Environments page shows:

| Section | Information |
|---------|-------------|
| **Active** | Currently running environments |
| **Pending** | Environments being provisioned |
| **Recent** | Recently terminated environments |
| **Quota** | Usage against your limits |

### Environment Actions

| Action | Description |
|--------|-------------|
| **View Details** | See environment configuration |
| **Connect** | Get connection information |
| **Extend TTL** | Request more time |
| **Terminate** | End the environment early |

---

## Quotas and Limits

### Default Quotas

| Limit | Default Value |
|-------|---------------|
| Concurrent environments | 3 |
| Monthly budget | $500 |
| Daily budget | $50 |

### Checking Your Quota

1. Navigate to **Environments**
2. View the **Quota Display** card
3. See:
   - Environments used / total
   - Budget spent / limit
   - Time until reset

### Requesting More Quota

Contact your administrator to request increased limits.

---

## Sandbox Testing

### How Sandboxes Work

When a patch is generated:

1. **Sandbox Created**: Isolated environment provisioned
2. **Patch Applied**: Changes deployed to sandbox
3. **Tests Run**: Automated test suites execute
4. **Results Collected**: Pass/fail and metrics gathered
5. **Sandbox Destroyed**: Environment cleaned up

### Sandbox Isolation Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| **Container** | Isolated container | Quick tests |
| **VPC** | Dedicated VPC | Standard testing |
| **Full** | Complete isolation | Compliance testing |

### Viewing Sandbox Results

1. Navigate to **Approvals**
2. Click on a pending patch
3. View the **Sandbox Results** tab:
   - Test pass/fail status
   - Execution logs
   - Resource usage
   - Security scan results

---

## Deployment Modes

### Agent Orchestrator Deployment

How agents are deployed affects latency and cost:

| Mode | Latency | Cost | Best For |
|------|---------|------|----------|
| **On-Demand** | Higher (cold start) | Lowest (pay-per-use) | Low volume |
| **Warm Pool** | Low (instant) | Low (fixed) | Consistent use |
| **Hybrid** | Low + burst | Low + burst | Variable load |

### Checking Current Mode

1. Navigate to **Settings > Orchestrator**
2. View the current deployment mode
3. See operational status

### Switching Modes

1. Navigate to **Settings > Orchestrator**
2. Select new mode
3. Review impact
4. Click **Apply**

Note: There is a 5-minute cooldown between mode changes.

---

## Scheduled Provisioning

### What is Scheduled Provisioning?

Pre-create environments for planned testing windows.

### Creating a Schedule

1. Navigate to **Environments**
2. Click **Schedule Environment**
3. Configure:
   - Template
   - Start time
   - Duration
4. Click **Schedule**

### Managing Schedules

View and modify scheduled environments:

| Field | Description |
|-------|-------------|
| Scheduled Time | When it will start |
| Status | Pending, Active, Completed |
| Template | What type of environment |
| Actions | Cancel, Modify |

---

## EKS Namespace Environments

### Quick Test Namespaces

For rapid API prototyping and unit testing:

| Feature | Specification |
|---------|---------------|
| Provisioning Time | < 5 minutes |
| Default TTL | 4 hours |
| Isolation | Kubernetes namespace |
| Cost | $0.10/day |

### What You Get

- Dedicated Kubernetes namespace
- Resource quotas (CPU, memory, pods)
- Network policies for isolation
- Auto-generated kubeconfig

### Connecting to Your Namespace

1. Click **Connect** on your environment
2. Download the kubeconfig
3. Use kubectl:

```bash
export KUBECONFIG=/path/to/downloaded/kubeconfig
kubectl get pods
```

---

## Template Marketplace

### Available Templates

Standard templates for common use cases:

| Category | Templates |
|----------|-----------|
| **Backend** | Python FastAPI, Node.js Express, Go API |
| **Frontend** | React, Vue, Angular |
| **Full Stack** | API + UI combinations |
| **Data** | Data pipeline, ML inference |
| **Testing** | Load testing, integration testing |

### Submitting Custom Templates

1. Navigate to **Environments > Templates**
2. Click **Submit Template**
3. Provide:
   - Template name and description
   - CloudFormation/Terraform definition
   - Resource requirements
   - Estimated cost
4. Submit for approval

Templates require HITL approval before publishing.

---

## Cost Management

### Understanding Costs

Test environments incur costs based on:

| Factor | Impact |
|--------|--------|
| Resource size | Larger = more expensive |
| Duration | Longer = more expensive |
| Type | Compliance > Standard > Quick |

### Viewing Cost Data

1. Navigate to **Environments**
2. View the cost widget
3. See:
   - Current month spend
   - Budget remaining
   - Per-environment costs

### Cost Optimization Tips

1. **Use Quick Test when possible**: Lowest cost option
2. **Don't exceed TTL needs**: Terminate early if done
3. **Share environments**: Collaborate on single env
4. **Schedule during off-peak**: Some costs vary by time

---

## Approvals and Deployments

### The Approval Flow

```
Patch Generated
       |
       v
+----------------+
| Sandbox Test   |  <-- Automated validation
+----------------+
       |
       v
+----------------+
| Review Queue   |  <-- Await human review
+----------------+
       |
       v
+----------------+
| Approval       |  <-- Human decision
+----------------+
       |
       +--------+--------+
       |                 |
       v                 v
  Approved          Rejected
       |                 |
       v                 v
  Deploy to         Feedback
  Production        Provided
```

### Approval Requirements

Varies by your organization's autonomy policy:

| Patch Severity | Full HITL | Critical HITL | Audit Only |
|----------------|-----------|---------------|------------|
| CRITICAL | Yes | Yes | No |
| HIGH | Yes | Yes | No |
| MEDIUM | Yes | No | No |
| LOW | Yes | No | No |

### Guardrails (Always Require Approval)

These operations always need human approval:

- Production deployment
- Credential modification
- Access control changes
- Database migration
- Infrastructure changes

---

## Monitoring Deployments

### Deployment Dashboard

View deployment status:

| Status | Meaning |
|--------|---------|
| **Queued** | Waiting for resources |
| **In Progress** | Deploying |
| **Succeeded** | Completed successfully |
| **Failed** | Deployment failed |
| **Rolled Back** | Reverted to previous |

### Deployment Logs

View detailed logs:

1. Click on a deployment
2. View the **Logs** tab
3. See:
   - Step-by-step progress
   - Error messages
   - Timing information

### Rollback

If a deployment fails:

1. The system automatically rolls back
2. Previous version restored
3. Alert sent to team

---

## Best Practices

### For Test Environments

1. **Use appropriate type**: Quick for small tests, Extended for complex validation
2. **Set realistic TTLs**: Don't over-provision
3. **Clean up manually if done early**: Save costs
4. **Monitor quota**: Plan ahead for testing needs

### For Deployments

1. **Review sandbox results**: Understand what was tested
2. **Check security scans**: Look for introduced issues
3. **Understand the change**: Read the diff and explanation
4. **Approve with confidence**: Ask questions if unsure

### For Cost Control

1. **Use Quick Test by default**: Cheapest option
2. **Terminate unused environments**: Don't let them expire
3. **Review weekly costs**: Catch anomalies early
4. **Set budget alerts**: Get notified before overspend

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Getting Started](./getting-started.md) | Platform basics |
| [Security & Compliance](./security-compliance.md) | HITL and approvals |
| [Configuration](./configuration.md) | Environment settings |
| [Troubleshooting](./troubleshooting.md) | Deployment issues |
