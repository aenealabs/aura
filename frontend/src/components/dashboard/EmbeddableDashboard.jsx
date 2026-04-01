/**
 * Embeddable Dashboard Component
 *
 * Renders a dashboard in embed mode for iframe/external application usage.
 * Supports multiple display modes, themes, and customization options.
 *
 * Features:
 * - Full, minimal, and widget-only display modes
 * - Light, dark, and auto themes
 * - Optional title, refresh, and fullscreen controls
 * - Custom CSS injection support
 * - Responsive layout
 *
 * @module components/dashboard/EmbeddableDashboard
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';

// Embed display modes
const EmbedMode = {
  FULL: 'full',
  MINIMAL: 'minimal',
  WIDGET_ONLY: 'widget_only',
};

// Theme options
const EmbedTheme = {
  LIGHT: 'light',
  DARK: 'dark',
  AUTO: 'auto',
};

/**
 * Hook to fetch embedded dashboard data
 */
export function useEmbeddedDashboard(token) {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboard = useCallback(async () => {
    if (!token) {
      setError('No embed token provided');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Get requesting domain for validation
      const domain = window.location.hostname;
      const response = await fetch(
        `/api/v1/embed/${token}?domain=${encodeURIComponent(domain)}`
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to load dashboard');
      }

      const data = await response.json();
      setDashboard(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  return { dashboard, loading, error, refetch: fetchDashboard };
}

/**
 * Theme styles for embedded dashboard
 */
const getThemeStyles = (theme, systemPrefersDark) => {
  const isDark =
    theme === EmbedTheme.DARK ||
    (theme === EmbedTheme.AUTO && systemPrefersDark);

  return {
    container: {
      backgroundColor: isDark ? '#1a1a2e' : '#ffffff',
      color: isDark ? '#e4e4e7' : '#18181b',
      minHeight: '100%',
      fontFamily:
        'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    },
    header: {
      backgroundColor: isDark ? '#16162a' : '#f4f4f5',
      borderBottom: `1px solid ${isDark ? '#27273f' : '#e4e4e7'}`,
      padding: '12px 16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    },
    title: {
      fontSize: '18px',
      fontWeight: 600,
      margin: 0,
      color: isDark ? '#ffffff' : '#18181b',
    },
    description: {
      fontSize: '13px',
      color: isDark ? '#a1a1aa' : '#71717a',
      margin: '4px 0 0 0',
    },
    controls: {
      display: 'flex',
      gap: '8px',
    },
    button: {
      backgroundColor: isDark ? '#27273f' : '#e4e4e7',
      color: isDark ? '#e4e4e7' : '#18181b',
      border: 'none',
      borderRadius: '6px',
      padding: '8px 12px',
      fontSize: '13px',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      transition: 'background-color 0.15s',
    },
    content: {
      padding: '16px',
    },
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
      gap: '16px',
    },
    widget: {
      backgroundColor: isDark ? '#16162a' : '#ffffff',
      border: `1px solid ${isDark ? '#27273f' : '#e4e4e7'}`,
      borderRadius: '8px',
      padding: '16px',
      boxShadow: isDark
        ? '0 1px 3px rgba(0,0,0,0.3)'
        : '0 1px 3px rgba(0,0,0,0.1)',
    },
    widgetTitle: {
      fontSize: '14px',
      fontWeight: 600,
      color: isDark ? '#ffffff' : '#18181b',
      marginBottom: '12px',
    },
    loading: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      color: isDark ? '#a1a1aa' : '#71717a',
    },
    error: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      color: '#ef4444',
      textAlign: 'center',
      padding: '24px',
    },
  };
};

/**
 * Refresh icon SVG
 */
const RefreshIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

/**
 * Fullscreen icon SVG
 */
const FullscreenIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="15 3 21 3 21 9" />
    <polyline points="9 21 3 21 3 15" />
    <line x1="21" y1="3" x2="14" y2="10" />
    <line x1="3" y1="21" x2="10" y2="14" />
  </svg>
);

/**
 * Widget placeholder component
 */
const WidgetPlaceholder = ({ widget, styles }) => (
  <div style={styles.widget}>
    <div style={styles.widgetTitle}>{widget.title || widget.type || 'Widget'}</div>
    <div
      style={{
        height: '120px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderRadius: '4px',
        color: '#3b82f6',
        fontSize: '13px',
      }}
    >
      {widget.type || 'metric'}
    </div>
  </div>
);

WidgetPlaceholder.propTypes = {
  widget: PropTypes.shape({
    id: PropTypes.string,
    type: PropTypes.string,
    title: PropTypes.string,
  }).isRequired,
  styles: PropTypes.object.isRequired,
};

/**
 * Loading spinner component
 */
const LoadingSpinner = ({ styles }) => (
  <div style={styles.loading}>
    <div
      style={{
        width: '32px',
        height: '32px',
        border: '3px solid currentColor',
        borderTopColor: 'transparent',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
      }}
    />
    <style>
      {`@keyframes spin { to { transform: rotate(360deg); } }`}
    </style>
  </div>
);

LoadingSpinner.propTypes = {
  styles: PropTypes.object.isRequired,
};

/**
 * Error display component
 */
const ErrorDisplay = ({ error, onRetry, styles }) => (
  <div style={styles.error}>
    <svg
      width="48"
      height="48"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      style={{ marginBottom: '16px' }}
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
    <div style={{ fontSize: '16px', fontWeight: 500, marginBottom: '8px' }}>
      Unable to Load Dashboard
    </div>
    <div style={{ fontSize: '14px', opacity: 0.8, marginBottom: '16px' }}>
      {error}
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        style={{
          backgroundColor: '#ef4444',
          color: '#ffffff',
          border: 'none',
          borderRadius: '6px',
          padding: '8px 16px',
          fontSize: '13px',
          cursor: 'pointer',
        }}
      >
        Try Again
      </button>
    )}
  </div>
);

ErrorDisplay.propTypes = {
  error: PropTypes.string.isRequired,
  onRetry: PropTypes.func,
  styles: PropTypes.object.isRequired,
};

/**
 * Embeddable Dashboard Component
 *
 * Main component for rendering dashboards in embed mode.
 */
const EmbeddableDashboard = ({
  token,
  // Override props (if dashboard data is passed directly)
  dashboardData,
  mode: modeProp,
  theme: themeProp,
  showTitle: showTitleProp,
  showRefresh: showRefreshProp,
  showFullscreen: showFullscreenProp,
  customCss,
  onRefresh,
  className,
  style,
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Detect system dark mode preference
  const [systemPrefersDark, setSystemPrefersDark] = useState(
    typeof window !== 'undefined' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => setSystemPrefersDark(e.matches);

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Fetch dashboard if token provided (and no dashboardData override)
  const { dashboard, loading, error, refetch } = useEmbeddedDashboard(
    dashboardData ? null : token
  );

  // Use override data if provided
  const data = dashboardData || dashboard;
  const mode = modeProp || data?.mode || EmbedMode.MINIMAL;
  const theme = themeProp || data?.theme || EmbedTheme.LIGHT;
  const showTitle = showTitleProp ?? data?.show_title ?? true;
  const showRefresh = showRefreshProp ?? data?.show_refresh ?? true;
  const showFullscreen = showFullscreenProp ?? data?.show_fullscreen ?? false;
  const css = customCss || data?.custom_css;

  // Get theme-appropriate styles
  const styles = useMemo(
    () => getThemeStyles(theme, systemPrefersDark),
    [theme, systemPrefersDark]
  );

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    if (onRefresh) {
      await onRefresh();
    } else {
      await refetch();
    }
    setRefreshing(false);
  }, [onRefresh, refetch]);

  // Handle fullscreen toggle
  const handleFullscreen = useCallback(() => {
    const container = document.getElementById('embed-dashboard-container');
    if (!container) return;

    if (!isFullscreen) {
      if (container.requestFullscreen) {
        container.requestFullscreen();
      } else if (container.webkitRequestFullscreen) {
        container.webkitRequestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  // Loading state
  if (loading) {
    return (
      <div style={{ ...styles.container, ...style }} className={className}>
        <LoadingSpinner styles={styles} />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div style={{ ...styles.container, ...style }} className={className}>
        <ErrorDisplay error={error} onRetry={refetch} styles={styles} />
      </div>
    );
  }

  // No data state
  if (!data) {
    return (
      <div style={{ ...styles.container, ...style }} className={className}>
        <ErrorDisplay error="No dashboard data available" styles={styles} />
      </div>
    );
  }

  // Widget-only mode
  if (mode === EmbedMode.WIDGET_ONLY) {
    const widgets = data.widgets || [];
    return (
      <div
        id="embed-dashboard-container"
        style={{ ...styles.container, ...style }}
        className={className}
      >
        {css && <style>{css}</style>}
        <div style={styles.content}>
          <div style={styles.grid}>
            {widgets.map((widget, index) => (
              <WidgetPlaceholder
                key={widget.id || index}
                widget={widget}
                styles={styles}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Full or minimal mode
  const showHeader = mode === EmbedMode.FULL || showTitle || showRefresh || showFullscreen;

  return (
    <div
      id="embed-dashboard-container"
      style={{ ...styles.container, ...style }}
      className={className}
    >
      {css && <style>{css}</style>}

      {showHeader && (
        <div style={styles.header}>
          <div>
            {showTitle && <h1 style={styles.title}>{data.name}</h1>}
            {showTitle && data.description && (
              <p style={styles.description}>{data.description}</p>
            )}
          </div>

          <div style={styles.controls}>
            {showRefresh && (
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                style={{
                  ...styles.button,
                  opacity: refreshing ? 0.6 : 1,
                }}
                title="Refresh"
              >
                <RefreshIcon />
                {mode === EmbedMode.FULL && 'Refresh'}
              </button>
            )}

            {showFullscreen && (
              <button
                onClick={handleFullscreen}
                style={styles.button}
                title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
              >
                <FullscreenIcon />
                {mode === EmbedMode.FULL && (isFullscreen ? 'Exit' : 'Fullscreen')}
              </button>
            )}
          </div>
        </div>
      )}

      <div style={styles.content}>
        <div style={styles.grid}>
          {(data.widgets || []).map((widget, index) => (
            <WidgetPlaceholder
              key={widget.id || index}
              widget={widget}
              styles={styles}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

EmbeddableDashboard.propTypes = {
  /** Embed token for fetching dashboard */
  token: PropTypes.string,
  /** Direct dashboard data (overrides token fetch) */
  dashboardData: PropTypes.shape({
    dashboard_id: PropTypes.string,
    name: PropTypes.string,
    description: PropTypes.string,
    layout: PropTypes.object,
    widgets: PropTypes.array,
    mode: PropTypes.string,
    theme: PropTypes.string,
    show_title: PropTypes.bool,
    show_refresh: PropTypes.bool,
    show_fullscreen: PropTypes.bool,
    custom_css: PropTypes.string,
  }),
  /** Display mode override */
  mode: PropTypes.oneOf(Object.values(EmbedMode)),
  /** Theme override */
  theme: PropTypes.oneOf(Object.values(EmbedTheme)),
  /** Show title override */
  showTitle: PropTypes.bool,
  /** Show refresh button override */
  showRefresh: PropTypes.bool,
  /** Show fullscreen toggle override */
  showFullscreen: PropTypes.bool,
  /** Custom CSS to inject */
  customCss: PropTypes.string,
  /** Custom refresh handler */
  onRefresh: PropTypes.func,
  /** Additional CSS class */
  className: PropTypes.string,
  /** Inline styles */
  style: PropTypes.object,
};

EmbeddableDashboard.defaultProps = {
  token: null,
  dashboardData: null,
  mode: null,
  theme: null,
  showTitle: null,
  showRefresh: null,
  showFullscreen: null,
  customCss: null,
  onRefresh: null,
  className: '',
  style: {},
};

export default EmbeddableDashboard;
export { EmbedMode, EmbedTheme };
