"""Middle of the 3-way cycle."""

from __future__ import annotations

from tests.fixtures.ingestion.pathological.circular_imports_3way import module_c


class B:
    def hop_back(self) -> int:
        return module_c.C().tail()
