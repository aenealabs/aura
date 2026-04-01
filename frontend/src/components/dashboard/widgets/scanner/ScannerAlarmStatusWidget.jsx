/**
 * Scanner Alarm Status Widget (P0)
 *
 * Status grid showing health of 5 scanner alarms
 * with color-coded indicators.
 *
 * Per ADR-084: Widget ID 'scanner-alarm-status'
 *
 * @module components/dashboard/widgets/scanner/ScannerAlarmStatusWidget
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { BellAlertIcon } from '@heroicons/react/24/solid';
import { MOCK_ALARM_STATUS } from '../../../../services/vulnScannerMockData';
import { ALARM_COLORS, WidgetSkeleton, WidgetError, WidgetCard, formatRelativeTime } from './ScannerWidgetShared';

/**
 * Alarm row component
 */
function AlarmRow({ alarm }) {
  const config = ALARM_COLORS[alarm.status] || ALARM_COLORS.OK;

  return (
    <div className={`flex items-center justify-between p-2.5 rounded-lg ${config.bg}`}>
      <div className="flex items-center gap-2.5 min-w-0">
        <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${config.dot} ${
          alarm.status === 'ALARM' ? 'animate-pulse' : ''
        }`} />
        <div className="min-w-0">
          <p className={`text-sm font-medium truncate ${config.text}`}>
            {alarm.name}
          </p>
          {alarm.status !== 'OK' && alarm.current_value !== undefined && (
            <p className="text-[10px] text-gray-500 mt-0.5">
              {alarm.current_value}/{alarm.threshold} threshold
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={`text-xs font-medium ${config.text}`}>
          {alarm.status}
        </span>
      </div>
    </div>
  );
}

/**
 * ScannerAlarmStatusWidget component
 */
export function ScannerAlarmStatusWidget({
  refreshInterval = 30000,
  className = '',
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      await new Promise((r) => setTimeout(r, 200));
      if (mountedRef.current) {
        setData(MOCK_ALARM_STATUS);
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
  if (error) return <WidgetError title="Scanner Alarms" onRetry={fetchData} className={className} />;

  const alarmCount = data?.alarms?.filter((a) => a.status === 'ALARM').length || 0;
  const warningCount = data?.alarms?.filter((a) => a.status === 'WARNING').length || 0;

  return (
    <WidgetCard
      title="Scanner Alarms"
      subtitle="CloudWatch alarm health"
      icon={BellAlertIcon}
      iconColor={alarmCount > 0 ? 'red' : warningCount > 0 ? 'amber' : 'green'}
      onRefresh={fetchData}
      badge={
        alarmCount > 0 ? (
          <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 rounded-full">
            {alarmCount} firing
          </span>
        ) : null
      }
      className={className}
    >
      <div className="p-4 space-y-2">
        {data?.alarms?.map((alarm) => (
          <AlarmRow key={alarm.name} alarm={alarm} />
        ))}
      </div>
    </WidgetCard>
  );
}

export default ScannerAlarmStatusWidget;
