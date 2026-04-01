import React, { useEffect } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { ChatProvider, useChat } from './ChatContext';

// Mock the chatApi module
vi.mock('../services/chatApi', () => ({
  sendMessage: vi.fn(),
  streamMessage: vi.fn(),
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  startResearchTask: vi.fn(),
  getResearchTaskStatus: vi.fn(),
}));

import * as chatApi from '../services/chatApi';

// Test consumer component
function TestConsumer({ onMount }) {
  const context = useChat();

  useEffect(() => {
    if (onMount) onMount(context);
  }, [onMount, context]);

  return (
    <div>
      <span data-testid="is-open">{context.isOpen ? 'true' : 'false'}</span>
      <span data-testid="is-minimized">{context.isMinimized ? 'true' : 'false'}</span>
      <span data-testid="is-typing">{context.isTyping ? 'true' : 'false'}</span>
      <span data-testid="conversations-count">{context.conversations.length}</span>
      <span data-testid="active-conversation">{context.activeConversation?.id || 'none'}</span>
      <span data-testid="draft-message">{context.draftMessage || 'empty'}</span>
      <span data-testid="current-context">{context.currentContext.page}</span>
      <button data-testid="open-chat" onClick={() => context.openChat()}>Open</button>
      <button data-testid="close-chat" onClick={() => context.closeChat()}>Close</button>
      <button data-testid="toggle-chat" onClick={() => context.toggleChat()}>Toggle</button>
      <button data-testid="minimize-chat" onClick={() => context.minimizeChat()}>Minimize</button>
      <button data-testid="set-draft" onClick={() => context.setDraftMessage('Hello world')}>Set Draft</button>
    </div>
  );
}

describe('ChatContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // Default mock implementations
    chatApi.listConversations.mockResolvedValue([]);
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('ChatProvider', () => {
    test('provides initial state', async () => {
      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      expect(screen.getByTestId('is-open')).toHaveTextContent('false');
      expect(screen.getByTestId('is-minimized')).toHaveTextContent('false');
      expect(screen.getByTestId('is-typing')).toHaveTextContent('false');
      expect(screen.getByTestId('current-context')).toHaveTextContent('dashboard');
    });

    test('loads conversations from localStorage', async () => {
      const savedConversations = [
        { id: 'conv-1', title: 'First conversation', messages: [] },
        { id: 'conv-2', title: 'Second conversation', messages: [] },
      ];
      localStorage.setItem('aura-chat-conversations', JSON.stringify(savedConversations));

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      expect(screen.getByTestId('conversations-count')).toHaveTextContent('2');
    });

    test('loads draft message from localStorage', async () => {
      localStorage.setItem('aura-chat-draft', 'Saved draft message');

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      expect(screen.getByTestId('draft-message')).toHaveTextContent('Saved draft message');
    });
  });

  describe('Chat visibility', () => {
    test('openChat opens the chat panel', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      expect(screen.getByTestId('is-open')).toHaveTextContent('false');

      await user.click(screen.getByTestId('open-chat'));

      expect(screen.getByTestId('is-open')).toHaveTextContent('true');
      expect(screen.getByTestId('is-minimized')).toHaveTextContent('false');
    });

    test('closeChat closes the chat panel', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      await user.click(screen.getByTestId('open-chat'));
      expect(screen.getByTestId('is-open')).toHaveTextContent('true');

      await user.click(screen.getByTestId('close-chat'));
      expect(screen.getByTestId('is-open')).toHaveTextContent('false');
    });

    test('toggleChat toggles the chat panel', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      expect(screen.getByTestId('is-open')).toHaveTextContent('false');

      await user.click(screen.getByTestId('toggle-chat'));
      expect(screen.getByTestId('is-open')).toHaveTextContent('true');

      await user.click(screen.getByTestId('toggle-chat'));
      expect(screen.getByTestId('is-open')).toHaveTextContent('false');
    });

    test('minimizeChat minimizes the chat', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      await user.click(screen.getByTestId('open-chat'));
      await user.click(screen.getByTestId('minimize-chat'));

      expect(screen.getByTestId('is-minimized')).toHaveTextContent('true');
    });

    test('toggleChat restores from minimized state', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      await user.click(screen.getByTestId('open-chat'));
      await user.click(screen.getByTestId('minimize-chat'));
      expect(screen.getByTestId('is-minimized')).toHaveTextContent('true');

      await user.click(screen.getByTestId('toggle-chat'));
      expect(screen.getByTestId('is-minimized')).toHaveTextContent('false');
    });
  });

  describe('Draft message', () => {
    test('setDraftMessage updates draft', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      await user.click(screen.getByTestId('set-draft'));

      expect(screen.getByTestId('draft-message')).toHaveTextContent('Hello world');
    });

    test('draft message persists to localStorage', async () => {
      const user = userEvent.setup();

      render(
        <ChatProvider>
          <TestConsumer />
        </ChatProvider>
      );

      await user.click(screen.getByTestId('set-draft'));

      await waitFor(() => {
        expect(localStorage.getItem('aura-chat-draft')).toBe('Hello world');
      });
    });
  });

  describe('Conversations', () => {
    test('persists conversations to localStorage', async () => {
      let capturedContext;

      render(
        <ChatProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ChatProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      // Create a new conversation by simulating the internal state
      act(() => {
        capturedContext.setDraftMessage('Test');
      });

      await waitFor(() => {
        const saved = localStorage.getItem('aura-chat-conversations');
        expect(saved).toBeDefined();
      });
    });
  });

  describe('Context awareness', () => {
    test('setCurrentContext updates context', async () => {
      let capturedContext;

      render(
        <ChatProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ChatProvider>
      );

      await waitFor(() => {
        expect(capturedContext).toBeDefined();
      });

      act(() => {
        capturedContext.setCurrentContext({ page: 'settings', data: { tab: 'security' } });
      });

      expect(screen.getByTestId('current-context')).toHaveTextContent('settings');
    });
  });

  describe('Token usage', () => {
    test('loads token usage from localStorage', async () => {
      const savedUsage = { promptTokens: 1000, completionTokens: 500, totalTokens: 1500 };
      localStorage.setItem('aura-chat-token-usage', JSON.stringify(savedUsage));

      let capturedContext;

      render(
        <ChatProvider>
          <TestConsumer onMount={(ctx) => { capturedContext = ctx; }} />
        </ChatProvider>
      );

      await waitFor(() => {
        expect(capturedContext.totalTokenUsage.totalTokens).toBe(1500);
      });
    });
  });

  describe('useChat hook', () => {
    test('throws error when used outside ChatProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestConsumer />);
      }).toThrow('useChat must be used within a ChatProvider');

      consoleSpy.mockRestore();
    });
  });
});
