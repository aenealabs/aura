"""Phase 5: config-layer dependency extraction (ADR-090).

Detects code references to environment variables, AWS SSM parameters,
KMS aliases, and feature flags and emits :class:`CodeRelationship`
records targeting the new Phase 5 vertex types. The agent is
deliberately deterministic-first per the ADR's Phase 5 ruling:
regex + AST-context disambiguation only, with LLM augmentation
deferred until measured precision/recall on fixture repos drops
below the 90% threshold.

Sally's tiering (cybersecurity review) applies: ``USES_KMS_KEY`` and
``READS_CONFIG`` default to ``RESTRICTED``; ``DEPENDS_ON_ENV`` and
``FEATURE_GATED_BY`` default to ``CONFIDENTIAL``. The sensitivity
travels on the edge as a property and is the gate the ADR-090
Pattern A enforcement layer (Phase 5.3) reads from at query time.

The agent runs after Phase 2/3 AST parsing so it can attribute each
configuration reference to the smallest enclosing scope (function,
method, or module) using the entity list the parser already
produced. The relationship's ``source_name`` and
``source_parent_chain`` correspond to that scope; targets are the
config parameter / env var / KMS alias / feature flag *names*
(verbatim from source), and the consumer (Phase 5.2) materializes
matching vertices.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable, Iterator

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel

logger = logging.getLogger(__name__)


# Sensitivity tiers per Sally's review (ADR-090 Thread 4).
SENSITIVITY_RESTRICTED = "restricted"
SENSITIVITY_CONFIDENTIAL = "confidential"
SENSITIVITY_INTERNAL = "internal"
SENSITIVITY_TOP_LEVEL = "top_level"


# Vertex labels used by Phase 5.2 writers (declared here so detectors
# can attach a ``vertex_label`` hint to each emitted relationship's
# properties — the writer reads this to pick the right vertex type).
VERTEX_CONFIG_PARAMETER = "ConfigParameter"
VERTEX_KMS_ALIAS = "KMSAlias"
VERTEX_FEATURE_FLAG = "FeatureFlag"


# Per-edge sensitivity defaults. Phase 5.3 reads these to gate
# traversal; producers may emit a per-edge override property to
# bump sensitivity higher for known-secret parameter names (e.g.,
# ``/myapp/db/master_password``) but never below the default
# (fail-closed mediation).
EDGE_DEFAULT_SENSITIVITY: dict[str, str] = {
    EdgeLabel.READS_CONFIG.value: SENSITIVITY_RESTRICTED,
    EdgeLabel.USES_KMS_KEY.value: SENSITIVITY_RESTRICTED,
    EdgeLabel.DEPENDS_ON_ENV.value: SENSITIVITY_CONFIDENTIAL,
    EdgeLabel.FEATURE_GATED_BY.value: SENSITIVITY_CONFIDENTIAL,
}


# -- Regex bank ----------------------------------------------------------
#
# Each pattern is anchored on the call site or attribute access shape
# it targets. Groups extract the bare name. Patterns are intentionally
# tight: this is the deterministic-first stage, and false positives
# burn ABAC clearance more aggressively than misses.

_ENV_PATTERNS_PYTHON: tuple[re.Pattern[str], ...] = (
    # os.environ.get("X")  /  os.environ.get('X')
    re.compile(r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"),
    # os.environ["X"]
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]"),
    # os.getenv("X")
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"),
)

_ENV_PATTERNS_JAVASCRIPT: tuple[re.Pattern[str], ...] = (
    # process.env.X  (preferred shape; X is an identifier)
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    # process.env["X"]
    re.compile(r"process\.env\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]"),
)

# SSM patterns: targets boto3 client calls and the canonical "/path"
# parameter names. ``Name=`` keyword arg is the high-confidence shape.
_SSM_PATTERNS: tuple[re.Pattern[str], ...] = (
    # client.get_parameter(Name='/path/to/param')
    re.compile(
        r"\.get_parameter[s]?\(\s*[^)]*Name[s]?\s*=\s*['\"]"
        r"([/A-Za-z0-9_\-\.]+)['\"]"
    ),
    # ssm.get_parameter(Name="...") with named-argument shape
    re.compile(
        r"ssm[A-Za-z_]*\.get_parameter[s]?\([^)]*['\"]" r"(/[A-Za-z0-9_\-\./]+)['\"]"
    ),
)

# KMS aliases: alias/<name> and full key ARNs.
_KMS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"['\"](alias/[A-Za-z0-9_\-/]+)['\"]"),
    re.compile(r"['\"](arn:aws:kms:[a-z0-9\-]+:\d+:key/[A-Fa-f0-9\-]+)['\"]"),
    re.compile(r"['\"](arn:aws:kms:[a-z0-9\-]+:\d+:alias/[A-Za-z0-9_\-/]+)['\"]"),
)

# Feature flags. LaunchDarkly is the most common public surface;
# patterns also cover a generic ``feature_flag(...)`` / ``isEnabled(...)``
# helper shape that customer code commonly wraps around vendors.
_FEATURE_FLAG_PATTERNS: tuple[re.Pattern[str], ...] = (
    # ldclient.variation("flag-name", ...)
    re.compile(
        r"(?:ldclient|launchDarkly|ldClient)\."
        r"(?:variation|boolVariation|stringVariation|jsonVariation)"
        r"\(\s*['\"]([a-zA-Z][a-zA-Z0-9_\-]*)['\"]"
    ),
    # feature_flag("name") / featureFlag("name") / isEnabled("name")
    re.compile(
        r"(?:feature_flag|featureFlag|isEnabled|is_enabled|flag_enabled)"
        r"\(\s*['\"]([a-zA-Z][a-zA-Z0-9_\-]*)['\"]"
    ),
)


@dataclass
class ConfigScanStats:
    """Per-run extraction telemetry."""

    files_scanned: int = 0
    env_vars_emitted: int = 0
    ssm_params_emitted: int = 0
    kms_aliases_emitted: int = 0
    feature_flags_emitted: int = 0
    files_skipped: int = 0


@dataclass
class _Match:
    edge_label: str
    target_name: str
    line: int
    vertex_label: str
    extra_properties: dict = field(default_factory=dict)


class ConfigDependencyAgent:
    """Deterministic Phase 5 config-dependency extractor.

    Usage::

        agent = ConfigDependencyAgent()
        relationships = agent.scan_repo(
            entities=parser_entities,
            file_sources={path: text, ...},
        )

    The agent does not own file IO; the caller (typically the git
    ingestion pipeline) supplies a mapping from relative file path
    to source text. This keeps the agent unit-testable without a
    repo checkout and lets the caller apply size limits / file-type
    filters consistently with the rest of the pipeline.
    """

    PYTHON_SUFFIXES: frozenset[str] = frozenset({".py", ".pyi"})
    JS_SUFFIXES: frozenset[str] = frozenset(
        {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
    )

    def scan_repo(
        self,
        entities: Iterable[CodeEntity],
        file_sources: dict[str, str],
    ) -> tuple[list[CodeRelationship], ConfigScanStats]:
        stats = ConfigScanStats()
        scope_index = self._build_scope_index(list(entities))
        relationships: list[CodeRelationship] = []
        for file_path, source in file_sources.items():
            stats.files_scanned += 1
            try:
                file_relationships = self._scan_file(
                    file_path, source, scope_index, stats
                )
            except Exception as e:
                logger.warning(f"Config dependency scan failed for {file_path}: {e}")
                stats.files_skipped += 1
                continue
            relationships.extend(file_relationships)
        return relationships, stats

    # -- Scope indexing -----------------------------------------------

    @staticmethod
    def _build_scope_index(
        entities: list[CodeEntity],
    ) -> dict[str, list[CodeEntity]]:
        """Group entities by file_path so we can look up the smallest
        enclosing scope for a given line number in O(1) per file.
        """
        index: dict[str, list[CodeEntity]] = {}
        for entity in entities:
            if not entity.file_path or entity.entity_type not in {
                "function",
                "method",
                "class",
            }:
                continue
            index.setdefault(entity.file_path, []).append(entity)
        # Sort each file's entities by line_number ascending so the
        # smallest enclosing scope is the LAST entity whose line
        # number is <= the call site line. Phase 4b/5 share this
        # convention.
        for bucket in index.values():
            bucket.sort(key=lambda e: e.line_number)
        return index

    @staticmethod
    def _enclosing_scope(
        scope_index: dict[str, list[CodeEntity]],
        file_path: str,
        line: int,
    ) -> CodeEntity | None:
        bucket = scope_index.get(file_path, [])
        chosen: CodeEntity | None = None
        for entity in bucket:
            if entity.line_number <= line:
                chosen = entity
            else:
                break
        return chosen

    # -- Per-file dispatch --------------------------------------------

    def _scan_file(
        self,
        file_path: str,
        source: str,
        scope_index: dict[str, list[CodeEntity]],
        stats: ConfigScanStats,
    ) -> list[CodeRelationship]:
        suffix = PurePosixPath(file_path).suffix.lower()
        if suffix in self.PYTHON_SUFFIXES:
            language = "python"
            env_patterns = _ENV_PATTERNS_PYTHON
        elif suffix in self.JS_SUFFIXES:
            language = "javascript"
            env_patterns = _ENV_PATTERNS_JAVASCRIPT
        else:
            return []

        line_index = _LineIndex(source)
        # Two patterns can match the same call shape (e.g. both SSM
        # patterns recognise ``ssm.get_parameter(Name='/p')``); dedupe
        # by (edge_label, target_name, line) so each reference emits
        # exactly one edge.
        raw_matches = self._extract_matches(source, line_index, env_patterns)
        seen: set[tuple[str, str, int]] = set()
        matches: list[_Match] = []
        for m in raw_matches:
            key = (m.edge_label, m.target_name, m.line)
            if key in seen:
                continue
            seen.add(key)
            matches.append(m)
        relationships: list[CodeRelationship] = []
        for match in matches:
            scope = self._enclosing_scope(scope_index, file_path, match.line)
            source_name = scope.name if scope else PurePosixPath(file_path).stem
            source_chain = tuple(scope.parent_chain or ()) if scope is not None else ()
            sensitivity = EDGE_DEFAULT_SENSITIVITY.get(
                match.edge_label, SENSITIVITY_RESTRICTED
            )
            properties = {
                "line": match.line,
                "sensitivity": sensitivity,
                "vertex_label": match.vertex_label,
                "language": language,
                **match.extra_properties,
            }
            relationships.append(
                CodeRelationship(
                    source_name=source_name,
                    source_parent_chain=source_chain,
                    target_name=match.target_name,
                    relationship=match.edge_label,
                    properties=properties,
                    file_path=file_path,
                )
            )
            self._increment_counter(match.edge_label, stats)
        return relationships

    @staticmethod
    def _increment_counter(edge_label: str, stats: ConfigScanStats) -> None:
        if edge_label == EdgeLabel.DEPENDS_ON_ENV.value:
            stats.env_vars_emitted += 1
        elif edge_label == EdgeLabel.READS_CONFIG.value:
            stats.ssm_params_emitted += 1
        elif edge_label == EdgeLabel.USES_KMS_KEY.value:
            stats.kms_aliases_emitted += 1
        elif edge_label == EdgeLabel.FEATURE_GATED_BY.value:
            stats.feature_flags_emitted += 1

    # -- Detectors ----------------------------------------------------

    def _extract_matches(
        self,
        source: str,
        line_index: "_LineIndex",
        env_patterns: tuple[re.Pattern[str], ...],
    ) -> Iterator[_Match]:
        # Env vars
        for pattern in env_patterns:
            for m in pattern.finditer(source):
                yield _Match(
                    edge_label=EdgeLabel.DEPENDS_ON_ENV.value,
                    target_name=m.group(1),
                    line=line_index.line_for(m.start()),
                    vertex_label=VERTEX_CONFIG_PARAMETER,
                    extra_properties={"kind": "env"},
                )

        # SSM parameters
        for pattern in _SSM_PATTERNS:
            for m in pattern.finditer(source):
                yield _Match(
                    edge_label=EdgeLabel.READS_CONFIG.value,
                    target_name=m.group(1),
                    line=line_index.line_for(m.start()),
                    vertex_label=VERTEX_CONFIG_PARAMETER,
                    extra_properties={"kind": "ssm"},
                )

        # KMS aliases / ARNs
        for pattern in _KMS_PATTERNS:
            for m in pattern.finditer(source):
                yield _Match(
                    edge_label=EdgeLabel.USES_KMS_KEY.value,
                    target_name=m.group(1),
                    line=line_index.line_for(m.start()),
                    vertex_label=VERTEX_KMS_ALIAS,
                )

        # Feature flags
        for pattern in _FEATURE_FLAG_PATTERNS:
            for m in pattern.finditer(source):
                yield _Match(
                    edge_label=EdgeLabel.FEATURE_GATED_BY.value,
                    target_name=m.group(1),
                    line=line_index.line_for(m.start()),
                    vertex_label=VERTEX_FEATURE_FLAG,
                )


class _LineIndex:
    """Cheap O(log N) byte-offset → line-number index.

    Holds the start offsets of every line so :meth:`line_for` can
    binary-search instead of counting newlines per match.
    """

    __slots__ = ("_starts",)

    def __init__(self, source: str):
        starts = [0]
        for idx, ch in enumerate(source):
            if ch == "\n":
                starts.append(idx + 1)
        self._starts = starts

    def line_for(self, offset: int) -> int:
        # bisect_right would be cleaner, but a manual loop avoids the
        # import for what is otherwise a tight inner.
        lo, hi = 0, len(self._starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1
