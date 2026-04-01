/**
 * Project Aura - Base API Client
 *
 * Shared API client for all service modules.
 */

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

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
    let errorDetails = null;
    try {
      errorDetails = await response.json();
    } catch {
      // Response body is not JSON
    }
    throw new ApiError(
      errorDetails?.message || `Request failed with status ${response.status}`,
      response.status,
      errorDetails
    );
  }

  // Handle empty responses
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

/**
 * API client with axios-like interface
 */
export const apiClient = {
  /**
   * GET request
   * @param {string} url - Endpoint URL
   * @param {Object} config - Optional config
   * @returns {Promise<{data: any}>}
   */
  async get(url, config = {}) {
    const data = await fetchApi(url, { method: 'GET', ...config });
    return { data };
  },

  /**
   * POST request
   * @param {string} url - Endpoint URL
   * @param {Object} body - Request body
   * @param {Object} config - Optional config
   * @returns {Promise<{data: any}>}
   */
  async post(url, body = {}, config = {}) {
    const data = await fetchApi(url, {
      method: 'POST',
      body: JSON.stringify(body),
      ...config,
    });
    return { data };
  },

  /**
   * PUT request
   * @param {string} url - Endpoint URL
   * @param {Object} body - Request body
   * @param {Object} config - Optional config
   * @returns {Promise<{data: any}>}
   */
  async put(url, body = {}, config = {}) {
    const data = await fetchApi(url, {
      method: 'PUT',
      body: JSON.stringify(body),
      ...config,
    });
    return { data };
  },

  /**
   * PATCH request
   * @param {string} url - Endpoint URL
   * @param {Object} body - Request body
   * @param {Object} config - Optional config
   * @returns {Promise<{data: any}>}
   */
  async patch(url, body = {}, config = {}) {
    const data = await fetchApi(url, {
      method: 'PATCH',
      body: JSON.stringify(body),
      ...config,
    });
    return { data };
  },

  /**
   * DELETE request
   * @param {string} url - Endpoint URL
   * @param {Object} config - Optional config
   * @returns {Promise<{data: any}>}
   */
  async delete(url, config = {}) {
    const data = await fetchApi(url, { method: 'DELETE', ...config });
    return { data };
  },
};

export default apiClient;
