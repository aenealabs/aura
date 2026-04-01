/**
 * Identity Provider Card Component
 *
 * Displays a configured IdP with status, actions, and metadata.
 * ADR-054: Multi-IdP Authentication
 */

import { useState } from 'react';
import {
  EllipsisVerticalIcon,
  CheckCircleIcon,
  ClockIcon,
  NoSymbolIcon,
  ArrowPathIcon,
  PencilIcon,
  TrashIcon,
  StarIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarSolidIcon } from '@heroicons/react/24/solid';
import { IDP_STATUS } from '../../../services/identityProviderApi';
import { getProviderLogo } from '../../integrations/ProviderLogos';

// Protocol labels
const TYPE_LABELS = {
  ldap: 'LDAP',
  saml: 'SAML 2.0',
  oidc: 'OIDC',
  pingid: 'PingID',
  cognito: 'Cognito',
  entra_id: 'Entra ID',
  azure_ad_b2c: 'Azure B2C',
};

// Status configurations
const STATUS_CONFIG = {
  [IDP_STATUS.CONNECTED]: {
    label: 'Connected',
    dotColor: 'bg-olive-500',
    textColor: 'text-olive-700 dark:text-olive-400',
    bgColor: 'bg-olive-50 dark:bg-olive-900/20',
  },
  [IDP_STATUS.ERROR]: {
    label: 'Error',
    dotColor: 'bg-critical-500',
    textColor: 'text-critical-700 dark:text-critical-400',
    bgColor: 'bg-critical-50 dark:bg-critical-900/20',
  },
  [IDP_STATUS.PENDING]: {
    label: 'Pending',
    dotColor: 'bg-warning-500',
    textColor: 'text-warning-700 dark:text-warning-400',
    bgColor: 'bg-warning-50 dark:bg-warning-900/20',
  },
  [IDP_STATUS.DISABLED]: {
    label: 'Disabled',
    dotColor: 'bg-surface-400',
    textColor: 'text-surface-600 dark:text-surface-400',
    bgColor: 'bg-surface-100 dark:bg-surface-700',
  },
};

export default function IdPCard({
  provider,
  onEdit,
  onDelete,
  onTest,
  onSetDefault,
  onToggle,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [testing, setTesting] = useState(false);

  const LogoComponent = getProviderLogo(provider.type);
  const statusConfig = STATUS_CONFIG[provider.status] || STATUS_CONFIG[IDP_STATUS.PENDING];

  const handleTest = async () => {
    setTesting(true);
    try {
      await onTest();
    } finally {
      setTesting(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200/50 dark:border-surface-700/50 p-4 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <LogoComponent className="w-10 h-10 rounded-lg flex-shrink-0" />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                {provider.display_name}
              </h3>
              {provider.is_default && (
                <StarSolidIcon className="h-4 w-4 text-warning-500" title="Default provider" />
              )}
            </div>
            <span className="text-xs font-medium text-surface-500 dark:text-surface-400 px-1.5 py-0.5 bg-surface-100 dark:bg-surface-700 rounded">
              {TYPE_LABELS[provider.type]}
            </span>
          </div>
        </div>

        {/* Menu */}
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-1.5 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            aria-label="More actions"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <EllipsisVerticalIcon className="h-5 w-5" />
          </button>

          {menuOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setMenuOpen(false)}
              />
              <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-surface-800 rounded-lg shadow-lg border border-surface-200 dark:border-surface-700 py-1 z-20">
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onEdit();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700"
                >
                  <PencilIcon className="h-4 w-4" />
                  Edit Configuration
                </button>
                {!provider.is_default && provider.status === IDP_STATUS.CONNECTED && (
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      onSetDefault();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700"
                  >
                    <StarIcon className="h-4 w-4" />
                    Set as Default
                  </button>
                )}
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onToggle(!provider.enabled);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700"
                >
                  <NoSymbolIcon className="h-4 w-4" />
                  {provider.enabled ? 'Disable' : 'Enable'}
                </button>
                <hr className="my-1 border-surface-200 dark:border-surface-700" />
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onDelete();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20"
                >
                  <TrashIcon className="h-4 w-4" />
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${statusConfig.bgColor} ${statusConfig.textColor}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${statusConfig.dotColor} ${provider.status === IDP_STATUS.PENDING ? 'animate-pulse' : ''}`} />
          {statusConfig.label}
        </span>
        {provider.is_default && (
          <span className="px-2 py-1 rounded-full text-xs font-medium bg-aura-50 dark:bg-aura-900/20 text-aura-700 dark:text-aura-400">
            Default
          </span>
        )}
      </div>

      {/* Metadata */}
      <div className="text-xs text-surface-500 dark:text-surface-400 space-y-1 mb-4">
        {provider.entity_id && (
          <p className="truncate" title={provider.entity_id}>
            Entity ID: {provider.entity_id}
          </p>
        )}
        {provider.issuer_url && (
          <p className="truncate" title={provider.issuer_url}>
            Issuer: {provider.issuer_url}
          </p>
        )}
        {provider.server_url && (
          <p className="truncate" title={provider.server_url}>
            Server: {provider.server_url}
          </p>
        )}
        <p className="flex items-center gap-1">
          <ClockIcon className="h-3.5 w-3.5" />
          Last tested: {formatDate(provider.last_tested)}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleTest}
          disabled={testing || !provider.enabled}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-aura-600 dark:text-aura-400 bg-aura-50 dark:bg-aura-900/20 hover:bg-aura-100 dark:hover:bg-aura-900/30 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {testing ? (
            <>
              <ArrowPathIcon className="h-4 w-4 animate-spin" />
              Testing...
            </>
          ) : (
            <>
              {provider.status === IDP_STATUS.CONNECTED ? (
                <CheckCircleIcon className="h-4 w-4" />
              ) : (
                <ArrowPathIcon className="h-4 w-4" />
              )}
              Test Connection
            </>
          )}
        </button>
        <button
          onClick={onEdit}
          className="px-3 py-2 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
        >
          Edit
        </button>
      </div>
    </div>
  );
}
