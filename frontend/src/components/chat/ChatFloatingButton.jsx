import { ChatBubbleLeftRightIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { useChat } from '../../context/ChatContext';

/**
 * ChatFloatingButton - Floating action button to open/close the chat assistant
 *
 * Design Decisions:
 * - Bottom-right corner placement (industry standard for chat widgets)
 * - Olive green accent color for brand consistency
 * - Smooth scale and rotation animations
 * - Pulse animation when there are unread messages
 * - Accessible with keyboard focus and ARIA labels
 */
export default function ChatFloatingButton({ hasUnread = false }) {
  const { isOpen, isMinimized, openChat, closeChat } = useChat();

  // Determine visual state: chat is "visually open" only when open AND not minimized
  const isVisuallyOpen = isOpen && !isMinimized;

  const handleClick = () => {
    if (isVisuallyOpen) {
      closeChat();
    } else {
      openChat();
    }
  };

  return (
    <button
      onClick={handleClick}
      className={`
        fixed bottom-6 right-6 z-50
        w-14 h-14 rounded-full
        flex items-center justify-center
        shadow-lg hover:shadow-xl
        transition-all duration-300 ease-smooth
        focus:outline-none focus:ring-2 focus:ring-olive-500 focus:ring-offset-2
        dark:focus:ring-offset-surface-900
        ${isVisuallyOpen
          ? 'bg-surface-700 dark:bg-surface-600 hover:bg-surface-800 dark:hover:bg-surface-500 rotate-0'
          : 'bg-olive-500 hover:bg-olive-600 dark:bg-olive-600 dark:hover:bg-olive-500'
        }
        ${!isVisuallyOpen && 'hover:scale-110 active:scale-95'}
        group
      `}
      aria-label={isVisuallyOpen ? 'Close chat assistant' : 'Open chat assistant'}
      aria-expanded={isVisuallyOpen}
    >
      {/* Icon transition */}
      <div className="relative w-6 h-6">
        {/* Chat icon - show when closed or minimized */}
        <ChatBubbleLeftRightIcon
          className={`
            absolute inset-0 w-6 h-6 text-white
            transition-all duration-300 ease-smooth
            ${isVisuallyOpen ? 'opacity-0 rotate-90 scale-50' : 'opacity-100 rotate-0 scale-100'}
          `}
        />
        {/* Close icon - show when open and visible */}
        <XMarkIcon
          className={`
            absolute inset-0 w-6 h-6 text-white
            transition-all duration-300 ease-smooth
            ${isVisuallyOpen ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'}
          `}
        />
      </div>

      {/* Unread indicator */}
      {hasUnread && !isOpen && (
        <span className="absolute -top-1 -right-1 flex h-4 w-4">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-critical-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-4 w-4 bg-critical-500" />
        </span>
      )}


      {/* Tooltip */}
      <span
        className={`
          absolute right-full mr-3 top-1/2 -translate-y-1/2
          px-3 py-1.5 rounded-lg
          bg-surface-900 dark:bg-surface-100
          text-white dark:text-surface-900
          text-sm font-medium whitespace-nowrap
          opacity-0 invisible translate-x-2
          group-hover:opacity-100 group-hover:visible group-hover:translate-x-0
          transition-all duration-200
          pointer-events-none
        `}
      >
        {isVisuallyOpen ? 'Close Aura Assistant' : 'Open Aura Assistant'}
        {/* Tooltip arrow */}
        <span
          className={`
            absolute right-0 top-1/2 -translate-y-1/2 translate-x-1
            w-2 h-2 rotate-45
            bg-surface-900 dark:bg-surface-100
          `}
        />
      </span>
    </button>
  );
}
