# Query Language Strategy Decision

**Status:** Decided
**Date:** 2026-01-03
**Decision Makers:** Platform Architecture Team
**Context:** ADR-049 Phase 0 Prerequisite

---

## Executive Summary

**Decision: Implement native Cypher adapter for Neo4j self-hosted deployments.**

The existing GraphDatabaseService abstraction layer enables a clean implementation strategy where Gremlin remains the SaaS query language (AWS Neptune) while Cypher is used natively for self-hosted Neo4j deployments.

---

## Context

### Current State

Project Aura uses AWS Neptune with Gremlin queries for the SaaS deployment:

```
┌─────────────────────────────────────────────────────────────┐
│                 GraphDatabaseService (Abstract)              │
│                   src/abstractions/graph_database.py         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   NeptuneGraphAdapter                CosmosGraphAdapter      │
│   (AWS - Gremlin)                    (Azure - Gremlin API)   │
│                                                              │
│         │                                  │                 │
│         ▼                                  ▼                 │
│   NeptuneGraphService              CosmosGraphService        │
│   (Gremlin queries)                (Gremlin queries)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Query Patterns in Use

Analysis of `src/services/neptune_graph_service.py` reveals simple Gremlin patterns:

| Pattern | Example | Complexity |
|---------|---------|------------|
| Connection test | `g.V().limit(1)` | Simple |
| Vertex creation | `g.addV('CodeEntity').property(...)` | Simple |
| Edge creation | `g.V().has('entity_id', x).as('from')...addE(...)` | Medium |
| Traversal | `g.V().has('name', x).repeat(bothE().otherV()).times(n)` | Medium |
| Search | `g.V().has('name', containing(x)).limit(n)` | Simple |
| Delete | `g.V().has('repository', x).drop()` | Simple |

**Files with Gremlin queries:** 15 files in `src/services/`

---

## Options Evaluated

### Option A: Neo4j Gremlin Plugin

Use Apache TinkerPop's neo4j-gremlin module to run existing Gremlin queries on Neo4j.

**Pros:**
- No changes to NeptuneGraphService
- Single query language across all deployments

**Cons:**
- ⚠️ Uncertain long-term support: *"Neo4j-Gremlin may be dropped from future versions of TinkerPop"*
- Performance overhead (translation layer)
- Limited data type support vs native Neo4j
- Old/archived plugin repositories

**Risk Level:** High

---

### Option B: Native Cypher for Neo4j (RECOMMENDED)

Implement a new Neo4jGraphService using native Cypher queries.

**Pros:**
- Native performance (no translation overhead)
- Long-term support (Neo4j owns Cypher)
- GQL standard alignment (ISO standardization in progress)
- Rich tooling ecosystem (Neo4j Browser, Bloom, etc.)
- Clean abstraction layer makes implementation isolated

**Cons:**
- Requires implementing ~500 lines of Cypher equivalents
- Two query languages to maintain

**Risk Level:** Low

**Effort:** 2-3 weeks (estimated)

---

### Option C: JanusGraph (Alternative)

Replace Neo4j with JanusGraph for native Gremlin support.

**Pros:**
- Native Gremlin (no translation needed)
- Apache 2.0 license
- Pluggable storage backends

**Cons:**
- Less mature than Neo4j
- Smaller community and ecosystem
- More operational complexity
- No Cypher support

**Risk Level:** Medium

---

## Decision

**Implement Option B: Native Cypher adapter for Neo4j.**

### Rationale

1. **Clean abstraction exists** - GraphDatabaseService interface isolates query language from business logic
2. **Simple query patterns** - No complex Gremlin-specific patterns that are hard to translate
3. **Long-term viability** - Cypher is the de facto standard, with GQL ISO standardization underway
4. **Performance** - Native queries outperform translation layers
5. **Ecosystem** - Neo4j tooling (Browser, Bloom, GDS) works best with native Cypher

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 GraphDatabaseService (Abstract)              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   NeptuneGraphAdapter      Neo4jGraphAdapter (NEW)           │
│   (AWS SaaS - Gremlin)     (Self-Hosted - Cypher)           │
│                                                              │
│         │                           │                        │
│         ▼                           ▼                        │
│   NeptuneGraphService      Neo4jGraphService (NEW)           │
│   (Gremlin queries)        (Native Cypher queries)           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Query Translation Reference

### Vertex Operations

| Operation | Gremlin | Cypher |
|-----------|---------|--------|
| Create vertex | `g.addV('Label').property('k','v')` | `CREATE (n:Label {k: 'v'}) RETURN n` |
| Get vertex | `g.V().has('id', x).valueMap(true)` | `MATCH (n {id: $x}) RETURN n` |
| Update vertex | `g.V(id).property('k','v')` | `MATCH (n) WHERE id(n) = $id SET n.k = 'v'` |
| Delete vertex | `g.V().has('id', x).drop()` | `MATCH (n {id: $x}) DETACH DELETE n` |

### Edge Operations

| Operation | Gremlin | Cypher |
|-----------|---------|--------|
| Create edge | `g.V(from).addE('REL').to(g.V(to))` | `MATCH (a {id:$from}), (b {id:$to}) CREATE (a)-[:REL]->(b)` |
| Get edges | `g.V(id).outE('REL')` | `MATCH (n {id:$id})-[r:REL]->() RETURN r` |
| Delete edge | `g.E(id).drop()` | `MATCH ()-[r]->() WHERE id(r) = $id DELETE r` |

### Traversal Operations

| Operation | Gremlin | Cypher |
|-----------|---------|--------|
| Find related | `g.V(x).repeat(out()).times(2)` | `MATCH (n {id:$x})-[*1..2]->(m) RETURN m` |
| With path | `g.V(x).repeat(out()).emit().path()` | `MATCH p = (n {id:$x})-[*]->(m) RETURN p` |
| Filtered | `g.V(x).out('CALLS').out('USES')` | `MATCH (n {id:$x})-[:CALLS]->()-[:USES]->(m) RETURN m` |

### Search Operations

| Operation | Gremlin | Cypher |
|-----------|---------|--------|
| Name contains | `g.V().has('name', containing(x))` | `MATCH (n) WHERE n.name CONTAINS $x RETURN n` |
| Text search | `g.V().has('name', textContains(x))` | `MATCH (n) WHERE n.name =~ ('.*' + $x + '.*') RETURN n` |
| Full-text | N/A | `CALL db.index.fulltext.queryNodes('idx', $query)` |

---

## Implementation Plan

### Phase 1: Core Adapter (Week 1-2)

1. Create `src/services/providers/neo4j/neo4j_graph_service.py`
   - Connection management (Bolt protocol)
   - CRUD operations for vertices/edges
   - Basic traversal queries

2. Create `src/services/providers/neo4j/neo4j_adapter.py`
   - Implement GraphDatabaseService interface
   - Map entity types to Neo4j labels

3. Unit tests with embedded Neo4j or testcontainers

### Phase 2: Advanced Features (Week 2-3)

1. Complex traversal patterns
2. Full-text search integration
3. Bulk operations (batch import)
4. Transaction support

### Phase 3: Integration (Week 3)

1. Factory method to select adapter by deployment mode
2. Integration tests
3. Performance benchmarks vs Gremlin

---

## Cypher Connection Example

```python
# src/services/providers/neo4j/neo4j_graph_service.py

from neo4j import GraphDatabase

class Neo4jGraphService:
    """Native Cypher implementation for self-hosted Neo4j."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def add_entity(self, entity: GraphEntity) -> str:
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (n:CodeEntity {
                    entity_id: $entity_id,
                    name: $name,
                    entity_type: $entity_type,
                    file_path: $file_path,
                    repository: $repository
                })
                RETURN n.entity_id AS id
                """,
                entity_id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type.value,
                file_path=entity.file_path,
                repository=entity.repository
            )
            return result.single()["id"]

    def find_related_code(
        self,
        entity_id: str,
        max_depth: int = 2,
        relationship_types: list[str] | None = None
    ) -> list[dict]:
        rel_filter = ""
        if relationship_types:
            rel_filter = ":" + "|".join(relationship_types)

        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (start {{entity_id: $entity_id}})
                MATCH path = (start)-[r{rel_filter}*1..{max_depth}]-(related)
                RETURN DISTINCT related,
                       type(last(relationships(path))) AS relationship,
                       length(path) AS depth
                """,
                entity_id=entity_id
            )
            return [dict(record) for record in result]
```

---

## Migration Path

For customers migrating from SaaS (Neptune) to self-hosted (Neo4j):

1. **Export** graph data using Neptune bulk export (CSV/JSON)
2. **Transform** property names if needed (entity_id → entityId)
3. **Import** using Neo4j Admin Import or LOAD CSV
4. **Validate** data integrity with count queries

The Migration Toolkit (Phase 1.5 of ADR-049) will automate this process.

---

## Future Considerations

### Neptune openCypher Support

AWS Neptune now supports openCypher. In future, we could:
- Migrate SaaS deployment from Gremlin to openCypher
- Share query logic between Neptune and Neo4j
- Simplify to single query language

### GQL Standard

ISO GQL (Graph Query Language) standardization is in progress, heavily influenced by Cypher. Adopting Cypher now aligns with the likely future standard.

---

## References

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [openCypher Project](https://opencypher.org/)
- [TinkerPop neo4j-gremlin](https://tinkerpop.apache.org/docs/current/reference/#neo4j-gremlin)
- [Cypher for Gremlin](https://github.com/opencypher/cypher-for-gremlin)
- ADR-004: Cloud Abstraction Layer
- ADR-049: Self-Hosted Deployment Strategy
