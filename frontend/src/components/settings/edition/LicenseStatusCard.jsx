/**
 * License Status Card Component
 *
 * Hero card displaying current license status, organization, and expiration.
 */

import { CheckCircleIcon, XCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import EditionBadge from './EditionBadge';

function formatDate(dateString) {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function getDaysRemaining(expiresAt) {
  if (!expiresAt) return null;
  const now = new Date();
  const expiry = new Date(expiresAt);
  return Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
}

function getExpirationColor(daysRemaining) {
  if (daysRemaining === null) return 'bg-surface-500';
  if (daysRemaining <= 0) return 'bg-critical-500';
  if (daysRemaining <= 7) return 'bg-critical-500';
  if (daysRemaining <= 14) return 'bg-warning-500';
  if (daysRemaining <= 30) return 'bg-warning-400';
  return 'bg-aura-500';
}

export default function LicenseStatusCard({
  edition,
  license,
  onSync,
  onManage,
  syncing = false,
}) {
  const isCommunity = edition?.edition === 'community';
  const isValid = license?.is_valid && !license?.is_expired;
  const daysRemaining = getDaysRemaining(license?.expires_at);
  const expirationPercent = daysRemaining !== null && daysRemaining > 0
    ? Math.min(100, Math.max(0, (daysRemaining / 365) * 100))
    : 0;

  return (
    <div
      className="
        bg-white dark:bg-surface-800
        backdrop-blur-xl
        rounded-xl
        border border-surface-200/50 dark:border-surface-700/30
        p-6
        shadow-sm
      "
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <EditionBadge edition={edition?.edition} size="large" />
        <div className="flex items-center gap-2">
          {!isCommunity && (
            <button
              onClick={onSync}
              disabled={syncing}
              className="
                inline-flex items-center gap-1.5 px-3 py-1.5
                text-sm font-medium text-surface-700 dark:text-surface-300
                bg-surface-100 dark:bg-surface-700/50
                hover:bg-surface-200 dark:hover:bg-surface-700
                rounded-lg border border-surface-200 dark:border-surface-600
                transition-colors duration-200
                disabled:opacity-50 disabled:cursor-not-allowed
              "
              aria-label="Sync license with server"
            >
              <ArrowPathIcon
                className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`}
              />
              Sync
            </button>
          )}
          <button
            onClick={onManage}
            className="
              inline-flex items-center gap-1.5 px-3 py-1.5
              text-sm font-medium text-aura-700 dark:text-aura-300
              bg-aura-50 dark:bg-aura-900/30
              hover:bg-aura-100 dark:hover:bg-aura-900/50
              rounded-lg border border-aura-200 dark:border-aura-800
              transition-colors duration-200
            "
          >
            Manage License
          </button>
        </div>
      </div>

      {/* Community Edition - Simple message */}
      {isCommunity ? (
        <div className="space-y-4">
          <p className="text-surface-600 dark:text-surface-400">
            You&apos;re using the Community Edition - free and open source with basic features.
          </p>
          <div className="flex items-center gap-4 text-sm text-surface-500 dark:text-surface-400">
            <span className="flex items-center gap-1.5">
              <span className="font-medium text-surface-700 dark:text-surface-300">
                {edition?.feature_count || 0}
              </span>
              Features
            </span>
            <span className="text-surface-300 dark:text-surface-600">|</span>
            <span>No License Required</span>
          </div>
        </div>
      ) : (
        <>
          {/* Organization & License Key */}
          <div className="space-y-2 mb-6">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-surface-500 dark:text-surface-400">Organization:</span>
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {license?.organization || 'Unknown'}
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-surface-500 dark:text-surface-400">License Key:</span>
              <code className="font-mono text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-700/50 px-2 py-0.5 rounded">
                {license?.license_key || 'Not set'}
              </code>
            </div>
          </div>

          {/* Status & Expiration */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {/* Status */}
            <div className="bg-surface-50 dark:bg-surface-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                {isValid ? (
                  <CheckCircleIcon className="h-5 w-5 text-olive-500" />
                ) : (
                  <XCircleIcon className="h-5 w-5 text-critical-500" />
                )}
                <span className="text-sm font-medium text-surface-500 dark:text-surface-400">
                  STATUS
                </span>
              </div>
              <p className={`text-lg font-semibold ${isValid ? 'text-olive-600 dark:text-olive-400' : 'text-critical-600 dark:text-critical-400'}`}>
                {isValid ? 'Valid' : license?.is_expired ? 'Expired' : 'Invalid'}
              </p>
              {license?.validation_error && (
                <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                  {license.validation_error}
                </p>
              )}
            </div>

            {/* Expiration */}
            <div className="bg-surface-50 dark:bg-surface-700/30 rounded-lg p-4">
              <div className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-1">
                EXPIRATION
              </div>
              <p className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-2">
                {license?.expires_at ? formatDate(license.expires_at) : 'Never'}
              </p>
              {daysRemaining !== null && (
                <>
                  <div className="flex justify-between text-xs text-surface-500 dark:text-surface-400 mb-1">
                    <span>{daysRemaining > 0 ? `${daysRemaining} days remaining` : 'Expired'}</span>
                  </div>
                  <div className="h-2 bg-surface-200 dark:bg-surface-600 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${getExpirationColor(daysRemaining)}`}
                      style={{ width: `${expirationPercent}%` }}
                      role="progressbar"
                      aria-valuenow={daysRemaining}
                      aria-valuemin={0}
                      aria-valuemax={365}
                      aria-label={`${daysRemaining} days until license expiration`}
                    />
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Footer Stats */}
          <div className="flex flex-wrap items-center gap-4 text-sm text-surface-500 dark:text-surface-400 pt-4 border-t border-surface-200/50 dark:border-surface-700/30">
            <span className="flex items-center gap-1.5">
              <span className="font-medium text-surface-700 dark:text-surface-300">
                {edition?.feature_count || 0}
              </span>
              Features
            </span>
            <span className="text-surface-300 dark:text-surface-600">|</span>
            <span className="flex items-center gap-1.5">
              <span className="font-medium text-surface-700 dark:text-surface-300">
                {license?.support_tier || 'Basic'}
              </span>
              Support
            </span>
            {license?.max_users && (
              <>
                <span className="text-surface-300 dark:text-surface-600">|</span>
                <span className="flex items-center gap-1.5">
                  <span className="font-medium text-surface-700 dark:text-surface-300">
                    {license.max_users.toLocaleString()}
                  </span>
                  User Limit
                </span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
