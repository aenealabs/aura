#!/usr/bin/env python3
"""
Project Aura - Secrets Detection Pre-commit Hook

Scans staged files for secrets, API keys, and credentials.
Blocks commits containing critical secrets.

Usage:
    python -m scripts.security_hooks.secrets_hook [files...]

Exit codes:
    0 - No secrets found
    1 - Secrets found (commit blocked)

Author: Project Aura Team
Created: 2025-12-12
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.services.secrets_detection_service import (
    SecretsDetectionService,
    SecretSeverity,
)


# ANSI color codes for terminal output
class Colors:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_banner():
    """Print hook banner."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}=== Aura Secrets Scanner ==={Colors.RESET}\n")


def print_finding(finding, file_path: str):
    """Print a single finding with formatting."""
    severity_colors = {
        SecretSeverity.CRITICAL: Colors.RED,
        SecretSeverity.HIGH: Colors.RED,
        SecretSeverity.MEDIUM: Colors.YELLOW,
        SecretSeverity.LOW: Colors.BLUE,
    }

    color = severity_colors.get(finding.severity, Colors.RESET)

    print(
        f"  {color}{Colors.BOLD}[{finding.severity.value.upper()}]{Colors.RESET} "
        f"{finding.secret_type.value}"
    )
    print(f"    File: {file_path}")
    print(f"    Line: {finding.line_number}")
    print(f"    Match: {finding.redacted_value}")
    if finding.recommendation:
        print(f"    Fix: {finding.recommendation}")
    print()


def scan_file(scanner: SecretsDetectionService, file_path: str) -> list:
    """Scan a single file for secrets."""
    try:
        result = scanner.scan_file(file_path)
        return result.findings
    except Exception as e:
        print(
            f"  {Colors.YELLOW}Warning: Could not scan {file_path}: {e}{Colors.RESET}"
        )
        return []


def main():
    """Main hook entry point."""
    print_banner()

    # Get files from command line arguments
    files = sys.argv[1:]

    if not files:
        print(f"  {Colors.GREEN}No files to scan.{Colors.RESET}")
        return 0

    # Initialize scanner
    scanner = SecretsDetectionService(
        enable_entropy_detection=True,
        log_findings=False,
    )

    # Track findings
    all_findings = []
    critical_count = 0
    high_count = 0
    files_scanned = 0

    # Scan each file
    for file_path in files:
        # Skip non-existent files (may have been deleted)
        if not Path(file_path).exists():
            continue

        # Skip binary files
        try:
            with open(file_path, "rb") as f:
                # Check first 8KB for binary content
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    continue
        except Exception:
            continue

        files_scanned += 1
        findings = scan_file(scanner, file_path)

        if findings:
            all_findings.extend([(f, file_path) for f in findings])

            for finding in findings:
                if finding.severity == SecretSeverity.CRITICAL:
                    critical_count += 1
                elif finding.severity == SecretSeverity.HIGH:
                    high_count += 1

    # Print results
    print(f"  Scanned {files_scanned} file(s)")
    print()

    if not all_findings:
        print(f"  {Colors.GREEN}{Colors.BOLD}No secrets detected.{Colors.RESET}")
        print()
        return 0

    # Print all findings
    print(
        f"  {Colors.RED}{Colors.BOLD}Found {len(all_findings)} potential secret(s):{Colors.RESET}"
    )
    print()

    for finding, file_path in all_findings:
        print_finding(finding, file_path)

    # Summary
    print(f"{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Critical: {critical_count}")
    print(f"  High: {high_count}")
    print(f"  Total: {len(all_findings)}")
    print()

    # Block commit if critical or high severity secrets found
    if critical_count > 0 or high_count > 0:
        print(
            f"{Colors.RED}{Colors.BOLD}COMMIT BLOCKED:{Colors.RESET} "
            f"Critical or high-severity secrets detected."
        )
        print()
        print("To fix:")
        print("  1. Remove the secrets from the affected files")
        print("  2. Use environment variables or AWS Secrets Manager")
        print("  3. Add secrets to .gitignore if they're in config files")
        print()
        print(f"To bypass (NOT RECOMMENDED): git commit --no-verify")
        print()
        return 1

    # Warn but allow for lower severity
    print(
        f"{Colors.YELLOW}Warning:{Colors.RESET} "
        f"Potential secrets detected. Please review before pushing."
    )
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
