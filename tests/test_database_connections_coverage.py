"""
Project Aura - Database Connections Coverage Tests

Non-forked tests specifically for coverage measurement.
These tests are separate from test_database_connections.py to avoid
the forked mode that breaks coverage tracking on non-Linux systems.

Target: 85% coverage of src/services/database_connections.py
"""

import os
from unittest.mock import MagicMock, patch

# Import the module for direct function testing
import src.services.database_connections as db_module
from src.services.database_connections import (
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


class TestGetEnvironmentCoverage:
    """Coverage tests for get_environment function."""

    def test_get_environment_returns_default(self):
        """Test that get_environment returns 'dev' when ENVIRONMENT not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ENVIRONMENT is not set
            os.environ.pop("ENVIRONMENT", None)
            result = get_environment()
            assert result == "dev"

    def test_get_environment_returns_custom(self):
        """Test that get_environment returns custom value from env var."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            result = get_environment()
            assert result == "production"

    def test_get_environment_returns_qa(self):
        """Test that get_environment returns qa."""
        with patch.dict(os.environ, {"ENVIRONMENT": "qa"}):
            result = get_environment()
            assert result == "qa"


class TestServiceCreationFunctionsCoverage:
    """Coverage tests for individual service creation functions."""

    def test_get_neptune_service_body_execution(self):
        """Test get_neptune_service executes the function body."""
        # Clear endpoint to force mock mode
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            service = get_neptune_service()
            assert service is not None
            assert hasattr(service, "mode")
            assert hasattr(service, "endpoint")
            # Verify it's in mock mode
            assert service.mode.value == "mock"

    def test_get_neptune_service_with_env_param(self):
        """Test get_neptune_service with environment parameter."""
        service = get_neptune_service(environment="test")
        assert service is not None

    def test_get_opensearch_service_body_execution(self):
        """Test get_opensearch_service executes the function body."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            service = get_opensearch_service()
            assert service is not None
            assert hasattr(service, "mode")
            assert hasattr(service, "endpoint")
            assert service.mode.value == "mock"

    def test_get_opensearch_service_with_env_param(self):
        """Test get_opensearch_service with environment parameter."""
        service = get_opensearch_service(environment="staging")
        assert service is not None

    def test_get_persistence_service_body_execution(self):
        """Test get_persistence_service executes the function body."""
        service = get_persistence_service()
        assert service is not None
        assert hasattr(service, "mode")
        assert hasattr(service, "table_name")

    def test_get_persistence_service_with_env_param(self):
        """Test get_persistence_service with environment parameter."""
        service = get_persistence_service(environment="prod")
        assert service is not None

    def test_get_embedding_service_body_execution(self):
        """Test get_embedding_service executes the function body."""
        service = get_embedding_service()
        assert service is not None
        assert hasattr(service, "mode")
        assert hasattr(service, "model_id")

    def test_get_embedding_service_with_env_param(self):
        """Test get_embedding_service with environment parameter."""
        service = get_embedding_service(environment="dev")
        assert service is not None

    def test_get_llm_service_body_execution(self):
        """Test get_llm_service executes the function body."""
        service = get_llm_service()
        assert service is not None
        assert hasattr(service, "mode")

    def test_get_llm_service_with_env_param(self):
        """Test get_llm_service with environment parameter."""
        service = get_llm_service(environment="qa")
        assert service is not None


class TestBatchServiceCreationCoverage:
    """Coverage tests for batch service creation functions."""

    def test_get_database_services_body_execution(self):
        """Test get_database_services executes the function body."""
        services = get_database_services()
        assert "neptune" in services
        assert "opensearch" in services
        assert "persistence" in services
        assert len(services) == 3

    def test_get_database_services_with_env_param(self):
        """Test get_database_services with environment parameter."""
        services = get_database_services(environment="qa")
        assert len(services) == 3

    def test_get_database_services_calls_get_environment(self):
        """Test get_database_services calls get_environment when no param."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test-env"}):
            services = get_database_services()
            assert services is not None

    def test_get_all_services_body_execution(self):
        """Test get_all_services executes the function body."""
        services = get_all_services()
        assert "neptune" in services
        assert "opensearch" in services
        assert "persistence" in services
        assert "embeddings" in services
        assert "llm" in services
        assert len(services) == 5

    def test_get_all_services_with_env_param(self):
        """Test get_all_services with environment parameter."""
        services = get_all_services(environment="prod")
        assert len(services) == 5

    def test_get_all_services_calls_get_environment(self):
        """Test get_all_services calls get_environment when no param."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            services = get_all_services()
            assert services is not None


class TestCheckAwsCredentialsCoverage:
    """Coverage tests for check_aws_credentials function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_check_aws_credentials_boto3_not_available(self):
        """Test check_aws_credentials returns False when boto3 not available."""
        with patch.object(db_module, "BOTO3_AVAILABLE", False):
            result = check_aws_credentials()
            assert result is False

    def test_check_aws_credentials_success(self):
        """Test check_aws_credentials returns True on success."""
        with patch.object(db_module, "BOTO3_AVAILABLE", True):
            with patch.object(db_module, "boto3") as mock_boto3:
                mock_sts = MagicMock()
                mock_boto3.client.return_value = mock_sts
                mock_sts.get_caller_identity.return_value = {
                    "Account": "123456789012",
                    "Arn": "arn:aws:iam::123456789012:user/test",
                }
                result = check_aws_credentials()
                assert result is True
                mock_boto3.client.assert_called_once_with("sts")

    def test_check_aws_credentials_no_credentials_error(self):
        """Test check_aws_credentials returns False on NoCredentialsError."""
        from botocore.exceptions import NoCredentialsError

        with patch.object(db_module, "BOTO3_AVAILABLE", True):
            with patch.object(db_module, "boto3") as mock_boto3:
                mock_sts = MagicMock()
                mock_boto3.client.return_value = mock_sts
                mock_sts.get_caller_identity.side_effect = NoCredentialsError()
                result = check_aws_credentials()
                assert result is False

    def test_check_aws_credentials_client_error(self):
        """Test check_aws_credentials returns False on ClientError."""
        from botocore.exceptions import ClientError

        with patch.object(db_module, "BOTO3_AVAILABLE", True):
            with patch.object(db_module, "boto3") as mock_boto3:
                mock_sts = MagicMock()
                mock_boto3.client.return_value = mock_sts
                mock_sts.get_caller_identity.side_effect = ClientError(
                    {"Error": {"Code": "ExpiredToken", "Message": "Token expired"}},
                    "GetCallerIdentity",
                )
                result = check_aws_credentials()
                assert result is False

    def test_check_aws_credentials_botocore_error(self):
        """Test check_aws_credentials returns False on BotoCoreError."""
        from botocore.exceptions import BotoCoreError

        with patch.object(db_module, "BOTO3_AVAILABLE", True):
            with patch.object(db_module, "boto3") as mock_boto3:
                mock_sts = MagicMock()
                mock_boto3.client.return_value = mock_sts
                mock_sts.get_caller_identity.side_effect = BotoCoreError()
                result = check_aws_credentials()
                assert result is False

    def test_check_aws_credentials_unexpected_exception(self):
        """Test check_aws_credentials returns False on unexpected exception."""
        with patch.object(db_module, "BOTO3_AVAILABLE", True):
            with patch.object(db_module, "boto3") as mock_boto3:
                mock_sts = MagicMock()
                mock_boto3.client.return_value = mock_sts
                mock_sts.get_caller_identity.side_effect = ValueError(
                    "Unexpected error"
                )
                result = check_aws_credentials()
                assert result is False


class TestGetAwsCredentialsStatusCoverage:
    """Coverage tests for get_aws_credentials_status function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_get_aws_credentials_status_initial_call(self):
        """Test get_aws_credentials_status on initial call (no cache)."""
        with patch.object(db_module, "check_aws_credentials", return_value=True):
            # Clear to ensure no cache
            clear_credentials_cache()
            result = get_aws_credentials_status()
            assert result is True

    def test_get_aws_credentials_status_uses_cache(self):
        """Test get_aws_credentials_status uses cached value."""
        with patch.object(
            db_module, "check_aws_credentials", return_value=True
        ) as mock_check:
            clear_credentials_cache()
            # First call
            result1 = get_aws_credentials_status()
            # Second call
            result2 = get_aws_credentials_status()

            assert result1 is True
            assert result2 is True
            # Should only call check once due to caching
            assert mock_check.call_count == 1

    def test_get_aws_credentials_status_force_refresh(self):
        """Test get_aws_credentials_status with force_refresh=True."""
        with patch.object(
            db_module, "check_aws_credentials", return_value=False
        ) as mock_check:
            clear_credentials_cache()
            # First call
            get_aws_credentials_status()
            # Force refresh
            result = get_aws_credentials_status(force_refresh=True)

            assert result is False
            assert mock_check.call_count == 2


class TestClearCredentialsCacheCoverage:
    """Coverage tests for clear_credentials_cache function."""

    def test_clear_credentials_cache_execution(self):
        """Test clear_credentials_cache executes."""
        # Should not raise
        clear_credentials_cache()

    def test_clear_credentials_cache_clears_state(self):
        """Test clear_credentials_cache actually clears the cached state."""
        with patch.object(
            db_module, "check_aws_credentials", return_value=True
        ) as mock_check:
            # Populate cache
            get_aws_credentials_status()
            assert mock_check.call_count == 1

            # Clear cache
            clear_credentials_cache()

            # Should check again
            get_aws_credentials_status()
            assert mock_check.call_count == 2


class TestGetConnectionStatusCoverage:
    """Coverage tests for get_connection_status function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_get_connection_status_all_mock_mode(self):
        """Test get_connection_status with all services in mock mode."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            os.environ.pop("AWS_REGION", None)

            with patch.object(
                db_module, "get_aws_credentials_status", return_value=False
            ):
                status = get_connection_status(verify_credentials=True)

                assert status.neptune_mode == "mock"
                assert status.opensearch_mode == "mock"
                assert status.persistence_mode == "mock"
                assert status.embeddings_mode == "mock"
                assert status.llm_mode == "mock"
                assert status.all_mock is True
                assert status.all_aws is False

    def test_get_connection_status_all_aws_mode(self):
        """Test get_connection_status with all services in AWS mode."""
        with patch.dict(
            os.environ,
            {
                "NEPTUNE_ENDPOINT": "neptune.cluster.example.com",
                "OPENSEARCH_ENDPOINT": "opensearch.example.com",
                "AWS_REGION": "us-east-1",
            },
        ):
            with patch.object(
                db_module, "get_aws_credentials_status", return_value=True
            ):
                status = get_connection_status(verify_credentials=True)

                assert status.neptune_mode == "aws"
                assert status.opensearch_mode == "aws"
                assert status.persistence_mode == "aws"
                assert status.embeddings_mode == "aws"
                assert status.llm_mode == "aws"
                assert status.all_aws is True
                assert status.all_mock is False

    def test_get_connection_status_mixed_mode(self):
        """Test get_connection_status with mixed mode services."""
        with patch.dict(
            os.environ,
            {
                "NEPTUNE_ENDPOINT": "neptune.example.com",
            },
            clear=True,
        ):
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            os.environ.pop("AWS_REGION", None)

            with patch.object(
                db_module, "get_aws_credentials_status", return_value=False
            ):
                status = get_connection_status(verify_credentials=True)

                assert status.neptune_mode == "aws"
                assert status.opensearch_mode == "mock"
                assert status.persistence_mode == "mock"
                assert status.embeddings_mode == "mock"
                assert status.llm_mode == "mock"
                assert status.all_aws is False
                assert status.all_mock is False

    def test_get_connection_status_fast_path(self):
        """Test get_connection_status with verify_credentials=False."""
        with patch.dict(
            os.environ,
            {"AWS_REGION": "us-east-1"},
            clear=True,
        ):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            os.environ.pop("OPENSEARCH_ENDPOINT", None)

            status = get_connection_status(verify_credentials=False)

            assert status.neptune_mode == "mock"
            assert status.opensearch_mode == "mock"
            assert status.persistence_mode == "aws"
            # Fast path: BOTO3_AVAILABLE and AWS_REGION
            # embeddings_mode and llm_mode depend on these

    def test_get_connection_status_fast_path_no_region(self):
        """Test get_connection_status fast path without AWS_REGION."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            os.environ.pop("AWS_REGION", None)

            status = get_connection_status(verify_credentials=False)

            assert status.persistence_mode == "mock"
            assert status.embeddings_mode == "mock"
            assert status.llm_mode == "mock"


class TestPrintConnectionStatusCoverage:
    """Coverage tests for print_connection_status function."""

    def setup_method(self):
        """Clear credentials cache before each test."""
        clear_credentials_cache()

    def test_print_connection_status_all_mock(self):
        """Test print_connection_status with all mock services."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            os.environ.pop("AWS_REGION", None)

            with patch.object(
                db_module, "get_aws_credentials_status", return_value=False
            ):
                # Should not raise
                print_connection_status()

    def test_print_connection_status_all_aws(self):
        """Test print_connection_status with all AWS services."""
        with patch.dict(
            os.environ,
            {
                "NEPTUNE_ENDPOINT": "neptune.example.com",
                "OPENSEARCH_ENDPOINT": "opensearch.example.com",
                "AWS_REGION": "us-east-1",
            },
        ):
            with patch.object(
                db_module, "get_aws_credentials_status", return_value=True
            ):
                # Should not raise
                print_connection_status()

    def test_print_connection_status_mixed_mode(self):
        """Test print_connection_status with mixed mode services."""
        with patch.dict(
            os.environ,
            {"NEPTUNE_ENDPOINT": "neptune.example.com"},
            clear=True,
        ):
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            os.environ.pop("AWS_REGION", None)

            with patch.object(
                db_module, "get_aws_credentials_status", return_value=False
            ):
                # Should not raise
                print_connection_status()

    def test_print_connection_status_logs_correct_info(self):
        """Test print_connection_status logs correct information."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            os.environ.pop("OPENSEARCH_ENDPOINT", None)
            os.environ.pop("AWS_REGION", None)

            with patch.object(
                db_module, "get_aws_credentials_status", return_value=False
            ):
                with patch.object(db_module, "logger") as mock_logger:
                    print_connection_status()

                    # Should have multiple info calls
                    assert mock_logger.info.call_count >= 6


class TestConnectionStatusDataclassCoverage:
    """Coverage tests for ConnectionStatus dataclass."""

    def test_connection_status_all_fields(self):
        """Test ConnectionStatus with all fields."""
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
        assert status.persistence_mode == "aws"
        assert status.embeddings_mode == "mock"
        assert status.llm_mode == "aws"
        assert status.all_aws is False
        assert status.all_mock is False

    def test_connection_status_all_aws_true(self):
        """Test ConnectionStatus with all_aws=True."""
        status = ConnectionStatus(
            neptune_mode="aws",
            opensearch_mode="aws",
            persistence_mode="aws",
            embeddings_mode="aws",
            llm_mode="aws",
            all_aws=True,
            all_mock=False,
        )

        assert status.all_aws is True
        assert status.all_mock is False

    def test_connection_status_all_mock_true(self):
        """Test ConnectionStatus with all_mock=True."""
        status = ConnectionStatus(
            neptune_mode="mock",
            opensearch_mode="mock",
            persistence_mode="mock",
            embeddings_mode="mock",
            llm_mode="mock",
            all_aws=False,
            all_mock=True,
        )

        assert status.all_aws is False
        assert status.all_mock is True
