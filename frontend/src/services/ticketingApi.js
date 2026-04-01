/**
 * Project Aura - Ticketing API Service
 *
 * API client for support ticketing configuration and operations.
 * See ADR-046 for architecture details.
 */

import { apiClient } from './api';

// Base URL for ticketing endpoints
const TICKETING_BASE = '/api/v1/ticketing';

/**
 * Provider metadata for UI display
 */
export const TICKETING_PROVIDERS = {
  github: {
    id: 'github',
    name: 'GitHub Issues',
    description: 'Free, open-source issue tracking built into GitHub',
    icon: 'github',
    isImplemented: true,
    configFields: [
      { name: 'repository', label: 'Repository', type: 'text', placeholder: 'owner/repo', required: true },
      { name: 'token', label: 'Personal Access Token', type: 'password', required: true, helpText: 'Requires issues:write scope' },
      { name: 'default_labels', label: 'Default Labels', type: 'tags', required: false },
    ],
  },
  zendesk: {
    id: 'zendesk',
    name: 'Zendesk',
    description: 'Enterprise customer service platform',
    icon: 'zendesk',
    isImplemented: false,
    configFields: [
      { name: 'subdomain', label: 'Subdomain', type: 'text', placeholder: 'yourcompany', required: true },
      { name: 'email', label: 'Agent Email', type: 'email', required: true },
      { name: 'api_token', label: 'API Token', type: 'password', required: true },
    ],
  },
  linear: {
    id: 'linear',
    name: 'Linear',
    description: 'Modern issue tracking for engineering teams',
    icon: 'linear',
    isImplemented: false,
    configFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'team_id', label: 'Team ID', type: 'text', required: true },
      { name: 'project_id', label: 'Default Project ID', type: 'text', required: false },
    ],
  },
  servicenow: {
    id: 'servicenow',
    name: 'ServiceNow',
    description: 'Enterprise IT service management',
    icon: 'servicenow',
    isImplemented: false,
    configFields: [
      { name: 'instance_url', label: 'Instance URL', type: 'url', placeholder: 'https://dev12345.service-now.com', required: true },
      { name: 'username', label: 'Username', type: 'text', required: true },
      { name: 'password', label: 'Password', type: 'password', required: true },
      { name: 'table', label: 'Table', type: 'select', options: ['incident', 'sc_request', 'problem'], required: true },
    ],
  },
};

/**
 * Default ticketing configuration
 */
export const DEFAULT_TICKETING_CONFIG = {
  provider: null,
  enabled: false,
  config: {},
  default_labels: ['support', 'aura'],
  auto_assign: false,
};

/**
 * Get the current ticketing configuration
 * @returns {Promise<Object>} Current ticketing configuration
 */
export async function getTicketingConfig() {
  try {
    const response = await apiClient.get(`${TICKETING_BASE}/config`);
    return response.data;
  } catch (error) {
    if (error.response?.status === 404) {
      return DEFAULT_TICKETING_CONFIG;
    }
    throw error;
  }
}

/**
 * Save ticketing configuration
 * @param {Object} config - Ticketing configuration to save
 * @returns {Promise<Object>} Saved configuration
 */
export async function saveTicketingConfig(config) {
  const response = await apiClient.post(`${TICKETING_BASE}/config`, config);
  return response.data;
}

/**
 * Update ticketing configuration
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated configuration
 */
export async function updateTicketingConfig(updates) {
  const response = await apiClient.patch(`${TICKETING_BASE}/config`, updates);
  return response.data;
}

/**
 * Test the ticketing connection
 * @param {Object} config - Configuration to test
 * @returns {Promise<Object>} Test result with success/failure
 */
export async function testTicketingConnection(config) {
  const response = await apiClient.post(`${TICKETING_BASE}/test-connection`, config);
  return response.data;
}

/**
 * Get available ticketing providers
 * @returns {Promise<Object>} Provider metadata
 */
export async function getTicketingProviders() {
  try {
    const response = await apiClient.get(`${TICKETING_BASE}/providers`);
    return response.data;
  } catch {
    // Return local metadata if API unavailable
    return TICKETING_PROVIDERS;
  }
}

/**
 * Create a support ticket
 * @param {Object} ticket - Ticket data
 * @returns {Promise<Object>} Created ticket
 */
export async function createTicket(ticket) {
  const response = await apiClient.post(`${TICKETING_BASE}/tickets`, ticket);
  return response.data;
}

/**
 * Get a ticket by ID
 * @param {string} ticketId - Ticket ID
 * @returns {Promise<Object>} Ticket data
 */
export async function getTicket(ticketId) {
  const response = await apiClient.get(`${TICKETING_BASE}/tickets/${ticketId}`);
  return response.data;
}

/**
 * Update a ticket
 * @param {string} ticketId - Ticket ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated ticket
 */
export async function updateTicket(ticketId, updates) {
  const response = await apiClient.patch(`${TICKETING_BASE}/tickets/${ticketId}`, updates);
  return response.data;
}

/**
 * List tickets with optional filters
 * @param {Object} filters - Filter criteria
 * @returns {Promise<Array>} List of tickets
 */
export async function listTickets(filters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.append('status', filters.status);
  if (filters.priority) params.append('priority', filters.priority);
  if (filters.assignee) params.append('assignee', filters.assignee);
  if (filters.limit) params.append('limit', filters.limit);
  if (filters.offset) params.append('offset', filters.offset);

  const response = await apiClient.get(`${TICKETING_BASE}/tickets?${params.toString()}`);
  return response.data;
}

/**
 * Add a comment to a ticket
 * @param {string} ticketId - Ticket ID
 * @param {string} comment - Comment text
 * @param {boolean} isInternal - Is internal note
 * @returns {Promise<Object>} Updated ticket
 */
export async function addTicketComment(ticketId, comment, isInternal = false) {
  const response = await apiClient.post(`${TICKETING_BASE}/tickets/${ticketId}/comments`, {
    comment,
    is_internal: isInternal,
  });
  return response.data;
}

/**
 * Close a ticket
 * @param {string} ticketId - Ticket ID
 * @param {string} resolution - Resolution summary
 * @returns {Promise<Object>} Closed ticket
 */
export async function closeTicket(ticketId, resolution = null) {
  const response = await apiClient.post(`${TICKETING_BASE}/tickets/${ticketId}/close`, {
    resolution,
  });
  return response.data;
}

/**
 * Reopen a ticket
 * @param {string} ticketId - Ticket ID
 * @param {string} reason - Reason for reopening
 * @returns {Promise<Object>} Reopened ticket
 */
export async function reopenTicket(ticketId, reason = null) {
  const response = await apiClient.post(`${TICKETING_BASE}/tickets/${ticketId}/reopen`, {
    reason,
  });
  return response.data;
}

export default {
  getTicketingConfig,
  saveTicketingConfig,
  updateTicketingConfig,
  testTicketingConnection,
  getTicketingProviders,
  createTicket,
  getTicket,
  updateTicket,
  listTickets,
  addTicketComment,
  closeTicket,
  reopenTicket,
  TICKETING_PROVIDERS,
  DEFAULT_TICKETING_CONFIG,
};
