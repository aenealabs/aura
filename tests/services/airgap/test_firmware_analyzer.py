"""
Tests for the firmware security analyzer service.
"""

import os

import pytest

from src.services.airgap import (
    FirmwareAnalyzer,
    FirmwareFormat,
    FirmwareTooLargeError,
    ProcessorArchitecture,
    RTOSType,
    Severity,
    VulnerabilityType,
    get_firmware_analyzer,
    reset_firmware_analyzer,
)


class TestAnalyzerInitialization:
    """Tests for analyzer initialization."""

    def test_initialize(self, test_config):
        """Test initializing analyzer."""
        analyzer = FirmwareAnalyzer(test_config)
        assert analyzer is not None

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        analyzer1 = get_firmware_analyzer()
        analyzer2 = get_firmware_analyzer()
        assert analyzer1 is analyzer2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        analyzer1 = get_firmware_analyzer()
        reset_firmware_analyzer()
        analyzer2 = get_firmware_analyzer()
        assert analyzer1 is not analyzer2


class TestFormatDetection:
    """Tests for firmware format detection."""

    def test_detect_elf_format(self, analyzer, sample_elf_file):
        """Test detecting ELF format."""
        format = analyzer.detect_format(sample_elf_file)
        assert format == FirmwareFormat.ELF

    def test_detect_pe_format(self, analyzer, temp_dir):
        """Test detecting PE format."""
        pe_file = os.path.join(temp_dir, "test.exe")
        with open(pe_file, "wb") as f:
            # PE magic number
            f.write(b"MZ" + b"\x00" * 62)

        format = analyzer.detect_format(pe_file)
        assert format == FirmwareFormat.PE

    def test_detect_ihex_format(self, analyzer, temp_dir):
        """Test detecting Intel HEX format."""
        ihex_file = os.path.join(temp_dir, "test.hex")
        with open(ihex_file, "wb") as f:
            f.write(b":100000001234567890\n")

        format = analyzer.detect_format(ihex_file)
        assert format == FirmwareFormat.IHEX

    def test_detect_srec_format(self, analyzer, temp_dir):
        """Test detecting S-record format."""
        srec_file = os.path.join(temp_dir, "test.srec")
        with open(srec_file, "wb") as f:
            f.write(b"S00E00006865616465720A")

        format = analyzer.detect_format(srec_file)
        assert format == FirmwareFormat.SREC

    def test_detect_bin_format(self, analyzer, temp_dir):
        """Test detecting raw binary format."""
        bin_file = os.path.join(temp_dir, "test.bin")
        with open(bin_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04")  # Random binary

        format = analyzer.detect_format(bin_file)
        assert format == FirmwareFormat.BIN


class TestArchitectureDetection:
    """Tests for processor architecture detection."""

    def test_detect_arm_architecture(self, analyzer, sample_elf_file):
        """Test detecting ARM architecture from ELF."""
        arch = analyzer.detect_architecture(sample_elf_file)
        assert arch == ProcessorArchitecture.ARM_CORTEX_M

    def test_detect_unknown_architecture(self, analyzer, temp_dir):
        """Test detecting unknown architecture."""
        bin_file = os.path.join(temp_dir, "test.bin")
        with open(bin_file, "wb") as f:
            f.write(b"\x00" * 64)

        arch = analyzer.detect_architecture(bin_file)
        assert arch == ProcessorArchitecture.UNKNOWN


class TestRTOSDetection:
    """Tests for RTOS detection."""

    def test_detect_freertos(self, analyzer, sample_elf_file):
        """Test detecting FreeRTOS signatures."""
        rtos_type, version = analyzer.detect_rtos(sample_elf_file)
        assert rtos_type == RTOSType.FREERTOS

    def test_detect_zephyr(self, analyzer, temp_dir):
        """Test detecting Zephyr signatures."""
        fw_file = os.path.join(temp_dir, "zephyr.bin")
        with open(fw_file, "wb") as f:
            f.write(b"ZEPHYR k_thread_create k_sem_init")

        rtos_type, version = analyzer.detect_rtos(fw_file)
        assert rtos_type == RTOSType.ZEPHYR

    def test_detect_threadx(self, analyzer, temp_dir):
        """Test detecting ThreadX signatures."""
        fw_file = os.path.join(temp_dir, "threadx.bin")
        with open(fw_file, "wb") as f:
            f.write(b"ThreadX tx_thread_create tx_semaphore_create")

        rtos_type, version = analyzer.detect_rtos(fw_file)
        assert rtos_type == RTOSType.THREADX

    def test_detect_no_rtos(self, analyzer, temp_dir):
        """Test when no RTOS is detected."""
        fw_file = os.path.join(temp_dir, "bare.bin")
        with open(fw_file, "wb") as f:
            f.write(b"main loop while true")

        rtos_type, version = analyzer.detect_rtos(fw_file)
        assert rtos_type == RTOSType.UNKNOWN


class TestVulnerabilityDetection:
    """Tests for vulnerability detection."""

    def test_find_buffer_overflow_vuln(self, analyzer, sample_firmware_with_vulns):
        """Test finding buffer overflow vulnerabilities."""
        issues = analyzer.find_vulnerable_functions(sample_firmware_with_vulns)

        strcpy_issues = [i for i in issues if "strcpy" in i.description]
        assert len(strcpy_issues) > 0
        assert strcpy_issues[0].vulnerability_type == VulnerabilityType.BUFFER_OVERFLOW

    def test_find_gets_vuln(self, analyzer, sample_firmware_with_vulns):
        """Test finding gets() vulnerabilities."""
        issues = analyzer.find_vulnerable_functions(sample_firmware_with_vulns)

        gets_issues = [i for i in issues if "gets" in i.description]
        assert len(gets_issues) > 0
        assert gets_issues[0].severity == Severity.CRITICAL

    def test_find_command_injection_vuln(self, analyzer, sample_firmware_with_vulns):
        """Test finding command injection vulnerabilities."""
        issues = analyzer.find_vulnerable_functions(sample_firmware_with_vulns)

        system_issues = [i for i in issues if "system" in i.description]
        assert len(system_issues) > 0
        assert (
            system_issues[0].vulnerability_type == VulnerabilityType.COMMAND_INJECTION
        )

    def test_find_weak_crypto(self, analyzer, sample_firmware_with_vulns):
        """Test finding weak cryptography."""
        issues = analyzer.find_weak_crypto(sample_firmware_with_vulns)

        assert len(issues) > 0
        assert any(
            i.vulnerability_type == VulnerabilityType.WEAK_CRYPTO for i in issues
        )

    def test_find_hardcoded_credentials(self, analyzer, sample_firmware_with_vulns):
        """Test finding hardcoded credentials."""
        issues = analyzer.find_hardcoded_credentials(sample_firmware_with_vulns)

        assert len(issues) > 0
        assert issues[0].vulnerability_type == VulnerabilityType.HARDCODED_CREDENTIALS
        assert issues[0].severity == Severity.CRITICAL


class TestStringExtraction:
    """Tests for string extraction."""

    def test_extract_strings(self, analyzer, sample_elf_file):
        """Test extracting printable strings."""
        strings = analyzer.extract_strings(sample_elf_file)

        assert len(strings) > 0
        assert any("FreeRTOS" in s for s in strings)

    def test_extract_strings_min_length(self, analyzer, temp_dir):
        """Test string extraction respects min length."""
        fw_file = os.path.join(temp_dir, "strings.bin")
        # Use null bytes to separate strings so they're found individually
        with open(fw_file, "wb") as f:
            f.write(b"ab\x00longerstring\x00verylongstring")

        strings = analyzer.extract_strings(fw_file, min_length=8)

        assert "longerstring" in strings
        assert "verylongstring" in strings
        assert "ab" not in strings

    def test_extract_strings_max_count(self, analyzer, temp_dir):
        """Test string extraction respects max count."""
        fw_file = os.path.join(temp_dir, "many_strings.bin")
        # Use null bytes to separate strings so they're found individually
        with open(fw_file, "wb") as f:
            for i in range(100):
                f.write(f"string_{i:03d}\x00".encode())

        strings = analyzer.extract_strings(fw_file, max_strings=10)

        assert len(strings) == 10


class TestImageLoading:
    """Tests for firmware image loading."""

    def test_load_image(self, analyzer, sample_elf_file):
        """Test loading a firmware image."""
        image = analyzer.load_image(
            sample_elf_file,
            name="test_firmware",
            version="1.0.0",
        )

        assert image.name == "test_firmware"
        assert image.version == "1.0.0"
        assert image.format == FirmwareFormat.ELF
        assert image.hash != ""

    def test_load_image_detects_rtos(self, analyzer, sample_elf_file):
        """Test that image loading detects RTOS."""
        image = analyzer.load_image(sample_elf_file)
        assert image.rtos_type == RTOSType.FREERTOS

    def test_load_image_too_large(self, analyzer, test_config, temp_dir):
        """Test loading fails for oversized firmware."""
        test_config.firmware.max_file_size_mb = 0  # 0 MB limit

        analyzer = FirmwareAnalyzer(test_config)

        large_file = os.path.join(temp_dir, "large.bin")
        with open(large_file, "wb") as f:
            f.write(b"x" * 1024)

        with pytest.raises(FirmwareTooLargeError):
            analyzer.load_image(large_file)

    def test_get_image(self, analyzer, sample_elf_file):
        """Test getting image by ID."""
        image = analyzer.load_image(sample_elf_file)
        retrieved = analyzer.get_image(image.image_id)

        assert retrieved is not None
        assert retrieved.image_id == image.image_id


class TestFirmwareAnalysis:
    """Tests for full firmware analysis."""

    def test_analyze_firmware(self, analyzer, sample_elf_file):
        """Test full firmware analysis."""
        image = analyzer.load_image(sample_elf_file)
        result = analyzer.analyze(image)

        assert result.analysis_id is not None
        assert result.image.image_id == image.image_id
        assert result.completed_at is not None
        assert result.duration_seconds is not None

    def test_analyze_finds_issues(self, analyzer, sample_firmware_with_vulns):
        """Test analysis finds security issues."""
        image = analyzer.load_image(sample_firmware_with_vulns)
        result = analyzer.analyze(image)

        assert result.issue_count > 0
        assert not result.passed  # Should fail with vulnerabilities

    def test_analyze_calculates_score(self, analyzer, sample_firmware_with_vulns):
        """Test analysis calculates security score."""
        image = analyzer.load_image(sample_firmware_with_vulns)
        result = analyzer.analyze(image)

        assert result.score < 100.0  # Should have deductions

    def test_analyze_extracts_strings(self, analyzer, sample_elf_file):
        """Test analysis extracts strings."""
        image = analyzer.load_image(sample_elf_file)
        result = analyzer.analyze(image)

        assert len(result.strings) > 0

    def test_analyze_detects_rtos(self, analyzer, sample_elf_file):
        """Test analysis detects RTOS."""
        image = analyzer.load_image(sample_elf_file)
        result = analyzer.analyze(image)

        assert result.rtos_detected is True


class TestResultManagement:
    """Tests for analysis result management."""

    def test_get_analysis(self, analyzer, sample_elf_file):
        """Test getting analysis by ID."""
        image = analyzer.load_image(sample_elf_file)
        result = analyzer.analyze(image)

        retrieved = analyzer.get_analysis(result.analysis_id)
        assert retrieved is not None
        assert retrieved.analysis_id == result.analysis_id

    def test_get_nonexistent_analysis(self, analyzer):
        """Test getting non-existent analysis."""
        retrieved = analyzer.get_analysis("nonexistent")
        assert retrieved is None

    def test_list_analyses(self, analyzer, temp_dir):
        """Test listing analyses."""
        # Analyze multiple files
        for i in range(3):
            fw_file = os.path.join(temp_dir, f"fw_{i}.bin")
            with open(fw_file, "wb") as f:
                f.write(b"firmware content " + str(i).encode())

            image = analyzer.load_image(fw_file, version=f"1.{i}")
            analyzer.analyze(image)

        analyses = analyzer.list_analyses()
        assert len(analyses) == 3

    def test_list_analyses_by_result(
        self, analyzer, temp_dir, sample_firmware_with_vulns
    ):
        """Test listing analyses by pass/fail."""
        # Create passing firmware
        passing_file = os.path.join(temp_dir, "passing.bin")
        with open(passing_file, "w") as f:
            f.write("safe firmware content")
        image1 = analyzer.load_image(passing_file)
        analyzer.analyze(image1)

        # Analyze failing firmware
        image2 = analyzer.load_image(sample_firmware_with_vulns)
        analyzer.analyze(image2)

        passed = analyzer.list_analyses(passed=True)
        failed = analyzer.list_analyses(passed=False)

        # At least one should pass, at least one should fail
        assert len(passed) >= 1
        assert len(failed) >= 1

    def test_get_issues_by_severity(self, analyzer, sample_firmware_with_vulns):
        """Test getting issues filtered by severity."""
        image = analyzer.load_image(sample_firmware_with_vulns)
        result = analyzer.analyze(image)

        critical_issues = analyzer.get_issues_by_severity(
            result.analysis_id,
            Severity.CRITICAL,
        )

        # Should have critical issues (gets, hardcoded creds)
        assert len(critical_issues) > 0
        assert all(i.severity == Severity.CRITICAL for i in critical_issues)

    def test_get_issues_by_type(self, analyzer, sample_firmware_with_vulns):
        """Test getting issues filtered by type."""
        image = analyzer.load_image(sample_firmware_with_vulns)
        result = analyzer.analyze(image)

        overflow_issues = analyzer.get_issues_by_type(
            result.analysis_id,
            VulnerabilityType.BUFFER_OVERFLOW,
        )

        assert len(overflow_issues) > 0
        assert all(
            i.vulnerability_type == VulnerabilityType.BUFFER_OVERFLOW
            for i in overflow_issues
        )


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_json_report(self, analyzer, sample_elf_file):
        """Test generating JSON report."""
        image = analyzer.load_image(sample_elf_file)
        result = analyzer.analyze(image)

        report = analyzer.generate_report(result.analysis_id, format="json")

        assert report != ""
        import json

        data = json.loads(report)
        assert data["analysis_id"] == result.analysis_id

    def test_generate_text_report(self, analyzer, sample_elf_file):
        """Test generating text report."""
        image = analyzer.load_image(sample_elf_file)
        result = analyzer.analyze(image)

        report = analyzer.generate_report(result.analysis_id, format="text")

        assert "Firmware Security Analysis Report" in report
        assert result.analysis_id in report
        assert "Security Score" in report

    def test_generate_report_nonexistent(self, analyzer):
        """Test generating report for non-existent analysis."""
        report = analyzer.generate_report("nonexistent")
        assert report == ""
