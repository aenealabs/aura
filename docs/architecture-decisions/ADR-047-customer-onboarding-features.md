# ADR-047: Customer Onboarding Features

**Status:** Deployed
**Date:** 2025-12-30
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-043 (Repository Onboarding Wizard), ADR-030 (Chat Assistant Architecture)

---

## Executive Summary

This ADR documents the decision to implement a comprehensive customer onboarding system for Project Aura that improves user activation and retention through guided onboarding experiences.

**Key Outcomes:**
- 6 onboarding features: Welcome Modal, Checklist, Tour, Tooltips, Videos, Team Invitations
- React Context-based state management with backend persistence
- DynamoDB tables for user onboarding state and team invitations
- S3/CloudFront hosting for onboarding videos
- Feature flags for progressive rollout
- WCAG 2.1 AA accessibility compliance

---

## Context

### Current State

Project Aura has a mature platform with complex features:
- Hybrid GraphRAG code intelligence
- HITL approval workflows
- Multi-agent security scanning
- Sandbox testing environments

However, new users face onboarding challenges:
1. **Feature Discovery:** Users don't know what features exist or how to use them
2. **Activation Friction:** No guided path from signup to value realization
3. **Team Adoption:** No mechanism to invite team members to the platform
4. **Learning Resources:** No in-app video tutorials or documentation

### Problem Statement

1. **Low Activation Rates:** Users sign up but don't complete key setup steps
2. **Feature Underutilization:** Advanced features (GraphRAG, HITL) go undiscovered
3. **Support Burden:** Common questions could be answered with better onboarding
4. **Team Growth:** No self-service team invitation workflow

### Requirements

1. **First-Time User Experience:** Welcome new users with clear next steps
2. **Progress Tracking:** Show users their setup completion status
3. **Feature Education:** Explain complex features through tooltips and videos
4. **Team Invitation:** Allow users to invite colleagues with role assignment
5. **Persistence:** Remember user progress across sessions
6. **Accessibility:** WCAG 2.1 AA compliance for all onboarding UI
7. **Progressive Rollout:** Feature flags for controlled enablement

---

## Decision

**Implement a 6-component onboarding system with centralized state management and backend persistence.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CUSTOMER ONBOARDING ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │   Frontend (React)               │
                    │   OnboardingProvider             │
                    │                                  │
                    │   ┌────────────────────────────┐ │
                    │   │ WelcomeModal (P0)          │ │
                    │   │ OnboardingChecklist (P1)   │ │
                    │   │ WelcomeTour (P2)           │ │
                    │   │ FeatureTooltip (P3)        │ │
                    │   │ VideoPlayer/Modal (P4)     │ │
                    │   │ TeamInviteWizard (P5)      │ │
                    │   └────────────┬───────────────┘ │
                    └────────────────┼────────────────┘
                                     │
                         ┌───────────┴───────────┐
                         │ REST API              │
                         ▼                       ▼
              ┌─────────────────────┐ ┌─────────────────────┐
              │ Onboarding API      │ │ Team API            │
              │ /api/v1/onboarding  │ │ /api/v1/team        │
              │ - GET/PATCH state   │ │ - invitations       │
              │ - tour/checklist    │ │ - members           │
              │ - video progress    │ │ - validate/accept   │
              └─────────┬───────────┘ └─────────┬───────────┘
                        │                       │
                        ▼                       ▼
              ┌───────────────────────────────────────────────┐
              │                Backend Services               │
              │  ┌───────────────────┐  ┌──────────────────┐ │
              │  │ OnboardingService │  │ TeamInvitation   │ │
              │  │ - State CRUD      │  │ Service          │ │
              │  │ - Video catalog   │  │ - Create/revoke  │ │
              │  └─────────┬─────────┘  │ - Validate/accept│ │
              │            │            │ - Email via SNS  │ │
              │            │            └────────┬─────────┘ │
              └────────────┼─────────────────────┼───────────┘
                           │                     │
          ┌────────────────┼─────────────────────┼────────────┐
          ▼                ▼                     ▼            ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌──────────┐
│ DynamoDB        │ │ DynamoDB        │ │ SNS             │ │ S3       │
│ user-onboarding │ │ team-invitations│ │ Invitations     │ │ Videos   │
│ - tour_state    │ │ - tokens        │ │ Topic           │ │ Bucket   │
│ - checklist     │ │ - status        │ └─────────────────┘ └──────────┘
│ - tooltips      │ │ - expiry        │
│ - video_progress│ └─────────────────┘
└─────────────────┘
```

### Component Specifications

#### P0: Welcome Modal (First-Time User)

**Purpose:** Greet new users and guide them to setup

**Trigger:** First login (welcomeModalDismissed === false)

**Design:**
- Glass morphism modal (backdrop-blur-lg, bg-white/90 dark:bg-gray-900/90)
- 480px max-width, centered
- Aura logo, personalized greeting
- 3 feature cards: Automated Security, Code Intelligence, Human-in-the-Loop
- CTAs: "Take a Quick Tour" (primary), "Skip to Setup Checklist" (secondary)
- Dismissable via button, Escape key, or backdrop click

**Accessibility:**
- Focus trapped within modal
- ARIA role="dialog", aria-labelledby, aria-describedby
- Focus returns to trigger element on close

#### P1: Onboarding Checklist (Progress Tracking)

**Purpose:** Track and display setup completion progress

**Position:** Fixed bottom-right corner (320px width)

**States:**
- Collapsed: Circular progress ring + "Setup (2/5)"
- Expanded: Full checklist with progress bar

**Checklist Items:**
1. Connect your first repository
2. Configure analysis settings
3. Run your first security scan
4. Review vulnerabilities
5. Invite a team member

**Auto-Detection:** Items auto-complete based on user actions (monitored via RepositoryContext, etc.)

**Persistence:** State saved to DynamoDB and localStorage

#### P2: Welcome Tour (Joyride-Style Walkthrough)

**Purpose:** Guide users through key UI areas

**Steps (7 total):**
1. Dashboard metrics section
2. Sidebar navigation
3. Quick actions panel
4. Activity feed
5. Command palette (Cmd+K)
6. Settings link
7. Completion celebration

**Implementation:**
- SVG spotlight overlay with cutout around target element
- Tooltip with step content, navigation dots, Next/Back buttons
- Keyboard navigation (Arrow keys, Escape)
- Auto-scroll target into view

**Target Identification:** Uses `data-tour="step-id"` attributes on elements

#### P3: Feature Tooltips (In-App Discovery)

**Purpose:** Explain complex features on hover/focus

**Locations:**
- GraphRAG toggle explanation
- HITL mode selector
- Sandbox isolation level selector
- Severity filter pills
- Agent status cards

**Implementation:**
- Pulsing indicator dot on unseen features
- Tooltip appears on hover (300ms delay) or focus
- Dismissable with "Got it" or X button
- Dismissed state persisted

#### P4: Video Onboarding (Getting-Started Content)

**Video Catalog:**
| ID | Title | Duration | Description |
|----|-------|----------|-------------|
| platform-overview | Platform Overview | 2:30 | Core capabilities and navigation |
| connecting-repositories | Connecting Repositories | 3:00 | OAuth setup and selection |
| security-scanning | Security Scanning | 2:45 | Vulnerability detection results |
| patch-approval | Patch Approval Workflow | 3:30 | HITL review and testing |
| team-management | Team Management | 2:00 | Invitations and permissions |

**Implementation:**
- Custom HTML5 video player with controls
- Chapter navigation (clickable chapter markers)
- Progress tracking (resume playback)
- Keyboard shortcuts (Space=play/pause, Arrow=seek)
- S3 + CloudFront hosting

#### P5: Team Invite Wizard (Multi-Step)

**Purpose:** Allow users to invite team members with roles

**Steps:**
1. **Email Entry:** Multi-email input with validation, paste support
2. **Role Assignment:** Dropdown per invitee (Admin, Developer, Viewer)
3. **Review:** Summary with optional personal message
4. **Completion:** Success confirmation with shareable link

**Backend Flow:**
1. Create invitation records in DynamoDB
2. Publish to SNS topic
3. Lambda sends emails via SES
4. Invitee clicks link → validate token → signup/join flow

**Security:**
- Tokens are cryptographically secure (secrets.token_urlsafe(32))
- 7-day expiration by default
- TTL cleanup in DynamoDB
- Tokens invalidated on acceptance or revocation

### Data Models

#### DynamoDB: User Onboarding Table

```yaml
TableName: aura-user-onboarding-{env}
KeySchema:
  - AttributeName: user_id
    KeyType: HASH
GlobalSecondaryIndexes:
  - IndexName: organization-index
    KeySchema:
      - AttributeName: organization_id
        KeyType: HASH
      - AttributeName: created_at
        KeyType: RANGE
Attributes:
  - user_id: S
  - organization_id: S
  - welcome_modal_dismissed: BOOL
  - welcome_modal_dismissed_at: S
  - tour_completed: BOOL
  - tour_step: N
  - tour_started_at: S
  - tour_completed_at: S
  - tour_skipped: BOOL
  - checklist_dismissed: BOOL
  - checklist_steps: M
    - connect_repository: BOOL
    - configure_analysis: BOOL
    - run_first_scan: BOOL
    - review_vulnerabilities: BOOL
    - invite_team_member: BOOL
  - checklist_started_at: S
  - checklist_completed_at: S
  - dismissed_tooltips: SS
  - video_progress: M
    - {video_id}: M
      - percent: N
      - completed: BOOL
      - updated_at: S
  - created_at: S
  - updated_at: S
TTL: Enabled (ttl attribute)
```

#### DynamoDB: Team Invitations Table

```yaml
TableName: aura-team-invitations-{env}
KeySchema:
  - AttributeName: invitation_id
    KeyType: HASH
GlobalSecondaryIndexes:
  - IndexName: organization-status-index
    KeySchema:
      - AttributeName: organization_id
        KeyType: HASH
      - AttributeName: status
        KeyType: RANGE
  - IndexName: email-index
    KeySchema:
      - AttributeName: invitee_email
        KeyType: HASH
  - IndexName: token-index
    KeySchema:
      - AttributeName: invitation_token
        KeyType: HASH
    Projection: KEYS_ONLY
Attributes:
  - invitation_id: S
  - organization_id: S
  - inviter_id: S
  - inviter_email: S
  - invitee_email: S
  - role: S (admin, developer, viewer)
  - status: S (pending, accepted, expired, revoked)
  - invitation_token: S
  - message: S (optional)
  - created_at: S
  - expires_at: S
  - accepted_at: S
  - revoked_at: S
TTL: 30 days
```

### API Endpoints

#### Onboarding Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/onboarding/state` | GET | Get full onboarding state |
| `/api/v1/onboarding/state` | PATCH | Update state (partial) |
| `/api/v1/onboarding/tour/start` | POST | Start tour |
| `/api/v1/onboarding/tour/step` | POST | Complete tour step |
| `/api/v1/onboarding/tour/complete` | POST | Mark tour complete |
| `/api/v1/onboarding/tour/skip` | POST | Skip tour |
| `/api/v1/onboarding/modal/dismiss` | POST | Dismiss welcome modal |
| `/api/v1/onboarding/tooltip/{id}/dismiss` | POST | Dismiss tooltip |
| `/api/v1/onboarding/checklist/{id}/complete` | POST | Complete checklist item |
| `/api/v1/onboarding/checklist/dismiss` | POST | Dismiss checklist |
| `/api/v1/onboarding/video/{id}/progress` | POST | Update video progress |
| `/api/v1/onboarding/videos` | GET | Get video catalog |
| `/api/v1/onboarding/reset` | POST | Reset state (dev only) |

#### Team Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/team/invitations` | GET | List org invitations |
| `/api/v1/team/invitations` | POST | Send invitation(s) |
| `/api/v1/team/invitations/{id}` | DELETE | Revoke invitation |
| `/api/v1/team/invitations/{id}/resend` | POST | Resend email |
| `/api/v1/team/invitations/validate` | GET | Validate token |
| `/api/v1/team/invitations/accept` | POST | Accept invitation |
| `/api/v1/team/members` | GET | List team members |

### Feature Flags

```python
ONBOARDING_FEATURES = {
    "welcome_modal": FeatureDefinition(
        status=GA, min_tier=FREE, enabled_by_default=True
    ),
    "onboarding_checklist": FeatureDefinition(
        status=GA, min_tier=FREE, enabled_by_default=True
    ),
    "welcome_tour": FeatureDefinition(
        status=BETA, min_tier=FREE, rollout_percentage=50
    ),
    "feature_tooltips": FeatureDefinition(
        status=GA, min_tier=FREE, enabled_by_default=True
    ),
    "video_onboarding": FeatureDefinition(
        status=BETA, min_tier=FREE, enabled_by_default=True
    ),
    "team_invitations": FeatureDefinition(
        status=GA, min_tier=STARTER, enabled_by_default=True
    ),
}
```

---

## Alternatives Considered

### Alternative 1: Third-Party Onboarding SDK (Rejected)

Use Intercom, Appcues, or Pendo for onboarding flows.

**Rejected because:**
- Privacy concerns (user data sent to third party)
- Limited customization for complex features
- Additional cost per user
- GovCloud deployment complications
- No control over data residency

### Alternative 2: Static Onboarding Pages (Rejected)

Create static documentation pages instead of interactive onboarding.

**Rejected because:**
- No contextual guidance
- Users must leave app to learn
- No progress tracking
- Poor engagement metrics industry-wide

### Alternative 3: Email-Based Onboarding Sequence (Partially Adopted)

Send onboarding emails with tips and tutorials.

**Partially adopted:**
- Team invitation emails use SNS + SES
- Welcome emails complement in-app onboarding
- Not a replacement for in-app guidance

### Alternative 4: Chatbot-Based Onboarding (Deferred)

Use existing Chat Assistant for conversational onboarding.

**Deferred because:**
- Chat assistant focuses on code intelligence tasks
- Guided UI provides better structure for setup
- Can be added later as complementary feature

---

## Consequences

### Positive

1. **Improved Activation:** Guided setup increases feature adoption
2. **Reduced Support Tickets:** Self-service answers common questions
3. **Team Growth:** Self-service invitations accelerate team onboarding
4. **Feature Discovery:** Tooltips expose advanced features
5. **Learning Resources:** Videos provide deep-dive education
6. **Progress Visibility:** Checklist motivates completion

### Negative

1. **Implementation Complexity:** 6 components require coordination
2. **Maintenance Overhead:** Videos and content need updates
3. **Performance Impact:** Additional state management and API calls
4. **UI Real Estate:** Checklist and tooltips consume screen space

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Users dismiss without engaging | Medium | Medium | Make CTAs compelling; track dismissal analytics |
| Tour targets break with UI changes | Low | Low | Use stable data-tour attributes; test in CI |
| Video content becomes stale | Medium | Low | Schedule quarterly content reviews |
| Invitation email deliverability | Low | Medium | Use SES with proper SPF/DKIM; monitor bounce rates |

---

## Implementation

### Files Created

**Frontend Components:**
- `frontend/src/components/onboarding/WelcomeModal.jsx`
- `frontend/src/components/onboarding/OnboardingChecklist.jsx`
- `frontend/src/components/onboarding/ChecklistItem.jsx`
- `frontend/src/components/onboarding/WelcomeTour.jsx`
- `frontend/src/components/onboarding/TourSpotlight.jsx`
- `frontend/src/components/onboarding/TourTooltip.jsx`
- `frontend/src/components/onboarding/FeatureTooltip.jsx`
- `frontend/src/components/onboarding/TooltipIndicator.jsx`
- `frontend/src/components/onboarding/VideoPlayer.jsx`
- `frontend/src/components/onboarding/VideoModal.jsx`
- `frontend/src/components/onboarding/TeamInviteWizard.jsx`
- `frontend/src/components/onboarding/steps/EmailEntryStep.jsx`
- `frontend/src/components/onboarding/steps/RoleAssignmentStep.jsx`
- `frontend/src/components/onboarding/steps/InviteReviewStep.jsx`
- `frontend/src/components/onboarding/steps/InviteCompletionStep.jsx`
- `frontend/src/components/onboarding/index.js`

**Frontend Services/Context:**
- `frontend/src/services/onboardingApi.js`
- `frontend/src/context/OnboardingContext.jsx`

**Backend API:**
- `src/api/onboarding_endpoints.py`
- `src/api/team_endpoints.py`

**Backend Services:**
- `src/services/onboarding_service.py`
- `src/services/team_invitation_service.py`

**Infrastructure:**
- `deploy/cloudformation/onboarding.yaml` (Layer 4.10)

**Configuration:**
- `src/config/feature_flags.py` (ONBOARDING_FEATURES section)

### CloudFormation Resources

| Resource | Type | Purpose |
|----------|------|---------|
| UserOnboardingTable | DynamoDB::Table | User onboarding state |
| TeamInvitationsTable | DynamoDB::Table | Team invitation records |
| OnboardingVideosBucket | S3::Bucket | Video content hosting |
| TeamInvitationsTopic | SNS::Topic | Invitation email notifications |
| SSM Parameters | SSM::Parameter | Service discovery |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Welcome modal engagement | > 70% click "Take Tour" | Analytics |
| Tour completion rate | > 60% | CloudWatch metric |
| Checklist completion rate | > 50% complete all items | CloudWatch metric |
| Video watch rate | > 40% watch at least one | Analytics |
| Team invitation acceptance | > 80% | DynamoDB query |
| Time to first scan | < 10 minutes | CloudWatch metric |

---

## References

- ADR-043: Repository Onboarding Wizard
- ADR-030: Chat Assistant Architecture
- [React Context API](https://react.dev/reference/react/useContext)
- [WCAG 2.1 AA Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Joyride](https://react-joyride.com/) (inspiration for tour pattern)
- Existing: `frontend/src/context/AuthContext.jsx`
- Existing: `frontend/src/services/profileApi.js`
