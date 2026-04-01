"""
PII Detection Service
=====================

ADR-056 Phase 3: Data Flow Analysis

Detects Personally Identifiable Information (PII) patterns in code:
- Field names suggesting PII (email, ssn, phone, etc.)
- Data patterns (regex for SSN, credit cards, etc.)
- Compliance tagging (GDPR, HIPAA, PCI-DSS, etc.)
- Encryption/masking detection
"""

import ast
import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from src.services.data_flow.types import (
    ComplianceFramework,
    DataClassification,
    PIICategory,
    PIIField,
)

logger = logging.getLogger(__name__)

# PII field name patterns with categories
PII_FIELD_PATTERNS: list[dict[str, Any]] = [
    # Names
    {
        "category": PIICategory.NAME,
        "patterns": [
            r"^(first|last|middle|full)[_-]?name$",
            r"^name$",
            r"^(user|customer|employee|patient|client)[_-]?name$",
            r"^(given|family|sur)[_-]?name$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.CONFIDENTIAL,
    },
    # Email
    {
        "category": PIICategory.EMAIL,
        "patterns": [
            r"^e?mail(_address)?$",
            r"^(user|customer|employee|contact)[_-]?email$",
            r"^email[_-]?(addr|address)?$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.CONFIDENTIAL,
    },
    # Phone
    {
        "category": PIICategory.PHONE,
        "patterns": [
            r"^phone(_number)?$",
            r"^(mobile|cell|home|work)[_-]?phone$",
            r"^tel(ephone)?$",
            r"^contact[_-]?number$",
            r"^fax$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.CONFIDENTIAL,
    },
    # SSN (Social Security Number)
    {
        "category": PIICategory.SSN,
        "patterns": [
            r"^ssn$",
            r"^social[_-]?security[_-]?(number|num)?$",
            r"^ss[_-]?number$",
            r"^tax[_-]?id$",
            r"^national[_-]?id$",
        ],
        "compliance": [
            ComplianceFramework.NIST_800_53,
            ComplianceFramework.SOX,
            ComplianceFramework.CCPA,
        ],
        "classification": DataClassification.RESTRICTED,
    },
    # Address
    {
        "category": PIICategory.ADDRESS,
        "patterns": [
            r"^address(_line)?[_-]?[12]?$",
            r"^street(_address)?$",
            r"^(city|state|province|country|zip|postal)[_-]?(code)?$",
            r"^(home|mailing|billing|shipping)[_-]?address$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.CONFIDENTIAL,
    },
    # Date of Birth
    {
        "category": PIICategory.DATE_OF_BIRTH,
        "patterns": [
            r"^(date[_-]?of[_-]?)?birth(_date)?$",
            r"^dob$",
            r"^birthday$",
            r"^birth[_-]?year$",
            r"^age$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.HIPAA],
        "classification": DataClassification.CONFIDENTIAL,
    },
    # Credit Card
    {
        "category": PIICategory.CREDIT_CARD,
        "patterns": [
            r"^(credit|debit)[_-]?card(_number)?$",
            r"^card[_-]?(number|num)$",
            r"^cc[_-]?(number|num)$",
            r"^pan$",  # Primary Account Number
            r"^cvv$",
            r"^(card[_-]?)?expir(y|ation)(_date)?$",
        ],
        "compliance": [ComplianceFramework.PCI_DSS],
        "classification": DataClassification.RESTRICTED,
    },
    # Bank Account
    {
        "category": PIICategory.BANK_ACCOUNT,
        "patterns": [
            r"^bank[_-]?account(_number)?$",
            r"^account[_-]?(number|num)$",
            r"^(iban|swift|routing)[_-]?(number|code)?$",
            r"^aba[_-]?(number|routing)?$",
        ],
        "compliance": [ComplianceFramework.SOX, ComplianceFramework.PCI_DSS],
        "classification": DataClassification.RESTRICTED,
    },
    # Medical/Health
    {
        "category": PIICategory.MEDICAL_RECORD,
        "patterns": [
            r"^medical[_-]?record[_-]?(number|id)?$",
            r"^mrn$",
            r"^patient[_-]?id$",
            r"^health[_-]?record$",
        ],
        "compliance": [ComplianceFramework.HIPAA],
        "classification": DataClassification.RESTRICTED,
    },
    {
        "category": PIICategory.HEALTH_INSURANCE_ID,
        "patterns": [
            r"^(health[_-]?)?insurance[_-]?(id|number)$",
            r"^policy[_-]?(number|id)$",
            r"^member[_-]?id$",
            r"^subscriber[_-]?id$",
        ],
        "compliance": [ComplianceFramework.HIPAA],
        "classification": DataClassification.RESTRICTED,
    },
    {
        "category": PIICategory.DIAGNOSIS,
        "patterns": [
            r"^diagnosis(_code)?$",
            r"^icd[_-]?code$",
            r"^condition$",
            r"^disease$",
            r"^medical[_-]?condition$",
        ],
        "compliance": [ComplianceFramework.HIPAA],
        "classification": DataClassification.RESTRICTED,
    },
    # Passport/License
    {
        "category": PIICategory.PASSPORT,
        "patterns": [
            r"^passport[_-]?(number|num|id)?$",
            r"^travel[_-]?document$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.NIST_800_53],
        "classification": DataClassification.RESTRICTED,
    },
    {
        "category": PIICategory.DRIVERS_LICENSE,
        "patterns": [
            r"^(driver[s]?[_-]?)?licen[cs]e[_-]?(number|num|id)?$",
            r"^dl[_-]?(number|num)?$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.RESTRICTED,
    },
    # Authentication
    {
        "category": PIICategory.PASSWORD,
        "patterns": [
            r"^password(_hash)?$",
            r"^passwd$",
            r"^pwd$",
            r"^secret$",
            r"^pin(_code)?$",
        ],
        "compliance": [ComplianceFramework.NIST_800_53],
        "classification": DataClassification.RESTRICTED,
    },
    {
        "category": PIICategory.API_KEY,
        "patterns": [
            r"^api[_-]?key$",
            r"^access[_-]?key(_id)?$",
            r"^secret[_-]?key$",
            r"^auth[_-]?token$",
        ],
        "compliance": [ComplianceFramework.NIST_800_53],
        "classification": DataClassification.RESTRICTED,
    },
    # IP Address
    {
        "category": PIICategory.IP_ADDRESS,
        "patterns": [
            r"^ip[_-]?(address|addr)?$",
            r"^client[_-]?ip$",
            r"^source[_-]?ip$",
            r"^remote[_-]?(addr|address)$",
        ],
        "compliance": [ComplianceFramework.GDPR],
        "classification": DataClassification.INTERNAL,
    },
    # Location
    {
        "category": PIICategory.LOCATION,
        "patterns": [
            r"^(geo)?location$",
            r"^(lat|latitude)$",
            r"^(lon|lng|longitude)$",
            r"^coordinates$",
            r"^gps$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.CONFIDENTIAL,
    },
    # Device ID
    {
        "category": PIICategory.DEVICE_ID,
        "patterns": [
            r"^device[_-]?id$",
            r"^udid$",
            r"^imei$",
            r"^mac[_-]?address$",
            r"^hardware[_-]?id$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.INTERNAL,
    },
    # Biometric
    {
        "category": PIICategory.BIOMETRIC,
        "patterns": [
            r"^(biometric|fingerprint|face[_-]?id|voice[_-]?print)$",
            r"^retina(_scan)?$",
            r"^facial[_-]?recognition$",
        ],
        "compliance": [ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        "classification": DataClassification.RESTRICTED,
    },
]

# Data value patterns (regex for actual PII in data)
PII_VALUE_PATTERNS: list[dict[str, Any]] = [
    {
        "category": PIICategory.EMAIL,
        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "confidence": 0.9,
    },
    {
        "category": PIICategory.SSN,
        "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
        "confidence": 0.95,
    },
    {
        "category": PIICategory.CREDIT_CARD,
        "pattern": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        "confidence": 0.95,
    },
    {
        "category": PIICategory.PHONE,
        "pattern": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "confidence": 0.8,
    },
    {
        "category": PIICategory.IP_ADDRESS,
        "pattern": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "confidence": 0.85,
    },
]

# Patterns indicating encryption
ENCRYPTION_PATTERNS = [
    r"encrypt",
    r"cipher",
    r"aes",
    r"kms",
    r"hashlib",
    r"bcrypt",
    r"argon2",
    r"scrypt",
    r"fernet",
    r"cryptography",
]

# Patterns indicating masking
MASKING_PATTERNS = [
    r"mask",
    r"redact",
    r"obfuscate",
    r"sanitize",
    r"\*{3,}",  # Asterisks for masking
    r"x{3,}",  # X's for masking
]


class PIIDetectionService:
    """Detects PII fields and values in code.

    Identifies:
    - Field names suggesting PII storage
    - Data patterns matching PII formats
    - Compliance framework applicability
    - Encryption/masking status

    Attributes:
        use_mock: If True, returns mock data for testing
        field_patterns: List of field name patterns
        value_patterns: List of value patterns
    """

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize PIIDetectionService.

        Args:
            use_mock: If True, returns mock data instead of real analysis
        """
        self.use_mock = use_mock
        self.field_patterns = PII_FIELD_PATTERNS
        self.value_patterns = PII_VALUE_PATTERNS

    async def detect_in_file(self, file_path: str) -> list[PIIField]:
        """Detect PII fields in a single file.

        Args:
            file_path: Path to the Python file to analyze

        Returns:
            List of detected PII fields
        """
        if self.use_mock:
            return self._get_mock_fields(file_path)

        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return []

        try:
            content = path.read_text(encoding="utf-8")
            return self._analyze_file(content, file_path)
        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return []

    async def detect_in_directory(
        self,
        directory: str,
        recursive: bool = True,
        exclude_patterns: list[str] | None = None,
    ) -> list[PIIField]:
        """Detect PII fields across a directory.

        Args:
            directory: Directory path to analyze
            recursive: If True, analyze subdirectories
            exclude_patterns: Glob patterns to exclude

        Returns:
            List of all detected PII fields
        """
        if self.use_mock:
            return self._get_mock_fields(directory)

        exclude_patterns = exclude_patterns or ["**/test_*.py", "**/__pycache__/**"]
        dir_path = Path(directory)
        fields: list[PIIField] = []

        if not dir_path.exists():
            return fields

        pattern = "**/*.py" if recursive else "*.py"

        for py_file in dir_path.glob(pattern):
            # Skip excluded patterns
            skip = False
            for exclude in exclude_patterns:
                if py_file.match(exclude):
                    skip = True
                    break
            if skip:
                continue

            file_fields = await self.detect_in_file(str(py_file))
            fields.extend(file_fields)

        return fields

    def _analyze_file(self, content: str, file_path: str) -> list[PIIField]:
        """Analyze file content for PII patterns.

        Args:
            content: File content to analyze
            file_path: Path to the file (for reporting)

        Returns:
            List of detected PII fields
        """
        fields: list[PIIField] = []

        # Pre-split lines once and pass to all methods to avoid re-splitting
        lines = content.split("\n")

        # Parse AST for precise detection
        try:
            tree = ast.parse(content)
            ast_fields = self._analyze_ast(tree, content, file_path)
            fields.extend(ast_fields)
        except SyntaxError:
            # Fall back to regex for files that can't be parsed
            regex_fields = self._analyze_with_regex(content, file_path, lines=lines)
            fields.extend(regex_fields)

        # Also check for PII values in string literals
        value_fields = self._detect_pii_values(content, file_path, lines=lines)
        fields.extend(value_fields)

        return fields

    def _analyze_ast(
        self,
        tree: ast.AST,
        content: str,
        file_path: str,
    ) -> list[PIIField]:
        """Analyze AST for PII field definitions.

        Args:
            tree: Parsed AST
            content: Original file content
            file_path: Path to file

        Returns:
            List of detected PII fields
        """
        fields: list[PIIField] = []

        for node in ast.walk(tree):
            # Check class definitions (models, dataclasses)
            if isinstance(node, ast.ClassDef):
                class_fields = self._analyze_class(node, file_path, content)
                fields.extend(class_fields)

            # Check function arguments
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_fields = self._analyze_function_args(node, file_path)
                fields.extend(func_fields)

            # Check assignments
            elif isinstance(node, ast.Assign):
                assign_fields = self._analyze_assignment(node, file_path)
                fields.extend(assign_fields)

            # Check annotated assignments (type hints)
            elif isinstance(node, ast.AnnAssign):
                if node.target and isinstance(node.target, ast.Name):
                    field = self._check_field_name(
                        node.target.id,
                        file_path,
                        node.lineno,
                        "",
                    )
                    if field:
                        fields.append(field)

        return fields

    def _analyze_class(
        self,
        node: ast.ClassDef,
        file_path: str,
        content: str,
    ) -> list[PIIField]:
        """Analyze class definition for PII fields.

        Args:
            node: Class definition node
            file_path: Path to file
            content: File content

        Returns:
            List of detected PII fields
        """
        fields: list[PIIField] = []
        class_name = node.name

        # Check for dataclass, Pydantic, SQLAlchemy patterns
        _is_model = self._is_model_class(node)  # noqa: F841

        for item in node.body:
            # Check annotated assignments (field: type)
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field = self._check_field_name(
                    item.target.id,
                    file_path,
                    item.lineno,
                    class_name,
                )
                if field:
                    # Check if field is encrypted
                    field.is_encrypted = self._check_encryption_context(
                        content, item.lineno
                    )
                    field.is_masked = self._check_masking_context(content, item.lineno)
                    fields.append(field)

            # Check simple assignments
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field = self._check_field_name(
                            target.id,
                            file_path,
                            item.lineno,
                            class_name,
                        )
                        if field:
                            field.is_encrypted = self._check_encryption_context(
                                content, item.lineno
                            )
                            fields.append(field)

        return fields

    def _analyze_function_args(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
    ) -> list[PIIField]:
        """Analyze function arguments for PII.

        Args:
            node: Function definition node
            file_path: Path to file

        Returns:
            List of detected PII fields
        """
        fields: list[PIIField] = []

        for arg in node.args.args:
            field = self._check_field_name(
                arg.arg,
                file_path,
                node.lineno,
                f"{node.name}()",
            )
            if field:
                fields.append(field)

        return fields

    def _analyze_assignment(
        self,
        node: ast.Assign,
        file_path: str,
    ) -> list[PIIField]:
        """Analyze assignment for PII field names.

        Args:
            node: Assignment node
            file_path: Path to file

        Returns:
            List of detected PII fields
        """
        fields: list[PIIField] = []

        for target in node.targets:
            if isinstance(target, ast.Name):
                field = self._check_field_name(
                    target.id,
                    file_path,
                    node.lineno,
                    "",
                )
                if field:
                    fields.append(field)

        return fields

    def _check_field_name(
        self,
        field_name: str,
        file_path: str,
        line_number: int,
        entity_name: str,
    ) -> PIIField | None:
        """Check if field name matches PII patterns.

        Args:
            field_name: Name of the field
            file_path: Path to source file
            line_number: Line number
            entity_name: Containing entity name

        Returns:
            PIIField if match found, None otherwise
        """
        field_lower = field_name.lower()

        for pattern_config in self.field_patterns:
            for pattern in pattern_config["patterns"]:
                if re.match(pattern, field_lower, re.IGNORECASE):
                    field_id = self._generate_field_id(
                        file_path, line_number, field_name
                    )

                    return PIIField(
                        field_id=field_id,
                        field_name=field_name,
                        pii_category=pattern_config["category"],
                        source_file=file_path,
                        source_line=line_number,
                        entity_name=entity_name,
                        compliance_tags=pattern_config.get("compliance", []),
                        classification=pattern_config.get(
                            "classification", DataClassification.CONFIDENTIAL
                        ),
                        pattern_matched=pattern,
                        confidence=0.9,
                    )

        return None

    def _is_model_class(self, node: ast.ClassDef) -> bool:
        """Check if class is a data model (dataclass, Pydantic, etc.).

        Args:
            node: Class definition node

        Returns:
            True if class appears to be a model
        """
        # Check decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id in {"dataclass", "dataclasses"}:
                    return True
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    if decorator.func.id in {"dataclass", "dataclasses"}:
                        return True

        # Check base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                if base.id in {"BaseModel", "Model", "Base", "SQLModel"}:
                    return True
            elif isinstance(base, ast.Attribute):
                if base.attr in {"Model", "BaseModel"}:
                    return True

        return False

    def _check_encryption_context(
        self, content: str, line_number: int, lines: list[str] | None = None
    ) -> bool:
        """Check if field appears to be encrypted.

        Args:
            content: File content
            line_number: Line number of field
            lines: Pre-split lines (optional, avoids re-splitting)

        Returns:
            True if encryption context detected
        """
        if lines is None:
            lines = content.split("\n")
        # Check surrounding lines (5 lines before and after)
        start = max(0, line_number - 5)
        end = min(len(lines), line_number + 5)
        context = "\n".join(lines[start:end])

        for pattern in ENCRYPTION_PATTERNS:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        return False

    def _check_masking_context(
        self, content: str, line_number: int, lines: list[str] | None = None
    ) -> bool:
        """Check if field appears to be masked.

        Args:
            content: File content
            line_number: Line number of field
            lines: Pre-split lines (optional, avoids re-splitting)

        Returns:
            True if masking context detected
        """
        if lines is None:
            lines = content.split("\n")
        start = max(0, line_number - 5)
        end = min(len(lines), line_number + 5)
        context = "\n".join(lines[start:end])

        for pattern in MASKING_PATTERNS:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        return False

    def _detect_pii_values(
        self, content: str, file_path: str, lines: list[str] | None = None
    ) -> list[PIIField]:
        """Detect PII values in string literals.

        Args:
            content: File content
            file_path: Path to file
            lines: Pre-split lines (optional, avoids re-splitting)

        Returns:
            List of detected PII values
        """
        fields: list[PIIField] = []
        if lines is None:
            lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            for pattern_config in self.value_patterns:
                matches = re.finditer(pattern_config["pattern"], line)
                for match in matches:
                    # Don't flag obvious test/example data
                    value = match.group()
                    if self._is_example_value(value):
                        continue

                    field_id = self._generate_field_id(file_path, i, value[:20])

                    fields.append(
                        PIIField(
                            field_id=field_id,
                            field_name=f"literal_value_{i}",
                            pii_category=pattern_config["category"],
                            source_file=file_path,
                            source_line=i,
                            entity_name="",
                            classification=DataClassification.RESTRICTED,
                            pattern_matched=pattern_config["pattern"],
                            confidence=pattern_config["confidence"],
                        )
                    )

        return fields

    def _is_example_value(self, value: str) -> bool:
        """Check if value appears to be example/test data.

        Args:
            value: The detected value

        Returns:
            True if value appears to be example data
        """
        example_patterns = [
            r"example\.com",
            r"test@",
            r"user@",
            r"000-00-0000",
            r"123-45-6789",
            r"4111111111111111",  # Test credit card
            r"555-555-5555",
            r"127\.0\.0\.1",
            r"localhost",
        ]

        for pattern in example_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True

        return False

    def _analyze_with_regex(
        self, content: str, file_path: str, lines: list[str] | None = None
    ) -> list[PIIField]:
        """Analyze file with regex when AST parsing fails.

        Args:
            content: File content
            file_path: Path to file
            lines: Pre-split lines (optional, avoids re-splitting)

        Returns:
            List of detected PII fields
        """
        fields: list[PIIField] = []
        if lines is None:
            lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Look for variable assignments
            match = re.search(r"(\w+)\s*[:=]", line)
            if match:
                field_name = match.group(1)
                field = self._check_field_name(field_name, file_path, i, "")
                if field:
                    field.confidence = 0.7  # Lower confidence for regex
                    fields.append(field)

        return fields

    def _generate_field_id(self, file_path: str, line: int, name: str) -> str:
        """Generate unique field ID.

        Args:
            file_path: Source file path
            line: Line number
            name: Field name

        Returns:
            Unique field identifier
        """
        content = f"{file_path}:{line}:{name}"
        return f"pii-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def get_compliance_summary(
        self, fields: list[PIIField]
    ) -> dict[ComplianceFramework, list[PIIField]]:
        """Group PII fields by compliance framework.

        Args:
            fields: List of detected PII fields

        Returns:
            Dict mapping compliance frameworks to applicable fields
        """
        summary: dict[ComplianceFramework, list[PIIField]] = {}

        for field in fields:
            for framework in field.compliance_tags:
                if framework not in summary:
                    summary[framework] = []
                summary[framework].append(field)

        return summary

    def get_classification_summary(
        self, fields: list[PIIField]
    ) -> dict[DataClassification, int]:
        """Summarize fields by classification level.

        Args:
            fields: List of detected PII fields

        Returns:
            Dict mapping classification levels to field counts
        """
        summary: dict[DataClassification, int] = dict.fromkeys(DataClassification, 0)

        for field in fields:
            summary[field.classification] += 1

        return summary

    def _get_mock_fields(self, path: str) -> list[PIIField]:
        """Return mock PII fields for testing.

        Args:
            path: File or directory path

        Returns:
            List of mock PII fields
        """
        return [
            PIIField(
                field_id="pii-mock-001",
                field_name="email",
                pii_category=PIICategory.EMAIL,
                source_file=f"{path}/models/user.py",
                source_line=15,
                entity_name="User",
                compliance_tags=[ComplianceFramework.GDPR, ComplianceFramework.CCPA],
                classification=DataClassification.CONFIDENTIAL,
                is_encrypted=False,
                is_masked=True,
                pattern_matched=r"^e?mail(_address)?$",
                confidence=0.95,
            ),
            PIIField(
                field_id="pii-mock-002",
                field_name="ssn",
                pii_category=PIICategory.SSN,
                source_file=f"{path}/models/employee.py",
                source_line=22,
                entity_name="Employee",
                compliance_tags=[
                    ComplianceFramework.NIST_800_53,
                    ComplianceFramework.SOX,
                ],
                classification=DataClassification.RESTRICTED,
                is_encrypted=True,
                is_masked=True,
                pattern_matched=r"^ssn$",
                confidence=0.95,
            ),
            PIIField(
                field_id="pii-mock-003",
                field_name="credit_card_number",
                pii_category=PIICategory.CREDIT_CARD,
                source_file=f"{path}/models/payment.py",
                source_line=18,
                entity_name="PaymentInfo",
                compliance_tags=[ComplianceFramework.PCI_DSS],
                classification=DataClassification.RESTRICTED,
                is_encrypted=True,
                is_masked=True,
                pattern_matched=r"^(credit|debit)[_-]?card(_number)?$",
                confidence=0.95,
            ),
            PIIField(
                field_id="pii-mock-004",
                field_name="phone_number",
                pii_category=PIICategory.PHONE,
                source_file=f"{path}/models/contact.py",
                source_line=12,
                entity_name="Contact",
                compliance_tags=[ComplianceFramework.GDPR],
                classification=DataClassification.CONFIDENTIAL,
                is_encrypted=False,
                is_masked=False,
                pattern_matched=r"^phone(_number)?$",
                confidence=0.9,
            ),
            PIIField(
                field_id="pii-mock-005",
                field_name="medical_record_number",
                pii_category=PIICategory.MEDICAL_RECORD,
                source_file=f"{path}/models/patient.py",
                source_line=25,
                entity_name="Patient",
                compliance_tags=[ComplianceFramework.HIPAA],
                classification=DataClassification.RESTRICTED,
                is_encrypted=True,
                is_masked=True,
                pattern_matched=r"^medical[_-]?record[_-]?(number|id)?$",
                confidence=0.95,
            ),
        ]
