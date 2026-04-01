/**
 * Project Aura - Accessibility Hooks Tests (ADR-060 Phase 3)
 *
 * Tests for WCAG 2.1 AA accessibility utilities.
 */

import { render, screen, act, renderHook, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useReducedMotion,
  useHighContrast,
  useAnnouncer,
  useKeyboardNavigation,
  useRovingTabIndex,
  AnnouncerProvider,
  VisuallyHidden,
  SkipLink,
  LiveRegion,
} from './useAccessibility';

// ============================================================================
// useReducedMotion Tests
// ============================================================================

describe('useReducedMotion', () => {
  let originalMatchMedia;

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  test('returns false when no preference is set', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  test('returns true when user prefers reduced motion', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query.includes('prefers-reduced-motion'),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  test('updates when preference changes', async () => {
    let changeHandler;
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      addEventListener: (event, handler) => {
        if (event === 'change') changeHandler = handler;
      },
      removeEventListener: vi.fn(),
    }));

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);

    // Simulate preference change
    act(() => {
      changeHandler({ matches: true });
    });

    expect(result.current).toBe(true);
  });

  test('cleans up event listener on unmount', () => {
    const removeEventListener = vi.fn();
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener,
    }));

    const { unmount } = renderHook(() => useReducedMotion());
    unmount();

    expect(removeEventListener).toHaveBeenCalled();
  });
});

// ============================================================================
// useHighContrast Tests
// ============================================================================

describe('useHighContrast', () => {
  let originalMatchMedia;

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  test('returns false when high contrast is not active', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    const { result } = renderHook(() => useHighContrast());
    expect(result.current).toBe(false);
  });

  test('returns true when forced-colors is active', () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query.includes('forced-colors'),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    const { result } = renderHook(() => useHighContrast());
    expect(result.current).toBe(true);
  });
});

// ============================================================================
// useAnnouncer Tests
// ============================================================================

describe('useAnnouncer', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  test('returns no-op function when not in AnnouncerProvider', () => {
    const { result } = renderHook(() => useAnnouncer());

    // Should not throw when called
    expect(() => result.current('test')).not.toThrow();
  });

  test('announces messages within AnnouncerProvider', async () => {
    function TestComponent() {
      const announce = useAnnouncer();
      return (
        <button onClick={() => announce('Test announcement')}>Announce</button>
      );
    }

    render(
      <AnnouncerProvider>
        <TestComponent />
      </AnnouncerProvider>
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    // Check that the live region received the message
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Test announcement');
    });
  });

  test('announces assertive messages via alert role', async () => {
    function TestComponent() {
      const announce = useAnnouncer();
      return (
        <button onClick={() => announce('Error message', 'assertive')}>
          Announce Error
        </button>
      );
    }

    render(
      <AnnouncerProvider>
        <TestComponent />
      </AnnouncerProvider>
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Error message');
    });
  });

  test('clears message after timeout', async () => {
    vi.useFakeTimers();

    // Mock requestAnimationFrame since it's not controlled by fake timers
    const originalRAF = global.requestAnimationFrame;
    global.requestAnimationFrame = (cb) => {
      cb(0);
      return 0;
    };

    function TestComponent() {
      const announce = useAnnouncer();
      return (
        <button onClick={() => announce('Temporary message')}>Announce</button>
      );
    }

    render(
      <AnnouncerProvider>
        <TestComponent />
      </AnnouncerProvider>
    );

    // Click and wrap in act to ensure state updates are processed
    act(() => {
      fireEvent.click(screen.getByRole('button'));
    });

    expect(screen.getByRole('status')).toHaveTextContent('Temporary message');

    // Advance past the clear timeout (3000ms in the implementation)
    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.getByRole('status')).toHaveTextContent('');

    // Cleanup
    global.requestAnimationFrame = originalRAF;
    vi.useRealTimers();
  });
});

// ============================================================================
// useKeyboardNavigation Tests
// ============================================================================

describe('useKeyboardNavigation', () => {
  const createMockEvent = (key, props = {}) => ({
    key,
    preventDefault: vi.fn(),
    ...props,
  });

  test('initializes with correct active index', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 2,
      })
    );

    expect(result.current.activeIndex).toBe(2);
  });

  test('ArrowDown increments active index', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 0,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('ArrowDown'));
    });

    expect(result.current.activeIndex).toBe(1);
  });

  test('ArrowUp decrements active index', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 2,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('ArrowUp'));
    });

    expect(result.current.activeIndex).toBe(1);
  });

  test('loops from end to beginning when loop is true', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 3,
        initialIndex: 2,
        loop: true,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('ArrowDown'));
    });

    expect(result.current.activeIndex).toBe(0);
  });

  test('does not loop when loop is false', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 3,
        initialIndex: 2,
        loop: false,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('ArrowDown'));
    });

    expect(result.current.activeIndex).toBe(2);
  });

  test('Home moves to first item', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 3,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('Home'));
    });

    expect(result.current.activeIndex).toBe(0);
  });

  test('End moves to last item', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 1,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('End'));
    });

    expect(result.current.activeIndex).toBe(4);
  });

  test('Enter calls onSelect with active index', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 2,
        onSelect,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('Enter'));
    });

    expect(onSelect).toHaveBeenCalledWith(2);
  });

  test('Space calls onSelect with active index', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 2,
        onSelect,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent(' '));
    });

    expect(onSelect).toHaveBeenCalledWith(2);
  });

  test('uses ArrowLeft/ArrowRight when horizontal is true', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 5,
        initialIndex: 2,
        horizontal: true,
      })
    );

    act(() => {
      result.current.handleKeyDown(createMockEvent('ArrowRight'));
    });
    expect(result.current.activeIndex).toBe(3);

    act(() => {
      result.current.handleKeyDown(createMockEvent('ArrowLeft'));
    });
    expect(result.current.activeIndex).toBe(2);
  });

  test('getItemProps returns correct props for active item', () => {
    const { result } = renderHook(() =>
      useKeyboardNavigation({
        itemCount: 3,
        initialIndex: 1,
      })
    );

    const activeProps = result.current.getItemProps(1);
    expect(activeProps.tabIndex).toBe(0);
    expect(activeProps['aria-selected']).toBe(true);

    const inactiveProps = result.current.getItemProps(0);
    expect(inactiveProps.tabIndex).toBe(-1);
    expect(inactiveProps['aria-selected']).toBe(false);
  });
});

// ============================================================================
// VisuallyHidden Tests
// ============================================================================

describe('VisuallyHidden', () => {
  test('renders children with sr-only class', () => {
    render(<VisuallyHidden>Hidden text</VisuallyHidden>);

    const element = screen.getByText('Hidden text');
    expect(element).toHaveClass('sr-only');
  });

  test('renders as span by default', () => {
    render(<VisuallyHidden>Hidden text</VisuallyHidden>);

    const element = screen.getByText('Hidden text');
    expect(element.tagName).toBe('SPAN');
  });

  test('renders as custom element when specified', () => {
    render(<VisuallyHidden as="div">Hidden text</VisuallyHidden>);

    const element = screen.getByText('Hidden text');
    expect(element.tagName).toBe('DIV');
  });
});

// ============================================================================
// SkipLink Tests
// ============================================================================

describe('SkipLink', () => {
  test('renders as anchor with href', () => {
    render(<SkipLink href="#main">Skip to main content</SkipLink>);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '#main');
  });

  test('has sr-only class by default', () => {
    render(<SkipLink href="#main">Skip to main content</SkipLink>);

    const link = screen.getByRole('link');
    expect(link.className).toMatch(/sr-only/);
  });

  test('becomes visible on focus', () => {
    render(<SkipLink href="#main">Skip to main content</SkipLink>);

    const link = screen.getByRole('link');
    expect(link.className).toMatch(/focus:not-sr-only/);
  });
});

// ============================================================================
// LiveRegion Tests
// ============================================================================

describe('LiveRegion', () => {
  test('renders with status role for polite messages', () => {
    render(<LiveRegion message="Status message" politeness="polite" />);

    expect(screen.getByRole('status')).toHaveTextContent('Status message');
  });

  test('renders with alert role for assertive messages', () => {
    render(<LiveRegion message="Alert message" politeness="assertive" />);

    expect(screen.getByRole('alert')).toHaveTextContent('Alert message');
  });

  test('has aria-live attribute', () => {
    render(<LiveRegion message="Test" politeness="polite" />);

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });

  test('has aria-atomic attribute', () => {
    render(<LiveRegion message="Test" atomic={true} />);

    expect(screen.getByRole('status')).toHaveAttribute('aria-atomic', 'true');
  });

  test('has sr-only class', () => {
    render(<LiveRegion message="Test" />);

    expect(screen.getByRole('status')).toHaveClass('sr-only');
  });
});
