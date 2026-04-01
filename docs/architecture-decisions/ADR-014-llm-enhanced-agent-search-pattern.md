# ADR-014: LLM-Enhanced Agent Search and Ranking Pattern

**Status:** Deployed
**Date:** 2025-12-01
**Decision Makers:** Project Aura Team
**Related:** ADR-008 (Bedrock LLM Cost Controls), ADR-013 (Service Adapter Factory Pattern)

## Context

Project Aura agents perform code search and result ranking as core operations:
- `FilesystemNavigatorAgent` searches files by pattern or semantic meaning
- `ResultSynthesisAgent` ranks and prioritizes search results from multiple sources

The existing implementation uses:
1. **Embedding-based semantic search**: Fast, cost-effective, but limited to vector similarity
2. **Deterministic ranking**: Rule-based scoring (recency, file type, multi-strategy matches)

We identified opportunities to improve search quality:
- Users often phrase queries ambiguously ("find the auth stuff")
- Embedding similarity doesn't capture intent or context
- Deterministic ranking can't assess query-specific relevance

**Key Question:** Should agents use LLM intelligence to enhance search and ranking?

**Constraints:**
- Must not break existing functionality (backward compatibility)
- Must respect cost controls from ADR-008
- Must gracefully degrade when LLM unavailable
- Must be opt-in (not mandatory for all use cases)

## Decision

We chose an **Optional LLM Enhancement Pattern** with three tiers:

### Tier 1: Embedding-Only (Default, Fast, Cheap)
```python
# Fast path - no LLM calls
results = await navigator.search(query, search_type="semantic")
ranked = synthesizer.synthesize(results, budget)
```

### Tier 2: LLM-Enhanced (Opt-In, Slower, More Accurate)
```python
# Enhanced path - 2-3 LLM calls per operation
results = await navigator.intelligent_search(query)
ranked = await synthesizer.synthesize_with_llm(results, budget, query)
```

### Tier 3: Hybrid (Orchestrator-Controlled)
```python
# Orchestrator decides based on query complexity and user settings
if user_settings.llm_search_enabled and query.is_complex():
    results = await navigator.intelligent_search(query)
else:
    results = await navigator.search(query, search_type="semantic")
```

**Implementation Pattern:**

```python
class EnhancedAgent:
    def __init__(self, ..., llm_client: BedrockLLMService | None = None):
        self.llm_client = llm_client  # Optional

    async def basic_operation(self, query):
        """Always available, no LLM required."""
        return await self._embedding_based_search(query)

    async def enhanced_operation(self, query):
        """LLM-enhanced, falls back gracefully."""
        if not self.llm_client:
            logger.warning("LLM unavailable, using basic operation")
            return await self.basic_operation(query)
        # LLM-enhanced logic
```

**Configuration Hierarchy:**

| Level | Configured By | Example |
|-------|---------------|---------|
| Platform | Admin | "Enable LLM features for Enterprise tier" |
| User | Settings UI | "Always use intelligent search" |
| Runtime | Orchestrator | "Simple query, skip LLM" |
| Fallback | Agent | "LLM unavailable, use embeddings" |

## Alternatives Considered

### Alternative 1: LLM-Only Search (Replace Embeddings)

Replace all embedding-based search with LLM-powered search.

**Pros:**
- Maximum accuracy
- Consistent behavior
- Simpler codebase (one path)

**Cons:**
- 10-50x cost increase
- 200-500ms latency per operation
- No fallback if LLM unavailable
- Violates ADR-008 cost controls

**Rejected:** Cost and latency unacceptable for all operations.

### Alternative 2: Embedding-Only (No LLM Enhancement)

Keep existing embedding-based search without LLM.

**Pros:**
- Fast (~10ms)
- Cheap (embedding cost only)
- Always available

**Cons:**
- Can't understand query intent
- No query expansion
- Limited ranking intelligence

**Rejected:** Misses opportunity to improve complex query handling.

### Alternative 3: Mandatory LLM Enhancement

Require LLM for all search operations (no opt-out).

**Pros:**
- Consistent user experience
- Simpler API

**Cons:**
- Higher costs for simple queries
- No way to prioritize speed
- Breaks for users without LLM access

**Rejected:** Flexibility required for different use cases.

## Consequences

### Positive
- Users can choose accuracy vs. speed tradeoff
- Complex queries get intelligent handling
- Simple queries remain fast and cheap
- Graceful degradation maintains availability
- Pattern reusable across all agents

### Negative
- Two code paths to maintain
- Users must understand when to use each
- Testing complexity increases
- Documentation must explain tradeoffs

### Cost Impact

| Operation | Embedding-Only | LLM-Enhanced |
|-----------|---------------|--------------|
| Latency | ~10-50ms | ~200-500ms |
| Cost/query | ~$0.0001 | ~$0.001-0.003 |
| Accuracy | Good | Better |

## Implementation

### Files Modified
- `src/agents/result_synthesis_agent.py` (+169 lines)
  - `synthesize_with_llm()` - LLM-powered ranking
  - `_llm_rank_files()` - File relevance scoring
- `src/agents/filesystem_navigator_agent.py` (+184 lines)
  - `intelligent_search()` - Query understanding + multi-strategy search
  - `_analyze_query_intent()` - Intent extraction
  - `_llm_rank_results()` - Result ranking

### Integration Points
- Orchestrator: Decides which method to call
- Platform Settings: Enables/disables LLM features
- Cost Controls: Respects ADR-008 budget limits

### Future Enhancements
- Caching for repeated query patterns
- Query complexity scoring to auto-select tier
- A/B testing framework for ranking algorithms
- Fine-tuned models for code search

## References

- [ADR-008: Bedrock LLM Cost Controls](ADR-008-bedrock-llm-cost-controls.md)
- [ADR-013: Service Adapter Factory Pattern](ADR-013-service-adapter-factory-pattern.md)
- `src/agents/result_synthesis_agent.py`
- `src/agents/filesystem_navigator_agent.py`
