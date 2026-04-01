/**
 * Group to Role Mapping Section Component
 *
 * Maps IdP groups to Aura roles for RBAC.
 * Used in Step 4 of the IdP configuration wizard.
 *
 * ADR-054: Multi-IdP Authentication
 */

import { useState } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ArrowRightIcon,
  InformationCircleIcon,
  UserGroupIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { AURA_ROLES } from '../../../services/identityProviderApi';

// Role descriptions for help text
const ROLE_DESCRIPTIONS = {
  admin: 'Full system access, user management, and configuration',
  'security-engineer': 'Security scanning, vulnerability management, and remediation',
  'devops-engineer': 'Infrastructure management, deployments, and pipelines',
  developer: 'Code access, sandbox environments, and agent interactions',
  analyst: 'View metrics, reports, and read-only access to most features',
  viewer: 'Basic read-only access to dashboards and reports',
};

export default function GroupRoleMappingSection({
  mappings,
  onChange,
  defaultRole,
  onDefaultRoleChange,
}) {
  const [newGroup, setNewGroup] = useState('');
  const [newRole, setNewRole] = useState('');

  const handleAddMapping = () => {
    if (!newGroup.trim() || !newRole) return;

    // Check if group already exists
    const existingIndex = mappings.findIndex(
      (m) => m.group.toLowerCase() === newGroup.toLowerCase()
    );
    if (existingIndex >= 0) {
      // Update existing mapping
      const updated = [...mappings];
      updated[existingIndex] = { group: newGroup.trim(), role: newRole };
      onChange(updated);
    } else {
      // Add new mapping
      onChange([...mappings, { group: newGroup.trim(), role: newRole }]);
    }

    setNewGroup('');
    setNewRole('');
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

  const getRoleLabel = (roleId) => {
    const role = AURA_ROLES.find((r) => r.id === roleId);
    return role?.label || roleId;
  };

  const inputClass =
    'w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500 text-sm';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
          Group to Role Mapping
        </h3>
        <p className="text-sm text-surface-500 dark:text-surface-400">
          Map your identity provider groups to Aura roles for access control.
        </p>
      </div>

      {/* Info Box */}
      <div className="flex items-start gap-3 p-4 bg-aura-50 dark:bg-aura-900/20 rounded-lg border border-aura-200/50 dark:border-aura-800/50">
        <InformationCircleIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-aura-700 dark:text-aura-300">
          <p className="font-medium mb-1">How group mapping works</p>
          <p>
            When a user signs in, Aura checks their group memberships from the identity
            provider and assigns the corresponding Aura role. If a user belongs to
            multiple mapped groups, they receive the highest-privilege role.
          </p>
        </div>
      </div>

      {/* Default Role */}
      <div className="bg-surface-50 dark:bg-surface-700/50 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-surface-200 dark:bg-surface-600 rounded-lg">
              <ShieldCheckIcon className="h-5 w-5 text-surface-600 dark:text-surface-300" />
            </div>
            <div>
              <h4 className="font-medium text-surface-900 dark:text-surface-100">
                Default Role
              </h4>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Assigned to users without any matching group mappings
              </p>
            </div>
          </div>
          <select
            value={defaultRole}
            onChange={(e) => onDefaultRoleChange(e.target.value)}
            className="px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500 text-sm"
          >
            {AURA_ROLES.map((role) => (
              <option key={role.id} value={role.id}>
                {role.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Current Mappings */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100">
          Group Mappings ({mappings.length})
        </h4>

        {mappings.length === 0 ? (
          <div className="text-center py-6 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
            <UserGroupIcon className="h-8 w-8 text-surface-400 mx-auto mb-2" />
            <p className="text-sm text-surface-500 dark:text-surface-400">
              No group mappings configured.
            </p>
            <p className="text-xs text-surface-400 dark:text-surface-500">
              All users will receive the default role.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {mappings.map((mapping, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg group"
              >
                {/* Group Name */}
                <div className="flex-1">
                  <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                    IdP Group
                  </label>
                  <input
                    type="text"
                    value={mapping.group}
                    onChange={(e) =>
                      handleUpdateMapping(index, 'group', e.target.value)
                    }
                    className={inputClass}
                    placeholder="e.g., Engineering"
                  />
                </div>

                {/* Arrow */}
                <ArrowRightIcon className="h-5 w-5 text-surface-400 flex-shrink-0 mt-5" />

                {/* Aura Role */}
                <div className="flex-1">
                  <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
                    Aura Role
                  </label>
                  <select
                    value={mapping.role}
                    onChange={(e) =>
                      handleUpdateMapping(index, 'role', e.target.value)
                    }
                    className={inputClass}
                  >
                    {AURA_ROLES.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.label}
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
          Add Group Mapping
        </h4>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
              IdP Group Name
            </label>
            <input
              type="text"
              value={newGroup}
              onChange={(e) => setNewGroup(e.target.value)}
              placeholder="e.g., CN=Developers,OU=Groups,DC=company,DC=com"
              className={inputClass}
            />
          </div>

          <ArrowRightIcon className="h-5 w-5 text-surface-400 flex-shrink-0 mb-2.5" />

          <div className="flex-1">
            <label className="block text-xs text-surface-500 dark:text-surface-400 mb-1">
              Aura Role
            </label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className={inputClass}
            >
              <option value="">Select role...</option>
              {AURA_ROLES.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleAddMapping}
            disabled={!newGroup.trim() || !newRole}
            className="flex items-center gap-2 px-4 py-2 bg-aura-600 text-white font-medium rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Add
          </button>
        </div>
      </div>

      {/* Role Reference */}
      <div className="border-t border-surface-200 dark:border-surface-700 pt-4">
        <h4 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-3">
          Role Reference
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {AURA_ROLES.map((role) => (
            <div
              key={role.id}
              className="text-sm p-2 bg-surface-50 dark:bg-surface-700/50 rounded"
            >
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {role.label}
              </span>
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                {ROLE_DESCRIPTIONS[role.id]}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
