# Release Notes

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document provides release notes for Project Aura, including new features, improvements, bug fixes, and deprecation notices. Subscribe to release notifications through **Settings > Notifications > Product Updates** to stay informed about platform changes.

---

## Version Numbering

Project Aura follows [Semantic Versioning 2.0.0](https://semver.org/) (SemVer):

```
MAJOR.MINOR.PATCH

Example: 1.3.2
         │ │ └── Patch version (bug fixes, security patches)
         │ └──── Minor version (new features, backward compatible)
         └────── Major version (breaking changes)
```

### Version Types

| Version Type | Frequency | Content |
|--------------|-----------|---------|
| Major (X.0.0) | Annual | Breaking API changes, major architecture updates |
| Minor (1.X.0) | Monthly | New features, enhancements, deprecation notices |
| Patch (1.3.X) | Weekly | Bug fixes, security patches, performance improvements |

### Pre-release Versions

| Suffix | Meaning | Stability |
|--------|---------|-----------|
| `-alpha.N` | Early development | Unstable, may change significantly |
| `-beta.N` | Feature complete | Mostly stable, may have bugs |
| `-rc.N` | Release candidate | Stable, final testing |

---

## Release Cadence

| Release Type | Schedule | Notes |
|--------------|----------|-------|
| Feature releases | First Tuesday of each month | Contains new features and enhancements |
| Patch releases | Weekly (Thursdays) | Bug fixes and security patches |
| Hotfix releases | As needed | Critical security issues only |

### Release Timeline

1. **Development:** Features developed and tested internally
2. **Preview (optional):** Available in preview for Enterprise customers
3. **General Availability:** Released to all customers
4. **Long-Term Support:** Critical fixes for previous major versions

---

## Release Notes Template

Each release follows this structure for consistency:

```markdown
## vX.Y.Z (YYYY-MM-DD)

### Highlights
Brief summary of the most important changes in this release.

### New Features
- **Feature Name:** Description of the feature and its benefits.
  [Learn more](link-to-documentation)

### Improvements
- **Area:** Description of the improvement.

### Bug Fixes
- Fixed issue where [description of bug and resolution].

### Security
- Addressed [CVE-XXXX-XXXXX]: Description.

### Breaking Changes
- **Affected Area:** Description of breaking change and migration steps.

### Deprecations
- **Feature:** Will be removed in vX.Y.Z. Use [alternative] instead.

### Known Issues
- [Description of known issue and workaround if available.]
```

---

## Current Release

## v1.3.4 (2026-01-23)

### Highlights

This release introduces customizable dashboard widgets (ADR-064), enabling users to create personalized views tailored to their role and priorities. Security Engineers, DevOps Leads, and CISOs can now build dashboards that surface the metrics most relevant to their workflows.

### New Features

- **Customizable Dashboard Widgets:** Create personalized dashboards with drag-drop layout editing using react-grid-layout. Choose from 15+ widget types including metric cards, sparkline charts, heatmaps, and data tables.
  [Learn more](../core-concepts/index.md)

- **Dashboard Sharing:** Share dashboards with individual users, teams, or entire organizations. Shared dashboards can be view-only or editable based on permissions.

- **Custom Widget Builder:** Create custom query widgets that pull data from Aura's data sources with live preview. Supports filtering, aggregation, and threshold-based coloring.

- **Scheduled Reports:** Generate and email dashboard reports on daily, weekly, or monthly schedules. Reports are delivered as PDF attachments with point-in-time snapshots.

- **Dashboard Embedding:** Embed Aura dashboards in external applications using secure HMAC-signed iframe URLs. Supports theme customization for seamless integration.

- **Role-Based Dashboard Defaults:** New users automatically receive a dashboard preset based on their role (Security Engineer, DevOps Lead, Engineering Manager, Executive).

### Improvements

- **Widget Library:** New widget picker drawer with category filtering and search. Includes preview of each widget type before adding to dashboard.

- **Dashboard Persistence:** Dashboards now persist to DynamoDB with automatic conflict resolution and version history.

- **Clone Dashboard:** Quickly create copies of existing dashboards, including shared dashboards, as starting points for customization.

### Bug Fixes

- Fixed issue where dashboard widgets occasionally displayed stale data after page refresh.
- Fixed layout corruption when resizing widgets in narrow browser viewports.
- Fixed widget configuration modal not saving custom thresholds correctly.

### Security

- Dashboard embedding uses HMAC-SHA256 signatures with 1-hour expiration for secure external access.
- Added audit logging for all dashboard creation, modification, and sharing events.

### Deprecations

- The legacy fixed dashboard layout will be removed in v1.4.0. Users should migrate to customizable dashboards before then.

---

## Previous Releases

## v1.3.3 (2026-01-21)

### Highlights

This release completes the Constitutional AI integration (ADR-063), implementing principled critique-revision for all agent outputs. Constitutional AI ensures agent behavior aligns with explicit safety, compliance, and quality principles while maintaining helpful, non-evasive engagement.

### New Features

- **Constitutional AI Framework:** 16 constitutional principles across 6 categories (Safety, Compliance, Anti-Sycophancy, Transparency, Helpfulness, Code Quality) applied to all agent outputs.
  [Learn more](../core-concepts/constitutional-ai.md)

- **Critique-Revision Pipeline:** Agent outputs are automatically critiqued against constitutional principles. Outputs violating CRITICAL or HIGH severity principles are revised before delivery.

- **Trust Center Dashboard:** Real-time visibility into Constitutional AI operations including critique rates, revision rates, HITL escalation rates, and principle violation trends.

- **LLM-as-Judge Evaluation:** Nightly automated evaluation comparing agent outputs against a curated golden set of 100 verified cases. CloudWatch alarms trigger when accuracy drops below 90%.

- **Tiered Critique Strategy:** Three-tier critique system (fast/standard/deep) based on autonomy level and content sensitivity. Fast path uses Bedrock Guardrails for sub-50ms response on known-safe patterns.

### Improvements

- **Semantic Caching:** Constitutional AI critique results are cached by semantic similarity, reducing LLM costs by 30-40% on repeated or similar inputs.

- **Async Audit Logging:** Audit events are queued to SQS FIFO for asynchronous persistence, removing audit logging from the critical path.

- **Constitutional Mixin Pattern:** Agents integrate constitutional critique through explicit `process_with_constitutional()` method rather than implicit wrapping, improving transparency and debuggability.

### Infrastructure

- Deployed `aura-constitutional-audit-queue-{env}` stack (DynamoDB + SQS) to DEV and QA environments.
- Deployed `aura-constitutional-ai-evaluation-{env}` stack (Lambda + EventBridge + CloudWatch) to DEV and QA environments.

### Bug Fixes

- Fixed race condition in revision service when multiple principles required conflicting revisions.
- Fixed metric publishing delay when CloudWatch connection was temporarily unavailable.

---

## v1.3.2 (2026-01-19)

### Highlights

This release improves platform reliability with EventBridge schedule optimization and comprehensive test isolation fixes that resolved persistent Lambda test failures.

### Improvements

- **EventBridge Cost Optimization:** Reduced Lambda invocations by 80% for non-time-critical workloads. Dispatcher polling increased from 1 minute to 5 minutes; cost aggregator from 5 minutes to 1 hour.

- **Test Isolation:** Fixed event loop pollution affecting 14 Lambda tests when running the full test suite. Added automatic event loop reset in test fixtures.

- **Scheduling Service Coverage:** Added 748 lines of extended test coverage for scheduling service edge cases including DynamoDB errors, pagination, and organization filtering.

- **Recurring Task Service Coverage:** Added 631 lines of extended test coverage for recurring task service including cron validation, lazy loading, and error paths.

### Bug Fixes

- Fixed AsyncMock inconsistencies in Lambda threat intelligence tests causing intermittent failures.
- Fixed module cache pollution where Lambda modules retained stale mock state between tests.
- Fixed sys.modules manipulation in runtime incident CLI tests lacking proper fixture isolation.

### Known Issues

- Scheduler dispatcher: Job execution may be delayed up to 5 minutes (increased from 1 minute) due to polling interval optimization.

---

## v1.3.1 (2026-01-14)

### Highlights

This release introduces the Environment Validator Agent (ADR-062), which autonomously validates environment consistency across deployments, detecting misconfigurations before they cause failures or security issues.

### New Features

- **Environment Validator Agent:** Autonomous validation of environment consistency including ConfigMaps, ARN environment alignment, ECR registry validation, and environment variable consistency.
  [Learn more](../../support/architecture/system-overview.md)

- **Pre-Deployment Validation:** Analyze kustomize overlays and deployment manifests before apply to catch environment mismatches.

- **Continuous Drift Detection:** Scheduled scans detect configuration drift between environments with configurable alerting thresholds.

- **Cross-Account Boundary Enforcement:** Automatic detection of DEV/QA/PROD cross-contamination in resource references.

- **Validation Dashboard:** New dashboard showing validation timeline, violation heatmap, drift status, agent activity, and remediation history.

### Improvements

- **SSM Parameter Store Integration:** Environment registry moved from ConfigMaps to SSM Parameter Store for improved security and versioning.

- **Single-Table DynamoDB Design:** Validation results stored using single-table design to prevent hot partitions under high validation load.

- **IRSA Policy Scoping:** Environment Validator uses dedicated IRSA role with explicit resource scoping.

### Infrastructure

- Added 8 validation rules (ENV-001 through ENV-008) covering endpoints, ARNs, images, environment variables, regions, KMS keys, and IAM roles.

---

## v1.3.0 (2026-01-12)

### Highlights

Major release introducing GPU Workload Scheduler (ADR-061), enabling self-service GPU job management for code embedding generation, model fine-tuning, and local LLM inference.

### New Features

- **GPU Workload Scheduler:** Self-service UI for scheduling GPU jobs with queue management, progress monitoring, and cost tracking.
  [Learn more](../../support/operations/scaling.md)

- **GPU Job Types:** Support for code embedding generation, local LLM inference, vulnerability classifier training, self-play SWE-RL training, and Titan memory consolidation.

- **Priority Queue Management:** Four priority levels with configurable preemption policies for GPU workloads.

- **Cost Controls:** Per-job cost estimates, organization-level GPU budgets, and Spot instance support for cost optimization.

- **Checkpoint Support:** Long-running GPU jobs support checkpointing for graceful interruption and resumption.

### Improvements

- **Cluster Autoscaler Integration:** GPU node groups scale from 0 to MaxSize based on pending GPU workloads.

- **Spot Instance Support:** Optional Spot instances for GPU workloads with automatic fallback to on-demand when Spot capacity is unavailable.

### Infrastructure

- Deployed GPU node group (g4dn.xlarge) with MinSize=0, MaxSize=4 in DEV environment.
- NVIDIA k8s-device-plugin v0.14.3 deployed via kustomize.
- Approved 32 vCPU Spot quota for DEV environment (QA pending).

### Breaking Changes

- **GPU Workload API:** New `/api/v1/gpu/jobs` endpoint replaces deprecated `/api/v1/compute/gpu` endpoint. Migration guide available in API documentation.

---

## Upgrade Notes

### Upgrading to v1.3.x

#### From v1.2.x

1. **Database Migrations:** Run `aura-migrate upgrade` before starting new containers.

2. **Dashboard Migration:** Legacy fixed dashboards are automatically converted to customizable dashboards. User customizations are preserved.

3. **Constitutional AI:** New services require additional DynamoDB tables and SQS queues. CloudFormation templates handle provisioning automatically.

4. **GPU Workloads:** GPU node groups require Cluster Autoscaler configuration updates. See `docs/deployment/DEPLOYMENT_GUIDE.md` for details.

#### API Changes in v1.3.x

| Endpoint | Change | Migration |
|----------|--------|-----------|
| `/api/v1/compute/gpu` | Deprecated | Use `/api/v1/gpu/jobs` |
| `/api/v1/dashboards` | New fields | Existing integrations continue to work |
| `/api/v1/agents/*/outputs` | New `constitutional` field | Optional, backward compatible |

---

## Deprecation Schedule

| Feature | Deprecated In | Removed In | Alternative |
|---------|---------------|------------|-------------|
| Fixed dashboard layout | v1.3.4 | v1.4.0 | Customizable dashboards |
| `/api/v1/compute/gpu` endpoint | v1.3.0 | v1.4.0 | `/api/v1/gpu/jobs` |
| Legacy audit log format | v1.2.0 | v1.4.0 | Structured JSON format |
| Python 3.10 support | v1.3.0 | v1.5.0 | Python 3.11+ |

---

## Security Advisories

### 2026 Advisories

| Date | Severity | Description | Affected Versions | Fixed In |
|------|----------|-------------|-------------------|----------|
| 2026-01-15 | Medium | Dashboard sharing permissions could allow unauthorized view access | 1.3.0 - 1.3.3 | 1.3.4 |
| 2026-01-08 | Low | Verbose error messages in GPU scheduler exposed internal paths | 1.3.0 - 1.3.1 | 1.3.2 |

For the complete security advisory history, see [Security Advisories](../../support/troubleshooting/security-issues.md).

---

## Roadmap Preview

### v1.4.0 (Expected: February 2026)

- Multi-region deployment support
- Enhanced GraphRAG query optimization
- Custom compliance framework builder
- Advanced anomaly detection for agent behavior

### v1.5.0 (Expected: March 2026)

- FedRAMP High certification (GovCloud)
- Expanded language support (Rust, Swift)
- Real-time collaboration features
- Advanced ML model customization

*Roadmap items are subject to change based on customer feedback and market conditions.*

---

## Feedback

Have feedback on recent releases? Contact your Aenea Labs account representative or submit feedback through:

- **In-product:** Help > Send Feedback
- **Email:** product@aenealabs.com
- **Enterprise customers:** Your dedicated Slack channel

---

## Notification Settings

Configure release notifications at **Settings > Notifications > Product Updates**:

| Notification Type | Default | Description |
|-------------------|---------|-------------|
| Major releases | On | Breaking changes and major features |
| Minor releases | On | New features and enhancements |
| Patch releases | Off | Bug fixes and minor improvements |
| Security advisories | On (locked) | Cannot be disabled |
| Deprecation warnings | On | Advance notice of removals |

---

**Related Documentation:**
- [Getting Started](../getting-started/index.md) - Platform overview and setup
- [Troubleshooting](../../support/troubleshooting/index.md) - Common issues and solutions
- [API Reference](../../support/api-reference/index.md) - API documentation
- [Glossary](./glossary.md) - Term definitions
