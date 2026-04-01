/**
 * PrioritizedVulnsWidget Tests
 *
 * Tests for the Prioritized Vulnerabilities Widget component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { PrioritizedVulnsWidget } from './PrioritizedVulnsWidget';
import * as palantirApi from '../../../services/palantirApi';

vi.mock('../../../services/palantirApi');

describe('PrioritizedVulnsWidget', () => {
  const mockThreats = [
    {
      threat_id: 'threat-001',
      cves: ['CVE-2024-0001'],
      epss_score: 0.85,
      priority_score: 92,
      active_campaigns: ['APT29'],
      targeted_industries: ['Technology'],
    },
    {
      threat_id: 'threat-002',
      cves: ['CVE-2024-0002'],
      epss_score: 0.65,
      priority_score: 75,
      active_campaigns: [],
      targeted_industries: ['Finance'],
    },
    {
      threat_id: 'threat-003',
      cves: ['CVE-2024-0003'],
      epss_score: 0.45,
      priority_score: 55,
      active_campaigns: [],
      targeted_industries: [],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading skeleton initially', () => {
    palantirApi.getActiveThreats.mockImplementation(() => new Promise(() => {}));

    render(<PrioritizedVulnsWidget />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  test('renders vulnerabilities after loading', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText('Prioritized Vulnerabilities')).toBeInTheDocument();
    });

    expect(screen.getByText('CVE-2024-0001')).toBeInTheDocument();
  });

  test('displays vulnerabilities ranked by score', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText('CVE-2024-0001')).toBeInTheDocument();
    });

    // Check rank numbers are present
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  test('displays severity badges based on score', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });

    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
  });

  test('displays EPSS scores as percentages', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText(/85\.0%/)).toBeInTheDocument();
    });
  });

  test('calls onVulnClick when vulnerability clicked', async () => {
    const user = userEvent.setup();
    const handleVulnClick = vi.fn();
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget onVulnClick={handleVulnClick} />);

    await waitFor(() => {
      expect(screen.getByText('CVE-2024-0001')).toBeInTheDocument();
    });

    const vulnRow = screen.getByText('CVE-2024-0001').closest('button');
    await user.click(vulnRow);

    expect(handleVulnClick).toHaveBeenCalledWith('CVE-2024-0001');
  });

  test('renders error state when fetch fails', async () => {
    palantirApi.getActiveThreats.mockRejectedValue(new Error('Network error'));

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });

  test('limits displayed vulnerabilities to maxVulns', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget maxVulns={2} />);

    await waitFor(() => {
      expect(screen.getByText('CVE-2024-0001')).toBeInTheDocument();
    });

    expect(screen.queryByText('CVE-2024-0003')).not.toBeInTheDocument();
  });

  test('shows empty state when no vulnerabilities', async () => {
    palantirApi.getActiveThreats.mockResolvedValue([]);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText(/no prioritized vulnerabilities/i)).toBeInTheDocument();
    });
  });

  test('displays reason for prioritization', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText(/active campaign/i)).toBeInTheDocument();
    });
  });

  test('calls onViewQueue when full queue button clicked', async () => {
    const user = userEvent.setup();
    const handleViewQueue = vi.fn();
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    render(<PrioritizedVulnsWidget onViewQueue={handleViewQueue} />);

    await waitFor(() => {
      expect(screen.getByText('Prioritized Vulnerabilities')).toBeInTheDocument();
    });

    const viewQueueButton = screen.getByRole('button', { name: /full queue/i });
    await user.click(viewQueueButton);

    expect(handleViewQueue).toHaveBeenCalled();
  });

  test('applies custom className', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    const { container } = render(<PrioritizedVulnsWidget className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('Prioritized Vulnerabilities')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('displays score bar visualization', async () => {
    palantirApi.getActiveThreats.mockResolvedValue(mockThreats);

    const { container } = render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText('CVE-2024-0001')).toBeInTheDocument();
    });

    // Check for score bar elements
    const scoreBars = container.querySelectorAll('[style*="width"]');
    expect(scoreBars.length).toBeGreaterThan(0);
  });

  test('deduplicates CVEs with same ID', async () => {
    const duplicatedThreats = [
      ...mockThreats,
      {
        threat_id: 'threat-dup',
        cves: ['CVE-2024-0001'], // Same CVE as first threat
        epss_score: 0.90,
        priority_score: 80,
        active_campaigns: [],
        targeted_industries: [],
      },
    ];
    palantirApi.getActiveThreats.mockResolvedValue(duplicatedThreats);

    render(<PrioritizedVulnsWidget />);

    await waitFor(() => {
      expect(screen.getByText('CVE-2024-0001')).toBeInTheDocument();
    });

    // Should only show one instance of CVE-2024-0001
    const cve0001Elements = screen.getAllByText('CVE-2024-0001');
    expect(cve0001Elements.length).toBe(1);
  });
});
