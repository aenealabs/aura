/**
 * React-rendering smoke tests for the SDK hooks.
 *
 * The previous test suite was pure-logic only (utils/client) and did not
 * actually render any of the SDK's React hooks. Following the React 19
 * upgrade we need at least one test that mounts a component using the
 * hooks via @testing-library/react, so future regressions in the
 * React-version-touching code surface in CI rather than at consumer
 * install time.
 *
 * The same test passes against React 18 (RTL 14, vitest 1) and React 19
 * (RTL 16, vitest 4) because the hooks only consume the
 * version-agnostic core API (useState/useEffect/useCallback/useMemo/
 * useRef/useContext) and a deprecated-but-supported <Context.Provider>.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import type { ReactNode } from 'react';

import {
  AuraProvider,
  useAuraClient,
  useAuraConnection,
} from '../hooks';

describe('AuraProvider + core hooks (React render)', () => {
  beforeEach(() => {
    // Each test installs its own fetch mock — keep tests isolated.
    vi.unstubAllGlobals();
  });

  it('useAuraClient throws outside a provider', () => {
    // RTL surfaces the throw via the hook callback; we expect the runtime
    // error rather than an undefined client to come back.
    expect(() => renderHook(() => useAuraClient())).toThrow(
      /useAuraClient must be used within an AuraProvider/,
    );
  });

  it('useAuraClient returns the configured client inside a provider', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuraProvider baseUrl="https://api.aura.test" apiKey="test-key">
        {children}
      </AuraProvider>
    );
    const { result } = renderHook(() => useAuraClient(), { wrapper });
    expect(result.current).toBeDefined();
    expect(typeof result.current.healthCheck).toBe('function');
  });

  it('useAuraConnection updates after the health probe resolves', async () => {
    // Stub the global fetch with a healthy response; the provider runs
    // healthCheck() in useEffect and flips isConnected to true on success.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'healthy' }),
      text: async () => '{"status":"healthy"}',
      headers: new Headers({ 'content-type': 'application/json' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuraProvider baseUrl="https://api.aura.test" apiKey="test-key">
        {children}
      </AuraProvider>
    );
    const { result } = renderHook(() => useAuraConnection(), { wrapper });

    // Initial render: not yet connected.
    expect(result.current).toBe(false);

    // After the effect runs and the mocked fetch resolves, flips to true.
    await waitFor(() => {
      expect(result.current).toBe(true);
    });

    expect(fetchMock).toHaveBeenCalled();
  });

  it('useAuraConnection stays false when the health probe rejects', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('network down'));
    vi.stubGlobal('fetch', fetchMock);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuraProvider baseUrl="https://api.aura.test" apiKey="test-key">
        {children}
      </AuraProvider>
    );
    const { result } = renderHook(() => useAuraConnection(), { wrapper });

    // Give the rejection a tick to propagate through the promise chain.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current).toBe(false);
  });
});
