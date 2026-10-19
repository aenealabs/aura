/**
 * Tests for ChatConversationList's per-conversation actions menu
 *
 * - The menu opens from its trigger with menu items for each action
 * - Rename leaves focus in the title field (the field saves on blur, so losing focus would end
 *   the edit at once)
 * - Pin and Delete reach the chat context and the delete confirmation
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import ChatConversationList from './ChatConversationList';
import { useChat } from '../../context/ChatContext';

vi.mock('../../context/ChatContext', () => ({ useChat: vi.fn() }));

const conversation = {
  id: 'c1',
  title: 'Patch rollout plan',
  messages: [{ role: 'user', content: 'Draft a rollout plan' }],
  isPinned: false,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

let chat;

beforeEach(() => {
  chat = {
    conversations: [conversation],
    activeConversationId: null,
    createConversation: vi.fn(),
    selectConversation: vi.fn(),
    deleteConversation: vi.fn(),
    togglePinConversation: vi.fn(),
    renameConversation: vi.fn(),
    exportConversation: vi.fn(),
    searchConversations: vi.fn(() => [conversation]),
    totalTokenUsage: 0,
  };
  useChat.mockReturnValue(chat);
});

async function openMenu(user) {
  await user.click(screen.getByRole('button', { name: 'Actions for Patch rollout plan' }));
  return screen.getByRole('menu');
}

describe('ChatConversationList actions menu', () => {
  test('opens as a menu with an item per action', async () => {
    const user = userEvent.setup();
    render(<ChatConversationList />);
    await openMenu(user);
    expect(screen.getAllByRole('menuitem').map((i) => i.textContent)).toEqual([
      'Rename',
      'Pin to top',
      'Export as Markdown',
      'Delete',
    ]);
  });

  test('Rename keeps focus in the title field so the edit stays open', async () => {
    const user = userEvent.setup();
    render(<ChatConversationList />);
    await openMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Rename' }));

    const field = screen.getByDisplayValue('Patch rollout plan');
    expect(field).toHaveFocus();
    expect(chat.renameConversation).not.toHaveBeenCalled();

    await user.clear(field);
    await user.type(field, 'Rollout plan v2{Enter}');
    expect(chat.renameConversation).toHaveBeenCalledWith('c1', 'Rollout plan v2');
  });

  test('Pin to top pins the conversation and closes the menu', async () => {
    const user = userEvent.setup();
    render(<ChatConversationList />);
    await openMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Pin to top' }));
    expect(chat.togglePinConversation).toHaveBeenCalledWith('c1');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  test('Delete asks for confirmation first', async () => {
    const user = userEvent.setup();
    render(<ChatConversationList />);
    await openMenu(user);
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect(screen.getByText('Delete "Patch rollout plan"?')).toBeInTheDocument();
    expect(chat.deleteConversation).not.toHaveBeenCalled();
  });
});
