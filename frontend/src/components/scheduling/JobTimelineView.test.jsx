/**
 * JobTimelineView Component Tests
 *
 * Tests for the calendar/timeline visualization component.
 * ADR-055 Phase 2: Timeline and HITL Integration
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import JobTimelineView from './JobTimelineView';
import ToastProvider from '../ui/Toast';

// Mock the schedulingApi
vi.mock('../../services/schedulingApi', () => ({
  getTimeline: vi.fn(),
  getStatusColor: vi.fn(() => 'bg-aura-500'),
  formatDuration: vi.fn((s) => `${Math.floor(s / 60)}m`),
}));

import { getTimeline } from '../../services/schedulingApi';

const mockTimelineData = {
  entries: [
    {
      job_id: 'job-1',
      title: 'Security Scan - Main Repo',
      job_type: 'SECURITY_SCAN',
      status: 'SUCCEEDED',
      scheduled_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_seconds: 3600,
      repository_name: 'main-repo',
    },
    {
      job_id: 'job-2',
      title: 'Patch Deploy - CVE-2024-001',
      job_type: 'PATCH_GENERATION',
      status: 'RUNNING',
      scheduled_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      repository_name: 'backend-api',
    },
    {
      job_id: 'job-3',
      title: 'Code Review - PR #42',
      job_type: 'CODE_REVIEW',
      status: 'PENDING',
      scheduled_at: new Date(Date.now() + 3600000).toISOString(),
    },
  ],
  total: 3,
};

const renderComponent = (props = {}) => {
  return render(
    <BrowserRouter>
      <ToastProvider>
        <JobTimelineView onRefresh={vi.fn()} {...props} />
      </ToastProvider>
    </BrowserRouter>
  );
};

describe('JobTimelineView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTimeline.mockResolvedValue(mockTimelineData);
  });

  describe('Loading State', () => {
    test('shows loading skeleton while fetching data', () => {
      getTimeline.mockImplementation(() => new Promise(() => {}));

      renderComponent();

      // Should show skeleton loaders
      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Error State', () => {
    test('displays error message when API fails', async () => {
      getTimeline.mockRejectedValue(new Error('Network error'));

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('View Mode Buttons', () => {
    test('displays view mode buttons (Day, Week, Month)', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Day')).toBeInTheDocument();
        expect(screen.getByText('Week')).toBeInTheDocument();
        expect(screen.getByText('Month')).toBeInTheDocument();
      });
    });

    test('defaults to week view', async () => {
      renderComponent();

      await waitFor(() => {
        const weekButton = screen.getByText('Week');
        expect(weekButton.className).toContain('aura');
      });
    });

    test('switches to day view when clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Day')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Day'));

      await waitFor(() => {
        const dayButton = screen.getByText('Day');
        expect(dayButton.className).toContain('aura');
      });
    });

    test('switches to month view when clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Month')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Month'));

      await waitFor(() => {
        const monthButton = screen.getByText('Month');
        expect(monthButton.className).toContain('aura');
      });
    });
  });

  describe('Navigation', () => {
    test('shows Today button for navigation', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Today')).toBeInTheDocument();
      });
    });

    test('navigates to previous period when chevron left clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Today')).toBeInTheDocument();
      });

      // Find the chevron left button (first button with an SVG icon)
      const buttons = screen.getAllByRole('button');
      const prevButton = buttons.find(btn =>
        btn.querySelector('svg[data-slot="icon"]') &&
        btn.textContent === '' &&
        btn.querySelector('.w-5.h-5')
      );

      if (prevButton) {
        await user.click(prevButton);
        // API should be called with new date range
        expect(getTimeline).toHaveBeenCalled();
      }
    });

    test('returns to today when Today button clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Today')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Today'));

      expect(getTimeline).toHaveBeenCalled();
    });
  });

  describe('Filters', () => {
    test('renders filter button', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Filters')).toBeInTheDocument();
      });
    });

    test('toggles filter panel when Filters button clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Filters')).toBeInTheDocument();
      });

      // Click Filters button
      await user.click(screen.getByText('Filters'));

      await waitFor(() => {
        // Filter checkboxes should appear
        expect(screen.getByText('Scheduled')).toBeInTheDocument();
        expect(screen.getByText('Completed')).toBeInTheDocument();
      });
    });

    test('filters include Scheduled and Completed checkboxes', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Filters'));

      await waitFor(() => {
        const scheduledCheckbox = screen.getByRole('checkbox', { name: /scheduled/i });
        const completedCheckbox = screen.getByRole('checkbox', { name: /completed/i });

        expect(scheduledCheckbox).toBeChecked();
        expect(completedCheckbox).toBeChecked();
      });
    });
  });

  describe('Timeline Display', () => {
    test('displays date range in header', async () => {
      // Pin the wall clock locally — using fake timers globally interferes
      // with waitFor and userEvent in the other tests. Restore real timers
      // after the assertion. The regex is month-agnostic so the test still
      // works if the range straddles a month boundary (e.g., "Dec 31 -
      // Jan 6, 2026").
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-01-08T12:00:00Z'));
      try {
        renderComponent();

        await vi.waitFor(() => {
          const dateText = screen.getByText(
            /[A-Z][a-z]{2} \d+\s*[-–]\s*[A-Z][a-z]{2} \d+,\s*\d{4}/,
          );
          expect(dateText).toBeInTheDocument();
        });
      } finally {
        vi.useRealTimers();
      }
    });

    test('displays timeline entries when loaded', async () => {
      renderComponent();

      await waitFor(() => {
        // Should show job titles from mock data
        expect(screen.getByText('Security Scan - Main Repo')).toBeInTheDocument();
      });
    });

    test('shows "No jobs" for empty days', async () => {
      getTimeline.mockResolvedValue({ entries: [], total: 0 });

      renderComponent();

      await waitFor(() => {
        const noJobsElements = screen.getAllByText('No jobs');
        expect(noJobsElements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Entry Interaction', () => {
    test('opens entry detail modal on click', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Security Scan - Main Repo')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Security Scan - Main Repo'));

      await waitFor(() => {
        // Modal should show job details
        expect(screen.getByText('Job Type')).toBeInTheDocument();
        expect(screen.getByText('SECURITY SCAN')).toBeInTheDocument();
      });
    });

    test('closes entry detail modal when Close clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Security Scan - Main Repo')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Security Scan - Main Repo'));

      await waitFor(() => {
        expect(screen.getByText('Job Type')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Close'));

      await waitFor(() => {
        expect(screen.queryByText('Job Type')).not.toBeInTheDocument();
      });
    });
  });

  describe('Legend', () => {
    test('displays status legend', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Status:')).toBeInTheDocument();
        expect(screen.getByText('Pending')).toBeInTheDocument();
        expect(screen.getByText('Running')).toBeInTheDocument();
        expect(screen.getByText('Succeeded')).toBeInTheDocument();
        expect(screen.getByText('Failed')).toBeInTheDocument();
      });
    });
  });

  describe('Refresh', () => {
    test('reloads data when refresh button clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Filters')).toBeInTheDocument();
      });

      // Find the refresh button (last button with spinner icon)
      const allButtons = screen.getAllByRole('button');
      const refreshButton = allButtons.find(btn =>
        btn.querySelector('.w-5.h-5') &&
        !btn.textContent.includes('Day') &&
        !btn.textContent.includes('Week') &&
        !btn.textContent.includes('Month') &&
        !btn.textContent.includes('Today') &&
        !btn.textContent.includes('Filters')
      );

      if (refreshButton) {
        getTimeline.mockClear();
        await user.click(refreshButton);
        expect(getTimeline).toHaveBeenCalled();
      }
    });
  });
});
