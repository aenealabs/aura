import { useAuth } from '../context/AuthContext';
import { ShieldCheckIcon, LockClosedIcon, KeyIcon } from '@heroicons/react/24/outline';

const LoginPage = () => {
  const { login, loading, error } = useAuth();

  const features = [
    {
      icon: ShieldCheckIcon,
      title: 'Enterprise Security',
      description: 'CMMC Level 2 compliant authentication with MFA support',
    },
    {
      icon: LockClosedIcon,
      title: 'Secure Access',
      description: 'Role-based access control for HITL approvals',
    },
    {
      icon: KeyIcon,
      title: 'SSO Ready',
      description: 'Single sign-on with your organization credentials',
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-900 via-aura-900 to-surface-900 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 mb-4">
            <img
              src="/assets/aura-spiral.png"
              alt="Aura Logo"
              className="w-16 h-16 object-contain drop-shadow-lg"
            />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Project Aura</h1>
          <p className="text-surface-400">Autonomous Code Intelligence Platform</p>
        </div>

        {/* Login Card */}
        <div className="bg-white dark:bg-surface-800 rounded-2xl shadow-2xl p-8 border border-surface-200 dark:border-surface-700">
          <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 text-center mb-6">
            Sign in to continue
          </h2>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-800 rounded-lg">
              <p className="text-sm text-critical-600 dark:text-critical-400">{error}</p>
            </div>
          )}

          {/* Login Button */}
          <button
            onClick={login}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-aura-600 text-white rounded-lg font-medium hover:bg-aura-700 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin h-5 w-5 text-white"
                  xmlns="http://www.w3.org/2000/svg"
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
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <LockClosedIcon className="w-5 h-5" />
                <span>Sign in with Aenea Labs</span>
              </>
            )}
          </button>

          {/* Divider */}
          <div className="mt-6 mb-4 flex items-center">
            <div className="flex-1 border-t border-surface-200 dark:border-surface-700"></div>
            <span className="px-3 text-sm text-surface-500 dark:text-surface-400">Secure Login</span>
            <div className="flex-1 border-t border-surface-200 dark:border-surface-700"></div>
          </div>

          {/* Features */}
          <div className="space-y-3">
            {features.map((feature, index) => (
              <div key={index} className="flex items-start gap-3">
                <feature.icon className="w-5 h-5 text-aura-600 dark:text-aura-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-surface-900 dark:text-surface-100">{feature.title}</p>
                  <p className="text-xs text-surface-500 dark:text-surface-400">{feature.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-surface-500 dark:text-surface-400 text-sm mt-6">
          Aenea Labs
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
