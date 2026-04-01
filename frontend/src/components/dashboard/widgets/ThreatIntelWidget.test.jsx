/**
 * ThreatIntelWidget Tests
 *
 * Tests for the Threat Intelligence Widget component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { ThreatIntelWidget } from './ThreatIntelWidget';
import * as palantirApi from '../../../services/palantirApi';

vi.mock('../../../services/palantirApi');

describe('ThreatIntelWidget', () => {
  const mockThreats = [
    {
      threat_id: 'threat-001',
      source_platform: 'palantir',
      cves: ['CVE-2024-0001', 'CVE-2024-0002'],
      epss_score: 0.85,
      mitre_ttps: ['T1059', 'T1566'],
      targeted_industries: ['Technology', 'Finance'],
      active_campaigns: ['APT29-Operation'],
      priority_score: 92,
    },
    {
      threat_id: 'threat-002',
      source_platform: 'palantir',
      cves: ['CVE-2024-0003'],
      epss_score: 0.65,
      mitre_ttps: ['T1078'],
      targeted_industries: ['Healthcare'],
      active_campaigns: [],
      priority_score: 75,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading skeleton initially', () => {
    palantirApi.getActiveThreats.mockImplementation(() => new Promise(() => {}));

    render(<ThreatIntelWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders threats after loading', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText('Threat Intelligence')).toBeInTheDocument();
    });

    expect(screen.getByText(/CVE-2024-0001/)).toBeInTheDocument();
    expect(screen.getByText(/APT29-Operation/i)).toBeInTheDocument();
  });

  test('displays priority score and severity badge', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    });
  });

  test('renders error state when fetch fails', async () => {
    palantirApi.getActiveThreats.mockRejectedValue(new Error('Network error'));

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });

  test('retry button refetches data', async () => {
    const user = userEvent.setup();
    palantirApi.getActiveThreats.mockRejectedValueOnce(new Error('Failed'));
    palantirApi.getActiveThreats.mockResolvedValueOnce(mockThreats);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });

    const retryButton = screen.getByRole('button', { name: /retry/i });
    await user.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Threat Intelligence')).toBeInTheDocument();
    });
  });

  test('calls onCampaignClick when threat is clicked', async () => {
    const user = userEvent.setup();
    const handleCampaignClick = vi.fn();
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget onCampaignClick={handleCampaignClick} />);

    await waitFor(() => {
      expect(screen.getByText(/CVE-2024-0001/)).toBeInTheDocument();
    });

    const threatRow = screen.getByText(/CVE-2024-0001/).closest('button');
    await user.click(threatRow);

    expect(handleCampaignClick).toHaveBeenCalledWith(expect.objectContaining({
      threat_id: 'threat-001',
    }));
  });

  test('shows empty state when no threats', async () => {
    palantirApi.getActiveThreats.mockResolvedValue([]);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText(/no active threat campaigns/i)).toBeInTheDocument();
    });
  });

  test('limits displayed threats to maxCampaigns', async () => {
    const manyThreats = Array(10).fill(null).map((_, i) => ({
      ...mockThreats[0],
      threat_id: `threat-${i}`,
    }));
    palantirApi.getActiveThreats.mockResolvedValue(manyThreats);

    render(<ThreatIntelWidget maxCampaigns={3} />);

    await waitFor(() => {
      expect(screen.getByText('Threat Intelligence')).toBeInTheDocument();
    });

    // Should only show 3 threat rows
    const threatButtons = screen.getAllByRole('button').filter(
      (btn) => btn.textContent.includes('CVE')
    );
    expect(threatButtons.length).toBeLessThanOrEqual(3);
  });

  test('applies custom className', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    const { container } = render(<ThreatIntelWidget className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('Threat Intelligence')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('displays correlation indicator when showCorrelation is true', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget showCorrelation={true} />);

    await waitFor(() => {
      expect(screen.getByText(/Threat-to-Vulnerability Correlation/i)).toBeInTheDocument();
    });
  });

  test('displays CVE count for each threat', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText(/2 CVEs/i)).toBeInTheDocument();
    });
  });

  test('displays EPSS score as percentage', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      expect(screen.getByText(/85\.0%/)).toBeInTheDocument();
    });
  });

  test('displays data freshness indicator', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<ThreatIntelWidget />);

    await waitFor(() => {
      // DataFreshnessIndicator shows "Just now" or similar for fresh data
      expect(screen.getByText(/just now|fresh/i)).toBeInTheDocument();
    });
  });
});
