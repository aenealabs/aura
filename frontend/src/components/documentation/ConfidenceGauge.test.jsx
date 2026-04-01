import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  ConfidenceGauge,
  ConfidenceGaugeMini,
  ConfidenceBadge,
  ConfidenceBar,
  getConfidenceLevelFromScore,
  getConfidenceConfig,
} from './ConfidenceGauge';

describe('getConfidenceLevelFromScore', () => {
  test('returns high for score >= 0.85', () => {
    expect(getConfidenceLevelFromScore(0.85)).toBe('high');
    expect(getConfidenceLevelFromScore(0.95)).toBe('high');
    expect(getConfidenceLevelFromScore(1.0)).toBe('high');
  });

  test('returns medium for score >= 0.65 and < 0.85', () => {
    expect(getConfidenceLevelFromScore(0.65)).toBe('medium');
    expect(getConfidenceLevelFromScore(0.75)).toBe('medium');
    expect(getConfidenceLevelFromScore(0.84)).toBe('medium');
  });

  test('returns low for score >= 0.45 and < 0.65', () => {
    expect(getConfidenceLevelFromScore(0.45)).toBe('low');
    expect(getConfidenceLevelFromScore(0.55)).toBe('low');
    expect(getConfidenceLevelFromScore(0.64)).toBe('low');
  });

  test('returns uncertain for score < 0.45', () => {
    expect(getConfidenceLevelFromScore(0.44)).toBe('uncertain');
    expect(getConfidenceLevelFromScore(0.3)).toBe('uncertain');
    expect(getConfidenceLevelFromScore(0)).toBe('uncertain');
  });
});

describe('getConfidenceConfig', () => {
  test('returns config for high level', () => {
    const config = getConfidenceConfig('high');
    expect(config.label).toBe('High Confidence');
    expect(config.color).toBe('#10B981');
  });

  test('returns config for medium level', () => {
    const config = getConfidenceConfig('medium');
    expect(config.label).toBe('Medium Confidence');
    expect(config.color).toBe('#3B82F6');
  });

  test('returns config for low level', () => {
    const config = getConfidenceConfig('low');
    expect(config.label).toBe('Low Confidence');
    expect(config.color).toBe('#F59E0B');
  });

  test('returns config for uncertain level', () => {
    const config = getConfidenceConfig('uncertain');
    expect(config.label).toBe('Uncertain');
    expect(config.color).toBe('#DC2626');
  });

  test('returns uncertain config for invalid level', () => {
    const config = getConfidenceConfig('invalid');
    expect(config.label).toBe('Uncertain');
  });
});

describe('ConfidenceGauge', () => {
  beforeEach(() => {
    // Mock requestAnimationFrame for animation tests
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('renders with default props', () => {
    render(<ConfidenceGauge />);

    expect(screen.getByRole('meter')).toBeInTheDocument();
    expect(screen.getByText('Confidence Score')).toBeInTheDocument();
  });

  test('renders with score as decimal (0-1)', () => {
    render(<ConfidenceGauge score={0.85} animated={false} />);

    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '85');
    expect(meter).toHaveAttribute('aria-label', 'Confidence score: 85%');
  });

  test('renders with score as percentage (0-100)', () => {
    render(<ConfidenceGauge score={75} animated={false} />);

    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '75');
  });

  test('displays correct confidence level for high score', () => {
    render(<ConfidenceGauge score={0.9} animated={false} />);

    expect(screen.getByText('High Confidence')).toBeInTheDocument();
  });

  test('displays correct confidence level for medium score', () => {
    render(<ConfidenceGauge score={0.7} animated={false} />);

    expect(screen.getByText('Medium Confidence')).toBeInTheDocument();
  });

  test('displays correct confidence level for low score', () => {
    render(<ConfidenceGauge score={0.5} animated={false} />);

    expect(screen.getByText('Low Confidence')).toBeInTheDocument();
  });

  test('displays correct confidence level for uncertain score', () => {
    render(<ConfidenceGauge score={0.3} animated={false} />);

    expect(screen.getByText('Uncertain')).toBeInTheDocument();
  });

  test('hides label when showLabel is false', () => {
    render(<ConfidenceGauge score={0.8} showLabel={false} animated={false} />);

    expect(screen.queryByText('Confidence Score')).not.toBeInTheDocument();
  });

  test('hides status when showStatus is false', () => {
    render(<ConfidenceGauge score={0.8} showStatus={false} animated={false} />);

    expect(screen.queryByText('High Confidence')).not.toBeInTheDocument();
  });

  test('shows description when showDescription is true', () => {
    render(<ConfidenceGauge score={0.9} showDescription={true} animated={false} />);

    expect(screen.getByText('Minimal review needed')).toBeInTheDocument();
  });

  test('uses provided level instead of calculating from score', () => {
    render(<ConfidenceGauge score={0.9} level="low" animated={false} />);

    expect(screen.getByText('Low Confidence')).toBeInTheDocument();
  });

  test('renders loading skeleton when loading is true', () => {
    const { container } = render(<ConfidenceGauge loading={true} />);

    // Should not render the meter
    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
    // Should have skeleton elements
    expect(container.querySelector('[class*="animate-pulse"]')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    render(<ConfidenceGauge className="custom-class" />);

    expect(screen.getByRole('meter')).toHaveClass('custom-class');
  });

  test('has correct ARIA attributes', () => {
    render(<ConfidenceGauge score={0.75} animated={false} />);

    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '100');
    expect(meter).toHaveAttribute('aria-valuenow', '75');
    expect(meter).toHaveAttribute('aria-label', 'Confidence score: 75%');
  });
});

describe('ConfidenceGaugeMini', () => {
  test('renders with default props', () => {
    render(<ConfidenceGaugeMini />);

    expect(screen.getByRole('meter')).toBeInTheDocument();
  });

  test('renders with score', () => {
    render(<ConfidenceGaugeMini score={0.8} />);

    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '80');
    expect(meter).toHaveAttribute('aria-label', 'Confidence: 80%');
  });

  test('handles percentage score', () => {
    render(<ConfidenceGaugeMini score={65} />);

    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '65');
  });

  test('displays score text', () => {
    render(<ConfidenceGaugeMini score={0.85} />);

    expect(screen.getByText('85')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    render(<ConfidenceGaugeMini className="custom-mini" />);

    expect(screen.getByRole('meter')).toHaveClass('custom-mini');
  });
});

describe('ConfidenceBadge', () => {
  test('renders with default props', () => {
    render(<ConfidenceBadge />);

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  test('renders with score and shows label', () => {
    render(<ConfidenceBadge score={0.9} />);

    expect(screen.getByText('High Confidence')).toBeInTheDocument();
    expect(screen.getByText('(90%)')).toBeInTheDocument();
  });

  test('hides score when showScore is false', () => {
    render(<ConfidenceBadge score={0.8} showScore={false} />);

    expect(screen.getByText('Medium Confidence')).toBeInTheDocument();
    expect(screen.queryByText('(80%)')).not.toBeInTheDocument();
  });

  test('uses provided level instead of calculating from score', () => {
    render(<ConfidenceBadge score={0.9} level="uncertain" />);

    expect(screen.getByText('Uncertain')).toBeInTheDocument();
  });

  test('renders different sizes', () => {
    const { rerender } = render(<ConfidenceBadge score={0.8} size="sm" />);
    expect(screen.getByRole('status')).toHaveClass('text-xs');

    rerender(<ConfidenceBadge score={0.8} size="md" />);
    expect(screen.getByRole('status')).toHaveClass('text-sm');

    rerender(<ConfidenceBadge score={0.8} size="lg" />);
    expect(screen.getByRole('status')).toHaveClass('text-base');
  });

  test('has correct ARIA label', () => {
    render(<ConfidenceBadge score={0.85} />);

    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      'Confidence: High Confidence, 85%'
    );
  });

  test('applies custom className', () => {
    render(<ConfidenceBadge className="custom-badge" />);

    expect(screen.getByRole('status')).toHaveClass('custom-badge');
  });
});

describe('ConfidenceBar', () => {
  test('renders with default props', () => {
    render(<ConfidenceBar />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('Confidence')).toBeInTheDocument();
  });

  test('renders with score', () => {
    render(<ConfidenceBar score={0.75} />);

    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '75');
    expect(bar).toHaveAttribute('aria-label', 'Confidence: 75%');
  });

  test('displays percentage text', () => {
    render(<ConfidenceBar score={0.82} />);

    expect(screen.getByText('82%')).toBeInTheDocument();
  });

  test('hides label when showLabel is false', () => {
    render(<ConfidenceBar score={0.8} showLabel={false} />);

    expect(screen.queryByText('Confidence')).not.toBeInTheDocument();
    expect(screen.queryByText('80%')).not.toBeInTheDocument();
  });

  test('handles percentage score input', () => {
    render(<ConfidenceBar score={60} />);

    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '60');
  });

  test('has correct ARIA attributes', () => {
    render(<ConfidenceBar score={0.5} />);

    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuemin', '0');
    expect(bar).toHaveAttribute('aria-valuemax', '100');
  });

  test('applies custom className', () => {
    render(<ConfidenceBar className="custom-bar" />);

    const container = screen.getByRole('progressbar').parentElement;
    expect(container).toHaveClass('custom-bar');
  });
});
