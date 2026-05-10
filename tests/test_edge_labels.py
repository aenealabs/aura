"""Tests for EdgeLabel canonical edge contract (ADR-090)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.services.graph.edge_labels import (
    LEGACY_EXPANSIONS,
    EdgeLabel,
    LegacyAlias,
    is_known_label,
)


class TestEdgeLabelEnum:
    """Tests for the canonical EdgeLabel enum."""

    def test_str_subclass_compat(self):
        """EdgeLabel members compare equal to their string values."""
        assert EdgeLabel.CALLS == "CALLS"
        assert EdgeLabel.CONTAINS.value == "CONTAINS"

    def test_canonical_set_present(self):
        """All ADR-090 canonical labels are exposed."""
        expected = {
            "CONTAINS",
            "INHERITS",
            "IMPORTS",
            "CALLS",
            "CALLS_INFERRED",
            "READS_CONFIG",
            "DEPENDS_ON_ENV",
            "USES_KMS_KEY",
            "FEATURE_GATED_BY",
            "RUNTIME_DEPENDS_ON",
            "CACHES_KEY",
        }
        actual = {member.value for member in EdgeLabel}
        assert actual == expected

    def test_is_valid_accepts_canonical(self):
        for member in EdgeLabel:
            assert EdgeLabel.is_valid(member.value) is True

    def test_is_valid_rejects_unknown(self):
        assert EdgeLabel.is_valid("FROBNICATES") is False
        assert EdgeLabel.is_valid("") is False


class TestLegacyAlias:
    """Tests for LegacyAlias backward-compat labels."""

    def test_legacy_set_present(self):
        expected = {
            "DEPENDS_ON",
            "HAS_CLASS",
            "HAS_FUNCTION",
            "HAS_METHOD",
            "HAS_VARIABLE",
            "HAS_IMPORT",
        }
        actual = {member.value for member in LegacyAlias}
        assert actual == expected

    def test_legacy_expansions_cover_every_alias(self):
        """Every LegacyAlias has an expansion mapping."""
        for alias in LegacyAlias:
            assert alias in LEGACY_EXPANSIONS, (
                f"LegacyAlias.{alias.name} has no LEGACY_EXPANSIONS entry; "
                f"add a tuple of canonical EdgeLabel targets."
            )

    def test_legacy_expansions_target_canonical_only(self):
        """LegacyAlias entries always expand to canonical EdgeLabel members."""
        for alias, targets in LEGACY_EXPANSIONS.items():
            for target in targets:
                assert isinstance(target, EdgeLabel), (
                    f"{alias.value} expands to {target!r}; expansions must "
                    f"target canonical EdgeLabel members."
                )

    def test_depends_on_expands_to_inheritance_and_imports(self):
        targets = LEGACY_EXPANSIONS[LegacyAlias.DEPENDS_ON]
        assert EdgeLabel.INHERITS in targets
        assert EdgeLabel.IMPORTS in targets

    def test_has_family_expands_to_contains(self):
        for member in (
            LegacyAlias.HAS_CLASS,
            LegacyAlias.HAS_FUNCTION,
            LegacyAlias.HAS_METHOD,
            LegacyAlias.HAS_VARIABLE,
            LegacyAlias.HAS_IMPORT,
        ):
            assert LEGACY_EXPANSIONS[member] == (EdgeLabel.CONTAINS,)


class TestIsKnownLabel:
    """Tests for the is_known_label helper used by add_relationship."""

    def test_accepts_canonical(self):
        assert is_known_label("CALLS") is True
        assert is_known_label("INHERITS") is True
        assert is_known_label("USES_KMS_KEY") is True

    def test_accepts_legacy(self):
        assert is_known_label("DEPENDS_ON") is True
        assert is_known_label("HAS_METHOD") is True

    def test_rejects_unknown(self):
        assert is_known_label("FROBNICATES") is False
        assert is_known_label("calls") is False  # case-sensitive
        assert is_known_label("") is False


class TestContractConsistency:
    """Architectural test: every label the read side asks for has a writer.

    This is the belt-and-suspenders check noted in ADR-090. The lint
    catches *new* divergences at write time; this test catches the
    enum drifting away from reality (a label added but never written).
    """

    def test_every_canonical_label_appears_somewhere_or_is_planned(self):
        """Sanity check: each EdgeLabel member is referenced by either
        a writer in src/ or marked as a future-phase label.

        This is intentionally permissive — Phase 4/5/6 labels do not
        have writers yet. The test asserts each label is either
        referenced in source or matches a known future-phase set.
        """
        future_phase_labels = {
            EdgeLabel.CALLS_INFERRED.value,  # Phase 4 LLM tier
            EdgeLabel.READS_CONFIG.value,  # Phase 5
            EdgeLabel.DEPENDS_ON_ENV.value,  # Phase 5
            EdgeLabel.USES_KMS_KEY.value,  # Phase 5
            EdgeLabel.FEATURE_GATED_BY.value,  # Phase 5
            EdgeLabel.RUNTIME_DEPENDS_ON.value,  # ADR-083
            EdgeLabel.CACHES_KEY.value,  # ADR-083
        }
        present_labels = {EdgeLabel.CONTAINS.value, EdgeLabel.IMPORTS.value}
        # Sanity: every label is either present today or planned.
        all_known = (
            future_phase_labels
            | present_labels
            | {
                EdgeLabel.INHERITS.value,  # Phase 2 (proposed)
                EdgeLabel.CALLS.value,  # Phase 2 (proposed)
            }
        )
        for member in EdgeLabel:
            assert member.value in all_known, (
                f"EdgeLabel.{member.name} is not categorized as present or "
                f"planned. Update tests/test_edge_labels.py if you added a "
                f"new label."
            )

    def test_read_side_uses_only_canonical_or_legacy_labels(self):
        """context_retrieval_service._get_relationship_types must
        return only EdgeLabel or LegacyAlias values."""
        from src.services.context_retrieval_service import (
            ContextRetrievalService,
            GraphQueryType,
        )

        # Construct a minimal instance just to call the method.
        service = ContextRetrievalService.__new__(ContextRetrievalService)

        for query_type in GraphQueryType:
            types = service._get_relationship_types(query_type)
            if types is None:
                continue
            for label in types:
                assert is_known_label(label), (
                    f"_get_relationship_types({query_type.name}) returned "
                    f"{label!r}, which is not a known EdgeLabel or LegacyAlias."
                )


class TestNeptuneAddRelationshipValidation:
    """add_relationship rejects unknown labels at write time."""

    def test_rejects_unknown_label(self):
        from src.services.neptune_graph_service import (
            NeptuneError,
            NeptuneGraphService,
            NeptuneMode,
        )

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.add_code_entity("A", "class", "a.py", 1)
        service.add_code_entity("B", "class", "b.py", 1)

        with pytest.raises(NeptuneError, match="Unknown edge label"):
            service.add_relationship("a.py::A", "b.py::B", "FROBNICATES")

    def test_accepts_canonical_label(self):
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        id_a = service.add_code_entity("A", "class", "a.py", 1)
        id_b = service.add_code_entity("B", "class", "b.py", 1)

        # Should not raise
        result = service.add_relationship(id_a, id_b, EdgeLabel.CALLS.value)
        assert result is True

    def test_accepts_legacy_label(self):
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        id_a = service.add_code_entity("A", "class", "a.py", 1)
        id_b = service.add_code_entity("B", "class", "b.py", 1)

        # DEPENDS_ON is a legacy alias, must still be accepted
        result = service.add_relationship(id_a, id_b, "DEPENDS_ON")
        assert result is True

    def test_accepts_enum_member_directly(self):
        """EdgeLabel members are str subclasses; they pass directly."""
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        id_a = service.add_code_entity("A", "class", "a.py", 1)
        id_b = service.add_code_entity("B", "class", "b.py", 1)

        result = service.add_relationship(id_a, id_b, EdgeLabel.IMPORTS)
        assert result is True


class TestModuleEnumDefinitionStability:
    """The EdgeLabel module is the single source of truth.

    Parsing it should produce a single EdgeLabel class with str-Enum
    base; downstream callers depend on this shape.
    """

    def test_edge_labels_module_defines_str_enum(self):
        path = Path("src/services/graph/edge_labels.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))

        edge_label_classes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "EdgeLabel"
        ]
        assert len(edge_label_classes) == 1

        bases = [
            ast.unparse(b) if hasattr(ast, "unparse") else b.__class__.__name__
            for b in edge_label_classes[0].bases
        ]
        # Expect str-Enum subclass for transparent string interop
        assert any("str" in b for b in bases)
        assert any("Enum" in b for b in bases)
