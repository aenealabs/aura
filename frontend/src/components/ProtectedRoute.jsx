import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// Loading spinner component
const LoadingSpinner = () => (
  <div className="min-h-screen bg-surface-50 dark:bg-surface-900 flex items-center justify-center">
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-12 h-12 mb-4">
        <svg
          className="animate-spin w-12 h-12 text-aura-600"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      </div>
      <p className="text-surface-600 dark:text-surface-400">Loading...</p>
    </div>
  </div>
);

// Access denied component
const AccessDenied = ({ requiredRole }) => (
  <div className="min-h-screen bg-surface-50 dark:bg-surface-900 flex items-center justify-center px-4">
    <div className="max-w-md w-full bg-white dark:bg-surface-800 rounded-xl shadow-lg p-8 text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 bg-critical-100 dark:bg-critical-900/30 rounded-full mb-6">
        <svg
          className="w-8 h-8 text-critical-600 dark:text-critical-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
          />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">Access Denied</h2>
      <p className="text-surface-600 dark:text-surface-400 mb-6">
        You don't have permission to access this page.
        {requiredRole && (
          <span className="block mt-1 text-sm">
            Required role: <span className="font-medium">{requiredRole}</span>
          </span>
        )}
      </p>
      <a
        href="/"
        className="inline-flex items-center px-4 py-2 bg-aura-600 text-white rounded-lg font-medium hover:bg-aura-700 transition-colors"
      >
        Go to Dashboard
      </a>
    </div>
  </div>
);

/**
 * ProtectedRoute - Wrapper component for authenticated routes
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components to render
 * @param {string|string[]} props.requiredRole - Required role(s) to access this route
 * @param {string} props.redirectTo - Where to redirect if not authenticated (default: /login)
 */
const ProtectedRoute = ({ children, requiredRole = null, redirectTo = '/login' }) => {
  const { isAuthenticated, loading, hasRole, user: _user } = useAuth();
  const location = useLocation();

  // Show loading state while checking authentication
  if (loading) {
    return <LoadingSpinner />;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    // Save the attempted location for redirect after login
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  // Check role-based access
  if (requiredRole && !hasRole(requiredRole)) {
    return <AccessDenied requiredRole={Array.isArray(requiredRole) ? requiredRole.join(' or ') : requiredRole} />;
  }

  // User is authenticated and has required role
  return children;
};

/**
 * Higher-order component version of ProtectedRoute
 *
 * @param {React.ComponentType} Component - Component to wrap
 * @param {Object} options - Options for protection
 * @param {string|string[]} options.requiredRole - Required role(s)
 * @param {string} options.redirectTo - Redirect path
 */
export const withAuth = (Component, options = {}) => {
  const { requiredRole = null, redirectTo = '/login' } = options;

  const WrappedComponent = (props) => (
    <ProtectedRoute requiredRole={requiredRole} redirectTo={redirectTo}>
      <Component {...props} />
    </ProtectedRoute>
  );

  WrappedComponent.displayName = `withAuth(${Component.displayName || Component.name || 'Component'})`;

  return WrappedComponent;
};

export default ProtectedRoute;
