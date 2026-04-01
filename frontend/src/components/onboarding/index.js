/**
 * Project Aura - Onboarding Components
 *
 * Barrel exports for customer onboarding features:
 * - WelcomeModal (P0)
 * - OnboardingChecklist (P1)
 * - WelcomeTour (P2)
 * - FeatureTooltip (P3)
 * - VideoPlayer/VideoModal (P4)
 * - TeamInviteWizard (P5)
 */

// P0: Welcome Modal
export { default as WelcomeModal } from './WelcomeModal';

// P1: Onboarding Checklist
export { default as OnboardingChecklist } from './OnboardingChecklist';
export { default as ChecklistItem } from './ChecklistItem';

// P2: Welcome Tour
export { default as WelcomeTour } from './WelcomeTour';
export { default as TourSpotlight } from './TourSpotlight';
export { default as TourTooltip } from './TourTooltip';

// P3: Feature Tooltips
export { default as FeatureTooltip } from './FeatureTooltip';
export { default as TooltipIndicator } from './TooltipIndicator';

// P4: Video Components
export { default as VideoPlayer } from './VideoPlayer';
export { default as VideoModal, VideoCard } from './VideoModal';

// P5: Team Invite Wizard
export { default as TeamInviteWizard } from './TeamInviteWizard';

// Development Tools (only visible in dev mode)
export { default as DevToolbar } from './DevToolbar';

// Step components (internal use)
export { default as EmailEntryStep } from './steps/EmailEntryStep';
export { default as RoleAssignmentStep } from './steps/RoleAssignmentStep';
export { default as InviteReviewStep } from './steps/InviteReviewStep';
export { default as InviteCompletionStep } from './steps/InviteCompletionStep';
