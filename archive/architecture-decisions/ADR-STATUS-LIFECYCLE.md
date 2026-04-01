# ADR Status Lifecycle

This document defines the official status values for Architecture Decision Records (ADRs) in Project Aura.

## Status Definitions

| Status | Definition | Criteria |
|--------|------------|----------|
| **Draft** | Being written, not ready for review | Author still editing; incomplete sections |
| **Proposed** | Ready for review, awaiting decision | Complete ADR submitted for stakeholder review |
| **Rejected** | Reviewed and not accepted | Decision made not to proceed; reason documented |
| **Accepted** | Decision approved, implementation pending | Stakeholders agreed; work not yet started |
| **In Progress** | Actively being implemented | Work started but not complete |
| **Implemented** | Code/config complete, merged to main | All code merged; tests passing |
| **Deployed** | Live in dev/staging environment | CloudFormation stacks created; services running in dev |
| **Production** | Live in production environment | Deployed to prod (GovCloud when applicable) |
| **Deprecated** | Being phased out | Still works but no longer recommended |
| **Superseded** | Replaced by another ADR | Specify: "Superseded by ADR-XXX" |

## Status Lifecycle Flow

```
Draft → Proposed → Accepted → In Progress → Implemented → Deployed → Production
                ↓
            Rejected

Any status → Deprecated → Superseded
```

## Status Transition Rules

### Forward Transitions

1. **Draft → Proposed**: ADR is complete and ready for review
2. **Proposed → Accepted**: Stakeholders approve the decision
3. **Proposed → Rejected**: Stakeholders decide not to proceed
4. **Accepted → In Progress**: Implementation work begins
5. **In Progress → Implemented**: Code merged to main branch, tests passing
6. **Implemented → Deployed**: Infrastructure deployed to dev environment
7. **Deployed → Production**: Deployed to production/GovCloud

### Special Transitions

- **Any → Deprecated**: Decision is being phased out (document replacement plan)
- **Deprecated → Superseded**: New ADR fully replaces this one
- **In Progress → Accepted**: Work paused/rolled back (rare)

## How to Update ADR Status

When updating an ADR's status:

1. Change the `**Status:**` line in the ADR header
2. Add a dated note in the ADR body explaining the transition
3. Update the index table in `README.md`
4. For "Superseded" status, link to the replacement ADR

### Example Status Header

```markdown
**Status:** Deployed
**Date:** 2025-12-16 (Updated from Accepted)
```

## Verification Criteria

### Implemented
- [ ] Code exists in `src/` or `deploy/` directories
- [ ] Unit tests exist and pass
- [ ] Code merged to `main` branch

### Deployed
- [ ] CloudFormation stack exists in dev environment
- [ ] Services are running (verified via AWS CLI)
- [ ] Integration tests pass against deployed infrastructure

### Production
- [ ] Deployed to production AWS account
- [ ] Monitoring and alerting configured
- [ ] Runbook documentation complete (if applicable)

## Cross-Reference with Infrastructure

Use these commands to verify deployment status:

```bash
# List all deployed stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `aura`)].StackName' --output table

# Check specific stack
aws cloudformation describe-stacks --stack-name aura-{component}-dev
```

## Revision History

| Date | Change |
|------|--------|
| 2025-12-16 | Initial version - Established 10-status lifecycle |
