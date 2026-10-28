# Feature Backlog - Project Aura

This document captures feature ideas, autonomous agent capabilities, and future enhancements for the Project Aura platform.

**Last Updated:** December 1, 2025 (status labels reviewed against code 2026-10-26)

---

## How to Use This Document

- **Add ideas freely** - Capture concepts before they're lost
- **Include context** - Describe the problem being solved and expected behavior
- **Link to ADRs** - Reference architecture decisions when relevant
- **Mark status** - Use labels: `[IDEA]`, `[PLANNED]`, `[IN PROGRESS]`, `[COMPLETED]`

---

## Autonomous Agent Features

### [IDEA] Infrastructure Hygiene Agent

**Problem:** Enterprise cloud environments accumulate orphaned resources, unused secrets, stale configurations, and drift from intended architecture over time. Manual audits are infrequent and error-prone.

**Proposed Solution:** A specialized autonomous agent that performs scheduled architecture reviews over enterprise codebases and cloud infrastructure.

**Capabilities:**
1. **Scheduled Architecture Review**
   - Scan codebase for unused imports, dead code, deprecated patterns
   - Analyze CloudFormation/Terraform for resource drift
   - Identify unused IAM roles, policies with overly broad permissions

2. **Orphaned Resource Detection**
   - Detect orphaned cloud resources (ENIs, EBS volumes, snapshots, security groups)
   - Identify secrets in Secrets Manager that haven't been accessed in X days
   - Find log groups with no recent activity consuming storage

3. **Documentation & Reporting**
   - Generate detailed findings report with severity levels
   - Create remediation recommendations with risk assessment
   - Track historical trends (resources cleaned, cost savings)

4. **HITL Integration**
   - If HITL enabled: Present findings for human approval before action
   - If HITL disabled: Proceed to sandbox testing automatically
   - Configurable thresholds (e.g., auto-approve low-risk, require approval for high-risk)

5. **Sandbox Remediation**
   - Provision ephemeral sandbox environment
   - Apply proposed fixes in isolated context
   - Run validation tests to ensure fixes don't break functionality
   - Generate diff/patch for human review

6. **Notification & Audit Trail**
   - Notify human users via configured channels (email, Slack, SNS)
   - Full audit log of all actions taken (who, what, when, why)
   - Integration with SIEM/security monitoring

**Implementation Notes:**
- Extend existing `ArchitectureReviewAgent` from ADR pipeline
- Leverage AWS Cost Explorer API for cost-impact analysis
- Use CloudFormation drift detection APIs
- Integrate with existing sandbox network service for isolation

**Related ADRs:** ADR-010 (Autonomous ADR Generation Pipeline)

---

### [IDEA] Dependency Vulnerability Auto-Patcher

**Problem:** Security vulnerabilities in dependencies require manual tracking, assessment, and patching. Time-to-remediation is often measured in weeks.

**Proposed Solution:** Autonomous agent that monitors dependency vulnerabilities and generates verified patches.

**Capabilities:**
1. Monitor CVE feeds (NVD, GitHub Advisory, CISA KEV)
2. Match vulnerabilities against project SBOM
3. Generate patch proposals (version bumps, code changes)
4. Test patches in sandbox with full integration test suite
5. Create PR with security context and test results
6. HITL approval for merge

---

### [IDEA] Code Quality Trend Analyzer

**Problem:** Code quality degrades gradually over time. Teams don't notice until technical debt becomes unmanageable.

**Proposed Solution:** Agent that tracks code quality metrics over time and generates proactive refactoring recommendations.

**Capabilities:**
1. Track complexity metrics (cyclomatic, cognitive) per module
2. Monitor test coverage trends
3. Identify "hot spots" (frequently changed + low quality)
4. Generate refactoring proposals with effort estimates
5. Create issues/tickets automatically

---

### [IDEA] Cost Optimization Agent

**Problem:** Cloud costs grow unexpectedly. Reserved instances expire, right-sizing opportunities are missed, unused resources accumulate.

**Proposed Solution:** Autonomous agent that continuously optimizes cloud costs.

**Capabilities:**
1. Analyze usage patterns for right-sizing recommendations
2. Identify reserved instance/savings plan opportunities
3. Detect idle resources (low CPU, no connections)
4. Generate cost reduction proposals with risk assessment
5. Implement safe optimizations automatically (with HITL for risky changes)

---

## Platform Enhancements

### [IN PROGRESS] Multi-Model Orchestration

> **Status (2026-10-26):** `ModelRouter` (`src/services/model_router.py`, ADR-015 / ADR-028) implements complexity-based routing, per-model pricing, and SSM-unavailable fallback, and is exposed via `src/api/model_router_endpoints.py`. Outside the diagram generator (`src/services/diagrams/ai_diagram_generator.py`) it is not yet in the main agent LLM call path.

Support multiple LLM providers with intelligent routing based on task complexity and cost.

- Route simple tasks to smaller/cheaper models
- Use frontier models for complex reasoning
- Automatic fallback on rate limits or errors
- Cost tracking per model/task

### [IN PROGRESS] Agent Memory & Learning

> **Status (2026-10-26):** Episodic and neural memory services exist (ADR-024, ADR-080: `src/services/episodic_memory_service.py`, `src/services/titan_memory_service.py`, `src/services/memory_evolution/`). HITL approve/reject outcomes are recorded as memory episodes. See those ADRs for what is wired into production request paths.

Enable agents to learn from past interactions and improve over time.

- Store successful patterns in vector database
- Reference similar past problems during analysis
- Track false positives/negatives for calibration
- Feedback loop from HITL decisions

### [IN PROGRESS] Real-Time Streaming Analysis

> **Status (2026-10-26):** An incremental streaming analysis engine exists as a library (`src/services/streaming/analysis_engine.py`, ADR-079) and a GitHub webhook handler exists (`src/api/webhook_handler.py`), but the streaming engine is not yet called from any API route or worker.

Support real-time analysis of code changes as they're committed.

- GitHub webhook integration (already partial)
- Incremental graph updates (vs full re-index)
- Real-time security scanning
- Immediate developer feedback

---

## Integration Ideas

### [IN PROGRESS] IDE Plugin

> **Status (2026-10-26):** A VS Code extension (`vscode-extension/`: findings, diagnostics, code lens, patches, approvals, graph-context providers) and a PyCharm plugin (`pycharm-plugin/`: scan-file action, findings and graph-context services) exist; see ADR-048.

VS Code / JetBrains plugin for real-time Aura integration.

- In-editor security warnings
- Suggested fixes inline
- GraphRAG context lookup
- One-click patch application

### [IDEA] Slack/Teams Bot

> **Status (2026-10-26):** Outbound Slack notifications and approval-request messages exist (`src/services/integrations/slack_adapter.py`); the conversational bot interface described below is not built.

Chat-based interface for common operations.

- "What's the status of our security vulnerabilities?"
- "Show me the dependency graph for auth module"
- "Approve pending patches for low-risk CVEs"

---

## Notes

- Feature ideas should be validated against CMMC/compliance requirements before implementation
- All autonomous actions must have audit trail for compliance
- HITL must be configurable per-feature, per-environment, per-risk-level
