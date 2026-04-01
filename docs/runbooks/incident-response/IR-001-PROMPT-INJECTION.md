# IR-001: Prompt Injection Incident Response Playbook

**Version:** 1.0
**Last Updated:** January 25, 2026
**Owner:** Security Team
**Classification:** Public

---

## 1. Overview

### 1.1 Purpose
This playbook provides step-by-step procedures for detecting, containing, and remediating prompt injection attacks against Project Aura's AI/ML systems.

### 1.2 Scope
Applies to all prompt injection incidents affecting:
- Bedrock LLM integrations
- Agent Orchestrator (Coder, Reviewer, Validator agents)
- Context Retrieval Service
- RLM (Recursive Language Model) REPL
- Customer-facing chat interfaces

### 1.3 MITRE ATT&CK Mapping
| Technique | ID | Description |
|-----------|-----|-------------|
| Command and Scripting Interpreter | T1059 | Execution via injected prompts |
| Exploitation for Defense Evasion | T1211 | Bypassing content filters |
| Data Manipulation | T1565 | Modifying LLM outputs |

---

## 2. Severity Classification

| Severity | Criteria | Response Time |
|----------|----------|---------------|
| **Critical** | Successful jailbreak with data exfiltration or code execution | Immediate (< 15 min) |
| **High** | Successful bypass of content filters with harmful output | < 1 hour |
| **Medium** | Detected injection attempt blocked by guardrails | < 4 hours |
| **Low** | Failed injection attempt with no impact | < 24 hours |

---

## 3. Detection

### 3.1 Detection Sources

| Source | Alert Type | SNS Topic |
|--------|------------|-----------|
| Bedrock Guardrails | PROMPT_ATTACK filter triggered | `aura-security-alerts-{env}` |
| InputSanitizer | Injection pattern detected | `aura-security-alerts-{env}` |
| LLMPromptSanitizer | Jailbreak attempt blocked | `aura-security-alerts-{env}` |
| CloudWatch Logs | Anomalous token patterns | `aura-critical-anomalies-{env}` |
| SecurityAuditService | `PROMPT_INJECTION_ATTEMPT` event | `aura-iam-security-alerts-{env}` |

### 3.2 Indicators of Compromise (IOCs)

**Input Patterns:**
- "Ignore previous instructions"
- "You are now DAN" / "Developer mode"
- Delimiter injection: `Human:`, `Assistant:`, `<|system|>`
- Base64/ROT13 encoded instructions
- Zero-width characters or hidden Unicode
- Markdown/HTML comment injection

**Behavioral Indicators:**
- Unusual output length or format
- Output containing system prompt fragments
- Code execution outside sandbox
- Unauthorized API calls from agent
- Anomalous token consumption spike

### 3.3 Log Queries

**CloudWatch Insights - Detect Injection Attempts:**
```
fields @timestamp, @message, user_id, input_hash
| filter @message like /(?i)(ignore.*instruction|you are now|DAN mode|jailbreak)/
| sort @timestamp desc
| limit 100
```

**CloudWatch Insights - Guardrail Blocks:**
```
fields @timestamp, guardrail_id, action, input_tokens
| filter action = "BLOCKED" and filter_type = "PROMPT_ATTACK"
| stats count() by bin(1h)
```

---

## 4. Containment

### 4.1 Immediate Actions (First 15 Minutes)

| Step | Action | Owner | Command/Tool |
|------|--------|-------|--------------|
| 1 | Verify alert authenticity | On-Call Engineer | Review CloudWatch logs |
| 2 | Identify affected user/session | On-Call Engineer | `aws logs filter-log-events` |
| 3 | Block user session (if malicious) | On-Call Engineer | Cognito: Disable user |
| 4 | Isolate affected agent instance | On-Call Engineer | ECS: Stop task |
| 5 | Preserve evidence | On-Call Engineer | Export logs to S3 |

### 4.2 Session Termination

**Disable User in Cognito:**
```bash
aws cognito-idp admin-disable-user \
  --user-pool-id ${USER_POOL_ID} \
  --username ${USERNAME}
```

**Invalidate All User Sessions:**
```bash
aws cognito-idp admin-user-global-sign-out \
  --user-pool-id ${USER_POOL_ID} \
  --username ${USERNAME}
```

### 4.3 Agent Isolation

**Stop Affected ECS Task:**
```bash
aws ecs stop-task \
  --cluster aura-agents-${ENV} \
  --task ${TASK_ARN} \
  --reason "Security incident containment"
```

**Scale Down Agent Service (if widespread):**
```bash
aws ecs update-service \
  --cluster aura-agents-${ENV} \
  --service ${SERVICE_NAME} \
  --desired-count 0
```

### 4.4 Evidence Preservation

**Export CloudWatch Logs:**
```bash
aws logs create-export-task \
  --task-name "IR-$(date +%Y%m%d)-prompt-injection" \
  --log-group-name "/aura/${ENV}/agents" \
  --from $(date -d '1 hour ago' +%s)000 \
  --to $(date +%s)000 \
  --destination "aura-security-forensics-${ENV}"
```

---

## 5. Eradication

### 5.1 Root Cause Analysis

| Question | Investigation Method |
|----------|---------------------|
| How did the injection bypass defenses? | Review InputSanitizer/Guardrail logs |
| What was the attack vector? | Analyze input payload |
| Was the attack automated or manual? | Check request patterns, IP analysis |
| What data was potentially accessed? | Review agent actions and outputs |
| Are other users affected? | Query for similar patterns |

### 5.2 Defense Updates

**Add New Detection Pattern to InputSanitizer:**

File: `src/services/rlm/input_sanitizer.py`
```python
# Add to INJECTION_PATTERNS list
r"<new_pattern_here>",
```

**Update Bedrock Guardrails:**
```bash
aws bedrock update-guardrail \
  --guardrail-identifier ${GUARDRAIL_ID} \
  --blocked-input-messaging "Request blocked for security" \
  --content-policy-config file://updated-policy.json
```

### 5.3 Validation

**Test New Defenses:**
```bash
# Run adversarial test suite
pytest tests/security/test_prompt_injection.py -v --tb=short

# Verify pattern detection
python -c "
from src.services.rlm.input_sanitizer import InputSanitizer
sanitizer = InputSanitizer()
result = sanitizer.sanitize('<test_payload>')
print(f'Blocked: {result.is_blocked}')
"
```

---

## 6. Recovery

### 6.1 Service Restoration

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Deploy patched InputSanitizer | Unit tests pass |
| 2 | Update Guardrail configuration | AWS console verification |
| 3 | Scale agent service back up | Health checks pass |
| 4 | Re-enable affected users (if appropriate) | Manual review |
| 5 | Monitor for recurrence | CloudWatch dashboard |

### 6.2 User Communication

**If customer-facing impact occurred:**
- Notify affected users within 24 hours
- Provide incident summary (without attack details)
- Offer password reset if credentials potentially exposed
- Document notification in incident record

---

## 7. Post-Incident Activities

### 7.1 Incident Report

Complete within 72 hours:
- [ ] Timeline of events
- [ ] Root cause analysis
- [ ] Impact assessment
- [ ] Actions taken
- [ ] Lessons learned
- [ ] Recommendations

### 7.2 Metrics to Track

| Metric | Target |
|--------|--------|
| Time to Detection (TTD) | < 5 minutes |
| Time to Containment (TTC) | < 15 minutes |
| Time to Eradication (TTE) | < 4 hours |
| Time to Recovery (TTR) | < 8 hours |

### 7.3 Follow-Up Actions

- [ ] Update threat model with new attack vector
- [ ] Add detection pattern to monitoring
- [ ] Schedule team retrospective
- [ ] Update this playbook if needed
- [ ] Brief leadership on incident

---

## 8. Escalation Matrix

| Severity | Primary | Secondary | Executive |
|----------|---------|-----------|-----------|
| Critical | On-Call Engineer | Security Lead | CTO (within 1 hour) |
| High | On-Call Engineer | Security Lead | CTO (within 4 hours) |
| Medium | On-Call Engineer | Security Lead | Weekly report |
| Low | On-Call Engineer | - | Monthly report |

### Contact Information

| Role | Contact | Method |
|------|---------|--------|
| On-Call Engineer | PagerDuty | `aura-oncall` rotation |
| Security Lead | security@aenealabs.com | Email + Slack |
| CTO | cto@aenealabs.com | Phone for Critical |
| AWS Support | Enterprise Support | AWS Console |

---

## 9. Related Runbooks

- [IR-002: GraphRAG Context Poisoning](./IR-002-GRAPHRAG-POISONING.md)
- [IR-003: Credential Exposure](./IR-003-CREDENTIAL-EXPOSURE.md)
- [IR-004: Sandbox Escape](./IR-004-SANDBOX-ESCAPE.md)
- [IR-005: Data Leakage via LLM](./IR-005-DATA-LEAKAGE.md)

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-25 | Security Team | Initial version |

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│           PROMPT INJECTION INCIDENT - QUICK REFERENCE       │
├─────────────────────────────────────────────────────────────┤
│ 1. VERIFY    - Check CloudWatch logs for alert context      │
│ 2. IDENTIFY  - Find affected user/session/agent             │
│ 3. CONTAIN   - Disable user, stop agent task                │
│ 4. PRESERVE  - Export logs to forensics bucket              │
│ 5. ANALYZE   - Determine attack vector and impact           │
│ 6. PATCH     - Update detection patterns                    │
│ 7. TEST      - Run adversarial test suite                   │
│ 8. RESTORE   - Scale services back up                       │
│ 9. REPORT    - Complete incident report within 72h          │
├─────────────────────────────────────────────────────────────┤
│ CRITICAL: Escalate to Security Lead + CTO within 15 min     │
│ SNS Topic: aura-security-alerts-{env}                       │
│ PagerDuty: aura-oncall                                      │
└─────────────────────────────────────────────────────────────┘
```
