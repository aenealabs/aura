/**
 * useFocusTrap Hook
 *
 * WCAG 2.1 AA compliant focus trap for modals and dialogs.
 * Traps keyboard focus within a specified container.
 *
 * Features:
 * - Traps Tab and Shift+Tab within container
 * - Focuses first focusable element on open
 * - Returns focus to trigger element on close
 * - Handles dynamic content updates
 */

import { useEffect, useRef, useCallback } from 'react';

// Focusable element selectors
const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  'audio[controls]',
  'video[controls]',
  '[contenteditable]:not([contenteditable="false"])',
].join(',');

/**
 * Hook to trap focus within a container element
 * @param {boolean} isActive - Whether the focus trap is active
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoFocus - Auto-focus first element on activation (default: true)
 * @param {boolean} options.restoreFocus - Restore focus to previous element on deactivation (default: true)
 * @param {boolean} options.escapeDeactivates - Close on Escape key (default: true)
 * @param {Function} options.onEscape - Callback when Escape is pressed
 * @returns {Object} - { containerRef, firstFocusableRef }
 */
export function useFocusTrap(isActive, options = {}) {
  const {
    autoFocus = true,
    restoreFocus = true,
    escapeDeactivates = true,
    onEscape,
  } = options;

  const containerRef = useRef(null);
  const firstFocusableRef = useRef(null);
  const previousActiveElementRef = useRef(null);

  // Get all focusable elements within container
  const getFocusableElements = useCallback(() => {
    if (!containerRef.current) return [];
    const elements = containerRef.current.querySelectorAll(FOCUSABLE_SELECTORS);
    return Array.from(elements).filter(
      (el) => el.offsetParent !== null && !el.hasAttribute('inert')
    );
  }, []);

  // Handle keydown events
  useEffect(() => {
    if (!isActive) return;

    const handleKeyDown = (event) => {
      // Handle Escape key
      if (event.key === 'Escape' && escapeDeactivates) {
        event.preventDefault();
        onEscape?.();
        return;
      }

      // Handle Tab key for focus trapping
      if (event.key !== 'Tab') return;

      const focusableElements = getFocusableElements();
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      // Shift + Tab: go to last element if on first
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
        return;
      }

      // Tab: go to first element if on last
      if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
        return;
      }

      // If focus is outside container, move it inside
      if (
        containerRef.current &&
        !containerRef.current.contains(document.activeElement)
      ) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isActive, escapeDeactivates, onEscape, getFocusableElements]);

  // Store previous active element and auto-focus first element
  useEffect(() => {
    if (!isActive) return;

    // Store the currently focused element
    if (restoreFocus) {
      previousActiveElementRef.current = document.activeElement;
    }

    // Auto-focus first focusable element
    if (autoFocus) {
      // Use requestAnimationFrame to ensure DOM is ready
      requestAnimationFrame(() => {
        if (firstFocusableRef.current) {
          firstFocusableRef.current.focus();
        } else {
          const focusableElements = getFocusableElements();
          if (focusableElements.length > 0) {
            focusableElements[0].focus();
          }
        }
      });
    }

    // Cleanup: restore focus when deactivated
    return () => {
      if (restoreFocus && previousActiveElementRef.current) {
        previousActiveElementRef.current.focus?.();
      }
    };
  }, [isActive, autoFocus, restoreFocus, getFocusableElements]);

  // Prevent focus from leaving container via click
  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const handleFocusIn = (event) => {
      if (!containerRef.current) return;

      // Check if container is actually visible and interactive
      const style = window.getComputedStyle(containerRef.current);
      if (style.pointerEvents === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
        return; // Don't trap focus if container is hidden
      }

      if (!containerRef.current.contains(event.target)) {
        const focusableElements = getFocusableElements();
        if (focusableElements.length > 0) {
          focusableElements[0].focus();
        }
      }
    };

    document.addEventListener('focusin', handleFocusIn);
    return () => document.removeEventListener('focusin', handleFocusIn);
  }, [isActive, getFocusableElements]);

  return {
    containerRef,
    firstFocusableRef,
  };
}

export default useFocusTrap;
