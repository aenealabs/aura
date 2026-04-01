# Human-in-the-Loop (HITL) Sandbox Architecture
**Version:** 2.2
**Date:** December 2025
**Status:** Design Specification for Enhanced Security Workflow

---

## 1. Executive Overview

This document specifies the enhanced architecture for Project Aura's autonomous vulnerability remediation system, incorporating **mandatory sandbox testing** and **human-in-the-loop (HITL) approval** workflows before production deployment.

> **Related Documentation:**
> - **ADR-016 Auto-Escalation:** `docs/architecture-decisions/ADR-016-hitl-auto-escalation-strategy.md` - Severity-based expiration handling
> - **Adaptive Security Intelligence Workflow:** `agent-config/agents/security-code-reviewer.md#adaptive-security-intelligence-workflow` - Proactive threat monitoring that triggers this HITL workflow
> - **System Architecture:** `SYSTEM_ARCHITECTURE.md` - Overall platform architecture
> - **Security Agent:** `agent-config/agents/security-code-reviewer.md` - Security review patterns and AI threat intelligence

### Strategic Value

| Enhancement | Security Benefit | Compliance Impact |
|-------------|-----------------|-------------------|
| **Sandbox Testing** | Validates patches in isolated environment before production | Prevents untested code from reaching production systems |
| **Human Approval Gate** | Senior engineers review AI-generated security patches | Satisfies SOX/CMMC requirements for change management approval |
| **AWS Notification** | Real-time alerts via SNS/SES for pending approvals | Ensures timely review and audit trail for compliance |
| **Rollback Capability** | Automated rollback if sandbox tests fail | Minimizes risk of service disruption |

---

## 2. Enhanced Architecture Components

### 2.1 New Microservices

| Service Name | Technology | Role | AWS Services |
|--------------|-----------|------|--------------|
| **Sandbox Orchestration Agent** | Python/AWS Step Functions | Provisions isolated ECS/Fargate environments for patch testing | ECS, Fargate, VPC |
| **HITL Approval Service** | AWS Step Functions + Lambda | Manages approval workflow and state transitions | Step Functions, Lambda, DynamoDB |
| **Notification Service** | Python/Lambda | Sends notifications to security team via SNS/SES | SNS, SES, Lambda |
| **Sandbox Test Runner** | Python/pytest | Executes comprehensive integration tests in sandbox | Fargate, CloudWatch |
| **Approval Dashboard Service** | React Component + API Gateway | Web interface for reviewing and approving/rejecting patches | API Gateway, Lambda, S3 |

### 2.2 Data Stores

| Store | Purpose | Technology |
|-------|---------|-----------|
| **Approval Request Table** | Tracks patch approval status and history | DynamoDB |
| **Sandbox Results Table** | Stores test results from sandbox executions | DynamoDB |
| **Audit Log** | Immutable record of all approval decisions | CloudWatch Logs / S3 |

---

## 3. Enhanced Vulnerability Remediation Workflow

### 3.1 Process Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: DETECTION & GENERATION                       │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [Reviewer Agent] Detects Vulnerability (e.g., SHA1)
         │
         ├─> [Orchestrator] Triggers Coder Agent
         │
         └─> [Coder Agent] Generates Security Patch (SHA1 → SHA256)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: SANDBOX PROVISIONING (NEW)                   │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [Sandbox Orchestrator] Creates Isolated ECS Environment
         │     - Provisions VPC with isolated subnets
         │     - Deploys Fargate task with patched code
         │     - Configures security groups (no production access)
         │
         └─> [Sandbox Ready] Environment ID: sandbox-{timestamp}-{uuid}
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: SANDBOX TESTING (NEW)                        │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [Sandbox Test Runner] Executes Test Suite
         │     - Unit tests (syntax validation)
         │     - Integration tests (API compatibility)
         │     - Security tests (SAST/SCA on patched code)
         │     - Performance tests (latency benchmarks)
         │
         ├─> [Results] All Tests Pass ✓ / Some Tests Fail ✗
         │
         └─> [DynamoDB] Store test results in Sandbox Results Table
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              STAGE 4: HUMAN-IN-THE-LOOP NOTIFICATION (NEW)               │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [HITL Service] Creates Approval Request
         │     - Approval ID: approval-{timestamp}-{uuid}
         │     - Status: PENDING_APPROVAL
         │     - Timeout: 24 hours (configurable)
         │
         ├─> [DynamoDB] Record approval request
         │
         ├─> [Notification Service] Sends AWS SNS Notification
         │     - Email to security team (via SES)
         │     - Slack webhook (optional)
         │     - Includes: Vulnerability details, patch diff, sandbox test results
         │
         └─> [Step Functions] Wait for Human Decision (Manual Approval Step)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 5: HUMAN APPROVAL DECISION (NEW)                │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [Approval Dashboard] Senior Engineer Reviews:
         │     - Original vulnerable code
         │     - AI-generated patch
         │     - Sandbox test results
         │     - Security scan results
         │     - Deployment plan
         │
         ├─> DECISION:
         │     [APPROVE] ──────────────┐
         │     [REJECT] ───────────┐   │
         │     [REQUEST CHANGES]   │   │
         │                         │   │
         │   ┌─────────────────────┘   │
         │   │                         │
         │   ▼                         ▼
         │ [Reject Path]          [Approve Path]
         │   │                         │
         │   ├─> Log rejection         ├─> Log approval
         │   ├─> Notify Orchestrator   ├─> Trigger deployment
         │   ├─> Cleanup sandbox       ├─> Continue to Stage 6
         │   └─> END                    │
         │                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 6: PRODUCTION DEPLOYMENT (GATED)                │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [CI/CD Pipeline] Triggered by approval
         │
         ├─> [Deployment] Apply patch to production codebase
         │     - Create feature branch
         │     - Commit approved patch
         │     - Run production CI/CD gates (SAST/SCA/ECR)
         │     - Deploy to staging (optional)
         │     - Deploy to production
         │
         ├─> [Monitor Agent] Track deployment metrics
         │
         └─> [Cleanup] Tear down sandbox environment
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 7: POST-DEPLOYMENT VERIFICATION                 │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ├─> [Validation] Verify patch is live in production
         │
         ├─> [Monitoring] Track for 24 hours:
         │     - Application errors
         │     - Performance degradation
         │     - Security events
         │
         ├─> [Audit Log] Record final status
         │
         └─> [Notification] Send completion notice to approver
```

---

## 4. Technical Implementation Details

### 4.1 Sandbox Orchestration Agent

**File:** `src/agents/sandbox_orchestrator.py`

**Responsibilities:**
- Provision isolated ECS/Fargate environments on-demand
- Deploy patched code to sandbox
- Manage sandbox lifecycle (create, test, destroy)
- Enforce network isolation (no production data access)

**Key Methods:**
```python
class SandboxOrchestrator:
    def provision_sandbox(self, patch_code: str, metadata: dict) -> str:
        """Creates isolated Fargate environment and returns sandbox_id"""

    def deploy_patch_to_sandbox(self, sandbox_id: str, patch_code: str) -> bool:
        """Deploys the AI-generated patch to sandbox environment"""

    def run_sandbox_tests(self, sandbox_id: str) -> dict:
        """Executes comprehensive test suite in sandbox"""

    def teardown_sandbox(self, sandbox_id: str) -> bool:
        """Destroys sandbox environment and cleans up resources"""
```

**AWS Resources Created per Sandbox:**
- ECS Task Definition (ephemeral)
- Fargate Service (1 task, isolated VPC)
- Security Group (deny all except internal testing)
- CloudWatch Log Group (sandbox-specific)

**Cost Optimization:**
- Fargate Spot instances for sandbox tasks
- Auto-teardown after 2 hours (configurable)
- Shared VPC with isolated subnets

---

### 4.2 HITL Approval Service

**File:** `src/services/hitl_approval_service.py`

**Responsibilities:**
- Create approval requests in DynamoDB
- Integrate with AWS Step Functions for manual approval
- Handle approval/rejection decisions
- Manage approval timeouts (default: 24 hours)

**Key Methods:**
```python
class HITLApprovalService:
    def create_approval_request(self, vulnerability_data: dict,
                                patch_code: str,
                                sandbox_results: dict) -> str:
        """Creates approval request and returns approval_id"""

    def notify_security_team(self, approval_id: str) -> bool:
        """Sends SNS notification to configured security team"""

    def process_approval_decision(self, approval_id: str,
                                  decision: str,
                                  approver_email: str,
                                  comments: str = "") -> dict:
        """Processes human decision (APPROVE/REJECT/REQUEST_CHANGES)"""

    def handle_timeout(self, approval_id: str) -> dict:
        """Handles approval timeout (auto-reject after 24 hours)"""
```

**DynamoDB Schema - Approval Request Table:**
```json
{
  "approval_id": "approval-2025-10-30-abc123",
  "timestamp": "2025-10-30T14:32:00Z",
  "status": "PENDING_APPROVAL | APPROVED | REJECTED | TIMEOUT",
  "vulnerability": {
    "type": "Weak Cryptography",
    "severity": "High",
    "original_code": "hashlib.sha1(...)",
    "cve_reference": null
  },
  "patch": {
    "code": "hashlib.sha256(...)",
    "diff_url": "s3://bucket/diffs/approval-abc123.diff",
    "loc_changed": 3
  },
  "sandbox_results": {
    "sandbox_id": "sandbox-2025-10-30-xyz789",
    "tests_passed": 47,
    "tests_failed": 0,
    "test_report_url": "s3://bucket/test-reports/sandbox-xyz789.html"
  },
  "approver_email": "senior.engineer@company.com",
  "approval_timestamp": "2025-10-30T15:45:00Z",
  "approver_comments": "Verified patch is correct. Approved for prod.",
  "ttl": 1730380800
}
```

---

### 4.3 Notification Service

**File:** `src/services/notification_service.py`

**Responsibilities:**
- Send email notifications via AWS SES
- Publish to SNS topics for multi-channel delivery
- Format rich notifications with patch details
- Track notification delivery status

**Email Template:**
```
Subject: [AURA SECURITY] Pending Approval: High-Severity Vulnerability Patch

Classification: CONFIDENTIAL

Dear Security Team,

Project Aura has detected and remediated a High-Severity vulnerability in the production codebase.
Human approval is required before deployment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VULNERABILITY DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type:              Weak Cryptographic Hash (SHA1)
Severity:          High
CMMC/SOX Impact:   Violates cryptography standard
Detected In:       DataProcessor.calculate_checksum() [line 24]
Detection Time:    2025-10-30 14:32:00 UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI-GENERATED PATCH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- return hashlib.sha1(data.encode()).hexdigest()
+ return hashlib.sha256(data.encode()).hexdigest()

Lines Changed:     3
Complexity:        Low

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SANDBOX TEST RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Environment:       sandbox-2025-10-30-xyz789
Tests Passed:      47 / 47 ✓
Security Scan:     No new vulnerabilities ✓
Performance:       Latency +2ms (acceptable) ✓

Full Report:       https://console.aws.amazon.com/aura/sandbox/xyz789

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTION REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Approval ID:       approval-2025-10-30-abc123
Timeout:           24 hours (auto-reject after 2025-10-31 14:32:00 UTC)

Review & Approve:  https://console.aws.amazon.com/aura/approvals/abc123

[APPROVE PATCH]    [REJECT PATCH]    [REQUEST CHANGES]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated notification from Project Aura.
For questions, contact: aura-support@company.com

Compliance: SOX/CMMC Audit Trail #AUR-2025-10-30-abc123
```

---

### 4.4 Expiration Processor (Scheduled Lambda)

**File:** `src/lambda/expiration_processor.py`
**CloudFormation:** `deploy/cloudformation/hitl-scheduler.yaml`

**Responsibilities:**
- Proactively scan PENDING approval requests hourly
- Send warning notifications at 75% of timeout period
- Escalate CRITICAL/HIGH severity requests to backup reviewers
- Expire MEDIUM/LOW severity requests and re-queue for future processing
- Maintain full audit trail of all state transitions

**Architecture Decision:** See `docs/architecture-decisions/ADR-016-hitl-auto-escalation-strategy.md`

**Escalation Logic:**
```python
class ExpirationProcessor:
    def process_expirations(self) -> ExpirationProcessingResult:
        """
        Hourly scheduled function that processes expired approval requests.

        Severity-Based Behavior:
        - CRITICAL/HIGH: Escalate to backup reviewer (max 2 escalations)
        - MEDIUM/LOW: Mark as EXPIRED and re-queue for next cycle

        Warning System:
        - At 75% of timeout, send warning notification
        - Gives original reviewer opportunity to respond
        """

    def _determine_action(self, request: ApprovalRequest) -> EscalationAction:
        """Determines ESCALATE, EXPIRE, or WARN based on severity and age."""

    def _escalate_request(self, request: ApprovalRequest) -> ExpirationResult:
        """Assigns to backup reviewer, resets timeout, sends notification."""

    def _expire_request(self, request: ApprovalRequest) -> ExpirationResult:
        """Marks request as EXPIRED, sends notification, re-queues."""
```

**Configuration Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `TIMEOUT_HOURS` | 24 | Hours before initial expiration |
| `ESCALATION_TIMEOUT_HOURS` | 12 | Shorter timeout for escalated requests |
| `WARNING_THRESHOLD_PERCENT` | 0.75 | Send warning at 75% of timeout |
| `MAX_ESCALATIONS` | 2 | Maximum escalations before final expiration |
| `BACKUP_REVIEWERS` | Configurable | Comma-separated reviewer email list |

**CloudFormation Resources:**
- `ExpirationProcessorFunction` - Lambda function (Python 3.11)
- `ExpirationScheduleRule` - EventBridge rule (`rate(1 hour)`)
- `ExpirationProcessorRole` - IAM role with DynamoDB, SNS, SES permissions
- `ExpirationProcessorLogGroup` - CloudWatch Logs (365 days prod / 90 days dev)
- `ExpirationProcessorErrorAlarm` - CloudWatch alarm for Lambda errors

**State Machine Integration:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                    EXPIRATION PROCESSING FLOW                         │
└──────────────────────────────────────────────────────────────────────┘
         │
    [Hourly EventBridge Trigger]
         │
         ▼
┌─────────────────────────────────────┐
│  Scan PENDING Approval Requests     │
└─────────────────────────────────────┘
         │
         ├─> [Age < 75% timeout] ──> No action, continue monitoring
         │
         ├─> [Age >= 75% timeout, warning_sent = false]
         │         │
         │         └──> Send Warning Notification
         │              Update warning_sent_at
         │
         └─> [Age >= 100% timeout]
                   │
                   ├─[CRITICAL/HIGH, escalation_count < 2]
                   │         │
                   │         └──> ESCALATE
                   │              - Assign to backup reviewer
                   │              - Reset timeout (12 hours)
                   │              - Increment escalation_count
                   │              - Send escalation notification
                   │
                   ├─[CRITICAL/HIGH, escalation_count >= 2]
                   │         │
                   │         └──> EXPIRE (max escalations reached)
                   │
                   └─[MEDIUM/LOW]
                             │
                             └──> EXPIRE
                                  - Update status to EXPIRED
                                  - Send expiration notification
                                  - Re-queue for next review cycle
```

**Notification Types:**
| Type | Recipient | Trigger |
|------|-----------|---------|
| Warning | Original reviewer | 75% of timeout reached |
| Escalation | Backup reviewer | CRITICAL/HIGH expired, escalation_count < MAX |
| Expiration | Security team | Request expired (MEDIUM/LOW or max escalations) |

---

### 4.5 Approval Dashboard (Frontend Extension)

**File:** `frontend/components/ApprovalDashboard.jsx`

**Features:**
- Real-time list of pending approvals
- Side-by-side code diff viewer
- Sandbox test results visualization
- One-click approve/reject buttons
- Comment/feedback form for requester

**UI Sections:**
1. **Pending Approvals List** - Table with approval ID, severity, age, timeout countdown
2. **Approval Detail View** - Full vulnerability context and patch details
3. **Test Results Panel** - Pass/fail status, test logs, performance metrics
4. **Decision Panel** - Approve/Reject/Request Changes with mandatory comment field
5. **Audit History** - Past approvals by user, filterable and searchable

---

## 5. AWS Step Functions State Machine

**File:** `deploy/step_functions/hitl_remediation_workflow.json`

```json
{
  "Comment": "HITL Vulnerability Remediation Workflow",
  "StartAt": "DetectVulnerability",
  "States": {
    "DetectVulnerability": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:reviewer-agent",
      "Next": "GeneratePatch"
    },
    "GeneratePatch": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:coder-agent",
      "Next": "ProvisionSandbox"
    },
    "ProvisionSandbox": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:sandbox-orchestrator",
      "ResultPath": "$.sandbox_id",
      "Next": "RunSandboxTests"
    },
    "RunSandboxTests": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:sandbox-test-runner",
      "ResultPath": "$.sandbox_results",
      "Next": "EvaluateTestResults"
    },
    "EvaluateTestResults": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.sandbox_results.all_tests_passed",
          "BooleanEquals": true,
          "Next": "CreateApprovalRequest"
        }
      ],
      "Default": "SandboxTestsFailed"
    },
    "SandboxTestsFailed": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:handle-test-failure",
      "Next": "TeardownSandbox"
    },
    "CreateApprovalRequest": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:hitl-approval-service",
      "ResultPath": "$.approval_id",
      "Next": "SendNotification"
    },
    "SendNotification": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:notification-service",
      "Next": "WaitForHumanApproval"
    },
    "WaitForHumanApproval": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:${region}:${account}:function:wait-for-approval",
        "Payload": {
          "approval_id.$": "$.approval_id",
          "task_token.$": "$$.Task.Token"
        }
      },
      "TimeoutSeconds": 86400,
      "Next": "ProcessApprovalDecision"
    },
    "ProcessApprovalDecision": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.decision",
          "StringEquals": "APPROVED",
          "Next": "DeployToProduction"
        },
        {
          "Variable": "$.decision",
          "StringEquals": "REJECTED",
          "Next": "HandleRejection"
        }
      ],
      "Default": "HandleTimeout"
    },
    "DeployToProduction": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:production-deployer",
      "Next": "TeardownSandbox"
    },
    "HandleRejection": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:handle-rejection",
      "Next": "TeardownSandbox"
    },
    "HandleTimeout": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:handle-timeout",
      "Next": "TeardownSandbox"
    },
    "TeardownSandbox": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:sandbox-teardown",
      "End": true
    }
  }
}
```

---

## 6. Security and Compliance Considerations

### 6.1 Sandbox Isolation

**Network Isolation:**
- Sandbox VPC completely isolated from production VPC
- No VPC peering or transit gateway connections
- NAT Gateway for outbound internet (package downloads only)
- Security groups deny all inbound traffic

**Data Isolation:**
- Sandbox uses synthetic/anonymized test data only
- No access to production databases (Neptune, OpenSearch)
- Mock API endpoints for external dependencies

**Compute Isolation:**
- Dedicated ECS cluster for sandbox tasks
- No shared task execution with production
- Resource limits enforced (CPU, memory, execution time)

### 6.2 Approval Audit Trail

**Immutable Logging:**
- All approval decisions logged to CloudWatch Logs
- S3 bucket with WORM (Write Once Read Many) policy
- Retention: 7 years (SOX compliance)

**Logged Events:**
- Approval request creation
- Notification sent
- Human decision (approve/reject)
- Approver identity (email, IAM role)
- Decision timestamp
- Approver comments
- Deployment execution

### 6.3 Access Control

**Who Can Approve:**
- Senior Security Engineers (IAM role: `AuraPatchApprover`)
- Security Operations Manager (IAM role: `AuraSecurityManager`)
- CISO (IAM role: `AuraCISO`)

**Least Privilege:**
- Approval Dashboard requires MFA authentication
- API Gateway enforces IAM authentication
- DynamoDB table has fine-grained access control
- CloudWatch Logs encrypted with KMS

---

## 7. Operational Metrics

**Monitoring Dashboard:**
- Pending approvals count (alert if > 10)
- Average time to approval (target: < 4 hours)
- Approval rate (approved vs. rejected)
- Sandbox test success rate
- Timeout rate (auto-rejected due to no response)

**SLA Targets:**
- Sandbox provisioning: < 5 minutes
- Test execution: < 10 minutes
- Notification delivery: < 1 minute
- Human approval: < 24 hours
- Production deployment (post-approval): < 30 minutes

---

## 8. Cost Analysis

**Per-Patch Estimate:**
| Resource | Usage | Cost |
|----------|-------|------|
| Fargate (Sandbox) | 0.5 vCPU x 1 GB x 20 min | $0.02 |
| ECS Task Storage | 20 GB ephemeral | $0.00 |
| SNS Notifications | 1 email | $0.00 |
| Step Functions | 10 state transitions | $0.00 |
| DynamoDB | 10 read/write units | $0.00 |
| CloudWatch Logs | 100 MB | $0.01 |
| **Total per Patch** | | **$0.03** |

**Monthly Estimate (100 patches/month):**
- Total HITL infrastructure cost: ~$3/month
- Minimal overhead vs. current architecture

---

## 9. Rollout Plan

### Phase 1: MVP (Weeks 1-2)
- [ ] Implement Sandbox Orchestrator
- [ ] Implement HITL Approval Service
- [ ] Implement Notification Service
- [ ] Deploy Step Functions state machine
- [ ] Create DynamoDB tables

### Phase 2: Dashboard (Weeks 3-4)
- [ ] Build Approval Dashboard UI
- [ ] Integrate with API Gateway
- [ ] Add authentication/authorization
- [ ] User acceptance testing

### Phase 3: Integration (Week 5)
- [ ] Integrate with existing Orchestrator
- [ ] Update CI/CD pipeline
- [ ] End-to-end testing
- [ ] Security review

### Phase 4: Production (Week 6)
- [ ] Deploy to AWS GovCloud
- [ ] Train security team
- [ ] Enable monitoring/alerts
- [ ] Go-live with HITL workflow

---

## 10. Success Criteria

**Technical:**
- [ ] 100% of security patches go through sandbox testing
- [ ] Zero production incidents from approved patches
- [ ] Sandbox test suite detects 95%+ of breaking changes
- [ ] < 5% false positive rate (valid patches rejected)

**Operational:**
- [ ] Average approval time < 4 hours
- [ ] Timeout rate < 5%
- [ ] Approver satisfaction score > 4/5

**Compliance:**
- [ ] 100% audit trail coverage
- [ ] SOX/CMMC auditors approve workflow
- [ ] Zero unauthorized deployments
