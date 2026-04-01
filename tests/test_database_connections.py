"""
Project Aura - Database Connections Tests

Tests for the database connection factory module.

Target: 85% coverage of src/services/database_connections.py
"""

import os
import platform
from unittest.mock import patch

import pytest

# These tests require pytest-forked for isolation due to AWS credential cache.
# On Linux (CI), mock patches don't apply correctly without forked mode.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Set environment before importing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

import src.services.database_connections as db_connections_module
from src.services.database_connections import (
    BOTO3_AVAILABLE,
    ConnectionStatus,
    check_aws_credentials,
    clear_credentials_cache,
    get_all_services,
    get_aws_credentials_status,
    get_connection_status,
    get_database_services,
    get_embedding_service,
    get_environment,
    get_llm_service,
    get_neptune_service,
    get_opensearch_service,
    get_persistence_service,
    print_connection_status,
)


class TestGetEnvironment:
    """Tests for get_environment function."""

    def test_get_environment_default(self):
        """Test default environment is dev."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENVIRONMENT", None)
            result = get_environment()
            assert result == "dev"

    def test_get_environment_from_env_var(self):
        """Test environment from environment variable."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            result = get_environment()
            assert result == "prod"


class TestGetNeptuneService:
    """Tests for get_neptune_service function."""

    def test_get_neptune_service_mock_mode(self):
        """Test creating Neptune service in mock mode."""
        # Ensure mock mode
        env_backup = os.environ.get("NEPTUNE_ENDPOINT")
        if "NEPTUNE_ENDPOINT" in os.environ:
            del os.environ["NEPTUNE_ENDPOINT"]

        try:
            service = get_neptune_service()

            from src.services.neptune_graph_service import NeptuneMode

            # Use .value comparison for fork-safe enum identity
            assert service.mode.value == NeptuneMode.MOCK.value
        finally:
            if env_backup:
                os.environ["NEPTUNE_ENDPOINT"] = env_backup

    def test_get_neptune_service_with_environment(self):
        """Test creating Neptune service with environment parameter."""
        service = get_neptune_service(environment="qa")

        assert service is not None


class TestGetOpenSearchService:
    """Tests for get_opensearch_service function."""

    def test_get_opensearch_service_mock_mode(self):
        """Test creating OpenSearch service in mock mode."""
        # Ensure mock mode
        env_backup = os.environ.get("OPENSEARCH_ENDPOINT")
        if "OPENSEARCH_ENDPOINT" in os.environ:
            del os.environ["OPENSEARCH_ENDPOINT"]

        try:
            service = get_opensearch_service()

            from src.services.opensearch_vector_service import OpenSearchMode

            # Use .value comparison for fork-safe enum identity
            assert service.mode.value == OpenSearchMode.MOCK.value
        finally:
            if env_backup:
                os.environ["OPENSEARCH_ENDPOINT"] = env_backup

    def test_get_opensearch_service_with_environment(self):
        """Test creating OpenSearch service with environment parameter."""
        service = get_opensearch_service(environment="qa")

        assert service is not None


class TestGetPersistenceService:
    """Tests for get_persistence_service function."""

    def test_get_persistence_service_mock_mode(self):
        """Test creating persistence service in mock mode."""
        service = get_persistence_service()

        from src.services.job_persistence_service import PersistenceMode

        # Mode depends on whether AWS_REGION is set
        # Use .value comparison for fork-safe enum identity
        assert service.mode.value in [
            PersistenceMode.MOCK.value,
            PersistenceMode.AWS.value,
        ]

    def test_get_persistence_service_with_environment(self):
        """Test creating persistence service with environment parameter."""
        service = get_persistence_service(environment="qa")

        assert service is not None


class TestGetEmbeddingService:
    """Tests for get_embedding_service function."""

    def test_get_embedding_service_mock_mode(self):
        """Test creating embedding service."""
        service = get_embedding_service()

        assert service is not None
        assert hasattr(service, "mode")
        assert hasattr(service, "model_id")

    def test_get_embedding_service_with_environment(self):
        """Test creating embedding service with environment parameter."""
        service = get_embedding_service(environment="qa")

        assert service is not None


class TestGetLlmService:
    """Tests for get_llm_service function."""

    def test_get_llm_service_mock_mode(self):
        """Test creating LLM service."""
        service = get_llm_service()

        assert service is not None
        assert hasattr(service, "mode")

    def test_get_llm_service_with_environment(self):
        """Test creating LLM service with environment parameter."""
        service = get_llm_service(environment="qa")

        assert service is not None


class TestGetDatabaseServices:
    """Tests for get_database_services function."""

    def test_get_database_services_returns_all_databases(self):
        """Test that get_database_services returns all database services."""
        services = get_database_services()

        assert "neptune" in services
        assert "opensearch" in services
        assert "persistence" in services

    def test_get_database_services_with_environment(self):
        """Test get_database_services with environment parameter."""
        services = get_database_services(environment="qa")

        assert len(services) == 3

    def test_get_database_services_default_environment(self):
        """Test get_database_services uses default environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test-env"}):
            services = get_database_services()

            assert services is not None


class TestGetAllServices:
    """Tests for get_all_services function."""

    def test_get_all_services_returns_all(self):
        """Test that get_all_services returns all services."""
        services = get_all_services()

        assert "neptune" in services
        assert "opensearch" in services
        assert "persistence" in services
        assert "embeddings" in services
        assert "llm" in services

    def test_get_all_services_with_environment(self):
        """Test get_all_services with environment parameter."""
        services = get_all_services(environment="qa")

        assert len(services) == 5


class TestGetConnectionStatus:
    """Tests for get_connection_status function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_get_connection_status_mock_mode_no_verify(self):
        """Test connection status in mock mode without credential verification."""
        # Clear all endpoint env vars
        env_backup = {}
        for key in ["NEPTUNE_ENDPOINT", "OPENSEARCH_ENDPOINT", "AWS_REGION"]:
            env_backup[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        try:
            # Use verify_credentials=False for fast path
            status = get_connection_status(verify_credentials=False)

            assert status.neptune_mode == "mock"
            assert status.opensearch_mode == "mock"
            assert status.persistence_mode == "mock"
            # Without AWS_REGION set and verify_credentials=False,
            # embeddings and LLM should be mock
            assert status.embeddings_mode == "mock"
            assert status.llm_mode == "mock"
        finally:
            for key, value in env_backup.items():
                if value:
                    os.environ[key] = value

    def test_get_connection_status_with_credential_check(self):
        """Test connection status with actual credential verification."""
        # Mock the STS call to return valid credentials
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=True
        ):
            clear_credentials_cache()
            with patch.dict(
                os.environ,
                {
                    "NEPTUNE_ENDPOINT": "neptune.example.com",
                    "OPENSEARCH_ENDPOINT": "opensearch.example.com",
                    "AWS_REGION": "us-east-1",
                },
            ):
                status = get_connection_status(verify_credentials=True)

                assert status.neptune_mode == "aws"
                assert status.opensearch_mode == "aws"
                assert status.persistence_mode == "aws"
                assert status.embeddings_mode == "aws"
                assert status.llm_mode == "aws"
                assert status.all_aws is True

    def test_get_connection_status_invalid_credentials(self):
        """Test connection status when credentials are invalid."""
        # Mock the STS call to return invalid credentials
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=False
        ):
            clear_credentials_cache()
            with patch.dict(
                os.environ,
                {
                    "NEPTUNE_ENDPOINT": "neptune.example.com",
                    "OPENSEARCH_ENDPOINT": "opensearch.example.com",
                    "AWS_REGION": "us-east-1",
                },
            ):
                status = get_connection_status(verify_credentials=True)

                assert status.neptune_mode == "aws"
                assert status.opensearch_mode == "aws"
                assert status.persistence_mode == "aws"
                # Embeddings and LLM should be mock when credentials invalid
                assert status.embeddings_mode == "mock"
                assert status.llm_mode == "mock"
                assert status.all_aws is False

    def test_get_connection_status_aws_mode(self):
        """Test connection status with AWS endpoints set."""
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=True
        ):
            clear_credentials_cache()
            with patch.dict(
                os.environ,
                {
                    "NEPTUNE_ENDPOINT": "neptune.example.com",
                    "OPENSEARCH_ENDPOINT": "opensearch.example.com",
                    "AWS_REGION": "us-east-1",
                },
            ):
                status = get_connection_status()

                assert status.neptune_mode == "aws"
                assert status.opensearch_mode == "aws"
                assert status.persistence_mode == "aws"
                assert status.all_aws is True

    def test_get_connection_status_mixed_mode(self):
        """Test connection status in mixed mode."""
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=True
        ):
            clear_credentials_cache()
            with patch.dict(
                os.environ,
                {
                    "NEPTUNE_ENDPOINT": "neptune.example.com",
                    "OPENSEARCH_ENDPOINT": "",
                    "AWS_REGION": "",
                },
                clear=False,
            ):
                # Remove specific keys
                os.environ.pop("OPENSEARCH_ENDPOINT", None)
                os.environ.pop("AWS_REGION", None)

                status = get_connection_status()

                assert status.neptune_mode == "aws"
                assert status.opensearch_mode == "mock"
                assert status.all_aws is False
                assert status.all_mock is False


class TestPrintConnectionStatus:
    """Tests for print_connection_status function."""

    def test_print_connection_status_mock_mode(self):
        """Test printing connection status in mock mode."""
        # Should not raise
        print_connection_status()

    def test_print_connection_status_all_aws(self):
        """Test printing connection status when all AWS."""
        with patch.dict(
            os.environ,
            {
                "NEPTUNE_ENDPOINT": "neptune.example.com",
                "OPENSEARCH_ENDPOINT": "opensearch.example.com",
                "AWS_REGION": "us-east-1",
            },
        ):
            # Should not raise
            print_connection_status()

    def test_print_connection_status_logs_info(self):
        """Test that print_connection_status logs information."""
        # Use patch.object for fork-safe mocking
        with patch.object(db_connections_module, "logger") as mock_logger:
            print_connection_status()

            # Should have called logger.info multiple times
            assert mock_logger.info.call_count >= 6


class TestConnectionStatusDataclass:
    """Tests for ConnectionStatus dataclass."""

    def test_connection_status_creation(self):
        """Test creating ConnectionStatus dataclass."""
        status = ConnectionStatus(
            neptune_mode="aws",
            opensearch_mode="mock",
            persistence_mode="aws",
            embeddings_mode="mock",
            llm_mode="aws",
            all_aws=False,
            all_mock=False,
        )

        assert status.neptune_mode == "aws"
        assert status.opensearch_mode == "mock"
        assert status.all_aws is False
        assert status.all_mock is False


class TestTypeDefinitions:
    """Tests for type definitions."""

    def test_database_services_type(self):
        """Test DatabaseServices TypedDict structure."""
        services = get_database_services()

        # Verify it matches DatabaseServices structure
        assert "neptune" in services
        assert "opensearch" in services
        assert "persistence" in services

    def test_all_services_type(self):
        """Test AllServices TypedDict structure."""
        services = get_all_services()

        # Verify it matches AllServices structure
        assert "neptune" in services
        assert "opensearch" in services
        assert "persistence" in services
        assert "embeddings" in services
        assert "llm" in services


class TestExports:
    """Tests for module exports."""

    def test_module_exports_all(self):
        """Test that all expected items are exported."""
        from src.services import database_connections

        assert hasattr(database_connections, "get_neptune_service")
        assert hasattr(database_connections, "get_opensearch_service")
        assert hasattr(database_connections, "get_persistence_service")
        assert hasattr(database_connections, "get_embedding_service")
        assert hasattr(database_connections, "get_llm_service")
        assert hasattr(database_connections, "get_database_services")
        assert hasattr(database_connections, "get_all_services")
        assert hasattr(database_connections, "get_connection_status")
        assert hasattr(database_connections, "print_connection_status")
        assert hasattr(database_connections, "get_environment")
        assert hasattr(database_connections, "ConnectionStatus")

    def test_mode_enums_exported(self):
        """Test that mode enums are re-exported."""
        from src.services import database_connections

        assert hasattr(database_connections, "NeptuneMode")
        assert hasattr(database_connections, "OpenSearchMode")
        assert hasattr(database_connections, "PersistenceMode")
        assert hasattr(database_connections, "EmbeddingMode")
        assert hasattr(database_connections, "BedrockMode")

    def test_credential_functions_exported(self):
        """Test that credential check functions are exported."""
        from src.services import database_connections

        assert hasattr(database_connections, "check_aws_credentials")
        assert hasattr(database_connections, "get_aws_credentials_status")
        assert hasattr(database_connections, "clear_credentials_cache")
        assert hasattr(database_connections, "BOTO3_AVAILABLE")


class TestCheckAwsCredentials:
    """Tests for check_aws_credentials function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_check_aws_credentials_no_boto3(self):
        """Test credentials check when boto3 is not available."""
        with patch.object(db_connections_module, "BOTO3_AVAILABLE", False):
            result = check_aws_credentials()
            assert result is False

    def test_check_aws_credentials_valid(self):
        """Test credentials check with valid credentials."""
        mock_sts = patch.object(db_connections_module.boto3, "client").start()
        mock_client = mock_sts.return_value
        mock_client.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDAEXAMPLE",
        }

        try:
            result = check_aws_credentials()
            assert result is True
            mock_sts.assert_called_once_with("sts")
        finally:
            patch.stopall()

    def test_check_aws_credentials_no_credentials_error(self):
        """Test credentials check when no credentials are configured."""
        from botocore.exceptions import NoCredentialsError

        mock_sts = patch.object(db_connections_module.boto3, "client").start()
        mock_client = mock_sts.return_value
        mock_client.get_caller_identity.side_effect = NoCredentialsError()

        try:
            result = check_aws_credentials()
            assert result is False
        finally:
            patch.stopall()

    def test_check_aws_credentials_client_error(self):
        """Test credentials check when AWS returns client error."""
        from botocore.exceptions import ClientError

        mock_sts = patch.object(db_connections_module.boto3, "client").start()
        mock_client = mock_sts.return_value
        mock_client.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "InvalidIdentityToken", "Message": "Token expired"}},
            "GetCallerIdentity",
        )

        try:
            result = check_aws_credentials()
            assert result is False
        finally:
            patch.stopall()

    def test_check_aws_credentials_unexpected_error(self):
        """Test credentials check handles unexpected errors gracefully."""
        mock_sts = patch.object(db_connections_module.boto3, "client").start()
        mock_client = mock_sts.return_value
        mock_client.get_caller_identity.side_effect = RuntimeError("Network error")

        try:
            result = check_aws_credentials()
            assert result is False
        finally:
            patch.stopall()


class TestGetAwsCredentialsStatus:
    """Tests for get_aws_credentials_status function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_get_aws_credentials_status_caches_result(self):
        """Test that credentials status is cached."""
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=True
        ) as mock_check:
            # First call - should check
            result1 = get_aws_credentials_status()
            assert result1 is True
            assert mock_check.call_count == 1

            # Second call - should use cache
            result2 = get_aws_credentials_status()
            assert result2 is True
            assert mock_check.call_count == 1  # Not called again

    def test_get_aws_credentials_status_force_refresh(self):
        """Test that force_refresh bypasses cache."""
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=True
        ) as mock_check:
            # First call
            get_aws_credentials_status()
            assert mock_check.call_count == 1

            # Force refresh
            get_aws_credentials_status(force_refresh=True)
            assert mock_check.call_count == 2


class TestClearCredentialsCache:
    """Tests for clear_credentials_cache function."""

    def test_clear_credentials_cache(self):
        """Test clearing the credentials cache."""
        with patch.object(
            db_connections_module, "check_aws_credentials", return_value=True
        ) as mock_check:
            # Populate cache
            get_aws_credentials_status()
            assert mock_check.call_count == 1

            # Clear cache
            clear_credentials_cache()

            # Next call should check again
            get_aws_credentials_status()
            assert mock_check.call_count == 2


class TestBoto3Available:
    """Tests for BOTO3_AVAILABLE constant."""

    def test_boto3_available_is_boolean(self):
        """Test BOTO3_AVAILABLE is a boolean."""
        assert isinstance(BOTO3_AVAILABLE, bool)

    def test_boto3_available_true_in_test_env(self):
        """Test BOTO3_AVAILABLE is True in test environment (boto3 installed)."""
        # boto3 should be installed in the test environment
        assert BOTO3_AVAILABLE is True
