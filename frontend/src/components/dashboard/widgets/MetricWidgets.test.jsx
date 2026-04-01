/**
 * Metric Widget Tests
 *
 * Tests for InsiderRiskWidget and MTTRWidget components.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { InsiderRiskWidget } from './InsiderRiskWidget';
import { MTTRWidget } from './MTTRWidget';

describe('InsiderRiskWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading skeleton initially', () => {
    render(<InsiderRiskWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders elevated risk count after loading', async () => {
    render(<InsiderRiskWidget />);

    await waitFor(() => {
      expect(screen.getByText('Insider Risk')).toBeInTheDocument();
    });

    expect(screen.getByText('Elevated Risk Users')).toBeInTheDocument();
  });

  test('displays risk count metric', async () => {
    render(<InsiderRiskWidget />);

    await waitFor(() => {
      // Should show the elevated count (7 from mock data)
      expect(screen.getByText('7')).toBeInTheDocument();
    });
  });

  test('displays risk breakdown', async () => {
    render(<InsiderRiskWidget />);

    await waitFor(() => {
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });
  });

  test('displays trend indicator', async () => {
    render(<InsiderRiskWidget />);

    await waitFor(() => {
      // Should show trend delta
      expect(screen.getByText(/\+2/)).toBeInTheDocument();
    });
  });

  test('displays monitored users count', async () => {
    render(<InsiderRiskWidget />);

    await waitFor(() => {
      expect(screen.getByText(/1,250.*monitored/i)).toBeInTheDocument();
    });
  });

  test('calls onViewDetails when clicked', async () => {
    const user = userEvent.setup();
    const handleViewDetails = vi.fn();

    render(<InsiderRiskWidget onViewDetails={handleViewDetails} />);

    await waitFor(() => {
      expect(screen.getByText('Insider Risk')).toBeInTheDocument();
    });

    const widget = screen.getByRole('button');
    await user.click(widget);

    expect(handleViewDetails).toHaveBeenCalled();
  });

  test('applies custom className', async () => {
    const { container } = render(<InsiderRiskWidget className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('Insider Risk')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('displays data freshness indicator', async () => {
    render(<InsiderRiskWidget />);

    await waitFor(() => {
      expect(screen.getByText(/just now|fresh/i)).toBeInTheDocument();
    });
  });
});

describe('MTTRWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading skeleton initially', () => {
    render(<MTTRWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders MTTR gauge after loading', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      expect(screen.getByText('MTTR')).toBeInTheDocument();
    });
  });

  test('displays current MTTR value', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      // Mock data has 18.5 hours
      expect(screen.getByText(/18\.5h/)).toBeInTheDocument();
    });
  });

  test('displays target MTTR', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      // formatDuration(24) returns "1d" (24 hours = 1 day)
      expect(screen.getByText(/target.*1d/i)).toBeInTheDocument();
    });
  });

  test('displays severity breakdown', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });
  });

  test('shows improvement when current is below previous', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      // Should show improvement indicator (18.5 vs 22.3)
      expect(screen.getByText(/↓.*3\.8h/)).toBeInTheDocument();
    });
  });

  test('displays on-target indicator when under target', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      // Current (18.5) is under target (24), should show success indicator
      expect(document.querySelector('.text-green-500')).toBeInTheDocument();
    });
  });

  test('displays closed count', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      expect(screen.getByText(/47.*closed/i)).toBeInTheDocument();
    });
  });

  test('calls onViewDetails when clicked', async () => {
    const user = userEvent.setup();
    const handleViewDetails = vi.fn();

    render(<MTTRWidget onViewDetails={handleViewDetails} />);

    await waitFor(() => {
      expect(screen.getByText('MTTR')).toBeInTheDocument();
    });

    const widget = screen.getByRole('button');
    await user.click(widget);

    expect(handleViewDetails).toHaveBeenCalled();
  });

  test('applies custom className', async () => {
    const { container } = render(<MTTRWidget className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('MTTR')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('renders gauge visualization', async () => {
    const { container } = render(<MTTRWidget />);

    await waitFor(() => {
      expect(screen.getByText('MTTR')).toBeInTheDocument();
    });

    // Check for SVG gauge
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(container.querySelector('circle')).toBeInTheDocument();
  });

  test('displays data freshness indicator', async () => {
    render(<MTTRWidget />);

    await waitFor(() => {
      expect(screen.getByText(/just now|fresh/i)).toBeInTheDocument();
    });
  });
});
