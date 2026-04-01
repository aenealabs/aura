/**
 * Aura TypeScript SDK - Type Definitions
 *
 * Complete type definitions for all Aura API responses and requests.
 *
 * @packageDocumentation
 */

// ============================================================================
// Common Types
// ============================================================================

/**
 * Severity levels for findings and approvals
 */
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

/**
 * Finding categories aligned with OWASP Top 10
 */
export type FindingCategory =
  | 'injection'
  | 'broken_authentication'
  | 'sensitive_data_exposure'
  | 'xxe'
  | 'broken_access_control'
  | 'security_misconfiguration'
  | 'xss'
  | 'insecure_deserialization'
  | 'vulnerable_components'
  | 'insufficient_logging'
  | 'code_quality'
  | 'performance';

/**
 * Patch lifecycle status
 */
export type PatchStatus =
  | 'pending'
  | 'generating'
  | 'ready'
  | 'approved'
  | 'applied'
  | 'rejected'
  | 'failed';

/**
 * Scan job status
 */
export type ScanStatus = 'queued' | 'scanning' | 'completed' | 'failed';

/**
 * Approval request status
 */
export type ApprovalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'cancelled';

/**
 * Integration mode for the platform
 */
export type IntegrationMode = 'autonomous' | 'supervised' | 'manual';

/**
 * Approval types
 */
export type ApprovalType =
  | 'patch_application'
  | 'deployment'
  | 'security_override'
  | 'configuration_change';

// ============================================================================
// Extension API Types
// ============================================================================

/**
 * Extension configuration from server
 */
export interface ExtensionConfig {
  scan_on_save: boolean;
  auto_suggest_patches: boolean;
  severity_threshold: Severity;
  supported_languages: string[];
  api_version: string;
  features: Record<string, boolean>;
}

/**
 * Request to scan a file for vulnerabilities
 */
export interface ScanRequest {
  file_path: string;
  file_content: string;
  language?: string;
  workspace_path?: string;
}

/**
 * Response from file scan
 */
export interface ScanResponse {
  scan_id: string;
  status: ScanStatus;
  findings_count: number;
  message: string;
}

/**
 * A vulnerability or code quality finding
 */
export interface Finding {
  id: string;
  file_path: string;
  line_start: number;
  line_end: number;
  column_start: number;
  column_end: number;
  severity: Severity;
  category: FindingCategory;
  title: string;
  description: string;
  code_snippet: string;
  suggestion: string;
  cwe_id: string | null;
  owasp_category: string | null;
  has_patch: boolean;
  patch_id: string | null;
}

/**
 * Response containing findings for a file
 */
export interface FindingsResponse {
  file_path: string;
  findings: Finding[];
  scan_timestamp: string;
  scan_duration_ms: number;
}

/**
 * Response for listing all findings
 */
export interface FindingsListResponse {
  total: number;
  findings: Finding[];
  filters: {
    severity: Severity | null;
    category: FindingCategory | null;
  };
}

/**
 * Request to generate a patch for a finding
 */
export interface PatchRequest {
  finding_id: string;
  file_path: string;
  file_content: string;
  context_lines?: number;
}

/**
 * A generated code patch
 */
export interface Patch {
  id: string;
  finding_id: string;
  file_path: string;
  status: PatchStatus;
  original_code: string;
  patched_code: string;
  diff: string;
  explanation: string;
  confidence: number;
  requires_approval: boolean;
  approval_id: string | null;
  created_at: string;
  applied_at: string | null;
}

/**
 * Response from patch generation
 */
export interface PatchResponse {
  patch: Patch;
  message: string;
}

/**
 * Request to apply an approved patch
 */
export interface ApplyPatchRequest {
  patch_id: string;
  confirm: boolean;
}

/**
 * Response from patch application
 */
export interface ApplyPatchResponse {
  success: boolean;
  patch_id: string;
  file_path: string;
  message: string;
  backup_path: string | null;
}

// ============================================================================
// Approval API Types
// ============================================================================

/**
 * Approval request summary
 */
export interface ApprovalSummary {
  id: string;
  type: ApprovalType;
  title: string;
  description: string;
  severity: Severity;
  status: ApprovalStatus;
  requested_by: string;
  requested_at: string;
  expires_at: string;
  resource_type: string;
  resource_id: string;
}

/**
 * Detailed approval request
 */
export interface ApprovalDetail extends ApprovalSummary {
  metadata: Record<string, unknown>;
  context: {
    file_path?: string;
    diff?: string;
    impact_analysis?: string;
    related_findings?: string[];
  };
  reviewer?: string;
  reviewed_at?: string;
  review_comments?: string;
}

/**
 * List of approval requests
 */
export interface ApprovalListResponse {
  approvals: ApprovalSummary[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/**
 * Approval statistics
 */
export interface ApprovalStats {
  pending: number;
  approved: number;
  rejected: number;
  expired: number;
  cancelled: number;
  total: number;
  by_severity: Record<Severity, number>;
  by_type: Record<ApprovalType, number>;
  avg_response_time_hours: number;
}

/**
 * Response from approval action
 */
export interface ApprovalActionResponse {
  success: boolean;
  approval_id: string;
  new_status: ApprovalStatus;
  message: string;
  reviewed_at: string;
}

/**
 * Approval status response (for polling)
 */
export interface ApprovalStatusResponse {
  patch_id: string;
  approval_id: string | null;
  status: string;
  reviewer: string | null;
  reviewed_at: string | null;
  comments: string | null;
}

// ============================================================================
// Incident API Types
// ============================================================================

/**
 * Security incident summary
 */
export interface IncidentSummary {
  id: string;
  title: string;
  severity: Severity;
  status: 'open' | 'investigating' | 'mitigating' | 'resolved' | 'closed';
  created_at: string;
  updated_at: string;
  assigned_to: string | null;
  affected_resources: string[];
}

/**
 * Detailed incident information
 */
export interface IncidentDetail extends IncidentSummary {
  description: string;
  timeline: IncidentTimelineEvent[];
  root_cause: string | null;
  remediation_steps: string[];
  related_findings: string[];
  metadata: Record<string, unknown>;
}

/**
 * Incident timeline event
 */
export interface IncidentTimelineEvent {
  timestamp: string;
  event_type: string;
  description: string;
  actor: string | null;
}

/**
 * List of incidents
 */
export interface IncidentListResponse {
  incidents: IncidentSummary[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================================
// Settings API Types
// ============================================================================

/**
 * Platform settings
 */
export interface PlatformSettings {
  organization_name: string;
  integration_mode: IntegrationMode;
  default_severity_threshold: Severity;
  auto_patch_enabled: boolean;
  sandbox_enabled: boolean;
  notification_settings: NotificationSettings;
}

/**
 * Notification settings
 */
export interface NotificationSettings {
  email_enabled: boolean;
  slack_enabled: boolean;
  slack_webhook_url: string | null;
  notify_on_critical: boolean;
  notify_on_high: boolean;
  notify_on_medium: boolean;
  daily_digest: boolean;
}

/**
 * Integration mode response
 */
export interface IntegrationModeResponse {
  mode: IntegrationMode;
  description: string;
  features: {
    auto_scan: boolean;
    auto_patch: boolean;
    auto_deploy: boolean;
    requires_approval: boolean;
  };
}

/**
 * HITL (Human-in-the-Loop) settings
 */
export interface HITLSettings {
  enabled: boolean;
  approval_timeout_hours: number;
  require_approval_for: ApprovalType[];
  auto_approve_low_risk: boolean;
  escalation_enabled: boolean;
  escalation_after_hours: number;
}

/**
 * MCP (Model Context Protocol) settings
 */
export interface MCPSettings {
  enabled: boolean;
  gateway_url: string | null;
  tools_enabled: string[];
  rate_limit_per_minute: number;
}

/**
 * External tool information
 */
export interface ExternalToolInfo {
  name: string;
  description: string;
  enabled: boolean;
  last_used: string | null;
  usage_count: number;
}

/**
 * MCP usage statistics
 */
export interface MCPUsageResponse {
  total_calls: number;
  calls_this_month: number;
  tools_usage: Record<string, number>;
  avg_latency_ms: number;
}

/**
 * Connection test response
 */
export interface ConnectionTestResponse {
  success: boolean;
  latency_ms: number;
  message: string;
  tools_available: string[];
}

// ============================================================================
// API Error Types
// ============================================================================

/**
 * API error response
 */
export interface APIError {
  detail: string;
  status_code: number;
  error_code?: string;
  timestamp?: string;
}

/**
 * Validation error detail
 */
export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * Validation error response
 */
export interface ValidationError {
  detail: ValidationErrorDetail[];
}

// ============================================================================
// Pagination Types
// ============================================================================

/**
 * Pagination parameters
 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/**
 * Filter parameters for findings
 */
export interface FindingsFilterParams extends PaginationParams {
  severity?: Severity;
  category?: FindingCategory;
  file_path?: string;
  has_patch?: boolean;
}

/**
 * Filter parameters for approvals
 */
export interface ApprovalsFilterParams extends PaginationParams {
  status?: ApprovalStatus;
  type?: ApprovalType;
  severity?: Severity;
  requested_by?: string;
}

/**
 * Filter parameters for incidents
 */
export interface IncidentsFilterParams extends PaginationParams {
  status?: string;
  severity?: Severity;
  assigned_to?: string;
}
