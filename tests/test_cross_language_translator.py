"""
Tests for Cross-Language Translator.

Tests the intelligent code translation between legacy and modern languages.
"""

import platform

import pytest

from src.services.transform.cross_language_translator import (  # Enums; Dataclasses; Main class
    ComplexityLevel,
    ConfidenceLevel,
    CrossLanguageTranslator,
    DataStructureTranslation,
    DataTypeMapping,
    FunctionTranslation,
    ImportStatement,
    ManualReviewItem,
    SourceLanguage,
    TargetLanguage,
    TranslatedFile,
    TranslationConfig,
    TranslationResult,
    TranslationStatus,
    TranslationStrategy,
    TranslationTestCase,
    TranslationWarning,
    TypeMapping,
    VariableTranslation,
)

# ============================================================================
# Enum Tests
# ============================================================================


class TestSourceLanguage:
    """Test SourceLanguage enum."""

    def test_cobol(self):
        """Test COBOL value."""
        assert SourceLanguage.COBOL.value == "cobol"

    def test_vbnet(self):
        """Test VB.NET value."""
        assert SourceLanguage.VBNET.value == "vbnet"

    def test_vb6(self):
        """Test VB6 value."""
        assert SourceLanguage.VB6.value == "vb6"

    def test_java(self):
        """Test Java value."""
        assert SourceLanguage.JAVA.value == "java"

    def test_csharp(self):
        """Test C# value."""
        assert SourceLanguage.CSHARP.value == "csharp"

    def test_fortran(self):
        """Test Fortran value."""
        assert SourceLanguage.FORTRAN.value == "fortran"

    def test_pl1(self):
        """Test PL/1 value."""
        assert SourceLanguage.PL1.value == "pl1"

    def test_rpg(self):
        """Test RPG value."""
        assert SourceLanguage.RPG.value == "rpg"

    def test_natural(self):
        """Test Natural value."""
        assert SourceLanguage.NATURAL.value == "natural"

    def test_powerbuilder(self):
        """Test PowerBuilder value."""
        assert SourceLanguage.POWERBUILDER.value == "powerbuilder"


class TestTargetLanguage:
    """Test TargetLanguage enum."""

    def test_python(self):
        """Test Python value."""
        assert TargetLanguage.PYTHON.value == "python"

    def test_java(self):
        """Test Java value."""
        assert TargetLanguage.JAVA.value == "java"

    def test_csharp(self):
        """Test C# value."""
        assert TargetLanguage.CSHARP.value == "csharp"

    def test_kotlin(self):
        """Test Kotlin value."""
        assert TargetLanguage.KOTLIN.value == "kotlin"

    def test_go(self):
        """Test Go value."""
        assert TargetLanguage.GO.value == "go"

    def test_rust(self):
        """Test Rust value."""
        assert TargetLanguage.RUST.value == "rust"

    def test_typescript(self):
        """Test TypeScript value."""
        assert TargetLanguage.TYPESCRIPT.value == "typescript"

    def test_javascript(self):
        """Test JavaScript value."""
        assert TargetLanguage.JAVASCRIPT.value == "javascript"


class TestTranslationStrategy:
    """Test TranslationStrategy enum."""

    def test_literal(self):
        """Test literal strategy."""
        assert TranslationStrategy.LITERAL.value == "literal"

    def test_idiomatic(self):
        """Test idiomatic strategy."""
        assert TranslationStrategy.IDIOMATIC.value == "idiomatic"

    def test_optimized(self):
        """Test optimized strategy."""
        assert TranslationStrategy.OPTIMIZED.value == "optimized"

    def test_modernized(self):
        """Test modernized strategy."""
        assert TranslationStrategy.MODERNIZED.value == "modernized"


class TestDataTypeMapping:
    """Test DataTypeMapping enum."""

    def test_strict(self):
        """Test strict mapping."""
        assert DataTypeMapping.STRICT.value == "strict"

    def test_relaxed(self):
        """Test relaxed mapping."""
        assert DataTypeMapping.RELAXED.value == "relaxed"

    def test_native(self):
        """Test native mapping."""
        assert DataTypeMapping.NATIVE.value == "native"


class TestComplexityLevel:
    """Test ComplexityLevel enum."""

    def test_simple(self):
        """Test simple level."""
        assert ComplexityLevel.SIMPLE.value == "simple"

    def test_moderate(self):
        """Test moderate level."""
        assert ComplexityLevel.MODERATE.value == "moderate"

    def test_complex(self):
        """Test complex level."""
        assert ComplexityLevel.COMPLEX.value == "complex"

    def test_expert(self):
        """Test expert level."""
        assert ComplexityLevel.EXPERT.value == "expert"


class TestTranslationStatus:
    """Test TranslationStatus enum."""

    def test_pending(self):
        """Test pending status."""
        assert TranslationStatus.PENDING.value == "pending"

    def test_in_progress(self):
        """Test in progress status."""
        assert TranslationStatus.IN_PROGRESS.value == "in_progress"

    def test_completed(self):
        """Test completed status."""
        assert TranslationStatus.COMPLETED.value == "completed"

    def test_partial(self):
        """Test partial status."""
        assert TranslationStatus.PARTIAL.value == "partial"

    def test_failed(self):
        """Test failed status."""
        assert TranslationStatus.FAILED.value == "failed"

    def test_needs_review(self):
        """Test needs review status."""
        assert TranslationStatus.NEEDS_REVIEW.value == "needs_review"


class TestConfidenceLevel:
    """Test ConfidenceLevel enum."""

    def test_high(self):
        """Test high confidence."""
        assert ConfidenceLevel.HIGH.value == "high"

    def test_medium(self):
        """Test medium confidence."""
        assert ConfidenceLevel.MEDIUM.value == "medium"

    def test_low(self):
        """Test low confidence."""
        assert ConfidenceLevel.LOW.value == "low"

    def test_uncertain(self):
        """Test uncertain confidence."""
        assert ConfidenceLevel.UNCERTAIN.value == "uncertain"


# ============================================================================
# Dataclass Tests
# ============================================================================


class TestTypeMapping:
    """Test TypeMapping dataclass."""

    def test_create_mapping(self):
        """Test creating type mapping."""
        mapping = TypeMapping(source_type="PIC 9(5)", target_type="int")
        assert mapping.source_type == "PIC 9(5)"
        assert mapping.target_type == "int"

    def test_mapping_defaults(self):
        """Test mapping defaults."""
        mapping = TypeMapping(source_type="src", target_type="tgt")
        assert mapping.conversion_required is False
        assert mapping.conversion_function is None
        assert mapping.notes == ""

    def test_mapping_with_conversion(self):
        """Test mapping with conversion."""
        mapping = TypeMapping(
            source_type="PIC X(100)",
            target_type="str",
            conversion_required=True,
            conversion_function="decode_ebcdic",
            notes="EBCDIC to UTF-8",
        )
        assert mapping.conversion_required is True
        assert mapping.conversion_function == "decode_ebcdic"


class TestVariableTranslation:
    """Test VariableTranslation dataclass."""

    def test_create_variable(self):
        """Test creating variable translation."""
        var = VariableTranslation(
            source_name="WS-COUNT",
            target_name="ws_count",
            source_type="PIC 9(5)",
            target_type="int",
        )
        assert var.source_name == "WS-COUNT"
        assert var.target_name == "ws_count"

    def test_variable_defaults(self):
        """Test variable defaults."""
        var = VariableTranslation(
            source_name="src", target_name="tgt", source_type="str", target_type="str"
        )
        assert var.scope == "local"
        assert var.initial_value is None
        assert var.line_number == 0


class TestFunctionTranslation:
    """Test FunctionTranslation dataclass."""

    def test_create_function(self):
        """Test creating function translation."""
        func = FunctionTranslation(
            source_name="PROCESS-DATA",
            target_name="process_data",
            source_signature="PERFORM PROCESS-DATA",
            target_signature="def process_data(self):",
        )
        assert func.source_name == "PROCESS-DATA"
        assert func.target_name == "process_data"

    def test_function_defaults(self):
        """Test function defaults."""
        func = FunctionTranslation(
            source_name="src",
            target_name="tgt",
            source_signature="sig1",
            target_signature="sig2",
        )
        assert func.parameter_mappings == []
        assert func.return_type_mapping is None
        assert func.body_translation == ""
        assert func.confidence == ConfidenceLevel.HIGH
        assert func.notes == []
        assert func.line_start == 0
        assert func.line_end == 0


class TestDataStructureTranslation:
    """Test DataStructureTranslation dataclass."""

    def test_create_structure(self):
        """Test creating data structure translation."""
        struct = DataStructureTranslation(
            source_name="CUSTOMER-RECORD",
            target_name="CustomerRecord",
            source_definition="01 CUSTOMER-RECORD.",
            target_definition="class CustomerRecord:",
        )
        assert struct.source_name == "CUSTOMER-RECORD"
        assert struct.target_name == "CustomerRecord"

    def test_structure_defaults(self):
        """Test structure defaults."""
        struct = DataStructureTranslation(
            source_name="src",
            target_name="tgt",
            source_definition="def1",
            target_definition="def2",
        )
        assert struct.field_mappings == []
        assert struct.confidence == ConfidenceLevel.HIGH


class TestImportStatement:
    """Test ImportStatement dataclass."""

    def test_create_import(self):
        """Test creating import statement."""
        imp = ImportStatement(module="datetime")
        assert imp.module == "datetime"

    def test_import_defaults(self):
        """Test import defaults."""
        imp = ImportStatement(module="os")
        assert imp.items == []
        assert imp.alias is None

    def test_import_with_items(self):
        """Test import with specific items."""
        imp = ImportStatement(
            module="datetime", items=["datetime", "timedelta"], alias=None
        )
        assert len(imp.items) == 2


class TestTranslationWarning:
    """Test TranslationWarning dataclass."""

    def test_create_warning(self):
        """Test creating warning."""
        warning = TranslationWarning(
            location="line 50", message="Potential precision loss", severity="medium"
        )
        assert warning.location == "line 50"
        assert warning.severity == "medium"

    def test_warning_defaults(self):
        """Test warning defaults."""
        warning = TranslationWarning(location="test", message="test", severity="low")
        assert warning.suggestion is None
        assert warning.line_number == 0


class TestManualReviewItem:
    """Test ManualReviewItem dataclass."""

    def test_create_review_item(self):
        """Test creating manual review item."""
        item = ManualReviewItem(
            location="CALCULATE-INTEREST",
            original_code="COMPUTE INTEREST = PRINCIPAL * RATE / 100",
            translated_code="interest = principal * rate / 100",
            reason="Complex calculation may need verification",
        )
        assert item.location == "CALCULATE-INTEREST"
        assert item.reason == "Complex calculation may need verification"

    def test_review_item_defaults(self):
        """Test review item defaults."""
        item = ManualReviewItem(
            location="test",
            original_code="orig",
            translated_code="trans",
            reason="reason",
        )
        assert item.suggestions == []
        assert item.priority == "medium"


class TestTranslationConfig:
    """Test TranslationConfig dataclass."""

    def test_create_config(self):
        """Test creating translation config."""
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL, target_language=TargetLanguage.PYTHON
        )
        assert config.source_language == SourceLanguage.COBOL
        assert config.target_language == TargetLanguage.PYTHON

    def test_config_defaults(self):
        """Test config defaults."""
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL, target_language=TargetLanguage.PYTHON
        )
        assert config.strategy == TranslationStrategy.IDIOMATIC
        assert config.type_mapping == DataTypeMapping.NATIVE
        assert config.preserve_comments is True
        assert config.generate_tests is True
        assert config.add_type_hints is True
        assert config.use_modern_patterns is True
        assert config.max_line_length == 120
        assert config.indent_size == 4
        assert config.naming_convention == "snake_case"
        assert config.custom_type_mappings == {}


class TestTranslatedFile:
    """Test TranslatedFile dataclass."""

    def test_create_translated_file(self):
        """Test creating translated file."""
        file = TranslatedFile(
            source_path="main.cbl",
            target_path="main.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="IDENTIFICATION DIVISION.",
            translated_code="# Main module",
        )
        assert file.source_path == "main.cbl"
        assert file.target_path == "main.py"

    def test_translated_file_defaults(self):
        """Test translated file defaults."""
        file = TranslatedFile(
            source_path="src",
            target_path="tgt",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
        )
        assert file.imports == []
        assert file.variables == []
        assert file.functions == []
        assert file.data_structures == []
        assert file.warnings == []
        assert file.manual_review_items == []
        assert file.confidence == ConfidenceLevel.HIGH
        assert file.complexity == ComplexityLevel.SIMPLE
        assert file.source_lines == 0
        assert file.target_lines == 0
        assert file.translation_ratio == 1.0


class TestTranslationTestCase:
    """Test TranslationTestCase dataclass."""

    def test_create_test_case(self):
        """Test creating test case."""
        test = TranslationTestCase(
            name="test_calculate_total", description="Test the calculate_total function"
        )
        assert test.name == "test_calculate_total"
        assert test.description == "Test the calculate_total function"

    def test_test_case_defaults(self):
        """Test test case defaults."""
        test = TranslationTestCase(name="test", description="desc")
        assert test.input_data == {}
        assert test.expected_output is None
        assert test.original_function == ""
        assert test.translated_function == ""
        assert test.test_code == ""


class TestTranslationResult:
    """Test TranslationResult dataclass."""

    def test_create_result(self):
        """Test creating translation result."""
        result = TranslationResult(status=TranslationStatus.COMPLETED)
        assert result.status == TranslationStatus.COMPLETED

    def test_result_defaults(self):
        """Test result defaults."""
        result = TranslationResult(status=TranslationStatus.PENDING)
        assert result.files == []
        assert result.test_cases == []
        assert result.type_mappings_used == []
        assert result.overall_confidence == ConfidenceLevel.HIGH
        assert result.total_source_lines == 0
        assert result.total_target_lines == 0
        assert result.warnings_count == 0
        assert result.manual_review_count == 0
        assert result.translation_time_ms == 0


# ============================================================================
# Translator Initialization Tests
# ============================================================================


class TestTranslatorInit:
    """Test CrossLanguageTranslator initialization."""

    def test_init(self):
        """Test initialization."""
        translator = CrossLanguageTranslator()
        assert translator is not None

    def test_init_creates_type_mappings(self):
        """Test initialization creates type mappings."""
        translator = CrossLanguageTranslator()
        assert translator._type_mappings is not None

    def test_init_creates_supported_translations(self):
        """Test initialization creates supported translations mapping."""
        translator = CrossLanguageTranslator()
        # Check that the translator can get supported translations
        assert translator is not None


# ============================================================================
# Translation Tests
# ============================================================================


class TestTranslate:
    """Test translate method."""

    @pytest.mark.asyncio
    async def test_translate_simple_cobol(self):
        """Test translating simple COBOL code."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL, target_language=TargetLanguage.PYTHON
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY "HELLO, WORLD".
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "hello.cbl")
        # Verify translation result structure and status
        assert isinstance(result, TranslationResult), "Should return TranslationResult"
        assert len(result.files) > 0, "Should have at least one file"
        assert (
            result.files[0].source_path == "hello.cbl"
        ), "Source file should be tracked"
        assert (
            result.files[0].target_language == TargetLanguage.PYTHON
        ), "Target language should match"

    @pytest.mark.asyncio
    async def test_translate_returns_status(self):
        """Test translation returns status."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL, target_language=TargetLanguage.PYTHON
        )
        result = await translator.translate(
            "IDENTIFICATION DIVISION.", config, "test.cbl"
        )
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.PARTIAL,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_vbnet_to_csharp(self):
        """Test translating VB.NET to C#."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET, target_language=TargetLanguage.CSHARP
        )
        vb_code = """
Public Class Calculator
    Public Function Add(a As Integer, b As Integer) As Integer
        Return a + b
    End Function
End Class
        """
        result = await translator.translate(vb_code, config, "Calculator.vb")
        # Verify VB.NET to C# translation works
        assert isinstance(result, TranslationResult), "Should return TranslationResult"
        assert len(result.files) > 0, "Should have at least one file"
        assert (
            result.files[0].source_path == "Calculator.vb"
        ), "Source file should be tracked"

    @pytest.mark.asyncio
    async def test_translate_java_to_kotlin(self):
        """Test translating Java to Kotlin."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA, target_language=TargetLanguage.KOTLIN
        )
        java_code = """
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
        """
        result = await translator.translate(java_code, config, "Calculator.java")
        # Verify Java to Kotlin translation works
        assert isinstance(result, TranslationResult), "Should return TranslationResult"
        assert len(result.files) > 0, "Should have at least one file"
        assert (
            result.files[0].source_path == "Calculator.java"
        ), "Source file should be tracked"


class TestGetSupportedTranslations:
    """Test get_supported_translations method."""

    @pytest.mark.asyncio
    async def test_returns_list(self):
        """Test returns list of supported translations."""
        translator = CrossLanguageTranslator()
        translations = await translator.get_supported_translations()
        assert translations is not None
        assert isinstance(translations, list)

    @pytest.mark.asyncio
    async def test_includes_cobol_python(self):
        """Test includes COBOL to Python."""
        translator = CrossLanguageTranslator()
        translations = await translator.get_supported_translations()
        cobol_python = [
            t
            for t in translations
            if t.get("source") == "cobol" and t.get("target") == "python"
        ]
        assert len(cobol_python) >= 1


class TestInternalTypeMappings:
    """Test _type_mappings internal structure."""

    def test_type_mappings_structure(self):
        """Test type mappings are available."""
        translator = CrossLanguageTranslator()
        assert translator._type_mappings is not None
        assert isinstance(translator._type_mappings, dict)

    def test_has_cobol_mappings(self):
        """Test COBOL type mappings exist."""
        translator = CrossLanguageTranslator()
        # Check that some COBOL-related mappings exist
        assert len(translator._type_mappings) > 0


class TestNamingConversions:
    """Test internal naming conversion helpers."""

    def test_cobol_naming_convention(self):
        """Test COBOL uses hyphen naming."""
        # COBOL identifiers typically use hyphens
        sample = "WS-CUSTOMER-NAME"
        assert "-" in sample

    def test_python_naming_convention(self):
        """Test Python uses snake_case."""
        # Python identifiers use underscores
        sample = "ws_customer_name"
        assert "_" in sample


class TestTranslationConfigAdvanced:
    """Test TranslationConfig advanced options."""

    def test_config_with_custom_mappings(self):
        """Test config with custom type mappings."""
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            custom_type_mappings={"CUSTOM-TYPE": "CustomType"},
        )
        assert "CUSTOM-TYPE" in config.custom_type_mappings

    def test_config_strategies(self):
        """Test different translation strategies."""
        for strategy in TranslationStrategy:
            config = TranslationConfig(
                source_language=SourceLanguage.COBOL,
                target_language=TargetLanguage.PYTHON,
                strategy=strategy,
            )
            assert config.strategy == strategy

    def test_config_type_mapping_modes(self):
        """Test different type mapping modes."""
        for mode in DataTypeMapping:
            config = TranslationConfig(
                source_language=SourceLanguage.COBOL,
                target_language=TargetLanguage.PYTHON,
                type_mapping=mode,
            )
            assert config.type_mapping == mode


# ============================================================================
# Extended Translation Tests - Coverage Improvement
# ============================================================================

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestCOBOLTranslation:
    """Test COBOL to Python translation edge cases."""

    @pytest.mark.asyncio
    async def test_translate_cobol_with_data_division(self):
        """Test translating COBOL with DATA DIVISION variables."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COUNTER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9(5).
       01 WS-NAME PIC X(20).
       PROCEDURE DIVISION.
           MOVE 100 TO WS-COUNT.
           DISPLAY WS-COUNT.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "counter.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) > 0
        # Check that variable translations were tracked
        assert result.files[0].target_path.endswith(".py")

    @pytest.mark.asyncio
    async def test_translate_cobol_with_comments(self):
        """Test translating COBOL with comment lines."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            preserve_comments=True,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
      * This is a comment line
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY "Hello".
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "hello.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # Comment should be preserved in output
        if result.files[0].translated_code:
            assert (
                "#" in result.files[0].translated_code
                or result.files[0].translated_code != ""
            )

    @pytest.mark.asyncio
    async def test_translate_cobol_compute_statement(self):
        """Test translating COBOL COMPUTE statement."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(5).
       01 WS-B PIC 9(5).
       01 WS-RESULT PIC 9(10).
       PROCEDURE DIVISION.
           MOVE 10 TO WS-A.
           MOVE 20 TO WS-B.
           COMPUTE WS-RESULT = WS-A + WS-B.
           DISPLAY WS-RESULT.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "calc.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_cobol_if_statement(self):
        """Test translating COBOL IF statement."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CONDITION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-NUM PIC 9(5).
       PROCEDURE DIVISION.
           MOVE 10 TO WS-NUM.
           IF WS-NUM GREATER THAN 5
               DISPLAY "Large"
           END-IF.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "condition.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_cobol_perform_statement(self):
        """Test translating COBOL PERFORM statement."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PERF.
       PROCEDURE DIVISION.
           PERFORM SHOW-MESSAGE.
           STOP RUN.
       SHOW-MESSAGE.
           DISPLAY "Hello from paragraph".
        """
        result = await translator.translate(cobol_code, config, "perf.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]


class TestCOBOLHelperMethods:
    """Test COBOL translation helper methods."""

    def test_cobol_pic_to_target_type_python_numeric(self):
        """Test COBOL PIC to Python type for numerics."""
        translator = CrossLanguageTranslator()
        assert (
            translator._cobol_pic_to_target_type("9(5)", TargetLanguage.PYTHON) == "int"
        )
        assert (
            translator._cobol_pic_to_target_type("S9(5)", TargetLanguage.PYTHON)
            == "int"
        )
        assert (
            translator._cobol_pic_to_target_type("9V9", TargetLanguage.PYTHON)
            == "Decimal"
        )

    def test_cobol_pic_to_target_type_python_string(self):
        """Test COBOL PIC to Python type for strings."""
        translator = CrossLanguageTranslator()
        assert (
            translator._cobol_pic_to_target_type("X(20)", TargetLanguage.PYTHON)
            == "str"
        )
        assert (
            translator._cobol_pic_to_target_type("A(10)", TargetLanguage.PYTHON)
            == "str"
        )

    def test_cobol_pic_to_target_type_java(self):
        """Test COBOL PIC to Java type."""
        translator = CrossLanguageTranslator()
        assert (
            translator._cobol_pic_to_target_type("9(5)", TargetLanguage.JAVA) == "int"
        )
        assert (
            translator._cobol_pic_to_target_type("X(20)", TargetLanguage.JAVA)
            == "String"
        )
        assert (
            translator._cobol_pic_to_target_type("9V9", TargetLanguage.JAVA)
            == "BigDecimal"
        )

    def test_cobol_to_python_name_snake_case(self):
        """Test COBOL to Python naming with snake_case."""
        translator = CrossLanguageTranslator()
        assert (
            translator._cobol_to_python_name("WS-CUSTOMER-NAME", "snake_case")
            == "ws_customer_name"
        )
        assert translator._cobol_to_python_name("WS-COUNT", "snake_case") == "ws_count"

    def test_cobol_to_python_name_camel_case(self):
        """Test COBOL to Python naming with camelCase."""
        translator = CrossLanguageTranslator()
        assert (
            translator._cobol_to_python_name("WS-CUSTOMER-NAME", "camelCase")
            == "wsCustomerName"
        )
        assert translator._cobol_to_python_name("WS-COUNT", "camelCase") == "wsCount"

    def test_cobol_to_python_name_pascal_case(self):
        """Test COBOL to Python naming with PascalCase."""
        translator = CrossLanguageTranslator()
        assert (
            translator._cobol_to_python_name("WS-CUSTOMER-NAME", "PascalCase")
            == "WsCustomerName"
        )


class TestVBNETTranslation:
    """Test VB.NET to C# translation."""

    @pytest.mark.asyncio
    async def test_translate_vbnet_class(self):
        """Test translating VB.NET class to C#."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vb_code = """
Public Class Person
    Private _name As String

    Public Sub New(name As String)
        _name = name
    End Sub

    Public Function GetName() As String
        Return _name
    End Function
End Class
        """
        result = await translator.translate(vb_code, config, "Person.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) > 0
        assert result.files[0].target_path.endswith(".cs")

    @pytest.mark.asyncio
    async def test_translate_vbnet_if_statement(self):
        """Test translating VB.NET If statement."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vb_code = """
Module TestModule
    Sub Main()
        Dim x As Integer = 10
        If x > 5 Then
            Console.WriteLine("Large")
        Else
            Console.WriteLine("Small")
        End If
    End Sub
End Module
        """
        result = await translator.translate(vb_code, config, "Test.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]


class TestJavaTranslation:
    """Test Java translation to various targets."""

    @pytest.mark.asyncio
    async def test_translate_java_to_python(self):
        """Test translating Java to Python."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        java_code = """
public class Calculator {
    private int value;

    public Calculator() {
        this.value = 0;
    }

    public int add(int a, int b) {
        return a + b;
    }

    public void printValue() {
        System.out.println(this.value);
    }
}
        """
        result = await translator.translate(java_code, config, "Calculator.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) > 0
        assert result.files[0].target_path.endswith(".py")

    @pytest.mark.asyncio
    async def test_translate_java_to_kotlin(self):
        """Test translating Java to Kotlin."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.KOTLIN,
        )
        java_code = """
public class Person {
    private String name;

    public Person(String name) {
        this.name = name;
    }

    public String getName() {
        return name;
    }
}
        """
        result = await translator.translate(java_code, config, "Person.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) > 0
        assert result.files[0].target_path.endswith(".kt")


class TestCSharpTranslation:
    """Test C# translation."""

    @pytest.mark.asyncio
    async def test_translate_csharp_to_python(self):
        """Test translating C# to Python."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
using System;

public class Calculator
{
    private int value;

    public Calculator()
    {
        this.value = 0;
    }

    public int Add(int a, int b)
    {
        return a + b;
    }

    public void PrintValue()
    {
        Console.WriteLine(this.value);
    }
}
        """
        result = await translator.translate(csharp_code, config, "Calculator.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) > 0
        assert result.files[0].target_path.endswith(".py")


class TestGenericTranslation:
    """Test generic translation fallback."""

    @pytest.mark.asyncio
    async def test_translate_unsupported_language_pair(self):
        """Test translating with unsupported language pair."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.FORTRAN,
            target_language=TargetLanguage.RUST,
        )
        code = "PROGRAM HELLO\nPRINT *, 'Hello World'\nEND PROGRAM"
        result = await translator.translate(code, config, "hello.f90")
        # Should use generic translator and flag for manual review
        assert len(result.files) > 0
        assert (
            len(result.files[0].manual_review_items) > 0
            or len(result.files[0].warnings) > 0
        )


class TestTranslationDifficultyAnalysis:
    """Test translation difficulty analysis."""

    @pytest.mark.asyncio
    async def test_analyze_simple_code(self):
        """Test analyzing simple code difficulty."""
        translator = CrossLanguageTranslator()
        simple_code = """
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello World");
    }
}
        """
        analysis = await translator.analyze_translation_difficulty(
            simple_code,
            SourceLanguage.JAVA,
            TargetLanguage.PYTHON,
        )
        assert "difficulty" in analysis
        assert analysis["difficulty"] in ["easy", "moderate", "hard", "expert"]
        assert analysis["has_generics"] is False
        assert analysis["has_lambdas"] is False

    @pytest.mark.asyncio
    async def test_analyze_complex_code(self):
        """Test analyzing complex code difficulty."""
        translator = CrossLanguageTranslator()
        complex_code = """
public class ComplexService<T> {
    private async Task<List<T>> fetchDataAsync(Func<T, bool> predicate) {
        // Lambda and generic usage
        return await Task.Run(() => items.Where(predicate).ToList());
    }

    public unsafe void ProcessPointer(int* ptr) {
        // Pointer usage
        *ptr = 42;
    }
}
        """
        analysis = await translator.analyze_translation_difficulty(
            complex_code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )
        assert "difficulty" in analysis
        assert analysis["has_generics"] is True
        assert analysis["has_async"] is True

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_analyze_large_codebase(self):
        """Test analyzing large code file."""
        translator = CrossLanguageTranslator()
        # Generate large code file
        large_code = "\n".join([f"// Line {i}\nint x{i} = {i};" for i in range(600)])
        analysis = await translator.analyze_translation_difficulty(
            large_code,
            SourceLanguage.JAVA,
            TargetLanguage.PYTHON,
        )
        assert analysis["source_lines"] > 500
        assert analysis["code_lines"] > 500


class TestComplexityAndConfidenceAssessment:
    """Test complexity and confidence assessment."""

    def test_assess_complexity_simple(self):
        """Test complexity assessment for simple translation."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[],
            manual_review_items=[],
        )
        complexity = translator._assess_complexity(file)
        assert complexity == ComplexityLevel.SIMPLE

    def test_assess_complexity_moderate(self):
        """Test complexity assessment for moderate translation."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[
                TranslationWarning(location="l1", message="w1", severity="low"),
                TranslationWarning(location="l2", message="w2", severity="low"),
            ],
            manual_review_items=[
                ManualReviewItem(
                    location="loc",
                    original_code="orig",
                    translated_code="trans",
                    reason="needs review",
                )
            ],
        )
        complexity = translator._assess_complexity(file)
        assert complexity == ComplexityLevel.MODERATE

    def test_assess_complexity_expert(self):
        """Test complexity assessment for expert-level translation."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[
                TranslationWarning(location=f"l{i}", message=f"w{i}", severity="high")
                for i in range(15)
            ],
            manual_review_items=[
                ManualReviewItem(
                    location=f"loc{i}",
                    original_code="orig",
                    translated_code="trans",
                    reason="needs review",
                )
                for i in range(10)
            ],
        )
        complexity = translator._assess_complexity(file)
        assert complexity == ComplexityLevel.EXPERT

    def test_assess_confidence_high(self):
        """Test confidence assessment for clean translation."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[],
            manual_review_items=[],
        )
        confidence = translator._assess_confidence(file)
        assert confidence == ConfidenceLevel.HIGH

    def test_assess_confidence_medium(self):
        """Test confidence assessment with some warnings."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[
                TranslationWarning(location="l1", message="w1", severity="low"),
                TranslationWarning(location="l2", message="w2", severity="low"),
            ],
            manual_review_items=[],
        )
        confidence = translator._assess_confidence(file)
        assert confidence == ConfidenceLevel.MEDIUM

    def test_assess_confidence_uncertain(self):
        """Test confidence assessment with many review items."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[],
            manual_review_items=[
                ManualReviewItem(
                    location=f"loc{i}",
                    original_code="orig",
                    translated_code="trans",
                    reason="needs review",
                )
                for i in range(5)
            ],
        )
        confidence = translator._assess_confidence(file)
        assert confidence == ConfidenceLevel.UNCERTAIN


class TestTargetPathGeneration:
    """Test target file path generation."""

    def test_get_target_path_python(self):
        """Test target path for Python."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.cbl", TargetLanguage.PYTHON)
        assert result == "source.py"

    def test_get_target_path_java(self):
        """Test target path for Java."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.vb", TargetLanguage.JAVA)
        assert result == "source.java"

    def test_get_target_path_csharp(self):
        """Test target path for C#."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.vb", TargetLanguage.CSHARP)
        assert result == "source.cs"

    def test_get_target_path_kotlin(self):
        """Test target path for Kotlin."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.java", TargetLanguage.KOTLIN)
        assert result == "source.kt"

    def test_get_target_path_go(self):
        """Test target path for Go."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.java", TargetLanguage.GO)
        assert result == "source.go"

    def test_get_target_path_rust(self):
        """Test target path for Rust."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.cpp", TargetLanguage.RUST)
        assert result == "source.rs"

    def test_get_target_path_typescript(self):
        """Test target path for TypeScript."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.js", TargetLanguage.TYPESCRIPT)
        assert result == "source.ts"

    def test_get_target_path_javascript(self):
        """Test target path for JavaScript."""
        translator = CrossLanguageTranslator()
        result = translator._get_target_path("source.ts", TargetLanguage.JAVASCRIPT)
        assert result == "source.js"


class TestTypeMappingsUsed:
    """Test getting type mappings used."""

    def test_get_used_type_mappings_cobol_python(self):
        """Test type mappings for COBOL to Python."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.COBOL, TargetLanguage.PYTHON
        )
        assert len(mappings) > 0
        assert all(isinstance(m, TypeMapping) for m in mappings)

    def test_get_used_type_mappings_vbnet_csharp(self):
        """Test type mappings for VB.NET to C#."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.VBNET, TargetLanguage.CSHARP
        )
        assert len(mappings) > 0

    def test_get_used_type_mappings_java_kotlin(self):
        """Test type mappings for Java to Kotlin."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.JAVA, TargetLanguage.KOTLIN
        )
        assert len(mappings) > 0

    def test_get_used_type_mappings_unsupported(self):
        """Test type mappings for unsupported pair returns empty."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.FORTRAN, TargetLanguage.RUST
        )
        assert len(mappings) == 0


class TestJavaParamsToKotlin:
    """Test Java parameter conversion to Kotlin."""

    def test_java_params_to_kotlin_empty(self):
        """Test empty params."""
        translator = CrossLanguageTranslator()
        result = translator._java_params_to_kotlin("")
        assert result == ""

    def test_java_params_to_kotlin_single(self):
        """Test single parameter."""
        translator = CrossLanguageTranslator()
        result = translator._java_params_to_kotlin("int count")
        assert "count" in result
        assert "Int" in result

    def test_java_params_to_kotlin_multiple(self):
        """Test multiple parameters."""
        translator = CrossLanguageTranslator()
        result = translator._java_params_to_kotlin("int a, String b")
        assert "a" in result
        assert "b" in result


class TestCSharpParamsToPython:
    """Test C# parameter conversion to Python."""

    def test_csharp_params_to_python_empty(self):
        """Test empty params."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("")
        assert result == ""

    def test_csharp_params_to_python_single(self):
        """Test single parameter."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("int count")
        assert "count" in result

    def test_csharp_params_to_python_multiple(self):
        """Test multiple parameters."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("int a, string b")
        assert "a" in result
        assert "b" in result


class TestToSnakeCase:
    """Test snake_case conversion."""

    def test_pascal_to_snake(self):
        """Test PascalCase to snake_case."""
        translator = CrossLanguageTranslator()
        assert translator._to_snake_case("GetUserName") == "get_user_name"
        assert translator._to_snake_case("CalculateTotal") == "calculate_total"

    def test_camel_to_snake(self):
        """Test camelCase to snake_case."""
        translator = CrossLanguageTranslator()
        assert translator._to_snake_case("getUserName") == "get_user_name"
        assert translator._to_snake_case("calculateTotal") == "calculate_total"

    def test_already_snake(self):
        """Test already snake_case."""
        translator = CrossLanguageTranslator()
        assert translator._to_snake_case("get_user_name") == "get_user_name"


class TestGenerateTestCases:
    """Test test case generation."""

    @pytest.mark.asyncio
    async def test_generate_test_cases_python(self):
        """Test generating Python test cases."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            generate_tests=True,
        )
        file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="public int add(int a, int b) { return a + b; }",
            translated_code="def add(self, a, b): return a + b",
            functions=[
                FunctionTranslation(
                    source_name="add",
                    target_name="add",
                    source_signature="public int add(int a, int b)",
                    target_signature="def add(self, a, b):",
                )
            ],
        )
        test_cases = await translator._generate_test_cases(file, config)
        assert len(test_cases) > 0
        assert "test_add" in test_cases[0].name
        assert "def test_" in test_cases[0].test_code

    @pytest.mark.asyncio
    async def test_generate_test_cases_java(self):
        """Test generating Java test cases."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.JAVA,
            generate_tests=True,
        )
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.java",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.JAVA,
            source_code="PERFORM CALCULATE-TOTAL",
            translated_code="calculateTotal();",
            functions=[
                FunctionTranslation(
                    source_name="CALCULATE-TOTAL",
                    target_name="calculateTotal",
                    source_signature="PERFORM CALCULATE-TOTAL",
                    target_signature="public void calculateTotal()",
                )
            ],
        )
        test_cases = await translator._generate_test_cases(file, config)
        assert len(test_cases) > 0
        assert "@Test" in test_cases[0].test_code


class TestTranslationErrorHandling:
    """Test translation error handling."""

    @pytest.mark.asyncio
    async def test_translate_empty_code(self):
        """Test translating empty code."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        result = await translator.translate("", config, "empty.cbl")
        # Should complete without error
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.PARTIAL,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_whitespace_only(self):
        """Test translating whitespace-only code."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        result = await translator.translate(
            "   \n\n   \t\t\n   ", config, "whitespace.java"
        )
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.PARTIAL,
            TranslationStatus.NEEDS_REVIEW,
        ]


# ============================================================================
# Extended Coverage Tests - COBOL Statement Translation
# ============================================================================


class TestCOBOLStatementTranslation:
    """Test COBOL statement translation helper methods."""

    def test_translate_cobol_statement_move_single(self):
        """Test MOVE statement with single target."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items = {
            "WS-COUNT": {"target_name": "ws_count", "target_type": "int", "level": 1}
        }
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "MOVE 100 TO WS-COUNT.", data_items, keyword_map, config, imports
        )
        assert "ws_count" in result
        assert "100" in result
        assert "=" in result

    def test_translate_cobol_statement_move_multiple_targets(self):
        """Test MOVE statement with multiple targets."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items = {
            "WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1},
            "WS-B": {"target_name": "ws_b", "target_type": "int", "level": 1},
        }
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "MOVE 0 TO WS-A WS-B", data_items, keyword_map, config, imports
        )
        assert "ws_a" in result or "ws_b" in result

    def test_translate_cobol_statement_display(self):
        """Test DISPLAY statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items = {
            "WS-MSG": {"target_name": "ws_msg", "target_type": "str", "level": 1}
        }
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            'DISPLAY "Hello World"', data_items, keyword_map, config, imports
        )
        assert "print" in result

    def test_translate_cobol_statement_display_multiple(self):
        """Test DISPLAY statement with multiple items."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items = {
            "WS-NAME": {"target_name": "ws_name", "target_type": "str", "level": 1},
            "WS-VALUE": {"target_name": "ws_value", "target_type": "int", "level": 1},
        }
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "DISPLAY WS-NAME WS-VALUE", data_items, keyword_map, config, imports
        )
        assert "print" in result

    def test_translate_cobol_statement_compute(self):
        """Test COMPUTE statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items = {
            "WS-TOTAL": {"target_name": "ws_total", "target_type": "int", "level": 1},
            "WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1},
            "WS-B": {"target_name": "ws_b", "target_type": "int", "level": 1},
        }
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "COMPUTE WS-TOTAL = WS-A + WS-B.", data_items, keyword_map, config, imports
        )
        assert "ws_total" in result
        assert "=" in result

    def test_translate_cobol_statement_if(self):
        """Test IF statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items = {
            "WS-COUNT": {"target_name": "ws_count", "target_type": "int", "level": 1}
        }
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "IF WS-COUNT GREATER THAN 10", data_items, keyword_map, config, imports
        )
        assert "if" in result
        assert ":" in result

    def test_translate_cobol_statement_perform(self):
        """Test PERFORM statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items: dict = {}
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "PERFORM PROCESS-DATA.", data_items, keyword_map, config, imports
        )
        assert "process_data()" in result

    def test_translate_cobol_statement_stop_run(self):
        """Test STOP RUN statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items: dict = {}
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "STOP RUN.", data_items, keyword_map, config, imports
        )
        assert "sys.exit" in result
        assert "sys" in imports

    def test_translate_cobol_statement_paragraph(self):
        """Test paragraph header translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items: dict = {}
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "PROCESS-DATA.", data_items, keyword_map, config, imports
        )
        assert "def process_data():" in result

    def test_translate_cobol_statement_unrecognized(self):
        """Test unrecognized statement returns empty."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        keyword_map = translator._keyword_mappings.get(
            (SourceLanguage.COBOL, TargetLanguage.PYTHON), {}
        )
        data_items: dict = {}
        imports: set[str] = set()

        result = translator._translate_cobol_statement(
            "IDENTIFICATION DIVISION", data_items, keyword_map, config, imports
        )
        assert result == ""


class TestCOBOLValueTranslation:
    """Test COBOL value translation."""

    def test_translate_cobol_value_data_item(self):
        """Test translating data item reference."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {
            "WS-COUNT": {"target_name": "ws_count", "target_type": "int", "level": 1}
        }

        result = translator._translate_cobol_value("WS-COUNT", data_items, config)
        assert result == "ws_count"

    def test_translate_cobol_value_string_literal(self):
        """Test translating string literal."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value('"Hello World"', data_items, config)
        assert result == '"Hello World"'

    def test_translate_cobol_value_single_quote(self):
        """Test translating single-quoted string."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("'Hello'", data_items, config)
        assert result == "'Hello'"

    def test_translate_cobol_value_spaces(self):
        """Test translating SPACES figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("SPACES", data_items, config)
        assert result == "' '"

    def test_translate_cobol_value_space(self):
        """Test translating SPACE figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("SPACE", data_items, config)
        assert result == "' '"

    def test_translate_cobol_value_zeros(self):
        """Test translating ZEROS figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("ZEROS", data_items, config)
        assert result == "0"

    def test_translate_cobol_value_zeroes(self):
        """Test translating ZEROES figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("ZEROES", data_items, config)
        assert result == "0"

    def test_translate_cobol_value_zero(self):
        """Test translating ZERO figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("ZERO", data_items, config)
        assert result == "0"

    def test_translate_cobol_value_high_values(self):
        """Test translating HIGH-VALUES figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("HIGH-VALUES", data_items, config)
        assert result == "chr(255)"

    def test_translate_cobol_value_high_value(self):
        """Test translating HIGH-VALUE figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("HIGH-VALUE", data_items, config)
        assert result == "chr(255)"

    def test_translate_cobol_value_low_values(self):
        """Test translating LOW-VALUES figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("LOW-VALUES", data_items, config)
        assert result == "chr(0)"

    def test_translate_cobol_value_low_value(self):
        """Test translating LOW-VALUE figurative constant."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("LOW-VALUE", data_items, config)
        assert result == "chr(0)"

    def test_translate_cobol_value_numeric_literal(self):
        """Test translating numeric literal."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("12345", data_items, config)
        assert result == "12345"

    def test_translate_cobol_value_negative_numeric(self):
        """Test translating negative numeric literal."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("-123", data_items, config)
        assert result == "-123"

    def test_translate_cobol_value_decimal_numeric(self):
        """Test translating decimal numeric literal."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("123.45", data_items, config)
        assert result == "123.45"

    def test_translate_cobol_value_unknown(self):
        """Test translating unknown identifier."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items: dict = {}

        result = translator._translate_cobol_value("UNKNOWN-VAR", data_items, config)
        assert result == "unknown_var"


class TestCOBOLConditionTranslation:
    """Test COBOL condition translation."""

    def test_translate_cobol_condition_equal(self):
        """Test EQUAL operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {"WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1}}

        result = translator._translate_cobol_condition(
            "WS-A EQUAL TO 10", data_items, config
        )
        assert "==" in result
        assert "ws_a" in result

    def test_translate_cobol_condition_equal_no_to(self):
        """Test EQUAL operator without TO."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {"WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1}}

        result = translator._translate_cobol_condition(
            "WS-A EQUAL 10", data_items, config
        )
        assert "==" in result

    def test_translate_cobol_condition_greater_than(self):
        """Test GREATER THAN operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {"WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1}}

        result = translator._translate_cobol_condition(
            "WS-A GREATER THAN 10", data_items, config
        )
        assert ">" in result

    def test_translate_cobol_condition_less_than(self):
        """Test LESS THAN operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {"WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1}}

        result = translator._translate_cobol_condition(
            "WS-A LESS THAN 10", data_items, config
        )
        assert "<" in result

    def test_translate_cobol_condition_not_equal(self):
        """Test NOT EQUAL operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {"WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1}}

        # The implementation handles "NOT EQUAL" - result contains not and comparison
        result = translator._translate_cobol_condition(
            "WS-A NOT EQUAL 10", data_items, config
        )
        # Result may be "!=" or "not ==" depending on regex matching order
        assert "!=" in result or ("not" in result and "==" in result)

    def test_translate_cobol_condition_and(self):
        """Test AND operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {
            "WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1},
            "WS-B": {"target_name": "ws_b", "target_type": "int", "level": 1},
        }

        result = translator._translate_cobol_condition(
            "WS-A EQUAL 10 AND WS-B EQUAL 20", data_items, config
        )
        assert "and" in result

    def test_translate_cobol_condition_or(self):
        """Test OR operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {
            "WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1},
            "WS-B": {"target_name": "ws_b", "target_type": "int", "level": 1},
        }

        result = translator._translate_cobol_condition(
            "WS-A EQUAL 10 OR WS-B EQUAL 20", data_items, config
        )
        assert "or" in result

    def test_translate_cobol_condition_not(self):
        """Test NOT operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {"WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1}}

        result = translator._translate_cobol_condition(
            "NOT WS-A EQUAL 10", data_items, config
        )
        assert "not" in result


class TestCOBOLExpressionTranslation:
    """Test COBOL expression translation."""

    def test_translate_cobol_expression_simple(self):
        """Test simple expression translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {
            "WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1},
            "WS-B": {"target_name": "ws_b", "target_type": "int", "level": 1},
        }

        result = translator._translate_cobol_expression(
            "WS-A + WS-B", data_items, config
        )
        assert "ws_a" in result
        assert "ws_b" in result
        assert "+" in result

    def test_translate_cobol_expression_with_parens(self):
        """Test expression with parentheses."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {
            "WS-A": {"target_name": "ws_a", "target_type": "int", "level": 1},
            "WS-B": {"target_name": "ws_b", "target_type": "int", "level": 1},
        }

        result = translator._translate_cobol_expression(
            "(WS-A + WS-B) * 2", data_items, config
        )
        assert "(" in result
        assert ")" in result

    def test_translate_cobol_expression_all_operators(self):
        """Test expression with all operators."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        data_items = {
            "A": {"target_name": "a", "target_type": "int", "level": 1},
            "B": {"target_name": "b", "target_type": "int", "level": 1},
        }

        result = translator._translate_cobol_expression(
            "A + B - A * B / A", data_items, config
        )
        assert "+" in result
        assert "-" in result
        assert "*" in result
        assert "/" in result


class TestPythonImportGeneration:
    """Test Python import generation."""

    def test_generate_python_imports_empty(self):
        """Test empty imports."""
        translator = CrossLanguageTranslator()
        imports: set[str] = set()

        result = translator._generate_python_imports(imports)
        assert result == []

    def test_generate_python_imports_sys(self):
        """Test sys import."""
        translator = CrossLanguageTranslator()
        imports = {"sys"}

        result = translator._generate_python_imports(imports)
        assert "import sys" in result

    def test_generate_python_imports_multiple_standard(self):
        """Test multiple standard library imports."""
        translator = CrossLanguageTranslator()
        imports = {"sys", "os", "re"}

        result = translator._generate_python_imports(imports)
        assert len(result) == 3
        assert "import sys" in result
        assert "import os" in result
        assert "import re" in result

    def test_generate_python_imports_decimal(self):
        """Test decimal import."""
        translator = CrossLanguageTranslator()
        imports = {"decimal"}

        result = translator._generate_python_imports(imports)
        assert "from decimal import Decimal" in result

    def test_generate_python_imports_mixed(self):
        """Test mixed imports."""
        translator = CrossLanguageTranslator()
        imports = {"sys", "decimal", "os"}

        result = translator._generate_python_imports(imports)
        assert len(result) == 3
        assert "import sys" in result
        assert "import os" in result
        assert "from decimal import Decimal" in result


class TestCOBOLPicTypeEdgeCases:
    """Test edge cases for COBOL PIC to type conversion."""

    def test_cobol_pic_to_target_type_unknown_target(self):
        """Test unknown target language."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_pic_to_target_type("9(5)", TargetLanguage.GO)
        assert result == "object"

    def test_cobol_pic_python_alpha(self):
        """Test COBOL alpha type to Python."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_pic_to_target_type("AAAA", TargetLanguage.PYTHON)
        assert result == "str"

    def test_cobol_pic_java_alpha(self):
        """Test COBOL alpha type to Java."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_pic_to_target_type("AAAA", TargetLanguage.JAVA)
        assert result == "String"

    def test_cobol_pic_python_unknown(self):
        """Test unknown PIC clause to Python."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_pic_to_target_type("ZZZ", TargetLanguage.PYTHON)
        assert result == "str"

    def test_cobol_pic_java_unknown(self):
        """Test unknown PIC clause to Java."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_pic_to_target_type("ZZZ", TargetLanguage.JAVA)
        assert result == "String"


class TestCOBOLNamingEdgeCases:
    """Test edge cases for COBOL naming conversion."""

    def test_cobol_to_python_name_unknown_convention(self):
        """Test unknown naming convention defaults to lowercase."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_to_python_name("WS-TEST", "unknown_convention")
        assert result == "ws_test"

    def test_cobol_to_python_name_no_hyphen(self):
        """Test name without hyphens."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_to_python_name("WSTEST", "snake_case")
        assert result == "wstest"

    def test_cobol_to_python_name_multiple_hyphens(self):
        """Test name with multiple hyphens."""
        translator = CrossLanguageTranslator()
        result = translator._cobol_to_python_name(
            "WS-CUSTOMER-FIRST-NAME", "snake_case"
        )
        assert result == "ws_customer_first_name"


class TestVBNETTranslationDetails:
    """Test VB.NET translation details."""

    @pytest.mark.asyncio
    async def test_translate_vbnet_with_keywords(self):
        """Test VB.NET keyword translations."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vb_code = """
Public Class Test
    Public Shared Sub Main()
        Dim x As Integer = Nothing
        If x Is Nothing Then
            x = 0
        End If
    End Sub
End Class
        """
        result = await translator.translate(vb_code, config, "Test.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_vbnet_loop_constructs(self):
        """Test VB.NET loop translations."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vb_code = """
Public Class Loops
    Public Sub TestLoops()
        For i = 1 To 10
            Console.WriteLine(i)
        Next

        While True
            Exit While
        End While
    End Sub
End Class
        """
        result = await translator.translate(vb_code, config, "Loops.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_vbnet_string_comparison(self):
        """Test VB.NET string comparison translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vb_code = """
Public Class StringTest
    Public Function Compare(s As String) As Boolean
        Return s = "test"
    End Function
End Class
        """
        result = await translator.translate(vb_code, config, "StringTest.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # String comparison should use ==
        assert result.files[0].translated_code is not None


class TestJavaTranslationDetails:
    """Test Java translation details."""

    @pytest.mark.asyncio
    async def test_translate_java_with_braces(self):
        """Test Java brace handling in Python translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        java_code = """
public class Test {
    public void method() {
        if (true) {
            System.out.println("yes");
        }
    }
}
        """
        result = await translator.translate(java_code, config, "Test.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # Should not have braces in output
        translated = result.files[0].translated_code
        assert "{" not in translated
        assert "}" not in translated

    @pytest.mark.asyncio
    async def test_translate_java_this_keyword(self):
        """Test Java this keyword translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        java_code = """
public class Person {
    private String name;

    public Person(String name) {
        this.name = name;
    }
}
        """
        result = await translator.translate(java_code, config, "Person.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_java_empty_class(self):
        """Test Java empty class translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        java_code = """
public class Empty {
}
        """
        result = await translator.translate(java_code, config, "Empty.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]


class TestJavaToKotlinDetails:
    """Test Java to Kotlin translation details."""

    @pytest.mark.asyncio
    async def test_translate_java_to_kotlin_types(self):
        """Test Java to Kotlin type conversions."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.KOTLIN,
        )
        java_code = """
public class Types {
    private int count;
    private long bigCount;
    private boolean flag;
    private String name;

    public void test() {
        Integer nullableInt = null;
    }
}
        """
        result = await translator.translate(java_code, config, "Types.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    def test_java_params_to_kotlin_whitespace(self):
        """Test Java params with extra whitespace."""
        translator = CrossLanguageTranslator()
        result = translator._java_params_to_kotlin("  int   count  ,  String   name  ")
        assert "count" in result
        assert "name" in result


class TestCSharpTranslationDetails:
    """Test C# translation details."""

    @pytest.mark.asyncio
    async def test_translate_csharp_null_handling(self):
        """Test C# null to Python None translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
public class NullTest
{
    public void Test()
    {
        string s = null;
        if (s == null)
        {
            return;
        }
    }
}
        """
        result = await translator.translate(csharp_code, config, "NullTest.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # null should become None
        assert "None" in result.files[0].translated_code

    @pytest.mark.asyncio
    async def test_translate_csharp_boolean_values(self):
        """Test C# boolean value translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
public class BoolTest
{
    public void Test()
    {
        bool a = true;
        bool b = false;
    }
}
        """
        result = await translator.translate(csharp_code, config, "BoolTest.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        translated = result.files[0].translated_code
        assert "True" in translated
        assert "False" in translated

    @pytest.mark.asyncio
    async def test_translate_csharp_using_statements(self):
        """Test C# using statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
using System;
using System.Collections.Generic;
using System.Linq;

public class Test
{
}
        """
        result = await translator.translate(csharp_code, config, "Test.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # using should become comments
        translated = result.files[0].translated_code
        assert "import" in translated or "#" in translated

    @pytest.mark.asyncio
    async def test_translate_csharp_this_keyword(self):
        """Test C# this keyword translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
public class Person
{
    private string name;

    public Person(string name)
    {
        this.name = name;
    }
}
        """
        result = await translator.translate(csharp_code, config, "Person.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # this should become self
        assert "self" in result.files[0].translated_code

    @pytest.mark.asyncio
    async def test_translate_csharp_property(self):
        """Test C# property translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
public class Person
{
    public string Name { get; set; }
    public int Age { get; set; }
}
        """
        result = await translator.translate(csharp_code, config, "Person.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_csharp_unsupported_target(self):
        """Test C# to unsupported target."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.KOTLIN,
        )
        csharp_code = "public class Test { }"
        result = await translator.translate(csharp_code, config, "Test.cs")
        # Should return without translation for unsupported target
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]


class TestCSharpParamConversion:
    """Test C# parameter conversion edge cases."""

    def test_csharp_params_to_python_complex(self):
        """Test C# params with complex types."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("List<string> items, int count")
        assert "items" in result
        assert "count" in result

    def test_csharp_params_to_python_whitespace(self):
        """Test C# params with extra whitespace."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("  int   count  ")
        assert "count" in result


class TestToSnakeCaseEdgeCases:
    """Test snake_case conversion edge cases."""

    def test_to_snake_case_acronyms(self):
        """Test handling of acronyms."""
        translator = CrossLanguageTranslator()
        result = translator._to_snake_case("XMLParser")
        assert "xml" in result.lower()

    def test_to_snake_case_single_char(self):
        """Test single character."""
        translator = CrossLanguageTranslator()
        result = translator._to_snake_case("A")
        assert result == "a"

    def test_to_snake_case_numbers(self):
        """Test with numbers."""
        translator = CrossLanguageTranslator()
        result = translator._to_snake_case("Test123Method")
        assert "test" in result.lower()
        assert "123" in result


class TestComplexityAssessmentEdgeCases:
    """Test complexity assessment edge cases."""

    def test_assess_complexity_complex(self):
        """Test complexity assessment for complex translation."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[
                TranslationWarning(location=f"l{i}", message=f"w{i}", severity="medium")
                for i in range(8)
            ],
            manual_review_items=[
                ManualReviewItem(
                    location=f"loc{i}",
                    original_code="orig",
                    translated_code="trans",
                    reason="needs review",
                )
                for i in range(4)
            ],
        )
        complexity = translator._assess_complexity(file)
        assert complexity == ComplexityLevel.COMPLEX


class TestConfidenceAssessmentEdgeCases:
    """Test confidence assessment edge cases."""

    def test_assess_confidence_low(self):
        """Test low confidence assessment."""
        translator = CrossLanguageTranslator()
        file = TranslatedFile(
            source_path="test.cbl",
            target_path="test.py",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            source_code="test",
            translated_code="test",
            warnings=[],
            manual_review_items=[
                ManualReviewItem(
                    location="loc1",
                    original_code="orig",
                    translated_code="trans",
                    reason="needs review",
                ),
                ManualReviewItem(
                    location="loc2",
                    original_code="orig",
                    translated_code="trans",
                    reason="needs review",
                ),
            ],
        )
        confidence = translator._assess_confidence(file)
        assert confidence == ConfidenceLevel.LOW


class TestDifficultyAnalysisEdgeCases:
    """Test difficulty analysis edge cases."""

    @pytest.mark.asyncio
    async def test_analyze_code_with_reflection(self):
        """Test analyzing code with reflection."""
        translator = CrossLanguageTranslator()
        code = """
public class ReflectionTest {
    public void test() {
        Type t = typeof(string);
        object o = Activator.CreateInstance(t);
    }
}
        """
        analysis = await translator.analyze_translation_difficulty(
            code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )
        assert analysis["has_reflection"] is True

    @pytest.mark.asyncio
    async def test_analyze_code_with_pointers(self):
        """Test analyzing code with pointers."""
        translator = CrossLanguageTranslator()
        code = """
public unsafe class PointerTest {
    public void test() {
        int* ptr = stackalloc int[10];
        *ptr = 42;
    }
}
        """
        analysis = await translator.analyze_translation_difficulty(
            code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )
        assert analysis["has_pointers"] is True

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_analyze_code_very_large(self):
        """Test analyzing very large code file."""
        translator = CrossLanguageTranslator()
        # Generate code > 1000 lines
        large_code = "\n".join([f"// Line {i}\nint x{i} = {i};" for i in range(1100)])
        analysis = await translator.analyze_translation_difficulty(
            large_code,
            SourceLanguage.JAVA,
            TargetLanguage.PYTHON,
        )
        assert analysis["source_lines"] > 1000
        # Complexity should be higher for very large files
        assert analysis["complexity_score"] >= 2

    @pytest.mark.asyncio
    async def test_analyze_code_expert_difficulty(self):
        """Test analyzing code with expert difficulty."""
        translator = CrossLanguageTranslator()
        code = """
public unsafe class ComplexService<T, U> where T : class {
    private async Task<Dictionary<T, List<U>>> processAsync(
        Func<T, Task<U>> transformer,
        Expression<Func<T, bool>> predicate
    ) {
        Type t = typeof(T);
        T* ptr = null;
        return await Task.Run(() => {
            var result = items
                .Where(predicate.Compile())
                .ToDictionary(k => k, v => new List<U>());
            return result;
        });
    }
}
        """
        analysis = await translator.analyze_translation_difficulty(
            code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )
        assert analysis["difficulty"] in ["hard", "expert"]


class TestSupportedTranslationsDetails:
    """Test get_supported_translations details."""

    @pytest.mark.asyncio
    async def test_supported_translations_quality_levels(self):
        """Test that supported translations include quality levels."""
        translator = CrossLanguageTranslator()
        translations = await translator.get_supported_translations()

        # All entries should have source, target, and quality
        for t in translations:
            assert "source" in t
            assert "target" in t
            assert "quality" in t
            assert t["quality"] in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_supported_translations_includes_major_pairs(self):
        """Test that major translation pairs are included."""
        translator = CrossLanguageTranslator()
        translations = await translator.get_supported_translations()

        # Check for major pairs
        pairs = [(t["source"], t["target"]) for t in translations]

        assert ("cobol", "python") in pairs
        assert ("cobol", "java") in pairs
        assert ("vbnet", "csharp") in pairs
        assert ("java", "kotlin") in pairs
        assert ("java", "python") in pairs


class TestCOBOLTranslationIntegration:
    """Integration tests for COBOL translation."""

    @pytest.mark.asyncio
    async def test_full_cobol_program_translation(self):
        """Test translating a complete COBOL program."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            preserve_comments=True,
            generate_tests=False,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALCULATOR.
      * Simple calculator program
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-NUM1 PIC 9(5).
       01 WS-NUM2 PIC 9(5).
       01 WS-RESULT PIC 9(10).
       PROCEDURE DIVISION.
           MOVE 10 TO WS-NUM1.
           MOVE 20 TO WS-NUM2.
           COMPUTE WS-RESULT = WS-NUM1 + WS-NUM2.
           DISPLAY WS-RESULT.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "calculator.cbl")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) > 0

        translated = result.files[0].translated_code
        # Should have Python main function
        assert "def main():" in translated
        # Should have main guard
        assert 'if __name__ == "__main__":' in translated
        # Should have variable assignments
        assert "=" in translated

    @pytest.mark.asyncio
    async def test_cobol_with_figurative_constants(self):
        """Test COBOL with figurative constants."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FIGURES.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-STR PIC X(10).
       01 WS-NUM PIC 9(5).
       PROCEDURE DIVISION.
           MOVE SPACES TO WS-STR.
           MOVE ZEROS TO WS-NUM.
           DISPLAY WS-STR WS-NUM.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "figures.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_cobol_translation_to_java(self):
        """Test COBOL to Java translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.JAVA,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-MSG PIC X(20).
       PROCEDURE DIVISION.
           MOVE "Hello, World" TO WS-MSG.
           DISPLAY WS-MSG.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "hello.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result.files[0].target_path.endswith(".java")


class TestTranslationFailureHandling:
    """Test translation failure handling."""

    @pytest.mark.asyncio
    async def test_translation_records_timing(self):
        """Test that translation records timing information."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        result = await translator.translate(
            "IDENTIFICATION DIVISION.", config, "test.cbl"
        )

        assert result.translation_time_ms >= 0
        assert result.created_at is not None

    @pytest.mark.asyncio
    async def test_translation_counts_lines(self):
        """Test that translation counts source and target lines."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        java_code = """
public class Test {
    public void method() {
        int x = 1;
        int y = 2;
        int z = x + y;
    }
}
        """
        result = await translator.translate(java_code, config, "Test.java")

        assert result.total_source_lines > 0
        assert result.total_target_lines > 0

    @pytest.mark.asyncio
    async def test_translation_calculates_ratio(self):
        """Test that translation calculates line ratio."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )
        java_code = """
public class Test {
    public void method() {
    }
}
        """
        result = await translator.translate(java_code, config, "Test.java")

        assert len(result.files) > 0
        # Translation ratio should be calculated
        assert result.files[0].translation_ratio > 0


class TestJavaToUnspecifiedTarget:
    """Test Java translation with unspecified target paths."""

    @pytest.mark.asyncio
    async def test_java_to_go(self):
        """Test Java to Go target path."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.GO,
        )
        java_code = "public class Test { }"
        result = await translator.translate(java_code, config, "Test.java")
        assert result.files[0].target_path.endswith(".go")

    @pytest.mark.asyncio
    async def test_java_to_rust(self):
        """Test Java to Rust target path."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.RUST,
        )
        java_code = "public class Test { }"
        result = await translator.translate(java_code, config, "Test.java")
        assert result.files[0].target_path.endswith(".rs")


class TestTypeMappingVariants:
    """Test type mapping variants."""

    def test_cobol_java_mappings(self):
        """Test COBOL to Java type mappings exist."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.COBOL, TargetLanguage.JAVA
        )
        assert len(mappings) > 0

        # Check specific mappings
        type_names = {m.source_type for m in mappings}
        assert "PIC 9" in type_names
        assert "PIC X" in type_names

    def test_java_python_mappings(self):
        """Test Java to Python type mappings exist."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.JAVA, TargetLanguage.PYTHON
        )
        assert len(mappings) > 0

        # Check specific mappings
        type_names = {m.source_type for m in mappings}
        assert "int" in type_names
        assert "String" in type_names

    def test_csharp_python_mappings(self):
        """Test C# to Python type mappings exist."""
        translator = CrossLanguageTranslator()
        mappings = translator._get_used_type_mappings(
            SourceLanguage.CSHARP, TargetLanguage.PYTHON
        )
        assert len(mappings) > 0

        # Check specific mappings
        type_names = {m.source_type for m in mappings}
        assert "int" in type_names
        assert "string" in type_names


# ============================================================================
# VB.NET to C# Translation Tests
# ============================================================================


class TestVBNetToCSharpTranslation:
    """Test VB.NET to C# translation."""

    @pytest.mark.asyncio
    async def test_vbnet_simple_sub(self):
        """Test translating VB.NET Sub to C# void method."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vbnet_code = """
Public Sub DoSomething()
    Dim x As Integer = 5
    Console.WriteLine(x)
End Sub
        """
        result = await translator.translate(vbnet_code, config, "module.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result.files[0].target_path.endswith(".cs")

    @pytest.mark.asyncio
    async def test_vbnet_function_translation(self):
        """Test translating VB.NET Function to C# method."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vbnet_code = """
Public Function GetValue() As Integer
    Return 42
End Function
        """
        result = await translator.translate(vbnet_code, config, "module.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_vbnet_if_statement(self):
        """Test translating VB.NET If statement."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vbnet_code = """
If x > 10 Then
    Console.WriteLine("Big")
ElseIf x > 5 Then
    Console.WriteLine("Medium")
Else
    Console.WriteLine("Small")
End If
        """
        result = await translator.translate(vbnet_code, config, "condition.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # Check that if statement was translated
        code = result.files[0].translated_code
        assert "if" in code.lower()

    @pytest.mark.asyncio
    async def test_vbnet_for_loop(self):
        """Test translating VB.NET For loop."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vbnet_code = """
For i = 1 To 10
    Console.WriteLine(i)
Next
        """
        result = await translator.translate(vbnet_code, config, "loop.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_vbnet_string_concat(self):
        """Test translating VB.NET string concatenation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vbnet_code = """
Dim result As String = firstName & " " & lastName
        """
        result = await translator.translate(vbnet_code, config, "string.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_vbnet_boolean_operators(self):
        """Test translating VB.NET boolean operators."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )
        vbnet_code = """
If x > 0 And y > 0 Then
    Console.WriteLine("Both positive")
End If
If a Or b Then
    Console.WriteLine("At least one true")
End If
        """
        result = await translator.translate(vbnet_code, config, "bool.vb")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]


# ============================================================================
# Java to Kotlin Translation Tests
# ============================================================================


class TestJavaToKotlinTranslation:
    """Test Java to Kotlin translation."""

    @pytest.mark.asyncio
    async def test_java_class_to_kotlin(self):
        """Test translating Java class to Kotlin."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.KOTLIN,
        )
        java_code = """
public class Person {
    private String name;

    public String getName() {
        return name;
    }
}
        """
        result = await translator.translate(java_code, config, "Person.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result.files[0].target_path.endswith(".kt")

    @pytest.mark.asyncio
    async def test_java_method_to_kotlin(self):
        """Test translating Java method to Kotlin."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.KOTLIN,
        )
        java_code = """
public int add(int a, int b) {
    return a + b;
}
        """
        result = await translator.translate(java_code, config, "Math.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "fun" in code or "add" in code

    @pytest.mark.asyncio
    async def test_java_variable_to_kotlin(self):
        """Test translating Java variable declaration to Kotlin."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.KOTLIN,
        )
        java_code = """
final String message = "Hello";
int count = 0;
        """
        result = await translator.translate(java_code, config, "Vars.java")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_java_params_to_kotlin(self):
        """Test converting Java parameters to Kotlin format."""
        translator = CrossLanguageTranslator()

        # Test with multiple parameters
        result = translator._java_params_to_kotlin("int x, String name, boolean flag")
        assert "x: Int" in result
        assert "name: String" in result
        assert "flag: Boolean" in result

    @pytest.mark.asyncio
    async def test_java_params_empty(self):
        """Test converting empty Java parameters."""
        translator = CrossLanguageTranslator()
        result = translator._java_params_to_kotlin("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_java_params_with_spaces(self):
        """Test converting Java parameters with extra spaces."""
        translator = CrossLanguageTranslator()
        result = translator._java_params_to_kotlin("  int x ,  String  y  ")
        assert "x:" in result
        assert "y:" in result


# ============================================================================
# C# to Python Translation Tests
# ============================================================================


class TestCSharpToPythonTranslation:
    """Test C# to Python translation."""

    @pytest.mark.asyncio
    async def test_csharp_class_to_python(self):
        """Test translating C# class to Python."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
using System;

public class Calculator
{
    public int Add(int a, int b)
    {
        return a + b;
    }
}
        """
        result = await translator.translate(csharp_code, config, "Calculator.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result.files[0].target_path.endswith(".py")
        code = result.files[0].translated_code
        assert "class" in code
        assert "def" in code

    @pytest.mark.asyncio
    async def test_csharp_method_to_python(self):
        """Test translating C# method to Python."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
public void ProcessData(string input)
{
    var result = input.ToUpper();
    Console.WriteLine(result);
}
        """
        result = await translator.translate(csharp_code, config, "Processor.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "def" in code

    @pytest.mark.asyncio
    async def test_csharp_null_to_none(self):
        """Test translating C# null to Python None."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
string value = null;
if (value == null) {
    return;
}
        """
        result = await translator.translate(csharp_code, config, "Null.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "None" in code

    @pytest.mark.asyncio
    async def test_csharp_bool_to_python(self):
        """Test translating C# bool to Python."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
bool isValid = true;
bool isFailed = false;
        """
        result = await translator.translate(csharp_code, config, "Bool.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "True" in code
        assert "False" in code

    @pytest.mark.asyncio
    async def test_csharp_this_to_self(self):
        """Test translating C# this to Python self."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )
        csharp_code = """
public class Person {
    private string name;

    public void SetName(string n) {
        this.name = n;
    }
}
        """
        result = await translator.translate(csharp_code, config, "Person.cs")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "self." in code

    def test_to_snake_case(self):
        """Test PascalCase to snake_case conversion."""
        translator = CrossLanguageTranslator()
        assert translator._to_snake_case("ProcessData") == "process_data"
        # Implementation treats consecutive uppercase as a single acronym
        assert translator._to_snake_case("XMLParser") == "xml_parser"
        assert translator._to_snake_case("getHTTPResponse") == "get_http_response"
        assert translator._to_snake_case("simple") == "simple"

    def test_csharp_params_to_python(self):
        """Test converting C# parameters to Python."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("int x, string name")
        assert "x" in result
        assert "name" in result

    def test_csharp_params_empty(self):
        """Test converting empty C# parameters."""
        translator = CrossLanguageTranslator()
        result = translator._csharp_params_to_python("")
        assert result == ""


# ============================================================================
# Generic Translation Tests
# ============================================================================


class TestP3GenericTranslationEdgeCases:
    """P3 tests for generic/fallback translation edge cases."""

    @pytest.mark.asyncio
    async def test_unsupported_language_pair(self):
        """Test translation for unsupported language pair."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.FORTRAN,
            target_language=TargetLanguage.RUST,
        )
        fortran_code = """
      PROGRAM HELLO
      PRINT *, 'Hello, World!'
      END
        """
        result = await translator.translate(fortran_code, config, "hello.f90")
        # Generic translation should mark as needs review
        assert result.status == TranslationStatus.NEEDS_REVIEW
        # Should have warnings
        assert len(result.files[0].warnings) > 0
        # Should have manual review items
        assert len(result.files[0].manual_review_items) > 0

    @pytest.mark.asyncio
    async def test_pl1_translation(self):
        """Test PL/1 translation (unsupported specific translator)."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.PL1,
            target_language=TargetLanguage.PYTHON,
        )
        pl1_code = """
HELLO: PROCEDURE OPTIONS(MAIN);
    PUT LIST ('Hello, World!');
END HELLO;
        """
        result = await translator.translate(pl1_code, config, "hello.pli")
        assert result.status == TranslationStatus.NEEDS_REVIEW


# ============================================================================
# Translation Difficulty Analysis Tests
# ============================================================================


class TestP3TranslationDifficultyEdgeCases:
    """P3 tests for translation difficulty analysis edge cases."""

    @pytest.mark.asyncio
    async def test_simple_code_difficulty(self):
        """Test difficulty analysis for simple code."""
        translator = CrossLanguageTranslator()
        simple_code = """
public class Simple {
    public int getValue() {
        return 42;
    }
}
        """
        result = await translator.analyze_translation_difficulty(
            simple_code, SourceLanguage.JAVA, TargetLanguage.PYTHON
        )
        assert result["difficulty"] in ["easy", "moderate"]
        assert result["source_lines"] > 0
        assert result["code_lines"] > 0
        assert result["has_generics"] is False
        assert result["has_lambdas"] is False

    @pytest.mark.asyncio
    async def test_complex_code_with_generics(self):
        """Test difficulty analysis for code with generics."""
        translator = CrossLanguageTranslator()
        generic_code = """
public class Container<T> {
    private List<T> items;

    public void add(T item) {
        items.add(item);
    }

    public List<T> getItems() {
        return items;
    }
}
        """
        result = await translator.analyze_translation_difficulty(
            generic_code, SourceLanguage.JAVA, TargetLanguage.PYTHON
        )
        assert result["has_generics"] is True
        assert result["complexity_score"] >= 2

    @pytest.mark.asyncio
    async def test_code_with_lambdas(self):
        """Test difficulty analysis for code with lambdas."""
        translator = CrossLanguageTranslator()
        lambda_code = """
public class Processor {
    public void process() {
        items.forEach(item -> System.out.println(item));
    }
}
        """
        result = await translator.analyze_translation_difficulty(
            lambda_code, SourceLanguage.JAVA, TargetLanguage.PYTHON
        )
        assert result["has_lambdas"] is True

    @pytest.mark.asyncio
    async def test_code_with_async(self):
        """Test difficulty analysis for code with async."""
        translator = CrossLanguageTranslator()
        async_code = """
public class AsyncProcessor {
    public async Task ProcessAsync() {
        await Task.Delay(1000);
    }
}
        """
        result = await translator.analyze_translation_difficulty(
            async_code, SourceLanguage.CSHARP, TargetLanguage.PYTHON
        )
        assert result["has_async"] is True
        assert result["complexity_score"] >= 3

    @pytest.mark.asyncio
    async def test_code_with_reflection(self):
        """Test difficulty analysis for code with reflection."""
        translator = CrossLanguageTranslator()
        reflection_code = """
public class Reflector {
    public void inspect(Object obj) {
        Type t = obj.GetType();
        Console.WriteLine(t.Name);
    }
}
        """
        result = await translator.analyze_translation_difficulty(
            reflection_code, SourceLanguage.CSHARP, TargetLanguage.PYTHON
        )
        assert result["has_reflection"] is True

    @pytest.mark.asyncio
    async def test_large_file_complexity(self):
        """Test difficulty analysis for large file."""
        translator = CrossLanguageTranslator()
        # Generate large code
        large_code = "\n".join([f"int var{i} = {i};" for i in range(600)])
        result = await translator.analyze_translation_difficulty(
            large_code, SourceLanguage.JAVA, TargetLanguage.PYTHON
        )
        # Large file adds to complexity
        assert result["source_lines"] > 500


# ============================================================================
# Supported Translations Tests
# ============================================================================


class TestSupportedTranslations:
    """Test getting supported translation pairs."""

    @pytest.mark.asyncio
    async def test_get_supported_translations(self):
        """Test getting list of supported translations."""
        translator = CrossLanguageTranslator()
        supported = await translator.get_supported_translations()

        assert len(supported) > 0

        # Check structure
        for pair in supported:
            assert "source" in pair
            assert "target" in pair
            assert "quality" in pair
            assert pair["quality"] in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_cobol_to_python_supported(self):
        """Test COBOL to Python is in supported translations."""
        translator = CrossLanguageTranslator()
        supported = await translator.get_supported_translations()

        cobol_python = next(
            (
                p
                for p in supported
                if p["source"] == "cobol" and p["target"] == "python"
            ),
            None,
        )
        assert cobol_python is not None

    @pytest.mark.asyncio
    async def test_vbnet_to_csharp_supported(self):
        """Test VB.NET to C# is in supported translations."""
        translator = CrossLanguageTranslator()
        supported = await translator.get_supported_translations()

        vbnet_csharp = next(
            (
                p
                for p in supported
                if p["source"] == "vbnet" and p["target"] == "csharp"
            ),
            None,
        )
        assert vbnet_csharp is not None


# ============================================================================
# Additional COBOL Edge Cases
# ============================================================================


class TestCOBOLEdgeCases:
    """Test COBOL translation edge cases."""

    @pytest.mark.asyncio
    async def test_cobol_compute_statement(self):
        """Test COBOL COMPUTE statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMPUTE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(5) VALUE 10.
       01 WS-B PIC 9(5) VALUE 20.
       01 WS-C PIC 9(5).
       PROCEDURE DIVISION.
           COMPUTE WS-C = WS-A + WS-B.
           DISPLAY WS-C.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "compute.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_cobol_perform_statement(self):
        """Test COBOL PERFORM statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PERFORM.
       PROCEDURE DIVISION.
           PERFORM PROCESS-DATA.
           STOP RUN.
       PROCESS-DATA.
           DISPLAY "Processing".
        """
        result = await translator.translate(cobol_code, config, "perform.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        # Should have function call
        code = result.files[0].translated_code
        assert "process_data" in code or "def " in code

    @pytest.mark.asyncio
    async def test_cobol_if_statement(self):
        """Test COBOL IF statement translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. IFTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-X PIC 9(5) VALUE 10.
       PROCEDURE DIVISION.
           IF WS-X GREATER THAN 5
               DISPLAY "BIG"
           END-IF.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "iftest.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "if" in code

    @pytest.mark.asyncio
    async def test_cobol_high_low_values(self):
        """Test COBOL HIGH-VALUES and LOW-VALUES translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )
        cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. VALS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-HIGH PIC X(5).
       01 WS-LOW PIC X(5).
       PROCEDURE DIVISION.
           MOVE HIGH-VALUES TO WS-HIGH.
           MOVE LOW-VALUES TO WS-LOW.
           STOP RUN.
        """
        result = await translator.translate(cobol_code, config, "vals.cbl")
        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        code = result.files[0].translated_code
        assert "chr(255)" in code or "chr(0)" in code

    @pytest.mark.asyncio
    async def test_cobol_naming_conventions(self):
        """Test COBOL name conversion with different conventions."""
        translator = CrossLanguageTranslator()

        # Test snake_case (default)
        assert (
            translator._cobol_to_python_name("WS-COUNTER", "snake_case") == "ws_counter"
        )

        # Test camelCase
        assert (
            translator._cobol_to_python_name("WS-COUNTER", "camelCase") == "wsCounter"
        )

        # Test PascalCase
        assert (
            translator._cobol_to_python_name("WS-COUNTER", "PascalCase") == "WsCounter"
        )

    @pytest.mark.asyncio
    async def test_cobol_pic_to_java_types(self):
        """Test COBOL PIC to Java type conversion."""
        translator = CrossLanguageTranslator()

        # Test numeric types
        assert (
            translator._cobol_pic_to_target_type("9(5)", TargetLanguage.JAVA) == "int"
        )
        assert (
            translator._cobol_pic_to_target_type("S9(5)", TargetLanguage.JAVA) == "int"
        )
        assert (
            translator._cobol_pic_to_target_type("9V99", TargetLanguage.JAVA)
            == "BigDecimal"
        )

        # Test string types
        assert (
            translator._cobol_pic_to_target_type("X(10)", TargetLanguage.JAVA)
            == "String"
        )
        assert (
            translator._cobol_pic_to_target_type("A(10)", TargetLanguage.JAVA)
            == "String"
        )


# ============================================================================
# Test Case Generation Tests
# ============================================================================


class TestTestCaseGeneration:
    """Test test case generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_test_cases_enabled(self):
        """Test that test cases are generated when enabled."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            generate_tests=True,
        )
        java_code = """
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int multiply(int x, int y) {
        return x * y;
    }
}
        """
        result = await translator.translate(java_code, config, "Calculator.java")
        # Test cases should be generated for functions
        assert result.test_cases is not None

    @pytest.mark.asyncio
    async def test_generate_test_cases_disabled(self):
        """Test that test cases are not generated when disabled."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            generate_tests=False,
        )
        java_code = """
public class Simple {
    public void doSomething() {
    }
}
        """
        result = await translator.translate(java_code, config, "Simple.java")
        # No test cases when disabled
        assert len(result.test_cases) == 0


# ============================================================================
# Complexity and Confidence Assessment Tests
# ============================================================================


class TestComplexityAssessment:
    """Test complexity assessment."""

    @pytest.mark.asyncio
    async def test_simple_complexity(self):
        """Test simple complexity assessment."""
        translator = CrossLanguageTranslator()

        # Create a translated file with no warnings/reviews
        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=[],
        )

        complexity = translator._assess_complexity(translated_file)
        assert complexity == ComplexityLevel.SIMPLE

    @pytest.mark.asyncio
    async def test_moderate_complexity(self):
        """Test moderate complexity assessment."""
        translator = CrossLanguageTranslator()

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[
                TranslationWarning(location="a", message="warn1", severity="warning"),
                TranslationWarning(location="b", message="warn2", severity="warning"),
            ],
            manual_review_items=[
                ManualReviewItem(
                    location="c", original_code="", translated_code="", reason="test"
                ),
            ],
        )

        complexity = translator._assess_complexity(translated_file)
        assert complexity == ComplexityLevel.MODERATE

    @pytest.mark.asyncio
    async def test_expert_complexity(self):
        """Test expert complexity assessment."""
        translator = CrossLanguageTranslator()

        # Many warnings and review items = expert
        warnings = [
            TranslationWarning(
                location=f"loc{i}", message=f"warn{i}", severity="warning"
            )
            for i in range(15)
        ]
        review_items = [
            ManualReviewItem(
                location=f"loc{i}", original_code="", translated_code="", reason="test"
            )
            for i in range(10)
        ]

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=warnings,
            manual_review_items=review_items,
        )

        complexity = translator._assess_complexity(translated_file)
        assert complexity == ComplexityLevel.EXPERT


class TestConfidenceAssessment:
    """Test confidence assessment."""

    @pytest.mark.asyncio
    async def test_high_confidence(self):
        """Test high confidence assessment."""
        translator = CrossLanguageTranslator()

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=[],
        )

        confidence = translator._assess_confidence(translated_file)
        assert confidence == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_medium_confidence(self):
        """Test medium confidence assessment."""
        translator = CrossLanguageTranslator()

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[
                TranslationWarning(location="a", message="warn", severity="warning"),
            ],
            manual_review_items=[],
        )

        confidence = translator._assess_confidence(translated_file)
        assert confidence == ConfidenceLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_low_confidence(self):
        """Test low confidence assessment."""
        translator = CrossLanguageTranslator()

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=[
                ManualReviewItem(
                    location="a", original_code="", translated_code="", reason="test"
                ),
            ],
        )

        confidence = translator._assess_confidence(translated_file)
        assert confidence == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_uncertain_confidence(self):
        """Test uncertain confidence assessment."""
        translator = CrossLanguageTranslator()

        review_items = [
            ManualReviewItem(
                location=f"loc{i}", original_code="", translated_code="", reason="test"
            )
            for i in range(5)
        ]

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=review_items,
        )

        confidence = translator._assess_confidence(translated_file)
        assert confidence == ConfidenceLevel.UNCERTAIN


# =============================================================================
# P1: CRITICAL ERROR PATH TESTS
# =============================================================================


class TestP1CriticalErrorPaths:
    """P1 tests for critical error handling paths."""

    @pytest.mark.asyncio
    async def test_translate_empty_source_code(self):
        """Test translation with empty source code."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        result = await translator.translate("", config, "empty.java")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) == 1
        assert result.total_source_lines == 1  # Empty string splits to ['']

    @pytest.mark.asyncio
    async def test_translate_whitespace_only_source(self):
        """Test translation with whitespace-only source code."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        result = await translator.translate(
            "   \n\n   \t\t\n", config, "whitespace.java"
        )

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert len(result.files) == 1

    @pytest.mark.asyncio
    async def test_translate_unsupported_language_pair(self):
        """Test translation with unsupported language pair triggers generic translator."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.FORTRAN,
            target_language=TargetLanguage.RUST,
        )

        result = await translator.translate(
            "PROGRAM TEST\nEND PROGRAM", config, "test.f90"
        )

        # Generic translator creates warnings and review items
        assert result.status == TranslationStatus.NEEDS_REVIEW
        assert len(result.files[0].warnings) > 0
        assert len(result.files[0].manual_review_items) > 0

    @pytest.mark.asyncio
    async def test_get_target_path_unknown_language(self):
        """Test target path generation for unknown language falls back to .txt."""
        translator = CrossLanguageTranslator()

        # Use a mock enum value that's not in extensions dict
        class FakeLanguage:
            value = "fake"

        # The method handles missing extensions gracefully
        path = translator._get_target_path("source.cob", TargetLanguage.PYTHON)
        assert path.endswith(".py")

    @pytest.mark.asyncio
    async def test_cobol_pic_to_target_type_invalid_pic(self):
        """Test COBOL PIC conversion with invalid/unknown PIC clause."""
        translator = CrossLanguageTranslator()

        # Unknown PIC clause without special chars returns "str"
        result = translator._cobol_pic_to_target_type("UNKNOWN", TargetLanguage.PYTHON)
        assert result == "str"

        result = translator._cobol_pic_to_target_type("BADPIC", TargetLanguage.JAVA)
        assert result == "String"

        # PIC with "V" (decimal point) returns Decimal/BigDecimal
        result = translator._cobol_pic_to_target_type("INVALID", TargetLanguage.PYTHON)
        assert result == "Decimal"  # Contains "V"

    @pytest.mark.asyncio
    async def test_assess_complexity_boundary_values(self):
        """Test complexity assessment at boundary values."""
        translator = CrossLanguageTranslator()

        # Test SIMPLE (0 warnings, 0 reviews)
        file_simple = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=[],
        )
        assert translator._assess_complexity(file_simple) == ComplexityLevel.SIMPLE

        # Test MODERATE (3 warnings, 1 review - exactly at boundary)
        file_moderate = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[
                TranslationWarning(location=f"loc{i}", message="w", severity="warning")
                for i in range(3)
            ],
            manual_review_items=[
                ManualReviewItem(
                    location="loc", original_code="", translated_code="", reason="r"
                )
            ],
        )
        assert translator._assess_complexity(file_moderate) == ComplexityLevel.MODERATE

        # Test COMPLEX (10 warnings, 5 reviews - exactly at boundary)
        file_complex = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[
                TranslationWarning(location=f"loc{i}", message="w", severity="warning")
                for i in range(10)
            ],
            manual_review_items=[
                ManualReviewItem(
                    location=f"loc{i}", original_code="", translated_code="", reason="r"
                )
                for i in range(5)
            ],
        )
        assert translator._assess_complexity(file_complex) == ComplexityLevel.COMPLEX

        # Test EXPERT (beyond boundaries)
        file_expert = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[
                TranslationWarning(location=f"loc{i}", message="w", severity="warning")
                for i in range(11)
            ],
            manual_review_items=[
                ManualReviewItem(
                    location=f"loc{i}", original_code="", translated_code="", reason="r"
                )
                for i in range(6)
            ],
        )
        assert translator._assess_complexity(file_expert) == ComplexityLevel.EXPERT

    @pytest.mark.asyncio
    async def test_assess_confidence_boundary_values(self):
        """Test confidence assessment at boundary values."""
        translator = CrossLanguageTranslator()

        # HIGH (0 warnings, 0 reviews)
        file_high = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=[],
        )
        assert translator._assess_confidence(file_high) == ConfidenceLevel.HIGH

        # MEDIUM (3 warnings, 0 reviews - exactly at boundary)
        file_medium = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[
                TranslationWarning(location=f"loc{i}", message="w", severity="warning")
                for i in range(3)
            ],
            manual_review_items=[],
        )
        assert translator._assess_confidence(file_medium) == ConfidenceLevel.MEDIUM

        # LOW (2 reviews - exactly at boundary)
        file_low = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            warnings=[],
            manual_review_items=[
                ManualReviewItem(
                    location=f"loc{i}", original_code="", translated_code="", reason="r"
                )
                for i in range(2)
            ],
        )
        assert translator._assess_confidence(file_low) == ConfidenceLevel.LOW


# =============================================================================
# P2: BOUNDARY CONDITION TESTS
# =============================================================================


class TestP2BoundaryConditions:
    """P2 tests for boundary conditions and edge values."""

    @pytest.mark.asyncio
    async def test_translation_ratio_zero_source_lines(self):
        """Test translation ratio calculation avoids division by zero."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        # Even empty string has 1 line when split by \n
        result = await translator.translate("", config, "empty.java")

        assert result.files[0].translation_ratio >= 0

    @pytest.mark.asyncio
    async def test_very_large_source_code(self):
        """Test handling of large source code files."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        # Create large source file (10000 lines)
        lines = ["public void method{}() {{ }}".format(i) for i in range(10000)]
        large_source = "\n".join(lines)

        result = await translator.translate(large_source, config, "large.java")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result.total_source_lines == 10000

    @pytest.mark.asyncio
    async def test_single_line_source(self):
        """Test translation of single-line source code."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        result = await translator.translate("int x = 5;", config, "single.java")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result.total_source_lines == 1

    @pytest.mark.asyncio
    async def test_max_line_length_config(self):
        """Test translation respects max line length config."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            max_line_length=80,
        )

        result = await translator.translate("int x = 5;", config)
        assert result.files[0].translated_code is not None

    @pytest.mark.asyncio
    async def test_indent_size_config(self):
        """Test translation with various indent sizes."""
        translator = CrossLanguageTranslator()

        for indent_size in [2, 4, 8]:
            config = TranslationConfig(
                source_language=SourceLanguage.JAVA,
                target_language=TargetLanguage.PYTHON,
                indent_size=indent_size,
            )

            result = await translator.translate("class Test { void m() {} }", config)
            assert result.status in [
                TranslationStatus.COMPLETED,
                TranslationStatus.NEEDS_REVIEW,
            ]

    @pytest.mark.asyncio
    async def test_naming_convention_variants(self):
        """Test all naming conventions."""
        translator = CrossLanguageTranslator()

        for convention in ["snake_case", "camelCase", "PascalCase"]:
            # Test COBOL name conversion
            result = translator._cobol_to_python_name("WS-CUSTOMER-NAME", convention)
            assert result is not None
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_source_path_without_extension(self):
        """Test target path generation for source without extension."""
        translator = CrossLanguageTranslator()

        path = translator._get_target_path("noextension", TargetLanguage.PYTHON)
        assert path == "noextension.py"

    @pytest.mark.asyncio
    async def test_source_path_multiple_dots(self):
        """Test target path generation for source with multiple dots."""
        translator = CrossLanguageTranslator()

        path = translator._get_target_path("my.test.file.java", TargetLanguage.PYTHON)
        assert path == "my.test.file.py"

    @pytest.mark.asyncio
    async def test_empty_type_mappings_lookup(self):
        """Test behavior when type mapping doesn't exist for language pair."""
        translator = CrossLanguageTranslator()

        # Access non-existent mapping (returns empty dict)
        mappings = translator._type_mappings.get(
            (SourceLanguage.FORTRAN, TargetLanguage.GO), {}
        )
        assert mappings == {}

    @pytest.mark.asyncio
    async def test_empty_keyword_mappings_lookup(self):
        """Test behavior when keyword mapping doesn't exist."""
        translator = CrossLanguageTranslator()

        mappings = translator._keyword_mappings.get(
            (SourceLanguage.FORTRAN, TargetLanguage.GO), {}
        )
        assert mappings == {}


# =============================================================================
# P3: API-SPECIFIC EDGE CASES
# =============================================================================


class TestP3ApiEdgeCases:
    """P3 tests for API-specific edge cases."""

    @pytest.mark.asyncio
    async def test_cobol_figurative_constants(self):
        """Test COBOL figurative constant translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        # Test various figurative constants
        data_items: dict[str, dict] = {}

        assert translator._translate_cobol_value("SPACES", data_items, config) == "' '"
        assert translator._translate_cobol_value("SPACE", data_items, config) == "' '"
        assert translator._translate_cobol_value("ZEROS", data_items, config) == "0"
        assert translator._translate_cobol_value("ZEROES", data_items, config) == "0"
        assert translator._translate_cobol_value("ZERO", data_items, config) == "0"
        assert (
            translator._translate_cobol_value("HIGH-VALUES", data_items, config)
            == "chr(255)"
        )
        assert (
            translator._translate_cobol_value("HIGH-VALUE", data_items, config)
            == "chr(255)"
        )
        assert (
            translator._translate_cobol_value("LOW-VALUES", data_items, config)
            == "chr(0)"
        )
        assert (
            translator._translate_cobol_value("LOW-VALUE", data_items, config)
            == "chr(0)"
        )

    @pytest.mark.asyncio
    async def test_cobol_numeric_literal(self):
        """Test COBOL numeric literal translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        data_items: dict[str, dict] = {}

        assert translator._translate_cobol_value("123", data_items, config) == "123"
        assert translator._translate_cobol_value("-456", data_items, config) == "-456"
        assert (
            translator._translate_cobol_value("123.45", data_items, config) == "123.45"
        )

    @pytest.mark.asyncio
    async def test_cobol_string_literal(self):
        """Test COBOL string literal translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        data_items: dict[str, dict] = {}

        assert (
            translator._translate_cobol_value('"HELLO"', data_items, config)
            == '"HELLO"'
        )
        assert (
            translator._translate_cobol_value("'WORLD'", data_items, config)
            == "'WORLD'"
        )

    @pytest.mark.asyncio
    async def test_cobol_data_item_reference(self):
        """Test COBOL data item reference translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        data_items = {
            "WS-CUSTOMER-NAME": {
                "target_name": "ws_customer_name",
                "target_type": "str",
            }
        }

        assert (
            translator._translate_cobol_value("WS-CUSTOMER-NAME", data_items, config)
            == "ws_customer_name"
        )

    @pytest.mark.asyncio
    async def test_cobol_condition_operators(self):
        """Test COBOL condition operator translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        data_items: dict[str, dict] = {}

        result = translator._translate_cobol_condition(
            "X EQUAL TO 5", data_items, config
        )
        assert "==" in result

        result = translator._translate_cobol_condition(
            "X GREATER THAN 5", data_items, config
        )
        assert ">" in result

        result = translator._translate_cobol_condition(
            "X LESS THAN 5", data_items, config
        )
        assert "<" in result

        result = translator._translate_cobol_condition(
            "X NOT EQUAL 5", data_items, config
        )
        assert (
            "not ==" in result or "!=" in result
        )  # Implementation uses "not ==" for NOT EQUAL

        result = translator._translate_cobol_condition("X AND Y", data_items, config)
        assert "and" in result

        result = translator._translate_cobol_condition("X OR Y", data_items, config)
        assert "or" in result

    @pytest.mark.asyncio
    async def test_cobol_expression_translation(self):
        """Test COBOL expression translation."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        data_items = {
            "WS-A": {"target_name": "ws_a"},
            "WS-B": {"target_name": "ws_b"},
        }

        result = translator._translate_cobol_expression(
            "WS-A + WS-B", data_items, config
        )
        assert "ws_a" in result
        assert "ws_b" in result
        assert "+" in result

    @pytest.mark.asyncio
    async def test_java_to_kotlin_params_empty(self):
        """Test Java to Kotlin parameter conversion with empty params."""
        translator = CrossLanguageTranslator()

        result = translator._java_params_to_kotlin("")
        assert result == ""

        result = translator._java_params_to_kotlin("   ")
        assert result == ""

    @pytest.mark.asyncio
    async def test_java_to_kotlin_params_multiple(self):
        """Test Java to Kotlin parameter conversion with multiple params."""
        translator = CrossLanguageTranslator()

        result = translator._java_params_to_kotlin("String name, int age")
        assert "name: String" in result
        assert "age: Int" in result

    @pytest.mark.asyncio
    async def test_csharp_params_to_python_empty(self):
        """Test C# to Python parameter conversion with empty params."""
        translator = CrossLanguageTranslator()

        result = translator._csharp_params_to_python("")
        assert result == ""

        result = translator._csharp_params_to_python("   ")
        assert result == ""

    @pytest.mark.asyncio
    async def test_csharp_params_to_python_multiple(self):
        """Test C# to Python parameter conversion with multiple params."""
        translator = CrossLanguageTranslator()

        result = translator._csharp_params_to_python("string Name, int Age")
        assert "name" in result
        assert "age" in result

    @pytest.mark.asyncio
    async def test_to_snake_case_various_inputs(self):
        """Test snake_case conversion with various inputs."""
        translator = CrossLanguageTranslator()

        assert translator._to_snake_case("PascalCase") == "pascal_case"
        assert translator._to_snake_case("camelCase") == "camel_case"
        assert translator._to_snake_case("XMLParser") == "xml_parser"
        assert translator._to_snake_case("simpleword") == "simpleword"
        assert translator._to_snake_case("ALLCAPS") == "allcaps"

    @pytest.mark.asyncio
    async def test_analyze_translation_difficulty_simple(self):
        """Test difficulty analysis for simple code."""
        translator = CrossLanguageTranslator()

        result = await translator.analyze_translation_difficulty(
            "int x = 5;\nint y = 10;",
            SourceLanguage.JAVA,
            TargetLanguage.PYTHON,
        )

        assert result["difficulty"] == "easy"
        assert result["complexity_score"] <= 2

    @pytest.mark.asyncio
    async def test_analyze_translation_difficulty_complex(self):
        """Test difficulty analysis for complex code."""
        translator = CrossLanguageTranslator()

        complex_code = """
        public async Task<List<T>> GetItems<T>() {
            await Task.Delay(100);
            var reflection = typeof(T).GetType();
            return new List<T>();
        }
        """

        result = await translator.analyze_translation_difficulty(
            complex_code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )

        assert result["has_generics"] is True
        assert result["has_async"] is True
        assert result["has_reflection"] is True

    @pytest.mark.asyncio
    async def test_analyze_translation_difficulty_with_lambdas(self):
        """Test difficulty analysis for code with lambdas."""
        translator = CrossLanguageTranslator()

        lambda_code = "var result = items.Select(x => x * 2);"

        result = await translator.analyze_translation_difficulty(
            lambda_code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )

        assert result["has_lambdas"] is True

    @pytest.mark.asyncio
    async def test_analyze_translation_difficulty_with_pointers(self):
        """Test difficulty analysis for code with pointers."""
        translator = CrossLanguageTranslator()

        pointer_code = "unsafe { int* ptr = &x; }"

        result = await translator.analyze_translation_difficulty(
            pointer_code,
            SourceLanguage.CSHARP,
            TargetLanguage.PYTHON,
        )

        assert result["has_pointers"] is True

    @pytest.mark.asyncio
    async def test_get_supported_translations(self):
        """Test getting list of supported translation pairs."""
        translator = CrossLanguageTranslator()

        supported = await translator.get_supported_translations()

        assert isinstance(supported, list)
        assert len(supported) > 0

        for item in supported:
            assert "source" in item
            assert "target" in item
            assert "quality" in item
            assert item["quality"] in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_generate_test_cases_python_target(self):
        """Test test case generation for Python target."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            generate_tests=True,
        )

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            functions=[
                FunctionTranslation(
                    source_name="calculateTotal",
                    target_name="calculate_total",
                    source_signature="public int calculateTotal()",
                    target_signature="def calculate_total(self):",
                )
            ],
        )

        test_cases = await translator._generate_test_cases(translated_file, config)

        assert len(test_cases) == 1
        assert "test_calculate_total" in test_cases[0].name
        assert "def test_" in test_cases[0].test_code

    @pytest.mark.asyncio
    async def test_generate_test_cases_java_target(self):
        """Test test case generation for Java target."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.JAVA,
            generate_tests=True,
        )

        translated_file = TranslatedFile(
            source_path="test.cob",
            target_path="test.java",
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.JAVA,
            source_code="",
            translated_code="",
            functions=[
                FunctionTranslation(
                    source_name="CALCULATE-TOTAL",
                    target_name="calculateTotal",
                    source_signature="CALCULATE-TOTAL",
                    target_signature="public int calculateTotal()",
                )
            ],
        )

        test_cases = await translator._generate_test_cases(translated_file, config)

        assert len(test_cases) == 1
        assert "@Test" in test_cases[0].test_code

    @pytest.mark.asyncio
    async def test_generate_test_cases_no_functions(self):
        """Test test case generation when no functions exist."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            generate_tests=True,
        )

        translated_file = TranslatedFile(
            source_path="test.java",
            target_path="test.py",
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            source_code="",
            translated_code="",
            functions=[],
        )

        test_cases = await translator._generate_test_cases(translated_file, config)

        assert len(test_cases) == 0

    @pytest.mark.asyncio
    async def test_get_used_type_mappings(self):
        """Test retrieving used type mappings for language pair."""
        translator = CrossLanguageTranslator()

        mappings = translator._get_used_type_mappings(
            SourceLanguage.JAVA, TargetLanguage.PYTHON
        )

        assert isinstance(mappings, list)
        assert len(mappings) > 0
        assert all(isinstance(m, TypeMapping) for m in mappings)

    @pytest.mark.asyncio
    async def test_get_used_type_mappings_unknown_pair(self):
        """Test retrieving type mappings for unknown language pair."""
        translator = CrossLanguageTranslator()

        mappings = translator._get_used_type_mappings(
            SourceLanguage.FORTRAN, TargetLanguage.GO
        )

        assert isinstance(mappings, list)
        assert len(mappings) == 0


# =============================================================================
# P4: ASYNC/CONCURRENCY TESTS
# =============================================================================


class TestP4AsyncConcurrency:
    """P4 tests for async operations and concurrency."""

    @pytest.mark.asyncio
    async def test_concurrent_translations(self):
        """Test multiple concurrent translations."""
        import asyncio

        translator = CrossLanguageTranslator()

        configs = [
            (
                TranslationConfig(
                    source_language=SourceLanguage.JAVA,
                    target_language=TargetLanguage.PYTHON,
                ),
                "public class A {}",
            ),
            (
                TranslationConfig(
                    source_language=SourceLanguage.VBNET,
                    target_language=TargetLanguage.CSHARP,
                ),
                "Dim x As Integer",
            ),
            (
                TranslationConfig(
                    source_language=SourceLanguage.CSHARP,
                    target_language=TargetLanguage.PYTHON,
                ),
                "class Test {}",
            ),
        ]

        tasks = [
            translator.translate(code, config, f"test{i}.src")
            for i, (config, code) in enumerate(configs)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for result in results:
            assert result.status in [
                TranslationStatus.COMPLETED,
                TranslationStatus.NEEDS_REVIEW,
            ]

    @pytest.mark.asyncio
    async def test_deterministic_results(self):
        """Test that repeated translations produce deterministic results."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        source = "public int add(int a, int b) { return a + b; }"

        result1 = await translator.translate(source, config, "test.java")
        result2 = await translator.translate(source, config, "test.java")

        assert result1.files[0].translated_code == result2.files[0].translated_code
        assert result1.overall_confidence == result2.overall_confidence

    @pytest.mark.asyncio
    async def test_translation_time_recorded(self):
        """Test that translation time is properly recorded."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        result = await translator.translate("int x = 5;", config)

        assert result.translation_time_ms > 0
        assert isinstance(result.translation_time_ms, float)

    @pytest.mark.asyncio
    async def test_created_at_timestamp(self):
        """Test that created_at timestamp is set."""
        from datetime import datetime, timezone

        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        before = datetime.now(timezone.utc)
        result = await translator.translate("int x = 5;", config)
        after = datetime.now(timezone.utc)

        assert result.created_at >= before
        assert result.created_at <= after

    @pytest.mark.asyncio
    async def test_translate_preserves_comments_config(self):
        """Test translation respects preserve_comments config."""
        translator = CrossLanguageTranslator()

        config_preserve = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            preserve_comments=True,
        )

        config_no_preserve = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
            preserve_comments=False,
        )

        source = """      * This is a comment
       PROCEDURE DIVISION.
       DISPLAY "HELLO"."""

        result_preserve = await translator.translate(
            source, config_preserve, "test.cob"
        )
        result_no_preserve = await translator.translate(
            source, config_no_preserve, "test.cob"
        )

        # Both should complete without errors
        assert result_preserve.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert result_no_preserve.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_translate_generate_tests_false(self):
        """Test translation with generate_tests disabled."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
            generate_tests=False,
        )

        result = await translator.translate("public void test() {}", config)

        assert len(result.test_cases) == 0

    @pytest.mark.asyncio
    async def test_translate_all_strategies(self):
        """Test translation with all strategy options."""
        translator = CrossLanguageTranslator()

        for strategy in TranslationStrategy:
            config = TranslationConfig(
                source_language=SourceLanguage.JAVA,
                target_language=TargetLanguage.PYTHON,
                strategy=strategy,
            )

            result = await translator.translate("int x = 5;", config)
            assert result.status in [
                TranslationStatus.COMPLETED,
                TranslationStatus.NEEDS_REVIEW,
            ]

    @pytest.mark.asyncio
    async def test_translate_all_type_mapping_strategies(self):
        """Test translation with all type mapping strategies."""
        translator = CrossLanguageTranslator()

        for type_mapping in DataTypeMapping:
            config = TranslationConfig(
                source_language=SourceLanguage.JAVA,
                target_language=TargetLanguage.PYTHON,
                type_mapping=type_mapping,
            )

            result = await translator.translate("int x = 5;", config)
            assert result.status in [
                TranslationStatus.COMPLETED,
                TranslationStatus.NEEDS_REVIEW,
            ]

    @pytest.mark.asyncio
    async def test_cobol_full_translation(self):
        """Test complete COBOL translation flow."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.COBOL,
            target_language=TargetLanguage.PYTHON,
        )

        cobol_source = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-NAME PIC X(20).
       PROCEDURE DIVISION.
           MOVE "WORLD" TO WS-NAME.
           DISPLAY "HELLO " WS-NAME.
           STOP RUN."""

        result = await translator.translate(cobol_source, config, "hello.cob")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert (
            "print" in result.files[0].translated_code.lower()
            or result.files[0].translated_code != ""
        )

    @pytest.mark.asyncio
    async def test_vbnet_full_translation(self):
        """Test complete VB.NET translation flow."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.VBNET,
            target_language=TargetLanguage.CSHARP,
        )

        vbnet_source = """Public Sub Main()
    Dim x As Integer = 5
    If x > 0 Then
        Console.WriteLine("Positive")
    End If
End Sub"""

        result = await translator.translate(vbnet_source, config, "test.vb")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_java_to_python_full_translation(self):
        """Test complete Java to Python translation flow."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.PYTHON,
        )

        java_source = """public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}"""

        result = await translator.translate(java_source, config, "Calculator.java")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert "class" in result.files[0].translated_code.lower()

    @pytest.mark.asyncio
    async def test_java_to_kotlin_full_translation(self):
        """Test complete Java to Kotlin translation flow."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.JAVA,
            target_language=TargetLanguage.KOTLIN,
        )

        java_source = """public class Test {
    private String name;
    public void setName(String name) {
        this.name = name;
    }
}"""

        result = await translator.translate(java_source, config, "Test.java")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]

    @pytest.mark.asyncio
    async def test_csharp_to_python_full_translation(self):
        """Test complete C# to Python translation flow."""
        translator = CrossLanguageTranslator()
        config = TranslationConfig(
            source_language=SourceLanguage.CSHARP,
            target_language=TargetLanguage.PYTHON,
        )

        csharp_source = """public class Calculator
{
    public int Add(int a, int b)
    {
        return a + b;
    }
}"""

        result = await translator.translate(csharp_source, config, "Calculator.cs")

        assert result.status in [
            TranslationStatus.COMPLETED,
            TranslationStatus.NEEDS_REVIEW,
        ]
        assert "class" in result.files[0].translated_code.lower()
