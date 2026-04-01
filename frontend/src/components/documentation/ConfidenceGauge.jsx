import { useState, useEffect, useRef } from 'react';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ExclamationCircleIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/24/solid';
import { Skeleton } from '../ui/LoadingSkeleton';

/**
 * ConfidenceGauge Component
 *
 * Animated semicircular gauge displaying documentation confidence score.
 * ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.
 *
 * Features:
 * - Smooth 800ms ease-out animation
 * - Color-coded confidence levels (HIGH/MEDIUM/LOW/UNCERTAIN)
 * - WCAG 2.1 AA accessible with ARIA labels
 * - Apple-inspired clean design with gradients
 *
 * Confidence Levels:
 * - HIGH (>=85%): Green - High confidence, minimal review needed
 * - MEDIUM (>=65%): Blue - Good confidence, spot check recommended
 * - LOW (>=45%): Amber - Lower confidence, review recommended
 * - UNCERTAIN (<45%): Red - Low confidence, manual verification required
 */

const CONFIDENCE_CONFIG = {
  high: {
    color: '#10B981', // green-500
    bgColor: 'rgba(16, 185, 129, 0.1)',
    icon: CheckCircleIcon,
    label: 'High Confidence',
    description: 'Minimal review needed',
  },
  medium: {
    color: '#3B82F6', // blue-500
    bgColor: 'rgba(59, 130, 246, 0.1)',
    icon: CheckCircleIcon,
    label: 'Medium Confidence',
    description: 'Spot check recommended',
  },
  low: {
    color: '#F59E0B', // amber-500
    bgColor: 'rgba(245, 158, 11, 0.1)',
    icon: ExclamationTriangleIcon,
    label: 'Low Confidence',
    description: 'Review recommended',
  },
  uncertain: {
    color: '#DC2626', // red-600
    bgColor: 'rgba(220, 38, 38, 0.1)',
    icon: ExclamationCircleIcon,
    label: 'Uncertain',
    description: 'Manual verification required',
  },
};

/**
 * Get confidence level from score (0.0 to 1.0)
 */
export function getConfidenceLevelFromScore(score) {
  if (score >= 0.85) return 'high';
  if (score >= 0.65) return 'medium';
  if (score >= 0.45) return 'low';
  return 'uncertain';
}

/**
 * Get config for a confidence level
 */
export function getConfidenceConfig(level) {
  return CONFIDENCE_CONFIG[level] || CONFIDENCE_CONFIG.uncertain;
}

export function ConfidenceGauge({
  score = 0,
  level = null,
  size = 180,
  strokeWidth = 14,
  showLabel = true,
  showStatus = true,
  showDescription = false,
  animated = true,
  loading = false,
  className = '',
}) {
  const [displayScore, setDisplayScore] = useState(0);
  const animationRef = useRef(null);
  const prevScoreRef = useRef(0);

  // Normalize score to percentage (handle both 0-1 and 0-100 inputs)
  const normalizedScore = score > 1 ? score : score * 100;

  // Determine level from score if not provided
  const effectiveLevel = level || getConfidenceLevelFromScore(score > 1 ? score / 100 : score);
  const config = CONFIDENCE_CONFIG[effectiveLevel] || CONFIDENCE_CONFIG.uncertain;
  const StatusIcon = config.icon;

  // Calculate semicircle gauge dimensions
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  // Semicircle uses half circumference (180 degrees)
  const semicircumference = Math.PI * radius;

  // Animate score changes
  useEffect(() => {
    if (!animated) {
      setDisplayScore(normalizedScore);
      return;
    }

    const startScore = prevScoreRef.current;
    const endScore = normalizedScore;
    const duration = 800; // ms
    const startTime = performance.now();

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic for smooth deceleration
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
  }, [normalizedScore, animated]);

  // Calculate stroke offset for progress (semicircle)
  const progressOffset = semicircumference - (displayScore / 100) * semicircumference;

  // Generate unique gradient ID
  const gradientId = `confidence-gradient-${Math.random().toString(36).substr(2, 9)}`;

  if (loading) {
    return (
      <div className={`flex flex-col items-center ${className}`}>
        <Skeleton className="rounded-t-full" style={{ width: size, height: size / 2 + 20 }} />
        {showLabel && <Skeleton className="w-24 h-4 mt-3 rounded" />}
        {showStatus && <Skeleton className="w-32 h-6 mt-2 rounded-full" />}
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col items-center ${className}`}
      role="meter"
      aria-valuenow={Math.round(normalizedScore)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Confidence score: ${Math.round(normalizedScore)}%`}
    >
      <div className="relative" style={{ width: size, height: size / 2 + 30 }}>
        <svg
          width={size}
          height={size / 2 + strokeWidth}
          style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.05))' }}
        >
          {/* Gradient Definition */}
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={config.color} stopOpacity="0.7" />
              <stop offset="50%" stopColor={config.color} stopOpacity="1" />
              <stop offset="100%" stopColor={config.color} stopOpacity="0.7" />
            </linearGradient>
          </defs>

          {/* Background track (semicircle) */}
          <path
            d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-surface-200 dark:text-surface-700"
          />

          {/* Progress arc (semicircle) */}
          <path
            d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={strokeWidth}
            strokeDasharray={semicircumference}
            strokeDashoffset={progressOffset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
            style={{
              filter: `drop-shadow(0 0 8px ${config.color}40)`,
            }}
          />

          {/* Tick marks at 0%, 25%, 50%, 75%, 100% */}
          {[0, 25, 50, 75, 100].map((tick) => {
            // Convert percentage to angle (180 degrees = PI radians)
            const angle = Math.PI - (tick / 100) * Math.PI;
            const innerRadius = radius - strokeWidth / 2 - 3;
            const outerRadius = radius - strokeWidth / 2 + 3;
            const x1 = center + innerRadius * Math.cos(angle);
            const y1 = size / 2 - innerRadius * Math.sin(angle);
            const x2 = center + outerRadius * Math.cos(angle);
            const y2 = size / 2 - outerRadius * Math.sin(angle);

            return (
              <line
                key={tick}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-surface-400 dark:text-surface-500"
                opacity={tick === 0 || tick === 100 ? 0.8 : 0.5}
              />
            );
          })}

          {/* Threshold indicators */}
          {[45, 65, 85].map((threshold) => {
            const angle = Math.PI - (threshold / 100) * Math.PI;
            const tickRadius = radius + strokeWidth / 2 + 6;
            const x = center + tickRadius * Math.cos(angle);
            const y = size / 2 - tickRadius * Math.sin(angle);

            return (
              <circle
                key={threshold}
                cx={x}
                cy={y}
                r={2}
                fill="currentColor"
                className="text-surface-400 dark:text-surface-500"
              />
            );
          })}
        </svg>

        {/* Center content */}
        <div
          className="absolute flex flex-col items-center justify-center"
          style={{
            left: 0,
            right: 0,
            bottom: 0,
            height: size / 2,
          }}
        >
          <span
            className="font-bold transition-colors duration-300"
            style={{
              fontSize: size * 0.22,
              color: config.color,
            }}
          >
            {displayScore}%
          </span>
        </div>
      </div>

      {/* Labels below gauge */}
      {showLabel && (
        <span className="mt-2 text-sm font-medium text-surface-700 dark:text-surface-300">
          Confidence Score
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

      {showDescription && (
        <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">{config.description}</p>
      )}
    </div>
  );
}

/**
 * ConfidenceGaugeMini
 *
 * Compact circular gauge for use in cards and lists.
 */
export function ConfidenceGaugeMini({ score = 0, size = 48, strokeWidth = 4, className = '' }) {
  const normalizedScore = score > 1 ? score : score * 100;
  const level = getConfidenceLevelFromScore(score > 1 ? score / 100 : score);
  const config = CONFIDENCE_CONFIG[level];

  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progressOffset = circumference - (normalizedScore / 100) * circumference;

  return (
    <div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
      role="meter"
      aria-valuenow={Math.round(normalizedScore)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Confidence: ${Math.round(normalizedScore)}%`}
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
        style={{ fontSize: size * 0.26, color: config.color }}
      >
        {Math.round(normalizedScore)}
      </span>
    </div>
  );
}

/**
 * ConfidenceBadge
 *
 * Simple badge showing confidence level.
 */
export function ConfidenceBadge({
  score = 0,
  level = null,
  showScore = true,
  size = 'md',
  className = '',
}) {
  const effectiveLevel = level || getConfidenceLevelFromScore(score > 1 ? score / 100 : score);
  const config = CONFIDENCE_CONFIG[effectiveLevel];
  const StatusIcon = config.icon;
  const displayScore = score > 1 ? score : Math.round(score * 100);

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
      aria-label={`Confidence: ${config.label}${showScore ? `, ${displayScore}%` : ''}`}
    >
      <StatusIcon className={iconSizes[size] || iconSizes.md} />
      <span>{config.label}</span>
      {showScore && <span className="opacity-80">({displayScore}%)</span>}
    </div>
  );
}

/**
 * ConfidenceBar
 *
 * Horizontal progress bar showing confidence.
 */
export function ConfidenceBar({ score = 0, height = 8, showLabel = true, className = '' }) {
  const normalizedScore = score > 1 ? score : score * 100;
  const level = getConfidenceLevelFromScore(score > 1 ? score / 100 : score);
  const config = CONFIDENCE_CONFIG[level];

  return (
    <div className={className}>
      {showLabel && (
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
            Confidence
          </span>
          <span
            className="text-sm font-semibold"
            style={{ color: config.color }}
          >
            {Math.round(normalizedScore)}%
          </span>
        </div>
      )}
      <div
        className="w-full bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden"
        style={{ height }}
        role="progressbar"
        aria-valuenow={Math.round(normalizedScore)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Confidence: ${Math.round(normalizedScore)}%`}
      >
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${normalizedScore}%`,
            backgroundColor: config.color,
          }}
        />
      </div>
    </div>
  );
}

export default ConfidenceGauge;
