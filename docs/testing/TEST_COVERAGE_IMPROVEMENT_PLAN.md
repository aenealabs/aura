# Project Aura - Test Coverage Improvement Plan

**Target:** Achieve 80%+ overall test coverage
**Current Status:** ~30.62% (per user report) / ~3.72% on isolated module runs
**Assessment Date:** 2025-12-22
**Test Suite:** 10,027 tests (9,574 passing, 375 failing)

---

## Executive Summary

Project Aura currently has significant test coverage gaps across critical security, billing, and core agent services. This plan provides a phased approach to achieve 80%+ coverage while prioritizing business-critical functionality.

### Key Metrics

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Overall Coverage | ~31% | 80%+ | ~50% |
| Critical Security Services | ~5% | 90%+ | ~85% |
| Billing Services | ~40% | 95%+ | ~55% |
| Core Agent Framework | ~15% | 85%+ | ~70% |
| Data Layer Services | ~20% | 80%+ | ~60% |
| Transform Services | ~10% | 80%+ | ~70% |

### Estimated Effort

| Phase | Services | New Tests Est. | Weeks |
|-------|----------|----------------|-------|
| Phase 1: Critical | Security, Billing, Auth | ~400 tests | 3-4 |
| Phase 2: Core | Agents, LLM, Data | ~500 tests | 4-5 |
| Phase 3: Transform | Parsers, Translators | ~350 tests | 3-4 |
| Phase 4: Integration | Connectors, APIs | ~400 tests | 3-4 |
| Phase 5: Polish | Remaining gaps | ~200 tests | 2-3 |
| **Total** | | **~1,850 tests** | **15-20** |

---

## Phase 1: Critical Security & Revenue (Priority 1)

### 1.1 Authentication & Authorization

#### `src/api/auth.py` - Cognito JWT Authentication
- **Current Coverage:** ~0%
- **Target Coverage:** 95%
- **Estimated Tests:** 35-40

**Critical Test Scenarios:**
```python
# Unit Tests (Priority 1)
class TestCognitoAuthentication:
    """JWT validation and user extraction tests."""

    # Token validation
    def test_valid_jwt_token_extraction()
    def test_expired_jwt_token_rejection()
    def test_invalid_signature_rejection()
    def test_missing_token_returns_401()
    def test_malformed_token_returns_401()

    # User parsing
    def test_extract_user_from_valid_claims()
    def test_extract_groups_from_cognito_claims()
    def test_missing_sub_claim_rejection()

    # SSM configuration
    def test_load_config_from_ssm()
    def test_fallback_to_environment_variables()
    def test_config_caching_with_lru()

    # JWKS handling
    def test_fetch_jwks_keys()
    def test_jwks_key_rotation_handling()
    def test_network_failure_handling()

# Integration Tests
class TestAuthMiddleware:
    def test_protected_endpoint_with_valid_token()
    def test_protected_endpoint_without_token()
    def test_role_based_access_control()
```

**Mocking Pattern:**
```python
@pytest.fixture
def mock_cognito_jwks():
    """Mock JWKS endpoint response."""
    with patch('httpx.AsyncClient.get') as mock:
        mock.return_value = AsyncMock(json=lambda: MOCK_JWKS)
        yield mock
```

---

#### `src/services/a2as_security_service.py` - Agent-to-Agent Security
- **Current Coverage:** ~0%
- **Target Coverage:** 90%
- **Estimated Tests:** 50-60

**Critical Test Scenarios:**
```python
class TestA2ASSecurityService:
    # Agent authentication
    def test_agent_identity_verification()
    def test_agent_capability_validation()
    def test_agent_trust_score_calculation()
    def test_malicious_agent_detection()

    # Communication security
    def test_encrypted_message_exchange()
    def test_message_integrity_verification()
    def test_replay_attack_prevention()
    def test_man_in_middle_detection()

    # Authorization
    def test_agent_permission_enforcement()
    def test_resource_access_control()
    def test_privilege_escalation_prevention()

    # Audit logging
    def test_security_event_logging()
    def test_audit_trail_completeness()
```

---

#### `src/services/cedar_policy_engine.py` - Policy Engine
- **Current Coverage:** ~0%
- **Target Coverage:** 90%
- **Estimated Tests:** 40-45

**Critical Test Scenarios:**
```python
class TestCedarPolicyEngine:
    # Policy evaluation
    def test_allow_action_matching_policy()
    def test_deny_action_not_matching_policy()
    def test_principal_based_authorization()
    def test_resource_based_authorization()
    def test_condition_based_policies()

    # Policy management
    def test_policy_creation()
    def test_policy_update()
    def test_policy_deletion()
    def test_policy_conflict_resolution()

    # Edge cases
    def test_empty_policy_set()
    def test_circular_policy_references()
    def test_invalid_policy_syntax()
```

---

### 1.2 Billing & Revenue Services

#### `src/services/billing_service.py` - Subscription Billing
- **Current Coverage:** ~0% (existing tests cover model classes only)
- **Target Coverage:** 95%
- **Estimated Tests:** 60-70

**Critical Test Scenarios:**
```python
class TestSubscriptionLifecycle:
    # Creation
    async def test_create_subscription_success()
    async def test_create_subscription_with_trial()
    async def test_create_subscription_invalid_plan()
    async def test_create_duplicate_subscription()

    # Updates
    async def test_upgrade_subscription()
    async def test_downgrade_subscription()
    async def test_change_billing_cycle()
    async def test_update_payment_method()

    # Cancellation
    async def test_cancel_subscription_immediate()
    async def test_cancel_at_period_end()
    async def test_reactivate_canceled_subscription()

class TestUsageBilling:
    async def test_record_llm_token_usage()
    async def test_record_api_call_usage()
    async def test_usage_aggregation_monthly()
    async def test_overage_calculation()
    async def test_usage_limit_enforcement()

class TestInvoicing:
    async def test_generate_monthly_invoice()
    async def test_invoice_line_items()
    async def test_invoice_with_usage_charges()
    async def test_invoice_payment_status()
    async def test_invoice_history_retrieval()

class TestStripeIntegration:
    async def test_stripe_customer_creation()
    async def test_stripe_subscription_sync()
    async def test_stripe_webhook_handling()
    async def test_payment_failure_handling()
```

**Edge Cases (Security-Critical):**
```python
class TestBillingSecurityEdgeCases:
    async def test_subscription_tampering_prevention()
    async def test_invoice_amount_validation()
    async def test_unauthorized_plan_access()
    async def test_concurrent_subscription_updates()
```

---

#### `src/api/billing_endpoints.py` - Billing API
- **Current Coverage:** ~0%
- **Target Coverage:** 90%
- **Estimated Tests:** 30-35

**Critical Test Scenarios:**
```python
class TestBillingEndpoints:
    async def test_get_subscription_status()
    async def test_create_checkout_session()
    async def test_update_subscription_plan()
    async def test_cancel_subscription_endpoint()
    async def test_get_usage_summary()
    async def test_get_invoice_history()

    # Authorization tests
    async def test_subscription_access_authorization()
    async def test_admin_only_endpoints()
    async def test_cross_tenant_access_prevention()
```

---

### 1.3 Security Services

#### `src/services/security/pr_security_scanner.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 85%
- **Statements:** 575
- **Estimated Tests:** 45-50

**Critical Test Scenarios:**
```python
class TestPRSecurityScanner:
    # Vulnerability detection
    def test_detect_sql_injection()
    def test_detect_xss_vulnerabilities()
    def test_detect_command_injection()
    def test_detect_path_traversal()
    def test_detect_insecure_deserialization()

    # Secret detection
    def test_detect_api_keys()
    def test_detect_passwords()
    def test_detect_private_keys()
    def test_detect_aws_credentials()

    # Dependency scanning
    def test_scan_vulnerable_dependencies()
    def test_sbom_generation()

    # Reporting
    def test_generate_security_report()
    def test_severity_classification()
```

#### `src/services/input_validation_service.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 95%
- **Estimated Tests:** 30-35

```python
class TestInputValidation:
    # Injection prevention
    def test_sql_injection_sanitization()
    def test_nosql_injection_sanitization()
    def test_graph_injection_sanitization()
    def test_xss_prevention()
    def test_command_injection_prevention()

    # Format validation
    def test_email_validation()
    def test_url_validation()
    def test_uuid_validation()
    def test_json_schema_validation()

    # Boundary testing
    def test_max_length_enforcement()
    def test_unicode_handling()
    def test_null_byte_handling()
```

#### `src/services/llm_prompt_sanitizer.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 95%
- **Estimated Tests:** 25-30

```python
class TestPromptSanitizer:
    # Prompt injection prevention
    def test_detect_system_prompt_injection()
    def test_detect_jailbreak_attempts()
    def test_detect_role_confusion_attacks()
    def test_sanitize_user_input()

    # Output sanitization
    def test_prevent_pii_leakage()
    def test_prevent_secret_leakage()
    def test_content_filtering()
```

---

## Phase 2: Core Agent Framework & LLM Services (Priority 2)

### 2.1 Agent Orchestration

#### `src/agents/agent_orchestrator.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 85%
- **Statements:** 350
- **Estimated Tests:** 50-55

**Test Strategy:**
```python
class TestAgentOrchestrator:
    # Workflow orchestration
    async def test_vulnerability_detection_workflow()
    async def test_patch_generation_workflow()
    async def test_code_review_workflow()
    async def test_validation_workflow()

    # Agent coordination
    async def test_coder_reviewer_handoff()
    async def test_parallel_agent_execution()
    async def test_agent_failure_recovery()
    async def test_timeout_handling()

    # Context management
    async def test_context_sharing_between_agents()
    async def test_context_size_limits()
    async def test_hybrid_context_retrieval()

class TestInputSanitizer:
    def test_sanitize_for_graph_id()
    def test_empty_input_handling()
    def test_special_character_escaping()
    def test_max_length_enforcement()
```

#### `src/agents/meta_orchestrator.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 85%
- **Statements:** 400
- **Estimated Tests:** 55-60

```python
class TestMetaOrchestrator:
    # Task decomposition
    async def test_decompose_complex_task()
    async def test_task_prioritization()
    async def test_dependency_resolution()

    # Agent selection
    async def test_select_optimal_agents()
    async def test_agent_capability_matching()
    async def test_load_balancing()

    # Execution monitoring
    async def test_progress_tracking()
    async def test_resource_monitoring()
    async def test_failure_escalation()
```

#### `src/agents/coder_agent.py`, `reviewer_agent.py`, `validator_agent.py`
- **Current Coverage:** ~0-15%
- **Target Coverage:** 85%
- **Estimated Tests:** 40 each (120 total)

---

### 2.2 LLM & Memory Services

#### `src/services/bedrock_llm_service.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Statements:** 400
- **Estimated Tests:** 45-50

```python
class TestBedrockLLMService:
    # Model invocation
    async def test_invoke_claude_model()
    async def test_invoke_with_streaming()
    async def test_model_routing()
    async def test_fallback_model_selection()

    # Rate limiting
    async def test_rate_limit_handling()
    async def test_backoff_retry()
    async def test_concurrent_request_limits()

    # Error handling
    async def test_model_unavailable_error()
    async def test_context_length_exceeded()
    async def test_content_filter_triggered()

    # Token management
    async def test_token_counting()
    async def test_context_truncation()
    async def test_usage_tracking()
```

**Mocking Pattern:**
```python
@pytest.fixture
def mock_bedrock_client():
    with patch('boto3.client') as mock:
        client = MagicMock()
        client.invoke_model.return_value = {
            'body': StreamingBody(io.BytesIO(MOCK_RESPONSE), len(MOCK_RESPONSE))
        }
        mock.return_value = client
        yield client
```

#### `src/services/titan_memory_service.py`
- **Current Coverage:** 23%
- **Target Coverage:** 85%
- **Statements:** 326 (250 missing)
- **Estimated Tests:** 35-40 additional

```python
class TestTitanMemoryService:
    # Memory operations
    async def test_store_memory()
    async def test_retrieve_memory()
    async def test_memory_consolidation()
    async def test_memory_expiration()

    # Test-time training
    async def test_ttt_adaptation()
    async def test_surprise_detection()
    async def test_memorization_threshold()

    # Size management
    async def test_memory_size_limits()
    async def test_automatic_eviction()
```

#### `src/services/cognitive_memory_service.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Statements:** 600
- **Estimated Tests:** 50-55

---

### 2.3 Data Layer Services

#### `src/services/neptune_graph_service.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Statements:** 221
- **Estimated Tests:** 35-40

```python
class TestNeptuneGraphService:
    # Graph operations
    async def test_add_vertex()
    async def test_add_edge()
    async def test_query_by_id()
    async def test_graph_traversal()
    async def test_subgraph_extraction()

    # Connection management
    async def test_connection_pooling()
    async def test_reconnection_on_failure()
    async def test_transaction_rollback()

    # Query injection prevention
    async def test_gremlin_injection_prevention()
```

#### `src/services/opensearch_vector_service.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Estimated Tests:** 35-40

---

## Phase 3: Transform & Parsing Services (Priority 3)

### 3.1 Language Parsers

These services have the **largest coverage gaps** but are less immediately critical than security/billing.

#### `src/services/transform/cobol_parser.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Statements:** 728
- **Estimated Tests:** 55-60

```python
class TestCobolParser:
    # Parsing
    def test_parse_cobol_program()
    def test_parse_cobol_copybook()
    def test_parse_cobol_data_division()
    def test_parse_cobol_procedure_division()

    # AST generation
    def test_generate_ast()
    def test_extract_paragraphs()
    def test_extract_perform_statements()
    def test_extract_data_items()

    # Edge cases
    def test_parse_continuation_lines()
    def test_parse_nested_copy_statements()
    def test_parse_invalid_cobol()
```

#### `src/services/transform/dotnet_parser.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Statements:** 721
- **Estimated Tests:** 55-60

#### `src/services/transform/cross_language_translator.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 80%
- **Statements:** 605
- **Estimated Tests:** 50-55

```python
class TestCrossLanguageTranslator:
    # Translation
    async def test_cobol_to_python()
    async def test_dotnet_to_python()
    async def test_java_to_python()

    # Structure preservation
    async def test_preserve_business_logic()
    async def test_preserve_data_structures()
    async def test_preserve_error_handling()

    # Validation
    async def test_generated_code_syntax()
    async def test_generated_code_semantics()
```

---

## Phase 4: Integration & Connectors (Priority 4)

### 4.1 Enterprise Connectors

Each connector follows a similar testing pattern:

#### Connector Testing Template
```python
class TestEnterpriseConnector:
    # Connection
    async def test_connection_success()
    async def test_connection_failure_handling()
    async def test_authentication()
    async def test_retry_logic()

    # Operations
    async def test_create_resource()
    async def test_read_resource()
    async def test_update_resource()
    async def test_delete_resource()
    async def test_list_resources()

    # Error handling
    async def test_rate_limit_handling()
    async def test_timeout_handling()
    async def test_network_failure_recovery()
```

**Connectors to Test (30-40 tests each):**
- `servicenow_connector.py` - ServiceNow ITSM integration
- `splunk_connector.py` - Splunk SIEM integration
- `azure_devops_connector.py` - Azure DevOps integration
- `terraform_cloud_connector.py` - Terraform Cloud integration
- `qualys_connector.py` - Qualys vulnerability scanner
- `crowdstrike_connector.py` - CrowdStrike EDR integration
- `snyk_connector.py` - Snyk security scanning

**Mocking Pattern:**
```python
@pytest.fixture
def mock_servicenow_api():
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://instance.service-now.com/api/now/table/incident",
            json={"result": [...]},
            status=200
        )
        yield rsps
```

### 4.2 Ticketing Connectors

#### `src/services/ticketing/*.py`
- **Current Coverage:** ~0%
- **Target Coverage:** 85%
- **Total Estimated Tests:** 80-90

---

## Phase 5: Remaining Services & Polish (Priority 5)

### 5.1 Runbook Services

- `runbook_agent.py` - 30 tests
- `runbook_generator.py` - 25 tests
- `runbook_updater.py` - 20 tests
- `incident_detector.py` - 25 tests

### 5.2 DevOps Services

- `deployment_history_correlator.py` - 35 tests
- `incident_pattern_analyzer.py` - 35 tests
- `resource_topology_mapper.py` - 30 tests

### 5.3 Analytics & Monitoring

- `usage_analytics_service.py` - 25 tests
- `sla_monitoring_service.py` - 30 tests
- `observability_service.py` - 25 tests

---

## Testing Patterns & Best Practices

### 1. Use Existing Fixtures

The codebase has a comprehensive `conftest.py` with mocked AWS services:

```python
# Available fixtures in conftest.py
@pytest.fixture
def mock_aws_services(aws_credentials):
    """Comprehensive AWS service mocking."""
    with mock_aws():
        services = {
            "dynamodb": boto3.client("dynamodb", region_name=AWS_REGION),
            "s3": boto3.client("s3", region_name=AWS_REGION),
            "secretsmanager": boto3.client("secretsmanager", region_name=AWS_REGION),
            # ... more services
        }
        yield services
```

### 2. Module Isolation Pattern

For services with complex dependencies (like Titan Memory), use module isolation:

```python
# Save original modules before mocking
_modules_to_save = ['torch', 'src.services.memory_backends']
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock dependencies
mock_torch = MagicMock()
sys.modules["torch"] = mock_torch

# Import the module under test
from src.services.titan_memory_service import TitanMemoryService

# Restore original modules
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
```

### 3. Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    service = AsyncService()
    result = await service.do_something()
    assert result.status == "success"
```

### 4. Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated unit tests
│   ├── services/
│   ├── agents/
│   └── api/
├── integration/             # Service integration tests
│   ├── test_agent_flow.py
│   └── test_data_pipeline.py
├── security/                # Security-focused tests
│   ├── test_injection.py
│   └── test_auth.py
└── smoke/                   # Quick validation tests
    └── test_critical_paths.py
```

---

## Fix Failing Tests First

Before adding new tests, address the 375 failing tests:

### Priority Order for Fixing:
1. **Tests blocking CI/CD** - Critical path tests
2. **Flaky tests** - Non-deterministic failures
3. **Deprecated API usage** - `datetime.utcnow()` deprecation warnings
4. **Import errors** - Module loading issues
5. **Mock configuration** - Incorrect mock setups

### Common Fixes Needed:
```python
# Replace deprecated datetime.utcnow()
# OLD:
from datetime import datetime
now = datetime.utcnow()

# NEW:
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

---

## Coverage Monitoring

### CI/CD Integration

```yaml
# Add to buildspec or GitHub Actions
- name: Run Tests with Coverage
  run: |
    pytest tests/ \
      --cov=src \
      --cov-report=xml \
      --cov-report=html \
      --cov-fail-under=70  # Gradually increase

- name: Upload Coverage
  uses: codecov/codecov-action@v3
```

### Weekly Coverage Tracking

| Week | Target | Security | Billing | Core | Data | Transform |
|------|--------|----------|---------|------|------|-----------|
| 1 | 40% | 50% | 70% | 25% | 25% | 15% |
| 2 | 45% | 70% | 85% | 40% | 40% | 25% |
| 3 | 50% | 85% | 90% | 55% | 55% | 35% |
| 4 | 55% | 90% | 95% | 70% | 70% | 45% |
| ... | ... | ... | ... | ... | ... | ... |
| 12 | 80% | 95% | 95% | 90% | 85% | 85% |

---

## Appendix: Complete File List with Coverage Targets

### Critical Priority (95%+ Target)

| File | Current | Target | Tests Needed |
|------|---------|--------|--------------|
| src/api/auth.py | 0% | 95% | 40 |
| src/services/billing_service.py | 0% | 95% | 70 |
| src/services/input_validation_service.py | 0% | 95% | 35 |
| src/services/llm_prompt_sanitizer.py | 0% | 95% | 30 |
| src/services/a2as_security_service.py | 0% | 90% | 60 |
| src/services/cedar_policy_engine.py | 0% | 90% | 45 |
| **Subtotal** | | | **280** |

### High Priority (85%+ Target)

| File | Current | Target | Tests Needed |
|------|---------|--------|--------------|
| src/agents/agent_orchestrator.py | 0% | 85% | 55 |
| src/agents/meta_orchestrator.py | 0% | 85% | 60 |
| src/services/bedrock_llm_service.py | 0% | 80% | 50 |
| src/services/titan_memory_service.py | 23% | 85% | 40 |
| src/services/neptune_graph_service.py | 0% | 80% | 40 |
| src/services/security/*.py (4 files) | 0% | 85% | 160 |
| **Subtotal** | | | **405** |

### Medium Priority (80%+ Target)

| Category | Files | Tests Needed |
|----------|-------|--------------|
| Transform services | 5 | 250 |
| Enterprise connectors | 7 | 250 |
| Ticketing connectors | 6 | 90 |
| API endpoints | 10 | 200 |
| **Subtotal** | 28 | **790** |

### Lower Priority (75%+ Target)

| Category | Files | Tests Needed |
|----------|-------|--------------|
| DevOps services | 4 | 135 |
| Runbook services | 5 | 100 |
| Analytics/monitoring | 5 | 105 |
| Lambda handlers | 8 | 100 |
| Cloud providers | 10 | 150 |
| **Subtotal** | 32 | **590** |

---

## Conclusion

This plan provides a structured path to 80%+ test coverage:

1. **Weeks 1-4:** Focus on security and billing (highest business risk)
2. **Weeks 5-9:** Core agents and LLM services (foundational functionality)
3. **Weeks 10-14:** Transform and integration services
4. **Weeks 15-20:** Remaining coverage gaps and polish

**Key Success Factors:**
- Fix failing tests before adding new ones
- Prioritize business-critical paths
- Leverage existing fixtures and patterns
- Monitor coverage weekly
- Maintain test quality over quantity
