/**
 * License Compliance Widget
 *
 * Displays license distribution as a donut chart with compliance
 * status and violation counts.
 *
 * Per ADR-076: Widget ID 'supply-chain-license-compliance', Category: COMPLIANCE
 *
 * @module components/dashboard/widgets/LicenseComplianceWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ScaleIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/solid';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { getLicenseSummary } from '../../../services/supplyChainApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// License type colors
const LICENSE_COLORS = {
  'MIT': '#10B981',           // Green - permissive
  'Apache-2.0': '#3B82F6',    // Blue - permissive
  'BSD-3-Clause': '#06B6D4',  // Cyan - permissive
  'ISC': '#8B5CF6',           // Purple - permissive
  'GPL-3.0': '#F59E0B',       // Amber - copyleft (caution)
  'LGPL-2.1': '#F97316',      // Orange - copyleft
  'AGPL-3.0': '#EF4444',      // Red - strong copyleft
  'Unknown': '#6B7280',       // Gray - unknown
  'Proprietary': '#DC2626',   // Red - proprietary
  'Other': '#9CA3AF',         // Light gray - other
};

/**
 * Get color for license type
 */
function getLicenseColor(license) {
  return LICENSE_COLORS[license] || LICENSE_COLORS.Other;
}

/**
 * Loading skeleton
 */
function LicenseComplianceWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="flex justify-center">
        <div className="w-40 h-40 rounded-full bg-surface-200 dark:bg-surface-700" />
      </div>
    </div>
  );
}

/**
 * Error state
 */
function LicenseComplianceWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[250px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load license data
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Custom tooltip for pie chart
 */
function CustomTooltip({ active, payload }) {
  if (!active || !payload || !payload[0]) return null;

  const data = payload[0].payload;
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-3">
      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
        {data.name}
      </p>
      <p className="text-xs text-gray-500 mt-1">
        {data.value} components ({data.percentage}%)
      </p>
    </div>
  );
}

/**
 * LicenseComplianceWidget component
 */
export function LicenseComplianceWidget({
  refreshInterval = 300000,
  onViolationClick = null,
  className = '',
}) {
  const [licenseData, setLicenseData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchLicenses = useCallback(async () => {
    try {
      const data = await getLicenseSummary();

      if (mountedRef.current) {
        setLicenseData(data);
        setLastUpdated(new Date().toISOString());
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchLicenses();

    const interval = setInterval(fetchLicenses, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchLicenses, refreshInterval]);

  if (isLoading) {
    return <LicenseComplianceWidgetSkeleton />;
  }

  if (error) {
    return <LicenseComplianceWidgetError onRetry={fetchLicenses} />;
  }

  // Transform distribution data for chart
  const chartData = licenseData?.distribution
    ? Object.entries(licenseData.distribution)
        .map(([name, value]) => ({
          name,
          value,
          color: getLicenseColor(name),
          percentage: ((value / licenseData.total_components) * 100).toFixed(1),
        }))
        .sort((a, b) => b.value - a.value)
    : [];

  const complianceRate = licenseData
    ? ((licenseData.compliant_count / licenseData.total_components) * 100).toFixed(1)
    : 0;

  const hasViolations = licenseData?.violation_count > 0;
  const hasHighRisk = licenseData?.high_risk_licenses?.length > 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="License Compliance"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
              <ScaleIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              License Compliance
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {hasViolations ? (
              <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                {licenseData.violation_count} violations
              </span>
            ) : (
              <CheckCircleIcon className="w-5 h-5 text-green-500" />
            )}
            <button
              onClick={fetchLicenses}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {/* Compliance Summary */}
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 grid grid-cols-3 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center">
          <p className="text-xs text-gray-500">Compliance</p>
          <p className={`text-lg font-semibold ${parseFloat(complianceRate) >= 95 ? 'text-green-600' : 'text-amber-600'}`}>
            {complianceRate}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Components</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {licenseData?.total_components?.toLocaleString() || 0}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Unknown</p>
          <p className={`text-lg font-semibold ${licenseData?.unknown_count > 0 ? 'text-amber-600' : 'text-gray-900 dark:text-gray-100'}`}>
            {licenseData?.unknown_count || 0}
          </p>
        </div>
      </div>

      {/* Donut Chart */}
      <div className="p-4">
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={75}
                paddingAngle={2}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                layout="vertical"
                align="right"
                verticalAlign="middle"
                iconSize={8}
                formatter={(value) => (
                  <span className="text-xs text-gray-600 dark:text-gray-400">{value}</span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* High Risk Licenses Warning */}
      {hasHighRisk && (
        <div className="mx-4 mb-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
          <div className="flex items-start gap-2">
            <ExclamationCircleIcon className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-medium text-amber-800 dark:text-amber-200">
                High-risk licenses detected
              </p>
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                {licenseData.high_risk_licenses.join(', ')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <DataFreshnessIndicator timestamp={lastUpdated} label="Updated" />
      </div>
    </div>
  );
}

LicenseComplianceWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onViolationClick: PropTypes.func,
  className: PropTypes.string,
};

export default LicenseComplianceWidget;
