"""Override parent autouse fixtures that interfere with cryptography state.

This package's signature_verifier tests exercise PEM I/O via the
cryptography library. The ancestor conftest fixtures
``reset_lambda_environment`` and ``reset_rate_limiter_fixture`` were
observed to invalidate the identity of ``serialization.Encoding.PEM``
between consecutive tests in this directory, breaking PEM
serialisation. The model_provenance package uses neither lambdas nor
the rate limiter, so no-op overrides are safe here.
"""
import pytest


@pytest.fixture(autouse=True)
def reset_singletons():
    yield


@pytest.fixture(autouse=True)
def reset_lambda_environment():
    yield


@pytest.fixture(autouse=True)
def reset_rate_limiter_fixture():
    yield
