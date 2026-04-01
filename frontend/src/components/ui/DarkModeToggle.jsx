import { useTheme } from '../../context/ThemeContext';
import { SunIcon, MoonIcon } from '@heroicons/react/24/outline';

export default function DarkModeToggle({ className = '' }) {
  const { isDarkMode, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`
        relative p-2 rounded-lg
        bg-surface-100 dark:bg-surface-700
        hover:bg-surface-200 dark:hover:bg-surface-600
        border border-surface-200 dark:border-surface-600
        transition-all duration-300 ease-smooth
        focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
        dark:focus:ring-offset-surface-900
        group
        ${className}
      `}
      aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      <div className="relative w-5 h-5">
        {/* Sun Icon - visible in dark mode */}
        <SunIcon
          className={`
            absolute inset-0 w-5 h-5
            text-warning-400
            transition-all duration-300 ease-smooth
            ${isDarkMode
              ? 'opacity-100 rotate-0 scale-100'
              : 'opacity-0 rotate-90 scale-50'
            }
          `}
        />
        {/* Moon Icon - visible in light mode */}
        <MoonIcon
          className={`
            absolute inset-0 w-5 h-5
            text-aura-600
            transition-all duration-300 ease-smooth
            ${isDarkMode
              ? 'opacity-0 -rotate-90 scale-50'
              : 'opacity-100 rotate-0 scale-100'
            }
          `}
        />
      </div>

      {/* Subtle glow effect on hover */}
      <div
        className={`
          absolute inset-0 rounded-lg
          transition-opacity duration-300
          ${isDarkMode
            ? 'bg-warning-500/10 opacity-0 group-hover:opacity-100'
            : 'bg-aura-500/10 opacity-0 group-hover:opacity-100'
          }
        `}
      />
    </button>
  );
}

// Expanded version with text label
export function DarkModeToggleExpanded({ className = '' }) {
  const { isDarkMode, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`
        flex items-center gap-3 px-3 py-2 rounded-lg w-full
        bg-surface-100 dark:bg-surface-700
        hover:bg-surface-200 dark:hover:bg-surface-600
        border border-surface-200 dark:border-surface-600
        transition-all duration-300 ease-smooth
        focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
        dark:focus:ring-offset-surface-900
        group
        ${className}
      `}
      aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      <div className="relative w-5 h-5 flex-shrink-0">
        <SunIcon
          className={`
            absolute inset-0 w-5 h-5
            text-warning-400
            transition-all duration-300 ease-smooth
            ${isDarkMode
              ? 'opacity-100 rotate-0 scale-100'
              : 'opacity-0 rotate-90 scale-50'
            }
          `}
        />
        <MoonIcon
          className={`
            absolute inset-0 w-5 h-5
            text-aura-600
            transition-all duration-300 ease-smooth
            ${isDarkMode
              ? 'opacity-0 -rotate-90 scale-50'
              : 'opacity-100 rotate-0 scale-100'
            }
          `}
        />
      </div>

      <span className="text-sm font-medium text-surface-700 dark:text-surface-200">
        {isDarkMode ? 'Light Mode' : 'Dark Mode'}
      </span>

      {/* Toggle Switch Visual */}
      <div className="ml-auto relative">
        <div
          className={`
            w-9 h-5 rounded-full
            transition-colors duration-300 ease-smooth
            ${isDarkMode ? 'bg-aura-500' : 'bg-surface-300'}
          `}
        >
          <div
            className={`
              absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm
              transition-transform duration-300 ease-smooth
              ${isDarkMode ? 'translate-x-4' : 'translate-x-0.5'}
            `}
          />
        </div>
      </div>
    </button>
  );
}
