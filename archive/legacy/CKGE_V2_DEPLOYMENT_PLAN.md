# AWS Deployment Checklist: Codebase Knowledge Graph Engine (CKGE) V2.0

**Target Environment:** AWS GovCloud (or Commercial with equivalent security controls)
**Service:** Context Retrieval Service (Fargate) + HITL Workflow Components
**Version:** 2.0 (includes Human-in-the-Loop and Sandbox Testing)
**Status:** READY for CloudFormation / Terraform execution

---

## CRITICAL UPDATE: Version 2.0 Enhancement

This deployment plan now includes **mandatory Human-in-the-Loop (HITL)** approval workflows and **sandbox testing infrastructure** for all security patches. These enhancements are required for SOX/CMMC compliance and change management approval.

**Key Additions:**
- Sandbox ECS cluster for isolated patch testing
- AWS Step Functions state machine for HITL workflow orchestration
- SNS topics and SES configuration for security team notifications
- DynamoDB tables for approval request tracking
- Approval Dashboard frontend deployment
- IAM roles for patch approvers

**Reference:** See `docs/hitl_sandbox_architecture.md` for complete architectural details.

---

## Phase 1: Infrastructure Setup (DevOps / Architecture Team)

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| 1. VPC Setup | Verify VPC, subnets, and NAT Gateways are configured for GovCloud standards. | [ ] | Must use private subnets for all CKGE resources. |
| 2. IAM Roles (PLP) | Create TaskRole and ExecutionRole as defined in `fargate_task_definition.json`. | [ ] | Policies must be minimal; audited by Saviynt for CMMC compliance. |
| 3. Secrets Manager | Securely provision and store `LLM_API_KEY`, `NEPTUNE_ENDPOINT`, and `OPENSEARCH_ENDPOINT` secrets. | [ ] | Mandatory step for SOX compliance (no hardcoded credentials). |
| 4. ECR Repository | Create ECR repository: `ckge-context-retrieval`. | [ ] | Enable Enhanced Scanning on the repo for continuous vulnerability monitoring. |

---

## Phase 2: Data Service Provisioning

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| 5. Neptune Cluster | Provision Neptune DB Cluster (e.g., single writer, two read replicas). | [ ] | Configure Security Groups to allow inbound traffic only from Fargate subnets. |
| 6. OpenSearch | Provision OpenSearch Service domain (Vector Store). | [ ] | Configure k-NN index for vector embeddings; use fine-grained access control. |

---

## Phase 3: CI/CD Activation

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| 7. CodeCommit/GitHub Sync | Verify source code is pushed to the secure repository (URL: https://github.com/aenealabs/aura.git). | [ ] | Completed by `setup_repo.sh`. |
| 8. CodePipeline Setup | Deploy the CI/CD pipeline using the `pipeline_config.yml` definition. | [ ] | Must include the mandatory Security and Compliance Gates. |
| 9. Initial Run | Trigger the first manual pipeline run, verifying the build passes the SAST/SCA/ECR scans successfully. | [ ] | Build failure indicates a compliance risk—requires immediate vulnerability remediation. |

---

## Phase 4: HITL Infrastructure Provisioning (NEW - V2.0)

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| **10. Sandbox VPC** | Create dedicated VPC for sandbox environments with isolated subnets. | [ ] | **CRITICAL:** No VPC peering or connectivity to production VPC. NAT Gateway for outbound only. |
| **11. Sandbox ECS Cluster** | Provision dedicated ECS cluster for sandbox Fargate tasks. | [ ] | Configure cluster with resource limits (max 10 concurrent sandboxes). |
| **12. DynamoDB Tables** | Create `ApprovalRequests` and `SandboxResults` tables. | [ ] | Enable Point-in-Time Recovery (PITR) for compliance. Configure TTL for auto-cleanup. |
| **13. SNS Topic** | Create SNS topic: `aura-patch-approval-notifications`. | [ ] | Subscribe security team email addresses. Configure email template. |
| **14. SES Configuration** | Verify domain and configure SES for outbound emails. | [ ] | Move out of sandbox mode. Configure DKIM/SPF for deliverability. |
| **15. IAM Roles (Approvers)** | Create IAM roles: `AuraPatchApprover`, `AuraSecurityManager`, `AuraCISO`. | [ ] | Attach policies for DynamoDB write (approvals) and API Gateway access (dashboard). Require MFA. |
| **16. Step Functions** | Deploy HITL workflow state machine from `deploy/step_functions/hitl_remediation_workflow.json`. | [ ] | Configure task token callbacks and 24-hour timeout. |
| **17. Lambda Functions** | Deploy all HITL Lambda functions (sandbox orchestrator, approval service, notification service, etc.). | [ ] | Package with dependencies. Configure VPC access for DynamoDB/ECS. |

---

## Phase 5: Approval Dashboard Deployment (NEW - V2.0)

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| **18. S3 Bucket (Frontend)** | Create S3 bucket for hosting Approval Dashboard static files. | [ ] | Enable versioning. Configure bucket policy for CloudFront access only. |
| **19. CloudFront Distribution** | Create CloudFront distribution pointing to S3 bucket. | [ ] | Configure SSL certificate (ACM). Enable HTTPS only. |
| **20. API Gateway** | Deploy API Gateway for Approval Dashboard backend APIs. | [ ] | Configure IAM authentication. Enable CloudWatch logging. |
| **21. Build & Deploy Frontend** | Build React Approval Dashboard and deploy to S3. | [ ] | Run `npm run build` in `frontend/` directory. Sync to S3 bucket. |
| **22. DNS Configuration** | Create Route53 record pointing to CloudFront distribution. | [ ] | Example: `aura-approvals.company.com` |

---

## Phase 6: Security & Compliance Validation (NEW - V2.0)

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| **23. Network Isolation Test** | Verify sandbox VPC has no connectivity to production resources. | [ ] | Attempt connection from sandbox to production Neptune/OpenSearch (should fail). |
| **24. Notification Test** | Trigger test approval request and verify SNS/SES delivery. | [ ] | Confirm emails received by all subscribed security team members. |
| **25. Approval Workflow Test** | Execute end-to-end HITL workflow with test vulnerability. | [ ] | Verify Step Functions state transitions, approval recording, sandbox provisioning. |
| **26. Audit Log Verification** | Confirm all approval events logged to CloudWatch Logs and S3. | [ ] | Verify 7-year retention policy. Test log immutability (WORM). |
| **27. IAM Policy Audit** | Review all IAM roles against Least Privilege Principle (PLP). | [ ] | Submit to Saviynt for CMMC compliance audit. |
| **28. Approver Training** | Train security team on using Approval Dashboard. | [ ] | Provide documentation and conduct walkthrough session. |

---

## Phase 7: Production Cutover (V2.0 Go-Live)

| Step | Action | Status | Notes |
| :--- | :--- | :--- | :--- |
| **29. Enable HITL Workflow** | Update Orchestrator to use HITL-enabled Step Functions state machine. | [ ] | Deploy updated `agent_orchestrator.py` with HITL integration. |
| **30. Monitor First 10 Approvals** | Closely monitor first 10 patch approvals for issues. | [ ] | Track metrics: approval time, sandbox success rate, notification delivery. |
| **31. Adjust SLAs** | Fine-tune timeout values based on actual approval patterns. | [ ] | Default 24-hour timeout may need adjustment based on team availability. |
| **32. Executive Briefing** | Brief leadership on new HITL workflow and compliance benefits. | [ ] | Present updated metrics dashboard showing audit trail capabilities. |
