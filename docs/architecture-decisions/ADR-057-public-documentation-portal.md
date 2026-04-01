# ADR-057: Public Documentation Portal and Marketing Site Animations

**Status:** Proposed
**Date:** 2026-01-08
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-045 (External Documentation Links), ADR-046 (Support Ticketing), ADR-047 (Customer Onboarding), ADR-056 (Documentation Agent)

---

## Executive Summary

This ADR establishes the architecture for the public documentation portal (docs.aenealabs.com) and intelligent workflow animations for the marketing landing page (aenealabs.com). The strategy balances developer-led discovery with lead capture and security considerations for regulated enterprise buyers.

**Core Thesis:** In 2025, documentation transparency is a competitive advantage for enterprise security products. Buyers in regulated industries expect to validate technical claims before engaging sales. A tiered access model maximizes top-of-funnel conversion while protecting genuinely sensitive operational content.

**Key Outcomes:**
- Tiered documentation access (80% public, 10% soft-gated, 10% authenticated)
- Apple-inspired workflow animations demonstrating platform capabilities
- SEO-optimized documentation driving organic discovery
- Cognito integration for authenticated content (Tier 3)
- Screen recording placeholder system for human-captured content

---

## Context

### Current State

Project Aura has comprehensive internal documentation:
- **8 customer guides** in `docs/customer/` (4,892 lines total)
- **56 Architecture Decision Records** in `docs/architecture-decisions/`
- **Marketing website** in `marketing/site/` (Astro-based)
- **Documentation portal shell** in `marketing/docs-portal/` (minimal)

### The Gap

| Asset | Exists | Publicly Accessible | SEO Indexed |
|-------|--------|---------------------|-------------|
| Quick Start Guide | Yes | No | No |
| Architecture Overview | Yes | No | No |
| API Reference | Yes | No | No |
| Security Whitepaper | Yes | No | No |
| Landing Page Animations | No | N/A | N/A |
| Interactive Workflow Demos | No | N/A | N/A |

### Competitive Analysis

| Competitor | Docs Access | Animation Quality | Notes |
|------------|-------------|-------------------|-------|
| **Snyk** | Public | Basic diagrams | Developer-first; docs are marketing |
| **CrowdStrike** | Public | Product screenshots | Enterprise sales-led |
| **Datadog** | Public | Animated GIFs | PLG motion; docs enable self-serve |
| **Wiz** | Public | Interactive demos | Cloud security; transparency builds trust |
| **Apple** | Public | Sophisticated scroll animations | Gold standard for product marketing |

---

## Decision

### 1. Tiered Documentation Access Model

#### Tier 1: Fully Public (80% of content)

**No authentication required. SEO indexed.**

| Content | Rationale |
|---------|-----------|
| Quick Start Guide | Enables immediate evaluation |
| Prerequisites & Requirements | Shows transparency about costs/complexity |
| Architecture Overview | Builds technical credibility |
| API Reference | Required for integration evaluation |
| Configuration Reference | Shows flexibility and maturity |
| Security Whitepaper | Required for regulated buyer validation |
| Troubleshooting Guide | Reduces support burden |
| Changelog / Release Notes | Transparency about evolution |

#### Tier 2: Soft-Gated (10% of content)

**Email capture required. No account creation.**

| Content | Lead Value |
|---------|------------|
| Detailed Integration Guides | High-intent signal |
| Advanced Configuration Playbooks | Implementation planning |
| Best Practices Guides | Serious evaluation |
| Migration Guides (from competitors) | Competitive displacement |
| ROI Calculator / TCO Analysis | Budget planning |

**Implementation:** Modal with email input, immediate download, no password.

#### Tier 3: Authenticated (10% of content)

**Cognito authentication required. Same as main Aura platform.**

| Content | Security Rationale |
|---------|-------------------|
| Production Hardening Guide | Operational security details |
| Security Operations Playbooks | Incident response procedures |
| Internal API Endpoints | Attack surface exposure |
| Customer-specific Examples | Confidential configurations |
| Beta/Preview Documentation | Pre-release features |

### 2. Landing Page Workflow Animations

Five Apple-inspired animations showcasing Aura's autonomous capabilities:

#### Animation 1: Multi-Agent Orchestration

**Type:** Pure CSS/SVG (no human capture needed)

```
Plan → Context → Code → Review → Validate → Deploy
  |       |        |        |         |          |
Cards illuminate sequentially with data pulse traveling along connection lines
```

**Technical Approach:**
- Intersection Observer triggers on scroll
- SVG stroke-dasharray for line drawing
- CSS keyframes for glow effects and floating motion
- 10-second loop with 3-second pause

#### Animation 2: Hybrid GraphRAG Visualization

**Type:** SVG + CSS with placeholder for human capture

**Animated Elements:**
- Nodes emerge from center with spring physics
- Edge lines draw with stroke animation
- Semantic search highlight effect (nodes pulse when "queried")

**Human Capture Required:**
- Screenshot: Knowledge graph view from `/graph` route (1920x1080)
- Recording: 10-second graph navigation showing node clicks and connections

#### Animation 3: Security Vulnerability Detection

**Type:** Code scanner animation with placeholder

**Sequence:**
1. Code appears with typing animation
2. Scan line sweeps down
3. Vulnerable line highlights with red glow + shake
4. CVE badge slides in
5. Patch diff preview appears
6. Sandbox testing progress bar
7. Green checkmark success animation

**Human Capture Required:**
- Screenshot: CVE detail view with severity badge (1440x900)
- Recording: 15-20 second patch approval flow

#### Animation 4: Human-in-the-Loop Approval

**Type:** Card-based animation with placeholder

**Sequence:**
1. Notification bell rings
2. Badge count increments
3. Approval card slides in from bottom
4. Sections expand sequentially (accordion)
5. Simulated cursor moves to "Approve"
6. Button click ripple effect
7. Success state with subtle particles

**Human Capture Required:**
- Screenshot: Approval dashboard from `/approvals` (1440x900)
- Recording: 20-30 second complete approval flow

#### Animation 5: Real-Time Threat Intelligence

**Type:** Dashboard-style with continuous motion

**Elements:**
- Globe/network visualization with constellation effect
- Real-time event cards sliding in
- Threat level indicator pulsing
- Blocklist counter incrementing

**Human Capture Required:**
- Screenshot: Security monitoring dashboard (1920x1080)
- Recording: 15-second live monitoring

### 3. Documentation Portal Architecture

```
docs.aenealabs.com/
├── /                           → Landing with quick navigation (Tier 1)
├── /quick-start/               → Quick Start Guide (Tier 1)
├── /architecture/              → Architecture Overview (Tier 1)
│   ├── /multi-agent/
│   ├── /graphrag/
│   └── /sandbox/
├── /configuration/             → Configuration Reference (Tier 1)
├── /api/                       → API Reference (Tier 1)
│   ├── /rest/
│   └── /webhooks/
├── /security/                  → Security Whitepaper (Tier 1)
│   ├── /compliance/
│   └── /threat-model/
├── /troubleshooting/           → Troubleshooting Guide (Tier 1)
├── /guides/                    → Integration Guides (Tier 2 - email)
│   ├── /slack/
│   ├── /jira/
│   └── /github-enterprise/
├── /customer/                  → Customer-only Content (Tier 3 - Cognito)
│   ├── /hardening/
│   └── /security-ops/
├── /changelog/                 → Release Notes (Tier 1)
└── /search/                    → Search Results (Tier 1)
```

### 4. Technical Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Static Generator** | Astro (existing) | Consistency with marketing site |
| **Styling** | Tailwind CSS | Existing design system |
| **Search** | Algolia DocSearch | Free for documentation, excellent UX |
| **Syntax Highlighting** | Shiki | Built into Astro, VS Code themes |
| **Analytics** | Plausible | Privacy-respecting, GDPR compliant |
| **Authentication** | AWS Cognito | Existing infrastructure |
| **CDN** | CloudFront | Existing infrastructure |
| **Hosting** | S3 | Existing infrastructure |

---

## Consequences

### Positive

1. **SEO Discovery:** Public docs will rank for "CMMC compliance automation", "autonomous code security"
2. **Sales Velocity:** Prospects arrive pre-educated, reducing sales cycle
3. **Support Reduction:** 30-40% fewer basic support tickets (industry benchmark)
4. **Trust Signal:** Transparency builds credibility with security-conscious buyers
5. **Lead Capture:** Tier 2 soft-gating captures high-intent leads
6. **Brand Differentiation:** Apple-quality animations differentiate from competitors

### Negative

1. **Competitive Intelligence:** Architecture details publicly visible (mitigated: implementation is the moat)
2. **Content Maintenance:** More content to keep updated
3. **Human Capture Dependency:** Some animations require manual screen recording

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Competitors copy architecture | Low | Low | Implementation (350K+ lines) is the real IP |
| Sensitive info accidentally published | Medium | High | PR-based review workflow, automated scanning |
| Animation performance on mobile | Medium | Medium | Graceful degradation, reduced-motion support |
| Search indexing delays | Low | Low | Submit sitemap to Google Search Console |

---

## Implementation Plan

### Phase 1: Documentation Portal Foundation (Week 1-2)

**Deliverables:**
- [ ] Astro project setup at `marketing/docs/`
- [ ] Tailwind configuration with docs-specific components
- [ ] Layout components (DocsLayout, Sidebar, TOC, Search)
- [ ] MDX content pipeline from `docs/customer/`
- [ ] Dark/light mode toggle
- [ ] Mobile-responsive navigation

**Infrastructure:**
- [ ] S3 bucket: `docs.aenealabs.com`
- [ ] CloudFront distribution with custom domain
- [ ] Route 53 DNS record
- [ ] ACM certificate

### Phase 2: Content Migration & Tiering (Week 2-3)

**Deliverables:**
- [ ] Migrate 8 customer guides to MDX
- [ ] Implement tier metadata system
- [ ] Email capture modal for Tier 2
- [ ] Cognito redirect for Tier 3
- [ ] API reference generation from OpenAPI spec

**Content Classification:**
```yaml
# frontmatter for each doc
---
title: "Quick Start Guide"
tier: 1  # 1=public, 2=email, 3=auth
seo:
  title: "Project Aura Quick Start - Deploy in 30 Minutes"
  description: "Step-by-step guide to deploying Aura..."
---
```

### Phase 3: Landing Page Animations (Week 3-4)

**Deliverables:**
- [ ] WorkflowAnimation.astro component
- [ ] Animation 1: Multi-Agent Orchestration (CSS/SVG)
- [ ] Animation 2: GraphRAG (with placeholder)
- [ ] Animation 3: Security Detection (with placeholder)
- [ ] Animation 4: HITL Approval (with placeholder)
- [ ] Animation 5: Threat Intelligence (with placeholder)
- [ ] Tailwind animation keyframes
- [ ] Intersection Observer scroll triggers
- [ ] Reduced-motion accessibility support

### Phase 4: Search & Analytics (Week 4-5)

**Deliverables:**
- [ ] Algolia DocSearch integration
- [ ] Cmd+K search modal
- [ ] Plausible analytics
- [ ] Search query tracking
- [ ] Conversion funnel (docs → signup)
- [ ] Feedback widgets ("Was this helpful?")

### Phase 5: Human Capture Integration (Week 5-6)

**Deliverables:**
- [ ] Replace placeholders with captured screenshots
- [ ] Replace placeholders with screen recordings
- [ ] Video compression and optimization
- [ ] Lazy loading for video content

---

## Placeholder Asset System

Until human-captured content is available, use animated placeholders:

### Screenshot Placeholders

```html
<div class="placeholder-screenshot relative rounded-xl overflow-hidden bg-slate-900 aspect-video">
  <!-- Animated skeleton -->
  <div class="absolute inset-0 bg-gradient-to-r from-slate-800 via-slate-700 to-slate-800 animate-shimmer"></div>

  <!-- Overlay text -->
  <div class="absolute inset-0 flex items-center justify-center">
    <div class="text-center">
      <div class="w-12 h-12 mx-auto mb-4 rounded-lg bg-aura-500/20 flex items-center justify-center">
        <svg class="w-6 h-6 text-aura-400"><!-- Camera icon --></svg>
      </div>
      <p class="text-slate-400 text-sm">Screenshot: Knowledge Graph View</p>
      <p class="text-slate-500 text-xs mt-1">1920 x 1080</p>
    </div>
  </div>
</div>
```

### Video Placeholders

```html
<div class="placeholder-video relative rounded-xl overflow-hidden bg-slate-900 aspect-video">
  <!-- Animated gradient background -->
  <div class="absolute inset-0">
    <div class="absolute inset-0 bg-gradient-to-br from-aura-500/10 via-transparent to-purple-500/10"></div>
    <div class="absolute inset-0 opacity-30">
      <!-- Animated dots representing activity -->
      <div class="animate-pulse absolute top-1/4 left-1/4 w-2 h-2 bg-aura-400 rounded-full"></div>
      <div class="animate-pulse absolute top-1/3 right-1/3 w-2 h-2 bg-purple-400 rounded-full" style="animation-delay: 0.5s"></div>
      <div class="animate-pulse absolute bottom-1/3 left-1/2 w-2 h-2 bg-emerald-400 rounded-full" style="animation-delay: 1s"></div>
    </div>
  </div>

  <!-- Play button overlay -->
  <div class="absolute inset-0 flex items-center justify-center">
    <div class="w-16 h-16 rounded-full bg-white/10 backdrop-blur flex items-center justify-center">
      <svg class="w-8 h-8 text-white ml-1"><!-- Play icon --></svg>
    </div>
  </div>

  <!-- Caption -->
  <div class="absolute bottom-4 left-4 right-4 text-center">
    <p class="text-white text-sm font-medium">Patch Approval Workflow</p>
    <p class="text-slate-400 text-xs">20-30 second recording needed</p>
  </div>
</div>
```

---

## Screen Recording Capture Checklist

### Required Captures

| ID | Animation | Asset Type | Resolution | Duration | Route | Content |
|----|-----------|------------|------------|----------|-------|---------|
| C1 | GraphRAG | Screenshot | 1920x1080 | - | `/graph` | Knowledge graph with file/class nodes |
| C2 | GraphRAG | Recording | 1920x1080 | 10s | `/graph` | Click nodes, hover connections, search |
| C3 | Security | Screenshot | 1440x900 | - | `/vulnerabilities/{id}` | CVE detail with severity badge |
| C4 | Security | Recording | 1440x900 | 15-20s | `/vulnerabilities` | Review diff, sandbox results, approve |
| C5 | HITL | Screenshot | 1440x900 | - | `/approvals` | Pending approval card with diff |
| C6 | HITL | Recording | 1440x900 | 20-30s | `/approvals` | Notification → expand → review → approve |
| C7 | Threat Intel | Screenshot | 1920x1080 | - | `/security` | Dashboard with alerts and events |
| C8 | Threat Intel | Recording | 1920x1080 | 15s | `/security` | Live events appearing, status updates |

### Capture Guidelines

1. **Theme:** Dark mode preferred (matches landing page)
2. **Browser:** Chrome with clean profile (no extensions visible)
3. **Data:** Use realistic-looking demo data (no "test123" or Lorem ipsum)
4. **Cursor:** Visible, smooth movements (not erratic)
5. **Format:** MP4, H.264, 30fps minimum
6. **Quality:** High bitrate, no compression artifacts

---

## Metrics & Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Docs → Signup conversion | 5-8% | Plausible funnel |
| Organic docs traffic (90 days) | 10K+ visits | Plausible |
| Tier 2 email capture rate | 15-25% | Email provider |
| Support ticket reduction | 30%+ | Zendesk/GitHub |
| Time on Architecture page | 3+ minutes | Plausible |
| Search queries with no results | < 5% | Algolia |
| Core Web Vitals | All green | Google Search Console |

---

## References

- [Apple Product Page Animations](https://www.apple.com/macbook-pro/) - Animation inspiration
- [Stripe Documentation](https://stripe.com/docs) - Developer docs gold standard
- [Tailwind Documentation](https://tailwindcss.com/docs) - Search UX reference
- ADR-045: External Documentation Links
- ADR-046: Support Ticketing Connectors
- ADR-047: Customer Onboarding Features
- ADR-056: Documentation Agent
