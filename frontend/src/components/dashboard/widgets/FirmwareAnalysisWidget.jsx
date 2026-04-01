/**
 * Firmware Analysis Widget
 *
 * Displays firmware vulnerability analysis for edge devices
 * with vendor and version information.
 *
 * Per ADR-078: Widget ID 'airgap-firmware-analysis', Category: SECURITY
 *
 * @module components/dashboard/widgets/FirmwareAnalysisWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  CpuChipIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/solid';
import { getFirmwareAnalysis } from '../../../services/airgapApi';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Severity colors
const SEVERITY_COLORS = {
  critical: 'text-red-600 bg-red-100 dark:bg-red-900/30',
  high: 'text-orange-600 bg-orange-100 dark:bg-orange-900/30',
  medium: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
  low: 'text-green-600 bg-green-100 dark:bg-green-900/30',
};

/**
 * Loading skeleton
 */
function FirmwareAnalysisWidgetSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
        <div className="w-36 h-5 rounded bg-surface-200 dark:bg-surface-700" />
      </div>
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-3 rounded-lg bg-surface-100 dark:bg-surface-700">
            <div className="w-full h-4 rounded bg-surface-200 dark:bg-surface-600 mb-2" />
            <div className="w-2/3 h-3 rounded bg-surface-200 dark:bg-surface-600" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state
 */
function FirmwareAnalysisWidgetError({ onRetry }) {
  return (
    <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 dark:border-red-800 p-4 flex flex-col items-center justify-center min-h-[200px]">
      <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Failed to load firmware analysis
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
 * Device row
 */
function DeviceRow({ device, onClick }) {
  const hasCritical = device.critical > 0;

  return (
    <button
      onClick={() => onClick?.(device)}
      className="
        w-full text-left p-3 rounded-lg border
        bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700
        hover:bg-gray-100 dark:hover:bg-gray-800
        hover:shadow-sm transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
      "
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {device.type}
            </span>
            {hasCritical && (
              <span className="px-1.5 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded">
                {device.critical} critical
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {device.vendor} {device.model}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-sm font-semibold ${device.vulnerabilities > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {device.vulnerabilities}
          </span>
          <ChevronRightIcon className="w-4 h-4 text-gray-400" />
        </div>
      </div>
    </button>
  );
}

/**
 * Vulnerability item
 */
function VulnerabilityItem({ vuln }) {
  const severityClass = SEVERITY_COLORS[vuln.severity] || SEVERITY_COLORS.medium;

  return (
    <div className="flex items-start gap-2 py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${severityClass}`}>
        {vuln.severity.toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-mono text-gray-900 dark:text-gray-100">
          {vuln.cve}
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
          {vuln.component}: {vuln.description}
        </p>
      </div>
    </div>
  );
}

/**
 * FirmwareAnalysisWidget component
 */
export function FirmwareAnalysisWidget({
  refreshInterval = 300000,
  onDeviceClick = null,
  className = '',
}) {
  const [firmwareData, setFirmwareData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchAnalysis = useCallback(async () => {
    try {
      const data = await getFirmwareAnalysis();

      if (mountedRef.current) {
        setFirmwareData(data);
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
    fetchAnalysis();

    const interval = setInterval(fetchAnalysis, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAnalysis, refreshInterval]);

  if (isLoading) {
    return <FirmwareAnalysisWidgetSkeleton />;
  }

  if (error) {
    return <FirmwareAnalysisWidgetError onRetry={fetchAnalysis} />;
  }

  const totalVulnerabilities = firmwareData?.devices?.reduce((sum, d) => sum + d.vulnerabilities, 0) || 0;
  const totalCritical = firmwareData?.devices?.reduce((sum, d) => sum + d.critical, 0) || 0;

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
      role="region"
      aria-label="Firmware Analysis"
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-purple-100 dark:bg-purple-900/30">
              <CpuChipIcon className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Firmware Analysis
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {totalCritical > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                {totalCritical} critical
              </span>
            )}
            <button
              onClick={fetchAnalysis}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Refresh"
            >
              <ArrowPathIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Edge device firmware vulnerability scan
        </p>
      </div>

      {/* Summary */}
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 grid grid-cols-3 gap-4 border-b border-gray-200 dark:border-gray-700">
        <div className="text-center">
          <p className="text-xs text-gray-500">Devices</p>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {firmwareData?.devices?.length || 0}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Vulnerabilities</p>
          <p className={`text-lg font-semibold ${totalVulnerabilities > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {totalVulnerabilities}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Critical</p>
          <p className={`text-lg font-semibold ${totalCritical > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {totalCritical}
          </p>
        </div>
      </div>

      {/* Device List */}
      <div className="p-4">
        <h4 className="text-xs font-medium text-gray-500 uppercase mb-3">
          Scanned Devices
        </h4>
        {firmwareData?.devices?.length > 0 ? (
          <div className="space-y-2">
            {firmwareData.devices.slice(0, 4).map((device, index) => (
              <DeviceRow
                key={`${device.type}-${index}`}
                device={device}
                onClick={onDeviceClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
            <CpuChipIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No firmware scans available</p>
          </div>
        )}
      </div>

      {/* Top Vulnerabilities */}
      {firmwareData?.vulnerabilities?.length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50">
            <h4 className="text-xs font-medium text-gray-500 uppercase">
              Top Vulnerabilities
            </h4>
          </div>
          <div className="px-4 py-2">
            {firmwareData.vulnerabilities.slice(0, 3).map((vuln) => (
              <VulnerabilityItem key={vuln.cve} vuln={vuln} />
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            Last scan: {firmwareData?.last_scan
              ? new Date(firmwareData.last_scan).toLocaleString()
              : 'N/A'}
          </span>
          <DataFreshnessIndicator timestamp={lastUpdated} compact />
        </div>
      </div>
    </div>
  );
}

FirmwareAnalysisWidget.propTypes = {
  refreshInterval: PropTypes.number,
  onDeviceClick: PropTypes.func,
  className: PropTypes.string,
};

export default FirmwareAnalysisWidget;
