// Project Aura - Custom React Hooks
//
// Issue: #20 - Frontend production polish

// API hooks with retry logic
export {
  useApi,
  useMutation,
  useQuery,
  useOnlineStatus,
  OfflineBanner,
} from './useApi';

// Dashboard data hooks with auto-refresh
export {
  useDashboardData,
  useAgentStatus,
  useSystemHealth,
} from './useDashboardData';

// Dashboard configuration hooks (ADR-064)
export {
  useDashboardConfig,
  useDashboardList,
} from './useDashboardConfig';

// Voice input hook for Web Speech API
export {
  useVoiceInput,
  VoiceInputIndicator,
  VoiceInputUnsupportedMessage,
} from './useVoiceInput';

// File attachment hook for drag-and-drop uploads
export {
  useFileAttachment,
  DropZoneOverlay,
} from './useFileAttachment';

// Streaming response hook for SSE/LLM integration
export {
  useStreamingResponse,
  useStreamingText,
  useSSEConnection,
} from './useStreamingResponse';

// Customer health dashboard hooks
export {
  useCustomerHealth,
  useHealthOverview,
  useIncidents,
} from './useCustomerHealth';

// Integration management hooks
export {
  useIntegrations,
  useOAuthFlow,
  useIntegrationLogs,
  useIntegrationConfig,
} from './useIntegrations';

// Error tracking hooks for CloudWatch integration
export {
  useErrorTracking,
  useFormTracking,
  useComponentTracking,
  useAsyncTracking,
  useEngagementTracking,
  withErrorTracking,
} from './useErrorTracking';

// Accessibility hooks (ADR-060 Phase 3)
export {
  useReducedMotion,
  useHighContrast,
  useAnnouncer,
  useKeyboardNavigation,
  useRovingTabIndex,
  AnnouncerProvider,
  VisuallyHidden,
  SkipLink,
  LiveRegion,
} from './useAccessibility';

// Focus trap hook for modals
export { useFocusTrap } from './useFocusTrap';

// AI Trust Center hook
export { useTrustCenter } from './useTrustCenter';
