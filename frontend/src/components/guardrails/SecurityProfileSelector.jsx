/**
 * SecurityProfileSelector Component (ADR-069)
 *
 * Allows users to select their security posture through intuitive presets.
 * Frames choices around business outcomes (fewer interruptions vs. more oversight).
 *
 * @module components/guardrails/SecurityProfileSelector
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  ShieldCheckIcon,
  ScaleIcon,
  BoltIcon,
  RocketLaunchIcon,
  CheckCircleIcon,
  LockClosedIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { Tooltip } from '../shared';

/**
 * Security profile definitions
 */
const SECURITY_PROFILES = [
  {
    id: 'conservative',
    name: 'Conservative',
    tagline: 'Maximum oversight for high-risk environments',
    description: 'Every action is reviewed. Best for highly regulated industries or sensitive codebases.',
    features: ['Review all actions', 'Detailed audit logging', 'Maximum context verification'],
    promptsPerDay: '~15 prompts/day',
    icon: ShieldCheckIcon,
    iconColor: 'olive',
    recommended: false,
  },
  {
    id: 'balanced',
    name: 'Balanced',
    tagline: 'Recommended balance of speed and safety',
    description: 'Auto-approve safe operations while requiring review for risky changes.',
    features: ['Auto-approve safe ops', 'Review risky operations', 'Standard audit logging'],
    promptsPerDay: '~5 prompts/day',
    icon: ScaleIcon,
    iconColor: 'aura',
    recommended: true,
  },
  {
    id: 'efficient',
    name: 'Efficient',
    tagline: 'Minimal interruptions for trusted teams',
    description: 'Only critical operations require human review. For experienced teams with established trust.',
    features: ['Review critical only', 'Standard logging', 'Faster autonomous operations'],
    promptsPerDay: '~2 prompts/day',
    icon: BoltIcon,
    iconColor: 'warning',
    recommended: false,
  },
  {
    id: 'aggressive',
    name: 'Aggressive',
    tagline: 'Maximum autonomy for experienced users',
    description: 'Minimal interruptions. Only the most critical operations require approval.',
    features: ['Critical-only review', 'Essential logging', 'Maximum AI autonomy'],
    promptsPerDay: '~0-1 prompts/day',
    icon: RocketLaunchIcon,
    iconColor: 'critical',
    recommended: false,
  },
];

/**
 * Color mappings for profile icons and accents
 */
const COLOR_MAP = {
  olive: {
    icon: 'text-olive-600 dark:text-olive-400',
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    border: 'border-olive-500',
    ring: 'ring-olive-500/20',
    selectedBg: 'bg-olive-50 dark:bg-olive-900/20',
  },
  aura: {
    icon: 'text-aura-600 dark:text-aura-400',
    bg: 'bg-aura-100 dark:bg-aura-900/30',
    border: 'border-aura-500',
    ring: 'ring-aura-500/20',
    selectedBg: 'bg-aura-50 dark:bg-aura-900/20',
  },
  warning: {
    icon: 'text-warning-600 dark:text-warning-400',
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    border: 'border-warning-500',
    ring: 'ring-warning-500/20',
    selectedBg: 'bg-warning-50 dark:bg-warning-900/20',
  },
  critical: {
    icon: 'text-critical-600 dark:text-critical-400',
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    border: 'border-critical-500',
    ring: 'ring-critical-500/20',
    selectedBg: 'bg-critical-50 dark:bg-critical-900/20',
  },
};

/**
 * ProfileCard - Individual profile selection card
 */
function ProfileCard({ profile, isSelected, isLocked, lockedReason, onSelect }) {
  const Icon = profile.icon;
  const colors = COLOR_MAP[profile.iconColor];

  const handleClick = () => {
    if (!isLocked) {
      onSelect(profile.id);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <div
      role="radio"
      aria-checked={isSelected}
      aria-disabled={isLocked}
      tabIndex={isLocked ? -1 : 0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`
        relative rounded-xl p-4 transition-all duration-200
        ${
          isLocked
            ? 'opacity-60 cursor-not-allowed bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700'
            : isSelected
            ? 'cursor-pointer border-2 border-aura-500 ring-2 ring-aura-500/20 bg-aura-50 dark:bg-aura-900'
            : 'cursor-pointer border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600 hover:shadow-md'
        }
      `}
    >
      {/* Locked overlay */}
      {isLocked && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-surface-100/80 dark:bg-surface-800/80 z-10">
          <Tooltip content={lockedReason || 'Locked by compliance requirements'}>
            <div className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400">
              <LockClosedIcon className="w-5 h-5" />
              <span>Locked</span>
            </div>
          </Tooltip>
        </div>
      )}

      {/* Recommended badge */}
      {profile.recommended && (
        <div className="absolute -top-2 -right-2 px-2 py-0.5 text-xs font-medium rounded-full bg-aura-600 text-white">
          Recommended
        </div>
      )}

      {/* Selection indicator */}
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg ${colors.bg}`}>
          <Icon className={`w-6 h-6 ${colors.icon}`} />
        </div>
        {isSelected ? (
          <CheckCircleIcon className={`w-6 h-6 ${colors.icon}`} />
        ) : (
          <div className="w-6 h-6 rounded-full border-2 border-surface-300 dark:border-surface-600" />
        )}
      </div>

      {/* Content */}
      <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
        {profile.name}
      </h3>
      <p className="text-sm text-surface-600 dark:text-surface-400 mb-3">
        {profile.tagline}
      </p>

      {/* Features list */}
      <ul className="space-y-1.5 mb-3">
        {profile.features.map((feature, index) => (
          <li
            key={index}
            className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-surface-400 dark:bg-surface-500" />
            {feature}
          </li>
        ))}
      </ul>

      {/* Prompts estimate */}
      <div className="pt-3 border-t border-surface-200 dark:border-surface-700">
        <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
          {profile.promptsPerDay}
        </p>
      </div>
    </div>
  );
}

ProfileCard.propTypes = {
  profile: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    tagline: PropTypes.string.isRequired,
    description: PropTypes.string,
    features: PropTypes.arrayOf(PropTypes.string).isRequired,
    promptsPerDay: PropTypes.string.isRequired,
    icon: PropTypes.elementType.isRequired,
    iconColor: PropTypes.string.isRequired,
    recommended: PropTypes.bool,
  }).isRequired,
  isSelected: PropTypes.bool.isRequired,
  isLocked: PropTypes.bool,
  lockedReason: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
};

/**
 * SecurityProfileSelector - Main profile selection component
 *
 * @param {Object} props
 * @param {string} props.selectedProfile - Currently selected profile ID
 * @param {Function} props.onProfileChange - Callback when profile changes
 * @param {Array<string>} [props.lockedProfiles=[]] - Profile IDs locked by compliance
 * @param {Object} [props.lockedReasons={}] - Reasons for locked profiles
 * @param {boolean} [props.showHelp=true] - Show help button
 * @param {Function} [props.onHelpClick] - Callback when help clicked
 * @param {string} [props.className] - Additional CSS classes
 */
function SecurityProfileSelector({
  selectedProfile,
  onProfileChange,
  lockedProfiles = [],
  lockedReasons = {},
  showHelp = true,
  onHelpClick,
  className = '',
}) {
  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Security Profile
          </h2>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            Choose how Aura balances speed and safety for your organization
          </p>
        </div>
        {showHelp && (
          <button
            onClick={onHelpClick}
            className="p-2 rounded-lg text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
            aria-label="Learn more about security profiles"
          >
            <InformationCircleIcon className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Profile grid */}
      <div
        role="radiogroup"
        aria-label="Security profile selection"
        className="grid grid-cols-1 md:grid-cols-2 gap-4"
      >
        {SECURITY_PROFILES.map((profile) => (
          <ProfileCard
            key={profile.id}
            profile={profile}
            isSelected={selectedProfile === profile.id}
            isLocked={lockedProfiles.includes(profile.id)}
            lockedReason={lockedReasons[profile.id]}
            onSelect={onProfileChange}
          />
        ))}
      </div>
    </div>
  );
}

SecurityProfileSelector.propTypes = {
  selectedProfile: PropTypes.string.isRequired,
  onProfileChange: PropTypes.func.isRequired,
  lockedProfiles: PropTypes.arrayOf(PropTypes.string),
  lockedReasons: PropTypes.object,
  showHelp: PropTypes.bool,
  onHelpClick: PropTypes.func,
  className: PropTypes.string,
};

export default SecurityProfileSelector;
export { SECURITY_PROFILES };
