import { ChatSuggestedPromptGrid } from './ChatSuggestedPrompt';

/**
 * ChatEmptyState - Welcome screen shown when no conversation is active
 *
 * Design Decisions:
 * - Aura branding with gradient logo
 * - Clear value proposition
 * - Suggested prompts to reduce friction
 * - Context-aware based on current page
 */
export default function ChatEmptyState({ context = null, onSelectPrompt }) {
  return (
    <div className="flex flex-col items-center justify-start h-full px-6 pt-4 pb-8 animate-fade-in">
      {/* Welcome text */}
      <p className="text-sm text-surface-500 dark:text-surface-400 text-center max-w-sm mb-8">
        Your AI-powered helper for security metrics, reports, and platform guidance.
        Ask me anything about Project Aura.
      </p>

      {/* Capabilities */}
      <div className="w-full max-w-md mb-8">
        <div className="grid grid-cols-2 gap-3 text-center">
          <CapabilityItem
            title="Query Metrics"
            description="Vulnerabilities, agents, patches"
          />
          <CapabilityItem
            title="Generate Reports"
            description="Security summaries, compliance"
          />
          <CapabilityItem
            title="Configuration Help"
            description="Settings and workflows"
          />
          <CapabilityItem
            title="Search Docs"
            description="Find answers quickly"
          />
        </div>
      </div>

      {/* Suggested prompts */}
      <div className="w-full max-w-md">
        <h3 className="text-sm font-medium text-surface-600 dark:text-surface-400 mb-3">
          Try asking:
        </h3>
        <ChatSuggestedPromptGrid
          context={context}
          onSelectPrompt={onSelectPrompt}
          maxItems={4}
          columns={2}
        />
      </div>

      {/* Keyboard shortcut hint */}
      <p className="mt-8 text-xs text-surface-400 dark:text-surface-500">
        Press{' '}
        <kbd className="px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-700 text-surface-600 dark:text-surface-300 font-mono">
          Ctrl
        </kbd>
        <span className="text-surface-400 dark:text-surface-500">/</span>
        <kbd className="px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-700 text-surface-600 dark:text-surface-300 font-mono">
          Cmd
        </kbd>
        {' + '}
        <kbd className="px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-700 text-surface-600 dark:text-surface-300 font-mono">
          /
        </kbd>
        {' '}to quickly open chat
      </p>
    </div>
  );
}

/**
 * CapabilityItem - Small capability indicator
 */
function CapabilityItem({ title, description }) {
  return (
    <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/50">
      <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
        {title}
      </p>
      <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
        {description}
      </p>
    </div>
  );
}

/**
 * ChatEmptyConversation - Shown when a conversation is selected but has no messages
 */
export function ChatEmptyConversation({ _onSelectPrompt }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-8 animate-fade-in">
      <div className="w-12 h-12 rounded-xl bg-surface-100 dark:bg-surface-700 flex items-center justify-center mb-4">
        <svg
          className="w-6 h-6 text-surface-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </div>
      <p className="text-sm text-surface-500 dark:text-surface-400 text-center max-w-xs">
        Start a new conversation by typing a message below.
      </p>
    </div>
  );
}
