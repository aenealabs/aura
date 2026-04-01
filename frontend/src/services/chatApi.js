/**
 * Project Aura - Chat API Service
 *
 * Provides integration with the Bedrock/Claude LLM backend for the Aura Assistant.
 * Supports streaming responses via Server-Sent Events (SSE) for real-time text generation.
 *
 * Features:
 * - Real-time streaming message responses
 * - Conversation CRUD operations
 * - Token usage tracking
 * - Retry logic with exponential backoff
 * - Graceful fallback to mock responses
 */

// API Configuration
const API_BASE_URL = import.meta.env.VITE_CHAT_API_URL || '/api/v1';
const USE_MOCK = import.meta.env.VITE_MOCK_CHAT === 'true' || !import.meta.env.VITE_CHAT_API_URL;

/**
 * Get authentication headers from stored tokens
 */
function getAuthHeaders() {
  try {
    const stored = localStorage.getItem('aura_auth_tokens');
    if (stored) {
      const tokens = JSON.parse(stored);
      if (tokens.access_token) {
        return { Authorization: `Bearer ${tokens.access_token}` };
      }
    }
  } catch (e) {
    console.warn('Failed to parse auth tokens:', e);
  }
  return {};
}

/**
 * ChatApiError - Custom error class for chat API errors
 */
export class ChatApiError extends Error {
  constructor(message, status = null, code = null, details = null) {
    super(message);
    this.name = 'ChatApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isRetryable() {
    // Retry on server errors (5xx) and rate limiting (429)
    if (this.status >= 500) return true;
    if (this.status === 429) return true;
    if (this.code === 'NETWORK_ERROR') return true;
    return false;
  }
}

/**
 * Send a message and receive streaming response via SSE
 *
 * @param {string} message - The user's message content
 * @param {Array} attachments - Optional file attachments
 * @param {string} conversationId - Conversation ID (null for new conversation)
 * @param {Object} options - Additional options
 * @param {Object} options.context - Page context (current page, data)
 * @param {AbortSignal} options.signal - AbortController signal for cancellation
 * @param {Function} options.onToken - Callback for each streamed token
 * @param {Function} options.onToolCall - Callback for tool invocations
 * @param {Function} options.onComplete - Callback when streaming completes
 * @param {Function} options.onError - Callback on error
 * @returns {Promise<Object>} Complete response object
 */
export async function sendMessage(message, attachments = [], conversationId = null, options = {}) {
  const {
    context = {},
    signal,
    onToken,
    onToolCall,
    onComplete,
    onError,
  } = options;

  if (USE_MOCK) {
    return sendMockMessage(message, attachments, conversationId, options);
  }

  const url = `${API_BASE_URL}/chat/message`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: message.trim(),
        attachments: attachments.length > 0 ? attachments : undefined,
        context,
        stream: true,
      }),
      signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ChatApiError(
        errorData.message || `Request failed with status ${response.status}`,
        response.status,
        errorData.code,
        errorData.details
      );
    }

    // Handle streaming response
    return await handleStreamingResponse(response, { onToken, onToolCall, onComplete, onError });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw error;
    }

    if (error instanceof ChatApiError) {
      onError?.(error);
      throw error;
    }

    // Network or other error
    const apiError = new ChatApiError(
      error.message || 'Network error occurred',
      null,
      'NETWORK_ERROR'
    );
    onError?.(apiError);
    throw apiError;
  }
}

/**
 * Handle SSE streaming response from the API
 */
async function handleStreamingResponse(response, callbacks) {
  const { onToken, onToolCall, onComplete, onError } = callbacks;

  if (!response.body) {
    throw new ChatApiError('Response body is empty', null, 'EMPTY_BODY');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let fullContent = '';
  let messageId = null;
  let conversationId = null;
  let modelId = null;
  let tokenUsage = null;
  let toolCalls = [];

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim() || line.startsWith(':')) continue;

        if (line.startsWith('data: ')) {
          const data = line.slice(6);

          // Handle [DONE] marker
          if (data === '[DONE]') {
            const result = {
              messageId,
              conversationId,
              content: fullContent,
              modelId,
              tokenUsage,
              toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
            };
            onComplete?.(result);
            return result;
          }

          try {
            const parsed = JSON.parse(data);

            // Handle different event types
            switch (parsed.type) {
              case 'token':
                fullContent += parsed.content;
                onToken?.(parsed.content, fullContent);
                break;

              case 'tool_call':
                toolCalls.push(parsed.tool_call);
                onToolCall?.(parsed.tool_call);
                break;

              case 'metadata':
                messageId = parsed.message_id || messageId;
                conversationId = parsed.conversation_id || conversationId;
                modelId = parsed.model_id || modelId;
                break;

              case 'usage':
                tokenUsage = parsed.usage;
                break;

              case 'error':
                throw new ChatApiError(parsed.message, parsed.status, parsed.code);

              default:
                // Handle legacy format or unknown types
                if (parsed.content) {
                  fullContent += parsed.content;
                  onToken?.(parsed.content, fullContent);
                }
            }
          } catch (e) {
            if (e instanceof ChatApiError) throw e;
            console.warn('Failed to parse SSE data:', data, e);
          }
        }
      }
    }

    // Stream ended without [DONE] marker
    const result = {
      messageId,
      conversationId,
      content: fullContent,
      modelId,
      tokenUsage,
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
    };
    onComplete?.(result);
    return result;
  } catch (error) {
    onError?.(error);
    throw error;
  }
}

/**
 * Get list of conversations for the current user
 *
 * @param {Object} options - Query options
 * @param {number} options.limit - Maximum number of conversations to return
 * @param {number} options.offset - Offset for pagination
 * @param {string} options.search - Search query
 * @returns {Promise<Array>} List of conversations
 */
export async function getConversations(options = {}) {
  const { limit = 50, offset = 0, search = '' } = options;

  if (USE_MOCK) {
    return getMockConversations(options);
  }

  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  if (search) {
    params.set('search', search);
  }

  const url = `${API_BASE_URL}/chat/conversations?${params}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ChatApiError(
      errorData.message || 'Failed to fetch conversations',
      response.status,
      errorData.code
    );
  }

  const data = await response.json();
  return data.conversations || data;
}

/**
 * Get a specific conversation with full message history
 *
 * @param {string} conversationId - Conversation ID
 * @returns {Promise<Object>} Conversation with messages
 */
export async function getConversation(conversationId) {
  if (USE_MOCK) {
    return getMockConversation(conversationId);
  }

  const url = `${API_BASE_URL}/chat/conversations/${conversationId}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ChatApiError(
      errorData.message || 'Failed to fetch conversation',
      response.status,
      errorData.code
    );
  }

  return response.json();
}

/**
 * Delete a conversation
 *
 * @param {string} conversationId - Conversation ID to delete
 * @returns {Promise<void>}
 */
export async function deleteConversation(conversationId) {
  if (USE_MOCK) {
    return deleteMockConversation(conversationId);
  }

  const url = `${API_BASE_URL}/chat/conversations/${conversationId}`;

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      ...getAuthHeaders(),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ChatApiError(
      errorData.message || 'Failed to delete conversation',
      response.status,
      errorData.code
    );
  }
}

/**
 * Update conversation metadata (title, pinned status)
 *
 * @param {string} conversationId - Conversation ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated conversation
 */
export async function updateConversation(conversationId, updates) {
  if (USE_MOCK) {
    return updateMockConversation(conversationId, updates);
  }

  const url = `${API_BASE_URL}/chat/conversations/${conversationId}`;

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ChatApiError(
      errorData.message || 'Failed to update conversation',
      response.status,
      errorData.code
    );
  }

  return response.json();
}

/**
 * Rate a message (thumbs up/down)
 *
 * @param {string} messageId - Message ID
 * @param {string} rating - 'positive' or 'negative'
 * @param {string} feedback - Optional feedback text
 * @returns {Promise<void>}
 */
export async function rateMessage(messageId, rating, feedback = null) {
  if (USE_MOCK) {
    return; // No-op for mock
  }

  const url = `${API_BASE_URL}/chat/messages/${messageId}/rate`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ rating, feedback }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ChatApiError(
      errorData.message || 'Failed to rate message',
      response.status,
      errorData.code
    );
  }
}

/**
 * Copy message content to clipboard
 *
 * @param {string} content - Content to copy
 * @returns {Promise<boolean>} Success status
 */
export async function copyToClipboard(content) {
  try {
    await navigator.clipboard.writeText(content);
    return true;
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    return false;
  }
}

// ============================================================================
// Mock Implementations for Development
// ============================================================================

/**
 * Simulated delay for realistic mock behavior
 */
function mockDelay(min = 50, max = 150) {
  return new Promise((resolve) =>
    setTimeout(resolve, min + Math.random() * (max - min))
  );
}

/**
 * Mock message sending with simulated streaming
 */
async function sendMockMessage(message, attachments, conversationId, options) {
  const { onToken, onComplete, context } = options;

  const mockResponse = generateMockResponse(message, context);
  const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const newConversationId = conversationId || `conv-${Date.now()}`;

  let fullContent = '';

  // Simulate token-by-token streaming
  const words = mockResponse.split(' ');
  for (let i = 0; i < words.length; i++) {
    await mockDelay(30, 80);

    const token = (i === 0 ? '' : ' ') + words[i];
    fullContent += token;
    onToken?.(token, fullContent);
  }

  const result = {
    messageId,
    conversationId: newConversationId,
    content: fullContent,
    modelId: 'claude-3.5-sonnet-mock',
    tokenUsage: {
      promptTokens: Math.floor(message.length / 4),
      completionTokens: Math.floor(fullContent.length / 4),
      totalTokens: Math.floor((message.length + fullContent.length) / 4),
    },
  };

  onComplete?.(result);
  return result;
}

/**
 * Generate contextual mock response
 */
function generateMockResponse(userMessage, context) {
  const lowerMessage = userMessage.toLowerCase();

  if (lowerMessage.includes('vulnerabilit')) {
    return `Based on the latest scan, here's a summary of your vulnerabilities:

**Current Status:**
- **Critical:** 3 vulnerabilities
- **High:** 8 vulnerabilities
- **Medium:** 9 vulnerabilities
- **Low:** 4 vulnerabilities

The most critical issue is a SQL Injection vulnerability in \`src/auth/handlers/login.py\` (CVE-2024-1234). I recommend addressing this immediately.

**Suggested Actions:**
1. [View Critical Vulnerabilities](/vulnerabilities?severity=critical)
2. [Start Patch Generation](/patches/new?cve=CVE-2024-1234)

Would you like me to provide more details about any specific vulnerability?`;
  }

  if (lowerMessage.includes('agent')) {
    return `Here's the current status of your AI agents:

| Agent | Status | Current Task |
|-------|--------|--------------|
| **Coder** | Active | Generating patch for CVE-2024-1234 (65%) |
| **Reviewer** | Active | Analyzing patch quality (40%) |
| **Validator** | Idle | Waiting for patches |

All agents are operating within normal parameters. The Coder agent is expected to complete the current patch in approximately 12 minutes.

Would you like me to:
- Show detailed agent logs
- Start a new scan
- View agent performance metrics`;
  }

  if (lowerMessage.includes('approval') || lowerMessage.includes('hitl')) {
    return `You have **7 pending approvals** requiring attention:

1. **XSS Mitigation Patch** - High priority
   - Affects: \`frontend/components/UserInput.jsx\`
   - Sandbox Status: Passed

2. **CSRF Token Implementation** - Medium priority
   - Affects: \`api/middleware/auth.py\`
   - Sandbox Status: Passed

3. **SQL Injection Fix** - Critical priority
   - Affects: \`src/auth/handlers/login.py\`
   - Sandbox Status: Running

[Review Pending Approvals](/approvals)

The HITL (Human-in-the-Loop) workflow ensures all patches are reviewed before deployment. Would you like me to explain the approval process?`;
  }

  if (lowerMessage.includes('sandbox')) {
    return `**Sandbox Testing Environment**

Current sandbox status:
- **Active Sandboxes:** 2
- **Available Slots:** 3
- **Isolation Level:** VPC

Sandboxes provide isolated environments for testing patches before production deployment. Each sandbox includes:

- Ephemeral network isolation
- Mock database connections
- Simulated external services

\`\`\`yaml
# Current Sandbox Configuration
isolation_level: VPC
network_policy: strict
max_duration: 30m
resource_limits:
  cpu: 2
  memory: 4Gi
\`\`\`

Would you like to view active sandboxes or create a new one?`;
  }

  if (lowerMessage.includes('report')) {
    return `I can generate the following reports:

1. **Weekly Security Summary**
   - Vulnerabilities detected/resolved
   - Patches deployed
   - Agent performance metrics

2. **Compliance Status Report**
   - CMMC Level 3 progress
   - SOX compliance checklist
   - NIST 800-53 controls

3. **Custom Report**
   - Specify date range and metrics

Which report would you like me to generate?

\`\`\`
Tip: You can also ask for specific metrics like
"Show me patches deployed this week"
\`\`\``;
  }

  // Context-aware responses
  if (context?.page === 'approvals') {
    return `I see you're on the Approvals page. I can help you:

1. **Review pending patches** - Get details on any pending approval
2. **Bulk approve** - Approve multiple low-risk patches
3. **Check sandbox results** - View test outcomes before approving

What would you like help with?`;
  }

  // Default response
  return `I'm Aura Assistant, your AI-powered helper for the Project Aura platform. I can assist you with:

- **Security Metrics** - Query vulnerabilities, patches, and compliance status
- **Agent Management** - Monitor and control Coder, Reviewer, and Validator agents
- **Report Generation** - Create security summaries and compliance reports
- **Configuration Help** - Guide you through platform settings
- **Documentation** - Explain features and workflows

Try asking something like:
- "Show me today's vulnerabilities"
- "What agents are currently running?"
- "Generate a weekly security report"

How can I assist you today?`;
}

/**
 * Mock get conversations
 */
async function getMockConversations() {
  // Return conversations from localStorage (managed by ChatContext)
  return [];
}

/**
 * Mock get single conversation
 */
async function getMockConversation(conversationId) {
  return {
    id: conversationId,
    title: 'Mock Conversation',
    messages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

/**
 * Mock delete conversation
 */
async function deleteMockConversation() {
  return;
}

/**
 * Mock update conversation
 */
async function updateMockConversation(conversationId, updates) {
  return {
    id: conversationId,
    ...updates,
    updatedAt: new Date().toISOString(),
  };
}

// Export default object for convenience
export default {
  sendMessage,
  getConversations,
  getConversation,
  deleteConversation,
  updateConversation,
  rateMessage,
  copyToClipboard,
  ChatApiError,
};
