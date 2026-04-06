"""
Project Aura - Pytest Configuration

Provides shared fixtures for AWS service mocking using moto.
Target: 85% code coverage with enterprise-grade test infrastructure.

Module Isolation:
- Tracks sys.modules state at session start
- Cleans up any modules added during tests to prevent pollution
- Provides isolated_modules context manager for safe sys.modules mocking

Torch/Fork Safety (macOS):
- Detects tests requiring torch vs tests requiring fork isolation
- Orders tests to run forked tests BEFORE torch-loading tests
- Provides subprocess_isolated fixture as spawn-safe alternative to @pytest.mark.forked
- See: https://github.com/pytorch/pytorch/issues/70492
"""

import multiprocessing
import os
import platform
import subprocess
import sys
import tempfile
import textwrap
from contextlib import contextmanager
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Lazy import to avoid importing torch at collection time
# The src.services module imports titan services which pulls in torch
# This causes forked tests to fail on macOS due to Objective-C fork safety
_reset_rate_limiter = None


def _get_reset_rate_limiter():
    """Lazy import of reset_rate_limiter to avoid torch import at collection time."""
    global _reset_rate_limiter
    if _reset_rate_limiter is None:
        from src.services.api_rate_limiter import reset_rate_limiter

        _reset_rate_limiter = reset_rate_limiter
    return _reset_rate_limiter


# =============================================================================
# Torch/Fork Safety Configuration (macOS)
# =============================================================================

# Track if torch has been imported in this process
_torch_imported: bool = False

# Track if we are on macOS (fork-unsafe with torch)
_is_macos: bool = platform.system() == "Darwin"

# Set spawn as default multiprocessing method on macOS to avoid fork issues
if _is_macos:
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        # Already set, ignore
        pass

# Environment variable to disable Objective-C fork safety crash (partial mitigation)
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")


def _check_torch_imported() -> bool:
    """Check if torch has been imported in the current process."""
    return "torch" in sys.modules


def _is_torch_test(item: pytest.Item) -> bool:
    """Check if a test item requires torch (based on markers or module name)."""
    # Check for torch_required marker
    if item.get_closest_marker("torch_required"):
        return True

    # Check if test module/path contains torch-related names
    torch_patterns = (
        "titan",
        "neural",
        "embedding",
        "torch",
        "production_hardening",
        "memory_consolidation",
        "deep_mlp",
        "miras",
        "gpu_backend",
        "cpu_backend",
    )

    item_path = str(item.fspath) if hasattr(item, "fspath") else str(item.path)
    item_name = item.name.lower()

    for pattern in torch_patterns:
        if pattern in item_path.lower() or pattern in item_name:
            return True

    return False


def _is_forked_test(item: pytest.Item) -> bool:
    """Check if a test requires fork isolation."""
    return item.get_closest_marker("forked") is not None


# =============================================================================
# Module Isolation Infrastructure
# =============================================================================

# Track modules that existed before tests started
_initial_modules: set[str] | None = None

# Modules that should never be cleaned up (test infrastructure)
_protected_prefixes = (
    "_pytest",
    "pytest",
    "pluggy",
    "moto",
    "boto",
    # Core src modules - removing these breaks imports
    "src",
    "src.api",
    "src.services",
    "src.config",
    # Endpoint modules with routers that need to persist across tests
    "src.api.model_router_endpoints",
    "src.api.trace_endpoints",
    "src.services.model_router",
    "tests.",
    # External auth libraries - removing these breaks exception class identity
    # in auth.py's except blocks (jose.jwt.ExpiredSignatureError, httpx.HTTPError)
    "jose",
    "httpx",
    "conftest",
    "torch",  # Once loaded, cannot be safely unloaded
    "_C",  # torch internals
)


@contextmanager
def isolated_modules(*modules_to_mock: tuple[str, object]):
    """
    Context manager for isolated sys.modules mocking.

    Saves original state, applies mocks, yields, then restores.
    Use this when you need to mock modules for a specific test.

    Usage:
        with isolated_modules(('boto3', mock_boto3), ('src.config', mock_config)):
            from src.services.some_service import SomeService
            # SomeService sees the mocked modules
        # Original modules restored after context exits

    Args:
        modules_to_mock: Tuples of (module_name, mock_object)
    """
    original_modules = {}
    modules_to_remove = set()

    # Save original state and apply mocks
    for module_name, mock_obj in modules_to_mock:
        if module_name in sys.modules:
            original_modules[module_name] = sys.modules[module_name]
        else:
            modules_to_remove.add(module_name)
        sys.modules[module_name] = mock_obj

    try:
        yield
    finally:
        # Restore original state
        for module_name, _ in modules_to_mock:
            if module_name in modules_to_remove:
                sys.modules.pop(module_name, None)
            elif module_name in original_modules:
                sys.modules[module_name] = original_modules[module_name]


@pytest.fixture
def clean_module_cache():
    """
    Fixture that captures sys.modules state before test and restores after.

    Use for tests that MUST manipulate sys.modules at module level.
    This ensures any modules added during the test are removed afterward.

    Usage:
        def test_something(clean_module_cache):
            sys.modules['some_module'] = MagicMock()
            # ... test code ...
        # Module automatically cleaned up after test
    """
    original_keys = set(sys.modules.keys())
    yield
    # Remove any modules added during the test
    current_keys = set(sys.modules.keys())
    for key in current_keys - original_keys:
        if not key.startswith(_protected_prefixes):
            del sys.modules[key]


# Set AWS region for all mocked services
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "123456789012"


@pytest.fixture(autouse=True)
def reset_rate_limiter_fixture():
    """
    Reset rate limiter before each test to prevent rate limit
    state from bleeding between tests.
    """
    reset_fn = _get_reset_rate_limiter()
    reset_fn()
    yield
    reset_fn()


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio to use only asyncio backend."""
    return "asyncio"


@pytest.fixture(scope="function")
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION
    yield
    # Cleanup is automatic when fixture goes out of scope


# =============================================================================
# Lambda Test Isolation Fixtures
# =============================================================================

# Environment variables commonly used by Lambda modules
_LAMBDA_ENV_VARS = [
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "ENVIRONMENT",
    "PROJECT_NAME",
    "USE_MOCK",
    "SNS_TOPIC_ARN",
    "S3_BUCKET",
    "ENABLE_K8S_UPDATE",
    "SEVERITY_THRESHOLD",
    "MAX_CVE_AGE_DAYS",
    "NVD_API_KEY",
    "GITHUB_TOKEN",
    "ENABLE_LLM",
    "AURA_ENV",
]


@pytest.fixture(autouse=True)
def reset_lambda_environment():
    """
    Reset environment variables commonly used by Lambda modules.

    This autouse fixture ensures each test starts with a clean environment,
    preventing test pollution from environment variable modifications.

    Also clears the AWS client cache (Issue #466) to ensure each test gets
    fresh boto3 clients configured with the test's environment variables.

    Runs before EVERY test and restores original values after.
    """
    import asyncio

    # Store original values
    original_env = {key: os.environ.get(key) for key in _LAMBDA_ENV_VARS}

    # Clear AWS client caches before each test (Issue #466)
    # This ensures tests get fresh clients with current environment
    try:
        import importlib

        aws_clients = importlib.import_module("src.lambda.aws_clients")
        aws_clients.clear_all_caches()
    except (ImportError, ModuleNotFoundError):
        pass  # aws_clients not yet created or not applicable

    # Ensure clean event loop state for Lambda tests that use asyncio.run()
    # Some tests may leave event loops in a closed/corrupted state
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None or loop.is_closed():
        asyncio.set_event_loop(asyncio.new_event_loop())

    yield

    # Clear AWS client caches after test (Issue #466)
    try:
        import importlib

        aws_clients = importlib.import_module("src.lambda.aws_clients")
        aws_clients.clear_all_caches()
    except (ImportError, ModuleNotFoundError):
        pass

    # Restore original environment after test
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def reimport_lambda_module():
    """
    Fixture that provides fresh Lambda module import.

    Use this for tests that need the Lambda module to see
    current environment variables during import (since Lambda
    modules often create boto3 clients at module load time).

    Usage:
        def test_something(reimport_lambda_module):
            os.environ["USE_MOCK"] = "true"
            dns_module = reimport_lambda_module("src.lambda.dns_blocklist_updater")
            # dns_module has fresh boto3 clients with current env vars
    """
    import importlib

    def _reimport(module_name: str):
        # Remove from cache
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Also remove any submodules that might cache the parent
        to_remove = [k for k in sys.modules if k.startswith(module_name + ".")]
        for k in to_remove:
            del sys.modules[k]

        # Fresh import
        return importlib.import_module(module_name)

    return _reimport


@pytest.fixture(scope="function")
def mock_aws_services(aws_credentials):
    """
    Comprehensive AWS service mocking using moto.

    Provides mocked versions of all AWS services used by Project Aura.
    Each test gets a fresh, isolated AWS environment.

    Usage:
        def test_something(mock_aws_services):
            dynamodb = mock_aws_services["dynamodb"]
            s3 = mock_aws_services["s3"]
            # ... use clients as if they were real AWS
    """
    with mock_aws():
        services = {
            "dynamodb": boto3.client("dynamodb", region_name=AWS_REGION),
            "dynamodb_resource": boto3.resource("dynamodb", region_name=AWS_REGION),
            "s3": boto3.client("s3", region_name=AWS_REGION),
            "lambda": boto3.client("lambda", region_name=AWS_REGION),
            "sqs": boto3.client("sqs", region_name=AWS_REGION),
            "sns": boto3.client("sns", region_name=AWS_REGION),
            "cloudwatch": boto3.client("cloudwatch", region_name=AWS_REGION),
            "logs": boto3.client("logs", region_name=AWS_REGION),
            "secretsmanager": boto3.client("secretsmanager", region_name=AWS_REGION),
            "ssm": boto3.client("ssm", region_name=AWS_REGION),
            "ecs": boto3.client("ecs", region_name=AWS_REGION),
            "ec2": boto3.client("ec2", region_name=AWS_REGION),
            "events": boto3.client("events", region_name=AWS_REGION),
            "stepfunctions": boto3.client("stepfunctions", region_name=AWS_REGION),
            "sts": boto3.client("sts", region_name=AWS_REGION),
        }
        yield services


# =============================================================================
# DynamoDB Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_dynamodb(aws_credentials):
    """Isolated DynamoDB mock for table operations."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=AWS_REGION)
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        yield {"client": client, "resource": resource}


@pytest.fixture(scope="function")
def mock_anomalies_table(mock_dynamodb):
    """Pre-configured aura-anomalies table for testing."""
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    # Create table matching production schema
    client.create_table(
        TableName="aura-anomalies-dev",
        KeySchema=[
            {"AttributeName": "anomaly_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "anomaly_id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "severity", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "status-index",
                "KeySchema": [{"AttributeName": "status", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "severity-index",
                "KeySchema": [{"AttributeName": "severity", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-anomalies-dev")
    yield {"client": client, "resource": resource, "table": table}


@pytest.fixture(scope="function")
def mock_approvals_table(mock_dynamodb):
    """Pre-configured aura-approvals table for HITL testing."""
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    client.create_table(
        TableName="aura-approvals-dev",
        KeySchema=[
            {"AttributeName": "approval_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "approval_id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "status-created_at-index",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-approvals-dev")
    yield {"client": client, "resource": resource, "table": table}


@pytest.fixture(scope="function")
def mock_settings_table(mock_dynamodb):
    """Pre-configured aura-platform-settings table."""
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    client.create_table(
        TableName="aura-platform-settings-dev",
        KeySchema=[
            {"AttributeName": "setting_key", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "setting_key", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-platform-settings-dev")
    yield {"client": client, "resource": resource, "table": table}


# =============================================================================
# S3 Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_s3(aws_credentials):
    """Isolated S3 mock for bucket operations."""
    with mock_aws():
        client = boto3.client("s3", region_name=AWS_REGION)
        yield client


@pytest.fixture(scope="function")
def mock_blocklist_bucket(mock_s3):
    """Pre-configured S3 bucket for DNS blocklist storage."""
    mock_s3.create_bucket(Bucket="aura-dns-blocklist-dev")
    yield {"client": mock_s3, "bucket": "aura-dns-blocklist-dev"}


# =============================================================================
# Secrets Manager Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_secrets(aws_credentials):
    """Isolated Secrets Manager mock."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        yield client


@pytest.fixture(scope="function")
def mock_aura_secrets(mock_secrets):
    """Pre-configured secrets matching production."""
    secrets = {
        "aura/dev/neptune": '{"endpoint": "neptune.aura.local", "port": 8182}',
        "aura/dev/opensearch": '{"endpoint": "opensearch.aura.local", "port": 9200}',
        "aura/dev/bedrock": '{"model_id": "anthropic.claude-3-5-sonnet-20241022-v1:0"}',
        "aura/dev/jwt-secret": '{"secret": "test-jwt-secret-key"}',
    }

    for name, value in secrets.items():
        mock_secrets.create_secret(Name=name, SecretString=value)

    yield {"client": mock_secrets, "secrets": secrets}


# =============================================================================
# SSM Parameter Store Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_ssm(aws_credentials):
    """Isolated SSM Parameter Store mock."""
    with mock_aws():
        client = boto3.client("ssm", region_name=AWS_REGION)
        yield client


@pytest.fixture(scope="function")
def mock_aura_parameters(mock_ssm):
    """Pre-configured SSM parameters matching production."""
    parameters = {
        "/aura/global/codeconnections-arn": "arn:aws:codeconnections:us-east-1:123456789012:connection/test",
        "/aura/dev/admin-role-arn": "arn:aws:iam::123456789012:role/AuraAdminRole",
        "/aura/dev/alert-email": "test@example.com",
        "/aura/global/github-app-id": "12345",
        "/aura/global/github-app-private-key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        "/aura/global/github-app-installation-id": "67890",
    }

    for name, value in parameters.items():
        mock_ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)

    yield {"client": mock_ssm, "parameters": parameters}


# =============================================================================
# CloudWatch & EventBridge Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_cloudwatch(aws_credentials):
    """Isolated CloudWatch mock for metrics and alarms."""
    with mock_aws():
        client = boto3.client("cloudwatch", region_name=AWS_REGION)
        logs_client = boto3.client("logs", region_name=AWS_REGION)
        yield {"cloudwatch": client, "logs": logs_client}


@pytest.fixture(scope="function")
def mock_eventbridge(aws_credentials):
    """Isolated EventBridge mock for event routing."""
    with mock_aws():
        client = boto3.client("events", region_name=AWS_REGION)
        # Create default event bus
        client.create_event_bus(Name="aura-anomaly-events-dev")
        yield client


# =============================================================================
# SNS & SQS Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_sns(aws_credentials):
    """Isolated SNS mock for notifications."""
    with mock_aws():
        client = boto3.client("sns", region_name=AWS_REGION)
        yield client


@pytest.fixture(scope="function")
def mock_notification_topics(mock_sns):
    """Pre-configured SNS topics for alerting."""
    topics = {}
    topic_names = [
        "aura-critical-anomalies-dev",
        "aura-security-alerts-dev",
        "aura-hitl-notifications-dev",
    ]

    for name in topic_names:
        response = mock_sns.create_topic(Name=name)
        topics[name] = response["TopicArn"]

    yield {"client": mock_sns, "topics": topics}


@pytest.fixture(scope="function")
def mock_sqs(aws_credentials):
    """Isolated SQS mock for message queuing."""
    with mock_aws():
        client = boto3.client("sqs", region_name=AWS_REGION)
        yield client


# =============================================================================
# ECS & EC2 Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_ecs(aws_credentials):
    """Isolated ECS mock for container orchestration."""
    with mock_aws():
        client = boto3.client("ecs", region_name=AWS_REGION)
        # Create default cluster
        client.create_cluster(clusterName="aura-sandbox-cluster-dev")
        yield client


@pytest.fixture(scope="function")
def mock_ec2(aws_credentials):
    """Isolated EC2 mock for VPC and networking."""
    with mock_aws():
        client = boto3.client("ec2", region_name=AWS_REGION)
        yield client


@pytest.fixture(scope="function")
def mock_vpc_infrastructure(mock_ec2):
    """Pre-configured VPC matching production topology."""
    # Create VPC
    vpc = mock_ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]

    # Create subnets
    private_subnet_1 = mock_ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.0.3.0/24", AvailabilityZone="us-east-1a"
    )
    private_subnet_2 = mock_ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.0.4.0/24", AvailabilityZone="us-east-1b"
    )

    # Create security group
    sg = mock_ec2.create_security_group(
        GroupName="aura-sandbox-sg", Description="Sandbox security group", VpcId=vpc_id
    )

    yield {
        "client": mock_ec2,
        "vpc_id": vpc_id,
        "subnet_ids": [
            private_subnet_1["Subnet"]["SubnetId"],
            private_subnet_2["Subnet"]["SubnetId"],
        ],
        "security_group_id": sg["GroupId"],
    }


# =============================================================================
# Step Functions Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_stepfunctions(aws_credentials):
    """Isolated Step Functions mock for workflow orchestration."""
    with mock_aws():
        client = boto3.client("stepfunctions", region_name=AWS_REGION)
        yield client


# =============================================================================
# Lambda Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def mock_lambda(aws_credentials):
    """Isolated Lambda mock for serverless functions."""
    with mock_aws():
        client = boto3.client("lambda", region_name=AWS_REGION)
        yield client


# =============================================================================
# Integration Test Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers and capture initial sys.modules state."""
    global _initial_modules
    _initial_modules = set(sys.modules.keys())

    config.addinivalue_line(
        "markers",
        "aws_integration: tests that require mocked AWS services",
    )
    config.addinivalue_line(
        "markers",
        "slow: tests that take more than 1 second",
    )
    config.addinivalue_line(
        "markers",
        "forked: tests that should run in subprocess for isolation (deprecated on macOS)",
    )
    config.addinivalue_line(
        "markers",
        "torch_required: tests that import PyTorch (scheduled to run last)",
    )
    config.addinivalue_line(
        "markers",
        "subprocess_isolated: tests requiring fresh subprocess isolation (spawn-safe)",
    )


# =============================================================================
# Torch Import Guard During Collection
# =============================================================================
# Files known to import torch at module level (should be refactored to use lazy imports)
# This is a safety net - if these files accidentally import torch during collection,
# we can detect and warn or skip them.

TORCH_MODULE_LEVEL_IMPORT_FILES: set[str] = set()  # Add paths here if issues recur


def pytest_ignore_collect(collection_path, config):
    """
    Optionally ignore test files that import torch at module level.

    This is a fallback protection mechanism. If a file is added to
    TORCH_MODULE_LEVEL_IMPORT_FILES, it will be excluded from normal
    collection and only collected when running with -m torch_required.

    Currently this set is empty because test_production_hardening.py
    has been refactored to use lazy imports.
    """
    if not TORCH_MODULE_LEVEL_IMPORT_FILES:
        return None  # No files to skip

    path_str = str(collection_path)

    # Check if we're explicitly running torch tests via marker
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "torch_required" in markexpr:
        return None  # Collect all files when running torch tests

    # Skip files that import torch at module level
    for torch_file in TORCH_MODULE_LEVEL_IMPORT_FILES:
        if path_str.endswith(torch_file):
            return True  # Skip this file

    return None  # Collect normally


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
):
    """
    Reorder tests to prevent torch/fork conflicts on macOS.

    Test ordering strategy:
    1. Run forked tests FIRST (before any torch imports)
    2. Run regular tests in the middle
    3. Run torch-requiring tests LAST

    This prevents the scenario where torch is imported, then a forked test
    tries to fork the process and crashes due to Objective-C runtime safety.
    """
    if not _is_macos:
        # Only reorder on macOS where fork + torch is problematic
        return

    forked_tests = []
    regular_tests = []
    torch_tests = []

    for item in items:
        if _is_forked_test(item):
            forked_tests.append(item)
        elif _is_torch_test(item):
            torch_tests.append(item)
        else:
            regular_tests.append(item)

    # Log ordering info for debugging
    if forked_tests or torch_tests:
        print("\n[conftest] Test ordering for macOS fork safety:")
        print(f"  - Forked tests (run first): {len(forked_tests)}")
        print(f"  - Regular tests: {len(regular_tests)}")
        print(f"  - Torch tests (run last): {len(torch_tests)}")

    # Clear and rebuild the items list in the correct order
    items[:] = forked_tests + regular_tests + torch_tests


def _sync_setupstate_for_forked_test(item: pytest.Item, nextitem: pytest.Item | None):
    """
    Synchronize the parent process's SetupState after a forked test runs.

    When pytest-forked handles a test, it returns True from pytest_runtest_protocol,
    which tells pytest to skip the normal protocol (including setup/teardown calls).
    This leaves the parent's SetupState out of sync because:
    1. setup() is never called (happens in child process)
    2. teardown_exact() is never called (pytest-forked returns True, skipping normal protocol)

    This function manually syncs the SetupState to prevent the "previous item was not
    torn down properly" assertion error when the next non-forked test runs.

    See: https://github.com/pytest-dev/pytest-forked/issues/67
    """
    session = item.session
    if not hasattr(session, "_setupstate"):
        return

    setupstate = session._setupstate

    # Get the collector chain for this item
    needed_collectors = item.listchain()

    # First, ensure any collectors in the stack that aren't in the needed chain
    # are properly removed. This happens when the forked test is in a different
    # module than the previous test.
    stale_collectors = [col for col in setupstate.stack if col not in needed_collectors]
    for col in stale_collectors:
        # Run teardown for stale collectors
        finalizers, _ = setupstate.stack.pop(col, ([], None))
        for finalizer in reversed(finalizers):
            try:
                finalizer()
            except Exception:
                pass  # Ignore teardown errors for forked test sync

    # Now add any missing collectors to the stack (simulating setup)
    for col in needed_collectors:
        if col not in setupstate.stack:
            setupstate.stack[col] = ([col.teardown], None)

    # Finally, prepare for the next item by tearing down collectors not needed
    if nextitem is not None:
        next_collectors = set(nextitem.listchain())
        to_teardown = [col for col in setupstate.stack if col not in next_collectors]
        for col in reversed(to_teardown):
            finalizers, _ = setupstate.stack.pop(col, ([], None))
            for finalizer in reversed(finalizers):
                try:
                    finalizer()
                except Exception:
                    pass


def _refresh_src_modules_for_fork():
    """
    Refresh src.* modules to ensure fresh state in forked subprocess.

    When pytest-forked creates a subprocess, the child inherits the parent's
    sys.modules with already-imported modules. This can cause issues where:
    1. lru_cache decorators have stale cached values
    2. Module-level singletons or state are copies from the parent
    3. Class identity differs between parent-imported and child-imported modules

    This function clears and reimports key modules to ensure fresh state.
    """
    import importlib

    # Modules that have known state issues in forked processes
    # NOTE: FastAPI router modules are NOT reloaded here because reloading
    # breaks FastAPI's include_router mechanism (routes don't get added properly).
    # Router-based endpoint tests should handle their own isolation.
    modules_to_refresh = [
        # Auth module has lru_cache that needs clearing
        "src.api.auth",
        # Rate limiter has global state
        "src.services.api_rate_limiter",
        # Config modules may cache values
        "src.config",
    ]

    for mod_name in modules_to_refresh:
        if mod_name in sys.modules:
            try:
                # Reload to get fresh module state
                importlib.reload(sys.modules[mod_name])
            except Exception:
                # If reload fails, remove and let it be reimported on demand
                sys.modules.pop(mod_name, None)

    # Also clear auth caches specifically (in case reload didn't reset them)
    try:
        from src.api.auth import clear_auth_caches

        clear_auth_caches()
    except Exception:
        pass

    # Reset rate limiter state
    try:
        from src.services.api_rate_limiter import reset_rate_limiter

        reset_rate_limiter()
    except Exception:
        pass


# Track the last forked test item for SetupState synchronization
_last_forked_item: pytest.Item | None = None


@pytest.hookimpl(trylast=True, hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    """
    Synchronize SetupState after pytest-forked handles a test.

    This hook runs AFTER pytest-forked's hook (trylast=True) and uses hookwrapper
    to execute after the forked test completes. It syncs the parent process's
    SetupState to prevent "previous item was not torn down properly" errors.

    The issue occurs because pytest-forked's pytest_runtest_protocol returns True,
    which tells pytest to skip the normal protocol including teardown. This leaves
    the SetupState out of sync when transitioning between modules.
    """
    global _last_forked_item

    is_forked = _is_forked_test(item)

    # Let pytest-forked (or normal protocol) handle the test
    result = yield

    # After the test completes, sync SetupState if this was a forked test
    if is_forked:
        _sync_setupstate_for_forked_test(item, nextitem)
        _last_forked_item = item


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item):
    """
    Check for fork safety issues before running tests.

    If a forked test is about to run but torch has already been imported,
    issue a warning (the test will likely crash on macOS).

    For forked tests, also refresh key modules to ensure fresh state.
    """
    global _torch_imported

    if _is_macos and _is_forked_test(item) and _check_torch_imported():
        pytest.skip(
            "Skipping forked test: torch has been imported in this process. "
            "On macOS, forking after torch initialization causes crashes. "
            "Consider using @pytest.mark.subprocess_isolated instead, or "
            "run this test in isolation with: pytest path/to/test.py::test_name"
        )

    # Refresh module state for forked tests to prevent stale references
    if _is_forked_test(item):
        _refresh_src_modules_for_fork()

    yield

    # Track if torch was imported during this test
    if _check_torch_imported():
        _torch_imported = True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """
    Clean up sys.modules pollution after each test.

    This hook runs after every test teardown and removes any modules
    that were added during the test (excluding protected infrastructure modules).
    This prevents test pollution where one test's mocks affect subsequent tests.

    NOTE: Cannot clean up torch - once loaded, the Objective-C runtime is tainted.
    """
    yield

    if _initial_modules is not None:
        # Remove any modules added during tests
        current_modules = set(sys.modules.keys())
        added_modules = current_modules - _initial_modules

        for mod in added_modules:
            # Keep pytest and test infrastructure modules
            if not mod.startswith(_protected_prefixes):
                sys.modules.pop(mod, None)


# =============================================================================
# Subprocess Isolation Fixture (Spawn-Safe Alternative to @pytest.mark.forked)
# =============================================================================


def run_test_in_subprocess(
    test_file: str,
    test_name: str,
    timeout: int = 60,
    env_vars: dict[str, str] | None = None,
) -> tuple[bool, str, str]:
    """
    Run a single test in a fresh subprocess using spawn (not fork).

    This is the spawn-safe alternative to pytest-forked. It creates a completely
    new Python process that does not inherit any state from the parent.

    Args:
        test_file: Path to the test file
        test_name: Full test name (e.g., "TestClass::test_method")
        timeout: Maximum seconds to wait for the test
        env_vars: Additional environment variables to set

    Returns:
        Tuple of (passed: bool, stdout: str, stderr: str)
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())
    if env_vars:
        env.update(env_vars)

    # Construct the pytest command to run just this one test
    test_path = f"{test_file}::{test_name}" if test_name else test_file
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        "-v",
        "--no-cov",  # Disable coverage in subprocess (collect in main process)
        "-x",  # Stop on first failure
        "--tb=short",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(Path.cwd()),
        )
        passed = result.returncode == 0
        return passed, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Test timed out after {timeout} seconds"
    except Exception as e:
        return False, "", f"Failed to run subprocess: {e}"


@pytest.fixture
def subprocess_isolated():
    """
    Fixture that provides a helper to run code in an isolated subprocess.

    Use this when you need true process isolation without fork.
    This is safe to use even after torch has been imported.

    Usage:
        def test_something(subprocess_isolated):
            result = subprocess_isolated('''
                from src.services.some_service import SomeService
                service = SomeService()
                assert service.do_thing() == expected
            ''')
            assert result.success

    Returns:
        A callable that takes Python code and runs it in a subprocess.
    """

    class SubprocessResult:
        def __init__(self, success: bool, stdout: str, stderr: str, returncode: int):
            self.success = success
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

        def __bool__(self):
            return self.success

    def run_isolated(
        code: str, timeout: int = 30, env_vars: dict[str, str] | None = None
    ) -> SubprocessResult:
        """Run Python code in an isolated subprocess."""
        # Dedent the code to allow inline multi-line strings
        code = textwrap.dedent(code).strip()

        # Create a temporary file with the test code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Add imports and path setup
            f.write(
                f"""
import sys
sys.path.insert(0, {str(Path.cwd())!r})

{code}
"""
            )
            temp_file = f.name

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd())
            if env_vars:
                env.update(env_vars)

            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(Path.cwd()),
            )

            return SubprocessResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return SubprocessResult(
                success=False,
                stdout="",
                stderr=f"Code execution timed out after {timeout} seconds",
                returncode=-1,
            )
        except Exception as e:
            return SubprocessResult(
                success=False,
                stdout="",
                stderr=str(e),
                returncode=-1,
            )
        finally:
            # Clean up temp file
            try:
                Path(temp_file).unlink()
            except OSError:
                pass

    return run_isolated


@pytest.fixture
def require_no_torch():
    """
    Fixture that skips the test if torch has already been imported.

    Use this to protect tests that must run before torch is loaded.

    Usage:
        def test_something(require_no_torch):
            # This test will be skipped if torch was imported earlier
            ...
    """
    if _check_torch_imported():
        pytest.skip(
            "This test requires that torch has not been imported. "
            "Run this test in isolation or before torch-using tests."
        )
    yield


@pytest.fixture
def lazy_torch():
    """
    Fixture that provides lazy torch import to delay loading.

    Use this to defer torch import until the test actually needs it,
    helping with test ordering on macOS.

    Usage:
        def test_something(lazy_torch):
            torch = lazy_torch()  # Import happens here
            tensor = torch.zeros(10)
    """

    def get_torch():
        import torch

        return torch

    return get_torch


# =============================================================================
# Semantic Guardrails Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def reset_guardrails_singletons():
    """
    Reset all semantic guardrails singletons before and after each test.

    This prevents test pollution from shared state in:
    - SemanticGuardrailsEngine singleton
    - DecisionEngine singleton
    - MultiTurnTracker singleton (and its mock session storage)
    - GuardrailsMetricsPublisher singleton

    Usage:
        def test_something(reset_guardrails_singletons):
            from src.services.semantic_guardrails.engine import assess_threat
            assessment = assess_threat("test input")
            # Singletons are fresh for this test
    """
    # Import lazily to avoid import-time side effects
    from src.services.semantic_guardrails.decision_engine import reset_decision_engine
    from src.services.semantic_guardrails.engine import reset_guardrails_engine
    from src.services.semantic_guardrails.metrics import reset_metrics_publisher
    from src.services.semantic_guardrails.multi_turn_tracker import (
        reset_multi_turn_tracker,
    )

    # Reset before test
    reset_guardrails_engine()
    reset_decision_engine()
    reset_multi_turn_tracker()
    reset_metrics_publisher()

    yield

    # Reset after test (cleanup)
    reset_guardrails_engine()
    reset_decision_engine()
    reset_multi_turn_tracker()
    reset_metrics_publisher()


@pytest.fixture(scope="function")
def guardrails_engine_isolated(reset_guardrails_singletons):
    """
    Provide an isolated SemanticGuardrailsEngine instance.

    The engine uses mock mode for DynamoDB (in-memory session storage)
    and mock mode for CloudWatch metrics (no real API calls).

    Usage:
        def test_threat_detection(guardrails_engine_isolated):
            engine = guardrails_engine_isolated
            assessment = engine.assess_threat("ignore previous instructions")
            assert assessment.threat_level >= ThreatLevel.MEDIUM
    """
    from src.services.semantic_guardrails.engine import SemanticGuardrailsEngine

    engine = SemanticGuardrailsEngine()
    yield engine
    engine.shutdown()


@pytest.fixture(scope="function")
def guardrails_engine_with_mocked_aws(
    reset_guardrails_singletons, mock_cloudwatch, mock_dynamodb
):
    """
    Provide a SemanticGuardrailsEngine with moto-mocked AWS services.

    Uses mock_cloudwatch and mock_dynamodb fixtures for full AWS mocking.
    Useful for testing CloudWatch metrics publishing and DynamoDB session storage.

    Usage:
        def test_metrics_publish(guardrails_engine_with_mocked_aws, mock_cloudwatch):
            engine = guardrails_engine_with_mocked_aws
            engine.assess_threat("test input")
            # Verify metrics were published to mocked CloudWatch
    """
    from src.services.semantic_guardrails.config import (
        GuardrailsConfig,
        MetricsConfig,
        SessionTrackingConfig,
    )
    from src.services.semantic_guardrails.engine import SemanticGuardrailsEngine
    from src.services.semantic_guardrails.metrics import GuardrailsMetricsPublisher
    from src.services.semantic_guardrails.multi_turn_tracker import MultiTurnTracker

    # Create mocked components
    metrics_config = MetricsConfig(enabled=True, buffer_size=10)
    metrics_publisher = GuardrailsMetricsPublisher(
        cloudwatch_client=mock_cloudwatch["cloudwatch"],
        config=metrics_config,
    )

    session_config = SessionTrackingConfig(table_name="aura-guardrails-sessions-dev")
    session_tracker = MultiTurnTracker(
        dynamodb_client=mock_dynamodb["client"],
        config=session_config,
    )

    # Create engine with mocked components
    config = GuardrailsConfig()
    engine = SemanticGuardrailsEngine(
        config=config,
        session_tracker=session_tracker,
        metrics_publisher=metrics_publisher,
    )

    yield engine
    engine.shutdown()


@pytest.fixture(scope="function")
def mock_guardrails_session_table(mock_dynamodb):
    """
    Pre-configured DynamoDB table for guardrails session tracking.

    Creates the aura-guardrails-sessions table with the correct schema.

    Usage:
        def test_session_persistence(mock_guardrails_session_table):
            client = mock_guardrails_session_table["client"]
            # Use the mocked table
    """
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    client.create_table(
        TableName="aura-guardrails-sessions-dev",
        KeySchema=[
            {"AttributeName": "session_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "session_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-guardrails-sessions-dev")
    yield {"client": client, "resource": resource, "table": table}
