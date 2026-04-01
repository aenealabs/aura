import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import DarkModeToggle from './DarkModeToggle';

// Mock ThemeContext
vi.mock('../../context/ThemeContext', () => ({
  useTheme: vi.fn(),
}));

import { useTheme } from '../../context/ThemeContext';

describe('DarkModeToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders toggle button', () => {
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: vi.fn(),
    });

    render(<DarkModeToggle />);

    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  test('shows sun icon when in dark mode', () => {
    useTheme.mockReturnValue({
      isDarkMode: true,
      toggleTheme: vi.fn(),
    });

    render(<DarkModeToggle />);

    // Sun icon has aria-label for light mode
    expect(screen.getByRole('button', { name: /switch to light mode/i })).toBeInTheDocument();
  });

  test('shows moon icon when in light mode', () => {
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: vi.fn(),
    });

    render(<DarkModeToggle />);

    expect(screen.getByRole('button', { name: /switch to dark mode/i })).toBeInTheDocument();
  });

  test('calls toggleTheme when clicked', async () => {
    const user = userEvent.setup();
    const toggleTheme = vi.fn();

    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme,
    });

    render(<DarkModeToggle />);

    await user.click(screen.getByRole('button'));

    expect(toggleTheme).toHaveBeenCalledTimes(1);
  });

  test('applies custom className', () => {
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: vi.fn(),
    });

    render(<DarkModeToggle className="custom-class" />);

    expect(screen.getByRole('button')).toHaveClass('custom-class');
  });

  test('has accessible tooltip', () => {
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: vi.fn(),
    });

    render(<DarkModeToggle />);

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('title');
  });

  test('renders icon', () => {
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: vi.fn(),
    });

    const { container } = render(<DarkModeToggle />);
    // Component should render an icon
    expect(container.querySelector('svg')).toBeInTheDocument();
  });
});
