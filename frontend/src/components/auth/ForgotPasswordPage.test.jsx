import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import ForgotPasswordPage from './ForgotPasswordPage';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock auth context
const mockForgotPassword = vi.fn();
const mockClearError = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    forgotPassword: mockForgotPassword,
    loading: false,
    error: null,
    clearError: mockClearError,
    isAuthenticated: false,
  }),
}));

// Mock cognito config
vi.mock('../../config/cognito', () => ({
  validateEmail: vi.fn((email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)),
}));

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders forgot password form', () => {
    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/forgot.*password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  test('shows instructions', () => {
    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/enter your email.*send.*code/i)).toBeInTheDocument();
  });

  test('validates empty email', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    const emailInput = screen.getByLabelText(/email/i);

    // Click submit without entering email - browser validation prevents submission
    await user.click(screen.getByRole('button', { name: /send reset code/i }));

    // The form shouldn't submit due to required field validation
    expect(mockForgotPassword).not.toHaveBeenCalled();
    // Input should have required attribute and be invalid
    expect(emailInput).toBeRequired();
  });

  test('validates email format', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, 'invalid-email');
    await user.click(screen.getByRole('button', { name: /send reset code/i }));

    // Invalid email format is caught - either by browser validation or custom validation
    expect(mockForgotPassword).not.toHaveBeenCalled();
    // Input is still there (form not submitted)
    expect(emailInput).toBeInTheDocument();
  });

  test('submits form with valid email', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockResolvedValue({ Destination: 't***@example.com' });

    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /send reset code/i }));

    await waitFor(() => {
      expect(mockForgotPassword).toHaveBeenCalledWith('test@example.com');
    });
  });

  test('shows success message after submission', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockResolvedValue({ Destination: 't***@example.com' });

    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /send reset code/i }));

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });
  });

  test('has link back to login', () => {
    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    // There are multiple sign in links - use getAllByRole and check length
    const signInLinks = screen.getAllByRole('link', { name: /sign in/i });
    expect(signInLinks.length).toBeGreaterThan(0);
  });

  test('allows navigating to enter code page after success', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockResolvedValue({ Destination: 't***@example.com' });

    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /send reset code/i }));

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });

    // Click the enter code button
    await user.click(screen.getByRole('button', { name: /enter reset code/i }));

    expect(mockNavigate).toHaveBeenCalledWith('/reset-password', expect.anything());
  });

  test('allows trying again if email not received', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockResolvedValue({ Destination: 't***@example.com' });

    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /send reset code/i }));

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });

    // Click try again
    await user.click(screen.getByRole('button', { name: /try again/i }));

    // Should show form again
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  test('has option to enter existing code', () => {
    render(
      <BrowserRouter>
        <ForgotPasswordPage />
      </BrowserRouter>
    );

    expect(screen.getByRole('button', { name: /enter code/i })).toBeInTheDocument();
  });
});
