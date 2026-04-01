"""
Project Aura - Neptune Sharding for Polyglot Graph

Neptune sharding strategy for billion-node graphs with
hash-based partitioning and federated query execution.

Based on ADR-079: Scale & AI Model Security
"""

import asyncio
import hashlib
from typing import Any, Optional

from .config import PolyglotConfig, get_polyglot_config
from .contracts import (
    FederatedQueryPlan,
    GraphQuery,
    GraphQueryResult,
    ShardConfig,
)
from .exceptions import (
    ShardNotFoundError,
)


class NeptuneShardRouter:
    """Routes queries to appropriate Neptune shard."""

    def __init__(
        self,
        shards: Optional[list[ShardConfig]] = None,
        config: Optional[PolyglotConfig] = None,
    ):
        """Initialize shard router."""
        self._config = config or get_polyglot_config()

        if shards:
            self.shards = shards
        else:
            # Initialize default shards based on config
            self.shards = self._create_default_shards()

        self.num_shards = len(self.shards)
        self._connections: dict[int, Any] = {}

    def _create_default_shards(self) -> list[ShardConfig]:
        """Create default shard configuration."""
        shards = []
        num_shards = self._config.sharding.num_shards
        range_size = (2**32) // num_shards

        for i in range(num_shards):
            start = i * range_size
            end = start + range_size - 1 if i < num_shards - 1 else 2**32 - 1

            # Use configured endpoints or generate from cluster endpoint
            if self._config.sharding.shard_endpoints and i < len(
                self._config.sharding.shard_endpoints
            ):
                endpoint = self._config.sharding.shard_endpoints[i]
            else:
                endpoint = self._config.neptune.cluster_endpoint

            shards.append(
                ShardConfig(
                    shard_id=i,
                    endpoint=endpoint,
                    reader_endpoint=self._config.neptune.reader_endpoint,
                    repository_hash_range=(start, end),
                )
            )

        return shards

    def get_shard_for_repository(self, repository_id: str) -> ShardConfig:
        """Get shard for repository based on hash."""
        hash_value = self._hash_repository(repository_id)
        shard_index = hash_value % self.num_shards
        return self.shards[shard_index]

    def get_shard_by_id(self, shard_id: int) -> ShardConfig:
        """Get shard by ID."""
        for shard in self.shards:
            if shard.shard_id == shard_id:
                return shard
        raise ShardNotFoundError(shard_id)

    def get_shards_for_query(
        self,
        repository_ids: Optional[list[str]] = None,
    ) -> list[ShardConfig]:
        """Get shards needed for query."""
        if repository_ids is None:
            # Query all shards
            return self.shards

        shards_needed = set()
        for repo_id in repository_ids:
            shard = self.get_shard_for_repository(repo_id)
            shards_needed.add(shard.shard_id)

        return [s for s in self.shards if s.shard_id in shards_needed]

    def _hash_repository(self, repository_id: str) -> int:
        """Hash repository ID to integer."""
        hash_bytes = hashlib.sha256(repository_id.encode()).digest()
        return int.from_bytes(hash_bytes[:4], byteorder="big")

    def create_query_plan(
        self,
        query: GraphQuery,
        repository_ids: Optional[list[str]] = None,
    ) -> FederatedQueryPlan:
        """Create execution plan for federated query."""
        target_shards = self.get_shards_for_query(repository_ids)

        # Estimate cost based on number of shards and query complexity
        estimated_cost = len(target_shards) * 1.0

        return FederatedQueryPlan(
            plan_id=f"plan-{query.query_id}",
            query=query,
            target_shards=target_shards,
            parallel=self._config.sharding.parallel_queries and len(target_shards) > 1,
            merge_strategy="union",
            estimated_cost=estimated_cost,
        )

    async def execute_federated_query(
        self,
        query: GraphQuery,
        repository_ids: Optional[list[str]] = None,
    ) -> GraphQueryResult:
        """Execute query across shards and merge results."""
        plan = self.create_query_plan(query, repository_ids)

        if not plan.target_shards:
            return GraphQueryResult(
                query_id=query.query_id,
                success=True,
                result_count=0,
                results=[],
                shards_queried=0,
            )

        if plan.parallel and len(plan.target_shards) > 1:
            return await self._execute_parallel(plan)
        else:
            return await self._execute_sequential(plan)

    async def _execute_parallel(
        self,
        plan: FederatedQueryPlan,
    ) -> GraphQueryResult:
        """Execute query on multiple shards in parallel."""
        # Limit parallel execution
        max_parallel = min(
            self._config.sharding.max_parallel_shards,
            len(plan.target_shards),
        )

        semaphore = asyncio.Semaphore(max_parallel)
        tasks = []

        async def query_shard(shard: ShardConfig) -> GraphQueryResult:
            async with semaphore:
                return await self._execute_on_shard(shard, plan.query)

        for shard in plan.target_shards:
            tasks.append(query_shard(shard))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results
        return self._merge_results(plan.query.query_id, results, plan)

    async def _execute_sequential(
        self,
        plan: FederatedQueryPlan,
    ) -> GraphQueryResult:
        """Execute query on shards sequentially."""
        results = []

        for shard in plan.target_shards:
            try:
                result = await self._execute_on_shard(shard, plan.query)
                results.append(result)
            except Exception as e:
                results.append(e)

        return self._merge_results(plan.query.query_id, results, plan)

    async def _execute_on_shard(
        self,
        shard: ShardConfig,
        query: GraphQuery,
    ) -> GraphQueryResult:
        """Execute query on a single shard."""
        # In a real implementation, this would connect to Neptune
        # For now, return mock results
        import time

        start_time = time.time()

        # Simulate query execution
        await asyncio.sleep(0.01)  # 10ms simulated latency

        execution_time_ms = int((time.time() - start_time) * 1000)

        return GraphQueryResult(
            query_id=query.query_id,
            success=True,
            result_count=0,
            results=[],
            execution_time_ms=execution_time_ms,
            shards_queried=1,
        )

    def _merge_results(
        self,
        query_id: str,
        results: list,
        plan: FederatedQueryPlan,
    ) -> GraphQueryResult:
        """Merge results from multiple shards."""
        merged_results = []
        total_time_ms = 0
        shards_queried = 0
        failed_shards = []
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_shards.append(plan.target_shards[i].shard_id)
                errors.append(str(result))
            elif isinstance(result, GraphQueryResult):
                if result.success:
                    merged_results.extend(result.results)
                    total_time_ms = max(total_time_ms, result.execution_time_ms)
                    shards_queried += result.shards_queried
                else:
                    failed_shards.append(plan.target_shards[i].shard_id)
                    if result.error_message:
                        errors.append(result.error_message)

        # Apply merge strategy
        if plan.merge_strategy == "intersection":
            # Would need to implement intersection logic
            pass
        elif plan.merge_strategy == "aggregate":
            # Would need to implement aggregation logic
            pass
        # Default is union (concatenation)

        # Check if query succeeded
        success = len(failed_shards) == 0 or shards_queried > 0

        # Truncate if needed
        max_results = plan.query.max_results
        truncated = len(merged_results) > max_results
        if truncated:
            merged_results = merged_results[:max_results]

        return GraphQueryResult(
            query_id=query_id,
            success=success,
            result_count=len(merged_results),
            results=merged_results,
            execution_time_ms=total_time_ms,
            shards_queried=shards_queried,
            truncated=truncated,
            error_message="; ".join(errors) if errors else None,
        )

    def get_shard_stats(self) -> dict[str, Any]:
        """Get statistics for all shards."""
        return {
            "num_shards": self.num_shards,
            "shards": [
                {
                    "shard_id": s.shard_id,
                    "endpoint": s.endpoint,
                    "status": s.status,
                    "hash_range": s.repository_hash_range,
                }
                for s in self.shards
            ],
        }


# Singleton pattern
_shard_router: Optional[NeptuneShardRouter] = None


def get_shard_router() -> NeptuneShardRouter:
    """Get singleton shard router."""
    global _shard_router
    if _shard_router is None:
        _shard_router = NeptuneShardRouter()
    return _shard_router


def reset_shard_router() -> None:
    """Reset singleton shard router."""
    global _shard_router
    _shard_router = None
