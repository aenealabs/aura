/**
 * Attribute Mapping Section Component
 *
 * Maps IdP attributes to Aura user profile fields.
 * Used in Step 3 of the IdP configuration wizard.
 *
 * ADR-054: Multi-IdP Authentication
 */

import { useState } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ArrowRightIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { AURA_USER_FIELDS } from '../../../services/identityProviderApi';

// Common IdP attribute suggestions
const COMMON_IDP_ATTRIBUTES = [
  { value: 'email', label: 'email' },
  { value: 'mail', label: 'mail (LDAP)' },
  { value: 'given_name', label: 'given_name' },
  { value: 'givenName', label: 'givenName (LDAP)' },
  { value: 'family_name', label: 'family_name' },
  { value: 'sn', label: 'sn (LDAP surname)' },
  { value: 'displayName', label: 'displayName' },
  { value: 'name', label: 'name' },
  { value: 'preferred_username', label: 'preferred_username' },
  { value: 'sub', label: 'sub (OIDC subject)' },
  { value: 'phone_number', label: 'phone_number' },
  { value: 'telephoneNumber', label: 'telephoneNumber (LDAP)' },
  { value: 'department', label: 'department' },
  { value: 'title', label: 'title' },
  { value: 'memberOf', label: 'memberOf (LDAP groups)' },
  { value: 'groups', label: 'groups' },
];

export default function AttributeMappingSection({ mappings, onChange }) {
  const [newSource, setNewSource] = useState('');
  const [newTarget, setNewTarget] = useState('');

  const handleAddMapping = () => {
    if (!newSource.trim() || !newTarget) return;

    // Check if target already has a mapping
    const existingIndex = mappings.findIndex((m) => m.target === newTarget);
    if (existingIndex >= 0) {
      // Update existing mapping
      const updated = [...mappings];
      updated[existingIndex] = { source: newSource.trim(), target: newTarget };
      onChange(updated);
    } else {
      // Add new mapping
      onChange([...mappings, { source: newSource.trim(), target: newTarget }]);
    }

    setNewSource('');
    setNewTarget('');
  };

  const handleRemoveMapping = (index) => {
    const updated = mappings.filter((_, i) => i !== index);
    onChange(updated);
  };

  const handleUpdateMapping = (index, field, value) => {
    const updated = [...mappings];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  const getTargetLabel = (targetId) => {
    const field = AURA_USER_FIELDS.find((f) => f.id === targetId);
    return field?.label || targetId;
  };

  const isTargetMapped = (targetId) => {
    return mappings.some((m) => m.target === targetId);
  };

  const availableTargets = AURA_USER_FIELDS.filter(
    (field) => !isTargetMapped(field.id)
  );

  const inputClass =
    'w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500 text-sm';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
          Attribute Mapping
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Map attributes from your identity provider to Aura user profile fields.
        </p>
      </div>

      {/* Info Box */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 rounded-lg border border-aura-200/50 dark:border-aura-800/50">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-aura-700 dark:text-aura-300">
          <p className="font-medium mb-1">How attribute mapping works</p>
          <p>
            When a user signs in, Aura reads the attributes from your identity provider
            and maps them to the corresponding user profile fields. The email attribute
            is required for user identification.
          </p>
        </div>
      </div>

      {/* Current Mappings */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100">
          Current Mappings ({mappings.length})
        </h4>

        {mappings.length === 0 ? (
          <p className="text-sm text-surface-500 dark:text-surface-400 italic py-4 text-center">
            No attribute mappings configured. Add mappings below.
          </p>
        ) : (
          <div className="space-y-2">
            {mappings.map((mapping, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg group"
              >
                {/* Source Attribute */}
                <div className="flex-1">
                  <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                    IdP Attribute
                  </label>
                  <input
                    type="text"
                    value={mapping.source}
                    onChange={(e) =>
                      handleUpdateMapping(index, 'source', e.target.value)
                    }
                    list="idp-attributes"
                    className={inputClass}
                    placeholder="e.g., email"
                  />
                </div>

                {/* Arrow */}
                <ArrowRightIcon className="h-5 w-5 text-surface-400 flex-shrink-0 mt-5" />

                {/* Target Field */}
                <div className="flex-1">
                  <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                    Aura Field
                  </label>
                  <select
                    value={mapping.target}
                    onChange={(e) =>
                      handleUpdateMapping(index, 'target', e.target.value)
                    }
                    className={inputClass}
                  >
                    <option value={mapping.target}>{getTargetLabel(mapping.target)}</option>
                    {AURA_USER_FIELDS.filter(
                      (f) => f.id !== mapping.target && !isTargetMapped(f.id)
                    ).map((field) => (
                      <option key={field.id} value={field.id}>
                        {field.label}
                        {field.required && ' *'}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Delete Button */}
                <button
                  onClick={() => handleRemoveMapping(index)}
                  className="p-2 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors opacity-0 group-hover:opacity-100 mt-5"
                  title="Remove mapping"
                >
                  <TrashIcon className="h-5 w-5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add New Mapping */}
      <div className="border-t border-surface-200 dark:border-surface-700 pt-4">
        <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-3">
          Add Mapping
        </h4>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
              IdP Attribute
            </label>
            <input
              type="text"
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              list="idp-attributes"
              placeholder="Type or select attribute"
              className={inputClass}
            />
            <datalist id="idp-attributes">
              {COMMON_IDP_ATTRIBUTES.map((attr) => (
                <option key={attr.value} value={attr.value}>
                  {attr.label}
                </option>
              ))}
            </datalist>
          </div>

          <ArrowRightIcon className="h-5 w-5 text-surface-400 flex-shrink-0 mb-2.5" />

          <div className="flex-1">
            <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
              Aura Field
            </label>
            <select
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              className={inputClass}
            >
              <option value="">Select field...</option>
              {availableTargets.map((field) => (
                <option key={field.id} value={field.id}>
                  {field.label}
                  {field.required && ' *'}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleAddMapping}
            disabled={!newSource.trim() || !newTarget}
            className="flex items-center gap-2 px-4 py-2 bg-aura-600 text-white font-medium rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Add
          </button>
        </div>
      </div>

      {/* Required Fields Indicator */}
      <div className="text-xs text-surface-500 dark:text-surface-400">
        <span className="font-medium">Required fields:</span>{' '}
        {AURA_USER_FIELDS.filter((f) => f.required)
          .map((f) => f.label)
          .join(', ')}
      </div>
    </div>
  );
}
