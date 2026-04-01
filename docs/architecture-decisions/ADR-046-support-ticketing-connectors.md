# ADR-046: Support Ticketing Connectors Architecture

**Status:** Deployed
**Date:** 2025-12-20 | **Deployed:** 2025-12-31
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-043 (Repository Onboarding Wizard), ADR-037 (AWS Agent Capability)

---

## Executive Summary

This ADR documents the decision to implement a pluggable support ticketing system that natively supports GitHub Issues while providing an extensible connector interface for enterprise ticketing platforms (Zendesk, Linear, ServiceNow).

**Key Outcomes:**
- Abstract `TicketingConnector` interface for provider-agnostic ticket operations
- `GitHubIssuesConnector` as the primary, fully-implemented connector
- Stub implementations for Zendesk, Linear, and ServiceNow (future)
- UI-configurable ticketing settings in the Aura Settings page
- DynamoDB tables for configuration and ticket mapping

---

## Context

### Current State

Project Aura requires a customer support infrastructure to handle tickets, issue tracking, and SLA management at scale.

Current support capabilities:
- No formal ticketing system
- Manual support via email
- No integration with enterprise ticketing platforms
- No audit trail for support interactions

### Problem Statement

1. **Customer Expectation:** Enterprise customers expect integrated support ticketing
2. **Flexibility Requirement:** Customers may already use Zendesk, Linear, or ServiceNow
3. **Audit Trail:** Support interactions must be tracked for compliance (CMMC, SOX)
4. **Self-Hosted Customers:** Must work in isolated VPCs without SaaS dependencies

### Requirements

1. **Native GitHub Issues Support:** Free, no additional licensing, works in air-gapped environments
2. **Enterprise Connector Interface:** Abstract interface for Zendesk, Linear, ServiceNow
3. **UI Configuration:** Admin UI to select provider and configure credentials
4. **Secure Credential Storage:** OAuth tokens/API keys in Secrets Manager
5. **Bi-directional Sync:** Tickets created in Aura reflect in external systems
6. **Audit Logging:** All ticketing operations logged for compliance

---

## Decision

**Implement a pluggable ticketing connector architecture with GitHub Issues as the primary connector and abstract interfaces for enterprise platforms.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SUPPORT TICKETING ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │   Frontend (React)               │
                    │   /settings/ticketing            │
                    │                                  │
                    │   ┌──────────────────────────┐   │
                    │   │ TicketingSettings.jsx    │   │
                    │   │ - Provider selection     │   │
                    │   │ - Credential config      │   │
                    │   │ - Test connection        │   │
                    │   │ - Default labels         │   │
                    │   └──────────────────────────┘   │
                    └──────────────┬───────────────────┘
                                   │ REST API
                                   ▼
                    ┌──────────────────────────────────┐
                    │   Backend (FastAPI)              │
                    │   /api/v1/ticketing/*            │
                    │                                  │
                    │   ┌──────────────────────────┐   │
                    │   │ ticketing_endpoints.py   │   │
                    │   │ - POST /tickets          │   │
                    │   │ - GET /tickets/{id}      │   │
                    │   │ - PUT /tickets/{id}      │   │
                    │   │ - POST /config           │   │
                    │   │ - GET /config            │   │
                    │   └──────────────────────────┘   │
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────┐
                    │   Connector Factory              │
                    │   connector_factory.py           │
                    │                                  │
                    │   get_connector(provider) →      │
                    └──────────────┬───────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ GitHub Issues   │ │ Zendesk         │ │ Linear          │
    │ Connector       │ │ Connector       │ │ Connector       │
    │ (Implemented)   │ │ (Stub)          │ │ (Stub)          │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ GitHub API      │ │ Zendesk API     │ │ Linear GraphQL  │
    │ REST v3         │ │ REST            │ │ API             │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Component Details

#### 1. Base Connector Interface (`base_connector.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from datetime import datetime

class TicketPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"

@dataclass
class TicketCreate:
    title: str
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM
    labels: List[str] = None
    assignee: Optional[str] = None
    metadata: dict = None

@dataclass
class Ticket:
    id: str
    external_id: str  # ID in external system (GitHub issue number, etc.)
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    labels: List[str]
    assignee: Optional[str]
    created_at: datetime
    updated_at: datetime
    external_url: str  # Link to ticket in external system
    metadata: dict

@dataclass
class TicketResult:
    success: bool
    ticket: Optional[Ticket]
    error_message: Optional[str] = None

class TicketingConnector(ABC):
    """Abstract base class for ticketing system connectors."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (github, zendesk, linear, servicenow)."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connector can reach the external system."""
        pass

    @abstractmethod
    async def create_ticket(self, ticket: TicketCreate) -> TicketResult:
        """Create a new ticket in the external system."""
        pass

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Retrieve a ticket by ID."""
        pass

    @abstractmethod
    async def update_ticket(self, ticket_id: str, updates: dict) -> TicketResult:
        """Update an existing ticket."""
        pass

    @abstractmethod
    async def list_tickets(self, filters: dict = None) -> List[Ticket]:
        """List tickets with optional filters."""
        pass

    @abstractmethod
    async def add_comment(self, ticket_id: str, comment: str) -> TicketResult:
        """Add a comment to an existing ticket."""
        pass

    @abstractmethod
    async def close_ticket(self, ticket_id: str, resolution: str = None) -> TicketResult:
        """Close a ticket with optional resolution note."""
        pass
```

#### 2. GitHub Issues Connector (`github_connector.py`)

Primary connector implementation using GitHub REST API v3:
- OAuth App authentication for user context
- Personal Access Token support for automation
- Label management for categorization
- Milestone support for release tracking
- Bi-directional status sync

#### 3. Enterprise Connector Stubs

Stub implementations with clear extension points:
- `zendesk_connector.py` - Zendesk REST API
- `linear_connector.py` - Linear GraphQL API
- `servicenow_connector.py` - ServiceNow REST API (extends existing ServiceNowConnector)

#### 4. DynamoDB Tables

| Table | Purpose | Key Schema |
|-------|---------|------------|
| `aura-ticketing-config` | Provider configuration per customer | PK: `customer_id` |
| `aura-ticket-mapping` | Map internal to external ticket IDs | PK: `internal_id`, GSI: `external_id` |

### Data Flow

1. **Ticket Creation:**
   ```
   User → Frontend → POST /api/v1/ticketing/tickets → ConnectorFactory → GitHubConnector → GitHub API
                                                           ↓
                                                  DynamoDB (ticket mapping)
   ```

2. **Configuration:**
   ```
   Admin → TicketingSettings.jsx → POST /api/v1/ticketing/config → Secrets Manager + DynamoDB
   ```

---

## Alternatives Considered

### Alternative 1: Build-in Ticketing System
**Rejected:** Duplicates functionality customers already have. Increases maintenance burden.

### Alternative 2: Single Provider (Zendesk Only)
**Rejected:** Requires paid licensing. Not suitable for self-hosted/air-gapped deployments.

### Alternative 3: Email-Only Support
**Rejected:** No audit trail, no integration, poor customer experience.

---

## Implementation Plan

### Phase 1: Core Infrastructure (Complete)
- [x] Create ADR-046
- [x] Implement `TicketingConnector` base class (`src/services/ticketing/base_connector.py`)
- [x] Implement `GitHubIssuesConnector` (`src/services/ticketing/github_connector.py`)
- [x] Create connector factory (`src/services/ticketing/connector_factory.py`)
- [x] Create FastAPI endpoints (`src/api/ticketing_endpoints.py`)

### Phase 2: Frontend Integration (Complete)
- [x] Create `TicketingSettings.jsx` component (`frontend/src/components/settings/TicketingSettings.jsx`)
- [x] Add ticketing tab to Settings page
- [x] Implement credential configuration UI
- [x] Add test connection functionality
- [x] Create frontend API service (`frontend/src/services/ticketingApi.js`)

### Phase 3: Enterprise Connectors (Stubs Complete)
- [x] Implement `ZendeskConnector` stub (`src/services/ticketing/zendesk_connector.py`)
- [x] Implement `LinearConnector` stub (`src/services/ticketing/linear_connector.py`)
- [x] Implement `ServiceNowConnector` stub (`src/services/ticketing/servicenow_connector.py`)
- [x] Add connector-specific configuration UI (provider selection in TicketingSettings.jsx)

### Phase 4: Testing (Complete)
- [x] Unit tests (`tests/test_ticketing_connectors_unit.py`)
- [x] Endpoint tests (`tests/test_ticketing_endpoints.py`)
- [x] Integration tests (`tests/test_ticketing_connectors.py`)
- [x] Coverage tests (`tests/test_ticketing_connector_coverage.py`)

---

## Security Considerations

1. **Credential Storage:** All API keys and OAuth tokens stored in AWS Secrets Manager
2. **Least Privilege:** GitHub tokens scoped to `issues:write` only
3. **Audit Logging:** All ticketing operations logged with user context
4. **Network Isolation:** Connectors respect VPC boundaries for self-hosted deployments

---

## Testing Strategy

1. **Unit Tests:** Mock external APIs, test connector logic
2. **Integration Tests:** Use GitHub Actions to test real GitHub API
3. **E2E Tests:** Create/update/close ticket workflow

---

## Success Metrics

- Ticket creation latency < 2 seconds
- 99.9% success rate for connector operations
- Zero credential leaks (verified by security audit)
- Customer adoption: 80%+ using configured ticketing within 30 days

---

## References

- GitHub REST API v3: https://docs.github.com/en/rest
- Zendesk API: https://developer.zendesk.com/api-reference
- Linear GraphQL API: https://developers.linear.app/docs/graphql
- ServiceNow REST API: https://docs.servicenow.com/bundle/sandiego-api-reference
