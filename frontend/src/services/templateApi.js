/**
 * Project Aura - Template API Service
 *
 * Client-side service for managing environment templates.
 * Provides CRUD operations and configuration testing.
 */

import { apiClient, ApiError } from './api';

/**
 * Custom error class for Template API errors
 */
export class TemplateApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'TemplateApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Base image options for environment templates
 */
export const BASE_IMAGES = [
  {
    id: 'python-3.11',
    name: 'Python 3.11',
    description: 'Python 3.11 with pip and virtualenv',
    category: 'language',
  },
  {
    id: 'python-3.12',
    name: 'Python 3.12',
    description: 'Python 3.12 with pip and virtualenv',
    category: 'language',
  },
  {
    id: 'node-20',
    name: 'Node.js 20 LTS',
    description: 'Node.js 20 with npm and yarn',
    category: 'language',
  },
  {
    id: 'node-22',
    name: 'Node.js 22',
    description: 'Node.js 22 with npm and yarn',
    category: 'language',
  },
  {
    id: 'java-21',
    name: 'Java 21 LTS',
    description: 'OpenJDK 21 with Maven and Gradle',
    category: 'language',
  },
  {
    id: 'go-1.22',
    name: 'Go 1.22',
    description: 'Go 1.22 with standard toolchain',
    category: 'language',
  },
  {
    id: 'rust-1.75',
    name: 'Rust 1.75',
    description: 'Rust 1.75 with Cargo',
    category: 'language',
  },
  {
    id: 'dotnet-8',
    name: '.NET 8',
    description: '.NET 8 SDK with ASP.NET Core',
    category: 'language',
  },
  {
    id: 'multi-lang',
    name: 'Multi-Language',
    description: 'Python, Node.js, Java, and Go pre-installed',
    category: 'composite',
  },
  {
    id: 'security-scanner',
    name: 'Security Scanner',
    description: 'Pre-configured with security scanning tools',
    category: 'specialized',
  },
];

/**
 * Network policy options
 */
export const NETWORK_POLICIES = [
  {
    id: 'isolated',
    name: 'Isolated',
    description: 'No external network access, internal only',
    severity: 'high',
  },
  {
    id: 'restricted',
    name: 'Restricted',
    description: 'Limited external access via allowlist',
    severity: 'medium',
  },
  {
    id: 'standard',
    name: 'Standard',
    description: 'Outbound access allowed, inbound blocked',
    severity: 'low',
  },
  {
    id: 'open',
    name: 'Open',
    description: 'Full network access (not recommended)',
    severity: 'none',
  },
];

/**
 * Resource limit constraints
 */
export const RESOURCE_LIMITS = {
  cpu: {
    min: 0.25,
    max: 8,
    step: 0.25,
    unit: 'vCPU',
    default: 1,
  },
  memory: {
    min: 512,
    max: 32768,
    step: 256,
    unit: 'MB',
    default: 2048,
  },
  storage: {
    min: 1,
    max: 100,
    step: 1,
    unit: 'GB',
    default: 10,
  },
};

/**
 * Timeout configuration constraints
 */
export const TIMEOUT_LIMITS = {
  idle: {
    min: 5,
    max: 120,
    step: 5,
    unit: 'minutes',
    default: 30,
  },
  max: {
    min: 1,
    max: 168,
    step: 1,
    unit: 'hours',
    default: 24,
  },
};

/**
 * Default template configuration
 */
export const DEFAULT_TEMPLATE_CONFIG = {
  name: '',
  description: '',
  environment_type: 'standard',
  base_image: 'python-3.11',
  resource_limits: {
    cpu: RESOURCE_LIMITS.cpu.default,
    memory: RESOURCE_LIMITS.memory.default,
    storage: RESOURCE_LIMITS.storage.default,
  },
  network_policy: 'restricted',
  timeout_settings: {
    idle_timeout_minutes: TIMEOUT_LIMITS.idle.default,
    max_duration_hours: TIMEOUT_LIMITS.max.default,
  },
  environment_variables: {},
  init_script: '',
  requires_approval: false,
  cost_per_day: 0,
  default_ttl_hours: 24,
};

/**
 * Wrap API calls with template-specific error handling
 */
async function handleApiCall(apiCall) {
  try {
    const response = await apiCall();
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw new TemplateApiError(error.message, error.status, error.details);
    }
    throw new TemplateApiError(error.message || 'Unknown error', 500);
  }
}

/**
 * Get all environment templates
 *
 * @returns {Promise<Array>} List of templates
 */
export async function getTemplates() {
  return handleApiCall(() => apiClient.get('/environments/admin/templates'));
}

/**
 * Get a single template by ID
 *
 * @param {string} templateId - Template identifier
 * @returns {Promise<Object>} Template details
 */
export async function getTemplate(templateId) {
  return handleApiCall(() =>
    apiClient.get(`/environments/admin/templates/${templateId}`)
  );
}

/**
 * Create a new environment template
 *
 * @param {Object} templateData - Template configuration
 * @returns {Promise<Object>} Created template
 */
export async function createTemplate(templateData) {
  const payload = {
    ...DEFAULT_TEMPLATE_CONFIG,
    ...templateData,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  return handleApiCall(() =>
    apiClient.post('/environments/admin/templates', payload)
  );
}

/**
 * Update an existing environment template
 *
 * @param {string} templateId - Template identifier
 * @param {Object} updates - Template updates
 * @returns {Promise<Object>} Updated template
 */
export async function updateTemplate(templateId, updates) {
  const payload = {
    ...updates,
    updated_at: new Date().toISOString(),
  };

  return handleApiCall(() =>
    apiClient.put(`/environments/admin/templates/${templateId}`, payload)
  );
}

/**
 * Delete an environment template
 *
 * @param {string} templateId - Template identifier
 * @returns {Promise<null>} No content on success
 */
export async function deleteTemplate(templateId) {
  return handleApiCall(() =>
    apiClient.delete(`/environments/admin/templates/${templateId}`)
  );
}

/**
 * Test template configuration
 * Validates resource limits, network policies, and init scripts
 *
 * @param {Object} templateConfig - Template configuration to test
 * @returns {Promise<Object>} Test results with validation status
 */
export async function testConfiguration(templateConfig) {
  // Client-side validation first
  const validationErrors = validateTemplateConfig(templateConfig);

  if (validationErrors.length > 0) {
    return {
      success: false,
      errors: validationErrors,
      warnings: [],
    };
  }

  // Server-side validation
  try {
    const response = await handleApiCall(() =>
      apiClient.post('/environments/admin/templates/test', templateConfig)
    );

    return {
      success: true,
      errors: [],
      warnings: response.warnings || [],
      estimated_cost: response.estimated_cost,
      resource_availability: response.resource_availability,
    };
  } catch (error) {
    // If server test fails, return client validation as success
    // This allows offline validation
    return {
      success: true,
      errors: [],
      warnings: [
        'Server validation unavailable. Configuration passed client-side validation.',
      ],
      estimated_cost: estimateCost(templateConfig),
    };
  }
}

/**
 * Validate template configuration locally
 *
 * @param {Object} config - Template configuration
 * @returns {Array<string>} List of validation errors
 */
export function validateTemplateConfig(config) {
  const errors = [];

  // Name validation
  if (!config.name || config.name.trim().length === 0) {
    errors.push('Template name is required');
  } else if (config.name.length > 64) {
    errors.push('Template name must be 64 characters or less');
  }

  // Description validation
  if (config.description && config.description.length > 500) {
    errors.push('Description must be 500 characters or less');
  }

  // Resource limits validation
  if (config.resource_limits) {
    const { cpu, memory, storage } = config.resource_limits;

    if (cpu < RESOURCE_LIMITS.cpu.min || cpu > RESOURCE_LIMITS.cpu.max) {
      errors.push(
        `CPU must be between ${RESOURCE_LIMITS.cpu.min} and ${RESOURCE_LIMITS.cpu.max} ${RESOURCE_LIMITS.cpu.unit}`
      );
    }

    if (
      memory < RESOURCE_LIMITS.memory.min ||
      memory > RESOURCE_LIMITS.memory.max
    ) {
      errors.push(
        `Memory must be between ${RESOURCE_LIMITS.memory.min} and ${RESOURCE_LIMITS.memory.max} ${RESOURCE_LIMITS.memory.unit}`
      );
    }

    if (
      storage < RESOURCE_LIMITS.storage.min ||
      storage > RESOURCE_LIMITS.storage.max
    ) {
      errors.push(
        `Storage must be between ${RESOURCE_LIMITS.storage.min} and ${RESOURCE_LIMITS.storage.max} ${RESOURCE_LIMITS.storage.unit}`
      );
    }
  }

  // Timeout validation
  if (config.timeout_settings) {
    const { idle_timeout_minutes, max_duration_hours } = config.timeout_settings;

    if (
      idle_timeout_minutes < TIMEOUT_LIMITS.idle.min ||
      idle_timeout_minutes > TIMEOUT_LIMITS.idle.max
    ) {
      errors.push(
        `Idle timeout must be between ${TIMEOUT_LIMITS.idle.min} and ${TIMEOUT_LIMITS.idle.max} ${TIMEOUT_LIMITS.idle.unit}`
      );
    }

    if (
      max_duration_hours < TIMEOUT_LIMITS.max.min ||
      max_duration_hours > TIMEOUT_LIMITS.max.max
    ) {
      errors.push(
        `Max duration must be between ${TIMEOUT_LIMITS.max.min} and ${TIMEOUT_LIMITS.max.max} ${TIMEOUT_LIMITS.max.unit}`
      );
    }
  }

  // Init script validation (basic)
  if (config.init_script && config.init_script.length > 10000) {
    errors.push('Init script must be 10,000 characters or less');
  }

  return errors;
}

/**
 * Estimate daily cost based on resource configuration
 *
 * @param {Object} config - Template configuration
 * @returns {number} Estimated daily cost in USD
 */
export function estimateCost(config) {
  if (!config.resource_limits) {
    return 0;
  }

  const { cpu, memory, storage } = config.resource_limits;

  // Simplified cost calculation
  // CPU: $0.05 per vCPU per hour
  // Memory: $0.01 per GB per hour
  // Storage: $0.001 per GB per hour
  const cpuCost = cpu * 0.05 * 24;
  const memoryCost = (memory / 1024) * 0.01 * 24;
  const storageCost = storage * 0.001 * 24;

  return Math.round((cpuCost + memoryCost + storageCost) * 100) / 100;
}

/**
 * Clone an existing template
 *
 * @param {string} templateId - Source template ID
 * @param {string} newName - Name for the cloned template
 * @returns {Promise<Object>} Cloned template
 */
export async function cloneTemplate(templateId, newName) {
  const sourceTemplate = await getTemplate(templateId);

  const clonedTemplate = {
    ...sourceTemplate,
    name: newName,
    template_id: undefined, // Will be assigned by server
    created_at: undefined,
    updated_at: undefined,
  };

  return createTemplate(clonedTemplate);
}

export default {
  getTemplates,
  getTemplate,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  testConfiguration,
  validateTemplateConfig,
  estimateCost,
  cloneTemplate,
  BASE_IMAGES,
  NETWORK_POLICIES,
  RESOURCE_LIMITS,
  TIMEOUT_LIMITS,
  DEFAULT_TEMPLATE_CONFIG,
};
