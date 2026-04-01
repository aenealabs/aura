/**
 * Tests for EnvValidator Components (ADR-062 Phase 3b)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ValidationTimeline from './ValidationTimeline';
import ViolationHeatmap from './ViolationHeatmap';
import DriftStatusPanel from './DriftStatusPanel';
import AgentActivityFeed from './AgentActivityFeed';

// Mock data
const mockTimelineData = [
  {
    run_id: 'run-001',
    timestamp: new Date().toISOString(),
    environment: 'qa',
    trigger: 'pre_deploy',
    result: 'pass',
    violations_count: 0,
    warnings_count: 2,
    resources_scanned: 15,
  },
  {
    run_id: 'run-002',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    environment: 'dev',
    trigger: 'manual',
    result: 'fail',
    violations_count: 3,
    warnings_count: 1,
    resources_scanned: 8,
  },
];

const mockDriftData = {
  dev: {
    drift_detected: true,
    critical_count: 0,
    warning_count: 2,
    last_scan: new Date().toISOString(),
    events: [
      {
        event_id: 'drift-001',
        resource_type: 'ConfigMap',
        resource_name: 'test-config',
        namespace: 'default',
        field_path: 'data.ENVIRONMENT',
        baseline_value: 'dev',
        current_value: 'development',
        severity: 'warning',
        detected_at: new Date().toISOString(),
      },
    ],
  },
  qa: {
    drift_detected: false,
    critical_count: 0,
    warning_count: 0,
    last_scan: new Date().toISOString(),
    events: [],
  },
};

const mockActivities = [
  {
    id: 'act-001',
    type: 'validation_passed',
    timestamp: new Date().toISOString(),
    environment: 'qa',
    details: 'Pre-deploy validation completed',
    resources: 15,
    metadata: { run_id: 'run-001' },
  },
];

describe('ValidationTimeline', () => {
  it('renders timeline items', () => {
    render(<ValidationTimeline data={mockTimelineData} />);

    expect(screen.getByText('Validation Timeline')).toBeInTheDocument();
    // QA and DEV appear in both filter options and timeline cards
    expect(screen.getAllByText('QA').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('DEV').length).toBeGreaterThanOrEqual(1);
  });

  it('shows pass/fail badges', () => {
    render(<ValidationTimeline data={mockTimelineData} />);

    expect(screen.getByText('PASS')).toBeInTheDocument();
    expect(screen.getByText('FAIL')).toBeInTheDocument();
  });

  it('filters by environment', () => {
    render(<ValidationTimeline data={mockTimelineData} />);

    // There are two comboboxes (env filter and result filter), get the first one
    const comboboxes = screen.getAllByRole('combobox');
    const envFilter = comboboxes[0];
    fireEvent.change(envFilter, { target: { value: 'qa' } });

    // QA appears in dropdown option and in timeline card
    expect(screen.getAllByText('QA').length).toBeGreaterThanOrEqual(1);
    // DEV should be filtered out from timeline (may still appear in dropdown)
    expect(screen.queryAllByText('DEV').length).toBeLessThanOrEqual(1);
  });

  it('calls onSelectRun when item clicked', () => {
    const handleSelect = vi.fn();
    render(
      <ValidationTimeline data={mockTimelineData} onSelectRun={handleSelect} />
    );

    const items = screen.getAllByRole('button');
    fireEvent.click(items[0]);

    expect(handleSelect).toHaveBeenCalledWith(expect.objectContaining({
      run_id: 'run-001',
    }));
  });

  it('shows loading state', () => {
    render(<ValidationTimeline loading={true} />);

    expect(screen.queryByText('Validation Timeline')).not.toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    render(<ValidationTimeline data={[]} />);

    expect(screen.getByText('No validation runs found')).toBeInTheDocument();
  });
});

describe('ViolationHeatmap', () => {
  it('renders heatmap with severity sections', () => {
    render(<ViolationHeatmap />);

    expect(screen.getByText('Violation Heatmap')).toBeInTheDocument();
    // Severity labels include counts, e.g. "CRITICAL (8)"
    expect(screen.getByText(/CRITICAL \(8\)/i)).toBeInTheDocument();
    expect(screen.getByText(/WARNING \(4\)/i)).toBeInTheDocument();
    expect(screen.getByText(/INFO \(2\)/i)).toBeInTheDocument();
  });

  it('renders environment columns and rule labels', () => {
    render(<ViolationHeatmap />);

    // Environment column headers
    expect(screen.getByText('dev')).toBeInTheDocument();
    expect(screen.getByText('qa')).toBeInTheDocument();
    expect(screen.getByText('prod')).toBeInTheDocument();
    // Human-readable rule labels
    expect(screen.getByText('Account ID')).toBeInTheDocument();
    expect(screen.getByText('ECR Registry')).toBeInTheDocument();
  });

  it('shows legend by default', () => {
    render(<ViolationHeatmap showLegend={true} />);

    // Sidebar legend shows violation count scale and severity levels
    expect(screen.getByText('Violation Count')).toBeInTheDocument();
    expect(screen.getByText('No violations')).toBeInTheDocument();
    expect(screen.getByText('Severity Levels')).toBeInTheDocument();
  });

  it('hides legend when disabled', () => {
    render(<ViolationHeatmap showLegend={false} />);

    // No sidebar legend
    expect(screen.queryByText('Violation Count')).not.toBeInTheDocument();
  });
});

describe('DriftStatusPanel', () => {
  it('renders environment cards', () => {
    render(<DriftStatusPanel data={mockDriftData} />);

    expect(screen.getByText('Drift Status')).toBeInTheDocument();
    expect(screen.getByText('DEV')).toBeInTheDocument();
    expect(screen.getByText('QA')).toBeInTheDocument();
  });

  it('shows drift detected indicator', () => {
    render(<DriftStatusPanel data={mockDriftData} />);

    // There are 2 warning badges - one in header and one in dev card
    expect(screen.getAllByText('2 warning').length).toBeGreaterThanOrEqual(1);
    // QA and PROD show 'No drift'
    expect(screen.getAllByText('No drift').length).toBeGreaterThanOrEqual(1);
  });

  it('shows expanded environment card by default', () => {
    render(<DriftStatusPanel data={mockDriftData} />);

    // DEV card is expanded by default
    expect(screen.getByText('data.ENVIRONMENT')).toBeInTheDocument();
  });

  it('toggles environment card on click', () => {
    render(<DriftStatusPanel data={mockDriftData} />);

    // DEV is expanded by default, clicking should collapse it
    const devCard = screen.getByText('DEV').closest('button');
    fireEvent.click(devCard);

    // Field path should no longer be visible
    expect(screen.queryByText('data.ENVIRONMENT')).not.toBeInTheDocument();

    // Click again to expand
    fireEvent.click(devCard);
    expect(screen.getByText('data.ENVIRONMENT')).toBeInTheDocument();
  });

  it('calls onRescan when rescan clicked', () => {
    const handleRescan = vi.fn();
    render(<DriftStatusPanel data={mockDriftData} onRescan={handleRescan} />);

    // DEV card is expanded by default, Rescan button should be visible
    const rescanBtn = screen.getByText('Rescan');
    fireEvent.click(rescanBtn);

    expect(handleRescan).toHaveBeenCalledWith('dev');
  });
});

describe('AgentActivityFeed', () => {
  it('renders activity items', () => {
    render(<AgentActivityFeed activities={mockActivities} />);

    expect(screen.getByText('Agent Activity')).toBeInTheDocument();
    expect(screen.getByText('Validation Passed')).toBeInTheDocument();
    expect(screen.getByText('QA')).toBeInTheDocument();
  });

  it('shows live indicator', () => {
    render(<AgentActivityFeed />);

    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('shows empty state when no activities', () => {
    render(<AgentActivityFeed activities={[]} />);

    expect(screen.getByText('No recent activity')).toBeInTheDocument();
  });

  it('has pause/play toggle', () => {
    render(<AgentActivityFeed />);

    const pauseBtn = screen.getByRole('button', { name: /pause/i });
    expect(pauseBtn).toBeInTheDocument();

    fireEvent.click(pauseBtn);
    // Button should now show play icon
    expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument();
  });

  it('limits displayed items', () => {
    const manyActivities = Array(25).fill(null).map((_, i) => ({
      id: `act-${i}`,
      type: 'validation_passed',
      timestamp: new Date().toISOString(),
      environment: 'qa',
      details: `Activity ${i}`,
      resources: 1,
      metadata: {},
    }));

    render(<AgentActivityFeed activities={manyActivities} maxItems={10} />);

    // Should show "View all" link
    expect(screen.getByText('View all 25 activities')).toBeInTheDocument();
  });
});
