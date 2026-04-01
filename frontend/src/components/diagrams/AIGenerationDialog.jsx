/**
 * Project Aura - AI Diagram Generation Dialog (ADR-060 Phase 3)
 *
 * WCAG 2.1 AA compliant modal for AI-powered diagram generation.
 *
 * Accessibility Features:
 * - Focus trap within modal
 * - Escape key closes dialog
 * - Screen reader announcements for progress
 * - Keyboard navigable example prompts
 * - High contrast mode support
 * - Reduced motion support
 * - Data classification selector with proper labeling
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import {
  useReducedMotion,
  useAnnouncer,
  LiveRegion,
} from '../../hooks/useAccessibility';
import {
  SparklesIcon,
  XMarkIcon,
  LightBulbIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

// ============================================================================
// Constants
// ============================================================================

const EXAMPLE_PROMPTS = [
  {
    id: 'three-tier',
    label: 'Three-tier web architecture',
    prompt: 'Draw a three-tier web architecture with AWS services including load balancer, EC2 instances, and RDS database',
  },
  {
    id: 'microservices',
    label: 'Microservices with API Gateway',
    prompt: 'Create a microservices diagram with API Gateway connecting to multiple Lambda functions and DynamoDB tables',
  },
  {
    id: 'cicd-pipeline',
    label: 'CI/CD pipeline',
    prompt: 'Show a CI/CD pipeline from GitHub to EKS with CodeBuild, ECR, and ArgoCD',
  },
  {
    id: 'data-pipeline',
    label: 'Data processing pipeline',
    prompt: 'Design a data pipeline with Kinesis, Lambda transformations, S3 data lake, and Athena queries',
  },
  {
    id: 'serverless',
    label: 'Serverless architecture',
    prompt: 'Create a serverless architecture with API Gateway, Lambda, DynamoDB, and S3 for a web application',
  },
];

const DATA_CLASSIFICATIONS = [
  {
    id: 'public',
    label: 'Public',
    description: 'Non-sensitive data, can use any AI provider',
    icon: CheckCircleIcon,
    color: 'success',
  },
  {
    id: 'internal',
    label: 'Internal',
    description: 'Business data, standard security controls',
    icon: ShieldCheckIcon,
    color: 'aura',
  },
  {
    id: 'cui',
    label: 'CUI',
    description: 'Controlled Unclassified Information - GovCloud only',
    icon: ExclamationTriangleIcon,
    color: 'warning',
  },
  {
    id: 'restricted',
    label: 'Restricted',
    description: 'Highly sensitive - GovCloud with enhanced controls',
    icon: ExclamationTriangleIcon,
    color: 'critical',
  },
];

const GENERATION_STEPS = [
  { id: 'extracting', label: 'Extracting intent from description' },
  { id: 'generating', label: 'Generating diagram DSL' },
  { id: 'validating', label: 'Validating diagram structure' },
  { id: 'rendering', label: 'Rendering final diagram' },
];

// ============================================================================
// ProgressIndicator Component
// ============================================================================

function ProgressIndicator({ currentStep, isComplete, error, reducedMotion }) {
  return (
    <div className="space-y-3" role="group" aria-label="Generation progress">
      {GENERATION_STEPS.map((step, index) => {
        const stepIndex = GENERATION_STEPS.findIndex((s) => s.id === currentStep);
        const isActive = step.id === currentStep;
        const isCompleted = index < stepIndex || isComplete;
        const isPending = index > stepIndex && !isComplete;

        return (
          <div
            key={step.id}
            className="flex items-center gap-3"
            aria-current={isActive ? 'step' : undefined}
          >
            {/* Status Icon */}
            <div
              className={`
                flex items-center justify-center
                w-6 h-6 rounded-full
                transition-all ${reducedMotion ? '' : 'duration-300'}
                ${isCompleted ? 'bg-success-500' : ''}
                ${isActive ? 'bg-aura-500' : ''}
                ${isPending ? 'bg-surface-200 dark:bg-surface-700' : ''}
                ${error && isActive ? 'bg-critical-500' : ''}
              `}
            >
              {isCompleted && (
                <CheckCircleIcon className="w-4 h-4 text-white" aria-hidden="true" />
              )}
              {isActive && !error && (
                <ArrowPathIcon
                  className={`w-4 h-4 text-white ${reducedMotion ? '' : 'animate-spin'}`}
                  aria-hidden="true"
                />
              )}
              {isActive && error && (
                <XMarkIcon className="w-4 h-4 text-white" aria-hidden="true" />
              )}
              {isPending && (
                <span className="w-2 h-2 rounded-full bg-surface-400 dark:bg-surface-500" />
              )}
            </div>

            {/* Step Label */}
            <span
              className={`
                text-sm
                ${isCompleted ? 'text-success-600 dark:text-success-400' : ''}
                ${isActive ? 'text-aura-600 dark:text-aura-400 font-medium' : ''}
                ${isPending ? 'text-surface-400 dark:text-surface-500' : ''}
                ${error && isActive ? 'text-critical-600 dark:text-critical-400' : ''}
              `}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// ClassificationSelector Component
// ============================================================================

function ClassificationSelector({ value, onChange, disabled }) {
  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="text-sm font-medium text-surface-700 dark:text-surface-200 mb-2">
        Data Classification
        <span className="sr-only"> (required)</span>
      </legend>

      <div className="grid grid-cols-2 gap-2">
        {DATA_CLASSIFICATIONS.map((classification) => {
          const Icon = classification.icon;
          const isSelected = value === classification.id;
          const colorClasses = {
            success: 'border-success-500 bg-success-50 dark:bg-success-900/20',
            aura: 'border-aura-500 bg-aura-50 dark:bg-aura-900/20',
            warning: 'border-warning-500 bg-warning-50 dark:bg-warning-900/20',
            critical: 'border-critical-500 bg-critical-50 dark:bg-critical-900/20',
          };

          return (
            <label
              key={classification.id}
              className={`
                relative flex flex-col p-3 rounded-lg border-2 cursor-pointer
                transition-all duration-150
                hover:bg-surface-50 dark:hover:bg-surface-800
                focus-within:ring-2 focus-within:ring-aura-500 focus-within:ring-offset-2
                ${isSelected ? colorClasses[classification.color] : 'border-surface-200 dark:border-surface-700'}
                ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
              `}
            >
              <input
                type="radio"
                name="classification"
                value={classification.id}
                checked={isSelected}
                onChange={(e) => onChange(e.target.value)}
                className="sr-only"
                disabled={disabled}
              />

              <div className="flex items-center gap-2">
                <Icon
                  className={`
                    w-4 h-4
                    ${isSelected
                      ? `text-${classification.color}-600 dark:text-${classification.color}-400`
                      : 'text-surface-400'
                    }
                  `}
                  aria-hidden="true"
                />
                <span
                  className={`
                    text-sm font-medium
                    ${isSelected
                      ? 'text-surface-900 dark:text-surface-100'
                      : 'text-surface-600 dark:text-surface-400'
                    }
                  `}
                >
                  {classification.label}
                </span>
              </div>

              <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
                {classification.description}
              </p>

              {/* Selection indicator */}
              {isSelected && (
                <div
                  className={`
                    absolute top-2 right-2
                    w-4 h-4 rounded-full
                    bg-${classification.color}-500
                    flex items-center justify-center
                  `}
                  aria-hidden="true"
                >
                  <CheckCircleIcon className="w-3 h-3 text-white" />
                </div>
              )}
            </label>
          );
        })}
      </div>

      {/* GovCloud notice for CUI/Restricted */}
      {(value === 'cui' || value === 'restricted') && (
        <div
          className="
            flex items-start gap-2 p-2 mt-2
            bg-warning-50 dark:bg-warning-900/20
            border border-warning-200 dark:border-warning-800
            rounded-lg
          "
          role="note"
        >
          <InformationCircleIcon className="w-4 h-4 text-warning-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-warning-700 dark:text-warning-300">
            This classification requires GovCloud-hosted AI models. Generation may take longer.
          </p>
        </div>
      )}
    </fieldset>
  );
}

// ============================================================================
// ExamplePrompts Component
// ============================================================================

function ExamplePrompts({ onSelect, disabled }) {
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const listRef = useRef(null);

  const handleKeyDown = (event) => {
    if (disabled) return;

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        setFocusedIndex((prev) =>
          prev < EXAMPLE_PROMPTS.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        event.preventDefault();
        setFocusedIndex((prev) =>
          prev > 0 ? prev - 1 : EXAMPLE_PROMPTS.length - 1
        );
        break;
      case 'Enter':
      case ' ':
        if (focusedIndex >= 0) {
          event.preventDefault();
          onSelect(EXAMPLE_PROMPTS[focusedIndex].prompt);
        }
        break;
      default:
        break;
    }
  };

  // Focus management
  useEffect(() => {
    if (focusedIndex >= 0 && listRef.current) {
      const buttons = listRef.current.querySelectorAll('button');
      buttons[focusedIndex]?.focus();
    }
  }, [focusedIndex]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <LightBulbIcon className="w-4 h-4 text-warning-500" aria-hidden="true" />
        <span className="text-sm font-medium text-surface-700 dark:text-surface-200">
          Example prompts
        </span>
      </div>

      <div
        ref={listRef}
        role="listbox"
        aria-label="Example prompts"
        className="flex flex-wrap gap-2"
        onKeyDown={handleKeyDown}
      >
        {EXAMPLE_PROMPTS.map((example, index) => (
          <button
            key={example.id}
            type="button"
            role="option"
            aria-selected={focusedIndex === index}
            tabIndex={focusedIndex === index || (focusedIndex === -1 && index === 0) ? 0 : -1}
            onClick={() => onSelect(example.prompt)}
            onFocus={() => setFocusedIndex(index)}
            disabled={disabled}
            className={`
              px-3 py-1.5
              bg-surface-100 dark:bg-surface-700
              hover:bg-surface-200 dark:hover:bg-surface-600
              border border-surface-200 dark:border-surface-600
              rounded-full
              text-xs text-surface-600 dark:text-surface-300
              transition-colors duration-150
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-1
            `}
          >
            {example.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Main AIGenerationDialog Component
// ============================================================================

export default function AIGenerationDialog({
  isOpen,
  onClose,
  onGenerate,
  initialPrompt = '',
}) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [classification, setClassification] = useState('internal');
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState('');
  const [error, setError] = useState(null);

  const inputRef = useRef(null);
  const announce = useAnnouncer();
  const reducedMotion = useReducedMotion();

  // Focus trap
  const { containerRef, firstFocusableRef } = useFocusTrap(isOpen, {
    onEscape: onClose,
  });

  // Sync initial prompt
  useEffect(() => {
    if (isOpen) {
      setPrompt(initialPrompt);
      setError(null);
      setCurrentStep('');
      setIsGenerating(false);
    }
  }, [isOpen, initialPrompt]);

  // Announce dialog open
  useEffect(() => {
    if (isOpen) {
      announce('AI diagram generation dialog opened');
      // Focus input after a brief delay
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [isOpen, announce]);

  // Handle generation
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    try {
      // Simulate progress steps
      for (const step of GENERATION_STEPS) {
        setCurrentStep(step.id);
        announce(`${step.label}...`);
        // In real implementation, these would be actual API callbacks
        await new Promise((resolve) => setTimeout(resolve, 800));
      }

      await onGenerate(prompt.trim(), classification);
      announce('Diagram generated successfully', 'assertive');
      onClose();
    } catch (err) {
      setError(err.message || 'Generation failed');
      announce(`Error: ${err.message || 'Generation failed'}`, 'assertive');
    } finally {
      setIsGenerating(false);
    }
  }, [prompt, classification, isGenerating, onGenerate, onClose, announce]);

  // Handle example selection
  const handleExampleSelect = (examplePrompt) => {
    setPrompt(examplePrompt);
    announce('Example prompt selected');
    inputRef.current?.focus();
  };

  // Don't render if not open
  if (!isOpen) return null;

  // Render in portal
  return createPortal(
    <div
      className="
        fixed inset-0 z-50
        flex items-center justify-center
        p-4
      "
      role="presentation"
    >
      {/* Backdrop */}
      <div
        className={`
          absolute inset-0
          bg-black/50 backdrop-blur-sm
          ${reducedMotion ? '' : 'animate-fade-in'}
        `}
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-dialog-title"
        aria-describedby="ai-dialog-description"
        className={`
          relative w-full max-w-xl
          bg-white dark:bg-surface-800
          border border-surface-200 dark:border-surface-700
          rounded-2xl shadow-2xl
          ${reducedMotion ? '' : 'animate-slide-up'}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <SparklesIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h2
                id="ai-dialog-title"
                className="text-lg font-semibold text-surface-900 dark:text-surface-100"
              >
                Generate Diagram with AI
              </h2>
              <p
                id="ai-dialog-description"
                className="text-sm text-surface-500 dark:text-surface-400"
              >
                Describe your architecture in natural language
              </p>
            </div>
          </div>

          <button
            ref={firstFocusableRef}
            onClick={onClose}
            disabled={isGenerating}
            className="
              p-2 rounded-lg
              hover:bg-surface-100 dark:hover:bg-surface-700
              focus:outline-none focus:ring-2 focus:ring-aura-500
              transition-colors duration-150
              disabled:opacity-50
            "
            aria-label="Close dialog"
          >
            <XMarkIcon className="w-5 h-5 text-surface-500" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4">
          {/* Prompt Input */}
          <div>
            <label
              htmlFor="ai-prompt"
              className="block text-sm font-medium text-surface-700 dark:text-surface-200 mb-2"
            >
              Description
              <span className="sr-only"> (required)</span>
            </label>
            <textarea
              id="ai-prompt"
              ref={inputRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your architecture diagram..."
              disabled={isGenerating}
              rows={3}
              className="
                w-full px-4 py-3
                bg-surface-50 dark:bg-surface-900
                border border-surface-200 dark:border-surface-700
                rounded-lg
                text-sm text-surface-900 dark:text-surface-100
                placeholder:text-surface-400
                focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-transparent
                disabled:opacity-50 disabled:cursor-not-allowed
                resize-none
              "
              aria-required="true"
              aria-invalid={error ? 'true' : 'false'}
              aria-describedby={error ? 'ai-error' : undefined}
            />
          </div>

          {/* Example Prompts */}
          <ExamplePrompts onSelect={handleExampleSelect} disabled={isGenerating} />

          {/* Classification Selector */}
          <ClassificationSelector
            value={classification}
            onChange={setClassification}
            disabled={isGenerating}
          />

          {/* Progress Indicator */}
          {isGenerating && (
            <div className="pt-2">
              <ProgressIndicator
                currentStep={currentStep}
                isComplete={false}
                error={error}
                reducedMotion={reducedMotion}
              />
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div
              id="ai-error"
              role="alert"
              className="
                flex items-start gap-2 p-3
                bg-critical-50 dark:bg-critical-900/20
                border border-critical-200 dark:border-critical-800
                rounded-lg
              "
            >
              <ExclamationTriangleIcon className="w-5 h-5 text-critical-600 flex-shrink-0" />
              <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-surface-200 dark:border-surface-700">
          <button
            type="button"
            onClick={onClose}
            disabled={isGenerating}
            className="
              px-4 py-2
              text-sm font-medium text-surface-700 dark:text-surface-300
              hover:bg-surface-100 dark:hover:bg-surface-700
              rounded-lg
              focus:outline-none focus:ring-2 focus:ring-aura-500
              transition-colors duration-150
              disabled:opacity-50
            "
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleGenerate}
            disabled={!prompt.trim() || isGenerating}
            className="
              flex items-center gap-2 px-4 py-2
              bg-aura-500 hover:bg-aura-600
              text-white font-medium text-sm
              rounded-lg
              focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
              transition-colors duration-150
              disabled:bg-surface-300 dark:disabled:bg-surface-600
              disabled:cursor-not-allowed
            "
          >
            {isGenerating ? (
              <>
                <ArrowPathIcon
                  className={`w-4 h-4 ${reducedMotion ? '' : 'animate-spin'}`}
                />
                <span>Generating...</span>
              </>
            ) : (
              <>
                <SparklesIcon className="w-4 h-4" />
                <span>Generate Diagram</span>
              </>
            )}
          </button>
        </div>

        {/* Live region for status announcements */}
        <LiveRegion message={isGenerating ? `${currentStep}...` : ''} />
      </div>
    </div>,
    document.body
  );
}

// Named exports for testing
export { ProgressIndicator, ClassificationSelector, ExamplePrompts };
