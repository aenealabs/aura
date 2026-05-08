"""Tail of the 3-way cycle. C inherits from A, closing the loop."""

from __future__ import annotations

from tests.fixtures.ingestion.pathological.circular_imports_3way.module_a import A


class C(A):
    def tail(self) -> int:
        return 0
