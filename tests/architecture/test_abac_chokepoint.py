"""ADR-090 Phase 5.3 chokepoint contract test.

Pattern A enforcement requires every graph traversal to flow through
the ABAC-filtered wrapper in :mod:`context_retrieval_service`. A
direct call to :meth:`NeptuneGraphService.find_related_code` from
anywhere outside the wrapper (or the explicitly allow-listed
provider abstraction layer) bypasses the Phase 5 ABAC filter and
must be rejected at CI time, not at runtime.

The test walks every ``.py`` file under ``src/`` with the standard
:mod:`ast` module, collects every call site whose attribute access
ends in ``find_related_code``, and asserts that each is in the
allow-list. Adding a new caller requires either routing it through
the wrapper or appending an explicit justification to
:data:`ALLOWLISTED_CALL_SITES` -- the kind of decision that should
land in code review, not slip through on a trade-name change.

Per Kelly's test architecture review (ADR-090 closeout), this is the
P0 architectural-invariant guard that protects the chokepoint design
from PR-by-PR erosion.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Module paths (relative to repo root) where direct
# ``find_related_code`` calls are intentional and reviewed. New
# entries require a comment explaining why the caller cannot route
# through context_retrieval_service.
ALLOWLISTED_CALL_SITES: dict[str, str] = {
    # The single chokepoint -- every other caller must go through here.
    "src/services/context_retrieval_service.py": (
        "Wrapper that applies the Phase 5.3 ABAC filter."
    ),
    # Provider abstraction layer: implements the GraphDatabase
    # interface and delegates to NeptuneGraphService. Callers reach
    # this only via the abstraction, which itself is wrapped.
    "src/services/providers/aws/neptune_adapter.py": (
        "Provider abstraction; callers route through the abstraction."
    ),
    # Legacy adapter retained until the abstraction migration finishes;
    # documented as a known migration target in the ADR-004 multi-cloud
    # rollout. Tracked for removal once the abstraction owns all reads.
    "src/services/service_adapters.py": (
        "Pre-abstraction adapter; tracked for removal in ADR-004 rollout."
    ),
    # Demo / __main__ block at the bottom of the Neptune service
    # module. Not production code; runs only when the module is
    # executed directly for local development.
    "src/services/neptune_graph_service.py": (
        "Demo/__main__ block; not invoked by the application runtime."
    ),
}

# File patterns that are exempt from the contract entirely.
EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    "tests/",
    "archive/",
    "scripts/",
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def python_source_files() -> list[Path]:
    """All Python source files under ``src/``."""
    src = REPO_ROOT / "src"
    return sorted(src.rglob("*.py"))


def _collect_find_related_code_calls(path: Path) -> list[int]:
    """Return line numbers of every ``*.find_related_code(...)`` call."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    line_numbers: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "find_related_code":
            line_numbers.append(node.lineno)
    return line_numbers


def _relative_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _is_exempt(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)


class TestABACChokepoint:
    def test_no_unallowlisted_caller_invokes_find_related_code(
        self, python_source_files
    ):
        """Every direct caller of ``find_related_code`` must be allow-listed."""
        violations: list[tuple[str, int]] = []
        for path in python_source_files:
            rel_path = _relative_path(path)
            if _is_exempt(rel_path):
                continue
            calls = _collect_find_related_code_calls(path)
            if not calls:
                continue
            if rel_path in ALLOWLISTED_CALL_SITES:
                continue
            violations.extend((rel_path, line) for line in calls)
        if violations:
            formatted = "\n".join(f"  {p}:{ln}" for p, ln in violations)
            pytest.fail(
                "Phase 5.3 ABAC chokepoint violation: direct calls to "
                "find_related_code outside the allow-listed wrappers.\n"
                f"{formatted}\n\n"
                "Either route through "
                "context_retrieval_service._execute_graph_query, "
                "or add the file to "
                "tests/architecture/test_abac_chokepoint.py "
                "ALLOWLISTED_CALL_SITES with a justification."
            )

    def test_allowlist_paths_actually_exist(self, python_source_files):
        """Each allow-list entry must point to a real file with a
        find_related_code call. Stale entries silently weaken the
        contract."""
        existing = {_relative_path(p) for p in python_source_files}
        missing = [
            rel_path for rel_path in ALLOWLISTED_CALL_SITES if rel_path not in existing
        ]
        if missing:
            pytest.fail(
                "Allow-listed paths no longer exist in src/: "
                f"{missing}. Remove them from ALLOWLISTED_CALL_SITES."
            )

    def test_chokepoint_module_actually_imports_filter(self):
        """The wrapper must import apply_phase5_filter so the module-
        level intent stays visible. A grep here protects against the
        wrapper losing the filter call without the contract test
        catching it."""
        wrapper_path = REPO_ROOT / "src/services/context_retrieval_service.py"
        source = wrapper_path.read_text(encoding="utf-8")
        assert "apply_phase5_filter" in source, (
            "context_retrieval_service must import apply_phase5_filter "
            "to enforce the Phase 5.3 chokepoint."
        )
        assert "_clearance_filtered_relationship_types" in source, (
            "context_retrieval_service must define the clearance "
            "filter helper that removes Phase 5 labels from queries."
        )
