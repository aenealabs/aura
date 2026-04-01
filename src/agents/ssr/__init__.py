"""
Project Aura - Self-Play SWE-RL Agent Package

This package implements the dual-role agent architecture for ADR-050 Phase 3,
enabling self-play training where bug-injection and bug-solving agents
share a policy network.

Components:
- shared_policy: Role-switching mechanism and policy abstraction
- bug_injection_agent: Semantic bug generation with difficulty calibration
- bug_solving_agent: GraphRAG-enhanced bug resolution

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #164
"""

from src.agents.ssr.bug_injection_agent import (
    BugInjectionAgent,
    InjectionCandidate,
    InjectionResult,
)
from src.agents.ssr.bug_solving_agent import BugSolvingAgent, SolveAttempt, SolveResult
from src.agents.ssr.shared_policy import (
    AgentRole,
    PolicyConfig,
    RoleContext,
    SharedPolicy,
    create_shared_policy,
)

__all__ = [
    # Shared Policy
    "SharedPolicy",
    "PolicyConfig",
    "AgentRole",
    "RoleContext",
    "create_shared_policy",
    # Bug Injection
    "BugInjectionAgent",
    "InjectionCandidate",
    "InjectionResult",
    # Bug Solving
    "BugSolvingAgent",
    "SolveAttempt",
    "SolveResult",
]
