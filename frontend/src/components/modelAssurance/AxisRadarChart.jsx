/**
 * Pure-SVG 6-axis radar chart for ADR-088 model assurance.
 *
 * No external chart library — the chart is small (6 axes, 2
 * polygons), the math is straightforward, and a pure-SVG impl
 * keeps bundle size down and avoids the recharts/d3 dependency
 * tree. Supports a candidate polygon overlaid on an optional
 * incumbent baseline polygon per ADR-088 §Stage 7.
 *
 * Accessibility: each axis label is a real <text> element that
 * screen readers can read; the polygon points are described via
 * an aria-label summarising the per-axis scores.
 */

import { memo } from 'react';

const AXES = [
  { key: 'MA1_code_comprehension', label: 'Code Comprehension' },
  { key: 'MA2_vulnerability_detection_recall', label: 'Vuln Detection Recall' },
  { key: 'MA3_patch_functional_correctness', label: 'Patch Correctness' },
  { key: 'MA4_patch_security_equivalence', label: 'Patch Security' },
  { key: 'MA5_latency_token_efficiency', label: 'Latency / $ Efficiency' },
  { key: 'MA6_guardrail_compliance', label: 'Guardrail Compliance' },
];

function pointFor(axisIndex, value, cx, cy, radius) {
  // Start at the top (12 o'clock) and rotate clockwise.
  const angle = -Math.PI / 2 + (axisIndex / AXES.length) * 2 * Math.PI;
  const r = Math.max(0, Math.min(1, value)) * radius;
  return {
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  };
}

function polygonPoints(scores, cx, cy, radius) {
  return AXES.map((axis, i) => {
    const value = scores?.[axis.key] ?? 0;
    const p = pointFor(i, value, cx, cy, radius);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(' ');
}

const RING_FRACTIONS = [0.25, 0.5, 0.75, 1.0];

const AxisRadarChart = memo(function AxisRadarChart({
  candidateScores,
  incumbentScores = null,
  size = 360,
  candidateColor = '#3B82F6',
  incumbentColor = '#94a3b8',
}) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = (size / 2) * 0.7; // leave room for axis labels

  const candidateLabel = AXES.map(
    (a) => `${a.label} ${(candidateScores?.[a.key] ?? 0).toFixed(2)}`,
  ).join(', ');

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`6-axis assurance radar — ${candidateLabel}`}
      style={{ display: 'block' }}
    >
      {/* Concentric reference rings */}
      {RING_FRACTIONS.map((frac) => (
        <circle
          key={frac}
          cx={cx}
          cy={cy}
          r={radius * frac}
          fill="none"
          stroke="#E5E7EB"
          strokeWidth="1"
          aria-hidden="true"
        />
      ))}

      {/* Axis lines */}
      {AXES.map((axis, i) => {
        const end = pointFor(i, 1.0, cx, cy, radius);
        return (
          <line
            key={axis.key}
            x1={cx}
            y1={cy}
            x2={end.x}
            y2={end.y}
            stroke="#E5E7EB"
            strokeWidth="1"
            aria-hidden="true"
          />
        );
      })}

      {/* Incumbent polygon (drawn first so candidate sits on top) */}
      {incumbentScores && (
        <polygon
          points={polygonPoints(incumbentScores, cx, cy, radius)}
          fill={incumbentColor}
          fillOpacity="0.18"
          stroke={incumbentColor}
          strokeWidth="2"
          aria-label="incumbent baseline"
        />
      )}

      {/* Candidate polygon */}
      <polygon
        points={polygonPoints(candidateScores, cx, cy, radius)}
        fill={candidateColor}
        fillOpacity="0.30"
        stroke={candidateColor}
        strokeWidth="2"
        aria-label="candidate scores"
      />

      {/* Axis labels */}
      {AXES.map((axis, i) => {
        const labelPoint = pointFor(i, 1.18, cx, cy, radius);
        // Anchor labels to keep them inside the SVG bounds.
        let textAnchor = 'middle';
        if (labelPoint.x > cx + 5) textAnchor = 'start';
        if (labelPoint.x < cx - 5) textAnchor = 'end';
        return (
          <text
            key={axis.key}
            x={labelPoint.x}
            y={labelPoint.y}
            fontSize="11"
            fill="#374151"
            textAnchor={textAnchor}
            dominantBaseline="middle"
          >
            {axis.label}
          </text>
        );
      })}
    </svg>
  );
});

export default AxisRadarChart;
