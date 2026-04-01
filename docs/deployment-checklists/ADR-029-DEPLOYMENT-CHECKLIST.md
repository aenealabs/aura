# ADR-029 Incremental Deployment Checklist

**Purpose:** Deploy ADR-029 Agent Optimization features incrementally to mitigate risk and simplify troubleshooting.

**Created:** Dec 8, 2025
**Updated:** Dec 15, 2025 (Added Phase 3: Agent0 Self-Evolving Agents)
**Status:** Ready for deployment (Phases 1-2), Phase 3 planned for H2 2026

---

## Deployment Philosophy

Each phase should be deployed and validated independently before proceeding to the next:
1. Deploy one feature at a time
2. Run integration tests after each deployment
3. Monitor for 24-48 hours before next deployment
4. Document any issues encountered

---

## Phase 1: Quick Wins (40-70% LLM Cost Reduction)

### 1.1 Bedrock Guardrails Automated Reasoning

**Commit:** Part of Phase 1 series
**Priority:** HIGH (security-critical)

**What it does:**
- Content filtering (hate, violence, prompt attacks)
- PII protection (SSN, credit cards, API keys)
- Topic blocking (malware, social engineering)

**Files to deploy:**
- `deploy/cloudformation/bedrock-guardrails.yaml` - CloudFormation stack
- `src/config/guardrails_config.py` - Configuration module
- `src/services/bedrock_llm_service.py` - Integration (already deployed, needs guardrail params)

**Deployment steps:**
```bash
# 1. Deploy CloudFormation stack (if not already deployed)
aws cloudformation deploy \
  --template-file deploy/cloudformation/bedrock-guardrails.yaml \
  --stack-name aura-bedrock-guardrails-dev \
  --parameter-overrides Environment=dev ProjectName=aura

# 2. Verify guardrail creation
aws bedrock get-guardrail --guardrail-identifier $(aws ssm get-parameter --name /aura/dev/bedrock-guardrail-id --query Parameter.Value --output text)

# 3. Run guardrail tests
pytest tests/test_guardrails_config.py -v
```

**Validation:**
- [ ] CloudFormation stack deployed successfully
- [ ] Guardrail ID stored in SSM Parameter Store
- [ ] LLM requests are being filtered (check CloudWatch logs)
- [ ] No false positives blocking legitimate requests

**Rollback:** Set `GUARDRAILS_ENABLED=false` environment variable or delete stack

---

### 1.2 Chain of Draft (CoD) Prompting

**Commit:** Part of Phase 1 series
**Priority:** MEDIUM (cost optimization)

**What it does:**
- 92% token reduction vs Chain of Thought
- Minimalist reasoning prompts (1-5 words per step)

**Files to deploy:**
- `src/prompts/cod_templates.py` - CoD/CoT templates
- `src/prompts/ab_testing.py` - A/B testing framework
- Agent integrations already in place (reviewer, coder, validator, query_planner)

**Deployment steps:**
```bash
# 1. Deploy updated agent code (container rebuild)
# CoD is enabled by default, controlled by AURA_PROMPT_MODE env var

# 2. Run CoD tests
pytest tests/test_cod_templates.py -v

# 3. Monitor token usage
# Check CloudWatch metrics for token consumption reduction
```

**Environment variables:**
- `AURA_PROMPT_MODE=cod` - Use Chain of Draft (default)
- `AURA_PROMPT_MODE=cot` - Use Chain of Thought (fallback)
- `AURA_PROMPT_MODE=auto` - Auto-select based on task complexity

**Validation:**
- [ ] Token usage reduced by ~90% in CloudWatch metrics
- [ ] Response quality maintained (spot check outputs)
- [ ] A/B test framework capturing comparison data

**Rollback:** Set `AURA_PROMPT_MODE=cot` to revert to Chain of Thought

---

### 1.3 Semantic Caching

**Commit:** Part of Phase 1 series
**Priority:** MEDIUM (cost optimization)

**What it does:**
- 60-70% cache hit rate for similar queries
- OpenSearch k-NN with 0.92 similarity threshold
- Query-type-specific TTLs

**Files to deploy:**
- `src/services/semantic_cache_service.py` - Cache service
- `src/services/bedrock_llm_service.py` - Integration (already has cache support)

**Prerequisites:**
- OpenSearch cluster must be running
- k-NN plugin enabled on OpenSearch

**Deployment steps:**
```bash
# 1. Create semantic cache index in OpenSearch
# (Index created automatically on first cache write)

# 2. Run semantic cache tests
pytest tests/test_semantic_cache_service.py -v

# 3. Enable cache in production
# Set SEMANTIC_CACHE_MODE=read_write in environment
```

**Environment variables:**
- `SEMANTIC_CACHE_MODE=disabled` - No caching
- `SEMANTIC_CACHE_MODE=write_only` - Populate cache only
- `SEMANTIC_CACHE_MODE=read_write` - Full caching (production)
- `SEMANTIC_CACHE_MODE=read_only` - Read from cache, don't write

**Validation:**
- [ ] Cache index created in OpenSearch
- [ ] Cache hit rate >50% after warm-up period
- [ ] Response latency reduced for cache hits
- [ ] No stale responses (TTL working correctly)

**Rollback:** Set `SEMANTIC_CACHE_MODE=disabled`

---

### 1.4 MCP Tool Server

**Commit:** `043abd7`
**Priority:** MEDIUM (standardization)

**What it does:**
- Industry-standard MCP protocol for tool access
- 7 internal tools exposed via MCP
- HITL approval for sensitive operations

**Files to deploy:**
- `src/services/mcp_tool_server.py` - MCP server
- `src/agents/base_agent.py` - Base agent with MCP support

**Deployment steps:**
```bash
# 1. Deploy updated agent containers
# MCP server starts automatically with agent orchestrator

# 2. Run MCP tests
pytest tests/test_mcp_tool_server.py tests/test_base_agent.py -v

# 3. Verify tool registration
# Check logs for "MCP server initialized with X tools"
```

**Validation:**
- [ ] MCP server starts without errors
- [ ] All 7 tools registered and accessible
- [ ] HITL approval triggered for sandbox operations
- [ ] Tool statistics being recorded

**Rollback:** Set `MCP_ENABLED=false` environment variable

---

## Phase 2: Strategic Enhancements (Accuracy & Security)

### 2.1 Titan Memory Integration

**Commit:** `e359ce4`
**Priority:** LOW (enhancement)

**What it does:**
- 2M+ token effective context via neural memory
- Surprise-driven memorization for learning
- Memory-informed code generation and review

**Files to deploy:**
- `src/agents/context_objects.py` - NEURAL_MEMORY source
- `src/agents/agent_orchestrator.py` - Memory workflow integration
- `src/agents/coder_agent.py` - Memory guidance
- `src/agents/reviewer_agent.py` - Memory-informed review

**Prerequisites:**
- TitanCognitiveService from ADR-024 must be deployed
- Neural memory index in OpenSearch

**Deployment steps:**
```bash
# 1. Ensure TitanCognitiveService is available
# (Check for /aura/dev/titan-memory-endpoint SSM parameter)

# 2. Run Titan memory tests
pytest tests/test_titan_memory_integration.py -v

# 3. Enable memory in orchestrator
# Set TITAN_MEMORY_ENABLED=true in environment
```

**Validation:**
- [ ] NEURAL_MEMORY context items appearing in agent inputs
- [ ] Memory episodes being recorded after successful tasks
- [ ] Neural confidence scores being passed to agents
- [ ] No performance degradation from memory lookups

**Rollback:** Set `TITAN_MEMORY_ENABLED=false`

---

### 2.2 Self-Reflection for Reviewer

**Commit:** `715b4f7`
**Priority:** MEDIUM (quality improvement)

**What it does:**
- Reflexion-style self-critique loop
- 30% fewer false positives expected
- Configurable iterations and confidence threshold

**Files to deploy:**
- `src/agents/reflection_module.py` - Reflection module
- `src/agents/reviewer_agent.py` - Reflection integration

**Deployment steps:**
```bash
# 1. Run reflection tests
pytest tests/test_reflection_module.py -v

# 2. Enable reflection in reviewer
# Set REVIEWER_REFLECTION_ENABLED=true in environment
```

**Configuration:**
- `REVIEWER_REFLECTION_ENABLED=true/false` - Enable/disable reflection
- `REFLECTION_MAX_ITERATIONS=3` - Max self-critique iterations
- `REFLECTION_CONFIDENCE_THRESHOLD=0.9` - Confidence to stop iterating

**Validation:**
- [ ] Reflection iterations appearing in review results
- [ ] Confidence scores improving across iterations
- [ ] False positive rate reduced (compare before/after)
- [ ] Token usage increase acceptable (~1500 tokens/reflection)

**Rollback:** Set `REVIEWER_REFLECTION_ENABLED=false`

---

### 2.3 A2AS Security Framework

**Commit:** `92a8596`
**Priority:** HIGH (security-critical)

**What it does:**
- Four-layer defense for agent-to-agent communication
- 95%+ injection detection rate
- HITL escalation for critical threats

**Files to deploy:**
- `src/services/a2as_security_service.py` - Security service

**Deployment steps:**
```bash
# 1. Run A2AS security tests
pytest tests/security/test_a2as_framework.py -v

# 2. Enable A2AS in agent orchestrator
# Set A2AS_SECURITY_ENABLED=true in environment

# 3. Configure command signing secret
aws ssm put-parameter \
  --name /aura/dev/a2as-signing-secret \
  --value "$(openssl rand -hex 32)" \
  --type SecureString
```

**Configuration:**
- `A2AS_SECURITY_ENABLED=true/false` - Enable/disable A2AS
- `A2AS_SIGNING_SECRET` - HMAC signing key (from SSM)
- `A2AS_HITL_THRESHOLD=HIGH` - Threat level requiring HITL approval

**Validation:**
- [ ] Command signing working (check signatures in logs)
- [ ] Injection attempts being blocked (test with known patterns)
- [ ] HITL escalation triggered for HIGH/CRITICAL threats
- [ ] No false positives blocking legitimate agent communication

**Rollback:** Set `A2AS_SECURITY_ENABLED=false`

---

## Phase 3: Self-Evolving Agents (H2 2026)

**Status:** Planned (depends on Phases 1-2 completion)
**See:** ADR-029 v2.0 for full implementation details

### 3.1 Agent0 Curriculum Learning Integration

**What it does:**
- Symbiotic agent competition (Curriculum Agent + Executor Agent)
- Tool-integrated reasoning for sophisticated security challenges
- Self-reinforcing learning cycle without model fine-tuning
- Inference-only approach for GovCloud/FedRAMP compliance
- Expected outcome: 18-24% accuracy improvement on security remediation tasks

**Sub-Phases:**
- Phase 3.1: Curriculum Agent Foundation (Q3 2026) - 3-4 sprints
- Phase 3.2: Executor Integration (Q3 2026) - 2-3 sprints
- Phase 3.3: Competition Loop (Q4 2026) - 3-4 sprints
- Phase 3.4: Production Hardening (Q4 2026) - 2 sprints

**Prerequisites:**
- [ ] Phase 1 complete (MCP, Guardrails, CoD, Semantic Caching)
- [ ] Phase 2 complete (TitanMemory, Self-Reflection, A2AS)

**Security Considerations:**
- New threat vector: Curriculum poisoning attacks
- Mitigations: A2AS validation, domain boundaries, difficulty caps, HITL for high-risk tasks

**Files to create (planned):**
- `src/agents/curriculum_agent.py` - Curriculum task generation
- `src/agents/secure_curriculum_validator.py` - Security validation
- `src/services/task_difficulty_estimator.py` - Complexity scoring
- `src/services/agent0_memory_bridge.py` - TitanMemory integration
- `src/services/skill_profiler.py` - Agent skill tracking
- `src/agents/competition_orchestrator.py` - Symbiotic loop coordination
- `deploy/cloudformation/agent0-monitoring.yaml` - CloudWatch dashboards/alarms

**Environment variables (planned):**
- `AGENT0_ENABLED=true/false` - Enable/disable curriculum learning
- `AGENT0_MAX_DIFFICULTY=0.85` - Cap task difficulty
- `AGENT0_HITL_THRESHOLD=0.8` - Difficulty requiring HITL approval

---

## Recommended Deployment Order

Deploy in this order to minimize risk:

| Order | Feature | Risk Level | Dependencies |
|-------|---------|------------|--------------|
| 1 | Bedrock Guardrails (1.1) | Low | None |
| 2 | A2AS Security (2.3) | Low | None |
| 3 | Semantic Caching (1.3) | Low | OpenSearch |
| 4 | CoD Prompting (1.2) | Low | None |
| 5 | MCP Tool Server (1.4) | Medium | None |
| 6 | Self-Reflection (2.2) | Medium | None |
| 7 | Titan Memory (2.1) | Medium | ADR-024 TitanCognitiveService |
| 8 | Agent0 Curriculum Learning (3.1) | High | Phases 1-2 complete |

**Rationale:**
- Security features first (Guardrails, A2AS)
- Cost optimization next (Caching, CoD)
- Enhancements (MCP, Reflection, Memory)
- Self-evolving capabilities last (Agent0) - requires stable foundation

---

## Monitoring Checklist

After each deployment, monitor:

- [ ] CloudWatch error rate (should not increase)
- [ ] CloudWatch latency (should not increase significantly)
- [ ] Bedrock token usage (should decrease with CoD/caching)
- [ ] Application logs for new errors
- [ ] HITL approval queue (should not be overwhelmed)

---

## Quick Reference: Environment Variables

```bash
# Phase 1
GUARDRAILS_ENABLED=true
AURA_PROMPT_MODE=cod
SEMANTIC_CACHE_MODE=read_write
MCP_ENABLED=true

# Phase 2
TITAN_MEMORY_ENABLED=true
REVIEWER_REFLECTION_ENABLED=true
A2AS_SECURITY_ENABLED=true
A2AS_HITL_THRESHOLD=HIGH

# Phase 3 (H2 2026 - Planned)
AGENT0_ENABLED=true
AGENT0_MAX_DIFFICULTY=0.85
AGENT0_HITL_THRESHOLD=0.8
```

---

## Notes

- All features have feature flags for easy rollback
- Run full test suite after each deployment: `pytest tests/ -v`
- Check CloudWatch dashboards for anomalies
- Keep this checklist updated as deployments progress
