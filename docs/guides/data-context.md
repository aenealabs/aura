# Data and Context Guide

This guide explains how Aura manages code data, retrieves relevant context, and provides intelligent understanding of your codebase through GraphRAG technology.

---

## How Aura Understands Your Code

Aura builds a comprehensive understanding of your codebase using a hybrid approach:

```
            Your Codebase
                  |
                  v
    +---------------------------+
    |    AST Parser Agent       |
    |  (Extracts Code Structure)|
    +-------------|-------------+
                  |
          +-------+-------+
          |               |
          v               v
    +-----------+   +-----------+
    |  Neptune  |   | OpenSearch|
    |  (Graph)  |   | (Vectors) |
    +-----------+   +-----------+
          |               |
          +-------+-------+
                  |
                  v
    +---------------------------+
    |    GraphRAG Engine        |
    | (Unified Code Intelligence)|
    +---------------------------+
```

---

## GraphRAG: Hybrid Code Retrieval

GraphRAG combines graph-based and vector-based retrieval for comprehensive code understanding.

### What is GraphRAG?

GraphRAG (Graph Retrieval-Augmented Generation) combines:

- **Graph Database (Neptune)**: Stores code structure and relationships
- **Vector Database (OpenSearch)**: Stores semantic embeddings for similarity search
- **Keyword Search**: Traditional text matching for exact terms

### Why Three-Way Retrieval?

Each approach has strengths:

| Approach | Best For | Example Query |
|----------|----------|---------------|
| **Graph** | Structural relationships | "What functions call `authenticate()`?" |
| **Vector** | Semantic similarity | "Find code similar to this auth pattern" |
| **Keyword** | Exact matches | "Where is `API_KEY` defined?" |

### How Retrieval Works

> **Current status (October 2026).** The diagram below shows the three-way
> design. The agent workflow that runs today retrieves context with one Neptune
> graph traversal and one OpenSearch k-NN vector search and passes both result
> sets to the agent without keyword search or fused ranking. Keyword (BM25)
> search with Reciprocal Rank Fusion is implemented in
> `src/services/three_way_retrieval_service.py` but is not yet wired in.

```
User Query: "How does user authentication work?"
                    |
                    v
        +------------------------+
        |   Query Decomposition  |
        |   (Parallel Analysis)  |
        +------------------------+
                    |
     +--------------+--------------+
     |              |              |
     v              v              v
+----------+  +----------+  +----------+
|  Graph   |  |  Vector  |  | Keyword  |
| Neptune  |  | OpenSearch|  |  Search  |
+----------+  +----------+  +----------+
     |              |              |
     v              v              v
+------------------------------------------+
|         Result Fusion & Ranking          |
|    (Combines all results by relevance)   |
+------------------------------------------+
                    |
                    v
           Ranked Context Items
```

---

## Code Graph Structure

### What Gets Indexed

The AST Parser Agent extracts and indexes:

| Entity Type | Examples | Relationships Stored |
|-------------|----------|----------------------|
| **Functions** | `def authenticate()` | Calls (callers are found by traversing incoming `CALLS` edges) |
| **Classes** | `class UserService` | Inheritance, contained methods |
| **Methods** | `def get_user()` | Class membership, calls |
| **Variables** | `API_KEY = ...` | Definition location (variable usage is not tracked) |
| **Imports** | `import auth` | Module dependencies |

### Relationship Types

| Relationship | Meaning |
|--------------|---------|
| `CALLS` | Function A calls function B (deterministically resolved) |
| `CALLS_INFERRED` | Call target resolved by the LLM-based resolver tier |
| `CONTAINS` | Parent entity contains class/function |
| `IMPORTS` | Module imports module |
| `INHERITS` | Class A inherits from class B |
| `READS_CONFIG`, `DEPENDS_ON_ENV`, `USES_KMS_KEY`, `FEATURE_GATED_BY` | Code depends on configuration or infrastructure |

### Example Graph Query

"Find all functions that call the database layer":

```
                    +------------+
                    |  auth.py   |
                    +------------+
                          |
                    contains
                          |
                          v
                  +---------------+
                  | authenticate()|
                  +---------------+
                          |
                       calls
                          |
                          v
                  +---------------+
                  | db_service.py |
                  +---------------+
                          |
                    contains
                          |
                          v
                  +---------------+
                  |  get_user()   |
                  +---------------+
```

---

## Context Engineering

Aura uses advanced context engineering to provide the most relevant information to agents.

### Context Stack Manager

Manages context throughout a session:

```
Session Start
     |
     v
+--------------------+
| Push: User Query   |
+--------------------+
     |
     v
+--------------------+
| Push: Code Context |
+--------------------+
     |
     v
+--------------------+
| Push: Memory       |
+--------------------+
     |
     v
     Agent Processing
     |
     v
+--------------------+
| Pop: Memory        |
+--------------------+
     |
     v
Session End
```

### Context Scoring

The Context Scoring Service (`src/services/context_scoring_service.py`) scores each context item for relevance. It is implemented and unit-tested but not yet called by the agent workflow.

| Factor | Weight | Description |
|--------|--------|-------------|
| Relevance | 50% | 70% embedding cosine similarity plus 30% TF-IDF term overlap with the query |
| Recency | 30% | Exponential decay on file modification age (`recency_half_life_days` = 30) |
| Density | 20% | Character-level Shannon entropy of the content, normalized to 0-1 |

### Hierarchical Tool Registry

Tools are organized in three tiers:

| Tier | Scope | Example |
|------|-------|---------|
| **Global** | All contexts | Code graph query |
| **Domain** | Specific domains | Security scanning |
| **Task-Specific** | Individual tasks | Patch generation |

---

## HopRAG: Multi-Hop Reasoning

Aura's HopRAG service (`src/services/hoprag_service.py`) is designed for multi-hop reasoning across the code graph on complex queries. It is implemented and unit-tested but not yet called by the agent workflow.

### What is Multi-Hop?

Multi-hop reasoning follows relationships across multiple steps:

**Query**: "What security vulnerabilities could affect user authentication?"

```
Step 1: Find auth-related code
        |
        v
Step 2: Find functions that call auth code
        |
        v
Step 3: Find input validation for those functions
        |
        v
Step 4: Identify missing validation (vulnerability)
```

### How HopRAG Works

```
Initial Query
     |
     v
+--------------------+
| Find Starting      |
| Entities           |
+--------------------+
     |
     v
+--------------------+
| Traverse Graph     |  <-- Follow relationships
| (Hop 1)            |
+--------------------+
     |
     v
+--------------------+
| Evaluate Results   |  <-- Score relevance
+--------------------+
     |
     v
Need more hops? ----> Continue traversal
     |  No
     v
Return Results
```

---

## Data Sources

### Internal Data

| Source | Description | Update Frequency |
|--------|-------------|------------------|
| Code Repository | Your source code | On push/scan |
| Vulnerability DB | Known CVEs | Daily sync |
| Compliance Rules | Framework requirements | On policy change |

### Context Sources

When agents receive context, each item is tagged with its source:

| Source | Tag | Example |
|--------|-----|---------|
| Graph Structural | `graph` | Class hierarchy |
| Vector Semantic | `vector` | Similar code patterns |
| Security Policy | `security` | Compliance requirements |
| Remediation | `remediation` | Fix patterns |
| User Prompt | `user_prompt` | Original request |
| Neural Memory | `neural_memory` | Past experiences |

---

## Community Summarization

For large codebases, Aura's community summarization service groups related code with Leiden clustering (falling back to connected components when the clustering libraries are not installed) and generates LLM summaries. It is implemented and unit-tested but not yet called by the agent workflow.

### What is Community Detection?

Community detection groups related code:

```
           +------------------+
           |   Auth Module    |
           |  +-----------+   |
           |  | login()   |   |
           |  | logout()  |   |
           |  | verify()  |   |
           |  +-----------+   |
           +------------------+

           +------------------+
           |   Data Module    |
           |  +-----------+   |
           |  | query()   |   |
           |  | insert()  |   |
           |  | update()  |   |
           |  +-----------+   |
           +------------------+
```

### How Summaries Help

Instead of loading all code, agents receive:

1. High-level community summaries
2. Detailed code for relevant areas only
3. Relationship context between communities

**Benefits**:
- Faster processing
- Lower token usage
- Better focus on relevant code

---

## MCP Context Protocol

Aura supports the Model Context Protocol (MCP) for standardized context exchange.

### What is MCP?

MCP is an industry standard for how AI tools share context:

```
+------------+      MCP       +------------+
|   Aura     | <-----------> |  External  |
|   Agent    |   Protocol    |   Tool     |
+------------+               +------------+
```

### MCP Context Manager

Coordinates context between tools:

| Function | Description |
|----------|-------------|
| Context Registration | Tools register their context |
| Context Broadcast | Share context with all subscribers |
| Context Request | Tools request specific context |
| Context Sync | Keep context consistent |

### Enabling MCP

1. Navigate to **Settings > MCP Configuration**
2. Enable MCP Gateway
3. Configure connection details
4. Select which tools can access context

---

## Data Privacy and Isolation

### Tenant Separation

The diagram below shows the target isolation model. Today, ingestion writes all repositories to a shared OpenSearch index and a shared Neptune graph, with entities and documents tagged by repository; dedicated per-tenant clusters are the planned higher isolation tiers (see ADR-093):

```
+----------------------------------+
|          Your Tenant             |
|  +--------+  +--------+          |
|  |Neptune |  |OpenSearch|         |
|  | (Your  |  | (Your   |         |
|  |  Data) |  |  Data)  |         |
|  +--------+  +--------+          |
+----------------------------------+

+----------------------------------+
|        Other Tenant              |
|  +--------+  +--------+          |
|  |Neptune |  |OpenSearch|         |
|  | (Their |  | (Their  |         |
|  |  Data) |  |  Data)  |         |
|  +--------+  +--------+          |
+----------------------------------+
```

### Data Encryption

| Data State | Encryption |
|------------|------------|
| At Rest | AES-256 (KMS) |
| In Transit | TLS 1.3 |
| In Memory | Process isolation |

### Data Retention

| Data Type | Retention |
|-----------|-----------|
| Code Index | Until repository removed |
| Audit Logs | Configurable (30-365 days) |
| Session Data | 24 hours |
| Memory Data | Configurable |

---

## Querying Your Data

### Using the Chat Assistant

Ask natural language questions:

| Question Type | Example |
|---------------|---------|
| Structural | "Show me the inheritance hierarchy for UserService" |
| Semantic | "Find code similar to this authentication pattern" |
| Relationship | "What depends on the database module?" |
| Security | "Where is user input not validated?" |

### Query Decomposition Panel

**Planned.** A Query Decomposition panel component exists in the frontend but is not yet shown on any page, and the `/api/v1/query/decompose` endpoint currently returns illustrative sub-queries with randomly generated counts and confidence values. When connected, it will show how Aura breaks a query down into individual sub-queries:

- **Structural** (Neptune) - Blue
- **Semantic** (OpenSearch) - Green
- **Temporal** (Git history) - Purple

---

## Data Ingestion

### Indexing Your Repository

1. Start ingestion through `POST /api/v1/ingest`, or configure the GitHub webhook for push-triggered updates
2. Aura automatically:
   - Parses supported file types
   - Extracts code entities
   - Builds the graph
   - Generates embeddings
3. Monitor progress with `GET /api/v1/jobs/{job_id}`

> **Known gap.** Adding a repository or clicking sync through the Repositories
> page (`/api/v1/repositories/ingest` and `/api/v1/repositories/{id}/sync`)
> records an ingestion job but does not yet start the ingestion pipeline.

### Supported Languages

| Language | File Extensions | Graph entities | Vector embeddings |
|----------|-----------------|----------------|-------------------|
| Python | `.py` | Yes (Python `ast`) | Yes |
| JavaScript | `.js`, `.jsx` | Yes (tree-sitter; regex fallback without relationships when tree-sitter is not installed) | Yes |
| TypeScript | `.ts`, `.tsx` | Yes (parsed with the JavaScript grammar; type annotations are ignored) | Yes |
| Java | `.java` | Planned | Yes |
| Go | `.go` | Planned | Yes |
| Rust | `.rs` | Planned | Yes |

C/C++, C#, Ruby, and PHP are not yet ingested. The vulnerability scanner has its own parser with broader language coverage; this table covers the GraphRAG code graph and embeddings only.

### Incremental Updates

After initial indexing, Aura updates incrementally:

- On git push (GitHub webhook)
- On manual trigger (`POST /api/v1/ingest`)

Scheduled scans are planned.

---

## Best Practices

### For Better Context

1. **Use descriptive names**: Help semantic search work better
2. **Document your code**: Comments improve understanding
3. **Organize logically**: Clear module boundaries help graph analysis
4. **Keep dependencies explicit**: Explicit imports improve relationship tracking

### For Query Performance

1. **Be specific**: Narrow queries return faster
2. **Use entity names**: "Find `UserService.authenticate`" vs "find auth"
3. **Specify scope**: "In the auth module" limits search space
4. **Leverage relationships**: "Functions that call X" uses graph efficiently

### For Privacy

1. **Review indexed content**: Ensure no secrets in code
2. **Use .gitignore patterns**: Exclude sensitive files
3. **Configure retention**: Match compliance requirements
4. **Audit access**: Review who can query your data

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Agent System](./agent-system.md) | How agents use context |
| [Configuration](./configuration.md) | Data settings |
| [API Reference](./api-reference.md) | Query APIs |
| [Integrations](./integrations.md) | Repository connections |
