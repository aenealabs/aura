/**
 * CircuitBreakerIndicator Tests
 *
 * Tests for the Circuit Breaker state indicator component.
 *
 * ADR-075: Palantir AIP UI Enhancements
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import { CircuitBreakerIndicator } from './CircuitBreakerIndicator';

describe('CircuitBreakerIndicator', () => {
  test('renders CLOSED state correctly', () => {
    render(<CircuitBreakerIndicator state="CLOSED" />);

    expect(screen.getByText('Operational')).toBeInTheDocument();
  });

  test('renders HALF_OPEN state correctly', () => {
    render(<CircuitBreakerIndicator state="HALF_OPEN" />);

    expect(screen.getByText('Recovering')).toBeInTheDocument();
  });

  test('renders OPEN state correctly', () => {
    render(<CircuitBreakerIndicator state="OPEN" />);

    expect(screen.getByText('Degraded')).toBeInTheDocument();
  });

  test('renders compact mode', () => {
    const { container } = render(<CircuitBreakerIndicator state="CLOSED" compact />);

    // In compact mode, should have smaller styling
    expect(container.querySelector('.text-sm')).toBeInTheDocument();
  });

  test('displays failure count when provided', () => {
    render(<CircuitBreakerIndicator state="HALF_OPEN" failureCount={3} failureThreshold={5} />);

    expect(screen.getByText(/3.*5/)).toBeInTheDocument();
  });

  test('displays failure progress bar', () => {
    const { container } = render(
      <CircuitBreakerIndicator state="HALF_OPEN" failureCount={3} failureThreshold={5} />
    );

    // Check for progress bar
    expect(container.querySelector('[style*="width"]')).toBeInTheDocument();
  });

  test('calls onReset when reset button clicked', async () => {
    const user = userEvent.setup();
    const handleReset = vi.fn();

    render(
      <CircuitBreakerIndicator
        state="OPEN"
        showActions
        onReset={handleReset}
      />
    );

    const resetButton = screen.getByRole('button', { name: /reset/i });
    await user.click(resetButton);

    expect(handleReset).toHaveBeenCalledTimes(1);
  });

  test('calls onForceOpen when force open button clicked', async () => {
    const user = userEvent.setup();
    const handleForceOpen = vi.fn();

    render(
      <CircuitBreakerIndicator
        state="CLOSED"
        showActions
        onForceOpen={handleForceOpen}
      />
    );

    const forceOpenButton = screen.getByRole('button', { name: /force open/i });
    await user.click(forceOpenButton);

    expect(handleForceOpen).toHaveBeenCalledTimes(1);
  });

  test('does not show admin actions when showActions is false', () => {
    const handleReset = vi.fn();

    render(
      <CircuitBreakerIndicator
        state="OPEN"
        showActions={false}
        onReset={handleReset}
      />
    );

    expect(screen.queryByRole('button', { name: /reset/i })).not.toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(
      <CircuitBreakerIndicator state="CLOSED" className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('displays last failure time when provided', () => {
    const lastFailure = new Date().toISOString();

    render(
      <CircuitBreakerIndicator
        state="HALF_OPEN"
        lastFailure={lastFailure}
      />
    );

    expect(screen.getByText(/last failure/i)).toBeInTheDocument();
  });
});
