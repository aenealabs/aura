/**
 * Project Aura - Welcome Modal
 *
 * P0: First-time user modal displayed after initial login.
 * Introduces the platform and provides options to:
 * - Start the guided tour
 * - Go directly to the checklist
 * - Skip onboarding entirely
 *
 * Features:
 * - Glass morphism design
 * - Keyboard navigation (Escape to dismiss)
 * - Feature highlights with icons
 * - WCAG 2.1 AA accessible
 */

import { useCallback, useRef } from 'react';
import { useOnboarding } from '../../context/OnboardingContext';
import Modal, { ModalTitle } from '../shared/Modal';
import {
  ShieldCheckIcon,
  CodeBracketSquareIcon,
  SparklesIcon,
  XMarkIcon,
  PlayIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';

const WelcomeModal = () => {
  const { showWelcome, dismissWelcomeModal, startTour, user } = useOnboarding();

  // Focus the skip button first, so Enter does not start the tour by accident
  const firstFocusableRef = useRef(null);

  // Handle start tour
  const handleStartTour = useCallback(() => {
    startTour();
  }, [startTour]);

  // Handle skip
  const handleSkip = useCallback(() => {
    dismissWelcomeModal();
  }, [dismissWelcomeModal]);

  if (!showWelcome) {
    return null;
  }

  const userName = user?.name?.split(' ')[0] || 'there';

  const features = [
    {
      icon: ShieldCheckIcon,
      title: 'Automated Security',
      description: 'AI-powered vulnerability detection and patch generation',
      color: 'text-critical-500 dark:text-critical-400',
      bgColor: 'bg-critical-50 dark:bg-critical-900/20',
    },
    {
      icon: CodeBracketSquareIcon,
      title: 'Code Intelligence',
      description: 'Deep code understanding with GraphRAG technology',
      color: 'text-aura-500 dark:text-aura-400',
      bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    },
    {
      icon: SparklesIcon,
      title: 'Human-in-the-Loop',
      description: 'Review and approve changes before they go live',
      color: 'text-olive-500 dark:text-olive-400',
      bgColor: 'bg-olive-50 dark:bg-olive-900/20',
    },
  ];

  return (
    <Modal
      open
      onClose={dismissWelcomeModal}
      size="sm"
      initialFocusRef={firstFocusableRef}
      overlayClassName="!z-[100] bg-black/60 backdrop-blur-sm"
      panelClassName="!z-[100] bg-white/95 dark:bg-surface-900/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/20 dark:border-surface-700/50"
    >
      <div className="relative">
        {/* Close button */}
        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
          aria-label="Close welcome modal"
        >
          <XMarkIcon className="w-5 h-5" />
        </button>

        {/* Content */}
        <div className="p-6 pt-8">
          {/* Logo and Title */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 mb-4">
              <img
                src="/assets/aura-spiral.png"
                alt="Aura Logo"
                className="w-16 h-16 object-contain drop-shadow-lg"
              />
            </div>

            <ModalTitle className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              Welcome, {userName}!
            </ModalTitle>
            <p className="mt-2 text-surface-600 dark:text-surface-400">
              Let&apos;s get you set up with Project Aura
            </p>
          </div>

          {/* Feature Cards */}
          <div className="space-y-3 mb-6">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="flex items-start gap-3 p-3 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-100 dark:border-surface-700/50"
              >
                <div className={`p-2 rounded-lg ${feature.bgColor}`}>
                  <feature.icon className={`w-5 h-5 ${feature.color}`} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                    {feature.title}
                  </h3>
                  <p className="text-xs text-surface-500 dark:text-surface-400">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <button
              onClick={handleStartTour}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-aura-600 hover:bg-aura-700 text-white font-medium rounded-xl shadow-lg shadow-aura-500/25 transition-all hover:shadow-aura-500/35 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-900"
            >
              <PlayIcon className="w-5 h-5" />
              <span>Take a Quick Tour</span>
            </button>

            <button
              ref={firstFocusableRef}
              onClick={handleSkip}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-surface-100 dark:bg-surface-800 hover:bg-surface-200 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 font-medium rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-surface-400 focus:ring-offset-2 dark:focus:ring-offset-surface-900"
            >
              <CheckCircleIcon className="w-5 h-5" />
              <span>Skip to Setup Checklist</span>
            </button>
          </div>

          {/* Footer hint */}
          <p className="mt-4 text-center text-xs text-surface-400 dark:text-surface-500">
            Press <kbd className="px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-800 font-mono">Esc</kbd> to close
          </p>
        </div>
      </div>
    </Modal>
  );
};

export default WelcomeModal;
