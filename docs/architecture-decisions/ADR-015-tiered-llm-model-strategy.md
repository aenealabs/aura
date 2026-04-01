# ADR-015: Tiered LLM Model Strategy

**Status:** Deployed
**Date:** 2025-12-01
**Decision Makers:** Project Aura Team
**Related:** ADR-008 (Bedrock LLM Cost Controls), ADR-014 (LLM-Enhanced Agent Search Pattern)

## Context

Project Aura agents use LLM calls for various operations with different accuracy requirements:

| Operation Type | Accuracy Requirement | Example |
|----------------|---------------------|---------|
| Query intent extraction | Low-Medium | "What type of files is the user looking for?" |
| Query expansion | Low | "Generate related search terms" |
| Security result ranking | **High** | "Which files contain actual vulnerabilities?" |
| Vulnerability assessment | **Critical** | "Is this a true positive? What's the severity?" |
| Patch generation | **Critical** | "Generate a security patch for this CVE" |

ADR-008 established cost controls and mentioned model routing, but didn't specify:
- Which operations use which models
- How to implement tiered selection
- Fallback behavior when accurate model unavailable

**Key Question:** How should agents select between fast/cheap models and accurate/expensive models?

**Constraints:**
- Must respect ADR-008 budget limits
- Security-critical operations cannot compromise accuracy
- Must work with AWS Bedrock (FedRAMP High in GovCloud)
- Must be consistent across all agents

## Decision

We chose a **Task-Based Tiered Model Selection** pattern with explicit model assignment per operation type.

### Model Tiers

| Tier | Model | Latency | Cost/1M tokens | Use Case |
|------|-------|---------|----------------|----------|
| **Fast** | Claude 3 Haiku | ~80-150ms | ~$1.50 | Classification, expansion, simple extraction |
| **Accurate** | Claude Sonnet 4.5 | ~200-500ms | ~$18.00 | Security analysis, ranking, standard patches |
| **Maximum** | Claude Opus 4.5 | ~500-1000ms | ~$75.00 | Cross-codebase correlation, novel threats, complex refactoring |

### When to Use Maximum Tier (Opus)

Opus is reserved for operations requiring **extended reasoning across large contexts** or **novel problem-solving**:

| Operation | Why Opus Required | Example |
|-----------|-------------------|---------|
| Cross-codebase vulnerability correlation | Connects patterns across 50+ files | "This auth bug in module A enables injection in module C" |
| Novel zero-day detection | Identifies attack patterns not in training data | "Unusual control flow suggests new exploit technique" |
| Multi-file refactoring patches | Coordinated changes with dependency awareness | "Refactor 12 tightly-coupled files without breaking interfaces" |
| Compliance edge case interpretation | Nuanced SOX/CMMC judgment calls | "Does this logging approach satisfy AC-2(4)?" |
| Architecture impact analysis | System-wide implications of changes | "How does this change affect 200 downstream consumers?" |

**Cost Justification:** At ~$37.50/month for 100 Opus calls, the cost of missing a real vulnerability exceeds the model cost.

### Operation-to-Model Mapping

```python
class ModelTier(Enum):
    FAST = "fast"          # Haiku - simple classification, expansion
    ACCURATE = "accurate"  # Sonnet - security analysis, standard patches
    MAXIMUM = "maximum"    # Opus - cross-codebase reasoning, novel threats

OPERATION_MODEL_MAP: dict[str, ModelTier] = {
    # Fast tier - simple, low-stakes tasks (~40% of calls)
    "query_intent_analysis": ModelTier.FAST,
    "query_expansion": ModelTier.FAST,
    "file_type_classification": ModelTier.FAST,
    "syntax_validation": ModelTier.FAST,
    "format_conversion": ModelTier.FAST,
    "metadata_extraction": ModelTier.FAST,
    "simple_summarization": ModelTier.FAST,

    # Accurate tier - security-critical operations (~55% of calls)
    "vulnerability_ranking": ModelTier.ACCURATE,
    "security_result_scoring": ModelTier.ACCURATE,
    "patch_generation": ModelTier.ACCURATE,
    "code_review": ModelTier.ACCURATE,
    "threat_assessment": ModelTier.ACCURATE,
    "compliance_check": ModelTier.ACCURATE,
    "single_file_analysis": ModelTier.ACCURATE,
    "cve_impact_assessment": ModelTier.ACCURATE,

    # Maximum tier - complex reasoning operations (~5% of calls)
    "cross_codebase_correlation": ModelTier.MAXIMUM,
    "novel_threat_detection": ModelTier.MAXIMUM,
    "multi_file_refactoring": ModelTier.MAXIMUM,
    "compliance_edge_case": ModelTier.MAXIMUM,
    "architecture_impact_analysis": ModelTier.MAXIMUM,
    "zero_day_pattern_analysis": ModelTier.MAXIMUM,
    "dependency_chain_reasoning": ModelTier.MAXIMUM,
}
```

### Implementation Pattern

```python
class BedrockLLMService:
    """Tiered LLM service with task-based model selection."""

    MODEL_IDS = {
        ModelTier.FAST: "anthropic.claude-3-haiku-20240307-v1:0",
        ModelTier.ACCURATE: "anthropic.claude-sonnet-4-5-20250929-v1:0",
        ModelTier.MAXIMUM: "anthropic.claude-opus-4-5-20251101-v1:0",
    }

    async def invoke(
        self,
        prompt: str,
        operation: str,
        override_tier: ModelTier | None = None,
    ) -> str:
        """Invoke LLM with automatic model selection based on operation."""
        tier = override_tier or OPERATION_MODEL_MAP.get(operation, ModelTier.ACCURATE)
        model_id = self.MODEL_IDS[tier]

        # Log for cost attribution (per ADR-008)
        self._log_request(operation=operation, tier=tier, model=model_id)

        return await self._invoke_bedrock(model_id, prompt)

    # Convenience methods for common patterns
    async def analyze_intent(self, query: str) -> dict:
        """Fast model for query understanding."""
        return await self.invoke(prompt, operation="query_intent_analysis")

    async def rank_security_results(self, results: list, query: str) -> list:
        """Accurate model for security-critical ranking."""
        return await self.invoke(prompt, operation="security_result_scoring")
```

### Agent Integration

```python
class FilesystemNavigatorAgent:
    async def intelligent_search(self, query: str) -> list[FileMatch]:
        # Step 1: Fast model for intent (80-150ms)
        intent = await self.llm_client.invoke(
            prompt=self._build_intent_prompt(query),
            operation="query_intent_analysis"  # Uses Haiku
        )

        # Step 2: Fast model for expansion (80-150ms)
        expanded = await self.llm_client.invoke(
            prompt=self._build_expansion_prompt(query, intent),
            operation="query_expansion"  # Uses Haiku
        )

        # Step 3: Accurate model for ranking (200-500ms)
        ranked = await self.llm_client.invoke(
            prompt=self._build_ranking_prompt(results, query),
            operation="security_result_scoring"  # Uses Sonnet
        )

        return ranked
```

### Latency Comparison

| Approach | Total Latency | Cost/Query | Accuracy |
|----------|--------------|------------|----------|
| All Opus | 1,500-3,000ms | ~$0.015 | Maximum |
| All Sonnet | 600-1,500ms | ~$0.003 | High |
| **Tiered (Haiku + Sonnet + Opus)** | **360-1,500ms** | **~$0.001-0.005** | **Optimal per task** |
| All Haiku (not recommended) | 240-450ms | ~$0.0003 | Low |

**Expected Distribution:**
- ~40% Fast tier (Haiku): Simple tasks
- ~55% Accurate tier (Sonnet): Standard security operations
- ~5% Maximum tier (Opus): Complex cross-codebase reasoning

### Configuration Hierarchy

| Level | Control | Example |
|-------|---------|---------|
| Default | `OPERATION_MODEL_MAP` | Built-in operation→model mapping |
| Platform | Environment variable | `AURA_LLM_DEFAULT_TIER=accurate` |
| Runtime | `override_tier` parameter | Force accurate for specific call |
| Emergency | Budget exhaustion | Falls back to fast tier |

## Alternatives Considered

### Alternative 1: Single Model for All Operations

Use Claude Sonnet for everything.

**Pros:**
- Simplest implementation
- Consistent behavior
- Maximum accuracy everywhere

**Cons:**
- 60-70% higher cost than necessary
- Slower response times
- Wasted accuracy on simple tasks
- Violates ADR-008 cost optimization goal

**Rejected:** Unnecessary cost and latency for simple operations.

### Alternative 2: User-Configurable Model Selection

Let users choose model per request.

**Pros:**
- Maximum flexibility
- Users control cost/accuracy tradeoff

**Cons:**
- Users don't know which tasks need accuracy
- Security-critical tasks could use wrong model
- Inconsistent platform behavior
- Compliance risk if users choose cheap model for security

**Rejected:** Security-critical operations must use accurate models regardless of user preference.

### Alternative 3: Dynamic Model Selection Based on Query Complexity

AI analyzes each query and selects appropriate model.

**Pros:**
- Adaptive to context
- Could optimize cost dynamically

**Cons:**
- Requires LLM call to select LLM model (chicken-egg)
- Adds latency
- Complex to implement correctly
- Edge cases hard to handle

**Rejected:** Adds complexity and latency without proportional benefit.

### Alternative 4: Cost-Based Selection (Stay Within Budget)

Always use cheapest model that stays within budget.

**Pros:**
- Never exceeds budget
- Simple rule

**Cons:**
- Security analysis with Haiku is dangerous
- Quality degrades as budget depletes
- No guarantee of accuracy when needed

**Rejected:** Security accuracy cannot be compromised by budget status.

## Consequences

### Positive

1. **Cost Reduction**
   - 60-70% cost reduction for search operations
   - Haiku handles ~40% of LLM calls at 12x lower cost
   - Monthly savings: ~$300-700 at production scale

2. **Latency Improvement**
   - 40-50% faster for multi-step operations
   - Sub-second response for most searches
   - Better user experience

3. **Security Preserved**
   - Critical operations always use accurate model
   - No accuracy compromise for vulnerability assessment
   - Audit trail shows which model made each decision

4. **Operational Clarity**
   - Clear operation→model mapping
   - Easy to audit and explain
   - Predictable behavior

### Negative

1. **Mapping Maintenance**
   - New operations require mapping decision
   - Risk of incorrect tier assignment

2. **Model Updates**
   - Must update when new models released
   - GovCloud may lag behind commercial

3. **Testing Complexity**
   - Must test all three tiers
   - Integration tests need all models available
   - Opus tests may be expensive to run frequently

4. **Opus Cost Control**
   - Maximum tier operations are expensive (~$75/1M tokens)
   - Requires careful operation mapping to prevent accidental overuse

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Wrong tier assignment | Default to ACCURATE for unmapped operations (safe middle ground) |
| Model unavailable | Fallback chain: Opus → Sonnet → Haiku → Error |
| GovCloud model lag | Use model aliases, update centrally |
| Cost spike despite tiering | ADR-008 hard budget caps still apply |
| Opus overuse | Explicit operation whitelist, CloudWatch alerts on Opus usage |
| Complex operation misclassified as simple | Code review for tier assignments, audit logs |

## Implementation Plan

### Phase 1: Core Infrastructure (~50 LOC)
- Add `ModelTier` enum to `BedrockLLMService`
- Add `OPERATION_MODEL_MAP` constant
- Modify `invoke()` to accept `operation` parameter
- Update cost logging to include tier

### Phase 2: Agent Integration (~100 LOC)
- Update `FilesystemNavigatorAgent.intelligent_search()`
- Update `ResultSynthesisAgent.synthesize_with_llm()`
- Update `ThreatIntelligenceAgent` methods
- Add operation parameter to all LLM calls

### Phase 3: Monitoring (~50 LOC)
- Add CloudWatch metrics for tier usage
- Dashboard widget for cost-by-tier
- Alert if fast tier used for security operations

## References

- [ADR-008: Bedrock LLM Cost Controls](ADR-008-bedrock-llm-cost-controls.md)
- [ADR-014: LLM-Enhanced Agent Search Pattern](ADR-014-llm-enhanced-agent-search-pattern.md)
- `src/services/bedrock_llm_service.py`
- [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Claude Model Comparison](https://docs.anthropic.com/claude/docs/models-overview)
