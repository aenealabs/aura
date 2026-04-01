/**
 * ExplainabilityPage Component (ADR-068)
 *
 * Connected page wrapper that integrates ExplainabilityDashboard with the API layer.
 * Handles data fetching, contradiction resolution, and navigation.
 * Uses global toast system for consistent notifications.
 *
 * @module components/explainability/ExplainabilityPage
 */

import React, { useCallback } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import ExplainabilityDashboard from './ExplainabilityDashboard';
import { useToast } from '../ui/Toast';
import {
  getDecisions,
  getContradictions,
  getExplainabilityStats,
  resolveContradiction,
  dismissContradiction,
} from '../../services/explainabilityApi';

/**
 * ExplainabilityPage - Connected page component
 *
 * @param {Object} props
 * @param {string} [props.className] - Additional CSS classes
 */
function ExplainabilityPage({ className = '' }) {
  const navigate = useNavigate();
  const { toast } = useToast();

  // Handle back navigation
  const handleBack = useCallback(() => {
    navigate(-1);
  }, [navigate]);

  // Fetch decisions wrapper
  const fetchDecisions = useCallback(async (filters = {}) => {
    try {
      const data = await getDecisions(filters);
      return data;
    } catch (err) {
      console.error('Failed to fetch decisions:', err);
      toast.error('Failed to load decisions', {
        title: 'Error',
        action: { label: 'Retry', onClick: () => fetchDecisions(filters) },
      });
      return [];
    }
  }, [toast]);

  // Fetch contradictions wrapper
  const fetchContradictions = useCallback(async () => {
    try {
      return await getContradictions();
    } catch (err) {
      console.error('Failed to fetch contradictions:', err);
      toast.warning('Failed to load contradictions');
      return [];
    }
  }, [toast]);

  // Fetch stats wrapper
  const fetchStats = useCallback(async () => {
    try {
      return await getExplainabilityStats();
    } catch (err) {
      console.error('Failed to fetch stats:', err);
      // Don't show toast for stats - non-critical
      return null;
    }
  }, []);

  // Handle refresh with toast notification
  const handleRefresh = useCallback(async () => {
    try {
      // Fetch all data in parallel
      const [decisions, contradictions, stats] = await Promise.all([
        getDecisions(),
        getContradictions(),
        getExplainabilityStats(),
      ]);

      toast.success('Dashboard refreshed successfully', {
        title: 'Refreshed',
      });

      return { decisions, contradictions, stats };
    } catch (err) {
      console.error('Failed to refresh dashboard:', err);
      toast.error('Failed to refresh dashboard', {
        title: 'Refresh Failed',
        action: { label: 'Retry', onClick: handleRefresh },
      });
      throw err;
    }
  }, [toast]);

  // Handle resolve contradiction
  const handleResolveContradiction = useCallback(async (contradictionId, resolution) => {
    try {
      await resolveContradiction(contradictionId, resolution);
      toast.success('Contradiction resolved successfully', {
        title: 'Resolved',
      });
      return true;
    } catch (err) {
      console.error('Failed to resolve contradiction:', err);
      toast.error('Failed to resolve contradiction', {
        title: 'Error',
      });
      return false;
    }
  }, [toast]);

  // Handle dismiss contradiction
  const handleDismissContradiction = useCallback(async (contradictionId, reason) => {
    try {
      await dismissContradiction(contradictionId, reason);
      toast.info('Contradiction dismissed', {
        title: 'Dismissed',
      });
      return true;
    } catch (err) {
      console.error('Failed to dismiss contradiction:', err);
      toast.error('Failed to dismiss contradiction', {
        title: 'Error',
      });
      return false;
    }
  }, [toast]);

  return (
    <ExplainabilityDashboard
      fetchDecisions={fetchDecisions}
      fetchContradictions={fetchContradictions}
      fetchStats={fetchStats}
      onRefresh={handleRefresh}
      onResolveContradiction={handleResolveContradiction}
      onDismissContradiction={handleDismissContradiction}
      onBack={handleBack}
      className={className}
    />
  );
}

ExplainabilityPage.propTypes = {
  className: PropTypes.string,
};

export default ExplainabilityPage;
