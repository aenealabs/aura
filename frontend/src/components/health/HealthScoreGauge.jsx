import { useState, useEffect, useRef } from 'react';
import { CheckCircleIcon, ExclamationTriangleIcon, XCircleIcon } from '@heroicons/react/24/solid';
import { Skeleton } from '../ui/LoadingSkeleton';

/**
 * HealthScoreGauge Component
 *
 * Animated circular gauge displaying overall health score.
 * Features:
 * - Smooth animated transitions
 * - Color-coded status (green/amber/red)
 * - Trend indicator
 * - Accessible with ARIA labels
 *
 * Design follows Apple's gauge aesthetics with clean gradients
 * and subtle depth effects.
 */

const STATUS_CONFIG = {
  healthy: {
    color: '#10B981', // olive/green
    bgColor: 'rgba(16, 185, 129, 0.1)',
    icon: CheckCircleIcon,
    label: 'Healthy',
  },
  degraded: {
    color: '#F59E0B', // warning/amber
    bgColor: 'rgba(245, 158, 11, 0.1)',
    icon: ExclamationTriangleIcon,
    label: 'Degraded',
  },
  unhealthy: {
    color: '#DC2626', // critical/red
    bgColor: 'rgba(220, 38, 38, 0.1)',
    icon: XCircleIcon,
    label: 'Unhealthy',
  },
};

function getStatusFromScore(score) {
  if (score >= 90) return 'healthy';
  if (score >= 70) return 'degraded';
  return 'unhealthy';
}

function _getColorFromScore(score) {
  const status = getStatusFromScore(score);
  return STATUS_CONFIG[status].color;
}

export function HealthScoreGauge({
  score = 0,
  status = null,
  size = 200,
  strokeWidth = 16,
  showLabel = true,
  showStatus = true,
  showTrend = true,
  trend = null,
  animated = true,
  loading = false,
  className = '',
}) {
  const [displayScore, setDisplayScore] = useState(0);
  const animationRef = useRef(null);
  const prevScoreRef = useRef(0);

  // Determine status from score if not provided
  const effectiveStatus = status || getStatusFromScore(score);
  const config = STATUS_CONFIG[effectiveStatus] || STATUS_CONFIG.healthy;
  const StatusIcon = config.icon;

  // Calculate gauge dimensions
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Animate score changes
  useEffect(() => {
    if (!animated) {
      setDisplayScore(score);
      return;
    }

    const startScore = prevScoreRef.current;
    const endScore = score;
    const duration = 800; // ms
    const startTime = performance.now();

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startScore + (endScore - startScore) * eased;

      setDisplayScore(Math.round(current));

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        prevScoreRef.current = endScore;
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [score, animated]);

  // Calculate stroke offset for progress
  const progressOffset = circumference - (displayScore / 100) * circumference;

  // Generate gradient ID
  const gradientId = `gauge-gradient-${Math.random().toString(36).substr(2, 9)}`;

  if (loading) {
    return (
      <div className={`flex flex-col items-center ${className}`}>
        <Skeleton className="rounded-full" style={{ width: size, height: size }} />
        {showLabel && <Skeleton className="w-20 h-4 mt-3 rounded" />}
        {showStatus && <Skeleton className="w-16 h-5 mt-2 rounded-full" />}
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col items-center ${className}`}
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Health score: ${score}%`}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          className="transform -rotate-90"
          style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.05))' }}
        >
          {/* Gradient Definition */}
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={config.color} stopOpacity="1" />
              <stop offset="100%" stopColor={config.color} stopOpacity="0.7" />
            </linearGradient>
          </defs>

          {/* Background track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-surface-200 dark:text-surface-700"
          />

          {/* Progress arc */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={progressOffset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
            style={{
              filter: 'drop-shadow(0 0 8px ' + config.color + '40)',
            }}
          />

          {/* Tick marks for visual reference */}
          {[0, 25, 50, 75, 100].map((tick) => {
            const angle = (tick / 100) * 360 - 90;
            const rad = (angle * Math.PI) / 180;
            const innerRadius = radius - strokeWidth / 2 - 4;
            const outerRadius = radius - strokeWidth / 2 + 4;
            const x1 = center + innerRadius * Math.cos(rad);
            const y1 = center + innerRadius * Math.sin(rad);
            const x2 = center + outerRadius * Math.cos(rad);
            const y2 = center + outerRadius * Math.sin(rad);

            return (
              <line
                key={tick}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="currentColor"
                strokeWidth="1"
                className="text-surface-300 dark:text-surface-600"
                opacity={tick === 0 || tick === 100 ? 0.8 : 0.4}
              />
            );
          })}
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-bold text-surface-900 dark:text-surface-100 transition-colors duration-300"
            style={{
              fontSize: size * 0.22,
              color: config.color,
            }}
          >
            {displayScore}
          </span>
          <span
            className="text-surface-500 dark:text-surface-400 font-medium"
            style={{ fontSize: size * 0.08 }}
          >
            / 100
          </span>

          {/* Trend indicator */}
          {showTrend && trend && (
            <div
              className={`flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-xs font-medium
                ${trend.direction === 'up' ? 'text-olive-600 bg-olive-100 dark:text-olive-400 dark:bg-olive-900/30' : ''}
                ${trend.direction === 'down' ? 'text-critical-600 bg-critical-100 dark:text-critical-400 dark:bg-critical-900/30' : ''}
                ${trend.direction === 'stable' ? 'text-surface-600 bg-surface-100 dark:text-surface-400 dark:bg-surface-700' : ''}
              `}
            >
              {trend.direction === 'up' && (
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                  <path d="M6 2L10 7H2L6 2Z" />
                </svg>
              )}
              {trend.direction === 'down' && (
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                  <path d="M6 10L2 5H10L6 10Z" />
                </svg>
              )}
              {trend.direction === 'stable' && (
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                  <rect x="2" y="5" width="8" height="2" rx="1" />
                </svg>
              )}
              <span>{Math.abs(trend.change).toFixed(1)}%</span>
            </div>
          )}
        </div>
      </div>

      {/* Labels below gauge */}
      {showLabel && (
        <span className="mt-3 text-sm font-medium text-surface-700 dark:text-surface-300">
          Health Score
        </span>
      )}

      {showStatus && (
        <div
          className={`
            mt-2 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium
            transition-colors duration-300
          `}
          style={{
            backgroundColor: config.bgColor,
            color: config.color,
          }}
        >
          <StatusIcon className="w-4 h-4" />
          <span>{config.label}</span>
        </div>
      )}
    </div>
  );
}

/**
 * HealthScoreGaugeMini
 *
 * Compact version for use in cards and lists.
 */
export function HealthScoreGaugeMini({
  score = 0,
  size = 48,
  strokeWidth = 4,
  className = '',
}) {
  const status = getStatusFromScore(score);
  const config = STATUS_CONFIG[status];

  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progressOffset = circumference - (score / 100) * circumference;

  return (
    <div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Health: ${score}%`}
    >
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-surface-200 dark:text-surface-700"
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={config.color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={progressOffset}
          strokeLinecap="round"
          className="transition-all duration-300"
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center font-semibold"
        style={{ fontSize: size * 0.28, color: config.color }}
      >
        {score}
      </span>
    </div>
  );
}

/**
 * HealthScoreBadge
 *
 * Simple badge showing health status.
 */
export function HealthScoreBadge({
  score = 0,
  status = null,
  showScore = true,
  size = 'md',
  className = '',
}) {
  const effectiveStatus = status || getStatusFromScore(score);
  const config = STATUS_CONFIG[effectiveStatus];
  const StatusIcon = config.icon;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1 text-sm gap-1.5',
    lg: 'px-4 py-2 text-base gap-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  return (
    <div
      className={`
        inline-flex items-center font-medium rounded-full
        transition-colors duration-300
        ${sizeClasses[size] || sizeClasses.md}
        ${className}
      `}
      style={{
        backgroundColor: config.bgColor,
        color: config.color,
      }}
      role="status"
      aria-label={`Health status: ${config.label}${showScore ? `, ${score}%` : ''}`}
    >
      <StatusIcon className={iconSizes[size] || iconSizes.md} />
      <span>{config.label}</span>
      {showScore && <span className="opacity-80">({score}%)</span>}
    </div>
  );
}

export default HealthScoreGauge;
