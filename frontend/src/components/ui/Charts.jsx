import { useState, useRef, useEffect } from 'react';
import { ChartSkeleton } from './LoadingSkeleton';

// Simple SVG Line Chart with responsive design
export function LineChart({
  data = [],
  labels = [],
  title,
  subtitle,
  color = 'aura',
  height = 200,
  loading = false,
  showDots = true,
  showGrid = true,
  showArea = true,
  yAxisLabel = '',
  className = '',
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, value: 0, label: '' });
  const containerRef = useRef(null);
  const [_containerWidth, setContainerWidth] = useState(400);

  // Responsive container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  if (loading) {
    return <ChartSkeleton className={className} />;
  }

  if (!data || data.length === 0) {
    return (
      <div className={`flex items-center justify-center h-48 text-surface-400 ${className}`}>
        No data available
      </div>
    );
  }

  // Color palette with gradient support
  const colorClasses = {
    aura: {
      stroke: '#3B82F6',
      gradientStart: 'rgba(59, 130, 246, 0.15)',
      gradientEnd: 'rgba(59, 130, 246, 0.02)',
      dot: '#3B82F6',
      dotRing: 'rgba(59, 130, 246, 0.2)',
    },
    olive: {
      stroke: '#7C9A3E',
      gradientStart: 'rgba(124, 154, 62, 0.15)',
      gradientEnd: 'rgba(124, 154, 62, 0.02)',
      dot: '#7C9A3E',
      dotRing: 'rgba(124, 154, 62, 0.2)',
    },
    critical: {
      stroke: '#DC2626',
      gradientStart: 'rgba(220, 38, 38, 0.12)',
      gradientEnd: 'rgba(220, 38, 38, 0.02)',
      dot: '#DC2626',
      dotRing: 'rgba(220, 38, 38, 0.2)',
    },
    warning: {
      stroke: '#F59E0B',
      gradientStart: 'rgba(245, 158, 11, 0.12)',
      gradientEnd: 'rgba(245, 158, 11, 0.02)',
      dot: '#F59E0B',
      dotRing: 'rgba(245, 158, 11, 0.2)',
    },
  };

  const colors = colorClasses[color] || colorClasses.aura;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  // Padding adjusted for y-axis label
  const padding = { top: 12, right: 16, bottom: 36, left: yAxisLabel ? 52 : 40 };
  const chartWidth = 520; // Wider for rectangular time series shape
  const chartHeight = height;
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  // Generate points
  const points = data.map((value, index) => {
    const x = padding.left + (index / (data.length - 1)) * innerWidth;
    const y = padding.top + innerHeight - ((value - min) / range) * innerHeight;
    return { x, y, value };
  });

  // Generate path
  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  // Generate area path
  const areaD = `${pathD} L ${points[points.length - 1].x} ${padding.top + innerHeight} L ${padding.left} ${padding.top + innerHeight} Z`;

  // Y-axis labels (5 gridlines for more detail)
  const yLabels = [0, 0.25, 0.5, 0.75, 1].map(ratio => {
    const val = max - ratio * range;
    return Math.round(val);
  });

  const handleMouseMove = (e, index) => {
    const point = points[index];
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
  const gradientId = `lineGradient-${color}-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div
      ref={containerRef}
      className={`
        glass-card p-4 h-full flex flex-col
        ${className}
      `}
    >
      {/* Title with optional subtitle */}
      {title && (
        <div className="mb-2">
          <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
            {title}
          </h3>
          {subtitle && (
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
      )}

      <div className="flex-1 flex items-center justify-center">
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="w-full"
          style={{ height }}
        >
          {/* Gradient Definition */}
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors.gradientStart} />
              <stop offset="100%" stopColor={colors.gradientEnd} />
            </linearGradient>
          </defs>

          {/* Grid lines with tick marks */}
          {showGrid && (
            <g>
              {/* Horizontal gridlines */}
              {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => (
                <g key={`h-${i}`}>
                  <line
                    x1={padding.left}
                    y1={padding.top + innerHeight * ratio}
                    x2={chartWidth - padding.right}
                    y2={padding.top + innerHeight * ratio}
                    className="stroke-surface-200 dark:stroke-surface-700"
                    strokeWidth="1"
                    opacity={ratio === 0 || ratio === 1 ? 0.6 : 0.3}
                  />
                  {/* Y-axis tick mark */}
                  <line
                    x1={padding.left - 4}
                    y1={padding.top + innerHeight * ratio}
                    x2={padding.left}
                    y2={padding.top + innerHeight * ratio}
                    className="stroke-surface-400 dark:stroke-surface-500"
                    strokeWidth="1"
                  />
                </g>
              ))}
              {/* Vertical gridlines */}
              {data.map((_, i) => {
                // Show vertical lines at regular intervals
                const showLine = data.length <= 7 || i % Math.ceil(data.length / 7) === 0;
                if (!showLine && i !== data.length - 1) return null;
                const x = padding.left + (i / (data.length - 1)) * innerWidth;
                return (
                  <line
                    key={`v-${i}`}
                    x1={x}
                    y1={padding.top}
                    x2={x}
                    y2={padding.top + innerHeight}
                    className="stroke-surface-200 dark:stroke-surface-700"
                    strokeWidth="1"
                    opacity={i === 0 || i === data.length - 1 ? 0.6 : 0.25}
                  />
                );
              })}
              {/* Y-axis line */}
              <line
                x1={padding.left}
                y1={padding.top}
                x2={padding.left}
                y2={padding.top + innerHeight}
                className="stroke-surface-300 dark:stroke-surface-600"
                strokeWidth="1"
              />
              {/* X-axis line */}
              <line
                x1={padding.left}
                y1={padding.top + innerHeight}
                x2={chartWidth - padding.right}
                y2={padding.top + innerHeight}
                className="stroke-surface-300 dark:stroke-surface-600"
                strokeWidth="1"
              />
            </g>
          )}

          {/* Area fill with gradient */}
          {showArea && (
            <path
              d={areaD}
              fill={`url(#${gradientId})`}
              className="transition-opacity duration-300"
            />
          )}

          {/* Line */}
          <path
            d={pathD}
            fill="none"
            stroke={colors.stroke}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="transition-all duration-300"
          />

          {/* Dots with enhanced hover */}
          {showDots && points.map((point, index) => {
            const isEndpoint = index === 0 || index === points.length - 1;
            const isHovered = hoveredIndex === index;
            const baseRadius = isEndpoint ? 4 : 3;
            const currentRadius = isHovered ? baseRadius + 2 : baseRadius;

            return (
              <g key={index}>
                {/* Outer ring on hover */}
                {isHovered && (
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={currentRadius + 6}
                    fill={colors.dotRing}
                    className="transition-all duration-200"
                  />
                )}
                {/* White background ring */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={currentRadius + 1}
                  className="fill-white dark:fill-surface-800"
                />
                {/* Colored dot */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={currentRadius}
                  fill={colors.dot}
                  className="transition-all duration-200"
                />
                {/* Invisible larger hit area */}
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
          <g className="text-[10px] fill-surface-500 dark:fill-surface-400">
            {yLabels.map((label, i) => (
              <text
                key={i}
                x={padding.left - 6}
                y={padding.top + (innerHeight / 4) * i}
                textAnchor="end"
                dominantBaseline="middle"
              >
                {label}
              </text>
            ))}
          </g>

          {/* X-axis labels */}
          <g className="text-[10px] fill-surface-500 dark:fill-surface-400">
            {labels.map((label, i) => {
              if (labels.length > 10 && i % Math.ceil(labels.length / 7) !== 0) return null;
              const x = padding.left + (i / (labels.length - 1)) * innerWidth;
              return (
                <text
                  key={i}
                  x={x}
                  y={padding.top + innerHeight + 14}
                  textAnchor="middle"
                >
                  {label}
                </text>
              );
            })}
          </g>

          {/* Y-axis title */}
          {yAxisLabel && (
            <text
              x={8}
              y={padding.top + innerHeight / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              transform={`rotate(-90, 8, ${padding.top + innerHeight / 2})`}
              className="text-xs fill-surface-500 dark:fill-surface-400 font-medium"
            >
              {yAxisLabel}
            </text>
          )}
        </svg>

        {/* Tooltip with caret */}
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
              left: `${(tooltip.x / chartWidth) * 100}%`,
              top: `${(tooltip.y / chartHeight) * 100}%`,
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
            <div className="text-base font-semibold mt-0.5">{tooltip.value}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// Simple Bar Chart
export function BarChart({
  data = [],
  labels = [],
  title,
  color = 'aura',
  height = 200,
  loading = false,
  horizontal = false,
  className = '',
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (loading) {
    return <ChartSkeleton className={className} />;
  }

  if (!data || data.length === 0) {
    return (
      <div className={`flex items-center justify-center h-48 text-surface-400 ${className}`}>
        No data available
      </div>
    );
  }

  const colorClasses = {
    aura: 'bg-aura-500 hover:bg-aura-600',
    olive: 'bg-olive-500 hover:bg-olive-600',
    critical: 'bg-critical-500 hover:bg-critical-600',
    warning: 'bg-warning-500 hover:bg-warning-600',
  };

  const max = Math.max(...data);

  return (
    <div
      className={`
        glass-card p-4
        ${className}
      `}
    >
      {title && (
        <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-3">
          {title}
        </h3>
      )}

      <div
        className={`flex ${horizontal ? 'flex-col' : 'items-end'} gap-2`}
        style={{ height: horizontal ? 'auto' : height }}
      >
        {data.map((value, index) => {
          const percentage = (value / max) * 100;

          return (
            <div
              key={index}
              className={`
                flex-1 flex ${horizontal ? 'flex-row items-center' : 'flex-col justify-end'}
                ${horizontal ? 'gap-3' : ''}
              `}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {/* Label for horizontal */}
              {horizontal && labels[index] && (
                <span className="text-sm text-surface-600 dark:text-surface-400 w-20 truncate">
                  {labels[index]}
                </span>
              )}

              {/* Bar */}
              <div
                className={`
                  ${horizontal ? 'h-8 flex-1' : 'w-full'}
                  rounded-t-md transition-all duration-300 ease-smooth
                  ${colorClasses[color] || colorClasses.aura}
                `}
                style={{
                  [horizontal ? 'width' : 'height']: `${percentage}%`,
                  minHeight: horizontal ? undefined : '4px',
                  minWidth: horizontal ? '4px' : undefined,
                }}
              />

              {/* Value tooltip */}
              {hoveredIndex === index && (
                <div
                  className={`
                    absolute ${horizontal ? '-translate-y-full -mt-2' : 'translate-y-[-100%] -mt-2'}
                    bg-surface-900 dark:bg-surface-100
                    text-white dark:text-surface-900
                    px-2 py-1 rounded text-xs font-medium
                    whitespace-nowrap
                  `}
                >
                  {value}
                </div>
              )}

              {/* Label for vertical */}
              {!horizontal && labels[index] && (
                <span className="text-xs text-surface-500 dark:text-surface-400 mt-2 truncate text-center">
                  {labels[index]}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Donut/Pie Chart
export function DonutChart({
  data = [],
  labels = [],
  colors = ['aura', 'olive', 'warning', 'critical'],
  title,
  size = 200,
  strokeWidth = 40,
  loading = false,
  showLegend = true,
  centerLabel,
  centerValue,
  className = '',
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (loading) {
    return <ChartSkeleton className={className} />;
  }

  if (!data || data.length === 0) {
    return (
      <div className={`flex items-center justify-center h-48 text-surface-400 ${className}`}>
        No data available
      </div>
    );
  }

  const colorMap = {
    aura: '#3B82F6',
    olive: '#7C9A3E',
    warning: '#F59E0B',
    critical: '#DC2626',
    surface: '#6B7280',
  };

  const total = data.reduce((sum, val) => sum + val, 0);

  // Add padding to accommodate hover expansion (strokeWidth increases by 12 on hover)
  const hoverExpansion = 12;
  const svgPadding = hoverExpansion / 2 + 4; // Extra buffer for smooth appearance
  const svgSize = size + svgPadding * 2;
  const center = svgSize / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulatedOffset = 0;

  return (
    <div
      className={`
        glass-card p-4 h-full flex flex-col
        ${className}
      `}
    >
      {title && (
        <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mb-3">
          {title}
        </h3>
      )}

      <div className="flex-1 flex items-center justify-center gap-6">
        {/* Donut - container sized for hover expansion */}
        <div className="relative" style={{ width: svgSize, height: svgSize }}>
          <svg width={svgSize} height={svgSize} className="transform -rotate-90" overflow="visible">
            {data.map((value, index) => {
              const percentage = value / total;
              const dashLength = circumference * percentage;
              const dashOffset = circumference - (accumulatedOffset * circumference);
              accumulatedOffset += percentage;

              const isHovered = hoveredIndex === index;
              return (
                <g key={index}>
                  {/* White outline behind hovered segment */}
                  {isHovered && (
                    <circle
                      cx={center}
                      cy={center}
                      r={radius}
                      fill="none"
                      stroke="white"
                      strokeWidth={strokeWidth + 16}
                      strokeDasharray={`${dashLength} ${circumference - dashLength}`}
                      strokeDashoffset={dashOffset}
                      className="transition-all duration-300 ease-smooth"
                      style={{
                        filter: 'drop-shadow(0 4px 12px rgba(0, 0, 0, 0.3))',
                      }}
                    />
                  )}
                  {/* Colored segment */}
                  <circle
                    cx={center}
                    cy={center}
                    r={radius}
                    fill="none"
                    stroke={colorMap[colors[index % colors.length]] || colors[index % colors.length]}
                    strokeWidth={isHovered ? strokeWidth + 12 : strokeWidth}
                    strokeDasharray={`${dashLength} ${circumference - dashLength}`}
                    strokeDashoffset={dashOffset}
                    className="transition-all duration-300 ease-smooth cursor-pointer"
                    style={{
                      opacity: hoveredIndex !== null && !isHovered ? 0.5 : 1,
                    }}
                    onMouseEnter={() => setHoveredIndex(index)}
                    onMouseLeave={() => setHoveredIndex(null)}
                  />
                </g>
              );
            })}
          </svg>

          {/* Center label */}
          {(centerLabel || centerValue) && (
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              {centerValue && (
                <span className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                  {centerValue}
                </span>
              )}
              {centerLabel && (
                <span className="text-sm text-surface-500 dark:text-surface-400">
                  {centerLabel}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Legend */}
        {showLegend && (
          <div className="space-y-1 min-w-0 flex-shrink">
            {data.map((value, index) => {
              const percentage = ((value / total) * 100).toFixed(1);
              const formattedValue = typeof value === 'number' ? value.toLocaleString() : value;
              return (
                <div
                  key={index}
                  className={`
                    flex items-center gap-2 px-2 py-1.5 rounded-xl cursor-pointer
                    transition-all duration-200 ease-[var(--ease-tahoe)]
                    ${hoveredIndex === index ? 'bg-white dark:bg-surface-700 shadow-sm' : ''}
                  `}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                >
                  <div
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor: colorMap[colors[index % colors.length]] || colors[index % colors.length],
                    }}
                  />
                  <span className="text-sm text-surface-700 dark:text-surface-300 truncate min-w-0 flex-1">
                    {labels[index] || `Item ${index + 1}`}
                  </span>
                  <span className="text-sm font-medium text-surface-900 dark:text-surface-100 tabular-nums whitespace-nowrap">
                    {formattedValue}
                  </span>
                  <span className="text-xs text-surface-400 dark:text-surface-500 whitespace-nowrap">
                    ({percentage}%)
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// Progress/Gauge Chart
export function ProgressChart({
  value = 0,
  max = 100,
  label,
  color = 'aura',
  size = 120,
  strokeWidth = 12,
  loading = false,
  showPercentage = true,
  displayValue = null, // Custom display value (e.g., "687ms" for latency)
  className = '',
}) {
  if (loading) {
    return (
      <div className={`flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
        <div className="skeleton w-full h-full rounded-full" />
      </div>
    );
  }

  const colorMap = {
    aura: '#3B82F6',
    olive: '#7C9A3E',
    warning: '#F59E0B',
    critical: '#DC2626',
    surface: '#6B7280',
  };

  const percentage = Math.min((value / max) * 100, 100);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;
  const center = size / 2;

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-surface-200 dark:text-surface-700"
        />

        {/* Progress circle */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colorMap[color] || color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500 ease-smooth"
        />
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {displayValue ? (
          <span className="text-xl font-bold text-surface-900 dark:text-surface-100">
            {displayValue}
          </span>
        ) : showPercentage && (
          <span className="text-xl font-bold text-surface-900 dark:text-surface-100">
            {Math.round(percentage)}%
          </span>
        )}
        {label && (
          <span className="text-xs text-surface-500 dark:text-surface-400 text-center px-2">
            {label}
          </span>
        )}
      </div>
    </div>
  );
}
