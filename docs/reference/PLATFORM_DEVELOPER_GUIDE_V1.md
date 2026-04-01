# Aura Platform Developer Guide (Version 1.0)

## 1. Overview and Architecture

**Aura** is an autonomous code development platform powered by the **Codebase Knowledge Graph Engine (CKGE)**. CKGE provides **Infinite Code Context** through a hybrid graph-vector architecture, enabling Aura to autonomously generate production-ready code with built-in CMMC/FedRAMP compliance. The platform operates as a coordinated multi-agent microservice architecture.

### Key Architectural Concepts

* **Decoupled Agents:** All agents (`Planner`, `Coder`, `Reviewer`) are decoupled microservices (simulated by Python classes) designed for deployment on **AWS Fargate** (see `deploy/`).
* **Hybrid RAG:** Context retrieval fuses **Structural Context** (Dependencies from Neptune) with **Semantic Context** (Policies/Docs from OpenSearch vectors).
* **Auditable Flow:** The **Monitor Agent** tracks every step, providing metrics necessary for **SOX/CMMC audit trails**.

## 2. Security and Compliance

### A. Vulnerability Remediation by Design

The platform is hardened against common vulnerabilities found in AI code generation:

* **Graph Injection Prevention:** The `InputSanitizer` utility (in `src/agents/agent_orchestrator.py`) must be used for all inputs derived from external or untrusted sources (e.g., code entity names) before interacting with the Neptune or OpenSearch data stores.
* **Cryptographic Standards:** The **Reviewer Agent** enforces compliance by mandating secure standards (e.g., forcing **SHA256** adoption) before code is finalized.

### B. CI/CD Contribution Checklist

To contribute a new feature or fix to the Aura platform (CKGE):

1. **Code and Test:** Implement changes in Python and update **`requirements.txt`** if needed.
2. **Unit Test Coverage:** All new logic must achieve $100\%$ unit test coverage (e.g., in `src/tests/ckge_tests.py`).
3. **Run Integration Test:** Execute `python3 src/tests/ckge_tests.py` locally to verify the full multi-agent flow.
4. **Submit Pull Request (PR):** Target the `develop` branch.
5. **Pass Security Gates:** The PR merge will trigger the CI/CD pipeline, which must pass **SAST, SCA, and ECR Vulnerability Scans** before merging into `main`.

## 3. Data Flow and Persistence

### A. Data Stores

| Data Store | Role | Access Pattern |
| :--- | :--- | :--- |
| **Amazon Neptune** | Code Dependencies (Structural Graph) | Gremlin/OpenCypher queries executed by the **Context Retrieval Service**. |
| **OpenSearch** | Policy/Docs (Semantic Vectors) | **k-NN Search** for compliance and conceptual context. |
| **AWS CloudWatch/Timestream** | Metrics/Telemetry | Used by the **Monitor Agent** for cost and velocity tracking. |

### B. Scalability Considerations (Microservices)

The agents are currently simulated synchronously. For production, scale-out is achieved by:

* **Containerization:** Deploying each agent (Parser, Embedder, Coder) as dedicated **AWS Fargate** services.
* **Asynchronous Orchestration:** Replacing the Python loop with **AWS Step Functions** to manage long-running tasks and agent hand-offs.
