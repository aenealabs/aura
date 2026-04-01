"""
Cross-Language Translator - AWS Transform Agent Parity

Intelligent code translation between legacy and modern languages.
Supports COBOL to Java/Python, VB.NET to C#, and other transformations
with semantic preservation and idiomatic output.

Reference: ADR-030 Section 5.4 Transform Agent Components
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SourceLanguage(str, Enum):
    """Supported source languages for translation."""

    COBOL = "cobol"
    VBNET = "vbnet"
    VB6 = "vb6"
    JAVA = "java"
    CSHARP = "csharp"
    FORTRAN = "fortran"
    PL1 = "pl1"
    RPG = "rpg"
    NATURAL = "natural"
    POWERBUILDER = "powerbuilder"


class TargetLanguage(str, Enum):
    """Supported target languages for translation."""

    PYTHON = "python"
    JAVA = "java"
    CSHARP = "csharp"
    KOTLIN = "kotlin"
    GO = "go"
    RUST = "rust"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"


class TranslationStrategy(str, Enum):
    """Translation approach strategies."""

    LITERAL = "literal"
    IDIOMATIC = "idiomatic"
    OPTIMIZED = "optimized"
    MODERNIZED = "modernized"


class DataTypeMapping(str, Enum):
    """Data type mapping strategies."""

    STRICT = "strict"
    RELAXED = "relaxed"
    NATIVE = "native"


class ComplexityLevel(str, Enum):
    """Translation complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


class TranslationStatus(str, Enum):
    """Translation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ConfidenceLevel(str, Enum):
    """Translation confidence levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


@dataclass
class TypeMapping:
    """Mapping between source and target types."""

    source_type: str
    target_type: str
    conversion_required: bool = False
    conversion_function: str | None = None
    notes: str = ""


@dataclass
class VariableTranslation:
    """Translated variable information."""

    source_name: str
    target_name: str
    source_type: str
    target_type: str
    scope: str = "local"
    initial_value: str | None = None
    line_number: int = 0


@dataclass
class FunctionTranslation:
    """Translated function/method information."""

    source_name: str
    target_name: str
    source_signature: str
    target_signature: str
    parameter_mappings: list[tuple[str, str]] = field(default_factory=list)
    return_type_mapping: TypeMapping | None = None
    body_translation: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    notes: list[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class DataStructureTranslation:
    """Translated data structure."""

    source_name: str
    target_name: str
    source_definition: str
    target_definition: str
    field_mappings: list[tuple[str, str, str]] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH


@dataclass
class ImportStatement:
    """Import/using statement for target code."""

    module: str
    items: list[str] = field(default_factory=list)
    alias: str | None = None


@dataclass
class TranslationWarning:
    """Warning during translation."""

    location: str
    message: str
    severity: str
    suggestion: str | None = None
    line_number: int = 0


@dataclass
class ManualReviewItem:
    """Item requiring manual review."""

    location: str
    original_code: str
    translated_code: str
    reason: str
    suggestions: list[str] = field(default_factory=list)
    priority: str = "medium"


@dataclass
class TranslationConfig:
    """Configuration for translation."""

    source_language: SourceLanguage
    target_language: TargetLanguage
    strategy: TranslationStrategy = TranslationStrategy.IDIOMATIC
    type_mapping: DataTypeMapping = DataTypeMapping.NATIVE
    preserve_comments: bool = True
    generate_tests: bool = True
    add_type_hints: bool = True
    use_modern_patterns: bool = True
    max_line_length: int = 120
    indent_size: int = 4
    naming_convention: str = "snake_case"
    custom_type_mappings: dict[str, str] = field(default_factory=dict)


@dataclass
class TranslatedFile:
    """Result of translating a single file."""

    source_path: str
    target_path: str
    source_language: SourceLanguage
    target_language: TargetLanguage
    source_code: str
    translated_code: str
    imports: list[ImportStatement] = field(default_factory=list)
    variables: list[VariableTranslation] = field(default_factory=list)
    functions: list[FunctionTranslation] = field(default_factory=list)
    data_structures: list[DataStructureTranslation] = field(default_factory=list)
    warnings: list[TranslationWarning] = field(default_factory=list)
    manual_review_items: list[ManualReviewItem] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    source_lines: int = 0
    target_lines: int = 0
    translation_ratio: float = 1.0


@dataclass
class TranslationTestCase:
    """Generated test case for translated code."""

    name: str
    description: str
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: Any = None
    original_function: str = ""
    translated_function: str = ""
    test_code: str = ""


@dataclass
class TranslationResult:
    """Complete translation result."""

    status: TranslationStatus
    files: list[TranslatedFile] = field(default_factory=list)
    test_cases: list[TranslationTestCase] = field(default_factory=list)
    type_mappings_used: list[TypeMapping] = field(default_factory=list)
    overall_confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    total_source_lines: int = 0
    total_target_lines: int = 0
    warnings_count: int = 0
    manual_review_count: int = 0
    translation_time_ms: float = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CrossLanguageTranslator:
    """
    Cross-language code translator for legacy modernization.

    Provides intelligent translation between legacy and modern languages:
    - COBOL to Python/Java
    - VB.NET/VB6 to C#
    - Java to Kotlin/Python
    - Various legacy languages to modern equivalents

    Features:
    - Semantic preservation
    - Idiomatic output generation
    - Type system mapping
    - Test case generation
    - Manual review flagging
    """

    def __init__(self) -> None:
        """Initialize cross-language translator."""
        self._type_mappings = self._build_type_mappings()
        self._keyword_mappings = self._build_keyword_mappings()
        self._pattern_translators = self._build_pattern_translators()

    def _build_type_mappings(
        self,
    ) -> dict[tuple[SourceLanguage, TargetLanguage], dict[str, TypeMapping]]:
        """Build type mappings between language pairs."""
        mappings: dict[
            tuple[SourceLanguage, TargetLanguage], dict[str, TypeMapping]
        ] = {}

        # COBOL to Python
        mappings[(SourceLanguage.COBOL, TargetLanguage.PYTHON)] = {
            "PIC 9": TypeMapping("PIC 9", "int", False),
            "PIC 9(n)": TypeMapping("PIC 9(n)", "int", False),
            "PIC 9V9": TypeMapping("PIC 9V9", "Decimal", True, "Decimal"),
            "PIC S9": TypeMapping("PIC S9", "int", False),
            "PIC X": TypeMapping("PIC X", "str", False),
            "PIC X(n)": TypeMapping("PIC X(n)", "str", False),
            "PIC A": TypeMapping("PIC A", "str", False),
            "COMP": TypeMapping("COMP", "int", False),
            "COMP-1": TypeMapping("COMP-1", "float", False),
            "COMP-2": TypeMapping("COMP-2", "float", False),
            "COMP-3": TypeMapping("COMP-3", "Decimal", True, "Decimal"),
        }

        # COBOL to Java
        mappings[(SourceLanguage.COBOL, TargetLanguage.JAVA)] = {
            "PIC 9": TypeMapping("PIC 9", "int", False),
            "PIC 9(n)": TypeMapping("PIC 9(n)", "int", False),
            "PIC 9V9": TypeMapping("PIC 9V9", "BigDecimal", True, "BigDecimal"),
            "PIC S9": TypeMapping("PIC S9", "int", False),
            "PIC X": TypeMapping("PIC X", "String", False),
            "PIC X(n)": TypeMapping("PIC X(n)", "String", False),
            "PIC A": TypeMapping("PIC A", "String", False),
            "COMP": TypeMapping("COMP", "int", False),
            "COMP-1": TypeMapping("COMP-1", "float", False),
            "COMP-2": TypeMapping("COMP-2", "double", False),
            "COMP-3": TypeMapping("COMP-3", "BigDecimal", True, "BigDecimal"),
        }

        # VB.NET to C#
        mappings[(SourceLanguage.VBNET, TargetLanguage.CSHARP)] = {
            "Integer": TypeMapping("Integer", "int", False),
            "Long": TypeMapping("Long", "long", False),
            "Short": TypeMapping("Short", "short", False),
            "Byte": TypeMapping("Byte", "byte", False),
            "Single": TypeMapping("Single", "float", False),
            "Double": TypeMapping("Double", "double", False),
            "Decimal": TypeMapping("Decimal", "decimal", False),
            "String": TypeMapping("String", "string", False),
            "Boolean": TypeMapping("Boolean", "bool", False),
            "Date": TypeMapping("Date", "DateTime", False),
            "Object": TypeMapping("Object", "object", False),
            "Char": TypeMapping("Char", "char", False),
        }

        # Java to Kotlin
        mappings[(SourceLanguage.JAVA, TargetLanguage.KOTLIN)] = {
            "int": TypeMapping("int", "Int", False),
            "long": TypeMapping("long", "Long", False),
            "short": TypeMapping("short", "Short", False),
            "byte": TypeMapping("byte", "Byte", False),
            "float": TypeMapping("float", "Float", False),
            "double": TypeMapping("double", "Double", False),
            "boolean": TypeMapping("boolean", "Boolean", False),
            "char": TypeMapping("char", "Char", False),
            "String": TypeMapping("String", "String", False),
            "Integer": TypeMapping("Integer", "Int?", False),
            "Long": TypeMapping("Long", "Long?", False),
            "Boolean": TypeMapping("Boolean", "Boolean?", False),
            "void": TypeMapping("void", "Unit", False),
        }

        # Java to Python
        mappings[(SourceLanguage.JAVA, TargetLanguage.PYTHON)] = {
            "int": TypeMapping("int", "int", False),
            "long": TypeMapping("long", "int", False),
            "short": TypeMapping("short", "int", False),
            "byte": TypeMapping("byte", "int", False),
            "float": TypeMapping("float", "float", False),
            "double": TypeMapping("double", "float", False),
            "boolean": TypeMapping("boolean", "bool", False),
            "char": TypeMapping("char", "str", False),
            "String": TypeMapping("String", "str", False),
            "List": TypeMapping("List", "list", False),
            "Map": TypeMapping("Map", "dict", False),
            "Set": TypeMapping("Set", "set", False),
            "void": TypeMapping("void", "None", False),
        }

        # C# to Python
        mappings[(SourceLanguage.CSHARP, TargetLanguage.PYTHON)] = {
            "int": TypeMapping("int", "int", False),
            "long": TypeMapping("long", "int", False),
            "short": TypeMapping("short", "int", False),
            "byte": TypeMapping("byte", "int", False),
            "float": TypeMapping("float", "float", False),
            "double": TypeMapping("double", "float", False),
            "decimal": TypeMapping("decimal", "Decimal", True, "Decimal"),
            "bool": TypeMapping("bool", "bool", False),
            "char": TypeMapping("char", "str", False),
            "string": TypeMapping("string", "str", False),
            "List<T>": TypeMapping("List<T>", "list[T]", False),
            "Dictionary<K,V>": TypeMapping("Dictionary<K,V>", "dict[K, V]", False),
            "void": TypeMapping("void", "None", False),
        }

        return mappings

    def _build_keyword_mappings(
        self,
    ) -> dict[tuple[SourceLanguage, TargetLanguage], dict[str, str]]:
        """Build keyword mappings between language pairs."""
        mappings: dict[tuple[SourceLanguage, TargetLanguage], dict[str, str]] = {}

        # COBOL to Python
        mappings[(SourceLanguage.COBOL, TargetLanguage.PYTHON)] = {
            "MOVE": "=",
            "ADD": "+=",
            "SUBTRACT": "-=",
            "MULTIPLY": "*=",
            "DIVIDE": "/=",
            "IF": "if",
            "ELSE": "else",
            "END-IF": "",
            "PERFORM": "call",
            "UNTIL": "while not",
            "VARYING": "for",
            "DISPLAY": "print",
            "ACCEPT": "input",
            "STOP RUN": "sys.exit()",
            "SPACES": "' '",
            "ZEROS": "0",
            "HIGH-VALUES": "chr(255)",
            "LOW-VALUES": "chr(0)",
        }

        # VB.NET to C#
        mappings[(SourceLanguage.VBNET, TargetLanguage.CSHARP)] = {
            "Sub": "void",
            "Function": "",
            "End Sub": "}",
            "End Function": "}",
            "Dim": "var",
            "If": "if",
            "Then": "",
            "ElseIf": "else if",
            "Else": "else",
            "End If": "}",
            "For": "for",
            "To": "",
            "Step": "",
            "Next": "}",
            "While": "while",
            "End While": "}",
            "Do While": "while",
            "Loop": "}",
            "Select Case": "switch",
            "Case": "case",
            "End Select": "}",
            "Try": "try",
            "Catch": "catch",
            "Finally": "finally",
            "End Try": "}",
            "Throw": "throw",
            "Return": "return",
            "Nothing": "null",
            "True": "true",
            "False": "false",
            "And": "&&",
            "Or": "||",
            "Not": "!",
            "AndAlso": "&&",
            "OrElse": "||",
            "Is": "==",
            "IsNot": "!=",
            "&": "+",
            "Mod": "%",
            "\\": "/",
            "^": "Math.Pow",
            "Me": "this",
            "MyBase": "base",
            "Imports": "using",
            "Namespace": "namespace",
            "Class": "class",
            "Inherits": ":",
            "Implements": ":",
            "Interface": "interface",
            "MustInherit": "abstract",
            "NotInheritable": "sealed",
            "Overridable": "virtual",
            "Overrides": "override",
            "MustOverride": "abstract",
            "Shared": "static",
            "ReadOnly": "readonly",
            "Const": "const",
            "Public": "public",
            "Private": "private",
            "Protected": "protected",
            "Friend": "internal",
            "Property": "",
            "Get": "get",
            "Set": "set",
            "End Property": "}",
            "WithEvents": "",
            "RaiseEvent": "",
            "Handles": "",
            "AddHandler": "+=",
            "RemoveHandler": "-=",
        }

        # Java to Python
        mappings[(SourceLanguage.JAVA, TargetLanguage.PYTHON)] = {
            "public": "",
            "private": "",
            "protected": "",
            "static": "@staticmethod",
            "final": "",
            "class": "class",
            "interface": "class",
            "extends": "",
            "implements": "",
            "new": "",
            "this": "self",
            "super": "super()",
            "null": "None",
            "true": "True",
            "false": "False",
            "void": "",
            "return": "return",
            "if": "if",
            "else": "else",
            "for": "for",
            "while": "while",
            "do": "",
            "switch": "match",
            "case": "case",
            "default": "case _",
            "break": "break",
            "continue": "continue",
            "try": "try",
            "catch": "except",
            "finally": "finally",
            "throw": "raise",
            "throws": "",
            "instanceof": "isinstance",
            "&&": "and",
            "||": "or",
            "!": "not",
            "System.out.println": "print",
            "System.out.print": "print",
        }

        return mappings

    def _build_pattern_translators(
        self,
    ) -> dict[tuple[SourceLanguage, TargetLanguage], list[tuple[re.Pattern, str]]]:
        """Build regex pattern translators."""
        translators: dict[
            tuple[SourceLanguage, TargetLanguage], list[tuple[re.Pattern, str]]
        ] = {}

        # VB.NET to C# patterns
        translators[(SourceLanguage.VBNET, TargetLanguage.CSHARP)] = [
            # Method declarations
            (
                re.compile(
                    r"(?:Public|Private|Protected)?\s*(?:Shared\s+)?Sub\s+(\w+)\s*\(([^)]*)\)",
                    re.IGNORECASE,
                ),
                r"void \1(\2)",
            ),
            (
                re.compile(
                    r"(?:Public|Private|Protected)?\s*(?:Shared\s+)?Function\s+(\w+)\s*\(([^)]*)\)\s*As\s+(\w+)",
                    re.IGNORECASE,
                ),
                r"\3 \1(\2)",
            ),
            # Variable declarations
            (
                re.compile(r"Dim\s+(\w+)\s+As\s+(\w+)(?:\s*=\s*(.+))?", re.IGNORECASE),
                r"\2 \1 = \3",
            ),
            # If statements
            (re.compile(r"If\s+(.+?)\s+Then", re.IGNORECASE), r"if (\1)"),
            # For loops
            (
                re.compile(
                    r"For\s+(\w+)\s*=\s*(\d+)\s+To\s+(\d+)(?:\s+Step\s+(\d+))?",
                    re.IGNORECASE,
                ),
                r"for (int \1 = \2; \1 <= \3; \1 += \4)",
            ),
            # String concatenation
            (re.compile(r"(\w+)\s*&\s*(\w+)"), r"\1 + \2"),
        ]

        # Java to Python patterns
        translators[(SourceLanguage.JAVA, TargetLanguage.PYTHON)] = [
            # Class definition
            (
                re.compile(
                    r"(?:public\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+[\w,\s]+)?"
                ),
                r"class \1(\2):",
            ),
            # Method definition
            (
                re.compile(
                    r"(?:public|private|protected)?\s*(?:static\s+)?(\w+)\s+(\w+)\s*\(([^)]*)\)"
                ),
                r"def \2(self, \3) -> \1:",
            ),
            # Variable declaration with initialization
            (re.compile(r"(?:final\s+)?(\w+)\s+(\w+)\s*=\s*(.+);"), r"\2: \1 = \3"),
            # System.out.println
            (re.compile(r"System\.out\.println\(([^)]+)\);"), r"print(\1)"),
            # new Object()
            (re.compile(r"new\s+(\w+)\(([^)]*)\)"), r"\1(\2)"),
            # Array declaration
            (
                re.compile(r"(\w+)\[\]\s+(\w+)\s*=\s*new\s+\w+\[(\d+)\]"),
                r"\2: list[\1] = [None] * \3",
            ),
            # ArrayList to list
            (
                re.compile(
                    r"(?:ArrayList|List)<(\w+)>\s+(\w+)\s*=\s*new\s+ArrayList<>?\(\)"
                ),
                r"\2: list[\1] = []",
            ),
            # HashMap to dict
            (
                re.compile(
                    r"(?:HashMap|Map)<(\w+),\s*(\w+)>\s+(\w+)\s*=\s*new\s+HashMap<>?\(\)"
                ),
                r"\3: dict[\1, \2] = {}",
            ),
        ]

        return translators

    async def translate(
        self, source_code: str, config: TranslationConfig, source_path: str = "source"
    ) -> TranslationResult:
        """
        Translate source code to target language.

        Args:
            source_code: Source code to translate
            config: Translation configuration
            source_path: Path/name of source file

        Returns:
            TranslationResult with translated code
        """
        start_time = datetime.now(timezone.utc)

        # Initialize result
        result = TranslationResult(status=TranslationStatus.IN_PROGRESS)

        try:
            # Create translated file
            translated_file = TranslatedFile(
                source_path=source_path,
                target_path=self._get_target_path(source_path, config.target_language),
                source_language=config.source_language,
                target_language=config.target_language,
                source_code=source_code,
                translated_code="",
                source_lines=len(source_code.split("\n")),
            )

            # Select translation method based on language pair
            if config.source_language == SourceLanguage.COBOL:
                translated_file = await self._translate_cobol(
                    source_code, config, translated_file
                )
            elif config.source_language == SourceLanguage.VBNET:
                translated_file = await self._translate_vbnet(
                    source_code, config, translated_file
                )
            elif config.source_language == SourceLanguage.JAVA:
                translated_file = await self._translate_java(
                    source_code, config, translated_file
                )
            elif config.source_language == SourceLanguage.CSHARP:
                translated_file = await self._translate_csharp(
                    source_code, config, translated_file
                )
            else:
                translated_file = await self._translate_generic(
                    source_code, config, translated_file
                )

            # Calculate metrics
            translated_file.target_lines = len(
                translated_file.translated_code.split("\n")
            )
            translated_file.translation_ratio = translated_file.target_lines / max(
                translated_file.source_lines, 1
            )

            # Determine complexity
            translated_file.complexity = self._assess_complexity(translated_file)

            # Determine confidence
            translated_file.confidence = self._assess_confidence(translated_file)

            # Generate test cases if requested
            test_cases = []
            if config.generate_tests:
                test_cases = await self._generate_test_cases(translated_file, config)

            # Compile result
            result.files.append(translated_file)
            result.test_cases = test_cases
            result.type_mappings_used = self._get_used_type_mappings(
                config.source_language, config.target_language
            )
            result.overall_confidence = translated_file.confidence
            result.total_source_lines = translated_file.source_lines
            result.total_target_lines = translated_file.target_lines
            result.warnings_count = len(translated_file.warnings)
            result.manual_review_count = len(translated_file.manual_review_items)

            if result.manual_review_count > 0:
                result.status = TranslationStatus.NEEDS_REVIEW
            else:
                result.status = TranslationStatus.COMPLETED

        except Exception as e:
            result.status = TranslationStatus.FAILED
            result.files.append(
                TranslatedFile(
                    source_path=source_path,
                    target_path="",
                    source_language=config.source_language,
                    target_language=config.target_language,
                    source_code=source_code,
                    translated_code="",
                    warnings=[
                        TranslationWarning(
                            location="translation", message=str(e), severity="error"
                        )
                    ],
                )
            )

        result.translation_time_ms = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000
        return result

    def _get_target_path(
        self, source_path: str, target_language: TargetLanguage
    ) -> str:
        """Get target file path based on target language."""
        extensions = {
            TargetLanguage.PYTHON: ".py",
            TargetLanguage.JAVA: ".java",
            TargetLanguage.CSHARP: ".cs",
            TargetLanguage.KOTLIN: ".kt",
            TargetLanguage.GO: ".go",
            TargetLanguage.RUST: ".rs",
            TargetLanguage.TYPESCRIPT: ".ts",
            TargetLanguage.JAVASCRIPT: ".js",
        }

        base_name = source_path.rsplit(".", 1)[0]
        return base_name + extensions.get(target_language, ".txt")

    async def _translate_cobol(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate COBOL to target language."""
        lines = source_code.split("\n")
        output_lines = []
        imports_needed: set[str] = set()

        # Get type mappings
        _type_map = self._type_mappings.get(  # noqa: F841
            (config.source_language, config.target_language), {}
        )

        # Get keyword mappings
        keyword_map = self._keyword_mappings.get(
            (config.source_language, config.target_language), {}
        )

        # Track data items for translation
        data_items: dict[str, dict[str, Any]] = {}
        in_procedure = False
        current_indent = 0

        for i, line in enumerate(lines):
            # Skip sequence numbers and comments
            if len(line) > 6:
                indicator = line[6] if len(line) > 6 else " "
                content = line[7:72] if len(line) > 7 else line

                if indicator == "*":
                    if config.preserve_comments:
                        output_lines.append(f"# {content.strip()}")
                    continue

                line = content

            stripped = line.strip().upper()

            # Track division changes
            if "PROCEDURE DIVISION" in stripped:
                in_procedure = True
                if config.target_language == TargetLanguage.PYTHON:
                    output_lines.append("")
                    output_lines.append("def main():")
                    current_indent = 1
                continue

            if not in_procedure:
                # Parse data items in DATA DIVISION
                data_match = re.match(
                    r"(\d{1,2})\s+(\w[\w\-]*)\s+PIC\s+(\S+)", stripped, re.IGNORECASE
                )
                if data_match:
                    level = int(data_match.group(1))
                    name = data_match.group(2)
                    pic = data_match.group(3)

                    target_type = self._cobol_pic_to_target_type(
                        pic, config.target_language
                    )
                    python_name = self._cobol_to_python_name(
                        name, config.naming_convention
                    )

                    data_items[name.upper()] = {
                        "level": level,
                        "pic": pic,
                        "target_name": python_name,
                        "target_type": target_type,
                    }

                    translated_file.variables.append(
                        VariableTranslation(
                            source_name=name,
                            target_name=python_name,
                            source_type=f"PIC {pic}",
                            target_type=target_type,
                            line_number=i + 1,
                        )
                    )
                continue

            # Translate procedure statements
            translated_line = self._translate_cobol_statement(
                stripped, data_items, keyword_map, config, imports_needed
            )

            if translated_line:
                indent = "    " * current_indent
                output_lines.append(f"{indent}{translated_line}")

        # Add imports at the beginning
        import_lines = self._generate_python_imports(imports_needed)
        if import_lines:
            output_lines = import_lines + [""] + output_lines

        # Add main guard for Python
        if config.target_language == TargetLanguage.PYTHON:
            output_lines.append("")
            output_lines.append("")
            output_lines.append('if __name__ == "__main__":')
            output_lines.append("    main()")

        translated_file.translated_code = "\n".join(output_lines)
        translated_file.imports = [ImportStatement(module=m) for m in imports_needed]

        return translated_file

    def _cobol_pic_to_target_type(
        self, pic: str, target_language: TargetLanguage
    ) -> str:
        """Convert COBOL PIC clause to target type."""
        pic_upper = pic.upper()

        if target_language == TargetLanguage.PYTHON:
            if "V" in pic_upper:
                return "Decimal"
            elif re.match(r"S?9+", pic_upper):
                return "int"
            elif re.match(r"X+", pic_upper):
                return "str"
            elif re.match(r"A+", pic_upper):
                return "str"
            return "str"

        elif target_language == TargetLanguage.JAVA:
            if "V" in pic_upper:
                return "BigDecimal"
            elif re.match(r"S?9+", pic_upper):
                return "int"
            elif re.match(r"X+", pic_upper):
                return "String"
            elif re.match(r"A+", pic_upper):
                return "String"
            return "String"

        return "object"

    def _cobol_to_python_name(self, name: str, convention: str) -> str:
        """Convert COBOL name to Python naming convention."""
        # Replace hyphens with underscores
        name = name.replace("-", "_")

        if convention == "snake_case":
            return name.lower()
        elif convention == "camelCase":
            parts = name.lower().split("_")
            return parts[0] + "".join(p.title() for p in parts[1:])
        elif convention == "PascalCase":
            return "".join(p.title() for p in name.lower().split("_"))

        return name.lower()

    def _translate_cobol_statement(
        self,
        statement: str,
        data_items: dict[str, dict[str, Any]],
        keyword_map: dict[str, str],
        config: TranslationConfig,
        imports: set[str],
    ) -> str:
        """Translate a single COBOL statement."""
        # MOVE statement
        move_match = re.match(
            r"MOVE\s+(.+?)\s+TO\s+(.+?)\.?$", statement, re.IGNORECASE
        )
        if move_match:
            source = move_match.group(1).strip()
            targets = [t.strip() for t in move_match.group(2).split()]

            translated_targets = []
            for target in targets:
                if target.upper() in data_items:
                    translated_targets.append(data_items[target.upper()]["target_name"])
                else:
                    translated_targets.append(
                        self._cobol_to_python_name(target, config.naming_convention)
                    )

            # Translate source value
            source_translated = self._translate_cobol_value(source, data_items, config)

            return " = ".join(translated_targets) + f" = {source_translated}"

        # DISPLAY statement
        display_match = re.match(r"DISPLAY\s+(.+?)\.?$", statement, re.IGNORECASE)
        if display_match:
            content = display_match.group(1).strip()
            # Handle multiple items
            items = re.split(r"\s+", content)
            translated_items = []
            for item in items:
                translated_items.append(
                    self._translate_cobol_value(item, data_items, config)
                )
            return f"print({', '.join(translated_items)})"

        # COMPUTE statement
        compute_match = re.match(
            r"COMPUTE\s+(\w[\w\-]*)\s*=\s*(.+?)\.?$", statement, re.IGNORECASE
        )
        if compute_match:
            target = compute_match.group(1).strip()
            expression = compute_match.group(2).strip()

            target_name = self._cobol_to_python_name(target, config.naming_convention)
            expr_translated = self._translate_cobol_expression(
                expression, data_items, config
            )

            return f"{target_name} = {expr_translated}"

        # IF statement
        if_match = re.match(r"IF\s+(.+?)\.?$", statement, re.IGNORECASE)
        if if_match:
            condition = if_match.group(1).strip()
            condition_translated = self._translate_cobol_condition(
                condition, data_items, config
            )
            return f"if {condition_translated}:"

        # PERFORM statement
        perform_match = re.match(r"PERFORM\s+(\w[\w\-]*)\.?$", statement, re.IGNORECASE)
        if perform_match:
            para_name = perform_match.group(1).strip()
            func_name = self._cobol_to_python_name(para_name, config.naming_convention)
            return f"{func_name}()"

        # STOP RUN
        if "STOP RUN" in statement:
            imports.add("sys")
            return "sys.exit(0)"

        # Paragraph header
        para_match = re.match(r"(\w[\w\-]*)\.?$", statement)
        if para_match and not any(
            kw in statement for kw in ["MOVE", "ADD", "IF", "PERFORM", "DISPLAY"]
        ):
            func_name = self._cobol_to_python_name(
                para_match.group(1), config.naming_convention
            )
            return f"\ndef {func_name}():"

        return ""

    def _translate_cobol_value(
        self,
        value: str,
        data_items: dict[str, dict[str, Any]],
        config: TranslationConfig,
    ) -> str:
        """Translate a COBOL value reference."""
        value_upper = value.upper().strip()

        # Check for known data items
        if value_upper in data_items:
            return str(data_items[value_upper]["target_name"])

        # Handle literals
        if value.startswith('"') or value.startswith("'"):
            return value

        # Handle figurative constants
        if value_upper == "SPACES" or value_upper == "SPACE":
            return "' '"
        if value_upper == "ZEROS" or value_upper == "ZEROES" or value_upper == "ZERO":
            return "0"
        if value_upper == "HIGH-VALUES" or value_upper == "HIGH-VALUE":
            return "chr(255)"
        if value_upper == "LOW-VALUES" or value_upper == "LOW-VALUE":
            return "chr(0)"

        # Numeric literal
        if re.match(r"^-?\d+\.?\d*$", value):
            return value

        return self._cobol_to_python_name(value, config.naming_convention)

    def _translate_cobol_expression(
        self,
        expression: str,
        data_items: dict[str, dict[str, Any]],
        config: TranslationConfig,
    ) -> str:
        """Translate a COBOL arithmetic expression."""
        # Tokenize
        tokens = re.findall(r"[\w\-]+|[+\-*/()]", expression)
        translated_tokens = []

        for token in tokens:
            if token in "+-*/()":
                translated_tokens.append(token)
            else:
                translated_tokens.append(
                    self._translate_cobol_value(token, data_items, config)
                )

        return " ".join(translated_tokens)

    def _translate_cobol_condition(
        self,
        condition: str,
        data_items: dict[str, dict[str, Any]],
        config: TranslationConfig,
    ) -> str:
        """Translate a COBOL condition."""
        # Replace COBOL operators
        condition = re.sub(r"\bEQUAL(?:\s+TO)?\b", "==", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\bGREATER\s+THAN\b", ">", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\bLESS\s+THAN\b", "<", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\bNOT\s+EQUAL\b", "!=", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\bAND\b", "and", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\bOR\b", "or", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\bNOT\b", "not", condition, flags=re.IGNORECASE)

        # Translate variable references
        words = re.findall(r"\b[\w\-]+\b", condition)
        for word in words:
            if word.upper() in data_items:
                condition = re.sub(
                    rf"\b{re.escape(word)}\b",
                    data_items[word.upper()]["target_name"],
                    condition,
                    flags=re.IGNORECASE,
                )

        return condition

    def _generate_python_imports(self, imports: set[str]) -> list[str]:
        """Generate Python import statements."""
        lines = []

        standard_libs = {"sys", "os", "re", "math", "datetime", "json"}
        third_party = {"decimal": "from decimal import Decimal"}

        for imp in sorted(imports):
            if imp in standard_libs:
                lines.append(f"import {imp}")
            elif imp in third_party:
                lines.append(third_party[imp])

        return lines

    async def _translate_vbnet(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate VB.NET to C#."""
        output_lines = []
        keyword_map = self._keyword_mappings.get(
            (config.source_language, config.target_language), {}
        )

        # Get pattern translators
        pattern_translators = self._pattern_translators.get(
            (config.source_language, config.target_language), []
        )

        for line in source_code.split("\n"):
            translated = line

            # Apply pattern translators
            for pattern, replacement in pattern_translators:
                translated = pattern.sub(replacement, translated)

            # Apply keyword mappings
            for vb_keyword, cs_keyword in keyword_map.items():
                translated = re.sub(
                    rf"\b{re.escape(vb_keyword)}\b",
                    cs_keyword,
                    translated,
                    flags=re.IGNORECASE,
                )

            # Handle specific VB.NET to C# transformations
            # String comparison
            translated = re.sub(r'(\w+)\s*=\s*"([^"]*)"', r'\1 == "\2"', translated)

            # Add semicolons (if not a control structure)
            if (
                translated.strip()
                and not translated.strip().endswith("{")
                and not translated.strip().endswith("}")
            ):
                if not any(
                    kw in translated.lower()
                    for kw in [
                        "if",
                        "else",
                        "for",
                        "while",
                        "try",
                        "catch",
                        "finally",
                        "switch",
                        "case",
                    ]
                ):
                    if not translated.strip().endswith(";"):
                        translated = translated.rstrip() + ";"

            output_lines.append(translated)

        translated_file.translated_code = "\n".join(output_lines)
        return translated_file

    async def _translate_java(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate Java to target language."""
        if config.target_language == TargetLanguage.PYTHON:
            return await self._translate_java_to_python(
                source_code, config, translated_file
            )
        elif config.target_language == TargetLanguage.KOTLIN:
            return await self._translate_java_to_kotlin(
                source_code, config, translated_file
            )

        return translated_file

    async def _translate_java_to_python(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate Java to Python."""
        output_lines = []
        keyword_map = self._keyword_mappings.get(
            (config.source_language, config.target_language), {}
        )
        pattern_translators = self._pattern_translators.get(
            (config.source_language, config.target_language), []
        )

        indent_level = 0
        _in_class = False  # noqa: F841

        for line in source_code.split("\n"):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                output_lines.append("")
                continue

            translated = line

            # Apply pattern translators
            for pattern, replacement in pattern_translators:
                translated = pattern.sub(replacement, translated)

            # Apply keyword mappings
            for java_keyword, py_keyword in keyword_map.items():
                translated = re.sub(
                    rf"\b{re.escape(java_keyword)}\b", py_keyword, translated
                )

            # Handle braces
            if "{" in translated:
                translated = translated.replace("{", ":").rstrip(":")
                if translated.strip().endswith(":"):
                    pass
                else:
                    translated = translated.rstrip() + ":"
                indent_level += 1
            if "}" in stripped:
                indent_level = max(0, indent_level - 1)
                continue  # Skip closing braces

            # Remove semicolons
            translated = translated.rstrip(";")

            # Fix method signatures
            if "def " in translated and "(self," in translated:
                # Already processed
                pass

            # Add proper indentation
            if translated.strip():
                current_indent = "    " * indent_level
                output_lines.append(current_indent + translated.strip())
            else:
                output_lines.append("")

        translated_file.translated_code = "\n".join(output_lines)
        return translated_file

    async def _translate_java_to_kotlin(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate Java to Kotlin."""
        output_lines = []
        type_map = self._type_mappings.get(
            (config.source_language, config.target_language), {}
        )

        for line in source_code.split("\n"):
            translated = line

            # Class definition
            translated = re.sub(r"public\s+class\s+(\w+)", r"class \1", translated)

            # Method definition
            translated = re.sub(
                r"(?:public|private|protected)?\s*(?:static\s+)?(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{",
                lambda m: f"fun {str(m.group(2))}({self._java_params_to_kotlin(str(m.group(3)))}): {type_map.get(str(m.group(1)), TypeMapping(str(m.group(1)), str(m.group(1)), False)).target_type} {{",
                translated,
            )

            # Variable declarations
            translated = re.sub(
                r"(?:final\s+)?(\w+)\s+(\w+)\s*=",
                lambda m: f"val {str(m.group(2))}: {type_map.get(str(m.group(1)), TypeMapping(str(m.group(1)), str(m.group(1)), False)).target_type} =",
                translated,
            )

            # null to null (same in Kotlin)
            # true/false (same in Kotlin)

            output_lines.append(translated)

        translated_file.translated_code = "\n".join(output_lines)
        return translated_file

    def _java_params_to_kotlin(self, params: str) -> str:
        """Convert Java parameters to Kotlin format."""
        if not params.strip():
            return ""

        type_map = self._type_mappings.get(
            (SourceLanguage.JAVA, TargetLanguage.KOTLIN), {}
        )

        kotlin_params = []
        for param in params.split(","):
            param = param.strip()
            if not param:
                continue

            parts = param.split()
            if len(parts) >= 2:
                java_type = parts[0]
                name = parts[1]
                kotlin_type = type_map.get(
                    java_type, TypeMapping(java_type, java_type, False)
                ).target_type
                kotlin_params.append(f"{name}: {kotlin_type}")

        return ", ".join(kotlin_params)

    async def _translate_csharp(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate C# to target language."""
        if config.target_language == TargetLanguage.PYTHON:
            return await self._translate_csharp_to_python(
                source_code, config, translated_file
            )

        return translated_file

    async def _translate_csharp_to_python(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Translate C# to Python."""
        output_lines = []
        _type_map = self._type_mappings.get(  # noqa: F841
            (config.source_language, config.target_language), {}
        )

        indent_level = 0

        for line in source_code.split("\n"):
            stripped = line.strip()

            if not stripped:
                output_lines.append("")
                continue

            translated = line

            # Using to import
            translated = re.sub(r"using\s+([\w.]+);", r"# import \1", translated)

            # Class definition
            translated = re.sub(
                r"(?:public|private|internal)?\s*(?:static\s+)?class\s+(\w+)(?:\s*:\s*(\w+))?",
                lambda m: (
                    f"class {str(m.group(1))}({str(m.group(2)) or 'object'}):"
                    if m.group(2)
                    else f"class {str(m.group(1))}:"
                ),
                translated,
            )

            # Method definition
            translated = re.sub(
                r"(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(\w+)\s+(\w+)\s*\(([^)]*)\)",
                lambda m: f"def {self._to_snake_case(str(m.group(2)))}(self{', ' + self._csharp_params_to_python(str(m.group(3))) if str(m.group(3)).strip() else ''}):",
                translated,
            )

            # Property to method
            translated = re.sub(
                r"(?:public|private|protected)\s+(\w+)\s+(\w+)\s*\{\s*get;\s*set;\s*\}",
                lambda m: f"# @property\n# def {self._to_snake_case(str(m.group(2)))}(self): pass",
                translated,
            )

            # Variable declaration
            translated = re.sub(
                r"(?:var|(\w+))\s+(\w+)\s*=",
                lambda m: f"{self._to_snake_case(str(m.group(2)))} =",
                translated,
            )

            # null -> None
            translated = re.sub(r"\bnull\b", "None", translated)

            # true/false
            translated = re.sub(r"\btrue\b", "True", translated)
            translated = re.sub(r"\bfalse\b", "False", translated)

            # this -> self
            translated = re.sub(r"\bthis\.", "self.", translated)

            # Handle braces
            if "{" in stripped and "}" not in stripped:
                indent_level += 1
                translated = translated.replace("{", "").rstrip()
                if not translated.strip().endswith(":"):
                    translated = translated.rstrip() + ":"
            elif "}" in stripped:
                indent_level = max(0, indent_level - 1)
                continue

            # Remove semicolons
            translated = translated.rstrip(";")

            if translated.strip():
                current_indent = "    " * indent_level
                output_lines.append(current_indent + translated.strip())
            else:
                output_lines.append("")

        translated_file.translated_code = "\n".join(output_lines)
        return translated_file

    def _to_snake_case(self, name: str) -> str:
        """Convert PascalCase/camelCase to snake_case."""
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def _csharp_params_to_python(self, params: str) -> str:
        """Convert C# parameters to Python format."""
        if not params.strip():
            return ""

        python_params = []
        for param in params.split(","):
            param = param.strip()
            if not param:
                continue

            parts = param.split()
            if len(parts) >= 2:
                name = parts[-1]
                python_params.append(self._to_snake_case(name))

        return ", ".join(python_params)

    async def _translate_generic(
        self,
        source_code: str,
        config: TranslationConfig,
        translated_file: TranslatedFile,
    ) -> TranslatedFile:
        """Generic translation using keyword and type mappings."""
        translated_file.translated_code = source_code
        translated_file.warnings.append(
            TranslationWarning(
                location="translation",
                message=f"No specific translator for {config.source_language.value} to {config.target_language.value}",
                severity="warning",
                suggestion="Consider using idiomatic translation or manual review",
            )
        )
        translated_file.manual_review_items.append(
            ManualReviewItem(
                location="entire_file",
                original_code=source_code[:500],
                translated_code="",
                reason="No specific translator available",
                suggestions=["Manual translation required"],
            )
        )
        return translated_file

    def _assess_complexity(self, translated_file: TranslatedFile) -> ComplexityLevel:
        """Assess translation complexity."""
        # Based on warnings and review items
        warning_count = len(translated_file.warnings)
        review_count = len(translated_file.manual_review_items)

        if warning_count == 0 and review_count == 0:
            return ComplexityLevel.SIMPLE
        elif warning_count <= 3 and review_count <= 1:
            return ComplexityLevel.MODERATE
        elif warning_count <= 10 and review_count <= 5:
            return ComplexityLevel.COMPLEX
        return ComplexityLevel.EXPERT

    def _assess_confidence(self, translated_file: TranslatedFile) -> ConfidenceLevel:
        """Assess translation confidence."""
        if len(translated_file.manual_review_items) == 0:
            if len(translated_file.warnings) == 0:
                return ConfidenceLevel.HIGH
            elif len(translated_file.warnings) <= 3:
                return ConfidenceLevel.MEDIUM
        elif len(translated_file.manual_review_items) <= 2:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.UNCERTAIN

    def _get_used_type_mappings(
        self, source_lang: SourceLanguage, target_lang: TargetLanguage
    ) -> list[TypeMapping]:
        """Get type mappings used for a language pair."""
        mappings = self._type_mappings.get((source_lang, target_lang), {})
        return list(mappings.values())

    async def _generate_test_cases(
        self, translated_file: TranslatedFile, config: TranslationConfig
    ) -> list[TranslationTestCase]:
        """Generate test cases for translated code."""
        test_cases = []

        for func in translated_file.functions:
            test_case = TranslationTestCase(
                name=f"test_{func.target_name}",
                description=f"Test case for {func.source_name} -> {func.target_name}",
                original_function=func.source_name,
                translated_function=func.target_name,
            )

            # Generate basic test code based on target language
            if config.target_language == TargetLanguage.PYTHON:
                test_case.test_code = f"""
def test_{func.target_name}():
    # TODO: Add test assertions
    # Original: {func.source_name}
    # result = {func.target_name}(...)
    # assert result == expected
    pass
"""
            elif config.target_language == TargetLanguage.JAVA:
                test_case.test_code = f"""
@Test
public void test{func.target_name.title()}() {{
    // TODO: Add test assertions
    // Original: {func.source_name}
    // assertEquals(expected, result);
}}
"""

            test_cases.append(test_case)

        return test_cases

    async def get_supported_translations(self) -> list[dict[str, str]]:
        """Get list of supported translation pairs."""
        supported = []

        for source_lang, target_lang in self._type_mappings.keys():
            supported.append(
                {
                    "source": source_lang.value,
                    "target": target_lang.value,
                    "quality": (
                        "high"
                        if (source_lang, target_lang) in self._pattern_translators
                        else "medium"
                    ),
                }
            )

        return supported

    async def analyze_translation_difficulty(
        self,
        source_code: str,
        source_language: SourceLanguage,
        target_language: TargetLanguage,
    ) -> dict[str, Any]:
        """Analyze difficulty of translating source code."""
        lines = source_code.split("\n")
        code_lines = [
            line
            for line in lines
            if line.strip()
            and not line.strip().startswith("//")
            and not line.strip().startswith("#")
        ]

        # Check for complex constructs
        has_generics = bool(re.search(r"<[\w,\s]+>", source_code))
        has_lambdas = bool(re.search(r"=>|->|lambda", source_code))
        has_async = bool(re.search(r"\basync\b|\bawait\b", source_code))
        has_reflection = bool(re.search(r"typeof|GetType|Reflection", source_code))
        has_pointers = bool(re.search(r"\*|\->|unsafe", source_code))

        complexity_score = sum(
            [
                has_generics * 2,
                has_lambdas * 2,
                has_async * 3,
                has_reflection * 4,
                has_pointers * 5,
                len(code_lines) > 500,
                len(code_lines) > 1000,
            ]
        )

        if complexity_score <= 2:
            difficulty = "easy"
        elif complexity_score <= 5:
            difficulty = "moderate"
        elif complexity_score <= 8:
            difficulty = "hard"
        else:
            difficulty = "expert"

        return {
            "difficulty": difficulty,
            "complexity_score": complexity_score,
            "source_lines": len(lines),
            "code_lines": len(code_lines),
            "has_generics": has_generics,
            "has_lambdas": has_lambdas,
            "has_async": has_async,
            "has_reflection": has_reflection,
            "has_pointers": has_pointers,
            "estimated_manual_review_items": complexity_score * 2,
            "recommended_strategy": (
                TranslationStrategy.IDIOMATIC
                if complexity_score < 5
                else TranslationStrategy.LITERAL
            ),
        }
