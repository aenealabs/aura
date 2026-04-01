# Alert Frequency Cost Optimization - Original Values

**Date of Change:** 2026-02-20
**Purpose:** Reduce AWS alerting costs by lowering evaluation/schedule frequencies for non-critical alerts.
**Revert Instructions:** Restore each setting to the "Original Value" column below, then redeploy the affected CloudFormation stacks.

---

## Priority 1: EventBridge Scheduler Frequency Reductions

| # | Template File | Resource (Logical ID) | Property | Original Value | Changed To | Line |
|---|---|---|---|---|---|---|
| 1 | `deploy/cloudformation/test-env-scheduler.yaml` | `SchedulerEventRule` | `ScheduleExpression` | `rate(15 minutes)` | `rate(1 hour)` | 198 |
| 2 | `deploy/cloudformation/scheduling-infrastructure.yaml` | `SchedulerDispatcherRule` | `ScheduleExpression` | `rate(5 minutes)` | `rate(15 minutes)` | 405 |
| 3 | `deploy/cloudformation/test-env-budgets.yaml` | `CostAggregatorSchedule` | `ScheduleExpression` | `rate(1 hour)` | `rate(6 hours)` | 372 |
| 4 | `deploy/cloudformation/runbook-agent.yaml` | `ProcessingSchedule` (Parameter Default) | `Default` | `rate(1 hour)` | `rate(6 hours)` | 44 |
| 5 | `deploy/cloudformation/hitl-scheduler.yaml` | `ScheduleExpression` (Parameter Default) | `Default` | `rate(1 hour)` | `rate(3 hours)` | 22 |
| 6 | `deploy/cloudformation/drift-detection.yaml` | `DriftDetectionSchedule` (Parameter Default) | `Default` | `rate(6 hours)` | `rate(1 day)` | 35 |
| 7 | `deploy/cloudformation/env-validator-drift-lambda.yaml` | `DriftDetectionRule` | `ScheduleExpression` | `rate(6 hours)` | `rate(1 day)` | 160 |
| 8 | `deploy/cloudformation/org-cost-monitoring.yaml` | `CostAggregatorSchedule` | `ScheduleExpression` | `rate(6 hours)` | `rate(1 day)` | 620 |

### Revert Commands (Priority 1)

To revert each template, restore the original value in the YAML file and redeploy:

```bash
# After restoring original values in the template files:
aws codebuild start-build --project-name aura-sandbox-deploy-dev      # test-env-scheduler (Layer 7)
aws codebuild start-build --project-name aura-serverless-deploy-dev   # scheduling-infrastructure, runbook-agent, hitl-scheduler (Layer 6)
aws codebuild start-build --project-name aura-sandbox-deploy-dev      # test-env-budgets (Layer 7)
aws codebuild start-build --project-name aura-security-deploy-dev     # drift-detection (Layer 8)
aws codebuild start-build --project-name aura-serverless-deploy-dev   # env-validator-drift-lambda (Layer 6)
aws codebuild start-build --project-name aura-observability-deploy-dev # org-cost-monitoring (Layer 5)
```

---

## Priority 2: CloudWatch Alarm Evaluation Period Changes

| # | Template File | Resource (Logical ID) | Property Changed | Original Value | Changed To | Line |
|---|---|---|---|---|---|---|
| 1 | `deploy/cloudformation/gpu-monitoring.yaml` | `GPUUnderutilizationAlarm` | `Period` | `3600` | `86400` | 399 |
| 1 | `deploy/cloudformation/gpu-monitoring.yaml` | `GPUUnderutilizationAlarm` | `EvaluationPeriods` | `6` | `1` | 400 |
| 2 | `deploy/cloudformation/monitoring.yaml` | `NeptuneLowTrafficAlarm` | `Period` | `300` | `3600` | 253 |
| 2 | `deploy/cloudformation/monitoring.yaml` | `NeptuneLowTrafficAlarm` | `EvaluationPeriods` | `3` | `2` | 254 |
| 3 | `deploy/cloudformation/aura-cost-alerts.yaml` | `BedrockDailyCostAlarm` | `EvaluationPeriods` | `1` | `7` | 202 |
| 4 | `deploy/cloudformation/test-env-monitoring.yaml` | `DailyCostAlarm` | `Period` | `3600` | `21600` | 337 |
| 5 | `deploy/cloudformation/test-env-monitoring.yaml` | `QuotaExceededAlarm` | `Period` | `3600` | `86400` | 413 |
| 6 | `deploy/cloudformation/realtime-monitoring.yaml` | `HITLTimeoutAlarm` | `Period` | `3600` | `10800` | 762 |
| 7 | `deploy/cloudformation/realtime-monitoring.yaml` | `RateLimitAlarm` | `Period` | `600` | `3600` | 892 |
| 8 | `deploy/cloudformation/gpu-monitoring.yaml` | `GPUSpotInterruptionAlarm` | `Period` | `3600` | `21600` | 338 |

### Revert Commands (Priority 2)

```bash
# After restoring original values in the template files:
aws codebuild start-build --project-name aura-observability-deploy-dev  # monitoring, aura-cost-alerts (Layer 5)
aws codebuild start-build --project-name aura-sandbox-deploy-dev        # test-env-monitoring (Layer 7)
aws codebuild start-build --project-name aura-compute-deploy-dev        # gpu-monitoring (Layer 3)
aws codebuild start-build --project-name aura-serverless-deploy-dev     # realtime-monitoring (Layer 6)
```

---

## Summary of Impact

**Original total evaluation frequency per day (approximate):**
- EventBridge schedulers: ~480 invocations/day
- CloudWatch alarm evaluations: ~1,200 evaluations/day

**After optimization:**
- EventBridge schedulers: ~100 invocations/day
- CloudWatch alarm evaluations: ~400 evaluations/day

**Estimated savings:** ~$20-35/month across dev/qa environments

---

## Unchanged (Security/Availability Critical - Do NOT Modify)

These alarms were explicitly excluded from changes:

| Alarm | Template | Period | Reason |
|---|---|---|---|
| `SecretsExposureAlarm` | `realtime-monitoring.yaml` | 60s | Security - immediate response |
| `OpenSearchClusterRedAlarm` | `monitoring.yaml` | 60s | Availability - cluster down |
| `InjectionAttemptAlarm` | `realtime-monitoring.yaml` | 300s | Security - active attack |
| `PromptInjectionAlarm` | `realtime-monitoring.yaml` | 300s | Security - AI threat |
| `LLMSecurityOperationMisuseAlarm` | `monitoring.yaml` | 300s | Security - agent misuse |
| `EKSHighCPUAlarm` | `monitoring.yaml` | 300s | Availability - compute |
| `BackupJobFailedAlarm` | `disaster-recovery.yaml` | 3600s | DR compliance |
