"""
Project Aura - Software Bill of Materials (SBOM) Detection Service

Automatically detects project dependencies from common package manifest files:
- requirements.txt, setup.py, pyproject.toml (Python)
- package.json, package-lock.json (Node.js/npm)
- go.mod, go.sum (Go)
- Cargo.toml, Cargo.lock (Rust)
- Gemfile, Gemfile.lock (Ruby)
- *.csproj, packages.config (NuGet/.NET)

This service integrates with ThreatIntelligenceAgent to automatically match
CVE/advisory vulnerabilities against the project's actual dependencies.

Compliance:
- CMMC Level 3: CM-8 (Information System Component Inventory)
- NIST 800-53: CM-8, SA-10 (Developer Configuration Management)
- Executive Order 14028: Software Bill of Materials requirements
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


class PackageEcosystem(Enum):
    """Package ecosystem identifiers (aligned with GitHub Advisory)."""

    PIP = "pip"  # Python (PyPI)
    NPM = "npm"  # Node.js
    GO = "go"  # Go modules
    CARGO = "cargo"  # Rust (crates.io)
    RUBYGEMS = "rubygems"  # Ruby
    NUGET = "nuget"  # .NET
    MAVEN = "maven"  # Java
    COMPOSER = "composer"  # PHP
    UNKNOWN = "unknown"


@dataclass
class Dependency:
    """Represents a project dependency."""

    name: str
    version: str
    ecosystem: PackageEcosystem
    source_file: str
    is_dev_dependency: bool = False
    extras: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "ecosystem": self.ecosystem.value,
            "source_file": self.source_file,
            "is_dev_dependency": self.is_dev_dependency,
        }

    def to_sbom_entry(self) -> dict[str, str]:
        """Convert to SBOM entry format for ThreatIntelligenceAgent."""
        return {
            "name": self.name,
            "version": self.version,
            "ecosystem": self.ecosystem.value,
        }


@dataclass
class SBOMReport:
    """Complete SBOM report for a project."""

    project_path: str
    generated_at: datetime
    dependencies: list[Dependency] = field(default_factory=list)
    dev_dependencies: list[Dependency] = field(default_factory=list)
    manifest_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """Total number of dependencies."""
        return len(self.dependencies) + len(self.dev_dependencies)

    @property
    def by_ecosystem(self) -> dict[str, int]:
        """Count dependencies by ecosystem."""
        counts: dict[str, int] = {}
        for dep in self.dependencies + self.dev_dependencies:
            eco = dep.ecosystem.value
            counts[eco] = counts.get(eco, 0) + 1
        return counts

    def to_sbom_list(self, include_dev: bool = False) -> list[dict[str, str]]:
        """Convert to SBOM list format for ThreatIntelligenceAgent."""
        deps = list(self.dependencies)
        if include_dev:
            deps.extend(self.dev_dependencies)
        return [d.to_sbom_entry() for d in deps]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "project_path": self.project_path,
            "generated_at": self.generated_at.isoformat(),
            "total_dependencies": self.total_count,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "dev_dependencies": [d.to_dict() for d in self.dev_dependencies],
            "manifest_files": self.manifest_files,
            "by_ecosystem": self.by_ecosystem,
            "errors": self.errors,
        }


class SBOMDetectionService:
    """
    Detects and parses project dependencies from manifest files.

    Supports multiple package ecosystems and formats:
    - Python: requirements.txt, setup.py, pyproject.toml
    - Node.js: package.json, package-lock.json
    - Go: go.mod
    - Rust: Cargo.toml
    - Ruby: Gemfile.lock
    - .NET: *.csproj, packages.config

    Usage:
        service = SBOMDetectionService()
        report = service.detect_dependencies("/path/to/project")

        # Get SBOM for threat matching
        sbom = report.to_sbom_list()

        # Integrate with ThreatIntelligenceAgent
        agent.set_dependency_sbom(sbom)
    """

    # Manifest file patterns to search for
    MANIFEST_PATTERNS = [
        "requirements.txt",
        "requirements-*.txt",
        "requirements/*.txt",
        "setup.py",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "go.mod",
        "Cargo.toml",
        "Cargo.lock",
        "Gemfile",
        "Gemfile.lock",
        "*.csproj",
        "packages.config",
    ]

    def __init__(self, max_depth: int = 3) -> None:
        """Initialize SBOM detection service.

        Args:
            max_depth: Maximum directory depth to search for manifests
        """
        self.max_depth = max_depth
        self._seen_dependencies: set[str] = set()

    def detect_dependencies(
        self,
        project_path: str | Path,
        include_dev: bool = True,
    ) -> SBOMReport:
        """Detect all dependencies in a project.

        Args:
            project_path: Path to project root directory
            include_dev: Include dev dependencies in scan

        Returns:
            SBOMReport with all detected dependencies
        """
        project_path = Path(project_path)
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        report = SBOMReport(
            project_path=str(project_path),
            generated_at=datetime.now(timezone.utc),
        )
        self._seen_dependencies.clear()

        # Find all manifest files
        manifest_files = self._find_manifest_files(project_path)
        report.manifest_files = [
            str(f.relative_to(project_path)) for f in manifest_files
        ]

        logger.info(f"Found {len(manifest_files)} manifest files in {project_path}")

        # Parse each manifest file
        for manifest in manifest_files:
            try:
                deps, dev_deps = self._parse_manifest(manifest, include_dev)

                # Deduplicate
                for dep in deps:
                    key = f"{dep.ecosystem.value}:{dep.name}:{dep.version}"
                    if key not in self._seen_dependencies:
                        self._seen_dependencies.add(key)
                        report.dependencies.append(dep)

                for dep in dev_deps:
                    key = f"{dep.ecosystem.value}:{dep.name}:{dep.version}"
                    if key not in self._seen_dependencies:
                        self._seen_dependencies.add(key)
                        report.dev_dependencies.append(dep)

            except Exception as e:
                error_msg = f"Error parsing {manifest}: {e}"
                logger.warning(error_msg)
                report.errors.append(error_msg)

        logger.info(
            f"Detected {report.total_count} dependencies "
            f"({len(report.dependencies)} prod, {len(report.dev_dependencies)} dev)"
        )

        return report

    def _find_manifest_files(self, project_path: Path) -> list[Path]:
        """Find all manifest files in the project.

        Args:
            project_path: Project root directory

        Returns:
            List of manifest file paths
        """
        manifests: list[Path] = []

        # Check each pattern
        for pattern in self.MANIFEST_PATTERNS:
            # Handle glob patterns
            if "*" in pattern:
                for match in project_path.rglob(pattern):
                    if self._is_within_depth(match, project_path):
                        if not self._is_excluded_path(match):
                            manifests.append(match)
            else:
                # Direct file check
                file_path = project_path / pattern
                if file_path.exists():
                    manifests.append(file_path)

                # Also check subdirectories up to max_depth
                for match in project_path.rglob(pattern):
                    if self._is_within_depth(match, project_path):
                        if not self._is_excluded_path(match):
                            if match not in manifests:
                                manifests.append(match)

        return sorted(set(manifests))

    def _is_within_depth(self, path: Path, root: Path) -> bool:
        """Check if path is within max depth from root."""
        try:
            rel_path = path.relative_to(root)
            return len(rel_path.parts) <= self.max_depth + 1
        except ValueError:
            return False

    def _is_excluded_path(self, path: Path) -> bool:
        """Check if path should be excluded (node_modules, venv, etc.)."""
        excluded_dirs = {
            "node_modules",
            ".venv",
            "venv",
            ".git",
            "__pycache__",
            ".tox",
            "build",
            "dist",
            ".eggs",
            "target",  # Rust
            "vendor",  # Go
        }
        return any(part in excluded_dirs for part in path.parts)

    def _parse_manifest(
        self,
        manifest_path: Path,
        include_dev: bool,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse a manifest file and extract dependencies.

        Args:
            manifest_path: Path to manifest file
            include_dev: Include dev dependencies

        Returns:
            Tuple of (production deps, dev deps)
        """
        filename = manifest_path.name.lower()
        source_file = str(manifest_path)

        if filename == "requirements.txt" or filename.startswith("requirements"):
            return self._parse_requirements_txt(manifest_path, source_file)

        elif filename == "pyproject.toml":
            return self._parse_pyproject_toml(manifest_path, source_file, include_dev)

        elif filename == "package.json":
            return self._parse_package_json(manifest_path, source_file, include_dev)

        elif filename == "package-lock.json":
            return self._parse_package_lock_json(manifest_path, source_file)

        elif filename == "go.mod":
            return self._parse_go_mod(manifest_path, source_file)

        elif filename == "cargo.toml":
            return self._parse_cargo_toml(manifest_path, source_file, include_dev)

        elif filename == "gemfile.lock":
            return self._parse_gemfile_lock(manifest_path, source_file)

        elif filename.endswith(".csproj"):
            return self._parse_csproj(manifest_path, source_file)

        else:
            logger.debug(f"Skipping unsupported manifest: {filename}")
            return [], []

    def _parse_requirements_txt(
        self,
        path: Path,
        source_file: str,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse requirements.txt file."""
        deps: list[Dependency] = []

        # Regex for requirement lines
        # Matches: package==1.0.0, package>=1.0, package~=1.0, package[extra]==1.0
        req_pattern = re.compile(r"^([a-zA-Z0-9_-]+)(?:\[([^\]]+)\])?([<>=!~]+)?(.+)?$")

        content = path.read_text(encoding="utf-8", errors="ignore")

        for line in content.splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Skip URLs and editable installs
            if line.startswith("http") or line.startswith("git+"):
                continue

            match = req_pattern.match(line)
            if match:
                name = match.group(1)
                extras = match.group(2).split(",") if match.group(2) else []
                _operator = match.group(3) or ""  # noqa: F841
                version = match.group(4) or "*"

                # Clean version
                version = version.strip().split(",")[0].strip()
                if not version:
                    version = "*"

                deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem=PackageEcosystem.PIP,
                        source_file=source_file,
                        extras=extras,
                    )
                )

        return deps, []

    def _parse_pyproject_toml(
        self,
        path: Path,
        source_file: str,
        include_dev: bool,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse pyproject.toml file."""
        deps: list[Dependency] = []
        dev_deps: list[Dependency] = []

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                logger.warning("tomllib/tomli not available, skipping pyproject.toml")
                return [], []

        content = path.read_text(encoding="utf-8")
        try:
            data = tomllib.loads(content)
        except Exception as e:
            logger.warning(f"Failed to parse pyproject.toml: {e}")
            return [], []

        # PEP 621 dependencies
        project = data.get("project", {})
        for dep_str in project.get("dependencies", []):
            dep = self._parse_pep508_dependency(dep_str, source_file)
            if dep:
                deps.append(dep)

        # Optional dependencies (often includes dev deps)
        if include_dev:
            optional = project.get("optional-dependencies", {})
            for group, group_deps in optional.items():
                is_dev = group.lower() in ("dev", "test", "testing", "development")
                for dep_str in group_deps:
                    dep = self._parse_pep508_dependency(dep_str, source_file)
                    if dep:
                        dep.is_dev_dependency = is_dev
                        if is_dev:
                            dev_deps.append(dep)
                        else:
                            deps.append(dep)

        # Poetry dependencies
        poetry = data.get("tool", {}).get("poetry", {})
        for name, spec in poetry.get("dependencies", {}).items():
            if name.lower() == "python":
                continue
            version = self._extract_poetry_version(spec)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=PackageEcosystem.PIP,
                    source_file=source_file,
                )
            )

        if include_dev:
            for name, spec in poetry.get("dev-dependencies", {}).items():
                version = self._extract_poetry_version(spec)
                dev_deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem=PackageEcosystem.PIP,
                        source_file=source_file,
                        is_dev_dependency=True,
                    )
                )

        return deps, dev_deps

    def _parse_pep508_dependency(
        self,
        dep_str: str,
        source_file: str,
    ) -> Dependency | None:
        """Parse a PEP 508 dependency string."""
        # Basic pattern: name[extras]>=version
        pattern = re.compile(
            r"^([a-zA-Z0-9_-]+)(?:\[([^\]]+)\])?\s*([<>=!~]+)?\s*(.+)?$"
        )
        match = pattern.match(dep_str.strip())
        if match:
            name = match.group(1)
            extras = match.group(2).split(",") if match.group(2) else []
            version = match.group(4) or "*"
            version = version.split(",")[0].strip().split(";")[0].strip()

            return Dependency(
                name=name,
                version=version or "*",
                ecosystem=PackageEcosystem.PIP,
                source_file=source_file,
                extras=extras,
            )
        return None

    def _extract_poetry_version(self, spec: Any) -> str:
        """Extract version from Poetry dependency spec."""
        if isinstance(spec, str):
            return spec
        elif isinstance(spec, dict):
            return cast(str, spec.get("version", "*"))
        return "*"

    def _parse_package_json(
        self,
        path: Path,
        source_file: str,
        include_dev: bool,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse package.json file."""
        deps: list[Dependency] = []
        dev_deps: list[Dependency] = []

        content = path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse package.json: {e}")
            raise  # Re-raise to be caught by detect_dependencies

        # Production dependencies
        for name, version in data.get("dependencies", {}).items():
            deps.append(
                Dependency(
                    name=name,
                    version=self._clean_npm_version(version),
                    ecosystem=PackageEcosystem.NPM,
                    source_file=source_file,
                )
            )

        # Dev dependencies
        if include_dev:
            for name, version in data.get("devDependencies", {}).items():
                dev_deps.append(
                    Dependency(
                        name=name,
                        version=self._clean_npm_version(version),
                        ecosystem=PackageEcosystem.NPM,
                        source_file=source_file,
                        is_dev_dependency=True,
                    )
                )

        return deps, dev_deps

    def _clean_npm_version(self, version: str) -> str:
        """Clean npm version string."""
        # Remove ^ and ~ prefixes
        version = version.lstrip("^~")
        # Handle ranges
        if " " in version or "||" in version:
            version = version.split()[0].split("||")[0].strip()
        return version or "*"

    def _parse_package_lock_json(
        self,
        path: Path,
        source_file: str,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse package-lock.json file (v2/v3 format)."""
        deps: list[Dependency] = []

        content = path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse package-lock.json: {e}")
            raise  # Re-raise to be caught by detect_dependencies

        # v2/v3 format uses "packages"
        packages = data.get("packages", {})
        for pkg_path, pkg_info in packages.items():
            if not pkg_path:  # Skip root package
                continue

            # Extract package name from path
            name = pkg_path.replace("node_modules/", "").split("/")[-1]
            if name.startswith("@"):
                # Scoped package
                parts = pkg_path.replace("node_modules/", "").split("/")
                name = "/".join(parts[-2:])

            version = pkg_info.get("version", "*")
            is_dev = pkg_info.get("dev", False)

            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=PackageEcosystem.NPM,
                    source_file=source_file,
                    is_dev_dependency=is_dev,
                )
            )

        return deps, []

    def _parse_go_mod(
        self,
        path: Path,
        source_file: str,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse go.mod file."""
        deps: list[Dependency] = []
        seen: set[str] = set()

        content = path.read_text(encoding="utf-8")

        # Match require blocks
        require_pattern = re.compile(r"require\s*\((.*?)\)", re.DOTALL)
        # Single line require: require github.com/user/pkg v1.0.0
        single_require = re.compile(r"^require\s+(\S+)\s+(v?\S+)\s*$", re.MULTILINE)

        # Parse require blocks
        for block in require_pattern.findall(content):
            for line in block.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("//"):
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        # Skip indirect dependencies marker
                        if name.startswith("//"):
                            continue
                        version = parts[1].lstrip("v")
                        if name not in seen:
                            seen.add(name)
                            deps.append(
                                Dependency(
                                    name=name,
                                    version=version,
                                    ecosystem=PackageEcosystem.GO,
                                    source_file=source_file,
                                )
                            )

        # Parse single-line requires (not inside a block)
        for match in single_require.finditer(content):
            name = match.group(1)
            # Skip if it's a parenthesis (start of a block)
            if name == "(":
                continue
            version = match.group(2).lstrip("v")
            if name not in seen:
                seen.add(name)
                deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem=PackageEcosystem.GO,
                        source_file=source_file,
                    )
                )

        return deps, []

    def _parse_cargo_toml(
        self,
        path: Path,
        source_file: str,
        include_dev: bool,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse Cargo.toml file."""
        deps: list[Dependency] = []
        dev_deps: list[Dependency] = []

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                logger.warning("tomllib/tomli not available, skipping Cargo.toml")
                return [], []

        content = path.read_text(encoding="utf-8")
        try:
            data = tomllib.loads(content)
        except Exception as e:
            logger.warning(f"Failed to parse Cargo.toml: {e}")
            return [], []

        # Production dependencies
        for name, spec in data.get("dependencies", {}).items():
            version = self._extract_cargo_version(spec)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=PackageEcosystem.CARGO,
                    source_file=source_file,
                )
            )

        # Dev dependencies
        if include_dev:
            for name, spec in data.get("dev-dependencies", {}).items():
                version = self._extract_cargo_version(spec)
                dev_deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem=PackageEcosystem.CARGO,
                        source_file=source_file,
                        is_dev_dependency=True,
                    )
                )

        return deps, dev_deps

    def _extract_cargo_version(self, spec: Any) -> str:
        """Extract version from Cargo dependency spec."""
        if isinstance(spec, str):
            return spec.lstrip("^~")
        elif isinstance(spec, dict):
            return cast(str, spec.get("version", "*")).lstrip("^~")
        return "*"

    def _parse_gemfile_lock(
        self,
        path: Path,
        source_file: str,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse Gemfile.lock file."""
        deps: list[Dependency] = []

        content = path.read_text(encoding="utf-8")

        # Parse GEM section
        in_specs = False
        gem_pattern = re.compile(r"^\s{4}(\S+)\s+\((.+)\)$")

        for line in content.splitlines():
            if line.strip() == "specs:":
                in_specs = True
                continue
            elif line.strip() == "" and in_specs:
                in_specs = False
                continue

            if in_specs:
                match = gem_pattern.match(line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    deps.append(
                        Dependency(
                            name=name,
                            version=version,
                            ecosystem=PackageEcosystem.RUBYGEMS,
                            source_file=source_file,
                        )
                    )

        return deps, []

    def _parse_csproj(
        self,
        path: Path,
        source_file: str,
    ) -> tuple[list[Dependency], list[Dependency]]:
        """Parse .csproj file for NuGet packages."""
        deps: list[Dependency] = []

        content = path.read_text(encoding="utf-8")

        # Match PackageReference elements
        pattern = re.compile(
            r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"',
            re.IGNORECASE,
        )

        for match in pattern.finditer(content):
            name = match.group(1)
            version = match.group(2)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=PackageEcosystem.NUGET,
                    source_file=source_file,
                )
            )

        return deps, []


def create_sbom_detection_service(max_depth: int = 3) -> SBOMDetectionService:
    """Factory function to create an SBOM detection service.

    Args:
        max_depth: Maximum directory depth to search

    Returns:
        Configured SBOMDetectionService instance
    """
    return SBOMDetectionService(max_depth=max_depth)


def detect_project_sbom(project_path: str | Path) -> SBOMReport:
    """Convenience function to detect SBOM for a project.

    Args:
        project_path: Path to project root

    Returns:
        SBOMReport with all detected dependencies
    """
    service = SBOMDetectionService()
    return service.detect_dependencies(project_path)
