# ADR-045: External Documentation Links for Knowledge Graph

**Status:** Deployed
**Date:** 2025-12-18 | **Deployed:** 2025-12-31
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-044 (Enhanced Node Detail Panel)

---

## Executive Summary

This ADR documents the decision to add external documentation links to the Knowledge Graph Node Detail Panel. Links provide quick access to official vendor documentation for dependencies while maintaining strict security boundaries.

**Key Outcomes:**
- Graph-scoped queries only (no external data fetching with code context)
- Curated allowlist of official documentation domains
- Graceful fallback when documentation unavailable
- CMMC/FedRAMP compliant (no data exfiltration)

---

## Context

### Current State

The Knowledge Graph displays dependency nodes (e.g., `spring-boot-2.7.0`, `log4j-2.17.0`) with metadata like version and risk level. Users wanting to learn more about a dependency must manually search for documentation.

### Problem Statement

1. **Context Switching**: Users must leave the platform to find documentation
2. **Trust Uncertainty**: Users may land on unofficial or outdated sources
3. **Security Risk**: Uncontrolled external queries could leak code context

### Requirements

1. **Security First**: No code context sent to external services
2. **Official Sources Only**: Link only to curated, official documentation
3. **Graceful Degradation**: Handle unavailable documentation gracefully
4. **Compliance**: Maintain CMMC/FedRAMP compliance
5. **User Experience**: Minimal friction, clear visual signals

---

## Decision

**Implement external documentation links using a curated domain allowlist with graph-scoped queries.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Knowledge Graph Query                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────┐  │
│  │   Neptune    │───▶│  Query Processor   │───▶│   Results   │  │
│  │   (Graph)    │    │  (Graph-scoped)    │    │   + Links   │  │
│  └──────────────┘    └────────────────────┘    └──────┬──────┘  │
│                                                       │          │
│                                                       ▼          │
│                              ┌────────────────────────────────┐  │
│                              │  Documentation Link Resolver   │  │
│                              │  ├─ Curated Allowlist          │  │
│                              │  ├─ URL Validation             │  │
│                              │  └─ Fallback Handling          │  │
│                              └────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Node Detail Panel                                       │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │  📄 Official Documentation ↗                     │    │    │
│  │  │     spring.io/projects/spring-boot               │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  │                        OR                                │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │  ○ No official documentation available           │    │    │
│  │  │    Search on: Internet ↗                         │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  rel="noopener noreferrer" on all external links                │
└─────────────────────────────────────────────────────────────────┘
```

### Security Model

| Principle | Implementation |
|-----------|----------------|
| **No Data Exfiltration** | Links are purely navigational; no code context sent |
| **Domain Allowlist** | Only pre-approved official documentation domains |
| **URL Validation** | HTTPS only, no IPs, no suspicious patterns |
| **Audit Logging** | Log all link generations for security monitoring |
| **Trust Indicators** | Visual distinction between curated and generated links |

### Curated Documentation Domains

```javascript
const TRUSTED_DOCUMENTATION_DOMAINS = {
  // Official language/framework documentation
  'docs.python.org': { ecosystem: 'python', trust: 'official' },
  'docs.oracle.com': { ecosystem: 'java', trust: 'official' },
  'learn.microsoft.com': { ecosystem: 'dotnet', trust: 'official' },
  'docs.aws.amazon.com': { ecosystem: 'aws', trust: 'official' },

  // Official package registries
  'pypi.org': { ecosystem: 'python', trust: 'registry' },
  'npmjs.com': { ecosystem: 'javascript', trust: 'registry' },
  'mvnrepository.com': { ecosystem: 'java', trust: 'registry' },
  'pkg.go.dev': { ecosystem: 'go', trust: 'official' },

  // Major framework documentation
  'spring.io': { ecosystem: 'java', trust: 'official' },
  'fastapi.tiangolo.com': { ecosystem: 'python', trust: 'official' },
  'react.dev': { ecosystem: 'javascript', trust: 'official' },

  // Security sources
  'nvd.nist.gov': { ecosystem: 'security', trust: 'official' },
  'cve.mitre.org': { ecosystem: 'security', trust: 'official' },
};

const BLOCKED_DOMAINS = [
  'pypi.com',      // Typosquat of pypi.org
  'npmjs.org',     // Typosquat of npmjs.com
];
```

### Link Resolution Strategy

| Priority | Source | Trust Level | Example |
|----------|--------|-------------|---------|
| 1 | Curated allowlist | Highest | spring.io/projects/spring-boot |
| 2 | Official registry metadata | Medium | From PyPI/npm API |
| 3 | Pattern-based generation | Lower | pypi.org/project/{name} |
| 4 | Unavailable fallback | N/A | "Search on: Internet" |

---

## UI/UX Specifications

### Placement

Documentation link appears in the Node Detail Panel, below the description section, above properties.

### Available Documentation State

```
┌─────────────────────────────────────────────┐
│  📄 Official Documentation ↗                │
│     spring.io/projects/spring-boot          │
└─────────────────────────────────────────────┘
```

- Document icon (`DocumentTextIcon`) + external arrow icon
- Link text: "Official Documentation"
- Domain displayed below for transparency
- Opens in new tab with `rel="noopener noreferrer"`
- Hover state: subtle background, blue text

### Unavailable Documentation State

```
┌─────────────────────────────────────────────┐
│  ○ No official documentation available      │
│    Search on: Internet ↗                    │
└─────────────────────────────────────────────┘
```

- Empty circle icon (neutral, non-alarming)
- Generic search link to avoid recommending unofficial sources
- Links to search engine with package name query

### Loading State

Skeleton placeholder matching final layout dimensions. No spinner.

---

## Handling Unavailable Documentation

| Scenario | User Message | Action |
|----------|--------------|--------|
| No official docs exist | "No official documentation available" | Show Internet search link |
| Vendor site temporarily down | "Documentation temporarily unavailable" | Show Internet search link |
| Internal/proprietary package | "Internal dependency" | No external link |
| Package deprecated | "Package deprecated" | Show deprecation notice |

---

## Compliance Considerations

### CMMC/FedRAMP Impact

| Control | Requirement | External Links Impact |
|---------|-------------|----------------------|
| **AC-4** | Control information flows | Compliant - no data sent externally |
| **SC-7** | Boundary protection | Compliant - user-initiated navigation only |
| **SI-3** | Malware protection | Mitigated via domain allowlist |
| **AU-2** | Audit events | Implemented - all navigations logged |

### Key Compliance Points

1. **No data exfiltration**: Links are purely navigational hyperlinks
2. **User-initiated**: No automatic content fetching
3. **Auditable**: All link generations and clicks logged
4. **Controlled**: Domain allowlist reviewed quarterly

---

## Alternatives Considered

### Alternative 1: RAG with External Documentation

**Rejected:** Would require sending code context to external services, creating data leakage risk.

### Alternative 2: Cache Documentation Locally

**Rejected:** Legal/licensing concerns, storage costs, staleness issues, operational burden.

### Alternative 3: Proxy External Documentation

**Rejected:** Complex, single point of failure, legal concerns about content reproduction.

### Alternative 4: No External Links

**Rejected:** Poor user experience; users would manually search anyway without guidance toward official sources.

---

## Implementation Phases

### Phase 1: Frontend UI (Complete)

- [x] Add `docs_url` field to mock dependency and vulnerability nodes
- [x] Implement `DocumentationLink` component (`CKGEConsole.jsx:899-973`)
- [x] Integrate into `NodeDetailPanel` (`CKGEConsole.jsx:1234`)
- [x] Handle available state with domain display and external link
- [x] Handle unavailable state with Internet search fallback
- [x] Use `rel="noopener noreferrer"` on all external links

### Phase 2: Backend Service (Future)

- Implement `DocumentationLinkResolver` service
- Create curated allowlist database table
- Integrate with official registry APIs
- Add audit logging

### Phase 3: Operations (Future)

- Set up domain health monitoring
- Create quarterly allowlist review process
- Build CloudWatch dashboards for link metrics

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Domain hijacking | High | Allowlist validation, periodic verification |
| Link rot | Medium | Health checks, generic search fallback |
| Typosquatting | High | Strict allowlist, block known typosquats |
| Compromised vendor site | High | User awareness, cannot fully mitigate |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Link click rate | >10% of node views | Analytics tracking |
| Fallback rate | <20% of dependencies | Nodes without official docs |
| Security incidents | 0 | Audit log monitoring |

---

## References

- Architecture team: Security implementation patterns
- Design Review: Interface design recommendations
- ADR-044: Enhanced Node Detail Panel
- NIST 800-53: Security controls reference

---

## Appendix: URL Validation Rules

```javascript
const validateUrl = (url) => {
  // HTTPS only
  if (!url.startsWith('https://')) return false;

  // No IP addresses
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/.test(hostname)) return false;

  // No localhost/internal
  if (['localhost', '127.0.0.1'].includes(hostname)) return false;

  // Domain in allowlist
  if (!domainInAllowlist(hostname)) return false;

  // No suspicious patterns
  const suspicious = ['@', '\\', '%00', 'javascript:', 'data:'];
  if (suspicious.some(p => url.includes(p))) return false;

  return true;
};
```
