/**
 * Project Aura - Invite Completion Step
 *
 * Step 4 of the Team Invite Wizard.
 * Shows success message and shareable link.
 */

import { useState, useCallback } from 'react';
import {
  CheckCircleIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';

const InviteCompletionStep = ({ invitees, inviteLink, onClose, onAddMore }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyLink = useCallback(async () => {
    if (inviteLink) {
      try {
        await navigator.clipboard.writeText(inviteLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    }
  }, [inviteLink]);

  return (
    <div className="space-y-6 text-center">
      {/* Success icon */}
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-olive-100 dark:bg-olive-900/30">
        <CheckCircleIcon className="w-8 h-8 text-olive-600 dark:text-olive-400" />
      </div>

      {/* Message */}
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Invitations sent!
        </h2>
        <p className="mt-2 text-sm text-surface-600 dark:text-surface-400">
          {invitees.length} invitation{invitees.length !== 1 ? 's' : ''} sent
          successfully. Your team members will receive an email shortly.
        </p>
      </div>

      {/* Invited list */}
      <div className="text-left bg-surface-50 dark:bg-surface-800/50 rounded-lg p-4">
        <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-2">
          Invited
        </h3>
        <div className="space-y-1 max-h-32 overflow-y-auto">
          {invitees.map((inv) => (
            <div
              key={inv.email}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-surface-600 dark:text-surface-400">
                {inv.email}
              </span>
              <span className="text-xs text-surface-500 dark:text-surface-400 capitalize">
                {inv.role}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Shareable link */}
      {inviteLink && (
        <div className="text-left bg-surface-50 dark:bg-surface-800/50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-surface-900 dark:text-surface-100 mb-2">
            <LinkIcon className="inline w-4 h-4 mr-1" />
            Shareable invite link
          </h3>
          <p className="text-xs text-surface-500 dark:text-surface-400 mb-2">
            Anyone with this link can request to join your organization.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={inviteLink}
              className="flex-1 px-3 py-2 text-sm bg-white dark:bg-surface-700 border border-surface-200 dark:border-surface-600 rounded-lg text-surface-600 dark:text-surface-400"
            />
            <button
              onClick={handleCopyLink}
              className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-aura-600 dark:text-aura-400 bg-aura-50 dark:bg-aura-900/20 hover:bg-aura-100 dark:hover:bg-aura-900/30 rounded-lg transition-colors"
            >
              {copied ? (
                <>
                  <ClipboardDocumentCheckIcon className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <ClipboardDocumentIcon className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-center gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
        <button
          onClick={onAddMore}
          className="px-4 py-2 text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300 font-medium transition-colors"
        >
          Invite more people
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2 bg-aura-600 hover:bg-aura-700 text-white font-medium rounded-lg transition-colors"
        >
          Done
        </button>
      </div>
    </div>
  );
};

export default InviteCompletionStep;
