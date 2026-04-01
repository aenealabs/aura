/**
 * Command Palette Component (Cmd+K / Ctrl+K)
 *
 * A macOS Spotlight-inspired command palette for quick navigation
 * and actions across Project Aura. Features fuzzy search, keyboard
 * navigation, and categorized results.
 *
 * Design: Apple-inspired with backdrop blur, subtle shadows, and
 * smooth transitions following Project Aura's design system.
 */

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  createContext,
  useContext,
} from 'react';

// =============================================================================
// Custom Debounce Hook
// =============================================================================

/**
 * Debounces a value by delaying updates until after the specified delay.
 * Useful for search inputs to reduce unnecessary re-renders and API calls.
 *
 * @param {any} value - The value to debounce
 * @param {number} delay - Delay in milliseconds (default: 150ms)
 * @returns {any} The debounced value
 */
function useDebounce(value, delay = 150) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import {
  HomeIcon,
  CodeBracketIcon,
  BeakerIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  BugAntIcon,
  BellIcon,
  ShareIcon,
  CpuChipIcon,
  EyeIcon,
  PuzzlePieceIcon,
  Cog6ToothIcon,
  PlayIcon,
  HeartIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  ChartBarIcon,
  DocumentTextIcon,
  CommandLineIcon,
  FolderIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

// =============================================================================
// Command Palette Context
// =============================================================================

const CommandPaletteContext = createContext(null);

export function useCommandPalette() {
  const context = useContext(CommandPaletteContext);
  if (!context) {
    throw new Error('useCommandPalette must be used within a CommandPaletteProvider');
  }
  return context;
}

// =============================================================================
// Fuzzy Search Implementation
// =============================================================================

/**
 * Simple fuzzy search that matches characters in sequence
 * Returns a score (higher is better) or -1 if no match
 */
function fuzzyMatch(pattern, str) {
  if (!pattern) return { score: 1, matches: [] };

  const patternLower = pattern.toLowerCase();
  const strLower = str.toLowerCase();
  const matches = [];

  let patternIdx = 0;
  let score = 0;
  let consecutiveBonus = 0;

  for (let i = 0; i < strLower.length && patternIdx < patternLower.length; i++) {
    if (strLower[i] === patternLower[patternIdx]) {
      matches.push(i);
      // Bonus for consecutive matches
      score += 1 + consecutiveBonus;
      consecutiveBonus += 0.5;
      // Bonus for matching at word boundaries
      if (i === 0 || str[i - 1] === ' ' || str[i - 1] === '/' || str[i - 1] === '-') {
        score += 2;
      }
      patternIdx++;
    } else {
      consecutiveBonus = 0;
    }
  }

  // Return -1 if pattern not fully matched
  if (patternIdx < patternLower.length) {
    return { score: -1, matches: [] };
  }

  // Bonus for shorter strings (more relevant)
  score += (100 - str.length) * 0.1;

  return { score, matches };
}

/**
 * Highlight matched characters in a string
 */
function HighlightedText({ text, matches }) {
  if (!matches || matches.length === 0) {
    return <span>{text}</span>;
  }

  const parts = [];
  let lastIndex = 0;

  matches.forEach((matchIndex, i) => {
    if (matchIndex > lastIndex) {
      parts.push(
        <span key={`text-${i}`}>{text.slice(lastIndex, matchIndex)}</span>
      );
    }
    parts.push(
      <span key={`match-${i}`} className="text-aura-600 dark:text-aura-400 font-semibold">
        {text[matchIndex]}
      </span>
    );
    lastIndex = matchIndex + 1;
  });

  if (lastIndex < text.length) {
    parts.push(<span key="text-end">{text.slice(lastIndex)}</span>);
  }

  return <>{parts}</>;
}

// =============================================================================
// Command Data
// =============================================================================

const PAGES = [
  { id: 'dashboard', name: 'Dashboard', path: '/', icon: HomeIcon, shortcut: 'G D', category: 'pages' },
  { id: 'repositories', name: 'Repositories', path: '/repositories', icon: CodeBracketIcon, shortcut: 'G R', category: 'pages' },
  { id: 'environments', name: 'Environments', path: '/environments', icon: BeakerIcon, shortcut: 'G E', category: 'pages' },
  { id: 'approvals', name: 'Approvals', path: '/approvals', icon: ShieldCheckIcon, shortcut: 'G A', category: 'pages' },
  { id: 'incidents', name: 'Incidents', path: '/incidents', icon: ExclamationTriangleIcon, shortcut: 'G I', category: 'pages' },
  { id: 'red-team', name: 'Red Team', path: '/security/red-team', icon: BugAntIcon, category: 'pages' },
  { id: 'alerts', name: 'Security Alerts', path: '/security/alerts', icon: BellIcon, category: 'pages' },
  { id: 'graph', name: 'Knowledge Graph', path: '/graph', icon: ShareIcon, shortcut: 'G K', category: 'pages' },
  { id: 'agents', name: 'Agent Registry', path: '/agents/registry', icon: CpuChipIcon, category: 'pages' },
  { id: 'mission-control', name: 'Mission Control', path: '/agents/mission-control', icon: EyeIcon, category: 'pages' },
  { id: 'traces', name: 'Trace Explorer', path: '/observability/traces', icon: ChartBarIcon, category: 'pages' },
  { id: 'integrations', name: 'Integrations', path: '/integrations', icon: PuzzlePieceIcon, category: 'pages' },
  { id: 'settings', name: 'Settings', path: '/settings', icon: Cog6ToothIcon, shortcut: 'G S', category: 'pages' },
];

const AGENTS = [
  { id: 'orchestrator', name: 'Orchestrator Prime', type: 'orchestrator', icon: CpuChipIcon, category: 'agents', status: 'active' },
  { id: 'coder', name: 'Coder Agent Alpha', type: 'coder', icon: CommandLineIcon, category: 'agents', status: 'busy' },
  { id: 'reviewer', name: 'Security Reviewer', type: 'reviewer', icon: EyeIcon, category: 'agents', status: 'active' },
  { id: 'validator', name: 'Sandbox Validator', type: 'validator', icon: ShieldCheckIcon, category: 'agents', status: 'idle' },
  { id: 'scanner', name: 'Vulnerability Scanner', type: 'scanner', icon: MagnifyingGlassIcon, category: 'agents', status: 'active' },
];

const QUICK_ACTIONS = [
  { id: 'start-scan', name: 'Start Security Scan', action: 'scan', icon: PlayIcon, shortcut: null, category: 'actions' },
  { id: 'health-check', name: 'Run Health Check', action: 'health', icon: HeartIcon, category: 'actions' },
  { id: 'refresh', name: 'Refresh Dashboard', action: 'refresh', icon: ArrowPathIcon, shortcut: 'R', category: 'actions' },
  { id: 'new-project', name: 'Create New Project', action: 'new-project', icon: FolderIcon, shortcut: 'N', category: 'actions' },
  { id: 'view-docs', name: 'View Documentation', action: 'docs', icon: DocumentTextIcon, shortcut: '?', category: 'actions' },
];

const CATEGORY_LABELS = {
  pages: 'Pages',
  agents: 'Agents',
  actions: 'Quick Actions',
  repositories: 'Repositories',
};

const CATEGORY_ORDER = ['pages', 'actions', 'agents', 'repositories'];

// =============================================================================
// Command Palette Provider
// =============================================================================

export function CommandPaletteProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  // Global keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Cmd+K (Mac) or Ctrl+K (Windows/Linux)
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggle();
      }
      // Escape to close
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        close();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, toggle, close]);

  return (
    <CommandPaletteContext.Provider value={{ isOpen, open, close, toggle }}>
      {children}
      <CommandPaletteModal isOpen={isOpen} onClose={close} />
    </CommandPaletteContext.Provider>
  );
}

// =============================================================================
// Command Palette Modal
// =============================================================================

function CommandPaletteModal({ isOpen, onClose }) {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 150); // Debounce search for performance
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [repositories, setRepositories] = useState([]);

  // Mock repositories - in production, fetch from RepositoryContext
  useEffect(() => {
    // Simulated repositories data
    setRepositories([
      { id: 'repo-1', name: 'core-api', provider: 'github', category: 'repositories' },
      { id: 'repo-2', name: 'frontend-app', provider: 'github', category: 'repositories' },
      { id: 'repo-3', name: 'auth-service', provider: 'gitlab', category: 'repositories' },
      { id: 'repo-4', name: 'data-pipeline', provider: 'github', category: 'repositories' },
    ]);
  }, []);

  // All searchable items
  const allItems = useMemo(() => {
    const repoItems = repositories.map((repo) => ({
      ...repo,
      icon: CodeBracketIcon,
      path: `/repositories?search=${repo.name}`,
    }));
    return [...PAGES, ...QUICK_ACTIONS, ...AGENTS, ...repoItems];
  }, [repositories]);

  // Filter and sort items based on debounced query (prevents excessive re-renders)
  const filteredItems = useMemo(() => {
    if (!debouncedQuery.trim()) {
      // Show default items when no query
      return allItems.slice(0, 10);
    }

    const results = allItems
      .map((item) => {
        const nameMatch = fuzzyMatch(debouncedQuery, item.name);
        const categoryMatch = fuzzyMatch(debouncedQuery, CATEGORY_LABELS[item.category] || '');
        const typeMatch = item.type ? fuzzyMatch(debouncedQuery, item.type) : { score: -1, matches: [] };

        // Use best match score
        const bestScore = Math.max(nameMatch.score, categoryMatch.score * 0.5, typeMatch.score * 0.3);

        return {
          ...item,
          score: bestScore,
          matches: nameMatch.score > 0 ? nameMatch.matches : [],
        };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score);

    return results.slice(0, 15);
  }, [debouncedQuery, allItems]);

  // Group items by category
  const groupedItems = useMemo(() => {
    const groups = {};
    filteredItems.forEach((item) => {
      if (!groups[item.category]) {
        groups[item.category] = [];
      }
      groups[item.category].push(item);
    });

    // Sort groups by predefined order
    const sortedGroups = [];
    CATEGORY_ORDER.forEach((category) => {
      if (groups[category]) {
        sortedGroups.push({
          category,
          label: CATEGORY_LABELS[category],
          items: groups[category],
        });
      }
    });

    return sortedGroups;
  }, [filteredItems]);

  // Flatten grouped items for keyboard navigation
  const flatItems = useMemo(() => {
    return groupedItems.flatMap((group) => group.items);
  }, [groupedItems]);

  // Reset selection when filtered results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [debouncedQuery]);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current && flatItems[selectedIndex]) {
      const selectedElement = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex, flatItems]);

  // Handle keyboard navigation
  const handleKeyDown = (e) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, flatItems.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (flatItems[selectedIndex]) {
          handleSelect(flatItems[selectedIndex]);
        }
        break;
      case 'Tab':
        e.preventDefault();
        if (e.shiftKey) {
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
        } else {
          setSelectedIndex((prev) => Math.min(prev + 1, flatItems.length - 1));
        }
        break;
      default:
        break;
    }
  };

  // Handle item selection
  const handleSelect = (item) => {
    if (item.path) {
      navigate(item.path);
      onClose();
    } else if (item.action) {
      handleAction(item.action);
      onClose();
    } else if (item.category === 'agents') {
      navigate(`/agents/mission-control/${item.id}`);
      onClose();
    }
  };

  // Handle quick actions
  const handleAction = (action) => {
    switch (action) {
      case 'scan':
        // TODO: Implement security scan trigger
        break;
      case 'health':
        // TODO: Implement health check trigger
        break;
      case 'refresh':
        window.location.reload();
        break;
      case 'new-project':
        navigate('/repositories');
        break;
      case 'docs':
        window.open('https://docs.aenealabs.com', '_blank');
        break;
      default:
        // Unknown action - no-op
        break;
    }
  };

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // Track flat index for keyboard navigation
  let flatIndex = -1;

  return createPortal(
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="command-palette-title"
    >
      {/* Backdrop - Glass style */}
      <div
        className="fixed inset-0 glass-backdrop transition-opacity duration-[var(--duration-overlay)]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog - Glass style */}
      <div className="flex min-h-full items-start justify-center p-4 pt-[15vh]">
        <div
          className="
            relative w-full max-w-xl
            bg-white dark:bg-surface-800
            backdrop-blur-xl backdrop-saturate-150
            rounded-2xl
            border border-white/50 dark:border-surface-700/50
            shadow-[var(--shadow-glass-hover)]
            overflow-hidden
            transform transition-all duration-[var(--duration-overlay)] ease-[var(--ease-tahoe)]
            animate-in fade-in slide-in-from-top-4
          "
          onClick={(e) => e.stopPropagation()}
        >
          {/* Search Input */}
          <div className="relative border-b border-surface-100/50 dark:border-surface-700/30">
            <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400 dark:text-surface-500 pointer-events-none" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search pages, agents, actions..."
              className="
                w-full pl-12 pr-12 py-4
                text-base text-surface-900 dark:text-surface-100
                placeholder-surface-400 dark:placeholder-surface-500
                bg-transparent
                border-0 focus:outline-none focus:ring-0
              "
              id="command-palette-title"
              autoComplete="off"
              spellCheck="false"
            />
            <button
              onClick={onClose}
              className="
                absolute right-3 top-1/2 -translate-y-1/2
                p-1.5 rounded-lg
                text-surface-400 hover:text-surface-600
                dark:text-surface-500 dark:hover:text-surface-300
                hover:bg-surface-50 dark:hover:bg-surface-700
                transition-all duration-150
              "
              aria-label="Close command palette"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Results */}
          <div
            ref={listRef}
            className="max-h-[400px] overflow-y-auto overscroll-contain py-2"
            role="listbox"
          >
            {groupedItems.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <MagnifyingGlassIcon className="w-12 h-12 mx-auto text-surface-300 dark:text-surface-600 mb-3" />
                <p className="text-surface-500 dark:text-surface-400 text-sm">
                  No results found for "{query}"
                </p>
                <p className="text-surface-400 dark:text-surface-500 text-xs mt-1">
                  Try searching for pages, agents, or actions
                </p>
              </div>
            ) : (
              groupedItems.map((group) => (
                <div key={group.category} className="mb-2">
                  {/* Category Header */}
                  <div className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">
                    {group.label}
                  </div>

                  {/* Items */}
                  <div>
                    {group.items.map((item) => {
                      flatIndex++;
                      const isSelected = flatIndex === selectedIndex;
                      const Icon = item.icon;

                      return (
                        <button
                          key={item.id}
                          data-index={flatIndex}
                          onClick={() => handleSelect(item)}
                          onMouseEnter={() => setSelectedIndex(flatIndex)}
                          className={`
                            w-full flex items-center gap-3 mx-2 px-3 py-2.5 rounded-xl
                            text-left transition-all duration-150 ease-[var(--ease-tahoe)]
                            ${isSelected
                              ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-sm'
                              : 'text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700'
                            }
                          `}
                          style={{ width: 'calc(100% - 1rem)' }}
                          role="option"
                          aria-selected={isSelected}
                        >
                          {/* Icon */}
                          <div
                            className={`
                              flex-shrink-0 p-2 rounded-lg
                              ${isSelected
                                ? 'bg-aura-100 dark:bg-aura-800/50 text-aura-600 dark:text-aura-400'
                                : 'bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400'
                              }
                            `}
                          >
                            <Icon className="w-4 h-4" />
                          </div>

                          {/* Text */}
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate">
                              <HighlightedText text={item.name} matches={item.matches} />
                            </div>
                            {item.type && (
                              <div className="text-xs text-surface-500 dark:text-surface-400 capitalize">
                                {item.type} Agent
                                {item.status && (
                                  <span
                                    className={`
                                      ml-2 px-1.5 py-0.5 rounded text-xs
                                      ${item.status === 'active'
                                        ? 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400'
                                        : item.status === 'busy'
                                          ? 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400'
                                          : 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400'
                                      }
                                    `}
                                  >
                                    {item.status}
                                  </span>
                                )}
                              </div>
                            )}
                            {item.provider && (
                              <div className="text-xs text-surface-500 dark:text-surface-400 capitalize">
                                {item.provider}
                              </div>
                            )}
                          </div>

                          {/* Shortcut */}
                          {item.shortcut && (
                            <div className="flex-shrink-0 flex gap-1">
                              {item.shortcut.split(' ').map((key, i) => (
                                <kbd
                                  key={i}
                                  className="
                                    min-w-[22px] h-6 px-1.5
                                    flex items-center justify-center
                                    rounded-md text-xs font-medium
                                    bg-surface-100 dark:bg-surface-700
                                    text-surface-500 dark:text-surface-400
                                    border border-surface-200 dark:border-surface-600
                                  "
                                >
                                  {key}
                                </kbd>
                              ))}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer - Glass style */}
          <div className="px-4 py-3 border-t border-surface-100 dark:border-surface-700 bg-surface-50 dark:bg-surface-800">
            <div className="flex items-center justify-between text-xs text-surface-500 dark:text-surface-400">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <kbd className="px-1.5 py-0.5 rounded-md bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 font-mono border border-surface-200 dark:border-surface-600">
                    Enter
                  </kbd>
                  to select
                </span>
                <span className="flex items-center gap-1.5">
                  <kbd className="px-1.5 py-0.5 rounded-md bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 font-mono border border-surface-200 dark:border-surface-600">
                    ↑↓
                  </kbd>
                  to navigate
                </span>
              </div>
              <span className="flex items-center gap-1.5">
                <kbd className="px-1.5 py-0.5 rounded-md bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 font-mono border border-surface-200 dark:border-surface-600">
                  Esc
                </kbd>
                to close
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

// =============================================================================
// Standalone Trigger Button Component
// =============================================================================

export function CommandPaletteTrigger({ className = '', variant = 'default' }) {
  const { open } = useCommandPalette();

  const isMac = typeof navigator !== 'undefined' && navigator.platform.toLowerCase().includes('mac');
  const shortcutKey = isMac ? 'Cmd' : 'Ctrl';

  if (variant === 'minimal') {
    return (
      <button
        onClick={open}
        className={`
          flex items-center gap-2 px-3 py-2 rounded-lg
          text-surface-400 dark:text-surface-500
          hover:text-surface-600 dark:hover:text-surface-300
          hover:bg-surface-100 dark:hover:bg-surface-700
          transition-colors duration-150
          ${className}
        `}
        aria-label="Open command palette"
      >
        <MagnifyingGlassIcon className="w-5 h-5" />
        <kbd className="text-xs px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-700">
          {shortcutKey}+K
        </kbd>
      </button>
    );
  }

  return (
    <button
      onClick={open}
      className={`
        w-full flex items-center gap-2 px-3 py-2.5 rounded-xl
        glass-card-subtle
        text-surface-500 dark:text-surface-400
        hover:bg-surface-50 dark:hover:bg-surface-700
        hover:shadow-sm
        transition-all duration-200 ease-[var(--ease-tahoe)]
        text-sm
        ${className}
      `}
    >
      <MagnifyingGlassIcon className="w-4 h-4" />
      <span>Go to...</span>
      <kbd className="ml-auto text-xs px-1.5 py-0.5 rounded-md bg-surface-100 dark:bg-surface-700 text-surface-500 dark:text-surface-400 border border-surface-200 dark:border-surface-600">
        {shortcutKey}+K
      </kbd>
    </button>
  );
}

// =============================================================================
// Dashboard Search Trigger Component
// =============================================================================

export function DashboardSearchTrigger({ className = '' }) {
  const { open } = useCommandPalette();

  const isMac = typeof navigator !== 'undefined' && navigator.platform.toLowerCase().includes('mac');
  const shortcutLabel = isMac ? 'cmd/ctrl + K' : 'ctrl + K';

  return (
    <button
      onClick={open}
      className={`
        w-full max-w-sm
        flex items-center gap-3 px-4 py-3
        rounded-xl
        bg-white dark:bg-surface-700 border border-surface-300 dark:border-surface-600
        text-surface-500
        hover:bg-surface-50 dark:hover:bg-surface-600
        hover:-translate-y-px
        focus:outline-none focus:ring-2 focus:ring-aura-500/50 dark:focus:ring-aura-400/50 focus:ring-offset-2 dark:focus:ring-offset-surface-900
        transition-all duration-200 ease-[var(--ease-tahoe)]
        ${className}
      `}
    >
      <MagnifyingGlassIcon className="w-5 h-5 text-surface-400" />
      <span className="flex-1 text-left text-sm">
        Go to...
      </span>
      <kbd className="
        hidden sm:inline-flex items-center gap-1
        px-2 py-1 rounded-lg
        bg-surface-100 dark:bg-surface-700
        text-xs font-medium text-surface-500 dark:text-surface-400
        border border-surface-200 dark:border-surface-600
      ">
        <span className="text-xs">{shortcutLabel}</span>
      </kbd>
    </button>
  );
}

export default CommandPaletteProvider;
