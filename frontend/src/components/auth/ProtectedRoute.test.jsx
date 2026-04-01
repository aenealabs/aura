import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute, { SessionTimeoutModal, withAuth } from './ProtectedRoute';

// Mock AuthContext
vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '../../context/AuthContext';

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows loading spinner while checking auth', () => {
    useAuth.mockReturnValue({
      isAuthenticated: false,
      loading: true,
      hasRole: vi.fn(),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Verifying authentication...')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  test('redirects to login when not authenticated', () => {
    useAuth.mockReturnValue({
      isAuthenticated: false,
      loading: false,
      hasRole: vi.fn(),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  test('renders children when authenticated', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(true),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  test('shows access denied when user lacks required role', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(false),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole="admin">
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeInTheDocument();
    expect(screen.getByText(/Required role:/)).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
  });

  test('renders children when user has required role', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(true),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole="admin">
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Content')).toBeInTheDocument();
  });

  test('shows session timeout modal when session is expiring', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(true),
      sessionExpiring: true,
      extendSession: vi.fn(),
      signOut: vi.fn(),
    });

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Session Expiring')).toBeInTheDocument();
    expect(screen.getByText('Stay Signed In')).toBeInTheDocument();
    expect(screen.getByText('Sign Out')).toBeInTheDocument();
  });

  test('redirects to custom path when specified', () => {
    useAuth.mockReturnValue({
      isAuthenticated: false,
      loading: false,
      hasRole: vi.fn(),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/custom-login" element={<div>Custom Login</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute redirectTo="/custom-login">
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Custom Login')).toBeInTheDocument();
  });

  test('handles array of required roles', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(false),
      sessionExpiring: false,
    });

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole={['admin', 'editor']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('admin or editor')).toBeInTheDocument();
  });
});

describe('SessionTimeoutModal', () => {
  test('calls onExtend when Stay Signed In clicked', async () => {
    const user = userEvent.setup();
    const onExtend = vi.fn();
    const onLogout = vi.fn();

    render(<SessionTimeoutModal onExtend={onExtend} onLogout={onLogout} />);

    await user.click(screen.getByText('Stay Signed In'));

    expect(onExtend).toHaveBeenCalled();
    expect(onLogout).not.toHaveBeenCalled();
  });

  test('calls onLogout when Sign Out clicked', async () => {
    const user = userEvent.setup();
    const onExtend = vi.fn();
    const onLogout = vi.fn();

    render(<SessionTimeoutModal onExtend={onExtend} onLogout={onLogout} />);

    await user.click(screen.getByText('Sign Out'));

    expect(onLogout).toHaveBeenCalled();
    expect(onExtend).not.toHaveBeenCalled();
  });
});

describe('withAuth HOC', () => {
  test('wraps component with ProtectedRoute', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(true),
      sessionExpiring: false,
    });

    const TestComponent = () => <div>Test Component</div>;
    const WrappedComponent = withAuth(TestComponent);

    render(
      <MemoryRouter>
        <WrappedComponent />
      </MemoryRouter>
    );

    expect(screen.getByText('Test Component')).toBeInTheDocument();
  });

  test('passes options to ProtectedRoute', () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      hasRole: vi.fn().mockReturnValue(false),
      sessionExpiring: false,
    });

    const TestComponent = () => <div>Admin Component</div>;
    const WrappedComponent = withAuth(TestComponent, { requiredRole: 'admin' });

    render(
      <MemoryRouter>
        <WrappedComponent />
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeInTheDocument();
  });

  test('sets correct displayName', () => {
    const TestComponent = () => null;
    TestComponent.displayName = 'TestComponent';
    const WrappedComponent = withAuth(TestComponent);

    expect(WrappedComponent.displayName).toBe('withAuth(TestComponent)');
  });
});
