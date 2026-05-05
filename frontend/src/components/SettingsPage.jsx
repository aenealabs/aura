import { useState, useEffect } from 'react';
import {
  Cog6ToothIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ServerStackIcon,
  CloudIcon,
  LockClosedIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  CurrencyDollarIcon,
  ClockIcon,
  UserGroupIcon,
  BellIcon,
  LinkIcon,
  CommandLineIcon,
  DocumentCheckIcon,
  CpuChipIcon,
  BoltIcon,
  ChartBarIcon,
  TicketIcon,
  ChevronDownIcon,
  XMarkIcon,
  KeyIcon,
  FingerPrintIcon,
} from '@heroicons/react/24/outline';

import ComplianceSettingsTab from './ComplianceSettings';
import EditionSettings from './settings/EditionSettings';
import DeveloperSettings from './settings/DeveloperSettings';
import AutonomyPoliciesTab from './settings/AutonomyPoliciesTab';
import OrchestratorModeTab from './settings/OrchestratorModeTab';
import ModelRouterSettings from './settings/ModelRouterSettings';
import NotificationsSettings from './settings/NotificationsSettings';
import RateLimitingSettings from './settings/RateLimitingSettings';
import SecurityAlertSettings from './settings/SecurityAlertSettings';
import TicketingSettings from './settings/TicketingSettings';
import PrivacyTrainingSettings from './settings/PrivacyTrainingSettings';
import IdentityProvidersSettings from './settings/IdentityProvidersSettings';
import { useToast } from './ui/Toast';
import { useConfirm } from './ui/ConfirmDialog';

import {
  getSettings,
  updateIntegrationMode,
  updateHitlSettings,
  updateMcpSettings,
  updateSecuritySettings,
  getAvailableExternalTools,
  getMcpUsageStats,
  testMcpConnection,
  applyComplianceProfile,
  IntegrationModes,
  DEFAULT_SETTINGS,
  LOG_RETENTION_OPTIONS,
} from '../services/settingsApi';

// Integration Mode configurations with descriptions
const MODE_CONFIGS = {
  [IntegrationModes.DEFENSE]: {
    title: 'Defense Mode',
    subtitle: 'Maximum Security',
    description: 'Air-gap compatible, GovCloud-ready, no external dependencies. Ideal for defense contractors and highly regulated industries.',
    icon: ShieldExclamationIcon,
    color: 'red',
    features: [
      'No external network calls',
      'CMMC Level 3 / NIST 800-53 compliant',
      'Air-gap deployment ready',
      'FedRAMP High compatible',
      'All processing on-premises',
    ],
    restrictions: [
      'MCP Gateway disabled',
      'External tools unavailable',
      'Manual integrations only',
    ],
  },
  [IntegrationModes.ENTERPRISE]: {
    title: 'Enterprise Mode',
    subtitle: 'Full Integration',
    description: 'Full AgentCore Gateway integration with MCP protocol for external tool access. Maximum productivity for commercial enterprises.',
    icon: CloudIcon,
    color: 'blue',
    features: [
      'AgentCore Gateway enabled',
      'External tool integrations',
      'Slack, Jira, PagerDuty, GitHub, Datadog',
      'Automated notifications',
      'Enhanced AI capabilities',
    ],
    restrictions: [
      'Requires internet connectivity',
      'External API dependencies',
      'Usage-based MCP costs',
    ],
  },
  [IntegrationModes.HYBRID]: {
    title: 'Hybrid Mode',
    subtitle: 'Balanced Approach',
    description: 'Selective external integrations with strict controls. Balance security with productivity.',
    icon: ServerStackIcon,
    color: 'purple',
    features: [
      'Configurable tool allowlist',
      'Per-tool HITL approval',
      'Budget controls per integration',
      'Audit trail for all external calls',
      'Gradual rollout support',
    ],
    restrictions: [
      'Complex configuration required',
      'Per-tool security review needed',
    ],
  },
};

// Color styles following design system
const COLOR_STYLES = {
  red: {
    bg: 'bg-critical-50 dark:bg-critical-900/20',
    border: 'border-critical-200 dark:border-critical-800',
    text: 'text-critical-700 dark:text-critical-400',
    iconBg: 'bg-critical-100 dark:bg-critical-900/30',
    button: 'bg-critical-600 hover:bg-critical-700',
    ring: 'ring-critical-500',
  },
  blue: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    text: 'text-aura-700 dark:text-aura-400',
    iconBg: 'bg-aura-100 dark:bg-aura-900/30',
    button: 'bg-aura-600 hover:bg-aura-700',
    ring: 'ring-aura-500',
  },
  purple: {
    bg: 'bg-aura-50 dark:bg-aura-900/20',
    border: 'border-aura-200 dark:border-aura-800',
    text: 'text-aura-700 dark:text-aura-400',
    iconBg: 'bg-aura-100 dark:bg-aura-900/30',
    button: 'bg-aura-600 hover:bg-aura-700',
    ring: 'ring-aura-500',
  },
};

export default function SettingsPage() {
  const { toast } = useToast();
  const { confirm } = useConfirm();
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [availableTools, setAvailableTools] = useState([]);
  const [mcpUsage, setMcpUsage] = useState(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [activeTab, setActiveTab] = useState('integration');

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  // Clear errors when switching tabs
  useEffect(() => {
    setError(null);
    setSuccessMessage(null);
  }, [activeTab]);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsData, tools, usage] = await Promise.all([
        getSettings(),
        getAvailableExternalTools(),
        getMcpUsageStats(),
      ]);
      setSettings(settingsData);
      setAvailableTools(tools);
      setMcpUsage(usage);
    } catch (err) {
      console.error('Failed to load settings:', err);
      setError('Failed to load settings. Using defaults.');
      // Continue with defaults
    } finally {
      setLoading(false);
    }
  };

  // Handle refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await loadSettings();
      toast.success('Settings refreshed');
    } catch (err) {
      toast.error('Failed to refresh settings');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleModeChange = async (mode) => {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    // Safe access to mcpSettings with fallback
    const mcpEnabled = settings.mcpSettings?.enabled ?? false;

    // If switching to defense mode, confirm MCP will be disabled
    if (mode === IntegrationModes.DEFENSE && mcpEnabled) {
      const confirmed = await confirm({
        title: 'Switch to Defense Mode',
        message: 'Switching to Defense Mode will disable MCP Gateway and all external tool integrations. Compliance will be set to CMMC Level 1. This change is reversible.',
        confirmText: 'Switch to Defense Mode',
        cancelText: 'Cancel',
        variant: 'warning',
      });
      if (!confirmed) {
        setSaving(false);
        return;
      }
    }

    try {
      await updateIntegrationMode(mode);

      // Update local state
      const newSettings = {
        ...settings,
        integrationMode: mode,
        mcpSettings: {
          ...(settings.mcpSettings || {}),
          enabled: mode === IntegrationModes.ENTERPRISE || (mode === IntegrationModes.HYBRID && mcpEnabled),
        },
      };

      // If defense mode, disable MCP and set CMMC Level 1 compliance
      if (mode === IntegrationModes.DEFENSE) {
        newSettings.mcpSettings.enabled = false;

        // Apply CMMC Level 1 compliance profile as default for Defense Mode
        try {
          await applyComplianceProfile('cmmc_l1');
        } catch (complianceErr) {
          console.warn('Could not apply compliance profile:', complianceErr);
        }

        setSettings(newSettings);
        setSuccessMessage('Defense Mode activated. MCP disabled, compliance set to CMMC Level 1. You can adjust compliance level in the Compliance tab.');

        // Navigate to compliance tab after a short delay to show the message
        setTimeout(() => {
          setActiveTab('compliance');
        }, 1500);
      } else {
        setSettings(newSettings);
        setSuccessMessage(`Integration mode changed to ${MODE_CONFIGS[mode].title}`);
      }

      // Clear success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg = typeof err?.message === 'string' ? err.message : (err?.toString?.() || 'Unknown error');
      setError(`Failed to update integration mode: ${errorMsg}`);
    } finally {
      setSaving(false);
    }
  };

  const handleHitlChange = async (field, value) => {
    const newHitlSettings = {
      ...settings.hitlSettings,
      [field]: value,
    };

    setSaving(true);
    try {
      await updateHitlSettings(newHitlSettings);
      setSettings({
        ...settings,
        hitlSettings: newHitlSettings,
      });
      setSuccessMessage('HITL settings updated');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(`Failed to update HITL settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleMcpChange = async (field, value) => {
    const newMcpSettings = {
      ...settings.mcpSettings,
      [field]: value,
    };

    setSaving(true);
    try {
      await updateMcpSettings(newMcpSettings);
      setSettings({
        ...settings,
        mcpSettings: newMcpSettings,
      });
      setSuccessMessage('MCP settings updated');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(`Failed to update MCP settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleToolToggle = async (toolId) => {
    const currentTools = settings.mcpSettings.externalToolsEnabled || [];
    const newTools = currentTools.includes(toolId)
      ? currentTools.filter((t) => t !== toolId)
      : [...currentTools, toolId];

    await handleMcpChange('externalToolsEnabled', newTools);
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionStatus(null);
    try {
      await testMcpConnection(
        settings.mcpSettings.gatewayUrl,
        settings.mcpSettings.apiKey
      );
      setConnectionStatus({ success: true, message: 'Connection successful!' });
    } catch (err) {
      setConnectionStatus({ success: false, message: err.message });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSecurityChange = async (field, value) => {
    const newSecuritySettings = {
      ...settings.securitySettings,
      [field]: value,
    };

    setSaving(true);
    try {
      await updateSecuritySettings(newSecuritySettings);
      setSettings({
        ...settings,
        securitySettings: newSecuritySettings,
      });
      setSuccessMessage('Security settings updated');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(`Failed to update security settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Grouped navigation structure for sidebar
  const navGroups = [
    {
      id: 'system',
      label: 'System',
      items: [
        { id: 'integration', label: 'Integration Mode', icon: ServerStackIcon },
        { id: 'orchestrator', label: 'Orchestrator Mode', icon: CpuChipIcon },
        { id: 'model_router', label: 'Model Router', icon: CpuChipIcon },
        { id: 'edition', label: 'Edition & License', icon: KeyIcon },
      ],
    },
    {
      id: 'workflows',
      label: 'Workflows',
      items: [
        { id: 'autonomy', label: 'Autonomy Policies', icon: BoltIcon },
        { id: 'hitl', label: 'HITL Settings', icon: UserGroupIcon },
      ],
    },
    {
      id: 'integrations',
      label: 'Integrations',
      items: [
        { id: 'mcp', label: 'MCP Configuration', icon: CloudIcon },
        { id: 'notifications', label: 'Notifications', icon: BellIcon },
        { id: 'ticketing', label: 'Support Ticketing', icon: TicketIcon },
      ],
    },
    {
      id: 'security',
      label: 'Security & Compliance',
      items: [
        { id: 'identity_providers', label: 'Identity Providers', icon: FingerPrintIcon },
        { id: 'security', label: 'Security Policies', icon: ShieldCheckIcon },
        { id: 'security_alerts', label: 'Alert Thresholds', icon: ShieldExclamationIcon },
        { id: 'privacy', label: 'Privacy & AI Training', icon: LockClosedIcon },
        { id: 'rate_limiting', label: 'Rate Limiting', icon: ChartBarIcon },
        { id: 'compliance', label: 'Compliance', icon: DocumentCheckIcon },
      ],
    },
    {
      id: 'advanced',
      label: 'Advanced',
      items: [
        { id: 'developer', label: 'Developer Tools', icon: CommandLineIcon },
      ],
    },
  ];

  // Mobile navigation state
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Get current nav item for mobile display
  const getCurrentNavItem = () => {
    for (const group of navGroups) {
      const item = group.items.find((i) => i.id === activeTab);
      if (item) return item;
    }
    return navGroups[0].items[0];
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ArrowPathIcon className="h-12 w-12 text-aura-600 dark:text-aura-400 animate-spin mx-auto" />
          <p className="mt-4 text-surface-600 dark:text-surface-400">Loading settings...</p>
        </div>
      </div>
    );
  }

  const currentNavItem = getCurrentNavItem();

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-100/50 dark:border-surface-700/30 px-4 sm:px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Cog6ToothIcon className="h-7 w-7 sm:h-8 sm:w-8 text-aura-600 dark:text-aura-400" />
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-surface-900 dark:text-surface-100">Platform Settings</h1>
              <p className="text-xs sm:text-sm text-surface-500 dark:text-surface-400 hidden sm:block">Configure integration mode, HITL controls, and security settings</p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)] disabled:opacity-50"
          >
            <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Mobile Navigation Trigger */}
      <div className="lg:hidden flex-shrink-0 bg-white dark:bg-surface-800 backdrop-blur-xl border-b border-surface-100/50 dark:border-surface-700/30 px-4 py-3">
        <button
          onClick={() => setMobileNavOpen(true)}
          className="w-full flex items-center justify-between px-4 py-3 bg-white dark:bg-surface-800 backdrop-blur-sm rounded-xl border border-surface-200/50 dark:border-surface-700/30 hover:bg-white/80 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
          aria-expanded={mobileNavOpen}
          aria-controls="mobile-settings-nav"
        >
          <div className="flex items-center gap-3">
            <currentNavItem.icon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
            <span className="font-medium text-surface-900 dark:text-surface-100">{currentNavItem.label}</span>
          </div>
          <ChevronDownIcon className="h-5 w-5 text-surface-400" />
        </button>
      </div>

      {/* Mobile Navigation Modal */}
      {mobileNavOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-md"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          {/* Modal */}
          <div
            id="mobile-settings-nav"
            className="absolute bottom-0 left-0 right-0 bg-white/95 dark:bg-surface-800/95 backdrop-blur-xl backdrop-saturate-150 rounded-t-2xl max-h-[80vh] overflow-y-auto shadow-[var(--shadow-glass-hover)] animate-in slide-in-from-bottom duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]"
            role="dialog"
            aria-modal="true"
            aria-label="Settings navigation"
          >
            <div className="sticky top-0 bg-white dark:bg-surface-800 backdrop-blur-xl px-4 py-3 border-b border-surface-100/50 dark:border-surface-700/30 flex items-center justify-between">
              <span className="font-semibold text-surface-900 dark:text-surface-100">Settings</span>
              <button
                onClick={() => setMobileNavOpen(false)}
                className="p-2 hover:bg-white/60 dark:hover:bg-surface-700 rounded-xl transition-all duration-200 ease-[var(--ease-tahoe)]"
                aria-label="Close navigation"
              >
                <XMarkIcon className="h-5 w-5 text-surface-500" />
              </button>
            </div>
            <nav className="p-4 space-y-6" aria-label="Settings navigation">
              {navGroups.map((group) => (
                <div key={group.id}>
                  <p className="px-3 mb-2 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">
                    {group.label}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => {
                          setActiveTab(item.id);
                          setMobileNavOpen(false);
                        }}
                        className={`
                          w-full flex items-center gap-3 px-3 py-3 rounded-xl text-left transition-all duration-200 ease-[var(--ease-tahoe)]
                          ${activeTab === item.id
                            ? 'bg-aura-100/80 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400 shadow-sm'
                            : 'text-surface-700 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700'
                          }
                        `}
                        aria-current={activeTab === item.id ? 'page' : undefined}
                      >
                        <item.icon className={`h-5 w-5 ${activeTab === item.id ? 'text-aura-600 dark:text-aura-400' : 'text-surface-400'}`} />
                        <span className="font-medium">{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </nav>
          </div>
        </div>
      )}

      {/* Main Content Area with Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop Sidebar Navigation */}
        <aside className="hidden lg:flex lg:flex-col lg:w-60 xl:w-64 flex-shrink-0 bg-white dark:bg-surface-800 backdrop-blur-xl border-r border-surface-100/50 dark:border-surface-700/30 overflow-y-auto">
          <nav className="p-4 space-y-6" aria-label="Settings navigation">
            {navGroups.map((group) => (
              <div key={group.id}>
                <p className="px-3 mb-2 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider">
                  {group.label}
                </p>
                <div className="space-y-1">
                  {group.items.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setActiveTab(item.id)}
                      className={`
                        w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all duration-200 ease-[var(--ease-tahoe)]
                        ${activeTab === item.id
                          ? 'bg-aura-100/80 dark:bg-aura-900/30 text-aura-600 dark:text-aura-400 shadow-[var(--shadow-glass)]'
                          : 'text-surface-600 dark:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700 hover:text-surface-900 dark:hover:text-surface-100'
                        }
                      `}
                      aria-current={activeTab === item.id ? 'page' : undefined}
                    >
                      <item.icon className={`h-5 w-5 flex-shrink-0 ${activeTab === item.id ? 'text-aura-600 dark:text-aura-400' : 'text-surface-400'}`} />
                      <span className="font-medium text-sm truncate">{item.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto">
          {/* Status messages */}
          {error && (
            <div className="mx-4 sm:mx-6 mt-4 p-4 bg-critical-50/90 dark:bg-critical-900/30 backdrop-blur-sm border border-critical-200/50 dark:border-critical-800/50 rounded-xl flex items-center gap-3 shadow-[var(--shadow-glass)]">
              <ExclamationTriangleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400 flex-shrink-0" />
              <span className="text-critical-700 dark:text-critical-300 text-sm">{error}</span>
            </div>
          )}

          {successMessage && (
            <div className="mx-4 sm:mx-6 mt-4 p-4 bg-olive-50/90 dark:bg-olive-900/30 backdrop-blur-sm border border-olive-200/50 dark:border-olive-800/50 rounded-xl flex items-center gap-3 shadow-[var(--shadow-glass)]">
              <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400 flex-shrink-0" />
              <span className="text-olive-700 dark:text-olive-300 text-sm">{successMessage}</span>
            </div>
          )}

          {/* Current Mode Banner */}
          <div className="mx-4 sm:mx-6 mt-4">
            <CurrentModeBanner mode={settings.integrationMode} />
          </div>

          {/* Tab Content */}
          <div className="px-4 sm:px-6 pt-6 pb-24">
            {activeTab === 'integration' && (
              <IntegrationModeTab
                currentMode={settings.integrationMode}
                onModeChange={handleModeChange}
                saving={saving}
              />
            )}

            {activeTab === 'hitl' && (
              <HitlSettingsTab
                settings={settings.hitlSettings}
                onChange={handleHitlChange}
                saving={saving}
              />
            )}

            {activeTab === 'mcp' && (
              <McpSettingsTab
                settings={settings.mcpSettings}
                integrationMode={settings.integrationMode}
                availableTools={availableTools}
                usage={mcpUsage}
                connectionStatus={connectionStatus}
                testingConnection={testingConnection}
                onChange={handleMcpChange}
                onToolToggle={handleToolToggle}
                onTestConnection={handleTestConnection}
                saving={saving}
              />
            )}

            {activeTab === 'security' && (
              <SecuritySettingsTab
                settings={settings.securitySettings}
                integrationMode={settings.integrationMode}
                onChange={handleSecurityChange}
                saving={saving}
              />
            )}

            {activeTab === 'autonomy' && (
              <AutonomyPoliciesTab
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'orchestrator' && (
              <OrchestratorModeTab
                integrationMode={settings.integrationMode}
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'model_router' && (
              <ModelRouterSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'notifications' && (
              <NotificationsSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'ticketing' && (
              <TicketingSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'security_alerts' && (
              <SecurityAlertSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'rate_limiting' && (
              <RateLimitingSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'privacy' && (
              <PrivacyTrainingSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'identity_providers' && (
              <IdentityProvidersSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'compliance' && (
              <ComplianceSettingsTab
                integrationMode={settings.integrationMode}
                onSuccess={(msg) => setSuccessMessage(msg)}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'edition' && (
              <EditionSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}

            {activeTab === 'developer' && (
              <DeveloperSettings
                onSuccess={(msg) => {
                  setSuccessMessage(msg);
                  setTimeout(() => setSuccessMessage(null), 3000);
                }}
                onError={(msg) => setError(msg)}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

// Current Mode Banner Component - uses green accent for selected state
function CurrentModeBanner({ mode }) {
  const config = MODE_CONFIGS[mode] || MODE_CONFIGS[IntegrationModes.DEFENSE];
  const Icon = config.icon;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-sm border-2 border-olive-500 dark:border-olive-400 rounded-xl p-4 shadow-[var(--shadow-glass)]">
      <div className="flex items-center gap-4">
        <div className="bg-olive-100 dark:bg-olive-900/30 p-3 rounded-xl backdrop-blur-sm">
          <Icon className="h-6 w-6 text-olive-600 dark:text-olive-400" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-olive-600 dark:text-olive-400">Current Mode:</span>
            <span className="font-bold text-surface-900 dark:text-surface-100">{config.title}</span>
          </div>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">{config.description}</p>
        </div>
      </div>
    </div>
  );
}

// Integration Mode Tab Component - unified card styling matching Compliance Profile
function IntegrationModeTab({ currentMode, onModeChange, saving }) {
  // Check if any mode is selected (should always be true, but defensive)
  const hasSelection = currentMode !== null && currentMode !== undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-4">
        <InformationCircleIcon className="h-5 w-5 text-aura-500" />
        <p className="text-sm text-surface-600 dark:text-surface-400">
          Select the integration mode that matches your organization&apos;s security requirements.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {Object.entries(MODE_CONFIGS).map(([mode, config]) => {
          const Icon = config.icon;
          const isSelected = currentMode === mode;
          // Grey out unselected cards when one is selected
          const isGreyedOut = hasSelection && !isSelected;

          return (
            <div
              key={mode}
              className={`
                relative border-2 rounded-xl p-6 transition-all duration-200 ease-[var(--ease-tahoe)] cursor-pointer
                bg-white dark:bg-surface-800
                ${isSelected
                  ? 'border-olive-500 dark:border-olive-400 shadow-[var(--shadow-glass-hover)]'
                  : 'border-surface-200 dark:border-surface-700 hover:border-surface-400 dark:hover:border-surface-500 shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)]'
                }
                ${isGreyedOut && !saving ? 'opacity-50' : ''}
                ${saving ? 'opacity-50 cursor-not-allowed' : ''}
              `}
              onClick={() => !saving && onModeChange(mode)}
            >
              {isSelected && (
                <div className="absolute top-3 right-3">
                  <CheckCircleIcon className="h-6 w-6 text-olive-500 dark:text-olive-400" />
                </div>
              )}

              <div className={`${isSelected ? 'bg-olive-100 dark:bg-olive-900/30' : 'bg-surface-100 dark:bg-surface-700'} w-12 h-12 rounded-xl flex items-center justify-center mb-4`}>
                <Icon className={`h-6 w-6 ${isSelected ? 'text-olive-600 dark:text-olive-400' : 'text-surface-600 dark:text-surface-400'}`} />
              </div>

              <h3 className={`text-lg font-bold ${isSelected ? 'text-olive-600 dark:text-olive-400' : 'text-surface-900 dark:text-surface-100'}`}>{config.title}</h3>
              <p className={`text-sm ${isSelected ? 'text-olive-600 dark:text-olive-400' : 'text-surface-500 dark:text-surface-400'} mb-4`}>{config.subtitle}</p>
              <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">{config.description}</p>

              <div className="space-y-3">
                <div>
                  <p className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">Features</p>
                  <ul className="space-y-1">
                    {config.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-surface-700 dark:text-surface-300">
                        <CheckCircleIcon className="h-4 w-4 text-olive-500 mt-0.5 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <p className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-2">Restrictions</p>
                  <ul className="space-y-1">
                    {config.restrictions.map((restriction, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-surface-500 dark:text-surface-400">
                        <ExclamationTriangleIcon className="h-4 w-4 text-warning-500 mt-0.5 flex-shrink-0" />
                        {restriction}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  if (!saving && !isSelected) {
                    onModeChange(mode);
                  }
                }}
                disabled={saving || isSelected}
                className={`
                  mt-6 w-full py-2.5 px-4 rounded-xl font-medium transition-all duration-200 ease-[var(--ease-tahoe)] relative z-10
                  ${isSelected
                    ? 'bg-olive-500 text-white cursor-default'
                    : 'bg-aura-500 hover:bg-aura-600 text-white hover:opacity-90 active:scale-[0.98] shadow-sm hover:shadow-md'
                  }
                `}
              >
                {isSelected ? 'Current Mode' : `Select ${config.title}`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// HITL Settings Tab Component
function HitlSettingsTab({ settings, onChange, saving }) {
  // Defensive defaults for undefined settings
  const safeSettings = settings || {
    requireApprovalForPatches: true,
    requireApprovalForDeployments: true,
    requireApprovalForNewAgents: true,
    autoApproveMinorPatches: false,
    approvalTimeout: 24,
    escalationEnabled: true,
  };

  return (
    <div className="max-w-3xl space-y-8">
      {/* Approval Requirements */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ShieldCheckIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          Approval Requirements
        </h3>
        <div className="space-y-4">
          <ToggleSetting
            label="Require approval for patches"
            description="All auto-generated patches require human approval before deployment"
            checked={safeSettings.requireApprovalForPatches}
            onChange={(checked) => onChange('requireApprovalForPatches', checked)}
            disabled={saving}
          />
          <ToggleSetting
            label="Require approval for deployments"
            description="All deployment operations require human approval"
            checked={safeSettings.requireApprovalForDeployments}
            onChange={(checked) => onChange('requireApprovalForDeployments', checked)}
            disabled={saving}
          />
          <ToggleSetting
            label="Auto-approve minor patches"
            description="Low-severity patches can be auto-approved after sandbox testing passes"
            checked={safeSettings.autoApproveMinorPatches}
            onChange={(checked) => onChange('autoApproveMinorPatches', checked)}
            disabled={saving}
          />
        </div>
      </div>

      {/* Approval Workflow */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ClockIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          Approval Workflow
        </h3>
        <div className="space-y-4">
          <NumberSetting
            label="Approval timeout (hours)"
            description="Time before an approval request expires"
            value={safeSettings.approvalTimeoutHours}
            onChange={(value) => onChange('approvalTimeoutHours', value)}
            min={1}
            max={168}
            disabled={saving}
          />
          <NumberSetting
            label="Minimum approvers"
            description="Number of approvals required for critical patches"
            value={safeSettings.minApprovers}
            onChange={(value) => onChange('minApprovers', value)}
            min={1}
            max={5}
            disabled={saving}
          />
        </div>
      </div>

      {/* Notifications */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <BellIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          Notifications
        </h3>
        <div className="space-y-4">
          <ToggleSetting
            label="Notify on approval request"
            description="Send email/Slack notification when new approval is requested"
            checked={safeSettings.notifyOnApprovalRequest}
            onChange={(checked) => onChange('notifyOnApprovalRequest', checked)}
            disabled={saving}
          />
          <ToggleSetting
            label="Notify on approval timeout"
            description="Send reminder before approval requests expire"
            checked={safeSettings.notifyOnApprovalTimeout}
            onChange={(checked) => onChange('notifyOnApprovalTimeout', checked)}
            disabled={saving}
          />
        </div>
      </div>
    </div>
  );
}

// MCP Settings Tab Component
function McpSettingsTab({
  settings,
  integrationMode,
  availableTools,
  usage,
  connectionStatus,
  testingConnection,
  onChange,
  onToolToggle,
  onTestConnection,
  saving,
}) {
  // Defensive defaults for undefined settings
  const safeSettings = settings || {
    enabled: false,
    gatewayUrl: '',
    apiKey: '',
    monthlyBudgetUsd: 100,
    dailyLimitUsd: 10,
    externalToolsEnabled: [],
  };

  const isDisabled = integrationMode === IntegrationModes.DEFENSE;

  if (isDisabled) {
    return (
      <div className="max-w-3xl">
        <div className="bg-warning-50/90 dark:bg-warning-900/30 backdrop-blur-sm border border-warning-200/50 dark:border-warning-800/50 rounded-xl p-6 shadow-[var(--shadow-glass)]">
          <div className="flex items-start gap-4">
            <ExclamationTriangleIcon className="h-6 w-6 text-warning-600 dark:text-warning-400 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-warning-800 dark:text-warning-200">MCP Disabled in Defense Mode</h3>
              <p className="text-sm text-warning-700 dark:text-warning-300 mt-1">
                MCP Gateway and external tool integrations are disabled in Defense Mode for maximum security.
                Switch to Enterprise or Hybrid mode to enable these features.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-8">
      {/* MCP Enable/Disable */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <CloudIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          AgentCore Gateway
        </h3>
        <ToggleSetting
          label="Enable MCP Gateway"
          description="Connect to AgentCore Gateway for external tool integrations"
          checked={safeSettings.enabled}
          onChange={(checked) => onChange('enabled', checked)}
          disabled={saving}
        />

        {safeSettings.enabled && (
          <div className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Gateway URL
              </label>
              <input
                type="url"
                value={safeSettings.gatewayUrl}
                onChange={(e) => onChange('gatewayUrl', e.target.value)}
                placeholder="https://gateway.agentcore.io"
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-xl bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent transition-all duration-200 ease-[var(--ease-tahoe)]"
                disabled={saving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                API Key
              </label>
              <input
                type="password"
                value={safeSettings.apiKey}
                onChange={(e) => onChange('apiKey', e.target.value)}
                placeholder="Enter your AgentCore API key"
                className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-xl bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent transition-all duration-200 ease-[var(--ease-tahoe)]"
                disabled={saving}
              />
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={onTestConnection}
                disabled={!safeSettings.gatewayUrl || !safeSettings.apiKey || testingConnection}
                className="flex items-center gap-2 px-4 py-2.5 bg-aura-600 text-white rounded-xl hover:bg-aura-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-all duration-200 ease-[var(--ease-tahoe)] shadow-sm hover:shadow-md"
              >
                {testingConnection ? (
                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                ) : (
                  <LinkIcon className="h-4 w-4" />
                )}
                Test Connection
              </button>
              {connectionStatus && (
                <span className={`flex items-center gap-1 text-sm ${connectionStatus.success ? 'text-olive-600 dark:text-olive-400' : 'text-critical-600 dark:text-critical-400'}`}>
                  {connectionStatus.success ? (
                    <CheckCircleIcon className="h-4 w-4" />
                  ) : (
                    <ExclamationTriangleIcon className="h-4 w-4" />
                  )}
                  {connectionStatus.message}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Budget Controls */}
      {safeSettings.enabled && (
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
            <CurrencyDollarIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
            Budget Controls
          </h3>

          {usage && (
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-surface-50 dark:bg-surface-800 backdrop-blur-sm rounded-xl p-4 border border-surface-200/30 dark:border-surface-700/20">
                <p className="text-sm text-surface-500 dark:text-surface-400">Current Month</p>
                <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">${(usage.currentMonthCost ?? 0).toFixed(2)}</p>
              </div>
              <div className="bg-surface-50 dark:bg-surface-800 backdrop-blur-sm rounded-xl p-4 border border-surface-200/30 dark:border-surface-700/20">
                <p className="text-sm text-surface-500 dark:text-surface-400">Budget Remaining</p>
                <p className="text-2xl font-bold text-olive-600 dark:text-olive-400">${(usage.budgetRemaining ?? 0).toFixed(2)}</p>
              </div>
            </div>
          )}

          <div className="space-y-4">
            <NumberSetting
              label="Monthly budget (USD)"
              description="Maximum monthly spend on MCP invocations"
              value={safeSettings.monthlyBudgetUsd}
              onChange={(value) => onChange('monthlyBudgetUsd', value)}
              min={0}
              max={10000}
              step={10}
              disabled={saving}
              prefix="$"
            />
            <NumberSetting
              label="Daily limit (USD)"
              description="Maximum daily spend on MCP invocations"
              value={safeSettings.dailyLimitUsd}
              onChange={(value) => onChange('dailyLimitUsd', value)}
              min={0}
              max={1000}
              step={1}
              disabled={saving}
              prefix="$"
            />
          </div>
        </div>
      )}

      {/* External Tools */}
      {safeSettings.enabled && (
        <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
            <CommandLineIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
            External Tool Integrations
          </h3>
          <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
            Select which external tools can be accessed via MCP Gateway.
            {integrationMode === IntegrationModes.HYBRID && ' Each tool requires HITL approval in Hybrid mode.'}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {availableTools.map((tool) => (
              <ToolCard
                key={tool.id}
                tool={tool}
                enabled={(safeSettings.externalToolsEnabled || []).includes(tool.id)}
                onToggle={() => onToolToggle(tool.id)}
                disabled={saving}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Security Settings Tab Component
function SecuritySettingsTab({ settings, integrationMode, onChange, saving }) {
  // Defensive defaults for undefined settings
  const safeSettings = settings || {
    retainLogsForDays: 90,
    blockExternalNetwork: true,
    auditAllActions: true,
    sandboxIsolationLevel: 'container',
  };

  const isDefenseMode = integrationMode === IntegrationModes.DEFENSE;

  // Determine compliance status based on log retention
  const getRetentionCompliance = (days) => {
    if (days >= 365) return { status: 'compliant', label: 'GovCloud Ready' };
    if (days >= 90) return { status: 'compliant', label: 'CMMC L2 Compliant' };
    return { status: 'warning', label: 'Below CMMC L2 Minimum' };
  };

  const retentionCompliance = getRetentionCompliance(safeSettings.retainLogsForDays);

  return (
    <div className="max-w-3xl space-y-8">
      {/* Log Retention Configuration */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ClockIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          Log Retention Policy
        </h3>

        <div className="mb-4">
          <p className="text-sm text-surface-600 dark:text-surface-400 mb-4">
            Configure how long CloudWatch logs are retained. CMMC Level 2 requires a minimum of 90 days.
          </p>

          {/* Current Compliance Status */}
          <div className={`
            mb-4 p-3 rounded-xl flex items-center gap-3 backdrop-blur-sm
            ${retentionCompliance.status === 'compliant'
              ? 'bg-olive-50/90 dark:bg-olive-900/20 border border-olive-200/50 dark:border-olive-800/50'
              : 'bg-warning-50/90 dark:bg-warning-900/20 border border-warning-200/50 dark:border-warning-800/50'
            }
          `}>
            {retentionCompliance.status === 'compliant' ? (
              <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
            ) : (
              <ExclamationTriangleIcon className="h-5 w-5 text-warning-600 dark:text-warning-400" />
            )}
            <span className={`text-sm font-medium ${
              retentionCompliance.status === 'compliant'
                ? 'text-olive-700 dark:text-olive-300'
                : 'text-warning-700 dark:text-warning-300'
            }`}>
              {retentionCompliance.label}: {safeSettings.retainLogsForDays} days retention
            </span>
          </div>

          {/* Retention Selector */}
          <div className="space-y-3">
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
              Select Retention Period
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {LOG_RETENTION_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => onChange('retainLogsForDays', option.value)}
                  disabled={saving}
                  className={`
                    relative p-4 rounded-xl border text-left transition-all duration-200 ease-[var(--ease-tahoe)]
                    ${safeSettings.retainLogsForDays === option.value
                      ? 'border-aura-500 bg-aura-50/90 dark:bg-aura-900/20 ring-2 ring-aura-500 shadow-[var(--shadow-glass-hover)]'
                      : 'border-surface-200/50 dark:border-surface-700/30 bg-white dark:bg-surface-800 hover:border-surface-300/60 dark:hover:border-surface-600/40 hover:bg-white/80 dark:hover:bg-surface-700 shadow-[var(--shadow-glass)]'
                    }
                    ${saving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                  `}
                >
                  {safeSettings.retainLogsForDays === option.value && (
                    <CheckCircleIcon className="absolute top-2 right-2 h-5 w-5 text-aura-600 dark:text-aura-400" />
                  )}
                  {option.recommended && (
                    <span className="absolute top-2 right-2 text-xs font-medium text-olive-600 dark:text-olive-400 bg-olive-100 dark:bg-olive-900/30 px-2 py-0.5 rounded">
                      Recommended
                    </span>
                  )}
                  <p className="font-semibold text-surface-900 dark:text-surface-100">{option.label}</p>
                  <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">{option.compliance}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 p-3 bg-surface-50 dark:bg-surface-800 backdrop-blur-sm rounded-xl border border-surface-200/30 dark:border-surface-700/20">
          <p className="text-xs text-surface-500 dark:text-surface-400">
            <InformationCircleIcon className="inline h-4 w-4 mr-1" />
            Changes to log retention will apply to all new log entries. Existing logs follow their original retention policy until expiration.
          </p>
        </div>
      </div>

      {/* Security Overview */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <LockClosedIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          Security Overview
        </h3>

        <div className="grid grid-cols-2 gap-4">
          <SecurityStatusCard
            label="Air-Gap Compatible"
            status={isDefenseMode}
            description={isDefenseMode ? 'No external network calls' : 'External calls enabled'}
          />
          <SecurityStatusCard
            label="External Network"
            status={safeSettings.blockExternalNetwork}
            statusLabel={safeSettings.blockExternalNetwork ? 'Blocked' : 'Allowed'}
            description="Sandbox network isolation"
          />
          <SecurityStatusCard
            label="Audit Logging"
            status={safeSettings.auditAllActions}
            description="All actions logged"
          />
          <SecurityStatusCard
            label="Log Retention"
            status={safeSettings.retainLogsForDays >= 90}
            statusLabel={`${safeSettings.retainLogsForDays} days`}
            description="CMMC L2 minimum: 90 days"
          />
        </div>
      </div>

      {/* Compliance Status */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
          <ShieldCheckIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
          Compliance Status
        </h3>
        <div className="space-y-3">
          <ComplianceBadge
            framework="CMMC Level 2"
            status={safeSettings.retainLogsForDays >= 90 ? 'compliant' : 'partial'}
          />
          <ComplianceBadge
            framework="NIST 800-53"
            status={isDefenseMode ? 'compliant' : 'partial'}
          />
          <ComplianceBadge
            framework="FedRAMP High"
            status={isDefenseMode && safeSettings.retainLogsForDays >= 365 ? 'ready' : 'not_applicable'}
          />
          <ComplianceBadge
            framework="SOX"
            status="compliant"
          />
        </div>
      </div>

      {/* Sandbox Isolation */}
      <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 p-6 shadow-[var(--shadow-glass)]">
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-4">Sandbox Isolation Level</h3>
        <div className="flex gap-4">
          {['container', 'vpc', 'full'].map((level) => (
            <div
              key={level}
              className={`
                flex-1 p-4 rounded-xl border transition-all duration-200 ease-[var(--ease-tahoe)]
                ${safeSettings.sandboxIsolationLevel === level
                  ? 'border-aura-500 bg-aura-50/90 dark:bg-aura-900/20 shadow-[var(--shadow-glass-hover)]'
                  : 'border-surface-200/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800 hover:bg-white/80 dark:hover:bg-surface-700'
                }
              `}
            >
              <p className="font-medium text-surface-900 dark:text-surface-100 capitalize">{level}</p>
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                {level === 'container' && 'Isolated container'}
                {level === 'vpc' && 'Dedicated VPC'}
                {level === 'full' && 'Complete isolation'}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Reusable Components
function ToggleSetting({ label, description, checked, onChange, disabled }) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="font-medium text-surface-900 dark:text-surface-100">{label}</p>
        <p className="text-sm text-surface-500 dark:text-surface-400">{description}</p>
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        disabled={disabled}
        className={`
          relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
          transition-all duration-200 ease-[var(--ease-tahoe)] focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
          ${checked ? 'bg-aura-600 shadow-sm' : 'bg-surface-200 dark:bg-surface-600'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <span
          className={`
            pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0
            transition-all duration-200 ease-[var(--ease-tahoe)]
            ${checked ? 'translate-x-5' : 'translate-x-0'}
          `}
        />
      </button>
    </div>
  );
}

function NumberSetting({ label, description, value, onChange, min, max, step = 1, disabled, prefix }) {
  return (
    <div className="py-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="font-medium text-surface-900 dark:text-surface-100">{label}</p>
          <p className="text-sm text-surface-500 dark:text-surface-400">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          {prefix && <span className="text-surface-500 dark:text-surface-400">{prefix}</span>}
          <input
            type="number"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            min={min}
            max={max}
            step={step}
            disabled={disabled}
            className="w-24 px-3 py-1.5 border border-surface-300 dark:border-surface-600 rounded-xl text-right bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent disabled:bg-surface-100 dark:disabled:bg-surface-800 transition-all duration-200 ease-[var(--ease-tahoe)]"
          />
        </div>
      </div>
    </div>
  );
}

function ToolCard({ tool, enabled, onToggle, disabled }) {
  return (
    <div
      className={`
        p-4 rounded-xl border cursor-pointer transition-all duration-200 ease-[var(--ease-tahoe)]
        ${enabled
          ? 'border-aura-500 bg-aura-50/90 dark:bg-aura-900/20 shadow-[var(--shadow-glass-hover)]'
          : 'border-surface-200/50 dark:border-surface-700/30 bg-white dark:bg-surface-800 hover:border-surface-300/60 dark:hover:border-surface-600/40 hover:bg-white/80 dark:hover:bg-surface-700 shadow-[var(--shadow-glass)]'
        }
      `}
      onClick={() => !disabled && onToggle()}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="font-medium text-surface-900 dark:text-surface-100">{tool.name}</p>
          <p className="text-xs text-surface-500 dark:text-surface-400 capitalize">{tool.category.replace('_', ' ')}</p>
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">{tool.description}</p>
        </div>
        <div
          className={`
            w-5 h-5 rounded border-2 flex items-center justify-center transition-colors
            ${enabled
              ? 'bg-aura-600 border-aura-600'
              : 'border-surface-300 dark:border-surface-600'
            }
          `}
        >
          {enabled && <CheckCircleIcon className="h-4 w-4 text-white" />}
        </div>
      </div>
    </div>
  );
}

function SecurityStatusCard({ label, status, statusLabel, description }) {
  return (
    <div className="bg-surface-50 dark:bg-surface-800 backdrop-blur-sm rounded-xl p-4 border border-surface-200/30 dark:border-surface-700/20">
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm font-medium text-surface-700 dark:text-surface-300">{label}</p>
        <span
          className={`
            px-2.5 py-0.5 rounded-lg text-xs font-medium
            ${status
              ? 'bg-olive-100/80 dark:bg-olive-900/30 text-olive-700 dark:text-olive-400'
              : 'bg-warning-100/80 dark:bg-warning-900/30 text-warning-700 dark:text-warning-400'
            }
          `}
        >
          {statusLabel || (status ? 'Enabled' : 'Disabled')}
        </span>
      </div>
      <p className="text-xs text-surface-500 dark:text-surface-400">{description}</p>
    </div>
  );
}

function ComplianceBadge({ framework, status }) {
  const statusConfig = {
    compliant: { bg: 'bg-olive-100/80 dark:bg-olive-900/30', text: 'text-olive-700 dark:text-olive-400', label: 'Compliant' },
    partial: { bg: 'bg-warning-100/80 dark:bg-warning-900/30', text: 'text-warning-700 dark:text-warning-400', label: 'Partial' },
    ready: { bg: 'bg-aura-100/80 dark:bg-aura-900/30', text: 'text-aura-700 dark:text-aura-400', label: 'Ready' },
    not_applicable: { bg: 'bg-surface-100/80 dark:bg-surface-700/50', text: 'text-surface-600 dark:text-surface-400', label: 'N/A' },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center justify-between py-2">
      <span className="font-medium text-surface-900 dark:text-surface-100">{framework}</span>
      <span className={`px-3 py-1 rounded-xl text-sm font-medium ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    </div>
  );
}
