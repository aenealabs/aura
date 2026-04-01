/**
 * Project Aura - Invite Review Step
 *
 * Step 3 of the Team Invite Wizard.
 * Review invitations and personalize message.
 */

import { useState, useCallback } from 'react';
import {
  ShieldCheckIcon,
  UserIcon,
  EyeIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline';

const ROLE_ICONS = {
  admin: ShieldCheckIcon,
  developer: UserIcon,
  viewer: EyeIcon,
};

const ROLE_COLORS = {
  admin: 'text-critical-600 dark:text-critical-400 bg-critical-50 dark:bg-critical-900/20',
  developer: 'text-aura-600 dark:text-aura-400 bg-aura-50 dark:bg-aura-900/20',
  viewer: 'text-surface-600 dark:text-surface-400 bg-surface-100 dark:bg-surface-700',
};

const DEFAULT_MESSAGE = `Hi there,

I'd like to invite you to join our organization on Project Aura. You'll be able to collaborate on security reviews, monitor vulnerabilities, and help approve patches.

Looking forward to having you on the team!`;

const InviteReviewStep = ({
  invitees,
  message,
  onMessageChange,
  onSend,
  onBack,
  isSending,
}) => {
  const [customMessage, setCustomMessage] = useState(message || DEFAULT_MESSAGE);

  const handleMessageChange = useCallback(
    (e) => {
      const newMessage = e.target.value;
      setCustomMessage(newMessage);
      onMessageChange(newMessage);
    },
    [onMessageChange]
  );

  const handleSend = useCallback(() => {
    onSend(customMessage);
  }, [onSend, customMessage]);

  // Group invitees by role
  const groupedByRole = invitees.reduce((acc, inv) => {
    if (!acc[inv.role]) {
      acc[inv.role] = [];
    }
    acc[inv.role].push(inv);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Review &amp; send
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Review your invitations and customize the welcome message.
        </p>
      </div>

      {/* Invitees summary */}
      <div className="bg-surface-50 dark:bg-surface-800/50 rounded-lg p-4">
        <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-3">
          Invitations ({invitees.length})
        </h3>

        <div className="space-y-4">
          {Object.entries(groupedByRole).map(([role, members]) => {
            const RoleIcon = ROLE_ICONS[role] || UserIcon;
            const colorClass = ROLE_COLORS[role] || ROLE_COLORS.developer;

            return (
              <div key={role}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded ${colorClass}`}>
                    <RoleIcon className="w-3.5 h-3.5" />
                    {role.charAt(0).toUpperCase() + role.slice(1)}
                  </span>
                  <span className="text-xs text-surface-500">
                    ({members.length})
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {members.map((inv) => (
                    <span
                      key={inv.email}
                      className="text-xs text-surface-600 dark:text-surface-400 bg-white dark:bg-surface-700 px-2 py-1 rounded border border-surface-200 dark:border-surface-600"
                    >
                      {inv.email}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Custom message */}
      <div className="space-y-2">
        <label
          htmlFor="invite-message"
          className="block text-sm font-medium text-surface-700 dark:text-surface-300"
        >
          Personal message (optional)
        </label>
        <textarea
          id="invite-message"
          value={customMessage}
          onChange={handleMessageChange}
          rows={5}
          className="w-full px-3 py-2 text-sm bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 resize-none"
          placeholder="Add a personal note to your invitation..."
        />
        <p className="text-xs text-surface-500 dark:text-surface-400">
          This message will be included in the invitation email.
        </p>
      </div>

      {/* Preview */}
      <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 overflow-hidden">
        <div className="px-4 py-2 bg-surface-50 dark:bg-surface-700/50 border-b border-surface-200 dark:border-surface-700">
          <span className="text-xs font-medium text-surface-500 dark:text-surface-400">
            Email Preview
          </span>
        </div>
        <div className="p-4">
          <p className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-2">
            You&apos;re invited to join Project Aura
          </p>
          <div className="text-sm text-surface-600 dark:text-surface-400 whitespace-pre-line">
            {customMessage}
          </div>
          <div className="mt-4 pt-4 border-t border-surface-200 dark:border-surface-700">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-aura-600 text-white text-sm font-medium rounded-lg">
              Accept Invitation
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4 border-t border-surface-200 dark:border-surface-700">
        <button
          onClick={onBack}
          disabled={isSending}
          className="px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-800 dark:hover:text-surface-200 font-medium transition-colors disabled:opacity-50"
        >
          Back
        </button>
        <button
          onClick={handleSend}
          disabled={isSending}
          className="inline-flex items-center gap-2 px-4 py-2 bg-aura-600 hover:bg-aura-700 disabled:bg-aura-400 text-white font-medium rounded-lg transition-colors"
        >
          {isSending ? (
            <>
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Sending...
            </>
          ) : (
            <>
              <PaperAirplaneIcon className="w-4 h-4" />
              Send Invitations
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default InviteReviewStep;
