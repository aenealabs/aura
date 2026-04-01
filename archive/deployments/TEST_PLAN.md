# CKGE Platform Test Plan & Case Documentation

**Version:** 1.0  
**Status:** Active & Passing
**Total Test Cases:** 12

---

## 1. Overview

This document outlines the comprehensive test suite for the Codebase Knowledge Graph Engine (CKGE). The suite is designed to ensure the reliability, security, and correctness of the multi-agent autonomous development platform. It includes unit tests for individual components, a core logic test for the Hybrid RAG system, and a full end-to-end integration test.

All tests are located in `tests/ckge_tests.py` and are executed as a mandatory gate in the CI/CD pipeline (`deploy/ci/pipeline_config.yml`).

---

## 2. Test Case Inventory (Backend)

### 2.1. Unit Tests (7 Cases)

These tests validate the functionality of individual classes and methods in isolation.

| Test Case Name | Component Tested | Description |
| :--- | :--- | :--- |
| `test_security_input_sanitizer_graph_injection` | `InputSanitizer` | **(Security)** Verifies that inputs are sanitized to prevent Gremlin/OpenCypher injection attacks (VULN-CKGE-001). |
| `test_security_input_sanitizer_edge_cases` | `InputSanitizer` | **(Security)** Ensures the sanitizer correctly handles null, empty, and overly long strings. |
| `test_graph_builder_agent_node_and_edge_creation` | `GraphBuilderAgent` | Verifies that the agent correctly parses mock code to create the expected nodes and labels in the knowledge graph. |
| `test_monitor_agent_activity_recording` | `MonitorAgent` | Verifies that agent token usage and lines of code generated are correctly aggregated. |
| `test_monitor_agent_security_finding` | `MonitorAgent` | Confirms that security findings logged by agents are correctly recorded. |
| `test_monitor_agent_finalize_report` | `MonitorAgent` | Ensures the final executive report correctly calculates cost, hours saved, and vulnerability counts. |
| `test_embedding_agent_chunking` | `EmbeddingAgent` | Validates the basic logic of the agent, ensuring it handles content of appropriate length for embedding. |

### 2.2. Hybrid Retrieval & Edge Case Tests (2 Cases)

This test focuses on the core intelligence of the platform's context retrieval mechanism.

| Test Case Name | Component Tested | Description |
| :--- | :--- | :--- |
| `test_context_retrieval_service_hybrid_fusion` | `ContextRetrievalService` | **(Core Logic)** Validates that the GraphRAG system successfully fuses structural context (from the graph) and semantic context (from the vector store). |
| `test_context_retrieval_with_unknown_entity` | `ContextRetrievalService` | **(Edge Case)** Verifies the system handles queries for non-existent entities gracefully, preventing crashes. |

### 2.3. System Integration Tests (3 Cases)

This end-to-end test simulates the entire autonomous workflow.

| Test Case Name | Component Tested | Description |
| :--- | :--- | :--- |
| `test_system2_orchestrator_autonomous_remediation` | `System2Orchestrator` | **(E2E Workflow)** Simulates the full multi-agent loop, verifying the system can autonomously detect a vulnerability (insecure `sha1`), self-correct using a retrieved policy, and produce secure code (`sha256`). |
| `test_orchestrator_remediation_failure` | `System2Orchestrator` | **(Failure Path)** Ensures the orchestrator fails gracefully and reports failure if it cannot fix a vulnerability after multiple attempts. |
| `test_validator_agent_with_invalid_code` | `System2Orchestrator` | **(Validation Logic)** Confirms the `_validator_agent` correctly identifies and rejects syntactically invalid code. |
