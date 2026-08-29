"""Tests that production-path guards are armed during the test run.

Several endpoints branch on an environment variable before calling AWS. When
that variable is not set, unit tests take the production branch and construct
real boto3 clients against whatever credential chain the developer happens to
have. That is wrong on its own terms -- a unit test should not reach for
Lambda -- and it costs money on a platform this size.

On macOS it is also the direct cause of SIGABRT crashes in
``pytest.mark.forked`` tests. Constructing a boto3 client initialises
Objective-C machinery (``+[NSCharacterSet initialize]``) on a background
thread; pytest-forked then calls ``fork()`` while that initialiser is in
progress. The ObjC runtime refuses to ignore an in-progress initialiser and
aborts, which is why ``OBJC_DISABLE_INITIALIZE_FORK_SAFETY`` -- set in
``conftest.py`` and described there as a "partial mitigation" -- cannot
suppress it.

The symptom was narrow enough to look like flakiness: only the three
``TestSecuritySettings`` tests that change ``retain_logs_for_days`` crashed,
because only a retention change reaches the Lambda call. GET-only tests in the
same file, with the same marker, passed.
"""

import asyncio
import os

import pytest

pytestmark = pytest.mark.unit


class TestTestingGuardIsArmed:
    """``TESTING`` must be set, and the guards must actually short-circuit."""

    def test_testing_env_var_is_set(self):
        assert os.environ.get("TESTING", "").lower() == "true", (
            "TESTING is not armed -- endpoints will attempt real AWS Lambda "
            "calls during tests. Set via os.environ.setdefault in "
            "tests/conftest.py."
        )

    def test_log_retention_sync_takes_the_skip_branch(self):
        """Assert the guard short-circuits, not merely that the var is set.

        Checking the variable alone would still pass if someone changed the
        guard's condition.
        """
        from src.api.settings_endpoints import _invoke_log_retention_sync

        result = asyncio.run(_invoke_log_retention_sync(180))

        assert result["status"] == "skipped"
        assert result["reason"] == "test_mode"

    def test_compliance_settings_sync_takes_the_skip_branch(self):
        """The second guarded Lambda path (settings_endpoints.py:893)."""
        from src.api.settings_endpoints import (
            ComplianceSettingsModel,
            _invoke_compliance_settings_sync,
        )

        result = asyncio.run(
            _invoke_compliance_settings_sync(ComplianceSettingsModel())
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "test_mode"


class TestGuardIsOverridable:
    """``setdefault`` semantics: a test that wants the real branch can opt in."""

    def test_env_var_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("TESTING", "false")
        assert os.environ["TESTING"] == "false"
        # Restored by monkeypatch teardown; the session default is unaffected.
