# Aura Assistant - Chat Interface

A 24/7 AI-powered chat assistant for the Project Aura platform. Helps users query metrics, generate reports, get configuration help, and search documentation.

## Architecture Overview

### Design Decision: Floating Panel Approach

After analyzing the placement options, I chose a **hybrid floating button + slide-in panel** approach:

| Approach | Pros | Cons |
|----------|------|------|
| **Floating button + modal** | Familiar pattern, non-blocking | Can feel disconnected |
| **Sidebar panel** | Always visible, persistent | Uses screen real estate |
| **Dedicated page** | Full-featured, focused | Breaks workflow |
| **Split view** | Context + chat together | Complex layout |

**Final Choice: Floating Button + Slide-in Panel**

This approach:
1. **Non-disruptive**: Users can still see and interact with the main app
2. **Persistent**: Chat stays open while navigating between pages
3. **Familiar**: Matches patterns from Intercom, Drift, ChatGPT
4. **Mobile-friendly**: Adapts to full-screen on small devices
5. **Context-aware**: Can read current page context

---

## Component Structure

```
frontend/src/
├── context/
│   └── ChatContext.jsx       # State management (conversations, messages, UI state)
└── components/
    └── chat/
        ├── index.js                    # Exports all components
        ├── ChatAssistant.jsx           # Main container component
        ├── ChatFloatingButton.jsx      # Floating action button (bottom-right)
        ├── ChatInput.jsx               # Message input with auto-grow
        ├── ChatMessage.jsx             # Individual message with markdown
        ├── ChatConversationList.jsx    # Sidebar with conversation history
        ├── ChatEmptyState.jsx          # Welcome screen
        ├── ChatTypingIndicator.jsx     # Animated typing dots
        ├── ChatSuggestedPrompt.jsx     # Quick action cards
        └── README.md                   # This file
```

---

## Usage

### Basic Integration

The chat assistant is already integrated into `App.jsx`. To use it in a new project:

```jsx
import { ChatProvider } from './context/ChatContext';
import ChatAssistant from './components/chat/ChatAssistant';

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ChatProvider>
          <BrowserRouter>
            {/* Your routes */}
          </BrowserRouter>
          <ChatAssistant />
        </ChatProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
```

### Using the useChat Hook

Access chat functionality from any component:

```jsx
import { useChat } from '../../context/ChatContext';

function MyComponent() {
  const {
    openChat,
    closeChat,
    sendMessage,
    isOpen,
    activeConversation,
    setCurrentContext,
  } = useChat();

  // Set context for context-aware suggestions
  useEffect(() => {
    setCurrentContext({ page: 'approvals', data: { pendingCount: 7 } });
  }, []);

  return (
    <button onClick={() => {
      openChat();
      sendMessage('Show me pending approvals');
    }}>
      Ask about approvals
    </button>
  );
}
```

---

## Visual Design

### Color Scheme

Following Project Aura design system:

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| User message bubble | `#3B82F6` (aura-500) | `#3B82F6` |
| Assistant message bubble | `#F3F4F6` (surface-100) | `#374151` (surface-700) |
| Send button | `#7C9A3E` (olive-500) | `#7C9A3E` |
| Floating button | `#7C9A3E` (olive-500) | `#6B8E23` (olive-600) |
| Links | `#6B8E23` (olive-600) | `#9FB87A` (olive-400) |

### Typography

- **Messages**: Inter, 14px (text-sm)
- **Code blocks**: JetBrains Mono, 13px (text-code)
- **Timestamps**: Inter, 12px (text-xs)

### Spacing

- **Message padding**: 16px (p-4)
- **Message gap**: 12px (gap-3)
- **Panel padding**: 16px (p-4)

---

## Responsive Behavior

### Desktop (>1024px)
- Chat panel: 420px wide, 600px tall
- Expandable to near-fullscreen
- Conversation list sidebar visible

### Tablet (768-1024px)
- Chat panel: 420px wide, 600px tall
- Conversation list as overlay

### Mobile (<768px)
- Full-screen chat interface
- Backdrop overlay behind panel
- Fixed bottom input bar

---

## Component Details

### ChatFloatingButton

Floating action button in bottom-right corner:
- Olive green background
- Icon transition (chat icon / X icon)
- Pulse animation for unread messages
- Tooltip on hover

### ChatEmptyState

Welcome screen when no conversation:
- Aura logo with gradient
- Capability overview
- Suggested prompts grid
- Keyboard shortcut hint

### ChatMessage

Individual message display:
- User messages: Right-aligned, blue bubble
- Assistant messages: Left-aligned, gray bubble
- Markdown rendering (bold, lists, code, links, tables)
- Code blocks with syntax highlighting
- Copy code button
- Thumbs up/down feedback
- Regenerate button

### ChatInput

Message input area:
- Auto-growing textarea
- Enter to send, Shift+Enter for new line
- Character counter (shows near limit)
- Attachment button (future)
- Voice input button (future)
- Send button with olive green styling

### ChatConversationList

Conversation history sidebar:
- Grouped by time (Today, Yesterday, Last 7 days, Older)
- Pinned conversations at top
- Search functionality
- Context menu (rename, pin, delete, export)
- New conversation button

### ChatTypingIndicator

Animated indicator while assistant responds:
- Three bouncing dots
- "Aura is thinking..." label
- Matches assistant message styling

---

## State Management

### ChatContext provides:

```typescript
interface ChatContextValue {
  // UI State
  isOpen: boolean;
  isMinimized: boolean;
  isTyping: boolean;
  isLoading: boolean;
  showConversationList: boolean;

  // Data
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversation: Conversation | null;
  draftMessage: string;
  currentContext: { page: string; data: any };

  // Actions
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  minimizeChat: () => void;
  restoreChat: () => void;
  createConversation: () => Conversation;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  togglePinConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  sendMessage: (content: string) => Promise<void>;
  regenerateResponse: () => Promise<void>;
  setDraftMessage: (message: string) => void;
  setCurrentContext: (context: object) => void;
  searchConversations: (query: string) => Conversation[];
  exportConversation: (id: string) => string | null;
}
```

### Persistence

- **Conversations**: Stored in localStorage (`aura-chat-conversations`)
- **Draft message**: Stored in localStorage (`aura-chat-draft`)

---

## API Integration

The chat currently uses mock responses. To integrate with a real backend:

1. Update `ChatContext.jsx` `sendMessage` function:

```jsx
const sendMessage = useCallback(async (content) => {
  // ... existing code ...

  try {
    const response = await fetch('/api/v1/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversationId,
        message: content,
        context: currentContext,
      }),
    });

    const data = await response.json();

    const assistantMessage = {
      id: generateId(),
      role: 'assistant',
      content: data.response,
      timestamp: new Date().toISOString(),
      status: 'sent',
    };

    // Update conversation...
  } catch (error) {
    // Handle error...
  }
}, [/* deps */]);
```

### Expected API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/message` | POST | Send message, get response |
| `/api/v1/chat/conversations` | GET | List user's conversations |
| `/api/v1/chat/conversations/{id}/messages` | GET | Get conversation messages |
| `/api/v1/chat/conversations/{id}` | DELETE | Delete conversation |

---

## Accessibility

### Keyboard Navigation

- `Tab`: Navigate between interactive elements
- `Enter`: Send message, activate buttons
- `Shift+Enter`: New line in input
- `Escape`: Close chat panel
- `Cmd/Ctrl + /`: Toggle chat (global shortcut)

### Screen Reader Support

- All buttons have `aria-label`
- Chat panel has `role="dialog"` and `aria-label`
- Messages are in semantic HTML
- Focus management on open/close

### Color Contrast

- All text meets WCAG 2.1 AA (4.5:1 minimum)
- Dark mode fully supported
- Focus indicators use olive green outline

---

## Animations

| Animation | Duration | Easing | Purpose |
|-----------|----------|--------|---------|
| Panel slide-in | 300ms | ease-smooth | Opening chat |
| Message fade-in-up | 300ms | ease-out | New messages |
| Typing dots bounce | 600ms | ease-in-out | Typing indicator |
| Button hover | 200ms | ease-smooth | Interaction feedback |
| Icon rotation | 300ms | ease-smooth | Button state change |

---

## Future Enhancements

### Planned Features

1. **File Attachments**: Upload screenshots, logs, config files
2. **Voice Input**: Speech-to-text for hands-free input
3. **Streaming Responses**: Real-time response streaming (SSE/WebSocket)
4. **Rich Actions**: Inline buttons that trigger platform actions
5. **Charts in Responses**: Embedded visualizations for metrics
6. **Multi-modal**: Support for images in responses

### Integration Improvements

1. **Deep Linking**: Navigate to entities mentioned in responses
2. **Context Injection**: Auto-inject relevant page data
3. **Proactive Suggestions**: Offer help based on user behavior
4. **Notification Integration**: Show chat notifications in header

---

## Testing

Run tests with:

```bash
cd frontend
npm test -- --grep "Chat"
```

Test coverage includes:
- Component rendering
- User interactions
- State management
- Keyboard navigation
- Dark mode

---

## Contributing

When modifying chat components:

1. Follow Project Aura design system
2. Ensure dark mode compatibility
3. Test keyboard navigation
4. Add ARIA labels for accessibility
5. Update this README if adding features
