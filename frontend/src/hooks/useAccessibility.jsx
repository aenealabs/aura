/**
 * Project Aura - Accessibility Hooks (ADR-060 Phase 3)
 *
 * WCAG 2.1 AA compliant accessibility utilities:
 * - useReducedMotion: Respects prefers-reduced-motion
 * - useAnnouncer: Screen reader announcements via ARIA live regions
 * - useHighContrast: Detects high contrast mode preference
 * - useKeyboardNavigation: Arrow key navigation within components
 */

import { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react';

// ============================================================================
// useReducedMotion Hook
// ============================================================================

/**
 * Hook to detect user's prefers-reduced-motion setting.
 * Components should disable animations when this returns true.
 *
 * @returns {boolean} - True if user prefers reduced motion
 *
 * @example
 * const prefersReducedMotion = useReducedMotion();
 * const animationClass = prefersReducedMotion ? '' : 'animate-fade-in';
 */
export function useReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    // Check initial preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    // Listen for changes
    const handleChange = (event) => {
      setPrefersReducedMotion(event.matches);
    };

    // Modern browsers
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }
    // Legacy browsers
    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return prefersReducedMotion;
}

// ============================================================================
// useHighContrast Hook
// ============================================================================

/**
 * Hook to detect user's high contrast mode preference.
 * Components can adjust colors for better visibility.
 *
 * @returns {boolean} - True if user prefers high contrast
 */
export function useHighContrast() {
  const [prefersHighContrast, setPrefersHighContrast] = useState(false);

  useEffect(() => {
    // Check for forced-colors (Windows High Contrast Mode)
    const mediaQuery = window.matchMedia('(forced-colors: active)');
    setPrefersHighContrast(mediaQuery.matches);

    const handleChange = (event) => {
      setPrefersHighContrast(event.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }
    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return prefersHighContrast;
}

// ============================================================================
// Announcer Context & Hook
// ============================================================================

const AnnouncerContext = createContext(null);

/**
 * Provider component for screen reader announcements.
 * Wrap your app with this to enable useAnnouncer hook.
 *
 * @example
 * <AnnouncerProvider>
 *   <App />
 * </AnnouncerProvider>
 */
export function AnnouncerProvider({ children }) {
  const [message, setMessage] = useState('');
  const [politeness, setPoliteness] = useState('polite');
  const timeoutRef = useRef(null);

  const announce = useCallback((text, level = 'polite') => {
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Clear message first to ensure re-announcement of same text
    setMessage('');
    setPoliteness(level);

    // Set new message after brief delay
    requestAnimationFrame(() => {
      setMessage(text);
    });

    // Clear after announcement
    timeoutRef.current = setTimeout(() => {
      setMessage('');
    }, 3000);
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <AnnouncerContext.Provider value={announce}>
      {children}
      {/* Polite announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {politeness === 'polite' && message}
      </div>
      {/* Assertive announcements (interrupts) */}
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {politeness === 'assertive' && message}
      </div>
    </AnnouncerContext.Provider>
  );
}

/**
 * Hook for announcing messages to screen readers.
 *
 * @returns {Function} - announce(message, politeness)
 *   - message: Text to announce
 *   - politeness: 'polite' (default) or 'assertive'
 *
 * @example
 * const announce = useAnnouncer();
 * announce('Diagram generated successfully');
 * announce('Error: Invalid input', 'assertive');
 */
export function useAnnouncer() {
  const context = useContext(AnnouncerContext);
  if (!context) {
    // Return no-op function if not within provider
    return () => {};
  }
  return context;
}

// ============================================================================
// useKeyboardNavigation Hook
// ============================================================================

/**
 * Hook for managing keyboard navigation within a component.
 * Supports arrow keys, Home, End, and typeahead.
 *
 * @param {Object} options - Configuration
 * @param {number} options.itemCount - Total number of items
 * @param {boolean} options.horizontal - Use left/right instead of up/down
 * @param {boolean} options.loop - Wrap around at ends (default: true)
 * @param {Function} options.onSelect - Callback when item is selected (Enter/Space)
 * @returns {Object} - { activeIndex, setActiveIndex, handleKeyDown, itemProps }
 *
 * @example
 * const { activeIndex, handleKeyDown, itemProps } = useKeyboardNavigation({
 *   itemCount: items.length,
 *   onSelect: (index) => selectItem(items[index]),
 * });
 */
export function useKeyboardNavigation({
  itemCount,
  horizontal = false,
  loop = true,
  onSelect,
  initialIndex = 0,
}) {
  const [activeIndex, setActiveIndex] = useState(initialIndex);

  const handleKeyDown = useCallback(
    (event) => {
      const { key } = event;
      let newIndex = activeIndex;
      let handled = false;

      const prevKey = horizontal ? 'ArrowLeft' : 'ArrowUp';
      const nextKey = horizontal ? 'ArrowRight' : 'ArrowDown';

      switch (key) {
        case prevKey:
          if (activeIndex > 0) {
            newIndex = activeIndex - 1;
          } else if (loop) {
            newIndex = itemCount - 1;
          }
          handled = true;
          break;

        case nextKey:
          if (activeIndex < itemCount - 1) {
            newIndex = activeIndex + 1;
          } else if (loop) {
            newIndex = 0;
          }
          handled = true;
          break;

        case 'Home':
          newIndex = 0;
          handled = true;
          break;

        case 'End':
          newIndex = itemCount - 1;
          handled = true;
          break;

        case 'Enter':
        case ' ':
          onSelect?.(activeIndex);
          handled = true;
          break;

        default:
          break;
      }

      if (handled) {
        event.preventDefault();
        setActiveIndex(newIndex);
      }
    },
    [activeIndex, itemCount, horizontal, loop, onSelect]
  );

  // Generate props for each item
  const getItemProps = useCallback(
    (index) => ({
      tabIndex: index === activeIndex ? 0 : -1,
      'aria-selected': index === activeIndex,
      onFocus: () => setActiveIndex(index),
    }),
    [activeIndex]
  );

  return {
    activeIndex,
    setActiveIndex,
    handleKeyDown,
    getItemProps,
  };
}

// ============================================================================
// useRovingTabIndex Hook
// ============================================================================

/**
 * Hook for managing roving tabindex pattern in toolbars and menus.
 * Only one item has tabindex=0; others have tabindex=-1.
 *
 * @param {React.RefObject} containerRef - Ref to the container element
 * @param {string} selector - CSS selector for focusable items
 * @returns {Object} - { currentIndex, setCurrentIndex }
 */
export function useRovingTabIndex(containerRef, selector = 'button') {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const items = container.querySelectorAll(selector);

    const handleKeyDown = (event) => {
      const { key } = event;
      const itemsArray = Array.from(items);
      let newIndex = currentIndex;

      switch (key) {
        case 'ArrowRight':
        case 'ArrowDown':
          newIndex = (currentIndex + 1) % itemsArray.length;
          break;
        case 'ArrowLeft':
        case 'ArrowUp':
          newIndex = (currentIndex - 1 + itemsArray.length) % itemsArray.length;
          break;
        case 'Home':
          newIndex = 0;
          break;
        case 'End':
          newIndex = itemsArray.length - 1;
          break;
        default:
          return;
      }

      event.preventDefault();
      setCurrentIndex(newIndex);
      itemsArray[newIndex]?.focus();
    };

    container.addEventListener('keydown', handleKeyDown);
    return () => container.removeEventListener('keydown', handleKeyDown);
  }, [containerRef, selector, currentIndex]);

  // Update tabindex on items
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const items = container.querySelectorAll(selector);
    items.forEach((item, index) => {
      item.setAttribute('tabindex', index === currentIndex ? '0' : '-1');
    });
  }, [containerRef, selector, currentIndex]);

  return { currentIndex, setCurrentIndex };
}

// ============================================================================
// VisuallyHidden Component
// ============================================================================

/**
 * Component for visually hiding content while keeping it accessible
 * to screen readers. Commonly used for skip links, labels, etc.
 *
 * @example
 * <VisuallyHidden>Skip to main content</VisuallyHidden>
 */
export function VisuallyHidden({ children, as: Component = 'span' }) {
  return (
    <Component className="sr-only">
      {children}
    </Component>
  );
}

// ============================================================================
// SkipLink Component
// ============================================================================

/**
 * Skip link for keyboard navigation.
 * Allows users to skip to main content without tabbing through navigation.
 *
 * @example
 * <SkipLink href="#main-content">Skip to main content</SkipLink>
 */
export function SkipLink({ href, children }) {
  return (
    <a
      href={href}
      className="
        sr-only focus:not-sr-only
        fixed top-4 left-4 z-[9999]
        px-4 py-2
        bg-aura-600 text-white font-medium
        rounded-lg shadow-lg
        focus:outline-none focus:ring-2 focus:ring-aura-400 focus:ring-offset-2
        transition-all duration-150
      "
    >
      {children}
    </a>
  );
}

// ============================================================================
// LiveRegion Component
// ============================================================================

/**
 * Live region component for dynamic status announcements.
 *
 * @param {string} message - Text to announce
 * @param {string} politeness - 'polite' or 'assertive'
 * @param {boolean} atomic - Announce entire region vs just changes
 */
export function LiveRegion({
  message,
  politeness = 'polite',
  atomic = true,
  className = '',
}) {
  return (
    <div
      role={politeness === 'assertive' ? 'alert' : 'status'}
      aria-live={politeness}
      aria-atomic={atomic}
      className={`sr-only ${className}`}
    >
      {message}
    </div>
  );
}

export default {
  useReducedMotion,
  useHighContrast,
  useAnnouncer,
  useKeyboardNavigation,
  useRovingTabIndex,
  AnnouncerProvider,
  VisuallyHidden,
  SkipLink,
  LiveRegion,
};
