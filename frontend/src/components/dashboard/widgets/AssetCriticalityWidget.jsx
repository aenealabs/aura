/**
 * Asset Criticality Widget
 *
 * Displays repository criticality scores from Palantir CMDB integration.
 *
 * Per ADR-075: Widget ID 'palantir-asset-criticality', Category: OPERATIONS
 *
 * @module components/dashboard/widgets/AssetCriticalityWidget
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  BuildingOffice2Icon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/solid';
import { DataFreshnessIndicator } from '../../palantir/DataFreshnessIndicator';

// Classification colors
const CLASSIFICATION_COLORS = {
  Restricted: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
  Confidential: { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
  Internal: { bg: 'bg-blue-100', text: 'text-blue-700', dot: 'bg-blue-500' },
  Public: { bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' },
};

// Mock data for development
const MOCK_ASSETS = [
  { asset_id: 'payment-service', criticality_score: 10, data_classification: 'Restricted', business_owner: 'jsmith@company.com' },
  { asset_id: 'auth-gateway', criticality_score: 9, data_classification: 'Confidential', business_owner: 'mchen@company.com' },
  { asset_id: 'user-api', criticality_score: 8, data_classification: 'Internal', business_owner: 'alee@company.com' },
  { asset_id: 'analytics-pipeline', criticality_score: 6, data_classification: 'Internal', business_owner: 'bwilson@company.com' },
];

/**
 * Criticality bar visualization
 */
function CriticalityBar({ score, maxScore = 10 }) {
  const percentage = (score / maxScore) * 100;
  const getColor = () => {
    if (score >= 9) return 'bg-red-500';
    if (score >= 7) return 'bg-orange-500';
    if (score >= 5) return 'bg-amber-500';
    return 'bg-green-500';
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 w-8">
        {score}/{maxScore}
      </span>
      <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor()} transition-all`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Asset row
 */
function AssetRow({ asset, onClick }) {
  const classColors = CLASSIFICATION_COLORS[asset.data_classification] || CLASSIFICATION_COLORS.Internal;
  const ownerName = asset.business_owner ? asset.business_owner.split('@')[0] : 'Unassigned';

  return (
    <button
      onClick={() => onClick?.(asset)}
      className="
        w-full text-left py-2 px-1
        hover:bg-gray-50 dark:hover:bg-gray-800
        rounded transition-colors
        focus:outline-none focus:ring-2 focus:ring-blue-500
      "
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {asset.asset_id}
        </span>
        <span className={`
          px-2 py-0.5 text-xs font-medium rounded
          ${classColors.bg} ${classColors.text}
        `}>
          {asset.data_classification}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <CriticalityBar score={asset.criticality_score} />
        <span className="text-xs text-gray-500 ml-2">@{ownerName}</span>
      </div>
    </button>
  );
}

/**
 * AssetCriticalityWidget component
 */
export function AssetCriticalityWidget({
  refreshInterval = 3600000,
  maxAssets = 4,
  onAssetClick = null,
  onViewAll = null,
  className = '',
}) {
  const [assets, setAssets] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const fetchAssets = useCallback(async () => {
    try {
      // Mock data for now - would call getAssetCriticality in production
      await new Promise((resolve) => setTimeout(resolve, 500));

      if (mountedRef.current) {
        setAssets(MOCK_ASSETS);
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
    fetchAssets();

    const interval = setInterval(fetchAssets, refreshInterval);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchAssets, refreshInterval]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 p-4 animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-surface-200 dark:bg-surface-700" />
          <div className="w-32 h-5 rounded bg-surface-200 dark:bg-surface-700" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 rounded bg-surface-100 dark:bg-surface-700" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-surface-800 rounded-xl border border-red-200 p-4 flex flex-col items-center justify-center min-h-[200px]">
        <ExclamationTriangleIcon className="w-8 h-8 text-red-500 mb-2" />
        <p className="text-sm text-gray-600 mb-3">Failed to load assets</p>
        <button
          onClick={fetchAssets}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  const businessCritical = assets?.filter((a) => a.criticality_score >= 8).length || 0;
  const totalAssets = assets?.length || 0;
  const displayAssets = assets?.slice(0, maxAssets) || [];

  return (
    <div
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-purple-100 dark:bg-purple-900/30">
              <BuildingOffice2Icon className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              Asset Criticality
            </h3>
          </div>
          {onViewAll && (
            <button
              onClick={onViewAll}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              View All Assets
            </button>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="p-4 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Business-Critical Assets
          </span>
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {businessCritical} repos
          </span>
        </div>
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-500 transition-all"
            style={{ width: `${(businessCritical / totalAssets) * 100}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {businessCritical}/{totalAssets} repos
        </p>
      </div>

      {/* Asset List */}
      <div className="p-4 divide-y divide-gray-100 dark:divide-gray-700">
        {displayAssets.map((asset) => (
          <AssetRow key={asset.asset_id} asset={asset} onClick={onAssetClick} />
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between text-xs text-gray-500">
        <span>Source: Palantir CMDB</span>
        <DataFreshnessIndicator timestamp={lastUpdated} compact />
      </div>
    </div>
  );
}

AssetCriticalityWidget.propTypes = {
  refreshInterval: PropTypes.number,
  maxAssets: PropTypes.number,
  onAssetClick: PropTypes.func,
  onViewAll: PropTypes.func,
  className: PropTypes.string,
};

export default AssetCriticalityWidget;
