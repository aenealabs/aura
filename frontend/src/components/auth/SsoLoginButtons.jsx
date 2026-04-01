/**
 * SSO Login Buttons Component
 *
 * Displays configured identity providers as login options.
 * Supports email-based provider auto-detection.
 *
 * ADR-054: Multi-IdP Authentication
 */

import { useState, useEffect } from 'react';
import {
  ServerStackIcon,
  KeyIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  CloudIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import {
  getEnabledIdentityProviders,
  getProviderForEmail,
  initiateSsoAuth,
} from '../../services/identityProviderApi';

// Icon mapping for IdP types
const TYPE_ICONS = {
  ldap: ServerStackIcon,
  saml: KeyIcon,
  oidc: GlobeAltIcon,
  pingid: ShieldCheckIcon,
  cognito: CloudIcon,
};

// Protocol labels
const TYPE_LABELS = {
  ldap: 'LDAP',
  saml: 'SAML',
  oidc: 'OIDC',
  pingid: 'PingID',
  cognito: 'Cognito',
};

export default function SsoLoginButtons({ email, onError, className = '' }) {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [authenticating, setAuthenticating] = useState(null);
  const [detectedProvider, setDetectedProvider] = useState(null);

  // Load enabled providers
  useEffect(() => {
    const loadProviders = async () => {
      try {
        const enabledProviders = await getEnabledIdentityProviders();
        setProviders(enabledProviders);
      } catch (err) {
        console.error('Failed to load identity providers:', err);
      } finally {
        setLoading(false);
      }
    };

    loadProviders();
  }, []);

  // Detect provider based on email domain
  useEffect(() => {
    const detectProvider = async () => {
      if (!email || !email.includes('@')) {
        setDetectedProvider(null);
        return;
      }

      try {
        const provider = await getProviderForEmail(email);
        setDetectedProvider(provider);
      } catch (err) {
        console.error('Failed to detect provider:', err);
        setDetectedProvider(null);
      }
    };

    // Debounce email detection
    const timeout = setTimeout(detectProvider, 500);
    return () => clearTimeout(timeout);
  }, [email]);

  const handleSsoLogin = async (provider) => {
    setAuthenticating(provider.id);
    try {
      const result = await initiateSsoAuth(provider.id);
      if (result.redirect_url) {
        // Redirect to IdP
        window.location.href = result.redirect_url;
      }
    } catch (err) {
      onError?.(err.message || 'SSO authentication failed');
      setAuthenticating(null);
    }
  };

  // Don't show anything if no providers
  if (!loading && providers.length === 0) {
    return null;
  }

  // Loading state
  if (loading) {
    return (
      <div className={`space-y-3 ${className}`}>
        <div className="flex items-center justify-center py-4">
          <ArrowPathIcon className="h-5 w-5 text-surface-400 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Detected Provider Banner */}
      {detectedProvider && (
        <div className="p-3 bg-aura-50 dark:bg-aura-900/20 border border-aura-200/50 dark:border-aura-800/50 rounded-lg">
          <p className="text-sm text-aura-700 dark:text-aura-300 mb-2">
            We detected your organization uses{' '}
            <span className="font-medium">{detectedProvider.display_name}</span>
          </p>
          <button
            onClick={() => handleSsoLogin(detectedProvider)}
            disabled={authenticating === detectedProvider.id}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-aura-600 text-white font-medium rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {authenticating === detectedProvider.id ? (
              <>
                <ArrowPathIcon className="h-5 w-5 animate-spin" />
                <span>Connecting...</span>
              </>
            ) : (
              <>
                {(() => {
                  const Icon = TYPE_ICONS[detectedProvider.type] || KeyIcon;
                  return <Icon className="h-5 w-5" />;
                })()}
                <span>Continue with {detectedProvider.display_name}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-surface-200 dark:border-surface-700" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-3 bg-white dark:bg-surface-800 text-surface-500">
            {detectedProvider ? 'Or sign in with' : 'Sign in with SSO'}
          </span>
        </div>
      </div>

      {/* Provider Buttons */}
      <div className="grid grid-cols-1 gap-2">
        {providers
          .filter((p) => p.id !== detectedProvider?.id) // Exclude detected provider
          .map((provider) => {
            const Icon = TYPE_ICONS[provider.type] || KeyIcon;
            const isLoading = authenticating === provider.id;

            return (
              <button
                key={provider.id}
                onClick={() => handleSsoLogin(provider)}
                disabled={!!authenticating}
                className="flex items-center justify-center gap-3 px-4 py-2.5 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 hover:bg-surface-50 dark:hover:bg-surface-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <ArrowPathIcon className="h-5 w-5 text-surface-400 animate-spin" />
                ) : (
                  <Icon className="h-5 w-5 text-surface-600 dark:text-surface-400" />
                )}
                <span className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  {provider.display_name}
                </span>
                <span className="text-xs text-surface-500 dark:text-surface-400">
                  ({TYPE_LABELS[provider.type]})
                </span>
              </button>
            );
          })}
      </div>

      {/* Or divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-surface-200 dark:border-surface-700" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-3 bg-white dark:bg-surface-800 text-surface-500">
            Or continue with email
          </span>
        </div>
      </div>
    </div>
  );
}
