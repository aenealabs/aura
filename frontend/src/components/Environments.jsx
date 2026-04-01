import { useState, useEffect, useCallback } from 'react';
import {
  PlusIcon,
  BeakerIcon,
  ClockIcon,
  CpuChipIcon,
  TrashIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ServerStackIcon,
  CurrencyDollarIcon,
  DocumentDuplicateIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { PageSkeleton } from './ui/LoadingSkeleton';
import EnvironmentDashboard from './EnvironmentDashboard';
import { useToast } from './ui/Toast';
import {
  listEnvironments,
  createEnvironment,
  terminateEnvironment,
  extendEnvironmentTTL,
  getTemplates,
  getUserQuota,
  EnvironmentsApiError,
} from '../services/environmentsApi';

// Status styles following design system
const STATUS_STYLES = {
  active: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: CheckCircleIcon,
    label: 'Active',
    color: 'olive',
  },
  pending_approval: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: ClockIcon,
    label: 'Pending Approval',
    color: 'warning',
  },
  provisioning: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: ArrowPathIcon,
    label: 'Provisioning',
    color: 'aura',
  },
  expiring: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: ExclamationTriangleIcon,
    label: 'Expiring Soon',
    color: 'warning',
  },
  terminating: {
    badge: 'bg-surface-100 text-surface-700 dark:bg-surface-700/30 dark:text-surface-400',
    icon: TrashIcon,
    label: 'Terminating',
    color: 'surface',
  },
  terminated: {
    badge: 'bg-surface-100 text-surface-500 dark:bg-surface-800/30 dark:text-surface-500',
    icon: XCircleIcon,
    label: 'Terminated',
    color: 'surface',
  },
  failed: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: XCircleIcon,
    label: 'Failed',
    color: 'critical',
  },
};

// Environment type styles
const TYPE_STYLES = {
  quick: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    label: 'Quick',
    description: 'EKS Namespace (4h)',
  },
  standard: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    label: 'Standard',
    description: 'Service Catalog (24h)',
  },
  extended: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    label: 'Extended',
    description: 'Service Catalog (7d)',
  },
  compliance: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    label: 'Compliance',
    description: 'Dedicated VPC (24h)',
  },
};

// Default quota used when API is unavailable
const DEFAULT_QUOTA = {
  user_id: 'unknown',
  concurrent_limit: 3,
  active_count: 0,
  available: 3,
  monthly_budget: 500.0,
  monthly_spent: 0,
  monthly_remaining: 500.0,
};

// Format time remaining
function formatTimeRemaining(expiresAt) {
  const now = new Date();
  const expires = new Date(expiresAt);
  const diff = expires - now;

  if (diff <= 0) return 'Expired';

  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }

  return `${hours}h ${minutes}m`;
}

// Format date
function _formatDate(dateString) {
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Environment Card Component
function EnvironmentCard({ environment, templates, onTerminate, onExtend, onSelect }) {
  const statusStyle = STATUS_STYLES[environment.status] || STATUS_STYLES.active;
  const typeStyle = TYPE_STYLES[environment.environment_type] || TYPE_STYLES.standard;
  const StatusIcon = statusStyle.icon;

  const isExpiringSoon = environment.status === 'expiring' ||
    (environment.status === 'active' && new Date(environment.expires_at) - new Date() < 2 * 60 * 60 * 1000);

  // Find template name from templates list
  const templateName = templates.find(t => t.template_id === environment.template_id)?.name || environment.template_id;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl border
        ${isExpiringSoon ? 'border-warning-300 dark:border-warning-700' : 'border-surface-200 dark:border-surface-700'}
        shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer
      `}
      onClick={() => onSelect(environment)}
    >
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 truncate">
              {environment.display_name}
            </h3>
            <p className="text-sm text-surface-500 dark:text-surface-400 font-mono truncate">
              {environment.environment_id}
            </p>
          </div>
          <div className="flex items-center gap-2 ml-2">
            <span className={`px-2 py-1 text-xs font-medium rounded-full ${typeStyle.badge}`}>
              {typeStyle.label}
            </span>
            <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusStyle.badge} flex items-center gap-1`}>
              <StatusIcon className="w-3 h-3" />
              {statusStyle.label}
            </span>
          </div>
        </div>

        {/* Template info */}
        <div className="flex items-center gap-4 text-sm text-surface-600 dark:text-surface-400 mb-3">
          <div className="flex items-center gap-1">
            <DocumentDuplicateIcon className="w-4 h-4" />
            <span>{templateName}</span>
          </div>
          <div className="flex items-center gap-1">
            <CurrencyDollarIcon className="w-4 h-4" />
            <span>${environment.cost_estimate_daily.toFixed(2)}/day</span>
          </div>
        </div>

        {/* DNS and timing */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-1 text-surface-500 dark:text-surface-400">
            <GlobeAltIcon className="w-4 h-4" />
            <span className="font-mono text-xs">{environment.dns_name}</span>
          </div>
          <div className={`flex items-center gap-1 ${isExpiringSoon ? 'text-warning-600 dark:text-warning-400 font-medium' : 'text-surface-500 dark:text-surface-400'}`}>
            <ClockIcon className="w-4 h-4" />
            <span>{formatTimeRemaining(environment.expires_at)}</span>
          </div>
        </div>
      </div>

      {/* Actions */}
      {(environment.status === 'active' || environment.status === 'expiring') && (
        <div className="px-4 py-3 border-t border-surface-100 dark:border-surface-700/50 flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); onExtend(environment); }}
            className="flex-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-aura-50 text-aura-600 hover:bg-aura-100 dark:bg-aura-900/20 dark:text-aura-400 dark:hover:bg-aura-900/30 transition-colors"
          >
            Extend TTL
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onTerminate(environment); }}
            className="flex-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-critical-50 text-critical-600 hover:bg-critical-100 dark:bg-critical-900/20 dark:text-critical-400 dark:hover:bg-critical-900/30 transition-colors"
          >
            Terminate
          </button>
        </div>
      )}
    </div>
  );
}

// Template Card Component
function _TemplateCard({ template, onSelect, disabled }) {
  const typeStyle = TYPE_STYLES[template.environment_type] || TYPE_STYLES.standard;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)]
        shadow-sm hover:shadow-md transition-all duration-200
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-aura-300 dark:hover:border-aura-700'}
      `}
      onClick={() => !disabled && onSelect(template)}
    >
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">
            {template.name}
          </h3>
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${typeStyle.badge}`}>
            {typeStyle.label}
          </span>
        </div>

        <p className="text-sm text-surface-500 dark:text-surface-400 mb-3">
          {template.description}
        </p>

        <div className="flex items-center gap-4 text-xs text-surface-500 dark:text-surface-400">
          <div className="flex items-center gap-1">
            <ClockIcon className="w-3.5 h-3.5" />
            <span>{template.default_ttl_hours}h default</span>
          </div>
          <div className="flex items-center gap-1">
            <CurrencyDollarIcon className="w-3.5 h-3.5" />
            <span>${template.cost_per_day.toFixed(2)}/day</span>
          </div>
          {template.requires_approval && (
            <span className="px-1.5 py-0.5 bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400 rounded text-xs">
              HITL Required
            </span>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-1">
          {template.resources.map((resource, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 rounded text-xs"
            >
              {resource}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// Quota Display Component
function QuotaDisplay({ quota }) {
  const usagePercent = (quota.active_count / quota.concurrent_limit) * 100;
  const budgetPercent = (quota.monthly_spent / quota.monthly_budget) * 100;

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
      <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">Your Quota</h3>

      <div className="space-y-4">
        {/* Environment slots */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-surface-600 dark:text-surface-400">Environment Slots</span>
            <span className="font-medium text-surface-900 dark:text-surface-100">
              {quota.active_count} / {quota.concurrent_limit}
            </span>
          </div>
          <div className="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                usagePercent >= 100 ? 'bg-critical-500' :
                usagePercent >= 66 ? 'bg-warning-500' : 'bg-olive-500'
              }`}
              style={{ width: `${Math.min(usagePercent, 100)}%` }}
            />
          </div>
        </div>

        {/* Monthly budget */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-surface-600 dark:text-surface-400">Monthly Budget</span>
            <span className="font-medium text-surface-900 dark:text-surface-100">
              ${quota.monthly_spent.toFixed(2)} / ${quota.monthly_budget.toFixed(2)}
            </span>
          </div>
          <div className="h-2 bg-surface-100 dark:bg-surface-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                budgetPercent >= 100 ? 'bg-critical-500' :
                budgetPercent >= 80 ? 'bg-warning-500' : 'bg-aura-500'
              }`}
              style={{ width: `${Math.min(budgetPercent, 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// Template icon mapping for visual distinction
const _TEMPLATE_ICONS = {
  'basic-sandbox': BeakerIcon,
  'development': CpuChipIcon,
  'security-testing': ShieldCheckIcon,
  'integration-testing': ServerStackIcon,
  // Fallback based on environment type
  quick: BeakerIcon,
  standard: CpuChipIcon,
  extended: ServerStackIcon,
  compliance: ShieldCheckIcon,
};

// Template metadata for enhanced display
const TEMPLATE_METADATA = {
  'basic-sandbox': {
    icon: BeakerIcon,
    spinUpTime: '~2 min',
    gradient: 'from-aura-500 to-aura-600',
    bgLight: 'bg-aura-50',
    bgDark: 'dark:bg-aura-900/20',
    borderSelected: 'border-aura-500 ring-aura-500/20',
    iconBg: 'bg-aura-100 dark:bg-aura-900/40',
    iconColor: 'text-aura-600 dark:text-aura-400',
  },
  'development': {
    icon: CpuChipIcon,
    spinUpTime: '~5 min',
    gradient: 'from-olive-500 to-olive-600',
    bgLight: 'bg-olive-50',
    bgDark: 'dark:bg-olive-900/20',
    borderSelected: 'border-olive-500 ring-olive-500/20',
    iconBg: 'bg-olive-100 dark:bg-olive-900/40',
    iconColor: 'text-olive-600 dark:text-olive-400',
  },
  'security-testing': {
    icon: ShieldCheckIcon,
    spinUpTime: '~8 min',
    gradient: 'from-warning-500 to-warning-600',
    bgLight: 'bg-warning-50',
    bgDark: 'dark:bg-warning-900/20',
    borderSelected: 'border-warning-500 ring-warning-500/20',
    iconBg: 'bg-warning-100 dark:bg-warning-900/40',
    iconColor: 'text-warning-600 dark:text-warning-400',
  },
  'integration-testing': {
    icon: ServerStackIcon,
    spinUpTime: '~10 min',
    gradient: 'from-critical-500 to-critical-600',
    bgLight: 'bg-critical-50',
    bgDark: 'dark:bg-critical-900/20',
    borderSelected: 'border-critical-500 ring-critical-500/20',
    iconBg: 'bg-critical-100 dark:bg-critical-900/40',
    iconColor: 'text-critical-600 dark:text-critical-400',
  },
};

// Default template metadata for dynamic templates
const getTemplateMetadata = (template) => {
  // Check for exact match first
  if (TEMPLATE_METADATA[template.template_id]) {
    return TEMPLATE_METADATA[template.template_id];
  }
  // Fall back to environment type based styling
  const typeMetadata = {
    quick: TEMPLATE_METADATA['basic-sandbox'],
    standard: TEMPLATE_METADATA['development'],
    extended: TEMPLATE_METADATA['integration-testing'],
    compliance: TEMPLATE_METADATA['security-testing'],
  };
  return typeMetadata[template.environment_type] || TEMPLATE_METADATA['basic-sandbox'];
};

// Duration options for TTL selection
const DURATION_OPTIONS = [
  { value: 1, label: '1 hour', description: 'Quick test' },
  { value: 4, label: '4 hours', description: 'Short session' },
  { value: 8, label: '8 hours', description: 'Work day' },
  { value: 24, label: '24 hours', description: '1 day' },
  { value: 72, label: '3 days', description: 'Extended testing' },
];

// Resource tier options
const RESOURCE_TIERS = [
  {
    id: 'small',
    name: 'Small',
    description: '2 vCPU, 4 GB RAM',
    costMultiplier: 1.0,
    icon: 'S',
  },
  {
    id: 'medium',
    name: 'Medium',
    description: '4 vCPU, 8 GB RAM',
    costMultiplier: 2.0,
    icon: 'M',
  },
  {
    id: 'large',
    name: 'Large',
    description: '8 vCPU, 16 GB RAM',
    costMultiplier: 4.0,
    icon: 'L',
  },
];

// Default templates when API returns empty (for development/demo)
const DEFAULT_TEMPLATES = [
  {
    template_id: 'basic-sandbox',
    name: 'Minimal Sandbox',
    description: 'Lightweight isolated environment for quick tests and experiments. Minimal resources with fast spin-up time.',
    environment_type: 'quick',
    requires_approval: false,
    default_ttl_hours: 4,
    cost_per_day: 3.60,
    resources: ['Docker', 'Git', 'Python 3.11'],
  },
  {
    template_id: 'development',
    name: 'Standard Development',
    description: 'Full development environment with common tools and services. Ideal for feature development and debugging.',
    environment_type: 'standard',
    requires_approval: false,
    default_ttl_hours: 8,
    cost_per_day: 10.80,
    resources: ['Docker', 'Git', 'Python 3.11', 'Node.js 20', 'PostgreSQL', 'Redis'],
  },
  {
    template_id: 'integration-testing',
    name: 'Integration Testing',
    description: 'Complete testing environment with all dependencies. Includes mock services and test data generators.',
    environment_type: 'extended',
    requires_approval: false,
    default_ttl_hours: 24,
    cost_per_day: 20.40,
    resources: ['Docker', 'Git', 'Python 3.11', 'Node.js 20', 'PostgreSQL', 'Redis', 'Elasticsearch', 'LocalStack'],
  },
  {
    template_id: 'security-testing',
    name: 'Security Testing',
    description: 'Hardened environment for security assessments and compliance testing. Requires HITL approval.',
    environment_type: 'compliance',
    requires_approval: true,
    default_ttl_hours: 8,
    cost_per_day: 15.60,
    resources: ['Docker', 'Git', 'Python 3.11', 'SAST Tools', 'DAST Scanner', 'Vulnerability DB'],
  },
];

// Create Environment Modal - Apple-inspired multi-step design
function CreateEnvironmentModal({ isOpen, onClose, templates, quota, onCreate }) {
  // Step management (1: Template, 2: Configure)
  const [step, setStep] = useState(1);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [displayName, setDisplayName] = useState('');
  const [selectedDuration, setSelectedDuration] = useState(null);
  const [selectedTier, setSelectedTier] = useState('small');
  const [autoShutdown, setAutoShutdown] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setSelectedTemplate(null);
      setDisplayName('');
      setSelectedDuration(null);
      setSelectedTier('small');
      setAutoShutdown(true);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const canCreate = quota.available > 0;

  // Calculate estimated cost
  const calculateCost = () => {
    if (!selectedTemplate) return 0;
    const baseCost = selectedTemplate.cost_per_day || 0;
    const tierMultiplier = RESOURCE_TIERS.find(t => t.id === selectedTier)?.costMultiplier || 1;
    const duration = selectedDuration || selectedTemplate.default_ttl_hours || 24;
    const dailyCost = baseCost * tierMultiplier;
    const totalCost = (dailyCost / 24) * duration;
    return { dailyCost, totalCost, duration };
  };

  const { dailyCost, totalCost, duration } = calculateCost();

  // Handle template selection and auto-advance
  const handleTemplateSelect = (template) => {
    if (!canCreate) return;
    setSelectedTemplate(template);
    // Set default duration based on template
    const defaultDuration = DURATION_OPTIONS.find(d => d.value === template.default_ttl_hours)
      || DURATION_OPTIONS.find(d => d.value <= template.default_ttl_hours)
      || DURATION_OPTIONS[1];
    setSelectedDuration(defaultDuration.value);
  };

  // Handle create
  const handleCreate = async () => {
    if (!selectedTemplate || !displayName) return;

    setIsCreating(true);
    try {
      await onCreate({
        template_id: selectedTemplate.template_id,
        display_name: displayName,
        ttl_hours: selectedDuration || selectedTemplate.default_ttl_hours,
        resource_tier: selectedTier,
        auto_shutdown: autoShutdown,
      });
      onClose();
    } finally {
      setIsCreating(false);
    }
  };

  // Navigation helpers
  const canProceedToStep2 = selectedTemplate !== null;
  const canSubmit = selectedTemplate && displayName.trim().length >= 3;

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-env-title"
    >
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop with blur */}
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />

        {/* Modal container */}
        <div className="relative bg-white dark:bg-surface-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden transform transition-all">

          {/* Header with step indicator */}
          <div className="px-8 pt-6 pb-4 border-b border-surface-100 dark:border-surface-700/50">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2
                  id="create-env-title"
                  className="text-xl font-semibold text-surface-900 dark:text-surface-100"
                >
                  Create Sandbox
                </h2>
                <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
                  {step === 1 ? 'Choose a template and spin up in under 5 minutes' : 'Configure your sandbox settings'}
                </p>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-full text-surface-400 hover:text-surface-600 hover:bg-surface-100 dark:hover:text-surface-300 dark:hover:bg-surface-700 transition-colors"
                aria-label="Close modal"
              >
                <XCircleIcon className="w-6 h-6" />
              </button>
            </div>

            {/* Step indicator */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors
                  ${step >= 1
                    ? 'bg-aura-500 text-white'
                    : 'bg-surface-200 dark:bg-surface-600 text-surface-500 dark:text-surface-400'}
                `}>
                  1
                </div>
                <span className={`text-sm font-medium ${step >= 1 ? 'text-surface-900 dark:text-surface-100' : 'text-surface-400'}`}>
                  Template
                </span>
              </div>
              <div className={`flex-1 h-0.5 ${step >= 2 ? 'bg-aura-500' : 'bg-surface-200 dark:bg-surface-600'}`} />
              <div className="flex items-center gap-2">
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors
                  ${step >= 2
                    ? 'bg-aura-500 text-white'
                    : 'bg-surface-200 dark:bg-surface-600 text-surface-500 dark:text-surface-400'}
                `}>
                  2
                </div>
                <span className={`text-sm font-medium ${step >= 2 ? 'text-surface-900 dark:text-surface-100' : 'text-surface-400'}`}>
                  Configure
                </span>
              </div>
            </div>
          </div>

          {/* Quota warning */}
          {!canCreate && (
            <div className="mx-8 mt-6 p-4 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-xl">
              <div className="flex items-start gap-3">
                <ExclamationTriangleIcon className="w-5 h-5 text-warning-600 dark:text-warning-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium text-warning-800 dark:text-warning-300">Quota Exceeded</p>
                  <p className="text-sm text-warning-700 dark:text-warning-400 mt-0.5">
                    You have reached your concurrent sandbox limit ({quota.concurrent_limit}). Terminate an existing sandbox to create a new one.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Content area with smooth transitions */}
          <div className="p-8 overflow-y-auto max-h-[calc(90vh-280px)]">

            {/* Step 1: Template Selection */}
            {step === 1 && (
              <div className="space-y-4">
                <p className="text-sm text-surface-600 dark:text-surface-400 mb-6">
                  Select the environment template that best fits your testing needs.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {templates.map((template) => {
                    const metadata = getTemplateMetadata(template);
                    const TemplateIcon = metadata.icon || BeakerIcon;
                    const isSelected = selectedTemplate?.template_id === template.template_id;

                    return (
                      <button
                        key={template.template_id}
                        type="button"
                        onClick={() => handleTemplateSelect(template)}
                        disabled={!canCreate}
                        className={`
                          relative p-5 rounded-xl border-2 text-left transition-all duration-200
                          focus:outline-none focus:ring-4 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-surface-800
                          ${isSelected
                            ? `${metadata.borderSelected} bg-white dark:bg-surface-800 backdrop-blur-xl ring-4`
                            : 'border-surface-200/50 dark:border-surface-700/30 bg-white dark:bg-surface-800 backdrop-blur-xl shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glass-hover)]'
                          }
                          ${!canCreate ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                        `}
                        aria-pressed={isSelected}
                        aria-label={`Select ${template.name} template`}
                      >
                        {/* Selection checkmark */}
                        {isSelected && (
                          <div className="absolute top-3 right-3">
                            <CheckCircleIcon className="w-6 h-6 text-aura-500" />
                          </div>
                        )}

                        {/* Icon and title */}
                        <div className="flex items-start gap-4">
                          <div className={`p-3 rounded-xl ${metadata.iconBg}`}>
                            <TemplateIcon className={`w-6 h-6 ${metadata.iconColor}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                                {template.name}
                              </h3>
                              {template.requires_approval && (
                                <span className="px-2 py-0.5 text-xs font-medium bg-warning-100 text-warning-700 dark:bg-warning-900/40 dark:text-warning-400 rounded-full">
                                  HITL
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-surface-500 dark:text-surface-400 mb-3 line-clamp-2">
                              {template.description}
                            </p>

                            {/* Template metadata */}
                            <div className="flex flex-wrap items-center gap-3 text-xs">
                              <span className="flex items-center gap-1 text-surface-500 dark:text-surface-400">
                                <ClockIcon className="w-3.5 h-3.5" />
                                {metadata.spinUpTime || `~${Math.ceil(template.default_ttl_hours / 4)} min`}
                              </span>
                              <span className="flex items-center gap-1 text-surface-500 dark:text-surface-400">
                                <CurrencyDollarIcon className="w-3.5 h-3.5" />
                                ${template.cost_per_day?.toFixed(2) || '0.00'}/day
                              </span>
                              <span className={`px-2 py-0.5 rounded-full font-medium ${TYPE_STYLES[template.environment_type]?.badge || 'bg-surface-100 text-surface-600'}`}>
                                {TYPE_STYLES[template.environment_type]?.label || template.environment_type}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Resources preview */}
                        {template.resources && template.resources.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-surface-200 dark:border-surface-600/50">
                            <div className="flex flex-wrap gap-1.5">
                              {template.resources.slice(0, 4).map((resource, idx) => (
                                <span
                                  key={idx}
                                  className="px-2 py-0.5 bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 rounded text-xs"
                                >
                                  {resource}
                                </span>
                              ))}
                              {template.resources.length > 4 && (
                                <span className="px-2 py-0.5 text-surface-400 text-xs">
                                  +{template.resources.length - 4} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Empty state if no templates */}
                {templates.length === 0 && (
                  <div className="text-center py-12">
                    <BeakerIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600 mb-4" />
                    <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
                      No templates available
                    </h3>
                    <p className="text-sm text-surface-500 dark:text-surface-400">
                      Contact your administrator to configure environment templates.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Step 2: Configuration */}
            {step === 2 && selectedTemplate && (
              <div className="space-y-8">
                {/* Selected template summary */}
                <div className="flex items-center gap-4 p-4 bg-surface-50 dark:bg-surface-700/50 rounded-xl">
                  {(() => {
                    const metadata = getTemplateMetadata(selectedTemplate);
                    const TemplateIcon = metadata.icon || BeakerIcon;
                    return (
                      <>
                        <div className={`p-3 rounded-xl ${metadata.iconBg}`}>
                          <TemplateIcon className={`w-5 h-5 ${metadata.iconColor}`} />
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-surface-900 dark:text-surface-100">
                            {selectedTemplate.name}
                          </p>
                          <p className="text-sm text-surface-500 dark:text-surface-400">
                            {TYPE_STYLES[selectedTemplate.environment_type]?.description || selectedTemplate.environment_type}
                          </p>
                        </div>
                        <button
                          onClick={() => setStep(1)}
                          className="text-sm font-medium text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
                        >
                          Change
                        </button>
                      </>
                    );
                  })()}
                </div>

                {/* Environment Name */}
                <div>
                  <label
                    htmlFor="env-name"
                    className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2"
                  >
                    Environment Name <span className="text-critical-500">*</span>
                  </label>
                  <input
                    id="env-name"
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g., API Integration Tests"
                    className="w-full px-4 py-3 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 dark:placeholder-surface-500 focus:ring-2 focus:ring-aura-500 focus:border-transparent transition-colors"
                    maxLength={100}
                    aria-required="true"
                    aria-describedby="env-name-hint"
                  />
                  <p id="env-name-hint" className="mt-1.5 text-xs text-surface-500 dark:text-surface-400">
                    A descriptive name to identify this environment (minimum 3 characters)
                  </p>
                </div>

                {/* Duration Selection */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
                    Duration / TTL
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                    {DURATION_OPTIONS.filter(d => d.value <= (selectedTemplate.max_ttl_hours || 168)).map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setSelectedDuration(option.value)}
                        className={`
                          p-3 rounded-xl border-2 text-center transition-all duration-150
                          focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
                          ${selectedDuration === option.value
                            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/30'
                            : 'border-surface-200 dark:border-surface-600 hover:border-surface-300 dark:hover:border-surface-500'
                          }
                        `}
                        aria-pressed={selectedDuration === option.value}
                      >
                        <span className={`block text-sm font-semibold ${selectedDuration === option.value ? 'text-aura-700 dark:text-aura-300' : 'text-surface-900 dark:text-surface-100'}`}>
                          {option.label}
                        </span>
                        <span className="block text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                          {option.description}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Resource Tier */}
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
                    Resource Tier
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {RESOURCE_TIERS.map((tier) => (
                      <button
                        key={tier.id}
                        type="button"
                        onClick={() => setSelectedTier(tier.id)}
                        className={`
                          p-4 rounded-xl border-2 text-center transition-all duration-150
                          focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
                          ${selectedTier === tier.id
                            ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/30'
                            : 'border-surface-200 dark:border-surface-600 hover:border-surface-300 dark:hover:border-surface-500'
                          }
                        `}
                        aria-pressed={selectedTier === tier.id}
                      >
                        <span className={`
                          inline-flex items-center justify-center w-10 h-10 rounded-full mb-2 text-lg font-bold
                          ${selectedTier === tier.id
                            ? 'bg-aura-500 text-white'
                            : 'bg-surface-100 dark:bg-surface-600 text-surface-600 dark:text-surface-300'}
                        `}>
                          {tier.icon}
                        </span>
                        <span className={`block text-sm font-semibold ${selectedTier === tier.id ? 'text-aura-700 dark:text-aura-300' : 'text-surface-900 dark:text-surface-100'}`}>
                          {tier.name}
                        </span>
                        <span className="block text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                          {tier.description}
                        </span>
                        {tier.costMultiplier > 1 && (
                          <span className="block text-xs text-aura-600 dark:text-aura-400 mt-1 font-medium">
                            {tier.costMultiplier}x cost
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Auto-shutdown toggle */}
                <div className="flex items-center justify-between p-4 bg-surface-50 dark:bg-surface-700/50 rounded-xl">
                  <div className="flex-1">
                    <label
                      htmlFor="auto-shutdown"
                      className="block text-sm font-medium text-surface-900 dark:text-surface-100"
                    >
                      Auto-shutdown on inactivity
                    </label>
                    <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                      Automatically terminate after 4 hours of inactivity to save costs
                    </p>
                  </div>
                  <button
                    id="auto-shutdown"
                    type="button"
                    role="switch"
                    aria-checked={autoShutdown}
                    onClick={() => setAutoShutdown(!autoShutdown)}
                    className={`
                      relative inline-flex h-7 w-12 items-center rounded-full transition-colors duration-200
                      focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
                      ${autoShutdown ? 'bg-aura-500' : 'bg-surface-300 dark:bg-surface-600'}
                    `}
                  >
                    <span
                      className={`
                        inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform duration-200
                        ${autoShutdown ? 'translate-x-6' : 'translate-x-1'}
                      `}
                    />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Footer with cost preview and actions */}
          <div className="px-8 py-5 border-t border-surface-100 dark:border-surface-700/50 bg-surface-50 dark:bg-surface-800/50">
            <div className="flex items-center justify-between">
              {/* Cost preview */}
              {step === 2 && selectedTemplate && (
                <div className="flex items-center gap-6">
                  <div>
                    <p className="text-xs text-surface-500 dark:text-surface-400 uppercase tracking-wide">Estimated Cost</p>
                    <p className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                      ${totalCost.toFixed(2)}
                      <span className="text-sm font-normal text-surface-500 dark:text-surface-400 ml-1">
                        for {duration}h
                      </span>
                    </p>
                  </div>
                  <div className="h-8 w-px bg-surface-200 dark:bg-surface-600" />
                  <div>
                    <p className="text-xs text-surface-500 dark:text-surface-400 uppercase tracking-wide">Daily Rate</p>
                    <p className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                      ${dailyCost.toFixed(2)}
                      <span className="text-sm font-normal text-surface-500 dark:text-surface-400 ml-1">/day</span>
                    </p>
                  </div>
                </div>
              )}

              {step === 1 && (
                <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
                  <CheckCircleIcon className="w-4 h-4" />
                  <span>
                    {quota.available} of {quota.concurrent_limit} slots available
                  </span>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-3">
                {step === 2 && (
                  <button
                    onClick={() => setStep(1)}
                    className="px-5 py-2.5 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-xl transition-colors"
                  >
                    Back
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="px-5 py-2.5 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-xl transition-colors"
                >
                  Cancel
                </button>

                {step === 1 ? (
                  <button
                    onClick={() => setStep(2)}
                    disabled={!canProceedToStep2 || !canCreate}
                    className="px-5 py-2.5 text-sm font-medium bg-aura-500 text-white rounded-xl hover:bg-aura-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    Continue
                    <ChevronRightIcon className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    onClick={handleCreate}
                    disabled={!canSubmit || isCreating || !canCreate}
                    className="px-5 py-2.5 text-sm font-medium bg-aura-500 text-white rounded-xl hover:bg-aura-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    {isCreating ? (
                      <>
                        <ArrowPathIcon className="w-4 h-4 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      <>
                        <PlusIcon className="w-4 h-4" />
                        Create Sandbox
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Main Environments Component
export default function Environments() {
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [environments, setEnvironments] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [quota, setQuota] = useState(null);
  const [selectedEnvironment, setSelectedEnvironment] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showExtendModal, setShowExtendModal] = useState(false);
  const [extendingEnv, setExtendingEnv] = useState(null);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState(null);
  const { toast } = useToast();

  // Load data from API
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [envResponse, templatesResponse, quotaResponse] = await Promise.all([
        listEnvironments(),
        getTemplates().catch(() => []),
        getUserQuota().catch(() => DEFAULT_QUOTA),
      ]);
      setEnvironments(envResponse.environments || []);
      // Use default templates if API returns empty
      const templates = templatesResponse && templatesResponse.length > 0
        ? templatesResponse
        : DEFAULT_TEMPLATES;
      setTemplates(templates);
      setQuota(quotaResponse);
    } catch (err) {
      console.error('Failed to load environments:', err);
      setError(err instanceof EnvironmentsApiError ? err.message : 'Failed to load environments');
      // Use defaults on error
      setEnvironments([]);
      setTemplates(DEFAULT_TEMPLATES);
      setQuota(DEFAULT_QUOTA);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await loadData();
      toast.success('Environments refreshed');
    } catch (err) {
      toast.error('Failed to refresh environments');
    } finally {
      setIsRefreshing(false);
    }
  }, [loadData, toast]);

  const handleCreate = async (config) => {
    try {
      const newEnv = await createEnvironment(config);
      setEnvironments(prev => [newEnv, ...prev]);
      // Refresh quota after creating
      const updatedQuota = await getUserQuota().catch(() => null);
      if (updatedQuota) setQuota(updatedQuota);
    } catch (err) {
      console.error('Failed to create environment:', err);
      throw err; // Re-throw to be handled by the modal
    }
  };

  const handleTerminate = async (env) => {
    if (confirm(`Are you sure you want to terminate "${env.display_name}"?`)) {
      try {
        // Optimistically update UI
        setEnvironments(prev => prev.map(e =>
          e.environment_id === env.environment_id ? { ...e, status: 'terminating' } : e
        ));
        await terminateEnvironment(env.environment_id);
        // Refresh data after termination
        await loadData();
      } catch (err) {
        console.error('Failed to terminate environment:', err);
        setError(err instanceof EnvironmentsApiError ? err.message : 'Failed to terminate environment');
        // Revert optimistic update
        await loadData();
      }
    }
  };

  const handleExtend = async (env) => {
    setExtendingEnv(env);
    setShowExtendModal(true);
  };

  const handleExtendSubmit = async (hours, reason) => {
    if (!extendingEnv) return;
    try {
      const updatedEnv = await extendEnvironmentTTL(extendingEnv.environment_id, hours, reason);
      setEnvironments(prev => prev.map(e =>
        e.environment_id === updatedEnv.environment_id ? updatedEnv : e
      ));
      setShowExtendModal(false);
      setExtendingEnv(null);
    } catch (err) {
      console.error('Failed to extend environment:', err);
      throw err; // Re-throw to be handled by the modal
    }
  };

  // Filter environments
  const filteredEnvironments = environments.filter(env => {
    if (filter !== 'all' && env.status !== filter) return false;
    if (searchQuery && !env.display_name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !env.environment_id.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  if (isLoading) {
    return <PageSkeleton />;
  }

  // If an environment is selected, show the dashboard
  if (selectedEnvironment) {
    return (
      <EnvironmentDashboard
        environment={selectedEnvironment}
        onBack={() => setSelectedEnvironment(null)}
        onTerminate={handleTerminate}
        onExtend={handleExtend}
      />
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              Sandboxes
            </h1>
            <p className="text-surface-500 dark:text-surface-400 mt-1">
              Spin up isolated test environments in minutes
            </p>
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
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-aura-500 text-white rounded-lg hover:bg-aura-600 transition-colors font-medium"
            >
              <PlusIcon className="w-5 h-5" />
              New Sandbox
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-2 text-critical-700 dark:text-critical-400">
              <ExclamationTriangleIcon className="w-5 h-5" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-critical-500 hover:text-critical-700 dark:hover:text-critical-300"
            >
              <XCircleIcon className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Quota and Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
          <div className="lg:col-span-1">
            <QuotaDisplay quota={quota} />
          </div>
          <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
                  <CheckCircleIcon className="w-5 h-5 text-olive-600 dark:text-olive-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                    {environments.filter(e => e.status === 'active').length}
                  </p>
                  <p className="text-sm text-surface-500 dark:text-surface-400">Active</p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-warning-100 dark:bg-warning-900/30 rounded-lg">
                  <ClockIcon className="w-5 h-5 text-warning-600 dark:text-warning-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                    {environments.filter(e => e.status === 'pending_approval').length}
                  </p>
                  <p className="text-sm text-surface-500 dark:text-surface-400">Pending</p>
                </div>
              </div>
            </div>
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
                  <CurrencyDollarIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                    ${environments.reduce((sum, e) => sum + (e.status === 'active' ? e.cost_estimate_daily : 0), 0).toFixed(2)}
                  </p>
                  <p className="text-sm text-surface-500 dark:text-surface-400">Daily Cost</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Search and Filter */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
            <input
              type="text"
              placeholder="Search sandboxes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2">
            <FunnelIcon className="w-5 h-5 text-surface-400" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="pending_approval">Pending Approval</option>
              <option value="provisioning">Provisioning</option>
              <option value="expiring">Expiring</option>
              <option value="terminated">Terminated</option>
            </select>
          </div>
        </div>

        {/* Environment List */}
        {filteredEnvironments.length === 0 ? (
          <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-12 text-center">
            <ServerStackIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600 mb-4" />
            <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100 mb-2">
              No sandboxes yet
            </h3>
            <p className="text-surface-500 dark:text-surface-400 mb-6">
              {searchQuery || filter !== 'all'
                ? 'Try adjusting your search or filter criteria'
                : 'Create your first sandbox to start prototyping'}
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-aura-500 text-white rounded-lg hover:bg-aura-600 transition-colors font-medium"
            >
              <PlusIcon className="w-5 h-5" />
              New Sandbox
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredEnvironments.map((env) => (
              <EnvironmentCard
                key={env.environment_id}
                environment={env}
                templates={templates}
                onTerminate={handleTerminate}
                onExtend={handleExtend}
                onSelect={setSelectedEnvironment}
              />
            ))}
          </div>
        )}

        {/* Create Modal */}
        <CreateEnvironmentModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          templates={templates}
          quota={quota}
          onCreate={handleCreate}
        />

        {/* Extend TTL Modal */}
        <ExtendTTLModal
          isOpen={showExtendModal}
          onClose={() => { setShowExtendModal(false); setExtendingEnv(null); }}
          environment={extendingEnv}
          onExtend={handleExtendSubmit}
        />
      </div>
    </div>
  );
}

// Extend TTL Modal Component
function ExtendTTLModal({ isOpen, onClose, environment, onExtend }) {
  const [hours, setHours] = useState(4);
  const [reason, setReason] = useState('');
  const [isExtending, setIsExtending] = useState(false);
  const [error, setError] = useState(null);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setHours(4);
      setReason('');
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen || !environment) return null;

  const handleSubmit = async () => {
    setIsExtending(true);
    setError(null);
    try {
      await onExtend(hours, reason);
    } catch (err) {
      setError(err.message || 'Failed to extend TTL');
    } finally {
      setIsExtending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50 transition-opacity" onClick={onClose} />

        <div className="relative bg-white dark:bg-surface-800 rounded-2xl shadow-xl max-w-md w-full">
          {/* Header */}
          <div className="px-6 py-4 border-b border-surface-200 dark:border-surface-700">
            <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
              Extend Environment TTL
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
              Extend the lifetime of "{environment.display_name}"
            </p>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            {error && (
              <div className="p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
                <p className="text-sm text-critical-700 dark:text-critical-400">{error}</p>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Additional Hours
              </label>
              <input
                type="number"
                value={hours}
                onChange={(e) => setHours(Math.max(1, Math.min(168, parseInt(e.target.value) || 1)))}
                min={1}
                max={168}
                className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
              />
              <p className="text-xs text-surface-500 mt-1">Max 168 hours (7 days)</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Reason (Optional)
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why do you need more time?"
                rows={3}
                maxLength={500}
                className="w-full px-4 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-transparent resize-none"
              />
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-surface-200 dark:border-surface-700 flex justify-end gap-3">
            <button
              onClick={onClose}
              disabled={isExtending}
              className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={isExtending}
              className="px-4 py-2 text-sm font-medium bg-aura-500 text-white rounded-lg hover:bg-aura-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {isExtending ? (
                <>
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  Extending...
                </>
              ) : (
                <>
                  <ClockIcon className="w-4 h-4" />
                  Extend by {hours}h
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
