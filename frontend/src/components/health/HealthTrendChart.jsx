import { useState, useRef, useEffect, useMemo } from 'react';
import { ChartSkeleton } from '../ui/LoadingSkeleton';

/**
 * HealthTrendChart Component
 *
 * Line chart showing health score trends over time.
 * Features:
 * - Smooth SVG path rendering
 * - Interactive tooltips
 * - Gradient fill
 * - Threshold lines
 * - Responsive design
 * - Dark mode support
 *
 * Follows Apple design principles with clean lines and subtle gradients.
 */

// Health thresholds
const THRESHOLDS = {
  healthy: 90,
  degraded: 70,
};

// Color palette
const COLORS = {
  healthy: '#10B981',
  degraded: '#F59E0B',
  unhealthy: '#DC2626',
  line: '#3B82F6',
  grid: '#E5E7EB',
  gridDark: '#374151',
};

function getScoreColor(score) {
  if (score >= THRESHOLDS.healthy) return COLORS.healthy;
  if (score >= THRESHOLDS.degraded) return COLORS.degraded;
  return COLORS.unhealthy;
}

export function HealthTrendChart({
  data = [],
  labels = [],
  title = 'Health Trend',
  subtitle,
  height = 200,
  showThresholds = true,
  showArea = true,
  showDots = true,
  showGrid = true,
  showLabels = true,
  loading = false,
  className = '',
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, value: 0, label: '' });
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 400, height });

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [height]);

  // Chart calculations
  const chartConfig = useMemo(() => {
    const padding = { top: 20, right: 20, bottom: 40, left: 50 };
    const chartWidth = dimensions.width;
    const chartHeight = dimensions.height;
    const innerWidth = chartWidth - padding.left - padding.right;
    const innerHeight = chartHeight - padding.top - padding.bottom;

    // Determine Y-axis range (0-100 for health scores)
    const yMin = 0;
    const yMax = 100;
    const yRange = yMax - yMin;

    // Generate points
    const points = data.length > 0 ? data.map((value, index) => {
      const x = padding.left + (index / Math.max(data.length - 1, 1)) * innerWidth;
      const y = padding.top + innerHeight - ((value - yMin) / yRange) * innerHeight;
      return { x, y, value };
    }) : [];

    // Generate smooth curve path using cardinal spline
    const generateSmoothPath = (pts) => {
      if (pts.length < 2) return '';
      if (pts.length === 2) {
        return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;
      }

      let path = `M ${pts[0].x} ${pts[0].y}`;

      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[Math.max(0, i - 1)];
        const p1 = pts[i];
        const p2 = pts[i + 1];
        const p3 = pts[Math.min(pts.length - 1, i + 2)];

        const cp1x = p1.x + (p2.x - p0.x) / 6;
        const cp1y = p1.y + (p2.y - p0.y) / 6;
        const cp2x = p2.x - (p3.x - p1.x) / 6;
        const cp2y = p2.y - (p3.y - p1.y) / 6;

        path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
      }

      return path;
    };

    const linePath = generateSmoothPath(points);

    // Area path
    const areaPath = points.length > 0
      ? `${linePath} L ${points[points.length - 1].x} ${padding.top + innerHeight} L ${points[0].x} ${padding.top + innerHeight} Z`
      : '';

    // Y-axis labels
    const yLabels = [100, 75, 50, 25, 0].map(value => ({
      value,
      y: padding.top + innerHeight - ((value - yMin) / yRange) * innerHeight,
    }));

    // Threshold lines
    const thresholdLines = showThresholds ? [
      {
        value: THRESHOLDS.healthy,
        y: padding.top + innerHeight - ((THRESHOLDS.healthy - yMin) / yRange) * innerHeight,
        color: COLORS.healthy,
        label: 'Healthy',
      },
      {
        value: THRESHOLDS.degraded,
        y: padding.top + innerHeight - ((THRESHOLDS.degraded - yMin) / yRange) * innerHeight,
        color: COLORS.degraded,
        label: 'Degraded',
      },
    ] : [];

    return {
      chartWidth,
      chartHeight,
      innerWidth,
      innerHeight,
      padding,
      points,
      linePath,
      areaPath,
      yLabels,
      thresholdLines,
    };
  }, [data, dimensions, showThresholds]);

  const handleMouseMove = (e, index) => {
    const point = chartConfig.points[index];
    if (!point) return;

    setTooltip({
      show: true,
      x: point.x,
      y: point.y,
      value: point.value,
      label: labels[index] || `Point ${index + 1}`,
    });
    setHoveredIndex(index);
  };

  const handleMouseLeave = () => {
    setTooltip({ show: false, x: 0, y: 0, value: 0, label: '' });
    setHoveredIndex(null);
  };

  // Generate unique gradient ID
  const gradientId = useMemo(() => `health-trend-gradient-${Math.random().toString(36).substr(2, 9)}`, []);

  if (loading) {
    return <ChartSkeleton className={className} />;
  }

  if (!data || data.length === 0) {
    return (
      <div
        className={`
          bg-white dark:bg-surface-800 rounded-xl
          border border-surface-200 dark:border-surface-700
          shadow-card p-6 flex items-center justify-center
          ${className}
        `}
        style={{ minHeight: height }}
      >
        <p className="text-surface-400 dark:text-surface-500">No trend data available</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`
        bg-white dark:bg-surface-800 rounded-xl
        border border-surface-200 dark:border-surface-700
        shadow-card p-4
        ${className}
      `}
    >
      {/* Header */}
      {(title || subtitle) && (
        <div className="mb-4">
          {title && (
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
              {title}
            </h3>
          )}
          {subtitle && (
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="relative" style={{ height }}>
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 ${chartConfig.chartWidth} ${chartConfig.chartHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="overflow-visible"
        >
          {/* Gradient Definition */}
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.line} stopOpacity="0.2" />
              <stop offset="100%" stopColor={COLORS.line} stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {showGrid && (
            <g>
              {chartConfig.yLabels.map((label, i) => (
                <line
                  key={i}
                  x1={chartConfig.padding.left}
                  y1={label.y}
                  x2={chartConfig.chartWidth - chartConfig.padding.right}
                  y2={label.y}
                  className="stroke-surface-200 dark:stroke-surface-700"
                  strokeWidth="1"
                  opacity={i === 0 || i === chartConfig.yLabels.length - 1 ? 0.6 : 0.3}
                />
              ))}
            </g>
          )}

          {/* Threshold lines */}
          {showThresholds && chartConfig.thresholdLines.map((threshold, i) => (
            <g key={i}>
              <line
                x1={chartConfig.padding.left}
                y1={threshold.y}
                x2={chartConfig.chartWidth - chartConfig.padding.right}
                y2={threshold.y}
                stroke={threshold.color}
                strokeWidth="1"
                strokeDasharray="4 4"
                opacity="0.5"
              />
              <text
                x={chartConfig.chartWidth - chartConfig.padding.right + 4}
                y={threshold.y}
                className="fill-current"
                style={{ fill: threshold.color, fontSize: '9px' }}
                dominantBaseline="middle"
              >
                {threshold.value}
              </text>
            </g>
          ))}

          {/* Area fill */}
          {showArea && chartConfig.areaPath && (
            <path
              d={chartConfig.areaPath}
              fill={`url(#${gradientId})`}
              className="transition-opacity duration-300"
            />
          )}

          {/* Line */}
          {chartConfig.linePath && (
            <path
              d={chartConfig.linePath}
              fill="none"
              stroke={COLORS.line}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transition-all duration-300"
            />
          )}

          {/* Dots */}
          {showDots && chartConfig.points.map((point, index) => {
            const isHovered = hoveredIndex === index;
            const isEndpoint = index === 0 || index === chartConfig.points.length - 1;
            const baseRadius = isEndpoint ? 4 : 3;
            const currentRadius = isHovered ? baseRadius + 2 : baseRadius;
            const pointColor = getScoreColor(point.value);

            return (
              <g key={index}>
                {/* Hover ring */}
                {isHovered && (
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={currentRadius + 6}
                    fill={pointColor}
                    opacity="0.2"
                    className="transition-all duration-200"
                  />
                )}
                {/* White background */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={currentRadius + 1.5}
                  className="fill-white dark:fill-surface-800"
                />
                {/* Colored dot */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={currentRadius}
                  fill={pointColor}
                  className="transition-all duration-200"
                />
                {/* Hit area */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={20}
                  fill="transparent"
                  onMouseEnter={(e) => handleMouseMove(e, index)}
                  onMouseLeave={handleMouseLeave}
                  className="cursor-pointer"
                />
              </g>
            );
          })}

          {/* Y-axis labels */}
          {showLabels && (
            <g className="text-[10px] fill-surface-500 dark:fill-surface-400">
              {chartConfig.yLabels.map((label, i) => (
                <text
                  key={i}
                  x={chartConfig.padding.left - 8}
                  y={label.y}
                  textAnchor="end"
                  dominantBaseline="middle"
                >
                  {label.value}
                </text>
              ))}
            </g>
          )}

          {/* X-axis labels */}
          {showLabels && (
            <g className="text-[10px] fill-surface-500 dark:fill-surface-400">
              {labels.map((label, i) => {
                // Show fewer labels if there are many data points
                if (labels.length > 10 && i % Math.ceil(labels.length / 7) !== 0 && i !== labels.length - 1) {
                  return null;
                }
                const x = chartConfig.padding.left + (i / Math.max(labels.length - 1, 1)) * chartConfig.innerWidth;
                return (
                  <text
                    key={i}
                    x={x}
                    y={chartConfig.chartHeight - 8}
                    textAnchor="middle"
                  >
                    {label}
                  </text>
                );
              })}
            </g>
          )}
        </svg>

        {/* Tooltip */}
        {tooltip.show && (
          <div
            className="
              absolute pointer-events-none z-20
              bg-surface-900 dark:bg-white
              text-white dark:text-surface-900
              px-3 py-2 rounded-lg shadow-lg
              transition-opacity duration-150
            "
            style={{
              left: `${(tooltip.x / chartConfig.chartWidth) * 100}%`,
              top: `${(tooltip.y / chartConfig.chartHeight) * 100}%`,
              transform: 'translate(-50%, calc(-100% - 14px))',
            }}
          >
            {/* Caret */}
            <div
              className="
                absolute left-1/2 -translate-x-1/2 top-full
                border-8 border-transparent
                border-t-surface-900 dark:border-t-white
              "
              style={{ marginTop: '-1px' }}
            />
            <div className="text-xs text-surface-400 dark:text-surface-500 font-medium">
              {tooltip.label}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className="text-lg font-semibold"
                style={{ color: getScoreColor(tooltip.value) }}
              >
                {tooltip.value}
              </span>
              <span className="text-xs opacity-60">/ 100</span>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      {showThresholds && (
        <div className="flex items-center justify-center gap-6 mt-4 pt-3 border-t border-surface-100 dark:border-surface-700">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.healthy }} />
            <span className="text-xs text-surface-600 dark:text-surface-400">Healthy (90+)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.degraded }} />
            <span className="text-xs text-surface-600 dark:text-surface-400">Degraded (70-89)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS.unhealthy }} />
            <span className="text-xs text-surface-600 dark:text-surface-400">Unhealthy (&lt;70)</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * HealthTrendSparkline
 *
 * Minimal sparkline version for use in cards and lists.
 */
export function HealthTrendSparkline({
  data = [],
  width = 100,
  height = 32,
  strokeWidth = 2,
  className = '',
}) {
  if (!data || data.length < 2) {
    return <div className={className} style={{ width, height }} />;
  }

  // Normalize data to 0-1 range
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return { x, y, value };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const endColor = getScoreColor(data[data.length - 1]);

  return (
    <svg
      width={width}
      height={height}
      className={className}
      viewBox={`0 0 ${width} ${height}`}
    >
      <path
        d={pathD}
        fill="none"
        stroke={endColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.8"
      />
      {/* End dot */}
      <circle
        cx={points[points.length - 1].x}
        cy={points[points.length - 1].y}
        r={strokeWidth + 1}
        fill={endColor}
      />
    </svg>
  );
}

export default HealthTrendChart;
