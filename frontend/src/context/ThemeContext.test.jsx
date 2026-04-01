import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';

// Test component to access theme context
function TestConsumer() {
  const { isDarkMode, toggleTheme, setTheme, theme } = useTheme();
  return (
    <div>
      <span data-testid="is-dark">{isDarkMode ? 'true' : 'false'}</span>
      <span data-testid="theme">{theme}</span>
      <button data-testid="toggle" onClick={toggleTheme}>Toggle</button>
      <button data-testid="set-dark" onClick={() => setTheme('dark')}>Set Dark</button>
      <button data-testid="set-light" onClick={() => setTheme('light')}>Set Light</button>
    </div>
  );
}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  describe('ThemeProvider', () => {
    test('provides default light theme when no preference saved', () => {
      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('is-dark')).toHaveTextContent('false');
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    test('reads dark theme from localStorage', () => {
      localStorage.setItem('aura-theme', 'dark');

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('is-dark')).toHaveTextContent('true');
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    });

    test('reads light theme from localStorage', () => {
      localStorage.setItem('aura-theme', 'light');

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('is-dark')).toHaveTextContent('false');
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    test('toggleTheme switches between light and dark', async () => {
      const user = userEvent.setup();

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      expect(screen.getByTestId('is-dark')).toHaveTextContent('false');

      await user.click(screen.getByTestId('toggle'));
      expect(screen.getByTestId('is-dark')).toHaveTextContent('true');

      await user.click(screen.getByTestId('toggle'));
      expect(screen.getByTestId('is-dark')).toHaveTextContent('false');
    });

    test('setTheme sets specific theme', async () => {
      const user = userEvent.setup();

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('set-dark'));
      expect(screen.getByTestId('theme')).toHaveTextContent('dark');

      await user.click(screen.getByTestId('set-light'));
      expect(screen.getByTestId('theme')).toHaveTextContent('light');
    });

    test('applies dark class to document when dark mode enabled', async () => {
      const user = userEvent.setup();

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('set-dark'));
      expect(document.documentElement.classList.contains('dark')).toBe(true);

      await user.click(screen.getByTestId('set-light'));
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    test('persists theme preference to localStorage', async () => {
      const user = userEvent.setup();

      render(
        <ThemeProvider>
          <TestConsumer />
        </ThemeProvider>
      );

      await user.click(screen.getByTestId('set-dark'));
      expect(localStorage.getItem('aura-theme')).toBe('dark');

      await user.click(screen.getByTestId('set-light'));
      expect(localStorage.getItem('aura-theme')).toBe('light');
    });
  });

  describe('useTheme', () => {
    test('throws error when used outside ThemeProvider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useTheme must be used within a ThemeProvider');

      consoleSpy.mockRestore();
    });
  });
});
