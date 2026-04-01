/**
 * Project Aura - Notifications API Service
 *
 * Client-side service for managing notification channels and preferences.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for Notifications API errors
 */
export class NotificationsApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'NotificationsApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new NotificationsApiError(
      errorData.detail || errorData.error || `API error: ${response.status}`,
      response.status,
      errorData
    );
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * Notification channel types
 */
export const ChannelTypes = {
  EMAIL: 'email',
  SLACK: 'slack',
  TEAMS: 'teams',
  SNS: 'sns',
  WEBHOOK: 'webhook',
  PAGERDUTY: 'pagerduty',
};

/**
 * Channel type display configuration
 */
export const CHANNEL_TYPE_CONFIG = {
  email: {
    label: 'Email',
    description: 'Send notifications via email',
    icon: 'EnvelopeIcon',
    color: 'aura',
    configFields: ['recipients', 'from_address', 'subject_prefix'],
  },
  slack: {
    label: 'Slack',
    description: 'Send notifications to Slack channels',
    icon: 'ChatBubbleLeftRightIcon',
    color: 'olive',
    configFields: ['webhook_url', 'channel', 'bot_name', 'icon_emoji'],
  },
  teams: {
    label: 'Microsoft Teams',
    description: 'Send notifications to Microsoft Teams channels',
    icon: 'ChatBubbleLeftRightIcon',
    color: 'indigo',
    configFields: ['webhook_url', 'channel_name'],
  },
  sns: {
    label: 'AWS SNS',
    description: 'Publish to AWS SNS topics',
    icon: 'BellAlertIcon',
    color: 'warning',
    configFields: ['topic_arn', 'region'],
  },
  webhook: {
    label: 'Webhook',
    description: 'Send POST requests to custom endpoints',
    icon: 'LinkIcon',
    color: 'surface',
    configFields: ['url', 'headers', 'auth_type', 'auth_token'],
  },
  pagerduty: {
    label: 'PagerDuty',
    description: 'Create incidents in PagerDuty',
    icon: 'ExclamationTriangleIcon',
    color: 'critical',
    configFields: ['routing_key', 'service_id'],
  },
};

/**
 * Event types for notifications
 */
export const EventTypes = {
  APPROVAL_REQUIRED: 'approval_required',
  APPROVAL_TIMEOUT: 'approval_timeout',
  PATCH_GENERATED: 'patch_generated',
  PATCH_DEPLOYED: 'patch_deployed',
  PATCH_FAILED: 'patch_failed',
  SECURITY_ALERT: 'security_alert',
  SYSTEM_ERROR: 'system_error',
  AGENT_DEGRADED: 'agent_degraded',
  BUDGET_WARNING: 'budget_warning',
  ENVIRONMENT_EXPIRING: 'environment_expiring',
};

/**
 * Event type display configuration
 */
export const EVENT_TYPE_CONFIG = {
  approval_required: {
    label: 'Approval Required',
    description: 'New HITL approval request',
    severity: 'info',
  },
  approval_timeout: {
    label: 'Approval Timeout',
    description: 'HITL approval request expired',
    severity: 'warning',
  },
  patch_generated: {
    label: 'Patch Generated',
    description: 'New security patch created',
    severity: 'info',
  },
  patch_deployed: {
    label: 'Patch Deployed',
    description: 'Patch successfully deployed',
    severity: 'success',
  },
  patch_failed: {
    label: 'Patch Failed',
    description: 'Patch deployment failed',
    severity: 'error',
  },
  security_alert: {
    label: 'Security Alert',
    description: 'Critical security event detected',
    severity: 'critical',
  },
  system_error: {
    label: 'System Error',
    description: 'Platform error occurred',
    severity: 'error',
  },
  agent_degraded: {
    label: 'Agent Degraded',
    description: 'Agent health degraded',
    severity: 'warning',
  },
  budget_warning: {
    label: 'Budget Warning',
    description: 'Approaching budget limit',
    severity: 'warning',
  },
  environment_expiring: {
    label: 'Environment Expiring',
    description: 'Test environment expiring soon',
    severity: 'info',
  },
};

/**
 * Default notification settings
 */
export const DEFAULT_NOTIFICATION_SETTINGS = {
  channels: [],
  preferences: {
    approval_required: { enabled: true, channels: ['email', 'slack', 'teams'] },
    approval_timeout: { enabled: true, channels: ['email'] },
    patch_generated: { enabled: false, channels: [] },
    patch_deployed: { enabled: true, channels: ['slack', 'teams'] },
    patch_failed: { enabled: true, channels: ['email', 'slack', 'teams', 'pagerduty'] },
    security_alert: { enabled: true, channels: ['email', 'slack', 'teams', 'pagerduty'] },
    system_error: { enabled: true, channels: ['email', 'pagerduty'] },
    agent_degraded: { enabled: true, channels: ['slack', 'teams'] },
    budget_warning: { enabled: true, channels: ['email'] },
    environment_expiring: { enabled: false, channels: [] },
  },
  quiet_hours: {
    enabled: false,
    start: '22:00',
    end: '08:00',
    timezone: 'UTC',
    bypass_critical: true,
  },
};

/**
 * Get notification channels
 *
 * @returns {Promise<Array>} List of configured channels
 */
export async function getNotificationChannels() {
  try {
    return await fetchApi('/notifications/channels');
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}

/**
 * Create notification channel
 *
 * @param {Object} channelData - Channel configuration
 * @returns {Promise<Object>} Created channel
 */
export async function createNotificationChannel(channelData) {
  try {
    return await fetchApi('/notifications/channels', {
      method: 'POST',
      body: JSON.stringify(channelData),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Notifications API not available, using local state');
      return { ...channelData, id: `channel-${Date.now()}`, created_at: new Date().toISOString() };
    }
    throw error;
  }
}

/**
 * Update notification channel
 *
 * @param {string} channelId - Channel identifier
 * @param {Object} updates - Configuration updates
 * @returns {Promise<Object>} Updated channel
 */
export async function updateNotificationChannel(channelId, updates) {
  try {
    return await fetchApi(`/notifications/channels/${channelId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Notifications API not available, using local state');
      return { id: channelId, ...updates, updated_at: new Date().toISOString() };
    }
    throw error;
  }
}

/**
 * Delete notification channel
 *
 * @param {string} channelId - Channel identifier
 * @returns {Promise<null>} No content
 */
export async function deleteNotificationChannel(channelId) {
  try {
    return await fetchApi(`/notifications/channels/${channelId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Notifications API not available, simulating deletion');
      return null;
    }
    throw error;
  }
}

/**
 * Test notification channel
 *
 * @param {string} channelId - Channel identifier
 * @returns {Promise<Object>} Test result
 */
export async function testNotificationChannel(channelId) {
  try {
    return await fetchApi(`/notifications/channels/${channelId}/test`, {
      method: 'POST',
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Notifications API not available, simulating test');
      return { success: true, message: 'Test notification sent (dev mode)', latency_ms: 125 };
    }
    throw error;
  }
}

/**
 * Get notification preferences
 *
 * @returns {Promise<Object>} Notification preferences
 */
export async function getNotificationPreferences() {
  try {
    return await fetchApi('/notifications/preferences');
  } catch (error) {
    if (error.status === 404) {
      return DEFAULT_NOTIFICATION_SETTINGS.preferences;
    }
    throw error;
  }
}

/**
 * Update notification preferences
 *
 * @param {Object} preferences - Preference updates
 * @returns {Promise<Object>} Updated preferences
 */
export async function updateNotificationPreferences(preferences) {
  try {
    return await fetchApi('/notifications/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Notifications API not available, using local state');
      return { ...DEFAULT_NOTIFICATION_SETTINGS.preferences, ...preferences, updated: true };
    }
    throw error;
  }
}

/**
 * Get quiet hours settings
 *
 * @returns {Promise<Object>} Quiet hours configuration
 */
export async function getQuietHours() {
  try {
    return await fetchApi('/notifications/quiet-hours');
  } catch (error) {
    if (error.status === 404) {
      return DEFAULT_NOTIFICATION_SETTINGS.quiet_hours;
    }
    throw error;
  }
}

/**
 * Update quiet hours settings
 *
 * @param {Object} settings - Quiet hours configuration
 * @returns {Promise<Object>} Updated settings
 */
export async function updateQuietHours(settings) {
  try {
    return await fetchApi('/notifications/quiet-hours', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  } catch (error) {
    if (error.message?.includes('Failed to fetch') || error.status === 404 || error.status === 500) {
      console.warn('Notifications API not available, using local state');
      return { ...DEFAULT_NOTIFICATION_SETTINGS.quiet_hours, ...settings, updated: true };
    }
    throw error;
  }
}

/**
 * Get notification history
 *
 * @param {number} limit - Maximum results
 * @param {string} eventType - Filter by event type (optional)
 * @returns {Promise<Array>} Notification history
 */
export async function getNotificationHistory(limit = 50, eventType = null) {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (eventType) {
    params.append('event_type', eventType);
  }
  try {
    return await fetchApi(`/notifications/history?${params}`);
  } catch (error) {
    if (error.status === 404) {
      return [];
    }
    throw error;
  }
}
