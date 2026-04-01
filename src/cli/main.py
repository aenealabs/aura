"""
Aura CLI - Command Line Interface for Project Aura.

Usage:
    aura --version
    aura status [--json]
    aura config init [--interactive]
    aura config show
    aura config set <key> <value>
    aura license status
    aura license activate <license-key>
    aura license request
    aura deploy status
    aura deploy upgrade
    aura health [--verbose]
    aura logs [--service <name>] [--tail <lines>]
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Version info
__version__ = "1.0.0"
__build__ = os.getenv("AURA_BUILD_NUMBER", "dev")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("aura")


class OutputFormat(Enum):
    """Output format options."""

    TEXT = "text"
    JSON = "json"
    YAML = "yaml"


@dataclass
class CLIConfig:
    """CLI configuration."""

    api_url: str = "http://localhost:8080"
    config_dir: str = "~/.aura"
    log_level: str = "INFO"
    output_format: str = "text"
    color_enabled: bool = True


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    @classmethod
    def disable(cls) -> None:
        """Disable all colors."""
        cls.RESET = ""
        cls.BOLD = ""
        cls.DIM = ""
        cls.RED = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.MAGENTA = ""
        cls.CYAN = ""
        cls.WHITE = ""


# Professional ASCII banner
BANNER = r"""
{cyan}╭──────────────────────────────────────────────────────────────╮
│                                                              │
│  {blue}█████╗ {cyan}█{blue}█╗   ██╗{cyan}█{blue}█████╗ {cyan}█{blue}█╗ {cyan}█{blue}█╗{cyan}█{blue}██████╗  █████╗ {cyan}         │
│  {blue}██╔══██╗{cyan}█{blue}█║   ██║{cyan}█{blue}█╔══██╗{cyan}█{blue}█║ {cyan}█{blue}█║{cyan}█{blue}█╔══██╗██╔══██╗{cyan}         │
│  {blue}███████║{cyan}█{blue}█║   ██║{cyan}█{blue}█████╔╝{cyan}█{blue}█████║{cyan}█{blue}█████╔╝███████║{cyan}         │
│  {blue}██╔══██║{cyan}█{blue}█║   ██║{cyan}█{blue}█╔══██╗{cyan}█{blue}█╔══██║{cyan}█{blue}█╔══██║██╔══██║{cyan}         │
│  {blue}██║  ██║{cyan}╚{blue}██████╔╝{cyan}█{blue}█║  ██║{cyan}█{blue}█║  {cyan}█{blue}█║{cyan}█{blue}█║  ██║██║  ██║{cyan}         │
│  {blue}╚═╝  ╚═╝ {cyan}╚{blue}═════╝ {cyan}╚{blue}═╝  ╚═╝{cyan}╚{blue}═╝  {cyan}╚{blue}═╝{cyan}╚{blue}═╝  ╚═╝╚═╝  ╚═╝{cyan}         │
│                                                              │
│  {white}{bold}Autonomous Code Intelligence Platform{reset}{cyan}                      │
│  {dim}Aenea Labs • https://aenealabs.com{reset}{cyan}                          │
│                                                              │
╰──────────────────────────────────────────────────────────────╯{reset}
"""

BANNER_SIMPLE = r"""
{cyan}┌──────────────────────────────────────────────────────────────┐
│                                                              │
│     {blue}█████╗ ██╗   ██╗██████╗  █████╗{cyan}                          │
│    {blue}██╔══██╗██║   ██║██╔══██╗██╔══██╗{cyan}                         │
│    {blue}███████║██║   ██║██████╔╝███████║{cyan}                         │
│    {blue}██╔══██║██║   ██║██╔══██║██╔══██║{cyan}                         │
│    {blue}██║  ██║╚██████╔╝██║  ██║██║  ██║{cyan}                         │
│    {blue}╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{cyan}                         │
│                                                              │
│     {white}{bold}Autonomous Code Intelligence Platform{reset}{cyan}                   │
│     {dim}Aenea Labs{reset}{cyan}                                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘{reset}
"""


def get_banner() -> str:
    """Get formatted banner with colors."""
    return BANNER_SIMPLE.format(
        cyan=Colors.CYAN,
        blue=Colors.BLUE,
        white=Colors.WHITE,
        bold=Colors.BOLD,
        dim=Colors.DIM,
        reset=Colors.RESET,
    )


def colorize(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{Colors.RESET}"


def print_success(message: str) -> None:
    """Print success message."""
    print(colorize(f"✓ {message}", Colors.GREEN))


def print_error(message: str) -> None:
    """Print error message."""
    print(colorize(f"✗ {message}", Colors.RED), file=sys.stderr)


def print_warning(message: str) -> None:
    """Print warning message."""
    print(colorize(f"⚠ {message}", Colors.YELLOW))


def print_info(message: str) -> None:
    """Print info message."""
    print(colorize(f"ℹ {message}", Colors.BLUE))


def print_header(title: str) -> None:
    """Print section header."""
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
    print("─" * len(title))


def get_config_path() -> Path:
    """Get configuration file path."""
    config_dir = Path(os.getenv("AURA_CONFIG_DIR", "~/.aura")).expanduser()
    return config_dir / "config.yaml"


def load_config() -> CLIConfig:
    """Load CLI configuration."""
    config_path = get_config_path()

    if config_path.exists():
        try:
            import yaml

            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                return CLIConfig(**data)
        except Exception:
            pass

    return CLIConfig()


def save_config(config: CLIConfig) -> None:
    """Save CLI configuration."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import yaml

        with open(config_path, "w") as f:
            yaml.dump(asdict(config), f, default_flow_style=False)
    except ImportError:
        # Fallback to JSON if yaml not available
        with open(config_path.with_suffix(".json"), "w") as f:
            json.dump(asdict(config), f, indent=2)


# ============================================================================
# Command Implementations
# ============================================================================


def cmd_version(args: argparse.Namespace) -> int:
    """Show version information."""
    if args.json:
        print(
            json.dumps(
                {
                    "version": __version__,
                    "build": __build__,
                    "python": sys.version.split()[0],
                    "platform": sys.platform,
                }
            )
        )
    else:
        print(get_banner())
        print(f"  {Colors.BOLD}Version:{Colors.RESET}  {__version__}")
        print(f"  {Colors.BOLD}Build:{Colors.RESET}    {__build__}")
        print(f"  {Colors.BOLD}Python:{Colors.RESET}   {sys.version.split()[0]}")
        print(f"  {Colors.BOLD}Platform:{Colors.RESET} {sys.platform}")
        print()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show deployment status."""
    try:
        status = get_deployment_status()

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print_header("Project Aura Status")

            # Deployment info
            print(f"\n{'Deployment:':<20} {status.get('deployment_name', 'N/A')}")
            print(f"{'Environment:':<20} {status.get('environment', 'N/A')}")
            print(f"{'Version:':<20} {status.get('version', 'N/A')}")

            # License status
            license_info = status.get("license", {})
            license_status = license_info.get("edition", "community")
            if license_info.get("is_valid"):
                print(
                    f"{'License:':<20} {colorize(license_status.upper(), Colors.GREEN)}"
                )
            else:
                print(f"{'License:':<20} {colorize('UNLICENSED', Colors.YELLOW)}")

            # Services
            print_header("Services")
            services = status.get("services", {})
            for name, svc_status in services.items():
                if svc_status.get("healthy"):
                    indicator = colorize("●", Colors.GREEN)
                else:
                    indicator = colorize("●", Colors.RED)
                print(f"  {indicator} {name}: {svc_status.get('status', 'unknown')}")

        return 0

    except Exception as e:
        print_error(f"Failed to get status: {e}")
        return 1


def cmd_config_init(args: argparse.Namespace) -> int:
    """Initialize CLI configuration."""
    config_path = get_config_path()

    if config_path.exists() and not args.force:
        print_warning(f"Configuration already exists at {config_path}")
        print_info("Use --force to overwrite")
        return 1

    config = CLIConfig()

    if args.interactive:
        print_header("Aura CLI Configuration")

        # API URL
        default_url = config.api_url
        api_url = input(f"API URL [{default_url}]: ").strip() or default_url
        config.api_url = api_url

        # Output format
        default_format = config.output_format
        output_format = (
            input(f"Output format (text/json/yaml) [{default_format}]: ").strip()
            or default_format
        )
        config.output_format = output_format

    save_config(config)
    print_success(f"Configuration saved to {config_path}")
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    """Show current configuration."""
    config = load_config()

    if args.json:
        print(json.dumps(asdict(config), indent=2))
    else:
        print_header("Aura CLI Configuration")
        for key, value in asdict(config).items():
            print(f"  {key}: {value}")

    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    """Set a configuration value."""
    config = load_config()

    if not hasattr(config, args.key):
        print_error(f"Unknown configuration key: {args.key}")
        return 1

    setattr(config, args.key, args.value)
    save_config(config)
    print_success(f"Set {args.key} = {args.value}")
    return 0


def cmd_license_status(args: argparse.Namespace) -> int:
    """Show license status."""
    try:
        license_info = get_license_status()

        if args.json:
            print(json.dumps(license_info, indent=2))
        else:
            print_header("License Status")

            if license_info.get("licensed"):
                print_success("License is active")
                print(
                    f"\n{'Edition:':<20} {license_info.get('edition', 'N/A').upper()}"
                )
                print(
                    f"{'Organization:':<20} {license_info.get('organization', 'N/A')}"
                )
                print(f"{'Expires:':<20} {license_info.get('expires_at', 'N/A')}")

                days = license_info.get("days_until_expiry", 0)
                if days <= 30:
                    print(
                        colorize(
                            f"{'Days Remaining:':<20} {days} (expiring soon!)",
                            Colors.YELLOW,
                        )
                    )
                else:
                    print(f"{'Days Remaining:':<20} {days}")

                print(
                    f"{'Max Users:':<20} {license_info.get('max_users', 'Unlimited') or 'Unlimited'}"
                )
                print(
                    f"{'Max Repos:':<20} {license_info.get('max_repositories', 'Unlimited') or 'Unlimited'}"
                )
            else:
                print_warning("No active license")
                print_info("Running in Community Edition mode")
                pricing_url = os.environ.get(
                    "PRICING_PAGE_URL", "https://app.aura.local/pricing"
                )
                print_info(f"Visit {pricing_url} for upgrade options")

        return 0

    except Exception as e:
        print_error(f"Failed to get license status: {e}")
        return 1


def cmd_license_activate(args: argparse.Namespace) -> int:
    """Activate a license key."""
    license_key = args.license_key

    if not license_key:
        print_error("License key is required")
        return 1

    try:
        result = activate_license(license_key)

        if result.get("success"):
            print_success("License activated successfully!")
            print(f"Edition: {result.get('edition', 'N/A').upper()}")
            print(f"Expires: {result.get('expires_at', 'N/A')}")
        else:
            print_error(
                f"License activation failed: {result.get('error', 'Unknown error')}"
            )
            return 1

        return 0

    except Exception as e:
        print_error(f"Failed to activate license: {e}")
        return 1


def cmd_license_request(args: argparse.Namespace) -> int:
    """Generate offline license request."""
    try:
        from src.services.licensing.offline_validator import OfflineLicenseValidator

        request_data = OfflineLicenseValidator.generate_license_request()

        if args.json:
            print(json.dumps(request_data, indent=2))
        else:
            print_header("Offline License Request")
            support_email = os.environ.get("SUPPORT_EMAIL", "support@aura.local")
            print_info(f"Send this information to {support_email}")
            print()
            print(json.dumps(request_data, indent=2))
            print()
            print_info("You will receive a license key file for offline activation")

        return 0

    except ImportError:
        print_error("Licensing module not available")
        return 1
    except Exception as e:
        print_error(f"Failed to generate license request: {e}")
        return 1


def cmd_health(args: argparse.Namespace) -> int:
    """Check system health."""
    try:
        health = get_health_status()

        if args.json:
            print(json.dumps(health, indent=2))
        else:
            print_header("System Health")

            overall = health.get("status", "unknown")
            if overall == "healthy":
                print_success("All systems operational")
            elif overall == "degraded":
                print_warning("Some systems degraded")
            else:
                print_error("System unhealthy")

            if args.verbose:
                print_header("Component Health")
                for component, status in health.get("components", {}).items():
                    healthy = status.get("healthy", False)
                    indicator = colorize("●", Colors.GREEN if healthy else Colors.RED)
                    print(f"  {indicator} {component}")
                    if not healthy and status.get("error"):
                        print(f"      Error: {status['error']}")

        return 0 if health.get("status") == "healthy" else 1

    except Exception as e:
        print_error(f"Health check failed: {e}")
        return 1


def cmd_deploy_status(args: argparse.Namespace) -> int:
    """Show deployment status."""
    return cmd_status(args)


def cmd_deploy_upgrade(args: argparse.Namespace) -> int:
    """Upgrade deployment to latest version."""
    print_header("Deployment Upgrade")

    if args.dry_run:
        print_info("Dry run mode - no changes will be made")

    # Check current version
    current = get_deployment_status().get("version", "unknown")
    print(f"Current version: {current}")

    # Check for updates
    print_info("Checking for updates...")

    try:
        latest = check_for_updates()

        if latest.get("version") == current:
            print_success("Already running the latest version")
            return 0

        print(f"Latest version: {latest.get('version')}")
        print(f"Release notes: {latest.get('release_notes_url', 'N/A')}")

        if args.dry_run:
            print_info("Would upgrade to version " + latest.get("version"))
            return 0

        # Confirm upgrade
        if not args.yes:
            confirm = input("\nProceed with upgrade? [y/N]: ").strip().lower()
            if confirm != "y":
                print_info("Upgrade cancelled")
                return 0

        # Perform upgrade
        print_info("Starting upgrade...")
        result = perform_upgrade(latest.get("version"))

        if result.get("success"):
            print_success("Upgrade completed successfully!")
        else:
            print_error(f"Upgrade failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        print_error(f"Upgrade failed: {e}")
        return 1


def cmd_logs(args: argparse.Namespace) -> int:
    """View service logs."""
    service = args.service or "all"
    tail = args.tail or 100

    try:
        logs = get_service_logs(service, tail)

        if args.json:
            print(json.dumps(logs, indent=2))
        else:
            print_header(f"Logs: {service}")
            for entry in logs.get("entries", []):
                timestamp = entry.get("timestamp", "")
                level = entry.get("level", "INFO")
                message = entry.get("message", "")

                # Color by level
                if level == "ERROR":
                    level_color = Colors.RED
                elif level == "WARN":
                    level_color = Colors.YELLOW
                else:
                    level_color = Colors.RESET

                print(f"{timestamp} [{colorize(level, level_color)}] {message}")

        return 0

    except Exception as e:
        print_error(f"Failed to get logs: {e}")
        return 1


# ============================================================================
# API/Backend Functions (stubs for now, will integrate with actual API)
# ============================================================================


def get_deployment_status() -> dict[str, Any]:
    """Get deployment status from API or local state."""
    # Try to connect to local API
    config = load_config()

    try:
        import httpx

        response = httpx.get(f"{config.api_url}/api/v1/status", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    # Return mock/offline status
    return {
        "deployment_name": os.getenv("AURA_DEPLOYMENT_NAME", "aura"),
        "environment": os.getenv("AURA_ENVIRONMENT", "development"),
        "version": __version__,
        "license": {"edition": "community", "is_valid": False},
        "services": {
            "api": {"status": "unknown", "healthy": False},
            "orchestrator": {"status": "unknown", "healthy": False},
            "context-retrieval": {"status": "unknown", "healthy": False},
        },
    }


def get_license_status() -> dict[str, Any]:
    """Get license status."""
    try:
        from src.services.licensing import LicenseService

        service = LicenseService()
        return service.get_status()
    except ImportError:
        return {"licensed": False, "edition": "community"}


def activate_license(license_key: str) -> dict[str, Any]:
    """Activate a license key."""
    try:
        from src.services.licensing import LicenseService

        service = LicenseService(license_key=license_key)
        info = service.get_license_info()

        if info:
            # Save license key to config
            config_path = get_config_path().parent / "license.key"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(license_key)

            return {
                "success": True,
                "edition": info.edition.value,
                "expires_at": info.expires_at.isoformat(),
            }
        return {"success": False, "error": "Invalid license key"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_health_status() -> dict[str, Any]:
    """Get health status."""
    config = load_config()

    try:
        import httpx

        response = httpx.get(f"{config.api_url}/health", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    return {
        "status": "unknown",
        "components": {},
    }


def check_for_updates() -> dict[str, Any]:
    """Check for available updates."""
    try:
        import os as _os

        import httpx

        api_releases_url = _os.environ.get(
            "API_RELEASES_URL", "https://api.aura.local/v1/releases/latest"
        )
        response = httpx.get(
            api_releases_url,
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass

    return {"version": __version__}


def perform_upgrade(version: str) -> dict[str, Any]:
    """Perform upgrade to specified version."""
    # This would integrate with helm upgrade or kubectl apply
    return {"success": False, "error": "Upgrade not yet implemented"}


def get_service_logs(service: str, tail: int) -> dict[str, Any]:
    """Get service logs."""
    return {
        "service": service,
        "entries": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "message": "Log retrieval requires kubectl access",
            }
        ],
    }


# ============================================================================
# Main Entry Point
# ============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="aura",
        description="Project Aura CLI - Autonomous Code Intelligence Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status command
    status_parser = subparsers.add_parser("status", help="Show deployment status")
    status_parser.add_argument("--json", action="store_true", help="JSON output")

    # config commands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    config_init = config_subparsers.add_parser("init", help="Initialize configuration")
    config_init.add_argument("-i", "--interactive", action="store_true")
    config_init.add_argument("-f", "--force", action="store_true")

    config_show = config_subparsers.add_parser("show", help="Show configuration")
    config_show.add_argument("--json", action="store_true")

    config_set = config_subparsers.add_parser("set", help="Set configuration value")
    config_set.add_argument("key", help="Configuration key")
    config_set.add_argument("value", help="Configuration value")

    # license commands
    license_parser = subparsers.add_parser("license", help="License management")
    license_subparsers = license_parser.add_subparsers(dest="license_command")

    license_status = license_subparsers.add_parser("status", help="Show license status")
    license_status.add_argument("--json", action="store_true")

    license_activate = license_subparsers.add_parser(
        "activate", help="Activate license"
    )
    license_activate.add_argument("license_key", help="License key to activate")

    license_request = license_subparsers.add_parser(
        "request", help="Generate offline license request"
    )
    license_request.add_argument("--json", action="store_true")

    # deploy commands
    deploy_parser = subparsers.add_parser("deploy", help="Deployment management")
    deploy_subparsers = deploy_parser.add_subparsers(dest="deploy_command")

    deploy_status = deploy_subparsers.add_parser(
        "status", help="Show deployment status"
    )
    deploy_status.add_argument("--json", action="store_true")

    deploy_upgrade = deploy_subparsers.add_parser("upgrade", help="Upgrade deployment")
    deploy_upgrade.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    deploy_upgrade.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation"
    )

    # health command
    health_parser = subparsers.add_parser("health", help="Check system health")
    health_parser.add_argument("--json", action="store_true")
    health_parser.add_argument("-v", "--verbose", action="store_true")

    # logs command
    logs_parser = subparsers.add_parser("logs", help="View service logs")
    logs_parser.add_argument("--service", "-s", help="Service name")
    logs_parser.add_argument(
        "--tail", "-n", type=int, default=100, help="Number of lines"
    )
    logs_parser.add_argument("--json", action="store_true")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Handle --no-color
    if args.no_color or os.getenv("NO_COLOR"):
        Colors.disable()

    # Handle --version at top level
    if args.version:
        return cmd_version(args)

    # Route to command handlers
    if args.command == "status":
        return cmd_status(args)

    elif args.command == "config":
        if args.config_command == "init":
            return cmd_config_init(args)
        elif args.config_command == "show":
            return cmd_config_show(args)
        elif args.config_command == "set":
            return cmd_config_set(args)
        else:
            parser.parse_args(["config", "--help"])
            return 1

    elif args.command == "license":
        if args.license_command == "status":
            return cmd_license_status(args)
        elif args.license_command == "activate":
            return cmd_license_activate(args)
        elif args.license_command == "request":
            return cmd_license_request(args)
        else:
            parser.parse_args(["license", "--help"])
            return 1

    elif args.command == "deploy":
        if args.deploy_command == "status":
            return cmd_deploy_status(args)
        elif args.deploy_command == "upgrade":
            return cmd_deploy_upgrade(args)
        else:
            parser.parse_args(["deploy", "--help"])
            return 1

    elif args.command == "health":
        return cmd_health(args)

    elif args.command == "logs":
        return cmd_logs(args)

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
