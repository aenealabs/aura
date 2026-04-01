"""
Project Aura - Polyglot Dependency Graph Contracts

Data models and enums for cross-language dependency tracking
with billion-node scalability via Neptune sharding.

Based on ADR-079: Scale & AI Model Security
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    KOTLIN = "kotlin"
    RUST = "rust"
    CPP = "cpp"
    C = "c"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    SCALA = "scala"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """Types of package dependencies."""

    DIRECT = "direct"
    TRANSITIVE = "transitive"
    DEV = "dev"
    OPTIONAL = "optional"
    PEER = "peer"
    RUNTIME = "runtime"
    BUILD = "build"


class RelationType(str, Enum):
    """Types of code relationships."""

    IMPORTS = "imports"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    CALLS = "calls"
    INSTANTIATES = "instantiates"
    USES_TYPE = "uses_type"
    INHERITS = "inherits"
    COMPOSES = "composes"
    REFERENCES = "references"
    DEFINES = "defines"


class EntityType(str, Enum):
    """Types of code entities."""

    FILE = "file"
    MODULE = "module"
    PACKAGE = "package"
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE = "type"
    ENUM = "enum"


class IndexStatus(str, Enum):
    """Status of repository indexing."""

    PENDING = "pending"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    OUTDATED = "outdated"


class VulnerabilityStatus(str, Enum):
    """Status of vulnerability in dependency."""

    UNAFFECTED = "unaffected"
    AFFECTED = "affected"
    FIXED = "fixed"
    UNDER_REVIEW = "under_review"


class Ecosystem(str, Enum):
    """Package ecosystems."""

    NPM = "npm"
    PYPI = "pypi"
    MAVEN = "maven"
    CARGO = "cargo"
    GO = "go"
    NUGET = "nuget"
    RUBYGEMS = "rubygems"
    PACKAGIST = "packagist"
    COCOAPODS = "cocoapods"


@dataclass
class CodeEntity:
    """Entity in the code graph."""

    id: str
    type: EntityType
    name: str
    qualified_name: str
    language: Language
    file_path: str
    line_start: int
    line_end: int
    repository_id: Optional[str] = None
    visibility: str = "public"  # public, private, protected, internal
    docstring: Optional[str] = None
    signature: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class CodeRelationship:
    """Relationship between code entities."""

    id: str
    source_id: str
    target_id: str
    type: RelationType
    weight: float = 1.0
    line_number: Optional[int] = None
    is_cross_language: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DependencyNode:
    """Node in dependency graph."""

    package_name: str
    version: str
    language: Language
    ecosystem: Ecosystem
    dep_type: DependencyType
    depth: int
    purl: Optional[str] = None  # Package URL
    license: Optional[str] = None
    vulnerabilities: list[str] = field(default_factory=list)
    children: list["DependencyNode"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PackageVulnerability:
    """Vulnerability in a package."""

    vulnerability_id: str
    package_name: str
    ecosystem: Ecosystem
    affected_versions: str  # Version range
    fixed_version: Optional[str] = None
    severity: str = "unknown"
    cvss_score: Optional[float] = None
    cwe_ids: list[str] = field(default_factory=list)
    description: str = ""
    published_at: Optional[datetime] = None
    references: list[str] = field(default_factory=list)


@dataclass
class ImpactAnalysis:
    """Impact analysis result."""

    analysis_id: str
    repository_id: str
    changed_entity: CodeEntity
    directly_affected: list[CodeEntity] = field(default_factory=list)
    transitively_affected: list[CodeEntity] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    affected_packages: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    analysis_depth: int = 0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VulnerabilityPropagation:
    """Shows how a vulnerability propagates through code."""

    propagation_id: str
    vulnerability: PackageVulnerability
    affected_entities: list[CodeEntity] = field(default_factory=list)
    propagation_paths: list[list[str]] = field(default_factory=list)
    total_affected_files: int = 0
    total_affected_functions: int = 0
    risk_score: float = 0.0


@dataclass
class IndexingResult:
    """Result of repository indexing."""

    index_id: str
    repository_id: str
    status: IndexStatus
    languages_detected: list[Language] = field(default_factory=list)
    total_files: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    total_packages: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class IncrementalUpdate:
    """Result of incremental graph update."""

    update_id: str
    repository_id: str
    commit_sha: str
    files_updated: int = 0
    entities_added: int = 0
    entities_removed: int = 0
    entities_modified: int = 0
    relationships_added: int = 0
    relationships_removed: int = 0
    duration_ms: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CrossLanguageDependency:
    """Dependency that crosses language boundaries."""

    dependency_id: str
    source_entity: CodeEntity
    target_entity: CodeEntity
    source_language: Language
    target_language: Language
    binding_type: str  # ffi, rpc, http, grpc, etc.
    interface_definition: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LanguageStats:
    """Statistics for a language in repository."""

    language: Language
    file_count: int = 0
    line_count: int = 0
    entity_count: int = 0
    package_count: int = 0
    percentage: float = 0.0


@dataclass
class RepositoryGraph:
    """Complete graph for a repository."""

    repository_id: str
    name: str
    languages: list[LanguageStats] = field(default_factory=list)
    total_entities: int = 0
    total_relationships: int = 0
    total_packages: int = 0
    index_status: IndexStatus = IndexStatus.PENDING
    last_indexed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphQuery:
    """Query for the dependency graph."""

    query_id: str
    query_type: str  # gremlin, sparql, custom
    query_text: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 5000
    max_results: int = 1000
    shard_hint: Optional[int] = None  # Hint for shard routing


@dataclass
class GraphQueryResult:
    """Result of a graph query."""

    query_id: str
    success: bool
    result_count: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    execution_time_ms: int = 0
    shards_queried: int = 1
    truncated: bool = False
    error_message: Optional[str] = None


@dataclass
class ShardConfig:
    """Configuration for a Neptune shard."""

    shard_id: int
    endpoint: str
    reader_endpoint: str
    repository_hash_range: tuple[int, int]  # (start, end)
    status: str = "active"
    weight: float = 1.0


@dataclass
class FederatedQueryPlan:
    """Plan for executing a federated query across shards."""

    plan_id: str
    query: GraphQuery
    target_shards: list[ShardConfig] = field(default_factory=list)
    parallel: bool = True
    merge_strategy: str = "union"  # union, intersection, aggregate
    estimated_cost: float = 0.0


@dataclass
class DependencyDiff:
    """Diff between two dependency states."""

    diff_id: str
    repository_id: str
    base_commit: str
    head_commit: str
    added_packages: list[DependencyNode] = field(default_factory=list)
    removed_packages: list[DependencyNode] = field(default_factory=list)
    upgraded_packages: list[tuple[DependencyNode, DependencyNode]] = field(
        default_factory=list
    )
    downgraded_packages: list[tuple[DependencyNode, DependencyNode]] = field(
        default_factory=list
    )
    new_vulnerabilities: list[PackageVulnerability] = field(default_factory=list)
    fixed_vulnerabilities: list[PackageVulnerability] = field(default_factory=list)
