/**
 * Chat Components Index
 *
 * Aura Assistant - AI-powered chat interface for Project Aura
 *
 * Usage:
 * 1. Wrap your app with ChatProvider (in App.jsx or main.jsx)
 * 2. Add ChatAssistant component at the root level
 * 3. Use useChat() hook to access chat state and actions
 *
 * Example:
 * ```jsx
 * import { ChatProvider } from './context/ChatContext';
 * import ChatAssistant from './components/chat/ChatAssistant';
 *
 * function App() {
 *   return (
 *     <ChatProvider>
 *       <YourApp />
 *       <ChatAssistant />
 *     </ChatProvider>
 *   );
 * }
 * ```
 */

// Main container component
export { default as ChatAssistant } from './ChatAssistant';

// Individual components
export { default as ChatFloatingButton } from './ChatFloatingButton';
export { default as ChatMessage } from './ChatMessage';
export { default as ChatInput, ChatInputCompact } from './ChatInput';
export { default as ChatConversationList } from './ChatConversationList';
export { default as ChatEmptyState, ChatEmptyConversation } from './ChatEmptyState';
export { default as ChatTypingIndicator, ChatTypingIndicatorInline } from './ChatTypingIndicator';
export {
  default as ChatSuggestedPrompt,
  ChatSuggestedPromptGrid,
  ChatQuickFilters,
  defaultPrompts,
  contextPrompts,
} from './ChatSuggestedPrompt';

// Context and hooks
export { ChatProvider, useChat } from '../../context/ChatContext';
