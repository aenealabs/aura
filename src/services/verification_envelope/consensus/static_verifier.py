"""Project Aura - Non-LLM Static Verifier Track (issue #209).

Closes the LLM-independence gap in ADR-085's N-of-M consensus. The
existing consensus pillar runs N LLM generations and compares them
against each other -- but the verdict still comes from one model
family (Bedrock / Claude). A coordinated failure in that family is
not detectable by intra-family consensus.

This module adds an **independent second voice** that does not call
an LLM. It examines the selected centroid output and either confirms
the consensus or flags a disagreement that forces HITL escalation.

The Port is intentionally small so future implementations (semgrep,
bandit, custom CWE-rule packs, Z3 lite-mode) can drop in without
touching the consensus service.

Implements issue #209.

Author: Project Aura Team
Created: 2026-05-22
"""

from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass
from typing import Iterable, Protocol

# ---------------------------------------------------------------- contracts


@dataclass(frozen=True)
class StaticVerificationFinding:
    """A single finding produced by a static verifier."""

    rule_id: str  # e.g. "AURA-SV-001"
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW / INFO
    message: str
    cwe_id: str = ""  # optional CWE attribution
    line_hint: int = 0  # 1-indexed; 0 if unknown


@dataclass(frozen=True)
class StaticVerificationVerdict:
    """Result of one static-verifier track examining one candidate."""

    verifier_id: str  # stable identifier for the verifier
    passed: bool  # True iff no CRITICAL / HIGH findings
    findings: tuple[StaticVerificationFinding, ...] = ()
    rationale: str = ""
    latency_ms: float = 0.0

    @property
    def has_blocking_finding(self) -> bool:
        return any(f.severity.upper() in {"CRITICAL", "HIGH"} for f in self.findings)


@dataclass(frozen=True)
class StaticVerificationReport:
    """Aggregate report across one or more static verifiers."""

    verdicts: tuple[StaticVerificationVerdict, ...] = ()
    agreed_with_llm: bool = True  # True iff all verdicts passed
    aggregated_findings: tuple[StaticVerificationFinding, ...] = ()
    verifier_count: int = 0
    aggregate_latency_ms: float = 0.0

    @property
    def disagreed_with_llm(self) -> bool:
        return not self.agreed_with_llm

    def to_audit_dict(self) -> dict:
        return {
            "verifier_count": self.verifier_count,
            "agreed_with_llm": self.agreed_with_llm,
            "verdicts": [
                {
                    "verifier_id": v.verifier_id,
                    "passed": v.passed,
                    "finding_count": len(v.findings),
                    "latency_ms": v.latency_ms,
                }
                for v in self.verdicts
            ],
            "aggregate_latency_ms": self.aggregate_latency_ms,
        }


# ---------------------------------------------------------------- Port


class StaticVerifierPort(Protocol):
    """Non-LLM verifier that examines one candidate source string.

    Implementations must be **deterministic** (same input -> same
    verdict) and **side-effect-free**. They run inside the consensus
    service hot path; latency budget is < 200ms per verifier.
    """

    verifier_id: str

    def verify(self, source: str) -> StaticVerificationVerdict:
        """Examine ``source`` and return a verdict."""


# ---------------------------------------------------------------- dispatcher


class StaticVerifierDispatcher:
    """Runs one or more static verifiers and aggregates their verdicts.

    The dispatcher is deliberately synchronous: each verifier is
    CPU-bound and small, and serialising them keeps the audit trail
    deterministic. Tests can pass a single verifier; production wires
    several.
    """

    def __init__(self, verifiers: Iterable[StaticVerifierPort]) -> None:
        self._verifiers: tuple[StaticVerifierPort, ...] = tuple(verifiers)
        seen: set[str] = set()
        for v in self._verifiers:
            if v.verifier_id in seen:
                raise ValueError(
                    f"Duplicate verifier_id in dispatcher: {v.verifier_id!r}"
                )
            seen.add(v.verifier_id)

    @property
    def verifier_ids(self) -> tuple[str, ...]:
        return tuple(v.verifier_id for v in self._verifiers)

    def is_empty(self) -> bool:
        return len(self._verifiers) == 0

    def verify(self, source: str) -> StaticVerificationReport:
        """Run every verifier on ``source``; aggregate the verdicts."""
        start = time.time()
        verdicts: list[StaticVerificationVerdict] = []
        aggregated: list[StaticVerificationFinding] = []
        all_passed = True
        for verifier in self._verifiers:
            verdict = verifier.verify(source)
            verdicts.append(verdict)
            aggregated.extend(verdict.findings)
            if not verdict.passed:
                all_passed = False
        return StaticVerificationReport(
            verdicts=tuple(verdicts),
            agreed_with_llm=all_passed,
            aggregated_findings=tuple(aggregated),
            verifier_count=len(self._verifiers),
            aggregate_latency_ms=(time.time() - start) * 1000.0,
        )


# ---------------------------------------------------------------- concrete


# Rule pack for the initial AST-rule verifier. Each rule is intentionally
# *narrow* -- this verifier exists to provide an independent second
# voice on common dangerous patterns, not to replace the dedicated
# vulnerability scanner. Findings here trigger HITL escalation, not
# auto-rejection, because the LLM consensus may have a legitimate
# reason to use these patterns (test fixtures, deliberate examples).
_DANGEROUS_BUILTINS: frozenset[str] = frozenset({"eval", "exec", "compile"})
_DANGEROUS_OS_CALLS: frozenset[str] = frozenset({"system", "popen", "spawn"})
_HARDCODED_SECRET_RE: re.Pattern[str] = re.compile(
    r"""(?xi)
    (?P<kind>password|passwd|secret|api[_-]?key|access[_-]?token|
        bearer|private[_-]?key|aws[_-]?secret)
    \s*[=:]\s*
    ['"]
    (?P<value>[A-Za-z0-9+/=_\-]{12,})
    ['"]
    """,
)
_SHELL_INJECTION_RE: re.Pattern[str] = re.compile(r"shell\s*=\s*True", re.IGNORECASE)


class _DangerousCallVisitor(ast.NodeVisitor):
    """Collects line numbers of calls to dangerous builtins / os APIs."""

    def __init__(self) -> None:
        self.dangerous_builtin_calls: list[tuple[str, int]] = []
        self.dangerous_os_calls: list[tuple[str, int]] = []
        self.pickle_loads_calls: list[int] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 (ast convention)
        # eval / exec / compile
        if isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_BUILTINS:
            self.dangerous_builtin_calls.append((node.func.id, node.lineno))
        # os.system / os.popen / subprocess.* with shell=True caught separately
        elif isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr in _DANGEROUS_OS_CALLS
            ):
                self.dangerous_os_calls.append((node.func.attr, node.lineno))
            elif (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "pickle"
                and node.func.attr in {"loads", "load"}
            ):
                self.pickle_loads_calls.append(node.lineno)
        self.generic_visit(node)


class ASTRuleVerifier:
    """Initial non-LLM static verifier.

    Performs a deterministic AST + regex scan for a narrow set of
    high-signal patterns:

    - eval / exec / compile (CWE-94 Code Injection)
    - os.system / os.popen / os.spawn (CWE-78 OS Command Injection)
    - subprocess shell=True (CWE-78)
    - pickle.loads / pickle.load on untrusted data (CWE-502)
    - hardcoded credential literals (CWE-798)

    Each match becomes a HIGH-severity finding. The dispatcher treats
    HIGH findings as 'disagreed with LLM' and the consensus service
    downgrades the verdict accordingly. Source files that fail to
    parse emit a single INFO finding and the verifier returns
    ``passed=True`` (the LLM-side AST normaliser already rejects
    unparseable output, so this would be a redundant failure).
    """

    verifier_id: str = "ast-rule-v1"

    def verify(self, source: str) -> StaticVerificationVerdict:
        start = time.time()
        findings: list[StaticVerificationFinding] = []

        # AST-based checks.
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return StaticVerificationVerdict(
                verifier_id=self.verifier_id,
                passed=True,  # AST-normaliser will reject; we don't double-fail
                findings=(
                    StaticVerificationFinding(
                        rule_id="AURA-SV-PARSE",
                        severity="INFO",
                        message=f"Source unparseable; deferred to AST normaliser: {exc}",
                    ),
                ),
                rationale="parse-fail",
                latency_ms=(time.time() - start) * 1000.0,
            )

        visitor = _DangerousCallVisitor()
        visitor.visit(tree)
        for name, lineno in visitor.dangerous_builtin_calls:
            findings.append(
                StaticVerificationFinding(
                    rule_id="AURA-SV-001",
                    severity="HIGH",
                    message=f"Dangerous builtin call: {name}()",
                    cwe_id="CWE-94",
                    line_hint=lineno,
                )
            )
        for name, lineno in visitor.dangerous_os_calls:
            findings.append(
                StaticVerificationFinding(
                    rule_id="AURA-SV-002",
                    severity="HIGH",
                    message=f"Shell-equivalent OS call: os.{name}()",
                    cwe_id="CWE-78",
                    line_hint=lineno,
                )
            )
        for lineno in visitor.pickle_loads_calls:
            findings.append(
                StaticVerificationFinding(
                    rule_id="AURA-SV-003",
                    severity="HIGH",
                    message="Deserialisation of untrusted data via pickle",
                    cwe_id="CWE-502",
                    line_hint=lineno,
                )
            )

        # Regex-based checks (run on the raw source for shell=True and
        # hardcoded secrets -- AST is overkill for these).
        for match in _SHELL_INJECTION_RE.finditer(source):
            lineno = source[: match.start()].count("\n") + 1
            findings.append(
                StaticVerificationFinding(
                    rule_id="AURA-SV-004",
                    severity="HIGH",
                    message="subprocess invocation with shell=True",
                    cwe_id="CWE-78",
                    line_hint=lineno,
                )
            )
        for match in _HARDCODED_SECRET_RE.finditer(source):
            lineno = source[: match.start()].count("\n") + 1
            findings.append(
                StaticVerificationFinding(
                    rule_id="AURA-SV-005",
                    severity="HIGH",
                    message=(
                        f"Hardcoded {match.group('kind')!s} literal "
                        f"(len={len(match.group('value'))})"
                    ),
                    cwe_id="CWE-798",
                    line_hint=lineno,
                )
            )

        passed = not any(f.severity.upper() in {"CRITICAL", "HIGH"} for f in findings)
        return StaticVerificationVerdict(
            verifier_id=self.verifier_id,
            passed=passed,
            findings=tuple(findings),
            rationale=(
                "no blocking findings"
                if passed
                else f"{len(findings)} blocking findings"
            ),
            latency_ms=(time.time() - start) * 1000.0,
        )


__all__ = [
    "ASTRuleVerifier",
    "StaticVerificationFinding",
    "StaticVerificationReport",
    "StaticVerificationVerdict",
    "StaticVerifierDispatcher",
    "StaticVerifierPort",
]
