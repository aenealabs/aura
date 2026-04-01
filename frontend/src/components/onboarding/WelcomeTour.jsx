/**
 * Project Aura - Welcome Tour
 *
 * P2: Joyride-style guided tour of the platform.
 * Orchestrates TourSpotlight and TourTooltip components.
 *
 * Features:
 * - Spotlight overlay with cutout
 * - Positioned tooltips
 * - Keyboard navigation
 * - Progress dots
 * - Skip option
 */

import { useCallback, useEffect } from 'react';
import { useTour } from '../../context/OnboardingContext';
import TourSpotlight from './TourSpotlight';
import TourTooltip from './TourTooltip';

const WelcomeTour = () => {
  const {
    isActive,
    currentStep,
    totalSteps,
    currentStepData,
    next,
    prev,
    skip,
  } = useTour();

  // Prevent body scroll during tour
  useEffect(() => {
    if (isActive) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isActive]);

  const handleNext = useCallback(() => {
    next();
  }, [next]);

  const handlePrev = useCallback(() => {
    prev();
  }, [prev]);

  const handleSkip = useCallback(() => {
    skip();
  }, [skip]);

  if (!isActive || !currentStepData) {
    return null;
  }

  return (
    <>
      {/* Spotlight overlay */}
      <TourSpotlight target={currentStepData.target} />

      {/* Tooltip */}
      <TourTooltip
        step={currentStepData}
        currentStep={currentStep}
        totalSteps={totalSteps}
        onNext={handleNext}
        onPrev={handlePrev}
        onSkip={handleSkip}
      />
    </>
  );
};

export default WelcomeTour;
