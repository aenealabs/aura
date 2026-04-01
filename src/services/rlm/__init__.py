"""
RLM (Recursive Language Model) Services Package.

This package implements the Recursive Language Model architecture from MIT CSAIL
(December 2025) for 100x context scaling through REPL-based programmatic decomposition.

Key Components:
- RecursiveContextEngine: Core RLM decomposition engine for 100x context scaling
- REPLSecurityGuard: Security controls for executing LLM-generated code
- InputSanitizer: Prevents prompt injection attacks in RLM inputs

Security Architecture (5 layers):
1. Input Sanitization - Pattern detection, size limits
2. Code Validation - AST analysis, RestrictedPython compilation
3. Restricted Execution - Safe namespace, guarded operations
4. Container Isolation - gVisor, seccomp (deployment-level)
5. Network Isolation - NetworkPolicy (deployment-level)

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

from src.services.rlm.input_sanitizer import InputSanitizer, SanitizationResult
from src.services.rlm.recursive_context_engine import (
    Match,
    RecursiveContextEngine,
    RLMConfig,
    RLMResult,
    SyncRecursiveContextEngine,
)
from src.services.rlm.security_guard import (
    CodeValidationResult,
    ExecutionResult,
    REPLSecurityGuard,
)

__all__ = [
    # Core Engine
    "RecursiveContextEngine",
    "SyncRecursiveContextEngine",
    "RLMConfig",
    "RLMResult",
    "Match",
    # Security
    "REPLSecurityGuard",
    "CodeValidationResult",
    "ExecutionResult",
    # Input Sanitization
    "InputSanitizer",
    "SanitizationResult",
]
