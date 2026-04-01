import {
  ShieldExclamationIcon,
  CpuChipIcon,
  DocumentChartBarIcon,
  Cog6ToothIcon,
  QuestionMarkCircleIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline';

/**
 * ChatSuggestedPrompt - Clickable prompt cards for quick actions
 *
 * Design Decisions:
 * - Card-based layout with icon and text
 * - Hover animation with subtle lift
 * - Aura blue accent on hover
 * - Context-aware prompts based on current page
 */

// Default suggested prompts
const defaultPrompts = [
  {
    id: 'vulnerabilities',
    icon: ShieldExclamationIcon,
    title: "Show today's vulnerabilities",
    description: 'View critical and high severity issues',
    prompt: "Show me today's vulnerabilities",
  },
  {
    id: 'agents',
    icon: CpuChipIcon,
    title: 'Check agent status',
    description: 'See what agents are currently running',
    prompt: 'What agents are currently running?',
  },
  {
    id: 'report',
    icon: DocumentChartBarIcon,
    title: 'Generate security report',
    description: 'Create a weekly security summary',
    prompt: 'Generate a weekly security report',
  },
  {
    id: 'hitl',
    icon: ClipboardDocumentListIcon,
    title: 'Review pending approvals',
    description: 'Check HITL approval queue',
    prompt: 'Explain the HITL approval workflow',
  },
  {
    id: 'sandbox',
    icon: Cog6ToothIcon,
    title: 'Sandbox configuration',
    description: 'Configure sandbox test settings',
    prompt: 'How do I configure sandbox settings?',
  },
  {
    id: 'help',
    icon: QuestionMarkCircleIcon,
    title: 'Get help',
    description: 'Learn about platform features',
    prompt: 'What can you help me with?',
  },
];

// Context-specific prompts
const contextPrompts = {
  dashboard: [
    {
      id: 'explain-metrics',
      icon: DocumentChartBarIcon,
      title: 'Explain these metrics',
      description: 'Understand dashboard data',
      prompt: 'Explain the metrics shown on my dashboard',
    },
    {
      id: 'recent-activity',
      icon: ClipboardDocumentListIcon,
      title: 'Summarize recent activity',
      description: 'Get activity overview',
      prompt: 'Summarize the recent security activity',
    },
  ],
  approvals: [
    {
      id: 'pending-details',
      icon: ClipboardDocumentListIcon,
      title: 'Show pending approval details',
      description: 'View what needs review',
      prompt: 'Show me details on pending approvals',
    },
    {
      id: 'approval-workflow',
      icon: QuestionMarkCircleIcon,
      title: 'How does approval work?',
      description: 'Understand the process',
      prompt: 'How does the patch approval workflow work?',
    },
  ],
  incidents: [
    {
      id: 'summarize-incidents',
      icon: ShieldExclamationIcon,
      title: 'Summarize open incidents',
      description: 'Get incident overview',
      prompt: 'Summarize all open incidents',
    },
    {
      id: 'incident-priority',
      icon: DocumentChartBarIcon,
      title: 'What needs attention first?',
      description: 'Prioritized incident list',
      prompt: 'Which incidents need immediate attention?',
    },
  ],
};

export default function ChatSuggestedPrompt({
  prompt,
  onClick,
  size = 'default',
}) {
  const { icon: Icon, title, description } = prompt;

  const sizeClasses = {
    default: 'p-4',
    compact: 'p-3',
  };

  return (
    <button
      onClick={() => onClick(prompt.prompt)}
      className={`
        w-full text-left
        bg-white dark:bg-surface-800
        border border-surface-200 dark:border-surface-700
        rounded-xl
        shadow-card hover:shadow-card-hover
        transition-all duration-200 ease-smooth
        hover:-translate-y-0.5
        hover:border-blue-300 dark:hover:border-blue-600
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        dark:focus:ring-offset-surface-900
        group
        ${sizeClasses[size]}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className="
            flex-shrink-0 p-2 rounded-lg
            bg-surface-100 dark:bg-surface-700
            group-hover:bg-blue-100 dark:group-hover:bg-blue-900/30
            transition-colors duration-200
          "
        >
          <Icon
            className="
              w-5 h-5
              text-surface-500 dark:text-surface-400
              group-hover:text-blue-600 dark:group-hover:text-blue-400
              transition-colors duration-200
            "
          />
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <h4
            className="
              text-sm font-medium
              text-surface-900 dark:text-surface-100
              group-hover:text-blue-700 dark:group-hover:text-blue-300
              transition-colors duration-200
              truncate
            "
          >
            {title}
          </h4>
          {size === 'default' && description && (
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5 truncate">
              {description}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

/**
 * ChatSuggestedPromptGrid - Grid of suggested prompts
 */
export function ChatSuggestedPromptGrid({
  context = null,
  onSelectPrompt,
  maxItems = 6,
  columns = 2,
}) {
  // Get context-specific prompts or use defaults
  const prompts = context && contextPrompts[context]
    ? [...contextPrompts[context], ...defaultPrompts].slice(0, maxItems)
    : defaultPrompts.slice(0, maxItems);

  const gridCols = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  };

  return (
    <div className={`grid gap-3 ${gridCols[columns] || gridCols[2]}`}>
      {prompts.map((prompt) => (
        <ChatSuggestedPrompt
          key={prompt.id}
          prompt={prompt}
          onClick={onSelectPrompt}
          size="compact"
        />
      ))}
    </div>
  );
}

/**
 * ChatQuickFilters - Horizontal filter chips for quick filtering
 */
export function ChatQuickFilters({ onSelect }) {
  const filters = [
    { id: 'metrics', label: 'Metrics', icon: DocumentChartBarIcon },
    { id: 'docs', label: 'Docs', icon: QuestionMarkCircleIcon },
    { id: 'config', label: 'Config', icon: Cog6ToothIcon },
    { id: 'reports', label: 'Reports', icon: ClipboardDocumentListIcon },
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {filters.map((filter) => {
        const Icon = filter.icon;
        return (
          <button
            key={filter.id}
            onClick={() => onSelect(filter.id)}
            className="
              inline-flex items-center gap-1.5
              px-3 py-1.5
              bg-surface-100 dark:bg-surface-700
              hover:bg-blue-100 dark:hover:bg-blue-900/30
              text-surface-600 dark:text-surface-400
              hover:text-blue-700 dark:hover:text-blue-300
              rounded-full
              text-sm font-medium
              transition-colors duration-150
              focus:outline-none focus:ring-2 focus:ring-blue-500
            "
          >
            <Icon className="w-4 h-4" />
            {filter.label}
          </button>
        );
      })}
    </div>
  );
}

export { defaultPrompts, contextPrompts };
