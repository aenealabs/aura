// Project Aura UI Component Library
// Export all reusable UI components from a single entry point
//
// Issue: #20 - Frontend production polish

// Loading States
export {
  default as Skeleton,
  SkeletonText,
  SkeletonCircle,
  MetricCardSkeleton,
  ChartSkeleton,
  ActivityItemSkeleton,
  ActivityFeedSkeleton,
  TableRowSkeleton,
  TableSkeleton,
  PageSkeleton,
} from './LoadingSkeleton';

// Error Handling
export {
  ErrorBoundary,
  ErrorFallback,
  ErrorFallbackCompact,
  ErrorFallbackFullPage,
  InlineError,
  PageError,
} from './ErrorBoundary';

// Toast Notifications
export {
  ToastProvider,
  useToast,
  showApiError,
} from './Toast';

// Confirmation Dialogs
export {
  ConfirmProvider,
  useConfirm,
  StandaloneConfirmDialog,
} from './ConfirmDialog';

// Buttons
export {
  Button,
  IconButton,
  ButtonGroup,
} from './Button';

// Form Elements
export {
  FormField,
  Input,
  Textarea,
  Select,
  Checkbox,
  Radio,
  validators,
  composeValidators,
} from './FormElements';

// Metric Cards
export {
  default as MetricCard,
  MetricCardCompact,
  MetricCardGrid,
} from './MetricCard';

// Activity Feed
export {
  default as ActivityFeed,
  ActivityFeedCompact,
} from './ActivityFeed';

// Charts
export {
  LineChart,
  BarChart,
  DonutChart,
  ProgressChart,
} from './Charts';

// Theme Toggle
export {
  default as DarkModeToggle,
  DarkModeToggleExpanded,
} from './DarkModeToggle';
