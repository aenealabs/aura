import { useRef, useEffect, useState } from 'react';
import {
  XMarkIcon,
  ChevronDownIcon,
  Bars3Icon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
} from '@heroicons/react/24/outline';
import { useChat } from '../../context/ChatContext';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import ChatEmptyState, { ChatEmptyConversation } from './ChatEmptyState';
import ChatTypingIndicator from './ChatTypingIndicator';
import ChatConversationList from './ChatConversationList';
import ChatFloatingButton from './ChatFloatingButton';

/**
 * ChatAssistant - Main container component for Aura Assistant
 *
 * Design Decision: Floating Panel + Modal Approach
 *
 * After analyzing the placement options, I recommend a hybrid approach:
 * - Floating button (bottom-right) to trigger the chat
 * - Slide-in panel from the right (not a modal) for the chat interface
 * - Panel overlays content without blocking navigation
 * - Collapsible conversation list sidebar within the panel
 *
 * Why this approach:
 * 1. Non-disruptive: Users can still see and interact with the main app
 * 2. Persistent: Chat stays open while navigating between pages
 * 3. Familiar: Matches patterns from Intercom, Drift, ChatGPT
 * 4. Mobile-friendly: Adapts to full-screen on small devices
 * 5. Context-aware: Can read current page context
 */

export default function ChatAssistant() {
  const {
    isOpen,
    isMinimized,
    closeChat,
    minimizeChat,
    activeConversation,
    isTyping,
    sendMessage,
    showConversationList,
    setShowConversationList,
    currentContext,
  } = useChat();

  const messagesEndRef = useRef(null);
  const [isExpanded, setIsExpanded] = useState(false);

  // WCAG 2.1 AA: Focus trap for chat panel when open
  const { containerRef } = useFocusTrap(isOpen && !isMinimized, {
    autoFocus: true,
    restoreFocus: true,
    escapeDeactivates: true,
    onEscape: closeChat,
  });

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeConversation?.messages, isTyping]);

  // Handle keyboard shortcut (Cmd/Ctrl + /)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        const { toggleChat } = useChat.getState?.() || {};
        toggleChat?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelectPrompt = (prompt) => {
    sendMessage(prompt);
  };

  const messages = activeConversation?.messages || [];
  const hasMessages = messages.length > 0;

  return (
    <>
      {/* Floating button - always visible */}
      <ChatFloatingButton />

      {/* Chat panel */}
      <div
        ref={containerRef}
        className={`
          fixed z-40
          transition-all duration-300 ease-smooth
          ${isOpen && !isMinimized ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}
          ${isExpanded
            ? 'inset-4 lg:inset-8'
            : 'bottom-24 right-6 w-[420px] h-[780px] max-h-[calc(100vh-120px)]'
          }
          max-w-full
        `}
        role="dialog"
        aria-modal="true"
        aria-label="Aura Assistant"
        aria-hidden={!isOpen || isMinimized}
        inert={isMinimized ? '' : undefined}
      >
        <div
          className={`
            h-full w-full
            bg-white dark:bg-surface-800
            rounded-2xl
            shadow-modal
            border border-surface-200 dark:border-surface-700
            flex flex-col
            overflow-hidden
            animate-scale-in
          `}
        >
          {/* Header */}
          <ChatHeader
            isExpanded={isExpanded}
            showConversationList={showConversationList}
            onToggleExpand={() => setIsExpanded(!isExpanded)}
            onToggleConversationList={() => setShowConversationList(!showConversationList)}
            onMinimize={minimizeChat}
            onClose={closeChat}
          />

          {/* Main content area */}
          <div className="flex-1 flex overflow-hidden relative">
            {/* Conversation list sidebar - only shown inline when expanded */}
            {showConversationList && isExpanded && (
              <div
                className="
                  flex-shrink-0 border-r border-surface-200 dark:border-surface-700
                  transition-all duration-300
                  w-72
                "
              >
                <ChatConversationList />
              </div>
            )}

            {/* Conversation list overlay - shown in compact mode or on mobile */}
            {showConversationList && !isExpanded && (
              <div
                className="absolute inset-0 z-10 bg-black/50"
                onClick={() => setShowConversationList(false)}
              >
                <div
                  className="absolute left-0 top-0 bottom-0 w-80 max-w-[85vw] bg-white dark:bg-surface-800"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ChatConversationList onClose={() => setShowConversationList(false)} />
                </div>
              </div>
            )}

            {/* Chat area */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Messages or empty state */}
              <div className="flex-1 overflow-y-auto">
                {!activeConversation ? (
                  <ChatEmptyState
                    context={currentContext?.page}
                    onSelectPrompt={handleSelectPrompt}
                  />
                ) : !hasMessages ? (
                  <ChatEmptyConversation onSelectPrompt={handleSelectPrompt} />
                ) : (
                  <div className="py-4">
                    {messages.map((message, index) => (
                      <ChatMessage
                        key={message.id}
                        message={message}
                        isLast={index === messages.length - 1}
                      />
                    ))}
                    {isTyping && <ChatTypingIndicator />}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* Input area */}
              <ChatInput />
            </div>
          </div>
        </div>
      </div>

      {/* Backdrop for mobile */}
      {isOpen && !isMinimized && (
        <div
          className="fixed inset-0 z-30 bg-black/20 lg:hidden"
          onClick={closeChat}
          aria-hidden="true"
        />
      )}
    </>
  );
}

/**
 * ChatHeader - Header bar with controls
 */
function ChatHeader({
  isExpanded,
  showConversationList,
  onToggleExpand,
  onToggleConversationList,
  onMinimize,
  onClose,
}) {
  return (
    <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
      {/* Left side */}
      <div className="flex items-center gap-3">
        {/* Toggle conversation list */}
        <button
          onClick={onToggleConversationList}
          className="
            p-2 rounded-lg
            text-surface-500 dark:text-surface-400
            hover:text-surface-700 dark:hover:text-surface-200
            hover:bg-surface-100 dark:hover:bg-surface-700
            transition-colors duration-150
            hidden lg:block
          "
          aria-label={showConversationList ? 'Hide conversations' : 'Show conversations'}
        >
          <Bars3Icon className="w-5 h-5" />
        </button>

        {/* Mobile menu button */}
        <button
          onClick={onToggleConversationList}
          className="
            p-2 rounded-lg
            text-surface-500 dark:text-surface-400
            hover:text-surface-700 dark:hover:text-surface-200
            hover:bg-surface-100 dark:hover:bg-surface-700
            transition-colors duration-150
            lg:hidden
          "
          aria-label="Open menu"
        >
          <Bars3Icon className="w-5 h-5" />
        </button>

        {/* Logo and title */}
        <div className="flex items-center gap-2">
          <img
            src="/assets/aura-spiral.png"
            alt="Aura"
            className="w-7 h-7 rounded-lg object-contain"
          />
          <h2 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
            Aura Assistant
          </h2>
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-1">
        {/* Expand/collapse */}
        <button
          onClick={onToggleExpand}
          className="
            p-2 rounded-lg
            text-surface-500 dark:text-surface-400
            hover:text-surface-700 dark:hover:text-surface-200
            hover:bg-surface-100 dark:hover:bg-surface-700
            transition-colors duration-150
            hidden lg:block
          "
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? (
            <ArrowsPointingInIcon className="w-5 h-5" />
          ) : (
            <ArrowsPointingOutIcon className="w-5 h-5" />
          )}
        </button>

        {/* Minimize */}
        <button
          onClick={onMinimize}
          className="
            p-2 rounded-lg
            text-surface-500 dark:text-surface-400
            hover:text-surface-700 dark:hover:text-surface-200
            hover:bg-surface-100 dark:hover:bg-surface-700
            transition-colors duration-150
          "
          aria-label="Minimize"
        >
          <ChevronDownIcon className="w-5 h-5" />
        </button>

        {/* Close */}
        <button
          onClick={onClose}
          className="
            p-2 rounded-lg
            text-surface-500 dark:text-surface-400
            hover:text-surface-700 dark:hover:text-surface-200
            hover:bg-surface-100 dark:hover:bg-surface-700
            transition-colors duration-150
          "
          aria-label="Close"
        >
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

/**
 * ChatAssistantProvider - Wrapper that includes the ChatProvider
 * Use this in App.jsx if you want a self-contained chat component
 */
export { ChatProvider } from '../../context/ChatContext';
