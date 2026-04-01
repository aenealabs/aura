/**
 * Environment Validator API Service (ADR-062)
 *
 * Client-side API for environment validation, drift detection,
 * and baseline management.
 */

import api from './api';

const BASE_PATH = '/api/v1/environment';

/**
 * Validate a Kubernetes manifest
 * @param {string} manifest - YAML manifest content
 * @param {string} targetEnv - Target environment (dev, qa, staging, prod)
 * @param {Object} options - Validation options
 * @param {boolean} options.strict - Treat warnings as errors
 * @param {boolean} options.saveBaseline - Save as baseline if valid
 * @returns {Promise<Object>} Validation result
 */
export async function validateManifest(manifest, targetEnv, options = {}) {
  const response = await api.post(`${BASE_PATH}/validate`, {
    manifest,
    target_env: targetEnv,
    strict: options.strict || false,
    save_baseline: options.saveBaseline || false,
  });
  return response.data;
}

/**
 * Detect drift against baseline
 * @param {string} manifest - Current manifest YAML
 * @param {string} env - Environment to check
 * @returns {Promise<Object>} Drift detection result
 */
export async function detectDrift(manifest, env) {
  const response = await api.post(`${BASE_PATH}/drift/detect`, { manifest }, {
    params: { env },
  });
  return response.data;
}

/**
 * Get current drift status for an environment
 * @param {string} env - Environment name
 * @returns {Promise<Object>} Drift status
 */
export async function getDriftStatus(env) {
  const response = await api.get(`${BASE_PATH}/drift`, {
    params: { env },
  });
  return response.data;
}

/**
 * Get environment registry
 * @returns {Promise<Object>} Environment configurations
 */
export async function getEnvironmentRegistry() {
  const response = await api.get(`${BASE_PATH}/registry`);
  return response.data;
}

/**
 * Get validation history
 * @param {string} env - Environment name
 * @param {Object} options - Pagination options
 * @param {number} options.limit - Maximum results
 * @param {number} options.offset - Pagination offset
 * @returns {Promise<Object>} Validation history
 */
export async function getValidationHistory(env, options = {}) {
  const response = await api.get(`${BASE_PATH}/validation-history`, {
    params: {
      env,
      limit: options.limit || 50,
      offset: options.offset || 0,
    },
  });
  return response.data;
}

/**
 * List baselines for an environment
 * @param {string} env - Environment name
 * @param {string} resourceType - Optional resource type filter
 * @returns {Promise<Object>} List of baselines
 */
export async function listBaselines(env, resourceType = null) {
  const params = { env };
  if (resourceType) {
    params.resource_type = resourceType;
  }
  const response = await api.get(`${BASE_PATH}/baselines`, { params });
  return response.data;
}

/**
 * Save a baseline
 * @param {string} manifest - Validated manifest YAML
 * @param {string} env - Environment name
 * @param {string} createdBy - Creator identifier
 * @returns {Promise<Object>} Saved baseline info
 */
export async function saveBaseline(manifest, env, createdBy = 'dashboard') {
  const response = await api.post(`${BASE_PATH}/baselines`, {
    manifest,
    created_by: createdBy,
  }, {
    params: { env },
  });
  return response.data;
}

/**
 * Delete a baseline
 * @param {string} env - Environment name
 * @param {string} resourceType - Resource type
 * @param {string} namespace - Resource namespace
 * @param {string} resourceName - Resource name
 * @returns {Promise<Object>} Deletion result
 */
export async function deleteBaseline(env, resourceType, namespace, resourceName) {
  const response = await api.delete(
    `${BASE_PATH}/baselines/${resourceType}/${namespace}/${resourceName}`,
    { params: { env } }
  );
  return response.data;
}

/**
 * Get environment validator health
 * @param {string} env - Environment name
 * @returns {Promise<Object>} Health status
 */
export async function getHealth(env = 'dev') {
  const response = await api.get(`${BASE_PATH}/health`, {
    params: { env },
  });
  return response.data;
}

// Severity levels for UI
export const Severity = {
  CRITICAL: 'critical',
  WARNING: 'warning',
  INFO: 'info',
};

// Environment names (staging removed - not in current infrastructure)
export const Environments = ['dev', 'qa', 'prod'];

// Severity colors for UI
export const SeverityColors = {
  critical: {
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    text: 'text-critical-700 dark:text-critical-400',
    border: 'border-critical-200 dark:border-critical-800',
    dot: 'bg-critical-500',
  },
  warning: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-700 dark:text-warning-400',
    border: 'border-warning-200 dark:border-warning-800',
    dot: 'bg-warning-500',
  },
  info: {
    bg: 'bg-aura-100 dark:bg-aura-900/30',
    text: 'text-aura-700 dark:text-aura-400',
    border: 'border-aura-200 dark:border-aura-800',
    dot: 'bg-aura-500',
  },
};

// Validation result colors
export const ResultColors = {
  pass: {
    bg: 'bg-olive-100 dark:bg-olive-900/30',
    text: 'text-olive-700 dark:text-olive-400',
    icon: 'text-olive-500',
  },
  fail: {
    bg: 'bg-critical-100 dark:bg-critical-900/30',
    text: 'text-critical-700 dark:text-critical-400',
    icon: 'text-critical-500',
  },
  warn: {
    bg: 'bg-warning-100 dark:bg-warning-900/30',
    text: 'text-warning-700 dark:text-warning-400',
    icon: 'text-warning-500',
  },
};
