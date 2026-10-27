# Hybrid GraphRAG Architecture

**Version:** 1.0
**Last Updated:** October 2026

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

Published research on three-way hybrid retrieval reports a 22-25% MRR
improvement over two-way retrieval; ADR-034 adopts that finding as the
rationale for this design. The figure is the research result, not a
measurement of Aura -- retrieval quality has not been benchmarked against a
single-method baseline on customer data, because no customer codebases are
onboarded. See `src/services/three_way_retrieval_service.py`.

---

## Architecture Components

Aura's Hybrid GraphRAG consists of the components below.

> **Implementation status (October 2026).** The Neptune Gremlin client and the
> OpenSearch k-NN client are real code paths (`src/services/neptune_graph_service.py`,
> `src/services/opensearch_vector_service.py`). Both fall back silently to
> in-memory mock mode when `NEPTUNE_ENDPOINT` / `OPENSEARCH_ENDPOINT` are unset or
> the connection fails, and the Neptune readiness probe still reports ready in
> mock mode. The retrieval path used by the production agent
> workflow (`ContextRetrievalService` in `src/agents/agent_orchestrator.py`)
> runs one graph traversal and one k-NN search and concatenates the results;
> it does not run BM25 or RRF. The three-way RRF service described in
> section 3 is implemented and unit-tested but is not yet called by any API
> route or agent workflow.

### 1. Neptune Graph Database

AWS Neptune stores structural code relationships as a property graph.

**Vertices:** Code entities are written as a single `CodeEntity` vertex label.
The entity kind (`class`, `function`, `method`, `import`, `variable`) is stored
in the `type` property, alongside `entity_id`, `name`, `file_path`,
`line_number`, optional `fqn`, and `parent`. Infrastructure, config, KMS-alias,
feature-flag, service-boundary, and data-flow vertices use their own labels.

**Edge labels** (`src/services/graph/edge_labels.py`):

| Edge Label | Description |
|------------|-------------|
| `CONTAINS` / `HAS_<TYPE>` | Parent entity contains a child definition |
| `CALLS` | Deterministically resolved call (symbol-resolver tiers 1-2) |
| `CALLS_INFERRED` | Call resolved by the tier-3 LLM resolver (lower trust tier); not produced by API-triggered ingestion today because that service is constructed without a Bedrock client |
| `IMPORTS` | Import dependency |
| `INHERITS` | Class inheritance |
| `READS_CONFIG`, `DEPENDS_ON_ENV`, `USES_KMS_KEY`, `FEATURE_GATED_BY` | Config and infrastructure dependencies (clearance-filtered at query time) |

There is no `REFERENCES` (variable-usage) edge today.

**Example Gremlin Query:**

```groovy
// Find all callers of a vulnerable function
g.V().has('CodeEntity', 'name', 'insecure_hash')
  .in('CALLS')
  .valueMap('name', 'file_path', 'line_number')
```

### 2. OpenSearch Vector Store

AWS OpenSearch stores code embeddings for semantic search.

**Index Structure:**

```json
{
  "mappings": {
    "properties": {
      "text": { "type": "text", "analyzer": "standard" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib",
          "parameters": { "m": 16, "ef_construction": 512 }
        }
      },
      "metadata": { "type": "object" },
      "timestamp": { "type": "date" },
      "provenance": { "type": "object" }
    }
  }
}
```

**Embedding Generation:**

During repository ingestion (`GitIngestionService`), each supported file is embedded as a whole:

1. **Content limit**: The first 20 KB of each file is used (files are not yet split at function/class boundaries)
2. **Injection scan**: Content is scanned for prompt-injection payloads in comments and docstrings before embedding
3. **Embedding**: Amazon Titan Text Embeddings v2 via Bedrock (`amazon.titan-embed-text-v2:0`), 1024-dimensional vectors
4. **Indexing**: Stored in the `aura-code-embeddings` OpenSearch index with file metadata; stored text is truncated to 5,000 characters

Function-level chunking is planned.

### 3. Three-Way Retrieval Service

`src/services/three_way_retrieval_service.py` orchestrates queries across all three sources and fuses results.

**Status:** Implemented and unit-tested; not yet wired into an API route or agent workflow. Steps 1-4 below describe this service. Its default BM25 query targets an `aura-code-index` index with `content`, `file_path`, and `function_names` fields, while ingestion writes to `aura-code-embeddings` with a `text` field; the index schemas must be reconciled before the service is wired in.

**Three Retrieval Methods:**

1. **Dense (Vector k-NN)**: Semantic similarity via embedding comparison
2. **Sparse (BM25)**: Keyword matching via traditional text search
3. **Graph (Gremlin)**: Structural traversal via relationship queries

### 4. Cross-File Taint Resolver (ADR-093)

A persistence layer on top of Neptune that turns per-function taint summaries (sources, sinks, sanitizers, propagators) into a reusable cache class. This sits alongside the structural and semantic graph data above; it does not replace them.

**Status:** Code-complete as of May 13, 2026; live deployment is **Deferred (Cost Gate)** pending budget restoration. Capability is reviewable now; production enablement will follow.

**What this enables for your team:**

- **Incremental scans that get faster as your repo grows.** When the scanner re-runs after a small pull request, summaries for unchanged files are reused from the prior scan. A 10K-file repo with 10 changed files reuses ~9,990 summaries instead of recomputing them. Target win: 10x to 100x latency reduction on small-diff scans versus full-rescan.
- **Cross-file dataflow at scale across all 8 vulnerability-scanner languages.** Python, JavaScript, TypeScript, Go, Java, Rust, C, and C++ all participate in the same source-to-sink graph. A taint flowing from a request handler in one file to a SQL query in another file is followed deterministically, not heuristically.
- **Audit-defensible "which summary produced this finding?"** Every persisted summary is signed with a tenant-scoped KMS asymmetric key (RSASSA_PSS_SHA_256), and the signed payload is transport-bound to the scan ID, commit SHA, and a session nonce. Replay or substitution attempts fail signature verification. Compromised-signer revocation is consulted on every read.
- **Tiered isolation that matches your regulatory posture.**
  - **T1 (commercial SaaS):** shared cluster with a tenant-predicate-enforcing Gremlin client; per-tenant data keys envelope-encrypted under a shared CMK.
  - **T2 (FedRAMP-Moderate / CMMC-L2):** dedicated Neptune cluster per tenant.
  - **T3 (GovCloud / classified):** dedicated VPC.
- **No live-failure surface.** The resolver is treated as a cache class. If the persistence layer is unavailable, the scanner degrades to per-scan in-memory analysis (`CrossFileTaintContext`) with no correctness loss. A pre-staged operator kill-switch flips this in under five minutes via SSM Parameter Store, with no redeploy.

For operations details and the named CloudWatch alarms covering this layer, see the [taint resolver runbook](../../runbooks/NEPTUNE_TAINT_RESOLVER_RUNBOOK.md). For full design rationale, threat model, and NIST 800-53 mapping, see [ADR-093](../../architecture-decisions/ADR-093-neptune-cross-file-taint-resolver.md).

---

## How Hybrid Retrieval Works

The steps below describe the three-way retrieval design (`ThreeWayRetrievalService` plus `QueryAnalyzer`). The agent workflow that runs today uses the simpler graph-plus-vector path noted at the top of this page.

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

The patterns below are illustrative Gremlin for the structural questions Aura targets. The service code issues `repeat(bothE(<labels>).otherV().simplePath()).times(<depth>)` traversals over `CodeEntity` vertices, with the edge-label set chosen per query type (call graph, dependencies, inheritance, references, related) in `src/services/context_retrieval_service.py`.

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

The figures in this section are design targets. No retrieval latency benchmark results are checked into the repository.

### Latency Targets

| Operation | Target | Measured (p95) |
|-----------|--------|----------------|
| Single source retrieval | < 100ms | Not yet measured |
| Three-way fusion | < 150ms | Not yet measured |
| Graph traversal (2 hops) | < 200ms | Not yet measured |
| Full context retrieval | < 500ms | Not yet measured |

### Scaling Characteristics

| Codebase Size | Index Size | Query Latency Impact |
|---------------|------------|----------------------|
| < 100K LOC | < 1 GB | Baseline |
| 100K - 1M LOC | 1-10 GB | +10-20% |
| 1M - 10M LOC | 10-100 GB | +20-40% |
| > 10M LOC | > 100 GB | Requires sharding |

### Index Update Frequency

| Event | Update Type | Latency target |
|-------|-------------|----------------|
| Push to a tracked branch (GitHub webhook) | Incremental (`ingest_changes`) | < 60 seconds |
| Full ingestion (`POST /api/v1/ingest`) | Complete rebuild | 1-4 hours (background) |

File-save-triggered indexing is not implemented.

---

## Configuration Options

> **Planned.** These settings exist today only as constructor/dataclass
> defaults in code (`RetrievalConfig` in `three_way_retrieval_service.py`, `GitIngestionService`). There is
> no administrator-facing configuration API or file for them yet. Ingested file
> types are currently fixed in code.

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

> **Three-way fusion is the target design.** Published research reports a 22-25% MRR improvement from adding BM25 sparse search to dense vectors and graph traversal; Aura has not yet measured this on its own retrieval path.

> **Sparse boost is critical.** The 1.2x weight for BM25 results helps capture exact identifier matches that vector search might miss.

> **Query latency scales with codebase size.** Large codebases may require index sharding and additional optimization.

---

## Related Concepts

- [Autonomous Security Intelligence](./autonomous-security-intelligence.md) - How retrieved context is used by AI
- [Multi-Agent System](./multi-agent-system.md) - How agents request context
- [Sandbox Security](./sandbox-security.md) - How context informs validation

---

## Technical References

- ADR-034: Context Engineering Framework
- Issue #151: Hybrid GraphRAG Implementation
- ADR-051: Recursive Context and Embedding Prediction
- ADR-093: Neptune-Backed Cross-File Taint Resolver (code-complete; deploy Deferred (Cost Gate))
