# Cognitive Memory Architecture Schema

Comprehensive schema for implementing neuroscience-inspired memory systems in specialized agents.

---

## Schema Metadata

| Field | Value |
|-------|-------|
| **Name** | Cognitive Memory Architecture Schema |
| **Domain** | COGNITIVE |
| **Version** | 1.0.0 |
| **Last Updated** | 2025-12-04 |
| **Target Accuracy** | 85% |
| **Related ADR** | ADR-021 |

---

## Neuroscience-to-Architecture Mapping

| Brain Region | Memory Type | Implementation | Storage |
|-------------|-------------|----------------|---------|
| **Hippocampus** | Episodic | Specific problem-solving instances | DynamoDB |
| **Neocortex** | Semantic | Guardrails, patterns, abstractions | Neptune + OpenSearch |
| **Basal Ganglia** | Procedural | Workflows, action sequences | DynamoDB + Neptune |
| **Prefrontal Cortex** | Working | Active task context (limited) | In-memory |
| **Hippocampal Replay** | Consolidation | Pattern extraction pipeline | Lambda + Step Functions |

---

## 1. Memory Type Schemas

### 1.1 Episodic Memory Schema

Stores specific problem-solving episodes with full context snapshots.

```yaml
EpisodicMemory:
  type: object
  description: "A specific problem-solving episode with full context"

  properties:
    # Identity
    episode_id:
      type: string
      format: uuid
      description: "Unique identifier"
      example: "ep-20251204-143022-abc123"

    timestamp:
      type: string
      format: date-time
      description: "When this episode occurred"

    domain:
      type: string
      enum: [CICD, IAM, SECURITY, CFN, KUBERNETES, API, GRAPH, AGENT]
      description: "Primary domain of this episode"

    # Context Snapshot
    task_context:
      type: object
      properties:
        task_description:
          type: string
          description: "What the agent was trying to accomplish"

        input_query:
          type: string
          description: "Original user/system request"

        codebase_state:
          type: object
          properties:
            git_commit:
              type: string
              description: "Git commit hash at episode time"
            modified_files:
              type: array
              items:
                type: string
              description: "Files touched during episode"

        retrieved_context:
          type: array
          description: "What memories/guardrails were retrieved"
          items:
            type: object
            properties:
              memory_id:
                type: string
              memory_type:
                type: string
                enum: [EPISODIC, SEMANTIC, PROCEDURAL]
              relevance_score:
                type: number
                minimum: 0
                maximum: 1

    # Decision Record
    decision:
      type: object
      properties:
        action_taken:
          type: string
          description: "The action/decision made"

        reasoning:
          type: string
          description: "Why this decision was made"

        confidence_at_decision:
          type: number
          minimum: 0
          maximum: 1
          description: "Agent's confidence when making decision"

        strategy_used:
          type: string
          enum: [PROCEDURAL_EXECUTION, SCHEMA_GUIDED, ACTIVE_LEARNING, CAUTIOUS_EXPLORATION]

    # Outcome
    outcome:
      type: object
      properties:
        status:
          type: string
          enum: [SUCCESS, FAILURE, PARTIAL, ESCALATED]

        details:
          type: string
          description: "What specifically happened"

        error_message:
          type: string
          nullable: true
          description: "Error message if failure"

        duration_ms:
          type: integer
          description: "How long execution took"

    # Learning Signals
    learning_signals:
      type: object
      properties:
        feedback_received:
          type: string
          nullable: true
          description: "Human feedback if any"

        guardrail_violated:
          type: string
          nullable: true
          description: "If a guardrail was hit, which one"

        pattern_discovered:
          type: string
          nullable: true
          description: "New pattern identified during episode"

        confidence_calibration:
          type: number
          description: "Difference between predicted and actual outcome"

    # Retrieval Optimization
    embedding:
      type: array
      items:
        type: number
      description: "1536-dim vector embedding for similarity search"

    keywords:
      type: array
      items:
        type: string
      description: "Extracted keywords for filtering"

    # Lifecycle
    ttl:
      type: integer
      description: "Unix timestamp for auto-deletion (episodic decay)"

    consolidated:
      type: boolean
      default: false
      description: "Whether patterns extracted to semantic memory"

  required:
    - episode_id
    - timestamp
    - domain
    - task_context
    - decision
    - outcome
```

### 1.2 Semantic Memory Schema

Stores generalized knowledge extracted from episodes.

```yaml
SemanticMemory:
  type: object
  description: "Generalized knowledge independent of specific episodes"

  properties:
    # Identity
    memory_id:
      type: string
      format: uuid
      example: "sem-guardrail-cicd-001"

    memory_type:
      type: string
      enum: [GUARDRAIL, PATTERN, SCHEMA, CONCEPT, ANTI_PATTERN]
      description: "Type of semantic knowledge"

    domain:
      type: string
      enum: [CICD, IAM, SECURITY, CFN, KUBERNETES, API, GRAPH, AGENT, GENERAL]

    # Content
    title:
      type: string
      maxLength: 100
      description: "Human-readable title"

    content:
      type: string
      description: "The knowledge content (markdown supported)"

    severity:
      type: string
      enum: [CRITICAL, HIGH, MEDIUM, LOW]
      description: "Importance level for prioritization"

    # Reliability Metrics
    confidence:
      type: number
      minimum: 0
      maximum: 1
      description: "How reliable this knowledge is (evidence-based)"

    evidence_count:
      type: integer
      minimum: 0
      description: "Number of supporting episodes"

    contradiction_count:
      type: integer
      minimum: 0
      description: "Number of contradicting episodes"

    last_validated:
      type: string
      format: date-time
      description: "When last confirmed correct"

    # Relationships (stored in Neptune graph)
    relationships:
      type: object
      properties:
        related_to:
          type: array
          description: "Related semantic memories"
          items:
            type: object
            properties:
              memory_id:
                type: string
              relationship_type:
                type: string
                enum: [RELATED, PREREQUISITE, EXTENDS, CONFLICTS]
              strength:
                type: number
                minimum: 0
                maximum: 1

        derived_from:
          type: array
          description: "Episode IDs this was extracted from"
          items:
            type: string

        supersedes:
          type: string
          nullable: true
          description: "If this replaces older knowledge"

    # Applicability Conditions
    applicability:
      type: object
      properties:
        preconditions:
          type: array
          items:
            type: string
          description: "Conditions that must be true"

        file_patterns:
          type: array
          items:
            type: string
          description: "File patterns where this applies"
          example: ["deploy/buildspecs/*.yml", "deploy/cloudformation/*.yaml"]

        tech_stack:
          type: array
          items:
            type: string
          description: "Technologies this applies to"
          example: ["CodeBuild", "CloudFormation", "YAML"]

    # Retrieval Optimization
    embedding:
      type: array
      items:
        type: number

    keywords:
      type: array
      items:
        type: string

    # Lifecycle
    created_at:
      type: string
      format: date-time

    updated_at:
      type: string
      format: date-time

    status:
      type: string
      enum: [ACTIVE, DEPRECATED, ARCHIVED]
      default: ACTIVE

  required:
    - memory_id
    - memory_type
    - domain
    - title
    - content
    - confidence
```

### 1.3 Procedural Memory Schema

Stores learned action sequences and workflows.

```yaml
ProceduralMemory:
  type: object
  description: "A learned sequence of actions for accomplishing a goal"

  properties:
    # Identity
    procedure_id:
      type: string
      format: uuid
      example: "proc-cfn-deploy-001"

    name:
      type: string
      description: "Human-readable procedure name"

    domain:
      type: string
      enum: [CICD, IAM, SECURITY, CFN, KUBERNETES, API, GRAPH, AGENT]

    version:
      type: integer
      minimum: 1
      description: "Procedure version number"

    # Goal and Triggers
    goal:
      type: object
      properties:
        description:
          type: string
          description: "What this procedure accomplishes"

        success_criteria:
          type: array
          items:
            type: string
          description: "Conditions that define success"

    trigger_conditions:
      type: array
      description: "When to activate this procedure"
      items:
        type: object
        properties:
          condition_type:
            type: string
            enum: [TASK_MATCH, CONTEXT_MATCH, ERROR_MATCH, EXPLICIT_REQUEST]
          pattern:
            type: string
            description: "Regex or keyword pattern"
          confidence_threshold:
            type: number
            description: "Minimum confidence to trigger"

    # The Procedure Steps
    steps:
      type: array
      items:
        type: object
        properties:
          step_id:
            type: string
          order:
            type: integer
          action:
            type: string
            description: "Action to perform"
          tool:
            type: string
            nullable: true
            description: "Tool to use (Bash, Edit, Grep, etc.)"
          parameters:
            type: object
            description: "Action parameters"
          expected_outcome:
            type: string
          error_handling:
            type: object
            properties:
              on_error:
                type: string
                enum: [RETRY, SKIP, ABORT, BRANCH]
              retry_count:
                type: integer
              fallback_step:
                type: string

    # Branching Logic
    branching:
      type: array
      description: "Conditional flow control"
      items:
        type: object
        properties:
          from_step:
            type: string
          condition:
            type: string
            description: "Condition expression"
          true_branch:
            type: string
            description: "Step ID if condition true"
          false_branch:
            type: string
            description: "Step ID if condition false"

    # Performance Metrics
    metrics:
      type: object
      properties:
        success_rate:
          type: number
          minimum: 0
          maximum: 1
          description: "Historical success rate"

        execution_count:
          type: integer
          description: "Total executions"

        avg_duration_ms:
          type: integer
          description: "Average execution time"

        last_executed:
          type: string
          format: date-time

        failure_modes:
          type: array
          items:
            type: object
            properties:
              step_id:
                type: string
              failure_count:
                type: integer
              common_error:
                type: string

    # Learning Metadata
    derived_from:
      type: array
      items:
        type: string
      description: "Episode IDs where this was learned"

    required_guardrails:
      type: array
      items:
        type: string
      description: "Guardrails that must be loaded"

  required:
    - procedure_id
    - name
    - domain
    - goal
    - steps
```

### 1.4 Working Memory Schema

Represents active context during task execution.

```yaml
WorkingMemory:
  type: object
  description: "Active context during task execution (limited capacity)"

  properties:
    session_id:
      type: string
      format: uuid

    capacity:
      type: integer
      default: 7
      description: "Maximum active items (Miller's Law: 7±2)"

    # Current Task
    current_task:
      type: object
      properties:
        task_id:
          type: string
        description:
          type: string
        domain:
          type: string
        started_at:
          type: string
          format: date-time

    # Retrieved Memories (capacity-limited)
    retrieved_memories:
      type: array
      maxItems: 9  # 7+2 upper bound
      items:
        type: object
        properties:
          memory_id:
            type: string
          memory_type:
            type: string
            enum: [EPISODIC, SEMANTIC, PROCEDURAL]
          relevance_score:
            type: number
          salience:
            type: number
            description: "Attention weight (decays over time)"
          last_accessed:
            type: string
            format: date-time

    # Active Schema
    active_schema:
      type: object
      nullable: true
      properties:
        schema_id:
          type: string
        name:
          type: string

    # Pending Actions
    pending_actions:
      type: array
      items:
        type: object
        properties:
          action_id:
            type: string
          description:
            type: string
          priority:
            type: integer
          status:
            type: string
            enum: [PENDING, IN_PROGRESS, COMPLETED, BLOCKED]

    # Attention State
    attention_state:
      type: object
      properties:
        focus_item:
          type: string
          description: "Currently focused memory/action"
        attention_weights:
          type: object
          additionalProperties:
            type: number
          description: "Salience weights for each item"

    # Context Budget
    token_budget:
      type: object
      properties:
        total:
          type: integer
          default: 4000
        used:
          type: integer
        remaining:
          type: integer
```

---

## 2. Consolidation Pipeline Schema

### 2.1 Pattern Extraction Schema

```yaml
PatternExtraction:
  type: object
  description: "Pattern extracted from episode cluster"

  properties:
    pattern_id:
      type: string

    source_episodes:
      type: array
      items:
        type: string
      description: "Episode IDs used to extract pattern"
      minItems: 3  # Minimum episodes for pattern confidence

    cluster_similarity:
      type: number
      description: "How similar the source episodes were"

    # Extracted Pattern
    pattern:
      type: object
      properties:
        context_features:
          type: array
          description: "Context features that predict this pattern"
          items:
            type: object
            properties:
              feature:
                type: string
              importance:
                type: number

        decision_pattern:
          type: string
          description: "The common decision/action pattern"

        outcome_association:
          type: string
          enum: [SUCCESS, FAILURE, MIXED]

        preconditions:
          type: array
          items:
            type: string

    # Validation
    validation:
      type: object
      properties:
        holdout_accuracy:
          type: number
          description: "Accuracy on held-out episodes"

        confidence_interval:
          type: array
          items:
            type: number
          minItems: 2
          maxItems: 2
          description: "[lower, upper] 95% CI"

    # Proposed Action
    proposed_action:
      type: string
      enum: [CREATE_GUARDRAIL, CREATE_PATTERN, STRENGTHEN_EXISTING, DISCARD]

    target_memory_id:
      type: string
      nullable: true
      description: "If strengthening existing, which memory"
```

### 2.2 Consolidation Event Schema

```yaml
ConsolidationEvent:
  type: object
  description: "Record of a consolidation cycle"

  properties:
    event_id:
      type: string

    timestamp:
      type: string
      format: date-time

    # Input
    input:
      type: object
      properties:
        episodes_processed:
          type: integer
        time_window:
          type: string
          description: "ISO 8601 duration"

    # Output
    output:
      type: object
      properties:
        patterns_extracted:
          type: integer
        memories_created:
          type: integer
        memories_strengthened:
          type: integer
        episodes_pruned:
          type: integer

    # Patterns
    patterns:
      type: array
      items:
        $ref: '#/PatternExtraction'

    # Status
    status:
      type: string
      enum: [COMPLETED, PARTIAL, FAILED]

    errors:
      type: array
      items:
        type: string
```

---

## 3. Retrieval Schema

### 3.1 Retrieval Cue Schema

```yaml
RetrievalCue:
  type: object
  description: "Sparse cue for pattern completion retrieval"

  properties:
    # Text-based cues
    task_description:
      type: string
      description: "What the agent is trying to do"

    error_message:
      type: string
      nullable: true
      description: "Error message if debugging"

    # Structural cues
    file_path:
      type: string
      nullable: true

    code_entity:
      type: string
      nullable: true
      description: "Function/class name"

    # Domain filtering
    domain:
      type: string
      nullable: true

    keywords:
      type: array
      items:
        type: string

    # Pre-computed embedding
    embedding:
      type: array
      items:
        type: number
      nullable: true

    # Retrieval parameters
    max_results:
      type: integer
      default: 5

    memory_types:
      type: array
      items:
        type: string
        enum: [EPISODIC, SEMANTIC, PROCEDURAL]
      default: [SEMANTIC, PROCEDURAL]

    min_confidence:
      type: number
      default: 0.5
```

### 3.2 Retrieved Memory Schema

```yaml
RetrievedMemory:
  type: object
  description: "Memory retrieved via pattern completion"

  properties:
    # Source
    memory_id:
      type: string

    memory_type:
      type: string
      enum: [EPISODIC, SEMANTIC, PROCEDURAL]

    # Retrieval Scores
    scores:
      type: object
      properties:
        keyword_score:
          type: number
        vector_similarity:
          type: number
        graph_relevance:
          type: number
        combined_score:
          type: number

    # Completed Content
    full_content:
      type: object
      description: "Full memory content (varies by type)"

    relevant_portions:
      type: array
      items:
        type: string
      description: "Most relevant excerpts for current task"

    # Pattern Completion Metadata
    completion_confidence:
      type: number
      description: "Confidence in pattern completion accuracy"

    completion_method:
      type: string
      enum: [EXACT_MATCH, PARTIAL_MATCH, INFERRED]

    # Related Information
    related_procedures:
      type: array
      items:
        type: string
      description: "Procedure IDs that use this memory"

    related_guardrails:
      type: array
      items:
        type: string
```

---

## 4. Metacognition Schema

### 4.1 Confidence Estimate Schema

```yaml
ConfidenceEstimate:
  type: object
  description: "Metacognitive confidence assessment"

  properties:
    # Overall Score
    score:
      type: number
      minimum: 0
      maximum: 1
      description: "Overall confidence (weighted combination)"

    # Component Factors
    factors:
      type: object
      properties:
        memory_coverage:
          type: number
          description: "Do we have relevant experience?"

        memory_agreement:
          type: number
          description: "Do memories agree on approach?"

        recency:
          type: number
          description: "How recent are relevant memories?"

        outcome_history:
          type: number
          description: "How have similar decisions fared?"

        schema_match:
          type: number
          description: "Does task match a known schema?"

    # Weights Used
    weights:
      type: object
      additionalProperties:
        type: number

    # Uncertainty Sources
    uncertainties:
      type: array
      items:
        type: string
      description: "Factors with score < 0.5"

    # Recommended Action
    recommended_action:
      type: string
      enum:
        - PROCEED_AUTONOMOUS    # confidence >= 0.85
        - PROCEED_WITH_LOGGING  # confidence >= 0.70
        - REQUEST_REVIEW        # confidence >= 0.50
        - ESCALATE_TO_HUMAN     # confidence < 0.50

    # Confidence Interval
    confidence_interval:
      type: array
      items:
        type: number
      minItems: 2
      maxItems: 2
      description: "[lower, upper] bounds"
```

### 4.2 Strategy Schema

```yaml
Strategy:
  type: object
  description: "Selected problem-solving strategy"

  properties:
    strategy_type:
      type: string
      enum:
        - PROCEDURAL_EXECUTION  # High confidence, matching procedure
        - SCHEMA_GUIDED         # Medium confidence, use schema
        - ACTIVE_LEARNING       # Low confidence, ask questions
        - CAUTIOUS_EXPLORATION  # Default, heavy logging
        - HUMAN_GUIDANCE        # Escalate to human

    # Strategy-Specific Configuration
    procedure:
      type: object
      nullable: true
      description: "If PROCEDURAL_EXECUTION"
      properties:
        procedure_id:
          type: string
        expected_duration_ms:
          type: integer

    schema:
      type: object
      nullable: true
      description: "If SCHEMA_GUIDED"
      properties:
        schema_id:
          type: string
        required_guardrails:
          type: array
          items:
            type: string

    questions:
      type: array
      nullable: true
      description: "If ACTIVE_LEARNING"
      items:
        type: object
        properties:
          question:
            type: string
          priority:
            type: integer

    # Fallback
    fallback_strategy:
      type: string
      nullable: true

    # Logging Level
    logging_level:
      type: string
      enum: [MINIMAL, NORMAL, VERBOSE]
      default: NORMAL

    # Checkpointing
    checkpoint_frequency:
      type: string
      enum: [NONE, LOW, MEDIUM, HIGH]
      default: MEDIUM
```

---

## 5. Integration Schemas

### 5.1 Extended HybridContext Schema

Extension to existing `HybridContext` for cognitive memory integration.

```yaml
HybridContextExtension:
  type: object
  description: "Extension to HybridContext for cognitive memory"

  properties:
    # Existing fields inherited from HybridContext
    # ... (items, query, target_entity, session_id)

    # Cognitive Memory Extension
    cognitive_context:
      type: object
      properties:
        retrieved_memories:
          type: array
          items:
            $ref: '#/RetrievedMemory'

        confidence_estimate:
          $ref: '#/ConfidenceEstimate'

        selected_strategy:
          $ref: '#/Strategy'

        working_memory_state:
          type: object
          properties:
            capacity_used:
              type: integer
            focus_item:
              type: string

        # Audit Trail
        retrieval_trace:
          type: object
          properties:
            cue_used:
              $ref: '#/RetrievalCue'
            retrieval_time_ms:
              type: integer
            memories_considered:
              type: integer
            memories_selected:
              type: integer
```

### 5.2 Agent Execution Record Schema

```yaml
AgentExecutionRecord:
  type: object
  description: "Complete record of agent task execution for episodic storage"

  properties:
    execution_id:
      type: string

    agent_type:
      type: string
      enum: [CODER, REVIEWER, VALIDATOR, SECURITY, ORCHESTRATOR]

    # Input
    input:
      type: object
      properties:
        task:
          type: string
        hybrid_context:
          $ref: '#/HybridContextExtension'

    # Cognitive State
    cognitive_state:
      type: object
      properties:
        confidence_at_start:
          type: number
        strategy_selected:
          type: string
        guardrails_loaded:
          type: array
          items:
            type: string
        procedures_available:
          type: array
          items:
            type: string

    # Execution
    execution:
      type: object
      properties:
        actions_taken:
          type: array
          items:
            type: object
            properties:
              action:
                type: string
              timestamp:
                type: string
                format: date-time
              result:
                type: string

        errors_encountered:
          type: array
          items:
            type: object
            properties:
              error:
                type: string
              recovery_action:
                type: string

    # Output
    output:
      type: object
      properties:
        result:
          type: string
        success:
          type: boolean
        confidence_at_end:
          type: number

    # Learning
    learning_opportunities:
      type: array
      items:
        type: object
        properties:
          type:
            type: string
            enum: [NEW_PATTERN, GUARDRAIL_VIOLATION, CONFIDENCE_MISCALIBRATION]
          details:
            type: string
```

---

## 6. Accuracy Monitoring Schema

### 6.1 Accuracy Metrics Schema

```yaml
AccuracyMetrics:
  type: object
  description: "Rolling accuracy metrics for 85% target"

  properties:
    window:
      type: string
      description: "Time window for metrics"

    timestamp:
      type: string
      format: date-time

    # Overall Accuracy
    overall_accuracy:
      type: number
      description: "Correct decisions / total decisions"

    # By Confidence Band
    by_confidence_band:
      type: object
      properties:
        high:  # >= 0.85
          type: object
          properties:
            count:
              type: integer
            accuracy:
              type: number
            target:
              type: number
              default: 0.95

        medium:  # 0.50-0.84
          type: object
          properties:
            count:
              type: integer
            accuracy:
              type: number
            target:
              type: number
              default: 0.85

        low:  # < 0.50
          type: object
          properties:
            count:
              type: integer
            accuracy:
              type: number
            target:
              type: number
              default: 0.75

    # By Domain
    by_domain:
      type: object
      additionalProperties:
        type: object
        properties:
          count:
            type: integer
          accuracy:
            type: number

    # Failure Analysis
    failure_analysis:
      type: object
      properties:
        top_failure_domains:
          type: array
          items:
            type: string

        confidence_miscalibration:
          type: number
          description: "Average |predicted - actual| confidence"

        novel_error_rate:
          type: number
          description: "% errors not matching known guardrails"

    # Alerts
    alerts:
      type: array
      items:
        type: object
        properties:
          severity:
            type: string
            enum: [WARNING, CRITICAL]
          message:
            type: string
          recommended_action:
            type: string
```

---

## Usage Guidelines

### Loading Cognitive Context

```python
# Example: Loading cognitive context for a task
async def load_cognitive_context(task: str, domain: str) -> HybridContextExtension:
    # 1. Create retrieval cue
    cue = RetrievalCue(
        task_description=task,
        domain=domain,
        keywords=extract_keywords(task),
        embedding=await embed(task)
    )

    # 2. Retrieve memories via pattern completion
    memories = await pattern_completion_retrieve(cue)

    # 3. Estimate confidence
    confidence = estimate_confidence(task, memories)

    # 4. Select strategy
    strategy = select_strategy(confidence, get_procedures(domain))

    # 5. Build extended context
    return HybridContextExtension(
        cognitive_context=CognitiveContext(
            retrieved_memories=memories,
            confidence_estimate=confidence,
            selected_strategy=strategy
        )
    )
```

### Recording Episodes

```python
# Example: Recording episode after task completion
async def record_episode(execution_record: AgentExecutionRecord):
    episode = EpisodicMemory(
        episode_id=generate_id(),
        timestamp=datetime.now(),
        domain=execution_record.input.hybrid_context.domain,
        task_context=TaskContext(
            task_description=execution_record.input.task,
            retrieved_context=execution_record.cognitive_state.guardrails_loaded
        ),
        decision=Decision(
            action_taken=execution_record.execution.actions_taken[-1],
            reasoning=execution_record.cognitive_state.strategy_selected,
            confidence_at_decision=execution_record.cognitive_state.confidence_at_start
        ),
        outcome=Outcome(
            status=OutcomeStatus.SUCCESS if execution_record.output.success else OutcomeStatus.FAILURE,
            details=execution_record.output.result
        ),
        embedding=await embed(execution_record.input.task),
        ttl=calculate_ttl(execution_record.output.success)  # Keep failures longer
    )

    await episodic_store.put(episode)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-04 | Initial schema from cognitive architecture design |
