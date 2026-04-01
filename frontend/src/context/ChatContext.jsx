import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import * as chatApi from '../services/chatApi';

/**
 * ChatContext - State management for Aura Assistant
 *
 * Manages:
 * - Conversations list and active conversation
 * - Messages within conversations
 * - Chat panel visibility
 * - Loading/typing states
 * - Context awareness (current page)
 * - Real-time streaming via SSE
 * - Deep research tasks with async progress tracking
 * - Token usage tracking
 * - Message retry on failure
 *
 * Backend Integration:
 * - REST API for conversation management
 * - SSE streaming for real-time responses
 * - Research task polling for async deep analysis
 * - Graceful fallback to mock responses when backend unavailable
 */

const ChatContext = createContext(undefined);

// Storage keys for localStorage persistence
const STORAGE_KEY = 'aura-chat-conversations';
const DRAFT_KEY = 'aura-chat-draft';
const RESEARCH_TASKS_KEY = 'aura-research-tasks';
const TOKEN_USAGE_KEY = 'aura-chat-token-usage';

// Research task polling interval (ms)
const RESEARCH_POLL_INTERVAL = 3000;

// Maximum retry attempts for failed messages
const MAX_RETRY_ATTEMPTS = 3;

// Configuration
const CHAT_API_URL = import.meta.env.VITE_CHAT_API_URL || '';
const USE_MOCK_CHAT = import.meta.env.VITE_MOCK_CHAT === 'true' || !CHAT_API_URL;

// Generate unique IDs
const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Generate conversation title from first message
const generateTitle = (content) => {
  const cleaned = content.replace(/[#*`]/g, '').trim();
  return cleaned.length > 40 ? cleaned.substring(0, 40) + '...' : cleaned;
};

export function ChatProvider({ children }) {
  // Chat panel visibility
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  // Conversations state
  const [conversations, setConversations] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Active conversation ID
  const [activeConversationId, setActiveConversationId] = useState(null);

  // Loading/typing states
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, _setIsLoading] = useState(false);

  // Streaming state
  const [streamingMessageId, setStreamingMessageId] = useState(null);
  const [streamingContent, setStreamingContent] = useState('');

  // Draft message (persisted across sessions)
  const [draftMessage, setDraftMessage] = useState(() => {
    try {
      return localStorage.getItem(DRAFT_KEY) || '';
    } catch {
      return '';
    }
  });

  // Context awareness - current page/route
  const [currentContext, setCurrentContext] = useState({
    page: 'dashboard',
    data: null,
  });

  // Sidebar visibility for conversation list
  // Default to false for clean initial view in compact panel mode
  const [showConversationList, setShowConversationList] = useState(false);

  // Token usage tracking
  const [totalTokenUsage, setTotalTokenUsage] = useState(() => {
    try {
      const saved = localStorage.getItem(TOKEN_USAGE_KEY);
      return saved ? JSON.parse(saved) : { promptTokens: 0, completionTokens: 0, totalTokens: 0 };
    } catch {
      return { promptTokens: 0, completionTokens: 0, totalTokens: 0 };
    }
  });

  // Research tasks state - tracks async deep research operations
  const [researchTasks, setResearchTasks] = useState(() => {
    try {
      const saved = localStorage.getItem(RESEARCH_TASKS_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Abort controller for canceling streams
  const abortControllerRef = useRef(null);

  // Polling intervals for active research tasks
  const pollingIntervalsRef = useRef({});

  // Failed message retry tracking
  const retryCountRef = useRef({});

  // Persist conversations to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch (e) {
      console.warn('Failed to save conversations to localStorage:', e);
    }
  }, [conversations]);

  // Persist draft message
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, draftMessage);
    } catch (e) {
      console.warn('Failed to save draft to localStorage:', e);
    }
  }, [draftMessage]);

  // Persist research tasks
  useEffect(() => {
    try {
      localStorage.setItem(RESEARCH_TASKS_KEY, JSON.stringify(researchTasks));
    } catch (e) {
      console.warn('Failed to save research tasks to localStorage:', e);
    }
  }, [researchTasks]);

  // Persist token usage
  useEffect(() => {
    try {
      localStorage.setItem(TOKEN_USAGE_KEY, JSON.stringify(totalTokenUsage));
    } catch (e) {
      console.warn('Failed to save token usage to localStorage:', e);
    }
  }, [totalTokenUsage]);

  // Cleanup on unmount
  useEffect(() => {
    // Capture refs at effect creation time for cleanup
    const pollingIntervals = pollingIntervalsRef.current;
    const abortController = abortControllerRef.current;
    return () => {
      Object.values(pollingIntervals).forEach(clearInterval);
      if (abortController) {
        abortController.abort();
      }
    };
  }, []);

  // Get active conversation
  const activeConversation = conversations.find(c => c.id === activeConversationId) || null;

  // Open chat panel
  const openChat = useCallback(() => {
    setIsOpen(true);
    setIsMinimized(false);
  }, []);

  // Close chat panel
  const closeChat = useCallback(() => {
    setIsOpen(false);
    setIsMinimized(false);
  }, []);

  // Toggle chat panel
  const toggleChat = useCallback(() => {
    if (isMinimized) {
      // Restore from minimized state
      setIsMinimized(false);
      setIsOpen(true);
    } else if (isOpen) {
      // Close the chat
      setIsOpen(false);
    } else {
      // Open the chat
      setIsOpen(true);
    }
  }, [isMinimized, isOpen]);

  // Minimize/restore chat
  const minimizeChat = useCallback(() => {
    setIsMinimized(true);
  }, []);

  const restoreChat = useCallback(() => {
    setIsMinimized(false);
    setIsOpen(true);
  }, []);

  // Create new conversation
  const createConversation = useCallback(() => {
    const newConversation = {
      id: generateId(),
      title: 'New Conversation',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      isPinned: false,
    };

    setConversations(prev => [newConversation, ...prev]);
    setActiveConversationId(newConversation.id);
    setDraftMessage('');

    return newConversation;
  }, []);

  // Select a conversation
  const selectConversation = useCallback((conversationId) => {
    setActiveConversationId(conversationId);
    setDraftMessage('');
    // Cancel any ongoing stream when switching conversations
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  // Delete a conversation
  const deleteConversation = useCallback(async (conversationId) => {
    // Try to delete from backend first
    try {
      await chatApi.deleteConversation(conversationId);
    } catch (error) {
      console.warn('Failed to delete conversation from backend:', error);
      // Continue with local deletion even if backend fails
    }

    setConversations(prev => prev.filter(c => c.id !== conversationId));
    if (activeConversationId === conversationId) {
      setActiveConversationId(null);
    }
  }, [activeConversationId]);

  // Pin/unpin a conversation
  const togglePinConversation = useCallback(async (conversationId) => {
    const conversation = conversations.find(c => c.id === conversationId);
    if (!conversation) return;

    const newPinned = !conversation.isPinned;

    // Update backend
    try {
      await chatApi.updateConversation(conversationId, { isPinned: newPinned });
    } catch (error) {
      console.warn('Failed to update conversation on backend:', error);
    }

    // Update local state
    setConversations(prev =>
      prev.map(c =>
        c.id === conversationId
          ? { ...c, isPinned: newPinned }
          : c
      ).sort((a, b) => {
        // Pinned first, then by updatedAt
        if (a.isPinned !== b.isPinned) return b.isPinned ? 1 : -1;
        return new Date(b.updatedAt) - new Date(a.updatedAt);
      })
    );
  }, [conversations]);

  // Rename a conversation
  const renameConversation = useCallback(async (conversationId, newTitle) => {
    // Update backend
    try {
      await chatApi.updateConversation(conversationId, { title: newTitle });
    } catch (error) {
      console.warn('Failed to update conversation title on backend:', error);
    }

    // Update local state
    setConversations(prev =>
      prev.map(c =>
        c.id === conversationId
          ? { ...c, title: newTitle }
          : c
      )
    );
  }, []);

  // Cancel current stream
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsTyping(false);
    setStreamingMessageId(null);
    setStreamingContent('');
  }, []);

  // Send a message with streaming support
  const sendMessage = useCallback(async (content, attachments = []) => {
    // Allow sending with attachments only (no text content required)
    if (!content.trim() && attachments.length === 0) return;

    let conversationId = activeConversationId;

    // Create new conversation if none active
    if (!conversationId) {
      const newConversation = createConversation();
      conversationId = newConversation.id;
    }

    // Cancel any existing stream
    cancelStream();

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    // Create user message with optional attachments
    const userMessage = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
      status: 'sent',
      attachments: attachments.length > 0 ? attachments : undefined,
    };

    // Create placeholder for assistant message
    const assistantMessageId = generateId();
    const assistantMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      status: 'streaming',
      isStreaming: true,
    };

    // Update conversation with both messages
    setConversations(prev =>
      prev.map(c => {
        if (c.id !== conversationId) return c;

        const isFirstMessage = c.messages.length === 0;
        return {
          ...c,
          title: isFirstMessage ? generateTitle(content) : c.title,
          messages: [...c.messages, userMessage, assistantMessage],
          updatedAt: new Date().toISOString(),
        };
      })
    );

    // Clear draft and set streaming state
    setDraftMessage('');
    setIsTyping(true);
    setStreamingMessageId(assistantMessageId);
    setStreamingContent('');

    try {
      // Send message with streaming
      const result = await chatApi.sendMessage(
        content.trim(),
        attachments,
        conversationId,
        {
          context: currentContext,
          signal: abortControllerRef.current.signal,
          onToken: (token, fullContent) => {
            setStreamingContent(fullContent);
            // Update the message content in real-time
            setConversations(prev =>
              prev.map(c => {
                if (c.id !== conversationId) return c;
                return {
                  ...c,
                  messages: c.messages.map(m =>
                    m.id === assistantMessageId
                      ? { ...m, content: fullContent }
                      : m
                  ),
                };
              })
            );
          },
          onToolCall: (toolCall) => {
            // Update message with tool call
            setConversations(prev =>
              prev.map(c => {
                if (c.id !== conversationId) return c;
                return {
                  ...c,
                  messages: c.messages.map(m =>
                    m.id === assistantMessageId
                      ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
                      : m
                  ),
                };
              })
            );
          },
          onComplete: (response) => {
            // Finalize the message
            setConversations(prev =>
              prev.map(c => {
                if (c.id !== conversationId) return c;
                return {
                  ...c,
                  messages: c.messages.map(m =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          content: response.content,
                          status: 'sent',
                          isStreaming: false,
                          modelId: response.modelId,
                          tokenUsage: response.tokenUsage,
                          toolCalls: response.toolCalls,
                        }
                      : m
                  ),
                  updatedAt: new Date().toISOString(),
                };
              })
            );

            // Update token usage
            if (response.tokenUsage) {
              setTotalTokenUsage(prev => ({
                promptTokens: prev.promptTokens + (response.tokenUsage.promptTokens || 0),
                completionTokens: prev.completionTokens + (response.tokenUsage.completionTokens || 0),
                totalTokens: prev.totalTokens + (response.tokenUsage.totalTokens || 0),
              }));
            }

            // Clear retry count on success
            delete retryCountRef.current[userMessage.id];
          },
          onError: (error) => {
            console.error('Stream error:', error);
          },
        }
      );

      return result;
    } catch (error) {
      // Handle abort
      if (error.name === 'AbortError') {
        // Mark message as cancelled
        setConversations(prev =>
          prev.map(c => {
            if (c.id !== conversationId) return c;
            return {
              ...c,
              messages: c.messages.map(m =>
                m.id === assistantMessageId
                  ? { ...m, status: 'cancelled', isStreaming: false }
                  : m
              ),
            };
          })
        );
        return;
      }

      console.error('Failed to send message:', error);

      // Mark message as failed
      setConversations(prev =>
        prev.map(c => {
          if (c.id !== conversationId) return c;
          return {
            ...c,
            messages: c.messages.map(m =>
              m.id === assistantMessageId
                ? {
                    ...m,
                    status: 'error',
                    isStreaming: false,
                    error: error.message,
                    canRetry: error.isRetryable !== false,
                  }
                : m
            ),
          };
        })
      );
    } finally {
      setIsTyping(false);
      setStreamingMessageId(null);
      setStreamingContent('');
      abortControllerRef.current = null;
    }
  }, [activeConversationId, createConversation, currentContext, cancelStream]);

  // Retry a failed message
  const retryMessage = useCallback(async (messageId) => {
    const conversation = activeConversation;
    if (!conversation) return;

    // Find the failed assistant message and the preceding user message
    const messageIndex = conversation.messages.findIndex(m => m.id === messageId);
    if (messageIndex < 0) return;

    const failedMessage = conversation.messages[messageIndex];
    if (failedMessage.role !== 'assistant' || failedMessage.status !== 'error') return;

    // Find the user message that triggered this response
    let userMessage = null;
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (conversation.messages[i].role === 'user') {
        userMessage = conversation.messages[i];
        break;
      }
    }

    if (!userMessage) return;

    // Track retry count
    const retryCount = (retryCountRef.current[userMessage.id] || 0) + 1;
    if (retryCount > MAX_RETRY_ATTEMPTS) {
      console.warn('Maximum retry attempts reached for message:', userMessage.id);
      return;
    }
    retryCountRef.current[userMessage.id] = retryCount;

    // Remove the failed message
    setConversations(prev =>
      prev.map(c => {
        if (c.id !== conversation.id) return c;
        return {
          ...c,
          messages: c.messages.filter(m => m.id !== messageId),
        };
      })
    );

    // Resend the message
    await sendMessage(userMessage.content, userMessage.attachments || []);
  }, [activeConversation, sendMessage]);

  // Regenerate last assistant response
  const regenerateResponse = useCallback(async () => {
    if (!activeConversation || activeConversation.messages.length < 2) return;

    const messages = activeConversation.messages;
    const lastAssistantIndex = [...messages].reverse().findIndex(m => m.role === 'assistant');

    if (lastAssistantIndex < 0) return;

    const actualIndex = messages.length - 1 - lastAssistantIndex;
    const lastAssistantMessage = messages[actualIndex];

    // Find the user message that triggered this response
    let userMessage = null;
    for (let i = actualIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMessage = messages[i];
        break;
      }
    }

    if (!userMessage) return;

    // Remove the last assistant message
    setConversations(prev =>
      prev.map(c => {
        if (c.id !== activeConversationId) return c;
        return {
          ...c,
          messages: c.messages.filter(m => m.id !== lastAssistantMessage.id),
        };
      })
    );

    // Resend the message
    await sendMessage(userMessage.content, userMessage.attachments || []);
  }, [activeConversation, activeConversationId, sendMessage]);

  // Copy message content
  const copyMessageContent = useCallback(async (messageId) => {
    const conversation = activeConversation;
    if (!conversation) return false;

    const message = conversation.messages.find(m => m.id === messageId);
    if (!message) return false;

    return await chatApi.copyToClipboard(message.content);
  }, [activeConversation]);

  // Rate a message
  const rateMessage = useCallback(async (messageId, rating) => {
    try {
      await chatApi.rateMessage(messageId, rating);

      // Update local state
      setConversations(prev =>
        prev.map(c => ({
          ...c,
          messages: c.messages.map(m =>
            m.id === messageId
              ? { ...m, rating }
              : m
          ),
        }))
      );

      return true;
    } catch (error) {
      console.error('Failed to rate message:', error);
      return false;
    }
  }, []);

  // Search conversations
  const searchConversations = useCallback((query) => {
    if (!query.trim()) return conversations;

    const lowerQuery = query.toLowerCase();
    return conversations.filter(c =>
      c.title.toLowerCase().includes(lowerQuery) ||
      c.messages.some(m => m.content.toLowerCase().includes(lowerQuery))
    );
  }, [conversations]);

  // Export conversation as markdown
  const exportConversation = useCallback((conversationId) => {
    const conversation = conversations.find(c => c.id === conversationId);
    if (!conversation) return null;

    let markdown = `# ${conversation.title}\n\n`;
    markdown += `*Exported on ${new Date().toLocaleDateString()}*\n\n---\n\n`;

    conversation.messages.forEach(message => {
      const role = message.role === 'user' ? 'You' : 'Aura Assistant';
      const timestamp = new Date(message.timestamp).toLocaleString();
      markdown += `**${role}** *(${timestamp})*\n\n${message.content}\n\n---\n\n`;
    });

    return markdown;
  }, [conversations]);

  // ==========================================================================
  // Research Task Management
  // ==========================================================================

  // Start a new deep research task
  const startResearchTask = useCallback(async (query, options = {}) => {
    const {
      scope = 'repository',
      urgency = 'standard',
      dataSources = ['code_graph', 'security_findings'],
    } = options;

    // Create optimistic task entry
    const taskId = `RSH-${generateId().toUpperCase().substring(0, 12)}`;
    const newTask = {
      taskId,
      query,
      scope,
      urgency,
      dataSources,
      status: 'pending',
      progress: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      result: null,
      error: null,
    };

    setResearchTasks(prev => [newTask, ...prev]);

    try {
      if (!USE_MOCK_CHAT && CHAT_API_URL) {
        // Call real API to start research
        const token = localStorage.getItem('aura_auth_tokens');
        const accessToken = token ? JSON.parse(token).access_token : null;

        const response = await fetch(`${CHAT_API_URL}/chat/research`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(accessToken && { 'Authorization': `Bearer ${accessToken}` }),
          },
          body: JSON.stringify({
            research_query: query,
            scope,
            urgency,
            data_sources: dataSources,
          }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        // Update task with server response
        setResearchTasks(prev =>
          prev.map(t =>
            t.taskId === taskId
              ? { ...t, taskId: data.task_id, status: data.status, progress: data.progress }
              : t
          )
        );

        // Start polling for progress if task is async
        if (data.status !== 'completed') {
          startPollingTask(data.task_id);
        }

        return data;
      } else {
        // Mock research task - simulate progress
        simulateMockResearch(taskId, query);
        return newTask;
      }
    } catch (error) {
      console.error('Failed to start research task:', error);

      // Update task with error
      setResearchTasks(prev =>
        prev.map(t =>
          t.taskId === taskId
            ? { ...t, status: 'failed', error: error.message }
            : t
        )
      );

      // Fall back to mock
      simulateMockResearch(taskId, query);
      return newTask;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll for research task status
  const pollResearchStatus = useCallback(async (taskId) => {
    try {
      if (!USE_MOCK_CHAT && CHAT_API_URL) {
        const token = localStorage.getItem('aura_auth_tokens');
        const accessToken = token ? JSON.parse(token).access_token : null;

        const response = await fetch(`${CHAT_API_URL}/chat/research/${taskId}`, {
          headers: {
            ...(accessToken && { 'Authorization': `Bearer ${accessToken}` }),
          },
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        // Update task state
        setResearchTasks(prev =>
          prev.map(t =>
            t.taskId === taskId
              ? {
                  ...t,
                  status: data.status,
                  progress: data.progress,
                  result: data.result,
                  error: data.error,
                  updatedAt: new Date().toISOString(),
                }
              : t
          )
        );

        // Stop polling if completed or failed
        if (data.status === 'completed' || data.status === 'failed') {
          stopPollingTask(taskId);
        }

        return data;
      }
    } catch (error) {
      console.error('Failed to poll research status:', error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Start polling for a task
  const startPollingTask = useCallback((taskId) => {
    if (pollingIntervalsRef.current[taskId]) return;

    pollingIntervalsRef.current[taskId] = setInterval(() => {
      pollResearchStatus(taskId);
    }, RESEARCH_POLL_INTERVAL);
  }, [pollResearchStatus]);

  // Stop polling for a task
  const stopPollingTask = useCallback((taskId) => {
    if (pollingIntervalsRef.current[taskId]) {
      clearInterval(pollingIntervalsRef.current[taskId]);
      delete pollingIntervalsRef.current[taskId];
    }
  }, []);

  // Get a specific research task
  const getResearchTask = useCallback((taskId) => {
    return researchTasks.find(t => t.taskId === taskId);
  }, [researchTasks]);

  // Get active (in-progress) research tasks
  const activeResearchTasks = researchTasks.filter(
    t => t.status === 'pending' || t.status === 'in_progress'
  );

  // Clear completed research tasks
  const clearCompletedResearchTasks = useCallback(() => {
    setResearchTasks(prev =>
      prev.filter(t => t.status !== 'completed' && t.status !== 'failed')
    );
  }, []);

  // Dismiss a specific research task
  const dismissResearchTask = useCallback((taskId) => {
    stopPollingTask(taskId);
    setResearchTasks(prev => prev.filter(t => t.taskId !== taskId));
  }, [stopPollingTask]);

  // Simulate mock research progress for development
  const simulateMockResearch = useCallback((taskId, query) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 20 + 5;

      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);

        // Generate mock result
        const result = generateMockResearchResult(query);

        setResearchTasks(prev =>
          prev.map(t =>
            t.taskId === taskId
              ? {
                  ...t,
                  status: 'completed',
                  progress: 100,
                  result,
                  updatedAt: new Date().toISOString(),
                }
              : t
          )
        );
      } else {
        setResearchTasks(prev =>
          prev.map(t =>
            t.taskId === taskId
              ? {
                  ...t,
                  status: 'in_progress',
                  progress: Math.min(Math.round(progress), 95),
                  updatedAt: new Date().toISOString(),
                }
              : t
          )
        );
      }
    }, 1000);

    // Store interval for cleanup
    pollingIntervalsRef.current[taskId] = interval;
  }, []);

  // Context value
  const value = {
    // State
    isOpen,
    isMinimized,
    isTyping,
    isLoading,
    conversations,
    activeConversationId,
    activeConversation,
    draftMessage,
    currentContext,
    showConversationList,
    streamingMessageId,
    streamingContent,
    totalTokenUsage,

    // Research task state
    researchTasks,
    activeResearchTasks,

    // Actions
    openChat,
    closeChat,
    toggleChat,
    minimizeChat,
    restoreChat,
    createConversation,
    selectConversation,
    deleteConversation,
    togglePinConversation,
    renameConversation,
    sendMessage,
    cancelStream,
    retryMessage,
    regenerateResponse,
    copyMessageContent,
    rateMessage,
    setDraftMessage,
    setCurrentContext,
    setShowConversationList,
    searchConversations,
    exportConversation,

    // Research task actions
    startResearchTask,
    getResearchTask,
    pollResearchStatus,
    dismissResearchTask,
    clearCompletedResearchTasks,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}

// Mock research result generator for development
function generateMockResearchResult(query) {
  const lowerQuery = query.toLowerCase();

  // Security-related queries
  if (lowerQuery.includes('security') || lowerQuery.includes('vulnerab') || lowerQuery.includes('cve')) {
    return {
      type: 'security_analysis',
      summary: 'Security analysis completed for the specified scope.',
      findings: [
        {
          severity: 'high',
          title: 'Outdated dependency with known CVE',
          description: 'boto3 version should be updated to address CVE-2024-XXXXX',
          recommendation: 'Update boto3 to version 1.35.0 or later',
          affectedFiles: ['requirements.txt'],
        },
        {
          severity: 'medium',
          title: 'Missing input validation',
          description: 'API endpoint lacks proper input sanitization',
          recommendation: 'Add pydantic validation to request handlers',
          affectedFiles: ['src/api/routes/chat.py'],
        },
      ],
      metrics: {
        filesAnalyzed: 156,
        vulnerabilitiesFound: 2,
        securityScore: 87,
      },
    };
  }

  // Architecture-related queries
  if (lowerQuery.includes('architecture') || lowerQuery.includes('design') || lowerQuery.includes('structure')) {
    return {
      type: 'architecture_analysis',
      summary: 'Architecture analysis completed.',
      components: [
        { name: 'Agent Orchestrator', status: 'healthy', coupling: 'low' },
        { name: 'Context Retrieval', status: 'healthy', coupling: 'medium' },
        { name: 'Sandbox Network', status: 'healthy', coupling: 'low' },
      ],
      recommendations: [
        'Consider extracting shared utilities into a common module',
        'Add circuit breaker pattern for Neptune queries',
      ],
      metrics: {
        totalComponents: 12,
        couplingScore: 0.3,
        cohesionScore: 0.8,
      },
    };
  }

  // Code quality queries
  if (lowerQuery.includes('quality') || lowerQuery.includes('refactor') || lowerQuery.includes('debt')) {
    return {
      type: 'code_quality_analysis',
      summary: 'Code quality analysis completed.',
      hotspots: [
        { file: 'src/agents/orchestrator.py', complexity: 45, issues: 3 },
        { file: 'src/services/context_retrieval.py', complexity: 38, issues: 2 },
      ],
      metrics: {
        totalLines: 150000,
        testCoverage: 78.5,
        averageComplexity: 12.3,
        technicalDebtHours: 45,
      },
      recommendations: [
        'Reduce cyclomatic complexity in orchestrator.py',
        'Add unit tests for edge cases in context_retrieval.py',
      ],
    };
  }

  // Default comprehensive analysis
  return {
    type: 'comprehensive_analysis',
    summary: `Research completed for query: ${query}`,
    findings: [
      'Analysis covered all specified data sources',
      'No critical issues identified',
      'Recommendations provided for improvements',
    ],
    metrics: {
      filesAnalyzed: 200,
      dataPointsProcessed: 5000,
      confidenceScore: 0.85,
    },
    recommendations: [
      'Continue monitoring for emerging patterns',
      'Review findings with team leads',
    ],
  };
}

export default ChatContext;
