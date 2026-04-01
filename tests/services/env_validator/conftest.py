"""Pytest configuration for Environment Validator tests (ADR-062).

Sets up the test environment with parameterized AWS account IDs.
Uses generic placeholder values to avoid hardcoding real account IDs.
"""

import pytest

from src.services.env_validator.config import clear_registry_cache

# Generic placeholder account IDs for testing
# These are clearly fake values - not real AWS accounts
TEST_DEV_ACCOUNT_ID = "111111111111"
TEST_QA_ACCOUNT_ID = "222222222222"
TEST_PROD_ACCOUNT_ID = "333333333333"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment with parameterized account IDs.

    The env_validator config uses AWS_ACCOUNT_ID from the environment.
    Tests use generic placeholder IDs to avoid hardcoding real accounts.
    """
    # Set the account ID to match test fixtures (QA environment for most tests)
    monkeypatch.setenv("AWS_ACCOUNT_ID", TEST_QA_ACCOUNT_ID)
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    # Clear the registry cache so it picks up the new environment values
    clear_registry_cache()

    yield

    # Clear cache after test to ensure clean state
    clear_registry_cache()
