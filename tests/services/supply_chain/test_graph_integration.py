"""
Tests for supply chain graph integration service.
"""

from datetime import datetime, timezone

from src.services.supply_chain import (
    Attestation,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    SigningMethod,
    get_supply_chain_graph_service,
    reset_supply_chain_graph_service,
)
from src.services.supply_chain.graph_integration import (
    EdgeLabel,
    GraphMode,
    SupplyChainGraphService,
    VertexLabel,
)


class TestGraphServiceInitialization:
    """Tests for graph service initialization."""

    def test_initialize_mock_mode(self, test_config):
        """Test initializing in mock mode."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)
        assert service.mode == GraphMode.MOCK

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        service1 = get_supply_chain_graph_service()
        service2 = get_supply_chain_graph_service()
        assert service1 is service2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        service1 = get_supply_chain_graph_service()
        reset_supply_chain_graph_service()
        service2 = get_supply_chain_graph_service()
        assert service1 is not service2


class TestSBOMOperations:
    """Tests for SBOM graph operations."""

    def test_store_sbom(self, test_config, sample_sbom):
        """Test storing SBOM in graph."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        vertex_id = service.store_sbom(sample_sbom)

        assert vertex_id == f"sbom:{sample_sbom.sbom_id}"

    def test_store_sbom_creates_vertices(self, test_config, sample_sbom):
        """Test that storing SBOM creates component vertices."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)

        # Check SBOM vertex exists
        sbom_data = service.get_sbom(sample_sbom.sbom_id)
        assert sbom_data is not None
        assert sbom_data["sbom_id"] == sample_sbom.sbom_id
        assert sbom_data["component_count"] == len(sample_sbom.components)

    def test_store_sbom_creates_edges(self, test_config, sample_sbom):
        """Test that storing SBOM creates CONTAINS edges."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)

        # Check edges were created
        contains_edges = [
            e for e in service._mock_edges.values() if e.label == EdgeLabel.CONTAINS
        ]
        assert len(contains_edges) == len(sample_sbom.components)

    def test_get_nonexistent_sbom(self, test_config):
        """Test getting non-existent SBOM."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        sbom_data = service.get_sbom("nonexistent-sbom")

        assert sbom_data is None

    def test_delete_sbom(self, test_config, sample_sbom):
        """Test deleting SBOM."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)
        assert service.get_sbom(sample_sbom.sbom_id) is not None

        result = service.delete_sbom(sample_sbom.sbom_id)

        assert result is True
        assert service.get_sbom(sample_sbom.sbom_id) is None

    def test_delete_nonexistent_sbom(self, test_config):
        """Test deleting non-existent SBOM."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        result = service.delete_sbom("nonexistent")

        assert result is False


class TestAttestationOperations:
    """Tests for attestation graph operations."""

    def test_store_attestation(self, test_config, sample_sbom):
        """Test storing attestation in graph."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        # First store the SBOM
        service.store_sbom(sample_sbom)

        # Create attestation
        attestation = Attestation(
            attestation_id="att-test-001",
            sbom_id=sample_sbom.sbom_id,
            predicate_type="https://in-toto.io/attestation/sbom/v1",
            subject_digest="sha256:abc123",
            signature="mock-signature",
            signing_method=SigningMethod.SIGSTORE_KEYLESS,
            created_at=datetime.now(timezone.utc),
        )

        vertex_id = service.store_attestation(attestation)

        assert vertex_id == f"attestation:{attestation.attestation_id}"

    def test_store_attestation_creates_edge(self, test_config, sample_sbom):
        """Test that storing attestation creates ATTESTED_BY edge."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)
        attestation = Attestation(
            attestation_id="att-test-002",
            sbom_id=sample_sbom.sbom_id,
            predicate_type="test",
            subject_digest="sha256:xyz",
            signature="sig",
            signing_method=SigningMethod.OFFLINE_KEY,
            created_at=datetime.now(timezone.utc),
        )

        service.store_attestation(attestation)

        # Check ATTESTED_BY edge was created
        attested_edges = [
            e for e in service._mock_edges.values() if e.label == EdgeLabel.ATTESTED_BY
        ]
        assert len(attested_edges) == 1

    def test_get_attestations_for_sbom(self, test_config, sample_sbom):
        """Test getting attestations for an SBOM."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)

        # Create multiple attestations
        for i in range(3):
            attestation = Attestation(
                attestation_id=f"att-test-{i}",
                sbom_id=sample_sbom.sbom_id,
                predicate_type="test",
                subject_digest=f"sha256:hash{i}",
                signature=f"sig{i}",
                signing_method=SigningMethod.NONE,
                created_at=datetime.now(timezone.utc),
            )
            service.store_attestation(attestation)

        attestations = service.get_attestations_for_sbom(sample_sbom.sbom_id)

        assert len(attestations) == 3

    def test_link_superseding_attestation(self, test_config, sample_sbom):
        """Test linking superseding attestation."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)

        # Create old and new attestations
        old_att = Attestation(
            attestation_id="att-old",
            sbom_id=sample_sbom.sbom_id,
            predicate_type="test",
            subject_digest="sha256:old",
            signature="old-sig",
            signing_method=SigningMethod.NONE,
            created_at=datetime.now(timezone.utc),
        )
        new_att = Attestation(
            attestation_id="att-new",
            sbom_id=sample_sbom.sbom_id,
            predicate_type="test",
            subject_digest="sha256:new",
            signature="new-sig",
            signing_method=SigningMethod.NONE,
            created_at=datetime.now(timezone.utc),
        )

        service.store_attestation(old_att)
        service.store_attestation(new_att)

        # Link as superseding
        service.link_superseding_attestation("att-new", "att-old")

        # Check SUPERSEDES edge was created
        supersedes_edges = [
            e for e in service._mock_edges.values() if e.label == EdgeLabel.SUPERSEDES
        ]
        assert len(supersedes_edges) == 1


class TestLicenseOperations:
    """Tests for license graph operations."""

    def test_store_component_with_license(self, test_config):
        """Test that storing component creates license vertex and edge."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        sbom = SBOMDocument(
            sbom_id="test-sbom",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(
                    name="mit-package",
                    version="1.0.0",
                    licenses=["MIT"],
                ),
            ],
        )

        service.store_sbom(sbom)

        # Check license vertex exists
        license_vertex = service._mock_vertices.get("license:MIT")
        assert license_vertex is not None
        assert license_vertex.properties["spdx_id"] == "MIT"

        # Check LICENSED_UNDER edge exists
        licensed_edges = [
            e
            for e in service._mock_edges.values()
            if e.label == EdgeLabel.LICENSED_UNDER
        ]
        assert len(licensed_edges) == 1

    def test_get_license_usage(self, test_config):
        """Test getting dependencies using a specific license."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        sbom = SBOMDocument(
            sbom_id="test-sbom",
            name="test",
            version="1.0.0",
            format=SBOMFormat.INTERNAL,
            spec_version="1.0",
            repository_id="repo",
            created_at=datetime.now(timezone.utc),
            components=[
                SBOMComponent(name="pkg1", version="1.0.0", licenses=["MIT"]),
                SBOMComponent(name="pkg2", version="2.0.0", licenses=["MIT"]),
                SBOMComponent(name="pkg3", version="1.0.0", licenses=["Apache-2.0"]),
            ],
        )

        service.store_sbom(sbom)

        mit_deps = service.get_license_usage("MIT")

        assert len(mit_deps) == 2


class TestProvenanceQueries:
    """Tests for provenance chain queries."""

    def test_get_provenance_chain(self, test_config, sample_sbom):
        """Test getting provenance chain for a package."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)
        attestation = Attestation(
            attestation_id="att-prov",
            sbom_id=sample_sbom.sbom_id,
            predicate_type="test",
            subject_digest="sha256:xyz",
            signature="sig",
            signing_method=SigningMethod.SIGSTORE_KEYLESS,
            created_at=datetime.now(timezone.utc),
        )
        service.store_attestation(attestation)

        # Get provenance for first component
        component = sample_sbom.components[0]
        chain = service.get_provenance_chain(component.purl)

        assert chain is not None
        assert chain.package_url == component.purl

    def test_get_provenance_for_unknown_package(self, test_config):
        """Test getting provenance for unknown package."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        chain = service.get_provenance_chain("pkg:pypi/unknown@1.0.0")

        assert chain is None

    def test_provenance_chain_includes_attestations(self, test_config, sample_sbom):
        """Test that provenance chain includes attestation data."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        service.store_sbom(sample_sbom)

        # Create multiple attestations
        for i in range(2):
            attestation = Attestation(
                attestation_id=f"att-chain-{i}",
                sbom_id=sample_sbom.sbom_id,
                predicate_type="test",
                subject_digest=f"sha256:hash{i}",
                signature=f"sig{i}",
                signing_method=SigningMethod.SIGSTORE_KEYLESS,
                created_at=datetime.now(timezone.utc),
            )
            service.store_attestation(attestation)

        component = sample_sbom.components[0]
        chain = service.get_provenance_chain(component.purl)

        assert chain is not None
        assert len(chain.attestations) == 2


class TestVertexLabels:
    """Tests for vertex labels enum."""

    def test_vertex_labels(self):
        """Test vertex label values."""
        assert VertexLabel.SBOM.value == "SBOM"
        assert VertexLabel.ATTESTATION.value == "Attestation"
        assert VertexLabel.LICENSE.value == "License"
        assert VertexLabel.DEPENDENCY.value == "Dependency"


class TestEdgeLabels:
    """Tests for edge labels enum."""

    def test_edge_labels(self):
        """Test edge label values."""
        assert EdgeLabel.ATTESTED_BY.value == "ATTESTED_BY"
        assert EdgeLabel.CONTAINS.value == "CONTAINS"
        assert EdgeLabel.LICENSED_UNDER.value == "LICENSED_UNDER"
        assert EdgeLabel.SUPERSEDES.value == "SUPERSEDES"


class TestServiceCleanup:
    """Tests for service cleanup."""

    def test_close_service(self, test_config):
        """Test closing service."""
        service = SupplyChainGraphService(mode=GraphMode.MOCK)

        # Should not raise
        service.close()

        # Should be safe to call twice
        service.close()


class TestGremlinEscaping:
    """Tests for Gremlin string escaping."""

    def test_escape_quotes(self, test_config):
        """Test escaping quotes in strings."""
        from src.services.supply_chain.graph_integration import escape_gremlin_string

        assert escape_gremlin_string("test'quote") == "test\\'quote"
        assert escape_gremlin_string("double''quote") == "double\\'\\'quote"

    def test_escape_newlines(self, test_config):
        """Test escaping newlines."""
        from src.services.supply_chain.graph_integration import escape_gremlin_string

        assert escape_gremlin_string("line1\nline2") == "line1\\nline2"
        assert escape_gremlin_string("tab\there") == "tab\\there"

    def test_escape_backslashes(self, test_config):
        """Test escaping backslashes."""
        from src.services.supply_chain.graph_integration import escape_gremlin_string

        assert escape_gremlin_string("path\\to\\file") == "path\\\\to\\\\file"
