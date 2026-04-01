import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import ResetPasswordPage from './ResetPasswordPage';

// Mock useNavigate and useLocation
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({
      state: { email: 'test@example.com' },
    }),
  };
});

// Mock auth context
const mockConfirmForgotPassword = vi.fn();
const mockClearError = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    confirmForgotPassword: mockConfirmForgotPassword,
    loading: false,
    error: null,
    clearError: mockClearError,
    isAuthenticated: false,
  }),
}));

// Mock cognito config
vi.mock('../../config/cognito', () => ({
  validatePassword: vi.fn((password) => {
    const errors = [];
    if (password.length < 12) errors.push('At least 12 characters');
    if (!/[A-Z]/.test(password)) errors.push('One uppercase letter');
    if (!/[a-z]/.test(password)) errors.push('One lowercase letter');
    if (!/[0-9]/.test(password)) errors.push('One number');
    if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)) errors.push('One special character');
    return { valid: errors.length === 0, errors };
  }),
  validateEmail: vi.fn((email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)),
}));

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders reset password form', () => {
    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /reset your password/i })).toBeInTheDocument();
  });

  test('shows verification code input', () => {
    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/verification code|code/i)).toBeInTheDocument();
  });

  test('shows new password input', () => {
    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    // Get password inputs - there's New password and Confirm new password
    const passwordInputs = screen.getAllByLabelText(/password/i);
    expect(passwordInputs.length).toBeGreaterThanOrEqual(2);
  });

  test('shows confirm password input', () => {
    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/confirm.*password/i)).toBeInTheDocument();
  });

  test('validates password requirements on weak password', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    // Get the new password input by name attribute
    const newPasswordInput = document.querySelector('input[name="newPassword"]');
    await user.type(newPasswordInput, 'weak');
    await user.tab();

    // Should show password requirements checkmarks (the component shows requirement indicators)
    await waitFor(() => {
      const requirementElements = document.querySelectorAll('.text-xs');
      expect(requirementElements.length).toBeGreaterThan(0);
    });
  });

  test('validates password match', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    const codeInput = screen.getByLabelText(/verification code/i);
    const newPasswordInput = document.querySelector('input[name="newPassword"]');
    const confirmPasswordInput = document.querySelector('input[name="confirmPassword"]');

    // Enter valid code and passwords that don't match
    await user.type(codeInput, '123456');
    await user.type(newPasswordInput, 'Password123!');
    await user.type(confirmPasswordInput, 'DifferentPassword!');

    // Try to submit
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    });
  });

  test('submits form with valid data', async () => {
    const user = userEvent.setup();
    mockConfirmForgotPassword.mockResolvedValue({ success: true });

    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    const passwordInputs = screen.getAllByLabelText(/password/i);
    const newPasswordInput = passwordInputs.find(input => input.id === 'newPassword');
    const confirmPasswordInput = passwordInputs.find(input => input.id === 'confirmPassword');

    await user.type(screen.getByLabelText(/verification code|code/i), '123456');
    await user.type(newPasswordInput, 'NewPassword123!');
    await user.type(confirmPasswordInput, 'NewPassword123!');

    await user.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() => {
      expect(mockConfirmForgotPassword).toHaveBeenCalledWith(
        'test@example.com',
        '123456',
        'NewPassword123!'
      );
    });
  });

  test('shows success page after password reset', async () => {
    const user = userEvent.setup();
    mockConfirmForgotPassword.mockResolvedValue({ success: true });

    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    const newPasswordInput = document.querySelector('input[name="newPassword"]');
    const confirmPasswordInput = document.querySelector('input[name="confirmPassword"]');

    await user.type(screen.getByLabelText(/verification code|code/i), '123456');
    await user.type(newPasswordInput, 'NewPassword123!');
    await user.type(confirmPasswordInput, 'NewPassword123!');

    await user.click(screen.getByRole('button', { name: /reset password/i }));

    // Success shows completion message with Sign in link
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /password reset complete/i })).toBeInTheDocument();
    });
  });

  test('has link to request new code', () => {
    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByRole('link', { name: /request.*new|get.*new|resend/i })).toBeInTheDocument();
  });

  test('prevents submission with empty fields', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    await user.click(screen.getByRole('button', { name: /reset password/i }));

    expect(mockConfirmForgotPassword).not.toHaveBeenCalled();
  });

  test('shows password strength indicator', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <ResetPasswordPage />
      </BrowserRouter>
    );

    const passwordInputs = screen.getAllByLabelText(/password/i);
    const newPasswordInput = passwordInputs.find(input => input.id === 'newPassword');
    await user.type(newPasswordInput, 'NewPassword123!');

    // Should show strength indicator
    await waitFor(() => {
      expect(screen.getByText(/strong|good|fair|weak/i)).toBeInTheDocument();
    });
  });
});
