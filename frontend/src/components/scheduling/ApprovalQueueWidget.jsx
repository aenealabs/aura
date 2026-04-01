/**
 * Approval Queue Widget
 *
 * HITL pending approvals with expiration countdown and quick actions.
 * ADR-055 Phase 2: Timeline and HITL Integration
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ShieldExclamationIcon,
  ClockIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { useNavigate } from 'react-router-dom';
import { getPendingApprovals, approveRequest, rejectRequest } from '../../services/schedulingApi';

// Severity colors and labels
const SEVERITY_CONFIG = {
  CRITICAL: {
    color: 'critical',
    bgClass: 'bg-critical-50 dark:bg-critical-900/20',
    borderClass: 'border-critical-200 dark:border-critical-800',
    textClass: 'text-critical-700 dark:text-critical-300',
    badgeClass: 'bg-critical-100 dark:bg-critical-900/40 text-critical-700 dark:text-critical-300',
  },
  HIGH: {
    color: 'warning',
    bgClass: 'bg-warning-50 dark:bg-warning-900/20',
    borderClass: 'border-warning-200 dark:border-warning-800',
    textClass: 'text-warning-700 dark:text-warning-300',
    badgeClass: 'bg-warning-100 dark:bg-warning-900/40 text-warning-700 dark:text-warning-300',
  },
  MEDIUM: {
    color: 'info',
    bgClass: 'bg-aura-50 dark:bg-aura-900/20',
    borderClass: 'border-aura-200 dark:border-aura-800',
    textClass: 'text-aura-700 dark:text-aura-300',
    badgeClass: 'bg-aura-100 dark:bg-aura-900/40 text-aura-700 dark:text-aura-300',
  },
  LOW: {
    color: 'surface',
    bgClass: 'bg-surface-50 dark:bg-surface-800',
    borderClass: 'border-surface-200 dark:border-surface-700',
    textClass: 'text-surface-700 dark:text-surface-300',
    badgeClass: 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400',
  },
};

export default function ApprovalQueueWidget({ compact = false, onApprovalAction }) {
  const navigate = useNavigate();
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [processingIds, setProcessingIds] = useState(new Set());
  const [search, setSearch] = useState('');

  // Load pending approvals
  const loadApprovals = useCallback(async () => {
    try {
      const data = await getPendingApprovals({ limit: compact ? 5 : 20 });
      setApprovals(data.approvals || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load pending approvals:', err);
      setError(err.message || 'Failed to load approvals');
    } finally {
      setLoading(false);
    }
  }, [compact]);

  // Initial load
  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  // Auto-refresh every minute (for countdown updates)
  useEffect(() => {
    const interval = setInterval(() => {
      loadApprovals();
    }, 60000);

    return () => clearInterval(interval);
  }, [loadApprovals]);

  // Handle approve action
  const handleApprove = async (approvalId) => {
    setProcessingIds((prev) => new Set([...prev, approvalId]));
    try {
      await approveRequest(approvalId, 'Approved via scheduling dashboard');
      setApprovals((prev) => prev.filter((a) => a.approval_id !== approvalId));
      onApprovalAction?.();
    } catch (err) {
      console.error('Failed to approve:', err);
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(approvalId);
        return next;
      });
    }
  };

  // Handle reject action
  const handleReject = async (approvalId) => {
    setProcessingIds((prev) => new Set([...prev, approvalId]));
    try {
      await rejectRequest(approvalId, 'Rejected via scheduling dashboard');
      setApprovals((prev) => prev.filter((a) => a.approval_id !== approvalId));
      onApprovalAction?.();
    } catch (err) {
      console.error('Failed to reject:', err);
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(approvalId);
        return next;
      });
    }
  };

  // Navigate to full approval dashboard
  const goToApprovalDashboard = () => {
    navigate('/approvals');
  };

  // Filter approvals by search
  const filteredApprovals = approvals.filter((approval) => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    return (
      approval.patch_id?.toLowerCase().includes(searchLower) ||
      approval.vulnerability_id?.toLowerCase().includes(searchLower) ||
      approval.reviewer_email?.toLowerCase().includes(searchLower) ||
      approval.severity?.toLowerCase().includes(searchLower)
    );
  });

  // Group approvals by severity
  const groupedApprovals = filteredApprovals.reduce((acc, approval) => {
    const severity = approval.severity || 'MEDIUM';
    if (!acc[severity]) acc[severity] = [];
    acc[severity].push(approval);
    return acc;
  }, {});

  // Count by severity
  const severityCounts = {
    CRITICAL: groupedApprovals.CRITICAL?.length || 0,
    HIGH: groupedApprovals.HIGH?.length || 0,
    MEDIUM: groupedApprovals.MEDIUM?.length || 0,
    LOW: groupedApprovals.LOW?.length || 0,
  };

  const totalPending = filteredApprovals.length;

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-6">
        <div className="flex items-center justify-center gap-2">
          <ArrowPathIcon className="w-5 h-5 text-aura-600 animate-spin" />
          <span className="text-sm text-surface-500">Loading approvals...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-critical-50 dark:bg-critical-900/20 rounded-xl border border-critical-200 dark:border-critical-800 p-6">
        <div className="flex items-center gap-2 text-critical-700 dark:text-critical-300">
          <ExclamationTriangleIcon className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center gap-3">
          <ShieldExclamationIcon className="w-5 h-5 text-warning-500" />
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">
              HITL Approval Queue
            </h3>
            <p className="text-xs text-surface-500">
              {totalPending} pending {totalPending === 1 ? 'approval' : 'approvals'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadApprovals}
            className="p-1.5 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            <ArrowPathIcon className="w-4 h-4" />
          </button>
          {!compact && (
            <button
              onClick={goToApprovalDashboard}
              className="flex items-center gap-1 text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
            >
              View All
              <ChevronRightIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Search Bar */}
      {!compact && (
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="relative max-w-md" role="search">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-surface-400" aria-hidden="true" />
            <input
              type="text"
              placeholder="Search approvals..."
              aria-label="Search pending approvals"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:border-transparent"
            />
          </div>
        </div>
      )}

      {/* Severity Summary */}
      {!compact && totalPending > 0 && (
        <div className="grid grid-cols-4 gap-2 p-4 border-b border-surface-200 dark:border-surface-700">
          {Object.entries(severityCounts).map(([severity, count]) => {
            const config = SEVERITY_CONFIG[severity];
            return (
              <div
                key={severity}
                className={`text-center p-2 rounded-lg ${config.bgClass} ${config.borderClass} border`}
              >
                <p className={`text-lg font-bold ${config.textClass}`}>{count}</p>
                <p className="text-xs text-surface-500">{severity}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Approval List */}
      {totalPending === 0 ? (
        <div className="p-8 text-center">
          {search ? (
            <>
              <MagnifyingGlassIcon className="w-12 h-12 text-surface-400 mx-auto mb-3" />
              <p className="text-surface-500">No approvals match your search</p>
              <p className="text-xs text-surface-400 mt-1">
                Try adjusting your search terms
              </p>
            </>
          ) : (
            <>
              <CheckIcon className="w-12 h-12 text-success-400 mx-auto mb-3" />
              <p className="text-surface-500">No pending approvals</p>
              <p className="text-xs text-surface-400 mt-1">
                All HITL requests have been processed
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="divide-y divide-surface-100 dark:divide-surface-700 max-h-[500px] overflow-y-auto">
          {filteredApprovals.slice(0, compact ? 5 : 20).map((approval) => (
            <ApprovalItem
              key={approval.approval_id}
              approval={approval}
              onApprove={() => handleApprove(approval.approval_id)}
              onReject={() => handleReject(approval.approval_id)}
              isProcessing={processingIds.has(approval.approval_id)}
              compact={compact}
            />
          ))}
        </div>
      )}

      {/* View All Link (compact mode) */}
      {compact && totalPending > 5 && (
        <div className="p-3 border-t border-surface-200 dark:border-surface-700">
          <button
            onClick={goToApprovalDashboard}
            className="w-full text-center text-sm text-aura-600 dark:text-aura-400 hover:text-aura-700 dark:hover:text-aura-300"
          >
            View all {totalPending} pending approvals
          </button>
        </div>
      )}
    </div>
  );
}

// Individual Approval Item
function ApprovalItem({ approval, onApprove, onReject, isProcessing, compact }) {
  const config = SEVERITY_CONFIG[approval.severity] || SEVERITY_CONFIG.MEDIUM;
  const expiresAt = approval.expires_at ? new Date(approval.expires_at) : null;
  const timeRemaining = expiresAt ? getTimeRemaining(expiresAt) : null;
  const isExpiringSoon = timeRemaining && timeRemaining.totalMinutes < 60;

  return (
    <div className={`p-4 ${config.bgClass}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded ${config.badgeClass}`}>
              {approval.severity}
            </span>
            {approval.escalation_count > 0 && (
              <span className="text-xs font-medium px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">
                Escalated ×{approval.escalation_count}
              </span>
            )}
          </div>

          {/* Title */}
          <p className="font-medium text-surface-900 dark:text-surface-100 truncate">
            {approval.patch_id || approval.vulnerability_id || 'Approval Request'}
          </p>

          {/* Details */}
          {!compact && (
            <div className="mt-1 text-xs text-surface-500 space-y-0.5">
              {approval.vulnerability_id && (
                <p>Vulnerability: {approval.vulnerability_id}</p>
              )}
              {approval.reviewer_email && (
                <p>Reviewer: {approval.reviewer_email}</p>
              )}
            </div>
          )}

          {/* Expiration */}
          {timeRemaining && (
            <div
              className={`flex items-center gap-1 mt-2 text-xs ${
                isExpiringSoon
                  ? 'text-critical-600 dark:text-critical-400'
                  : 'text-surface-500'
              }`}
            >
              <ClockIcon className="w-3 h-3" />
              <span>
                {isExpiringSoon ? 'Expiring soon: ' : 'Expires in '}
                {timeRemaining.display}
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onApprove}
            disabled={isProcessing}
            className="p-2 text-success-600 hover:text-success-700 dark:text-success-400 dark:hover:text-success-300 bg-success-50 dark:bg-success-900/20 hover:bg-success-100 dark:hover:bg-success-900/40 rounded-lg transition-colors disabled:opacity-50"
            title="Approve"
          >
            <CheckIcon className="w-4 h-4" />
          </button>
          <button
            onClick={onReject}
            disabled={isProcessing}
            className="p-2 text-critical-600 hover:text-critical-700 dark:text-critical-400 dark:hover:text-critical-300 bg-critical-50 dark:bg-critical-900/20 hover:bg-critical-100 dark:hover:bg-critical-900/40 rounded-lg transition-colors disabled:opacity-50"
            title="Reject"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// Calculate time remaining until expiration
function getTimeRemaining(expiresAt) {
  const now = new Date();
  const diff = expiresAt.getTime() - now.getTime();

  if (diff <= 0) {
    return { totalMinutes: 0, display: 'Expired' };
  }

  const totalMinutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  let display;
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    display = `${days}d ${hours % 24}h`;
  } else if (hours > 0) {
    display = `${hours}h ${minutes}m`;
  } else {
    display = `${minutes}m`;
  }

  return { totalMinutes, display };
}
