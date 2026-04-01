/**
 * Trust Center API Service
 *
 * Provides API client functions for the AI Trust Center dashboard.
 * Endpoints:
 * - GET /api/v1/trust-center/status
 * - GET /api/v1/trust-center/principles
 * - GET /api/v1/trust-center/autonomy
 * - GET /api/v1/trust-center/metrics
 * - GET /api/v1/trust-center/decisions
 * - POST /api/v1/trust-center/export
 *
 * In development mode, falls back to mock data when the backend is unavailable.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';
const IS_DEV = import.meta.env.DEV;

/**
 * Get auth headers for API requests
 */
function getAuthHeaders() {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Handle API response and parse JSON
 */
async function handleResponse(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Mock data for development when backend is unavailable
 */
// Helper to generate smooth time series data points for the past 24 hours
function generateTimeSeries(currentValue, trend, points = 12) {
  const now = Date.now();
  const interval = (24 * 60 * 60 * 1000) / points; // 24h divided by points
  const data = [];

  // Calculate starting value based on trend (work backwards from current)
  let startValue;
  if (trend === 'improving') {
    startValue = currentValue - 3.5; // Started ~3.5% lower
  } else if (trend === 'degrading') {
    startValue = currentValue + 4; // Started ~4% higher
  } else {
    startValue = currentValue - 0.5; // Stable with slight variation
  }

  for (let i = 0; i < points; i++) {
    const timestamp = new Date(now - ((points - 1 - i) * interval)).toISOString();
    // Smooth interpolation from start to current with small noise
    const progress = i / (points - 1);
    const baseValue = startValue + (currentValue - startValue) * progress;
    // Add very small noise (±0.3%) for realism
    const noise = (Math.sin(i * 1.5) * 0.3);
    const value = Math.max(0, Math.min(100, baseValue + noise));
    data.push({ timestamp, value: parseFloat(value.toFixed(1)) });
  }
  return data;
}

// Helper to generate smooth latency time series (different scale)
function generateLatencyTimeSeries(currentValue, trend, points = 12) {
  const now = Date.now();
  const interval = (24 * 60 * 60 * 1000) / points;
  const data = [];

  // Calculate starting value based on trend
  let startValue;
  if (trend === 'improving') {
    startValue = currentValue + 80; // Started 80ms higher (worse)
  } else if (trend === 'degrading') {
    startValue = currentValue - 100; // Started 100ms lower (better)
  } else {
    startValue = currentValue - 15; // Stable
  }

  for (let i = 0; i < points; i++) {
    const timestamp = new Date(now - ((points - 1 - i) * interval)).toISOString();
    const progress = i / (points - 1);
    const baseValue = startValue + (currentValue - startValue) * progress;
    // Add small noise (±10ms) for realism
    const noise = Math.sin(i * 1.2) * 10;
    const value = Math.max(100, baseValue + noise);
    data.push({ timestamp, value: Math.round(value) });
  }
  return data;
}

const MOCK_DATA = {
  status: {
    overall_status: 'warning',
    compliance_score: 0.847, // 84.7% - reflects mixed metric health
    constitutional_ai_active: true,
    guardrails_active: true,
    active_principles_count: 16,
    critical_principles_count: 4,
    decisions_last_24h: 1247,
    issues_last_24h: 42, // 2 critical + 5 high + 12 medium + 23 low
    autonomy_level: 'critical_hitl',
    last_evaluation_time: new Date(Date.now() - 180000).toISOString(), // 3 minutes ago
    // HITL approval queue data - Math: 23 approved + 1 rejected + 7 pending = 31 HITL decisions
    pending_hitl_approvals: 7,
    pending_hitl_critical: 2,
    pending_hitl_high: 3,
    hitl_approved_24h: 23,
    hitl_rejected_24h: 1,
    // System info
    system_uptime_hours: 2847.5, // ~118 days
    avg_response_time_ms: 342,
    last_principle_update: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days ago
    // Model info
    model_info: {
      cai_version: '2.4.1',
      model_provider: 'anthropic',
      model_name: 'claude-3-5-sonnet',
      last_model_update: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
      embedding_model: 'text-embedding-3-large',
    },
    // Compliance certifications
    compliance_status: {
      soc2_type2: { status: 'certified', expires: '2026-08-15', last_audit: '2025-08-15' },
      cmmc_level2: { status: 'in_progress', target_date: '2026-06-01', completion: 0.72 },
      iso27001: { status: 'certified', expires: '2027-03-22', last_audit: '2024-03-22' },
      fedramp_moderate: { status: 'planned', target_date: '2027-01-01', completion: 0.15 },
    },
  },
  // Active alerts and incidents
  alerts: [
    {
      alert_id: 'alert-001',
      severity: 'warning',
      title: 'Cache Hit Rate Below Target',
      message: 'Semantic cache hit rate has dropped to 15.5%, below the 30% target. Consider reviewing cache invalidation policies.',
      metric: 'cache_hit_rate',
      triggered_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      acknowledged: false,
      acknowledged_by: null,
    },
    {
      alert_id: 'alert-002',
      severity: 'warning',
      title: 'Critique Latency P95 Elevated',
      message: 'P95 latency has exceeded 500ms threshold at 687ms. Monitor for continued degradation.',
      metric: 'critique_latency_p95',
      triggered_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(), // 45 min ago
      acknowledged: true,
      acknowledged_by: 'platform-admin@projectaura.com',
    },
    {
      alert_id: 'alert-003',
      severity: 'critical',
      title: 'Pending Critical HITL Approvals',
      message: '2 critical severity decisions awaiting human approval for over 30 minutes.',
      metric: 'pending_hitl_critical',
      triggered_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(), // 35 min ago
      acknowledged: false,
      acknowledged_by: null,
    },
  ],
  principles: [
    // Safety principles (4) - critical severity: 2 total violations
    {
      id: 'SEC-001',
      name: 'No Credential Exposure',
      category: 'safety',
      severity: 'critical',
      enabled: true,
      description: 'Never expose secrets, API keys, or credentials in output.',
      violation_count_24h: 0,
      domain_tags: ['security', 'compliance'],
      version: '1.2.0',
      last_violation_time: new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString(), // 3 days ago
      threshold: { type: 'pattern_match', patterns: ['api_key', 'secret', 'password', 'token'], confidence: 0.95 },
      remediation_guidance: 'Redact detected credentials and replace with placeholder tokens. Alert security team for potential exposure.',
      owner: 'security-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-11-20T00:00:00Z',
    },
    {
      id: 'SEC-002',
      name: 'Safe Code Generation',
      category: 'safety',
      severity: 'critical',
      enabled: true,
      description: 'Generate code free from known vulnerabilities (OWASP Top 10, CWE Top 25).',
      violation_count_24h: 2,
      domain_tags: ['security', 'code'],
      version: '2.1.0',
      last_violation_time: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), // 4 hours ago
      threshold: { type: 'vulnerability_scan', scanner: 'semgrep', min_severity: 'medium', confidence: 0.85 },
      remediation_guidance: 'Apply secure coding patterns. For SQL: use parameterized queries. For XSS: sanitize output. For injection: validate inputs.',
      owner: 'security-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-12-10T00:00:00Z',
    },
    {
      id: 'SEC-003',
      name: 'Input Sanitization',
      category: 'safety',
      severity: 'critical',
      enabled: true,
      description: 'Sanitize all user inputs to prevent injection attacks.',
      violation_count_24h: 0,
      domain_tags: ['security', 'validation'],
      version: '1.0.0',
      last_violation_time: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(), // 14 days ago
      threshold: { type: 'input_validation', checks: ['sql_injection', 'xss', 'command_injection'], confidence: 0.90 },
      remediation_guidance: 'Implement input validation at system boundaries. Use allowlists over denylists. Escape special characters.',
      owner: 'security-team@aenealabs.com',
      created_at: '2025-04-01T00:00:00Z',
      updated_at: '2025-04-01T00:00:00Z',
    },
    {
      id: 'SEC-004',
      name: 'Sandbox Isolation',
      category: 'safety',
      severity: 'critical',
      enabled: true,
      description: 'Ensure all code execution occurs in isolated sandboxes with no network egress.',
      violation_count_24h: 0,
      domain_tags: ['security', 'isolation'],
      version: '1.1.0',
      last_violation_time: null, // Never violated
      threshold: { type: 'runtime_check', checks: ['network_isolation', 'filesystem_isolation', 'process_isolation'], confidence: 1.0 },
      remediation_guidance: 'Reject execution requests that cannot be sandboxed. Escalate to HITL if sandbox provisioning fails.',
      owner: 'platform-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-09-01T00:00:00Z',
    },
    // Compliance principles (3) - high severity: 5 violations
    {
      id: 'COMP-001',
      name: 'Audit Trail Completeness',
      category: 'compliance',
      severity: 'high',
      enabled: true,
      description: 'Maintain complete audit trails for all operations with immutable logging.',
      violation_count_24h: 2,
      domain_tags: ['compliance', 'logging'],
      version: '1.3.0',
      last_violation_time: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), // 6 hours ago
      threshold: { type: 'completeness_check', required_fields: ['user_id', 'action', 'timestamp', 'resource', 'outcome'], confidence: 1.0 },
      remediation_guidance: 'Ensure all required audit fields are populated before operation completion. Queue failed audits for retry.',
      owner: 'compliance-team@aenealabs.com',
      created_at: '2025-03-20T00:00:00Z',
      updated_at: '2025-10-15T00:00:00Z',
    },
    {
      id: 'COMP-002',
      name: 'Data Retention Policy',
      category: 'compliance',
      severity: 'high',
      enabled: true,
      description: 'Comply with data retention and deletion requirements per jurisdiction.',
      violation_count_24h: 1,
      domain_tags: ['compliance', 'data'],
      version: '1.0.0',
      last_violation_time: new Date(Date.now() - 18 * 60 * 60 * 1000).toISOString(), // 18 hours ago
      threshold: { type: 'policy_check', max_retention_days: 365, deletion_verification: true, confidence: 1.0 },
      remediation_guidance: 'Apply retention policies based on data classification. Schedule deletion jobs for expired data.',
      owner: 'compliance-team@aenealabs.com',
      created_at: '2025-05-01T00:00:00Z',
      updated_at: '2025-05-01T00:00:00Z',
    },
    {
      id: 'COMP-003',
      name: 'Access Control Verification',
      category: 'compliance',
      severity: 'high',
      enabled: true,
      description: 'Verify user authorization before sensitive operations using RBAC.',
      violation_count_24h: 1,
      domain_tags: ['compliance', 'access'],
      version: '1.1.0',
      last_violation_time: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), // 12 hours ago
      threshold: { type: 'authorization_check', require_explicit_grant: true, check_resource_ownership: true, confidence: 1.0 },
      remediation_guidance: 'Deny access if authorization cannot be verified. Log unauthorized access attempts for security review.',
      owner: 'security-team@aenealabs.com',
      created_at: '2025-04-15T00:00:00Z',
      updated_at: '2025-08-20T00:00:00Z',
    },
    {
      id: 'COMP-004',
      name: 'PII Handling',
      category: 'compliance',
      severity: 'high',
      enabled: true,
      description: 'Detect and protect personally identifiable information in all processing.',
      violation_count_24h: 1,
      domain_tags: ['compliance', 'privacy', 'pii'],
      version: '1.2.0',
      last_violation_time: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), // 8 hours ago
      threshold: { type: 'pii_detection', categories: ['ssn', 'email', 'phone', 'address', 'dob'], confidence: 0.90 },
      remediation_guidance: 'Mask or tokenize detected PII before storage. Apply encryption at rest for PII fields.',
      owner: 'compliance-team@aenealabs.com',
      created_at: '2025-06-01T00:00:00Z',
      updated_at: '2025-11-01T00:00:00Z',
    },
    // Transparency principles (3) - medium severity: 7 violations
    {
      id: 'TRANS-001',
      name: 'Explainable Decisions',
      category: 'transparency',
      severity: 'medium',
      enabled: true,
      description: 'Provide clear reasoning for all decisions with traceable logic chains.',
      violation_count_24h: 4,
      domain_tags: ['transparency'],
      version: '1.0.0',
      last_violation_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      threshold: { type: 'explanation_quality', min_reasoning_steps: 2, require_evidence: true, confidence: 0.80 },
      remediation_guidance: 'Include step-by-step reasoning in responses. Reference specific principles or policies that influenced the decision.',
      owner: 'ai-ethics-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-03-15T00:00:00Z',
    },
    {
      id: 'TRANS-002',
      name: 'Uncertainty Communication',
      category: 'transparency',
      severity: 'medium',
      enabled: true,
      description: 'Clearly communicate confidence levels and limitations in responses.',
      violation_count_24h: 2,
      domain_tags: ['transparency', 'honesty'],
      version: '1.1.0',
      last_violation_time: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(), // 5 hours ago
      threshold: { type: 'confidence_disclosure', require_confidence_score: true, low_confidence_threshold: 0.70, confidence: 0.75 },
      remediation_guidance: 'Express uncertainty using calibrated language. Suggest verification for low-confidence outputs.',
      owner: 'ai-ethics-team@aenealabs.com',
      created_at: '2025-04-01T00:00:00Z',
      updated_at: '2025-07-15T00:00:00Z',
    },
    {
      id: 'TRANS-003',
      name: 'Source Attribution',
      category: 'transparency',
      severity: 'medium',
      enabled: true,
      description: 'Attribute information sources when applicable and verifiable.',
      violation_count_24h: 1,
      domain_tags: ['transparency', 'citation'],
      version: '1.0.0',
      last_violation_time: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(), // 20 hours ago
      threshold: { type: 'attribution_check', require_source_for_facts: true, verify_source_exists: false, confidence: 0.70 },
      remediation_guidance: 'Include source references for factual claims. Distinguish between retrieved knowledge and generated content.',
      owner: 'ai-ethics-team@aenealabs.com',
      created_at: '2025-05-01T00:00:00Z',
      updated_at: '2025-05-01T00:00:00Z',
    },
    // Helpfulness principles (2) - medium/low severity: 3 medium, 11 low
    {
      id: 'HELP-001',
      name: 'Constructive Engagement',
      category: 'helpfulness',
      severity: 'medium',
      enabled: true,
      description: 'Engage constructively with requests, explaining concerns rather than refusing outright.',
      violation_count_24h: 3,
      domain_tags: ['helpfulness'],
      version: '1.2.0',
      last_violation_time: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
      threshold: { type: 'engagement_quality', min_explanation_length: 50, require_alternatives: true, confidence: 0.75 },
      remediation_guidance: 'When declining a request, explain why and offer alternative approaches. Avoid terse refusals.',
      owner: 'ai-ethics-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-10-01T00:00:00Z',
    },
    {
      id: 'HELP-002',
      name: 'Task Completion',
      category: 'helpfulness',
      severity: 'low',
      enabled: true,
      description: 'Complete requested tasks thoroughly within safety bounds.',
      violation_count_24h: 11,
      domain_tags: ['helpfulness', 'completion'],
      version: '1.0.0',
      last_violation_time: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 min ago
      threshold: { type: 'completion_check', require_full_response: true, max_truncation_ratio: 0.10, confidence: 0.80 },
      remediation_guidance: 'Ensure responses fully address the request. If truncation is necessary, indicate continuation is available.',
      owner: 'product-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-03-15T00:00:00Z',
    },
    // Anti-sycophancy principles (2) - high/medium severity: 1 high, 2 medium
    {
      id: 'ANTI-001',
      name: 'Honest Assessment',
      category: 'anti_sycophancy',
      severity: 'high',
      enabled: true,
      description: 'Provide honest technical assessments even when they contradict user expectations.',
      violation_count_24h: 1,
      domain_tags: ['honesty'],
      version: '1.1.0',
      last_violation_time: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(), // 16 hours ago
      threshold: { type: 'honesty_check', detect_excessive_agreement: true, require_critical_analysis: true, confidence: 0.80 },
      remediation_guidance: 'Identify and flag potential issues even if the user expects validation. Use respectful but direct language.',
      owner: 'ai-ethics-team@aenealabs.com',
      created_at: '2025-04-01T00:00:00Z',
      updated_at: '2025-09-15T00:00:00Z',
    },
    {
      id: 'ANTI-002',
      name: 'Disagreement Expression',
      category: 'anti_sycophancy',
      severity: 'medium',
      enabled: true,
      description: 'Express disagreement respectfully when user assumptions or code are incorrect.',
      violation_count_24h: 2,
      domain_tags: ['honesty', 'feedback'],
      version: '1.0.0',
      last_violation_time: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(), // 7 hours ago
      threshold: { type: 'disagreement_check', detect_false_validation: true, require_correction: true, confidence: 0.75 },
      remediation_guidance: 'Politely correct misconceptions with evidence. Frame disagreements constructively.',
      owner: 'ai-ethics-team@aenealabs.com',
      created_at: '2025-04-15T00:00:00Z',
      updated_at: '2025-04-15T00:00:00Z',
    },
    // Code quality principles (1) - low severity: 12 violations
    {
      id: 'CODE-001',
      name: 'Code Quality Standards',
      category: 'code_quality',
      severity: 'low',
      enabled: true,
      description: 'Adhere to clean code principles, SOLID, and language-specific best practices.',
      violation_count_24h: 12,
      domain_tags: ['code', 'quality'],
      version: '2.0.0',
      last_violation_time: new Date(Date.now() - 15 * 60 * 1000).toISOString(), // 15 min ago
      threshold: { type: 'lint_check', linters: ['eslint', 'pylint', 'rustfmt'], max_warnings: 5, confidence: 0.90 },
      remediation_guidance: 'Apply language-specific formatting. Follow naming conventions. Keep functions focused and testable.',
      owner: 'engineering-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-12-01T00:00:00Z',
    },
    // Meta principles (1) - critical severity: 0 violations (disabled)
    {
      id: 'META-001',
      name: 'Self-Improvement Bounds',
      category: 'meta',
      severity: 'critical',
      enabled: false,
      description: 'Operate within defined capability boundaries. Do not attempt to modify own weights or training.',
      violation_count_24h: 0,
      domain_tags: ['meta', 'safety'],
      version: '1.0.0',
      last_violation_time: null, // Never violated (disabled)
      threshold: { type: 'capability_boundary', detect_self_modification: true, detect_training_manipulation: true, confidence: 1.0 },
      remediation_guidance: 'Immediately halt and escalate any detected self-modification attempts. This principle should never be disabled in production.',
      owner: 'security-team@aenealabs.com',
      created_at: '2025-03-15T00:00:00Z',
      updated_at: '2025-03-15T00:00:00Z',
    },
    // Total: 16 principles (4 critical, 4 high, 6 medium, 2 low)
    // Violations by severity: critical=2, high=5, medium=12, low=23 (total=42)
  ],
  autonomy: {
    current_level: 'critical_hitl',
    policy_id: 'default-enterprise',
    policy_name: 'Enterprise Standard',
    preset_name: 'Enterprise Standard',
    description: 'Human approval required for critical and high-severity operations. Auto-approval for medium/low severity with full audit logging.',
    hitl_enabled: true,
    // Decision statistics - must align with status data
    // Total decisions: 1247, HITL required: 31 (23 approved + 1 rejected + 7 pending), Auto-approved: 1216
    auto_approved_24h: 1216,
    hitl_required_24h: 31,
    last_hitl_decision: new Date(Date.now() - 420000).toISOString(), // 7 minutes ago
    levels: [
      { id: 'full_hitl', name: 'Full HITL', description: 'All operations require approval', is_current: false },
      { id: 'critical_hitl', name: 'Critical HITL', description: 'Critical operations require approval', is_current: true },
      { id: 'audit_only', name: 'Audit Only', description: 'All operations logged, no approval needed', is_current: false },
      { id: 'full_autonomous', name: 'Autonomous', description: 'Full autonomous operation', is_current: false },
    ],
    approval_requirements: {
      code_changes: 'critical_only',
      deployments: 'always',
      security_patches: 'always',
      config_changes: 'critical_only',
    },
    // Severity-based overrides (maps severity to autonomy level)
    severity_overrides: {
      critical: 'full_hitl',
      high: 'critical_hitl',
      medium: 'audit_only',
      low: 'full_autonomous',
    },
    // Operation-specific overrides (maps operation to autonomy level)
    operation_overrides: {
      security_patch: 'full_hitl',
      deployment: 'full_hitl',
      config_change: 'critical_hitl',
      code_generation: 'audit_only',
      code_refactoring: 'audit_only',
      dependency_update: 'critical_hitl',
    },
    // Active guardrails
    active_guardrails: [
      'credential_detection',
      'code_injection_prevention',
      'sandbox_enforcement',
      'rate_limiting',
      'output_sanitization',
      'prompt_injection_detection',
    ],
  },
  metrics: {
    period: '24h',
    generated_at: new Date().toISOString(),
    total_evaluations: 1247,
    total_critiques: 892,
    total_revisions: 156,
    issues_by_severity: { critical: 2, high: 5, medium: 12, low: 23 },
    // Core CAI Metrics (from ADR-063)
    // GREEN: 92.3/90 = 102.6% of target (≥90% = healthy)
    critique_accuracy: { current_value: 92.3, target_value: 90, status: 'healthy', trend: 'improving', unit: 'percent', change_24h: 1.2, time_series: generateTimeSeries(92.3, 'improving') },
    // YELLOW: 79.8/95 = 84.0% of target (60-89% = warning)
    revision_convergence_rate: { current_value: 79.8, target_value: 95, status: 'warning', trend: 'degrading', unit: 'percent', change_24h: -2.3, time_series: generateTimeSeries(79.8, 'degrading') },
    // RED: 15.5/30 = 51.7% of target (<60% = critical)
    cache_hit_rate: { current_value: 15.5, target_value: 30, status: 'critical', trend: 'degrading', unit: 'percent', change_24h: -4.1, time_series: generateTimeSeries(15.5, 'degrading') },
    // YELLOW: 58.1/70 = 83.0% of target (60-89% = warning)
    non_evasive_rate: { current_value: 58.1, target_value: 70, status: 'warning', trend: 'stable', unit: 'percent', change_24h: -0.8, time_series: generateTimeSeries(58.1, 'stable') },
    // RED: 687/500 = 137.4% of target (>130% over = critical for latency)
    critique_latency_p95: { current_value: 687, target_value: 500, status: 'critical', trend: 'degrading', unit: 'ms', change_24h: 52, time_series: generateLatencyTimeSeries(687, 'degrading') },
    // GREEN: 97.0/95 = 102.1% of target (≥90% = healthy)
    golden_set_pass_rate: { current_value: 97.0, target_value: 95, status: 'healthy', trend: 'stable', unit: 'percent', change_24h: 0.5, time_series: generateTimeSeries(97.0, 'stable') },
    // Additional Operational Metrics
    false_positive_rate: { current_value: 4.2, target_value: 5, status: 'healthy', trend: 'improving', unit: 'percent', change_24h: -0.3, time_series: generateTimeSeries(4.2, 'improving') },
    human_override_rate: { current_value: 2.8, target_value: 5, status: 'healthy', trend: 'stable', unit: 'percent', change_24h: 0.1, time_series: generateTimeSeries(2.8, 'stable') },
    avg_revision_iterations: { current_value: 1.4, target_value: 2, status: 'healthy', trend: 'stable', unit: 'count', change_24h: 0.0 },
    // Per-Agent Breakdown
    by_agent: {
      CoderAgent: { evaluations: 523, issues: 18, avg_latency_ms: 312, accuracy: 93.1 },
      ReviewerAgent: { evaluations: 298, issues: 12, avg_latency_ms: 287, accuracy: 94.2 },
      ValidatorAgent: { evaluations: 245, issues: 8, avg_latency_ms: 198, accuracy: 91.5 },
      PatcherAgent: { evaluations: 181, issues: 4, avg_latency_ms: 456, accuracy: 90.8 },
    },
    // Per-Principle Breakdown (top violators)
    by_principle: {
      'CODE-001': { violations: 12, trend: 'stable' },
      'HELP-002': { violations: 11, trend: 'degrading' },
      'TRANS-001': { violations: 4, trend: 'improving' },
      'HELP-001': { violations: 3, trend: 'stable' },
      'SEC-002': { violations: 2, trend: 'improving' },
    },
    // Cost Metrics
    cost_metrics: {
      total_tokens_24h: 4_892_340,
      input_tokens_24h: 3_245_120,
      output_tokens_24h: 1_647_220,
      estimated_cost_24h_usd: 48.92,
      avg_cost_per_evaluation_usd: 0.039,
      cost_trend: 'stable',
      cost_change_24h_percent: 2.1,
    },
  },
  decisions: {
    // Sample of 20 recent decisions showing variety of outcomes
    // Stats: 1247 total, 31 HITL required (23 approved, 1 rejected, 7 pending), 1216 auto-approved
    decisions: [
      // Recent auto-approved (no issues)
      {
        decision_id: 'cai-dec-7f3a9b2e-4c81-4d5f-a123-8e9f0c6d7b4a',
        timestamp: new Date(Date.now() - 300000).toISOString(), // 5 min ago
        agent_name: 'CoderAgent',
        operation_type: 'code_generation',
        execution_time_ms: 245.32,
        principles_evaluated: 4,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        // Context fields
        user_id: 'usr-a1b2c3d4',
        user_email: 'sarah.chen@acme-corp.com',
        team_id: 'team-frontend',
        project_id: 'proj-webapp-v2',
        repository: 'acme-corp/webapp-frontend',
        session_id: 'sess-2024-01-21-001',
        request_id: 'req-7f3a9b2e',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        input_tokens: 1245,
        output_tokens: 892,
      },
      // Auto-approved with medium issue (revised)
      {
        decision_id: 'cai-dec-2e8c4d1a-9f7b-4a3e-b567-1c2d3e4f5a6b',
        timestamp: new Date(Date.now() - 600000).toISOString(), // 10 min ago
        agent_name: 'ReviewerAgent',
        operation_type: 'security_review',
        execution_time_ms: 312.87,
        principles_evaluated: 6,
        issues_found: 2,
        severity_breakdown: { medium: 1, low: 1 },
        requires_revision: true,
        revised: true,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-e5f6g7h8',
        user_email: 'marcus.johnson@acme-corp.com',
        team_id: 'team-backend',
        project_id: 'proj-api-gateway',
        repository: 'acme-corp/api-gateway',
        session_id: 'sess-2024-01-21-002',
        request_id: 'req-2e8c4d1a',
        parent_decision_id: null,
        critique_summary: 'Missing input validation on user-supplied parameters. Potential for injection if not sanitized.',
        revision_summary: 'Added parameterized query binding and input sanitization middleware.',
        input_tokens: 2341,
        output_tokens: 1567,
      },
      // HITL approved (high severity deployment)
      {
        decision_id: 'cai-dec-5b6c7d8e-1a2b-3c4d-e5f6-7a8b9c0d1e2f',
        timestamp: new Date(Date.now() - 900000).toISOString(), // 15 min ago
        agent_name: 'ValidatorAgent',
        operation_type: 'deployment_validation',
        execution_time_ms: 189.45,
        principles_evaluated: 3,
        issues_found: 1,
        severity_breakdown: { high: 1 },
        requires_revision: true,
        revised: false,
        hitl_required: true,
        hitl_approved: true,
        approved_by: 'aura-admin@projectaura.com',
        user_id: 'usr-i9j0k1l2',
        user_email: 'devops@acme-corp.com',
        team_id: 'team-devops',
        project_id: 'proj-infrastructure',
        repository: 'acme-corp/terraform-modules',
        session_id: 'sess-2024-01-21-003',
        request_id: 'req-5b6c7d8e',
        parent_decision_id: null,
        critique_summary: 'Production deployment lacks rollback strategy. High risk of service disruption if issues occur.',
        revision_summary: null,
        hitl_decision_time_ms: 45000, // 45 seconds to approve
        hitl_notes: 'Approved after confirming rollback procedure documented in runbook.',
        input_tokens: 1876,
        output_tokens: 423,
      },
      // HITL pending (security patch awaiting approval)
      {
        decision_id: 'cai-dec-9d8e7f6a-5b4c-3d2e-1f0a-b9c8d7e6f5a4',
        timestamp: new Date(Date.now() - 1200000).toISOString(), // 20 min ago
        agent_name: 'PatcherAgent',
        operation_type: 'security_patch',
        execution_time_ms: 567.21,
        principles_evaluated: 8,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: true,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-m3n4o5p6',
        user_email: 'security@acme-corp.com',
        team_id: 'team-security',
        project_id: 'proj-auth-service',
        repository: 'acme-corp/auth-service',
        session_id: 'sess-2024-01-21-004',
        request_id: 'req-9d8e7f6a',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        hitl_queue_position: 3,
        hitl_escalation_level: 'standard',
        input_tokens: 3456,
        output_tokens: 2134,
      },
      // Auto-approved with low issue
      {
        decision_id: 'cai-dec-3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f',
        timestamp: new Date(Date.now() - 1500000).toISOString(), // 25 min ago
        agent_name: 'CoderAgent',
        operation_type: 'code_refactoring',
        execution_time_ms: 423.67,
        principles_evaluated: 5,
        issues_found: 1,
        severity_breakdown: { low: 1 },
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-a1b2c3d4',
        user_email: 'sarah.chen@acme-corp.com',
        team_id: 'team-frontend',
        project_id: 'proj-webapp-v2',
        repository: 'acme-corp/webapp-frontend',
        session_id: 'sess-2024-01-21-001',
        request_id: 'req-3c4d5e6f',
        parent_decision_id: null,
        critique_summary: 'Function naming does not follow project conventions (camelCase vs snake_case).',
        revision_summary: null,
        input_tokens: 2134,
        output_tokens: 1789,
      },
      // Auto-approved (compliance check clean)
      {
        decision_id: 'cai-dec-1a2b3c4d-5e6f-7a8b-9c0d-e1f2a3b4c5d6',
        timestamp: new Date(Date.now() - 1800000).toISOString(), // 30 min ago
        agent_name: 'ReviewerAgent',
        operation_type: 'compliance_check',
        execution_time_ms: 278.93,
        principles_evaluated: 7,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-q7r8s9t0',
        user_email: 'compliance@acme-corp.com',
        team_id: 'team-compliance',
        project_id: 'proj-data-pipeline',
        repository: 'acme-corp/data-pipeline',
        session_id: 'sess-2024-01-21-005',
        request_id: 'req-1a2b3c4d',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        input_tokens: 1567,
        output_tokens: 234,
      },
      // HITL approved (critical infrastructure issue)
      {
        decision_id: 'cai-dec-8f9e0d1c-2b3a-4c5d-6e7f-8a9b0c1d2e3f',
        timestamp: new Date(Date.now() - 2100000).toISOString(), // 35 min ago
        agent_name: 'ValidatorAgent',
        operation_type: 'infrastructure_validation',
        execution_time_ms: 156.42,
        principles_evaluated: 4,
        issues_found: 3,
        severity_breakdown: { critical: 1, medium: 2 },
        requires_revision: true,
        revised: true,
        hitl_required: true,
        hitl_approved: true,
        approved_by: 'aura-admin@projectaura.com',
        user_id: 'usr-i9j0k1l2',
        user_email: 'devops@acme-corp.com',
        team_id: 'team-devops',
        project_id: 'proj-infrastructure',
        repository: 'acme-corp/terraform-modules',
        session_id: 'sess-2024-01-21-003',
        request_id: 'req-8f9e0d1c',
        parent_decision_id: 'cai-dec-prev-infra-001',
        critique_summary: 'Security group allows unrestricted SSH access (0.0.0.0/0). Critical exposure risk.',
        revision_summary: 'Restricted SSH access to VPN CIDR blocks only. Added bastion host requirement.',
        hitl_decision_time_ms: 120000, // 2 minutes to approve
        hitl_notes: 'Verified revised security group rules with InfoSec team.',
        input_tokens: 2890,
        output_tokens: 1456,
      },
      // Auto-approved (dependency update clean)
      {
        decision_id: 'cai-dec-4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a',
        timestamp: new Date(Date.now() - 2400000).toISOString(), // 40 min ago
        agent_name: 'PatcherAgent',
        operation_type: 'dependency_update',
        execution_time_ms: 389.15,
        principles_evaluated: 6,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-u1v2w3x4',
        user_email: 'alex.kumar@acme-corp.com',
        team_id: 'team-backend',
        project_id: 'proj-api-gateway',
        repository: 'acme-corp/api-gateway',
        session_id: 'sess-2024-01-21-006',
        request_id: 'req-4d5e6f7a',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        input_tokens: 987,
        output_tokens: 654,
      },
      // HITL pending - critical issue (pending approval #2)
      {
        decision_id: 'cai-dec-a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        timestamp: new Date(Date.now() - 2700000).toISOString(), // 45 min ago
        agent_name: 'CoderAgent',
        operation_type: 'code_generation',
        execution_time_ms: 512.34,
        principles_evaluated: 5,
        issues_found: 1,
        severity_breakdown: { critical: 1 },
        requires_revision: true,
        revised: false,
        hitl_required: true,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-y5z6a7b8',
        user_email: 'jamie.wilson@acme-corp.com',
        team_id: 'team-ml',
        project_id: 'proj-ml-pipeline',
        repository: 'acme-corp/ml-pipeline',
        session_id: 'sess-2024-01-21-007',
        request_id: 'req-a1b2c3d4',
        parent_decision_id: null,
        critique_summary: 'Generated code executes user-provided Python expressions without sandboxing. Remote code execution risk.',
        revision_summary: null,
        hitl_queue_position: 1,
        hitl_escalation_level: 'critical',
        input_tokens: 3211,
        output_tokens: 2567,
      },
      // HITL rejected (user declined the change)
      {
        decision_id: 'cai-dec-b2c3d4e5-f6a7-8901-bcde-f23456789012',
        timestamp: new Date(Date.now() - 3000000).toISOString(), // 50 min ago
        agent_name: 'PatcherAgent',
        operation_type: 'security_patch',
        execution_time_ms: 634.21,
        principles_evaluated: 6,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: true,
        hitl_approved: false,
        approved_by: 'security-lead@projectaura.com',
        user_id: 'usr-m3n4o5p6',
        user_email: 'security@acme-corp.com',
        team_id: 'team-security',
        project_id: 'proj-auth-service',
        repository: 'acme-corp/auth-service',
        session_id: 'sess-2024-01-21-004',
        request_id: 'req-b2c3d4e5',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        hitl_decision_time_ms: 180000, // 3 minutes to reject
        hitl_notes: 'Rejected: Patch changes authentication flow. Requires broader security review before deployment.',
        rejection_reason: 'scope_change_required',
        input_tokens: 2789,
        output_tokens: 1234,
      },
      // Auto-approved (code review clean)
      {
        decision_id: 'cai-dec-c3d4e5f6-a7b8-9012-cdef-345678901234',
        timestamp: new Date(Date.now() - 3300000).toISOString(), // 55 min ago
        agent_name: 'ReviewerAgent',
        operation_type: 'code_review',
        execution_time_ms: 287.56,
        principles_evaluated: 8,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-c9d0e1f2',
        user_email: 'priya.sharma@acme-corp.com',
        team_id: 'team-frontend',
        project_id: 'proj-webapp-v2',
        repository: 'acme-corp/webapp-frontend',
        session_id: 'sess-2024-01-21-008',
        request_id: 'req-c3d4e5f6',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        input_tokens: 4567,
        output_tokens: 1890,
      },
      // HITL pending - high severity (pending approval #3)
      {
        decision_id: 'cai-dec-d4e5f6a7-b8c9-0123-defa-456789012345',
        timestamp: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
        agent_name: 'ValidatorAgent',
        operation_type: 'deployment_validation',
        execution_time_ms: 445.89,
        principles_evaluated: 5,
        issues_found: 2,
        severity_breakdown: { high: 2 },
        requires_revision: true,
        revised: false,
        hitl_required: true,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-i9j0k1l2',
        user_email: 'devops@acme-corp.com',
        team_id: 'team-devops',
        project_id: 'proj-microservices',
        repository: 'acme-corp/order-service',
        session_id: 'sess-2024-01-21-009',
        request_id: 'req-d4e5f6a7',
        parent_decision_id: null,
        critique_summary: 'Database migration lacks transaction wrapping. Partial failures could leave data inconsistent.',
        revision_summary: null,
        hitl_queue_position: 4,
        hitl_escalation_level: 'high',
        input_tokens: 2345,
        output_tokens: 987,
      },
      // Auto-approved with multiple low issues
      {
        decision_id: 'cai-dec-e5f6a7b8-c9d0-1234-efab-567890123456',
        timestamp: new Date(Date.now() - 3900000).toISOString(), // 1h 5min ago
        agent_name: 'CoderAgent',
        operation_type: 'code_refactoring',
        execution_time_ms: 356.78,
        principles_evaluated: 4,
        issues_found: 3,
        severity_breakdown: { low: 3 },
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-g3h4i5j6',
        user_email: 'tom.baker@acme-corp.com',
        team_id: 'team-backend',
        project_id: 'proj-reporting',
        repository: 'acme-corp/reporting-service',
        session_id: 'sess-2024-01-21-010',
        request_id: 'req-e5f6a7b8',
        parent_decision_id: null,
        critique_summary: 'Minor style violations: unused imports, inconsistent spacing, missing docstrings.',
        revision_summary: null,
        input_tokens: 1876,
        output_tokens: 2345,
      },
      // HITL approved (deployment to production)
      {
        decision_id: 'cai-dec-f6a7b8c9-d0e1-2345-fabc-678901234567',
        timestamp: new Date(Date.now() - 4200000).toISOString(), // 1h 10min ago
        agent_name: 'ValidatorAgent',
        operation_type: 'deployment_validation',
        execution_time_ms: 234.56,
        principles_evaluated: 6,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: true,
        hitl_approved: true,
        approved_by: 'devops-lead@projectaura.com',
        user_id: 'usr-i9j0k1l2',
        user_email: 'devops@acme-corp.com',
        team_id: 'team-devops',
        project_id: 'proj-api-gateway',
        repository: 'acme-corp/api-gateway',
        session_id: 'sess-2024-01-21-011',
        request_id: 'req-f6a7b8c9',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        hitl_decision_time_ms: 30000, // 30 seconds to approve
        hitl_notes: 'Routine production deployment. All pre-flight checks passed.',
        input_tokens: 1234,
        output_tokens: 567,
      },
      // Auto-approved (test generation)
      {
        decision_id: 'cai-dec-a7b8c9d0-e1f2-3456-abcd-789012345678',
        timestamp: new Date(Date.now() - 4500000).toISOString(), // 1h 15min ago
        agent_name: 'CoderAgent',
        operation_type: 'test_generation',
        execution_time_ms: 198.34,
        principles_evaluated: 3,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-k7l8m9n0',
        user_email: 'qa-team@acme-corp.com',
        team_id: 'team-qa',
        project_id: 'proj-webapp-v2',
        repository: 'acme-corp/webapp-frontend',
        session_id: 'sess-2024-01-21-012',
        request_id: 'req-a7b8c9d0',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        input_tokens: 2345,
        output_tokens: 3456,
      },
      // HITL pending - high severity (pending approval #4)
      {
        decision_id: 'cai-dec-b8c9d0e1-f2a3-4567-bcde-890123456789',
        timestamp: new Date(Date.now() - 4800000).toISOString(), // 1h 20min ago
        agent_name: 'PatcherAgent',
        operation_type: 'security_patch',
        execution_time_ms: 678.92,
        principles_evaluated: 7,
        issues_found: 1,
        severity_breakdown: { high: 1 },
        requires_revision: true,
        revised: false,
        hitl_required: true,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-m3n4o5p6',
        user_email: 'security@acme-corp.com',
        team_id: 'team-security',
        project_id: 'proj-payment-service',
        repository: 'acme-corp/payment-service',
        session_id: 'sess-2024-01-21-013',
        request_id: 'req-b8c9d0e1',
        parent_decision_id: null,
        critique_summary: 'Patch modifies encryption key rotation logic. Requires security team verification.',
        revision_summary: null,
        hitl_queue_position: 5,
        hitl_escalation_level: 'high',
        input_tokens: 3789,
        output_tokens: 2456,
      },
      // Auto-approved (documentation update)
      {
        decision_id: 'cai-dec-c9d0e1f2-a3b4-5678-cdef-901234567890',
        timestamp: new Date(Date.now() - 5100000).toISOString(), // 1h 25min ago
        agent_name: 'ReviewerAgent',
        operation_type: 'documentation_review',
        execution_time_ms: 145.67,
        principles_evaluated: 2,
        issues_found: 1,
        severity_breakdown: { low: 1 },
        requires_revision: false,
        revised: false,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-o1p2q3r4',
        user_email: 'docs@acme-corp.com',
        team_id: 'team-docs',
        project_id: 'proj-api-gateway',
        repository: 'acme-corp/api-gateway',
        session_id: 'sess-2024-01-21-014',
        request_id: 'req-c9d0e1f2',
        parent_decision_id: null,
        critique_summary: 'API documentation example uses deprecated endpoint format.',
        revision_summary: null,
        input_tokens: 876,
        output_tokens: 234,
      },
      // HITL approved (config change)
      {
        decision_id: 'cai-dec-d0e1f2a3-b4c5-6789-defa-012345678901',
        timestamp: new Date(Date.now() - 5400000).toISOString(), // 1h 30min ago
        agent_name: 'ValidatorAgent',
        operation_type: 'config_validation',
        execution_time_ms: 312.45,
        principles_evaluated: 4,
        issues_found: 0,
        severity_breakdown: {},
        requires_revision: false,
        revised: false,
        hitl_required: true,
        hitl_approved: true,
        approved_by: 'platform-admin@projectaura.com',
        user_id: 'usr-s5t6u7v8',
        user_email: 'platform@acme-corp.com',
        team_id: 'team-platform',
        project_id: 'proj-infrastructure',
        repository: 'acme-corp/platform-config',
        session_id: 'sess-2024-01-21-015',
        request_id: 'req-d0e1f2a3',
        parent_decision_id: null,
        critique_summary: null,
        revision_summary: null,
        hitl_decision_time_ms: 60000, // 1 minute to approve
        hitl_notes: 'Config change approved for staging environment.',
        input_tokens: 567,
        output_tokens: 123,
      },
      // HITL pending - critical (pending approval #5 - one of the 2 critical pending)
      {
        decision_id: 'cai-dec-e1f2a3b4-c5d6-7890-efab-123456789012',
        timestamp: new Date(Date.now() - 5700000).toISOString(), // 1h 35min ago
        agent_name: 'PatcherAgent',
        operation_type: 'security_patch',
        execution_time_ms: 723.15,
        principles_evaluated: 8,
        issues_found: 2,
        severity_breakdown: { critical: 1, high: 1 },
        requires_revision: true,
        revised: false,
        hitl_required: true,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-m3n4o5p6',
        user_email: 'security@acme-corp.com',
        team_id: 'team-security',
        project_id: 'proj-auth-service',
        repository: 'acme-corp/auth-service',
        session_id: 'sess-2024-01-21-016',
        request_id: 'req-e1f2a3b4',
        parent_decision_id: null,
        critique_summary: 'Patch addresses CVE-2024-1234 but introduces potential session fixation vulnerability.',
        revision_summary: null,
        hitl_queue_position: 2,
        hitl_escalation_level: 'critical',
        input_tokens: 4567,
        output_tokens: 3456,
      },
      // Auto-approved (API integration)
      {
        decision_id: 'cai-dec-f2a3b4c5-d6e7-8901-fabc-234567890123',
        timestamp: new Date(Date.now() - 6000000).toISOString(), // 1h 40min ago
        agent_name: 'CoderAgent',
        operation_type: 'api_integration',
        execution_time_ms: 456.78,
        principles_evaluated: 5,
        issues_found: 1,
        severity_breakdown: { medium: 1 },
        requires_revision: true,
        revised: true,
        hitl_required: false,
        hitl_approved: null,
        approved_by: null,
        user_id: 'usr-w9x0y1z2',
        user_email: 'integrations@acme-corp.com',
        team_id: 'team-integrations',
        project_id: 'proj-crm-sync',
        repository: 'acme-corp/crm-integration',
        session_id: 'sess-2024-01-21-017',
        request_id: 'req-f2a3b4c5',
        parent_decision_id: null,
        critique_summary: 'API response handling does not account for rate limiting errors from external service.',
        revision_summary: 'Added exponential backoff retry logic with jitter for rate limit responses.',
        input_tokens: 2134,
        output_tokens: 1789,
      },
    ],
    total_count: 1247,
    has_more: true,
  },
};

/**
 * Wrapper to fall back to mock data in development mode
 */
async function withMockFallback(apiCall, mockData, label) {
  try {
    return await apiCall();
  } catch (error) {
    if (IS_DEV) {
      console.warn(`[Trust Center] ${label} API unavailable, using mock data:`, error.message);
      return mockData;
    }
    throw error;
  }
}

/**
 * Time periods for metrics queries
 */
export const MetricPeriods = {
  DAY: '24h',
  WEEK: '7d',
  MONTH: '30d',
};

/**
 * Get overall system status
 * @returns {Promise<Object>} System status including health, scores, and counts
 */
export async function getTrustCenterStatus() {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/trust-center/status`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.status,
    'Status'
  );
}

/**
 * Get constitutional AI principles
 * @param {Object} options - Query options
 * @param {string} [options.category] - Filter by category
 * @param {string} [options.severity] - Filter by severity
 * @param {boolean} [options.includeMetrics=false] - Include violation metrics
 * @returns {Promise<Array>} List of principles
 */
export async function getPrinciples(options = {}) {
  return withMockFallback(
    async () => {
      const params = new URLSearchParams();
      if (options.category) params.append('category', options.category);
      if (options.severity) params.append('severity', options.severity);
      if (options.includeMetrics) params.append('include_metrics', 'true');

      const url = `${API_BASE}/api/v1/trust-center/principles${params.toString() ? `?${params}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.principles.filter(p => {
      if (options.category && p.category !== options.category) return false;
      if (options.severity && p.severity !== options.severity) return false;
      return true;
    }),
    'Principles'
  );
}

/**
 * Get autonomy configuration
 * @param {string} [policyId] - Specific policy ID (optional)
 * @returns {Promise<Object>} Autonomy configuration
 */
export async function getAutonomyConfig(policyId = null) {
  return withMockFallback(
    async () => {
      const params = policyId ? `?policy_id=${policyId}` : '';
      const response = await fetch(`${API_BASE}/api/v1/trust-center/autonomy${params}`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.autonomy,
    'Autonomy'
  );
}

/**
 * Get safety metrics for the specified period
 * @param {string} period - Time period ('24h', '7d', '30d')
 * @returns {Promise<Object>} Metrics snapshot
 */
export async function getSafetyMetrics(period = MetricPeriods.DAY) {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/trust-center/metrics?period=${period}`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    { ...MOCK_DATA.metrics, period },
    'Metrics'
  );
}

/**
 * Get audit decisions with pagination
 * @param {Object} options - Query options
 * @param {number} [options.limit=50] - Maximum results
 * @param {number} [options.offset=0] - Pagination offset
 * @param {string} [options.agentName] - Filter by agent name
 * @param {string} [options.startTime] - Filter by start time (ISO format)
 * @param {string} [options.endTime] - Filter by end time (ISO format)
 * @returns {Promise<Object>} Paginated decision list
 */
export async function getAuditDecisions(options = {}) {
  return withMockFallback(
    async () => {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.agentName) params.append('agent_name', options.agentName);
      if (options.startTime) params.append('start_time', options.startTime);
      if (options.endTime) params.append('end_time', options.endTime);

      const url = `${API_BASE}/api/v1/trust-center/decisions${params.toString() ? `?${params}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.decisions,
    'Decisions'
  );
}

/**
 * Export Trust Center data
 * @param {Object} options - Export options
 * @param {string} [options.format='json'] - Export format ('json' or 'pdf')
 * @param {string} [options.period='24h'] - Time period
 * @returns {Promise<Object>} Export metadata
 */
export async function exportTrustCenterData(options = {}) {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/trust-center/export`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          format: options.format || 'json',
          period: options.period || '24h',
        }),
      });
      return handleResponse(response);
    },
    { export_id: 'mock-export-001', status: 'completed', format: options.format || 'json', download_url: '#' },
    'Export'
  );
}

/**
 * Get full export data by export ID
 * @param {string} exportId - Export ID from export request
 * @returns {Promise<Object>} Full export data
 */
export async function getExportData(exportId) {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/trust-center/export/${exportId}/data`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    { ...MOCK_DATA, export_id: exportId },
    'ExportData'
  );
}

/**
 * Helper to format metric status
 * @param {Object} metric - Metric object
 * @returns {string} Status color class
 */
export function getMetricStatusColor(metric) {
  if (!metric) return 'surface';
  switch (metric.status) {
    case 'healthy':
      return 'olive';
    case 'warning':
      return 'warning';
    case 'critical':
      return 'critical';
    default:
      return 'surface';
  }
}

/**
 * Helper to format trend direction
 * @param {string} trend - Trend direction
 * @returns {Object} Trend icon and color
 */
export function getTrendInfo(trend) {
  switch (trend) {
    case 'improving':
      return { direction: 'up', color: 'olive' };
    case 'degrading':
      return { direction: 'down', color: 'critical' };
    case 'stable':
    default:
      return { direction: 'neutral', color: 'surface' };
  }
}

/**
 * Helper to format severity badge
 * @param {string} severity - Severity level
 * @returns {string} Badge color class
 */
export function getSeverityColor(severity) {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return 'critical';
    case 'high':
      return 'warning';
    case 'medium':
      return 'aura';
    case 'low':
    default:
      return 'surface';
  }
}

/**
 * Helper to format category for display
 * @param {string} category - Category name
 * @returns {string} Formatted category
 */
export function formatCategory(category) {
  if (!category) return 'Unknown';
  return category
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export default {
  getTrustCenterStatus,
  getPrinciples,
  getAutonomyConfig,
  getSafetyMetrics,
  getAuditDecisions,
  exportTrustCenterData,
  getExportData,
  getMetricStatusColor,
  getTrendInfo,
  getSeverityColor,
  formatCategory,
  MetricPeriods,
};
