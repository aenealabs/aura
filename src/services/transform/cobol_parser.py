"""
COBOL Parser - AWS Transform Agent Parity

Enterprise COBOL code analysis and parsing for legacy modernization.
Provides deep understanding of COBOL programs including data divisions,
procedure divisions, copybooks, and complex control flow.

Reference: ADR-030 Section 5.4 Transform Agent Components
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class COBOLDivision(str, Enum):
    """COBOL program divisions."""

    IDENTIFICATION = "identification"
    ENVIRONMENT = "environment"
    DATA = "data"
    PROCEDURE = "procedure"


class DataItemType(str, Enum):
    """Types of COBOL data items."""

    GROUP = "group"
    ELEMENTARY = "elementary"
    OCCURS = "occurs"
    REDEFINES = "redefines"
    FILLER = "filler"
    CONDITION = "condition"


class DataSection(str, Enum):
    """COBOL data division sections."""

    FILE = "file"
    WORKING_STORAGE = "working_storage"
    LOCAL_STORAGE = "local_storage"
    LINKAGE = "linkage"
    SCREEN = "screen"
    REPORT = "report"


class StatementType(str, Enum):
    """COBOL procedure statement types."""

    MOVE = "move"
    COMPUTE = "compute"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    IF = "if"
    EVALUATE = "evaluate"
    PERFORM = "perform"
    CALL = "call"
    READ = "read"
    WRITE = "write"
    REWRITE = "rewrite"
    DELETE = "delete"
    START = "start"
    OPEN = "open"
    CLOSE = "close"
    DISPLAY = "display"
    ACCEPT = "accept"
    STRING = "string"
    UNSTRING = "unstring"
    INSPECT = "inspect"
    INITIALIZE = "initialize"
    SET = "set"
    GO_TO = "go_to"
    STOP = "stop"
    EXIT = "exit"
    CONTINUE = "continue"
    EXEC_SQL = "exec_sql"
    EXEC_CICS = "exec_cics"
    COPY = "copy"
    UNKNOWN = "unknown"


class PictureCategory(str, Enum):
    """COBOL PICTURE clause categories."""

    NUMERIC = "numeric"
    ALPHABETIC = "alphabetic"
    ALPHANUMERIC = "alphanumeric"
    NUMERIC_EDITED = "numeric_edited"
    ALPHANUMERIC_EDITED = "alphanumeric_edited"
    EXTERNAL_FLOAT = "external_float"
    NATIONAL = "national"
    DBCS = "dbcs"


class FileOrganization(str, Enum):
    """COBOL file organization types."""

    SEQUENTIAL = "sequential"
    INDEXED = "indexed"
    RELATIVE = "relative"
    LINE_SEQUENTIAL = "line_sequential"


class AccessMode(str, Enum):
    """COBOL file access modes."""

    SEQUENTIAL = "sequential"
    RANDOM = "random"
    DYNAMIC = "dynamic"


class Complexity(str, Enum):
    """Code complexity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class PictureClause:
    """Parsed COBOL PICTURE clause."""

    raw: str
    category: PictureCategory
    size: int
    decimal_positions: int = 0
    signed: bool = False
    usage: str = "display"

    @property
    def python_type(self) -> str:
        """Get equivalent Python type."""
        if self.category == PictureCategory.NUMERIC:
            if self.decimal_positions > 0:
                return "Decimal"
            return "int"
        elif self.category == PictureCategory.ALPHABETIC:
            return "str"
        return "str"


@dataclass
class DataItem:
    """COBOL data item definition."""

    name: str
    level: int
    item_type: DataItemType
    section: DataSection
    picture: PictureClause | None = None
    occurs: int | None = None
    occurs_depending: str | None = None
    redefines: str | None = None
    value: str | None = None
    children: list["DataItem"] = field(default_factory=list)
    parent: str | None = None
    line_number: int = 0
    byte_offset: int = 0
    byte_length: int = 0

    @property
    def full_path(self) -> str:
        """Get fully qualified name."""
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name


@dataclass
class Copybook:
    """COBOL copybook reference."""

    name: str
    library: str | None = None
    replacing: dict[str, str] = field(default_factory=dict)
    suppress: bool = False
    line_number: int = 0
    data_items: list[DataItem] = field(default_factory=list)


@dataclass
class FileDefinition:
    """COBOL file definition."""

    name: str
    file_name: str
    organization: FileOrganization
    access_mode: AccessMode
    record_key: str | None = None
    alternate_keys: list[str] = field(default_factory=list)
    record_size: int | None = None
    block_size: int | None = None
    record_definition: DataItem | None = None
    line_number: int = 0


@dataclass
class Paragraph:
    """COBOL paragraph definition."""

    name: str
    section: str | None = None
    statements: list["Statement"] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    called_by: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    @property
    def cyclomatic_complexity(self) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1
        for stmt in self.statements:
            if stmt.statement_type in [
                StatementType.IF,
                StatementType.EVALUATE,
                StatementType.PERFORM,
            ]:
                complexity += 1
            if stmt.statement_type == StatementType.EVALUATE:
                complexity += len(stmt.metadata.get("when_clauses", []))
        return complexity


@dataclass
class Section:
    """COBOL section definition."""

    name: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class Statement:
    """COBOL procedure statement."""

    statement_type: StatementType
    raw_text: str
    line_number: int
    variables_read: list[str] = field(default_factory=list)
    variables_written: list[str] = field(default_factory=list)
    called_paragraphs: list[str] = field(default_factory=list)
    called_programs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SQLStatement:
    """Embedded SQL statement."""

    operation: str
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    host_variables: list[str] = field(default_factory=list)
    cursor_name: str | None = None
    raw_sql: str = ""
    line_number: int = 0


@dataclass
class CICSCommand:
    """Embedded CICS command."""

    command: str
    options: dict[str, str] = field(default_factory=dict)
    line_number: int = 0


@dataclass
class ProgramDependency:
    """External program dependency."""

    program_name: str
    call_type: str
    parameters: list[str] = field(default_factory=list)
    line_numbers: list[int] = field(default_factory=list)


@dataclass
class DataFlow:
    """Data flow analysis result."""

    source: str
    target: str
    statement_type: StatementType
    line_number: int
    transformation: str | None = None


@dataclass
class COBOLProgram:
    """Parsed COBOL program representation."""

    program_id: str
    source_file: str

    # Divisions
    identification: dict[str, str] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)

    # Data structures
    data_items: list[DataItem] = field(default_factory=list)
    copybooks: list[Copybook] = field(default_factory=list)
    files: list[FileDefinition] = field(default_factory=list)

    # Procedure division
    sections: list[Section] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)

    # External interfaces
    sql_statements: list[SQLStatement] = field(default_factory=list)
    cics_commands: list[CICSCommand] = field(default_factory=list)
    program_dependencies: list[ProgramDependency] = field(default_factory=list)

    # Analysis results
    data_flows: list[DataFlow] = field(default_factory=list)

    # Metadata
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    parse_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_hash: str = ""

    @property
    def complexity(self) -> Complexity:
        """Overall program complexity assessment."""
        total_complexity = sum(p.cyclomatic_complexity for p in self.paragraphs)
        avg_complexity = total_complexity / max(len(self.paragraphs), 1)

        if avg_complexity < 5:
            return Complexity.LOW
        elif avg_complexity < 10:
            return Complexity.MEDIUM
        elif avg_complexity < 20:
            return Complexity.HIGH
        return Complexity.VERY_HIGH

    @property
    def has_db2(self) -> bool:
        """Check if program uses DB2."""
        return len(self.sql_statements) > 0

    @property
    def has_cics(self) -> bool:
        """Check if program uses CICS."""
        return len(self.cics_commands) > 0


@dataclass
class ParseError:
    """COBOL parse error."""

    line_number: int
    column: int
    message: str
    severity: str
    context: str = ""


@dataclass
class ParseResult:
    """Result of COBOL parsing."""

    success: bool
    program: COBOLProgram | None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)
    parse_duration_ms: float = 0


class COBOLParser:
    """
    Enterprise COBOL parser for legacy modernization.

    Provides comprehensive parsing of COBOL programs including:
    - All four divisions (Identification, Environment, Data, Procedure)
    - Data item hierarchy and PICTURE clause analysis
    - Copybook expansion
    - Embedded SQL (DB2) parsing
    - CICS command parsing
    - Control flow analysis
    - Data flow tracking
    """

    def __init__(self) -> None:
        """Initialize COBOL parser."""
        self._statement_patterns = self._build_statement_patterns()
        self._picture_patterns = self._build_picture_patterns()

    def _build_statement_patterns(self) -> dict[StatementType, re.Pattern]:
        """Build regex patterns for statement recognition."""
        return {
            StatementType.MOVE: re.compile(
                r"^\s*MOVE\s+(.+?)\s+TO\s+(.+?)\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
            StatementType.COMPUTE: re.compile(
                r"^\s*COMPUTE\s+(.+?)\s*=\s*(.+?)\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
            StatementType.IF: re.compile(
                r"^\s*IF\s+(.+?)\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
            StatementType.EVALUATE: re.compile(
                r"^\s*EVALUATE\s+(.+?)\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
            StatementType.PERFORM: re.compile(
                r"^\s*PERFORM\s+(.+?)\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
            StatementType.CALL: re.compile(
                r"^\s*CALL\s+['\"]?(\w+)['\"]?\s*(USING\s+(.+?))?\.?\s*$",
                re.IGNORECASE | re.DOTALL,
            ),
            StatementType.READ: re.compile(r"^\s*READ\s+(\w+)", re.IGNORECASE),
            StatementType.WRITE: re.compile(r"^\s*WRITE\s+(\w+)", re.IGNORECASE),
            StatementType.EXEC_SQL: re.compile(
                r"^\s*EXEC\s+SQL\s+(.+?)\s*END-EXEC\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
            StatementType.EXEC_CICS: re.compile(
                r"^\s*EXEC\s+CICS\s+(.+?)\s*END-EXEC\.?\s*$", re.IGNORECASE | re.DOTALL
            ),
        }

    def _build_picture_patterns(self) -> dict[str, re.Pattern]:
        """Build regex patterns for PICTURE clause parsing."""
        return {
            "numeric": re.compile(r"^[S]?9+(\([0-9]+\))?(V9+(\([0-9]+\))?)?$"),
            "alpha": re.compile(r"^A+(\([0-9]+\))?$"),
            "alphanum": re.compile(r"^X+(\([0-9]+\))?$"),
            "edited": re.compile(r".*[Z\$\*\-\+,\.].*"),
        }

    async def parse(
        self,
        source_code: str,
        source_file: str = "unknown.cbl",
        expand_copybooks: bool = True,
        copybook_resolver: Any = None,
    ) -> ParseResult:
        """
        Parse COBOL source code.

        Args:
            source_code: COBOL source code
            source_file: Source file name
            expand_copybooks: Whether to expand copybook references
            copybook_resolver: Optional function to resolve copybook contents

        Returns:
            ParseResult with parsed program or errors
        """
        start_time = datetime.now(timezone.utc)
        errors: list[ParseError] = []
        warnings: list[ParseError] = []

        # Normalize source code
        lines = self._normalize_source(source_code)

        # Calculate source hash
        source_hash = hashlib.sha256(source_code.encode()).hexdigest()[:16]

        # Initialize program
        program = COBOLProgram(
            program_id="",
            source_file=source_file,
            source_hash=source_hash,
            total_lines=len(lines),
        )

        # Parse divisions
        division_ranges = self._identify_divisions(lines)

        # Parse Identification Division
        if COBOLDivision.IDENTIFICATION in division_ranges:
            start, end = division_ranges[COBOLDivision.IDENTIFICATION]
            program.identification = self._parse_identification_division(
                lines[start:end]
            )
            program.program_id = program.identification.get("PROGRAM-ID", "UNKNOWN")

        # Parse Environment Division
        if COBOLDivision.ENVIRONMENT in division_ranges:
            start, end = division_ranges[COBOLDivision.ENVIRONMENT]
            program.environment = self._parse_environment_division(lines[start:end])

        # Parse Data Division
        if COBOLDivision.DATA in division_ranges:
            start, end = division_ranges[COBOLDivision.DATA]
            data_result = await self._parse_data_division(
                lines[start:end], start, expand_copybooks, copybook_resolver
            )
            program.data_items = data_result["items"]
            program.copybooks = data_result["copybooks"]
            program.files = data_result["files"]
            errors.extend(data_result["errors"])

        # Parse Procedure Division
        if COBOLDivision.PROCEDURE in division_ranges:
            start, end = division_ranges[COBOLDivision.PROCEDURE]
            proc_result = self._parse_procedure_division(lines[start:end], start)
            program.sections = proc_result["sections"]
            program.paragraphs = proc_result["paragraphs"]
            program.sql_statements = proc_result["sql"]
            program.cics_commands = proc_result["cics"]
            program.program_dependencies = proc_result["dependencies"]
            errors.extend(proc_result["errors"])

        # Perform data flow analysis
        program.data_flows = self._analyze_data_flow(program)

        # Build call graph
        self._build_call_graph(program)

        # Count lines
        program.code_lines = sum(
            1 for line in lines if line.strip() and not self._is_comment(line)
        )
        program.comment_lines = sum(1 for line in lines if self._is_comment(line))

        # Calculate parse duration
        parse_duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        return ParseResult(
            success=len(errors) == 0,
            program=program,
            errors=errors,
            warnings=warnings,
            parse_duration_ms=parse_duration,
        )

    def _normalize_source(self, source: str) -> list[str]:
        """Normalize COBOL source handling fixed/free format."""
        lines = source.split("\n")
        normalized = []

        for line in lines:
            # Handle sequence numbers (columns 1-6)
            if len(line) > 6:
                # Check for indicator in column 7
                indicator = line[6] if len(line) > 6 else " "
                content = line[7:72] if len(line) > 7 else ""

                if indicator == "*" or indicator == "/":
                    # Comment line
                    normalized.append(f"*{content}")
                elif indicator == "-":
                    # Continuation line
                    if normalized:
                        normalized[-1] = normalized[-1].rstrip() + content.lstrip()
                    else:
                        normalized.append(content)
                else:
                    normalized.append(content)
            else:
                normalized.append(line)

        return normalized

    def _is_comment(self, line: str) -> bool:
        """Check if line is a comment."""
        stripped = line.strip()
        return stripped.startswith("*") or stripped.startswith("/")

    def _identify_divisions(
        self, lines: list[str]
    ) -> dict[COBOLDivision, tuple[int, int]]:
        """Identify division boundaries in source."""
        divisions = {}
        current_division = None
        division_start = 0

        for i, line in enumerate(lines):
            upper_line = line.upper().strip()

            if "IDENTIFICATION DIVISION" in upper_line:
                if current_division:
                    divisions[current_division] = (division_start, i)
                current_division = COBOLDivision.IDENTIFICATION
                division_start = i
            elif "ENVIRONMENT DIVISION" in upper_line:
                if current_division:
                    divisions[current_division] = (division_start, i)
                current_division = COBOLDivision.ENVIRONMENT
                division_start = i
            elif "DATA DIVISION" in upper_line:
                if current_division:
                    divisions[current_division] = (division_start, i)
                current_division = COBOLDivision.DATA
                division_start = i
            elif "PROCEDURE DIVISION" in upper_line:
                if current_division:
                    divisions[current_division] = (division_start, i)
                current_division = COBOLDivision.PROCEDURE
                division_start = i

        if current_division:
            divisions[current_division] = (division_start, len(lines))

        return divisions

    def _parse_identification_division(self, lines: list[str]) -> dict[str, str]:
        """Parse Identification Division."""
        identification = {}

        for line in lines:
            if self._is_comment(line):
                continue

            upper_line = line.upper().strip()

            # Parse common identification entries
            for keyword in [
                "PROGRAM-ID",
                "AUTHOR",
                "INSTALLATION",
                "DATE-WRITTEN",
                "DATE-COMPILED",
                "SECURITY",
            ]:
                if keyword in upper_line:
                    # Extract value after keyword
                    parts = line.split(".", 1)
                    if len(parts) > 0:
                        value_part = parts[0]
                        if keyword in value_part.upper():
                            idx = value_part.upper().index(keyword)
                            value = value_part[idx + len(keyword) :].strip()
                            # Remove leading period or IS
                            value = re.sub(
                                r"^[\s\.]*IS\s*", "", value, flags=re.IGNORECASE
                            )
                            value = value.strip(" .")
                            identification[keyword] = value

        return identification

    def _parse_environment_division(self, lines: list[str]) -> dict[str, Any]:
        """Parse Environment Division."""
        environment: dict[str, Any] = {"configuration": {}, "input_output": {}}

        current_section = None

        for line in lines:
            if self._is_comment(line):
                continue

            upper_line = line.upper().strip()

            if "CONFIGURATION SECTION" in upper_line:
                current_section = "configuration"
            elif "INPUT-OUTPUT SECTION" in upper_line:
                current_section = "input_output"
            elif current_section == "configuration":
                if "SOURCE-COMPUTER" in upper_line:
                    environment["configuration"]["source_computer"] = (
                        self._extract_value(line, "SOURCE-COMPUTER")
                    )
                elif "OBJECT-COMPUTER" in upper_line:
                    environment["configuration"]["object_computer"] = (
                        self._extract_value(line, "OBJECT-COMPUTER")
                    )

        return environment

    def _extract_value(self, line: str, keyword: str) -> str:
        """Extract value after a keyword."""
        idx = line.upper().index(keyword)
        value = line[idx + len(keyword) :].strip()
        return value.strip(" .")

    async def _parse_data_division(
        self,
        lines: list[str],
        line_offset: int,
        expand_copybooks: bool,
        copybook_resolver: Any,
    ) -> dict[str, Any]:
        """Parse Data Division."""
        result: dict[str, Any] = {
            "items": [],
            "copybooks": [],
            "files": [],
            "errors": [],
        }

        current_section = DataSection.WORKING_STORAGE
        item_stack: list[DataItem] = []
        byte_offset = 0

        for i, line in enumerate(lines):
            if self._is_comment(line):
                continue

            upper_line = line.upper().strip()
            actual_line = line_offset + i

            # Check for section changes
            if "FILE SECTION" in upper_line:
                current_section = DataSection.FILE
                continue
            elif "WORKING-STORAGE SECTION" in upper_line:
                current_section = DataSection.WORKING_STORAGE
                continue
            elif "LOCAL-STORAGE SECTION" in upper_line:
                current_section = DataSection.LOCAL_STORAGE
                continue
            elif "LINKAGE SECTION" in upper_line:
                current_section = DataSection.LINKAGE
                continue

            # Check for COPY statement
            if upper_line.startswith("COPY"):
                copybook = self._parse_copy_statement(line, actual_line)
                if copybook:
                    result["copybooks"].append(copybook)

                    if expand_copybooks and copybook_resolver:
                        try:
                            copybook_source = await copybook_resolver(
                                copybook.name, copybook.library
                            )
                            if copybook_source:
                                # Apply REPLACING if specified
                                for old, new in copybook.replacing.items():
                                    copybook_source = copybook_source.replace(old, new)

                                # Recursively parse copybook
                                cb_result = await self._parse_data_division(
                                    copybook_source.split("\n"),
                                    0,
                                    expand_copybooks,
                                    copybook_resolver,
                                )
                                copybook.data_items = cb_result["items"]
                                result["items"].extend(cb_result["items"])
                        except Exception:
                            pass
                continue

            # Parse data item
            item = self._parse_data_item(line, current_section, actual_line)
            if item:
                # Calculate byte offset and length
                item.byte_offset = byte_offset
                if item.picture:
                    item.byte_length = item.picture.size
                    if item.occurs:
                        item.byte_length *= item.occurs
                    byte_offset += item.byte_length

                # Handle hierarchy
                while item_stack and item_stack[-1].level >= item.level:
                    item_stack.pop()

                if item_stack:
                    item.parent = item_stack[-1].name
                    item_stack[-1].children.append(item)

                item_stack.append(item)
                result["items"].append(item)

        # Parse FD entries for files
        result["files"] = self._parse_file_definitions(lines, line_offset)

        return result

    def _parse_copy_statement(self, line: str, line_number: int) -> Copybook | None:
        """Parse COPY statement."""
        pattern = re.compile(
            r"COPY\s+(\w+)(?:\s+(?:OF|IN)\s+(\w+))?(?:\s+REPLACING\s+(.+?))?(?:\s+SUPPRESS)?\.?",
            re.IGNORECASE,
        )
        match = pattern.search(line)

        if not match:
            return None

        copybook = Copybook(
            name=match.group(1), library=match.group(2), line_number=line_number
        )

        # Parse REPLACING clause
        if match.group(3):
            replacing_text = match.group(3)
            # Pattern: ==old== BY ==new==
            replace_pattern = re.compile(r"==(.+?)==\s+BY\s+==(.+?)==")
            for rm in replace_pattern.finditer(replacing_text):
                copybook.replacing[rm.group(1)] = rm.group(2)

        if "SUPPRESS" in line.upper():
            copybook.suppress = True

        return copybook

    def _parse_data_item(
        self, line: str, section: DataSection, line_number: int
    ) -> DataItem | None:
        """Parse a single data item definition."""
        # Pattern for data item
        pattern = re.compile(
            r"^\s*(\d{1,2})\s+(\w[\w\-]*|\s*FILLER)(.*)\.?\s*$", re.IGNORECASE
        )
        match = pattern.match(line)

        if not match:
            return None

        level = int(match.group(1))
        name = match.group(2).strip()
        rest = match.group(3)

        # Determine item type
        item_type = DataItemType.ELEMENTARY
        if name.upper() == "FILLER":
            item_type = DataItemType.FILLER
        elif level == 88:
            item_type = DataItemType.CONDITION

        item = DataItem(
            name=name,
            level=level,
            item_type=item_type,
            section=section,
            line_number=line_number,
        )

        # Parse PICTURE clause
        pic_match = re.search(
            r"(?:PIC|PICTURE)\s+IS\s+(\S+)|(?:PIC|PICTURE)\s+(\S+)", rest, re.IGNORECASE
        )
        if pic_match:
            pic_string = pic_match.group(1) or pic_match.group(2)
            item.picture = self._parse_picture(pic_string)

        # Parse OCCURS clause
        occurs_match = re.search(
            r"OCCURS\s+(\d+)(?:\s+(?:TO\s+(\d+))?\s+TIMES?)?(?:\s+DEPENDING\s+ON\s+(\w+))?",
            rest,
            re.IGNORECASE,
        )
        if occurs_match:
            item.item_type = DataItemType.OCCURS
            item.occurs = int(occurs_match.group(2) or occurs_match.group(1))
            if occurs_match.group(3):
                item.occurs_depending = occurs_match.group(3)

        # Parse REDEFINES clause
        redef_match = re.search(r"REDEFINES\s+(\w+)", rest, re.IGNORECASE)
        if redef_match:
            item.item_type = DataItemType.REDEFINES
            item.redefines = redef_match.group(1)

        # Parse VALUE clause
        value_match = re.search(
            r"VALUE\s+(?:IS\s+)?(['\"][^'\"]+['\"]|\d+|ZERO|ZEROS|ZEROES|SPACE|SPACES|HIGH-VALUE|LOW-VALUE)",
            rest,
            re.IGNORECASE,
        )
        if value_match:
            item.value = value_match.group(1).strip("'\"")

        # Check if this is a group item (no PICTURE)
        if not item.picture and item.item_type == DataItemType.ELEMENTARY:
            item.item_type = DataItemType.GROUP

        return item

    def _parse_picture(self, pic_string: str) -> PictureClause:
        """Parse a PICTURE clause string."""
        pic_upper = pic_string.upper()

        # Expand shorthand notation
        expanded = re.sub(
            r"(\w)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic_upper
        )

        # Determine category
        category = PictureCategory.ALPHANUMERIC
        if re.match(r"^S?9+V?9*$", expanded):
            category = PictureCategory.NUMERIC
        elif re.match(r"^A+$", expanded):
            category = PictureCategory.ALPHABETIC
        elif re.match(r"^X+$", expanded):
            category = PictureCategory.ALPHANUMERIC
        elif re.search(r"[Z\$\*\-\+,\.]", expanded):
            if "9" in expanded or "Z" in expanded:
                category = PictureCategory.NUMERIC_EDITED
            else:
                category = PictureCategory.ALPHANUMERIC_EDITED

        # Calculate size
        size = len(
            expanded.replace("V", "").replace("S", "").replace("+", "").replace("-", "")
        )

        # Calculate decimal positions
        decimal_positions = 0
        if "V" in expanded:
            decimal_positions = len(expanded.split("V")[1]) if "V" in expanded else 0

        # Check for sign
        signed = "S" in expanded or "+" in expanded or "-" in expanded

        return PictureClause(
            raw=pic_string,
            category=category,
            size=size,
            decimal_positions=decimal_positions,
            signed=signed,
        )

    def _parse_file_definitions(
        self, lines: list[str], line_offset: int
    ) -> list[FileDefinition]:
        """Parse FD (File Description) entries."""
        files = []
        current_fd = None

        for i, line in enumerate(lines):
            if self._is_comment(line):
                continue

            upper_line = line.upper().strip()

            if upper_line.startswith("FD "):
                if current_fd:
                    files.append(current_fd)

                # Parse FD line
                fd_match = re.match(r"FD\s+(\w+)", upper_line)
                if fd_match:
                    current_fd = FileDefinition(
                        name=fd_match.group(1),
                        file_name="",
                        organization=FileOrganization.SEQUENTIAL,
                        access_mode=AccessMode.SEQUENTIAL,
                        line_number=line_offset + i,
                    )

            elif current_fd:
                # Parse file attributes
                if "RECORD" in upper_line:
                    rec_match = re.search(r"RECORD\s+(?:CONTAINS\s+)?(\d+)", upper_line)
                    if rec_match:
                        current_fd.record_size = int(rec_match.group(1))

                if "BLOCK" in upper_line:
                    blk_match = re.search(r"BLOCK\s+(?:CONTAINS\s+)?(\d+)", upper_line)
                    if blk_match:
                        current_fd.block_size = int(blk_match.group(1))

        if current_fd:
            files.append(current_fd)

        return files

    def _parse_procedure_division(
        self, lines: list[str], line_offset: int
    ) -> dict[str, Any]:
        """Parse Procedure Division."""
        result: dict[str, Any] = {
            "sections": [],
            "paragraphs": [],
            "sql": [],
            "cics": [],
            "dependencies": [],
            "errors": [],
        }

        current_section: Section | None = None
        current_paragraph: Paragraph | None = None
        statement_buffer = ""

        for i, line in enumerate(lines):
            if self._is_comment(line):
                continue

            stripped = line.strip()
            upper_line = stripped.upper()
            actual_line = line_offset + i

            # Skip division header
            if "PROCEDURE DIVISION" in upper_line:
                continue

            # Check for section
            if stripped.endswith("SECTION."):
                if current_paragraph:
                    current_paragraph.line_end = actual_line - 1
                    if current_section:
                        current_section.paragraphs.append(current_paragraph)
                    else:
                        result["paragraphs"].append(current_paragraph)

                if current_section:
                    current_section.line_end = actual_line - 1
                    result["sections"].append(current_section)

                section_name = stripped[:-8].strip()
                current_section = Section(name=section_name, line_start=actual_line)
                current_paragraph = None
                continue

            # Check for paragraph
            if stripped and not stripped[0].isspace() and stripped.endswith("."):
                potential_name = stripped[:-1].strip()
                if re.match(r"^[A-Z][\w\-]*$", potential_name, re.IGNORECASE):
                    if current_paragraph:
                        current_paragraph.line_end = actual_line - 1
                        if current_section:
                            current_section.paragraphs.append(current_paragraph)
                        else:
                            result["paragraphs"].append(current_paragraph)

                    current_paragraph = Paragraph(
                        name=potential_name,
                        section=current_section.name if current_section else None,
                        line_start=actual_line,
                    )
                    continue

            # Accumulate statement
            statement_buffer += " " + stripped

            # Check for statement termination
            if statement_buffer.strip().endswith("."):
                stmt = self._parse_statement(statement_buffer.strip(), actual_line)

                if stmt and current_paragraph:
                    current_paragraph.statements.append(stmt)

                    # Track SQL statements
                    if stmt.statement_type == StatementType.EXEC_SQL:
                        sql = self._parse_sql(stmt.raw_text, actual_line)
                        if sql:
                            result["sql"].append(sql)

                    # Track CICS commands
                    elif stmt.statement_type == StatementType.EXEC_CICS:
                        cics = self._parse_cics(stmt.raw_text, actual_line)
                        if cics:
                            result["cics"].append(cics)

                    # Track external CALLs
                    elif stmt.statement_type == StatementType.CALL:
                        for prog in stmt.called_programs:
                            existing = next(
                                (
                                    d
                                    for d in result["dependencies"]
                                    if d.program_name == prog
                                ),
                                None,
                            )
                            if existing:
                                existing.line_numbers.append(actual_line)
                            else:
                                result["dependencies"].append(
                                    ProgramDependency(
                                        program_name=prog,
                                        call_type="CALL",
                                        parameters=stmt.metadata.get("parameters", []),
                                        line_numbers=[actual_line],
                                    )
                                )

                statement_buffer = ""

        # Finalize last paragraph and section
        if current_paragraph:
            current_paragraph.line_end = line_offset + len(lines)
            if current_section:
                current_section.paragraphs.append(current_paragraph)
            else:
                result["paragraphs"].append(current_paragraph)

        if current_section:
            current_section.line_end = line_offset + len(lines)
            result["sections"].append(current_section)

        return result

    def _parse_statement(self, text: str, line_number: int) -> Statement | None:
        """Parse a single statement."""
        upper_text = text.upper()

        # Identify statement type
        statement_type = StatementType.UNKNOWN

        for stype, pattern in self._statement_patterns.items():
            if pattern.match(text):
                statement_type = stype
                break

        # Fallback detection based on verb
        if statement_type == StatementType.UNKNOWN:
            first_word = upper_text.split()[0] if upper_text.split() else ""
            type_map = {
                "MOVE": StatementType.MOVE,
                "COMPUTE": StatementType.COMPUTE,
                "ADD": StatementType.ADD,
                "SUBTRACT": StatementType.SUBTRACT,
                "MULTIPLY": StatementType.MULTIPLY,
                "DIVIDE": StatementType.DIVIDE,
                "IF": StatementType.IF,
                "EVALUATE": StatementType.EVALUATE,
                "PERFORM": StatementType.PERFORM,
                "CALL": StatementType.CALL,
                "READ": StatementType.READ,
                "WRITE": StatementType.WRITE,
                "DISPLAY": StatementType.DISPLAY,
                "ACCEPT": StatementType.ACCEPT,
                "INITIALIZE": StatementType.INITIALIZE,
                "STRING": StatementType.STRING,
                "UNSTRING": StatementType.UNSTRING,
                "INSPECT": StatementType.INSPECT,
                "GO": StatementType.GO_TO,
                "STOP": StatementType.STOP,
                "EXIT": StatementType.EXIT,
                "CONTINUE": StatementType.CONTINUE,
                "SET": StatementType.SET,
                "OPEN": StatementType.OPEN,
                "CLOSE": StatementType.CLOSE,
            }
            statement_type = type_map.get(first_word, StatementType.UNKNOWN)

        stmt = Statement(
            statement_type=statement_type, raw_text=text, line_number=line_number
        )

        # Extract variables
        self._extract_variables(stmt, text)

        # Extract paragraph calls for PERFORM
        if statement_type == StatementType.PERFORM:
            perform_match = re.search(
                r"PERFORM\s+(\w[\w\-]*?)(?:\s+THRU|\s+THROUGH|\s+UNTIL|\s+VARYING|\s+TIMES|\s*\.)",
                text,
                re.IGNORECASE,
            )
            if perform_match:
                stmt.called_paragraphs.append(perform_match.group(1))

        # Extract program calls for CALL
        if statement_type == StatementType.CALL:
            call_match = re.search(r"CALL\s+['\"]?(\w+)['\"]?", text, re.IGNORECASE)
            if call_match:
                stmt.called_programs.append(call_match.group(1))

            # Extract USING parameters
            using_match = re.search(
                r"USING\s+(.+?)(?:ON\s+|END-CALL|\.)", text, re.IGNORECASE | re.DOTALL
            )
            if using_match:
                params = re.findall(
                    r"\b([A-Z][\w\-]*)\b", using_match.group(1), re.IGNORECASE
                )
                stmt.metadata["parameters"] = params

        return stmt

    def _extract_variables(self, stmt: Statement, text: str) -> None:
        """Extract variable references from statement."""
        upper_text = text.upper()

        # Variables that are written to
        write_patterns = [
            r"MOVE\s+.+?\s+TO\s+(.+?)(?:\.|$)",
            r"COMPUTE\s+(\w[\w\-]*)\s*=",
            r"ADD\s+.+?\s+TO\s+(\w[\w\-]*)",
            r"SUBTRACT\s+.+?\s+FROM\s+(\w[\w\-]*)",
            r"MULTIPLY\s+.+?\s+BY\s+(\w[\w\-]*)",
            r"DIVIDE\s+.+?\s+INTO\s+(\w[\w\-]*)",
            r"READ\s+\w+\s+INTO\s+(\w[\w\-]*)",
            r"ACCEPT\s+(\w[\w\-]*)",
        ]

        for pattern in write_patterns:
            match = re.search(pattern, upper_text, re.IGNORECASE)
            if match:
                vars_text = match.group(1)
                var_names = re.findall(r"\b([A-Z][\w\-]*)\b", vars_text, re.IGNORECASE)
                stmt.variables_written.extend(var_names)

        # Extract all variable references as reads (excluding written ones)
        all_vars = re.findall(r"\b([A-Z][\w\-]*)\b", text, re.IGNORECASE)
        keywords = {
            "MOVE",
            "TO",
            "COMPUTE",
            "ADD",
            "SUBTRACT",
            "MULTIPLY",
            "DIVIDE",
            "IF",
            "THEN",
            "ELSE",
            "END-IF",
            "PERFORM",
            "THRU",
            "THROUGH",
            "UNTIL",
            "VARYING",
            "FROM",
            "BY",
            "GIVING",
            "CALL",
            "USING",
            "READ",
            "WRITE",
            "INTO",
            "DISPLAY",
            "ACCEPT",
            "AND",
            "OR",
            "NOT",
            "EQUAL",
            "GREATER",
            "LESS",
            "THAN",
            "WHEN",
            "EVALUATE",
            "END-EVALUATE",
            "STRING",
            "UNSTRING",
            "DELIMITED",
            "SIZE",
            "ALL",
            "SPACES",
            "ZEROS",
            "ZEROES",
            "HIGH-VALUES",
            "LOW-VALUES",
            "ON",
            "EXCEPTION",
            "END-STRING",
        }

        for var in all_vars:
            if var.upper() not in keywords and var not in stmt.variables_written:
                if var not in stmt.variables_read:
                    stmt.variables_read.append(var)

    def _parse_sql(self, text: str, line_number: int) -> SQLStatement | None:
        """Parse embedded SQL statement."""
        sql_match = re.search(
            r"EXEC\s+SQL\s+(.+?)\s*END-EXEC", text, re.IGNORECASE | re.DOTALL
        )

        if not sql_match:
            return None

        sql_text = sql_match.group(1).strip()
        upper_sql = sql_text.upper()

        # Determine operation
        operation = "UNKNOWN"
        if upper_sql.startswith("SELECT"):
            operation = "SELECT"
        elif upper_sql.startswith("INSERT"):
            operation = "INSERT"
        elif upper_sql.startswith("UPDATE"):
            operation = "UPDATE"
        elif upper_sql.startswith("DELETE"):
            operation = "DELETE"
        elif upper_sql.startswith("DECLARE"):
            operation = "DECLARE_CURSOR"
        elif upper_sql.startswith("OPEN"):
            operation = "OPEN_CURSOR"
        elif upper_sql.startswith("FETCH"):
            operation = "FETCH"
        elif upper_sql.startswith("CLOSE"):
            operation = "CLOSE_CURSOR"
        elif upper_sql.startswith("COMMIT"):
            operation = "COMMIT"
        elif upper_sql.startswith("ROLLBACK"):
            operation = "ROLLBACK"

        sql_stmt = SQLStatement(
            operation=operation, raw_sql=sql_text, line_number=line_number
        )

        # Extract table names
        table_pattern = re.compile(r"(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)", re.IGNORECASE)
        sql_stmt.tables = table_pattern.findall(sql_text)

        # Extract host variables (prefixed with :)
        host_var_pattern = re.compile(r":(\w+)")
        sql_stmt.host_variables = host_var_pattern.findall(sql_text)

        # Extract cursor name for cursor operations
        cursor_pattern = re.compile(
            r"(?:DECLARE|OPEN|FETCH|CLOSE)\s+(\w+)\s+CURSOR", re.IGNORECASE
        )
        cursor_match = cursor_pattern.search(sql_text)
        if cursor_match:
            sql_stmt.cursor_name = cursor_match.group(1)

        return sql_stmt

    def _parse_cics(self, text: str, line_number: int) -> CICSCommand | None:
        """Parse embedded CICS command."""
        cics_match = re.search(
            r"EXEC\s+CICS\s+(\w+)\s*(.*?)\s*END-EXEC", text, re.IGNORECASE | re.DOTALL
        )

        if not cics_match:
            return None

        command = cics_match.group(1).upper()
        options_text = cics_match.group(2)

        cics_cmd = CICSCommand(command=command, line_number=line_number)

        # Parse options
        option_pattern = re.compile(r"(\w+)\s*\(\s*([^)]+)\s*\)")
        for match in option_pattern.finditer(options_text):
            cics_cmd.options[match.group(1).upper()] = match.group(2).strip()

        return cics_cmd

    def _analyze_data_flow(self, program: COBOLProgram) -> list[DataFlow]:
        """Analyze data flow through the program."""
        flows = []

        for paragraph in program.paragraphs:
            for stmt in paragraph.statements:
                if stmt.statement_type == StatementType.MOVE:
                    for source in stmt.variables_read:
                        for target in stmt.variables_written:
                            flows.append(
                                DataFlow(
                                    source=source,
                                    target=target,
                                    statement_type=stmt.statement_type,
                                    line_number=stmt.line_number,
                                )
                            )

                elif stmt.statement_type == StatementType.COMPUTE:
                    for source in stmt.variables_read:
                        for target in stmt.variables_written:
                            flows.append(
                                DataFlow(
                                    source=source,
                                    target=target,
                                    statement_type=stmt.statement_type,
                                    line_number=stmt.line_number,
                                    transformation="compute",
                                )
                            )

        return flows

    def _build_call_graph(self, program: COBOLProgram) -> None:
        """Build call graph between paragraphs."""
        para_map = {p.name: p for p in program.paragraphs}

        for paragraph in program.paragraphs:
            for stmt in paragraph.statements:
                for called in stmt.called_paragraphs:
                    paragraph.calls.append(called)
                    if called in para_map:
                        para_map[called].called_by.append(paragraph.name)

    async def get_data_item(self, program: COBOLProgram, name: str) -> DataItem | None:
        """Get a data item by name."""
        for item in program.data_items:
            if item.name.upper() == name.upper():
                return item
        return None

    async def get_paragraph(self, program: COBOLProgram, name: str) -> Paragraph | None:
        """Get a paragraph by name."""
        for para in program.paragraphs:
            if para.name.upper() == name.upper():
                return para
        return None

    async def generate_copybook_dependency_graph(
        self, program: COBOLProgram
    ) -> dict[str, list[str]]:
        """Generate copybook dependency graph."""
        graph: dict[str, list[str]] = {program.program_id: []}

        for copybook in program.copybooks:
            graph[program.program_id].append(copybook.name)
            if copybook.name not in graph:
                graph[copybook.name] = []

        return graph

    async def get_program_metrics(self, program: COBOLProgram) -> dict[str, Any]:
        """Get comprehensive program metrics."""
        total_statements = sum(len(p.statements) for p in program.paragraphs)

        avg_paragraph_size = total_statements / max(len(program.paragraphs), 1)

        max_cyclomatic = max(
            (p.cyclomatic_complexity for p in program.paragraphs), default=0
        )

        return {
            "total_lines": program.total_lines,
            "code_lines": program.code_lines,
            "comment_lines": program.comment_lines,
            "comment_ratio": program.comment_lines / max(program.total_lines, 1),
            "total_data_items": len(program.data_items),
            "total_paragraphs": len(program.paragraphs),
            "total_sections": len(program.sections),
            "total_statements": total_statements,
            "avg_paragraph_size": round(avg_paragraph_size, 2),
            "max_cyclomatic_complexity": max_cyclomatic,
            "overall_complexity": program.complexity.value,
            "copybook_count": len(program.copybooks),
            "file_count": len(program.files),
            "sql_statement_count": len(program.sql_statements),
            "cics_command_count": len(program.cics_commands),
            "external_calls": len(program.program_dependencies),
            "has_db2": program.has_db2,
            "has_cics": program.has_cics,
        }
