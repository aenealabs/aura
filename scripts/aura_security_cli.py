#!/usr/bin/env python3
"""
Project Aura - Security Scanning CLI

A comprehensive security scanning tool for developers:
- Scan files and directories for secrets
- Validate inputs for injection attacks
- Generate security audit reports

Usage:
    python scripts/aura_security_cli.py scan [paths...]
    python scripts/aura_security_cli.py validate "input text"
    python scripts/aura_security_cli.py report [--output file.json]
    python scripts/aura_security_cli.py stats

Author: Project Aura Team
Created: 2025-12-12
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.input_validation_service import (
    InputValidator,
    ThreatType,
    ValidationResult,
)
from src.services.secrets_detection_service import (
    ScanResult,
    SecretsDetectionService,
    SecretSeverity,
)
from src.services.security_audit_service import (
    SecurityAuditService,
    SecurityEventSeverity,
    SecurityEventType,
)


# ANSI color codes
class Colors:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    """Print CLI banner."""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
    _                       ____                       _ _
   / \\  _   _ _ __ __ _    / ___|  ___  ___ _   _ _ __(_) |_ _   _
  / _ \\| | | | '__/ _` |   \\___ \\ / _ \\/ __| | | | '__| | __| | | |
 / ___ \\ |_| | | | (_| |    ___) |  __/ (__| |_| | |  | | |_| |_| |
/_/   \\_\\__,_|_|  \\__,_|   |____/ \\___|\\___|\\__,_|_|  |_|\\__|\\__, |
                                                             |___/
{Colors.RESET}
{Colors.DIM}Project Aura Security Scanner v1.0.0{Colors.RESET}
"""
    print(banner)


def get_severity_color(severity: str) -> str:
    """Get color for severity level."""
    colors = {
        "critical": Colors.RED,
        "high": Colors.RED,
        "medium": Colors.YELLOW,
        "low": Colors.BLUE,
        "info": Colors.CYAN,
    }
    return colors.get(severity.lower(), Colors.RESET)


# =============================================================================
# Scan Command
# =============================================================================


def cmd_scan(args):
    """Scan files/directories for secrets."""
    paths = args.paths or ["."]
    recursive = args.recursive
    output_format = args.format
    output_file = args.output

    scanner = SecretsDetectionService(
        enable_entropy_detection=not args.no_entropy,
        log_findings=False,
    )

    # Collect files to scan
    files_to_scan = []
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            files_to_scan.append(path)
        elif path.is_dir():
            if recursive:
                files_to_scan.extend(path.rglob("*"))
            else:
                files_to_scan.extend(path.glob("*"))

    # Filter to only files
    files_to_scan = [f for f in files_to_scan if f.is_file()]

    # Exclude patterns
    exclude_patterns = [
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".pytest_cache",
        "htmlcov",
        ".coverage",
        "*.pyc",
        "*.pyo",
    ]

    def should_exclude(file_path: Path) -> bool:
        path_str = str(file_path)
        for pattern in exclude_patterns:
            if pattern in path_str:
                return True
        return False

    files_to_scan = [f for f in files_to_scan if not should_exclude(f)]

    # Scan files
    all_findings = []
    total_files = 0
    total_lines = 0

    if not args.quiet:
        print(f"\n{Colors.BOLD}Scanning {len(files_to_scan)} files...{Colors.RESET}\n")

    for file_path in files_to_scan:
        try:
            # Skip binary files
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    continue

            result = scanner.scan_file(str(file_path))
            total_files += 1
            total_lines += result.scanned_lines

            if result.has_secrets:
                for finding in result.findings:
                    all_findings.append(
                        {
                            "file": str(file_path),
                            "line": finding.line_number,
                            "column": finding.column,
                            "type": finding.secret_type.value,
                            "severity": finding.severity.value,
                            "match": finding.redacted_value,
                            "recommendation": finding.recommendation,
                        }
                    )

        except Exception:
            continue

    # Output results
    if output_format == "json":
        output = {
            "scan_time": datetime.utcnow().isoformat(),
            "files_scanned": total_files,
            "lines_scanned": total_lines,
            "secrets_found": len(all_findings),
            "findings": all_findings,
        }
        json_output = json.dumps(output, indent=2)

        if output_file:
            with open(output_file, "w") as f:
                f.write(json_output)
            print(f"Results written to {output_file}")
        else:
            print(json_output)
    else:
        # Human-readable format
        print(f"{Colors.BOLD}Scan Complete{Colors.RESET}")
        print(f"  Files scanned: {total_files}")
        print(f"  Lines scanned: {total_lines:,}")
        print()

        if not all_findings:
            print(f"  {Colors.GREEN}{Colors.BOLD}No secrets detected!{Colors.RESET}")
            return 0

        print(
            f"  {Colors.RED}{Colors.BOLD}Found {len(all_findings)} secret(s):{Colors.RESET}"
        )
        print()

        # Group by file
        by_file = {}
        for finding in all_findings:
            file_path = finding["file"]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(finding)

        for file_path, findings in by_file.items():
            print(f"  {Colors.BOLD}{file_path}{Colors.RESET}")
            for f in findings:
                color = get_severity_color(f["severity"])
                print(
                    f"    {color}[{f['severity'].upper()}]{Colors.RESET} "
                    f"Line {f['line']}: {f['type']}"
                )
                print(f"      Match: {f['match']}")
            print()

        # Summary
        critical = sum(1 for f in all_findings if f["severity"] == "critical")
        high = sum(1 for f in all_findings if f["severity"] == "high")

        print(f"{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  {Colors.RED}Critical: {critical}{Colors.RESET}")
        print(f"  {Colors.RED}High: {high}{Colors.RESET}")
        print(f"  Total: {len(all_findings)}")

        if critical > 0 or high > 0:
            return 1

    return 0


# =============================================================================
# Validate Command
# =============================================================================


def cmd_validate(args):
    """Validate input for security threats."""
    text = args.text
    check_all = args.all

    validator = InputValidator(strict_mode=False, log_threats=False)

    print(f"\n{Colors.BOLD}Validating input...{Colors.RESET}\n")
    print(f"  Input: {text[:100]}{'...' if len(text) > 100 else ''}")
    print()

    result = validator.validate_string(
        text,
        check_sql_injection=True,
        check_xss=True,
        check_command_injection=check_all,
    )

    if not result.threats_detected:
        print(f"  {Colors.GREEN}{Colors.BOLD}No threats detected!{Colors.RESET}")
        return 0

    print(f"  {Colors.RED}{Colors.BOLD}Threats detected:{Colors.RESET}")
    for threat in result.threats_detected:
        print(f"    - {Colors.RED}{threat.value}{Colors.RESET}")

    if result.warnings:
        print()
        print(f"  {Colors.YELLOW}Warnings:{Colors.RESET}")
        for warning in result.warnings:
            print(f"    - {warning}")

    print()
    print(f"  {Colors.BOLD}Sanitized output:{Colors.RESET}")
    print(f"    {result.sanitized_value[:200]}")

    return 1


# =============================================================================
# Report Command
# =============================================================================


def cmd_report(args):
    """Generate security audit report."""
    output_file = args.output or "security_report.json"

    # Get statistics from all services
    secrets_service = SecretsDetectionService(log_findings=False)
    validator = InputValidator(log_threats=False)
    audit_service = SecurityAuditService(enable_console=False, enable_file=False)

    report = {
        "report_generated": datetime.utcnow().isoformat(),
        "project": "Project Aura",
        "security_services": {
            "secrets_detection": {
                "status": "active",
                "patterns": len(secrets_service._patterns),
                "entropy_detection": secrets_service.enable_entropy_detection,
            },
            "input_validation": {
                "status": "active",
                "threat_types": [t.value for t in ThreatType],
            },
            "audit_logging": {
                "status": "active",
                "event_types": len(SecurityEventType),
                "severity_levels": [s.value for s in SecurityEventSeverity],
            },
        },
        "recommendations": [
            "Run secrets scan before every commit",
            "Enable pre-commit hooks for automatic scanning",
            "Review all HIGH and CRITICAL findings immediately",
            "Use environment variables for secrets",
            "Implement AWS Secrets Manager for production",
        ],
    }

    json_output = json.dumps(report, indent=2)

    with open(output_file, "w") as f:
        f.write(json_output)

    print(f"\n{Colors.BOLD}Security Report Generated{Colors.RESET}")
    print(f"  Output: {output_file}")
    print()
    print(json_output)

    return 0


# =============================================================================
# Stats Command
# =============================================================================


def cmd_stats(args):
    """Show security scanning statistics."""
    from src.api.security_integration import get_security_stats

    stats = get_security_stats()

    print(f"\n{Colors.BOLD}Security Service Statistics{Colors.RESET}\n")

    print(f"  {Colors.CYAN}Input Validation:{Colors.RESET}")
    for key, value in stats["input_validation"].items():
        print(f"    {key}: {value}")

    print()
    print(f"  {Colors.CYAN}Audit Logging:{Colors.RESET}")
    for key, value in stats["audit_logging"].items():
        if isinstance(value, dict):
            print(f"    {key}:")
            for k, v in value.items():
                print(f"      {k}: {v}")
        else:
            print(f"    {key}: {value}")

    print()
    print(f"  {Colors.CYAN}Secrets Detection:{Colors.RESET}")
    for key, value in stats["secrets_detection"].items():
        print(f"    {key}: {value}")

    return 0


# =============================================================================
# Quick Scan Command
# =============================================================================


def cmd_quick(args):
    """Quick scan of common sensitive files."""
    sensitive_patterns = [
        ".env",
        ".env.*",
        "*.pem",
        "*.key",
        "*credentials*",
        "*secret*",
        "config.json",
        "settings.json",
        "docker-compose*.yml",
    ]

    print(f"\n{Colors.BOLD}Quick Security Scan{Colors.RESET}\n")
    print("  Scanning for common sensitive files...")

    found_files = []
    for pattern in sensitive_patterns:
        found_files.extend(Path(".").rglob(pattern))

    # Filter out excluded directories
    exclude = [".git", "node_modules", "__pycache__", ".venv", "venv"]
    found_files = [
        f
        for f in found_files
        if all(ex not in str(f) for ex in exclude) and f.is_file()
    ]

    if not found_files:
        print(f"  {Colors.GREEN}No sensitive files found.{Colors.RESET}")
        return 0

    print(f"  Found {len(found_files)} potentially sensitive files:")
    print()

    scanner = SecretsDetectionService(log_findings=False)
    issues_found = 0

    for file_path in found_files:
        try:
            result = scanner.scan_file(str(file_path))
            status_icon = f"{Colors.RED}!" if result.has_secrets else f"{Colors.GREEN}✓"
            print(f"    {status_icon}{Colors.RESET} {file_path}")
            if result.has_secrets:
                issues_found += result.findings.__len__()
                for finding in result.findings[:3]:  # Limit to 3 per file
                    print(
                        f"      - {finding.secret_type.value} (line {finding.line_number})"
                    )
        except Exception:
            print(f"    {Colors.YELLOW}?{Colors.RESET} {file_path} (could not scan)")

    print()
    if issues_found > 0:
        print(
            f"  {Colors.RED}{Colors.BOLD}Found {issues_found} issue(s)!{Colors.RESET}"
        )
        return 1
    else:
        print(
            f"  {Colors.GREEN}{Colors.BOLD}No secrets detected in sensitive files.{Colors.RESET}"
        )
        return 0


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Project Aura Security Scanner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan .                     # Scan current directory
  %(prog)s scan src/ tests/ -r        # Scan directories recursively
  %(prog)s scan -f json -o report.json  # Output JSON report
  %(prog)s validate "user input"      # Validate input text
  %(prog)s quick                      # Quick scan for sensitive files
  %(prog)s stats                      # Show scanning statistics
  %(prog)s report                     # Generate security report
""",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output except errors",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan files for secrets")
    scan_parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan",
    )
    scan_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Scan directories recursively",
    )
    scan_parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    scan_parser.add_argument(
        "-o",
        "--output",
        help="Output file for results",
    )
    scan_parser.add_argument(
        "--no-entropy",
        action="store_true",
        help="Disable entropy-based detection",
    )
    scan_parser.set_defaults(func=cmd_scan)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate input text")
    validate_parser.add_argument(
        "text",
        help="Text to validate",
    )
    validate_parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Check all threat types",
    )
    validate_parser.set_defaults(func=cmd_validate)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate security report")
    report_parser.add_argument(
        "-o",
        "--output",
        default="security_report.json",
        help="Output file for report",
    )
    report_parser.set_defaults(func=cmd_report)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show security statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # Quick command
    quick_parser = subparsers.add_parser("quick", help="Quick scan for sensitive files")
    quick_parser.set_defaults(func=cmd_quick)

    args = parser.parse_args()

    if not args.quiet:
        print_banner()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
