"""Project Aura - dev-mode fallback helpers.

Many AWS-coupled endpoints (repositories, oauth, model-router, etc.) fail
with 500 in local dev because boto3 cannot resolve a region or credentials.
The exceptions are recoverable for the purposes of populating a demo UI:
the user does not need real DynamoDB data to navigate the dashboard.

This module centralises the "is this a missing-AWS-credentials problem?"
check so individual endpoints can short-circuit to seeded mock data without
each one re-implementing the boto-error sniffing.

Activated only when ``AURA_DEV_MOCK_ON_AWS_ERROR`` is unset or truthy.
Production deployments should set this to ``false`` so genuine AWS failures
surface as 5xx instead of being papered over.
"""

from __future__ import annotations

import os
from typing import Any


def dev_mock_enabled() -> bool:
    """True when dev-mock-on-aws-error fallback should be used."""
    return os.environ.get("AURA_DEV_MOCK_ON_AWS_ERROR", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def is_aws_credential_error(exc: BaseException) -> bool:
    """Return True if ``exc`` looks like an AWS-credential or region miss.

    Avoids importing botocore at module level (it's optional in some slim
    deployment images). Walks the cause chain because boto wrapped errors
    often live a level or two deep inside the FastAPI handler's outer
    try/except.
    """
    cur: BaseException | None = exc
    while cur is not None:
        name = type(cur).__name__
        if name in (
            "NoRegionError",
            "NoCredentialsError",
            "PartialCredentialsError",
            "EndpointConnectionError",
            "ClientError",
        ):
            return True
        msg = str(cur).lower()
        if (
            "you must specify a region" in msg
            or "unable to locate credentials" in msg
            or "could not connect to the endpoint" in msg
        ):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def should_serve_mock(exc: BaseException) -> bool:
    """Combined gate: feature flag on AND error matches the fallback class."""
    return dev_mock_enabled() and is_aws_credential_error(exc)


def mock_marker() -> dict[str, Any]:
    """Standard envelope marker so frontends can tell mock from real."""
    return {"_mock": True, "_reason": "AWS unavailable in this environment"}
