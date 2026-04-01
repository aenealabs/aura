/**
 * Project Aura - Role Assignment Step
 *
 * Step 2 of the Team Invite Wizard.
 * Assign roles to each invitee.
 */

import { useCallback } from 'react';
import {
  ShieldCheckIcon,
  UserIcon,
  EyeIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';

const ROLES = [
  {
    id: 'admin',
    name: 'Admin',
    description: 'Full access to all settings and features',
    icon: ShieldCheckIcon,
    color: 'text-critical-500 dark:text-critical-400',
    bgColor: 'bg-critical-50 dark:bg-critical-900/20',
  },
  {
    id: 'developer',
    name: 'Developer',
    description: 'Can view, edit, and approve patches',
    icon: UserIcon,
    color: 'text-aura-500 dark:text-aura-400',
    bgColor: 'bg-aura-50 dark:bg-aura-900/20',
  },
  {
    id: 'viewer',
    name: 'Viewer',
    description: 'Read-only access to dashboards',
    icon: EyeIcon,
    color: 'text-surface-500 dark:text-surface-400',
    bgColor: 'bg-surface-100 dark:bg-surface-700',
  },
];

const RoleAssignmentStep = ({ invitees, onInviteesChange, onNext, onBack }) => {
  const handleRoleChange = useCallback(
    (email, role) => {
      onInviteesChange(
        invitees.map((inv) =>
          inv.email === email ? { ...inv, role } : inv
        )
      );
    },
    [invitees, onInviteesChange]
  );

  const handleApplyToAll = useCallback(
    (role) => {
      onInviteesChange(invitees.map((inv) => ({ ...inv, role })));
    },
    [invitees, onInviteesChange]
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Assign roles
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Choose what each person can do in your organization.
        </p>
      </div>

      {/* Apply to all */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-surface-600 dark:text-surface-400">
          Apply to all:
        </span>
        {ROLES.map((role) => (
          <button
            key={role.id}
            onClick={() => handleApplyToAll(role.id)}
            className="px-2 py-1 text-xs font-medium text-surface-600 dark:text-surface-400 bg-surface-100 dark:bg-surface-700 hover:bg-surface-200 dark:hover:bg-surface-600 rounded transition-colors"
          >
            {role.name}
          </button>
        ))}
      </div>

      {/* Invitee list */}
      <div className="space-y-3">
        {invitees.map((invitee) => {
          const selectedRole = ROLES.find((r) => r.id === invitee.role) || ROLES[1];

          return (
            <div
              key={invitee.email}
              className="flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-800/50 rounded-lg border border-surface-200 dark:border-surface-700"
            >
              {/* Email */}
              <span className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                {invitee.email}
              </span>

              {/* Role selector */}
              <div className="relative">
                <select
                  value={invitee.role}
                  onChange={(e) => handleRoleChange(invitee.email, e.target.value)}
                  className="appearance-none pl-3 pr-8 py-1.5 text-sm bg-white dark:bg-surface-700 border border-surface-200 dark:border-surface-600 rounded-lg text-surface-900 dark:text-surface-100 cursor-pointer focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                >
                  {ROLES.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
                <ChevronDownIcon className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400 pointer-events-none" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Role descriptions */}
      <div className="bg-surface-50 dark:bg-surface-800/50 rounded-lg p-4">
        <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-3">
          Role permissions
        </h3>
        <div className="space-y-3">
          {ROLES.map((role) => (
            <div key={role.id} className="flex items-start gap-3">
              <div className={`p-1.5 rounded-lg ${role.bgColor}`}>
                <role.icon className={`w-4 h-4 ${role.color}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  {role.name}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  {role.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4 border-t border-surface-200 dark:border-surface-700">
        <button
          onClick={onBack}
          className="px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-800 dark:hover:text-surface-200 font-medium transition-colors"
        >
          Back
        </button>
        <button
          onClick={onNext}
          className="px-4 py-2 bg-aura-600 hover:bg-aura-700 text-white font-medium rounded-lg transition-colors"
        >
          Continue
        </button>
      </div>
    </div>
  );
};

export default RoleAssignmentStep;
