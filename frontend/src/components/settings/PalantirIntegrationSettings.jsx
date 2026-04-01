/**
 * Palantir AIP Integration Settings
 *
 * 5-step configuration wizard for Palantir AIP integration.
 * Steps: 1) Connection, 2) Authentication, 3) Data Mapping, 4) Event Stream, 5) Review
 *
 * ADR-075: Palantir AIP UI Enhancements
 *
 * @module components/settings/PalantirIntegrationSettings
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  XMarkIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  CubeIcon,
  CloudIcon,
  DocumentCheckIcon,
  Cog6ToothIcon,
  LinkIcon,
  KeyIcon,
  Square3Stack3DIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';
import { testConnection, getHealth } from '../../services/palantirApi';

// Steps configuration
const STEPS = [
  { id: 'connection', label: 'Connection', icon: LinkIcon },
  { id: 'auth', label: 'Authentication', icon: KeyIcon },
  { id: 'mapping', label: 'Data Mapping', icon: Square3Stack3DIcon },
  { id: 'events', label: 'Event Stream', icon: BoltIcon },
  { id: 'review', label: 'Review & Enable', icon: DocumentCheckIcon },
];

// Ontology object types available for sync
const OBJECT_TYPES = [
  { id: 'threat_intel', label: 'Threat Intelligence', description: 'CVE context, active campaigns, MITRE TTP mappings' },
  { id: 'asset_cmdb', label: 'Asset CMDB', description: 'Repository criticality scores, business owners, data classification' },
  { id: 'insider_risk', label: 'Insider Risk Indicators', description: 'User risk scores and elevated risk counts' },
  { id: 'compliance', label: 'Compliance Controls', description: 'Framework controls and drift status' },
  { id: 'epss_scores', label: 'EPSS Scores', description: 'Exploit prediction scores for CVEs' },
];

// Sync frequency options
const SYNC_FREQUENCIES = [
  { value: 30, label: 'Every 30 seconds', description: 'Real-time (recommended for threat intel)' },
  { value: 60, label: 'Every minute', description: 'Near real-time' },
  { value: 300, label: 'Every 5 minutes', description: 'Standard' },
  { value: 900, label: 'Every 15 minutes', description: 'Low frequency' },
  { value: 3600, label: 'Hourly', description: 'Asset and compliance data' },
];

// Event stream targets
const EVENT_TARGETS = [
  { id: 'eventbridge', label: 'AWS EventBridge', description: 'Native AWS event bus integration' },
  { id: 'kafka', label: 'Apache Kafka', description: 'High-throughput event streaming' },
  { id: 'sqs', label: 'AWS SQS', description: 'Simple queue service' },
];

// Event types to subscribe
const EVENT_TYPES = [
  { id: 'threat.new', label: 'New Threats', description: 'Newly discovered threat campaigns' },
  { id: 'threat.updated', label: 'Threat Updates', description: 'Changes to existing threat context' },
  { id: 'asset.criticality_change', label: 'Asset Criticality Changes', description: 'When repository criticality scores change' },
  { id: 'compliance.drift', label: 'Compliance Drift', description: 'Control failures detected' },
  { id: 'risk.elevated', label: 'Elevated Risk', description: 'Users with newly elevated risk scores' },
];

/**
 * Step indicator component
 */
function StepIndicator({ steps, currentStep }) {
  return (
    <div className="flex items-center justify-between mb-8">
      {steps.map((step, index) => {
        const isActive = index === currentStep;
        const isComplete = index < currentStep;
        const Icon = step.icon;

        return (
          <React.Fragment key={step.id}>
            <div className="flex items-center">
              <div
                className={`
                  flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors
                  ${isComplete
                    ? 'bg-green-500 border-green-500 text-white'
                    : isActive
                      ? 'bg-aura-600 border-aura-600 text-white'
                      : 'bg-white dark:bg-surface-700 border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400'
                  }
                `}
              >
                {isComplete ? (
                  <CheckIcon className="w-5 h-5" />
                ) : (
                  <Icon className="w-5 h-5" />
                )}
              </div>
              <span
                className={`
                  ml-2 text-sm font-medium hidden sm:inline
                  ${isActive ? 'text-aura-600 dark:text-aura-400' : 'text-gray-500 dark:text-gray-400'}
                `}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`
                  flex-1 h-0.5 mx-2
                  ${index < currentStep
                    ? 'bg-green-500'
                    : 'bg-gray-200 dark:bg-gray-600'
                  }
                `}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/**
 * Connection step component
 */
function ConnectionStep({ config, onChange, errors }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Palantir Connection Settings
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Configure the connection to your Palantir Foundry instance.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Ontology API URL <span className="text-red-500">*</span>
          </label>
          <input
            type="url"
            value={config.ontology_url || ''}
            onChange={(e) => onChange('ontology_url', e.target.value)}
            placeholder="https://your-instance.palantirfoundry.com/ontology/api"
            className={`
              w-full px-3 py-2 border rounded-lg
              bg-white dark:bg-surface-700
              text-gray-900 dark:text-gray-100
              focus:outline-none focus:ring-2 focus:ring-aura-500
              ${errors.ontology_url ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
            `}
          />
          {errors.ontology_url && (
            <p className="mt-1 text-sm text-red-500">{errors.ontology_url}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Foundry URL <span className="text-red-500">*</span>
          </label>
          <input
            type="url"
            value={config.foundry_url || ''}
            onChange={(e) => onChange('foundry_url', e.target.value)}
            placeholder="https://your-instance.palantirfoundry.com"
            className={`
              w-full px-3 py-2 border rounded-lg
              bg-white dark:bg-surface-700
              text-gray-900 dark:text-gray-100
              focus:outline-none focus:ring-2 focus:ring-aura-500
              ${errors.foundry_url ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
            `}
          />
          {errors.foundry_url && (
            <p className="mt-1 text-sm text-red-500">{errors.foundry_url}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Environment Name
          </label>
          <input
            type="text"
            value={config.environment_name || ''}
            onChange={(e) => onChange('environment_name', e.target.value)}
            placeholder="production"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
          />
          <p className="mt-1 text-xs text-gray-500">Optional label for this connection</p>
        </div>
      </div>
    </div>
  );
}

/**
 * Authentication step component
 */
function AuthenticationStep({ config, onChange, errors, onTest, testing, testResult }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Authentication
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Configure API authentication for your Palantir instance.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            API Key <span className="text-red-500">*</span>
          </label>
          <input
            type="password"
            value={config.api_key || ''}
            onChange={(e) => onChange('api_key', e.target.value)}
            placeholder="Enter your Palantir API key"
            className={`
              w-full px-3 py-2 border rounded-lg
              bg-white dark:bg-surface-700
              text-gray-900 dark:text-gray-100
              focus:outline-none focus:ring-2 focus:ring-aura-500
              ${errors.api_key ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
            `}
          />
          {errors.api_key && (
            <p className="mt-1 text-sm text-red-500">{errors.api_key}</p>
          )}
        </div>

        <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            mTLS Certificate (Optional)
          </h4>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                Client Certificate (PEM)
              </label>
              <textarea
                value={config.mtls_cert || ''}
                onChange={(e) => onChange('mtls_cert', e.target.value)}
                placeholder="Paste mTLS certificate (PEM format)"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500 font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                Private Key (PEM)
              </label>
              <textarea
                value={config.mtls_key || ''}
                onChange={(e) => onChange('mtls_key', e.target.value)}
                placeholder="Paste mTLS private key (PEM format)"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500 font-mono text-xs"
              />
            </div>
          </div>
        </div>

        {/* Test Connection Button */}
        <div className="pt-4">
          <button
            onClick={onTest}
            disabled={testing || !config.ontology_url || !config.api_key}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors
              ${testing
                ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                : 'bg-aura-600 text-white hover:bg-aura-700'
              }
            `}
          >
            {testing ? (
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
            ) : (
              <ShieldCheckIcon className="w-5 h-5" />
            )}
            {testing ? 'Testing...' : 'Test Connection'}
          </button>

          {testResult && (
            <div
              className={`
                mt-3 p-3 rounded-lg flex items-start gap-2
                ${testResult.success
                  ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                  : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                }
              `}
            >
              {testResult.success ? (
                <CheckCircleIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
              ) : (
                <ExclamationCircleIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
              )}
              <div>
                <p className="font-medium">
                  {testResult.success ? 'Connection successful' : 'Connection failed'}
                </p>
                {testResult.latency_ms && (
                  <p className="text-sm mt-1">Latency: {testResult.latency_ms}ms</p>
                )}
                {testResult.error && (
                  <p className="text-sm mt-1">{testResult.error}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Data Mapping step component
 */
function DataMappingStep({ config, onChange }) {
  const handleObjectTypeToggle = (objectId) => {
    const current = config.enabled_object_types || [];
    const updated = current.includes(objectId)
      ? current.filter((id) => id !== objectId)
      : [...current, objectId];
    onChange('enabled_object_types', updated);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Data Mapping
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Select which Ontology object types to synchronize.
        </p>
      </div>

      <div className="space-y-3">
        {OBJECT_TYPES.map((objType) => {
          const isSelected = (config.enabled_object_types || []).includes(objType.id);
          return (
            <button
              key={objType.id}
              onClick={() => handleObjectTypeToggle(objType.id)}
              className={`
                w-full text-left p-4 rounded-lg border-2 transition-colors
                ${isSelected
                  ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                }
              `}
            >
              <div className="flex items-start gap-3">
                <div
                  className={`
                    w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5
                    ${isSelected
                      ? 'bg-aura-600 border-aura-600'
                      : 'border-gray-300 dark:border-gray-600'
                    }
                  `}
                >
                  {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    {objType.label}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    {objType.description}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Default Sync Frequency
        </label>
        <select
          value={config.sync_frequency || 300}
          onChange={(e) => onChange('sync_frequency', parseInt(e.target.value, 10))}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
        >
          {SYNC_FREQUENCIES.map((freq) => (
            <option key={freq.value} value={freq.value}>
              {freq.label} - {freq.description}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/**
 * Event Stream step component
 */
function EventStreamStep({ config, onChange }) {
  const handleEventTypeToggle = (eventId) => {
    const current = config.enabled_event_types || [];
    const updated = current.includes(eventId)
      ? current.filter((id) => id !== eventId)
      : [...current, eventId];
    onChange('enabled_event_types', updated);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Event Stream Configuration
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Configure real-time event streaming from Palantir.
        </p>
      </div>

      {/* Event Target */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Event Target
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {EVENT_TARGETS.map((target) => {
            const isSelected = config.event_target === target.id;
            return (
              <button
                key={target.id}
                onClick={() => onChange('event_target', target.id)}
                className={`
                  p-3 rounded-lg border-2 text-left transition-colors
                  ${isSelected
                    ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }
                `}
              >
                <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">
                  {target.label}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {target.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Event Types */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Event Types to Subscribe
        </label>
        <div className="space-y-2">
          {EVENT_TYPES.map((eventType) => {
            const isSelected = (config.enabled_event_types || []).includes(eventType.id);
            return (
              <button
                key={eventType.id}
                onClick={() => handleEventTypeToggle(eventType.id)}
                className={`
                  w-full text-left p-3 rounded-lg border transition-colors flex items-start gap-3
                  ${isSelected
                    ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }
                `}
              >
                <div
                  className={`
                    w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5
                    ${isSelected
                      ? 'bg-aura-600 border-aura-600'
                      : 'border-gray-300 dark:border-gray-600'
                    }
                  `}
                >
                  {isSelected && <CheckIcon className="w-2.5 h-2.5 text-white" />}
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">
                    {eventType.label}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {eventType.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Kafka/EventBridge specific config */}
      {config.event_target === 'kafka' && (
        <div className="p-4 bg-gray-50 dark:bg-surface-700 rounded-lg space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Kafka Configuration
          </h4>
          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              Bootstrap Servers
            </label>
            <input
              type="text"
              value={config.kafka_bootstrap_servers || ''}
              onChange={(e) => onChange('kafka_bootstrap_servers', e.target.value)}
              placeholder="broker1:9092,broker2:9092"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              Topic Prefix
            </label>
            <input
              type="text"
              value={config.kafka_topic_prefix || ''}
              onChange={(e) => onChange('kafka_topic_prefix', e.target.value)}
              placeholder="palantir-aip"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
            />
          </div>
        </div>
      )}

      {config.event_target === 'eventbridge' && (
        <div className="p-4 bg-gray-50 dark:bg-surface-700 rounded-lg space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            EventBridge Configuration
          </h4>
          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              Event Bus Name
            </label>
            <input
              type="text"
              value={config.eventbridge_bus_name || ''}
              onChange={(e) => onChange('eventbridge_bus_name', e.target.value)}
              placeholder="default"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-surface-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
            />
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Review step component
 */
function ReviewStep({ config, consent, onConsentChange }) {
  const enabledObjectTypes = (config.enabled_object_types || [])
    .map((id) => OBJECT_TYPES.find((t) => t.id === id)?.label)
    .filter(Boolean);

  const enabledEventTypes = (config.enabled_event_types || [])
    .map((id) => EVENT_TYPES.find((t) => t.id === id)?.label)
    .filter(Boolean);

  const syncFrequency = SYNC_FREQUENCIES.find((f) => f.value === config.sync_frequency);
  const eventTarget = EVENT_TARGETS.find((t) => t.id === config.event_target);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Review Configuration
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Please review your Palantir AIP integration settings before enabling.
        </p>
      </div>

      <div className="space-y-4">
        {/* Connection Summary */}
        <div className="p-4 bg-gray-50 dark:bg-surface-700 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
            <LinkIcon className="w-4 h-4" />
            Connection
          </h4>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Ontology URL</dt>
              <dd className="text-gray-900 dark:text-gray-100 font-mono text-xs truncate max-w-[60%]">
                {config.ontology_url || '-'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Foundry URL</dt>
              <dd className="text-gray-900 dark:text-gray-100 font-mono text-xs truncate max-w-[60%]">
                {config.foundry_url || '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Data Mapping Summary */}
        <div className="p-4 bg-gray-50 dark:bg-surface-700 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
            <Square3Stack3DIcon className="w-4 h-4" />
            Data Mapping
          </h4>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Object Types</dt>
              <dd className="text-gray-900 dark:text-gray-100">
                {enabledObjectTypes.length > 0 ? enabledObjectTypes.join(', ') : 'None selected'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Sync Frequency</dt>
              <dd className="text-gray-900 dark:text-gray-100">
                {syncFrequency?.label || '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Event Stream Summary */}
        <div className="p-4 bg-gray-50 dark:bg-surface-700 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 mb-3">
            <BoltIcon className="w-4 h-4" />
            Event Stream
          </h4>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Target</dt>
              <dd className="text-gray-900 dark:text-gray-100">
                {eventTarget?.label || 'Not configured'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Event Types</dt>
              <dd className="text-gray-900 dark:text-gray-100">
                {enabledEventTypes.length > 0 ? `${enabledEventTypes.length} selected` : 'None selected'}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Consent Checkbox */}
      <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => onConsentChange(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-aura-600 focus:ring-aura-500"
          />
          <span className="text-sm text-gray-600 dark:text-gray-400">
            I understand that enabling this integration will synchronize data between
            Project Aura and Palantir Foundry. I confirm that I have the necessary
            permissions to configure this integration.
          </span>
        </label>
      </div>
    </div>
  );
}

/**
 * Main PalantirIntegrationSettings component
 */
export function PalantirIntegrationSettings({
  isOpen,
  onClose,
  existingConfig = null,
  onSave,
  onSuccess,
  onError,
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [config, setConfig] = useState({
    ontology_url: '',
    foundry_url: '',
    environment_name: '',
    api_key: '',
    mtls_cert: '',
    mtls_key: '',
    enabled_object_types: ['threat_intel', 'asset_cmdb'],
    sync_frequency: 300,
    event_target: 'eventbridge',
    enabled_event_types: ['threat.new', 'threat.updated'],
    kafka_bootstrap_servers: '',
    kafka_topic_prefix: 'palantir-aip',
    eventbridge_bus_name: 'default',
    ...existingConfig,
  });
  const [errors, setErrors] = useState({});
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(existingConfig ? 1 : 0);
      setErrors({});
      setTestResult(null);
      setConsent(false);
    }
  }, [isOpen, existingConfig]);

  const handleConfigChange = useCallback((field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null }));
  }, []);

  const validateStep = useCallback((step) => {
    const newErrors = {};

    switch (step) {
      case 0: // Connection
        if (!config.ontology_url?.trim()) {
          newErrors.ontology_url = 'Ontology URL is required';
        }
        if (!config.foundry_url?.trim()) {
          newErrors.foundry_url = 'Foundry URL is required';
        }
        break;
      case 1: // Authentication
        if (!config.api_key?.trim()) {
          newErrors.api_key = 'API key is required';
        }
        break;
      default:
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [config]);

  const handleNext = useCallback(() => {
    if (!validateStep(currentStep)) {
      return;
    }
    setCurrentStep((prev) => Math.min(prev + 1, STEPS.length - 1));
  }, [currentStep, validateStep]);

  const handleBack = useCallback(() => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  }, []);

  const handleTest = useCallback(async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const result = await testConnection({
        ontology_url: config.ontology_url,
        api_key: config.api_key,
        mtls_cert: config.mtls_cert,
        mtls_key: config.mtls_key,
      });
      setTestResult(result);
    } catch (err) {
      setTestResult({
        success: false,
        error: err.message || 'Connection test failed',
      });
    } finally {
      setTesting(false);
    }
  }, [config]);

  const handleSave = useCallback(async () => {
    if (!consent) {
      return;
    }

    setSaving(true);
    try {
      await onSave?.(config);
      onSuccess?.('Palantir AIP integration enabled');
      onClose?.();
    } catch (err) {
      onError?.(err.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  }, [config, consent, onSave, onSuccess, onError, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
              <CubeIcon className="w-6 h-6 text-aura-600 dark:text-aura-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {existingConfig ? 'Edit Palantir AIP Integration' : 'Configure Palantir AIP Integration'}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Connect your Palantir Foundry instance
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="px-6 pt-6">
          <StepIndicator steps={STEPS} currentStep={currentStep} />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {currentStep === 0 && (
            <ConnectionStep
              config={config}
              onChange={handleConfigChange}
              errors={errors}
            />
          )}
          {currentStep === 1 && (
            <AuthenticationStep
              config={config}
              onChange={handleConfigChange}
              errors={errors}
              onTest={handleTest}
              testing={testing}
              testResult={testResult}
            />
          )}
          {currentStep === 2 && (
            <DataMappingStep
              config={config}
              onChange={handleConfigChange}
            />
          )}
          {currentStep === 3 && (
            <EventStreamStep
              config={config}
              onChange={handleConfigChange}
            />
          )}
          {currentStep === 4 && (
            <ReviewStep
              config={config}
              consent={consent}
              onConsentChange={setConsent}
            />
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <button
            onClick={currentStep === 0 ? onClose : handleBack}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-4 h-4" />
            {currentStep === 0 ? 'Cancel' : 'Back'}
          </button>

          {currentStep < STEPS.length - 1 ? (
            <button
              onClick={handleNext}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
            >
              Next
              <ArrowRightIcon className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={!consent || saving}
              className={`
                flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors
                ${!consent || saving
                  ? 'bg-gray-300 dark:bg-gray-600 text-gray-500 cursor-not-allowed'
                  : 'bg-green-600 text-white hover:bg-green-700'
                }
              `}
            >
              {saving ? (
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
              ) : (
                <CheckIcon className="w-4 h-4" />
              )}
              {saving ? 'Enabling...' : 'Enable Integration'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

PalantirIntegrationSettings.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  existingConfig: PropTypes.object,
  onSave: PropTypes.func,
  onSuccess: PropTypes.func,
  onError: PropTypes.func,
};

export default PalantirIntegrationSettings;
