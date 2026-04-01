import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import SignUpPage from './SignUpPage';

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
const mockSignUp = vi.fn();
const mockClearError = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    signUp: mockSignUp,
    loading: false,
    error: null,
    clearError: mockClearError,
    isAuthenticated: false,
  }),
}));

// Mock cognito config
vi.mock('../../config/cognito', () => ({
  validatePassword: vi.fn().mockReturnValue({ valid: true, errors: [] }),
  validateEmail: vi.fn().mockReturnValue(true),
  isDevMode: false,
}));

describe('SignUpPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders signup form', () => {
    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
  });

  test('shows name field', () => {
    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  test('shows confirm password field', () => {
    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  test('has submit button', () => {
    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    expect(screen.getByRole('button', { name: /sign up|create account/i })).toBeInTheDocument();
  });

  test('has link to login page', () => {
    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    // The component has "Already have an account? Sign in" with Sign in as a Link
    expect(screen.getByText(/already have an account/i)).toBeInTheDocument();
  });

  test('shows terms checkbox', () => {
    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/terms|agree/i)).toBeInTheDocument();
  });

  test('can fill out form fields', async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <SignUpPage />
      </BrowserRouter>
    );

    await user.type(screen.getByLabelText(/name/i), 'Test User');
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/^password/i), 'Password123!');
    await user.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    expect(screen.getByLabelText(/name/i)).toHaveValue('Test User');
    expect(screen.getByLabelText(/email/i)).toHaveValue('test@example.com');
  });
});
