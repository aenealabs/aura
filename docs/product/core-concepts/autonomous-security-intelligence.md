# Autonomous Security Intelligence

**Version:** 1.0
**Last Updated:** October 2026

---

## Overview

Autonomous Security Intelligence is the AI foundation that powers Project Aura's ability to understand, analyze, and remediate security vulnerabilities in enterprise codebases. Unlike traditional static analysis tools that rely on pattern matching, Aura uses large language models (LLMs) to reason about code at a semantic level.

This document explains what makes Aura "autonomous," how its AI systems work, and when human intervention is still necessary.

---

## What Makes Aura "Autonomous"

Traditional security tools identify problems. Aura solves them.

### Traditional Security Scanner

```
Vulnerability Detected: SQL Injection in user_service.py:47
Severity: Critical
Recommendation: Sanitize user input before database queries
```

The security team must then:
1. Understand the vulnerability
2. Research the correct fix
3. Write the patch
4. Test the patch
5. Deploy the fix

### Aura's Autonomous Approach

```
Vulnerability Detected: SQL Injection in user_service.py:47
Severity: Critical

Patch Generated:
- Modified: user_service.py
- Added parameterized query using SQLAlchemy ORM
- Updated unit tests to validate fix
- Sandbox validation: PASSED (all tests green)

Awaiting approval for deployment...
```

Aura autonomously:
1. **Understands** the vulnerability in context
2. **Generates** a patch, with security review and static validation feeding failures back to the Coder
3. **Validates** the patch in isolation (runtime sandbox testing is not yet connected; see [Sandbox Security](./sandbox-security.md))
4. **Queues** for human approval (every patch today; policy-based auto-approval is planned)
5. **Deploys** upon approval (planned; approval currently records the decision only)

> **Implementation status (October 2026).** The job server runs steps 1, 2, and 4 for a free-text prompt against the configured sample project. Starting from a scanner finding in a customer repository, runtime sandbox testing, and deployment or pull-request creation after approval are planned. The example output above is illustrative.

---

## AI/ML Foundations

Aura's intelligence comes from several interconnected AI systems.

### Large Language Models (LLMs)

Aura uses foundation models from leading AI providers, accessed through AWS Bedrock (Bedrock holds its own FedRAMP High authorization in AWS GovCloud; Aura itself is not FedRAMP authorized):

| Tier | Model family | Use Case |
|------|--------------|----------|
| `fast` | Claude Haiku | Classification, routing, query expansion |
| `accurate` | Claude Sonnet | Code generation, patch creation, code review |
| `maximum` | Claude Opus | Cross-codebase reasoning, multi-file refactoring |

**Why multiple models?** Different tasks have different requirements. Patch generation requires deep reasoning (Sonnet), while vulnerability classification needs speed (Haiku). The specific model for each tier is discovered from the deployment region at startup or pinned by the operator; see [Model Selection](../admin-guide/configuration-reference.md#model-selection).

### Chain of Draft (CoD) Prompting

Aura uses a prompting technique called Chain of Draft. Instead of verbose
Chain of Thought reasoning, CoD produces concise, structured outputs. The
commonly cited 92% token reduction comes from the published CoD research,
not from a measurement of Aura's own workloads.

```python
# Traditional CoT approach (verbose)
"Let me think through this step by step. First, I need to understand
the vulnerability. The code uses hashlib.sha1() which is not
FIPS-compliant. According to security policies, I should use
SHA256 instead. Let me generate a patch that replaces..."

# Chain of Draft approach (concise)
"VULN: SHA1 non-compliant | FIX: hashlib.sha256 | CONF: 0.95"
```

This efficiency enables faster processing and lower costs at scale.

### Embeddings and Vector Search

Code and documentation are converted into high-dimensional vectors (embeddings) that capture semantic meaning. This enables:

- **Similarity search**: Find code that is semantically related to a query
- **Pattern matching**: Identify code that follows similar patterns
- **Contextual retrieval**: Pull relevant context for patch generation

---

## How the System Learns

Aura improves over time through multiple learning mechanisms.

### Neural Memory Architecture

Based on research from Google's Titans architecture, Aura's neural memory system learns from every remediation:

1. **Surprise-Driven Memorization**: Only novel or unexpected patterns are memorized, preventing redundant learning
2. **Confidence Weighting**: High-confidence outcomes have more influence
3. **Temporal Decay**: Older patterns gradually fade unless reinforced

```
Experience: SHA1 vulnerability in auth_service.py
Surprise Score: 0.3 (familiar pattern)
Action: Skip memorization (already learned)

Experience: Novel race condition in async_handler.py
Surprise Score: 0.9 (unfamiliar pattern)
Action: Memorize with high priority
```

### Feedback Loops

Planned: human decisions create feedback that improves the system. Today approval decisions are stored in the HITL service but are not fed back into agent memory (`process_approval_decision` has no caller outside tests), and the orchestrator's Titan memory uses placeholder stores. The table shows the intended loop:

| Human Action | System Learning |
|--------------|-----------------|
| Approve patch | Reinforce confidence in similar patterns |
| Reject patch | Reduce confidence, analyze rejection reason |
| Modify patch | Learn the preferred modification pattern |
| Escalate to manual | Mark pattern as requiring human judgment |

### Organization-Specific Learning

Planned: Aura learns your organization's coding patterns and preferences:

- **Naming conventions**: Understands your variable and function naming patterns
- **Architecture patterns**: Recognizes your service structure and dependencies
- **Security policies**: Learns your specific compliance requirements beyond defaults

---

## Confidence Scoring

Aura is designed to attach a confidence score to each decision.

> **Implementation status.** The remediation workflow records one confidence value per approval request: the Reviewer's self-reflection confidence when reflection ran, otherwise a fixed prior of 0.8 (`DEFAULT_DECISION_CONFIDENCE`), labeled with its source. Confidence does not route work: every patch goes to human review regardless of score. The weighted multi-factor score, thresholds, and uncertainty intervals below are planned.

### Confidence Levels

| Score Range | Interpretation | Typical Action |
|-------------|----------------|----------------|
| 0.85 - 1.00 | High confidence | Proceed autonomously |
| 0.70 - 0.84 | Moderate confidence | Proceed with enhanced logging |
| 0.50 - 0.69 | Low confidence | Request human review |
| 0.00 - 0.49 | Very low confidence | Escalate to human |

### Confidence Factors

Planned: confidence computed from multiple signals:

```python
confidence_factors = {
    "pattern_familiarity": 0.85,    # How similar to known patterns?
    "context_completeness": 0.90,   # Is all relevant context available?
    "policy_match": 0.95,           # Does fix align with security policies?
    "test_coverage": 0.80,          # Is the affected code well-tested?
    "neural_memory": 0.75,          # Past experience with similar issues
    "taint_chain_confidence": 0.82, # Source-to-sink dataflow strength + CWE attribution
}

# Weighted combination
final_confidence = weighted_average(confidence_factors, weights)
```

**On `taint_chain_confidence`:** When the scanner produces a finding, the analyzer hands the LLM a structured taint chain (source -> propagators -> sanitizers -> sink) together with its CWE attribution and per-edge taint labels. The presence and strength of that chain is itself a confidence signal -- a fully-traced chain across files contributes more weight than a partial one. Cross-file taint analysis spans all 8 supported languages (Python, JavaScript, TypeScript, Go, Java, Rust, C, C++). The persistence layer that makes this reusable across scans is described in [Hybrid GraphRAG -> Cross-File Taint Resolver](./hybrid-graphrag.md#4-cross-file-taint-resolver-adr-093).

### Uncertainty Quantification

Planned: beyond a single confidence score, uncertainty details:

```json
{
  "confidence": 0.78,
  "confidence_interval": [0.72, 0.84],
  "uncertainties": [
    "Limited test coverage in affected module",
    "Multiple valid fix approaches possible",
    "Dependency interaction not fully analyzed"
  ],
  "recommended_action": "REQUEST_REVIEW"
}
```

---

## Limitations and Human Intervention

Aura is powerful, but not omniscient. Understanding its limitations helps you configure appropriate oversight.

### When Aura Excels

| Scenario | Why Aura Works Well |
|----------|---------------------|
| Known vulnerability patterns | Large training dataset, clear best practices |
| Standard library usage | Well-documented, consistent patterns |
| Common frameworks | Extensive context in training data |
| Clear security policies | Unambiguous right/wrong decisions |
| Well-tested codebases | High confidence in validation |

### When Human Intervention is Needed

| Scenario | Why Human Judgment is Required |
|----------|--------------------------------|
| Business logic vulnerabilities | Requires understanding of business context |
| Novel attack vectors | No prior training data for new threats |
| Architectural decisions | Trade-offs beyond security scope |
| Performance-critical code | Optimization requires domain expertise |
| Compliance edge cases | Regulatory interpretation needed |
| Cross-system dependencies | Full system context unavailable |

### Guardrails That Always Require Humans

Regardless of autonomy settings, these operations always require human approval when a policy is evaluated (the first two are hard-coded; the rest are in every default policy):

- **Production deployments**: Changes to production systems
- **Credential modifications**: API keys, secrets, passwords
- **Access control changes**: IAM, RBAC, permissions
- **Database migrations**: Schema changes, data modifications
- **Infrastructure changes**: Cloud resource modifications

---

## Recursive Context Scaling

For large codebases that exceed LLM context windows, Aura includes Recursive Language Model (RLM) techniques to analyze code at scale. The RLM package (`src/services/rlm/`) is not yet called by the remediation agents.

### The Context Problem

LLMs have finite context windows (typically 200K tokens). Enterprise codebases can contain millions of lines of code. How does Aura analyze the entire codebase?

### Recursive Decomposition

Aura generates code that analyzes code:

```python
# RLM-generated decomposition
def analyze_codebase():
    # Find all Python files
    files = context_search(r"\.py$")

    # Group by module
    modules = group_by_directory(files)

    # Analyze each module recursively
    results = []
    for module in modules:
        if module.size > CONTEXT_LIMIT:
            # Recursively decompose large modules
            result = recursive_call(module, "find_vulnerabilities")
        else:
            # Analyze directly
            result = analyze_module(module)
        results.append(result)

    # Aggregate findings
    return aggregate_results(results)
```

This enables analysis of codebases with 10M+ tokens while maintaining context coherence.

---

## Selective Decoding (JEPA)

Not every task requires full text generation. Aura includes a Joint Embedding Predictive Architecture (JEPA) package (`src/services/jepa/`) for efficient task routing; the remediation agents do not route through it yet, and the latencies below are design targets.

### Non-Generative Tasks (Fast Path)

Tasks that can be answered with embeddings alone:

| Task | Latency | Method |
|------|---------|--------|
| Vulnerability classification | ~15ms | Embedding similarity |
| Agent routing | ~10ms | Embedding matching |
| Code similarity | ~20ms | Cosine similarity |
| Priority ranking | ~25ms | Embedding-based sort |

### Generative Tasks (Standard Path)

Tasks that require text output:

| Task | Latency | Method |
|------|---------|--------|
| Patch generation | ~2000ms | Full LLM decoding |
| Code explanation | ~1500ms | Full LLM decoding |
| Fix suggestion | ~1800ms | Full LLM decoding |

The design target is a 2.85x efficiency improvement from routing simple tasks through the fast path; this has not been measured on Aura workloads.

---

## Key Takeaways

> **Aura is autonomous, not automatic.** It makes intelligent decisions based on context, confidence, and policy, but humans remain in control of critical operations.

> **Humans review every patch today.** Confidence-based routing is planned; until then, all patches go to human review.

> **The system is designed to learn continuously.** Memory guidance reaches the agent prompts when a memory service is configured; learning from approvals and rejections is planned.

> **Guardrails cannot be bypassed.** Production deployment and credential changes always require human approval in policy evaluation, regardless of autonomy settings.

---

## Related Concepts

- [Hybrid GraphRAG](./hybrid-graphrag.md) - How context is retrieved for AI decisions
- [Multi-Agent System](./multi-agent-system.md) - How specialized agents collaborate
- [HITL Workflows](./hitl-workflows.md) - Configuring human oversight
- [Sandbox Security](./sandbox-security.md) - Validating AI-generated code

---

## Technical References

- ADR-024: Titan Neural Memory Architecture
- ADR-029: Agent Optimization Strategies
- ADR-051: Recursive Context and Embedding Prediction
