#!/usr/bin/env python3
"""
Project Aura - Configuration Validation Pre-commit Hook

Validates configuration files for security issues:
- Hardcoded secrets in config
- Insecure settings
- Exposed credentials

Usage:
    python -m scripts.security_hooks.config_hook [files...]

Exit codes:
    0 - No issues found
    1 - Security issues found

Author: Project Aura Team
Created: 2025-12-12
"""

import json
import re
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.services.secrets_detection_service import (
    SecretsDetectionService,
    SecretSeverity,
)


# ANSI color codes
class Colors:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


# Insecure configuration patterns
INSECURE_PATTERNS = [
    # Debug mode enabled
    {
        "pattern": r"(?i)(debug|DEBUG)\s*[:=]\s*(true|1|yes|on)",
        "message": "Debug mode enabled - should be disabled in production",
        "severity": "medium",
    },
    # Insecure SSL settings
    {
        "pattern": r"(?i)(ssl_?verify|verify_?ssl)\s*[:=]\s*(false|0|no|off)",
        "message": "SSL verification disabled - vulnerable to MITM attacks",
        "severity": "high",
    },
    # Wildcard CORS
    {
        "pattern": r"(?i)(cors|allowed_?origins?)\s*[:=]\s*['\"]?\*['\"]?",
        "message": "Wildcard CORS origin - allows any domain",
        "severity": "medium",
    },
    # Localhost/0.0.0.0 bindings
    {
        "pattern": r"(?i)(host|bind)\s*[:=]\s*['\"]?0\.0\.0\.0['\"]?",
        "message": "Binding to all interfaces - consider restricting",
        "severity": "low",
    },
    # Exposed admin paths
    {
        "pattern": r"(?i)(admin|management)\s*[:=]\s*['\"]?true",
        "message": "Admin/management endpoints enabled",
        "severity": "low",
    },
    # Weak password requirements
    {
        "pattern": r"(?i)(min_?password_?length|password_?min)\s*[:=]\s*[1-7]\b",
        "message": "Weak password minimum length (should be 8+)",
        "severity": "medium",
    },
    # Insecure cookie settings
    {
        "pattern": r"(?i)(secure_?cookie|cookie_?secure)\s*[:=]\s*(false|0|no)",
        "message": "Secure cookie flag disabled",
        "severity": "high",
    },
    # HTTP instead of HTTPS
    {
        "pattern": r"(?i)(url|endpoint|host)\s*[:=]\s*['\"]?http://(?!localhost|127\.0\.0\.1)",
        "message": "HTTP URL detected - consider using HTTPS",
        "severity": "medium",
    },
]


def print_banner():
    """Print hook banner."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}=== Aura Config Validator ==={Colors.RESET}\n")


def check_insecure_patterns(content: str, file_path: str) -> list:
    """Check for insecure configuration patterns."""
    issues = []

    for pattern_def in INSECURE_PATTERNS:
        matches = re.finditer(pattern_def["pattern"], content)
        for match in matches:
            # Find line number
            line_num = content[: match.start()].count("\n") + 1

            issues.append(
                {
                    "file": file_path,
                    "line": line_num,
                    "message": pattern_def["message"],
                    "severity": pattern_def["severity"],
                    "match": match.group(0)[:50],  # Truncate match
                }
            )

    return issues


def check_env_file(file_path: str) -> list:
    """Check .env files for exposed secrets."""
    issues = []

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Use secrets scanner
        scanner = SecretsDetectionService(log_findings=False)
        result = scanner.scan_text(content, file_path)

        for finding in result.findings:
            issues.append(
                {
                    "file": file_path,
                    "line": finding.line_number,
                    "message": f"Secret detected: {finding.secret_type.value}",
                    "severity": finding.severity.value,
                    "match": finding.redacted_value,
                }
            )

    except Exception as e:
        print(
            f"  {Colors.YELLOW}Warning: Could not scan {file_path}: {e}{Colors.RESET}"
        )

    return issues


def validate_json_config(file_path: str) -> list:
    """Validate JSON configuration file."""
    issues = []

    try:
        with open(file_path, "r") as f:
            content = f.read()
            data = json.loads(content)

        # Check for secrets in JSON
        scanner = SecretsDetectionService(log_findings=False)
        result = scanner.scan_text(content, file_path)

        for finding in result.findings:
            issues.append(
                {
                    "file": file_path,
                    "line": finding.line_number,
                    "message": f"Secret in JSON: {finding.secret_type.value}",
                    "severity": finding.severity.value,
                    "match": finding.redacted_value,
                }
            )

        # Check for insecure patterns
        issues.extend(check_insecure_patterns(content, file_path))

    except json.JSONDecodeError as e:
        issues.append(
            {
                "file": file_path,
                "line": e.lineno,
                "message": f"Invalid JSON syntax: {e.msg}",
                "severity": "high",
                "match": "",
            }
        )
    except Exception as e:
        print(
            f"  {Colors.YELLOW}Warning: Could not validate {file_path}: {e}{Colors.RESET}"
        )

    return issues


def validate_yaml_config(file_path: str) -> list:
    """Validate YAML configuration file."""
    issues = []

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Check for secrets
        scanner = SecretsDetectionService(log_findings=False)
        result = scanner.scan_text(content, file_path)

        for finding in result.findings:
            issues.append(
                {
                    "file": file_path,
                    "line": finding.line_number,
                    "message": f"Secret in YAML: {finding.secret_type.value}",
                    "severity": finding.severity.value,
                    "match": finding.redacted_value,
                }
            )

        # Check for insecure patterns
        issues.extend(check_insecure_patterns(content, file_path))

    except Exception as e:
        print(
            f"  {Colors.YELLOW}Warning: Could not validate {file_path}: {e}{Colors.RESET}"
        )

    return issues


def print_issue(issue: dict):
    """Print a single issue with formatting."""
    severity_colors = {
        "critical": Colors.RED,
        "high": Colors.RED,
        "medium": Colors.YELLOW,
        "low": Colors.BLUE,
    }

    color = severity_colors.get(issue["severity"], Colors.RESET)

    print(
        f"  {color}{Colors.BOLD}[{issue['severity'].upper()}]{Colors.RESET} "
        f"{issue['message']}"
    )
    print(f"    File: {issue['file']}")
    if issue["line"]:
        print(f"    Line: {issue['line']}")
    if issue["match"]:
        print(f"    Found: {issue['match']}")
    print()


def main():
    """Main hook entry point."""
    print_banner()

    # Get files from command line arguments
    files = sys.argv[1:]

    if not files:
        print(f"  {Colors.GREEN}No config files to validate.{Colors.RESET}")
        return 0

    all_issues = []
    files_checked = 0

    for file_path in files:
        path = Path(file_path)

        if not path.exists():
            continue

        files_checked += 1
        file_lower = file_path.lower()

        # Route to appropriate validator
        if file_lower.endswith(".env") or ".env." in file_lower:
            issues = check_env_file(file_path)
        elif file_lower.endswith(".json"):
            issues = validate_json_config(file_path)
        elif file_lower.endswith((".yaml", ".yml")):
            issues = validate_yaml_config(file_path)
        else:
            # Generic secrets scan
            scanner = SecretsDetectionService(log_findings=False)
            result = scanner.scan_file(file_path)
            issues = []
            for finding in result.findings:
                issues.append(
                    {
                        "file": file_path,
                        "line": finding.line_number,
                        "message": f"Secret detected: {finding.secret_type.value}",
                        "severity": finding.severity.value,
                        "match": finding.redacted_value,
                    }
                )

        all_issues.extend(issues)

    # Print results
    print(f"  Checked {files_checked} config file(s)")
    print()

    if not all_issues:
        print(f"  {Colors.GREEN}{Colors.BOLD}No security issues found.{Colors.RESET}")
        print()
        return 0

    # Print issues
    print(f"  {Colors.RED}{Colors.BOLD}Found {len(all_issues)} issue(s):{Colors.RESET}")
    print()

    for issue in all_issues:
        print_issue(issue)

    # Count by severity
    critical = sum(1 for i in all_issues if i["severity"] == "critical")
    high = sum(1 for i in all_issues if i["severity"] == "high")

    # Summary
    print(f"{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Critical: {critical}")
    print(f"  High: {high}")
    print(f"  Total: {len(all_issues)}")
    print()

    # Block on critical/high
    if critical > 0 or high > 0:
        print(
            f"{Colors.RED}{Colors.BOLD}COMMIT BLOCKED:{Colors.RESET} "
            f"Critical or high-severity config issues detected."
        )
        print()
        return 1

    print(
        f"{Colors.YELLOW}Warning:{Colors.RESET} "
        f"Config issues detected. Please review."
    )
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
