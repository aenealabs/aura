| Step | Directory Path        | File Name                     | Role / Purpose                                                                 |
|------|------------------------|--------------------------------|--------------------------------------------------------------------------------|
| 1    | .                      | .env                           | **Security:** Placeholder for external secrets (ignored by Git).               |
| 1    | .                      | requirements.txt                | **Engineering:** Lists Python dependencies for the backend.                    |
| 1    | .                      | setup_repo.sh                   | **DevOps:** Script to initialize Git and push the entire project securely.     |
| 2    | sample_project/         | main.py                         | **Codebase:** Sample file ingested and modified by the AI agents.              |
| 3    | src/agents/             | agent_orchestrator.py           | **Backend:** System 2 AI Control Plane and execution logic.                    |
| 3    | src/agents/             | monitoring_service.py           | **Backend:** Monitor Agent logic for executive metrics (Cost, Velocity, Quality). |
| 4    | src/tests/              | ckge_tests.py                   | **Testing:** Unit, Integration, and Security Tests (validates InputSanitizer). |
| 5    | frontend/               | CKGEConsole.jsx                 | **Frontend:** Complete React User Interface (Prompt submission & Report display). |
| 6    | deploy/ci/              | pipeline_config.yml             | **CI/CD:** AWS CodePipeline/CodeBuild definition, including security gates.    |
| 6    | deploy/fargate/         | fargate_task_definition.json    | **Deployment:** Secure Fargate Task Definition for microservices.              |
| 7    | docs/                   | technical_spec.md               | **Documentation:** Comprehensive Architecture, Data Flow, and Design.          |
| 7    | docs/                   | deployment_plan.md              | **Documentation:** AWS Deployment Checklist (Infrastructure and CI/CD).        |
| 7    | docs/                   | security_analysis.md            | **Documentation:** Initial Vulnerability Findings and Remediation Plan.        |
| 7    | docs/                   | metrics_dashboard.md            | **Documentation:** Executive Reporting Template (for Leadership Visibility).   |

---

# CKGE File Structure

This document outlines the full directory structure of the **Codebase Knowledge Graph Engine (CKGE)** project, including file purposes and organizational hierarchy.

---

## Root Directory

- `.gitignore`  
  *Security*: Ensures `.env` and IDE files are never committed.

- `.env`  
  *Security*: Placeholder for externalized secrets (e.g., AWS Secrets Manager).

- `setup_repo.sh`  
  *DevOps*: Script to initialize Git and push the entire project.

- `requirements.txt`  
  *Engineering*: List of required Python packages (e.g., `requests`, `networkx`, `mock`).

---

## Frontend

Directory: `frontend/` – The React User Interface

- `CKGEConsole.jsx`  
  The complete user-facing application (single-file mandate).

---

## Source Code

Directory: `src/` – Core Backend Logic (Microservices Simulation)

### Agents

Directory: `src/agents/` – Holds the primary, integrated agent logic

- `agent_orchestrator.py`  
  System 2 Orchestrator (main execution/control plane).

- `monitoring_service.py`  
  Monitor Agent logic for executive reporting.

### Tests

Directory: `src/tests/` – Testing and Validation Layer

- `ckge_tests.py`  
  Unit, integration, and security tests (validates `InputSanitizer`).

---

## Sample Project

Directory: `sample_project/` – Mock codebase for ingestion and modification

- `main.py`  
  Sample file analyzed by the AST Parser Agent.

---

## Deployment

Directory: `deploy/` – Deployment and infrastructure configuration

### Continuous Integration

Directory: `deploy/ci/`

- `pipeline_config.yml`  
  AWS CodePipeline/CodeBuild definition with security gates.

### Fargate

Directory: `deploy/fargate/`

- `fargate_task_definition.json`  
  Secure task definition for microservices.

---

## Documentation

Directory: `docs/` – Technical and executive documentation

- `technical_spec.md`  
  Comprehensive architecture and data flow.

- `deployment_plan.md`  
  Initial AWS GovCloud/Fargate deployment checklist.

- `security_analysis.md`  
  Initial vulnerability findings and remediation plan.

- `metrics_dashboard.md`  
  Executive report template for cost, velocity, and quality.

  ---
