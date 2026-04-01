# ADR-001: Separate DynamoDB Tables for Job Types

**Status:** Deployed
**Date:** 2025-11-28
**Decision Makers:** Project Aura Team

## Context

When implementing the Git Ingestion Pipeline, we needed DynamoDB persistence for tracking ingestion jobs (clone, parse, index workflows). The existing `deploy/cloudformation/dynamodb.yaml` already contained a `CodeGenJobsTable` designed for tracking AI code generation tasks:

```yaml
CodeGenJobsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub '${ProjectName}-codegen-jobs-${Environment}'
    AttributeDefinitions:
      - AttributeName: jobId
      - AttributeName: userId
      - AttributeName: createdAt
      - AttributeName: status
    GlobalSecondaryIndexes:
      - IndexName: UserIdIndex
      - IndexName: StatusIndex
```

This table has a similar structure (jobId, status, createdAt) and could theoretically be reused for ingestion jobs, raising the question: **Should we reuse the existing table or create a dedicated one?**

## Decision

We chose to create a **dedicated `IngestionJobsTable`** rather than reusing `CodeGenJobsTable`.

```yaml
IngestionJobsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub '${ProjectName}-ingestion-jobs-${Environment}'
    AttributeDefinitions:
      - AttributeName: jobId
      - AttributeName: repositoryId
      - AttributeName: status
      - AttributeName: createdAt
    GlobalSecondaryIndexes:
      - IndexName: RepositoryIndex   # Query by repository
      - IndexName: StatusIndex       # Query by job status
    TimeToLiveSpecification:
      AttributeName: ttl
      Enabled: true                  # 30-day automatic cleanup
```

## Alternatives Considered

### Alternative 1: Reuse CodeGenJobsTable

Add a `jobType` attribute to distinguish between code generation and ingestion jobs.

**Pros:**
- Fewer DynamoDB tables to manage
- Single table for all job tracking
- Simpler infrastructure

**Cons:**
- Tighter coupling between unrelated services
- Complex queries mixing different job types
- Schema changes affecting multiple services
- Different GSI requirements (userId vs repositoryId)

### Alternative 2: Single Jobs Table with Type Discrimination

Create a generic `JobsTable` with a `jobType` partition in the GSI.

**Pros:**
- Unified job management interface
- Single monitoring dashboard

**Cons:**
- Hot partition risk if one job type dominates
- Different TTL requirements harder to enforce
- Still requires different GSI patterns

## Consequences

### Positive

1. **Domain Separation**
   - `CodeGenJobsTable`: Tracks AI code generation tasks (user-initiated)
   - `IngestionJobsTable`: Tracks repository ingestion pipeline jobs (webhook/automation-initiated)
   - Each service owns its own table with clear boundaries

2. **Schema Independence**
   - Ingestion jobs use `repositoryId` GSI for querying jobs by repository
   - Code generation jobs use `userId` GSI for querying jobs by user
   - No need for irrelevant indexes on either table

3. **Independent Scaling**
   - Ingestion jobs may have high burst activity during webhook events
   - Code generation jobs scale with user activity
   - Separate tables allow independent capacity planning and cost optimization

4. **Data Lifecycle Management**
   - Ingestion jobs have 30-day TTL (operational data)
   - Code generation jobs may need longer retention (audit/billing purposes)
   - Different TTL policies are cleanly separated

5. **Service Isolation**
   - `GitIngestionService` and future `CodeGenerationService` have no coupling
   - Schema migrations affect only one service
   - Easier testing with isolated data stores

### Negative

1. **More Tables to Manage**
   - Additional CloudFormation resources
   - More CloudWatch alarms/dashboards needed
   - Slightly higher operational complexity

2. **No Unified Job View**
   - Querying "all jobs" requires querying multiple tables
   - Cross-job analytics requires aggregation

### Mitigation

The negative consequences are acceptable because:
- DynamoDB on-demand pricing means unused tables have zero cost
- CloudFormation manages table lifecycle automatically
- A unified job dashboard can aggregate from multiple tables if needed

## References

- `deploy/cloudformation/dynamodb.yaml` - DynamoDB table definitions
- `src/services/job_persistence_service.py` - Ingestion job persistence implementation
- `src/services/git_ingestion_service.py` - Git ingestion pipeline using persistence
