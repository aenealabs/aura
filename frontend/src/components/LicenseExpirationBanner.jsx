/**
 * License Expiration Banner Component
 *
 * App-level banner that displays license expiration warnings.
 * This component is shown globally across all pages when the
 * license is approaching expiration or has expired.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ExclamationTriangleIcon,
  XMarkIcon,
  ArrowTopRightOnSquareIcon,
  ClockIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import { useEdition } from '../context/EditionContext';

const WARNING_CONFIGS = {
  gentle: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    text: 'text-aura-700 dark:text-aura-300',
    icon: ClockIcon,
    iconColor: 'text-aura-500',
  },
  warning: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-800',
    text: 'text-warning-700 dark:text-warning-300',
    icon: ExclamationTriangleIcon,
    iconColor: 'text-warning-500',
  },
  urgent: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    border: 'border-warning-300 dark:border-warning-700',
    text: 'text-warning-800 dark:text-warning-200',
    icon: ExclamationTriangleIcon,
    iconColor: 'text-warning-600',
  },
  critical: {
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    border: 'border-critical-200 dark:border-critical-800',
    text: 'text-critical-700 dark:text-critical-300',
    icon: ExclamationCircleIcon,
    iconColor: 'text-critical-500',
  },
  expired: {
    bg: 'bg-critical-100 dark:bg-critical-900/40',
    border: 'border-critical-300 dark:border-critical-700',
    text: 'text-critical-800 dark:text-critical-200',
    icon: ExclamationCircleIcon,
    iconColor: 'text-critical-600',
  },
};

export default function LicenseExpirationBanner() {
  const { warningLevel, edition } = useEdition();
  const [dismissed, setDismissed] = useState(false);

  // Don't show if no warning or already dismissed (unless expired)
  if (!warningLevel || warningLevel.level === 'healthy') {
    return null;
  }

  // Expired banners cannot be dismissed
  const canDismiss = warningLevel.level !== 'expired';

  if (dismissed && canDismiss) {
    return null;
  }

  const config = WARNING_CONFIGS[warningLevel.level] || WARNING_CONFIGS.warning;
  const Icon = config.icon;

  // Generate message based on warning level
  const getMessage = () => {
    if (warningLevel.level === 'expired') {
      return 'Your license has expired. Some features may be disabled.';
    }
    return `Your ${edition?.edition || 'Enterprise'} license expires in ${warningLevel.daysRemaining} days.`;
  };

  // Action button based on level
  const getAction = () => {
    if (warningLevel.level === 'expired') {
      return (
        <Link
          to="/settings?tab=edition"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-critical-600 hover:bg-critical-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Renew Now
          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
        </Link>
      );
    }

    if (warningLevel.level === 'critical' || warningLevel.level === 'urgent') {
      return (
        <Link
          to="/settings?tab=edition"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-warning-600 hover:bg-warning-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Renew License
        </Link>
      );
    }

    return (
      <Link
        to="/settings?tab=edition"
        className={`${config.text} hover:underline text-sm font-medium`}
      >
        Manage License
      </Link>
    );
  };

  return (
    <div
      className={`
        ${config.bg} ${config.border} border-b
        px-4 py-2.5 flex items-center justify-between gap-4
      `}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <Icon className={`h-5 w-5 ${config.iconColor} flex-shrink-0`} />
        <p className={`${config.text} text-sm truncate`}>
          {getMessage()}
        </p>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        {getAction()}

        {canDismiss && (
          <button
            onClick={() => setDismissed(true)}
            className={`
              p-1 rounded-md ${config.text}
              hover:bg-black/5 dark:hover:bg-white/5
              transition-colors
            `}
            aria-label="Dismiss notification"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
