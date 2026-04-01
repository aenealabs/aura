"""
Chain of Draft (CoD) Prompting Templates

Implements minimalist reasoning that uses ~7.6% of Chain of Thought (CoT) tokens
while maintaining equivalent accuracy. Based on research from arXiv:2502.18600.

Key Principle: CoD uses SHORT phrases (1-5 words) per reasoning step, like human
notes during problem-solving, rather than verbose explanations.

Benefits:
- 92% token reduction vs traditional CoT
- 40-50% LLM cost reduction
- 30-50% latency improvement
- Equivalent or better accuracy on reasoning tasks

ADR-029 Phase 1.2 Implementation
"""

import logging
import os
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CoDPromptMode(Enum):
    """Prompt mode selection."""

    COD = "cod"  # Chain of Draft (minimalist, token-efficient)
    COT = "cot"  # Chain of Thought (verbose, traditional)
    AUTO = "auto"  # Automatically select based on task complexity


# Global prompt mode setting (can be overridden per-request)
_current_prompt_mode = CoDPromptMode.COD


def get_prompt_mode() -> CoDPromptMode:
    """Get current global prompt mode."""
    env_mode = os.environ.get("AURA_PROMPT_MODE", "").lower()
    if env_mode == "cot":
        return CoDPromptMode.COT
    if env_mode == "auto":
        return CoDPromptMode.AUTO
    return _current_prompt_mode


def set_prompt_mode(mode: CoDPromptMode) -> None:
    """Set global prompt mode."""
    global _current_prompt_mode
    _current_prompt_mode = mode
    logger.info(f"Prompt mode set to: {mode.value}")


# =============================================================================
# REVIEWER AGENT PROMPTS
# =============================================================================

COD_REVIEWER_PROMPT = """Security code reviewer for CMMC L3/SOX/NIST 800-53 compliance.

Code:
```python
{code}
```

Policies: FIPS crypto (SHA256+), no secrets, validate inputs, OWASP Top 10.

Draft reasoning (1-5 words per step):
<draft>
[Crypto check]: {crypto_note}
[Secrets check]: {secrets_note}
[Injection check]: {injection_note}
[OWASP check]: {owasp_note}
</draft>

JSON response:
{{"status": "PASS" or "FAIL_SECURITY", "finding": "...", "severity": "Critical/High/Medium/Low", "vulnerabilities": [...], "recommendations": [...]}}"""

COT_REVIEWER_PROMPT = """You are a security code reviewer for enterprise software following CMMC Level 3, SOX, and NIST 800-53 compliance requirements.

Review the following code for security vulnerabilities and policy compliance.

Code:
```python
{code}
```

Security Policies to Check:
1. Cryptographic Operations:
   - PROHIBITED: SHA1, MD5, DES, RC4 (not FIPS-compliant)
   - REQUIRED: SHA256, SHA384, SHA512, SHA3, AES (FIPS 140-2 compliant)

2. Secrets Management:
   - No hardcoded passwords, API keys, tokens, or credentials
   - Must use environment variables or AWS Secrets Manager

3. Input Validation:
   - All user inputs must be validated and sanitized
   - No use of eval(), exec(), or shell=True without proper controls

4. OWASP Top 10:
   - Check for injection vulnerabilities
   - Check for broken authentication patterns
   - Check for sensitive data exposure

Respond with a JSON object containing:
- "status": "PASS" if code is secure, "FAIL_SECURITY" if vulnerabilities found
- "finding": Summary description of the issue or "Code is secure and compliant"
- "severity": "Critical", "High", "Medium", or "Low" (only if status is FAIL_SECURITY)
- "vulnerabilities": Array of specific vulnerability objects with "type", "line", "description"
- "recommendations": Array of remediation recommendations

Response (JSON only):"""


# =============================================================================
# CODER AGENT PROMPTS
# =============================================================================

COD_CODER_PROMPT = """Secure code generator. Fix: {vulnerability}

Context:
{context}

Original:
```python
{code}
```

Draft (1-5 words per step):
<draft>
[Issue]: {issue_note}
[Fix]: {fix_note}
[Edge cases]: {edge_note}
</draft>

Generate ONLY the fixed Python code:"""

COD_CODER_INITIAL_PROMPT = """Secure code generator.

Task: {task}

Context:
{context}

Draft (1-5 words per step):
<draft>
[Approach]: {approach_note}
[Security]: {security_note}
[Implementation]: {impl_note}
</draft>

Generate ONLY Python code (FIPS crypto, no secrets, validated inputs):"""

COT_CODER_PROMPT = """You are a secure code generation agent for enterprise software.

Task: {task}

Context:
{context}

{remediation_note}

Requirements:
- Follow all security policies mentioned in the context
- Use FIPS-compliant algorithms (SHA256 or SHA3-512, never SHA1)
- Include appropriate comments explaining security decisions
- Follow Python best practices (PEP 8, type hints where appropriate)
- Handle errors appropriately

Generate ONLY the Python code, no explanations or markdown:"""


# =============================================================================
# VALIDATOR AGENT PROMPTS
# =============================================================================

COD_VALIDATOR_INSIGHTS_PROMPT = """Code validator. Analyze for additional issues.

Code:
```python
{code}
```

Known issues: {issues}

Draft (1-5 words per step):
<draft>
[Security gaps]: {security_note}
[Quality issues]: {quality_note}
[Fix approach]: {fix_note}
</draft>

JSON: {{"additional_issues": [...], "recommendations": [...]}}"""

COD_VALIDATOR_REQUIREMENTS_PROMPT = """Requirements validator.

Code:
```python
{code}
```

Requirements: {requirements}

Draft (1-5 words per step):
<draft>
{requirements_checks}
</draft>

JSON: {{"all_met": true/false, "results": {{...}}, "confidence": 0.0-1.0}}"""

COT_VALIDATOR_INSIGHTS_PROMPT = """You are a code validation expert.

Analyze the following code and the issues already detected.

Code:
```python
{code}
```

Issues Already Detected:
{issues}

Provide additional insights:
1. Any additional security or quality issues not already detected
2. Specific recommendations for fixing the issues

Respond with a JSON object containing:
- "additional_issues": Array of new issues with "type", "message", "severity"
- "recommendations": Array of specific fix recommendations

Response (JSON only):"""

COT_VALIDATOR_REQUIREMENTS_PROMPT = """You are a requirements validation expert.

Verify if the following code meets all the specified requirements.

Code:
```python
{code}
```

Requirements:
{requirements}

For each requirement, determine if it is met and explain why.

Respond with a JSON object containing:
- "all_met": true if ALL requirements are satisfied, false otherwise
- "results": Object with requirement number as key, containing "met" (bool) and "reason" (string)
- "confidence": Overall confidence score from 0.0 to 1.0

Response (JSON only):"""


# =============================================================================
# QUERY PLANNING AGENT PROMPTS
# =============================================================================

COD_QUERY_PLANNER_PROMPT = """Search planner for code intelligence.

Query: "{query}"
Budget: {budget} tokens

Strategies: graph (structure), vector (semantic), filesystem (paths), git (history)

Draft (1-5 words per step):
<draft>
[Intent]: {intent_note}
[Primary]: {primary_note}
[Secondary]: {secondary_note}
</draft>

JSON: {{"strategies": [{{"type": "...", "query": "...", "priority": 1-10, "tokens": N}}, ...]}}"""

COT_QUERY_PLANNER_PROMPT = """You are a search query planner for a code intelligence system.

Given a user's code search query, generate an optimal multi-strategy search plan.

USER QUERY: "{query}"
CONTEXT BUDGET: {budget} tokens

AVAILABLE SEARCH STRATEGIES:

1. **Graph Search (Neptune)**
   - Purpose: Structural queries (call graphs, dependencies, inheritance)
   - Use when: Query involves relationships between code entities
   - Examples: "functions calling X", "dependencies of Y", "classes extending Z"
   - Cost: Low (typically 1000-5000 tokens per query)

2. **Vector Search (OpenSearch)**
   - Purpose: Semantic similarity search using embeddings
   - Use when: Query is conceptual or semantic in nature
   - Examples: "code similar to authentication", "error handling patterns"
   - Cost: Medium (typically 5000-10000 tokens per query)

3. **Filesystem Search (OpenSearch metadata)**
   - Purpose: File pattern matching, metadata filtering
   - Use when: Query involves file paths, recent changes, file properties
   - Examples: "files matching *auth*.py", "recently modified files", "test files"
   - Cost: Low (typically 1000-3000 tokens per query)

4. **Git Search (commit history)**
   - Purpose: Find files by commit history, authorship, recent changes
   - Use when: Query involves temporal aspects or code evolution
   - Examples: "files changed in last week", "code by author X", "commits fixing bug Y"
   - Cost: Low (typically 1000-2000 tokens per query)

TASK:
Generate a prioritized list of search strategies to answer the user's query.
For each strategy, provide:
- Strategy type (graph/vector/filesystem/git)
- Specific query to execute
- Priority (1-10, where 10 is highest)
- Estimated token cost

RESPOND IN JSON FORMAT:
{{"strategies": [{{"type": "...", "query": "...", "priority": N, "tokens": N}}, ...]}}"""


# =============================================================================
# PROMPT BUILDER FUNCTIONS
# =============================================================================


def build_cod_prompt(
    agent_type: str,
    mode: CoDPromptMode | None = None,
    **kwargs: Any,
) -> str:
    """
    Build a prompt using the appropriate template based on mode.

    Args:
        agent_type: Type of agent ("reviewer", "coder", "validator_insights",
                   "validator_requirements", "query_planner")
        mode: Prompt mode override (uses global setting if None)
        **kwargs: Template variables

    Returns:
        Formatted prompt string

    Example:
        >>> prompt = build_cod_prompt(
        ...     "reviewer",
        ...     code="def foo(): pass",
        ...     mode=CoDPromptMode.COD
        ... )
    """
    effective_mode = mode or get_prompt_mode()

    # Select template based on agent type and mode
    templates = {
        "reviewer": {
            CoDPromptMode.COD: COD_REVIEWER_PROMPT,
            CoDPromptMode.COT: COT_REVIEWER_PROMPT,
        },
        "coder": {
            CoDPromptMode.COD: COD_CODER_PROMPT,
            CoDPromptMode.COT: COT_CODER_PROMPT,
        },
        "coder_initial": {
            CoDPromptMode.COD: COD_CODER_INITIAL_PROMPT,
            CoDPromptMode.COT: COT_CODER_PROMPT,
        },
        "validator_insights": {
            CoDPromptMode.COD: COD_VALIDATOR_INSIGHTS_PROMPT,
            CoDPromptMode.COT: COT_VALIDATOR_INSIGHTS_PROMPT,
        },
        "validator_requirements": {
            CoDPromptMode.COD: COD_VALIDATOR_REQUIREMENTS_PROMPT,
            CoDPromptMode.COT: COT_VALIDATOR_REQUIREMENTS_PROMPT,
        },
        "query_planner": {
            CoDPromptMode.COD: COD_QUERY_PLANNER_PROMPT,
            CoDPromptMode.COT: COT_QUERY_PLANNER_PROMPT,
        },
    }

    if agent_type not in templates:
        raise ValueError(f"Unknown agent type: {agent_type}")

    # AUTO mode: use CoD for most tasks
    if effective_mode == CoDPromptMode.AUTO:
        effective_mode = CoDPromptMode.COD

    template = templates[agent_type].get(
        effective_mode, templates[agent_type][CoDPromptMode.COT]
    )

    # Add placeholder values for draft notes if not provided
    draft_placeholders = {
        "crypto_note": "check algorithms",
        "secrets_note": "scan for hardcoded",
        "injection_note": "eval/exec/shell",
        "owasp_note": "top 10 patterns",
        "issue_note": "identify problem",
        "fix_note": "apply fix",
        "edge_note": "handle errors",
        "approach_note": "design solution",
        "security_note": "apply policies",
        "impl_note": "write code",
        "security_gaps_note": "gaps found",
        "quality_note": "code issues",
        "requirements_checks": "[Req 1]: check\n[Req 2]: check",
        "intent_note": "understand query",
        "primary_note": "main strategy",
        "secondary_note": "backup strategy",
    }

    # Merge placeholders with provided kwargs
    format_kwargs = {**draft_placeholders, **kwargs}

    try:
        return template.format(**format_kwargs)
    except KeyError as e:
        logger.warning(f"Missing template variable: {e}")
        # Return template with unfilled placeholders for debugging
        return template


def estimate_token_savings(cod_prompt: str, cot_prompt: str) -> dict[str, Any]:
    """
    Estimate token savings between CoD and CoT prompts.

    Args:
        cod_prompt: Chain of Draft prompt
        cot_prompt: Chain of Thought prompt

    Returns:
        Dict with token estimates and savings percentage
    """
    # Rough estimate: 1 token ~= 4 characters
    cod_chars = len(cod_prompt)
    cot_chars = len(cot_prompt)

    cod_tokens = cod_chars // 4
    cot_tokens = cot_chars // 4

    savings = 1 - (cod_tokens / cot_tokens) if cot_tokens > 0 else 0

    return {
        "cod_tokens": cod_tokens,
        "cot_tokens": cot_tokens,
        "savings_percent": round(savings * 100, 1),
        "tokens_saved": cot_tokens - cod_tokens,
    }


if __name__ == "__main__":
    # Demo: Show token savings for each agent type
    print("Chain of Draft (CoD) Token Savings Analysis")
    print("=" * 60)

    # Reviewer
    cod = build_cod_prompt(
        "reviewer", code="def example(): pass", mode=CoDPromptMode.COD
    )
    cot = build_cod_prompt(
        "reviewer", code="def example(): pass", mode=CoDPromptMode.COT
    )
    savings = estimate_token_savings(cod, cot)
    print("\nReviewer Agent:")
    print(f"  CoD: ~{savings['cod_tokens']} tokens")
    print(f"  CoT: ~{savings['cot_tokens']} tokens")
    print(f"  Savings: {savings['savings_percent']}%")

    # Coder
    cod = build_cod_prompt(
        "coder",
        vulnerability="SQL injection",
        context="User login function",
        code="query = f'SELECT * FROM users WHERE id={user_id}'",
        mode=CoDPromptMode.COD,
    )
    cot = build_cod_prompt(
        "coder",
        task="Fix SQL injection vulnerability",
        context="User login function",
        remediation_note="Security fix required",
        mode=CoDPromptMode.COT,
    )
    savings = estimate_token_savings(cod, cot)
    print("\nCoder Agent:")
    print(f"  CoD: ~{savings['cod_tokens']} tokens")
    print(f"  CoT: ~{savings['cot_tokens']} tokens")
    print(f"  Savings: {savings['savings_percent']}%")

    # Query Planner
    cod = build_cod_prompt(
        "query_planner",
        query="Find authentication code",
        budget=100000,
        mode=CoDPromptMode.COD,
    )
    cot = build_cod_prompt(
        "query_planner",
        query="Find authentication code",
        budget=100000,
        mode=CoDPromptMode.COT,
    )
    savings = estimate_token_savings(cod, cot)
    print("\nQuery Planner Agent:")
    print(f"  CoD: ~{savings['cod_tokens']} tokens")
    print(f"  CoT: ~{savings['cot_tokens']} tokens")
    print(f"  Savings: {savings['savings_percent']}%")

    print("\n" + "=" * 60)
    print("CoD implementation ready for agent integration!")
