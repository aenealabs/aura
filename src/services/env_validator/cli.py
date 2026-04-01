"""CLI for Environment Validator (ADR-062).

Usage:
    python -m src.services.env_validator.cli manifest.yaml --env qa --strict
    python -m src.services.env_validator.validate_manifest manifest.yaml --env qa
"""

import argparse
import json
import sys
from pathlib import Path

from src.services.env_validator.models import Severity, TriggerType, ValidationResult


# ANSI color codes for terminal output
class Colors:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def colorize(text: str, color: str) -> str:
    """Add ANSI color codes to text."""
    return f"{color}{text}{Colors.RESET}"


def print_violation(violation, show_fix: bool = True) -> None:
    """Print a single violation with formatting."""
    severity_colors = {
        Severity.CRITICAL: Colors.RED,
        Severity.WARNING: Colors.YELLOW,
        Severity.INFO: Colors.BLUE,
    }
    color = severity_colors.get(violation.severity, Colors.RESET)

    print(f"  {colorize(f'[{violation.rule_id}]', color)} {violation.message}")
    print(f"    Resource: {violation.resource_type}/{violation.resource_name}")
    print(f"    Field: {violation.field_path}")
    print(f"    Expected: {violation.expected_value}")
    print(f"    Actual: {violation.actual_value}")

    if show_fix and violation.suggested_fix:
        print(f"    Fix: {colorize(violation.suggested_fix, Colors.GREEN)}")

    print()


def print_summary(run) -> None:
    """Print validation summary."""
    result_colors = {
        ValidationResult.PASS: Colors.GREEN,
        ValidationResult.WARN: Colors.YELLOW,
        ValidationResult.FAIL: Colors.RED,
    }
    color = result_colors.get(run.result, Colors.RESET)

    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"Validation Result: {colorize(run.result.value.upper(), color)}")
    print(f"Environment: {run.environment}")
    print(f"Resources Scanned: {run.resources_scanned}")
    print(f"Duration: {run.duration_ms}ms")
    print(f"Run ID: {run.run_id}")
    print(f"{'='*60}\n")

    # Summary counts
    print(
        f"  Critical Violations: {colorize(str(len(run.violations)), Colors.RED if run.violations else Colors.GREEN)}"
    )
    print(
        f"  Warnings: {colorize(str(len(run.warnings)), Colors.YELLOW if run.warnings else Colors.GREEN)}"
    )
    print(f"  Info: {len(run.info)}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Kubernetes manifests for environment consistency (ADR-062)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a manifest for QA environment
  python -m src.services.env_validator.cli manifest.yaml --env qa

  # Strict mode: exit with error code on any critical violation
  python -m src.services.env_validator.cli manifest.yaml --env qa --strict

  # Output as JSON for CI/CD integration
  python -m src.services.env_validator.cli manifest.yaml --env qa --output-format json

  # Validate kustomize output
  kustomize build overlays/qa/ | python -m src.services.env_validator.cli - --env qa
        """,
    )

    parser.add_argument(
        "manifest",
        help="Path to manifest file (use '-' for stdin)",
    )
    parser.add_argument(
        "--env",
        "-e",
        required=True,
        choices=["dev", "qa", "staging", "prod"],
        help="Target environment to validate against",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code 1 if any critical violations found",
    )
    parser.add_argument(
        "--output-format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output errors and summary",
    )

    args = parser.parse_args()

    # Disable colors if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.RED = ""
        Colors.YELLOW = ""
        Colors.GREEN = ""
        Colors.BLUE = ""
        Colors.BOLD = ""
        Colors.RESET = ""

    # Read manifest content
    if args.manifest == "-":
        manifest_content = sys.stdin.read()
        manifest_path = None
    else:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(f"Error: File not found: {args.manifest}", file=sys.stderr)
            sys.exit(2)
        manifest_content = manifest_path.read_text()

    # Run validation
    from src.services.env_validator.engine import ValidationEngine

    engine = ValidationEngine(args.env)
    run = engine.validate_manifest(manifest_content, TriggerType.PRE_DEPLOY)

    # Output results
    if args.output_format == "json":
        print(json.dumps(run.to_dict(), indent=2))
    else:
        # Text output
        if not args.quiet:
            print(f"\n{Colors.BOLD}Environment Validator (ADR-062){Colors.RESET}")
            print(f"Validating: {args.manifest}")
            print(f"Target Environment: {args.env}\n")

        # Print violations by severity
        if run.violations:
            print(f"{Colors.BOLD}{Colors.RED}CRITICAL VIOLATIONS:{Colors.RESET}")
            for v in run.violations:
                print_violation(v)

        if run.warnings and not args.quiet:
            print(f"{Colors.BOLD}{Colors.YELLOW}WARNINGS:{Colors.RESET}")
            for v in run.warnings:
                print_violation(v)

        if run.info and not args.quiet:
            print(f"{Colors.BOLD}{Colors.BLUE}INFO:{Colors.RESET}")
            for v in run.info:
                print_violation(v, show_fix=False)

        print_summary(run)

    # Exit code
    if args.strict and run.has_critical:
        sys.exit(1)
    elif run.result == ValidationResult.FAIL:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
