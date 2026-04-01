import { useState, useMemo, useCallback } from 'react';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  TrashIcon,
  PencilIcon,
  EllipsisHorizontalIcon,
  MapPinIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  ChatBubbleLeftIcon,
  ArchiveBoxIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { MapPinIcon as MapPinSolidIcon } from '@heroicons/react/24/solid';
import { useChat } from '../../context/ChatContext';

/**
 * ChatConversationList - Sidebar with conversation history and management
 *
 * Design Decisions:
 * - Grouped by time (Today, Yesterday, Last 7 days, Older)
 * - Pinned conversations at top
 * - Search functionality with highlighting
 * - Collapsible groups
 * - Context menu for actions (delete, rename, pin, export)
 * - Delete confirmation dialog
 * - New conversation button
 * - Total token usage display
 * - Keyboard navigation support
 */

export default function ChatConversationList({ onClose }) {
  const {
    conversations,
    activeConversationId,
    createConversation,
    selectConversation,
    deleteConversation,
    togglePinConversation,
    renameConversation,
    exportConversation,
    searchConversations,
    totalTokenUsage,
  } = useChat();

  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [collapsedGroups, setCollapsedGroups] = useState({});
  const [sortBy, setSortBy] = useState('recent'); // 'recent', 'alphabetical', 'oldest'

  // Group conversations by time with search filtering
  const groupedConversations = useMemo(() => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today.getTime() - 86400000);
    const lastWeek = new Date(today.getTime() - 7 * 86400000);

    // Filter by search using context function
    let filtered = searchQuery.trim()
      ? searchConversations(searchQuery)
      : conversations;

    // Sort conversations
    const sorted = [...filtered].sort((a, b) => {
      // Pinned first always
      if (a.isPinned !== b.isPinned) return b.isPinned ? 1 : -1;

      // Then apply selected sort
      switch (sortBy) {
        case 'alphabetical':
          return a.title.localeCompare(b.title);
        case 'oldest':
          return new Date(a.updatedAt) - new Date(b.updatedAt);
        case 'recent':
        default:
          return new Date(b.updatedAt) - new Date(a.updatedAt);
      }
    });

    const groups = {
      pinned: [],
      today: [],
      yesterday: [],
      lastWeek: [],
      older: [],
    };

    sorted.forEach((conv) => {
      if (conv.isPinned) {
        groups.pinned.push(conv);
      } else {
        const date = new Date(conv.updatedAt);
        if (date >= today) {
          groups.today.push(conv);
        } else if (date >= yesterday) {
          groups.yesterday.push(conv);
        } else if (date >= lastWeek) {
          groups.lastWeek.push(conv);
        } else {
          groups.older.push(conv);
        }
      }
    });

    return groups;
  }, [conversations, searchQuery, searchConversations, sortBy]);

  // Toggle group collapse
  const toggleGroup = useCallback((groupName) => {
    setCollapsedGroups(prev => ({
      ...prev,
      [groupName]: !prev[groupName],
    }));
  }, []);

  const handleNewConversation = () => {
    createConversation();
    onClose?.();
  };

  const handleSelectConversation = (id) => {
    selectConversation(id);
    onClose?.();
  };

  const handleStartEdit = (conv) => {
    setEditingId(conv.id);
    setEditTitle(conv.title);
    setMenuOpenId(null);
  };

  const handleSaveEdit = () => {
    if (editingId && editTitle.trim()) {
      renameConversation(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const handleDelete = async (id) => {
    await deleteConversation(id);
    setDeleteConfirmId(null);
    setMenuOpenId(null);
  };

  const handleExport = (id) => {
    const markdown = exportConversation(id);
    if (markdown) {
      const blob = new Blob([markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation-${id}.md`;
      a.click();
      URL.revokeObjectURL(url);
    }
    setMenuOpenId(null);
  };

  // Close menu when clicking outside
  const handleClickOutside = useCallback(() => {
    setMenuOpenId(null);
  }, []);

  const hasConversations = conversations.length > 0;
  const filteredCount = Object.values(groupedConversations).flat().length;

  // Format token count for display
  const formatTokenCount = (count) => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return count.toString();
  };

  return (
    <div
      className="h-full flex flex-col bg-white dark:bg-surface-800"
      onClick={handleClickOutside}
    >
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            Conversations
          </h2>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 lg:hidden"
              aria-label="Close"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* New conversation button */}
        <button
          onClick={handleNewConversation}
          className="
            w-full flex items-center justify-center gap-2
            px-4 py-2.5
            bg-blue-500 hover:bg-blue-600
            text-white font-medium
            rounded-lg
            transition-colors duration-200
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            dark:focus:ring-offset-surface-800
          "
        >
          <PlusIcon className="w-5 h-5" />
          New Conversation
        </button>

        {/* Search and sort */}
        {hasConversations && (
          <div className="mt-3 space-y-2">
            {/* Search input */}
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search conversations..."
                className="
                  w-full pl-9 pr-4 py-2
                  bg-surface-50 dark:bg-surface-700
                  border border-surface-200 dark:border-surface-600
                  rounded-lg
                  text-sm text-surface-900 dark:text-surface-100
                  placeholder-surface-400 dark:placeholder-surface-500
                  focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-transparent
                "
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-surface-400 hover:text-surface-600"
                >
                  <XMarkIcon className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Sort dropdown */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-surface-400 dark:text-surface-500">
                {filteredCount} conversation{filteredCount !== 1 ? 's' : ''}
              </span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="
                  text-xs px-2 py-1
                  bg-surface-50 dark:bg-surface-700
                  border border-surface-200 dark:border-surface-600
                  rounded
                  text-surface-600 dark:text-surface-400
                  focus:outline-none focus:ring-1 focus:ring-olive-500
                "
              >
                <option value="recent">Most Recent</option>
                <option value="alphabetical">A-Z</option>
                <option value="oldest">Oldest First</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto">
        {!hasConversations ? (
          <EmptyState />
        ) : filteredCount === 0 ? (
          <NoResultsState query={searchQuery} onClear={() => setSearchQuery('')} />
        ) : (
          <div className="py-2">
            {/* Pinned */}
            <ConversationGroup
              title="Pinned"
              icon={MapPinSolidIcon}
              conversations={groupedConversations.pinned}
              activeId={activeConversationId}
              editingId={editingId}
              editTitle={editTitle}
              menuOpenId={menuOpenId}
              deleteConfirmId={deleteConfirmId}
              isCollapsed={collapsedGroups.pinned}
              searchQuery={searchQuery}
              onToggleCollapse={() => toggleGroup('pinned')}
              onSelect={handleSelectConversation}
              onStartEdit={handleStartEdit}
              onSaveEdit={handleSaveEdit}
              onEditTitleChange={setEditTitle}
              onCancelEdit={() => setEditingId(null)}
              onToggleMenu={setMenuOpenId}
              onTogglePin={togglePinConversation}
              onDelete={handleDelete}
              onConfirmDelete={setDeleteConfirmId}
              onCancelDelete={() => setDeleteConfirmId(null)}
              onExport={handleExport}
            />

            {/* Today */}
            <ConversationGroup
              title="Today"
              conversations={groupedConversations.today}
              activeId={activeConversationId}
              editingId={editingId}
              editTitle={editTitle}
              menuOpenId={menuOpenId}
              deleteConfirmId={deleteConfirmId}
              isCollapsed={collapsedGroups.today}
              searchQuery={searchQuery}
              onToggleCollapse={() => toggleGroup('today')}
              onSelect={handleSelectConversation}
              onStartEdit={handleStartEdit}
              onSaveEdit={handleSaveEdit}
              onEditTitleChange={setEditTitle}
              onCancelEdit={() => setEditingId(null)}
              onToggleMenu={setMenuOpenId}
              onTogglePin={togglePinConversation}
              onDelete={handleDelete}
              onConfirmDelete={setDeleteConfirmId}
              onCancelDelete={() => setDeleteConfirmId(null)}
              onExport={handleExport}
            />

            {/* Yesterday */}
            <ConversationGroup
              title="Yesterday"
              conversations={groupedConversations.yesterday}
              activeId={activeConversationId}
              editingId={editingId}
              editTitle={editTitle}
              menuOpenId={menuOpenId}
              deleteConfirmId={deleteConfirmId}
              isCollapsed={collapsedGroups.yesterday}
              searchQuery={searchQuery}
              onToggleCollapse={() => toggleGroup('yesterday')}
              onSelect={handleSelectConversation}
              onStartEdit={handleStartEdit}
              onSaveEdit={handleSaveEdit}
              onEditTitleChange={setEditTitle}
              onCancelEdit={() => setEditingId(null)}
              onToggleMenu={setMenuOpenId}
              onTogglePin={togglePinConversation}
              onDelete={handleDelete}
              onConfirmDelete={setDeleteConfirmId}
              onCancelDelete={() => setDeleteConfirmId(null)}
              onExport={handleExport}
            />

            {/* Last 7 days */}
            <ConversationGroup
              title="Last 7 Days"
              conversations={groupedConversations.lastWeek}
              activeId={activeConversationId}
              editingId={editingId}
              editTitle={editTitle}
              menuOpenId={menuOpenId}
              deleteConfirmId={deleteConfirmId}
              isCollapsed={collapsedGroups.lastWeek}
              searchQuery={searchQuery}
              onToggleCollapse={() => toggleGroup('lastWeek')}
              onSelect={handleSelectConversation}
              onStartEdit={handleStartEdit}
              onSaveEdit={handleSaveEdit}
              onEditTitleChange={setEditTitle}
              onCancelEdit={() => setEditingId(null)}
              onToggleMenu={setMenuOpenId}
              onTogglePin={togglePinConversation}
              onDelete={handleDelete}
              onConfirmDelete={setDeleteConfirmId}
              onCancelDelete={() => setDeleteConfirmId(null)}
              onExport={handleExport}
            />

            {/* Older */}
            <ConversationGroup
              title="Older"
              icon={ArchiveBoxIcon}
              conversations={groupedConversations.older}
              activeId={activeConversationId}
              editingId={editingId}
              editTitle={editTitle}
              menuOpenId={menuOpenId}
              deleteConfirmId={deleteConfirmId}
              isCollapsed={collapsedGroups.older}
              searchQuery={searchQuery}
              onToggleCollapse={() => toggleGroup('older')}
              onSelect={handleSelectConversation}
              onStartEdit={handleStartEdit}
              onSaveEdit={handleSaveEdit}
              onEditTitleChange={setEditTitle}
              onCancelEdit={() => setEditingId(null)}
              onToggleMenu={setMenuOpenId}
              onTogglePin={togglePinConversation}
              onDelete={handleDelete}
              onConfirmDelete={setDeleteConfirmId}
              onCancelDelete={() => setDeleteConfirmId(null)}
              onExport={handleExport}
            />
          </div>
        )}
      </div>

      {/* Footer with token usage */}
      {hasConversations && totalTokenUsage && totalTokenUsage.totalTokens > 0 && (
        <div className="flex-shrink-0 px-4 py-3 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-surface-500 dark:text-surface-400">
              <SparklesIcon className="w-4 h-4" />
              <span>Token Usage</span>
            </div>
            <span className="text-surface-600 dark:text-surface-300 font-medium">
              {formatTokenCount(totalTokenUsage.totalTokens)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * EmptyState - Shown when no conversations exist
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-8 text-center">
      <ChatBubbleLeftIcon className="w-12 h-12 text-surface-300 dark:text-surface-600 mb-3" />
      <p className="text-sm text-surface-500 dark:text-surface-400">
        No conversations yet.
      </p>
      <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
        Start a new conversation to get help from Aura.
      </p>
    </div>
  );
}

/**
 * NoResultsState - Shown when search returns no results
 */
function NoResultsState({ query, onClear }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-8 text-center">
      <MagnifyingGlassIcon className="w-12 h-12 text-surface-300 dark:text-surface-600 mb-3" />
      <p className="text-sm text-surface-500 dark:text-surface-400">
        No results for "{query}"
      </p>
      <button
        onClick={onClear}
        className="mt-2 text-xs text-olive-500 hover:text-olive-600 dark:text-olive-400"
      >
        Clear search
      </button>
    </div>
  );
}

/**
 * ConversationGroup - Group of conversations with collapsible header
 */
function ConversationGroup({
  title,
  icon: Icon,
  conversations,
  activeId,
  editingId,
  editTitle,
  menuOpenId,
  deleteConfirmId,
  isCollapsed,
  searchQuery,
  onToggleCollapse,
  onSelect,
  onStartEdit,
  onSaveEdit,
  onEditTitleChange,
  onCancelEdit,
  onToggleMenu,
  onTogglePin,
  onDelete,
  onConfirmDelete,
  onCancelDelete,
  onExport,
}) {
  if (conversations.length === 0) return null;

  const ChevronIcon = isCollapsed ? ChevronRightIcon : ChevronDownIcon;

  return (
    <div className="mb-2">
      <button
        onClick={onToggleCollapse}
        className="w-full px-4 py-2 flex items-center gap-2 text-xs font-semibold text-surface-400 dark:text-surface-500 uppercase tracking-wider hover:bg-surface-50 dark:hover:bg-surface-700/50"
      >
        <ChevronIcon className="w-3 h-3" />
        {Icon && <Icon className="w-3.5 h-3.5" />}
        <span>{title}</span>
        <span className="ml-auto text-surface-300 dark:text-surface-600 font-normal normal-case">
          {conversations.length}
        </span>
      </button>

      {!isCollapsed && (
        <div className="space-y-0.5">
          {conversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isActive={conv.id === activeId}
              isEditing={conv.id === editingId}
              editTitle={editTitle}
              isMenuOpen={conv.id === menuOpenId}
              isDeleteConfirm={conv.id === deleteConfirmId}
              searchQuery={searchQuery}
              onSelect={() => onSelect(conv.id)}
              onStartEdit={() => onStartEdit(conv)}
              onSaveEdit={onSaveEdit}
              onEditTitleChange={onEditTitleChange}
              onCancelEdit={onCancelEdit}
              onToggleMenu={() => onToggleMenu(conv.id === menuOpenId ? null : conv.id)}
              onTogglePin={() => onTogglePin(conv.id)}
              onDelete={() => onDelete(conv.id)}
              onConfirmDelete={() => onConfirmDelete(conv.id)}
              onCancelDelete={onCancelDelete}
              onExport={() => onExport(conv.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * ConversationItem - Single conversation in list
 */
function ConversationItem({
  conversation,
  isActive,
  isEditing,
  editTitle,
  isMenuOpen,
  isDeleteConfirm,
  searchQuery,
  onSelect,
  onStartEdit,
  onSaveEdit,
  onEditTitleChange,
  onCancelEdit,
  onToggleMenu,
  onTogglePin,
  onDelete,
  onConfirmDelete,
  onCancelDelete,
  onExport,
}) {
  const lastMessage = conversation.messages[conversation.messages.length - 1];
  const preview = lastMessage?.content?.slice(0, 50) || 'No messages yet';
  const messageCount = conversation.messages.length;

  // Highlight search terms in title
  const highlightedTitle = useMemo(() => {
    if (!searchQuery.trim()) return conversation.title;

    const regex = new RegExp(`(${searchQuery.trim()})`, 'gi');
    const parts = conversation.title.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-olive-200 dark:bg-olive-900/50 text-inherit">
          {part}
        </mark>
      ) : (
        part
      )
    );
  }, [conversation.title, searchQuery]);

  if (isDeleteConfirm) {
    return (
      <div className="mx-2 p-3 bg-critical-50 dark:bg-critical-900/20 rounded-lg border border-critical-200 dark:border-critical-800">
        <p className="text-sm text-critical-700 dark:text-critical-300 mb-3">
          Delete "{conversation.title}"?
        </p>
        <p className="text-xs text-critical-600 dark:text-critical-400 mb-3">
          This will permanently delete {messageCount} message{messageCount !== 1 ? 's' : ''}.
        </p>
        <div className="flex gap-2">
          <button
            onClick={onDelete}
            className="flex-1 px-3 py-1.5 bg-critical-500 hover:bg-critical-600 text-white text-sm font-medium rounded-md transition-colors"
          >
            Delete
          </button>
          <button
            onClick={onCancelDelete}
            className="flex-1 px-3 py-1.5 bg-surface-200 dark:bg-surface-700 hover:bg-surface-300 dark:hover:bg-surface-600 text-surface-700 dark:text-surface-300 text-sm font-medium rounded-md transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative group px-2" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={onSelect}
        className={`
          w-full text-left p-3 rounded-lg
          transition-colors duration-150
          ${isActive
            ? 'bg-olive-100 dark:bg-olive-900/30'
            : 'hover:bg-surface-100 dark:hover:bg-surface-700'
          }
        `}
      >
        <div className="flex items-start gap-2">
          {/* Pin indicator */}
          {conversation.isPinned && (
            <MapPinSolidIcon className="w-4 h-4 text-olive-500 flex-shrink-0 mt-0.5" />
          )}

          <div className="flex-1 min-w-0">
            {isEditing ? (
              <input
                type="text"
                value={editTitle}
                onChange={(e) => onEditTitleChange(e.target.value)}
                onBlur={onSaveEdit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSaveEdit();
                  if (e.key === 'Escape') onCancelEdit();
                }}
                autoFocus
                className="
                  w-full px-2 py-1 -ml-2
                  bg-white dark:bg-surface-700
                  border border-olive-500
                  rounded text-sm
                  text-surface-900 dark:text-surface-100
                  focus:outline-none focus:ring-2 focus:ring-olive-500
                "
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <h4
                className={`
                  text-sm font-medium truncate
                  ${isActive
                    ? 'text-olive-700 dark:text-olive-300'
                    : 'text-surface-900 dark:text-surface-100'
                  }
                `}
              >
                {highlightedTitle}
              </h4>
            )}
            <p className="text-xs text-surface-500 dark:text-surface-400 truncate mt-0.5">
              {preview}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-surface-400 dark:text-surface-500">
                {messageCount} msg{messageCount !== 1 ? 's' : ''}
              </span>
              <span className="text-xs text-surface-300 dark:text-surface-600">
                {formatRelativeDate(conversation.updatedAt)}
              </span>
            </div>
          </div>
        </div>
      </button>

      {/* Menu button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggleMenu();
        }}
        className={`
          absolute right-3 top-1/2 -translate-y-1/2
          p-1 rounded
          text-surface-400 dark:text-surface-500
          hover:text-surface-600 dark:hover:text-surface-300
          hover:bg-surface-200 dark:hover:bg-surface-600
          opacity-0 group-hover:opacity-100
          transition-opacity duration-150
          ${isMenuOpen ? 'opacity-100' : ''}
        `}
      >
        <EllipsisHorizontalIcon className="w-5 h-5" />
      </button>

      {/* Dropdown menu */}
      {isMenuOpen && (
        <div
          className="
            absolute right-2 top-full mt-1 z-10
            w-44 py-1
            bg-white dark:bg-surface-700
            border border-surface-200 dark:border-surface-600
            rounded-lg shadow-lg
          "
          onClick={(e) => e.stopPropagation()}
        >
          <MenuButton icon={PencilIcon} onClick={onStartEdit}>
            Rename
          </MenuButton>
          <MenuButton
            icon={conversation.isPinned ? MapPinSolidIcon : MapPinIcon}
            onClick={onTogglePin}
          >
            {conversation.isPinned ? 'Unpin' : 'Pin to top'}
          </MenuButton>
          <MenuButton icon={ArrowDownTrayIcon} onClick={onExport}>
            Export as Markdown
          </MenuButton>
          <div className="border-t border-surface-200 dark:border-surface-600 my-1" />
          <MenuButton
            icon={TrashIcon}
            onClick={onConfirmDelete}
            variant="danger"
          >
            Delete
          </MenuButton>
        </div>
      )}
    </div>
  );
}

/**
 * MenuButton - Dropdown menu item
 */
function MenuButton({ icon: Icon, children, onClick, variant = 'default' }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`
        w-full flex items-center gap-2 px-3 py-2
        text-sm
        transition-colors duration-150
        ${variant === 'danger'
          ? 'text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20'
          : 'text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-600'
        }
      `}
    >
      <Icon className="w-4 h-4" />
      {children}
    </button>
  );
}

/**
 * Format relative date for display
 */
function formatRelativeDate(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m`;
  if (hours < 24) return `${hours}h`;
  if (days < 7) return `${days}d`;

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
