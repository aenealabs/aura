/**
 * Project Aura - Privacy & AI Training Settings
 *
 * GDPR/CCPA compliant consent management for AI training participation.
 * Implements tiered consent with confirmation modals for data contribution.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheckIcon,
  CpuChipIcon,
  BugAntIcon,
  ChartBarIcon,
  SignalIcon,
  HandThumbUpIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowDownTrayIcon,
  TrashIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

import {
  getConsents,
  grantConsent,
  withdrawConsent,
  withdrawAllDataConsents,
  getConsentAuditLog,
  exportCustomerData,
  requestDataErasure,
  getJurisdiction,
  ConsentType,
  ConsentStatus,
  CONSENT_TYPE_CONFIG,
  formatConsentStatus,
  getDaysUntilExpiry,
  getConsentVersion,
} from '../../services/consentApi';

import ConsentConfirmModal from './ConsentConfirmModal';

// Icon mapping
const CONSENT_ICONS = {
  CpuChipIcon,
  BugAntIcon,
  ChartBarIcon,
  SignalIcon,
  HandThumbUpIcon,
  ArrowPathIcon,
};

/**
 * Toggle Switch Component
 */
function Toggle({ checked, onChange, disabled, ariaLabel }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
        dark:focus:ring-offset-surface-800
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${checked
          ? 'bg-aura-600'
          : 'bg-surface-300 dark:bg-surface-600'
        }
      `}
    >
      <span
        className={`
          inline-block h-4 w-4 transform rounded-full bg-white shadow-md
          transition-transform duration-200 ease-in-out
          ${checked ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  );
}

/**
 * Status Badge Component
 */
function StatusBadge({ status, expiresAt }) {
  const { label, color } = formatConsentStatus(status);
  const daysUntilExpiry = getDaysUntilExpiry(expiresAt);
  const isExpiringSoon = daysUntilExpiry !== null && daysUntilExpiry <= 30;

  const colorStyles = {
    olive: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    surface: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  };

  return (
    <div className="flex items-center gap-2">
      <span className={`px-2 py-0.5 text-xs font-medium rounded ${colorStyles[color]}`}>
        {label}
      </span>
      {status === ConsentStatus.GRANTED && expiresAt && (
        <span className={`text-xs ${isExpiringSoon ? 'text-warning-600' : 'text-surface-500 dark:text-surface-400'}`}>
          {isExpiringSoon && <ClockIcon className="inline h-3 w-3 mr-0.5" />}
          Expires {new Date(expiresAt).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}

/**
 * Individual Consent Card
 */
function ConsentCard({ consentType, consent, onToggle, isLoading }) {
  const [expanded, setExpanded] = useState(false);
  const config = CONSENT_TYPE_CONFIG[consentType];
  const Icon = CONSENT_ICONS[config.icon] || ShieldCheckIcon;
  const isGranted = consent?.status === ConsentStatus.GRANTED;

  return (
    <div className="py-4 border-b border-surface-200 dark:border-surface-700 last:border-b-0">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="p-2 rounded-lg bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400 shrink-0">
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-medium text-surface-900 dark:text-surface-100">
                {config.label}
              </h4>
              {config.tier === 2 && (
                <span className="px-1.5 py-0.5 text-xs bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400 rounded">
                  Data Contribution
                </span>
              )}
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
              {config.description}
            </p>
            {consent && (
              <div className="mt-2">
                <StatusBadge status={consent.status} expiresAt={consent.expires_at} />
              </div>
            )}

            {/* Expandable details */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 mt-2 hover:underline"
              aria-expanded={expanded}
            >
              {expanded ? (
                <>
                  <ChevronUpIcon className="h-3 w-3" />
                  Hide details
                </>
              ) : (
                <>
                  <ChevronDownIcon className="h-3 w-3" />
                  Learn more
                </>
              )}
            </button>

            {expanded && (
              <div className="mt-3 text-sm text-surface-600 dark:text-surface-400 bg-surface-50 dark:bg-surface-700/50 rounded-lg p-3">
                <ul className="list-disc list-inside space-y-1">
                  {config.details.map((detail, idx) => (
                    <li key={idx}>{detail}</li>
                  ))}
                </ul>
                <a
                  href={`/privacy#${consentType}`}
                  className="text-aura-600 dark:text-aura-400 mt-2 inline-block hover:underline"
                >
                  Read full policy
                </a>
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0">
          <Toggle
            checked={isGranted}
            onChange={(checked) => onToggle(consentType, checked)}
            disabled={isLoading}
            ariaLabel={`${config.label} consent is currently ${isGranted ? 'granted' : 'denied'}`}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Consent History Panel
 */
function ConsentHistoryPanel({ auditLog, onExport }) {
  const [expanded, setExpanded] = useState(false);

  const getActionIcon = (action) => {
    switch (action) {
      case 'granted':
        return <CheckCircleIcon className="h-5 w-5 text-olive-600" />;
      case 'withdrawn':
        return <XCircleIcon className="h-5 w-5 text-critical-600" />;
      default:
        return <ClockIcon className="h-5 w-5 text-warning-600" />;
    }
  };

  const formatConsentType = (type) => {
    return CONSENT_TYPE_CONFIG[type]?.label || type;
  };

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Consent History
        </h3>
        <button
          onClick={onExport}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-surface-600 dark:text-surface-400 hover:text-aura-600 dark:hover:text-aura-400 transition-colors"
        >
          <ArrowDownTrayIcon className="h-4 w-4" />
          Export (JSON)
        </button>
      </div>

      {auditLog.length === 0 ? (
        <p className="text-sm text-surface-500 dark:text-surface-400">
          No consent changes recorded yet.
        </p>
      ) : (
        <div className="space-y-4">
          {auditLog.slice(0, expanded ? undefined : 5).map((entry, index) => (
            <div key={entry.audit_id} className="flex gap-3">
              <div className="flex flex-col items-center">
                {getActionIcon(entry.action)}
                {index < (expanded ? auditLog.length : Math.min(5, auditLog.length)) - 1 && (
                  <div className="w-px h-full bg-surface-200 dark:bg-surface-700 mt-2" />
                )}
              </div>
              <div className="flex-1 pb-4">
                <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  {formatConsentType(entry.consent_type)} {entry.action}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                  {new Date(entry.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
          ))}

          {auditLog.length > 5 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-sm text-aura-600 dark:text-aura-400 hover:underline"
            >
              {expanded ? 'Show less' : `Show ${auditLog.length - 5} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Main Privacy & Training Settings Component
 */
export default function PrivacyTrainingSettings() {
  const [consents, setConsents] = useState({});
  const [auditLog, setAuditLog] = useState([]);
  const [jurisdiction, setJurisdiction] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingConsent, setPendingConsent] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showWithdrawAllModal, setShowWithdrawAllModal] = useState(false);

  // Fetch initial data
  useEffect(() => {
    async function fetchData() {
      try {
        setIsLoading(true);
        const [consentsData, auditData, jurisdictionData] = await Promise.all([
          getConsents(),
          getConsentAuditLog(20),
          getJurisdiction(),
        ]);

        // Convert array to object keyed by consent_type
        const consentsMap = {};
        consentsData.forEach(c => {
          consentsMap[c.consent_type] = c;
        });
        setConsents(consentsMap);
        setAuditLog(auditData);
        setJurisdiction(jurisdictionData);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, []);

  // Handle consent toggle
  const handleToggle = useCallback(async (consentType, grant) => {
    const config = CONSENT_TYPE_CONFIG[consentType];

    // Tier 2 consents require confirmation modal when granting
    if (grant && config.tier === 2) {
      setPendingConsent(consentType);
      setShowConfirmModal(true);
      return;
    }

    try {
      setIsLoading(true);
      const updated = grant
        ? await grantConsent(consentType)
        : await withdrawConsent(consentType);

      setConsents(prev => ({
        ...prev,
        [consentType]: updated,
      }));

      // Refresh audit log
      const newAudit = await getConsentAuditLog(20);
      setAuditLog(newAudit);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle confirmed grant (from modal)
  const handleConfirmedGrant = useCallback(async () => {
    if (!pendingConsent) return;

    try {
      setIsLoading(true);
      const updated = await grantConsent(pendingConsent);

      setConsents(prev => ({
        ...prev,
        [pendingConsent]: updated,
      }));

      const newAudit = await getConsentAuditLog(20);
      setAuditLog(newAudit);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
      setShowConfirmModal(false);
      setPendingConsent(null);
    }
  }, [pendingConsent]);

  // Handle withdraw all
  const handleWithdrawAll = useCallback(async () => {
    try {
      setIsLoading(true);
      await withdrawAllDataConsents();

      // Refresh consents
      const consentsData = await getConsents();
      const consentsMap = {};
      consentsData.forEach(c => {
        consentsMap[c.consent_type] = c;
      });
      setConsents(consentsMap);

      const newAudit = await getConsentAuditLog(20);
      setAuditLog(newAudit);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
      setShowWithdrawAllModal(false);
    }
  }, []);

  // Handle data export
  const handleExport = useCallback(async () => {
    try {
      const data = await exportCustomerData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aura-consent-export-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  // Handle data erasure request
  const handleErasureRequest = useCallback(async () => {
    if (!confirm('Are you sure you want to request deletion of all your training data? This cannot be undone.')) {
      return;
    }

    try {
      const result = await requestDataErasure();
      alert(`Data erasure request submitted. Request ID: ${result.request_id}. Estimated completion: ${new Date(result.estimated_completion).toLocaleDateString()}`);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  // Training consents (Tier 2)
  const trainingConsents = [
    ConsentType.TRAINING_DATA,
    ConsentType.SYNTHETIC_BUGS,
    ConsentType.ANONYMIZED_BENCHMARKS,
  ];

  // Platform consents (Tier 1)
  const platformConsents = [
    ConsentType.TELEMETRY,
    ConsentType.FEEDBACK,
    ConsentType.MODEL_UPDATES,
  ];

  if (isLoading && Object.keys(consents).length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Error Alert */}
      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg"
        >
          <ExclamationTriangleIcon className="h-5 w-5 text-critical-600" />
          <p className="text-sm text-critical-700 dark:text-critical-300">{error}</p>
          <button
            onClick={() => setError(null)}
            className="ml-auto text-critical-600 hover:text-critical-800"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-xl">
        <ShieldCheckIcon className="h-6 w-6 text-aura-600 shrink-0" />
        <div>
          <h3 className="font-medium text-surface-900 dark:text-surface-100">
            Privacy & AI Training
          </h3>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
            Control how your data is used to improve Aura&apos;s AI capabilities.
            All data is anonymized and you can withdraw consent at any time.
          </p>
          {jurisdiction && (
            <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 text-xs bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 rounded">
              <InformationCircleIcon className="h-3 w-3" />
              {jurisdiction.jurisdiction} jurisdiction detected
            </span>
          )}
        </div>
      </div>

      {/* Section 1: AI Training Participation */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
          AI Training Participation
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
          Help improve Aura&apos;s AI by contributing anonymized data
        </p>

        <div className="divide-y divide-surface-200 dark:divide-surface-700">
          {trainingConsents.map(type => (
            <ConsentCard
              key={type}
              consentType={type}
              consent={consents[type]}
              onToggle={handleToggle}
              isLoading={isLoading}
            />
          ))}
        </div>
      </div>

      {/* Section 2: Platform Improvement */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
          Platform Improvement
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
          Usage data and feedback to enhance your experience
        </p>

        <div className="divide-y divide-surface-200 dark:divide-surface-700">
          {platformConsents.map(type => (
            <ConsentCard
              key={type}
              consentType={type}
              consent={consents[type]}
              onToggle={handleToggle}
              isLoading={isLoading}
            />
          ))}
        </div>
      </div>

      {/* Section 3: Quick Actions */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Quick Actions
        </h3>
        <button
          onClick={() => setShowWithdrawAllModal(true)}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 border border-critical-300 dark:border-critical-700 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-lg transition-colors disabled:opacity-50"
        >
          <XCircleIcon className="h-4 w-4" />
          Withdraw All Data Consents
        </button>
        <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">
          This will withdraw all AI training consents. Platform consents (telemetry, feedback) must be managed separately.
        </p>
      </div>

      {/* Section 4: Your Data Rights */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
          Your Data Rights
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
          Under {jurisdiction?.jurisdiction || 'GDPR'}, you have the following rights:
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700 hover:bg-surface-200 dark:hover:bg-surface-600 rounded-lg transition-colors"
          >
            <ArrowDownTrayIcon className="h-4 w-4" />
            Download My Data
          </button>
          <button
            onClick={handleErasureRequest}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 bg-critical-50 dark:bg-critical-900/20 hover:bg-critical-100 dark:hover:bg-critical-900/40 rounded-lg transition-colors"
          >
            <TrashIcon className="h-4 w-4" />
            Request Deletion
          </button>
        </div>
      </div>

      {/* Section 5: Consent History */}
      <ConsentHistoryPanel auditLog={auditLog} onExport={handleExport} />

      {/* Consent Version Footer */}
      <p className="text-center text-xs text-surface-400 dark:text-surface-500">
        Consent Version: {getConsentVersion()}
      </p>

      {/* Confirmation Modal for Tier 2 Consents */}
      <ConsentConfirmModal
        isOpen={showConfirmModal}
        consentType={pendingConsent}
        onConfirm={handleConfirmedGrant}
        onCancel={() => {
          setShowConfirmModal(false);
          setPendingConsent(null);
        }}
      />

      {/* Withdraw All Confirmation Modal */}
      {showWithdrawAllModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-critical-100 dark:bg-critical-900/30 rounded-lg">
                <ExclamationTriangleIcon className="h-6 w-6 text-critical-600" />
              </div>
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Withdraw All Data Consents?
              </h3>
            </div>
            <p className="text-sm text-surface-600 dark:text-surface-400 mb-6">
              This will withdraw consent for Training Data, Synthetic Bugs, and Benchmark Reports.
              Your data will be queued for deletion within 30 days.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowWithdrawAllModal(false)}
                className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleWithdrawAll}
                disabled={isLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-critical-600 hover:bg-critical-700 rounded-lg transition-colors disabled:opacity-50"
              >
                Withdraw All
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
