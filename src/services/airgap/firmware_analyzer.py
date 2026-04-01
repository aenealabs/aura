"""
Project Aura - Firmware Security Analyzer

Service for analyzing embedded firmware images for security vulnerabilities,
RTOS detection, and memory safety issues.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

import hashlib
import os
import re
import struct
import uuid
from datetime import datetime, timezone
from typing import Optional

from .config import AirGapConfig, get_airgap_config
from .contracts import (
    AnalysisType,
    FirmwareAnalysisResult,
    FirmwareFormat,
    FirmwareImage,
    HashAlgorithm,
    MemorySafetyIssue,
    ProcessorArchitecture,
    RTOSTaskInfo,
    RTOSType,
    Severity,
    VulnerabilityType,
)
from .exceptions import (
    FirmwareAnalysisError,
    FirmwareParseError,
    FirmwareTooLargeError,
    UnsupportedFirmwareFormat,
)
from .metrics import get_airgap_metrics

# RTOS signature patterns for detection
RTOS_SIGNATURES = {
    RTOSType.FREERTOS: [
        b"FreeRTOS",
        b"xTaskCreate",
        b"vTaskDelay",
        b"xQueueCreate",
        b"xSemaphoreCreate",
        b"prvIdleTask",
        b"configTICK_RATE_HZ",
    ],
    RTOSType.ZEPHYR: [
        b"ZEPHYR",
        b"k_thread_create",
        b"k_sem_init",
        b"k_msgq_init",
        b"z_impl_",
        b"CONFIG_KERNEL",
    ],
    RTOSType.THREADX: [
        b"ThreadX",
        b"tx_thread_create",
        b"tx_semaphore_create",
        b"tx_queue_create",
        b"_tx_thread",
    ],
    RTOSType.VXWORKS: [
        b"VxWorks",
        b"taskSpawn",
        b"semCreate",
        b"msgQCreate",
        b"intConnect",
        b"WIND_TCB",
    ],
    RTOSType.RIOT: [
        b"RIOT",
        b"thread_create",
        b"mutex_lock",
        b"msg_send",
        b"THREAD_CREATE_STACKTEST",
    ],
    RTOSType.NUTTX: [
        b"NuttX",
        b"nxtask_create",
        b"nxsem_init",
        b"nxmq_open",
        b"CONFIG_ARCH",
    ],
    RTOSType.MBED: [
        b"mbed",
        b"rtos::Thread",
        b"Mutex::lock",
        b"EventQueue",
        b"MBED_CONF",
    ],
}

# Vulnerable function patterns
VULNERABLE_FUNCTIONS = {
    "strcpy": (VulnerabilityType.BUFFER_OVERFLOW, Severity.HIGH, "CWE-120"),
    "strcat": (VulnerabilityType.BUFFER_OVERFLOW, Severity.HIGH, "CWE-120"),
    "sprintf": (VulnerabilityType.BUFFER_OVERFLOW, Severity.HIGH, "CWE-120"),
    "vsprintf": (VulnerabilityType.BUFFER_OVERFLOW, Severity.HIGH, "CWE-120"),
    "gets": (VulnerabilityType.BUFFER_OVERFLOW, Severity.CRITICAL, "CWE-242"),
    "scanf": (VulnerabilityType.BUFFER_OVERFLOW, Severity.MEDIUM, "CWE-120"),
    "sscanf": (VulnerabilityType.BUFFER_OVERFLOW, Severity.MEDIUM, "CWE-120"),
    "printf": (VulnerabilityType.FORMAT_STRING, Severity.MEDIUM, "CWE-134"),
    "fprintf": (VulnerabilityType.FORMAT_STRING, Severity.MEDIUM, "CWE-134"),
    "syslog": (VulnerabilityType.FORMAT_STRING, Severity.MEDIUM, "CWE-134"),
    "system": (VulnerabilityType.COMMAND_INJECTION, Severity.CRITICAL, "CWE-78"),
    "popen": (VulnerabilityType.COMMAND_INJECTION, Severity.HIGH, "CWE-78"),
    "execl": (VulnerabilityType.COMMAND_INJECTION, Severity.HIGH, "CWE-78"),
    "execv": (VulnerabilityType.COMMAND_INJECTION, Severity.HIGH, "CWE-78"),
    "malloc": (VulnerabilityType.MEMORY_LEAK, Severity.LOW, "CWE-401"),
    "free": (VulnerabilityType.DOUBLE_FREE, Severity.HIGH, "CWE-415"),
    "rand": (VulnerabilityType.INSECURE_RANDOM, Severity.MEDIUM, "CWE-330"),
    "srand": (VulnerabilityType.INSECURE_RANDOM, Severity.LOW, "CWE-330"),
}

# Weak crypto patterns
WEAK_CRYPTO_PATTERNS = [
    (b"DES_", VulnerabilityType.WEAK_CRYPTO, Severity.HIGH, "CWE-327"),
    (b"MD5", VulnerabilityType.WEAK_CRYPTO, Severity.MEDIUM, "CWE-328"),
    (b"SHA1", VulnerabilityType.WEAK_CRYPTO, Severity.LOW, "CWE-328"),
    (b"RC4", VulnerabilityType.WEAK_CRYPTO, Severity.HIGH, "CWE-327"),
    (b"ECB", VulnerabilityType.WEAK_CRYPTO, Severity.MEDIUM, "CWE-327"),
]

# ELF magic numbers
ELF_MAGIC = b"\x7fELF"
PE_MAGIC = b"MZ"
IHEX_START = b":"
SREC_START = b"S"


class FirmwareAnalyzer:
    """Analyzer for embedded firmware security."""

    def __init__(self, config: Optional[AirGapConfig] = None):
        """Initialize the analyzer."""
        self._config = config or get_airgap_config()
        self._metrics = get_airgap_metrics()
        self._analyses: dict[str, FirmwareAnalysisResult] = {}
        self._images: dict[str, FirmwareImage] = {}

        # Initialize directories
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        dirs = [
            self._config.firmware.output_dir,
            self._config.firmware.temp_dir,
        ]
        for dir_path in dirs:
            if dir_path and not dir_path.startswith(":"):
                os.makedirs(dir_path, exist_ok=True)

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with prefix."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def _compute_hash(
        self,
        file_path: str,
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> str:
        """Compute hash of a file."""
        if algorithm == HashAlgorithm.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashAlgorithm.SHA384:
            hasher = hashlib.sha384()
        elif algorithm == HashAlgorithm.SHA512:
            hasher = hashlib.sha512()
        else:
            hasher = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    # =========================================================================
    # Format Detection
    # =========================================================================

    def detect_format(self, file_path: str) -> FirmwareFormat:
        """Detect firmware image format.

        Args:
            file_path: Path to firmware file

        Returns:
            Detected FirmwareFormat

        Raises:
            FirmwareParseError: If file cannot be read
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(64)

            if header.startswith(ELF_MAGIC):
                return FirmwareFormat.ELF
            elif header.startswith(PE_MAGIC):
                return FirmwareFormat.PE
            elif header.startswith(IHEX_START):
                return FirmwareFormat.IHEX
            elif header.startswith(SREC_START):
                return FirmwareFormat.SREC
            elif b"UF2\n" in header[:32]:
                return FirmwareFormat.UF2

            # Check for UEFI
            if b"EFI" in header or b"UEFI" in header:
                return FirmwareFormat.UEFI

            # Default to raw binary
            return FirmwareFormat.BIN

        except Exception as e:
            raise FirmwareParseError(f"Failed to detect format: {e}")

    def detect_architecture(self, file_path: str) -> ProcessorArchitecture:
        """Detect processor architecture from firmware.

        Args:
            file_path: Path to firmware file

        Returns:
            Detected ProcessorArchitecture
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(64)

            # ELF architecture detection
            if header.startswith(ELF_MAGIC):
                e_machine = struct.unpack("<H", header[18:20])[0]
                arch_map = {
                    0x03: ProcessorArchitecture.X86,
                    0x3E: ProcessorArchitecture.X86_64,
                    0x28: ProcessorArchitecture.ARM_CORTEX_M,
                    0xB7: ProcessorArchitecture.ARM64,
                    0xF3: ProcessorArchitecture.RISCV32,
                }
                return arch_map.get(e_machine, ProcessorArchitecture.UNKNOWN)

            # PE architecture detection
            if header.startswith(PE_MAGIC):
                # Find PE header offset
                pe_offset = struct.unpack("<I", header[60:64])[0]
                with open(file_path, "rb") as f:
                    f.seek(pe_offset + 4)
                    machine = struct.unpack("<H", f.read(2))[0]
                machine_map = {
                    0x014C: ProcessorArchitecture.X86,
                    0x8664: ProcessorArchitecture.X86_64,
                    0x01C0: ProcessorArchitecture.ARM_CORTEX_M,
                    0xAA64: ProcessorArchitecture.ARM64,
                }
                return machine_map.get(machine, ProcessorArchitecture.UNKNOWN)

            return ProcessorArchitecture.UNKNOWN

        except Exception:
            return ProcessorArchitecture.UNKNOWN

    # =========================================================================
    # RTOS Detection
    # =========================================================================

    def detect_rtos(
        self, file_path: str, firmware_data: Optional[bytes] = None
    ) -> tuple[RTOSType, Optional[str]]:
        """Detect RTOS type from firmware.

        Args:
            file_path: Path to firmware file
            firmware_data: Pre-read firmware bytes (optional, avoids re-reading)

        Returns:
            Tuple of (RTOSType, version string or None)
        """
        if not self._config.rtos.enabled:
            return RTOSType.UNKNOWN, None

        try:
            if firmware_data is not None:
                content = firmware_data
            else:
                with open(file_path, "rb") as f:
                    content = f.read()

            best_match = RTOSType.UNKNOWN
            best_score = 0
            version = None

            for rtos_type, signatures in RTOS_SIGNATURES.items():
                score = sum(1 for sig in signatures if sig in content)
                if score > best_score:
                    best_score = score
                    best_match = rtos_type

            # Try to extract version
            if best_match != RTOSType.UNKNOWN:
                version_patterns = {
                    RTOSType.FREERTOS: rb"FreeRTOS[/\s]V?(\d+\.\d+\.\d+)",
                    RTOSType.ZEPHYR: rb"Zephyr[/\s]v?(\d+\.\d+\.\d+)",
                    RTOSType.THREADX: rb"ThreadX[/\s]V?(\d+\.\d+)",
                    RTOSType.VXWORKS: rb"VxWorks[/\s](\d+\.\d+)",
                }
                pattern = version_patterns.get(best_match)
                if pattern:
                    match = re.search(pattern, content)
                    if match:
                        version = match.group(1).decode("utf-8", errors="ignore")

            return best_match, version

        except Exception:
            return RTOSType.UNKNOWN, None

    def analyze_rtos_tasks(
        self,
        file_path: str,
        rtos_type: RTOSType,
        firmware_data: Optional[bytes] = None,
    ) -> list[RTOSTaskInfo]:
        """Analyze RTOS tasks from firmware.

        Args:
            file_path: Path to firmware file
            rtos_type: Detected RTOS type
            firmware_data: Pre-read firmware bytes (optional, avoids re-reading)

        Returns:
            List of RTOSTaskInfo
        """
        if not self._config.rtos.analyze_tasks:
            return []

        tasks: list[RTOSTaskInfo] = []

        try:
            if firmware_data is not None:
                content = firmware_data
            else:
                with open(file_path, "rb") as f:
                    content = f.read()

            # Extract task names based on RTOS type
            task_patterns = {
                RTOSType.FREERTOS: rb'xTaskCreate\s*\([^,]+,\s*"([^"]+)"',
                RTOSType.ZEPHYR: rb"K_THREAD_DEFINE\s*\((\w+)",
                RTOSType.THREADX: rb'tx_thread_create\s*\([^,]+,\s*"([^"]+)"',
            }

            pattern = task_patterns.get(rtos_type)
            if pattern:
                for i, match in enumerate(re.finditer(pattern, content)):
                    task_name = match.group(1).decode("utf-8", errors="ignore")
                    tasks.append(
                        RTOSTaskInfo(
                            task_id=f"task-{i:03d}",
                            name=task_name,
                            priority=0,  # Would need deeper analysis
                            stack_size=0,
                            state="unknown",
                        )
                    )

        except Exception:
            pass

        return tasks

    # =========================================================================
    # Vulnerability Detection
    # =========================================================================

    def find_vulnerable_functions(
        self,
        file_path: str,
        firmware_data: Optional[bytes] = None,
    ) -> list[MemorySafetyIssue]:
        """Find calls to vulnerable functions.

        Args:
            file_path: Path to firmware file
            firmware_data: Pre-read firmware bytes (optional, avoids re-reading)

        Returns:
            List of MemorySafetyIssue
        """
        if not self._config.firmware.memory_safety_checks:
            return []

        issues: list[MemorySafetyIssue] = []

        try:
            if firmware_data is not None:
                content = firmware_data
            else:
                with open(file_path, "rb") as f:
                    content = f.read()

            for func_name, (
                vuln_type,
                severity,
                cwe_id,
            ) in VULNERABLE_FUNCTIONS.items():
                # Search for function name in binary
                pattern = func_name.encode()
                offset = 0
                while True:
                    pos = content.find(pattern, offset)
                    if pos == -1:
                        break

                    issues.append(
                        MemorySafetyIssue(
                            issue_id=self._generate_id("vuln"),
                            vulnerability_type=vuln_type,
                            severity=severity,
                            location=f"0x{pos:08x}",
                            description=f"Use of potentially unsafe function: {func_name}",
                            cwe_id=cwe_id,
                            remediation=f"Replace {func_name} with safer alternative",
                        )
                    )
                    offset = pos + 1

        except Exception:
            pass

        return issues

    def find_weak_crypto(
        self, file_path: str, firmware_data: Optional[bytes] = None
    ) -> list[MemorySafetyIssue]:
        """Find weak cryptographic implementations.

        Args:
            file_path: Path to firmware file
            firmware_data: Pre-read firmware bytes (optional, avoids re-reading)

        Returns:
            List of MemorySafetyIssue
        """
        if not self._config.firmware.detect_crypto:
            return []

        issues: list[MemorySafetyIssue] = []

        try:
            if firmware_data is not None:
                content = firmware_data
            else:
                with open(file_path, "rb") as f:
                    content = f.read()

            for pattern, vuln_type, severity, cwe_id in WEAK_CRYPTO_PATTERNS:
                if pattern in content:
                    issues.append(
                        MemorySafetyIssue(
                            issue_id=self._generate_id("crypto"),
                            vulnerability_type=vuln_type,
                            severity=severity,
                            location="binary",
                            description=f"Weak cryptographic implementation detected: {pattern.decode()}",
                            cwe_id=cwe_id,
                            remediation="Use modern, strong cryptographic algorithms",
                        )
                    )

        except Exception:
            pass

        return issues

    def find_hardcoded_credentials(
        self,
        file_path: str,
        firmware_data: Optional[bytes] = None,
    ) -> list[MemorySafetyIssue]:
        """Find hardcoded credentials in firmware.

        Args:
            file_path: Path to firmware file
            firmware_data: Pre-read firmware bytes (optional, avoids re-reading)

        Returns:
            List of MemorySafetyIssue
        """
        issues: list[MemorySafetyIssue] = []

        credential_patterns = [
            (rb"password\s*=\s*[\"']([^\"']+)[\"']", "password"),
            (rb"passwd\s*=\s*[\"']([^\"']+)[\"']", "password"),
            (rb"api[_-]?key\s*=\s*[\"']([^\"']+)[\"']", "API key"),
            (rb"secret\s*=\s*[\"']([^\"']+)[\"']", "secret"),
            (rb"token\s*=\s*[\"']([^\"']+)[\"']", "token"),
            (rb"private[_-]?key", "private key"),
        ]

        try:
            if firmware_data is not None:
                content = firmware_data
            else:
                with open(file_path, "rb") as f:
                    content = f.read()

            for pattern, cred_type in credential_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    issues.append(
                        MemorySafetyIssue(
                            issue_id=self._generate_id("cred"),
                            vulnerability_type=VulnerabilityType.HARDCODED_CREDENTIALS,
                            severity=Severity.CRITICAL,
                            location=f"offset 0x{match.start():08x}",
                            description=f"Hardcoded {cred_type} detected",
                            cwe_id="CWE-798",
                            remediation="Store credentials securely, not in firmware",
                        )
                    )

        except Exception:
            pass

        return issues

    # =========================================================================
    # String Extraction
    # =========================================================================

    def extract_strings(
        self,
        file_path: str,
        min_length: Optional[int] = None,
        max_strings: Optional[int] = None,
        firmware_data: Optional[bytes] = None,
    ) -> list[str]:
        """Extract printable strings from firmware.

        Args:
            file_path: Path to firmware file
            min_length: Minimum string length (default from config)
            max_strings: Maximum strings to return (default from config)
            firmware_data: Pre-read firmware bytes (optional, avoids re-reading)

        Returns:
            List of extracted strings
        """
        if not self._config.firmware.extract_strings:
            return []

        min_len = min_length or self._config.firmware.min_string_length
        max_count = max_strings or self._config.firmware.max_strings

        strings: list[str] = []

        try:
            if firmware_data is not None:
                content = firmware_data
            else:
                with open(file_path, "rb") as f:
                    content = f.read()

            # Extract ASCII strings
            pattern = rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}"
            for match in re.finditer(pattern, content):
                try:
                    s = match.group().decode("utf-8")
                    if len(strings) < max_count:
                        strings.append(s)
                    else:
                        break
                except UnicodeDecodeError:
                    continue

        except Exception:
            pass

        return strings

    # =========================================================================
    # Main Analysis
    # =========================================================================

    def load_image(
        self,
        file_path: str,
        name: Optional[str] = None,
        version: Optional[str] = None,
    ) -> FirmwareImage:
        """Load a firmware image for analysis.

        Args:
            file_path: Path to firmware file
            name: Optional name (defaults to filename)
            version: Optional version string

        Returns:
            FirmwareImage object

        Raises:
            FirmwareTooLargeError: If file exceeds size limit
            UnsupportedFirmwareFormat: If format not supported
        """
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = self._config.firmware.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise FirmwareTooLargeError(
                file_path,
                file_size,
                max_size,
            )

        # Detect format
        fw_format = self.detect_format(file_path)
        if fw_format.value not in self._config.firmware.allowed_formats:
            raise UnsupportedFirmwareFormat(
                fw_format.value,
                self._config.firmware.allowed_formats,
            )

        # Detect architecture
        architecture = self.detect_architecture(file_path)

        # Detect RTOS
        rtos_type, rtos_version = self.detect_rtos(file_path)

        # Compute hash
        file_hash = self._compute_hash(file_path)

        image = FirmwareImage(
            image_id=self._generate_id("fw"),
            name=name or os.path.basename(file_path),
            version=version or "unknown",
            format=fw_format,
            architecture=architecture,
            size_bytes=file_size,
            hash=file_hash,
            file_path=file_path,
            rtos_type=rtos_type,
            metadata={
                "rtos_version": rtos_version,
            },
        )

        self._images[image.image_id] = image
        return image

    def analyze(
        self,
        image: FirmwareImage,
        analysis_type: AnalysisType = AnalysisType.STATIC,
    ) -> FirmwareAnalysisResult:
        """Perform security analysis on firmware image.

        Args:
            image: FirmwareImage to analyze
            analysis_type: Type of analysis to perform

        Returns:
            FirmwareAnalysisResult with findings

        Raises:
            FirmwareAnalysisError: If analysis fails
        """
        analysis_id = self._generate_id("analysis")
        file_path = image.file_path

        if not file_path or not os.path.exists(file_path):
            raise FirmwareAnalysisError(
                "Firmware file not found",
                image.image_id,
                analysis_type.value,
            )

        self._metrics.record_firmware_analysis_started(
            analysis_id,
            image.format.value,
            image.architecture.value,
            image.size_bytes,
        )

        result = FirmwareAnalysisResult(
            analysis_id=analysis_id,
            image=image,
            analysis_type=analysis_type,
        )

        try:
            # Read firmware binary once and pass to all analysis methods
            with open(file_path, "rb") as f:
                firmware_data = f.read()

            # Extract strings
            result.strings = self.extract_strings(
                file_path, firmware_data=firmware_data
            )

            # Find vulnerabilities
            result.issues.extend(
                self.find_vulnerable_functions(file_path, firmware_data=firmware_data)
            )
            result.issues.extend(
                self.find_weak_crypto(file_path, firmware_data=firmware_data)
            )
            result.issues.extend(
                self.find_hardcoded_credentials(file_path, firmware_data=firmware_data)
            )

            # Analyze RTOS tasks
            if image.rtos_type != RTOSType.UNKNOWN:
                result.rtos_detected = True
                result.rtos_version = image.metadata.get("rtos_version")
                result.tasks = self.analyze_rtos_tasks(
                    file_path, image.rtos_type, firmware_data=firmware_data
                )

                self._metrics.record_rtos_detected(
                    analysis_id,
                    image.rtos_type.value,
                    len(result.tasks),
                )

            # Calculate score
            result.score = self._calculate_score(result.issues)
            result.passed = result.critical_count == 0 and result.high_count <= 3

            result.completed_at = datetime.now(timezone.utc)

            self._analyses[analysis_id] = result

            self._metrics.record_firmware_analysis_completed(
                analysis_id,
                result.duration_seconds or 0,
                result.issue_count,
                result.critical_count,
                result.high_count,
                result.passed,
            )

            # Record individual vulnerabilities
            for issue in result.issues:
                self._metrics.record_vulnerability_found(
                    analysis_id,
                    issue.vulnerability_type.value,
                    str(issue.severity),
                    issue.cwe_id,
                )

            return result

        except Exception as e:
            raise FirmwareAnalysisError(
                f"Analysis failed: {e}",
                image.image_id,
                analysis_type.value,
            )

    def _calculate_score(self, issues: list[MemorySafetyIssue]) -> float:
        """Calculate security score from issues.

        Args:
            issues: List of detected issues

        Returns:
            Security score (0-100)
        """
        if not issues:
            return 100.0

        # Deduct points based on severity
        deductions = {
            Severity.CRITICAL: 25,
            Severity.HIGH: 15,
            Severity.MEDIUM: 8,
            Severity.LOW: 3,
            Severity.INFO: 1,
        }

        total_deduction = sum(deductions.get(issue.severity, 0) for issue in issues)

        return max(0.0, 100.0 - total_deduction)

    # =========================================================================
    # Result Management
    # =========================================================================

    def get_analysis(self, analysis_id: str) -> Optional[FirmwareAnalysisResult]:
        """Get analysis result by ID."""
        return self._analyses.get(analysis_id)

    def get_image(self, image_id: str) -> Optional[FirmwareImage]:
        """Get firmware image by ID."""
        return self._images.get(image_id)

    def list_analyses(
        self,
        passed: Optional[bool] = None,
        rtos_type: Optional[RTOSType] = None,
    ) -> list[FirmwareAnalysisResult]:
        """List analysis results with optional filtering."""
        results = list(self._analyses.values())

        if passed is not None:
            results = [r for r in results if r.passed == passed]

        if rtos_type is not None:
            results = [r for r in results if r.image.rtos_type == rtos_type]

        return results

    def get_issues_by_severity(
        self,
        analysis_id: str,
        severity: Severity,
    ) -> list[MemorySafetyIssue]:
        """Get issues filtered by severity."""
        result = self._analyses.get(analysis_id)
        if not result:
            return []
        return [i for i in result.issues if i.severity == severity]

    def get_issues_by_type(
        self,
        analysis_id: str,
        vuln_type: VulnerabilityType,
    ) -> list[MemorySafetyIssue]:
        """Get issues filtered by vulnerability type."""
        result = self._analyses.get(analysis_id)
        if not result:
            return []
        return [i for i in result.issues if i.vulnerability_type == vuln_type]

    def generate_report(
        self,
        analysis_id: str,
        format: str = "json",
    ) -> str:
        """Generate analysis report.

        Args:
            analysis_id: Analysis ID
            format: Output format ("json" or "text")

        Returns:
            Report as string
        """
        result = self._analyses.get(analysis_id)
        if not result:
            return ""

        if format == "json":
            import json

            return json.dumps(result.to_dict(), indent=2)

        # Text format
        lines = [
            "Firmware Security Analysis Report",
            "=" * 40,
            f"Analysis ID: {result.analysis_id}",
            f"Image: {result.image.name} (v{result.image.version})",
            f"Format: {result.image.format.value}",
            f"Architecture: {result.image.architecture.value}",
            f"Size: {result.image.size_bytes:,} bytes",
            "",
            f"RTOS Detected: {result.rtos_detected}",
        ]

        if result.rtos_detected:
            lines.append(f"RTOS Type: {result.image.rtos_type.value}")
            if result.rtos_version:
                lines.append(f"RTOS Version: {result.rtos_version}")
            lines.append(f"Tasks Found: {len(result.tasks)}")

        lines.extend(
            [
                "",
                f"Security Score: {result.score:.1f}/100",
                f"Status: {'PASSED' if result.passed else 'FAILED'}",
                "",
                "Issues Summary:",
                f"  Critical: {result.critical_count}",
                f"  High: {result.high_count}",
                f"  Medium: {result.medium_count}",
                f"  Total: {result.issue_count}",
                "",
            ]
        )

        if result.issues:
            lines.append("Issues:")
            for issue in result.issues:
                lines.append(
                    f"  [{issue.severity}] {issue.vulnerability_type.value}: "
                    f"{issue.description} ({issue.cwe_id})"
                )

        return "\n".join(lines)


# Singleton instance
_analyzer_instance: Optional[FirmwareAnalyzer] = None


def get_firmware_analyzer() -> FirmwareAnalyzer:
    """Get singleton analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = FirmwareAnalyzer()
    return _analyzer_instance


def reset_firmware_analyzer() -> None:
    """Reset analyzer singleton (for testing)."""
    global _analyzer_instance
    _analyzer_instance = None
