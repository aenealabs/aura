/**
 * Project Aura - Profile API Service
 *
 * API service for user profile management including:
 * - Personal information updates
 * - Password changes
 * - Notification preferences
 * - Session management
 * - API key management
 */

import { apiClient, ApiError } from './api';

// Default profile data for development
const DEFAULT_PROFILE = {
  id: 'usr_dev_123',
  email: 'dev@aenealabs.com',
  name: 'Developer',
  avatar_url: null,
  role: 'admin',
  department: 'Engineering',
  timezone: 'UTC',
  created_at: '2024-06-15T10:30:00Z',
  last_login: new Date().toISOString(),
};

const DEFAULT_NOTIFICATION_PREFERENCES = {
  email: {
    enabled: true,
    security_alerts: true,
    approval_requests: true,
    system_updates: true,
    weekly_digest: true,
  },
  in_app: {
    enabled: true,
    security_alerts: true,
    approval_requests: true,
    agent_updates: true,
    mentions: true,
  },
  slack: {
    enabled: false,
    webhook_url: '',
    channel: '',
    security_alerts: true,
    approval_requests: true,
  },
};

const DEFAULT_SESSIONS = [
  {
    id: 'sess_current',
    device: 'Chrome on macOS',
    ip_address: '192.168.1.100',
    location: 'San Francisco, CA',
    last_active: new Date().toISOString(),
    is_current: true,
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 'sess_mobile',
    device: 'Safari on iOS',
    ip_address: '10.0.0.50',
    location: 'San Francisco, CA',
    last_active: new Date(Date.now() - 7200000).toISOString(),
    is_current: false,
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

const DEFAULT_API_KEYS = [
  {
    id: 'key_prod_001',
    name: 'Production CI/CD',
    prefix: 'aura_prod_',
    last_used: new Date(Date.now() - 3600000).toISOString(),
    created_at: '2024-10-01T14:00:00Z',
    expires_at: '2025-10-01T14:00:00Z',
    scopes: ['read:agents', 'write:agents', 'read:approvals'],
  },
  {
    id: 'key_dev_002',
    name: 'Local Development',
    prefix: 'aura_dev_',
    last_used: new Date(Date.now() - 86400000).toISOString(),
    created_at: '2024-11-15T09:00:00Z',
    expires_at: null,
    scopes: ['read:*', 'write:*'],
  },
];

// Simulated delay for mock responses
const simulateDelay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Get current user profile
 */
export async function getProfile() {
  try {
    const { data } = await apiClient.get('/user/profile');
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // Return mock data for development
      await simulateDelay();
      // Load avatar from localStorage if available
      const storedAvatar = localStorage.getItem('aura_user_avatar');
      return {
        ...DEFAULT_PROFILE,
        avatar_url: storedAvatar || null,
      };
    }
    throw error;
  }
}

/**
 * Update user profile information
 */
export async function updateProfile(updates) {
  try {
    const { data } = await apiClient.patch('/user/profile', updates);
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // Mock update for development
      await simulateDelay(500);
      return { ...DEFAULT_PROFILE, ...updates };
    }
    throw error;
  }
}

/**
 * Upload user avatar
 */
export async function uploadAvatar(file) {
  const apiUrl = import.meta.env.VITE_API_URL;

  // Dev mode: store avatar as base64 in localStorage
  if (!apiUrl || import.meta.env.DEV) {
    await simulateDelay(800);
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result;
        localStorage.setItem('aura_user_avatar', base64);
        resolve({
          avatar_url: base64,
          message: 'Avatar uploaded successfully',
        });
      };
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsDataURL(file);
    });
  }

  // Production: upload to API
  try {
    const formData = new FormData();
    formData.append('avatar', file);

    const response = await fetch(`${apiUrl}/user/avatar`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new ApiError('Failed to upload avatar', response.status);
    }

    return response.json();
  } catch (error) {
    throw error;
  }
}

/**
 * Delete user avatar
 */
export async function deleteAvatar() {
  const apiUrl = import.meta.env.VITE_API_URL;

  // Dev mode: remove from localStorage
  if (!apiUrl || import.meta.env.DEV) {
    await simulateDelay();
    localStorage.removeItem('aura_user_avatar');
    return { success: true };
  }

  // Production: delete via API
  try {
    await apiClient.delete('/user/avatar');
    return { success: true };
  } catch (error) {
    throw error;
  }
}

/**
 * Change user password
 */
export async function changePassword(currentPassword, newPassword) {
  try {
    const { data } = await apiClient.post('/user/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 400) {
        throw new ApiError('Current password is incorrect', 400);
      }
      if (error.status === 404) {
        // Mock password change for development
        await simulateDelay(500);
        return { success: true, message: 'Password changed successfully' };
      }
    }
    throw error;
  }
}

/**
 * Get notification preferences
 */
export async function getNotificationPreferences() {
  try {
    const { data } = await apiClient.get('/user/notifications/preferences');
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay();
      return DEFAULT_NOTIFICATION_PREFERENCES;
    }
    throw error;
  }
}

/**
 * Update notification preferences
 */
export async function updateNotificationPreferences(preferences) {
  try {
    const { data } = await apiClient.put('/user/notifications/preferences', preferences);
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay(500);
      return { ...DEFAULT_NOTIFICATION_PREFERENCES, ...preferences };
    }
    throw error;
  }
}

/**
 * Get active sessions
 */
export async function getSessions() {
  try {
    const { data } = await apiClient.get('/user/sessions');
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay();
      return DEFAULT_SESSIONS;
    }
    throw error;
  }
}

/**
 * Revoke a specific session
 */
export async function revokeSession(sessionId) {
  try {
    await apiClient.delete(`/user/sessions/${sessionId}`);
    return { success: true };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay();
      return { success: true };
    }
    throw error;
  }
}

/**
 * Revoke all sessions except current
 */
export async function revokeAllSessions() {
  try {
    await apiClient.post('/user/sessions/revoke-all');
    return { success: true };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay();
      return { success: true };
    }
    throw error;
  }
}

/**
 * Get API keys
 */
export async function getApiKeys() {
  try {
    const { data } = await apiClient.get('/user/api-keys');
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay();
      return DEFAULT_API_KEYS;
    }
    throw error;
  }
}

/**
 * Create new API key
 */
export async function createApiKey(name, scopes, expiresAt = null) {
  try {
    const { data } = await apiClient.post('/user/api-keys', {
      name,
      scopes,
      expires_at: expiresAt,
    });
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // Mock API key creation for development
      await simulateDelay(500);
      const newKey = {
        id: `key_${Date.now()}`,
        name,
        prefix: 'aura_',
        key: `aura_${Math.random().toString(36).substring(2, 15)}_${Math.random().toString(36).substring(2, 15)}`,
        created_at: new Date().toISOString(),
        expires_at: expiresAt,
        scopes,
      };
      return newKey;
    }
    throw error;
  }
}

/**
 * Delete API key
 */
export async function deleteApiKey(keyId) {
  try {
    await apiClient.delete(`/user/api-keys/${keyId}`);
    return { success: true };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await simulateDelay();
      return { success: true };
    }
    throw error;
  }
}

/**
 * Available API scopes
 */
export const API_SCOPES = [
  { id: 'read:agents', label: 'Read Agents', description: 'View agent configurations and status' },
  { id: 'write:agents', label: 'Write Agents', description: 'Create and modify agents' },
  { id: 'read:approvals', label: 'Read Approvals', description: 'View approval requests' },
  { id: 'write:approvals', label: 'Write Approvals', description: 'Approve or reject requests' },
  { id: 'read:repositories', label: 'Read Repositories', description: 'View connected repositories' },
  { id: 'write:repositories', label: 'Write Repositories', description: 'Manage repository connections' },
  { id: 'read:security', label: 'Read Security', description: 'View security alerts and reports' },
  { id: 'read:*', label: 'Read All', description: 'Read access to all resources' },
  { id: 'write:*', label: 'Write All', description: 'Write access to all resources' },
];

export default {
  getProfile,
  updateProfile,
  uploadAvatar,
  deleteAvatar,
  changePassword,
  getNotificationPreferences,
  updateNotificationPreferences,
  getSessions,
  revokeSession,
  revokeAllSessions,
  getApiKeys,
  createApiKey,
  deleteApiKey,
  API_SCOPES,
};
