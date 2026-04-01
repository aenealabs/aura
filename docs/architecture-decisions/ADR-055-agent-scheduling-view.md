# ADR-055: Agent Scheduling View and Job Queue Management

**Status:** Proposed
**Date:** 2026-01-06
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-032 (Autonomy Framework), ADR-039 (Self-Service Test Environments), ADR-042 (Real-Time Agent Intervention)

---

## Executive Summary

This ADR establishes a unified Scheduling View for Project Aura that surfaces existing backend scheduling capabilities and introduces new user-configurable scheduling features. The platform has mature backend infrastructure for job queuing, scheduled tasks, and HITL workflows, but lacks a user-facing interface for viewing and managing scheduled agent activities.

**Core Thesis:** Users operating in both autonomous and HITL modes need visibility into what agents are scheduled to do, when tasks will execute, and the ability to manually schedule, reschedule, or cancel agent work. This visibility is essential for operational planning, compliance auditing, and effective human-machine collaboration.

**Key Outcomes:**
- Unified view of scheduled, queued, and running agent jobs
- Manual scheduling capability for agent tasks
- HITL approval queue with expiration tracking
- Timeline/calendar visualization of agent activity
- Recurring task configuration for automated workflows

---

## Context

### Current Backend Scheduling Infrastructure

Project Aura has extensive backend scheduling capabilities implemented across multiple services:

#### EventBridge Scheduled Tasks

| Service | Schedule | Purpose | Infrastructure |
|---------|----------|---------|----------------|
| HITL Expiration Processor | `rate(1 hour)` | Process expired approvals, auto-escalate CRITICAL/HIGH | `hitl-scheduler.yaml` |
| Threat Intelligence Pipeline | `cron(0 6 * * ? *)` | CVE/CISA feeds, GitHub advisories | `threat-intel-scheduler.yaml` |
| Test Environment Scheduler | `rate(5 minutes)` | Process scheduled environment provisioning | `test-env-scheduler.yaml` |
| Drift Detection | EventBridge | Config compliance checks | `drift-detection.yaml` |
| Realtime Monitoring | EventBridge | Agent health checks | `realtime-monitoring.yaml` |

#### Step Functions Workflows

| Workflow | Purpose |
|----------|---------|
| HITL Patch Workflow | Sandbox testing → HITL approval → deployment |
| Incident Investigation | Security incident response automation |
| SSR Training Pipeline | Self-play SWE-RL curriculum training |
| Test Environment Approval | Extended environment HITL approval |

#### Job Queue Architecture

| Component | Technology | Purpose |
|-----------|------------|---------|
| OrchestrationService | SQS + DynamoDB | Job submission, tracking, status |
| AgentQueueService | SQS | Inter-agent messaging (Coder, Reviewer, Validator) |
| CurriculumScheduler | In-memory | Training batch scheduling |

### Data Already Captured

The `OrchestrationService` captures comprehensive job metadata:

```python
class JobStatus(Enum):
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"

# DynamoDB: aura-orchestrator-jobs-{env}
{
    "job_id": "uuid",
    "user_id": "string",
    "job_type": "SECURITY_SCAN | CODE_REVIEW | PATCH_GENERATION | ...",
    "status": "JobStatus",
    "priority": "CRITICAL | HIGH | NORMAL | LOW",
    "created_at": "ISO8601",
    "scheduled_at": "ISO8601 | null",
    "started_at": "ISO8601 | null",
    "completed_at": "ISO8601 | null",
    "ttl": "epoch (7 days)"
}
```

### The Gap: No User-Facing Interface

Despite mature backend infrastructure, users cannot:

| Capability | Backend Support | Frontend Support |
|------------|-----------------|------------------|
| View scheduled/queued jobs | ✅ Data in DynamoDB | ❌ No UI |
| Schedule future agent tasks | ✅ `delay_seconds` param | ❌ No UI |
| View queue depth | ✅ `get_queue_depth()` | ❌ No visualization |
| View HITL approval queue | ✅ Data exists | ❌ No dedicated view |
| Schedule HITL actions | ❌ Not supported | ❌ N/A |
| Configure recurring tasks | ❌ Only infrastructure cron | ❌ N/A |
| Timeline visualization | ❌ N/A | ❌ None |

### User Personas and Use Cases

**DevOps Engineer (Autonomous Mode)**
- "I want to see what security scans are queued for tonight's maintenance window"
- "I need to schedule a full repository re-indexing for this weekend"
- "Show me the queue depth so I know if agents are backed up"

**Security Lead (HITL Mode)**
- "I need to see all pending approvals and when they expire"
- "Let me schedule a batch of patch deployments for our next change window"
- "I want weekly recurring vulnerability scans on critical repos"

**Platform Admin**
- "Show me agent activity over the past week in a timeline view"
- "I need to reschedule several jobs due to an infrastructure change"
- "Cancel all queued jobs for a repository being decommissioned"

---

## Decision

**Implement a comprehensive Agent Scheduling View consisting of four integrated components that provide visibility, control, and planning capabilities for agent activities.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCHEDULING VIEW ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  COMPONENT 1: JOB QUEUE DASHBOARD                                      │ │
│  │  ────────────────────────────────────────────────────────────────────  │ │
│  │  • Real-time queue depth visualization (by priority, by type)          │ │
│  │  • Active job cards with progress indicators                           │ │
│  │  • Queue health metrics (throughput, latency, error rate)              │ │
│  │  • WebSocket updates via existing execution infrastructure             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  COMPONENT 2: SCHEDULED JOBS LIST                                      │ │
│  │  ────────────────────────────────────────────────────────────────────  │ │
│  │  • Sortable/filterable table of pending scheduled jobs                 │ │
│  │  • Countdown to execution time                                         │ │
│  │  • Actions: View details, Reschedule, Cancel                           │ │
│  │  • Grouping by repository, job type, or scheduled date                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  COMPONENT 3: TIMELINE VIEW                                            │ │
│  │  ────────────────────────────────────────────────────────────────────  │ │
│  │  • Calendar/Gantt visualization of scheduled + completed jobs          │ │
│  │  • Drag-and-drop rescheduling (P2)                                     │ │
│  │  • Zoom levels: Day, Week, Month                                       │ │
│  │  • Color coding by job type and status                                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  COMPONENT 4: HITL APPROVAL QUEUE                                      │ │
│  │  ────────────────────────────────────────────────────────────────────  │ │
│  │  • Pending approvals with expiration countdown                         │ │
│  │  • Severity-based sorting (CRITICAL first)                             │ │
│  │  • Quick approve/reject actions                                        │ │
│  │  • Escalation status indicators                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### API Design

#### New Endpoints

```
# Scheduling endpoints
POST   /api/v1/schedule                    - Schedule a new job
GET    /api/v1/schedule                    - List scheduled jobs
GET    /api/v1/schedule/{schedule_id}      - Get scheduled job details
PUT    /api/v1/schedule/{schedule_id}      - Reschedule job
DELETE /api/v1/schedule/{schedule_id}      - Cancel scheduled job

# Queue status endpoints
GET    /api/v1/queue/status                - Get queue depth and health metrics
GET    /api/v1/queue/jobs                  - List queued jobs (paginated)

# Timeline endpoints
GET    /api/v1/jobs/timeline               - Get jobs for timeline view
       ?start_date=ISO8601&end_date=ISO8601&status=all|scheduled|completed

# Recurring tasks (Phase 2)
POST   /api/v1/schedule/recurring          - Create recurring task
GET    /api/v1/schedule/recurring          - List recurring tasks
PUT    /api/v1/schedule/recurring/{id}     - Update recurring task
DELETE /api/v1/schedule/recurring/{id}     - Delete recurring task
```

#### Request/Response Models

```python
# Schedule Job Request
class ScheduleJobRequest(BaseModel):
    job_type: JobType
    repository_id: Optional[str]
    scheduled_at: datetime  # ISO8601, must be future
    priority: Priority = Priority.NORMAL
    parameters: Dict[str, Any] = {}
    notify_on_completion: bool = True

# Schedule Job Response
class ScheduledJob(BaseModel):
    schedule_id: str
    job_type: JobType
    repository_id: Optional[str]
    scheduled_at: datetime
    created_at: datetime
    created_by: str
    status: ScheduleStatus  # PENDING, DISPATCHED, CANCELLED
    priority: Priority
    parameters: Dict[str, Any]

# Queue Status Response
class QueueStatus(BaseModel):
    total_queued: int
    by_priority: Dict[str, int]  # {"CRITICAL": 2, "HIGH": 5, ...}
    by_type: Dict[str, int]      # {"SECURITY_SCAN": 3, ...}
    active_jobs: int
    avg_wait_time_seconds: float
    throughput_per_hour: float
    oldest_queued_at: Optional[datetime]

# Timeline Response
class TimelineEntry(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    repository_name: Optional[str]
```

### Database Schema

#### New Table: `aura-scheduled-jobs-{env}`

```yaml
TableName: !Sub 'aura-scheduled-jobs-${Environment}'
KeySchema:
  - AttributeName: organization_id
    KeyType: HASH
  - AttributeName: schedule_id
    KeyType: RANGE
GlobalSecondaryIndexes:
  - IndexName: status-scheduled_at-index
    KeySchema:
      - AttributeName: status
        KeyType: HASH
      - AttributeName: scheduled_at
        KeyType: RANGE
  - IndexName: user-created_at-index
    KeySchema:
      - AttributeName: created_by
        KeyType: HASH
      - AttributeName: created_at
        KeyType: RANGE
TimeToLiveSpecification:
  AttributeName: ttl
  Enabled: true
```

#### New Table: `aura-recurring-tasks-{env}` (Phase 2)

```yaml
TableName: !Sub 'aura-recurring-tasks-${Environment}'
KeySchema:
  - AttributeName: organization_id
    KeyType: HASH
  - AttributeName: task_id
    KeyType: RANGE
Attributes:
  - task_id: string
  - cron_expression: string  # "0 6 * * MON" (every Monday 6AM)
  - job_type: string
  - parameters: map
  - enabled: boolean
  - last_run_at: string
  - next_run_at: string
  - created_by: string
```

### Frontend Components

```
frontend/src/
├── pages/
│   └── SchedulingPage.jsx              # Main scheduling view with tabs
├── components/
│   └── scheduling/
│       ├── JobQueueDashboard.jsx       # Queue depth, active jobs, metrics
│       ├── QueueDepthChart.jsx         # Real-time queue visualization
│       ├── ActiveJobCard.jsx           # Individual running job card
│       ├── ScheduledJobsList.jsx       # Table of scheduled jobs
│       ├── ScheduleJobModal.jsx        # Schedule new job form
│       ├── RescheduleModal.jsx         # Reschedule existing job
│       ├── JobTimelineView.jsx         # Calendar/Gantt visualization
│       ├── TimelineControls.jsx        # Zoom, date range, filters
│       ├── ApprovalQueueWidget.jsx     # HITL approvals with countdown
│       └── RecurringTaskManager.jsx    # Recurring task CRUD (Phase 2)
├── hooks/
│   └── useScheduling.js                # Scheduling state and API calls
└── services/
    └── schedulingApi.js                # API client for scheduling endpoints
```

### Integration with Existing Systems

#### OrchestrationService Integration

The new scheduling service will integrate with `OrchestrationService`:

```python
class SchedulingService:
    def __init__(self, orchestration_service: OrchestrationService):
        self.orchestration = orchestration_service
        self.table = dynamodb.Table(f"aura-scheduled-jobs-{env}")

    async def schedule_job(self, request: ScheduleJobRequest, user_id: str) -> ScheduledJob:
        """Schedule a job for future execution."""
        schedule_id = str(uuid.uuid4())
        scheduled_job = ScheduledJob(
            schedule_id=schedule_id,
            job_type=request.job_type,
            scheduled_at=request.scheduled_at,
            created_at=datetime.utcnow(),
            created_by=user_id,
            status=ScheduleStatus.PENDING,
            priority=request.priority,
            parameters=request.parameters,
        )

        # Store in DynamoDB
        self.table.put_item(Item=scheduled_job.to_dynamodb())

        return scheduled_job

    async def dispatch_due_jobs(self):
        """Called by scheduler Lambda every minute."""
        due_jobs = self._query_due_jobs()
        for job in due_jobs:
            # Submit to OrchestrationService
            await self.orchestration.submit_job(
                job_type=job.job_type,
                priority=job.priority,
                parameters=job.parameters,
                user_id=job.created_by,
            )
            # Update status
            self._update_status(job.schedule_id, ScheduleStatus.DISPATCHED)
```

#### WebSocket Integration

Leverage existing WebSocket infrastructure from `RealTimeExecutionPanel`:

```javascript
// useScheduling.js
export function useScheduling() {
  const [queueStatus, setQueueStatus] = useState(null);
  const [activeJobs, setActiveJobs] = useState([]);

  useEffect(() => {
    // Connect to existing execution WebSocket
    const ws = new WebSocket(WS_URL);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'QUEUE_STATUS_UPDATE') {
        setQueueStatus(data.payload);
      } else if (data.type === 'JOB_STATUS_UPDATE') {
        updateActiveJob(data.payload);
      }
    };

    return () => ws.close();
  }, []);

  return { queueStatus, activeJobs };
}
```

---

## Implementation Phases

### Phase 1: Core Scheduling View (P0)

**Duration:** 2-3 weeks
**Deliverables:**
- [ ] `SchedulingPage.jsx` with tabbed navigation
- [ ] `JobQueueDashboard.jsx` - queue depth, active jobs
- [ ] `ScheduledJobsList.jsx` - table with actions
- [ ] `ScheduleJobModal.jsx` - schedule new job
- [ ] Backend: `/api/v1/schedule` CRUD endpoints
- [ ] Backend: `/api/v1/queue/status` endpoint
- [ ] DynamoDB: `aura-scheduled-jobs-{env}` table
- [ ] Lambda: Scheduler dispatcher (extend `test-env-scheduler` pattern)

### Phase 2: Timeline and HITL Integration (P1)

**Duration:** 2 weeks
**Deliverables:**
- [ ] `JobTimelineView.jsx` - calendar visualization
- [ ] `ApprovalQueueWidget.jsx` - HITL queue with countdown
- [ ] Backend: `/api/v1/jobs/timeline` endpoint
- [ ] Integration with HITL approval service
- [ ] WebSocket updates for real-time status

### Phase 3: Recurring Tasks and Advanced Features (P2)

**Duration:** 2 weeks
**Deliverables:**
- [ ] `RecurringTaskManager.jsx` - CRUD for recurring tasks
- [ ] Backend: `/api/v1/schedule/recurring` endpoints
- [ ] DynamoDB: `aura-recurring-tasks-{env}` table
- [ ] Cron expression builder UI
- [ ] Drag-and-drop rescheduling in timeline

---

## Consequences

### Positive

1. **Operational Visibility:** Users gain insight into agent activities and can plan accordingly
2. **Manual Control:** HITL operators can schedule actions for optimal timing (maintenance windows, low-traffic periods)
3. **Compliance:** Audit trail of who scheduled what and when
4. **Resource Optimization:** Queue depth visibility helps identify bottlenecks
5. **Leverages Existing Infrastructure:** Builds on proven `OrchestrationService` and `test-env-scheduler` patterns

### Negative

1. **Additional Infrastructure:** New DynamoDB tables and Lambda functions increase operational overhead
2. **Complexity:** Scheduler dispatcher must handle edge cases (missed schedules, duplicate dispatches)
3. **UI Real Estate:** Adding another view to an already feature-rich application

### Mitigations

| Risk | Mitigation |
|------|------------|
| Duplicate job dispatch | Idempotency keys, conditional DynamoDB updates |
| Missed schedules | Catch-up logic, alerts for scheduler Lambda failures |
| UI complexity | Progressive disclosure, sensible defaults |
| Stale queue data | WebSocket real-time updates, polling fallback |

---

## Alternatives Considered

### 1. Embed Scheduling in Existing Views

**Approach:** Add scheduling widgets to Dashboard, Agent Registry, and Repository views.
**Rejected Because:** Fragmented experience, no unified timeline view, harder to find scheduled jobs.

### 2. External Scheduling Tool Integration

**Approach:** Integrate with external tools like Rundeck, Airflow, or AWS EventBridge Scheduler console.
**Rejected Because:** Context switching, no Aura-specific job types, poor UX for non-technical users.

### 3. CLI-Only Scheduling

**Approach:** Provide scheduling via CLI commands only.
**Rejected Because:** Excludes non-technical users, no visualization, poor discoverability.

---

## Security Considerations

### Authorization

- Scheduling jobs requires `jobs:schedule` permission
- Cancelling/rescheduling requires ownership or `jobs:admin` permission
- Recurring tasks require `jobs:recurring` permission (admin-level)

### Audit Logging

All scheduling actions logged to `aura-audit-logs-{env}`:
```json
{
  "action": "SCHEDULE_JOB",
  "user_id": "user-123",
  "schedule_id": "sched-456",
  "job_type": "SECURITY_SCAN",
  "scheduled_at": "2026-01-07T06:00:00Z",
  "timestamp": "2026-01-06T14:30:00Z"
}
```

### Rate Limiting

- Max 100 scheduled jobs per user per day
- Max 10 recurring tasks per organization
- Schedule window: 5 minutes to 30 days in future

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Scheduling View adoption | 60% of active users within 30 days | Analytics |
| Scheduled jobs created | >500/week after launch | DynamoDB metrics |
| Queue visibility usage | >100 views/day | Page analytics |
| Mean time to schedule | <30 seconds | UX timing |
| Scheduling errors | <1% of attempts | Error logs |

---

## References

- [OrchestrationService](../../src/services/orchestration_service.py) - Job queue implementation
- [Test Environment Scheduler](../../deploy/cloudformation/test-env-scheduler.yaml) - Scheduler pattern
- [HITL Approval Service](../../src/services/hitl_approval_service.py) - Approval queue
- [RealTimeExecutionPanel](../../frontend/src/components/execution/RealTimeExecutionPanel.jsx) - WebSocket pattern
- [ADR-032](./ADR-032-configurable-autonomy-framework.md) - Autonomy Framework
- [ADR-039](./ADR-039-self-service-test-environments.md) - Test Environment Scheduling
