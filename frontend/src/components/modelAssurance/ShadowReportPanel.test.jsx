import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';

import ShadowReportPanel from './ShadowReportPanel';
import { MOCK_PENDING_REPORTS } from './mockData';

const REPORT = MOCK_PENDING_REPORTS[0];

describe('ShadowReportPanel', () => {
  test('renders header with candidate display name and id', () => {
    render(<ShadowReportPanel report={REPORT} integrityState="verified" />);
    expect(screen.getByText(REPORT.candidate_display_name)).toBeDefined();
    expect(screen.getByText(REPORT.candidate_id)).toBeDefined();
  });

  test('utility delta is positive when candidate beats incumbent', () => {
    render(<ShadowReportPanel report={REPORT} integrityState="verified" />);
    // Candidate 0.943, incumbent 0.912 → delta +0.031
    expect(screen.getByText(/\+0\.031/)).toBeDefined();
  });

  test('floor passing message shows when no violations', () => {
    render(<ShadowReportPanel report={REPORT} integrityState="verified" />);
    expect(screen.getByText(/All regression floors passed/)).toBeDefined();
  });

  test('approve and reject buttons fire callbacks', async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <ShadowReportPanel
        report={REPORT}
        integrityState="verified"
        onApprove={onApprove}
        onReject={onReject}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /Approve/ }));
    expect(onApprove).toHaveBeenCalledWith(REPORT);
    await userEvent.click(screen.getByRole('button', { name: /Reject/ }));
    expect(onReject).toHaveBeenCalledWith(REPORT);
  });

  test('tampered integrity hard-rejects rendering', () => {
    render(
      <ShadowReportPanel
        report={REPORT}
        integrityState="tampered"
        integrityVerification={{
          valid: false,
          expected: 'abcdef0123456789',
          actual: 'ffffffffffffffff',
        }}
      />,
    );
    expect(
      screen.getByText(/Report rejected — integrity hash mismatch/),
    ).toBeDefined();
    // Decision buttons must NOT render when tampered
    expect(screen.queryByRole('button', { name: /Approve/ })).toBeNull();
  });

  test('shows reviewer disagreement when human spot-check disagrees', () => {
    render(<ShadowReportPanel report={REPORT} integrityState="verified" />);
    // MOCK has a disagreeing spot-check
    expect(screen.getAllByText(/reviewer disagrees/).length).toBeGreaterThan(0);
  });

  test('integrity badge reflects state prop', () => {
    const { rerender } = render(
      <ShadowReportPanel report={REPORT} integrityState="verified" />,
    );
    expect(screen.getByText('Integrity verified')).toBeDefined();
    rerender(<ShadowReportPanel report={REPORT} integrityState="demo" />);
    expect(screen.getByText(/Demo mode/)).toBeDefined();
  });
});
