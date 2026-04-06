/**
 * Project Aura - Slack Integration Configuration Modal
 *
 * Configuration interface for Slack integration including OAuth 2.0 authentication,
 * webhook setup, channel configuration, and notification routing.
 *
 * Features:
 * - OAuth 2.0 authentication with Slack workspace
 * - Incoming webhook URL configuration
 * - Bot token management
 * - Channel mapping for different notification types
 * - Test connection functionality
 */

import { useState, useEffect } from 'react';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  EyeSlashIcon,
  LinkIcon,
  InformationCircleIcon,
  ChatBubbleLeftRightIcon,
  HashtagIcon,
  BellAlertIcon,
  ArrowTopRightOnSquareIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { useIntegrationConfig } from '../../hooks/useIntegrations';
import { useFocusTrap } from '../../hooks/useFocusTrap';

// Notification type options for channel mapping
const NOTIFICATION_TYPES = [
  {
    id: 'alerts',
    label: 'Security Alerts',
    description: 'Critical security notifications and vulnerability alerts',
    defaultChannel: '#security-alerts',
    icon: BellAlertIcon,
  },
  {
    id: 'approvals',
    label: 'HITL Approvals',
    description: 'Human-in-the-loop approval requests for patches',
    defaultChannel: '#hitl-approvals',
    icon: CheckCircleIcon,
  },
  {
    id: 'incidents',
    label: 'Incidents',
    description: 'Incident notifications and status updates',
    defaultChannel: '#incidents',
    icon: ExclamationCircleIcon,
  },
  {
    id: 'notifications',
    label: 'General Notifications',
    description: 'General system notifications and updates',
    defaultChannel: '#aura-notifications',
    icon: ChatBubbleLeftRightIcon,
  },
];

// Authentication method options
const AUTH_METHODS = [
  {
    id: 'oauth',
    label: 'OAuth 2.0',
    description: 'Full workspace integration with bot user',
    recommended: true,
  },
  {
    id: 'webhook',
    label: 'Incoming Webhook',
    description: 'Simple webhook for sending messages only',
    recommended: false,
  },
  {
    id: 'bot_token',
    label: 'Bot Token',
    description: 'Direct bot token for API access',
    recommended: false,
  },
];

export default function SlackConfig({ isOpen, onClose, onSave, existingConfig }) {
  const {
    config,
    loading,
    saving,
    testing,
    testResult,
    validationErrors,
    updateField,
    testConnection,
    saveConfig,
  } = useIntegrationConfig('slack');

  // WCAG 2.1 AA: Focus trap for modal
  const { containerRef } = useFocusTrap(isOpen, {
    autoFocus: true,
    restoreFocus: true,
    escapeDeactivates: true,
    onEscape: onClose,
  });

  const [showSecrets, setShowSecrets] = useState({});
  const [authMethod, setAuthMethod] = useState('webhook');
  const [channelMappings, setChannelMappings] = useState({
    alerts: '#security-alerts',
    approvals: '#hitl-approvals',
    incidents: '#incidents',
    notifications: '#aura-notifications',
  });
  const [notificationSettings, setNotificationSettings] = useState({
    includeStackTrace: false,
    mentionOnCritical: true,
    threadReplies: true,
  });

  // Initialize with existing config
  useEffect(() => {
    if (existingConfig) {
      Object.entries(existingConfig).forEach(([key, value]) => {
        updateField(key, value);
      });
      if (existingConfig.auth_method) {
        setAuthMethod(existingConfig.auth_method);
      }
      if (existingConfig.channel_mappings) {
        setChannelMappings(existingConfig.channel_mappings);
      }
      if (existingConfig.notification_settings) {
        setNotificationSettings(existingConfig.notification_settings);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingConfig]);

  const toggleSecret = (fieldName) => {
    setShowSecrets((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  };

  const updateChannelMapping = (notificationType, channel) => {
    setChannelMappings((prev) => ({ ...prev, [notificationType]: channel }));
  };

  const toggleNotificationSetting = (setting) => {
    setNotificationSettings((prev) => ({ ...prev, [setting]: !prev[setting] }));
  };

  const handleOAuthConnect = () => {
    // In a real implementation, this would redirect to Slack OAuth
    const clientId = config.client_id;
    const redirectUri = `${window.location.origin}/integrations/slack/callback`;
    const scopes = 'chat:write,channels:read,channels:join,groups:read,users:read,incoming-webhook';
    const state = crypto.getRandomValues(new Uint8Array(16)).reduce((s, b) => s + b.toString(16).padStart(2, '0'), '');

    // Store state for verification
    sessionStorage.setItem('slack_oauth_state', state);

    const oauthUrl = `https://slack.com/oauth/v2/authorize?client_id=${clientId}&scope=${scopes}&redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}`;

    window.open(oauthUrl, '_blank', 'width=600,height=700');
  };

  const handleSave = async () => {
    try {
      const fullConfig = {
        ...config,
        auth_method: authMethod,
        channel_mappings: channelMappings,
        notification_settings: notificationSettings,
      };
      await saveConfig(fullConfig);
      onSave?.(fullConfig);
      onClose();
    } catch (err) {
      // Error handled by hook
    }
  };

  const isValidConfig = () => {
    if (authMethod === 'webhook') {
      return config.webhook_url && config.webhook_url.startsWith('https://hooks.slack.com/');
    } else if (authMethod === 'bot_token') {
      return config.bot_token && config.bot_token.startsWith('xoxb-');
    } else if (authMethod === 'oauth') {
      return config.client_id && config.client_secret;
    }
    return false;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div ref={containerRef} className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col" role="dialog" aria-modal="true" aria-labelledby="slack-config-title">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-xl">
              <ChatBubbleLeftRightIcon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h2 id="slack-config-title" className="text-xl font-bold text-surface-900 dark:text-surface-100">
                Configure Slack Integration
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Team messaging and notifications
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
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <ArrowPathIcon className="h-8 w-8 text-aura-500 animate-spin" />
            </div>
          ) : (
            <>
              {/* Authentication Method Selection */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Authentication Method
                </h3>

                <div className="space-y-3">
                  {AUTH_METHODS.map((method) => (
                    <button
                      key={method.id}
                      type="button"
                      onClick={() => setAuthMethod(method.id)}
                      className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                        authMethod === method.id
                          ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                          : 'border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-surface-900 dark:text-surface-100">
                            {method.label}
                            {method.recommended && (
                              <span className="ml-2 text-xs px-2 py-0.5 bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded-full">
                                Recommended
                              </span>
                            )}
                          </p>
                          <p className="text-sm text-surface-500 dark:text-surface-400">
                            {method.description}
                          </p>
                        </div>
                        <div
                          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                            authMethod === method.id
                              ? 'border-aura-500 bg-aura-500'
                              : 'border-surface-300 dark:border-surface-600'
                          }`}
                        >
                          {authMethod === method.id && (
                            <div className="w-2 h-2 rounded-full bg-white" />
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </section>

              {/* OAuth Configuration */}
              {authMethod === 'oauth' && (
                <section>
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                    OAuth 2.0 Credentials
                  </h3>

                  <div className="space-y-4">
                    {/* Client ID */}
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Client ID <span className="text-critical-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={config.client_id || ''}
                        onChange={(e) => updateField('client_id', e.target.value)}
                        placeholder="Your Slack App Client ID"
                        className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.client_id
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                        Found in your Slack App's Basic Information page
                      </p>
                    </div>

                    {/* Client Secret */}
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Client Secret <span className="text-critical-500">*</span>
                      </label>
                      <div className="relative">
                        <input
                          type={showSecrets.client_secret ? 'text' : 'password'}
                          value={config.client_secret || ''}
                          onChange={(e) => updateField('client_secret', e.target.value)}
                          placeholder="Your Slack App Client Secret"
                          className="w-full px-3 py-2 pr-10 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                        />
                        <button
                          type="button"
                          onClick={() => toggleSecret('client_secret')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                        >
                          {showSecrets.client_secret ? (
                            <EyeSlashIcon className="h-5 w-5" />
                          ) : (
                            <EyeIcon className="h-5 w-5" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* OAuth Connect Button */}
                    <div className="pt-2">
                      <button
                        onClick={handleOAuthConnect}
                        disabled={!config.client_id || !config.client_secret}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
                      >
                        <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                        Connect with Slack
                      </button>
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">
                        This will open a new window to authorize Project Aura with your Slack workspace
                      </p>
                    </div>
                  </div>
                </section>
              )}

              {/* Webhook Configuration */}
              {authMethod === 'webhook' && (
                <section>
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                    Incoming Webhook
                  </h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Webhook URL <span className="text-critical-500">*</span>
                      </label>
                      <input
                        type="url"
                        value={config.webhook_url || ''}
                        onChange={(e) => updateField('webhook_url', e.target.value)}
                        placeholder="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
                        className={`w-full px-3 py-2 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                          validationErrors.webhook_url
                            ? 'border-critical-300 dark:border-critical-700'
                            : 'border-surface-300 dark:border-surface-600'
                        }`}
                      />
                      {validationErrors.webhook_url && (
                        <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                          {validationErrors.webhook_url}
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <p className="text-xs text-surface-500 dark:text-surface-400">
                          Create an incoming webhook in your Slack app settings
                        </p>
                        <a
                          href="https://api.slack.com/messaging/webhooks"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                        >
                          Learn more
                          <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                        </a>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* Bot Token Configuration */}
              {authMethod === 'bot_token' && (
                <section>
                  <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                    Bot User OAuth Token
                  </h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Bot Token <span className="text-critical-500">*</span>
                      </label>
                      <div className="relative">
                        <input
                          type={showSecrets.bot_token ? 'text' : 'password'}
                          value={config.bot_token || ''}
                          onChange={(e) => updateField('bot_token', e.target.value)}
                          placeholder="xoxb-your-bot-token"
                          className={`w-full px-3 py-2 pr-10 border rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 ${
                            validationErrors.bot_token
                              ? 'border-critical-300 dark:border-critical-700'
                              : 'border-surface-300 dark:border-surface-600'
                          }`}
                        />
                        <button
                          type="button"
                          onClick={() => toggleSecret('bot_token')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                        >
                          {showSecrets.bot_token ? (
                            <EyeSlashIcon className="h-5 w-5" />
                          ) : (
                            <EyeIcon className="h-5 w-5" />
                          )}
                        </button>
                      </div>
                      {validationErrors.bot_token && (
                        <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                          {validationErrors.bot_token}
                        </p>
                      )}
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                        Found in OAuth & Permissions page of your Slack app
                      </p>
                    </div>

                    {/* Signing Secret (optional) */}
                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Signing Secret
                      </label>
                      <div className="relative">
                        <input
                          type={showSecrets.signing_secret ? 'text' : 'password'}
                          value={config.signing_secret || ''}
                          onChange={(e) => updateField('signing_secret', e.target.value)}
                          placeholder="Optional: For verifying webhook requests"
                          className="w-full px-3 py-2 pr-10 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                        />
                        <button
                          type="button"
                          onClick={() => toggleSecret('signing_secret')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
                        >
                          {showSecrets.signing_secret ? (
                            <EyeSlashIcon className="h-5 w-5" />
                          ) : (
                            <EyeIcon className="h-5 w-5" />
                          )}
                        </button>
                      </div>
                      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                        Required for receiving interactive message events
                      </p>
                    </div>
                  </div>
                </section>
              )}

              {/* Default Channel */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Default Settings
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Default Channel
                    </label>
                    <div className="relative">
                      <HashtagIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-surface-400" />
                      <input
                        type="text"
                        value={config.default_channel || '#security-alerts'}
                        onChange={(e) => updateField('default_channel', e.target.value)}
                        placeholder="security-alerts"
                        className="w-full pl-9 pr-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                      />
                    </div>
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
                      Channel to use when no specific channel is configured
                    </p>
                  </div>
                </div>
              </section>

              {/* Channel Mapping */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Channel Routing
                </h3>
                <p className="text-sm text-surface-500 dark:text-surface-400 mb-4">
                  Configure which channels receive different types of notifications
                </p>

                <div className="space-y-3">
                  {NOTIFICATION_TYPES.map((notifType) => {
                    const TypeIcon = notifType.icon;
                    return (
                      <div
                        key={notifType.id}
                        className="flex items-center gap-4 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg"
                      >
                        <div className="p-2 bg-surface-100 dark:bg-surface-600 rounded-lg">
                          <TypeIcon className="h-4 w-4 text-surface-600 dark:text-surface-300" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                            {notifType.label}
                          </p>
                          <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
                            {notifType.description}
                          </p>
                        </div>
                        <div className="relative w-40">
                          <HashtagIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-surface-400" />
                          <input
                            type="text"
                            value={channelMappings[notifType.id]?.replace('#', '') || ''}
                            onChange={(e) =>
                              updateChannelMapping(
                                notifType.id,
                                e.target.value.startsWith('#') ? e.target.value : `#${e.target.value}`
                              )
                            }
                            placeholder={notifType.defaultChannel.replace('#', '')}
                            className="w-full pl-7 pr-2 py-1.5 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Notification Settings */}
              <section>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 uppercase tracking-wide mb-4">
                  Notification Options
                </h3>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                        Mention @channel on Critical Alerts
                      </p>
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Send @channel mention for critical severity notifications
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleNotificationSetting('mentionOnCritical')}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        notificationSettings.mentionOnCritical
                          ? 'bg-aura-600'
                          : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          notificationSettings.mentionOnCritical ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                        Use Thread Replies
                      </p>
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Send status updates as thread replies to original message
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleNotificationSetting('threadReplies')}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        notificationSettings.threadReplies
                          ? 'bg-aura-600'
                          : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          notificationSettings.threadReplies ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900 dark:text-surface-100 text-sm">
                        Include Stack Traces
                      </p>
                      <p className="text-xs text-surface-500 dark:text-surface-400">
                        Include code snippets and stack traces in error notifications
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleNotificationSetting('includeStackTrace')}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 ${
                        notificationSettings.includeStackTrace
                          ? 'bg-aura-600'
                          : 'bg-surface-200 dark:bg-surface-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          notificationSettings.includeStackTrace ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              </section>

              {/* Connection Test */}
              <section>
                <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-surface-900 dark:text-surface-100">
                      Test Connection
                    </h3>
                    <button
                      onClick={testConnection}
                      disabled={testing || !isValidConfig()}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:bg-surface-400 dark:disabled:bg-surface-600 disabled:cursor-not-allowed transition-colors"
                    >
                      {testing ? (
                        <>
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          Testing...
                        </>
                      ) : (
                        <>
                          <LinkIcon className="h-4 w-4" />
                          Test
                        </>
                      )}
                    </button>
                  </div>

                  {testResult && (
                    <div
                      className={`flex items-center gap-3 p-3 rounded-lg ${
                        testResult.success
                          ? 'bg-olive-50 dark:bg-olive-900/20 text-olive-700 dark:text-olive-300'
                          : 'bg-critical-50 dark:bg-critical-900/20 text-critical-700 dark:text-critical-300'
                      }`}
                    >
                      {testResult.success ? (
                        <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
                      ) : (
                        <ExclamationCircleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400" />
                      )}
                      <div>
                        <p className="font-medium">{testResult.message}</p>
                        {testResult.latency_ms && (
                          <p className="text-xs opacity-75">Latency: {testResult.latency_ms}ms</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 flex items-center justify-between bg-surface-50 dark:bg-surface-800">
          <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
            <InformationCircleIcon className="h-4 w-4" />
            <span>Credentials are encrypted at rest</span>
          </div>
          <div className="flex items-center gap-3">
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
                  Save Configuration
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
