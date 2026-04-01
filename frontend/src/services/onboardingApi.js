/**
 * Project Aura - Onboarding API Service
 *
 * API service for customer onboarding features including:
 * - Welcome modal state
 * - Tour progress tracking
 * - Checklist completion
 * - Tooltip dismissals
 * - Video progress
 */

import { apiClient } from './api';

// Storage key for local state persistence
const STORAGE_KEY = 'aura_onboarding_state';

// Development mode - skip API calls and use localStorage only
const DEV_MODE = import.meta.env.DEV || !import.meta.env.VITE_API_URL;

/**
 * Check if we should use local-only mode
 * Returns true if in dev mode or API is unavailable
 */
function shouldUseLocalMode() {
  return DEV_MODE;
}

// Default onboarding state for new users
const DEFAULT_STATE = {
  user_id: null,
  organization_id: null,

  // Welcome Modal
  welcome_modal_dismissed: false,
  welcome_modal_dismissed_at: null,

  // Tour
  tour_completed: false,
  tour_step: 0,
  tour_started_at: null,
  tour_completed_at: null,
  tour_skipped: false,

  // Checklist
  checklist_dismissed: false,
  checklist_steps: {
    connect_repository: false,
    configure_analysis: false,
    run_first_scan: false,
    review_vulnerabilities: false,
    invite_team_member: false,
  },
  checklist_started_at: null,
  checklist_completed_at: null,

  // Tooltips
  dismissed_tooltips: [],

  // Video progress
  video_progress: {},

  // Metadata
  created_at: null,
  updated_at: null,
};

// Simulated delay for mock responses
const simulateDelay = (ms = 200) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Get local storage state
 */
function getLocalState() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

/**
 * Save state to local storage
 */
function saveLocalState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('[Onboarding] Failed to save local state:', error);
  }
}

/**
 * Get full onboarding state
 */
export async function getOnboardingState() {
  // In dev mode, use localStorage directly
  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    const local = getLocalState();
    if (local) {
      return local;
    }
    const newState = {
      ...DEFAULT_STATE,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    saveLocalState(newState);
    return newState;
  }

  try {
    const { data } = await apiClient.get('/onboarding/state');
    saveLocalState(data);
    return data;
  } catch {
    // Fallback to local state on any error
    await simulateDelay(100);
    const local = getLocalState();
    if (local) return local;
    const newState = {
      ...DEFAULT_STATE,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    saveLocalState(newState);
    return newState;
  }
}

/**
 * Update onboarding state (partial update)
 */
export async function updateOnboardingState(updates) {
  const updateLocal = () => {
    const current = getLocalState() || { ...DEFAULT_STATE };
    const updated = {
      ...current,
      ...updates,
      updated_at: new Date().toISOString(),
    };
    saveLocalState(updated);
    return updated;
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return updateLocal();
  }

  try {
    const { data } = await apiClient.patch('/onboarding/state', updates);
    saveLocalState(data);
    return data;
  } catch {
    await simulateDelay(100);
    return updateLocal();
  }
}

/**
 * Dismiss welcome modal
 */
export async function dismissWelcomeModal() {
  const dismissLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.welcome_modal_dismissed = true;
    local.welcome_modal_dismissed_at = new Date().toISOString();
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return dismissLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/modal/dismiss');
    dismissLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return dismissLocal();
  }
}

/**
 * Start the welcome tour
 */
export async function startTour() {
  const startLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.tour_started_at = new Date().toISOString();
    local.tour_step = 0;
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true, step: 0 };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return startLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/tour/start');
    startLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return startLocal();
  }
}

/**
 * Complete a tour step
 */
export async function completeTourStep(stepIndex) {
  const completeLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.tour_step = stepIndex + 1;
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true, step: stepIndex + 1 };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return completeLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/tour/step', { step: stepIndex });
    completeLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return completeLocal();
  }
}

/**
 * Complete the tour
 */
export async function completeTour() {
  const completeLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.tour_completed = true;
    local.tour_completed_at = new Date().toISOString();
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return completeLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/tour/complete');
    completeLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return completeLocal();
  }
}

/**
 * Skip the tour
 */
export async function skipTour() {
  const skipLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.tour_skipped = true;
    local.tour_completed = true;
    local.tour_completed_at = new Date().toISOString();
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return skipLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/tour/skip');
    skipLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return skipLocal();
  }
}

/**
 * Complete a checklist item
 */
export async function completeChecklistItem(itemId) {
  const completeLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    if (local.checklist_steps[itemId] !== undefined) {
      local.checklist_steps[itemId] = true;
    }

    // Check if all steps complete
    const allComplete = Object.values(local.checklist_steps).every((v) => v);
    if (allComplete && !local.checklist_completed_at) {
      local.checklist_completed_at = new Date().toISOString();
    }

    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true, all_complete: allComplete };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return completeLocal();
  }

  try {
    const { data } = await apiClient.post(`/onboarding/checklist/${itemId}/complete`);
    completeLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return completeLocal();
  }
}

/**
 * Dismiss the checklist
 */
export async function dismissChecklist() {
  const dismissLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.checklist_dismissed = true;
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return dismissLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/checklist/dismiss');
    dismissLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return dismissLocal();
  }
}

/**
 * Dismiss a feature tooltip
 */
export async function dismissTooltip(tooltipId) {
  const dismissLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    if (!local.dismissed_tooltips.includes(tooltipId)) {
      local.dismissed_tooltips.push(tooltipId);
    }
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return dismissLocal();
  }

  try {
    const { data } = await apiClient.post(`/onboarding/tooltip/${tooltipId}/dismiss`);
    dismissLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return dismissLocal();
  }
}

/**
 * Update video progress
 */
export async function updateVideoProgress(videoId, progress, completed = false) {
  const updateLocal = () => {
    const local = getLocalState() || { ...DEFAULT_STATE };
    local.video_progress[videoId] = {
      percent: progress,
      completed,
      updated_at: new Date().toISOString(),
    };
    local.updated_at = new Date().toISOString();
    saveLocalState(local);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return updateLocal();
  }

  try {
    const { data } = await apiClient.post(`/onboarding/video/${videoId}/progress`, {
      progress,
      completed,
    });
    updateLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return updateLocal();
  }
}

/**
 * Get video catalog
 */
export async function getVideoCatalog() {
  const mockCatalog = [
    {
      id: 'platform-overview',
      title: 'Platform Overview',
      description: 'Learn about Project Aura\'s core capabilities and how it helps secure your codebase.',
      duration: 150,
      thumbnail_url: '/assets/videos/thumbnails/platform-overview.jpg',
      video_url: '/assets/videos/platform-overview.mp4',
      chapters: [
        { time: 0, title: 'Introduction' },
        { time: 30, title: 'Dashboard Tour' },
        { time: 60, title: 'Key Features' },
        { time: 120, title: 'Getting Help' },
      ],
    },
    {
      id: 'connecting-repositories',
      title: 'Connecting Repositories',
      description: 'Step-by-step guide to connecting your GitHub or GitLab repositories.',
      duration: 180,
      thumbnail_url: '/assets/videos/thumbnails/connecting-repos.jpg',
      video_url: '/assets/videos/connecting-repos.mp4',
      chapters: [
        { time: 0, title: 'OAuth Setup' },
        { time: 45, title: 'Selecting Repositories' },
        { time: 90, title: 'Configuration Options' },
        { time: 150, title: 'Starting Ingestion' },
      ],
    },
    {
      id: 'security-scanning',
      title: 'Security Scanning',
      description: 'Understanding vulnerability detection and security analysis results.',
      duration: 165,
      thumbnail_url: '/assets/videos/thumbnails/security-scanning.jpg',
      video_url: '/assets/videos/security-scanning.mp4',
      chapters: [
        { time: 0, title: 'Scan Types' },
        { time: 40, title: 'Reading Results' },
        { time: 90, title: 'Severity Levels' },
        { time: 130, title: 'Taking Action' },
      ],
    },
    {
      id: 'patch-approval',
      title: 'Patch Approval Workflow',
      description: 'How to review, test, and approve AI-generated security patches.',
      duration: 210,
      thumbnail_url: '/assets/videos/thumbnails/patch-approval.jpg',
      video_url: '/assets/videos/patch-approval.mp4',
      chapters: [
        { time: 0, title: 'HITL Overview' },
        { time: 50, title: 'Reviewing Patches' },
        { time: 100, title: 'Sandbox Testing' },
        { time: 160, title: 'Approval Process' },
      ],
    },
    {
      id: 'team-management',
      title: 'Team Management',
      description: 'Inviting team members and managing roles and permissions.',
      duration: 120,
      thumbnail_url: '/assets/videos/thumbnails/team-management.jpg',
      video_url: '/assets/videos/team-management.mp4',
      chapters: [
        { time: 0, title: 'Inviting Members' },
        { time: 40, title: 'Role Assignment' },
        { time: 70, title: 'Permissions' },
        { time: 100, title: 'Activity Tracking' },
      ],
    },
  ];

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return mockCatalog;
  }

  try {
    const { data } = await apiClient.get('/onboarding/videos');
    return data;
  } catch {
    await simulateDelay(100);
    return mockCatalog;
  }
}

/**
 * Reset onboarding state (for testing)
 */
export async function resetOnboardingState() {
  const resetLocal = () => {
    localStorage.removeItem(STORAGE_KEY);
    return { success: true };
  };

  if (shouldUseLocalMode()) {
    await simulateDelay(100);
    return resetLocal();
  }

  try {
    const { data } = await apiClient.post('/onboarding/reset');
    resetLocal();
    return data;
  } catch {
    await simulateDelay(100);
    return resetLocal();
  }
}

// Checklist item definitions
export const CHECKLIST_ITEMS = [
  {
    id: 'connect_repository',
    title: 'Connect your first repository',
    description: 'Link a GitHub or GitLab repository to start analyzing your code.',
    action: {
      label: 'Connect Repository',
      route: '/repositories',
    },
  },
  {
    id: 'configure_analysis',
    title: 'Configure analysis settings',
    description: 'Choose which security checks and analysis options to enable.',
    action: {
      label: 'Configure',
      route: '/settings/analysis',
    },
  },
  {
    id: 'run_first_scan',
    title: 'Run your first security scan',
    description: 'Trigger a scan to identify potential vulnerabilities.',
    action: {
      label: 'Run Scan',
      route: '/security',
    },
  },
  {
    id: 'review_vulnerabilities',
    title: 'Review vulnerabilities',
    description: 'Examine detected issues and explore suggested patches.',
    action: {
      label: 'View Issues',
      route: '/security/vulnerabilities',
    },
  },
  {
    id: 'invite_team_member',
    title: 'Invite a team member',
    description: 'Collaborate with your team on security reviews and approvals.',
    action: {
      label: 'Invite Team',
      route: '/settings/team',
    },
  },
];

// Tour step definitions
export const TOUR_STEPS = [
  {
    id: 'dashboard-metrics',
    target: '[data-tour="dashboard-metrics"]',
    title: 'Dashboard Overview',
    content: 'Monitor your security posture at a glance. View key metrics, recent activity, and agent status.',
    placement: 'bottom',
  },
  {
    id: 'sidebar-nav',
    target: '[data-tour="sidebar-nav"]',
    title: 'Navigation',
    content: 'Access all areas of the platform from the sidebar. Navigate to repositories, security, approvals, and settings.',
    placement: 'right',
  },
  {
    id: 'quick-actions',
    target: '[data-tour="quick-actions"]',
    title: 'Quick Actions',
    content: 'Perform common tasks quickly. Start scans, review approvals, and access recent items.',
    placement: 'bottom',
  },
  {
    id: 'activity-feed',
    target: '[data-tour="activity-feed"]',
    title: 'Activity Feed',
    content: 'Stay informed with real-time updates on scans, patches, approvals, and team activity.',
    placement: 'left',
  },
  {
    id: 'command-palette',
    target: '[data-tour="command-palette"]',
    title: 'Command Palette',
    content: 'Press Cmd+K (or Ctrl+K) to quickly search and navigate anywhere in the platform.',
    placement: 'bottom',
  },
  {
    id: 'settings-link',
    target: '[data-tour="settings-link"]',
    title: 'Settings',
    content: 'Configure your account, team, integrations, and notification preferences.',
    placement: 'right',
  },
  {
    id: 'completion',
    target: null,
    title: 'You\'re All Set!',
    content: 'You\'ve completed the tour. Check the setup checklist to finish configuring your workspace.',
    placement: 'center',
  },
];

// Feature tooltip definitions
export const FEATURE_TOOLTIPS = {
  graphrag_toggle: {
    id: 'graphrag_toggle',
    title: 'GraphRAG Mode',
    content: 'Toggle between hybrid graph+vector search and pure vector search for code context retrieval.',
  },
  hitl_mode: {
    id: 'hitl_mode',
    title: 'Human-in-the-Loop Mode',
    content: 'Control how much human oversight is required before patches are applied.',
  },
  sandbox_isolation: {
    id: 'sandbox_isolation',
    title: 'Sandbox Isolation',
    content: 'Choose the level of network isolation for testing patches in sandbox environments.',
  },
  severity_filter: {
    id: 'severity_filter',
    title: 'Severity Filters',
    content: 'Filter vulnerabilities by severity to focus on what matters most.',
  },
  agent_status: {
    id: 'agent_status',
    title: 'Agent Status',
    content: 'View real-time status of AI agents including their current task and health metrics.',
  },
};

export default {
  getOnboardingState,
  updateOnboardingState,
  dismissWelcomeModal,
  startTour,
  completeTourStep,
  completeTour,
  skipTour,
  completeChecklistItem,
  dismissChecklist,
  dismissTooltip,
  updateVideoProgress,
  getVideoCatalog,
  resetOnboardingState,
  CHECKLIST_ITEMS,
  TOUR_STEPS,
  FEATURE_TOOLTIPS,
};
