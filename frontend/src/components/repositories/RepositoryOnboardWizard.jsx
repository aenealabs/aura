/**
 * Project Aura - Repository Onboard Wizard
 *
 * Main wizard container for the 5-step repository onboarding flow.
 * Manages step navigation and renders appropriate step component.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useEffect, useCallback, Fragment } from 'react';
import { useRepositories, WizardSteps } from '../../context/RepositoryContext';
import {
  ConnectProviderStep,
  SelectRepositoriesStep,
  ConfigureAnalysisStep,
  ReviewStep,
  CompletionStep,
} from './steps';

const stepTitles = {
  [WizardSteps.CONNECT_PROVIDER]: 'Connect',
  [WizardSteps.SELECT_REPOSITORIES]: 'Select',
  [WizardSteps.CONFIGURE_ANALYSIS]: 'Configure',
  [WizardSteps.REVIEW]: 'Review',
  [WizardSteps.COMPLETION]: 'Complete',
};

const RepositoryOnboardWizard = ({ onComplete, onCancel, initialProvider = null }) => {
  const {
    isWizardOpen,
    currentStep,
    openWizard,
    closeWizard: _closeWizard,
    resetWizard,
    prevStep: _prevStep,
    nextStep: _nextStep,
  } = useRepositories();

  // Open wizard on mount if not already open
  useEffect(() => {
    if (!isWizardOpen) {
      openWizard(initialProvider);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isWizardOpen) return;

      // Escape to cancel/close
      if (e.key === 'Escape') {
        handleCancel();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isWizardOpen]);

  const handleCancel = useCallback(() => {
    resetWizard();
    if (onCancel) onCancel();
  }, [resetWizard, onCancel]);

  const handleComplete = useCallback(() => {
    resetWizard();
    if (onComplete) onComplete();
  }, [resetWizard, onComplete]);

  const handleAddMore = useCallback(() => {
    // Reset and start over
    openWizard();
  }, [openWizard]);

  if (!isWizardOpen) {
    return null;
  }

  // Render step content
  const renderStep = () => {
    switch (currentStep) {
      case WizardSteps.CONNECT_PROVIDER:
        return <ConnectProviderStep />;
      case WizardSteps.SELECT_REPOSITORIES:
        return <SelectRepositoriesStep />;
      case WizardSteps.CONFIGURE_ANALYSIS:
        return <ConfigureAnalysisStep />;
      case WizardSteps.REVIEW:
        return <ReviewStep />;
      case WizardSteps.COMPLETION:
        return (
          <CompletionStep
            onClose={handleComplete}
            onAddMore={handleAddMore}
          />
        );
      default:
        return <ConnectProviderStep />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={handleCancel}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-3xl bg-white dark:bg-surface-900 rounded-xl shadow-xl transform transition-all">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
            <h1 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Add Repository
            </h1>
            <button
              onClick={handleCancel}
              className="p-1 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Progress Steps */}
          <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700">
            <nav className="flex items-center justify-center">
              {Object.entries(stepTitles).map(([step, title], index) => {
                const stepNum = parseInt(step);
                const isActive = currentStep === stepNum;
                const isCompleted = currentStep > stepNum;
                const isLast = index === Object.keys(stepTitles).length - 1;

                return (
                  <Fragment key={step}>
                    <div className="flex items-center">
                      <div
                        className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium transition-colors ${
                          isActive
                            ? 'bg-aura-600 text-white'
                            : isCompleted
                            ? 'bg-olive-500 text-white'
                            : 'bg-surface-200 dark:bg-surface-700 text-surface-500 dark:text-surface-400'
                        }`}
                      >
                        {isCompleted ? (
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        ) : (
                          index + 1
                        )}
                      </div>
                      <span
                        className={`ml-2 text-sm hidden sm:inline ${
                          isActive
                            ? 'text-surface-900 dark:text-surface-100 font-medium'
                            : 'text-surface-500 dark:text-surface-400'
                        }`}
                      >
                        {title}
                      </span>
                    </div>
                    {!isLast && (
                      <div
                        className={`w-8 sm:w-16 h-0.5 mx-2 ${
                          isCompleted
                            ? 'bg-olive-500'
                            : 'bg-surface-200 dark:bg-surface-700'
                        }`}
                      />
                    )}
                  </Fragment>
                );
              })}
            </nav>
          </div>

          {/* Step Content */}
          <div className="px-6 py-6 max-h-[60vh] overflow-y-auto">
            {renderStep()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RepositoryOnboardWizard;
