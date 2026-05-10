"""Dynamic dispatch via getattr and a dict-of-callables.

Tier 1 will not resolve these targets (no static name to look up);
Tier 2 may or may not depending on type-inference accuracy; Tier 3
LLM is the intended resolver. The fixture exists to assert the
deterministic tiers DON'T spuriously resolve them.
"""

from __future__ import annotations

HANDLERS = {
    "ping": lambda: "pong",
    "echo": lambda x: x,
}


class Dispatcher:
    def dispatch(self, name: str):
        # getattr-based dispatch -- Tier 1 cannot resolve.
        return getattr(self, f"handle_{name}")()

    def call_via_dict(self, name: str):
        # Dict-of-callables -- Tier 1 cannot resolve.
        return HANDLERS[name]()

    def handle_ping(self):
        return "pong"

    def handle_pong(self):
        return "ping"
