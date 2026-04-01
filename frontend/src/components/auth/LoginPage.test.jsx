import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './LoginPage';

// Mock AuthContext
vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

// Mock cognito config
vi.mock('../../config/cognito', () => ({
  isDevMode: false,
}));

import { useAuth } from '../../context/AuthContext';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('LoginPage', () => {
  const defaultAuthValues = {
    signIn: vi.fn(),
    verifyMfa: vi.fn(),
    setNewPassword: vi.fn(),
    loading: false,
    error: null,
    clearError: vi.fn(),
    isAuthenticated: false,
    pendingChallenge: null,
    getRememberedEmail: vi.fn().mockReturnValue(null),
    checkRememberMe: vi.fn().mockReturnValue(false),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue(defaultAuthValues);
  });

  test('renders login form', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  test('shows forgot password link', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/forgot password/i)).toBeInTheDocument();
  });

  test('shows sign up link', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    // The actual text is "Sign up" in the link
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument();
  });

  test('shows remember me checkbox', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/remember me/i)).toBeInTheDocument();
  });

  test('validates empty email', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    const emailInput = screen.getByLabelText(/email/i);

    // Click submit without entering email - browser validation prevents submission
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // The form shouldn't submit due to required field validation
    expect(defaultAuthValues.signIn).not.toHaveBeenCalled();
    // Input should have required attribute
    expect(emailInput).toBeRequired();
  });

  test('calls signIn with email and password', async () => {
    const user = userEvent.setup();
    defaultAuthValues.signIn.mockResolvedValue({ success: true });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(defaultAuthValues.signIn).toHaveBeenCalledWith(
        'test@example.com',
        'password123',
        false
      );
    });
  });

  test('calls signIn with rememberMe checked', async () => {
    const user = userEvent.setup();
    defaultAuthValues.signIn.mockResolvedValue({ success: true });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByLabelText(/remember me/i));
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(defaultAuthValues.signIn).toHaveBeenCalledWith(
        'test@example.com',
        'password123',
        true
      );
    });
  });

  test('displays auth error', () => {
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      error: 'Invalid credentials',
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
  });

  test('shows loading state during sign in', () => {
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      loading: true,
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    // SubmitButton shows "Processing..." when loading
    expect(screen.getByRole('button', { name: /processing/i })).toBeDisabled();
  });

  test('redirects when already authenticated', () => {
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      isAuthenticated: true,
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
  });

  test('populates email from remembered value', () => {
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      getRememberedEmail: vi.fn().mockReturnValue('remembered@example.com'),
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/email/i)).toHaveValue('remembered@example.com');
    expect(screen.getByLabelText(/remember me/i)).toBeChecked();
  });

  test('shows MFA input when MFA is required', async () => {
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      pendingChallenge: { type: 'MFA', mfaType: 'SMS_MFA' },
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument();
  });

  test('shows new password form when new password required', async () => {
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      pendingChallenge: { type: 'NEW_PASSWORD' },
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    // Both "New password" and "Confirm new password" should be visible
    const passwordInputs = screen.getAllByLabelText(/password/i);
    expect(passwordInputs.length).toBeGreaterThanOrEqual(2);
  });

  test('clears errors on input change', async () => {
    const user = userEvent.setup();
    useAuth.mockReturnValue({
      ...defaultAuthValues,
      error: 'Some error',
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/email/i), 'a');

    expect(defaultAuthValues.clearError).toHaveBeenCalled();
  });
});
