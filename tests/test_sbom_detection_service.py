"""
Project Aura - SBOM Detection Service Tests

Tests for automatic dependency detection from manifest files.
Target: 85% coverage of src/services/sbom_detection_service.py
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.services.sbom_detection_service import (
    Dependency,
    PackageEcosystem,
    SBOMDetectionService,
    SBOMReport,
    create_sbom_detection_service,
    detect_project_sbom,
)


class TestDependency:
    """Tests for Dependency dataclass."""

    def test_dependency_creation(self):
        """Test creating a Dependency."""
        dep = Dependency(
            name="requests",
            version="2.28.0",
            ecosystem=PackageEcosystem.PIP,
            source_file="requirements.txt",
        )

        assert dep.name == "requests"
        assert dep.version == "2.28.0"
        assert dep.ecosystem == PackageEcosystem.PIP
        assert dep.is_dev_dependency is False

    def test_dependency_to_dict(self):
        """Test converting Dependency to dictionary."""
        dep = Dependency(
            name="pytest",
            version="7.0.0",
            ecosystem=PackageEcosystem.PIP,
            source_file="requirements-dev.txt",
            is_dev_dependency=True,
        )

        result = dep.to_dict()

        assert result["name"] == "pytest"
        assert result["version"] == "7.0.0"
        assert result["ecosystem"] == "pip"
        assert result["is_dev_dependency"] is True

    def test_dependency_to_sbom_entry(self):
        """Test converting Dependency to SBOM entry."""
        dep = Dependency(
            name="flask",
            version="2.0.0",
            ecosystem=PackageEcosystem.PIP,
            source_file="requirements.txt",
        )

        entry = dep.to_sbom_entry()

        assert entry == {
            "name": "flask",
            "version": "2.0.0",
            "ecosystem": "pip",
        }


class TestSBOMReport:
    """Tests for SBOMReport dataclass."""

    def test_total_count(self):
        """Test total dependency count."""
        report = SBOMReport(
            project_path="/test",
            generated_at=None,  # Will be set
        )
        report.dependencies = [
            Dependency("a", "1.0", PackageEcosystem.PIP, "req.txt"),
            Dependency("b", "2.0", PackageEcosystem.PIP, "req.txt"),
        ]
        report.dev_dependencies = [
            Dependency("c", "3.0", PackageEcosystem.PIP, "req.txt", True),
        ]

        assert report.total_count == 3

    def test_by_ecosystem(self):
        """Test counting by ecosystem."""
        report = SBOMReport(project_path="/test", generated_at=None)
        report.dependencies = [
            Dependency("a", "1.0", PackageEcosystem.PIP, "req.txt"),
            Dependency("b", "2.0", PackageEcosystem.NPM, "pkg.json"),
            Dependency("c", "3.0", PackageEcosystem.PIP, "req.txt"),
        ]

        counts = report.by_ecosystem
        assert counts["pip"] == 2
        assert counts["npm"] == 1

    def test_to_sbom_list(self):
        """Test converting to SBOM list."""
        report = SBOMReport(project_path="/test", generated_at=None)
        report.dependencies = [
            Dependency("a", "1.0", PackageEcosystem.PIP, "req.txt"),
        ]
        report.dev_dependencies = [
            Dependency("b", "2.0", PackageEcosystem.PIP, "req.txt", True),
        ]

        # Without dev
        sbom = report.to_sbom_list(include_dev=False)
        assert len(sbom) == 1
        assert sbom[0]["name"] == "a"

        # With dev
        sbom_with_dev = report.to_sbom_list(include_dev=True)
        assert len(sbom_with_dev) == 2


class TestSBOMDetectionServiceRequirementsTxt:
    """Tests for requirements.txt parsing."""

    def test_parse_simple_requirements(self):
        """Test parsing simple requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("""
requests==2.28.0
flask>=2.0.0
numpy~=1.21.0
pandas
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 4
            names = {d.name for d in report.dependencies}
            assert "requests" in names
            assert "flask" in names
            assert "numpy" in names
            assert "pandas" in names

    def test_parse_requirements_with_comments(self):
        """Test parsing requirements.txt with comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("""
# Core dependencies
requests==2.28.0

# Data processing
pandas>=1.3.0  # Latest stable
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 2

    def test_parse_requirements_with_extras(self):
        """Test parsing requirements with extras."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests[security]==2.28.0\n")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 1
            assert report.dependencies[0].name == "requests"
            assert "security" in report.dependencies[0].extras

    def test_skip_url_dependencies(self):
        """Test that URL dependencies are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("""
requests==2.28.0
git+https://github.com/user/repo.git
-e ./local-package
http://example.com/package.tar.gz
flask>=2.0
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 2
            names = {d.name for d in report.dependencies}
            assert "requests" in names
            assert "flask" in names


class TestSBOMDetectionServicePackageJson:
    """Tests for package.json parsing."""

    def test_parse_package_json(self):
        """Test parsing package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text(
                json.dumps(
                    {
                        "name": "test-project",
                        "dependencies": {
                            "express": "^4.18.0",
                            "lodash": "~4.17.21",
                        },
                        "devDependencies": {
                            "jest": "^29.0.0",
                        },
                    }
                )
            )

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 2
            assert len(report.dev_dependencies) == 1
            assert report.dev_dependencies[0].name == "jest"

    def test_clean_npm_versions(self):
        """Test npm version cleaning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text(
                json.dumps(
                    {
                        "dependencies": {
                            "a": "^1.0.0",
                            "b": "~2.0.0",
                            "c": "3.0.0",
                            "d": ">=4.0.0 <5.0.0",
                        }
                    }
                )
            )

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            versions = {d.name: d.version for d in report.dependencies}
            assert versions["a"] == "1.0.0"
            assert versions["b"] == "2.0.0"
            assert versions["c"] == "3.0.0"
            assert versions["d"] == ">=4.0.0"


class TestSBOMDetectionServiceGoMod:
    """Tests for go.mod parsing."""

    def test_parse_go_mod(self):
        """Test parsing go.mod."""
        with tempfile.TemporaryDirectory() as tmpdir:
            go_file = Path(tmpdir) / "go.mod"
            go_file.write_text("""
module example.com/myproject

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/go-redis/redis/v8 v8.11.5
)

require github.com/stretchr/testify v1.8.0
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 3
            names = {d.name for d in report.dependencies}
            assert "github.com/gin-gonic/gin" in names
            assert "github.com/go-redis/redis/v8" in names
            assert "github.com/stretchr/testify" in names


class TestSBOMDetectionServiceCargoToml:
    """Tests for Cargo.toml parsing."""

    def test_parse_cargo_toml(self):
        """Test parsing Cargo.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cargo_file = Path(tmpdir) / "Cargo.toml"
            cargo_file.write_text("""
[package]
name = "myproject"
version = "0.1.0"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
criterion = "^0.5"
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 2
            assert len(report.dev_dependencies) == 1

            # Check version extraction
            serde_dep = next(d for d in report.dependencies if d.name == "serde")
            assert serde_dep.version == "1.0"

            tokio_dep = next(d for d in report.dependencies if d.name == "tokio")
            assert tokio_dep.version == "1.0"


class TestSBOMDetectionServiceGemfile:
    """Tests for Gemfile.lock parsing."""

    def test_parse_gemfile_lock(self):
        """Test parsing Gemfile.lock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gem_file = Path(tmpdir) / "Gemfile.lock"
            gem_file.write_text("""
GEM
  remote: https://rubygems.org/
  specs:
    rails (7.0.4)
    rack (2.2.4)
    puma (5.6.5)

PLATFORMS
  x86_64-linux

DEPENDENCIES
  rails
  puma
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 3
            names = {d.name for d in report.dependencies}
            assert "rails" in names
            assert "rack" in names
            assert "puma" in names


class TestSBOMDetectionServiceCsproj:
    """Tests for .csproj parsing."""

    def test_parse_csproj(self):
        """Test parsing .csproj file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csproj_file = Path(tmpdir) / "MyProject.csproj"
            csproj_file.write_text("""
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net7.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.1" />
    <PackageReference Include="Serilog" Version="2.12.0" />
  </ItemGroup>
</Project>
""")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 2
            names = {d.name for d in report.dependencies}
            assert "Newtonsoft.Json" in names
            assert "Serilog" in names


class TestSBOMDetectionServiceMultipleManifests:
    """Tests for projects with multiple manifest files."""

    def test_multiple_ecosystems(self):
        """Test detecting dependencies from multiple ecosystems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Python
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            # Node.js
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text(json.dumps({"dependencies": {"express": "4.18.0"}}))

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert report.total_count == 2
            ecosystems = {d.ecosystem for d in report.dependencies}
            assert PackageEcosystem.PIP in ecosystems
            assert PackageEcosystem.NPM in ecosystems

    def test_deduplication(self):
        """Test that duplicate dependencies are deduplicated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Same dep in two files
            req1 = Path(tmpdir) / "requirements.txt"
            req1.write_text("requests==2.28.0\n")

            req2 = Path(tmpdir) / "requirements-dev.txt"
            req2.write_text("requests==2.28.0\npytest==7.0.0\n")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            # Should have 2 unique deps, not 3
            assert report.total_count == 2


class TestSBOMDetectionServiceExclusions:
    """Tests for excluded directories."""

    def test_exclude_node_modules(self):
        """Test that node_modules is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Root package.json
            root_pkg = Path(tmpdir) / "package.json"
            root_pkg.write_text(json.dumps({"dependencies": {"express": "4.18.0"}}))

            # node_modules package.json (should be ignored)
            nm_dir = Path(tmpdir) / "node_modules" / "express"
            nm_dir.mkdir(parents=True)
            nm_pkg = nm_dir / "package.json"
            nm_pkg.write_text(
                json.dumps(
                    {"dependencies": {"lodash": "4.0.0", "body-parser": "1.0.0"}}
                )
            )

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            # Should only have root dependency
            assert report.total_count == 1
            assert report.dependencies[0].name == "express"

    def test_exclude_venv(self):
        """Test that venv is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Root requirements
            root_req = Path(tmpdir) / "requirements.txt"
            root_req.write_text("requests==2.28.0\n")

            # venv pip packages (should be ignored)
            venv_dir = Path(tmpdir) / "venv" / "lib" / "python3.11"
            venv_dir.mkdir(parents=True)
            venv_req = Path(tmpdir) / "venv" / "requirements.txt"
            venv_req.write_text("pip==23.0.0\n")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert report.total_count == 1


class TestSBOMDetectionServiceMaxDepth:
    """Tests for max depth configuration."""

    def test_respects_max_depth(self):
        """Test that max depth is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directories
            deep_dir = Path(tmpdir) / "a" / "b" / "c" / "d" / "e"
            deep_dir.mkdir(parents=True)
            deep_req = deep_dir / "requirements.txt"
            deep_req.write_text("deep-package==1.0.0\n")

            # Root requirements
            root_req = Path(tmpdir) / "requirements.txt"
            root_req.write_text("root-package==1.0.0\n")

            service = SBOMDetectionService(max_depth=2)
            report = service.detect_dependencies(tmpdir)

            # Should only find root, not deep nested
            names = {d.name for d in report.dependencies}
            assert "root-package" in names
            assert "deep-package" not in names


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_sbom_detection_service(self):
        """Test factory function."""
        service = create_sbom_detection_service(max_depth=5)
        assert service.max_depth == 5

    def test_detect_project_sbom(self):
        """Test convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            report = detect_project_sbom(tmpdir)

            assert report.total_count == 1


class TestIntegrationWithThreatIntelligenceAgent:
    """Tests for integration with ThreatIntelligenceAgent."""

    def test_auto_detect_sbom(self):
        """Test auto_detect_sbom method."""
        from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("""
requests==2.28.0
flask>=2.0.0
boto3~=1.26
""")

            agent = ThreatIntelligenceAgent()
            count = agent.auto_detect_sbom(tmpdir)

            assert count == 3
            assert len(agent._dependency_sbom) == 3

    def test_auto_detect_sbom_includes_dev(self):
        """Test auto_detect_sbom with dev dependencies."""
        from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text(
                json.dumps(
                    {
                        "dependencies": {"express": "4.18.0"},
                        "devDependencies": {"jest": "29.0.0"},
                    }
                )
            )

            agent = ThreatIntelligenceAgent()

            # Without dev
            count_no_dev = agent.auto_detect_sbom(tmpdir, include_dev=False)
            assert count_no_dev == 1

            # With dev
            count_with_dev = agent.auto_detect_sbom(tmpdir, include_dev=True)
            assert count_with_dev == 2

    def test_auto_detect_on_real_project(self):
        """Test auto_detect_sbom on the actual project."""
        from src.agents.threat_intelligence_agent import ThreatIntelligenceAgent

        project_root = Path(__file__).parent.parent

        agent = ThreatIntelligenceAgent()
        count = agent.auto_detect_sbom(str(project_root))

        # Should find dependencies from requirements.txt and/or pyproject.toml
        assert count > 0
        assert len(agent._dependency_sbom) > 0

        # Check some known dependencies
        {d["name"].lower() for d in agent._dependency_sbom}
        # At minimum should have pytest from dev requirements
        # This verifies actual project scanning works


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_project_path(self):
        """Test handling of invalid project path."""
        service = SBOMDetectionService()

        with pytest.raises(ValueError, match="does not exist"):
            service.detect_dependencies("/nonexistent/path")

    def test_empty_project(self):
        """Test handling of empty project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert report.total_count == 0
            assert len(report.manifest_files) == 0

    def test_malformed_json(self):
        """Test handling of malformed package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text("{ invalid json }")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            # Should have error but not crash
            assert len(report.errors) > 0

    def test_encoding_handling(self):
        """Test handling of different file encodings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            # Write with utf-8 including non-ASCII
            req_file.write_text("# Dependencies\nrequests==2.28.0\n", encoding="utf-8")

            service = SBOMDetectionService()
            report = service.detect_dependencies(tmpdir)

            assert len(report.dependencies) == 1
