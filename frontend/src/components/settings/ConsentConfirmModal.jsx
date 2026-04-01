/**
 * Project Aura - Consent Confirmation Modal
 *
 * Modal for confirming Tier 2 (data contribution) consents.
 * Required for GDPR compliance - ensures informed, explicit consent.
 */

import { useState, useEffect, useRef } from 'react';
import {
  ShieldCheckIcon,
  XMarkIcon,
  CheckIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

import {
  CONSENT_TYPE_CONFIG,
  getConsentVersion,
} from '../../services/consentApi';

/**
 * ConsentConfirmModal Component
 *
 * Displays a confirmation dialog for Tier 2 consents that require
 * explicit user acknowledgment before granting.
 */
export default function ConsentConfirmModal({
  isOpen,
  consentType,
  onConfirm,
  onCancel,
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const modalRef = useRef(null);
  const firstFocusRef = useRef(null);

  const config = consentType ? CONSENT_TYPE_CONFIG[consentType] : null;
  const consentVersion = getConsentVersion();
  const expirationDate = new Date(Date.now() + 2 * 365 * 24 * 60 * 60 * 1000);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setAcknowledged(false);
      setIsConfirming(false);
      // Focus the first interactive element
      setTimeout(() => {
        firstFocusRef.current?.focus();
      }, 100);
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape' && isOpen) {
        onCancel();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onCancel]);

  // Handle confirm
  const handleConfirm = async () => {
    if (!acknowledged) return;

    setIsConfirming(true);
    try {
      await onConfirm();
    } finally {
      setIsConfirming(false);
    }
  };

  if (!isOpen || !config) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-modal-title"
    >
      {/* Backdrop click to close */}
      <div
        className="absolute inset-0"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Modal content */}
      <div
        ref={modalRef}
        className="relative bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <ShieldCheckIcon className="h-6 w-6 text-aura-600" />
            </div>
            <h2
              id="consent-modal-title"
              className="text-lg font-semibold text-surface-900 dark:text-surface-100"
            >
              Confirm AI Training Participation
            </h2>
          </div>
          <button
            ref={firstFocusRef}
            onClick={onCancel}
            className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700"
            aria-label="Close dialog"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Consent type being granted */}
          <div>
            <h3 className="font-medium text-surface-900 dark:text-surface-100 mb-2">
              You are granting consent for:
            </h3>
            <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
              <p className="font-medium text-aura-600 dark:text-aura-400">
                {config.label}
              </p>
              <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
                {config.description}
              </p>
            </div>
          </div>

          {/* What this means */}
          <div>
            <h3 className="font-medium text-surface-900 dark:text-surface-100 mb-2">
              What this means:
            </h3>
            <ul className="space-y-2">
              {config.details.map((detail, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-surface-600 dark:text-surface-400">
                  <CheckIcon className="h-4 w-4 text-olive-600 shrink-0 mt-0.5" />
                  <span>{detail}</span>
                </li>
              ))}
              <li className="flex items-start gap-2 text-sm text-surface-600 dark:text-surface-400">
                <CheckIcon className="h-4 w-4 text-olive-600 shrink-0 mt-0.5" />
                <span>You can withdraw consent at any time from Settings</span>
              </li>
              <li className="flex items-start gap-2 text-sm text-surface-600 dark:text-surface-400">
                <CheckIcon className="h-4 w-4 text-olive-600 shrink-0 mt-0.5" />
                <span>Data is deleted within 30 days of withdrawal</span>
              </li>
            </ul>
          </div>

          {/* Learn more link */}
          <a
            href={`/privacy#${consentType}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-aura-600 dark:text-aura-400 hover:underline"
          >
            <InformationCircleIcon className="h-4 w-4" />
            Learn more about our data practices
          </a>

          {/* Acknowledgment checkbox */}
          <div className="flex items-start gap-3 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <input
              type="checkbox"
              id="consent-acknowledge"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              className="mt-1 h-4 w-4 text-aura-600 border-surface-300 rounded focus:ring-aura-500"
            />
            <label
              htmlFor="consent-acknowledge"
              className="text-sm text-surface-700 dark:text-surface-300 cursor-pointer"
            >
              I understand and consent to this data use
            </label>
          </div>

          {/* Consent metadata */}
          <div className="text-xs text-surface-500 dark:text-surface-400 space-y-1">
            <p>Consent Version: {consentVersion}</p>
            <p>Expires: {expirationDate.toLocaleDateString()} (2 years)</p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!acknowledged || isConfirming}
            className="px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isConfirming ? 'Granting...' : 'Grant Consent'}
          </button>
        </div>
      </div>
    </div>
  );
}
