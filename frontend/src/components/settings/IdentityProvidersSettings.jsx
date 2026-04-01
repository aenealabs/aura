/**
 * Identity Providers Settings Component
 *
 * Main settings page for managing identity provider configurations.
 * Supports LDAP, SAML, OIDC, PingID, and Cognito.
 *
 * ADR-054: Multi-IdP Authentication
 */

import { useState, useEffect } from 'react';
import {
  ShieldCheckIcon,
  PlusIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  GlobeAltIcon,
  TrashIcon,
  PencilIcon,
} from '@heroicons/react/24/outline';
import IdPCard from './identity/IdPCard';
import IdPConfigModal from './identity/IdPConfigModal';
import {
  getIdentityProviders,
  deleteIdentityProvider,
  testIdentityProvider,
  setDefaultIdentityProvider,
  toggleIdentityProvider,
  getDomainRoutes,
  createDomainRoute,
  deleteDomainRoute,
} from '../../services/identityProviderApi';

export default function IdentityProvidersSettings({ onSuccess, onError }) {
  const [providers, setProviders] = useState([]);
  const [domainRoutes, setDomainRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [editingProvider, setEditingProvider] = useState(null);
  const [showDomainModal, setShowDomainModal] = useState(false);
  const [newDomain, setNewDomain] = useState('');
  const [newDomainProvider, setNewDomainProvider] = useState('');

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [providersData, routesData] = await Promise.all([
        getIdentityProviders(),
        getDomainRoutes(),
      ]);
      setProviders(providersData);
      setDomainRoutes(routesData);
    } catch (err) {
      console.error('Failed to load identity providers:', err);
      onError?.('Failed to load identity providers');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await loadData();
      onSuccess?.('Identity providers refreshed');
    } catch (err) {
      onError?.('Failed to refresh');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this identity provider? Users will no longer be able to sign in with this provider.')) {
      return;
    }
    try {
      await deleteIdentityProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
      // Also remove any domain routes pointing to this provider
      setDomainRoutes((prev) => prev.filter((r) => r.provider_id !== id));
      onSuccess?.('Identity provider deleted');
    } catch (err) {
      onError?.('Failed to delete identity provider');
    }
  };

  const handleTest = async (id) => {
    try {
      const result = await testIdentityProvider(id);
      if (result.success) {
        setProviders((prev) =>
          prev.map((p) =>
            p.id === id ? { ...p, status: 'connected', last_tested: new Date().toISOString() } : p
          )
        );
        onSuccess?.(`Connection successful (${result.latency_ms}ms)`);
      }
    } catch (err) {
      setProviders((prev) =>
        prev.map((p) => (p.id === id ? { ...p, status: 'error' } : p))
      );
      onError?.('Connection test failed');
    }
  };

  const handleSetDefault = async (id) => {
    try {
      await setDefaultIdentityProvider(id);
      setProviders((prev) =>
        prev.map((p) => ({ ...p, is_default: p.id === id }))
      );
      onSuccess?.('Default provider updated');
    } catch (err) {
      onError?.('Failed to set default provider');
    }
  };

  const handleToggle = async (id, enabled) => {
    try {
      await toggleIdentityProvider(id, enabled);
      setProviders((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, enabled, status: enabled ? 'pending' : 'disabled' } : p
        )
      );
      onSuccess?.(enabled ? 'Provider enabled' : 'Provider disabled');
    } catch (err) {
      onError?.('Failed to update provider');
    }
  };

  const handleSaveProvider = async (config) => {
    await loadData();
    setShowConfigModal(false);
    setEditingProvider(null);
    onSuccess?.(editingProvider ? 'Provider updated' : 'Provider created');
  };

  const handleAddDomainRoute = async () => {
    if (!newDomain || !newDomainProvider) return;
    try {
      const route = await createDomainRoute({
        domain: newDomain.toLowerCase().replace('@', ''),
        provider_id: newDomainProvider,
      });
      setDomainRoutes((prev) => [...prev, route]);
      setNewDomain('');
      setNewDomainProvider('');
      setShowDomainModal(false);
      onSuccess?.('Domain route added');
    } catch (err) {
      onError?.('Failed to add domain route');
    }
  };

  const handleDeleteDomainRoute = async (id) => {
    try {
      await deleteDomainRoute(id);
      setDomainRoutes((prev) => prev.filter((r) => r.id !== id));
      onSuccess?.('Domain route removed');
    } catch (err) {
      onError?.('Failed to remove domain route');
    }
  };

  const getProviderName = (providerId) => {
    const provider = providers.find((p) => p.id === providerId);
    return provider?.display_name || 'Unknown';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ArrowPathIcon className="h-8 w-8 text-aura-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheckIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
          <div>
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Identity Providers
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Configure single sign-on and enterprise authentication
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => {
              setEditingProvider(null);
              setShowConfigModal(true);
            }}
            className="flex items-center gap-2 px-4 py-2.5 bg-aura-600 text-white font-medium rounded-xl hover:bg-aura-700 transition-colors shadow-sm hover:shadow-md"
          >
            <PlusIcon className="h-5 w-5" />
            Add Provider
          </button>
        </div>
      </div>

      {/* Empty State */}
      {providers.length === 0 && (
        <div className="bg-aura-50/50 dark:bg-aura-900/20 border border-aura-200/50 dark:border-aura-800/50 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <InformationCircleIcon className="h-6 w-6 text-aura-600 dark:text-aura-400 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-aura-800 dark:text-aura-200">
                No identity providers configured
              </h3>
              <p className="text-sm text-aura-700 dark:text-aura-300 mt-1">
                Add your first identity provider to enable single sign-on for your users.
                Supports LDAP, SAML 2.0, OIDC, PingID, and AWS Cognito.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Provider List */}
      {providers.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
            Configured Providers ({providers.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {providers.map((provider) => (
              <IdPCard
                key={provider.id}
                provider={provider}
                onEdit={() => {
                  setEditingProvider(provider);
                  setShowConfigModal(true);
                }}
                onDelete={() => handleDelete(provider.id)}
                onTest={() => handleTest(provider.id)}
                onSetDefault={() => handleSetDefault(provider.id)}
                onToggle={(enabled) => handleToggle(provider.id, enabled)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Domain Routing */}
      {providers.length > 0 && (
        <section className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200/50 dark:border-surface-700/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <GlobeAltIcon className="h-5 w-5 text-surface-500" />
              <div>
                <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                  Email Domain Routing
                </h3>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Automatically route users to their identity provider based on email domain
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowDomainModal(true)}
              className="text-sm font-medium text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
            >
              + Add Rule
            </button>
          </div>

          {domainRoutes.length === 0 ? (
            <p className="text-sm text-surface-500 dark:text-surface-400 italic">
              No domain routes configured. Users will choose their provider manually.
            </p>
          ) : (
            <div className="space-y-2">
              {domainRoutes.map((route) => (
                <div
                  key={route.id}
                  className="flex items-center justify-between py-2 px-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-mono text-surface-700 dark:text-surface-300">
                      @{route.domain}
                    </span>
                    <span className="text-surface-400">→</span>
                    <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                      {getProviderName(route.provider_id)}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDeleteDomainRoute(route.id)}
                    className="p-1 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
                    title="Remove rule"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Add Domain Route Modal */}
      {showDomainModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">
              Add Domain Route
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Email Domain
                </label>
                <div className="flex items-center">
                  <span className="px-3 py-2 bg-surface-100 dark:bg-surface-700 border border-r-0 border-surface-300 dark:border-surface-600 rounded-l-lg text-surface-500">
                    @
                  </span>
                  <input
                    type="text"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    placeholder="acme.com"
                    className="flex-1 px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-r-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Identity Provider
                </label>
                <select
                  value={newDomainProvider}
                  onChange={(e) => setNewDomainProvider(e.target.value)}
                  className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
                >
                  <option value="">Select provider...</option>
                  {providers
                    .filter((p) => p.enabled && p.status === 'connected')
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name}
                      </option>
                    ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowDomainModal(false);
                  setNewDomain('');
                  setNewDomainProvider('');
                }}
                className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddDomainRoute}
                disabled={!newDomain || !newDomainProvider}
                className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add Route
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Config Modal */}
      {showConfigModal && (
        <IdPConfigModal
          isOpen={showConfigModal}
          onClose={() => {
            setShowConfigModal(false);
            setEditingProvider(null);
          }}
          existingConfig={editingProvider}
          onSave={handleSaveProvider}
          onError={onError}
        />
      )}
    </div>
  );
}
