"""Aura fully-qualified name (FQN) construction for graph entities.

Per ADR-090, this module is the single source of truth for entity
identifiers in Aura's GraphRAG layer. It replaces the brittle
``{file_path}::{name}`` scheme that collided on overloads, nested
classes, and cross-repo file-path overlaps.

Format::

    {scheme}:{repo_id}:{module_path}:{symbol_path}#{kind}[@{disambiguator}]

Components:

- ``scheme`` -- language identifier (``python``, ``typescript``,
  ``javascript``, or ``unknown``).
- ``repo_id`` -- stable repository identifier (e.g. ``owner/repo``).
  Repo-scoped: there is no cross-repo unification; two repos that both
  contain ``utils.User`` produce distinct FQNs.
- ``module_path`` -- dotted module name, derived from the file path by
  stripping a leading ``src/``, ``lib/``, or ``app/`` and the file
  extension.
- ``symbol_path`` -- dotted chain of every enclosing scope, e.g.
  ``Router.Config.timeout``.
- ``kind`` -- one of ``class``, ``function``, ``method``, ``variable``,
  ``import``.
- ``disambiguator`` -- optional integer suffix (``@0``, ``@1`` ...)
  appended in declaration order when two entities collide on
  ``(module_path, symbol_path, kind)``. Mirrors SCIP convention.

Two surfaces are exposed:

``compute_fqn`` is a pure function suitable for migration (where every
entity in a file is known up front and disambiguation can be derived
from declaration order).

``FQNBuilder`` is a stateful helper for streaming write paths (where
the parser visits one entity at a time and disambiguation requires
remembering previously emitted symbols).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

# Path components that are conventionally source-tree roots and are
# stripped when deriving the module path. Order does not matter; the
# leading match wins.
_SOURCE_TREE_ROOTS: frozenset[str] = frozenset({"src", "lib", "app"})

# File extensions and the SCIP-style scheme they map to.
_EXTENSION_TO_SCHEME: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}


def derive_scheme(file_path: str) -> str:
    """Return the FQN scheme component for a given source file path.

    Unknown extensions resolve to ``"unknown"`` rather than raising:
    a graph entity from a less-common language is still better
    represented under a deterministic FQN than left with a brittle
    legacy ID.
    """
    suffix = PurePosixPath(file_path).suffix.lower()
    return _EXTENSION_TO_SCHEME.get(suffix, "unknown")


def derive_module_path(file_path: str) -> str:
    """Convert a source file path to a dotted module path.

    Examples::

        derive_module_path("src/myapp/auth.py")   -> "myapp.auth"
        derive_module_path("lib/utils.py")        -> "utils"
        derive_module_path("myapp/api/main.py")   -> "myapp.api.main"
        derive_module_path("src/auth.ts")         -> "auth"

    The leading ``src/``, ``lib/``, or ``app/`` segment is stripped if
    present; the file extension is dropped. Empty paths and paths that
    consist solely of a stripped root resolve to ``"<unknown>"`` so
    downstream code can still construct a syntactically valid FQN.
    """
    if not file_path:
        return "<unknown>"

    parts = list(PurePosixPath(file_path).parts)

    # Drop leading source-tree root if present.
    if parts and parts[0] in _SOURCE_TREE_ROOTS:
        parts = parts[1:]

    if not parts:
        return "<unknown>"

    # Strip the file extension from the trailing path component.
    last = PurePosixPath(parts[-1])
    parts[-1] = last.stem if last.suffix else last.name

    # Filter empty components (e.g. a stray double-slash) and dot
    # segments.
    cleaned = [p for p in parts if p and p != "."]
    if not cleaned:
        return "<unknown>"

    return ".".join(cleaned)


@dataclass(frozen=True)
class FQNComponents:
    """Structured FQN, useful for tests and round-tripping."""

    scheme: str
    repo_id: str
    module_path: str
    symbol_path: str
    kind: str
    disambiguator: int | None = None

    def to_string(self) -> str:
        base = (
            f"{self.scheme}:{self.repo_id}:{self.module_path}:"
            f"{self.symbol_path}#{self.kind}"
        )
        if self.disambiguator is not None:
            return f"{base}@{self.disambiguator}"
        return base


def compute_fqn(
    *,
    name: str,
    kind: str,
    file_path: str,
    repo_id: str,
    parent_chain: tuple[str, ...] = (),
    disambiguator: int | None = None,
) -> str:
    """Compute the canonical FQN for an entity.

    Parameters
    ----------
    name:
        The entity's declared name (``MyClass``, ``my_function``).
    kind:
        One of ``class``, ``function``, ``method``, ``variable``,
        ``import``. Other values are accepted but should be added to
        the canonical set if they recur.
    file_path:
        Source file path relative to the repository root.
    repo_id:
        Repository identifier (e.g. ``owner/repo``).
    parent_chain:
        Names of every enclosing scope, root-most first. For
        ``Router.Config.timeout``, ``parent_chain`` is
        ``("Router", "Config")`` and ``name`` is ``timeout``.
    disambiguator:
        Optional integer suffix for overloads or decorator-produced
        duplicates. Use :class:`FQNBuilder` for stateful disambiguation.

    Returns
    -------
    The FQN string.
    """
    scheme = derive_scheme(file_path)
    module_path = derive_module_path(file_path)
    symbol_chain = (*parent_chain, name)
    symbol_path = ".".join(symbol_chain)

    return FQNComponents(
        scheme=scheme,
        repo_id=repo_id,
        module_path=module_path,
        symbol_path=symbol_path,
        kind=kind,
        disambiguator=disambiguator,
    ).to_string()


@dataclass
class FQNBuilder:
    """Stateful FQN builder that disambiguates collisions in declaration order.

    Parsers visit AST nodes sequentially. When two methods collide on
    ``(module_path, symbol_path, kind)`` (e.g. ``@overload`` decorated
    pairs), the first emission gets no disambiguator, the second
    ``@1``, the third ``@2``, and so on. This matches SCIP's
    descriptor-suffix convention and is the disambiguation strategy
    selected for ADR-090.

    The builder is per-repository: callers should construct one
    builder per ingest job, since collision counts reset across repos.
    """

    repo_id: str
    _seen_counts: dict[tuple[str, str, str, str], int] = field(
        default_factory=dict, init=False, repr=False
    )

    def build(
        self,
        *,
        name: str,
        kind: str,
        file_path: str,
        parent_chain: tuple[str, ...] = (),
    ) -> str:
        """Return the FQN, assigning the next disambiguator on collision.

        First call for a given ``(scheme, module_path, symbol_path,
        kind)`` produces an unsuffixed FQN. Subsequent calls append
        ``@1``, ``@2``, ... in arrival order.
        """
        scheme = derive_scheme(file_path)
        module_path = derive_module_path(file_path)
        symbol_chain = (*parent_chain, name)
        symbol_path = ".".join(symbol_chain)
        key = (scheme, module_path, symbol_path, kind)

        count = self._seen_counts.get(key, 0)
        disambiguator = None if count == 0 else count
        self._seen_counts[key] = count + 1

        return FQNComponents(
            scheme=scheme,
            repo_id=self.repo_id,
            module_path=module_path,
            symbol_path=symbol_path,
            kind=kind,
            disambiguator=disambiguator,
        ).to_string()

    def reset(self) -> None:
        """Forget all collision state. Useful between independent runs."""
        self._seen_counts.clear()
