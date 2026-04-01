/**
 * Project Aura - File Viewer Component
 *
 * Syntax-highlighted code display for Knowledge Graph file navigation.
 * Features include line numbers, search, tab support, and node highlighting.
 *
 * Design System: Apple-inspired with clean typography, generous spacing,
 * and smooth transitions per design-principles.md
 */

import { useState, useEffect, useRef, useCallback, useMemo, Fragment } from 'react';
import {
  XMarkIcon,
  MagnifyingGlassIcon,
  DocumentDuplicateIcon,
  ArrowTopRightOnSquareIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  FolderIcon,
} from '@heroicons/react/24/outline';
import { detectLanguage, getMockFileContent } from '../../services/fileApi';

// ============================================================================
// Syntax Highlighting (Lightweight implementation without Prism dependency)
// ============================================================================

const TOKEN_PATTERNS = {
  python: [
    { pattern: /(#.*$)/gm, className: 'token-comment' },
    { pattern: /("""[\s\S]*?"""|'''[\s\S]*?''')/g, className: 'token-docstring' },
    { pattern: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, className: 'token-string' },
    { pattern: /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|async|await|yield|raise|pass|break|continue|lambda|and|or|not|in|is|None|True|False)\b/g, className: 'token-keyword' },
    { pattern: /\b(self|cls)\b/g, className: 'token-builtin' },
    { pattern: /@[\w.]+/g, className: 'token-decorator' },
    { pattern: /\b([A-Z][a-zA-Z0-9_]*)\b/g, className: 'token-class' },
    { pattern: /\b(def\s+)(\w+)/g, className: 'token-function', groups: [1, 2] },
    { pattern: /\b(\d+\.?\d*)\b/g, className: 'token-number' },
  ],
  javascript: [
    { pattern: /(\/\/.*$)/gm, className: 'token-comment' },
    { pattern: /(\/\*[\s\S]*?\*\/)/g, className: 'token-comment' },
    { pattern: /(`(?:[^`\\]|\\.)*`)/g, className: 'token-template' },
    { pattern: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, className: 'token-string' },
    { pattern: /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|new|this|class|extends|import|export|from|default|async|await|yield|of|in|typeof|instanceof)\b/g, className: 'token-keyword' },
    { pattern: /\b(true|false|null|undefined|NaN|Infinity)\b/g, className: 'token-builtin' },
    { pattern: /\b(console|window|document|Array|Object|String|Number|Boolean|Function|Promise|Map|Set)\b/g, className: 'token-class' },
    { pattern: /\b(\d+\.?\d*)\b/g, className: 'token-number' },
  ],
  jsx: [
    { pattern: /(\/\/.*$)/gm, className: 'token-comment' },
    { pattern: /(\/\*[\s\S]*?\*\/)/g, className: 'token-comment' },
    { pattern: /(<\/?[A-Z][a-zA-Z0-9]*)/g, className: 'token-tag' },
    { pattern: /(<\/?[a-z][a-zA-Z0-9]*)/g, className: 'token-tag' },
    { pattern: /(\s[a-zA-Z-]+=)/g, className: 'token-attr' },
    { pattern: /(`(?:[^`\\]|\\.)*`)/g, className: 'token-template' },
    { pattern: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, className: 'token-string' },
    { pattern: /\b(const|let|var|function|return|if|else|for|while|import|export|from|default|async|await)\b/g, className: 'token-keyword' },
    { pattern: /\b(\d+\.?\d*)\b/g, className: 'token-number' },
  ],
  default: [
    { pattern: /(\/\/.*$|#.*$)/gm, className: 'token-comment' },
    { pattern: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, className: 'token-string' },
    { pattern: /\b(\d+\.?\d*)\b/g, className: 'token-number' },
  ],
};

/**
 * Apply syntax highlighting to a line of code
 */
function highlightLine(line, languageKey) {
  if (!line) return [{ text: line, className: '' }];

  const patterns = TOKEN_PATTERNS[languageKey] || TOKEN_PATTERNS.default;
  let tokens = [{ text: line, className: '' }];

  for (const { pattern, className } of patterns) {
    const newTokens = [];
    for (const token of tokens) {
      if (token.className) {
        newTokens.push(token);
        continue;
      }

      let lastIndex = 0;
      const text = token.text;
      const regex = new RegExp(pattern.source, pattern.flags);
      let match;

      while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
          newTokens.push({ text: text.slice(lastIndex, match.index), className: '' });
        }
        newTokens.push({ text: match[0], className });
        lastIndex = regex.lastIndex;

        // Prevent infinite loop on zero-width matches
        if (match[0].length === 0) {
          regex.lastIndex++;
        }
      }

      if (lastIndex < text.length) {
        newTokens.push({ text: text.slice(lastIndex), className: '' });
      }
    }
    tokens = newTokens.length > 0 ? newTokens : tokens;
  }

  return tokens;
}

// ============================================================================
// Breadcrumb Component
// ============================================================================

function FileBreadcrumb({ filePath, onNavigate }) {
  const parts = filePath.split('/').filter(Boolean);

  return (
    <nav className="flex items-center gap-1 text-sm overflow-x-auto">
      <FolderIcon className="w-4 h-4 text-surface-400 flex-shrink-0" />
      {parts.map((part, index) => {
        const isLast = index === parts.length - 1;
        const pathToHere = parts.slice(0, index + 1).join('/');

        return (
          <Fragment key={pathToHere}>
            <ChevronRightIcon className="w-3 h-3 text-surface-400 flex-shrink-0" />
            {isLast ? (
              <span className="font-medium text-surface-900 dark:text-surface-100 truncate">
                {part}
              </span>
            ) : (
              <button
                onClick={() => onNavigate?.(pathToHere)}
                className="text-surface-500 hover:text-aura-600 dark:text-surface-400 dark:hover:text-aura-400 truncate transition-colors"
              >
                {part}
              </button>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}

// ============================================================================
// Tab Bar Component
// ============================================================================

function FileTabBar({ tabs, activeTab, onTabSelect, onTabClose }) {
  if (tabs.length === 0) return null;

  return (
    <div className="flex items-center gap-0.5 px-2 bg-surface-50 dark:bg-surface-800 border-b border-surface-100/50 dark:border-surface-700/30 overflow-x-auto">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        const language = detectLanguage(tab.path);

        return (
          <div
            key={tab.id}
            className={`
              group flex items-center gap-2 px-3 py-2 text-sm
              border-b-2 transition-all duration-200 ease-[var(--ease-tahoe)] cursor-pointer
              ${isActive
                ? 'border-aura-500 bg-white dark:bg-surface-900 text-surface-900 dark:text-surface-100'
                : 'border-transparent text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-white/60 dark:hover:bg-surface-700'
              }
            `}
          >
            <button
              onClick={() => onTabSelect(tab.id)}
              className="flex items-center gap-2 truncate max-w-[160px]"
            >
              {language && (
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: language.color }}
                />
              )}
              <span className="truncate">{tab.path.split('/').pop()}</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onTabClose(tab.id);
              }}
              className="p-0.5 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 opacity-0 group-hover:opacity-100 transition-all duration-200 ease-[var(--ease-tahoe)]"
              aria-label={`Close ${tab.path}`}
            >
              <XMarkIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Search Bar Component
// ============================================================================

function FileSearchBar({ isOpen, onClose, onSearch, searchResults, currentMatch, onNavigateMatch }) {
  const inputRef = useRef(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handler = setTimeout(() => {
      onSearch(query);
    }, 150);
    return () => clearTimeout(handler);
  }, [query, onSearch]);

  if (!isOpen) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-surface-50 dark:bg-surface-800 border-b border-surface-100/50 dark:border-surface-700/30">
      <div className="relative flex-1 max-w-md">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search in file..."
          className="w-full pl-9 pr-4 py-1.5 text-sm rounded-xl border border-surface-200/50 dark:border-surface-600/50 bg-white dark:bg-surface-800 backdrop-blur-sm text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-aura-500 transition-all duration-200 ease-[var(--ease-tahoe)]"
        />
      </div>

      {searchResults.length > 0 && (
        <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
          <span>
            {currentMatch + 1} of {searchResults.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onNavigateMatch(-1)}
              className="p-1 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
              aria-label="Previous match"
            >
              <ChevronUpIcon className="w-4 h-4" />
            </button>
            <button
              onClick={() => onNavigateMatch(1)}
              className="p-1 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
              aria-label="Next match"
            >
              <ChevronDownIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <button
        onClick={onClose}
        className="p-1.5 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
        aria-label="Close search"
      >
        <XMarkIcon className="w-4 h-4 text-surface-500" />
      </button>
    </div>
  );
}

// ============================================================================
// Code Line Component
// ============================================================================

function CodeLine({
  lineNumber,
  content,
  languageKey,
  isHighlighted,
  isSearchMatch,
  highlightedSymbol,
  onLineClick,
}) {
  const tokens = useMemo(() => highlightLine(content, languageKey), [content, languageKey]);

  return (
    <div
      className={`
        flex group transition-colors
        ${isHighlighted ? 'bg-aura-100/50 dark:bg-aura-900/20' : ''}
        ${isSearchMatch ? 'bg-warning-100 dark:bg-warning-900/30' : ''}
        hover:bg-surface-100 dark:hover:bg-surface-800
      `}
    >
      {/* Line number */}
      <button
        onClick={() => onLineClick?.(lineNumber)}
        className="flex-shrink-0 w-12 pr-4 text-right text-xs text-surface-400 dark:text-surface-500 select-none hover:text-aura-500 transition-colors font-mono"
        aria-label={`Line ${lineNumber}`}
      >
        {lineNumber}
      </button>

      {/* Code content */}
      <pre className="flex-1 text-sm font-mono overflow-x-auto whitespace-pre">
        <code>
          {tokens.map((token, i) => {
            // Check if this token contains the highlighted symbol
            const containsSymbol = highlightedSymbol && token.text.includes(highlightedSymbol);

            return (
              <span
                key={i}
                className={`
                  ${token.className}
                  ${containsSymbol ? 'bg-aura-200 dark:bg-aura-800 ring-1 ring-aura-400 rounded px-0.5' : ''}
                `}
              >
                {token.text}
              </span>
            );
          })}
        </code>
      </pre>
    </div>
  );
}

// ============================================================================
// Main File Viewer Component
// ============================================================================

export default function FileViewer({
  initialFile = null,
  highlightedLines = [],
  highlightedSymbol = null,
  scrollToLine = null,
  onFileChange,
  onLineClick,
  onClose,
  className = '',
}) {
  // Tab management
  const [tabs, setTabs] = useState([]);
  const [activeTabId, setActiveTabId] = useState(null);

  // Current file state
  const [content, setContent] = useState('');
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Search state
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [_searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [currentSearchMatch, setCurrentSearchMatch] = useState(0);

  // Refs
  const codeContainerRef = useRef(null);

  // Get active tab
  const activeTab = tabs.find((t) => t.id === activeTabId);

  // Open a file in a new tab or switch to existing tab
  const openFile = useCallback(async (filePath, line = null) => {
    // Check if file is already open
    const existingTab = tabs.find((t) => t.path === filePath);
    if (existingTab) {
      setActiveTabId(existingTab.id);
      if (line) {
        // Scroll to line after a brief delay
        setTimeout(() => scrollToLineNumber(line), 100);
      }
      return;
    }

    // Create new tab
    const newTab = {
      id: `tab-${Date.now()}`,
      path: filePath,
      line,
    };

    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);

    // Load file content
    await loadFileContent(filePath,line);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabs]);

  // Load file content
  const loadFileContent = useCallback(async (filePath, scrollLine = null) => {
    setLoading(true);
    setError(null);

    try {
      // In production, this would call the API
      // const data = await getFileContent(repositoryId, filePath);

      // For now, use mock data
      await new Promise((resolve) => setTimeout(resolve, 300));
      const mockData = getMockFileContent(filePath);

      setContent(mockData.content);
      setMetadata(mockData.metadata);

      if (scrollLine) {
        setTimeout(() => scrollToLineNumber(scrollLine), 100);
      }

      onFileChange?.(filePath);
    } catch (err) {
      setError('Failed to load file content');
      console.error('Failed to load file:', err);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFileChange]);

  // Close a tab
  const closeTab = useCallback((tabId) => {
    setTabs((prev) => {
      const newTabs = prev.filter((t) => t.id !== tabId);

      // If closing active tab, switch to adjacent tab
      if (tabId === activeTabId && newTabs.length > 0) {
        const closedIndex = prev.findIndex((t) => t.id === tabId);
        const newActiveIndex = Math.min(closedIndex, newTabs.length - 1);
        setActiveTabId(newTabs[newActiveIndex].id);
        loadFileContent(newTabs[newActiveIndex].path);
      } else if (newTabs.length === 0) {
        setActiveTabId(null);
        setContent('');
        setMetadata(null);
      }

      return newTabs;
    });
  }, [activeTabId, loadFileContent]);

  // Scroll to line number
  const scrollToLineNumber = useCallback((lineNumber) => {
    if (!codeContainerRef.current) return;

    const lineHeight = 24; // Approximate line height
    const scrollTop = (lineNumber - 1) * lineHeight - 100; // Center in view

    codeContainerRef.current.scrollTo({
      top: Math.max(0, scrollTop),
      behavior: 'smooth',
    });
  }, []);

  // Handle search
  const handleSearch = useCallback((query) => {
    setSearchQuery(query);

    if (!query.trim()) {
      setSearchResults([]);
      setCurrentSearchMatch(0);
      return;
    }

    const lines = content.split('\n');
    const matches = [];

    lines.forEach((line, index) => {
      if (line.toLowerCase().includes(query.toLowerCase())) {
        matches.push(index + 1);
      }
    });

    setSearchResults(matches);
    setCurrentSearchMatch(0);

    if (matches.length > 0) {
      scrollToLineNumber(matches[0]);
    }
  }, [content, scrollToLineNumber]);

  // Navigate search matches
  const navigateSearchMatch = useCallback((direction) => {
    if (searchResults.length === 0) return;

    const newIndex = (currentSearchMatch + direction + searchResults.length) % searchResults.length;
    setCurrentSearchMatch(newIndex);
    scrollToLineNumber(searchResults[newIndex]);
  }, [searchResults, currentSearchMatch, scrollToLineNumber]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Cmd/Ctrl + F for search
      if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
        e.preventDefault();
        setIsSearchOpen(true);
      }

      // Escape to close search
      if (e.key === 'Escape' && isSearchOpen) {
        setIsSearchOpen(false);
      }

      // Enter/Shift+Enter to navigate matches
      if (isSearchOpen && e.key === 'Enter') {
        e.preventDefault();
        navigateSearchMatch(e.shiftKey ? -1 : 1);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, navigateSearchMatch]);

  // Load initial file
  useEffect(() => {
    if (initialFile) {
      openFile(initialFile.path, initialFile.line);
    }
  }, [initialFile, openFile]);

  // Scroll to highlighted line
  useEffect(() => {
    if (scrollToLine && !loading) {
      scrollToLineNumber(scrollToLine);
    }
  }, [scrollToLine, loading, scrollToLineNumber]);

  // Copy file path to clipboard
  const handleCopyPath = useCallback(() => {
    if (activeTab) {
      navigator.clipboard.writeText(activeTab.path);
    }
  }, [activeTab]);

  // Get language info for current file
  const languageInfo = activeTab ? detectLanguage(activeTab.path) : null;
  const lines = content.split('\n');

  return (
    <div className={`flex flex-col h-full bg-white dark:bg-surface-900 backdrop-blur-xl rounded-xl overflow-hidden border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-100/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800">
        <div className="flex-1 min-w-0">
          {activeTab ? (
            <FileBreadcrumb
              filePath={activeTab.path}
              onNavigate={(_path) => {
                // TODO: Implement breadcrumb navigation
              }}
            />
          ) : (
            <span className="text-sm text-surface-400">No file open</span>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          {/* Language badge */}
          {languageInfo && (
            <span
              className="px-2 py-0.5 text-xs font-medium rounded"
              style={{
                backgroundColor: `${languageInfo.color}20`,
                color: languageInfo.color,
              }}
            >
              {languageInfo.name}
            </span>
          )}

          {/* Search button */}
          <button
            onClick={() => setIsSearchOpen(!isSearchOpen)}
            className="p-1.5 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
            aria-label="Search in file"
          >
            <MagnifyingGlassIcon className="w-4 h-4 text-surface-500" />
          </button>

          {/* Copy path button */}
          <button
            onClick={handleCopyPath}
            className="p-1.5 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
            aria-label="Copy file path"
          >
            <DocumentDuplicateIcon className="w-4 h-4 text-surface-500" />
          </button>

          {/* Open externally button */}
          <button
            onClick={() => {
              // TODO: Implement IDE integration
            }}
            className="p-1.5 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
            aria-label="Open in IDE"
          >
            <ArrowTopRightOnSquareIcon className="w-4 h-4 text-surface-500" />
          </button>

          {/* Close button */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-white/60 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)]"
              aria-label="Close file viewer"
            >
              <XMarkIcon className="w-4 h-4 text-surface-500" />
            </button>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <FileTabBar
        tabs={tabs}
        activeTab={activeTabId}
        onTabSelect={(id) => {
          setActiveTabId(id);
          const tab = tabs.find((t) => t.id === id);
          if (tab) loadFileContent(tab.path);
        }}
        onTabClose={closeTab}
      />

      {/* Search bar */}
      <FileSearchBar
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSearch={handleSearch}
        searchResults={searchResults}
        currentMatch={currentSearchMatch}
        onNavigateMatch={navigateSearchMatch}
      />

      {/* Code content */}
      <div
        ref={codeContainerRef}
        className="flex-1 overflow-auto bg-white dark:bg-surface-900"
      >
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex items-center gap-3 text-surface-400">
              <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>Loading file...</span>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-critical-500 font-medium">{error}</p>
              <button
                onClick={() => activeTab && loadFileContent(activeTab.path)}
                className="mt-2 text-sm text-aura-600 hover:text-aura-700 dark:text-aura-400 dark:hover:text-aura-300"
              >
                Try again
              </button>
            </div>
          </div>
        ) : !activeTab ? (
          <div className="flex items-center justify-center h-full text-surface-400">
            <div className="text-center">
              <DocumentDuplicateIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Select a file from the Knowledge Graph to view its contents</p>
            </div>
          </div>
        ) : (
          <div className="py-4">
            {lines.map((line, index) => {
              const lineNumber = index + 1;
              const isHighlighted = highlightedLines.includes(lineNumber);
              const isSearchMatch = searchResults.includes(lineNumber);

              return (
                <CodeLine
                  key={lineNumber}
                  lineNumber={lineNumber}
                  content={line}
                  languageKey={languageInfo?.key || 'default'}
                  isHighlighted={isHighlighted}
                  isSearchMatch={isSearchMatch}
                  highlightedSymbol={highlightedSymbol}
                  onLineClick={onLineClick}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Footer with file info */}
      {metadata && (
        <div className="flex items-center justify-between px-4 py-2 text-xs text-surface-500 dark:text-surface-400 border-t border-surface-100/50 dark:border-surface-700/30 bg-surface-50 dark:bg-surface-800">
          <div className="flex items-center gap-4">
            <span>{metadata.lines} lines</span>
            <span>{(metadata.size / 1024).toFixed(1)} KB</span>
            <span>{metadata.encoding}</span>
          </div>
          <div>
            Line {currentSearchMatch > 0 ? searchResults[currentSearchMatch] : 1}, Column 1
          </div>
        </div>
      )}

      {/* Syntax highlighting styles */}
      <style>{`
        .token-comment { color: #6a737d; font-style: italic; }
        .token-docstring { color: #6a737d; }
        .token-string { color: #032f62; }
        .token-template { color: #22863a; }
        .token-keyword { color: #d73a49; font-weight: 500; }
        .token-builtin { color: #e36209; }
        .token-decorator { color: #6f42c1; }
        .token-class { color: #6f42c1; }
        .token-function { color: #6f42c1; }
        .token-number { color: #005cc5; }
        .token-tag { color: #22863a; }
        .token-attr { color: #6f42c1; }

        .dark .token-comment { color: #8b949e; }
        .dark .token-docstring { color: #8b949e; }
        .dark .token-string { color: #a5d6ff; }
        .dark .token-template { color: #7ee787; }
        .dark .token-keyword { color: #ff7b72; }
        .dark .token-builtin { color: #ffa657; }
        .dark .token-decorator { color: #d2a8ff; }
        .dark .token-class { color: #d2a8ff; }
        .dark .token-function { color: #d2a8ff; }
        .dark .token-number { color: #79c0ff; }
        .dark .token-tag { color: #7ee787; }
        .dark .token-attr { color: #d2a8ff; }
      `}</style>
    </div>
  );
}

// ============================================================================
// Exports
// ============================================================================

export { FileBreadcrumb, FileTabBar, FileSearchBar, CodeLine };
