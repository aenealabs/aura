"""Three-way circular import: a -> b -> c -> a.

The ingestion pipeline must handle this without infinite recursion
or duplicate entity emission. INHERITS, IMPORTS, and CALLS edges
across the cycle should land exactly once per call site.
"""

from __future__ import annotations

from tests.fixtures.ingestion.pathological.circular_imports_3way import module_b


class A:
    """Top-of-cycle class. b.B subclasses A."""

    def hop(self) -> int:
        return module_b.B().hop_back()
