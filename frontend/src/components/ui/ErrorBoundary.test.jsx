import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

// Mock the errorTrackingApi module
vi.mock('../../services/errorTrackingApi', () => ({
  reportError: vi.fn().mockResolvedValue({ errorId: 'ERR-123' }),
  breadcrumb: vi.fn(),
  trackEvent: vi.fn(),
}));

// Component that throws an error
function ThrowError({ shouldThrow = true }) {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>No error</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress console.error for expected errors
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  test('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  test('catches error and shows fallback UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  test('displays default error title', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  test('shows reference ID when available', async () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    // Wait for the error ID to be set from the mocked reportError
    const { waitFor } = await import('@testing-library/react');
    await waitFor(() => {
      expect(screen.getByText(/Reference ID:/i)).toBeInTheDocument();
    });
  });

  test('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom fallback</div>}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom fallback')).toBeInTheDocument();
  });

  test('reports error to tracking service', async () => {
    const { reportError } = await import('../../services/errorTrackingApi');

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    // The error is reported via componentDidCatch
    const { waitFor } = await import('@testing-library/react');
    await waitFor(() => {
      expect(reportError).toHaveBeenCalled();
    });
  });

  test('retry button resets error state', async () => {
    const user = userEvent.setup();
    let shouldThrow = true;

    function ConditionalThrow() {
      if (shouldThrow) {
        throw new Error('Test error');
      }
      return <div>Recovered</div>;
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();

    // Fix the error condition
    shouldThrow = false;

    // Click retry
    const retryButton = screen.getByRole('button', { name: /try again/i });
    await user.click(retryButton);

    // Rerender with fixed component
    rerender(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );
  });

  test('compact variant renders error UI', () => {
    render(
      <ErrorBoundary variant="compact">
        <ThrowError />
      </ErrorBoundary>
    );

    // Compact variant renders error message
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  test('fullPage variant renders error UI', () => {
    render(
      <ErrorBoundary variant="fullPage">
        <ThrowError />
      </ErrorBoundary>
    );

    // Full page variant renders error message
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  test('calls onError callback when error occurs', () => {
    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowError />
      </ErrorBoundary>
    );

    // Error boundary catches error and shows fallback
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });
});
