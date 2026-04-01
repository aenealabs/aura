import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const AuthCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleCallback, error: authError } = useAuth();
  const [status, setStatus] = useState('processing');
  const [error, setError] = useState(null);

  useEffect(() => {
    const processCallback = async () => {
      const code = searchParams.get('code');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Handle OAuth error
      if (errorParam) {
        setStatus('error');
        setError(errorDescription || errorParam);
        return;
      }

      // No code provided
      if (!code) {
        setStatus('error');
        setError('No authorization code received');
        return;
      }

      // Exchange code for tokens
      try {
        setStatus('exchanging');
        const success = await handleCallback(code);

        if (success) {
          setStatus('success');
          // Redirect to dashboard after short delay
          setTimeout(() => {
            navigate('/', { replace: true });
          }, 1000);
        } else {
          setStatus('error');
          setError(authError || 'Failed to complete authentication');
        }
      } catch (err) {
        setStatus('error');
        setError(err.message || 'An unexpected error occurred');
      }
    };

    processCallback();
  }, [searchParams, handleCallback, navigate, authError]);

  const statusConfig = {
    processing: {
      title: 'Processing',
      message: 'Please wait while we verify your authentication...',
      titleClass: 'text-aura-600',
    },
    exchanging: {
      title: 'Authenticating',
      message: 'Exchanging authorization code for tokens...',
      titleClass: 'text-aura-600',
    },
    success: {
      title: 'Success',
      message: 'Authentication successful! Redirecting to dashboard...',
      titleClass: 'text-olive-600 dark:text-olive-400',
    },
    error: {
      title: 'Authentication Failed',
      message: error || 'An error occurred during authentication',
      titleClass: 'text-critical-600 dark:text-critical-400',
    },
  };

  const config = statusConfig[status];

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-900 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white dark:bg-surface-800 rounded-xl shadow-lg p-8 text-center">
        {/* Status Icon */}
        <div className="mb-6">
          {status === 'error' ? (
            <div className="inline-flex items-center justify-center w-16 h-16 bg-critical-100 dark:bg-critical-900/30 rounded-full">
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
          ) : status === 'success' ? (
            <div className="inline-flex items-center justify-center w-16 h-16 bg-olive-100 dark:bg-olive-900/30 rounded-full">
              <svg
                className="w-8 h-8 text-olive-600 dark:text-olive-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
          ) : (
            <div className="inline-flex items-center justify-center w-16 h-16 bg-aura-100 dark:bg-aura-900/30 rounded-full">
              <svg
                className="animate-spin w-8 h-8 text-aura-600"
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
          )}
        </div>

        {/* Title */}
        <h2 className={`text-xl font-semibold mb-2 ${config.titleClass}`}>
          {config.title}
        </h2>

        {/* Message */}
        <p className="text-surface-600 dark:text-surface-400 mb-6">{config.message}</p>

        {/* Error details */}
        {status === 'error' && error && (
          <div className="mb-6 p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg text-left">
            <p className="text-sm text-critical-600 dark:text-critical-400">{error}</p>
          </div>
        )}

        {/* Actions */}
        {status === 'error' && (
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate('/login', { replace: true })}
              className="px-4 py-2 bg-aura-600 text-white rounded-lg font-medium hover:bg-aura-700 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={() => navigate('/', { replace: true })}
              className="px-4 py-2 bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-lg font-medium hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
            >
              Go Home
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuthCallback;
