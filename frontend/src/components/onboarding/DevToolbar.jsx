/**
 * Development Toolbar for Onboarding Testing
 *
 * Only visible in development mode. Provides quick actions for testing
 * the onboarding flow without manually clearing localStorage.
 */

import { useState } from 'react';
import {
  ArrowPathIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';
import { useOnboarding } from '../../context/OnboardingContext';
import { useAuth } from '../../context/AuthContext';
import { resetOnboardingState } from '../../services/onboardingApi';

// Only show in development mode
const IS_DEV = import.meta.env.DEV;

export default function DevToolbar() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [resetting, setResetting] = useState(false);
  const { isAuthenticated } = useAuth();
  const {
    welcomeModalDismissed,
    tourCompleted,
    tourStep,
    checklistSteps,
    loadState,
    startTour,
    loading,
    showWelcome,
  } = useOnboarding();

  // Hide in production
  if (!IS_DEV) {
    return null;
  }

  const handleReset = async () => {
    setResetting(true);
    try {
      // Clear onboarding state
      await resetOnboardingState();
      // Clear auth state to simulate fresh user
      localStorage.removeItem('aura_user');
      localStorage.removeItem('aura_auth_tokens');
      localStorage.removeItem('aura_last_activity');
      // Refresh the page to restart everything
      window.location.reload();
    } catch (error) {
      console.error('[DevToolbar] Reset failed:', error);
    } finally {
      setResetting(false);
    }
  };

  const handleResetOnboardingOnly = async () => {
    setResetting(true);
    try {
      await resetOnboardingState();
      await loadState();
    } catch (error) {
      console.error('[DevToolbar] Reset onboarding failed:', error);
    } finally {
      setResetting(false);
    }
  };

  const completedSteps = Object.values(checklistSteps || {}).filter(Boolean).length;
  const totalSteps = Object.keys(checklistSteps || {}).length || 5;

  return (
    <div className="fixed bottom-4 left-4 z-[9999]">
      {/* Collapsed state - just a button */}
      {!isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium shadow-lg hover:bg-purple-700 transition-colors"
        >
          <span className="text-xs font-bold bg-purple-800 px-1.5 py-0.5 rounded">DEV</span>
          <ChevronUpIcon className="w-4 h-4" />
        </button>
      )}

      {/* Expanded state - full toolbar */}
      {isExpanded && (
        <div className="bg-surface-900 text-white rounded-xl shadow-2xl overflow-hidden w-80 border border-purple-500/50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 bg-purple-700">
            <span className="font-semibold text-sm">Onboarding Dev Tools</span>
            <button
              onClick={() => setIsExpanded(false)}
              className="p-1 hover:bg-purple-600 rounded transition-colors"
            >
              <ChevronDownIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Status */}
          <div className="p-4 space-y-3 text-sm">
            <div className="space-y-2">
              <h3 className="text-xs uppercase tracking-wider text-surface-400 font-semibold">
                Current State
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <StatusItem
                  label="Authenticated"
                  value={isAuthenticated ? 'Yes' : 'No'}
                  active={isAuthenticated}
                />
                <StatusItem
                  label="Loading"
                  value={loading ? 'Yes' : 'No'}
                  active={!loading}
                />
                <StatusItem
                  label="showWelcome"
                  value={showWelcome ? 'Yes' : 'No'}
                  active={showWelcome}
                />
                <StatusItem
                  label="Modal Dismissed"
                  value={welcomeModalDismissed ? 'Yes' : 'No'}
                  active={!welcomeModalDismissed}
                />
                <StatusItem
                  label="Tour"
                  value={tourCompleted ? 'Done' : `Step ${tourStep + 1}`}
                  active={!tourCompleted}
                />
                <StatusItem
                  label="Checklist"
                  value={`${completedSteps}/${totalSteps}`}
                  active={completedSteps < totalSteps}
                />
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-2">
              <h3 className="text-xs uppercase tracking-wider text-surface-400 font-semibold">
                Actions
              </h3>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleReset}
                  disabled={resetting}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                >
                  <ArrowPathIcon className={`w-4 h-4 ${resetting ? 'animate-spin' : ''}`} />
                  Full Reset
                </button>
                <button
                  onClick={handleResetOnboardingOnly}
                  disabled={resetting}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                >
                  <ArrowPathIcon className={`w-4 h-4 ${resetting ? 'animate-spin' : ''}`} />
                  Reset Onboarding
                </button>
                <button
                  onClick={() => startTour()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-xs font-medium transition-colors"
                >
                  <PlayIcon className="w-4 h-4" />
                  Start Tour
                </button>
              </div>
            </div>

            {/* Instructions */}
            <div className="text-xs text-surface-400 border-t border-surface-700 pt-3 mt-3">
              <strong>Full Reset:</strong> Clears all state and reloads page as new user.
              <br />
              <strong>Reset Onboarding:</strong> Clears onboarding only, keeps auth.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusItem({ label, value, active }) {
  return (
    <div className="flex items-center justify-between bg-surface-800 rounded px-2 py-1.5">
      <span className="text-surface-400">{label}</span>
      <span className={`font-medium ${active ? 'text-green-400' : 'text-surface-500'}`}>
        {value}
      </span>
    </div>
  );
}
