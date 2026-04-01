"""Community Summarization Service for GraphRAG

Implements ADR-034 Phase 3: Community Summarization

Implements Microsoft GraphRAG community summarization:
1. Graph clustering (Leiden algorithm)
2. Hierarchical community detection
3. LLM-based summary generation
4. Summary index storage in Neptune

This enables answering global queries over entire codebases,
e.g., "What are the main architectural patterns in this codebase?"
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class NeptuneClient(Protocol):
    """Protocol for Neptune client."""

    async def execute(self, query: str) -> list:
        """Execute Gremlin query."""
        ...


class LLMClient(Protocol):
    """Protocol for LLM client."""

    async def generate(self, prompt: str, agent: str = "", operation: str = "") -> str:
        """Generate text from prompt."""
        ...


@dataclass
class Community:
    """A community of related code entities."""

    community_id: str
    level: int  # Hierarchy level (0=files, 1=modules, etc.)
    member_ids: list[str]
    parent_community_id: Optional[str] = None
    child_community_ids: list[str] = field(default_factory=list)
    summary: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class CommunityHierarchy:
    """Complete community hierarchy."""

    communities: dict[str, Community]
    levels: int
    total_members: int
    root_community_ids: list[str] = field(default_factory=list)


@dataclass
class CommunitySummarizationConfig:
    """Configuration for community summarization."""

    batch_size: int = 10
    max_levels: int = 4
    max_members_for_summary: int = 20
    min_community_size: int = 2
    summary_max_length: int = 500


class CommunitySummarizationService:
    """Generates and maintains community summaries for GraphRAG.

    Process:
    1. Load graph from Neptune
    2. Run Leiden clustering algorithm (or fallback)
    3. Build hierarchical community structure
    4. Generate summaries for each community using LLM
    5. Store summaries back in Neptune as summary nodes

    Query integration:
    - Global queries first search community summaries
    - Relevant communities guide entity retrieval
    - Enables "What is X about?" style queries

    Hierarchy levels:
    - Level 0: Files - individual code files
    - Level 1: Modules - related files grouped together
    - Level 2: Packages - larger organizational units
    - Level 3: Domains - high-level functional areas
    - Level 4: System - entire codebase summary
    """

    LEVEL_NAMES = {
        0: "file",
        1: "module",
        2: "package",
        3: "domain",
        4: "system",
    }

    def __init__(
        self,
        neptune_client: NeptuneClient,
        llm_client: LLMClient,
        config: Optional[CommunitySummarizationConfig] = None,
    ):
        """Initialize community summarization service.

        Args:
            neptune_client: Client for Neptune Gremlin queries
            llm_client: Client for LLM generation
            config: Summarization configuration
        """
        self.neptune = neptune_client
        self.llm = llm_client
        self.config = config or CommunitySummarizationConfig()

    async def build_community_hierarchy(self) -> CommunityHierarchy:
        """Build complete community hierarchy from Neptune graph.

        Returns:
            CommunityHierarchy with all communities and their relationships
        """
        logger.info("Building community hierarchy from Neptune graph...")

        # Step 1: Export graph for clustering
        graph_data = await self._export_graph_for_clustering()
        logger.info(
            f"Exported graph: {len(graph_data['vertices'])} vertices, "
            f"{len(graph_data['edges'])} edges"
        )

        if not graph_data["vertices"]:
            logger.warning("No vertices found in graph")
            return CommunityHierarchy(
                communities={}, levels=0, total_members=0, root_community_ids=[]
            )

        # Step 2: Run clustering
        clusters = self._run_clustering(graph_data)
        logger.info(f"Clustering produced {len(clusters)} communities")

        # Step 3: Build hierarchy from flat clusters
        hierarchy = self._build_hierarchy(clusters)
        logger.info(
            f"Built hierarchy with {len(hierarchy.communities)} total communities "
            f"across {hierarchy.levels} levels"
        )

        # Step 4: Generate summaries for each community
        await self._generate_all_summaries(hierarchy)

        # Step 5: Store summaries in Neptune
        await self._store_summaries_in_neptune(hierarchy)

        return hierarchy

    async def _export_graph_for_clustering(self) -> dict:
        """Export Neptune graph structure for clustering algorithm.

        Returns:
            Dictionary with vertices and edges
        """
        # Get all vertices
        vertices_query = """
        g.V().project('id', 'label', 'name', 'type', 'file_path')
            .by(id())
            .by(label())
            .by(coalesce(values('name'), constant('')))
            .by(coalesce(values('type'), constant('')))
            .by(coalesce(values('file_path'), constant('')))
        """

        # Get all edges
        edges_query = """
        g.E().project('source', 'target', 'label')
            .by(outV().id())
            .by(inV().id())
            .by(label())
        """

        try:
            vertices = await self.neptune.execute(vertices_query)
            edges = await self.neptune.execute(edges_query)

            return {"vertices": vertices, "edges": edges}

        except Exception as e:
            logger.error(f"Failed to export graph: {e}")
            return {"vertices": [], "edges": []}

    def _run_clustering(self, graph_data: dict) -> list[dict]:
        """Run clustering algorithm on graph.

        Attempts to use Leiden algorithm if available,
        falls back to connected components otherwise.

        Args:
            graph_data: Graph data with vertices and edges

        Returns:
            List of cluster dictionaries
        """
        try:
            return self._run_leiden_clustering(graph_data)
        except ImportError:
            logger.info("Leiden not available, using fallback clustering")
            return self._fallback_clustering(graph_data)
        except Exception as e:
            logger.warning(f"Leiden clustering failed: {e}, using fallback")
            return self._fallback_clustering(graph_data)

    def _run_leiden_clustering(self, graph_data: dict) -> list[dict]:
        """Run Leiden clustering algorithm on graph.

        Leiden is preferred over Louvain for:
        - Better modularity optimization
        - More stable communities
        - Hierarchical decomposition support

        Args:
            graph_data: Graph data

        Returns:
            List of cluster dictionaries
        """
        import igraph as ig
        import leidenalg

        # Build igraph from data
        g = ig.Graph()

        # Add vertices
        vertex_map = {}
        for i, v in enumerate(graph_data["vertices"]):
            g.add_vertex(name=str(v["id"]), label=v.get("label", ""))
            vertex_map[v["id"]] = i

        # Add edges
        for e in graph_data["edges"]:
            source_idx = vertex_map.get(e["source"])
            target_idx = vertex_map.get(e["target"])
            if source_idx is not None and target_idx is not None:
                try:
                    g.add_edge(source_idx, target_idx)
                except Exception:
                    continue  # Skip invalid edges

        # Run Leiden algorithm
        partition = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition)

        # Extract clusters
        clusters = []
        for i, cluster in enumerate(partition):
            if len(cluster) >= self.config.min_community_size:
                member_ids = [str(graph_data["vertices"][j]["id"]) for j in cluster]
                clusters.append(
                    {
                        "cluster_id": f"community_{i}",
                        "level": 0,
                        "members": member_ids,
                    }
                )

        return clusters

    def _fallback_clustering(self, graph_data: dict) -> list[dict]:
        """Simple connected components clustering as fallback.

        Args:
            graph_data: Graph data

        Returns:
            List of cluster dictionaries
        """
        # Build adjacency list
        adj: dict[str, set] = {}
        for v in graph_data["vertices"]:
            adj[str(v["id"])] = set()

        for e in graph_data["edges"]:
            source = str(e["source"])
            target = str(e["target"])
            if source in adj and target in adj:
                adj[source].add(target)
                adj[target].add(source)

        # Find connected components using DFS
        visited: set[str] = set()
        clusters: list[dict[str, Any]] = []

        def dfs(node: str, component: list) -> None:
            visited.add(node)
            component.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, component)

        for node in adj:
            if node not in visited:
                component: list = []
                dfs(node, component)
                if len(component) >= self.config.min_community_size:
                    clusters.append(
                        {
                            "cluster_id": f"community_{len(clusters)}",
                            "level": 0,
                            "members": component,
                        }
                    )

        return clusters

    def _build_hierarchy(self, flat_clusters: list[dict]) -> CommunityHierarchy:
        """Build hierarchical community structure from flat clusters.

        Args:
            flat_clusters: List of cluster dictionaries

        Returns:
            Complete community hierarchy
        """
        communities: dict[str, Community] = {}

        # Level 0: Direct clusters
        for cluster in flat_clusters:
            community = Community(
                community_id=cluster["cluster_id"],
                level=0,
                member_ids=cluster["members"],
                parent_community_id=None,
                child_community_ids=[],
            )
            communities[community.community_id] = community

        # Build higher levels by merging smaller communities
        current_level_communities = [c for c in communities.values() if c.level == 0]
        root_community_ids = []

        for level in range(1, self.config.max_levels):
            if len(current_level_communities) <= 1:
                # Only one community left - it's the root
                if current_level_communities:
                    root_community_ids = [current_level_communities[0].community_id]
                break

            # Group communities into parent communities
            parent_communities: list[Community] = []

            # Sort by size and group adjacent ones
            sorted_communities = sorted(
                current_level_communities, key=lambda c: len(c.member_ids)
            )

            for i in range(0, len(sorted_communities), 2):
                children = sorted_communities[i : i + 2]
                parent_id = f"community_L{level}_{len(parent_communities)}"

                parent = Community(
                    community_id=parent_id,
                    level=level,
                    member_ids=[m for c in children for m in c.member_ids],
                    parent_community_id=None,
                    child_community_ids=[c.community_id for c in children],
                )

                # Update children's parent reference
                for child in children:
                    child.parent_community_id = parent_id

                communities[parent_id] = parent
                parent_communities.append(parent)

            current_level_communities = parent_communities

            # Track root communities
            if level == self.config.max_levels - 1 or len(parent_communities) <= 1:
                root_community_ids = [c.community_id for c in parent_communities]

        # Calculate total members (avoid double counting)
        total_members = sum(
            len(c.member_ids) for c in communities.values() if c.level == 0
        )

        return CommunityHierarchy(
            communities=communities,
            levels=self.config.max_levels,
            total_members=total_members,
            root_community_ids=root_community_ids,
        )

    async def _generate_all_summaries(self, hierarchy: CommunityHierarchy) -> None:
        """Generate summaries for all communities using LLM.

        Processes level by level (bottom-up) so parent summaries
        can reference child summaries.

        Args:
            hierarchy: Community hierarchy to summarize
        """
        # Process level by level (bottom-up)
        max_level = (
            max(c.level for c in hierarchy.communities.values())
            if hierarchy.communities
            else 0
        )

        for level in range(max_level + 1):
            level_communities = [
                c for c in hierarchy.communities.values() if c.level == level
            ]

            logger.info(
                f"Generating summaries for level {level}: {len(level_communities)} communities"
            )

            # Batch process summaries
            for i in range(0, len(level_communities), self.config.batch_size):
                batch = level_communities[i : i + self.config.batch_size]
                tasks = [self._generate_community_summary(c, hierarchy) for c in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _generate_community_summary(
        self, community: Community, hierarchy: CommunityHierarchy
    ):
        """Generate summary for a single community.

        Args:
            community: Community to summarize
            hierarchy: Full hierarchy for context
        """
        try:
            # Get member details
            member_details = await self._get_member_details(
                community.member_ids[: self.config.max_members_for_summary]
            )

            # For higher levels, include child summaries
            child_summaries = ""
            if community.child_community_ids:
                children = [
                    hierarchy.communities[cid]
                    for cid in community.child_community_ids
                    if cid in hierarchy.communities
                ]
                child_summaries = "\n".join(
                    [
                        f"- {c.community_id}: {c.summary or 'No summary'}"
                        for c in children
                    ]
                )

            level_name = self.LEVEL_NAMES.get(
                community.level, f"level_{community.level}"
            )

            prompt = f"""Summarize this code community (a {level_name}-level grouping).

Community members ({len(community.member_ids)} entities):
{json.dumps(member_details, indent=2)[:2000]}

{f'Child community summaries:\\n{child_summaries}' if child_summaries else ''}

Write a 2-3 sentence summary describing:
1. What this code community does
2. Key patterns or responsibilities
3. How it relates to the broader system

Summary:"""

            summary = await self.llm.generate(
                prompt, agent="CommunitySummarizer", operation="summary_generation"
            )

            community.summary = summary.strip()[: self.config.summary_max_length]
            community.keywords = self._extract_keywords(summary)

        except Exception as e:
            logger.warning(
                f"Failed to generate summary for {community.community_id}: {e}"
            )
            community.summary = f"Community with {len(community.member_ids)} members"
            community.keywords = []

    async def _get_member_details(self, member_ids: list[str]) -> list[dict]:
        """Get details about community members from Neptune.

        Args:
            member_ids: List of member IDs

        Returns:
            List of member detail dictionaries
        """
        if not member_ids:
            return []

        # Build Gremlin query
        ids_str = ", ".join(f"'{m}'" for m in member_ids[:20])
        query = f"""
        g.V({ids_str})
            .project('id', 'name', 'type', 'description')
                .by(id())
                .by(coalesce(values('name'), constant('')))
                .by(label())
                .by(coalesce(values('description'), constant('')))
        """

        try:
            return await self.neptune.execute(query)
        except Exception as e:
            logger.warning(f"Failed to get member details: {e}")
            return [{"id": m, "name": m, "type": "unknown"} for m in member_ids[:20]]

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from summary text.

        Args:
            text: Summary text

        Returns:
            List of keywords
        """
        # Simple keyword extraction
        # In production: use NER or TF-IDF

        # Common words to exclude
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "and",
            "or",
            "but",
            "if",
            "then",
            "else",
            "when",
            "where",
            "why",
            "how",
            "what",
            "which",
            "who",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "for",
            "of",
            "to",
            "from",
            "by",
            "with",
            "as",
            "at",
            "in",
            "on",
            "about",
        }

        words = text.lower().split()
        keywords = []

        for word in words:
            # Clean word
            clean = "".join(c for c in word if c.isalnum())
            if clean and len(clean) > 3 and clean not in stop_words:
                if clean not in keywords:
                    keywords.append(clean)

        return keywords[:10]

    async def _store_summaries_in_neptune(self, hierarchy: CommunityHierarchy) -> None:
        """Store community summaries in Neptune as nodes.

        Args:
            hierarchy: Hierarchy with summaries to store
        """
        for community in hierarchy.communities.values():
            if not community.summary:
                continue

            # Escape special characters
            summary_escaped = community.summary.replace("'", "\\'").replace('"', '\\"')
            keywords_str = ",".join(community.keywords)

            query = f"""
            g.addV('CommunitySummary')
                .property('community_id', '{community.community_id}')
                .property('level', {community.level})
                .property('summary', '{summary_escaped}')
                .property('keywords', '{keywords_str}')
                .property('member_count', {len(community.member_ids)})
            """

            try:
                await self.neptune.execute(query)
            except Exception as e:
                logger.warning(
                    f"Failed to store summary for {community.community_id}: {e}"
                )

    async def search_communities(
        self, query: str, max_results: int = 10
    ) -> list[Community]:
        """Search for relevant communities by query.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of matching communities
        """
        # Search Neptune for matching community summaries
        search_terms = query.lower().split()[:5]
        terms_pattern = "|".join(search_terms)

        gremlin_query = f"""
        g.V().hasLabel('CommunitySummary')
            .has('summary', containing('{terms_pattern}'))
            .limit({max_results})
            .project('community_id', 'level', 'summary', 'keywords', 'member_count')
                .by('community_id')
                .by('level')
                .by('summary')
                .by('keywords')
                .by('member_count')
        """

        try:
            results = await self.neptune.execute(gremlin_query)
            return [
                Community(
                    community_id=r["community_id"],
                    level=r["level"],
                    member_ids=[],  # Not loaded for search results
                    summary=r["summary"],
                    keywords=r["keywords"].split(",") if r["keywords"] else [],
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Community search failed: {e}")
            return []

    async def get_community_by_id(self, community_id: str) -> Optional[Community]:
        """Get a specific community by ID.

        Args:
            community_id: Community ID

        Returns:
            Community or None
        """
        query = f"""
        g.V().hasLabel('CommunitySummary')
            .has('community_id', '{community_id}')
            .project('community_id', 'level', 'summary', 'keywords', 'member_count')
                .by('community_id')
                .by('level')
                .by('summary')
                .by('keywords')
                .by('member_count')
        """

        try:
            results = await self.neptune.execute(query)
            if results:
                r = results[0]
                return Community(
                    community_id=r["community_id"],
                    level=r["level"],
                    member_ids=[],
                    summary=r["summary"],
                    keywords=r["keywords"].split(",") if r["keywords"] else [],
                )
            return None
        except Exception as e:
            logger.warning(f"Failed to get community {community_id}: {e}")
            return None

    def get_service_stats(self) -> dict:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "config": {
                "batch_size": self.config.batch_size,
                "max_levels": self.config.max_levels,
                "min_community_size": self.config.min_community_size,
            },
            "level_names": self.LEVEL_NAMES,
        }
