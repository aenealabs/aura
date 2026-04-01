/**
 * Share Dashboard Modal Component
 *
 * Modal dialog for sharing dashboards with users, teams, or organizations.
 * Implements ADR-064 Phase 2 sharing & collaboration features.
 */

import { useState, useCallback, memo } from 'react';
import {
  XMarkIcon,
  ShareIcon,
  UserPlusIcon,
  BuildingOfficeIcon,
  TrashIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';

// Share permission levels
const PERMISSION_OPTIONS = [
  { value: 'view', label: 'View only', description: 'Can view but not edit' },
  { value: 'edit', label: 'Can edit', description: 'Can modify dashboard layout and widgets' },
];

// Mock data for user search (replace with actual API call)
const MOCK_USERS = [
  { id: 'user-001', name: 'Alice Johnson', email: 'alice@example.com', avatar: null },
  { id: 'user-002', name: 'Bob Smith', email: 'bob@example.com', avatar: null },
  { id: 'user-003', name: 'Carol Williams', email: 'carol@example.com', avatar: null },
  { id: 'user-004', name: 'David Brown', email: 'david@example.com', avatar: null },
];

// User search result item
const UserSearchItem = memo(function UserSearchItem({ user, onSelect }) {
  return (
    <button
      onClick={() => onSelect(user)}
      className="w-full flex items-center gap-3 px-3 py-2 hover:bg-surface-50 dark:hover:bg-surface-800 rounded-lg text-left transition-colors"
    >
      <div className="w-8 h-8 rounded-full bg-aura-100 dark:bg-aura-900/30 flex items-center justify-center text-aura-600 dark:text-aura-400 font-medium">
        {user.name.charAt(0)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
          {user.name}
        </p>
        <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
          {user.email}
        </p>
      </div>
    </button>
  );
});

// Share recipient row
const ShareRow = memo(function ShareRow({ share, onRemove, onPermissionChange }) {
  const isUser = !!share.userId;

  return (
    <div className="flex items-center justify-between px-3 py-2 bg-surface-50 dark:bg-surface-800 rounded-lg">
      <div className="flex items-center gap-3">
        {isUser ? (
          <div className="w-8 h-8 rounded-full bg-aura-100 dark:bg-aura-900/30 flex items-center justify-center text-aura-600 dark:text-aura-400 font-medium">
            {share.name?.charAt(0) || 'U'}
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-olive-100 dark:bg-olive-900/30 flex items-center justify-center">
            <BuildingOfficeIcon className="w-4 h-4 text-olive-600 dark:text-olive-400" />
          </div>
        )}
        <div className="min-w-0">
          <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
            {share.name || share.email || share.orgName || 'Unknown'}
          </p>
          {share.email && (
            <p className="text-xs text-surface-500 dark:text-surface-400 truncate">
              {share.email}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={share.permission}
          onChange={(e) => onPermissionChange(share.id, e.target.value)}
          className="text-xs px-2 py-1 rounded border border-surface-200 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-700 dark:text-surface-300"
        >
          {PERMISSION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          onClick={() => onRemove(share.id)}
          className="p-1 rounded text-surface-400 hover:text-critical-500 hover:bg-critical-50 dark:hover:bg-critical-900/20 transition-colors"
          title="Remove access"
        >
          <TrashIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
});

// Main Share Dashboard Modal
export default function ShareDashboardModal({
  dashboard,
  isOpen,
  onClose,
  onShare,
  onRevoke,
  existingShares = [],
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPermission, setSelectedPermission] = useState('view');
  const [pendingShares, setPendingShares] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);

  // Filter users based on search
  const filteredUsers = searchQuery.trim()
    ? MOCK_USERS.filter(
        (user) =>
          user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          user.email.toLowerCase().includes(searchQuery.toLowerCase())
      ).filter(
        // Exclude already shared users
        (user) =>
          !existingShares.some((s) => s.userId === user.id) &&
          !pendingShares.some((s) => s.userId === user.id)
      )
    : [];

  // Add user to pending shares
  const handleSelectUser = useCallback((user) => {
    setPendingShares((prev) => [
      ...prev,
      {
        id: `pending-${user.id}`,
        userId: user.id,
        name: user.name,
        email: user.email,
        permission: selectedPermission,
      },
    ]);
    setSearchQuery('');
  }, [selectedPermission]);

  // Remove from pending shares
  const handleRemovePending = useCallback((shareId) => {
    setPendingShares((prev) => prev.filter((s) => s.id !== shareId));
  }, []);

  // Change permission for pending share
  const handlePendingPermissionChange = useCallback((shareId, permission) => {
    setPendingShares((prev) =>
      prev.map((s) => (s.id === shareId ? { ...s, permission } : s))
    );
  }, []);

  // Handle share submission
  const handleShare = useCallback(async () => {
    if (pendingShares.length === 0) return;

    setIsLoading(true);
    setError(null);

    try {
      // Call onShare for each pending share
      for (const share of pendingShares) {
        await onShare({
          dashboardId: dashboard.dashboard_id,
          userId: share.userId,
          permission: share.permission,
        });
      }

      setSuccessMessage(`Shared with ${pendingShares.length} user(s)`);
      setPendingShares([]);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to share dashboard');
    } finally {
      setIsLoading(false);
    }
  }, [pendingShares, dashboard, onShare]);

  // Revoke existing share
  const handleRevoke = useCallback(async (shareId, userId) => {
    setIsLoading(true);
    setError(null);

    try {
      await onRevoke({
        dashboardId: dashboard.dashboard_id,
        userId,
      });
      setSuccessMessage('Access revoked');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to revoke access');
    } finally {
      setIsLoading(false);
    }
  }, [dashboard, onRevoke]);

  // Copy share link
  const handleCopyLink = useCallback(() => {
    const shareUrl = `${window.location.origin}/dashboard/${dashboard.dashboard_id}`;
    navigator.clipboard.writeText(shareUrl);
    setLinkCopied(true);
    setTimeout(() => setLinkCopied(false), 2000);
  }, [dashboard]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="bg-white dark:bg-surface-900 rounded-xl shadow-xl max-w-md w-full max-h-[90vh] overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-surface-200 dark:border-surface-700">
            <div className="flex items-center gap-2">
              <ShareIcon className="w-5 h-5 text-aura-500" />
              <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                Share Dashboard
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-500 transition-colors"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(90vh-120px)]">
            {/* Dashboard info */}
            <div className="px-3 py-2 bg-surface-50 dark:bg-surface-800 rounded-lg">
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                {dashboard.name}
              </p>
              {dashboard.description && (
                <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                  {dashboard.description}
                </p>
              )}
            </div>

            {/* Copy link */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyLink}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 border border-surface-200 dark:border-surface-700 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-800 transition-colors"
              >
                {linkCopied ? (
                  <>
                    <CheckIcon className="w-4 h-4 text-olive-500" />
                    <span className="text-sm text-olive-600 dark:text-olive-400">
                      Link copied!
                    </span>
                  </>
                ) : (
                  <>
                    <ClipboardDocumentIcon className="w-4 h-4 text-surface-500" />
                    <span className="text-sm text-surface-600 dark:text-surface-400">
                      Copy link
                    </span>
                  </>
                )}
              </button>
            </div>

            {/* User search */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                Add people
              </label>
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <UserPlusIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                  <input
                    type="text"
                    placeholder="Search by name or email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500/20 focus:border-aura-500 text-sm"
                  />
                </div>
                <select
                  value={selectedPermission}
                  onChange={(e) => setSelectedPermission(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300 text-sm"
                >
                  {PERMISSION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Search results */}
              {filteredUsers.length > 0 && (
                <div className="border border-surface-200 dark:border-surface-700 rounded-lg divide-y divide-surface-200 dark:divide-surface-700 overflow-hidden">
                  {filteredUsers.map((user) => (
                    <UserSearchItem
                      key={user.id}
                      user={user}
                      onSelect={handleSelectUser}
                    />
                  ))}
                </div>
              )}

              {searchQuery && filteredUsers.length === 0 && (
                <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-2">
                  No users found
                </p>
              )}
            </div>

            {/* Pending shares */}
            {pendingShares.length > 0 && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                  Pending invites ({pendingShares.length})
                </label>
                <div className="space-y-2">
                  {pendingShares.map((share) => (
                    <ShareRow
                      key={share.id}
                      share={share}
                      onRemove={handleRemovePending}
                      onPermissionChange={handlePendingPermissionChange}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Existing shares */}
            {existingShares.length > 0 && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                  People with access ({existingShares.length})
                </label>
                <div className="space-y-2">
                  {existingShares.map((share) => (
                    <ShareRow
                      key={share.id}
                      share={share}
                      onRemove={(id) => handleRevoke(id, share.userId)}
                      onPermissionChange={() => {
                        // Permission change for existing shares would need API call
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Error message */}
            {error && (
              <div className="flex items-center gap-2 px-3 py-2 bg-critical-50 dark:bg-critical-900/20 rounded-lg">
                <ExclamationCircleIcon className="w-4 h-4 text-critical-500" />
                <p className="text-sm text-critical-600 dark:text-critical-400">
                  {error}
                </p>
              </div>
            )}

            {/* Success message */}
            {successMessage && (
              <div className="flex items-center gap-2 px-3 py-2 bg-olive-50 dark:bg-olive-900/20 rounded-lg">
                <CheckIcon className="w-4 h-4 text-olive-500" />
                <p className="text-sm text-olive-600 dark:text-olive-400">
                  {successMessage}
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-surface-200 dark:border-surface-700">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleShare}
              disabled={pendingShares.length === 0 || isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-aura-600 hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {isLoading ? 'Sharing...' : 'Share'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
