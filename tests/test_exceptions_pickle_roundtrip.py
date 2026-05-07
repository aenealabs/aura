"""Verifies the project exception hierarchy survives pickle / copy round-trips.

This test exists as the empirical justification for the project-wide
B042 ignore in `.pre-commit-config.yaml`. flake8-bugbear B042 warns
that exception subclasses which don't pass all kwargs to
``super().__init__()`` may lose state across pickle/copy boundaries.

In CPython this concern doesn't manifest because ``BaseException.__reduce__``
returns ``(cls, args, __dict__)`` — instance attributes are preserved
via the ``__dict__`` slot regardless of what the constructor passes to
super. These tests prove that for every Aura exception subclass.

If a future change overrides ``__reduce__`` / ``__getstate__`` /
``__setstate__`` on any subclass, these tests will fail and the B042
ignore should be revisited.
"""

from __future__ import annotations

import copy
import pickle

import pytest

from src.exceptions import (
    AgentError,
    ApprovalError,
    AuraError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    DatabaseError,
    InjectionError,
    IntegrationError,
    LLMError,
    OrchestrationError,
    SandboxError,
    SchemaValidationError,
    SecurityError,
    ServiceError,
    ToolExecutionError,
    ValidationError,
    WorkflowError,
)


# Each tuple: (constructor, kwargs, attrs to verify)
EXCEPTION_FIXTURES = [
    (AuraError, {"message": "m", "error_code": "E", "context": {"k": "v"}},
     ["message", "error_code", "context"]),
    (ValidationError, {"message": "m", "field": "name", "context": {"v": 1}},
     ["message", "error_code", "context", "field"]),
    (SchemaValidationError, {"message": "m", "schema_errors": [{"e": 1}]},
     ["message", "error_code", "context"]),
    (ServiceError, {"message": "m", "service_name": "neptune"},
     ["message", "error_code", "context", "service_name"]),
    (DatabaseError, {"message": "m", "database": "neptune", "operation": "g.V()"},
     ["message", "error_code", "operation"]),
    (LLMError, {"message": "m", "model_id": "claude-3-5-sonnet"},
     ["message", "error_code", "model_id"]),
    (IntegrationError, {"message": "m", "integration": "github", "status_code": 503},
     ["message", "error_code", "status_code"]),
    (SecurityError, {"message": "m", "error_code": "X"},
     ["message", "error_code"]),
    (AuthenticationError, {"message": "m"},
     ["message", "error_code"]),
    (AuthorizationError, {"message": "m", "required_permission": "admin:write"},
     ["message", "error_code", "required_permission"]),
    (InjectionError, {"message": "m", "injection_type": "prompt"},
     ["message", "error_code", "injection_type"]),
    (ConfigurationError, {"message": "m", "config_key": "DB_URL"},
     ["message", "error_code", "config_key"]),
    (AgentError, {"message": "m", "agent_name": "Coder"},
     ["message", "error_code", "agent_name"]),
    (ToolExecutionError, {"message": "m", "tool_name": "search", "agent_name": "Coder"},
     ["message", "error_code", "tool_name"]),
    (OrchestrationError, {"message": "m", "workflow_id": "wf-1"},
     ["message", "error_code", "workflow_id"]),
    (WorkflowError, {"message": "m", "workflow_name": "patch_review"},
     ["message", "error_code", "workflow_name"]),
    (ApprovalError, {"message": "m", "approval_id": "ap-1"},
     ["message", "error_code", "approval_id"]),
    (SandboxError, {"message": "m", "sandbox_id": "sb-1"},
     ["message", "error_code", "sandbox_id"]),
]


@pytest.mark.parametrize("cls,kwargs,attrs", EXCEPTION_FIXTURES)
def test_pickle_roundtrip_preserves_attributes(cls, kwargs, attrs):
    original = cls(**kwargs)
    restored = pickle.loads(pickle.dumps(original))

    assert type(restored) is cls
    for attr in attrs:
        assert getattr(restored, attr) == getattr(original, attr), (
            f"{cls.__name__}.{attr} not preserved through pickle "
            f"(got {getattr(restored, attr)!r}, "
            f"expected {getattr(original, attr)!r})"
        )


@pytest.mark.parametrize("cls,kwargs,attrs", EXCEPTION_FIXTURES)
def test_copy_roundtrip_preserves_attributes(cls, kwargs, attrs):
    original = cls(**kwargs)
    cloned = copy.copy(original)
    deep = copy.deepcopy(original)

    for attr in attrs:
        assert getattr(cloned, attr) == getattr(original, attr)
        assert getattr(deep, attr) == getattr(original, attr)


@pytest.mark.parametrize("cls,kwargs,_attrs", EXCEPTION_FIXTURES)
def test_raise_then_pickle_preserves_traceback_safe_state(cls, kwargs, _attrs):
    """After raising and catching, the exception still pickles cleanly."""
    try:
        raise cls(**kwargs)
    except cls as caught:
        # __traceback__ is not picklable; pickle drops it. Other state must survive.
        restored = pickle.loads(pickle.dumps(caught))
        assert str(restored) == str(caught)
