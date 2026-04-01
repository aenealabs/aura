import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import { StandaloneConfirmDialog, ConfirmProvider, useConfirm } from './ConfirmDialog';

describe('StandaloneConfirmDialog', () => {
  test('does not render when not open', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={false}
        title="Confirm"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.queryByText('Confirm')).not.toBeInTheDocument();
  });

  test('renders when open', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm Action"
        message="Are you sure you want to proceed?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText('Confirm Action')).toBeInTheDocument();
    expect(screen.getByText('Are you sure you want to proceed?')).toBeInTheDocument();
  });

  test('shows confirm and cancel buttons with default text', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  test('calls onConfirm when confirm button clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    );

    await user.click(screen.getByRole('button', { name: /confirm/i }));

    expect(onConfirm).toHaveBeenCalled();
    expect(onCancel).not.toHaveBeenCalled();
  });

  test('calls onCancel when cancel button clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    );

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  test('uses custom button text', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        confirmText="Yes, delete"
        cancelText="No, keep it"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Yes, delete' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'No, keep it' })).toBeInTheDocument();
  });

  test('shows loading state on confirm button', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        loading={true}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    // Both buttons should be disabled when loading
    expect(screen.getByRole('button', { name: /confirm/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
  });

  test('renders danger variant', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Delete Item"
        message="This cannot be undone"
        variant="danger"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    // Danger variant renders correctly
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
  });

  test('renders warning variant', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Warning"
        message="Proceed with caution"
        variant="warning"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
  });

  test('renders info variant', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Info"
        message="Information"
        variant="info"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
  });

  test('has accessible dialog role', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('has accessible aria-labelledby', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm Action"
        message="Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-labelledby', 'confirm-title');
  });

  test('has aria-modal true', () => {
    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  test('closes on escape key press', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );

    // Press escape to close dialog
    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();
  });

  test('does not close on escape when loading', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(
      <StandaloneConfirmDialog
        isOpen={true}
        title="Confirm"
        message="Message"
        loading={true}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );

    // Try pressing escape when loading
    await user.keyboard('{Escape}');
    expect(onCancel).not.toHaveBeenCalled();
  });
});

describe('ConfirmProvider', () => {
  // Helper component to test useConfirm hook
  function TestComponent({ onConfirmResult }) {
    const { confirm } = useConfirm();

    const handleClick = async () => {
      const result = await confirm({
        title: 'Test Title',
        message: 'Test Message',
        confirmText: 'Yes',
        cancelText: 'No',
      });
      onConfirmResult(result);
    };

    return <button onClick={handleClick}>Open Dialog</button>;
  }

  test('renders children', () => {
    render(
      <ConfirmProvider>
        <div data-testid="child">Child Content</div>
      </ConfirmProvider>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  test('useConfirm throws error when used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function BadComponent() {
      useConfirm();
      return null;
    }

    expect(() => render(<BadComponent />)).toThrow(
      'useConfirm must be used within a ConfirmProvider'
    );

    consoleSpy.mockRestore();
  });

  test('confirm opens dialog and returns true on confirm', async () => {
    const user = userEvent.setup();
    const onConfirmResult = vi.fn();

    render(
      <ConfirmProvider>
        <TestComponent onConfirmResult={onConfirmResult} />
      </ConfirmProvider>
    );

    await user.click(screen.getByText('Open Dialog'));

    expect(screen.getByText('Test Title')).toBeInTheDocument();
    expect(screen.getByText('Test Message')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Yes' }));

    expect(onConfirmResult).toHaveBeenCalledWith(true);
  });

  test('confirm returns false on cancel', async () => {
    const user = userEvent.setup();
    const onConfirmResult = vi.fn();

    render(
      <ConfirmProvider>
        <TestComponent onConfirmResult={onConfirmResult} />
      </ConfirmProvider>
    );

    await user.click(screen.getByText('Open Dialog'));
    await user.click(screen.getByRole('button', { name: 'No' }));

    expect(onConfirmResult).toHaveBeenCalledWith(false);
  });
});
