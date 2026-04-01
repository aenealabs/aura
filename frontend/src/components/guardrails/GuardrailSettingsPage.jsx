/**
 * GuardrailSettingsPage Component (ADR-069)
 *
 * Connected page wrapper that integrates GuardrailSettings with the API layer.
 * Handles data fetching, saving, and navigation.
 * Uses global toast system for consistent notifications.
 *
 * @module components/guardrails/GuardrailSettingsPage
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import GuardrailSettings from './GuardrailSettings';
import { useToast } from '../ui/Toast';
import {
  getGuardrailConfig,
  updateGuardrailConfig,
  getGuardrailMetrics,
  getImpactPreview,
  getComplianceProfiles,
} from '../../services/guardrailsApi';

/**
 * GuardrailSettingsPage - Connected page component
 *
 * @param {Object} props
 * @param {string} [props.className] - Additional CSS classes
 */
function GuardrailSettingsPage({ className = '' }) {
  const navigate = useNavigate();
  const { toast } = useToast();

  // State
  const [initialSettings, setInitialSettings] = useState(null);
  const [complianceProfiles, setComplianceProfiles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load initial data
  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      setError(null);
      try {
        const [config, profiles] = await Promise.all([
          getGuardrailConfig(),
          getComplianceProfiles(),
        ]);
        setInitialSettings(config);
        setComplianceProfiles(profiles);
      } catch (err) {
        console.error('Failed to load guardrail config:', err);
        setError('Failed to load guardrail configuration. Please try again.');
        toast.error('Failed to load configuration', { title: 'Error' });
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [toast]);

  // Handle save
  const handleSave = useCallback(async (config, justification) => {
    try {
      const updated = await updateGuardrailConfig(config, justification);
      setInitialSettings(updated);
      toast.success('Settings saved successfully', { title: 'Saved' });
      return updated;
    } catch (err) {
      console.error('Failed to save config:', err);
      toast.error('Failed to save settings', { title: 'Error' });
      throw err;
    }
  }, [toast]);

  // Handle back navigation
  const handleBack = useCallback(() => {
    navigate(-1);
  }, [navigate]);

  // Fetch metrics wrapper
  const fetchMetrics = useCallback(async (timeRange) => {
    try {
      return await getGuardrailMetrics(timeRange);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
      toast.warning('Failed to load metrics');
      return null;
    }
  }, [toast]);

  // Fetch impact preview wrapper
  const fetchImpactPreview = useCallback(async (proposedChanges) => {
    try {
      return await getImpactPreview(proposedChanges);
    } catch (err) {
      console.error('Failed to fetch impact preview:', err);
      toast.warning('Failed to load impact preview');
      return null;
    }
  }, [toast]);

  // Loading state
  if (isLoading) {
    return (
      <div className={`min-h-screen bg-surface-50 dark:bg-surface-900 flex items-center justify-center ${className}`}>
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-aura-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-surface-600 dark:text-surface-400">Loading guardrail settings...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !initialSettings) {
    return (
      <div className={`min-h-screen bg-surface-50 dark:bg-surface-900 flex items-center justify-center ${className}`}>
        <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-8 max-w-md text-center">
          <div className="w-12 h-12 rounded-full bg-critical-100 dark:bg-critical-900/30 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-critical-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-2">
            Failed to Load Settings
          </h2>
          <p className="text-surface-600 dark:text-surface-400 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <GuardrailSettings
      initialSettings={initialSettings}
      onSave={handleSave}
      onBack={handleBack}
      fetchMetrics={fetchMetrics}
      fetchImpactPreview={fetchImpactPreview}
      complianceProfiles={complianceProfiles}
      className={className}
    />
  );
}

GuardrailSettingsPage.propTypes = {
  className: PropTypes.string,
};

export default GuardrailSettingsPage;
