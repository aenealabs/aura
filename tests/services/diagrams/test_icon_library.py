# Copyright (c) 2025 Aenea Labs. All rights reserved.
"""Unit tests for the diagram icon library."""

import pytest

from src.services.diagrams.icon_library import (
    AURA_CATEGORY_COLORS,
    CloudProvider,
    DiagramIcon,
    IconCategory,
    IconColorMode,
    IconLibrary,
)


class TestDiagramIcon:
    """Tests for DiagramIcon model."""

    def test_icon_creation(self):
        """Test basic icon creation."""
        icon = DiagramIcon(
            id="aws:ec2",
            provider=CloudProvider.AWS,
            category=IconCategory.COMPUTE,
            name="ec2",
            svg_path="icons/aws/compute/ec2.svg",
            display_name="Amazon EC2",
        )
        assert icon.id == "aws:ec2"
        assert icon.name == "ec2"
        assert icon.provider == CloudProvider.AWS
        assert icon.category == IconCategory.COMPUTE

    def test_icon_with_aliases(self):
        """Test icon with aliases."""
        icon = DiagramIcon(
            id="aws:ec2",
            provider=CloudProvider.AWS,
            category=IconCategory.COMPUTE,
            name="ec2",
            svg_path="icons/aws/ec2.svg",
            display_name="Amazon EC2",
            aliases=["vm", "virtual-machine", "instance"],
        )
        assert "vm" in icon.aliases
        assert "instance" in icon.aliases

    def test_icon_with_native_color(self):
        """Test icon with native color."""
        icon = DiagramIcon(
            id="aws:lambda",
            provider=CloudProvider.AWS,
            category=IconCategory.COMPUTE,
            name="lambda",
            svg_path="icons/aws/lambda.svg",
            display_name="AWS Lambda",
            native_color="#FF9900",
        )
        assert icon.native_color == "#FF9900"

    def test_icon_get_color_native_mode(self):
        """Test get_color returns native color in native mode."""
        icon = DiagramIcon(
            id="aws:ec2",
            provider=CloudProvider.AWS,
            category=IconCategory.COMPUTE,
            name="ec2",
            svg_path="icons/aws/ec2.svg",
            display_name="Amazon EC2",
            native_color="#FF9900",
        )
        assert icon.get_color(IconColorMode.NATIVE) == "#FF9900"

    def test_icon_get_color_aura_mode(self):
        """Test get_color returns Aura semantic color in aura mode."""
        icon = DiagramIcon(
            id="aws:ec2",
            provider=CloudProvider.AWS,
            category=IconCategory.COMPUTE,
            name="ec2",
            svg_path="icons/aws/ec2.svg",
            display_name="Amazon EC2",
            native_color="#FF9900",
        )
        aura_color = icon.get_color(IconColorMode.AURA_SEMANTIC)
        assert aura_color == AURA_CATEGORY_COLORS[IconCategory.COMPUTE]


class TestCloudProvider:
    """Tests for CloudProvider enum."""

    def test_all_providers_exist(self):
        """Test all expected cloud providers exist."""
        providers = [
            CloudProvider.AWS,
            CloudProvider.AZURE,
            CloudProvider.GCP,
            CloudProvider.KUBERNETES,
            CloudProvider.GENERIC,
        ]
        for provider in providers:
            assert provider.value is not None

    def test_provider_values(self):
        """Test provider enum values."""
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AZURE.value == "azure"
        assert CloudProvider.GCP.value == "gcp"
        assert CloudProvider.KUBERNETES.value == "kubernetes"
        assert CloudProvider.GENERIC.value == "generic"


class TestIconCategory:
    """Tests for IconCategory enum."""

    def test_core_categories_exist(self):
        """Test core icon categories exist."""
        categories = [
            IconCategory.COMPUTE,
            IconCategory.DATABASE,
            IconCategory.STORAGE,
            IconCategory.NETWORKING,
            IconCategory.SECURITY,
            IconCategory.ANALYTICS,
            IconCategory.ML,
            IconCategory.INTEGRATION,
            IconCategory.MANAGEMENT,
            IconCategory.DEVTOOLS,
            IconCategory.CONTAINERS,
        ]
        for category in categories:
            assert category.value is not None


class TestIconColorMode:
    """Tests for IconColorMode enum."""

    def test_all_color_modes(self):
        """Test all color modes exist."""
        modes = [
            IconColorMode.NATIVE,
            IconColorMode.AURA_SEMANTIC,
            IconColorMode.MONOCHROME,
        ]
        for mode in modes:
            assert mode.value is not None


class TestAuraCategoryColors:
    """Tests for Aura semantic color mapping."""

    def test_core_categories_have_colors(self):
        """Test core categories have assigned colors."""
        required_categories = [
            IconCategory.COMPUTE,
            IconCategory.DATABASE,
            IconCategory.STORAGE,
            IconCategory.NETWORKING,
            IconCategory.SECURITY,
        ]
        for category in required_categories:
            assert category in AURA_CATEGORY_COLORS

    def test_compute_is_blue(self):
        """Test compute category uses blue."""
        assert AURA_CATEGORY_COLORS[IconCategory.COMPUTE] == "#3B82F6"

    def test_database_is_violet(self):
        """Test database category uses violet."""
        assert AURA_CATEGORY_COLORS[IconCategory.DATABASE] == "#8B5CF6"

    def test_storage_is_green(self):
        """Test storage category uses green."""
        assert AURA_CATEGORY_COLORS[IconCategory.STORAGE] == "#10B981"

    def test_security_is_red(self):
        """Test security category uses red."""
        assert AURA_CATEGORY_COLORS[IconCategory.SECURITY] == "#DC2626"


class TestIconLibrary:
    """Tests for IconLibrary class."""

    @pytest.fixture
    def library(self):
        """Create an icon library instance."""
        return IconLibrary()

    def test_library_initialization(self, library):
        """Test library initializes with icons."""
        assert library._icons is not None
        assert len(library._icons) > 0

    def test_library_default_color_mode(self, library):
        """Test library default color mode is native."""
        assert library.color_mode == IconColorMode.NATIVE

    def test_library_set_color_mode(self, library):
        """Test changing color mode."""
        library.set_color_mode(IconColorMode.AURA_SEMANTIC)
        assert library.color_mode == IconColorMode.AURA_SEMANTIC

    # AWS Icon Tests
    def test_get_aws_ec2(self, library):
        """Test retrieving AWS EC2 icon."""
        icon = library.get_icon("aws:ec2")
        assert icon is not None
        assert icon.display_name == "Amazon EC2"
        assert icon.provider == CloudProvider.AWS
        assert icon.category == IconCategory.COMPUTE

    def test_get_aws_lambda(self, library):
        """Test retrieving AWS Lambda icon."""
        icon = library.get_icon("aws:lambda")
        assert icon is not None
        assert icon.display_name == "AWS Lambda"
        assert icon.category == IconCategory.COMPUTE

    def test_get_aws_rds(self, library):
        """Test retrieving AWS RDS icon."""
        icon = library.get_icon("aws:rds")
        assert icon is not None
        assert icon.display_name == "Amazon RDS"
        assert icon.category == IconCategory.DATABASE

    def test_get_aws_s3(self, library):
        """Test retrieving AWS S3 icon."""
        icon = library.get_icon("aws:s3")
        assert icon is not None
        assert icon.display_name == "Amazon S3"
        assert icon.category == IconCategory.STORAGE

    def test_get_aws_vpc(self, library):
        """Test retrieving AWS VPC icon."""
        icon = library.get_icon("aws:vpc")
        assert icon is not None
        assert icon.display_name == "Amazon VPC"
        assert icon.category == IconCategory.NETWORKING

    def test_get_aws_eks(self, library):
        """Test retrieving AWS EKS icon."""
        icon = library.get_icon("aws:eks")
        assert icon is not None
        assert icon.display_name == "Amazon EKS"
        assert icon.category == IconCategory.CONTAINERS

    def test_get_aws_bedrock(self, library):
        """Test retrieving AWS Bedrock icon."""
        icon = library.get_icon("aws:bedrock")
        assert icon is not None
        assert icon.display_name == "Amazon Bedrock"
        assert icon.category == IconCategory.ML

    def test_get_aws_cloudwatch(self, library):
        """Test retrieving AWS CloudWatch icon."""
        icon = library.get_icon("aws:cloudwatch")
        assert icon is not None
        assert icon.display_name == "Amazon CloudWatch"
        assert icon.category == IconCategory.MANAGEMENT

    # Azure Icon Tests
    def test_get_azure_vm(self, library):
        """Test retrieving Azure VM icon."""
        icon = library.get_icon("azure:vm")
        assert icon is not None
        assert icon.display_name == "Azure Virtual Machine"
        assert icon.provider == CloudProvider.AZURE
        assert icon.category == IconCategory.COMPUTE

    def test_get_azure_aks(self, library):
        """Test retrieving Azure AKS icon."""
        icon = library.get_icon("azure:aks")
        assert icon is not None
        assert icon.display_name == "Azure Kubernetes Service"
        assert icon.category == IconCategory.CONTAINERS

    def test_get_azure_cosmos_db(self, library):
        """Test retrieving Azure Cosmos DB icon."""
        icon = library.get_icon("azure:cosmos-db")
        assert icon is not None
        assert icon.display_name == "Azure Cosmos DB"
        assert icon.category == IconCategory.DATABASE

    # GCP Icon Tests
    def test_get_gcp_compute_engine(self, library):
        """Test retrieving GCP Compute Engine icon."""
        icon = library.get_icon("gcp:compute-engine")
        assert icon is not None
        assert icon.display_name == "Google Compute Engine"
        assert icon.provider == CloudProvider.GCP
        assert icon.category == IconCategory.COMPUTE

    def test_get_gcp_gke(self, library):
        """Test retrieving GCP GKE icon."""
        icon = library.get_icon("gcp:gke")
        assert icon is not None
        assert icon.display_name == "Google Kubernetes Engine"
        assert icon.category == IconCategory.CONTAINERS

    # Kubernetes Icon Tests
    def test_get_k8s_pod(self, library):
        """Test retrieving Kubernetes Pod icon."""
        icon = library.get_icon("k8s:pod")
        assert icon is not None
        assert icon.display_name == "Pod"
        assert icon.provider == CloudProvider.KUBERNETES
        assert icon.category == IconCategory.CONTAINERS

    def test_get_k8s_deployment(self, library):
        """Test retrieving Kubernetes Deployment icon."""
        icon = library.get_icon("k8s:deployment")
        assert icon is not None
        assert icon.display_name == "Deployment"

    def test_get_k8s_service(self, library):
        """Test retrieving Kubernetes Service icon."""
        icon = library.get_icon("k8s:service")
        assert icon is not None
        assert icon.display_name == "Service"

    # Generic Icon Tests
    def test_get_generic_user(self, library):
        """Test retrieving generic user icon."""
        icon = library.get_icon("generic:user")
        assert icon is not None
        assert icon.display_name == "User"
        assert icon.provider == CloudProvider.GENERIC

    def test_get_generic_database(self, library):
        """Test retrieving generic database icon."""
        icon = library.get_icon("generic:database")
        assert icon is not None
        assert icon.display_name == "Database"

    def test_get_generic_server(self, library):
        """Test retrieving generic server icon."""
        icon = library.get_icon("generic:server")
        assert icon is not None
        assert icon.display_name == "Server"

    # Lookup Tests
    def test_get_nonexistent_icon(self, library):
        """Test retrieving non-existent icon returns None."""
        icon = library.get_icon("nonexistent:icon")
        assert icon is None

    def test_get_icon_by_alias(self, library):
        """Test retrieving icon by alias works through get_icon."""
        # "vm" should find azure:vm or aws:ec2 (which has "vm" as alias)
        icon = library.get_icon("vm")
        assert icon is not None
        # Should resolve to an icon with "vm" in aliases
        assert "vm" in icon.aliases

    # Search Tests
    def test_search_icons_by_name(self, library):
        """Test searching icons by name."""
        results = library.search_icons("lambda")
        assert len(results) >= 1
        assert any(icon.name == "lambda" for icon in results)

    def test_search_icons_case_insensitive(self, library):
        """Test search is case insensitive."""
        results_lower = library.search_icons("ec2")
        results_upper = library.search_icons("EC2")
        assert len(results_lower) == len(results_upper)

    def test_search_icons_by_display_name(self, library):
        """Test searching returns icons matching display name."""
        results = library.search_icons("Bedrock")
        assert len(results) >= 1
        assert any("Bedrock" in icon.display_name for icon in results)

    def test_search_returns_empty_for_no_match(self, library):
        """Test search returns empty list for no matches."""
        results = library.search_icons("xyznonexistent123")
        assert results == []

    # Filter Tests
    def test_list_icons_by_provider(self, library):
        """Test getting icons filtered by provider."""
        aws_icons = library.list_icons_by_provider(CloudProvider.AWS)
        assert len(aws_icons) > 0
        for icon in aws_icons:
            assert icon.provider == CloudProvider.AWS

    def test_list_icons_by_category(self, library):
        """Test getting icons filtered by category."""
        compute_icons = library.list_icons_by_category(IconCategory.COMPUTE)
        assert len(compute_icons) > 0
        for icon in compute_icons:
            assert icon.category == IconCategory.COMPUTE

    # SVG Content Tests
    def test_get_svg_content_generates_placeholder(self, library):
        """Test getting SVG content generates placeholder for missing files."""
        icon = library.get_icon("aws:ec2")
        svg = library.get_svg_content(icon)
        assert svg is not None
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_get_svg_content_respects_color_mode(self, library):
        """Test SVG content includes color based on mode."""
        library.set_color_mode(IconColorMode.AURA_SEMANTIC)
        icon = library.get_icon("aws:ec2")
        svg = library.get_svg_content(icon, apply_color=True)
        assert svg is not None
        # Placeholder SVG should include the semantic color
        compute_color = AURA_CATEGORY_COLORS[IconCategory.COMPUTE]
        assert compute_color in svg

    # Listing Tests
    def test_list_icons(self, library):
        """Test listing all icons."""
        all_icons = library.list_icons()
        assert len(all_icons) > 50  # Should have many icons

    def test_get_icon_count(self, library):
        """Test getting icon count by provider."""
        counts = library.get_icon_count()
        assert "aws" in counts
        assert "azure" in counts
        assert "gcp" in counts
        assert counts["aws"] > 0


class TestIconLibraryIntegration:
    """Integration tests for icon library with diagram workflow."""

    def test_create_diagram_with_icons(self):
        """Test creating a diagram using icons from library."""
        library = IconLibrary()

        # Get icons for a typical architecture diagram
        ec2 = library.get_icon("aws:ec2")
        rds = library.get_icon("aws:rds")
        s3 = library.get_icon("aws:s3")

        assert ec2 is not None
        assert rds is not None
        assert s3 is not None

        # Verify we can get SVG content for all
        for icon in [ec2, rds, s3]:
            svg = library.get_svg_content(icon)
            assert "<svg" in svg

    def test_mixed_provider_diagram(self):
        """Test diagram with icons from multiple providers."""
        library = IconLibrary()

        icons = [
            library.get_icon("aws:ec2"),
            library.get_icon("azure:vm"),
            library.get_icon("gcp:compute-engine"),
            library.get_icon("k8s:pod"),
        ]

        assert all(icon is not None for icon in icons)

        # Each icon should have a different provider
        providers = {icon.provider for icon in icons}
        assert len(providers) == 4

    def test_semantic_coloring_consistency(self):
        """Test semantic coloring is consistent across providers."""
        library = IconLibrary()
        library.set_color_mode(IconColorMode.AURA_SEMANTIC)

        # All compute icons should have the same color
        ec2 = library.get_icon("aws:ec2")
        azure_vm = library.get_icon("azure:vm")
        gce = library.get_icon("gcp:compute-engine")

        compute_color = AURA_CATEGORY_COLORS[IconCategory.COMPUTE]

        assert ec2.get_color(IconColorMode.AURA_SEMANTIC) == compute_color
        assert azure_vm.get_color(IconColorMode.AURA_SEMANTIC) == compute_color
        assert gce.get_color(IconColorMode.AURA_SEMANTIC) == compute_color
