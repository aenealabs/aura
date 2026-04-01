
/**
 * ChatTypingIndicator - Animated typing dots shown while assistant is responding
 *
 * Design Decisions:
 * - Three dots with staggered bounce animation
 * - Matches assistant message bubble styling
 * - Subtle animation that doesn't distract
 * - "Aura is thinking..." label for accessibility
 */
export default function ChatTypingIndicator() {
  return (
    <div className="flex items-start gap-3 px-4 py-3 animate-fade-in">
      {/* Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-aura-500 to-olive-500 flex items-center justify-center shadow-sm">
        <span className="text-white font-bold text-xs">A</span>
      </div>

      {/* Typing bubble */}
      <div className="flex flex-col gap-1 max-w-[85%]">
        <div
          className="
            inline-flex items-center gap-1.5 px-4 py-3
            bg-surface-100 dark:bg-surface-700
            rounded-2xl rounded-tl-md
          "
        >
          {/* Animated dots */}
          <span
            className="w-2 h-2 rounded-full bg-surface-400 dark:bg-surface-500 animate-bounce"
            style={{ animationDelay: '0ms', animationDuration: '600ms' }}
          />
          <span
            className="w-2 h-2 rounded-full bg-surface-400 dark:bg-surface-500 animate-bounce"
            style={{ animationDelay: '150ms', animationDuration: '600ms' }}
          />
          <span
            className="w-2 h-2 rounded-full bg-surface-400 dark:bg-surface-500 animate-bounce"
            style={{ animationDelay: '300ms', animationDuration: '600ms' }}
          />
        </div>

        {/* Label */}
        <span className="text-xs text-surface-400 dark:text-surface-500 ml-2">
          Aura is thinking...
        </span>
      </div>
    </div>
  );
}

/**
 * ChatTypingIndicatorInline - Compact inline version for tight spaces
 */
export function ChatTypingIndicatorInline() {
  return (
    <div className="inline-flex items-center gap-1 px-2 py-1">
      <span
        className="w-1.5 h-1.5 rounded-full bg-surface-400 dark:bg-surface-500 animate-bounce"
        style={{ animationDelay: '0ms', animationDuration: '600ms' }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full bg-surface-400 dark:bg-surface-500 animate-bounce"
        style={{ animationDelay: '150ms', animationDuration: '600ms' }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full bg-surface-400 dark:bg-surface-500 animate-bounce"
        style={{ animationDelay: '300ms', animationDuration: '600ms' }}
      />
    </div>
  );
}
