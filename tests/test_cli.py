"""
Tests for Aura CLI.

Tests command-line interface functionality including argument parsing,
command execution, and output formatting.
"""

import json
import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for proper isolation due to global config state.
# On Linux (CI), pytest-forked causes mock patches to not apply correctly.
# On macOS/Windows, forked mode works correctly and provides test isolation.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.cli.main import (
    CLIConfig,
    Colors,
    cmd_config_init,
    cmd_config_set,
    cmd_config_show,
    cmd_health,
    cmd_license_request,
    cmd_license_status,
    cmd_status,
    cmd_version,
    colorize,
    create_parser,
    get_banner,
    get_config_path,
    load_config,
    main,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    save_config,
)


class TestColors:
    """Tests for Colors class."""

    def test_colors_have_values(self):
        """Test color codes are defined."""
        assert Colors.RESET != ""
        assert Colors.RED != ""
        assert Colors.GREEN != ""
        assert Colors.YELLOW != ""
        assert Colors.BLUE != ""
        assert Colors.CYAN != ""
        assert Colors.WHITE != ""
        assert Colors.DIM != ""
        assert Colors.BOLD != ""

    def test_disable_colors(self):
        """Test disabling colors."""
        # Save original values
        original_reset = Colors.RESET
        original_red = Colors.RED
        original_dim = Colors.DIM
        original_white = Colors.WHITE

        Colors.disable()

        assert Colors.RESET == ""
        assert Colors.RED == ""
        assert Colors.GREEN == ""
        assert Colors.DIM == ""
        assert Colors.WHITE == ""

        # Restore (since class is modified globally)
        Colors.RESET = original_reset
        Colors.RED = original_red
        Colors.DIM = original_dim
        Colors.WHITE = original_white


class TestBanner:
    """Tests for CLI banner."""

    def test_get_banner_contains_branding(self):
        """Test banner contains expected branding."""
        banner = get_banner()
        assert "Autonomous Code Intelligence Platform" in banner
        assert "Aenea Labs" in banner

    def test_get_banner_contains_ascii_art(self):
        """Test banner contains ASCII art box elements."""
        banner = get_banner()
        assert "┌" in banner  # Top left corner
        assert "┐" in banner  # Top right corner
        assert "└" in banner  # Bottom left corner
        assert "┘" in banner  # Bottom right corner
        assert "│" in banner  # Vertical lines


class TestColorize:
    """Tests for colorize function."""

    def test_colorize_text(self):
        """Test colorizing text."""
        result = colorize("test", Colors.RED)
        assert Colors.RED in result
        assert "test" in result
        assert Colors.RESET in result

    def test_colorize_with_disabled_colors(self):
        """Test colorize with disabled colors."""
        # Temporarily disable both color and reset
        original_red = Colors.RED
        original_reset = Colors.RESET
        Colors.RED = ""
        Colors.RESET = ""

        result = colorize("test", Colors.RED)
        assert result == "test"

        Colors.RED = original_red
        Colors.RESET = original_reset


class TestPrintFunctions:
    """Tests for print helper functions."""

    def test_print_success(self, capsys):
        """Test print_success output."""
        print_success("Operation completed")
        captured = capsys.readouterr()
        assert "Operation completed" in captured.out
        assert "✓" in captured.out

    def test_print_error(self, capsys):
        """Test print_error output."""
        print_error("Something failed")
        captured = capsys.readouterr()
        assert "Something failed" in captured.err
        assert "✗" in captured.err

    def test_print_warning(self, capsys):
        """Test print_warning output."""
        print_warning("Be careful")
        captured = capsys.readouterr()
        assert "Be careful" in captured.out
        assert "⚠" in captured.out

    def test_print_info(self, capsys):
        """Test print_info output."""
        print_info("FYI")
        captured = capsys.readouterr()
        assert "FYI" in captured.out
        assert "ℹ" in captured.out

    def test_print_header(self, capsys):
        """Test print_header output."""
        print_header("Section Title")
        captured = capsys.readouterr()
        assert "Section Title" in captured.out
        assert "─" in captured.out


class TestCLIConfig:
    """Tests for CLIConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CLIConfig()

        assert config.api_url == "http://localhost:8080"
        assert config.config_dir == "~/.aura"
        assert config.log_level == "INFO"
        assert config.output_format == "text"
        assert config.color_enabled is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CLIConfig(
            api_url="http://custom:9000",
            log_level="DEBUG",
            color_enabled=False,
        )

        assert config.api_url == "http://custom:9000"
        assert config.log_level == "DEBUG"
        assert config.color_enabled is False


class TestConfigPath:
    """Tests for configuration path functions."""

    def test_get_config_path_default(self):
        """Test default config path."""
        with patch.dict(os.environ, {"AURA_CONFIG_DIR": ""}, clear=False):
            # Remove env var if set
            os.environ.pop("AURA_CONFIG_DIR", None)
            path = get_config_path()
            assert path.name == "config.yaml"
            assert ".aura" in str(path)

    def test_get_config_path_custom(self):
        """Test custom config path via environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                path = get_config_path()
                assert str(path).startswith(tmpdir)


class TestLoadSaveConfig:
    """Tests for config load/save functions."""

    def test_load_config_default(self):
        """Test loading default config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                config = load_config()
                assert isinstance(config, CLIConfig)
                assert config.api_url == "http://localhost:8080"

    def test_save_and_load_config(self):
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                # Create custom config
                config = CLIConfig(
                    api_url="http://test:8080",
                    log_level="DEBUG",
                )

                # Save
                save_config(config)

                # Verify file exists
                config_path = get_config_path()
                assert config_path.exists() or config_path.with_suffix(".json").exists()


class TestParser:
    """Tests for argument parser."""

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "aura"

    def test_parse_version(self):
        """Test parsing --version."""
        parser = create_parser()
        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_parse_status(self):
        """Test parsing status command."""
        parser = create_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_parse_status_json(self):
        """Test parsing status --json."""
        parser = create_parser()
        args = parser.parse_args(["status", "--json"])
        assert args.command == "status"
        assert args.json is True

    def test_parse_config_init(self):
        """Test parsing config init."""
        parser = create_parser()
        args = parser.parse_args(["config", "init", "--interactive"])
        assert args.command == "config"
        assert args.config_command == "init"
        assert args.interactive is True

    def test_parse_config_set(self):
        """Test parsing config set."""
        parser = create_parser()
        args = parser.parse_args(["config", "set", "api_url", "http://new:8080"])
        assert args.command == "config"
        assert args.config_command == "set"
        assert args.key == "api_url"
        assert args.value == "http://new:8080"

    def test_parse_license_activate(self):
        """Test parsing license activate."""
        parser = create_parser()
        args = parser.parse_args(["license", "activate", "LICENSE-KEY-123"])
        assert args.command == "license"
        assert args.license_command == "activate"
        assert args.license_key == "LICENSE-KEY-123"

    def test_parse_health_verbose(self):
        """Test parsing health --verbose."""
        parser = create_parser()
        args = parser.parse_args(["health", "--verbose"])
        assert args.command == "health"
        assert args.verbose is True

    def test_parse_logs(self):
        """Test parsing logs command."""
        parser = create_parser()
        args = parser.parse_args(["logs", "--service", "api", "--tail", "50"])
        assert args.command == "logs"
        assert args.service == "api"
        assert args.tail == 50

    def test_parse_deploy_upgrade(self):
        """Test parsing deploy upgrade."""
        parser = create_parser()
        args = parser.parse_args(["deploy", "upgrade", "--dry-run", "-y"])
        assert args.command == "deploy"
        assert args.deploy_command == "upgrade"
        assert args.dry_run is True
        assert args.yes is True


class TestCmdVersion:
    """Tests for version command."""

    def test_cmd_version_text(self, capsys):
        """Test version command text output."""
        parser = create_parser()
        args = parser.parse_args(["--version"])
        args.json = False

        result = cmd_version(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Autonomous Code Intelligence Platform" in captured.out
        assert "Version:" in captured.out
        assert "Aenea Labs" in captured.out

    def test_cmd_version_json(self, capsys):
        """Test version command JSON output."""
        parser = create_parser()
        args = parser.parse_args(["--version"])
        args.json = True

        result = cmd_version(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "version" in data
        assert "platform" in data


class TestCmdStatus:
    """Tests for status command."""

    def test_cmd_status_text(self, capsys):
        """Test status command text output."""
        parser = create_parser()
        args = parser.parse_args(["status"])

        with patch("src.cli.main.get_deployment_status") as mock_status:
            mock_status.return_value = {
                "deployment_name": "test-aura",
                "environment": "dev",
                "version": "1.0.0",
                "license": {"edition": "community", "is_valid": False},
                "services": {},
            }

            result = cmd_status(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "test-aura" in captured.out

    def test_cmd_status_json(self, capsys):
        """Test status command JSON output."""
        parser = create_parser()
        args = parser.parse_args(["status", "--json"])

        with patch("src.cli.main.get_deployment_status") as mock_status:
            mock_status.return_value = {
                "deployment_name": "test-aura",
                "environment": "dev",
                "version": "1.0.0",
            }

            result = cmd_status(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["deployment_name"] == "test-aura"


class TestCmdConfigInit:
    """Tests for config init command."""

    def test_cmd_config_init_force(self):
        """Test config init with --force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                parser = create_parser()
                args = parser.parse_args(["config", "init", "--force"])
                args.interactive = False

                result = cmd_config_init(args)

                assert result == 0

    def test_cmd_config_init_exists_no_force(self, capsys):
        """Test config init when config exists without force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                # Create existing config
                config_path = Path(tmpdir) / "config.yaml"
                config_path.write_text("api_url: test")

                parser = create_parser()
                args = parser.parse_args(["config", "init"])
                args.interactive = False
                args.force = False

                result = cmd_config_init(args)

                assert result == 1
                captured = capsys.readouterr()
                assert "already exists" in captured.out


class TestCmdConfigShow:
    """Tests for config show command."""

    def test_cmd_config_show_text(self, capsys):
        """Test config show text output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                parser = create_parser()
                args = parser.parse_args(["config", "show"])
                args.json = False

                result = cmd_config_show(args)

                assert result == 0
                captured = capsys.readouterr()
                assert "api_url" in captured.out

    def test_cmd_config_show_json(self, capsys):
        """Test config show JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                parser = create_parser()
                args = parser.parse_args(["config", "show", "--json"])

                result = cmd_config_show(args)

                assert result == 0
                captured = capsys.readouterr()
                data = json.loads(captured.out)
                assert "api_url" in data


class TestCmdConfigSet:
    """Tests for config set command."""

    def test_cmd_config_set_valid(self, capsys):
        """Test setting valid config value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                parser = create_parser()
                args = parser.parse_args(
                    ["config", "set", "api_url", "http://new:9000"]
                )

                result = cmd_config_set(args)

                assert result == 0
                captured = capsys.readouterr()
                assert "Set api_url" in captured.out

    def test_cmd_config_set_invalid_key(self, capsys):
        """Test setting invalid config key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AURA_CONFIG_DIR": tmpdir}):
                parser = create_parser()
                args = parser.parse_args(["config", "set", "invalid_key", "value"])

                result = cmd_config_set(args)

                assert result == 1
                captured = capsys.readouterr()
                assert "Unknown configuration key" in captured.err


class TestCmdLicenseStatus:
    """Tests for license status command."""

    def test_cmd_license_status_unlicensed(self, capsys):
        """Test license status when unlicensed."""
        parser = create_parser()
        args = parser.parse_args(["license", "status"])
        args.json = False

        with patch("src.cli.main.get_license_status") as mock_status:
            mock_status.return_value = {"licensed": False}

            result = cmd_license_status(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No active license" in captured.out

    def test_cmd_license_status_licensed(self, capsys):
        """Test license status when licensed."""
        parser = create_parser()
        args = parser.parse_args(["license", "status"])
        args.json = False

        with patch("src.cli.main.get_license_status") as mock_status:
            mock_status.return_value = {
                "licensed": True,
                "edition": "enterprise",
                "organization": "Test Corp",
                "expires_at": "2026-12-31T00:00:00",
                "days_until_expiry": 365,
                "max_users": 100,
                "max_repositories": 50,
            }

            result = cmd_license_status(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "ENTERPRISE" in captured.out
        assert "Test Corp" in captured.out


class TestCmdHealth:
    """Tests for health command."""

    def test_cmd_health_healthy(self, capsys):
        """Test health command when healthy."""
        parser = create_parser()
        args = parser.parse_args(["health"])
        args.json = False
        args.verbose = False

        with patch("src.cli.main.get_health_status") as mock_health:
            mock_health.return_value = {"status": "healthy", "components": {}}

            result = cmd_health(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "operational" in captured.out

    def test_cmd_health_degraded(self, capsys):
        """Test health command when degraded."""
        parser = create_parser()
        args = parser.parse_args(["health"])
        args.json = False
        args.verbose = False

        with patch("src.cli.main.get_health_status") as mock_health:
            mock_health.return_value = {"status": "degraded", "components": {}}

            result = cmd_health(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "degraded" in captured.out


class TestMain:
    """Tests for main entry point."""

    def test_main_no_args(self, capsys):
        """Test main with no arguments shows help."""
        result = main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "aura" in captured.out.lower()

    def test_main_version(self, capsys):
        """Test main with --version."""
        result = main(["--version"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Autonomous Code Intelligence Platform" in captured.out
        assert "Aenea Labs" in captured.out

    def test_main_no_color(self, capsys):
        """Test main with --no-color."""
        # Save original
        original = Colors.RED

        result = main(["--no-color", "--version"])

        # Colors should be disabled
        assert result == 0

        # Restore
        Colors.RED = original

    def test_main_status(self):
        """Test main with status command."""
        with patch("src.cli.main.get_deployment_status") as mock_status:
            mock_status.return_value = {
                "deployment_name": "test",
                "environment": "dev",
                "version": "1.0.0",
                "license": {},
                "services": {},
            }

            result = main(["status"])
            assert result == 0


class TestCmdLicenseRequest:
    """Tests for license request command."""

    def test_cmd_license_request_success(self, capsys):
        """Test license request generation."""
        parser = create_parser()
        args = parser.parse_args(["license", "request"])
        args.json = False

        # Mock the import inside the function
        mock_validator_class = MagicMock()
        mock_validator_class.generate_license_request.return_value = {
            "fingerprint": "abc123",
            "system": {"platform": "Linux"},
            "request_time": "2026-01-03T00:00:00",
        }

        with patch.dict(
            "sys.modules",
            {
                "src.services.licensing.offline_validator": MagicMock(
                    OfflineLicenseValidator=mock_validator_class
                )
            },
        ):
            result = cmd_license_request(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "License Request" in captured.out or "fingerprint" in captured.out

    def test_cmd_license_request_import_error(self, capsys):
        """Test license request when module not available."""
        parser = create_parser()
        args = parser.parse_args(["license", "request"])
        args.json = False

        # Force ImportError by removing the module from sys.modules
        with patch.dict(
            "sys.modules",
            {"src.services.licensing.offline_validator": None},
        ):
            result = cmd_license_request(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "not available" in captured.err or "failed" in captured.err.lower()
