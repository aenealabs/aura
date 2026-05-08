"""Driver module exercising every ADR-090 phase in one file.

Frozen fixture: do not edit without running the golden-graph
regeneration step (``GOLDEN_GRAPH_UPDATE=1 pytest``).
"""

import os

from myapp.utils import helper


class Base:
    def shared(self) -> int:
        return 0


class Handler(Base):
    def handle(self) -> int:
        helper()
        self.shared()
        return int(os.environ.get("DATABASE_URL") or "0")
