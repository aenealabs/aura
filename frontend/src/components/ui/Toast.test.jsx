import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { ToastProvider, useToast, showApiError } from './Toast';

// Test consumer component
function TestConsumer({ onToastCreated }) {
  const { toast } = useToast();

  return (
    <div>
      <button
        data-testid="show-success"
        onClick={() => {
          const id = toast.success('Success message');
          if (onToastCreated) onToastCreated(id);
        }}
      >
        Success
      </button>
      <button data-testid="show-error" onClick={() => toast.error('Error message')}>
        Error
      </button>
      <button data-testid="show-warning" onClick={() => toast.warning('Warning message')}>
        Warning
      </button>
      <button data-testid="show-info" onClick={() => toast.info('Info message')}>
        Info
      </button>
      <button
        data-testid="show-with-title"
        onClick={() => toast.success('Message', { title: 'Title' })}
      >
        With Title
      </button>
      <button
        data-testid="show-with-action"
        onClick={() =>
          toast.info('Message', {
            action: { label: 'Undo', onClick: vi.fn() },
          })
        }
      >
        With Action
      </button>
      <button data-testid="dismiss-all" onClick={() => toast.dismissAll()}>
        Dismiss All
      </button>
    </div>
  );
}

describe('Toast', () => {
  describe('ToastProvider', () => {
    test('provides toast context to children', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      expect(screen.getByTestId('show-success')).toBeInTheDocument();
    });

    test('shows success toast', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));

      expect(screen.getByText('Success message')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    test('shows error toast', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-error'));

      expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    test('shows warning toast', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-warning'));

      expect(screen.getByText('Warning message')).toBeInTheDocument();
    });

    test('shows info toast', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-info'));

      expect(screen.getByText('Info message')).toBeInTheDocument();
    });

    test('shows toast with title', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-with-title'));

      expect(screen.getByText('Title')).toBeInTheDocument();
      expect(screen.getByText('Message')).toBeInTheDocument();
    });

    test('shows toast with action button', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-with-action'));

      expect(screen.getByText('Undo')).toBeInTheDocument();
    });

    test('dismissAll clears all toasts', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));
      fireEvent.click(screen.getByTestId('show-error'));

      expect(screen.getByText('Success message')).toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();

      fireEvent.click(screen.getByTestId('dismiss-all'));

      expect(screen.queryByText('Success message')).not.toBeInTheDocument();
      expect(screen.queryByText('Error message')).not.toBeInTheDocument();
    });

    test('limits max toasts shown', () => {
      render(
        <ToastProvider maxToasts={2}>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));
      fireEvent.click(screen.getByTestId('show-error'));
      fireEvent.click(screen.getByTestId('show-warning'));

      const toasts = screen.getAllByRole('alert');
      expect(toasts).toHaveLength(2);
    });

    test('toast has accessible role alert', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    test('success toast is accessible', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(screen.getByText('Success message')).toBeInTheDocument();
    });

    test('error toast is accessible', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-error'));

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    test('renders dismiss button in toast', () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));

      expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
    });

    test('clicking dismiss button starts toast removal', async () => {
      render(
        <ToastProvider>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));
      expect(screen.getByText('Success message')).toBeInTheDocument();

      const dismissButton = screen.getByRole('button', { name: 'Dismiss' });
      fireEvent.click(dismissButton);

      // Toast should be removed (or start removal process)
      // The toast may still be in DOM briefly during animation
      await waitFor(() => {
        expect(screen.queryByText('Success message')).not.toBeInTheDocument();
      }, { timeout: 1000 });
    });

    test('can show multiple toasts', () => {
      render(
        <ToastProvider maxToasts={5}>
          <TestConsumer />
        </ToastProvider>
      );

      fireEvent.click(screen.getByTestId('show-success'));
      fireEvent.click(screen.getByTestId('show-error'));
      fireEvent.click(screen.getByTestId('show-warning'));

      expect(screen.getByText('Success message')).toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();
      expect(screen.getByText('Warning message')).toBeInTheDocument();
    });
  });

  describe('useToast', () => {
    test('throws error when used outside ToastProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useToast must be used within a ToastProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('showApiError', () => {
    test('shows error toast with response message', () => {
      const toastMock = { error: vi.fn() };
      const error = { response: { data: { message: 'API Error' } } };

      showApiError(toastMock, error);

      expect(toastMock.error).toHaveBeenCalledWith('API Error', expect.any(Object));
    });

    test('falls back to error message', () => {
      const toastMock = { error: vi.fn() };
      const error = { message: 'Generic Error' };

      showApiError(toastMock, error);

      expect(toastMock.error).toHaveBeenCalledWith('Generic Error', expect.any(Object));
    });

    test('shows default message when no message available', () => {
      const toastMock = { error: vi.fn() };
      const error = {};

      showApiError(toastMock, error);

      expect(toastMock.error).toHaveBeenCalledWith('An error occurred', expect.any(Object));
    });

    test('includes retry action when onRetry provided', () => {
      const toastMock = { error: vi.fn() };
      const error = { message: 'Error' };
      const onRetry = vi.fn();

      showApiError(toastMock, error, onRetry);

      expect(toastMock.error).toHaveBeenCalledWith('Error', {
        title: 'Request Failed',
        duration: 8000,
        action: { label: 'Retry', onClick: onRetry },
      });
    });

    test('does not include retry action when onRetry not provided', () => {
      const toastMock = { error: vi.fn() };
      const error = { message: 'Error' };

      showApiError(toastMock, error);

      expect(toastMock.error).toHaveBeenCalledWith('Error', {
        title: 'Request Failed',
        duration: 8000,
        action: undefined,
      });
    });
  });
});
