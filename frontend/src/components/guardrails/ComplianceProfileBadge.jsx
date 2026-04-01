/**
 * ComplianceProfileBadge Component (ADR-069)
 *
 * Displays active compliance profile with locked settings indicator.
 * Shows when settings are restricted by compliance requirements.
 *
 * @module components/guardrails/ComplianceProfileBadge
 */

import React from 'react';
import PropTypes from 'prop-types';
import { LockClosedIcon, InformationCircleIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';
import { Tooltip } from '../shared';

/**
 * Compliance profile configurations
 */
const COMPLIANCE_PROFILES = {
  cmmc_l2: {
    id: 'cmmc_l2',
    label: 'CMMC Level 2',
    shortLabel: 'CMMC L2',
    color: 'olive',
    description: 'Cybersecurity Maturity Model Certification - Level 2',
  },
  cmmc_l3: {
    id: 'cmmc_l3',
    label: 'CMMC Level 3',
    shortLabel: 'CMMC L3',
    color: 'aura',
    description: 'Cybersecurity Maturity Model Certification - Level 3',
  },
  soc2: {
    id: 'soc2',
    label: 'SOC 2 Type II',
    shortLabel: 'SOC 2',
    color: 'aura',
    description: 'Service Organization Control 2 Type II Compliance',
  },
  fedramp_moderate: {
    id: 'fedramp_moderate',
    label: 'FedRAMP Moderate',
    shortLabel: 'FedRAMP',
    color: 'warning',
    description: 'Federal Risk and Authorization Management Program - Moderate',
  },
  fedramp_high: {
    id: 'fedramp_high',
    label: 'FedRAMP High',
    shortLabel: 'FedRAMP High',
    color: 'critical',
    description: 'Federal Risk and Authorization Management Program - High',
  },
  hipaa: {
    id: 'hipaa',
    label: 'HIPAA',
    shortLabel: 'HIPAA',
    color: 'warning',
    description: 'Health Insurance Portability and Accountability Act',
  },
  nist_800_53: {
    id: 'nist_800_53',
    label: 'NIST 800-53',
    shortLabel: 'NIST',
    color: 'aura',
    description: 'NIST Special Publication 800-53 Security Controls',
  },
};

/**
 * Color mappings for compliance badges
 */
const COLOR_MAP = {
  olive: {
    bg: 'bg-olive-50 dark:bg-olive-900/20',
    border: 'border-olive-200 dark:border-olive-800',
    text: 'text-olive-700 dark:text-olive-400',
    icon: 'text-olive-500',
  },
  aura: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    text: 'text-aura-700 dark:text-aura-400',
    icon: 'text-aura-500',
  },
  warning: {
    bg: 'bg-warning-50 dark:bg-warning-900/20',
    border: 'border-warning-200 dark:border-warning-800',
    text: 'text-warning-700 dark:text-warning-400',
    icon: 'text-warning-500',
  },
  critical: {
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    border: 'border-critical-200 dark:border-critical-800',
    text: 'text-critical-700 dark:text-critical-400',
    icon: 'text-critical-500',
  },
};

/**
 * ComplianceProfileBadge - Main component
 *
 * @param {Object} props
 * @param {string} props.profile - Compliance profile ID
 * @param {number} [props.lockedSettingsCount] - Number of locked settings
 * @param {Array<string>} [props.lockedSettings] - List of locked setting names
 * @param {boolean} [props.showDetails=true] - Show locked count details
 * @param {'sm' | 'md' | 'lg'} [props.size='md'] - Badge size
 * @param {string} [props.className] - Additional CSS classes
 */
function ComplianceProfileBadge({
  profile,
  lockedSettingsCount = 0,
  lockedSettings = [],
  showDetails = true,
  size = 'md',
  className = '',
}) {
  const profileConfig = COMPLIANCE_PROFILES[profile];

  if (!profileConfig) {
    return null;
  }

  const colors = COLOR_MAP[profileConfig.color] || COLOR_MAP.aura;

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs gap-1.5',
    md: 'px-3 py-2 text-sm gap-2',
    lg: 'px-4 py-2.5 text-base gap-2.5',
  };

  const iconSizes = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const tooltipContent = (
    <div className="space-y-2 max-w-xs">
      <div className="font-medium">{profileConfig.label}</div>
      <div className="text-surface-300">{profileConfig.description}</div>
      {lockedSettings.length > 0 && (
        <div className="pt-2 border-t border-surface-700">
          <div className="text-surface-400 mb-1">Locked settings:</div>
          <ul className="text-surface-300 space-y-0.5">
            {lockedSettings.slice(0, 5).map((setting, i) => (
              <li key={i}>• {setting}</li>
            ))}
            {lockedSettings.length > 5 && (
              <li className="text-surface-400">
                ...and {lockedSettings.length - 5} more
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );

  return (
    <Tooltip content={tooltipContent} position="bottom">
      <div
        className={`
          inline-flex items-center rounded-lg
          border ${colors.bg} ${colors.border}
          ${sizeClasses[size]}
          ${className}
        `}
      >
        <ShieldCheckIcon className={`${iconSizes[size]} ${colors.icon}`} />
        <span className={`font-medium ${colors.text}`}>
          {size === 'sm' ? profileConfig.shortLabel : profileConfig.label}
        </span>

        {showDetails && lockedSettingsCount > 0 && (
          <>
            <span className="text-surface-400">|</span>
            <div className="flex items-center gap-1">
              <LockClosedIcon className={`${iconSizes[size]} text-surface-500`} />
              <span className="text-surface-600 dark:text-surface-400">
                {lockedSettingsCount} locked
              </span>
            </div>
          </>
        )}

        <InformationCircleIcon
          className={`${iconSizes[size]} text-surface-400 ml-0.5`}
        />
      </div>
    </Tooltip>
  );
}

ComplianceProfileBadge.propTypes = {
  profile: PropTypes.oneOf(Object.keys(COMPLIANCE_PROFILES)).isRequired,
  lockedSettingsCount: PropTypes.number,
  lockedSettings: PropTypes.arrayOf(PropTypes.string),
  showDetails: PropTypes.bool,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  className: PropTypes.string,
};

/**
 * ComplianceProfileSelector - Dropdown for selecting compliance profile
 */
function ComplianceProfileSelector({ value, onChange, disabled, className = '' }) {
  return (
    <div className={className}>
      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
        Compliance Profile
      </label>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled}
        className="w-full px-3 py-2 rounded-lg
                   border border-surface-300 dark:border-surface-600
                   bg-white dark:bg-surface-700
                   text-surface-900 dark:text-surface-100
                   focus:ring-2 focus:ring-aura-500 focus:border-aura-500
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="">None (Custom Configuration)</option>
        {Object.values(COMPLIANCE_PROFILES).map((profile) => (
          <option key={profile.id} value={profile.id}>
            {profile.label}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
        Selecting a profile may lock certain settings to meet compliance requirements
      </p>
    </div>
  );
}

ComplianceProfileSelector.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  className: PropTypes.string,
};

export default ComplianceProfileBadge;
export { ComplianceProfileSelector, COMPLIANCE_PROFILES };
