/**
 * Project Aura - Security Alert Settings Component
 *
 * Configure alert thresholds for anomaly detection and security events.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldExclamationIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  BellAlertIcon,
  EyeIcon,
  LockClosedIcon,
  ServerStackIcon,
  UserGroupIcon,
  ChartBarIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';

// Alert categories and their thresholds
const ALERT_CATEGORIES = {
  authentication: {
    label: 'Authentication',
    description: 'Login failures, suspicious access patterns',
    icon: LockClosedIcon,
    color: 'critical',
    thresholds: [
      { id: 'failed_logins', label: 'Failed Login Attempts', unit: 'per 15 min', default: 5, min: 1, max: 50 },
      { id: 'suspicious_ips', label: 'Unique Suspicious IPs', unit: 'per hour', default: 3, min: 1, max: 20 },
      { id: 'credential_stuffing', label: 'Credential Stuffing Pattern', unit: 'attempts', default: 10, min: 5, max: 100 },
    ],
  },
  agent_behavior: {
    label: 'Agent Behavior',
    description: 'Unusual agent activity, potential compromise',
    icon: ServerStackIcon,
    color: 'warning',
    thresholds: [
      { id: 'agent_error_rate', label: 'Agent Error Rate', unit: '% per hour', default: 25, min: 5, max: 100 },
      { id: 'unusual_tool_calls', label: 'Unusual Tool Call Patterns', unit: 'deviation %', default: 50, min: 10, max: 200 },
      { id: 'sandbox_escape_attempts', label: 'Sandbox Escape Attempts', unit: 'per day', default: 1, min: 1, max: 10 },
    ],
  },
  data_access: {
    label: 'Data Access',
    description: 'Sensitive data access, exfiltration attempts',
    icon: EyeIcon,
    color: 'warning',
    thresholds: [
      { id: 'bulk_data_access', label: 'Bulk Data Access', unit: 'records', default: 1000, min: 100, max: 10000 },
      { id: 'sensitive_queries', label: 'Sensitive Data Queries', unit: 'per hour', default: 10, min: 1, max: 100 },
      { id: 'export_volume', label: 'Data Export Volume', unit: 'MB/hour', default: 100, min: 10, max: 1000 },
    ],
  },
  network: {
    label: 'Network Activity',
    description: 'Unusual network patterns, potential C2',
    icon: ChartBarIcon,
    color: 'aura',
    thresholds: [
      { id: 'outbound_connections', label: 'New Outbound Connections', unit: 'per hour', default: 50, min: 10, max: 500 },
      { id: 'dns_queries', label: 'Unusual DNS Queries', unit: 'per hour', default: 100, min: 20, max: 1000 },
      { id: 'lateral_movement', label: 'Lateral Movement Attempts', unit: 'per day', default: 3, min: 1, max: 20 },
    ],
  },
  compliance: {
    label: 'Compliance',
    description: 'Policy violations, audit failures',
    icon: UserGroupIcon,
    color: 'olive',
    thresholds: [
      { id: 'policy_violations', label: 'Policy Violations', unit: 'per day', default: 5, min: 1, max: 50 },
      { id: 'unauthorized_access', label: 'Unauthorized Access Attempts', unit: 'per hour', default: 3, min: 1, max: 20 },
      { id: 'audit_failures', label: 'Audit Check Failures', unit: 'per day', default: 3, min: 1, max: 20 },
    ],
  },
};

// Severity levels for alerts
const SEVERITY_LEVELS = {
  critical: {
    label: 'Critical',
    description: 'Immediate action required',
    color: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    multiplier: 1,
  },
  high: {
    label: 'High',
    description: 'Investigate within 1 hour',
    color: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    multiplier: 1.5,
  },
  medium: {
    label: 'Medium',
    description: 'Investigate within 4 hours',
    color: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    multiplier: 2,
  },
  low: {
    label: 'Low',
    description: 'Review in daily report',
    color: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    multiplier: 3,
  },
};

const COLOR_STYLES = {
  critical: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
  warning: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
  aura: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
  olive: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
};

/**
 * Threshold Slider Component
 */
function ThresholdSlider({ threshold, value, onChange, disabled }) {
  const _percentage = ((value - threshold.min) / (threshold.max - threshold.min)) * 100;

  return (
    <div className="py-3 border-b border-surface-100 dark:border-surface-700/50 last:border-0">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
          {threshold.label}
        </span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={threshold.min}
            max={threshold.max}
            value={value}
            onChange={(e) => onChange(parseInt(e.target.value))}
            disabled={disabled}
            className="w-20 px-2 py-1 text-sm text-right border border-surface-300 dark:border-surface-600 rounded bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 disabled:opacity-50"
          />
          <span className="text-xs text-surface-500 dark:text-surface-400 w-20">
            {threshold.unit}
          </span>
        </div>
      </div>
      <input
        type="range"
        min={threshold.min}
        max={threshold.max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        disabled={disabled}
        className="w-full h-2 bg-surface-200 dark:bg-surface-700 rounded-lg appearance-none cursor-pointer accent-aura-600 disabled:opacity-50"
      />
      <div className="flex justify-between text-xs text-surface-400 mt-1">
        <span>{threshold.min}</span>
        <span className="text-surface-500 dark:text-surface-400">Default: {threshold.default}</span>
        <span>{threshold.max}</span>
      </div>
    </div>
  );
}

/**
 * Alert Category Panel Component
 */
function AlertCategoryPanel({ categoryKey, category, thresholds, onChange, isLoading }) {
  const [expanded, setExpanded] = useState(true);
  const Icon = category.icon || ShieldExclamationIcon;
  const colorClass = COLOR_STYLES[category.color] || COLOR_STYLES.aura;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-surface-50 dark:hover:bg-surface-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${colorClass}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="text-left">
            <h4 className="font-medium text-surface-900 dark:text-surface-100">
              {category.label}
            </h4>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              {category.description}
            </p>
          </div>
        </div>
        <ChartBarIcon className={`h-5 w-5 text-surface-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-surface-200 dark:border-surface-700">
          {category.thresholds.map((threshold) => (
            <ThresholdSlider
              key={threshold.id}
              threshold={threshold}
              value={thresholds[threshold.id] || threshold.default}
              onChange={(value) => onChange(categoryKey, threshold.id, value)}
              disabled={isLoading}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Severity Configuration Panel
 */
function SeverityConfigPanel({ config: _config, onChange: _onChange, isLoading: _isLoading }) {
  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
      <div className="flex items-center gap-2 mb-4">
        <BellAlertIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
        <h3 className="font-semibold text-surface-900 dark:text-surface-100">
          Severity Escalation
        </h3>
      </div>

      <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
        Configure how thresholds escalate to different severity levels.
        Higher severity triggers faster response requirements.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(SEVERITY_LEVELS).map(([level, levelConfig]) => (
          <div
            key={level}
            className={`p-4 rounded-lg ${levelConfig.color}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{levelConfig.label}</span>
              <span className="text-xs">{levelConfig.multiplier}x threshold</span>
            </div>
            <p className="text-xs opacity-75">{levelConfig.description}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
        <InformationCircleIcon className="h-5 w-5 text-surface-500 flex-shrink-0" />
        <p className="text-sm text-surface-600 dark:text-surface-400">
          Critical alerts are triggered at base threshold. High at 1.5x, Medium at 2x, and Low at 3x.
        </p>
      </div>
    </div>
  );
}

/**
 * Alert Dashboard Link Component
 *
 * Directs users to the main Security Alerts page for viewing and responding to alerts.
 * This settings page is for configuring thresholds, not monitoring alerts.
 */
function AlertDashboardLink() {
  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
      <div className="flex items-start gap-4">
        <div className="p-3 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
          <BellAlertIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">
            View Active Alerts
          </h3>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1 mb-4">
            Monitor and respond to security alerts in the Security Alerts dashboard.
            This settings page configures when alerts trigger, not alert status.
          </p>
          <Link
            to="/security/alerts"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
          >
            <span>Go to Security Alerts</span>
            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}

/**
 * Main Security Alert Settings Component
 */
export default function SecurityAlertSettings({ onSuccess, onError }) {
  const [thresholds, setThresholds] = useState(() => {
    const initial = {};
    Object.entries(ALERT_CATEGORIES).forEach(([categoryKey, category]) => {
      initial[categoryKey] = {};
      category.thresholds.forEach((threshold) => {
        initial[categoryKey][threshold.id] = threshold.default;
      });
    });
    return initial;
  });
  const [_loading, _setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const handleThresholdChange = (categoryKey, thresholdId, value) => {
    setThresholds(prev => ({
      ...prev,
      [categoryKey]: {
        ...prev[categoryKey],
        [thresholdId]: value,
      },
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // In real implementation, this would save to API
      await new Promise(resolve => setTimeout(resolve, 1000));
      setHasChanges(false);
      onSuccess?.('Security alert thresholds updated');
    } catch (err) {
      onError?.(`Failed to update thresholds: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleResetAll = () => {
    const initial = {};
    Object.entries(ALERT_CATEGORIES).forEach(([categoryKey, category]) => {
      initial[categoryKey] = {};
      category.thresholds.forEach((threshold) => {
        initial[categoryKey][threshold.id] = threshold.default;
      });
    });
    setThresholds(initial);
    setHasChanges(false);
  };

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <ShieldExclamationIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-medium text-aura-800 dark:text-aura-200">Alert Threshold Configuration</h4>
          <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
            Configure thresholds that determine when security alerts are triggered.
            To view and respond to active alerts, visit the Security Alerts dashboard.
          </p>
        </div>
      </div>

      {/* Link to Security Alerts Dashboard */}
      <AlertDashboardLink />

      {/* Severity Configuration */}
      <SeverityConfigPanel
        config={{}}
        onChange={() => {}}
        isLoading={saving}
      />

      {/* Alert Categories */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Alert Thresholds by Category
        </h3>
        <div className="space-y-4">
          {Object.entries(ALERT_CATEGORIES).map(([categoryKey, category]) => (
            <AlertCategoryPanel
              key={categoryKey}
              categoryKey={categoryKey}
              category={category}
              thresholds={thresholds[categoryKey]}
              onChange={handleThresholdChange}
              isLoading={saving}
            />
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      {hasChanges && (
        <div className="flex justify-end gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={handleResetAll}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Reset All to Defaults
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <>
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircleIcon className="h-4 w-4" />
                Save Thresholds
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
