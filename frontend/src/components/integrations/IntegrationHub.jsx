/**
 * Project Aura - Integration Hub
 *
 * Central management interface for enterprise integrations including
 * ticketing systems, monitoring tools, CI/CD pipelines, and communication platforms.
 *
 * Features:
 * - Grid layout organized by category
 * - Integration cards with status indicators
 * - Provider-specific configuration modals
 * - Connection testing and sync controls
 * - Search and category filtering
 */

import { useState, useEffect } from 'react';
import {
  PuzzlePieceIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  XCircleIcon,
  ArrowPathIcon,
  TrashIcon,
  XMarkIcon,
  ShieldCheckIcon,
  CodeBracketIcon,
  ChartBarIcon,
  CloudIcon,
  ChatBubbleLeftRightIcon,
  TicketIcon,
  LinkIcon,
  Cog6ToothIcon,
  ExclamationTriangleIcon,
  BellAlertIcon,
  BuildingOfficeIcon,
  DocumentTextIcon,
  FunnelIcon,
  PlayIcon,
  EyeIcon,
  CircleStackIcon,
  CommandLineIcon,
  UserGroupIcon,
  ClipboardDocumentCheckIcon,
} from '@heroicons/react/24/outline';
import { useIntegrations } from '../../hooks/useIntegrations';
import {
  INTEGRATION_PROVIDERS,
  testConnection,
  saveIntegrationConfig,
} from '../../services/integrationApi';
import ZendeskConfig from './ZendeskConfig';
import LinearConfig from './LinearConfig';
import ServiceNowConfig from './ServiceNowConfig';
import DataikuConfig from './DataikuConfig';
import FivetranConfig from './FivetranConfig';
import VSCodeConfig from './VSCodeConfig';
import PyCharmConfig from './PyCharmConfig';
import JupyterLabConfig from './JupyterLabConfig';
import ZscalerConfig from './ZscalerConfig';
import SaviyntConfig from './SaviyntConfig';
import AuditBoardConfig from './AuditBoardConfig';
import SlackConfig from './SlackConfig';
import PalantirIntegrationSettings from '../settings/PalantirIntegrationSettings';
import { useToast } from '../ui/Toast';
import { useConfirm } from '../ui/ConfirmDialog';
import { getProviderLogo } from './ProviderLogos';

// ============================================================================
// Constants and Configuration
// ============================================================================

const CATEGORY_CONFIG = {
  ticketing: {
    label: 'Ticketing',
    icon: TicketIcon,
    color: 'warning',
    bgColor: 'bg-warning-50 dark:bg-warning-900/20',
    textColor: 'text-warning-700 dark:text-warning-400',
    borderColor: 'border-warning-200 dark:border-warning-800',
    badgeBg: 'bg-warning-100 dark:bg-warning-900/30',
  },
  monitoring: {
    label: 'Monitoring',
    icon: ChartBarIcon,
    color: 'aura',
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    textColor: 'text-aura-700 dark:text-aura-400',
    borderColor: 'border-aura-200 dark:border-aura-800',
    badgeBg: 'bg-aura-100 dark:bg-aura-900/30',
  },
  security: {
    label: 'Security',
    icon: ShieldCheckIcon,
    color: 'critical',
    bgColor: 'bg-critical-50 dark:bg-critical-900/20',
    textColor: 'text-critical-700 dark:text-critical-400',
    borderColor: 'border-critical-200 dark:border-critical-800',
    badgeBg: 'bg-critical-100 dark:bg-critical-900/30',
  },
  cicd: {
    label: 'CI/CD',
    icon: CodeBracketIcon,
    color: 'aura',
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    textColor: 'text-aura-700 dark:text-aura-400',
    borderColor: 'border-aura-200 dark:border-aura-800',
    badgeBg: 'bg-aura-100 dark:bg-aura-900/30',
  },
  communication: {
    label: 'Communication',
    icon: ChatBubbleLeftRightIcon,
    color: 'olive',
    bgColor: 'bg-olive-50 dark:bg-olive-900/20',
    textColor: 'text-olive-700 dark:text-olive-400',
    borderColor: 'border-olive-200 dark:border-olive-800',
    badgeBg: 'bg-olive-100 dark:bg-olive-900/30',
  },
  data_platforms: {
    label: 'Data Platforms',
    icon: CircleStackIcon,
    color: 'aura',
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    textColor: 'text-aura-700 dark:text-aura-400',
    borderColor: 'border-aura-200 dark:border-aura-800',
    badgeBg: 'bg-aura-100 dark:bg-aura-900/30',
  },
  developer_tools: {
    label: 'Developer Tools',
    icon: CommandLineIcon,
    color: 'olive',
    bgColor: 'bg-olive-50 dark:bg-olive-900/20',
    textColor: 'text-olive-700 dark:text-olive-400',
    borderColor: 'border-olive-200 dark:border-olive-800',
    badgeBg: 'bg-olive-100 dark:bg-olive-900/30',
  },
  identity: {
    label: 'Identity',
    icon: UserGroupIcon,
    color: 'aura',
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
    textColor: 'text-aura-700 dark:text-aura-400',
    borderColor: 'border-aura-200 dark:border-aura-800',
    badgeBg: 'bg-aura-100 dark:bg-aura-900/30',
  },
  grc: {
    label: 'GRC',
    icon: ClipboardDocumentCheckIcon,
    color: 'olive',
    bgColor: 'bg-olive-50 dark:bg-olive-900/20',
    textColor: 'text-olive-700 dark:text-olive-400',
    borderColor: 'border-olive-200 dark:border-olive-800',
    badgeBg: 'bg-olive-100 dark:bg-olive-900/30',
  },
  threat_intelligence: {
    label: 'Threat Intelligence',
    icon: ShieldCheckIcon,
    color: 'critical',
    bgColor: 'bg-critical-50 dark:bg-critical-900/20',
    textColor: 'text-critical-700 dark:text-critical-400',
    borderColor: 'border-critical-200 dark:border-critical-800',
    badgeBg: 'bg-critical-100 dark:bg-critical-900/30',
  },
};

const STATUS_CONFIG = {
  connected: {
    label: 'Connected',
    icon: CheckCircleIcon,
    color: 'text-olive-600 dark:text-olive-400',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    dotColor: 'bg-olive-500',
  },
  disconnected: {
    label: 'Disconnected',
    icon: XCircleIcon,
    color: 'text-surface-500 dark:text-surface-400',
    bgColor: 'bg-surface-100 dark:bg-surface-700',
    dotColor: 'bg-surface-400',
  },
  error: {
    label: 'Error',
    icon: ExclamationCircleIcon,
    color: 'text-critical-600 dark:text-critical-400',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    dotColor: 'bg-critical-500',
  },
  syncing: {
    label: 'Syncing',
    icon: ArrowPathIcon,
    color: 'text-aura-600 dark:text-aura-400',
    bgColor: 'bg-aura-100 dark:bg-aura-900/30',
    dotColor: 'bg-aura-500',
  },
  pending: {
    label: 'Pending',
    icon: ClockIcon,
    color: 'text-warning-600 dark:text-warning-400',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    dotColor: 'bg-warning-500',
  },
};

const ICON_MAP = {
  'ticket': TicketIcon,
  'shield-check': ShieldCheckIcon,
  'shield-exclamation': ExclamationTriangleIcon,
  'code-bracket': CodeBracketIcon,
  'chart-bar': ChartBarIcon,
  'chat-bubble-left-right': ChatBubbleLeftRightIcon,
  'bell-alert': BellAlertIcon,
  'building-office': BuildingOfficeIcon,
  'cloud': CloudIcon,
  'circle-stack': CircleStackIcon,
  'command-line': CommandLineIcon,
  'user-group': UserGroupIcon,
  'clipboard-document-check': ClipboardDocumentCheckIcon,
};

// ============================================================================
// Main Component
// ============================================================================

export default function IntegrationHub() {
  const {
    integrations,
    availableProviders: _availableProviders,
    loading,
    error: loadError,
    syncing,
    refresh,
    triggerSync,
    deleteIntegration: removeIntegration,
    toggleEnabled: _toggleEnabled,
  } = useIntegrations();

  const { toast } = useToast();
  const { confirm } = useConfirm();

  const [categoryFilter, setCategoryFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [editingIntegration, setEditingIntegration] = useState(null);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [logsProvider, setLogsProvider] = useState(null);

  // Testing states
  const [testingConnection, setTestingConnection] = useState({});

  // Handle error display
  useEffect(() => {
    if (loadError) {
      setError(loadError);
    }
  }, [loadError]);

  // Clear messages after timeout
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  // Handlers
  const handleConnectProvider = (providerId) => {
    setShowAddModal(false); // Close the add modal first
    setSelectedProvider(providerId);
    setEditingIntegration(null);
    setShowConfigModal(true);
  };

  const handleEditIntegration = (integration) => {
    setSelectedProvider(integration.provider);
    setEditingIntegration(integration);
    setShowConfigModal(true);
  };

  const handleCloseModal = () => {
    setShowConfigModal(false);
    setSelectedProvider(null);
    setEditingIntegration(null);
  };

  const handleSaveSuccess = async (_config) => {
    handleCloseModal();
    await refresh();
    setSuccessMessage(`Integration ${editingIntegration ? 'updated' : 'connected'} successfully`);
  };

  const handleTestConnection = async (providerId) => {
    setTestingConnection((prev) => ({ ...prev, [providerId]: true }));
    try {
      const result = await testConnection(providerId);
      if (result.success) {
        setSuccessMessage('Connection test passed');
        await refresh();
      } else {
        setError(`Connection test failed: ${result.message}`);
      }
    } catch (err) {
      setError(`Connection test failed: ${err.message}`);
    } finally {
      setTestingConnection((prev) => ({ ...prev, [providerId]: false }));
    }
  };

  const handleSync = async (providerId) => {
    try {
      await triggerSync(providerId);
      setSuccessMessage('Sync completed successfully');
    } catch (err) {
      setError(`Sync failed: ${err.message}`);
    }
  };

  const handleDelete = async (integrationId) => {
    const confirmed = await confirm({
      title: 'Disconnect Integration',
      message: 'Are you sure you want to disconnect this integration? This will remove all synced data and settings.',
      confirmText: 'Disconnect',
      cancelText: 'Cancel',
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      await removeIntegration(integrationId);
      setSuccessMessage('Integration disconnected');
    } catch (err) {
      setError(`Failed to disconnect: ${err.message}`);
    }
  };

  const handleViewLogs = (providerId) => {
    setLogsProvider(providerId);
    setShowLogsModal(true);
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refresh();
      toast.success('Integrations refreshed');
    } catch (err) {
      toast.error('Failed to refresh integrations');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Filter integrations
  const filteredIntegrations = integrations.filter((integration) => {
    if (categoryFilter !== 'all' && integration.category !== categoryFilter) return false;
    if (statusFilter !== 'all' && integration.status !== statusFilter) return false;
    if (searchQuery && !integration.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  // Filter available providers (exclude already connected)
  const connectedProviderIds = integrations.map((i) => i.provider);
  const filteredAvailableProviders = Object.values(INTEGRATION_PROVIDERS).filter((provider) => {
    if (categoryFilter !== 'all' && provider.category !== categoryFilter) return false;
    if (searchQuery && !provider.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return !connectedProviderIds.includes(provider.id);
  });

  // Group available providers by category
  const groupedProviders = filteredAvailableProviders.reduce((acc, provider) => {
    if (!acc[provider.category]) {
      acc[provider.category] = [];
    }
    acc[provider.category].push(provider);
    return acc;
  }, {});

  // Get config modal component for provider
  const renderConfigModal = () => {
    if (!showConfigModal || !selectedProvider) return null;

    const modalProps = {
      isOpen: showConfigModal,
      onClose: handleCloseModal,
      onSave: handleSaveSuccess,
      existingConfig: editingIntegration?.config,
    };

    switch (selectedProvider) {
      // Ticketing Integrations
      case 'zendesk':
        return <ZendeskConfig {...modalProps} />;
      case 'linear':
        return <LinearConfig {...modalProps} />;
      case 'servicenow':
        return <ServiceNowConfig {...modalProps} />;
      // Data Platform Integrations
      case 'dataiku':
        return <DataikuConfig {...modalProps} />;
      case 'fivetran':
        return <FivetranConfig {...modalProps} />;
      // Developer Tool Integrations
      case 'vscode':
        return <VSCodeConfig {...modalProps} />;
      case 'pycharm':
        return <PyCharmConfig {...modalProps} />;
      case 'jupyterlab':
        return <JupyterLabConfig {...modalProps} />;
      // Security Integrations (ADR-053)
      case 'zscaler':
        return <ZscalerConfig {...modalProps} />;
      // Identity Integrations (ADR-053)
      case 'saviynt':
        return <SaviyntConfig {...modalProps} />;
      // GRC Integrations (ADR-053)
      case 'auditboard':
        return <AuditBoardConfig {...modalProps} />;
      // Communication Integrations
      case 'slack':
        return <SlackConfig {...modalProps} />;
      // Threat Intelligence Integrations (ADR-074/075)
      case 'palantir_aip':
        return <PalantirIntegrationSettings {...modalProps} />;
      default:
        return <GenericConfigModal provider={selectedProvider} {...modalProps} />;
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ArrowPathIcon className="h-12 w-12 text-aura-600 dark:text-aura-400 animate-spin mx-auto" />
          <p className="mt-4 text-surface-600 dark:text-surface-400">Loading integrations...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <PuzzlePieceIcon className="h-8 w-8 text-aura-600 dark:text-aura-400" />
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                Integration Hub
              </h1>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Connect and manage enterprise integrations for ticketing, monitoring, and more
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-aura-600 hover:bg-aura-700 text-white font-medium rounded-lg transition-colors shadow-sm hover:shadow-md"
            >
              <PlusIcon className="h-5 w-5" />
              Add Integration
            </button>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-800 rounded-lg flex items-center gap-3">
          <ExclamationTriangleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400" />
          <span className="text-critical-700 dark:text-critical-300 flex-1">{error}</span>
          <button onClick={() => setError(null)}>
            <XMarkIcon className="h-5 w-5 text-critical-600 dark:text-critical-400" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="mx-6 mt-4 p-4 bg-olive-50 dark:bg-olive-900/30 border border-olive-200 dark:border-olive-800 rounded-lg flex items-center gap-3">
          <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
          <span className="text-olive-700 dark:text-olive-300">{successMessage}</span>
        </div>
      )}

      {/* Filters */}
      <div className="px-6 py-4 bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-4 flex-wrap">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-surface-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search integrations..."
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>

          {/* Category Filter */}
          <div className="flex items-center gap-2">
            <FunnelIcon className="h-4 w-4 text-surface-400" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
            >
              <option value="all">All Categories</option>
              {Object.entries(CATEGORY_CONFIG).map(([id, config]) => (
                <option key={id} value={id}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
          >
            <option value="all">All Statuses</option>
            <option value="connected">Connected</option>
            <option value="disconnected">Disconnected</option>
            <option value="error">Error</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-6 space-y-8">
        {/* Connected Integrations */}
        <section>
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
            <LinkIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
            Connected Integrations
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded-full">
              {integrations.length}
            </span>
          </h2>

          {filteredIntegrations.length === 0 ? (
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-8 text-center">
              <PuzzlePieceIcon className="h-12 w-12 text-surface-300 dark:text-surface-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
                No integrations connected
              </h3>
              <p className="text-surface-500 dark:text-surface-400 mb-4">
                Get started by connecting your first integration from the available providers below.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredIntegrations.map((integration) => (
                <ConnectedIntegrationCard
                  key={integration.id}
                  integration={integration}
                  onEdit={() => handleEditIntegration(integration)}
                  onDelete={() => handleDelete(integration.id)}
                  onTest={() => handleTestConnection(integration.provider)}
                  onSync={() => handleSync(integration.provider)}
                  onViewLogs={() => handleViewLogs(integration.provider)}
                  testing={testingConnection[integration.provider]}
                  syncing={syncing[integration.provider]}
                />
              ))}
            </div>
          )}
        </section>

      </div>

      {/* Add Integration Modal */}
      {showAddModal && (
        <AddIntegrationModal
          connectedProviderIds={connectedProviderIds}
          onSelect={handleConnectProvider}
          onClose={() => setShowAddModal(false)}
        />
      )}

      {/* Configuration Modal */}
      {renderConfigModal()}

      {/* Logs Modal */}
      {showLogsModal && (
        <IntegrationLogsModal
          provider={logsProvider}
          onClose={() => {
            setShowLogsModal(false);
            setLogsProvider(null);
          }}
        />
      )}
    </div>
  );
}

// ============================================================================
// Connected Integration Card
// ============================================================================

function ConnectedIntegrationCard({
  integration,
  onEdit,
  onDelete,
  onTest,
  onSync,
  onViewLogs,
  testing,
  syncing,
}) {
  const statusConfig = STATUS_CONFIG[integration.status] || STATUS_CONFIG.disconnected;
  const categoryConfig = CATEGORY_CONFIG[integration.category] || CATEGORY_CONFIG.ticketing;
  const ProviderLogo = getProviderLogo(integration.provider);
  const _StatusIcon = statusConfig.icon;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] p-5 transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <ProviderLogo className="h-9 w-9 rounded-lg" />
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">
              {integration.name}
            </h3>
            <span className={`text-xs font-medium ${categoryConfig.textColor}`}>
              {categoryConfig.label}
            </span>
          </div>
        </div>

        {/* Status Badge */}
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${statusConfig.bgColor}`}>
          <span className={`w-2 h-2 rounded-full ${statusConfig.dotColor} ${integration.status === 'syncing' ? 'animate-pulse' : ''}`} />
          <span className={`text-xs font-medium ${statusConfig.color}`}>
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Description */}
      {integration.description && (
        <p className="text-sm text-surface-600 dark:text-surface-400 mb-4 line-clamp-2">
          {integration.description}
        </p>
      )}

      {/* Sync Info */}
      <div className="flex items-center justify-between text-xs text-surface-500 dark:text-surface-400 mb-4">
        <span className="flex items-center gap-1">
          <ClockIcon className="h-3.5 w-3.5" />
          Sync: {integration.sync_frequency || 'Manual'}
        </span>
        {integration.last_sync && (
          <span>Last: {new Date(integration.last_sync).toLocaleDateString()}</span>
        )}
      </div>

      {/* Error Message */}
      {integration.last_error && (
        <div className="mb-4 p-2.5 bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-800 rounded-lg text-xs text-critical-700 dark:text-critical-400">
          {integration.last_error}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-4 border-t border-surface-100 dark:border-surface-700">
        <button
          onClick={onTest}
          disabled={testing}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors disabled:opacity-50"
        >
          {testing ? (
            <ArrowPathIcon className="h-4 w-4 animate-spin" />
          ) : (
            <LinkIcon className="h-4 w-4" />
          )}
          Test
        </button>
        <button
          onClick={onSync}
          disabled={syncing}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-aura-600 dark:text-aura-400 hover:bg-aura-50 dark:hover:bg-aura-900/20 rounded-lg transition-colors disabled:opacity-50"
        >
          {syncing ? (
            <ArrowPathIcon className="h-4 w-4 animate-spin" />
          ) : (
            <PlayIcon className="h-4 w-4" />
          )}
          Sync
        </button>
        <button
          onClick={onEdit}
          className="p-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          title="Configure"
        >
          <Cog6ToothIcon className="h-4 w-4" />
        </button>
        <button
          onClick={onViewLogs}
          className="p-2 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          title="View Logs"
        >
          <EyeIcon className="h-4 w-4" />
        </button>
        <button
          onClick={onDelete}
          className="p-2 text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-lg transition-colors"
          title="Disconnect"
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Available Provider Card
// ============================================================================

function AvailableProviderCard({ provider, onConnect }) {
  const categoryConfig = CATEGORY_CONFIG[provider.category] || CATEGORY_CONFIG.ticketing;
  const ProviderLogo = getProviderLogo(provider.id);

  return (
    <div
      onClick={onConnect}
      className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)] p-5 cursor-pointer hover:border-aura-300 dark:hover:border-aura-700 transition-all group"
    >
      <div className="flex items-center gap-3 mb-3">
        <ProviderLogo className="h-9 w-9 rounded-lg group-hover:scale-105 transition-transform" />
        <div>
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">{provider.name}</h3>
          <span className={`text-xs font-medium ${categoryConfig.textColor}`}>
            {categoryConfig.label}
          </span>
        </div>
      </div>

      <p className="text-sm text-surface-600 dark:text-surface-400 mb-4 line-clamp-2">
        {provider.description}
      </p>

      {/* Features */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {provider.features?.slice(0, 3).map((feature, idx) => (
          <span
            key={idx}
            className="text-xs px-2 py-0.5 bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 rounded"
          >
            {feature}
          </span>
        ))}
        {provider.features?.length > 3 && (
          <span className="text-xs px-2 py-0.5 bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 rounded">
            +{provider.features.length - 3}
          </span>
        )}
      </div>

      <button className="w-full flex items-center justify-center gap-2 py-2.5 text-sm font-medium text-aura-600 dark:text-aura-400 bg-aura-50 dark:bg-aura-900/20 hover:bg-aura-100 dark:hover:bg-aura-900/30 rounded-lg transition-colors">
        <PlusIcon className="h-4 w-4" />
        Connect
      </button>
    </div>
  );
}

// ============================================================================
// Add Integration Modal
// ============================================================================

function AddIntegrationModal({ connectedProviderIds, onSelect, onClose }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  // Get all available providers (exclude already connected)
  const availableProviders = Object.values(INTEGRATION_PROVIDERS).filter(
    (provider) => !connectedProviderIds.includes(provider.id)
  );

  // Filter by search and category
  const filteredProviders = availableProviders.filter((provider) => {
    if (selectedCategory !== 'all' && provider.category !== selectedCategory) return false;
    if (searchQuery && !provider.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  // Group by category
  const groupedProviders = filteredProviders.reduce((acc, provider) => {
    if (!acc[provider.category]) {
      acc[provider.category] = [];
    }
    acc[provider.category].push(provider);
    return acc;
  }, {});

  // Category order
  const categoryOrder = ['threat_intelligence', 'ticketing', 'monitoring', 'security', 'identity', 'grc', 'cicd', 'communication', 'data_platforms', 'developer_tools'];

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-aura-100 dark:bg-aura-900/30">
                <PlusIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                  Add Integration
                </h2>
                <p className="text-sm text-surface-500 dark:text-surface-400">
                  Choose a service to connect
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            >
              <XMarkIcon className="h-5 w-5 text-surface-500 dark:text-surface-400" />
            </button>
          </div>

          {/* Search and Filter */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-surface-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search integrations..."
                className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
              />
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
            >
              <option value="all">All Categories</option>
              {Object.entries(CATEGORY_CONFIG).map(([id, config]) => (
                <option key={id} value={id}>
                  {config.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {filteredProviders.length === 0 ? (
            <div className="text-center py-12">
              <PuzzlePieceIcon className="h-12 w-12 text-surface-300 dark:text-surface-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
                No integrations found
              </h3>
              <p className="text-surface-500 dark:text-surface-400">
                {connectedProviderIds.length === Object.keys(INTEGRATION_PROVIDERS).length
                  ? 'All available integrations are already connected.'
                  : 'Try adjusting your search or filter.'}
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {categoryOrder.map((categoryId) => {
                const providers = groupedProviders[categoryId];
                if (!providers || providers.length === 0) return null;

                const categoryConfig = CATEGORY_CONFIG[categoryId];
                const CategoryIcon = categoryConfig.icon;

                return (
                  <div key={categoryId}>
                    <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-3 flex items-center gap-2">
                      <CategoryIcon className={`h-4 w-4 ${categoryConfig.textColor}`} />
                      {categoryConfig.label}
                      <span className={`ml-1 px-1.5 py-0.5 text-xs font-medium ${categoryConfig.badgeBg} ${categoryConfig.textColor} rounded-full`}>
                        {providers.length}
                      </span>
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {providers.map((provider) => {
                        const ProviderLogo = getProviderLogo(provider.id);
                        return (
                          <button
                            key={provider.id}
                            onClick={() => onSelect(provider.id)}
                            className="flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-700/50 hover:bg-surface-100 dark:hover:bg-surface-700 border border-surface-200 dark:border-surface-600 hover:border-aura-300 dark:hover:border-aura-600 rounded-xl transition-all text-left group"
                          >
                            <ProviderLogo className="h-10 w-10 rounded-lg flex-shrink-0 group-hover:scale-105 transition-transform" />
                            <div className="flex-1 min-w-0">
                              <h4 className="font-medium text-surface-900 dark:text-surface-100 truncate">
                                {provider.name}
                              </h4>
                              <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
                                {provider.description}
                              </p>
                            </div>
                            <PlusIcon className="h-5 w-5 text-surface-400 group-hover:text-aura-500 transition-colors flex-shrink-0" />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 flex items-center justify-between">
          <p className="text-sm text-surface-500 dark:text-surface-400">
            {availableProviders.length} integration{availableProviders.length !== 1 ? 's' : ''} available
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Generic Configuration Modal
// ============================================================================

function GenericConfigModal({ provider, isOpen, onClose, onSave, existingConfig }) {
  const providerDef = INTEGRATION_PROVIDERS[provider];
  const [config, setConfig] = useState(existingConfig || {});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});

  if (!isOpen || !providerDef) return null;

  const categoryConfig = CATEGORY_CONFIG[providerDef.category] || CATEGORY_CONFIG.ticketing;
  const ProviderLogo = getProviderLogo(provider);

  const handleFieldChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
    setTestResult(null);
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await testConnection(provider, config);
      setTestResult(result);
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveIntegrationConfig(provider, config);
      await onSave(config);
    } catch (err) {
      setTestResult({ success: false, message: err.message || 'Failed to save configuration' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ProviderLogo className="h-10 w-10 rounded-lg" />
            <div>
              <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure {providerDef.name}
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                {providerDef.description}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-surface-500 dark:text-surface-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 space-y-4">
          {providerDef.configFields.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                {field.label}
                {field.required && <span className="text-critical-500 ml-1">*</span>}
              </label>
              {field.type === 'password' ? (
                <div className="relative">
                  <input
                    type={showSecrets[field.name] ? 'text' : 'password'}
                    value={config[field.name] || ''}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    placeholder={field.placeholder}
                    className="w-full px-3 py-2 pr-10 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecrets((prev) => ({ ...prev, [field.name]: !prev[field.name] }))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400"
                  >
                    {showSecrets[field.name] ? (
                      <EyeIcon className="h-5 w-5" />
                    ) : (
                      <EyeIcon className="h-5 w-5" />
                    )}
                  </button>
                </div>
              ) : field.type === 'select' ? (
                <select
                  value={config[field.name] || ''}
                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                  className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                >
                  <option value="">Select...</option>
                  {field.options?.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={field.type}
                  value={config[field.name] || ''}
                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                />
              )}
              {field.helpText && (
                <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                  {field.helpText}
                </p>
              )}
            </div>
          ))}

          {/* Test Connection */}
          <div className="pt-4">
            <button
              onClick={handleTest}
              disabled={testing}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 disabled:opacity-50 transition-colors"
            >
              {testing ? (
                <>
                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <LinkIcon className="h-4 w-4" />
                  Test Connection
                </>
              )}
            </button>

            {testResult && (
              <div
                className={`mt-3 flex items-center gap-3 p-3 rounded-lg ${
                  testResult.success
                    ? 'bg-olive-50 dark:bg-olive-900/20 text-olive-700 dark:text-olive-300'
                    : 'bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300'
                }`}
              >
                {testResult.success ? (
                  <CheckCircleIcon className="h-5 w-5" />
                ) : (
                  <ExclamationCircleIcon className="h-5 w-5" />
                )}
                <span className="font-medium">{testResult.message}</span>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 flex items-center justify-end gap-3 bg-surface-50 dark:bg-surface-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !testResult?.success}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? (
              <>
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircleIcon className="h-4 w-4" />
                Save
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Integration Logs Modal
// ============================================================================

function IntegrationLogsModal({ provider, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulated logs - would come from API
    setLogs([
      { id: 1, timestamp: new Date().toISOString(), level: 'info', message: 'Sync started' },
      { id: 2, timestamp: new Date().toISOString(), level: 'info', message: 'Fetched 15 items' },
      { id: 3, timestamp: new Date().toISOString(), level: 'success', message: 'Sync completed successfully' },
    ]);
    setLoading(false);
  }, [provider]);

  const getLevelStyles = (level) => {
    switch (level) {
      case 'error':
        return 'text-critical-600 dark:text-critical-400 bg-critical-50 dark:bg-critical-900/20';
      case 'warning':
        return 'text-warning-600 dark:text-warning-400 bg-warning-50 dark:bg-warning-900/20';
      case 'success':
        return 'text-olive-600 dark:text-olive-400 bg-olive-50 dark:bg-olive-900/20';
      default:
        return 'text-surface-600 dark:text-surface-400 bg-surface-50 dark:bg-surface-700';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <DocumentTextIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
            <h2 className="text-xl font-bold text-surface-900 dark:text-surface-100">
              Sync Logs: {provider}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-surface-500 dark:text-surface-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-surface-500 dark:text-surface-400">
              No logs available
            </div>
          ) : (
            <div className="space-y-2 font-mono text-sm">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className={`px-3 py-2 rounded ${getLevelStyles(log.level)}`}
                >
                  <span className="text-surface-400 mr-3">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="uppercase font-medium mr-3">[{log.level}]</span>
                  <span>{log.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
