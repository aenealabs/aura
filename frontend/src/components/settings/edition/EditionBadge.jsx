/**
 * Edition Badge Component
 *
 * Displays the current edition with appropriate styling.
 */

import { SparklesIcon, BuildingOffice2Icon, ShieldCheckIcon } from '@heroicons/react/24/solid';

const EDITION_CONFIG = {
  community: {
    label: 'Community',
    description: 'Free & Open Source',
    icon: SparklesIcon,
    className: 'bg-surface-100 dark:bg-surface-700/50 border-surface-300 dark:border-surface-600 text-surface-700 dark:text-surface-300',
    iconClassName: 'text-surface-500 dark:text-surface-400',
  },
  enterprise: {
    label: 'Enterprise',
    description: 'Commercial License',
    icon: BuildingOffice2Icon,
    className: 'bg-aura-100 dark:bg-aura-900/30 border-aura-300 dark:border-aura-800 text-aura-700 dark:text-aura-300',
    iconClassName: 'text-aura-600 dark:text-aura-400',
  },
  enterprise_plus: {
    label: 'Enterprise Plus',
    description: 'Air-Gap & GovCloud Ready',
    icon: ShieldCheckIcon,
    className: 'bg-gradient-to-r from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/30 border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300',
    iconClassName: 'text-amber-600 dark:text-amber-400',
  },
};

export default function EditionBadge({ edition, size = 'default', showDescription = false }) {
  const config = EDITION_CONFIG[edition] || EDITION_CONFIG.community;
  const Icon = config.icon;

  const sizeClasses = {
    small: 'px-2 py-1 text-xs',
    default: 'px-3 py-1.5 text-sm',
    large: 'px-4 py-2 text-base',
  };

  const iconSizes = {
    small: 'h-3.5 w-3.5',
    default: 'h-4 w-4',
    large: 'h-5 w-5',
  };

  return (
    <div
      className={`
        inline-flex items-center gap-2 rounded-lg border font-medium
        ${config.className}
        ${sizeClasses[size]}
      `}
      role="status"
      aria-label={`Current edition: ${config.label}`}
    >
      <Icon className={`${iconSizes[size]} ${config.iconClassName}`} />
      <span>{config.label}</span>
      {showDescription && (
        <span className="text-xs opacity-70 ml-1">({config.description})</span>
      )}
    </div>
  );
}
