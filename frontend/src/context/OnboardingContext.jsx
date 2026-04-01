/**
 * Onboarding Context
 *
 * Manages customer onboarding state for the entire application.
 * Provides:
 * - Welcome modal state
 * - Tour progress tracking
 * - Checklist completion
 * - Tooltip dismissals
 * - Video progress
 * - Auto-sync to backend
 *
 * @module context/OnboardingContext
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import { useAuth } from './AuthContext';
import {
  getOnboardingState,
  dismissWelcomeModal as apiDismissWelcomeModal,
  startTour as apiStartTour,
  completeTourStep as apiCompleteTourStep,
  completeTour as apiCompleteTour,
  skipTour as apiSkipTour,
  completeChecklistItem as apiCompleteChecklistItem,
  dismissChecklist as apiDismissChecklist,
  dismissTooltip as apiDismissTooltip,
  updateVideoProgress as apiUpdateVideoProgress,
  getVideoCatalog,
  CHECKLIST_ITEMS,
  TOUR_STEPS,
  FEATURE_TOOLTIPS,
} from '../services/onboardingApi';

// Context
const OnboardingContext = createContext(null);

// Default state shape
const DEFAULT_STATE = {
  // Welcome Modal
  welcomeModalDismissed: false,

  // Tour
  tourActive: false,
  tourStep: 0,
  tourCompleted: false,
  tourSkipped: false,

  // Checklist
  checklistExpanded: true,
  checklistDismissed: false,
  checklistSteps: {
    connect_repository: false,
    configure_analysis: false,
    run_first_scan: false,
    review_vulnerabilities: false,
    invite_team_member: false,
  },

  // Tooltips
  dismissedTooltips: new Set(),

  // Videos
  videoProgress: {},
  videoCatalog: [],
};

/**
 * Onboarding Provider Component
 */
export const OnboardingProvider = ({ children }) => {
  const { isAuthenticated, user } = useAuth();

  // State
  const [state, setState] = useState(DEFAULT_STATE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Debounce sync ref
  const syncTimeoutRef = useRef(null);

  /**
   * Load onboarding state from backend
   */
  const loadState = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [serverState, videos] = await Promise.all([
        getOnboardingState(),
        getVideoCatalog(),
      ]);

      setState({
        welcomeModalDismissed: serverState.welcome_modal_dismissed || false,
        tourActive: false,
        tourStep: serverState.tour_step || 0,
        tourCompleted: serverState.tour_completed || false,
        tourSkipped: serverState.tour_skipped || false,
        checklistExpanded: !serverState.checklist_dismissed,
        checklistDismissed: serverState.checklist_dismissed || false,
        checklistSteps: serverState.checklist_steps || DEFAULT_STATE.checklistSteps,
        dismissedTooltips: new Set(serverState.dismissed_tooltips || []),
        videoProgress: serverState.video_progress || {},
        videoCatalog: videos || [],
      });
    } catch (err) {
      console.error('[Onboarding] Failed to load state:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  // Load state when authenticated
  useEffect(() => {
    loadState();
  }, [loadState]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, []);

  /**
   * Dismiss welcome modal
   */
  const dismissWelcomeModal = useCallback(async () => {
    try {
      await apiDismissWelcomeModal();
      setState((prev) => ({
        ...prev,
        welcomeModalDismissed: true,
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to dismiss modal:', err);
    }
  }, []);

  /**
   * Show welcome modal (for testing)
   */
  const showWelcomeModal = useCallback(() => {
    setState((prev) => ({
      ...prev,
      welcomeModalDismissed: false,
    }));
  }, []);

  /**
   * Start the welcome tour
   */
  const startTour = useCallback(async () => {
    try {
      await apiStartTour();
      setState((prev) => ({
        ...prev,
        tourActive: true,
        tourStep: 0,
        welcomeModalDismissed: true,
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to start tour:', err);
    }
  }, []);

  /**
   * Go to next tour step
   */
  const nextTourStep = useCallback(async () => {
    const currentStep = state.tourStep;
    const nextStep = currentStep + 1;

    if (nextStep >= TOUR_STEPS.length) {
      // Tour complete
      try {
        await apiCompleteTour();
        setState((prev) => ({
          ...prev,
          tourActive: false,
          tourCompleted: true,
          tourStep: 0,
        }));
      } catch (err) {
        console.error('[Onboarding] Failed to complete tour:', err);
      }
    } else {
      try {
        await apiCompleteTourStep(currentStep);
        setState((prev) => ({
          ...prev,
          tourStep: nextStep,
        }));
      } catch (err) {
        console.error('[Onboarding] Failed to advance tour:', err);
      }
    }
  }, [state.tourStep]);

  /**
   * Go to previous tour step
   */
  const prevTourStep = useCallback(() => {
    setState((prev) => ({
      ...prev,
      tourStep: Math.max(0, prev.tourStep - 1),
    }));
  }, []);

  /**
   * Skip the tour
   */
  const skipTour = useCallback(async () => {
    try {
      await apiSkipTour();
      setState((prev) => ({
        ...prev,
        tourActive: false,
        tourSkipped: true,
        tourCompleted: true,
        tourStep: 0,
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to skip tour:', err);
    }
  }, []);

  /**
   * Complete a checklist item
   */
  const completeChecklistItem = useCallback(async (itemId) => {
    if (state.checklistSteps[itemId]) {
      return; // Already completed
    }

    try {
      await apiCompleteChecklistItem(itemId);
      setState((prev) => ({
        ...prev,
        checklistSteps: {
          ...prev.checklistSteps,
          [itemId]: true,
        },
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to complete checklist item:', err);
    }
  }, [state.checklistSteps]);

  /**
   * Toggle checklist expansion
   */
  const toggleChecklist = useCallback(() => {
    setState((prev) => ({
      ...prev,
      checklistExpanded: !prev.checklistExpanded,
    }));
  }, []);

  /**
   * Dismiss checklist
   */
  const dismissChecklist = useCallback(async () => {
    try {
      await apiDismissChecklist();
      setState((prev) => ({
        ...prev,
        checklistDismissed: true,
        checklistExpanded: false,
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to dismiss checklist:', err);
    }
  }, []);

  /**
   * Dismiss a tooltip
   */
  const dismissTooltip = useCallback(async (tooltipId) => {
    if (state.dismissedTooltips.has(tooltipId)) {
      return; // Already dismissed
    }

    try {
      await apiDismissTooltip(tooltipId);
      setState((prev) => ({
        ...prev,
        dismissedTooltips: new Set([...prev.dismissedTooltips, tooltipId]),
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to dismiss tooltip:', err);
    }
  }, [state.dismissedTooltips]);

  /**
   * Check if tooltip is dismissed
   */
  const isTooltipDismissed = useCallback(
    (tooltipId) => state.dismissedTooltips.has(tooltipId),
    [state.dismissedTooltips]
  );

  /**
   * Update video progress
   */
  const updateVideoProgress = useCallback(async (videoId, progress, completed = false) => {
    try {
      await apiUpdateVideoProgress(videoId, progress, completed);
      setState((prev) => ({
        ...prev,
        videoProgress: {
          ...prev.videoProgress,
          [videoId]: { percent: progress, completed },
        },
      }));
    } catch (err) {
      console.error('[Onboarding] Failed to update video progress:', err);
    }
  }, []);

  /**
   * Get video progress
   */
  const getVideoProgress = useCallback(
    (videoId) => state.videoProgress[videoId] || { percent: 0, completed: false },
    [state.videoProgress]
  );

  // Computed values
  const checklistProgress = useMemo(() => {
    const completed = Object.values(state.checklistSteps).filter(Boolean).length;
    const total = Object.keys(state.checklistSteps).length;
    return { completed, total, percent: Math.round((completed / total) * 100) };
  }, [state.checklistSteps]);

  const isChecklistComplete = useMemo(
    () => checklistProgress.completed === checklistProgress.total,
    [checklistProgress]
  );

  const showWelcome = useMemo(
    () => isAuthenticated && !state.welcomeModalDismissed && !loading,
    [isAuthenticated, state.welcomeModalDismissed, loading]
  );

  const showChecklist = useMemo(
    () =>
      isAuthenticated &&
      !state.checklistDismissed &&
      !state.tourActive &&
      !loading,
    [isAuthenticated, state.checklistDismissed, state.tourActive, loading]
  );

  const currentTourStep = useMemo(
    () => (state.tourActive ? TOUR_STEPS[state.tourStep] : null),
    [state.tourActive, state.tourStep]
  );

  // Context value
  const value = useMemo(
    () => ({
      // State
      ...state,
      loading,
      error,
      user,

      // Computed
      checklistProgress,
      isChecklistComplete,
      showWelcome,
      showChecklist,
      currentTourStep,
      checklistItems: CHECKLIST_ITEMS,
      tourSteps: TOUR_STEPS,
      featureTooltips: FEATURE_TOOLTIPS,

      // Actions
      loadState,
      dismissWelcomeModal,
      showWelcomeModal,
      startTour,
      nextTourStep,
      prevTourStep,
      skipTour,
      completeChecklistItem,
      toggleChecklist,
      dismissChecklist,
      dismissTooltip,
      isTooltipDismissed,
      updateVideoProgress,
      getVideoProgress,
    }),
    [
      state,
      loading,
      error,
      user,
      checklistProgress,
      isChecklistComplete,
      showWelcome,
      showChecklist,
      currentTourStep,
      loadState,
      dismissWelcomeModal,
      showWelcomeModal,
      startTour,
      nextTourStep,
      prevTourStep,
      skipTour,
      completeChecklistItem,
      toggleChecklist,
      dismissChecklist,
      dismissTooltip,
      isTooltipDismissed,
      updateVideoProgress,
      getVideoProgress,
    ]
  );

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>;
};

/**
 * Custom hook to use onboarding context
 * @returns {object} - Onboarding context value
 * @throws {Error} - If used outside OnboardingProvider
 */
export const useOnboarding = () => {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within an OnboardingProvider');
  }
  return context;
};

/**
 * Custom hook for checklist progress monitoring
 * Auto-completes items based on app state
 */
export const useChecklistProgress = () => {
  const { checklistSteps, completeChecklistItem } = useOnboarding();

  // This hook can be extended to monitor other contexts
  // and auto-complete checklist items when actions are detected

  return {
    checklistSteps,
    completeChecklistItem,
  };
};

/**
 * Custom hook for tour management
 */
export const useTour = () => {
  const {
    tourActive,
    tourStep,
    tourCompleted,
    tourSkipped,
    currentTourStep,
    tourSteps,
    startTour,
    nextTourStep,
    prevTourStep,
    skipTour,
  } = useOnboarding();

  return {
    isActive: tourActive,
    currentStep: tourStep,
    totalSteps: tourSteps.length,
    isCompleted: tourCompleted,
    isSkipped: tourSkipped,
    currentStepData: currentTourStep,
    steps: tourSteps,
    start: startTour,
    next: nextTourStep,
    prev: prevTourStep,
    skip: skipTour,
  };
};

/**
 * Custom hook for feature tooltips
 */
export const useFeatureTooltip = (tooltipId) => {
  const { featureTooltips, isTooltipDismissed, dismissTooltip } = useOnboarding();

  const tooltip = featureTooltips[tooltipId];
  const isDismissed = isTooltipDismissed(tooltipId);

  const dismiss = useCallback(() => {
    dismissTooltip(tooltipId);
  }, [dismissTooltip, tooltipId]);

  return {
    tooltip,
    isDismissed,
    dismiss,
    shouldShow: tooltip && !isDismissed,
  };
};

/**
 * Custom hook for video progress
 */
export const useVideoProgress = (videoId) => {
  const { getVideoProgress, updateVideoProgress, videoCatalog } = useOnboarding();

  const progress = getVideoProgress(videoId);
  const video = videoCatalog.find((v) => v.id === videoId);

  const updateProgress = useCallback(
    (percent, completed = false) => {
      updateVideoProgress(videoId, percent, completed);
    },
    [updateVideoProgress, videoId]
  );

  return {
    video,
    progress,
    updateProgress,
  };
};

// Note: No default export to fix Vite Fast Refresh compatibility
// Use named imports: import { OnboardingProvider, useOnboarding } from './OnboardingContext'
