/**
 * License Expiration Banner Component
 *
 * Displays warning banners based on license expiration status.
 */

import {
  InformationCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useState } from 'react';

const BANNER_CONFIG = {
  gentle: {
    bg: 'bg-aura-50/90 dark:bg-aura-900/20',
    border: 'border-aura-200/50 dark:border-aura-800/50',
    icon: InformationCircleIcon,
    iconColor: 'text-aura-600 dark:text-aura-400',
    textColor: 'text-aura-800 dark:text-aura-200',
    buttonVariant: 'secondary',
    getMessage: (days) => `Your license expires in ${days} days. Renew to ensure uninterrupted service.`,
  },
  warning: {
    bg: 'bg-warning-50/90 dark:bg-warning-900/20',
    border: 'border-warning-200/50 dark:border-warning-800/50',
    icon: ExclamationTriangleIcon,
    iconColor: 'text-warning-600 dark:text-warning-400',
    textColor: 'text-warning-800 dark:text-warning-200',
    buttonVariant: 'warning',
    getMessage: (days) => `License expiration approaching (${days} days). Please renew soon.`,
  },
  urgent: {
    bg: 'bg-warning-100/90 dark:bg-warning-900/30',
    border: 'border-warning-300/50 dark:border-warning-700/50',
    icon: ExclamationTriangleIcon,
    iconColor: 'text-warning-600 dark:text-warning-400',
    textColor: 'text-warning-900 dark:text-warning-100',
    buttonVariant: 'warning',
    pulse: true,
    getMessage: (days) => `Urgent: License expires in ${days} days. Features may be restricted.`,
  },
  critical: {
    bg: 'bg-critical-50/90 dark:bg-critical-900/20',
    border: 'border-critical-200/50 dark:border-critical-800/50',
    icon: XCircleIcon,
    iconColor: 'text-critical-600 dark:text-critical-400',
    textColor: 'text-critical-800 dark:text-critical-200',
    buttonVariant: 'danger',
    getMessage: (days) => `Critical: License expires in ${days} days. Immediate action required.`,
  },
  expired: {
    bg: 'bg-critical-100/90 dark:bg-critical-900/30',
    border: 'border-critical-300/50 dark:border-critical-700/50',
    icon: XCircleIcon,
    iconColor: 'text-critical-600 dark:text-critical-400',
    textColor: 'text-critical-900 dark:text-critical-100',
    buttonVariant: 'danger',
    getMessage: () => 'License expired. Some features have been disabled.',
  },
};

export default function ExpirationBanner({
  warningLevel,
  onRenew,
  onDismiss,
  dismissable = true,
}) {
  const [dismissed, setDismissed] = useState(false);

  if (!warningLevel || warningLevel.level === 'healthy' || dismissed) {
    return null;
  }

  const config = BANNER_CONFIG[warningLevel.level];
  if (!config) return null;

  const Icon = config.icon;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  return (
    <div
      className={`
        rounded-xl border p-4 mb-6
        ${config.bg} ${config.border}
        ${config.pulse ? 'animate-pulse' : ''}
      `}
      role="alert"
      aria-live={warningLevel.level === 'expired' || warningLevel.level === 'critical' ? 'assertive' : 'polite'}
    >
      <div className="flex items-start gap-3">
        <Icon
          className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.iconColor}`}
          aria-hidden="true"
        />
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${config.textColor}`}>
            {config.getMessage(warningLevel.days)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={onRenew}
              className={`
                px-4 py-1.5 text-sm font-medium rounded-lg
                ${warningLevel.level === 'expired' || warningLevel.level === 'critical'
                  ? 'bg-critical-600 hover:bg-critical-700 text-white'
                  : warningLevel.level === 'urgent' || warningLevel.level === 'warning'
                    ? 'bg-warning-600 hover:bg-warning-700 text-white'
                    : 'bg-aura-600 hover:bg-aura-700 text-white'
                }
                transition-colors duration-200
              `}
            >
              {warningLevel.level === 'expired' ? 'Reactivate License' : 'Renew Now'}
            </button>
            <a
              href="https://aenealabs.com/contact-sales"
              target="_blank"
              rel="noopener noreferrer"
              className={`
                px-4 py-1.5 text-sm font-medium rounded-lg
                bg-white/50 dark:bg-white/10
                hover:bg-surface-50 dark:hover:bg-surface-700
                ${config.textColor}
                transition-colors duration-200
              `}
            >
              Contact Sales
            </a>
          </div>
        </div>
        {dismissable && warningLevel.level !== 'expired' && (
          <button
            onClick={handleDismiss}
            className={`
              p-1 rounded-lg
              hover:bg-black/10 dark:hover:bg-white/10
              ${config.textColor}
              transition-colors duration-200
            `}
            aria-label="Dismiss warning"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
