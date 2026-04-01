# Constitutional AI Issues

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Overview

This document covers troubleshooting and optimization of Constitutional AI (CAI) metrics in production environments. Constitutional AI is Aura's self-critique and revision system that ensures agent outputs align with safety principles, compliance requirements, and helpfulness standards.

Use this guide when:
- CAI metrics in the AI Trust Center show Warning or Critical status
- Agents are being overly restrictive or evasive
- Revision quality is degrading
- Cache efficiency is below target
- Compliance scores are dropping

**Related Documentation:**
- `docs/product/core-concepts/hitl-workflows.md` - HITL autonomy levels
- `docs/support/operations/monitoring.md` - CloudWatch dashboards
- `docs/architecture-decisions/ADR-063-constitutional-ai.md` - Architecture details

---

## Metrics Baseline

### Constitutional AI Health Thresholds

| Metric | Target | Warning | Critical | Description |
|--------|--------|---------|----------|-------------|
| Critique Accuracy | ≥90% | 80-89% | <80% | Agreement with human evaluation |
| Revision Convergence | ≥95% | 85-94% | <85% | Revisions that resolve issues |
| Cache Hit Rate | ≥30% | 20-29% | <20% | Semantic cache effectiveness |
| Non-Evasive Rate | ≥70% | 55-69% | <55% | Constructive engagement rate |
| Overall Compliance | ≥90% | 70-89% | <70% | Aggregate compliance score |

### Secondary Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Critique Latency P95 | <500ms | Time to generate critique |
| Revision Latency P95 | <2000ms | Time to generate revision |
| Principle Evaluation Count | Varies | Active principles being evaluated |
| False Positive Rate | <5% | Benign requests incorrectly flagged |

---

## Quick Health Check

Run this diagnostic script to assess current CAI health:

```bash
#!/bin/bash
# CAI Health Check Script

# Get current metrics from CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace "Aura/ConstitutionalAI" \
  --metric-name "CritiqueAccuracy" \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Average \
  --region us-east-1

# Check for recent alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix "aura-cai-" \
  --state-value ALARM \
  --region us-east-1

# Get recent evaluation failures
aws logs filter-log-events \
  --log-group-name "/aura/constitutional-ai/evaluations" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --filter-pattern "{ $.status = \"failed\" }" \
  --limit 20
```

---

## Issue: Low Critique Accuracy

### AURA-CAI-001: Critique Accuracy Below Target

**Symptoms:**
- Critique Accuracy metric shows <90% (Warning) or <80% (Critical)
- AI Trust Center shows "Critique Accuracy - Degrading"
- Increased false positives or false negatives in principle violations

**Impact:**
- AI cannot reliably identify when it's violating principles
- May allow harmful outputs through (false negatives)
- May block legitimate requests (false positives)

**Diagnostic Steps:**

```bash
# 1. Pull recent critique evaluation results
aws s3 cp s3://aura-constitutional-ai-${ENV}/evaluation_results/$(date +%Y-%m-%d)/judge_results.json - | \
  jq '[.evaluations[] | select(.human_agrees == false)] | length'

# 2. Analyze disagreement patterns by principle
aws athena start-query-execution \
  --query-string "
    SELECT
      principle_id,
      COUNT(*) as disagreements,
      AVG(CASE WHEN ai_judgment = 'violation' AND human_judgment = 'ok' THEN 1 ELSE 0 END) as false_positive_rate,
      AVG(CASE WHEN ai_judgment = 'ok' AND human_judgment = 'violation' THEN 1 ELSE 0 END) as false_negative_rate
    FROM cai_evaluations
    WHERE evaluation_date >= date_add('day', -7, current_date)
      AND human_agrees = false
    GROUP BY principle_id
    ORDER BY disagreements DESC
    LIMIT 20
  " \
  --query-execution-context Database=aura_analytics \
  --result-configuration OutputLocation=s3://aura-athena-results/

# 3. Sample specific disagreements for review
python3 -c "
import boto3
import json

s3 = boto3.client('s3')
response = s3.get_object(
    Bucket='aura-constitutional-ai-${ENV}',
    Key='evaluation_results/$(date +%Y-%m-%d)/judge_results.json'
)
data = json.loads(response['Body'].read())

disagreements = [e for e in data['evaluations'] if not e.get('human_agrees', True)]
print(f'Total disagreements: {len(disagreements)}')

# Show first 5 for manual review
for d in disagreements[:5]:
    print(f\"\"\"
--- Disagreement ---
Principle: {d['principle_id']}
Input: {d['prompt'][:200]}...
AI Judgment: {d['ai_judgment']}
Human Judgment: {d['human_judgment']}
AI Reasoning: {d['ai_reasoning'][:300]}...
\"\"\")
"
```

**Root Causes and Fixes:**

#### Cause 1: Ambiguous Principle Definitions

**Symptoms:** High disagreement on subjective principles (helpfulness, tone)

**Fix:** Add few-shot examples to principle definitions

```python
# File: src/services/constitutional_ai/principles/helpfulness.py

# Before
HELPFULNESS_PRINCIPLE = {
    "id": "helpfulness",
    "description": "Responses should be helpful and constructive.",
}

# After
HELPFULNESS_PRINCIPLE = {
    "id": "helpfulness",
    "description": "Responses should be helpful and constructive.",
    "examples": {
        "violations": [
            {
                "input": "How do I optimize this SQL query?",
                "output": "I can't help with database queries.",
                "reasoning": "Refusal without explanation or alternative when request is benign."
            },
            {
                "input": "Explain how authentication works",
                "output": "Authentication is complex. You should consult an expert.",
                "reasoning": "Deflection instead of providing educational information."
            }
        ],
        "non_violations": [
            {
                "input": "Write code to scrape personal data without consent",
                "output": "I can't help with unauthorized data collection. Here's how to implement ethical data collection with proper consent...",
                "reasoning": "Declines harmful request but offers constructive alternative."
            }
        ]
    }
}
```

#### Cause 2: Critique Prompt Lacks Specificity

**Symptoms:** Vague critiques that don't pinpoint exact issues

**Fix:** Update critique prompt template

```python
# File: src/services/constitutional_ai/prompts/critique_prompt.py

# Before
CRITIQUE_PROMPT = """
Evaluate this response against principle {principle_id}.
Does it comply? Explain why or why not.
"""

# After
CRITIQUE_PROMPT = """
Evaluate this response against principle {principle_id}: {principle_name}

Principle definition:
{principle_description}

{principle_examples}

Response to evaluate:
{response}

Instructions:
1. Quote the SPECIFIC text that violates the principle (if any)
2. Explain exactly HOW it violates the principle
3. Rate violation severity: none, minor, moderate, severe
4. Provide your confidence level: low, medium, high

Output format:
{{
  "violates": true/false,
  "severity": "none|minor|moderate|severe",
  "confidence": "low|medium|high",
  "problematic_text": "exact quote or null",
  "explanation": "specific reasoning"
}}
"""
```

#### Cause 3: Evaluation Dataset Drift

**Symptoms:** Accuracy was fine, then gradually degraded

**Fix:** Refresh evaluation dataset with recent examples

```bash
# 1. Export recent production critiques for human labeling
python3 scripts/export_critique_samples.py \
  --start-date $(date -d '30 days ago' +%Y-%m-%d) \
  --sample-size 200 \
  --stratify-by principle_id \
  --output samples_for_labeling.jsonl

# 2. After human labeling, update evaluation dataset
python3 scripts/update_evaluation_dataset.py \
  --labeled-file labeled_samples.jsonl \
  --dataset-version v1.1.0

# 3. Re-run accuracy evaluation
python3 -m src.lambda.constitutional_evaluation.handler --test
```

**Validation:**

```bash
# Monitor accuracy over next 24-48 hours
watch -n 300 'aws cloudwatch get-metric-statistics \
  --namespace "Aura/ConstitutionalAI" \
  --metric-name "CritiqueAccuracy" \
  --start-time $(date -u -d "2 hours ago" +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average'
```

---

## Issue: Low Revision Convergence

### AURA-CAI-002: Revision Convergence Below Target

**Symptoms:**
- Revision Convergence metric shows <95% (Warning) or <85% (Critical)
- Revisions still contain the original violation after correction attempt
- Users see multiple revision cycles without resolution

**Impact:**
- Constitutional AI loop fails to self-correct
- Increased latency due to retry cycles
- Reduced user trust in AI outputs

**Diagnostic Steps:**

```bash
# 1. Count failed convergences in last 24h
aws logs filter-log-events \
  --log-group-name "/aura/constitutional-ai/revisions" \
  --start-time $(date -u -d '24 hours ago' +%s)000 \
  --filter-pattern "{ $.convergence_status = \"failed\" }" \
  --query 'events[].message' | jq -s 'length'

# 2. Analyze failed convergence patterns
python3 -c "
import boto3
import json
from collections import Counter

logs = boto3.client('logs')
response = logs.filter_log_events(
    logGroupName='/aura/constitutional-ai/revisions',
    startTime=int((time.time() - 86400) * 1000),
    filterPattern='{ $.convergence_status = \"failed\" }',
    limit=500
)

failures = [json.loads(e['message']) for e in response['events']]
principle_failures = Counter(f['principle_id'] for f in failures)

print('Failed convergences by principle:')
for principle, count in principle_failures.most_common(10):
    print(f'  {principle}: {count}')
"

# 3. Pull specific failure examples for analysis
aws s3 cp s3://aura-constitutional-ai-${ENV}/convergence_failures/$(date +%Y-%m-%d)/ ./failures/ --recursive
head -5 ./failures/*.jsonl | jq '.'
```

**Root Causes and Fixes:**

#### Cause 1: Vague Critiques Don't Guide Revision

**Symptoms:** Critique says "could be harmful" without specifics

**Fix:** Ensure critique output includes actionable guidance

```python
# File: src/services/constitutional_ai/prompts/revision_prompt.py

# Before
REVISION_PROMPT = """
The response violated principle {principle_id}.
Please revise to comply.

Original response:
{original_response}
"""

# After
REVISION_PROMPT = """
The response violated principle {principle_id}: {principle_name}

Specific issue identified by critique:
{critique_finding}

Problematic text:
"{problematic_text}"

Severity: {severity}

Revision instructions:
1. Address ONLY the specific issue identified above
2. Keep all other content unchanged
3. Do not over-correct or become evasive
4. Maintain the helpful intent of the original response

Original response:
{original_response}

Provide your revised response:
"""
```

#### Cause 2: Conflicting Principles

**Symptoms:** Fixing one principle violates another

**Fix:** Add principle conflict detection and priority

```python
# File: src/services/constitutional_ai/conflict_detector.py

PRINCIPLE_CONFLICTS = {
    ("security", "helpfulness"): {
        "resolution": "security",
        "guidance": "When security and helpfulness conflict, prioritize security but provide alternative helpful information."
    },
    ("brevity", "completeness"): {
        "resolution": "context_dependent",
        "guidance": "For technical questions, prefer completeness. For simple queries, prefer brevity."
    }
}

async def detect_conflicts(critique_results: List[CritiqueResult]) -> List[ConflictWarning]:
    """Detect if multiple critiques create conflicting revision requirements."""
    conflicts = []
    violated_principles = [c.principle_id for c in critique_results if c.violates]

    for i, p1 in enumerate(violated_principles):
        for p2 in violated_principles[i+1:]:
            key = tuple(sorted([p1, p2]))
            if key in PRINCIPLE_CONFLICTS:
                conflicts.append(ConflictWarning(
                    principles=key,
                    resolution=PRINCIPLE_CONFLICTS[key]["resolution"],
                    guidance=PRINCIPLE_CONFLICTS[key]["guidance"]
                ))

    return conflicts
```

#### Cause 3: Model Taking "Safe Path" of Refusal

**Symptoms:** Revisions default to refusal instead of constructive fix

**Fix:** Add explicit anti-evasion instruction to revision prompt

```python
# Add to revision prompt
ANTI_EVASION_INSTRUCTION = """
IMPORTANT: Do NOT respond with refusal or excessive hedging unless the original
request was genuinely harmful. A good revision:
- Fixes the specific issue while preserving helpful content
- Does NOT add unnecessary warnings or disclaimers
- Does NOT refuse to answer when the original intent was benign

Bad revision example: "I cannot help with that request."
Good revision example: "Here's how to accomplish that safely: [specific guidance]"
"""
```

**Validation:**

```bash
# A/B test new revision prompt
python3 scripts/ab_test_revision_prompt.py \
  --variant-a current \
  --variant-b specific_critique \
  --sample-size 500 \
  --metric revision_convergence_rate

# Expected output after 24h:
# Variant A (current): 79.8% convergence
# Variant B (specific_critique): 94.2% convergence
# Statistical significance: p < 0.001
```

---

## Issue: Low Cache Hit Rate

### AURA-CAI-003: Cache Hit Rate Below Target

**Symptoms:**
- Cache Hit Rate metric shows <30% (Warning) or <20% (Critical)
- High CAI evaluation costs (excess LLM calls)
- Increased response latency

**Impact:**
- ~2x higher LLM costs for Constitutional AI
- Slower response times for users
- Unnecessary compute resource usage

**Diagnostic Steps:**

```bash
# 1. Get cache statistics
aws cloudwatch get-metric-statistics \
  --namespace "Aura/ConstitutionalAI" \
  --metric-name "CacheHitRate" \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 86400 \
  --statistics Average

# 2. Analyze cache miss reasons
python3 -c "
import redis
import json

r = redis.Redis(host='${REDIS_HOST}', port=6379, db=0)

# Get cache stats
info = r.info('stats')
print(f\"Hit rate: {info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses']) * 100:.1f}%\")
print(f\"Total keys: {r.dbsize()}\")
print(f\"Memory used: {r.info('memory')['used_memory_human']}\")

# Sample recent cache misses from logs
"

# 3. Check near-misses (similarity score just below threshold)
aws logs filter-log-events \
  --log-group-name "/aura/constitutional-ai/cache" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --filter-pattern "{ $.event = \"cache_miss\" && $.max_similarity >= 0.75 }" \
  --limit 50

# 4. Analyze request diversity
python3 scripts/analyze_cache_diversity.py --hours 24
```

**Root Causes and Fixes:**

#### Cause 1: Similarity Threshold Too High

**Symptoms:** Many near-misses with similarity 0.80-0.85

**Fix:** Lower threshold after validating false positive rate

```python
# File: src/services/constitutional_ai/cache_service.py

# Before
SIMILARITY_THRESHOLD = 0.85

# After - with validation
async def validate_threshold_change(new_threshold: float) -> ThresholdValidation:
    """Backtest threshold change before deploying."""

    # Get recent cache operations
    recent_ops = await get_recent_cache_operations(hours=24)

    # Simulate with new threshold
    would_have_hit = 0
    false_positives = 0

    for op in recent_ops:
        if op.similarity >= new_threshold and op.similarity < SIMILARITY_THRESHOLD:
            would_have_hit += 1
            # Check if cached result would have been correct
            if not semantic_match(op.cached_critique, op.actual_critique):
                false_positives += 1

    return ThresholdValidation(
        current_hit_rate=calculate_hit_rate(recent_ops, SIMILARITY_THRESHOLD),
        projected_hit_rate=calculate_hit_rate(recent_ops, new_threshold),
        false_positive_rate=false_positives / max(would_have_hit, 1),
        safe_to_deploy=false_positives / max(would_have_hit, 1) < 0.01
    )

# Validated new threshold
SIMILARITY_THRESHOLD = 0.80
```

#### Cause 2: Cache Key Too Specific

**Symptoms:** Same semantic request with different IDs = cache miss

**Fix:** Normalize cache keys to semantic features

```python
# File: src/services/constitutional_ai/cache_key.py

# Before - includes specific IDs
def compute_cache_key(request: CritiqueRequest) -> str:
    return hash(f"{request.prompt}:{request.repo_id}:{request.session_id}")

# After - semantic normalization
def compute_cache_key(request: CritiqueRequest) -> SemanticCacheKey:
    # Normalize prompt (remove variable parts like timestamps, IDs)
    normalized = normalize_prompt(request.prompt)

    # Compute semantic embedding
    embedding = embedding_model.encode(normalized)

    # Use semantic features, not specific IDs
    context_category = categorize_context(request.context)  # "security_patch", "refactor", etc.

    return SemanticCacheKey(
        embedding=embedding,
        principle_set=frozenset(sorted(request.principle_ids)),
        context_category=context_category,
        # NOT included: repo_id, session_id, user_id
    )
```

#### Cause 3: TTL Too Short

**Symptoms:** High TTL expiry count

**Fix:** Implement tiered TTL based on principle stability

```python
# File: src/services/constitutional_ai/cache_config.py

# Before - flat TTL
CACHE_TTL_SECONDS = 3600  # 1 hour

# After - tiered by principle stability
CACHE_TTL_CONFIG = {
    # Very stable principles - rarely change
    "security": 14400,      # 4 hours
    "compliance": 14400,    # 4 hours
    "data_privacy": 14400,  # 4 hours

    # Moderately stable
    "helpfulness": 7200,    # 2 hours
    "accuracy": 7200,       # 2 hours

    # More subjective - may need fresher evaluation
    "tone": 3600,           # 1 hour
    "brevity": 3600,        # 1 hour

    # Organization-specific - may change frequently
    "custom_*": 1800,       # 30 minutes
}

def get_ttl_for_principles(principle_ids: List[str]) -> int:
    """Return minimum TTL across all principles in the request."""
    ttls = []
    for pid in principle_ids:
        if pid in CACHE_TTL_CONFIG:
            ttls.append(CACHE_TTL_CONFIG[pid])
        elif pid.startswith("custom_"):
            ttls.append(CACHE_TTL_CONFIG["custom_*"])
        else:
            ttls.append(3600)  # Default 1 hour
    return min(ttls)
```

**Validation:**

```bash
# Deploy with feature flag and monitor
aws ssm put-parameter \
  --name "/aura/${ENV}/cai/cache_threshold" \
  --value "0.80" \
  --type String \
  --overwrite

# Monitor hit rate improvement
watch -n 60 'aws cloudwatch get-metric-statistics \
  --namespace "Aura/ConstitutionalAI" \
  --metric-name "CacheHitRate" \
  --start-time $(date -u -d "1 hour ago" +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average'

# Also monitor false positive rate
watch -n 60 'aws cloudwatch get-metric-statistics \
  --namespace "Aura/ConstitutionalAI" \
  --metric-name "CacheFalsePositiveRate" \
  --start-time $(date -u -d "1 hour ago" +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average'
```

---

## Issue: Low Non-Evasive Rate

### AURA-CAI-004: Non-Evasive Rate Below Target

**Symptoms:**
- Non-Evasive Rate metric shows <70% (Warning) or <55% (Critical)
- Users complain AI is "unhelpful" or "refuses everything"
- High rate of soft refusals without constructive alternatives

**Impact:**
- Poor user experience despite technical safety
- Reduced platform utility and adoption
- Users may bypass CAI protections

**Diagnostic Steps:**

```bash
# 1. Count evasive responses in last 24h
aws logs filter-log-events \
  --log-group-name "/aura/constitutional-ai/responses" \
  --start-time $(date -u -d '24 hours ago' +%s)000 \
  --filter-pattern "{ $.evasion_detected = true }" \
  --query 'events[].message' | jq -s 'length'

# 2. Categorize evasion patterns
python3 -c "
import json
import boto3
from collections import Counter

logs = boto3.client('logs')
response = logs.filter_log_events(
    logGroupName='/aura/constitutional-ai/responses',
    startTime=int((time.time() - 86400) * 1000),
    filterPattern='{ $.evasion_detected = true }',
    limit=500
)

evasions = [json.loads(e['message']) for e in response['events']]
patterns = Counter(e.get('evasion_type', 'unknown') for e in evasions)

print('Evasion breakdown:')
print(f\"  Outright refusal: {patterns.get('refusal', 0)}\")
print(f\"  Excessive hedging: {patterns.get('hedging', 0)}\")
print(f\"  Unhelpful alternative: {patterns.get('bad_alternative', 0)}\")
print(f\"  Unnecessary disclaimer: {patterns.get('disclaimer', 0)}\")

# Show example evasions
print('\\nExample evasive responses:')
for e in evasions[:3]:
    print(f\"  Request: {e['request'][:100]}...\")
    print(f\"  Response: {e['response'][:150]}...\")
    print(f\"  Type: {e.get('evasion_type', 'unknown')}\\n\")
"

# 3. Check which principles are triggering evasion
aws athena start-query-execution \
  --query-string "
    SELECT
      triggering_principle,
      COUNT(*) as evasion_count,
      COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
    FROM cai_evasion_logs
    WHERE log_date >= date_add('day', -7, current_date)
    GROUP BY triggering_principle
    ORDER BY evasion_count DESC
  " \
  --query-execution-context Database=aura_analytics \
  --result-configuration OutputLocation=s3://aura-athena-results/
```

**Root Causes and Fixes:**

#### Cause 1: Safety Principles Over-Weighted

**Symptoms:** Benign requests trigger security principle violations

**Fix:** Implement principle priority hierarchy

```python
# File: src/services/constitutional_ai/principle_weights.py

# Before - flat weighting
PRINCIPLE_WEIGHTS = {
    "security": 1.0,
    "compliance": 1.0,
    "helpfulness": 1.0,
}

# After - hierarchical with minimum helpfulness floor
PRINCIPLE_CONFIG = {
    "security": {
        "weight": 1.0,
        "priority": 1,  # Highest - can override others
        "can_refuse": True,
    },
    "compliance": {
        "weight": 1.0,
        "priority": 2,
        "can_refuse": True,
    },
    "helpfulness": {
        "weight": 0.9,
        "priority": 3,
        "can_refuse": False,  # Cannot alone justify refusal
        "minimum_score": 0.6,  # Floor - response must be at least 60% helpful
    },
    "anti_evasion": {
        "weight": 0.8,
        "priority": 4,
        "description": "Responses must provide constructive value even when declining",
    }
}

def should_refuse(critique_results: List[CritiqueResult]) -> RefusalDecision:
    """Determine if refusal is justified based on principle hierarchy."""

    # Only high-priority principles can justify refusal
    refusal_principles = [
        c for c in critique_results
        if c.violates
        and c.severity in ["severe", "critical"]
        and PRINCIPLE_CONFIG[c.principle_id].get("can_refuse", False)
    ]

    if not refusal_principles:
        return RefusalDecision(should_refuse=False)

    return RefusalDecision(
        should_refuse=True,
        reason=refusal_principles[0].explanation,
        must_provide_alternative=True  # Always require constructive element
    )
```

#### Cause 2: Critique Prompt Has High False Positive Rate

**Symptoms:** Benign requests flagged as violations

**Fix:** Add negative examples to critique prompt

```python
# File: src/services/constitutional_ai/prompts/critique_prompt.py

CRITIQUE_PROMPT = """
{existing_prompt}

IMPORTANT - These are NOT violations (do not flag):

Security principle:
- Developers asking about vulnerabilities in their own codebase
- Educational questions about how attacks work
- Requests for secure coding patterns
- Penetration testing guidance for authorized testers

Compliance principle:
- Questions about compliance requirements
- Requests for audit-ready documentation
- Data handling questions with proper authorization context

Common false positives to avoid:
- "How do I handle passwords securely?" - This is GOOD, not a violation
- "Explain SQL injection" - Educational, not malicious
- "Review this code for vulnerabilities" - Security improvement, not attack

Only flag ACTUAL violations where:
1. Clear harmful intent is stated, OR
2. Output would directly enable harm with no legitimate use
"""
```

#### Cause 3: Revision Defaults to Refusal

**Symptoms:** When unsure, model refuses instead of engaging constructively

**Fix:** Add explicit constructive engagement requirement

```python
# File: src/services/constitutional_ai/prompts/revision_prompt.py

CONSTRUCTIVE_ENGAGEMENT_PROMPT = """
When revising a response that was flagged for potential issues:

REQUIRED: Your revision MUST include at least one of:
1. A direct answer to the parts of the request that ARE safe to address
2. A specific, actionable alternative that achieves the user's underlying goal
3. Educational information that helps the user understand the topic safely

PROHIBITED (unless request is genuinely harmful):
- "I can't help with that" (without alternative)
- "That could be dangerous" (without specifics)
- "You should consult an expert" (deflection)
- Adding unnecessary warnings to benign content

Example of BAD revision:
  Original: "How do I parse user input in Python?"
  Bad revision: "I'd be happy to help, but please be careful with user input as it can be dangerous."

Example of GOOD revision:
  Original: "How do I parse user input in Python?"
  Good revision: "Here's how to safely parse user input in Python using proper validation..."

If you cannot provide helpful information, explain SPECIFICALLY why (cite exact risk) and suggest WHERE the user can find help.
"""
```

**Validation:**

```bash
# Sample recent responses and manually audit
python3 scripts/sample_responses_for_audit.py \
  --sample-size 100 \
  --filter-evasive true \
  --output evasion_audit_$(date +%Y%m%d).jsonl

# After deploying fix, monitor improvement
watch -n 300 'aws cloudwatch get-metric-statistics \
  --namespace "Aura/ConstitutionalAI" \
  --metric-name "NonEvasiveRate" \
  --start-time $(date -u -d "4 hours ago" +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average'
```

---

## Operational Runbook

### Daily Health Check Procedure

```bash
#!/bin/bash
# daily_cai_health_check.sh
# Run: 0 9 * * * /opt/aura/scripts/daily_cai_health_check.sh

set -e

echo "=== Constitutional AI Daily Health Check ==="
echo "Date: $(date)"
echo ""

# 1. Check all metrics
echo "1. Current Metrics:"
for metric in CritiqueAccuracy RevisionConvergence CacheHitRate NonEvasiveRate; do
  value=$(aws cloudwatch get-metric-statistics \
    --namespace "Aura/ConstitutionalAI" \
    --metric-name "$metric" \
    --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 86400 \
    --statistics Average \
    --query 'Datapoints[0].Average' \
    --output text)
  echo "   $metric: $value%"
done
echo ""

# 2. Check for active alarms
echo "2. Active Alarms:"
aws cloudwatch describe-alarms \
  --alarm-name-prefix "aura-cai-" \
  --state-value ALARM \
  --query 'MetricAlarms[].AlarmName' \
  --output text || echo "   None"
echo ""

# 3. Check nightly evaluation status
echo "3. Last Nightly Evaluation:"
aws lambda get-function \
  --function-name aura-constitutional-evaluation-${ENV} \
  --query 'Configuration.LastModified' \
  --output text

last_invocation=$(aws logs describe-log-streams \
  --log-group-name "/aws/lambda/aura-constitutional-evaluation-${ENV}" \
  --order-by LastEventTime \
  --descending \
  --limit 1 \
  --query 'logStreams[0].lastEventTimestamp' \
  --output text)
echo "   Last run: $(date -d @$((last_invocation/1000)))"
echo ""

# 4. Golden set regression status
echo "4. Golden Set Status:"
aws s3 cp s3://aura-constitutional-ai-${ENV}/golden_set/latest_regression_report.json - 2>/dev/null | \
  jq '{pass_rate: .pass_rate, regressions: .regression_count, last_run: .timestamp}' || \
  echo "   No recent regression report found"

echo ""
echo "=== Health Check Complete ==="
```

### Incident Response Procedure

When CAI metrics enter Critical state:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAI INCIDENT RESPONSE RUNBOOK                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. ACKNOWLEDGE ALERT (within 15 min)                               │
│     - Check #aura-alerts Slack channel                              │
│     - Acknowledge in PagerDuty                                      │
│     - Open incident ticket                                          │
│           │                                                         │
│           ▼                                                         │
│  2. ASSESS IMPACT                                                   │
│     - Which metric(s) are critical?                                 │
│     - What percentage of traffic affected?                          │
│     - Any user complaints?                                          │
│           │                                                         │
│           ▼                                                         │
│  3. IMMEDIATE MITIGATION (if needed)                                │
│     - Consider increasing HITL coverage                             │
│       aws ssm put-parameter --name "/aura/${ENV}/autonomy_level"    │
│         --value "critical_hitl" --overwrite                         │
│     - This ensures human review of flagged content                  │
│           │                                                         │
│           ▼                                                         │
│  4. ROOT CAUSE ANALYSIS                                             │
│     - Run diagnostic commands from relevant section above           │
│     - Check for recent deployments: git log --oneline -10           │
│     - Check for principle/prompt changes                            │
│           │                                                         │
│           ▼                                                         │
│  5. IMPLEMENT FIX                                                   │
│     - Follow remediation steps from relevant section                │
│     - Deploy to staging first if possible                           │
│     - Use feature flags for gradual rollout                         │
│           │                                                         │
│           ▼                                                         │
│  6. VALIDATE FIX                                                    │
│     - Monitor metrics for 2-4 hours                                 │
│     - Confirm return to healthy thresholds                          │
│     - Run golden set regression check                               │
│           │                                                         │
│           ▼                                                         │
│  7. POST-INCIDENT                                                   │
│     - Update incident ticket with RCA                               │
│     - Add to evaluation dataset if appropriate                      │
│     - Schedule blameless retrospective if severity >= P2            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Monitoring and Alerting

### CloudWatch Alarms

The following alarms should be configured:

```yaml
# deploy/cloudformation/constitutional-ai-alarms.yaml (excerpt)
Resources:
  CritiqueAccuracyAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub 'aura-cai-critique-accuracy-${Environment}'
      AlarmDescription: Critique accuracy below target
      MetricName: CritiqueAccuracy
      Namespace: Aura/ConstitutionalAI
      Statistic: Average
      Period: 3600
      EvaluationPeriods: 3
      Threshold: 90
      ComparisonOperator: LessThanThreshold
      TreatMissingData: breaching
      AlarmActions:
        - !Ref AlertTopic

  RevisionConvergenceAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub 'aura-cai-revision-convergence-${Environment}'
      MetricName: RevisionConvergence
      Namespace: Aura/ConstitutionalAI
      Statistic: Average
      Period: 3600
      EvaluationPeriods: 3
      Threshold: 95
      ComparisonOperator: LessThanThreshold
      AlarmActions:
        - !Ref AlertTopic
```

### Dashboard Widgets

Key widgets for the CAI dashboard:

| Widget | Type | Purpose |
|--------|------|---------|
| Metric Health Overview | Gauge x 4 | Current state of all metrics |
| Trend Lines | Time Series | 7-day trends for each metric |
| Evaluation Volume | Number | Daily critique count |
| Cache Efficiency | Pie | Hit vs miss breakdown |
| Evasion Breakdown | Bar | Evasion types distribution |
| Golden Set Status | Single Value | Regression pass rate |
| Top Violated Principles | Table | Most common violations |
| P95 Latencies | Time Series | Critique and revision latency |

---

## Appendix: Key Files and Locations

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Critique Service | `src/services/constitutional_ai/critique_service.py` | Core critique logic |
| Revision Service | `src/services/constitutional_ai/revision_service.py` | Revision generation |
| Cache Service | `src/services/constitutional_ai/cache_service.py` | Semantic caching |
| Principles | `src/services/constitutional_ai/principles/` | Principle definitions |
| Prompts | `src/services/constitutional_ai/prompts/` | LLM prompt templates |
| Evaluation Lambda | `src/lambda/constitutional_evaluation/handler.py` | Nightly evaluation |
| Golden Set | `src/services/constitutional_ai/golden_set_service.py` | Regression testing |
| CloudFormation | `deploy/cloudformation/constitutional-ai-evaluation.yaml` | Infrastructure |
| Metrics Publisher | `src/services/constitutional_ai/cai_metrics_publisher.py` | CloudWatch metrics |

---

## Related Documentation

- [ADR-063: Constitutional AI Integration](../../architecture-decisions/ADR-063-constitutional-ai.md)
- [HITL Workflows](../../product/core-concepts/hitl-workflows.md)
- [Monitoring Guide](../operations/monitoring.md)
- [Performance Issues](./performance-issues.md)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Platform Team | Initial release |
