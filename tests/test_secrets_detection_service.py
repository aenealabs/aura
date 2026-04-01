"""
Project Aura - Secrets Detection Service Tests

Tests for the secrets detection service covering:
- AWS credential detection
- API key detection
- Private key detection
- Database credential detection
- High entropy string detection
- False positive handling

Author: Project Aura Team
Created: 2025-12-12
"""

import pytest

from src.services.secrets_detection_service import (
    ScanResult,
    SecretsDetectionService,
    SecretSeverity,
    SecretType,
    get_secrets_service,
    scan_for_secrets,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def detector():
    """Create a fresh detector instance for testing."""
    return SecretsDetectionService(
        enable_entropy_detection=True,
        log_findings=False,
    )


@pytest.fixture
def detector_no_entropy():
    """Create a detector without entropy detection."""
    return SecretsDetectionService(
        enable_entropy_detection=False,
        log_findings=False,
    )


# ============================================================================
# AWS Credential Tests
# ============================================================================


class TestAWSCredentials:
    """Tests for AWS credential detection."""

    def test_detect_aws_access_key(self, detector):
        """Test detection of AWS Access Key ID."""
        text = "aws_access_key = AKIAIOSFODNN7EXAMPLE"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert len(result.findings) >= 1
        assert any(f.secret_type == SecretType.AWS_ACCESS_KEY for f in result.findings)

    def test_detect_aws_access_key_in_config(self, detector):
        """Test AWS key detection in configuration context."""
        text = """
        [default]
        aws_access_key_id = AKIAIOSFODNN7EXAMPLE
        """
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.AWS_ACCESS_KEY for f in result.findings)

    def test_detect_aws_secret_key(self, detector):
        """Test detection of AWS Secret Access Key."""
        text = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.AWS_SECRET_KEY for f in result.findings)

    def test_aws_key_severity_is_critical(self, detector):
        """Test that AWS keys are marked as critical severity."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = detector.scan_text(text)

        for finding in result.findings:
            if finding.secret_type == SecretType.AWS_ACCESS_KEY:
                assert finding.severity == SecretSeverity.CRITICAL


# ============================================================================
# API Key Tests
# ============================================================================


class TestAPIKeys:
    """Tests for API key detection."""

    def test_detect_openai_api_key(self, detector):
        """Test detection of OpenAI API key."""
        text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456789012345678901234"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.OPENAI_API_KEY for f in result.findings)

    def test_detect_anthropic_api_key(self, detector):
        """Test detection of Anthropic API key."""
        text = 'api_key = "sk-ant-api01-abcdefghijklmnopqrstuvwxyz1234567890"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(
            f.secret_type == SecretType.ANTHROPIC_API_KEY for f in result.findings
        )

    def test_detect_github_pat(self, detector):
        """Test detection of GitHub Personal Access Token."""
        text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.GITHUB_PAT for f in result.findings)

    def test_detect_github_oauth_token(self, detector):
        """Test detection of GitHub OAuth token."""
        text = "token = gho_abcdefghijklmnopqrstuvwxyz1234567890"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.GITHUB_TOKEN for f in result.findings)

    def test_detect_gitlab_token(self, detector):
        """Test detection of GitLab token."""
        text = "GITLAB_TOKEN=glpat-AbCdEfGhIjKlMnOpQrSt"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.GITLAB_TOKEN for f in result.findings)

    def test_detect_slack_token(self, detector):
        """Test detection of Slack token."""
        text = 'slack_token = "xoxb-123456789-123456789-AbCdEfGhIj"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.SLACK_TOKEN for f in result.findings)

    def test_detect_slack_webhook(self, detector):
        """Test detection of Slack webhook URL."""
        text = "webhook = https://hooks.slack.com/services/T12345678/B12345678/AbCdEfGhIjKlMnOpQrSt"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.SLACK_WEBHOOK for f in result.findings)

    def test_detect_stripe_live_key(self, detector):
        """Test detection of Stripe live key."""
        text = "STRIPE_KEY=sk_live_abcdefghijklmnopqrstuvwxyz"
        result = detector.scan_text(text)

        assert result.has_secrets
        finding = next(
            f for f in result.findings if f.secret_type == SecretType.STRIPE_KEY
        )
        assert finding.severity == SecretSeverity.CRITICAL

    def test_detect_stripe_test_key_low_severity(self, detector):
        """Test that Stripe test key has low severity."""
        text = "STRIPE_KEY=sk_test_abcdefghijklmnopqrstuvwxyz"
        result = detector.scan_text(text)

        assert result.has_secrets
        finding = next(
            f for f in result.findings if f.secret_type == SecretType.STRIPE_KEY
        )
        assert finding.severity == SecretSeverity.LOW

    def test_detect_sendgrid_api_key(self, detector):
        """Test detection of SendGrid API key."""
        # SendGrid format: SG.[22+ chars].[43+ chars]
        text = "SENDGRID_API_KEY=SG.abcdefghijklmnopqrstuv.vwxyz1234567890abcdefghijklmnopqrstuvwxyz1234567"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(
            f.secret_type == SecretType.SENDGRID_API_KEY for f in result.findings
        )

    def test_detect_twilio_api_key(self, detector):
        """Test detection of Twilio API key."""
        text = "TWILIO_KEY=SK12345678901234567890123456789012"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.TWILIO_API_KEY for f in result.findings)

    def test_detect_npm_token(self, detector):
        """Test detection of NPM token."""
        text = "NPM_TOKEN=npm_abcdefghijklmnopqrstuvwxyz1234567890"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.NPM_TOKEN for f in result.findings)

    def test_detect_pypi_token(self, detector):
        """Test detection of PyPI token."""
        text = "PYPI_TOKEN=pypi-abcdefghijklmnopqrstuvwxyz12345678901234567890123456"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.PYPI_TOKEN for f in result.findings)

    def test_detect_gcp_api_key(self, detector):
        """Test detection of GCP API key."""
        text = "GCP_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz1234567"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.GCP_API_KEY for f in result.findings)

    def test_detect_generic_api_key(self, detector):
        """Test detection of generic API key pattern."""
        text = 'api_key = "abcdefghijklmnopqrstuvwxyz1234567890"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.GENERIC_API_KEY for f in result.findings)


# ============================================================================
# Private Key Tests
# ============================================================================


class TestPrivateKeys:
    """Tests for private key detection."""

    def test_detect_rsa_private_key(self, detector):
        """Test detection of RSA private key."""
        text = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.RSA_PRIVATE_KEY for f in result.findings)

    def test_detect_generic_private_key(self, detector):
        """Test detection of generic private key."""
        text = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBg...
-----END PRIVATE KEY-----"""
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.RSA_PRIVATE_KEY for f in result.findings)

    def test_detect_ssh_private_key(self, detector):
        """Test detection of SSH private key."""
        text = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAA...
-----END OPENSSH PRIVATE KEY-----"""
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.SSH_PRIVATE_KEY for f in result.findings)

    def test_detect_pgp_private_key(self, detector):
        """Test detection of PGP private key."""
        text = """-----BEGIN PGP PRIVATE KEY BLOCK-----
lQPGBF...
-----END PGP PRIVATE KEY BLOCK-----"""
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.PGP_PRIVATE_KEY for f in result.findings)

    def test_detect_ec_private_key(self, detector):
        """Test detection of EC private key."""
        text = """-----BEGIN EC PRIVATE KEY-----
MHQCAQEEICJxAp...
-----END EC PRIVATE KEY-----"""
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.PRIVATE_KEY for f in result.findings)

    def test_private_key_severity_is_critical(self, detector):
        """Test that private keys are marked as critical."""
        text = "-----BEGIN RSA PRIVATE KEY-----"
        result = detector.scan_text(text)

        for finding in result.findings:
            if "PRIVATE_KEY" in finding.secret_type.value.upper():
                assert finding.severity == SecretSeverity.CRITICAL


# ============================================================================
# Database Credential Tests
# ============================================================================


class TestDatabaseCredentials:
    """Tests for database credential detection."""

    def test_detect_postgres_url(self, detector):
        """Test detection of PostgreSQL connection string."""
        text = "DATABASE_URL=postgresql://user:password@localhost:5432/mydb"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.DATABASE_URL for f in result.findings)

    def test_detect_mysql_url(self, detector):
        """Test detection of MySQL connection string."""
        # Note: example.com triggers false positive filter, use different host
        text = "DB_URL=mysql://root:secret123@mysql.production.internal/app"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.DATABASE_URL for f in result.findings)

    def test_detect_mongodb_url(self, detector):
        """Test detection of MongoDB connection string."""
        # Note: example.com triggers false positive filter, use different host
        text = "MONGO_URI=mongodb://admin:password@mongo.production.internal/db"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.DATABASE_URL for f in result.findings)

    def test_detect_mongodb_srv(self, detector):
        """Test detection of MongoDB SRV connection string."""
        text = "MONGO_URI=mongodb+srv://admin:password@cluster.mongodb.net/db"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.MONGODB_URI for f in result.findings)

    def test_detect_redis_password(self, detector):
        """Test detection of Redis connection with password."""
        # Note: example.com triggers false positive filter, use different host
        text = "REDIS_URL=redis://:secretpassword@redis.production.internal:6379"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.REDIS_PASSWORD for f in result.findings)


# ============================================================================
# Token Tests
# ============================================================================


class TestTokens:
    """Tests for token detection."""

    def test_detect_jwt_token(self, detector):
        """Test detection of JWT token."""
        # Real JWT structure (header.payload.signature)
        text = 'token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.JWT_TOKEN for f in result.findings)

    def test_detect_bearer_token(self, detector):
        """Test detection of Bearer token."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.BEARER_TOKEN for f in result.findings)

    def test_detect_basic_auth(self, detector):
        """Test detection of Basic authentication."""
        text = 'Authorization = "Basic dXNlcm5hbWU6cGFzc3dvcmQ="'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.BASIC_AUTH for f in result.findings)


# ============================================================================
# Password Tests
# ============================================================================


class TestPasswords:
    """Tests for password detection."""

    def test_detect_password_assignment(self, detector):
        """Test detection of password assignment."""
        text = 'password = "MySecretPassword123!"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.PASSWORD for f in result.findings)

    def test_detect_passwd_assignment(self, detector):
        """Test detection of passwd assignment."""
        text = "passwd = 'admin@secure2024'"
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.PASSWORD for f in result.findings)

    def test_detect_secret_assignment(self, detector):
        """Test detection of secret assignment."""
        text = 'secret = "my-secret-value-12345"'
        result = detector.scan_text(text)

        assert result.has_secrets
        assert any(f.secret_type == SecretType.PASSWORD for f in result.findings)


# ============================================================================
# False Positive Tests
# ============================================================================


class TestFalsePositives:
    """Tests for false positive handling."""

    def test_ignore_example_domain(self, detector):
        """Test that example.com is ignored."""
        text = "url = https://api.example.com/v1"
        result = detector.scan_text(text)

        # Should have no findings or only low-priority ones
        assert not result.has_secrets or all(
            f.severity == SecretSeverity.LOW for f in result.findings
        )

    def test_ignore_placeholder_values(self, detector):
        """Test that placeholder values are ignored."""
        text = 'api_key = "your_api_key_here"'
        result = detector.scan_text(text)

        # Should not detect this as a secret
        high_severity = [
            f
            for f in result.findings
            if f.severity in [SecretSeverity.HIGH, SecretSeverity.CRITICAL]
        ]
        assert len(high_severity) == 0

    def test_ignore_template_variables(self, detector):
        """Test that template variables are ignored."""
        text = 'api_key = "${API_KEY}"'
        result = detector.scan_text(text)

        # Should not detect template variable as secret
        assert not result.has_secrets

    def test_ignore_xxx_placeholders(self, detector):
        """Test that xxx placeholders are ignored."""
        text = "password = xxxxxxxxxxxxxxxx"
        result = detector.scan_text(text)

        high_severity = [
            f
            for f in result.findings
            if f.severity in [SecretSeverity.HIGH, SecretSeverity.CRITICAL]
        ]
        assert len(high_severity) == 0

    def test_ignore_test_keys(self, detector):
        """Test that test/dummy keys are ignored."""
        text = 'test_api_key = "test_key_value_12345678901234567890"'
        result = detector.scan_text(text)

        # Should be ignored or low severity
        high_severity = [
            f
            for f in result.findings
            if f.severity in [SecretSeverity.HIGH, SecretSeverity.CRITICAL]
        ]
        assert len(high_severity) == 0


# ============================================================================
# High Entropy Tests
# ============================================================================


class TestHighEntropy:
    """Tests for high entropy string detection."""

    def test_detect_high_entropy_string(self, detector):
        """Test detection of high entropy strings."""
        # Random-looking string with high entropy
        text = 'secret = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5z"'
        result = detector.scan_text(text)

        # Should detect high entropy string
        assert result.has_secrets

    def test_low_entropy_not_detected(self, detector):
        """Test that low entropy strings are not detected."""
        text = 'value = "aaaaaaaaaaaaaaaaaaaaaaaaaaaa"'
        result = detector.scan_text(text)

        # Low entropy repeated characters should not be flagged
        high_entropy = [
            f
            for f in result.findings
            if f.secret_type == SecretType.HIGH_ENTROPY_STRING
        ]
        assert len(high_entropy) == 0

    def test_entropy_detection_disabled(self, detector_no_entropy):
        """Test that entropy detection can be disabled."""
        text = 'secret = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5z"'
        result = detector_no_entropy.scan_text(text)

        high_entropy = [
            f
            for f in result.findings
            if f.secret_type == SecretType.HIGH_ENTROPY_STRING
        ]
        assert len(high_entropy) == 0


# ============================================================================
# ScanResult Tests
# ============================================================================


class TestScanResult:
    """Tests for ScanResult class."""

    def test_scan_result_to_dict(self, detector):
        """Test ScanResult.to_dict()."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = detector.scan_text(text)

        d = result.to_dict()
        assert "has_secrets" in d
        assert "findings" in d
        assert "summary" in d
        assert "total_findings" in d["summary"]

    def test_scan_result_summary(self, detector):
        """Test ScanResult summary counts."""
        text = """
        AKIAIOSFODNN7EXAMPLE
        ghp_abcdefghijklmnopqrstuvwxyz1234567890
        """
        result = detector.scan_text(text)

        d = result.to_dict()
        assert d["summary"]["total_findings"] >= 2

    def test_scan_result_by_severity(self, detector):
        """Test ScanResult counts by severity."""
        text = """
        AKIAIOSFODNN7EXAMPLE
        sk_test_abcdefghijklmnopqrstuvwxyz
        """
        result = detector.scan_text(text)

        d = result.to_dict()
        assert "by_severity" in d["summary"]


# ============================================================================
# SecretFinding Tests
# ============================================================================


class TestSecretFinding:
    """Tests for SecretFinding class."""

    def test_finding_to_dict(self, detector):
        """Test SecretFinding.to_dict()."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = detector.scan_text(text)

        finding = result.findings[0]
        d = finding.to_dict()

        assert "secret_type" in d
        assert "severity" in d
        assert "line_number" in d
        assert "redacted_value" in d
        assert "recommendation" in d

    def test_finding_redaction(self, detector):
        """Test that values are properly redacted."""
        text = "AKIAIOSFODNN7EXAMPLE"
        result = detector.scan_text(text)

        finding = result.findings[0]
        # Redacted value should not contain full key
        assert "AKIAIOSFODNN7EXAMPLE" not in finding.redacted_value
        # Should show partial value
        assert "..." in finding.redacted_value


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    def test_stats_initialization(self, detector):
        """Test stats are initialized correctly."""
        stats = detector.get_stats()

        assert stats["total_scans"] == 0
        assert stats["total_findings"] == 0

    def test_stats_increment(self, detector):
        """Test stats increment on scan."""
        detector.scan_text("AKIAIOSFODNN7EXAMPLE")

        stats = detector.get_stats()
        assert stats["total_scans"] == 1
        assert stats["total_findings"] >= 1

    def test_stats_reset(self, detector):
        """Test stats can be reset."""
        detector.scan_text("AKIAIOSFODNN7EXAMPLE")
        detector.reset_stats()

        stats = detector.get_stats()
        assert stats["total_scans"] == 0
        assert stats["total_findings"] == 0


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_secrets_service_returns_instance(self):
        """Test get_secrets_service returns an instance."""
        service = get_secrets_service()
        assert isinstance(service, SecretsDetectionService)

    def test_get_secrets_service_singleton(self):
        """Test get_secrets_service returns same instance."""
        service1 = get_secrets_service()
        service2 = get_secrets_service()
        assert service1 is service2


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_scan_for_secrets_function(self):
        """Test scan_for_secrets convenience function."""
        result = scan_for_secrets("AKIAIOSFODNN7EXAMPLE")
        assert isinstance(result, ScanResult)
        assert result.has_secrets

    def test_scan_for_secrets_with_file_path(self):
        """Test scan_for_secrets with file path."""
        result = scan_for_secrets(
            "AKIAIOSFODNN7EXAMPLE",
            file_path="/path/to/file.py",
        )
        assert result.file_path == "/path/to/file.py"


# ============================================================================
# File Scanning Tests
# ============================================================================


class TestFileScanning:
    """Tests for file scanning."""

    def test_scan_file_not_found(self, detector):
        """Test scanning non-existent file."""
        result = detector.scan_file("/nonexistent/path/file.py")

        assert not result.has_secrets
        assert result.scanned_lines == 0

    def test_scan_file_with_secrets(self, detector, tmp_path):
        """Test scanning file with secrets."""
        # Create temp file with a secret
        test_file = tmp_path / "config.py"
        test_file.write_text("AWS_KEY = AKIAIOSFODNN7EXAMPLE")

        result = detector.scan_file(str(test_file))

        assert result.has_secrets
        assert result.file_path == str(test_file)

    def test_scan_file_clean(self, detector, tmp_path):
        """Test scanning clean file."""
        test_file = tmp_path / "clean.py"
        test_file.write_text("# This is a clean file\nprint('hello')")

        result = detector.scan_file(str(test_file))

        assert not result.has_secrets


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_text(self, detector):
        """Test scanning empty text."""
        result = detector.scan_text("")

        assert not result.has_secrets
        assert result.scanned_lines == 1  # Empty string splits to [""]

    def test_very_long_line(self, detector):
        """Test handling of very long lines."""
        long_line = "x" * 2000
        result = detector.scan_text(long_line)

        # Should not crash
        assert result.scanned_lines == 1

    def test_unicode_content(self, detector):
        """Test handling of unicode content."""
        text = "password = 'p@sswrd' # Comment with unicode: \u00e9\u00e8\u00ea"
        result = detector.scan_text(text)

        # Should not crash
        assert result.scanned_lines == 1

    def test_binary_like_content(self, detector):
        """Test handling of binary-like content."""
        text = "data = b'\\x00\\x01\\x02\\x03'"
        result = detector.scan_text(text)

        # Should not crash
        assert result.scanned_lines == 1

    def test_multiline_key(self, detector):
        """Test detection of secrets spanning multiple lines."""
        text = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0m59l2u9iDnMbrXH
-----END RSA PRIVATE KEY-----"""
        result = detector.scan_text(text)

        assert result.has_secrets


# ============================================================================
# Hash Function Tests
# ============================================================================


class TestHashFunction:
    """Tests for secret hashing."""

    def test_hash_secret(self, detector):
        """Test secret hashing for deduplication."""
        hash1 = detector.hash_secret("secret123")
        hash2 = detector.hash_secret("secret123")

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_different_secrets(self, detector):
        """Test that different secrets have different hashes."""
        hash1 = detector.hash_secret("secret1")
        hash2 = detector.hash_secret("secret2")

        assert hash1 != hash2


# ============================================================================
# Internal Method Tests (Coverage)
# ============================================================================


class TestInternalMethods:
    """Tests for internal helper methods to ensure full coverage."""

    def test_false_positive_placeholder_values(self, detector):
        """Test that placeholder values are detected as false positives - line 666."""
        # These should return True via _is_false_positive
        placeholders = [
            "your_api_key",
            "your_secret",
            "changeme",
            "xxxxxxxxxx",
            "**********",
        ]
        for placeholder in placeholders:
            assert detector._is_false_positive(placeholder, "") is True

    def test_redact_short_value(self, detector):
        """Test redaction of short values (<=8 chars) - line 673."""
        # Short values should be fully redacted
        result = detector._redact_value("secret")
        assert result == "******"
        assert len(result) == 6

        result = detector._redact_value("12345678")
        assert result == "********"

    def test_redact_long_value(self, detector):
        """Test redaction of long values (>8 chars)."""
        result = detector._redact_value("verylongsecretvalue")
        assert result == "very...alue"

    def test_calculate_entropy_empty_string(self, detector):
        """Test entropy calculation for empty string - line 734."""
        result = detector._calculate_entropy("")
        assert result == 0.0

    def test_calculate_entropy_single_char(self, detector):
        """Test entropy calculation for single repeated character."""
        result = detector._calculate_entropy("aaaaaaa")
        assert result == 0.0

    def test_calculate_entropy_high_entropy(self, detector):
        """Test entropy calculation for high entropy string."""
        result = detector._calculate_entropy("aB3$xY9!")
        assert result > 2.0  # High entropy


class TestFileScanConvenienceFunctions:
    """Tests for module-level file scan convenience functions."""

    def test_scan_file_for_secrets(self, tmp_path):
        """Test scan_file_for_secrets convenience function - line 797."""
        from src.services.secrets_detection_service import scan_file_for_secrets

        # Create a test file
        test_file = tmp_path / "test_secrets.txt"
        test_file.write_text("API_KEY=AKIAIOSFODNN7EXAMPLE")

        result = scan_file_for_secrets(str(test_file))
        assert result is not None
        assert result.scanned_lines == 1
