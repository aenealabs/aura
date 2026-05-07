# Hybrid GraphRAG Architecture

**Version:** 1.0
**Last Updated:** January 2026

---

## Overview

Hybrid GraphRAG is Aura's retrieval architecture that combines graph databases with vector search to provide comprehensive code understanding. "RAG" stands for Retrieval-Augmented Generation, a technique where relevant context is retrieved and provided to an LLM to improve its responses.

Traditional RAG uses vector similarity search alone. Aura's Hybrid GraphRAG adds structural code analysis through graph databases, enabling queries like "find all functions that call this vulnerable method" alongside semantic queries like "find similar authentication code."

---

## Why Hybrid Retrieval Matters

Code has two types of relationships that matter for security analysis:

### Structural Relationships

These are explicit, deterministic connections in code:

- **Call graphs**: Function A calls Function B
- **Dependencies**: Module X imports Module Y
- **Inheritance**: Class Child extends Class Parent
- **References**: Variable usage across files

Structural relationships answer questions like:
- "What code will be affected if I change this function?"
- "Where is this vulnerable dependency used?"
- "What classes inherit from this insecure base class?"

### Semantic Relationships

These are implicit, similarity-based connections:

- **Pattern similarity**: Code that does similar things
- **Intent matching**: Code that serves similar purposes
- **Contextual relevance**: Code related to a concept

Semantic relationships answer questions like:
- "Find other code that handles authentication"
- "What patterns exist for input validation?"
- "Show me similar error handling approaches"

### The Hybrid Advantage

Neither structural nor semantic retrieval alone provides complete context:

| Retrieval Type | Strengths | Limitations |
|----------------|-----------|-------------|
| **Structural (Graph)** | Precise relationships, deterministic | Misses semantic similarity |
| **Semantic (Vector)** | Captures meaning, finds patterns | Misses explicit connections |
| **Hybrid (Both)** | Comprehensive context | Requires fusion logic |

Aura's hybrid approach achieves 22-25% improvement in retrieval accuracy compared to single-method approaches.

---

## Architecture Components

Aura's Hybrid GraphRAG consists of three main components.

### 1. Neptune Graph Database

AWS Neptune stores structural code relationships as a property graph.

**Node Types:**

| Node Type | Description | Properties |
|-----------|-------------|------------|
| `File` | Source code file | path, language, last_modified |
| `Function` | Function or method | name, signature, line_start, line_end |
| `Class` | Class definition | name, docstring, decorators |
| `Variable` | Variable definition | name, type, scope |
| `Import` | Import statement | module, alias |

**Edge Types:**

| Edge Type | From | To | Description |
|-----------|------|-----|-------------|
| `CONTAINS` | File | Function/Class | File contains definition |
| `CALLS` | Function | Function | Function calls another |
| `IMPORTS` | File | File/Module | Import dependency |
| `EXTENDS` | Class | Class | Inheritance relationship |
| `REFERENCES` | Function | Variable | Variable usage |
| `DEPENDS_ON` | File | Package | External dependency |

**Example Gremlin Query:**

```groovy
// Find all functions that call a vulnerable function
g.V().has('Function', 'name', 'insecure_hash')
  .in('CALLS')
  .project('caller', 'file', 'line')
    .by('name')
    .by(out('CONTAINED_IN').values('path'))
    .by('line_start')
```

### 2. OpenSearch Vector Store

AWS OpenSearch stores code embeddings for semantic search.

**Index Structure:**

```json
{
  "mappings": {
    "properties": {
      "content": { "type": "text" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 1536,
        "method": {
          "name": "hnsw",
          "engine": "nmslib",
          "parameters": { "m": 16, "ef_construction": 512 }
        }
      },
      "file_path": { "type": "keyword" },
      "function_names": { "type": "keyword" },
      "language": { "type": "keyword" },
      "last_modified": { "type": "date" }
    }
  }
}
```

**Embedding Generation:**

Code is chunked and embedded using models optimized for code understanding:

1. **Chunking**: Code split at function/class boundaries
2. **Context enrichment**: Docstrings and comments included
3. **Embedding**: Convert to 1536-dimensional vectors
4. **Indexing**: Store in OpenSearch with metadata

### 3. Three-Way Retrieval Service

The retrieval service orchestrates queries across all three sources and fuses results.

**Three Retrieval Methods:**

1. **Dense (Vector k-NN)**: Semantic similarity via embedding comparison
2. **Sparse (BM25)**: Keyword matching via traditional text search
3. **Graph (Gremlin)**: Structural traversal via relationship queries

---

## How Hybrid Retrieval Works

When you ask Aura a question or trigger a vulnerability analysis, the retrieval process follows these steps.

### Step 1: Query Analysis

The query is analyzed to determine which retrieval methods are most relevant:

```python
query = "Find code that validates user authentication tokens"

# Query analysis
{
  "semantic_keywords": ["validates", "authentication", "tokens"],
  "structural_hints": ["user", "authentication"],
  "graph_traversal_needed": True,  # Look for auth-related calls
  "vector_search_needed": True,    # Find similar patterns
  "bm25_search_needed": True       # Match specific terms
}
```

### Step 2: Parallel Retrieval

All three retrieval methods execute concurrently:

```
┌─────────────────────────────────────────────────────────────────┐
│            Query: "validate auth tokens"                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Dense    │   │  Sparse   │   │   Graph   │
    │  (k-NN)   │   │  (BM25)   │   │ (Gremlin) │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │               │               │
          │ 50 results    │ 50 results    │ 50 results
          │               │               │
          └───────────────┼───────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │    RRF Fusion   │
                │    (k=60)       │
                └────────┬────────┘
                         │
                         ▼
                  Top 20 Results
```

### Step 3: Reciprocal Rank Fusion (RRF)

Results from all sources are combined using RRF, which balances precision and recall:

```
RRF Score = Σ (weight / (k + rank))

Where:
- k = 60 (constant to dampen high-ranking outliers)
- rank = position in source result list (1-indexed)
- weight = source-specific weight
```

**Default Weights:**

| Source | Weight | Rationale |
|--------|--------|-----------|
| Dense (Vector) | 1.0 | Baseline semantic relevance |
| Sparse (BM25) | 1.2 | Boost for exact keyword matches |
| Graph | 1.0 | Structural relationships |

The sparse boost (1.2) is research-tuned. BM25 excels at finding exact function names and identifiers that vector search might miss.

### Step 4: Result Enrichment

Top results are enriched with additional context:

```python
{
  "doc_id": "file_auth_service_validate_token",
  "content": "def validate_token(token: str) -> bool: ...",
  "rrf_score": 0.156,
  "source_scores": {
    "dense": 0.052,
    "sparse": 0.062,
    "graph": 0.042
  },
  "sources_contributed": ["dense", "sparse", "graph"],
  "file_path": "src/services/auth_service.py",
  "metadata": {
    "function_names": ["validate_token"],
    "related_functions": ["decode_jwt", "check_expiry"],
    "callers": ["authenticate_user", "verify_session"]
  }
}
```

---

## Graph Query Patterns

Aura supports several graph query patterns for structural analysis.

### CALL_GRAPH

Find all functions that call a specific function:

```groovy
g.V().has('Function', 'name', 'vulnerable_function')
  .in('CALLS')
  .path()
```

**Use case**: Impact analysis for vulnerability fixes

### DEPENDENCIES

Find all files that depend on a vulnerable package:

```groovy
g.V().has('Package', 'name', 'vulnerable-lib')
  .in('DEPENDS_ON')
  .values('path')
```

**Use case**: Dependency vulnerability assessment

### INHERITANCE

Find all classes that inherit from an insecure base class:

```groovy
g.V().has('Class', 'name', 'InsecureBase')
  .in('EXTENDS')
  .emit()
  .repeat(in('EXTENDS'))
  .until(__.not(in('EXTENDS')))
```

**Use case**: Identifying inherited vulnerabilities

### REFERENCES

Find all usages of a specific variable or constant:

```groovy
g.V().has('Variable', 'name', 'API_KEY')
  .in('REFERENCES')
  .project('function', 'file')
    .by('name')
    .by(out('CONTAINED_IN').values('path'))
```

**Use case**: Secret exposure analysis

### RELATED

Find structurally related code through multiple relationship types:

```groovy
g.V().has('Function', 'name', 'target_function')
  .union(
    in('CALLS'),           // Functions that call this
    out('CALLS'),          // Functions this calls
    out('CONTAINED_IN')    // File containing this
      .in('CONTAINED_IN')  // Other functions in same file
  )
  .dedup()
```

**Use case**: Comprehensive context gathering

---

## Performance Characteristics

Aura's Hybrid GraphRAG is optimized for enterprise-scale codebases.

### Latency Targets

| Operation | Target | Actual (p95) |
|-----------|--------|--------------|
| Single source retrieval | < 100ms | ~45ms |
| Three-way fusion | < 150ms | ~85ms |
| Graph traversal (2 hops) | < 200ms | ~120ms |
| Full context retrieval | < 500ms | ~350ms |

### Scaling Characteristics

| Codebase Size | Index Size | Query Latency Impact |
|---------------|------------|----------------------|
| < 100K LOC | < 1 GB | Baseline |
| 100K - 1M LOC | 1-10 GB | +10-20% |
| 1M - 10M LOC | 10-100 GB | +20-40% |
| > 10M LOC | > 100 GB | Requires sharding |

### Index Update Frequency

| Event | Update Type | Latency |
|-------|-------------|---------|
| File saved | Incremental | < 5 seconds |
| PR merged | Batch update | < 60 seconds |
| Full rescan | Complete rebuild | 1-4 hours (background) |

---

## Configuration Options

Administrators can tune retrieval behavior through configuration.

### Retrieval Weights

Adjust the relative importance of each retrieval method:

```json
{
  "retrieval_config": {
    "dense_weight": 1.0,
    "sparse_boost": 1.2,
    "graph_weight": 1.0,
    "rrf_k": 60
  }
}
```

**When to adjust:**

- Increase `sparse_boost` for codebases with unique naming conventions
- Increase `graph_weight` for highly interconnected architectures
- Decrease `graph_weight` for isolated microservices

### Index Configuration

Control what gets indexed and how:

```json
{
  "index_config": {
    "include_patterns": ["*.py", "*.js", "*.ts", "*.java"],
    "exclude_patterns": ["**/test/**", "**/vendor/**"],
    "chunk_size": 500,
    "chunk_overlap": 50,
    "embedding_model": "code-embedding-v2"
  }
}
```

### Query Limits

Set boundaries on query behavior:

```json
{
  "query_limits": {
    "max_results_per_source": 50,
    "max_graph_hops": 3,
    "max_graph_terms": 10,
    "query_timeout_ms": 5000
  }
}
```

---

## Key Takeaways

> **Hybrid retrieval captures both structure and meaning.** Graph databases provide precise relationships; vector search provides semantic similarity.

> **Three-way fusion outperforms dual approaches.** Adding BM25 sparse search to dense vectors and graph traversal improves accuracy by 22-25%.

> **Sparse boost is critical.** The 1.2x weight for BM25 results helps capture exact identifier matches that vector search might miss.

> **Query latency scales with codebase size.** Large codebases may require index sharding and additional optimization.

---

## Related Concepts

- [Autonomous Code Intelligence](./autonomous-code-intelligence.md) - How retrieved context is used by AI
- [Multi-Agent System](./multi-agent-system.md) - How agents request context
- [Sandbox Security](./sandbox-security.md) - How context informs validation

---

## Technical References

- ADR-034: Context Engineering Framework
- Issue #151: Hybrid GraphRAG Implementation
- ADR-051: Recursive Context and Embedding Prediction
