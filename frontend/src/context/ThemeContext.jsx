import { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext(undefined);

export function ThemeProvider({ children }) {
  // Light by default; dark only when the user has chosen it
  const [isDarkMode, setIsDarkMode] = useState(
    () => localStorage.getItem('aura-theme') === 'dark'
  );

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement;

    if (isDarkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Save only choices the user makes, so the default stays light until they pick dark
  const saveTheme = (dark) => {
    localStorage.setItem('aura-theme', dark ? 'dark' : 'light');
    setIsDarkMode(dark);
  };

  const toggleTheme = () => {
    saveTheme(!isDarkMode);
  };

  const setTheme = (theme) => {
    saveTheme(theme === 'dark');
  };

  const value = {
    isDarkMode,
    toggleTheme,
    setTheme,
    theme: isDarkMode ? 'dark' : 'light',
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

export default ThemeContext;
