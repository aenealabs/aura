/**
 * Recent Scan Activity Widget (P0)
 *
 * Activity feed showing recent scan events, sortable and filterable.
 *
 * Per ADR-084: Widget ID 'scanner-recent-activity'
 *
 * @module components/dashboard/widgets/scanner/RecentScanActivityWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ClockIcon,
  CheckCircleIcon,
  PlayCircleIcon,
  XCircleIcon,
  ShieldCheckIcon,
  WrenchScrewdriverIcon,
  FunnelIcon,
} from '@heroicons/react/24/solid';
import { MOCK_RECENT_ACTIVITY } from '../../../../services/vulnScannerMockData';
import { SEVERITY_COLORS, WidgetSkeleton, WidgetError, WidgetCard, formatRelativeTime, formatDuration } from './ScannerWidgetShared';

const TYPE_CONFIG = {
  scan_completed: { icon: CheckCircleIcon, color: 'text-green-500', label: 'Scan Completed' },
  scan_started: { icon: PlayCircleIcon, color: 'text-blue-500', label: 'Scan Started' },
  scan_failed: { icon: XCircleIcon, color: 'text-red-500', label: 'Scan Failed' },
  finding_triaged: { icon: ShieldCheckIcon, color: 'text-amber-500', label: 'Finding Triaged' },
  fix_applied: { icon: WrenchScrewdriverIcon, color: 'text-green-500', label: 'Fix Applied' },
};

/**
 * Activity row
 */
function ActivityRow({ activity, onClick }) {
  const config = TYPE_CONFIG[activity.type] || TYPE_CONFIG.scan_completed;
  const ActivityIcon = config.icon;

  return (
    <button
      onClick={() => onClick?.(activity)}
      className="w-full text-left flex items-start gap-3 py-2.5 px-2 -mx-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      <ActivityIcon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${config.color}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2 mb-0.5">
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {activity.repository}
          </span>
          <span className="text-[10px] text-gray-400 flex-shrink-0">
            {formatRelativeTime(activity.timestamp)}
          </span>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {config.label}
          {activity.finding_title && `: ${activity.finding_title}`}
          {activity.error && `: ${activity.error}`}
        </p>
        {activity.severity_summary && (
          <div className="flex items-center gap-2 mt-1">
            {Object.entries(activity.severity_summary).map(([sev, count]) => (
              <span
                key={sev}
                className="text-[10px] px-1 py-0.5 rounded font-medium"
                style={{
                  backgroundColor: SEVERITY_COLORS[sev]?.hex + '20',
                  color: SEVERITY_COLORS[sev]?.hex,
                }}
              >
                {count} {sev}
              </span>
            ))}
            {activity.duration_ms && (
              <span className="text-[10px] text-gray-400">
                {formatDuration(activity.duration_ms)}
              </span>
            )}
          </div>
        )}
        {activity.severity && (
          <span
            className="inline-block mt-1 text-[10px] px-1 py-0.5 rounded font-medium"
            style={{
              backgroundColor: SEVERITY_COLORS[activity.severity]?.hex + '20',
              color: SEVERITY_COLORS[activity.severity]?.hex,
            }}
          >
            {activity.severity}
          </span>
        )}
      </div>
    </button>
  );
}

/**
 * RecentScanActivityWidget component
 */
export function RecentScanActivityWidget({
  refreshInterval = 30000,
  maxItems = 8,
  onActivityClick = null,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) {
        setData(MOCK_RECENT_ACTIVITY);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) setError(err);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, refreshInterval]);

  if (isLoading) return <WidgetSkeleton className={className} />;
  if (error) return <WidgetError title="Recent Activity" onRetry={fetchData} className={className} />;

  const filteredActivities = data?.activities?.filter((a) =>
    filter === 'all' || a.type === filter
  ).slice(0, maxItems) || [];

  return (
    <WidgetCard
      title="Recent Scan Activity"
      subtitle="Latest scan events and findings"
      icon={ClockIcon}
      iconColor="blue"
      onRefresh={fetchData}
      className={className}
    >
      {/* Filters */}
      <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center gap-1 overflow-x-auto">
        {[
          { value: 'all', label: 'All' },
          { value: 'scan_completed', label: 'Completed' },
          { value: 'finding_triaged', label: 'Triaged' },
          { value: 'fix_applied', label: 'Fixed' },
          { value: 'scan_failed', label: 'Failed' },
        ].map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-2 py-1 text-[10px] font-medium rounded-full whitespace-nowrap transition-colors ${
              filter === f.value
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Activity list */}
      <div className="p-4 overflow-y-auto max-h-80">
        {filteredActivities.length > 0 ? (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {filteredActivities.map((activity) => (
              <ActivityRow
                key={activity.id}
                activity={activity}
                onClick={onActivityClick}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <ClockIcon className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No recent activity</p>
          </div>
        )}
      </div>
    </WidgetCard>
  );
}

export default RecentScanActivityWidget;
