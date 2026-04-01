/**
 * Vulnerability Scanner Mock Data
 *
 * Provides realistic mock data for all ADR-084 dashboard widgets
 * and pages during development.
 *
 * @module services/vulnScannerMockData
 */

// Pipeline stages in order
export const PIPELINE_STAGES = [
  'DISCOVERY',
  'EXTRACTION',
  'CANDIDATE_SELECTION',
  'LLM_ANALYSIS',
  'VERIFICATION',
  'DEDUP_TRIAGE',
  'CLEANUP',
];

// Severity levels
export const SEVERITY_LEVELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];

// Scan depth options
export const SCAN_DEPTHS = [
  { value: 'SURFACE', label: 'Surface', description: 'Quick scan of high-risk files only', estimatedCost: '$0.12' },
  { value: 'STANDARD', label: 'Standard', description: 'Balanced scan of common vulnerability patterns', estimatedCost: '$0.85' },
  { value: 'DEEP', label: 'Deep', description: 'Comprehensive analysis including dataflow tracking', estimatedCost: '$3.20' },
  { value: 'EXHAUSTIVE', label: 'Exhaustive', description: 'Full codebase analysis with all detection engines', estimatedCost: '$8.50' },
];

// Autonomy levels
export const AUTONOMY_LEVELS = [
  { value: 'FULL_HITL', label: 'Full HITL', description: 'All findings require human approval' },
  { value: 'CRITICAL_HITL', label: 'Critical HITL', description: 'Only critical/high findings require approval' },
  { value: 'AUDIT_ONLY', label: 'Audit Only', description: 'Findings logged but no patches applied' },
  { value: 'FULL_AUTONOMOUS', label: 'Full Autonomous', description: 'Auto-apply verified fixes (confidence > 95%)' },
];

// Supported languages
export const SUPPORTED_LANGUAGES = [
  'Python', 'JavaScript', 'TypeScript', 'Java', 'Go',
  'Rust', 'C', 'C++', 'C#', 'Ruby',
  'PHP', 'Swift', 'Kotlin', 'Scala', 'Terraform',
];

/**
 * Mock: Findings by Severity (stacked bar chart)
 */
export const MOCK_FINDINGS_BY_SEVERITY = {
  summary: { CRITICAL: 7, HIGH: 23, MEDIUM: 45, LOW: 31, INFO: 12 },
  total: 118,
  timeSeries: [
    { date: '2026-02-15', CRITICAL: 3, HIGH: 8, MEDIUM: 12, LOW: 10, INFO: 4 },
    { date: '2026-02-16', CRITICAL: 5, HIGH: 10, MEDIUM: 14, LOW: 9, INFO: 5 },
    { date: '2026-02-17', CRITICAL: 4, HIGH: 12, MEDIUM: 18, LOW: 11, INFO: 3 },
    { date: '2026-02-18', CRITICAL: 6, HIGH: 15, MEDIUM: 20, LOW: 14, INFO: 6 },
    { date: '2026-02-19', CRITICAL: 5, HIGH: 18, MEDIUM: 28, LOW: 18, INFO: 8 },
    { date: '2026-02-20', CRITICAL: 8, HIGH: 21, MEDIUM: 38, LOW: 25, INFO: 10 },
    { date: '2026-02-21', CRITICAL: 7, HIGH: 23, MEDIUM: 45, LOW: 31, INFO: 12 },
  ],
};

/**
 * Mock: Active Scans
 */
export const MOCK_ACTIVE_SCANS = {
  count: 3,
  scans: [
    {
      scan_id: 'scan-a1b2c3',
      repository: 'aura-core',
      branch: 'main',
      current_stage: 'LLM_ANALYSIS',
      stage_index: 3,
      progress_pct: 62,
      started_at: '2026-02-21T10:15:00Z',
    },
    {
      scan_id: 'scan-d4e5f6',
      repository: 'aura-frontend',
      branch: 'feature/dashboard',
      current_stage: 'EXTRACTION',
      stage_index: 1,
      progress_pct: 28,
      started_at: '2026-02-21T10:42:00Z',
    },
    {
      scan_id: 'scan-g7h8i9',
      repository: 'infra-templates',
      branch: 'develop',
      current_stage: 'VERIFICATION',
      stage_index: 4,
      progress_pct: 85,
      started_at: '2026-02-21T09:30:00Z',
    },
  ],
};

/**
 * Mock: Scan Pipeline Progress (for a single scan)
 */
export const MOCK_PIPELINE_PROGRESS = {
  scan_id: 'scan-a1b2c3',
  stages: [
    { name: 'DISCOVERY', status: 'complete', items_total: 1247, items_processed: 1247, duration_ms: 3200 },
    { name: 'EXTRACTION', status: 'complete', items_total: 438, items_processed: 438, duration_ms: 8700 },
    { name: 'CANDIDATE_SELECTION', status: 'complete', items_total: 438, items_processed: 438, duration_ms: 2100 },
    { name: 'LLM_ANALYSIS', status: 'running', items_total: 87, items_processed: 54, duration_ms: 42000 },
    { name: 'VERIFICATION', status: 'pending', items_total: 0, items_processed: 0, duration_ms: 0 },
    { name: 'DEDUP_TRIAGE', status: 'pending', items_total: 0, items_processed: 0, duration_ms: 0 },
    { name: 'CLEANUP', status: 'pending', items_total: 0, items_processed: 0, duration_ms: 0 },
  ],
};

/**
 * Mock: True Positive Rate
 */
export const MOCK_TRUE_POSITIVE_RATE = {
  rate: 87.3,
  trend: 2.1,
  total_verified: 312,
  true_positives: 272,
  false_positives: 40,
};

/**
 * Mock: LLM Token Spend
 */
export const MOCK_LLM_TOKEN_SPEND = {
  daily_tokens: 284500,
  daily_cost_usd: 4.27,
  monthly_tokens: 6832000,
  monthly_cost_usd: 102.48,
  trend_pct: -8.3,
  model_breakdown: [
    { model: 'claude-3.5-sonnet', tokens: 198000, cost_usd: 2.97 },
    { model: 'claude-3-haiku', tokens: 86500, cost_usd: 1.30 },
  ],
};

/**
 * Mock: Scanner Alarm Status
 */
export const MOCK_ALARM_STATUS = {
  alarms: [
    { name: 'ScanFailureRate', status: 'OK', last_checked: '2026-02-21T10:50:00Z' },
    { name: 'LLMLatencyP99', status: 'OK', last_checked: '2026-02-21T10:50:00Z' },
    { name: 'FindingBacklog', status: 'ALARM', last_checked: '2026-02-21T10:48:00Z', threshold: 50, current_value: 67 },
    { name: 'TokenBudgetUsage', status: 'WARNING', last_checked: '2026-02-21T10:50:00Z', threshold: 80, current_value: 78 },
    { name: 'QueueDepth', status: 'OK', last_checked: '2026-02-21T10:50:00Z' },
  ],
};

/**
 * Mock: Recent Scan Activity
 */
export const MOCK_RECENT_ACTIVITY = {
  activities: [
    { id: 'act-001', scan_id: 'scan-x1', type: 'scan_completed', repository: 'aura-core', severity_summary: { CRITICAL: 2, HIGH: 5 }, timestamp: '2026-02-21T10:30:00Z', duration_ms: 185000 },
    { id: 'act-002', scan_id: 'scan-x2', type: 'finding_triaged', repository: 'aura-frontend', finding_title: 'SQL Injection in user search', severity: 'CRITICAL', timestamp: '2026-02-21T10:25:00Z' },
    { id: 'act-003', scan_id: 'scan-x3', type: 'scan_started', repository: 'infra-templates', depth: 'DEEP', timestamp: '2026-02-21T10:20:00Z' },
    { id: 'act-004', scan_id: 'scan-x4', type: 'fix_applied', repository: 'aura-api', finding_title: 'XSS via unsanitized input', severity: 'HIGH', timestamp: '2026-02-21T10:15:00Z' },
    { id: 'act-005', scan_id: 'scan-x5', type: 'scan_completed', repository: 'auth-service', severity_summary: { HIGH: 1, MEDIUM: 3 }, timestamp: '2026-02-21T10:00:00Z', duration_ms: 92000 },
    { id: 'act-006', scan_id: 'scan-x6', type: 'scan_failed', repository: 'legacy-parser', error: 'Timeout after 600s', timestamp: '2026-02-21T09:45:00Z' },
    { id: 'act-007', scan_id: 'scan-x7', type: 'finding_triaged', repository: 'aura-core', finding_title: 'Path Traversal in file handler', severity: 'HIGH', timestamp: '2026-02-21T09:30:00Z' },
    { id: 'act-008', scan_id: 'scan-x8', type: 'scan_completed', repository: 'payment-service', severity_summary: { MEDIUM: 2, LOW: 5 }, timestamp: '2026-02-21T09:15:00Z', duration_ms: 145000 },
  ],
};

/**
 * Mock: Findings Requiring Approval
 */
export const MOCK_FINDINGS_REQUIRING_APPROVAL = {
  count: 14,
  trend: 3,
  by_severity: { CRITICAL: 4, HIGH: 7, MEDIUM: 3 },
};

/**
 * Mock: Scan Duration Trend
 */
export const MOCK_SCAN_DURATION_TREND = {
  data: [
    { date: '2026-02-15', avg_duration_s: 142, p50_s: 120, p95_s: 280 },
    { date: '2026-02-16', avg_duration_s: 155, p50_s: 130, p95_s: 310 },
    { date: '2026-02-17', avg_duration_s: 138, p50_s: 115, p95_s: 265 },
    { date: '2026-02-18', avg_duration_s: 162, p50_s: 140, p95_s: 320 },
    { date: '2026-02-19', avg_duration_s: 148, p50_s: 125, p95_s: 290 },
    { date: '2026-02-20', avg_duration_s: 135, p50_s: 110, p95_s: 250 },
    { date: '2026-02-21', avg_duration_s: 130, p50_s: 108, p95_s: 245 },
  ],
};

/**
 * Mock: Stage Duration Waterfall
 */
export const MOCK_STAGE_DURATION = {
  stages: [
    { name: 'DISCOVERY', avg_ms: 3200, pct: 4 },
    { name: 'EXTRACTION', avg_ms: 8700, pct: 10 },
    { name: 'CANDIDATE_SELECTION', avg_ms: 2100, pct: 2 },
    { name: 'LLM_ANALYSIS', avg_ms: 52000, pct: 60 },
    { name: 'VERIFICATION', avg_ms: 12500, pct: 14 },
    { name: 'DEDUP_TRIAGE', avg_ms: 5800, pct: 7 },
    { name: 'CLEANUP', avg_ms: 2700, pct: 3 },
  ],
  total_avg_ms: 87000,
};

/**
 * Mock: Findings by CWE
 */
export const MOCK_FINDINGS_BY_CWE = {
  categories: [
    { cwe_id: 'CWE-79', name: 'Cross-site Scripting', count: 18 },
    { cwe_id: 'CWE-89', name: 'SQL Injection', count: 12 },
    { cwe_id: 'CWE-22', name: 'Path Traversal', count: 9 },
    { cwe_id: 'CWE-78', name: 'OS Command Injection', count: 7 },
    { cwe_id: 'CWE-502', name: 'Deserialization', count: 6 },
    { cwe_id: 'CWE-798', name: 'Hardcoded Credentials', count: 5 },
    { cwe_id: 'CWE-918', name: 'SSRF', count: 4 },
    { cwe_id: 'CWE-327', name: 'Broken Crypto', count: 3 },
  ],
};

/**
 * Mock: LLM Latency
 */
export const MOCK_LLM_LATENCY = {
  data: [
    { timestamp: '2026-02-21T08:00:00Z', p50_ms: 850, p95_ms: 2200, p99_ms: 4100 },
    { timestamp: '2026-02-21T09:00:00Z', p50_ms: 920, p95_ms: 2400, p99_ms: 4500 },
    { timestamp: '2026-02-21T10:00:00Z', p50_ms: 880, p95_ms: 2150, p99_ms: 3900 },
    { timestamp: '2026-02-21T10:15:00Z', p50_ms: 910, p95_ms: 2300, p99_ms: 4200 },
    { timestamp: '2026-02-21T10:30:00Z', p50_ms: 870, p95_ms: 2100, p99_ms: 3800 },
    { timestamp: '2026-02-21T10:45:00Z', p50_ms: 840, p95_ms: 2050, p99_ms: 3700 },
  ],
  current: { p50_ms: 840, p95_ms: 2050, p99_ms: 3700 },
};

/**
 * Mock: Concurrent Scan Utilization
 */
export const MOCK_CONCURRENT_UTILIZATION = {
  active: 3,
  max: 5,
  utilization_pct: 60,
  queue_depth: 2,
};

/**
 * Mock: Critical Findings Trend (30d)
 */
export const MOCK_CRITICAL_FINDINGS_TREND = {
  data: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(2026, 1, i + 1).toISOString().split('T')[0],
    count: Math.max(0, Math.floor(Math.random() * 8) + (i > 20 ? 3 : 1)),
  })),
};

/**
 * Mock: Scan Queue Depth
 */
export const MOCK_SCAN_QUEUE_DEPTH = {
  depth: 2,
  trend: -1,
  oldest_queued_at: '2026-02-21T10:35:00Z',
};

/**
 * Mock: Candidate Filter Funnel
 */
export const MOCK_CANDIDATE_FUNNEL = {
  stages: [
    { name: 'Files Discovered', count: 1247 },
    { name: 'Code Units Extracted', count: 438 },
    { name: 'Candidates Identified', count: 87 },
    { name: 'Findings Confirmed', count: 23 },
  ],
};

/**
 * Mock: Findings by Language
 */
export const MOCK_FINDINGS_BY_LANGUAGE = {
  languages: [
    { name: 'Python', count: 42, pct: 35.6 },
    { name: 'JavaScript', count: 28, pct: 23.7 },
    { name: 'TypeScript', count: 18, pct: 15.3 },
    { name: 'Java', count: 14, pct: 11.9 },
    { name: 'Go', count: 9, pct: 7.6 },
    { name: 'Other', count: 7, pct: 5.9 },
  ],
};

/**
 * Mock: Verification Status Distribution
 */
export const MOCK_VERIFICATION_STATUS = {
  statuses: [
    { name: 'Verified True Positive', count: 72, pct: 61 },
    { name: 'Verified False Positive', count: 15, pct: 12.7 },
    { name: 'Pending Verification', count: 18, pct: 15.3 },
    { name: 'Skipped', count: 13, pct: 11 },
  ],
};

/**
 * Mock: Cleanup Activity
 */
export const MOCK_CLEANUP_ACTIVITY = {
  data: [
    { date: '2026-02-15', temp_files_cleaned: 45, caches_cleared: 12, artifacts_archived: 8 },
    { date: '2026-02-16', temp_files_cleaned: 38, caches_cleared: 10, artifacts_archived: 5 },
    { date: '2026-02-17', temp_files_cleaned: 52, caches_cleared: 15, artifacts_archived: 11 },
    { date: '2026-02-18', temp_files_cleaned: 41, caches_cleared: 8, artifacts_archived: 6 },
    { date: '2026-02-19', temp_files_cleaned: 60, caches_cleared: 18, artifacts_archived: 14 },
    { date: '2026-02-20', temp_files_cleaned: 35, caches_cleared: 9, artifacts_archived: 7 },
    { date: '2026-02-21', temp_files_cleaned: 48, caches_cleared: 13, artifacts_archived: 9 },
  ],
};

/**
 * Mock: Scan Depth Distribution
 */
export const MOCK_SCAN_DEPTH_DISTRIBUTION = {
  depths: [
    { name: 'SURFACE', count: 45, pct: 30 },
    { name: 'STANDARD', count: 68, pct: 45.3 },
    { name: 'DEEP', count: 28, pct: 18.7 },
    { name: 'EXHAUSTIVE', count: 9, pct: 6 },
  ],
};

/**
 * Mock: Full Scan Detail
 */
export const MOCK_SCAN_DETAIL = {
  scan_id: 'scan-a1b2c3d4',
  repository: 'https://github.com/aenealabs/aura-core',
  branch: 'main',
  commit_sha: 'c87350b7e2a1',
  depth: 'DEEP',
  autonomy_level: 'CRITICAL_HITL',
  requested_by: 'jane.smith@aenealabs.com',
  started_at: '2026-02-21T09:30:00Z',
  completed_at: '2026-02-21T09:33:05Z',
  status: 'completed',
  files_discovered: 1247,
  code_units_extracted: 438,
  candidates_identified: 87,
  findings_count: 23,
  llm_tokens_consumed: 284500,
  llm_cost_usd: 4.27,
  pipeline: MOCK_PIPELINE_PROGRESS.stages.map((s) => ({ ...s, status: 'complete' })),
  findings: [
    {
      finding_id: 'find-001',
      title: 'SQL Injection in user search endpoint',
      severity: 'CRITICAL',
      confidence: 0.96,
      cwe_id: 'CWE-89',
      cwe_name: 'SQL Injection',
      file_path: 'src/api/users/search.py',
      start_line: 42,
      end_line: 58,
      verification_status: 'verified_true_positive',
      affected_code: 'query = f"SELECT * FROM users WHERE name LIKE \'%{search_term}%\'"',
      llm_reasoning: 'The search_term parameter is directly interpolated into the SQL query string without parameterization. An attacker can inject arbitrary SQL by providing a crafted search term such as: %\' OR 1=1; DROP TABLE users; --',
      suggested_fix: 'query = "SELECT * FROM users WHERE name LIKE %s"\ncursor.execute(query, (f"%{search_term}%",))',
      dataflow: {
        source: { type: 'HTTP_PARAM', location: 'request.args["q"]', line: 35 },
        propagators: [
          { type: 'ASSIGN', location: 'search_term = request.args["q"]', line: 36 },
          { type: 'FORMAT', location: 'f"...{search_term}..."', line: 42 },
        ],
        sink: { type: 'SQL_EXEC', location: 'cursor.execute(query)', line: 43 },
      },
    },
    {
      finding_id: 'find-002',
      title: 'Cross-site Scripting in comment display',
      severity: 'HIGH',
      confidence: 0.91,
      cwe_id: 'CWE-79',
      cwe_name: 'Cross-site Scripting (XSS)',
      file_path: 'src/frontend/components/CommentList.jsx',
      start_line: 28,
      end_line: 32,
      verification_status: 'pending',
      affected_code: '<div dangerouslySetInnerHTML={{ __html: comment.body }} />',
      llm_reasoning: 'The comment body is rendered using dangerouslySetInnerHTML without sanitization. User-controlled HTML content can execute arbitrary JavaScript in the browser.',
      suggested_fix: 'import DOMPurify from "dompurify";\n<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(comment.body) }} />',
    },
    {
      finding_id: 'find-003',
      title: 'Path Traversal in file download',
      severity: 'HIGH',
      confidence: 0.88,
      cwe_id: 'CWE-22',
      cwe_name: 'Path Traversal',
      file_path: 'src/api/files/download.py',
      start_line: 15,
      end_line: 22,
      verification_status: 'verified_true_positive',
    },
    {
      finding_id: 'find-004',
      title: 'Hardcoded API key in configuration',
      severity: 'MEDIUM',
      confidence: 0.94,
      cwe_id: 'CWE-798',
      cwe_name: 'Use of Hardcoded Credentials',
      file_path: 'src/config/integrations.py',
      start_line: 8,
      end_line: 8,
      verification_status: 'verified_true_positive',
    },
    {
      finding_id: 'find-005',
      title: 'Missing rate limiting on auth endpoint',
      severity: 'MEDIUM',
      confidence: 0.72,
      cwe_id: 'CWE-307',
      cwe_name: 'Improper Restriction of Excessive Authentication Attempts',
      file_path: 'src/api/auth/login.py',
      start_line: 30,
      end_line: 55,
      verification_status: 'pending',
    },
  ],
  errors: [],
};

/**
 * Mock: Full Finding Detail (for drawer)
 */
export const MOCK_FINDING_DETAIL = MOCK_SCAN_DETAIL.findings[0];
