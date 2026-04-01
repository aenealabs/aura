"""
Shared fixtures for explainability tests.
"""

from unittest.mock import MagicMock

import pytest

from src.services.explainability.config import (
    AlternativesConfig,
    ConfidenceConfig,
    ConsistencyConfig,
    ExplainabilityConfig,
    InterAgentConfig,
    ReasoningChainConfig,
)
from src.services.explainability.contracts import (
    AlternativesReport,
    ClaimVerification,
    ConfidenceInterval,
    ConsistencyReport,
    ContradictionSeverity,
    DecisionSeverity,
    ExplainabilityRecord,
    ExplainabilityScore,
    ReasoningChain,
    VerificationReport,
)


@pytest.fixture
def sample_decision_input():
    """Sample decision input data."""
    return {
        "task": "security_review",
        "code": "def process_input(data): return eval(data)",
        "file": "processor.py",
        "line": 42,
    }


@pytest.fixture
def sample_decision_output():
    """Sample decision output data."""
    return {
        "action": "flag_vulnerability",
        "severity": "critical",
        "recommendation": "Replace eval() with safe parsing",
        "code_changes": {
            "file": "processor.py",
            "old": "def process_input(data): return eval(data)",
            "new": "def process_input(data): return json.loads(data)",
        },
    }


@pytest.fixture
def sample_reasoning_chain():
    """Sample reasoning chain with steps."""
    chain = ReasoningChain(
        decision_id="dec_test123",
        agent_id="security_agent",
    )
    chain.add_step(
        description="Identified eval() usage in code",
        evidence=["Found eval() at processor.py:42"],
        confidence=0.95,
        references=["CWE-94", "OWASP A03:2021"],
    )
    chain.add_step(
        description="Assessed security impact of arbitrary code execution",
        evidence=["eval() executes any Python code"],
        confidence=0.98,
        references=["NIST SP 800-53 SI-10"],
    )
    chain.add_step(
        description="Recommended safe alternative using json.loads()",
        evidence=["json.loads() only parses JSON data"],
        confidence=0.92,
        references=["Best practice documentation"],
    )
    return chain


@pytest.fixture
def sample_alternatives_report():
    """Sample alternatives report."""
    report = AlternativesReport(
        decision_id="dec_test123",
        comparison_criteria=["Security impact", "Code quality", "Maintainability"],
    )
    report.add_alternative(
        alternative_id="alt_001",
        description="Replace eval() with json.loads()",
        confidence=0.92,
        pros=["Safe parsing", "Standard library", "Well-tested"],
        cons=["JSON only", "Requires input validation"],
        was_chosen=True,
        rejection_reason=None,
    )
    report.add_alternative(
        alternative_id="alt_002",
        description="Use ast.literal_eval()",
        confidence=0.75,
        pros=["Evaluates Python literals safely"],
        cons=["Limited to literals", "Not suitable for JSON"],
        was_chosen=False,
        rejection_reason="JSON-specific solution preferred for this use case",
    )
    report.decision_rationale = (
        "json.loads() provides the safest and most appropriate solution"
    )
    return report


@pytest.fixture
def sample_confidence_interval():
    """Sample confidence interval."""
    return ConfidenceInterval(
        point_estimate=0.92,
        lower_bound=0.85,
        upper_bound=0.97,
        uncertainty_sources=["Limited static analysis context"],
        calibration_method="ensemble_disagreement",
        sample_size=5,
    )


@pytest.fixture
def sample_consistency_report():
    """Sample consistency report."""
    return ConsistencyReport(
        decision_id="dec_test123",
        is_consistent=True,
        contradictions=[],
    )


@pytest.fixture
def sample_consistency_report_with_contradiction():
    """Sample consistency report with a contradiction."""
    report = ConsistencyReport(
        decision_id="dec_test123",
        is_consistent=False,
    )
    report.add_contradiction(
        contradiction_id="ctr_001",
        severity=ContradictionSeverity.MODERATE,
        stated_claim="Will fix all security issues",
        actual_action="Only fixed one vulnerability",
        explanation="Claim overstated the scope of the fix",
        evidence=["Initial claim: 5 issues", "Actual fixes: 1 issue"],
    )
    return report


@pytest.fixture
def sample_verification_report():
    """Sample inter-agent verification report."""
    report = VerificationReport(decision_id="dec_test123")
    report.verifications.append(
        ClaimVerification(
            claim_id="clm_001",
            upstream_agent_id="scanner_agent",
            claim_text="Found critical vulnerability",
            claim_type="security_assessment",
            is_verified=True,
            verification_evidence=["CVE-2024-1234 confirmed"],
            confidence=0.95,
            discrepancy=None,
        )
    )
    return report


@pytest.fixture
def sample_explainability_score():
    """Sample explainability score."""
    return ExplainabilityScore(
        reasoning_completeness=0.95,
        alternatives_coverage=0.85,
        confidence_calibration=0.90,
        consistency_score=1.0,
        inter_agent_trust=0.92,
    )


@pytest.fixture
def sample_explainability_record(
    sample_reasoning_chain,
    sample_alternatives_report,
    sample_confidence_interval,
    sample_consistency_report,
    sample_verification_report,
    sample_explainability_score,
):
    """Sample complete explainability record."""
    return ExplainabilityRecord(
        record_id="rec_test123",
        decision_id="dec_test123",
        agent_id="security_agent",
        severity=DecisionSeverity.CRITICAL,
        reasoning_chain=sample_reasoning_chain,
        alternatives_report=sample_alternatives_report,
        confidence_interval=sample_confidence_interval,
        consistency_report=sample_consistency_report,
        verification_report=sample_verification_report,
        explainability_score=sample_explainability_score,
        hitl_required=False,
        hitl_reason=None,
        human_readable_summary="Identified and fixed critical eval() vulnerability",
    )


@pytest.fixture
def default_config():
    """Default explainability configuration."""
    return ExplainabilityConfig()


@pytest.fixture
def reasoning_chain_config():
    """Reasoning chain configuration."""
    return ReasoningChainConfig()


@pytest.fixture
def alternatives_config():
    """Alternatives configuration."""
    return AlternativesConfig()


@pytest.fixture
def confidence_config():
    """Confidence configuration."""
    return ConfidenceConfig()


@pytest.fixture
def consistency_config():
    """Consistency configuration."""
    return ConsistencyConfig()


@pytest.fixture
def inter_agent_config():
    """Inter-agent verification configuration."""
    return InterAgentConfig()


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client for LLM calls."""
    import json

    mock = MagicMock()

    def mock_invoke_model(**kwargs):
        response = MagicMock()
        response_body = {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "steps": [
                                {
                                    "step_number": 1,
                                    "description": "Analyzed input",
                                    "evidence": ["Input analysis complete"],
                                    "confidence": 0.9,
                                    "references": ["REF-001"],
                                }
                            ]
                        }
                    )
                }
            ]
        }
        response.__getitem__ = lambda self, key: (
            MagicMock(read=lambda: json.dumps(response_body).encode())
            if key == "body"
            else None
        )
        return response

    mock.invoke_model = MagicMock(side_effect=mock_invoke_model)
    return mock


@pytest.fixture
def mock_neptune_client():
    """Mock Neptune client for graph queries."""
    mock = MagicMock()
    return mock


@pytest.fixture
def sample_upstream_claims():
    """Sample upstream claims for verification."""
    return [
        {
            "agent_id": "scanner_agent",
            "claim_type": "security_assessment",
            "claim_text": "Found critical SQL injection vulnerability",
            "evidence": ["CVE-2024-1234", "OWASP A03:2021"],
            "confidence": 0.95,
        },
        {
            "agent_id": "test_agent",
            "claim_type": "test_result",
            "claim_text": "All tests passed",
            "evidence": ["pytest executed 50 tests", "0 failures"],
            "confidence": 0.99,
        },
    ]
