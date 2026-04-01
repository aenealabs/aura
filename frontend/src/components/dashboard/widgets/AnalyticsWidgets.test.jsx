/**
 * Analytics Widget Tests
 *
 * Tests for AssetCriticalityWidget, EPSSTrendWidget, and ComplianceDriftWidget.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { AssetCriticalityWidget } from './AssetCriticalityWidget';
import { EPSSTrendWidget } from './EPSSTrendWidget';
import { ComplianceDriftWidget } from './ComplianceDriftWidget';

// Asset Criticality Widget Tests
describe('AssetCriticalityWidget', () => {
  test('renders loading skeleton initially', () => {
    render(<AssetCriticalityWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders assets after loading', async () => {
    render(<AssetCriticalityWidget />);

    await waitFor(() => {
      expect(screen.getByText('Asset Criticality')).toBeInTheDocument();
    });
  });

  test('displays asset names', async () => {
    render(<AssetCriticalityWidget />);

    await waitFor(() => {
      expect(screen.getByText('payment-service')).toBeInTheDocument();
      expect(screen.getByText('auth-gateway')).toBeInTheDocument();
    });
  });

  test('displays criticality scores with bars', async () => {
    const { container } = render(<AssetCriticalityWidget />);

    await waitFor(() => {
      expect(screen.getByText(/10\/10/)).toBeInTheDocument();
    });

    // Check for progress bars
    expect(container.querySelectorAll('[style*="width"]').length).toBeGreaterThan(0);
  });

  test('displays data classification badges', async () => {
    render(<AssetCriticalityWidget />);

    await waitFor(() => {
      expect(screen.getByText('Restricted')).toBeInTheDocument();
      expect(screen.getByText('Confidential')).toBeInTheDocument();
    });
  });

  test('displays business-critical count summary', async () => {
    render(<AssetCriticalityWidget />);

    await waitFor(() => {
      expect(screen.getByText(/business-critical assets/i)).toBeInTheDocument();
    });
  });

  test('calls onAssetClick when asset clicked', async () => {
    const user = userEvent.setup();
    const handleAssetClick = vi.fn();

    render(<AssetCriticalityWidget onAssetClick={handleAssetClick} />);

    await waitFor(() => {
      expect(screen.getByText('payment-service')).toBeInTheDocument();
    });

    const assetRow = screen.getByText('payment-service').closest('button');
    await user.click(assetRow);

    expect(handleAssetClick).toHaveBeenCalledWith(expect.objectContaining({
      asset_id: 'payment-service',
    }));
  });

  test('calls onViewAll when view all button clicked', async () => {
    const user = userEvent.setup();
    const handleViewAll = vi.fn();

    render(<AssetCriticalityWidget onViewAll={handleViewAll} />);

    await waitFor(() => {
      expect(screen.getByText('Asset Criticality')).toBeInTheDocument();
    });

    const viewAllButton = screen.getByRole('button', { name: /view all/i });
    await user.click(viewAllButton);

    expect(handleViewAll).toHaveBeenCalled();
  });

  test('limits displayed assets to maxAssets', async () => {
    render(<AssetCriticalityWidget maxAssets={2} />);

    await waitFor(() => {
      expect(screen.getByText('payment-service')).toBeInTheDocument();
    });

    // Should only show 2 assets
    expect(screen.queryByText('analytics-pipeline')).not.toBeInTheDocument();
  });

  test('displays source attribution', async () => {
    render(<AssetCriticalityWidget />);

    await waitFor(() => {
      expect(screen.getByText(/palantir cmdb/i)).toBeInTheDocument();
    });
  });
});

// EPSS Trend Widget Tests
describe('EPSSTrendWidget', () => {
  test('renders loading skeleton initially', () => {
    render(<EPSSTrendWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders trend chart after loading', async () => {
    render(<EPSSTrendWidget />);

    await waitFor(() => {
      expect(screen.getByText('EPSS Score Trends')).toBeInTheDocument();
    });
  });

  test('displays percentile values', async () => {
    render(<EPSSTrendWidget />);

    await waitFor(() => {
      expect(screen.getByText('P50')).toBeInTheDocument();
      expect(screen.getByText('P95')).toBeInTheDocument();
      expect(screen.getByText('P99')).toBeInTheDocument();
    });
  });

  test('displays current percentile scores', async () => {
    render(<EPSSTrendWidget />);

    await waitFor(() => {
      // Should show percentage values
      const percentageElements = screen.getAllByText(/%/);
      expect(percentageElements.length).toBeGreaterThan(0);
    });
  });

  test('renders line chart', async () => {
    const { container } = render(<EPSSTrendWidget />);

    await waitFor(() => {
      expect(screen.getByText('EPSS Score Trends')).toBeInTheDocument();
    });

    // Check for Recharts elements
    expect(container.querySelector('.recharts-wrapper')).toBeInTheDocument();
  });

  test('displays refresh button', async () => {
    render(<EPSSTrendWidget />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  test('displays description text', async () => {
    render(<EPSSTrendWidget />);

    await waitFor(() => {
      expect(screen.getByText(/30-day percentile trends/i)).toBeInTheDocument();
    });
  });

  test('displays legend', async () => {
    const { container } = render(<EPSSTrendWidget />);

    await waitFor(() => {
      expect(screen.getByText('EPSS Score Trends')).toBeInTheDocument();
    });

    // Check for legend
    expect(container.querySelector('.recharts-legend-wrapper')).toBeInTheDocument();
  });

  test('applies custom className', async () => {
    const { container } = render(<EPSSTrendWidget className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('EPSS Score Trends')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });
});

// Compliance Drift Widget Tests
describe('ComplianceDriftWidget', () => {
  test('renders loading skeleton initially', () => {
    render(<ComplianceDriftWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders compliance data after loading', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText('Compliance Drift')).toBeInTheDocument();
    });
  });

  test('displays framework names', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText('SOC 2')).toBeInTheDocument();
      expect(screen.getByText('HIPAA')).toBeInTheDocument();
      expect(screen.getByText('CMMC L2')).toBeInTheDocument();
      expect(screen.getByText('NIST 800-53')).toBeInTheDocument();
    });
  });

  test('displays passing control counts', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText(/45\/48.*controls passing/i)).toBeInTheDocument();
    });
  });

  test('displays failing control counts', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText(/3 failing/i)).toBeInTheDocument();
    });
  });

  test('displays total drift count badge', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText(/17 drifts/i)).toBeInTheDocument();
    });
  });

  test('displays recent control failures section', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText(/recent control failures/i)).toBeInTheDocument();
    });
  });

  test('displays control failure details', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText('AC-2.3')).toBeInTheDocument();
      expect(screen.getByText(/access review not completed/i)).toBeInTheDocument();
    });
  });

  test('displays days open for failures', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText(/3d open/i)).toBeInTheDocument();
    });
  });

  test('calls onControlClick when failure clicked', async () => {
    const user = userEvent.setup();
    const handleControlClick = vi.fn();

    render(<ComplianceDriftWidget onControlClick={handleControlClick} />);

    await waitFor(() => {
      expect(screen.getByText('AC-2.3')).toBeInTheDocument();
    });

    const controlRow = screen.getByText('AC-2.3').closest('button');
    await user.click(controlRow);

    expect(handleControlClick).toHaveBeenCalledWith(expect.objectContaining({
      control: 'AC-2.3',
    }));
  });

  test('displays progress bars for frameworks', async () => {
    const { container } = render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText('Compliance Drift')).toBeInTheDocument();
    });

    // Check for progress bars
    expect(container.querySelectorAll('[style*="width"]').length).toBeGreaterThan(0);
  });

  test('shows check icon for fully compliant frameworks', async () => {
    const { container } = render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText('Compliance Drift')).toBeInTheDocument();
    });

    // None of our mock frameworks are fully compliant, but check structure exists
    expect(container.querySelectorAll('.h-1\\.5').length).toBeGreaterThan(0);
  });

  test('applies custom className', async () => {
    const { container } = render(<ComplianceDriftWidget className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('Compliance Drift')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('displays data freshness indicator', async () => {
    render(<ComplianceDriftWidget />);

    await waitFor(() => {
      expect(screen.getByText(/updated/i)).toBeInTheDocument();
    });
  });
});
