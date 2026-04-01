# ADR-033: Runbook Agent for Automated Incident Documentation

**Status:** Deployed
**Date:** 2025-12-11
**Author:** Platform Team
**Reviewers:** DevOps, SRE

## Context

During incident response and break/fix sessions, engineers resolve issues through a series of diagnostic and remediation steps. This knowledge is valuable for:
- Future incident response (reducing MTTR)
- Onboarding new team members
- Compliance and audit requirements
- Pattern recognition for proactive prevention

Currently, runbook creation is manual and often delayed or skipped due to time pressure. This leads to:
- Knowledge loss when engineers leave or forget details
- Repeated investigation of similar issues
- Inconsistent documentation quality
- No automated detection of when runbooks need updates

## Decision

Implement a **Runbook Agent** that automatically:
1. Detects break/fix resolutions from CI/CD logs, CloudFormation events, and git commits
2. Generates new runbooks following project templates
3. Updates existing runbooks when new resolution patterns are discovered
4. Maintains a searchable incident knowledge base

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Runbook Agent                                │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ IncidentDetector│  │ RunbookGenerator │  │  RunbookUpdater   │  │
│  │                 │  │                  │  │                   │  │
│  │ - Log analysis  │  │ - Template engine│  │ - Diff detection  │  │
│  │ - Error patterns│  │ - LLM generation │  │ - Merge logic     │  │
│  │ - Resolution    │  │ - Validation     │  │ - Version control │  │
│  │   detection     │  │                  │  │                   │  │
│  └────────┬────────┘  └────────┬─────────┘  └─────────┬─────────┘  │
│           │                    │                      │             │
│           └────────────────────┼──────────────────────┘             │
│                                │                                     │
│                    ┌───────────▼───────────┐                        │
│                    │  RunbookRepository    │                        │
│                    │                       │                        │
│                    │ - File system storage │                        │
│                    │ - DynamoDB index      │                        │
│                    │ - Semantic search     │                        │
│                    └───────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ CloudWatch    │    │ CloudFormation    │    │ Git Repository    │
│ Logs          │    │ Events            │    │ Commits           │
└───────────────┘    └───────────────────┘    └───────────────────┘
```

### Core Components

#### 1. IncidentDetector
Monitors multiple sources to detect break/fix events:

**Detection Sources:**
- CloudWatch Logs (CodeBuild failures → successes)
- CloudFormation stack events (ROLLBACK → successful deployment)
- Git commits with fix patterns (`fix:`, `hotfix:`, error keywords)
- Manual triggers via CLI or API

**Detection Patterns:**
```python
BREAK_FIX_PATTERNS = {
    "cloudformation": {
        "failure_states": ["ROLLBACK_COMPLETE", "CREATE_FAILED", "UPDATE_FAILED"],
        "success_states": ["CREATE_COMPLETE", "UPDATE_COMPLETE"],
    },
    "codebuild": {
        "failure_status": ["FAILED", "FAULT", "TIMED_OUT"],
        "success_status": ["SUCCEEDED"],
    },
    "git_commits": {
        "fix_patterns": [r"^fix(\(.+\))?:", r"^hotfix:", r"resolve.*error", r"fix.*issue"],
    },
}
```

#### 2. RunbookGenerator
Creates new runbooks from incident context:

**Input:**
- Error signatures and stack traces
- Resolution commands and their outputs
- Affected resources and services
- Time to resolution metrics

**Output:**
- Markdown runbook following project template
- Structured metadata for indexing
- Related runbook references

**Template Structure:**
```markdown
# Runbook: {Title}

**Purpose:** {Auto-generated from error context}
**Audience:** {Inferred from affected services}
**Estimated Time:** {Calculated from resolution duration}
**Last Updated:** {Current date}
**Auto-Generated:** Yes (Runbook Agent v1.0)

---

## Problem Description
{Extracted from error logs}

### Symptoms
{Error messages and indicators}

### Root Cause
{Inferred from resolution pattern}

---

## Quick Resolution
{Primary fix steps}

## Detailed Diagnostic Steps
{Step-by-step with commands}

## Resolution Procedures
{Categorized by approach}

## Prevention
{Recommendations based on fix}

## Related Documentation
{Links to related runbooks and docs}
```

#### 3. RunbookUpdater
Maintains existing runbooks with new knowledge:

**Update Triggers:**
- New resolution pattern for same error signature
- Additional diagnostic commands discovered
- Prevention measures identified
- Related incidents linked

**Update Strategy:**
- Non-destructive: Adds new sections, doesn't remove existing content
- Version tracking: Maintains history of changes
- Review workflow: Can require human approval for significant changes

#### 4. RunbookRepository
Stores and indexes runbooks for retrieval:

**Storage:**
- Primary: Git repository (`docs/runbooks/`)
- Index: DynamoDB table for fast lookups
- Search: OpenSearch for semantic similarity

**Schema:**
```python
@dataclass
class RunbookMetadata:
    id: str                      # UUID
    title: str                   # Human-readable title
    file_path: str               # docs/runbooks/EXAMPLE.md
    error_signatures: List[str]  # Unique error patterns
    services: List[str]          # Affected AWS services
    keywords: List[str]          # Search keywords
    created_at: datetime
    updated_at: datetime
    auto_generated: bool
    resolution_count: int        # Times this runbook was used
    avg_resolution_time: float   # Minutes
```

### Trigger Mechanisms

#### Automatic Triggers

1. **CodeBuild Success After Failure**
   ```python
   # EventBridge rule
   {
       "source": ["aws.codebuild"],
       "detail-type": ["CodeBuild Build State Change"],
       "detail": {
           "build-status": ["SUCCEEDED"],
           "previous-build-status": ["FAILED"]
       }
   }
   ```

2. **CloudFormation Recovery**
   ```python
   # EventBridge rule
   {
       "source": ["aws.cloudformation"],
       "detail-type": ["CloudFormation Stack Status Change"],
       "detail": {
           "status-details": {
               "status": ["CREATE_COMPLETE", "UPDATE_COMPLETE"]
           }
       }
   }
   ```

3. **Git Push with Fix Commit**
   ```python
   # GitHub webhook or CodePipeline trigger
   # Analyze commit messages for fix patterns
   ```

#### Manual Triggers

```bash
# CLI trigger after resolving an issue
aura runbook create --from-session <session-id>
aura runbook create --from-logs /aws/codebuild/project --since 2h
aura runbook update EXISTING_RUNBOOK.md --add-resolution "new fix steps"
```

### LLM Integration

The agent uses Bedrock Claude for intelligent content generation:

**Prompts:**
1. **Error Analysis:** Extract root cause from logs
2. **Resolution Summarization:** Condense command sequences into steps
3. **Prevention Recommendations:** Suggest preventive measures
4. **Similarity Detection:** Find related existing runbooks

**Example Prompt:**
```
Analyze this CI/CD incident and generate a runbook:

Error Logs:
{error_logs}

Resolution Commands:
{commands_executed}

Successful Outcome:
{success_indicators}

Generate a runbook following this template:
{runbook_template}

Focus on:
1. Clear problem description
2. Step-by-step resolution
3. Prevention recommendations
4. Related documentation links
```

## Integration Points

### EventBridge Rules
- CodeBuild state changes
- CloudFormation stack events
- Custom application events

### GitHub Actions
- Post-merge hook for fix commits
- PR comment with runbook suggestions

### Slack/Teams Notifications
- Alert when new runbook generated
- Request review for significant updates

### JIRA/ServiceNow
- Link runbooks to incident tickets
- Auto-attach runbooks to related issues

## File Structure

```
src/services/runbook/
├── __init__.py
├── runbook_agent.py           # Main orchestrator
├── incident_detector.py       # Break/fix detection
├── runbook_generator.py       # New runbook creation
├── runbook_updater.py         # Existing runbook updates
├── runbook_repository.py      # Storage and retrieval
├── templates/
│   ├── runbook_template.md    # Standard template
│   ├── quick_fix_template.md  # Short-form template
│   └── postmortem_template.md # Detailed incident template
└── patterns/
    ├── error_patterns.py      # Known error signatures
    ├── resolution_patterns.py # Common fix patterns
    └── service_mappings.py    # Service to runbook mappings
```

## Consequences

### Positive
- Automated knowledge capture reduces documentation burden
- Consistent runbook quality through templates
- Faster incident resolution via searchable knowledge base
- Improved onboarding with comprehensive documentation
- Audit trail of all incident resolutions

### Negative
- Initial setup and tuning of detection patterns
- LLM costs for content generation
- Potential for noisy/low-quality runbooks requiring review
- Storage costs for indexed runbooks

### Mitigations
- Human review workflow for auto-generated content
- Confidence scoring to filter low-quality detections
- Deduplication to prevent redundant runbooks
- Periodic cleanup of unused runbooks

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Auto-generated runbooks | 80% of incidents | Count / total incidents |
| Runbook accuracy | 90% useful | Human review scores |
| MTTR reduction | 30% improvement | Before/after comparison |
| Knowledge reuse | 50% of incidents | Runbook reference count |

## Implementation Plan

### Phase 1: Core Agent (Week 1-2)
- [ ] IncidentDetector with CloudWatch/CloudFormation sources
- [ ] RunbookGenerator with basic template
- [ ] File-based RunbookRepository

### Phase 2: Intelligence (Week 3-4)
- [ ] LLM integration for content generation
- [ ] Semantic search for similar runbooks
- [ ] Auto-update existing runbooks

### Phase 3: Integration (Week 5-6)
- [ ] EventBridge triggers
- [ ] GitHub Actions integration
- [ ] Notification system

## References

- [Existing Runbooks](../../docs/runbooks/)
- [ADR-030: AWS Agent Capability Replication](./ADR-030-aws-agent-capability-replication.md)
- [Incident Response Best Practices](https://sre.google/sre-book/managing-incidents/)
- [AWS Well-Architected Operational Excellence](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/)
