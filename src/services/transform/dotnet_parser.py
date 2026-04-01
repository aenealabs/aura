"""
.NET Parser - AWS Transform Agent Parity

Enterprise .NET code analysis and parsing for legacy modernization.
Supports C#, VB.NET, ASP.NET, and .NET Framework/Core applications.
Provides deep understanding of .NET assemblies, dependencies, and patterns.

Reference: ADR-030 Section 5.4 Transform Agent Components
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DotNetLanguage(str, Enum):
    """Supported .NET languages."""

    CSHARP = "csharp"
    VBNET = "vbnet"
    FSHARP = "fsharp"


class FrameworkType(str, Enum):
    """.NET framework types."""

    FRAMEWORK = "framework"
    CORE = "core"
    NET5_PLUS = "net5_plus"
    STANDARD = "standard"


class ProjectType(str, Enum):
    """.NET project types."""

    CONSOLE = "console"
    WEB_API = "web_api"
    WEB_MVC = "web_mvc"
    WEB_FORMS = "web_forms"
    WPF = "wpf"
    WINFORMS = "winforms"
    CLASS_LIBRARY = "class_library"
    WCF_SERVICE = "wcf_service"
    WINDOWS_SERVICE = "windows_service"
    BLAZOR = "blazor"
    MAUI = "maui"
    UNKNOWN = "unknown"


class MemberType(str, Enum):
    """Class member types."""

    FIELD = "field"
    PROPERTY = "property"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    EVENT = "event"
    INDEXER = "indexer"
    OPERATOR = "operator"
    DESTRUCTOR = "destructor"


class AccessModifier(str, Enum):
    """Access modifiers."""

    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    INTERNAL = "internal"
    PROTECTED_INTERNAL = "protected_internal"
    PRIVATE_PROTECTED = "private_protected"


class TypeKind(str, Enum):
    """Type kinds."""

    CLASS = "class"
    STRUCT = "struct"
    INTERFACE = "interface"
    ENUM = "enum"
    DELEGATE = "delegate"
    RECORD = "record"


class PatternType(str, Enum):
    """Design pattern types detected."""

    SINGLETON = "singleton"
    FACTORY = "factory"
    REPOSITORY = "repository"
    UNIT_OF_WORK = "unit_of_work"
    DEPENDENCY_INJECTION = "dependency_injection"
    MVC = "mvc"
    MVVM = "mvvm"
    CQRS = "cqrs"
    MEDIATOR = "mediator"
    OBSERVER = "observer"
    DECORATOR = "decorator"
    STRATEGY = "strategy"
    ASYNC_AWAIT = "async_await"
    ENTITY_FRAMEWORK = "entity_framework"
    DAPPER = "dapper"


class LegacyPattern(str, Enum):
    """Legacy patterns that need modernization."""

    WEB_FORMS = "web_forms"
    WCF = "wcf"
    ASMX = "asmx"
    REMOTING = "remoting"
    COM_INTEROP = "com_interop"
    TYPED_DATASETS = "typed_datasets"
    LINQ_TO_SQL = "linq_to_sql"
    ENTERPRISE_LIBRARY = "enterprise_library"
    SYNC_HTTP_CALLS = "sync_http_calls"
    THREAD_SLEEP = "thread_sleep"
    MANUAL_THREADING = "manual_threading"
    CONFIGURATION_MANAGER = "configuration_manager"
    WEB_CONFIG = "web_config"


@dataclass
class UsingDirective:
    """Using/import directive."""

    namespace: str
    alias: str | None = None
    is_static: bool = False
    is_global: bool = False
    line_number: int = 0


@dataclass
class Attribute:
    """Attribute/annotation."""

    name: str
    arguments: dict[str, str] = field(default_factory=dict)
    target: str | None = None


@dataclass
class Parameter:
    """Method/constructor parameter."""

    name: str
    type_name: str
    default_value: str | None = None
    is_params: bool = False
    is_ref: bool = False
    is_out: bool = False
    is_in: bool = False
    attributes: list[Attribute] = field(default_factory=list)


@dataclass
class GenericParameter:
    """Generic type parameter."""

    name: str
    constraints: list[str] = field(default_factory=list)
    variance: str | None = None


@dataclass
class MethodInfo:
    """Method information."""

    name: str
    return_type: str
    access: AccessModifier
    parameters: list[Parameter] = field(default_factory=list)
    generic_parameters: list[GenericParameter] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    is_static: bool = False
    is_virtual: bool = False
    is_override: bool = False
    is_abstract: bool = False
    is_sealed: bool = False
    is_async: bool = False
    is_extension: bool = False
    body_lines: int = 0
    cyclomatic_complexity: int = 1
    line_start: int = 0
    line_end: int = 0
    calls: list[str] = field(default_factory=list)


@dataclass
class PropertyInfo:
    """Property information."""

    name: str
    type_name: str
    access: AccessModifier
    has_getter: bool = True
    has_setter: bool = True
    is_auto: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_override: bool = False
    is_abstract: bool = False
    attributes: list[Attribute] = field(default_factory=list)
    line_number: int = 0


@dataclass
class FieldInfo:
    """Field information."""

    name: str
    type_name: str
    access: AccessModifier
    is_static: bool = False
    is_readonly: bool = False
    is_const: bool = False
    is_volatile: bool = False
    initial_value: str | None = None
    attributes: list[Attribute] = field(default_factory=list)
    line_number: int = 0


@dataclass
class EventInfo:
    """Event information."""

    name: str
    type_name: str
    access: AccessModifier
    is_static: bool = False
    attributes: list[Attribute] = field(default_factory=list)
    line_number: int = 0


@dataclass
class TypeDefinition:
    """Type (class, struct, interface, etc.) definition."""

    name: str
    kind: TypeKind
    namespace: str
    access: AccessModifier
    base_type: str | None = None
    interfaces: list[str] = field(default_factory=list)
    generic_parameters: list[GenericParameter] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    properties: list[PropertyInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    events: list[EventInfo] = field(default_factory=list)
    nested_types: list["TypeDefinition"] = field(default_factory=list)
    is_partial: bool = False
    is_static: bool = False
    is_sealed: bool = False
    is_abstract: bool = False
    line_start: int = 0
    line_end: int = 0
    file_path: str = ""

    @property
    def full_name(self) -> str:
        """Get fully qualified name."""
        if self.namespace:
            return f"{self.namespace}.{self.name}"
        return self.name

    @property
    def member_count(self) -> int:
        """Total member count."""
        return (
            len(self.fields)
            + len(self.properties)
            + len(self.methods)
            + len(self.events)
        )


@dataclass
class NuGetPackage:
    """NuGet package reference."""

    name: str
    version: str
    is_dev_dependency: bool = False
    target_framework: str | None = None


@dataclass
class ProjectReference:
    """Project reference."""

    path: str
    name: str
    include_assets: list[str] = field(default_factory=list)
    exclude_assets: list[str] = field(default_factory=list)


@dataclass
class AssemblyReference:
    """Assembly reference."""

    name: str
    version: str | None = None
    culture: str | None = None
    public_key_token: str | None = None
    hint_path: str | None = None


@dataclass
class ConfigurationSection:
    """Configuration section (from app.config/web.config)."""

    name: str
    settings: dict[str, str] = field(default_factory=dict)
    connection_strings: dict[str, str] = field(default_factory=dict)


@dataclass
class DetectedPattern:
    """Detected design or legacy pattern."""

    pattern: PatternType | LegacyPattern
    confidence: float
    locations: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class DatabaseAccess:
    """Database access detection."""

    technology: str
    connection_string_name: str | None = None
    tables: list[str] = field(default_factory=list)
    stored_procedures: list[str] = field(default_factory=list)
    raw_sql_locations: list[int] = field(default_factory=list)


@dataclass
class ApiEndpoint:
    """API endpoint definition."""

    route: str
    http_method: str
    controller: str
    action: str
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str = ""
    attributes: list[Attribute] = field(default_factory=list)


@dataclass
class SourceFile:
    """Parsed source file."""

    path: str
    language: DotNetLanguage
    using_directives: list[UsingDirective] = field(default_factory=list)
    namespace: str = ""
    types: list[TypeDefinition] = field(default_factory=list)
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    source_hash: str = ""


@dataclass
class DotNetProject:
    """Parsed .NET project."""

    name: str
    path: str
    project_type: ProjectType
    framework: FrameworkType
    target_framework: str
    language: DotNetLanguage

    # Dependencies
    nuget_packages: list[NuGetPackage] = field(default_factory=list)
    project_references: list[ProjectReference] = field(default_factory=list)
    assembly_references: list[AssemblyReference] = field(default_factory=list)

    # Source files
    source_files: list[SourceFile] = field(default_factory=list)

    # All types across files
    types: list[TypeDefinition] = field(default_factory=list)

    # Detected patterns
    patterns: list[DetectedPattern] = field(default_factory=list)

    # Database access
    database_access: list[DatabaseAccess] = field(default_factory=list)

    # API endpoints
    endpoints: list[ApiEndpoint] = field(default_factory=list)

    # Configuration
    configuration: ConfigurationSection | None = None

    # Metadata
    sdk_style: bool = False
    nullable_enabled: bool = False
    implicit_usings: bool = False

    parse_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DotNetSolution:
    """Parsed .NET solution."""

    name: str
    path: str
    projects: list[DotNetProject] = field(default_factory=list)
    solution_folders: dict[str, list[str]] = field(default_factory=dict)
    global_sections: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class ParseError:
    """.NET parse error."""

    file_path: str
    line_number: int
    column: int
    message: str
    severity: str


@dataclass
class ParseResult:
    """Result of .NET parsing."""

    success: bool
    project: DotNetProject | None = None
    solution: DotNetSolution | None = None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)
    parse_duration_ms: float = 0


class DotNetParser:
    """
    Enterprise .NET parser for legacy modernization.

    Provides comprehensive parsing of .NET projects including:
    - C#, VB.NET, and F# source files
    - Project files (.csproj, .vbproj)
    - Solution files (.sln)
    - Configuration files (app.config, web.config, appsettings.json)
    - NuGet packages and dependencies
    - Design pattern detection
    - Legacy pattern identification
    - API endpoint extraction
    - Database access analysis
    """

    def __init__(self) -> None:
        """Initialize .NET parser."""
        self._type_patterns = self._build_type_patterns()
        self._member_patterns = self._build_member_patterns()

    def _build_type_patterns(self) -> dict[str, re.Pattern]:
        """Build regex patterns for type definitions."""
        return {
            "class": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?P<modifiers>(?:(?:static|sealed|abstract|partial)\s+)*)?class\s+(?P<name>\w+)(?:<(?P<generics>[^>]+)>)?(?:\s*:\s*(?P<base>[^\{]+))?",
                re.IGNORECASE,
            ),
            "interface": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?:partial\s+)?interface\s+(?P<name>\w+)(?:<(?P<generics>[^>]+)>)?(?:\s*:\s*(?P<base>[^\{]+))?",
                re.IGNORECASE,
            ),
            "struct": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?P<modifiers>(?:(?:readonly|ref|partial)\s+)*)?struct\s+(?P<name>\w+)(?:<(?P<generics>[^>]+)>)?(?:\s*:\s*(?P<base>[^\{]+))?",
                re.IGNORECASE,
            ),
            "enum": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?enum\s+(?P<name>\w+)(?:\s*:\s*(?P<base>\w+))?",
                re.IGNORECASE,
            ),
            "record": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?P<modifiers>(?:(?:sealed|abstract|partial)\s+)*)?record\s+(?:struct\s+)?(?P<name>\w+)(?:<(?P<generics>[^>]+)>)?(?:\s*:\s*(?P<base>[^\{(]+))?",
                re.IGNORECASE,
            ),
            "delegate": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?delegate\s+(?P<return>\w+(?:<[^>]+>)?)\s+(?P<name>\w+)(?:<(?P<generics>[^>]+)>)?\s*\((?P<params>[^)]*)\)",
                re.IGNORECASE,
            ),
        }

    def _build_member_patterns(self) -> dict[str, re.Pattern]:
        """Build regex patterns for member definitions."""
        return {
            "method": re.compile(
                r"(?:(?P<access>public|private|protected|internal|protected\s+internal)\s+)?(?P<modifiers>(?:(?:static|virtual|override|abstract|sealed|async|extern|partial|new|unsafe)\s+)*)?(?P<return>[\w\.<>\[\],\s\?]+)\s+(?P<name>\w+)(?:<(?P<generics>[^>]+)>)?\s*\((?P<params>[^)]*)\)",
                re.IGNORECASE,
            ),
            "property": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?P<modifiers>(?:(?:static|virtual|override|abstract|sealed|new)\s+)*)?(?P<type>[\w\.<>\[\],\s\?]+)\s+(?P<name>\w+)\s*\{\s*(?P<accessors>.*?)\s*\}",
                re.IGNORECASE | re.DOTALL,
            ),
            "field": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?P<modifiers>(?:(?:static|readonly|const|volatile|new)\s+)*)?(?P<type>[\w\.<>\[\],\s\?]+)\s+(?P<name>\w+)(?:\s*=\s*(?P<value>[^;]+))?;",
                re.IGNORECASE,
            ),
            "event": re.compile(
                r"(?:(?P<access>public|private|protected|internal)\s+)?(?P<modifiers>(?:(?:static|virtual|override|abstract|sealed|new)\s+)*)?event\s+(?P<type>[\w\.<>\[\],\s]+)\s+(?P<name>\w+)",
                re.IGNORECASE,
            ),
        }

    async def parse_solution(
        self, sln_content: str, sln_path: str, project_resolver: Any = None
    ) -> ParseResult:
        """
        Parse .NET solution file.

        Args:
            sln_content: Solution file content
            sln_path: Path to solution file
            project_resolver: Optional function to resolve project contents

        Returns:
            ParseResult with parsed solution
        """
        start_time = datetime.now(timezone.utc)
        errors: list[ParseError] = []

        solution = DotNetSolution(
            name=sln_path.split("/")[-1].replace(".sln", ""), path=sln_path
        )

        # Parse project references
        project_pattern = re.compile(
            r'Project\("\{[^}]+\}"\)\s*=\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"\{([^}]+)\}"'
        )

        for match in project_pattern.finditer(sln_content):
            _project_name = match.group(1)  # noqa: F841
            project_path = match.group(2).replace("\\", "/")

            if project_path.endswith(".csproj") or project_path.endswith(".vbproj"):
                if project_resolver:
                    try:
                        proj_content = await project_resolver(project_path)
                        if proj_content:
                            proj_result = await self.parse_project(
                                proj_content,
                                project_path,
                                None,  # Source resolver would be passed here
                            )
                            if proj_result.project:
                                solution.projects.append(proj_result.project)
                    except Exception as e:
                        errors.append(
                            ParseError(
                                file_path=project_path,
                                line_number=0,
                                column=0,
                                message=str(e),
                                severity="error",
                            )
                        )

        # Parse solution folders
        folder_pattern = re.compile(
            r'Project\("\{2150E333-8FDC-42A3-9474-1A3956D46DE8\}"\)\s*=\s*"([^"]+)"'
        )
        for match in folder_pattern.finditer(sln_content):
            folder_name = match.group(1)
            solution.solution_folders[folder_name] = []

        # Parse GlobalSection
        global_section_pattern = re.compile(
            r"GlobalSection\(([^)]+)\)\s*=\s*(\w+)\s*(.*?)\s*EndGlobalSection",
            re.DOTALL,
        )

        for match in global_section_pattern.finditer(sln_content):
            section_name = match.group(1)
            section_content = match.group(3)
            settings = {}

            for line in section_content.strip().split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    settings[key.strip()] = value.strip()

            solution.global_sections[section_name] = settings

        parse_duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        return ParseResult(
            success=len(errors) == 0,
            solution=solution,
            errors=errors,
            parse_duration_ms=parse_duration,
        )

    async def parse_project(
        self, project_content: str, project_path: str, source_resolver: Any = None
    ) -> ParseResult:
        """
        Parse .NET project file.

        Args:
            project_content: Project file content
            project_path: Path to project file
            source_resolver: Optional function to resolve source file contents

        Returns:
            ParseResult with parsed project
        """
        start_time = datetime.now(timezone.utc)
        errors: list[ParseError] = []

        # Determine language
        language = DotNetLanguage.CSHARP
        if project_path.endswith(".vbproj"):
            language = DotNetLanguage.VBNET
        elif project_path.endswith(".fsproj"):
            language = DotNetLanguage.FSHARP

        # Detect SDK-style project
        sdk_style = "<Project Sdk=" in project_content

        project = DotNetProject(
            name=project_path.split("/")[-1]
            .replace(".csproj", "")
            .replace(".vbproj", ""),
            path=project_path,
            project_type=ProjectType.UNKNOWN,
            framework=FrameworkType.FRAMEWORK,
            target_framework="",
            language=language,
            sdk_style=sdk_style,
        )

        # Parse target framework
        tf_pattern = re.compile(r"<TargetFramework>([^<]+)</TargetFramework>")
        tf_match = tf_pattern.search(project_content)
        if tf_match:
            project.target_framework = tf_match.group(1)
            project.framework = self._determine_framework_type(tf_match.group(1))

        # Parse target frameworks (multiple)
        tfs_pattern = re.compile(r"<TargetFrameworks>([^<]+)</TargetFrameworks>")
        tfs_match = tfs_pattern.search(project_content)
        if tfs_match:
            project.target_framework = tfs_match.group(1).split(";")[0]
            project.framework = self._determine_framework_type(project.target_framework)

        # Parse output type to determine project type
        output_pattern = re.compile(r"<OutputType>([^<]+)</OutputType>")
        output_match = output_pattern.search(project_content)
        sdk_pattern = re.compile(r'<Project\s+Sdk="([^"]+)"')
        sdk_match = sdk_pattern.search(project_content)

        if output_match:
            output_type = output_match.group(1).lower()
            if output_type == "exe":
                project.project_type = ProjectType.CONSOLE
            elif output_type == "winexe":
                project.project_type = ProjectType.WINFORMS
            elif output_type == "library":
                project.project_type = ProjectType.CLASS_LIBRARY

        if sdk_match:
            sdk = sdk_match.group(1).lower()
            if "web" in sdk:
                project.project_type = ProjectType.WEB_API
            elif "blazor" in sdk:
                project.project_type = ProjectType.BLAZOR
            elif "maui" in sdk:
                project.project_type = ProjectType.MAUI
            elif "wpf" in sdk:
                project.project_type = ProjectType.WPF
            elif "windowsforms" in sdk:
                project.project_type = ProjectType.WINFORMS

        # Parse NuGet packages
        package_pattern = re.compile(
            r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"'
        )
        for match in package_pattern.finditer(project_content):
            project.nuget_packages.append(
                NuGetPackage(name=match.group(1), version=match.group(2))
            )

        # Parse project references
        proj_ref_pattern = re.compile(r'<ProjectReference\s+Include="([^"]+)"')
        for match in proj_ref_pattern.finditer(project_content):
            ref_path = match.group(1).replace("\\", "/")
            ref_name = ref_path.split("/")[-1].replace(".csproj", "")
            project.project_references.append(
                ProjectReference(path=ref_path, name=ref_name)
            )

        # Parse assembly references (old-style projects)
        asm_ref_pattern = re.compile(r'<Reference\s+Include="([^"]+)"')
        for match in asm_ref_pattern.finditer(project_content):
            ref_string = match.group(1)
            parts = ref_string.split(",")
            project.assembly_references.append(
                AssemblyReference(
                    name=parts[0].strip(),
                    version=self._extract_assembly_part(ref_string, "Version"),
                    culture=self._extract_assembly_part(ref_string, "Culture"),
                    public_key_token=self._extract_assembly_part(
                        ref_string, "PublicKeyToken"
                    ),
                )
            )

        # Check for nullable reference types
        if "<Nullable>enable</Nullable>" in project_content:
            project.nullable_enabled = True

        # Check for implicit usings
        if "<ImplicitUsings>enable</ImplicitUsings>" in project_content:
            project.implicit_usings = True

        # Parse source files if resolver provided
        if source_resolver:
            # Get source files from project
            source_files = await self._get_project_source_files(
                project_content, project_path, sdk_style
            )

            for source_path in source_files:
                try:
                    source_content = await source_resolver(source_path)
                    if source_content:
                        source_file = await self.parse_source_file(
                            source_content, source_path, language
                        )
                        project.source_files.append(source_file)
                        project.types.extend(source_file.types)
                except Exception as e:
                    errors.append(
                        ParseError(
                            file_path=source_path,
                            line_number=0,
                            column=0,
                            message=str(e),
                            severity="warning",
                        )
                    )

        # Detect patterns
        project.patterns = self._detect_patterns(project)

        # Detect database access
        project.database_access = self._detect_database_access(project)

        # Extract API endpoints
        project.endpoints = self._extract_endpoints(project)

        parse_duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        return ParseResult(
            success=len(errors) == 0,
            project=project,
            errors=errors,
            parse_duration_ms=parse_duration,
        )

    def _determine_framework_type(self, target_framework: str) -> FrameworkType:
        """Determine framework type from target framework moniker."""
        tf_lower = target_framework.lower()

        if (
            tf_lower.startswith("net4")
            or tf_lower.startswith("net3")
            or tf_lower.startswith("net2")
        ):
            return FrameworkType.FRAMEWORK
        elif tf_lower.startswith("netcoreapp"):
            return FrameworkType.CORE
        elif tf_lower.startswith("netstandard"):
            return FrameworkType.STANDARD
        elif (
            tf_lower.startswith("net5")
            or tf_lower.startswith("net6")
            or tf_lower.startswith("net7")
            or tf_lower.startswith("net8")
            or tf_lower.startswith("net9")
        ):
            return FrameworkType.NET5_PLUS
        return FrameworkType.FRAMEWORK

    def _extract_assembly_part(self, ref_string: str, part_name: str) -> str | None:
        """Extract a part from assembly reference string."""
        pattern = re.compile(rf"{part_name}=([^,]+)", re.IGNORECASE)
        match = pattern.search(ref_string)
        return match.group(1).strip() if match else None

    async def _get_project_source_files(
        self, project_content: str, project_path: str, sdk_style: bool
    ) -> list[str]:
        """Get list of source files from project."""
        source_files = []

        if sdk_style:
            # SDK-style projects include all .cs files by default
            # Would need filesystem access to enumerate
            # For now, parse explicit includes
            compile_pattern = re.compile(r'<Compile\s+Include="([^"]+)"')
            for match in compile_pattern.finditer(project_content):
                source_files.append(match.group(1).replace("\\", "/"))

            # Also check for Remove patterns
            remove_pattern = re.compile(r'<Compile\s+Remove="([^"]+)"')
            removes = set()
            for match in remove_pattern.finditer(project_content):
                removes.add(match.group(1).replace("\\", "/"))

            source_files = [f for f in source_files if f not in removes]
        else:
            # Old-style projects list all files explicitly
            compile_pattern = re.compile(r'<Compile\s+Include="([^"]+)"')
            for match in compile_pattern.finditer(project_content):
                source_files.append(match.group(1).replace("\\", "/"))

        return source_files

    async def parse_source_file(
        self,
        content: str,
        file_path: str,
        language: DotNetLanguage = DotNetLanguage.CSHARP,
    ) -> SourceFile:
        """
        Parse a .NET source file.

        Args:
            content: Source file content
            file_path: Path to source file
            language: Programming language

        Returns:
            Parsed SourceFile
        """
        source_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        lines = content.split("\n")

        source_file = SourceFile(
            path=file_path,
            language=language,
            total_lines=len(lines),
            source_hash=source_hash,
        )

        # Count code and comment lines
        in_multiline_comment = False
        for line in lines:
            stripped = line.strip()

            if "/*" in stripped:
                in_multiline_comment = True
            if "*/" in stripped:
                in_multiline_comment = False
                source_file.comment_lines += 1
                continue

            if in_multiline_comment or stripped.startswith("//"):
                source_file.comment_lines += 1
            elif stripped:
                source_file.code_lines += 1

        # Parse using directives
        source_file.using_directives = self._parse_using_directives(content)

        # Parse namespace
        ns_pattern = re.compile(r"namespace\s+([\w.]+)")
        ns_match = ns_pattern.search(content)
        if ns_match:
            source_file.namespace = ns_match.group(1)

        # Parse types
        source_file.types = self._parse_types(content, source_file.namespace, file_path)

        return source_file

    def _parse_using_directives(self, content: str) -> list[UsingDirective]:
        """Parse using directives from source."""
        directives = []

        # Standard using
        using_pattern = re.compile(
            r"(?P<global>global\s+)?using\s+(?P<static>static\s+)?(?:(?P<alias>\w+)\s*=\s*)?(?P<namespace>[\w.]+)\s*;",
            re.MULTILINE,
        )

        for _i, match in enumerate(using_pattern.finditer(content)):
            directives.append(
                UsingDirective(
                    namespace=match.group("namespace"),
                    alias=match.group("alias"),
                    is_static=match.group("static") is not None,
                    is_global=match.group("global") is not None,
                    line_number=content[: match.start()].count("\n") + 1,
                )
            )

        return directives

    def _parse_types(
        self, content: str, namespace: str, file_path: str
    ) -> list[TypeDefinition]:
        """Parse type definitions from source."""
        types = []

        for kind, pattern in self._type_patterns.items():
            for match in pattern.finditer(content):
                type_kind = TypeKind(kind)

                # Parse access modifier
                access_str = match.group("access") or "internal"
                access = self._parse_access_modifier(access_str)

                type_def = TypeDefinition(
                    name=match.group("name"),
                    kind=type_kind,
                    namespace=namespace,
                    access=access,
                    file_path=file_path,
                    line_start=content[: match.start()].count("\n") + 1,
                )

                # Parse modifiers
                modifiers = (
                    match.group("modifiers") if "modifiers" in match.groupdict() else ""
                )
                if modifiers:
                    modifiers_lower = modifiers.lower()
                    type_def.is_static = "static" in modifiers_lower
                    type_def.is_sealed = "sealed" in modifiers_lower
                    type_def.is_abstract = "abstract" in modifiers_lower
                    type_def.is_partial = "partial" in modifiers_lower

                # Parse base type and interfaces
                base_str = match.group("base") if "base" in match.groupdict() else None
                if base_str:
                    base_parts = [b.strip() for b in base_str.split(",")]
                    if base_parts:
                        # First one could be base class or interface
                        first = base_parts[0]
                        if first.startswith("I") and first[1].isupper():
                            type_def.interfaces.append(first)
                        else:
                            type_def.base_type = first

                        type_def.interfaces.extend(base_parts[1:])

                # Parse generic parameters
                generics_str = (
                    match.group("generics") if "generics" in match.groupdict() else None
                )
                if generics_str:
                    type_def.generic_parameters = self._parse_generic_parameters(
                        generics_str
                    )

                # Find type body and parse members
                type_body = self._extract_type_body(content, match.end())
                if type_body:
                    type_def.line_end = type_def.line_start + type_body.count("\n")
                    self._parse_members(type_body, type_def)

                types.append(type_def)

        return types

    def _parse_access_modifier(self, access_str: str) -> AccessModifier:
        """Parse access modifier string."""
        access_lower = access_str.lower().strip()

        if "protected internal" in access_lower or "internal protected" in access_lower:
            return AccessModifier.PROTECTED_INTERNAL
        elif "private protected" in access_lower or "protected private" in access_lower:
            return AccessModifier.PRIVATE_PROTECTED
        elif "public" in access_lower:
            return AccessModifier.PUBLIC
        elif "private" in access_lower:
            return AccessModifier.PRIVATE
        elif "protected" in access_lower:
            return AccessModifier.PROTECTED
        elif "internal" in access_lower:
            return AccessModifier.INTERNAL

        return AccessModifier.PRIVATE

    def _parse_generic_parameters(self, generics_str: str) -> list[GenericParameter]:
        """Parse generic type parameters."""
        params = []

        for param in generics_str.split(","):
            param = param.strip()
            if param:
                params.append(GenericParameter(name=param))

        return params

    def _extract_type_body(self, content: str, start_pos: int) -> str:
        """Extract type body (content between braces)."""
        brace_count = 0
        body_start = -1
        body_end = -1

        for i in range(start_pos, len(content)):
            if content[i] == "{":
                if body_start == -1:
                    body_start = i + 1
                brace_count += 1
            elif content[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    body_end = i
                    break

        if body_start != -1 and body_end != -1:
            return content[body_start:body_end]
        return ""

    def _parse_members(self, body: str, type_def: TypeDefinition) -> None:
        """Parse members from type body."""
        # Parse methods
        for match in self._member_patterns["method"].finditer(body):
            name = match.group("name")

            # Skip if it looks like a property accessor
            if name in ["get", "set", "add", "remove"]:
                continue

            access_str = match.group("access") or "private"
            modifiers = match.group("modifiers") or ""

            method = MethodInfo(
                name=name,
                return_type=match.group("return").strip(),
                access=self._parse_access_modifier(access_str),
                line_start=body[: match.start()].count("\n") + type_def.line_start,
            )

            modifiers_lower = modifiers.lower()
            method.is_static = "static" in modifiers_lower
            method.is_virtual = "virtual" in modifiers_lower
            method.is_override = "override" in modifiers_lower
            method.is_abstract = "abstract" in modifiers_lower
            method.is_sealed = "sealed" in modifiers_lower
            method.is_async = "async" in modifiers_lower

            # Parse parameters
            params_str = match.group("params")
            if params_str:
                method.parameters = self._parse_parameters(params_str)

            # Check for extension method
            if method.parameters and method.is_static:
                first_param = method.parameters[0]
                if first_param.name.startswith("this "):
                    method.is_extension = True
                    first_param.name = first_param.name[5:]

            type_def.methods.append(method)

        # Parse properties
        for match in self._member_patterns["property"].finditer(body):
            access_str = match.group("access") or "private"
            modifiers = match.group("modifiers") or ""
            accessors = match.group("accessors")

            prop = PropertyInfo(
                name=match.group("name"),
                type_name=match.group("type").strip(),
                access=self._parse_access_modifier(access_str),
                line_number=body[: match.start()].count("\n") + type_def.line_start,
            )

            modifiers_lower = modifiers.lower()
            prop.is_static = "static" in modifiers_lower
            prop.is_virtual = "virtual" in modifiers_lower
            prop.is_override = "override" in modifiers_lower
            prop.is_abstract = "abstract" in modifiers_lower

            # Check accessors
            prop.has_getter = "get" in accessors.lower()
            prop.has_setter = "set" in accessors.lower()
            prop.is_auto = "get;" in accessors or "set;" in accessors

            type_def.properties.append(prop)

        # Parse fields
        for match in self._member_patterns["field"].finditer(body):
            access_str = match.group("access") or "private"
            modifiers = match.group("modifiers") or ""

            field = FieldInfo(
                name=match.group("name"),
                type_name=match.group("type").strip(),
                access=self._parse_access_modifier(access_str),
                initial_value=match.group("value"),
                line_number=body[: match.start()].count("\n") + type_def.line_start,
            )

            modifiers_lower = modifiers.lower()
            field.is_static = "static" in modifiers_lower
            field.is_readonly = "readonly" in modifiers_lower
            field.is_const = "const" in modifiers_lower
            field.is_volatile = "volatile" in modifiers_lower

            type_def.fields.append(field)

        # Parse events
        for match in self._member_patterns["event"].finditer(body):
            access_str = match.group("access") or "private"
            modifiers = match.group("modifiers") or ""

            event = EventInfo(
                name=match.group("name"),
                type_name=match.group("type").strip(),
                access=self._parse_access_modifier(access_str),
                line_number=body[: match.start()].count("\n") + type_def.line_start,
            )

            event.is_static = "static" in modifiers.lower()

            type_def.events.append(event)

    def _parse_parameters(self, params_str: str) -> list[Parameter]:
        """Parse method parameters."""
        params = []

        # Split by comma, but respect generics
        depth = 0
        current = ""
        parts = []

        for char in params_str:
            if char == "<":
                depth += 1
            elif char == ">":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(current.strip())
                current = ""
                continue
            current += char

        if current.strip():
            parts.append(current.strip())

        for part in parts:
            if not part:
                continue

            # Parse parameter modifiers
            is_params = part.startswith("params ")
            is_ref = " ref " in f" {part} " or part.startswith("ref ")
            is_out = " out " in f" {part} " or part.startswith("out ")
            is_in = " in " in f" {part} " or part.startswith("in ")

            # Remove modifiers
            clean = part
            for mod in ["params", "ref", "out", "in"]:
                clean = re.sub(rf"\b{mod}\b\s*", "", clean)

            # Split type and name
            tokens = clean.split()
            if len(tokens) >= 2:
                type_name = " ".join(tokens[:-1])
                name = tokens[-1]

                # Check for default value
                default_value = None
                if "=" in name:
                    name, default_value = name.split("=", 1)
                    name = name.strip()
                    default_value = default_value.strip()

                params.append(
                    Parameter(
                        name=name,
                        type_name=type_name,
                        default_value=default_value,
                        is_params=is_params,
                        is_ref=is_ref,
                        is_out=is_out,
                        is_in=is_in,
                    )
                )

        return params

    def _detect_patterns(self, project: DotNetProject) -> list[DetectedPattern]:
        """Detect design and legacy patterns in project."""
        patterns = []

        # Check for patterns based on NuGet packages
        package_patterns = {
            "MediatR": PatternType.MEDIATOR,
            "AutoMapper": PatternType.DEPENDENCY_INJECTION,
            "Microsoft.Extensions.DependencyInjection": PatternType.DEPENDENCY_INJECTION,
            "Autofac": PatternType.DEPENDENCY_INJECTION,
            "Ninject": PatternType.DEPENDENCY_INJECTION,
            "Microsoft.EntityFrameworkCore": PatternType.ENTITY_FRAMEWORK,
            "EntityFramework": PatternType.ENTITY_FRAMEWORK,
            "Dapper": PatternType.DAPPER,
        }

        for package in project.nuget_packages:
            if package.name in package_patterns:
                patterns.append(
                    DetectedPattern(
                        pattern=package_patterns[package.name],
                        confidence=0.9,
                        locations=[f"NuGet: {package.name}"],
                        description=f"Detected via NuGet package {package.name}",
                    )
                )

        # Check for legacy patterns based on assemblies
        legacy_assemblies = {
            "System.Web": LegacyPattern.WEB_FORMS,
            "System.ServiceModel": LegacyPattern.WCF,
            "System.Runtime.Remoting": LegacyPattern.REMOTING,
            "System.EnterpriseServices": LegacyPattern.COM_INTEROP,
            "Microsoft.Practices.EnterpriseLibrary": LegacyPattern.ENTERPRISE_LIBRARY,
        }

        for ref in project.assembly_references:
            for pattern_name, pattern in legacy_assemblies.items():
                if pattern_name in ref.name:
                    patterns.append(
                        DetectedPattern(
                            pattern=pattern,
                            confidence=0.85,
                            locations=[f"Assembly: {ref.name}"],
                            description=f"Legacy assembly reference: {ref.name}",
                        )
                    )

        # Check for patterns in code
        for type_def in project.types:
            # Singleton pattern
            if any(
                f.is_static and "instance" in f.name.lower() for f in type_def.fields
            ):
                if any(
                    m.name.lower() in ["getinstance", "instance"]
                    for m in type_def.methods
                ):
                    patterns.append(
                        DetectedPattern(
                            pattern=PatternType.SINGLETON,
                            confidence=0.8,
                            locations=[type_def.full_name],
                            description="Static instance field with accessor method",
                        )
                    )

            # Repository pattern
            if "repository" in type_def.name.lower() or "repo" in type_def.name.lower():
                patterns.append(
                    DetectedPattern(
                        pattern=PatternType.REPOSITORY,
                        confidence=0.7,
                        locations=[type_def.full_name],
                        description="Class name contains 'Repository'",
                    )
                )

            # Factory pattern
            if "factory" in type_def.name.lower():
                patterns.append(
                    DetectedPattern(
                        pattern=PatternType.FACTORY,
                        confidence=0.7,
                        locations=[type_def.full_name],
                        description="Class name contains 'Factory'",
                    )
                )

            # Async/await pattern
            async_methods = [m for m in type_def.methods if m.is_async]
            if async_methods:
                patterns.append(
                    DetectedPattern(
                        pattern=PatternType.ASYNC_AWAIT,
                        confidence=0.9,
                        locations=[
                            f"{type_def.full_name}.{m.name}" for m in async_methods[:5]
                        ],
                        description=f"Found {len(async_methods)} async methods",
                    )
                )

        return patterns

    def _detect_database_access(self, project: DotNetProject) -> list[DatabaseAccess]:
        """Detect database access patterns."""
        db_access = []

        # Check for Entity Framework
        ef_packages = [
            p
            for p in project.nuget_packages
            if "EntityFramework" in p.name or "Microsoft.EntityFrameworkCore" in p.name
        ]
        if ef_packages:
            db_access.append(
                DatabaseAccess(
                    technology="Entity Framework", tables=[], stored_procedures=[]
                )
            )

        # Check for Dapper
        dapper_packages = [p for p in project.nuget_packages if p.name == "Dapper"]
        if dapper_packages:
            db_access.append(
                DatabaseAccess(technology="Dapper", tables=[], stored_procedures=[])
            )

        # Check for ADO.NET
        for ref in project.assembly_references:
            if "System.Data" in ref.name:
                db_access.append(
                    DatabaseAccess(
                        technology="ADO.NET", tables=[], stored_procedures=[]
                    )
                )
                break

        return db_access

    def _extract_endpoints(self, project: DotNetProject) -> list[ApiEndpoint]:
        """Extract API endpoints from controllers."""
        endpoints = []

        for type_def in project.types:
            # Check if this is a controller
            is_controller = (
                type_def.name.endswith("Controller")
                or "Controller" in (type_def.base_type or "")
                or any(
                    "ApiController" in attr.name or "Controller" in attr.name
                    for attr in type_def.attributes
                )
            )

            if not is_controller:
                continue

            # Get route prefix from controller attributes
            controller_route = ""
            for attr in type_def.attributes:
                if attr.name in ["Route", "RoutePrefix"]:
                    controller_route = (
                        list(attr.arguments.values())[0] if attr.arguments else ""
                    )

            # Extract endpoints from methods
            for method in type_def.methods:
                http_method = None
                route = ""

                for attr in method.attributes:
                    attr_name = attr.name.lower()

                    if attr_name in ["httpget", "get"]:
                        http_method = "GET"
                    elif attr_name in ["httppost", "post"]:
                        http_method = "POST"
                    elif attr_name in ["httpput", "put"]:
                        http_method = "PUT"
                    elif attr_name in ["httpdelete", "delete"]:
                        http_method = "DELETE"
                    elif attr_name in ["httppatch", "patch"]:
                        http_method = "PATCH"
                    elif attr_name == "route":
                        route = (
                            list(attr.arguments.values())[0] if attr.arguments else ""
                        )

                if http_method:
                    full_route = f"{controller_route}/{route}".replace("//", "/")
                    endpoints.append(
                        ApiEndpoint(
                            route=full_route,
                            http_method=http_method,
                            controller=type_def.name,
                            action=method.name,
                            parameters=method.parameters,
                            return_type=method.return_type,
                            attributes=method.attributes,
                        )
                    )

        return endpoints

    async def get_type_hierarchy(
        self, project: DotNetProject, type_name: str
    ) -> dict[str, Any]:
        """Get inheritance hierarchy for a type."""
        type_def = next(
            (
                t
                for t in project.types
                if t.name == type_name or t.full_name == type_name
            ),
            None,
        )

        if not type_def:
            return {}

        hierarchy: dict[str, Any] = {
            "type": type_def.full_name,
            "kind": type_def.kind.value,
            "base": type_def.base_type,
            "interfaces": type_def.interfaces,
            "derived": [],
        }

        # Find derived types
        for t in project.types:
            if t.base_type == type_def.name or t.base_type == type_def.full_name:
                hierarchy["derived"].append(t.full_name)

        return hierarchy

    async def get_project_metrics(self, project: DotNetProject) -> dict[str, Any]:
        """Get comprehensive project metrics."""
        total_lines = sum(f.total_lines for f in project.source_files)
        code_lines = sum(f.code_lines for f in project.source_files)
        comment_lines = sum(f.comment_lines for f in project.source_files)

        total_methods = sum(len(t.methods) for t in project.types)
        total_properties = sum(len(t.properties) for t in project.types)
        total_fields = sum(len(t.fields) for t in project.types)

        async_methods = sum(1 for t in project.types for m in t.methods if m.is_async)

        return {
            "total_files": len(project.source_files),
            "total_lines": total_lines,
            "code_lines": code_lines,
            "comment_lines": comment_lines,
            "comment_ratio": comment_lines / max(total_lines, 1),
            "total_types": len(project.types),
            "classes": sum(1 for t in project.types if t.kind == TypeKind.CLASS),
            "interfaces": sum(1 for t in project.types if t.kind == TypeKind.INTERFACE),
            "structs": sum(1 for t in project.types if t.kind == TypeKind.STRUCT),
            "enums": sum(1 for t in project.types if t.kind == TypeKind.ENUM),
            "total_methods": total_methods,
            "total_properties": total_properties,
            "total_fields": total_fields,
            "async_method_ratio": async_methods / max(total_methods, 1),
            "nuget_packages": len(project.nuget_packages),
            "project_references": len(project.project_references),
            "assembly_references": len(project.assembly_references),
            "detected_patterns": len(project.patterns),
            "api_endpoints": len(project.endpoints),
            "framework": project.framework.value,
            "target_framework": project.target_framework,
            "sdk_style": project.sdk_style,
            "nullable_enabled": project.nullable_enabled,
        }
