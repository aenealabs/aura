import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';

import AxisRadarChart from './AxisRadarChart';

const SCORES = {
  MA1_code_comprehension: 0.94,
  MA2_vulnerability_detection_recall: 0.96,
  MA3_patch_functional_correctness: 0.91,
  MA4_patch_security_equivalence: 0.97,
  MA5_latency_token_efficiency: 0.86,
  MA6_guardrail_compliance: 0.99,
};

describe('AxisRadarChart', () => {
  test('renders all six axis labels', () => {
    render(<AxisRadarChart candidateScores={SCORES} />);
    expect(screen.getByText('Code Comprehension')).toBeDefined();
    expect(screen.getByText('Vuln Detection Recall')).toBeDefined();
    expect(screen.getByText('Patch Correctness')).toBeDefined();
    expect(screen.getByText('Patch Security')).toBeDefined();
    expect(screen.getByText('Latency / $ Efficiency')).toBeDefined();
    expect(screen.getByText('Guardrail Compliance')).toBeDefined();
  });

  test('renders aria-label summarising every axis score', () => {
    render(<AxisRadarChart candidateScores={SCORES} />);
    const svg = screen.getByRole('img');
    const label = svg.getAttribute('aria-label') || '';
    expect(label).toContain('Code Comprehension 0.94');
    expect(label).toContain('Guardrail Compliance 0.99');
  });

  test('overlays incumbent polygon when supplied', () => {
    render(
      <AxisRadarChart
        candidateScores={SCORES}
        incumbentScores={{
          ...SCORES,
          MA1_code_comprehension: 0.80,
        }}
      />,
    );
    // Two polygons present: candidate + incumbent.
    expect(
      document.querySelectorAll('polygon').length,
    ).toBeGreaterThanOrEqual(2);
  });

  test('omits incumbent polygon when none supplied', () => {
    render(<AxisRadarChart candidateScores={SCORES} />);
    expect(document.querySelectorAll('polygon').length).toBe(1);
  });

  test('clamps out-of-range scores defensively', () => {
    // Scores outside [0,1] must not blow up the SVG generation.
    expect(() =>
      render(
        <AxisRadarChart
          candidateScores={{
            MA1_code_comprehension: 2.0,
            MA2_vulnerability_detection_recall: -0.5,
            MA3_patch_functional_correctness: 0.5,
            MA4_patch_security_equivalence: 0.5,
            MA5_latency_token_efficiency: 0.5,
            MA6_guardrail_compliance: 0.5,
          }}
        />,
      ),
    ).not.toThrow();
  });
});
