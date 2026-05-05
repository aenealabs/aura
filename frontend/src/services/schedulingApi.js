/**
 * Scheduling API Service
 *
 * Client for job scheduling and queue management API.
 * ADR-055: Agent Scheduling View and Job Queue Management
 */

const API_URL = import.meta.env.VITE_API_URL || '';
const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true' || (import.meta.env.DEV && !import.meta.env.VITE_API_URL);

// Mock data for development - Production-realistic scheduled job data
const mockScheduledJobs = [
  // CRITICAL priority jobs
  {
    schedule_id: 'sched-8a2b3c4d',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'VULNERABILITY_ASSESSMENT',
    job_title: 'Critical CVE-2026-1234 Assessment - Core Services',
    scheduled_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    created_by: 'usr-j5k6l7m8',
    created_by_email: 'james.wilson@acme-corp.com',
    created_by_name: 'James Wilson',
    status: 'PENDING',
    priority: 'CRITICAL',
    repository_id: 'repo-aura-core-1a2',
    repository_name: 'aura-core',
    repository_url: 'https://github.com/acme-corp/aura-core',
    description: 'Critical CVE-2026-1234 assessment for core services - RCE vulnerability in XML parser',
    target_branch: 'main',
    estimated_duration_minutes: 45,
    cost_estimate_usd: 2.50,
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    project_id: 'proj-vuln-mgmt-4k8',
    project_name: 'Vulnerability Management',
    tags: ['critical', 'cve-2026-1234', 'xml-parser', 'rce'],
    session_id: 'sess-sched-9n0p1q2r',
    request_id: 'req-4e5f6g7h8i9j',
  },
  {
    schedule_id: 'sched-5e6f7g8h',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'THREAT_ANALYSIS',
    job_title: 'Emergency Threat Scan - Auth Service Anomaly',
    scheduled_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    created_by: 'usr-n1o2p3q4',
    created_by_email: 'nina.patel@acme-corp.com',
    created_by_name: 'Nina Patel',
    status: 'DISPATCHED',
    priority: 'CRITICAL',
    repository_id: 'repo-auth-svc-3c4',
    repository_name: 'auth-service',
    repository_url: 'https://github.com/acme-corp/auth-service',
    description: 'Emergency threat scan after anomaly detection - unusual login patterns from 3 IPs',
    target_branch: 'main',
    estimated_duration_minutes: 30,
    cost_estimate_usd: 1.80,
    dispatched_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
    dispatched_job_id: 'job-threat-7a8b9c0d',
    execution_node: 'agent-worker-03',
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    project_id: 'proj-threat-intel-2m4',
    project_name: 'Threat Intelligence',
    tags: ['critical', 'anomaly', 'auth', 'emergency'],
    session_id: 'sess-sched-3s4t5u6v',
    request_id: 'req-0k1l2m3n4o5p',
  },
  // HIGH priority jobs
  {
    schedule_id: 'sched-9i0j1k2l',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'SECURITY_SCAN',
    job_title: 'Weekly Security Scan - API Service',
    scheduled_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString(),
    created_by: 'usr-m3k8n2p5',
    created_by_email: 'marcus.johnson@acme-corp.com',
    created_by_name: 'Marcus Johnson',
    status: 'PENDING',
    priority: 'HIGH',
    repository_id: 'repo-aura-api-5e6',
    repository_name: 'aura-api',
    repository_url: 'https://github.com/acme-corp/aura-api',
    description: 'Weekly security scan for API service - OWASP Top 10 + SANS 25',
    target_branch: 'main',
    estimated_duration_minutes: 60,
    cost_estimate_usd: 3.20,
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    project_id: 'proj-api-security-1n3',
    project_name: 'API Security Hardening',
    tags: ['weekly', 'owasp', 'sans-25', 'api'],
    session_id: 'sess-sched-7w8x9y0z',
    request_id: 'req-6q7r8s9t0u1v',
  },
  {
    schedule_id: 'sched-3m4n5o6p',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'PATCH_GENERATION',
    job_title: 'OWASP Findings Patch - Payment Gateway',
    scheduled_at: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-r5s6t7u8',
    created_by_email: 'rachel.torres@acme-corp.com',
    created_by_name: 'Rachel Torres',
    status: 'PENDING',
    priority: 'HIGH',
    repository_id: 'repo-payment-gw-7f8',
    repository_name: 'payment-gateway',
    repository_url: 'https://github.com/acme-corp/payment-gateway',
    description: 'Generate patches for 5 OWASP findings in payment module - SQL injection, XSS',
    target_branch: 'develop',
    estimated_duration_minutes: 90,
    cost_estimate_usd: 4.50,
    findings_count: 5,
    finding_severities: { critical: 1, high: 2, medium: 2, low: 0 },
    team_id: 'team-payments',
    team_name: 'Payments Team',
    project_id: 'proj-pci-compliance-8p2',
    project_name: 'PCI DSS Compliance',
    tags: ['owasp', 'sql-injection', 'xss', 'payments', 'pci'],
    session_id: 'sess-sched-1a2b3c4d',
    request_id: 'req-2w3x4y5z6a7b',
  },
  {
    schedule_id: 'sched-7q8r9s0t',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'COMPLIANCE_CHECK',
    job_title: 'SOC2 Compliance Validation - Organization-wide',
    scheduled_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-v9w0x1y2',
    created_by_email: 'victoria.chang@acme-corp.com',
    created_by_name: 'Victoria Chang',
    status: 'DISPATCHED',
    priority: 'HIGH',
    repository_id: null,
    repository_name: 'All Repositories',
    description: 'SOC2 Type II compliance validation across all 47 repositories',
    target_branch: null,
    estimated_duration_minutes: 120,
    cost_estimate_usd: 8.00,
    dispatched_at: new Date(Date.now() - 28 * 60 * 1000).toISOString(),
    dispatched_job_id: 'job-compliance-2e3f4g5h',
    execution_node: 'agent-worker-01',
    compliance_frameworks: ['SOC2', 'CMMC', 'NIST-800-53'],
    repositories_scanned: 47,
    team_id: 'team-compliance',
    team_name: 'Compliance & Governance',
    project_id: 'proj-soc2-audit-5r7',
    project_name: 'SOC2 Type II Audit 2026',
    tags: ['soc2', 'cmmc', 'nist', 'audit', 'org-wide'],
    session_id: 'sess-sched-5e6f7g8h',
    request_id: 'req-8c9d0e1f2g3h',
  },
  // NORMAL priority jobs
  {
    schedule_id: 'sched-1u2v3w4x',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'CODE_REVIEW',
    job_title: 'Automated Code Review - React Components',
    scheduled_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString(),
    created_by: 'usr-m3k8n2p5',
    created_by_email: 'marcus.johnson@acme-corp.com',
    created_by_name: 'Marcus Johnson',
    status: 'PENDING',
    priority: 'NORMAL',
    repository_id: 'repo-frontend-app-8b2',
    repository_name: 'frontend-app',
    repository_url: 'https://github.com/acme-corp/frontend-app',
    description: 'Automated code review for React components - PR #347, #352, #355',
    target_branch: 'feature/dashboard-v2',
    estimated_duration_minutes: 25,
    cost_estimate_usd: 1.20,
    pull_request_ids: [347, 352, 355],
    files_to_review: 28,
    team_id: 'team-frontend',
    team_name: 'Frontend Engineering',
    project_id: 'proj-dashboard-v2-3t5',
    project_name: 'Dashboard V2 Redesign',
    tags: ['code-review', 'react', 'frontend', 'pr-review'],
    session_id: 'sess-sched-9i0j1k2l',
    request_id: 'req-4i5j6k7l8m9n',
  },
  {
    schedule_id: 'sched-5y6z7a8b',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'DEPENDENCY_UPDATE',
    job_title: 'NPM Security Patches - Shared Libraries',
    scheduled_at: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    created_by: 'usr-sys-depbot',
    created_by_email: 'dependabot@acme-corp.com',
    created_by_name: 'Dependency Bot',
    status: 'PENDING',
    priority: 'NORMAL',
    repository_id: 'repo-shared-libs-9c0',
    repository_name: 'shared-libs',
    repository_url: 'https://github.com/acme-corp/shared-libs',
    description: 'Update 12 npm dependencies with security patches - lodash, axios, jsonwebtoken',
    target_branch: 'main',
    estimated_duration_minutes: 35,
    cost_estimate_usd: 1.80,
    dependencies_to_update: 12,
    security_advisories: ['GHSA-9f4q-7abc', 'GHSA-2h5k-mdef', 'GHSA-7x9p-ghij'],
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    project_id: 'proj-dep-mgmt-6u8',
    project_name: 'Dependency Management',
    tags: ['dependencies', 'npm', 'security-patches', 'automated'],
    session_id: 'sess-sched-3m4n5o6p',
    request_id: 'req-0o1p2q3r4s5t',
  },
  {
    schedule_id: 'sched-9c0d1e2f',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'REPOSITORY_INDEXING',
    job_title: 'GraphRAG Index Refresh - ML Pipeline',
    scheduled_at: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    created_by: 'usr-sys-scheduler',
    created_by_email: 'scheduler@acme-corp.com',
    created_by_name: 'System Scheduler',
    status: 'PENDING',
    priority: 'NORMAL',
    repository_id: 'repo-ml-pipeline-0d1',
    repository_name: 'ml-pipeline',
    repository_url: 'https://github.com/acme-corp/ml-pipeline',
    description: 'Re-index ML pipeline repository for GraphRAG - 2,847 files, Neptune + OpenSearch',
    target_branch: 'main',
    estimated_duration_minutes: 40,
    cost_estimate_usd: 2.10,
    files_to_index: 2847,
    index_targets: ['neptune-graph', 'opensearch-vector'],
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    project_id: 'proj-graphrag-7v9',
    project_name: 'GraphRAG Infrastructure',
    tags: ['indexing', 'graphrag', 'neptune', 'opensearch', 'ml'],
    session_id: 'sess-sched-7q8r9s0t',
    request_id: 'req-6u7v8w9x0y1z',
  },
  {
    schedule_id: 'sched-3g4h5i6j',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'CODE_QUALITY_SCAN',
    job_title: 'Quarterly Code Quality Assessment - Data Service',
    scheduled_at: new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString(),
    created_by: 'usr-z3a4b5c6',
    created_by_email: 'zoe.martinez@acme-corp.com',
    created_by_name: 'Zoe Martinez',
    status: 'PENDING',
    priority: 'NORMAL',
    repository_id: 'repo-data-svc-2e3',
    repository_name: 'data-service',
    repository_url: 'https://github.com/acme-corp/data-service',
    description: 'Quarterly code quality assessment - complexity, duplication, test coverage metrics',
    target_branch: 'main',
    estimated_duration_minutes: 55,
    cost_estimate_usd: 2.80,
    quality_metrics: ['complexity', 'duplication', 'coverage', 'maintainability'],
    threshold_targets: { complexity: 10, duplication: 3, coverage: 80 },
    team_id: 'team-qa',
    team_name: 'Quality Assurance',
    project_id: 'proj-code-health-8w0',
    project_name: 'Code Health Initiative',
    tags: ['code-quality', 'quarterly', 'metrics', 'qa'],
    session_id: 'sess-sched-1u2v3w4x',
    request_id: 'req-2a3b4c5d6e7f',
  },
  // LOW priority jobs
  {
    schedule_id: 'sched-7k8l9m0n',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'PERFORMANCE_ANALYSIS',
    job_title: 'Monthly Performance Benchmarking - Core Services',
    scheduled_at: new Date(Date.now() + 72 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    created_by: 'usr-d7e8f9g0',
    created_by_email: 'derek.wong@acme-corp.com',
    created_by_name: 'Derek Wong',
    status: 'PENDING',
    priority: 'LOW',
    repository_id: 'repo-aura-core-1a2',
    repository_name: 'aura-core',
    repository_url: 'https://github.com/acme-corp/aura-core',
    description: 'Monthly performance benchmarking - latency, throughput, memory profiling',
    target_branch: 'main',
    estimated_duration_minutes: 180,
    cost_estimate_usd: 9.50,
    benchmark_suites: ['latency', 'throughput', 'memory', 'cpu'],
    comparison_baseline: 'v2.4.0',
    team_id: 'team-performance',
    team_name: 'Performance Engineering',
    project_id: 'proj-perf-opt-9x1',
    project_name: 'Performance Optimization',
    tags: ['performance', 'monthly', 'benchmarking', 'profiling'],
    session_id: 'sess-sched-5y6z7a8b',
    request_id: 'req-8g9h0i1j2k3l',
  },
  // Completed jobs for history
  {
    schedule_id: 'sched-1o2p3q4r',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'SECURITY_SCAN',
    job_title: 'Completed Security Scan - API Service',
    scheduled_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-n1o2p3q4',
    created_by_email: 'nina.patel@acme-corp.com',
    created_by_name: 'Nina Patel',
    status: 'SUCCEEDED',
    priority: 'HIGH',
    repository_id: 'repo-aura-api-5e6',
    repository_name: 'aura-api',
    repository_url: 'https://github.com/acme-corp/aura-api',
    description: 'Completed security scan - 3 findings remediated, 0 critical remaining',
    target_branch: 'main',
    estimated_duration_minutes: 45,
    actual_duration_minutes: 42,
    cost_actual_usd: 2.30,
    dispatched_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 3.5 * 60 * 60 * 1000).toISOString(),
    dispatched_job_id: 'job-scan-3h4i5j6k',
    execution_node: 'agent-worker-02',
    result_summary: {
      findings_total: 3,
      findings_remediated: 3,
      findings_remaining: 0,
      severity_breakdown: { critical: 0, high: 1, medium: 2, low: 0 },
    },
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    project_id: 'proj-api-security-1n3',
    project_name: 'API Security Hardening',
    tags: ['completed', 'security-scan', 'remediated'],
    session_id: 'sess-sched-9c0d1e2f',
    request_id: 'req-4m5n6o7p8q9r',
  },
  {
    schedule_id: 'sched-5s6t7u8v',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'CODE_REVIEW',
    job_title: 'Cancelled Code Review - Legacy Service',
    scheduled_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-r5s6t7u8',
    created_by_email: 'rachel.torres@acme-corp.com',
    created_by_name: 'Rachel Torres',
    status: 'CANCELLED',
    priority: 'NORMAL',
    repository_id: 'repo-legacy-svc-4f5',
    repository_name: 'legacy-service',
    repository_url: 'https://github.com/acme-corp/legacy-service',
    description: 'Cancelled - repository deprecated and migrated to microservices',
    target_branch: 'main',
    estimated_duration_minutes: 30,
    cost_estimate_usd: 1.50,
    cancelled_at: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(),
    cancelled_by: 'usr-h1i2j3k4',
    cancelled_by_email: 'henry.kim@acme-corp.com',
    cancelled_by_name: 'Henry Kim',
    cancellation_reason: 'Repository deprecated - migrated to microservices architecture',
    team_id: 'team-backend',
    team_name: 'Backend Engineering',
    project_id: 'proj-legacy-decom-0y2',
    project_name: 'Legacy Decommission',
    tags: ['cancelled', 'deprecated', 'legacy'],
    session_id: 'sess-sched-3g4h5i6j',
    request_id: 'req-0s1t2u3v4w5x',
  },
  {
    schedule_id: 'sched-9w0x1y2z',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    job_type: 'VULNERABILITY_ASSESSMENT',
    job_title: 'Failed Vulnerability Assessment - Mobile App',
    scheduled_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-j5k6l7m8',
    created_by_email: 'james.wilson@acme-corp.com',
    created_by_name: 'James Wilson',
    status: 'FAILED',
    priority: 'HIGH',
    repository_id: 'repo-mobile-app-6g7',
    repository_name: 'mobile-app',
    repository_url: 'https://github.com/acme-corp/mobile-app',
    description: 'Failed - repository access token expired, requires re-authentication',
    target_branch: 'main',
    estimated_duration_minutes: 60,
    cost_estimate_usd: 3.20,
    dispatched_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    dispatched_job_id: 'job-vuln-7l8m9n0o',
    execution_node: 'agent-worker-04',
    error_message: 'Repository access token expired. GitHub OAuth token for repo-mobile-app-6g7 needs refresh.',
    error_code: 'AUTH_TOKEN_EXPIRED',
    error_details: {
      token_expiry: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      required_scopes: ['repo', 'read:org'],
      resolution_steps: ['Navigate to Settings > Integrations', 'Re-authorize GitHub connection'],
    },
    retry_count: 2,
    max_retries: 3,
    team_id: 'team-mobile',
    team_name: 'Mobile Development',
    project_id: 'proj-mobile-sec-1z3',
    project_name: 'Mobile Security Initiative',
    tags: ['failed', 'auth-error', 'mobile', 'needs-attention'],
    session_id: 'sess-sched-7k8l9m0n',
    request_id: 'req-6y7z8a9b0c1d',
  },
];

// Production-realistic queue status metrics
const mockQueueStatus = {
  // Queue summary
  total_queued: 18,
  total_scheduled: 8,
  active_jobs: 4,
  pending_approval: 8,
  // Organization context
  organization_id: 'org-acme-corp-7x2',
  organization_name: 'Acme Corporation',
  // Breakdown by priority
  by_priority: {
    CRITICAL: 3,
    HIGH: 6,
    NORMAL: 7,
    LOW: 2,
  },
  // Breakdown by job type
  by_type: {
    SECURITY_SCAN: 5,
    CODE_REVIEW: 4,
    VULNERABILITY_ASSESSMENT: 3,
    DEPENDENCY_UPDATE: 2,
    COMPLIANCE_CHECK: 2,
    THREAT_ANALYSIS: 1,
    PATCH_GENERATION: 1,
  },
  // Breakdown by team
  by_team: {
    'team-security-ops': { queued: 5, running: 2 },
    'team-platform-eng': { queued: 4, running: 1 },
    'team-frontend': { queued: 3, running: 0 },
    'team-backend': { queued: 2, running: 1 },
    'team-compliance': { queued: 2, running: 0 },
    'team-mobile': { queued: 2, running: 0 },
  },
  // Wait time statistics
  avg_wait_time_seconds: 67.3,
  p50_wait_time_seconds: 45.0,
  p90_wait_time_seconds: 180.0,
  p99_wait_time_seconds: 420.0,
  // Throughput metrics
  throughput_per_hour: 31.5,
  throughput_trend: 'stable',
  throughput_delta_percent: 2.3,
  // Queue positions
  oldest_queued_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
  oldest_queued_job_id: 'sched-8a2b3c4d',
  next_scheduled_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
  next_scheduled_job_id: 'sched-8a2b3c4d',
  // Daily statistics
  jobs_completed_today: 47,
  jobs_failed_today: 2,
  jobs_cancelled_today: 1,
  success_rate_today: 0.94,
  avg_execution_time_seconds: 312,
  // Cost tracking
  cost_today_usd: 128.50,
  cost_mtd_usd: 2847.30,
  budget_limit_usd: 5000.00,
  budget_utilization_percent: 56.95,
  // Agent utilization
  agents_total: 8,
  agents_active: 4,
  agents_idle: 4,
  agent_utilization_percent: 50.0,
  // Health metrics
  queue_health: 'healthy',
  bottleneck_detected: false,
  starvation_alert: false,
  // Timestamp
  metrics_timestamp: new Date().toISOString(),
  metrics_window_minutes: 60,
};

const mockJobTypes = [
  { value: 'SECURITY_SCAN', label: 'Security Scan' },
  { value: 'CODE_REVIEW', label: 'Code Review' },
  { value: 'PATCH_GENERATION', label: 'Patch Generation' },
  { value: 'VULNERABILITY_ASSESSMENT', label: 'Vulnerability Assessment' },
  { value: 'DEPENDENCY_UPDATE', label: 'Dependency Update' },
  { value: 'REPOSITORY_INDEXING', label: 'Repository Indexing' },
  { value: 'COMPLIANCE_CHECK', label: 'Compliance Check' },
  { value: 'THREAT_ANALYSIS', label: 'Threat Analysis' },
  { value: 'CODE_QUALITY_SCAN', label: 'Code Quality Scan' },
  { value: 'PERFORMANCE_ANALYSIS', label: 'Performance Analysis' },
];

/**
 * Get auth headers for API requests
 */
function getAuthHeaders() {
  const tokens = localStorage.getItem('aura_auth_tokens');
  if (tokens) {
    try {
      const { accessToken } = JSON.parse(tokens);
      if (accessToken) {
        return { Authorization: `Bearer ${accessToken}` };
      }
    } catch {
      // Ignore parse errors
    }
  }
  return {};
}

/**
 * Make API request with error handling
 */
async function apiRequest(endpoint, options = {}) {
  const url = `${API_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Schedule API Functions

/**
 * Create a new scheduled job
 */
export async function createScheduledJob(jobData) {
  if (DEV_MODE) {
    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 500));

    const newJob = {
      schedule_id: `sched-${Date.now()}`,
      organization_id: 'org-default',
      ...jobData,
      created_at: new Date().toISOString(),
      created_by: 'dev-user',
      status: 'PENDING',
    };

    mockScheduledJobs.unshift(newJob);
    return newJob;
  }

  return apiRequest('/api/v1/schedule', {
    method: 'POST',
    body: JSON.stringify(jobData),
  });
}

/**
 * Get list of scheduled jobs
 */
export async function getScheduledJobs({ status, limit = 50, cursor } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    let jobs = [...mockScheduledJobs];
    if (status) {
      jobs = jobs.filter((j) => j.status === status);
    }

    return {
      jobs: jobs.slice(0, limit),
      next_cursor: null,
    };
  }

  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (limit) params.append('limit', limit.toString());
  if (cursor) params.append('cursor', cursor);

  return apiRequest(`/api/v1/schedule?${params.toString()}`);
}

/**
 * Get a specific scheduled job
 */
export async function getScheduledJob(scheduleId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const job = mockScheduledJobs.find((j) => j.schedule_id === scheduleId);
    if (!job) {
      throw new Error('Scheduled job not found');
    }
    return job;
  }

  return apiRequest(`/api/v1/schedule/${scheduleId}`);
}

/**
 * Reschedule a job to a new time
 */
export async function rescheduleJob(scheduleId, newScheduledAt) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const job = mockScheduledJobs.find((j) => j.schedule_id === scheduleId);
    if (!job) {
      throw new Error('Scheduled job not found');
    }
    if (job.status !== 'PENDING') {
      throw new Error(`Cannot reschedule job with status ${job.status}`);
    }

    job.scheduled_at = newScheduledAt;
    return job;
  }

  return apiRequest(`/api/v1/schedule/${scheduleId}`, {
    method: 'PUT',
    body: JSON.stringify({ scheduled_at: newScheduledAt }),
  });
}

/**
 * Cancel a scheduled job
 */
export async function cancelScheduledJob(scheduleId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const jobIndex = mockScheduledJobs.findIndex((j) => j.schedule_id === scheduleId);
    if (jobIndex === -1) {
      throw new Error('Scheduled job not found');
    }

    const job = mockScheduledJobs[jobIndex];
    if (job.status !== 'PENDING') {
      throw new Error(`Cannot cancel job with status ${job.status}`);
    }

    job.status = 'CANCELLED';
    job.cancelled_at = new Date().toISOString();
    job.cancelled_by = 'dev-user';

    return job;
  }

  return apiRequest(`/api/v1/schedule/${scheduleId}`, {
    method: 'DELETE',
  });
}

// Queue API Functions

/**
 * Get current queue status and metrics
 */
export async function getQueueStatus() {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Add some randomness to make it feel live
    return {
      ...mockQueueStatus,
      total_queued: mockQueueStatus.total_queued + Math.floor(Math.random() * 3),
      active_jobs: Math.max(1, mockQueueStatus.active_jobs + Math.floor(Math.random() * 3) - 1),
      avg_wait_time_seconds: mockQueueStatus.avg_wait_time_seconds + (Math.random() * 10 - 5),
    };
  }

  return apiRequest('/api/v1/queue/status');
}

// Timeline API Functions

/**
 * Get timeline entries for visualization
 */
export async function getTimeline({ startDate, endDate, includeScheduled = true, includeCompleted = true, limit = 200 } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    const entries = [];
    const now = new Date();

    // Add scheduled jobs
    if (includeScheduled) {
      mockScheduledJobs
        .filter((j) => j.status === 'PENDING')
        .forEach((job) => {
          entries.push({
            job_id: job.schedule_id,
            job_type: job.job_type,
            status: job.status,
            title: job.description || `${job.job_type.replace(/_/g, ' ')} Job`,
            scheduled_at: job.scheduled_at,
            repository_name: job.repository_id,
            created_by: job.created_by,
          });
        });
    }

    // Add some mock completed jobs
    if (includeCompleted) {
      for (let i = 0; i < 5; i++) {
        const completedAt = new Date(now.getTime() - (i + 1) * 60 * 60 * 1000);
        const startedAt = new Date(completedAt.getTime() - 5 * 60 * 1000);

        entries.push({
          job_id: `completed-${i}`,
          job_type: mockJobTypes[i % mockJobTypes.length].value,
          status: 'SUCCEEDED',
          title: `Completed ${mockJobTypes[i % mockJobTypes.length].label}`,
          started_at: startedAt.toISOString(),
          completed_at: completedAt.toISOString(),
          duration_seconds: 300,
          repository_name: `repo-${i + 1}`,
        });
      }
    }

    return {
      entries: entries.slice(0, limit),
      start_date: startDate || new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      end_date: endDate || new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    };
  }

  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  params.append('include_scheduled', includeScheduled.toString());
  params.append('include_completed', includeCompleted.toString());
  if (limit) params.append('limit', limit.toString());

  return apiRequest(`/api/v1/schedule/timeline?${params.toString()}`);
}

// Utility Functions

/**
 * Get available job types for scheduling
 */
export async function getJobTypes() {
  if (DEV_MODE) {
    return mockJobTypes;
  }

  return apiRequest('/api/v1/schedule/job-types');
}

/**
 * Format duration in human-readable format
 */
export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '-';

  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
}

/**
 * Format relative time (e.g., "in 2 hours", "5 minutes ago")
 */
export function formatRelativeTime(dateString) {
  if (!dateString) return '-';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMins = Math.round(diffMs / (1000 * 60));
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffMs > 0) {
    // Future
    if (diffMins < 60) return `in ${diffMins} min`;
    if (diffHours < 24) return `in ${diffHours} hr`;
    return `in ${diffDays} days`;
  } else {
    // Past
    const absMins = Math.abs(diffMins);
    const absHours = Math.abs(diffHours);
    const absDays = Math.abs(diffDays);

    if (absMins < 60) return `${absMins} min ago`;
    if (absHours < 24) return `${absHours} hr ago`;
    return `${absDays} days ago`;
  }
}

/**
 * Get status badge color
 */
export function getStatusColor(status) {
  const colors = {
    PENDING: 'warning',
    DISPATCHED: 'info',
    RUNNING: 'info',
    SUCCEEDED: 'success',
    FAILED: 'critical',
    CANCELLED: 'surface',
    QUEUED: 'warning',
  };
  return colors[status] || 'surface';
}

/**
 * Get priority badge color
 */
export function getPriorityColor(priority) {
  const colors = {
    CRITICAL: 'critical',
    HIGH: 'warning',
    NORMAL: 'info',
    LOW: 'surface',
  };
  return colors[priority] || 'surface';
}

// HITL Approval Queue API Functions (Phase 2)

// Production-realistic HITL pending approvals
const mockPendingApprovals = [
  // CRITICAL - Urgent security patches
  {
    approval_id: 'appr-7a8b9c0d',
    patch_id: 'patch-sec-2026-001',
    vulnerability_id: 'CVE-2026-1234',
    status: 'PENDING',
    severity: 'CRITICAL',
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 22 * 60 * 60 * 1000).toISOString(),
    // User context
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: 'usr-j5k6l7m8',
    reviewer_email: 'james.wilson@acme-corp.com',
    reviewer_name: 'James Wilson',
    reviewer_role: 'Security Lead',
    escalation_count: 0,
    // Organization context
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    // Repository context
    repository_id: 'repo-aura-core-1a2',
    repository: 'aura-core',
    repository_url: 'https://github.com/acme-corp/aura-core',
    file_path: 'src/auth/jwt_validator.py',
    branch: 'security/cve-2026-1234-fix',
    commit_sha: 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0',
    pull_request_id: 892,
    // Patch details
    title: 'Fix JWT Signature Bypass Vulnerability',
    description: 'Fix JWT signature bypass vulnerability in authentication module - allows token forgery without secret key',
    lines_added: 47,
    lines_removed: 12,
    files_changed: 3,
    // Agent analysis
    agent_confidence: 0.95,
    agent_reasoning: 'High confidence fix. Pattern matches known JWT validation bypass (CVE-2026-1234). All test cases pass including edge cases.',
    risk_assessment: 'Low risk - isolated change to validation logic with comprehensive test coverage',
    // Test results
    test_results: { passed: 47, failed: 0, skipped: 2, coverage_percent: 94.2 },
    sandbox_validation: { status: 'passed', duration_seconds: 180, environment: 'sandbox-sec-01' },
    // Compliance
    compliance_impact: ['SOC2-CC6.1', 'NIST-IA-5'],
    audit_trail_id: 'audit-8e9f0a1b',
    // Session tracking
    session_id: 'sess-appr-2c3d4e5f',
    request_id: 'req-9g0h1i2j3k4l',
    tags: ['critical', 'cve', 'jwt', 'authentication', 'urgent'],
  },
  {
    approval_id: 'appr-1e2f3g4h',
    patch_id: 'patch-critical-rce',
    vulnerability_id: 'CVE-2026-5678',
    status: 'PENDING',
    severity: 'CRITICAL',
    created_at: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString(), // Expiring soon!
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: 'usr-j5k6l7m8',
    reviewer_email: 'james.wilson@acme-corp.com',
    reviewer_name: 'James Wilson',
    reviewer_role: 'Security Lead',
    escalation_count: 1,
    escalation_history: [
      { escalated_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), reason: 'Approaching SLA deadline', notified: ['security-team@acme-corp.com'] },
    ],
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-payments',
    team_name: 'Payments Team',
    repository_id: 'repo-payment-gw-7f8',
    repository: 'payment-gateway',
    repository_url: 'https://github.com/acme-corp/payment-gateway',
    file_path: 'src/processors/xml_parser.py',
    branch: 'security/cve-2026-5678-xxe-fix',
    commit_sha: 'b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1',
    pull_request_id: 478,
    title: 'Patch XXE Vulnerability in XML Parser',
    description: 'Patch XXE vulnerability allowing remote code execution via malicious XML payloads in payment processing',
    lines_added: 89,
    lines_removed: 23,
    files_changed: 5,
    agent_confidence: 0.92,
    agent_reasoning: 'High confidence. Disabled external entity processing and added input validation. Follows OWASP XXE prevention cheatsheet.',
    risk_assessment: 'Medium risk - payment processing module requires careful review of XML handling changes',
    test_results: { passed: 156, failed: 0, skipped: 0, coverage_percent: 97.8 },
    sandbox_validation: { status: 'passed', duration_seconds: 240, environment: 'sandbox-pci-01' },
    compliance_impact: ['PCI-DSS-6.5.1', 'SOC2-CC6.6'],
    audit_trail_id: 'audit-5m6n7o8p',
    session_id: 'sess-appr-6g7h8i9j',
    request_id: 'req-5m6n7o8p9q0r',
    tags: ['critical', 'cve', 'xxe', 'rce', 'payments', 'expiring-soon'],
    urgency_note: 'EXPIRES IN 1 HOUR - Escalated to security team',
  },
  // HIGH - Important security fixes
  {
    approval_id: 'appr-5i6j7k8l',
    patch_id: 'patch-dep-2026-042',
    vulnerability_id: 'GHSA-9f4q-7abc-defg',
    status: 'PENDING',
    severity: 'HIGH',
    created_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 20 * 60 * 60 * 1000).toISOString(),
    requested_by: 'usr-sys-depbot',
    requested_by_email: 'dependabot@acme-corp.com',
    requested_by_name: 'Dependency Bot',
    reviewer_id: 'usr-r5s6t7u8',
    reviewer_email: 'rachel.torres@acme-corp.com',
    reviewer_name: 'Rachel Torres',
    reviewer_role: 'Tech Lead',
    escalation_count: 0,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    repository_id: 'repo-shared-libs-9c0',
    repository: 'shared-libs',
    repository_url: 'https://github.com/acme-corp/shared-libs',
    file_path: 'package.json',
    branch: 'deps/lodash-4.17.21',
    commit_sha: 'c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2',
    pull_request_id: 234,
    title: 'Update lodash to 4.17.21 - Prototype Pollution Fix',
    description: 'Update lodash to 4.17.21 to fix prototype pollution vulnerability (GHSA-9f4q-7abc-defg)',
    lines_added: 1,
    lines_removed: 1,
    files_changed: 1,
    agent_confidence: 0.99,
    agent_reasoning: 'Dependency update only. No breaking changes in minor version bump. All tests pass.',
    risk_assessment: 'Very low risk - minor version update with backward compatibility',
    test_results: { passed: 234, failed: 0, skipped: 5, coverage_percent: 89.1 },
    sandbox_validation: { status: 'passed', duration_seconds: 90, environment: 'sandbox-dev-02' },
    compliance_impact: ['SOC2-CC6.8'],
    audit_trail_id: 'audit-9q0r1s2t',
    session_id: 'sess-appr-0k1l2m3n',
    request_id: 'req-1s2t3u4v5w6x',
    tags: ['high', 'dependency', 'lodash', 'prototype-pollution'],
  },
  {
    approval_id: 'appr-9m0n1o2p',
    patch_id: 'patch-sql-injection',
    vulnerability_id: 'CWE-89',
    status: 'PENDING',
    severity: 'HIGH',
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 18 * 60 * 60 * 1000).toISOString(),
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: null,
    reviewer_email: null,
    reviewer_name: null,
    reviewer_role: null,
    assignment_status: 'unassigned',
    escalation_count: 0,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-backend',
    team_name: 'Backend Engineering',
    repository_id: 'repo-data-svc-2e3',
    repository: 'data-service',
    repository_url: 'https://github.com/acme-corp/data-service',
    file_path: 'src/queries/user_search.py',
    branch: 'security/sql-injection-fix',
    commit_sha: 'd4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3',
    pull_request_id: 567,
    title: 'Parameterize SQL Query - User Search',
    description: 'Parameterize SQL query to prevent injection in user search - converts string interpolation to parameterized query',
    lines_added: 34,
    lines_removed: 28,
    files_changed: 2,
    agent_confidence: 0.97,
    agent_reasoning: 'Standard SQL injection fix using parameterized queries. Pattern follows SQLAlchemy best practices.',
    risk_assessment: 'Low risk - equivalent query functionality with proper parameterization',
    test_results: { passed: 89, failed: 0, skipped: 1, coverage_percent: 91.5 },
    sandbox_validation: { status: 'passed', duration_seconds: 120, environment: 'sandbox-dev-01' },
    compliance_impact: ['SOC2-CC6.1', 'OWASP-A03'],
    audit_trail_id: 'audit-3u4v5w6x',
    session_id: 'sess-appr-4o5p6q7r',
    request_id: 'req-7y8z9a0b1c2d',
    tags: ['high', 'sql-injection', 'cwe-89', 'database', 'unassigned'],
  },
  // MEDIUM - Standard patches
  {
    approval_id: 'appr-3q4r5s6t',
    patch_id: 'patch-xss-sanitize',
    vulnerability_id: 'CWE-79',
    status: 'PENDING',
    severity: 'MEDIUM',
    created_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 16 * 60 * 60 * 1000).toISOString(),
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: null,
    reviewer_email: null,
    reviewer_name: null,
    reviewer_role: null,
    assignment_status: 'unassigned',
    escalation_count: 0,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-frontend',
    team_name: 'Frontend Engineering',
    repository_id: 'repo-frontend-app-8b2',
    repository: 'frontend-app',
    repository_url: 'https://github.com/acme-corp/frontend-app',
    file_path: 'src/components/DataGrid.jsx',
    branch: 'security/xss-datagrid-fix',
    commit_sha: 'e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4',
    pull_request_id: 789,
    title: 'Add Input Sanitization - DataGrid XSS Prevention',
    description: 'Add input sanitization to prevent XSS in data grid renderer - escapes HTML entities in user-provided content',
    lines_added: 52,
    lines_removed: 8,
    files_changed: 4,
    agent_confidence: 0.88,
    agent_reasoning: 'XSS prevention using DOMPurify sanitization. Covers all render paths in DataGrid component.',
    risk_assessment: 'Low risk - adds sanitization layer without changing functionality',
    test_results: { passed: 67, failed: 0, skipped: 3, coverage_percent: 86.3 },
    sandbox_validation: { status: 'passed', duration_seconds: 60, environment: 'sandbox-fe-01' },
    compliance_impact: ['OWASP-A07'],
    audit_trail_id: 'audit-7y8z9a0b',
    session_id: 'sess-appr-8s9t0u1v',
    request_id: 'req-3e4f5g6h7i8j',
    tags: ['medium', 'xss', 'cwe-79', 'frontend', 'sanitization', 'unassigned'],
  },
  {
    approval_id: 'appr-7u8v9w0x',
    patch_id: 'patch-session-timeout',
    vulnerability_id: 'CWE-613',
    status: 'PENDING',
    severity: 'MEDIUM',
    created_at: new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 14 * 60 * 60 * 1000).toISOString(),
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: 'usr-n1o2p3q4',
    reviewer_email: 'nina.patel@acme-corp.com',
    reviewer_name: 'Nina Patel',
    reviewer_role: 'Security Engineer',
    escalation_count: 0,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    repository_id: 'repo-auth-svc-3c4',
    repository: 'auth-service',
    repository_url: 'https://github.com/acme-corp/auth-service',
    file_path: 'src/session/manager.py',
    branch: 'compliance/session-timeout',
    commit_sha: 'f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5',
    pull_request_id: 345,
    title: 'Reduce Session Timeout for Compliance',
    description: 'Reduce session timeout from 24h to 4h for SOC2 compliance - implements sliding expiration with warning',
    lines_added: 78,
    lines_removed: 15,
    files_changed: 3,
    agent_confidence: 0.94,
    agent_reasoning: 'Session timeout reduction for compliance. Added sliding expiration and user warning at 30 min remaining.',
    risk_assessment: 'Medium risk - may impact user experience, requires communication',
    test_results: { passed: 45, failed: 0, skipped: 0, coverage_percent: 100.0 },
    sandbox_validation: { status: 'passed', duration_seconds: 150, environment: 'sandbox-auth-01' },
    compliance_impact: ['SOC2-CC6.1', 'NIST-AC-11', 'NIST-AC-12'],
    audit_trail_id: 'audit-1c2d3e4f',
    session_id: 'sess-appr-2w3x4y5z',
    request_id: 'req-9k0l1m2n3o4p',
    tags: ['medium', 'session', 'cwe-613', 'compliance', 'soc2'],
  },
  // LOW - Minor improvements
  {
    approval_id: 'appr-1y2z3a4b',
    patch_id: 'patch-log-masking',
    vulnerability_id: null,
    status: 'PENDING',
    severity: 'LOW',
    created_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: null,
    reviewer_email: null,
    reviewer_name: null,
    reviewer_role: null,
    assignment_status: 'unassigned',
    escalation_count: 0,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    repository_id: 'repo-ml-pipeline-0d1',
    repository: 'ml-pipeline',
    repository_url: 'https://github.com/acme-corp/ml-pipeline',
    file_path: 'src/utils/logger.py',
    branch: 'improve/log-masking',
    commit_sha: 'g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6',
    pull_request_id: 123,
    title: 'Mask Sensitive Fields in Debug Logs',
    description: 'Mask sensitive fields in debug log output - PII, API keys, tokens automatically redacted',
    lines_added: 45,
    lines_removed: 12,
    files_changed: 2,
    agent_confidence: 0.91,
    agent_reasoning: 'Log masking utility using regex patterns for common sensitive data. Tested with sample log outputs.',
    risk_assessment: 'Very low risk - defensive logging improvement',
    test_results: { passed: 23, failed: 0, skipped: 0, coverage_percent: 95.0 },
    sandbox_validation: { status: 'passed', duration_seconds: 45, environment: 'sandbox-dev-03' },
    compliance_impact: ['SOC2-CC6.7', 'GDPR-Art32'],
    audit_trail_id: 'audit-5g6h7i8j',
    session_id: 'sess-appr-6a7b8c9d',
    request_id: 'req-5q6r7s8t9u0v',
    tags: ['low', 'logging', 'pii', 'security-hardening', 'unassigned'],
  },
  {
    approval_id: 'appr-5c6d7e8f',
    patch_id: 'patch-csp-header',
    vulnerability_id: null,
    status: 'PENDING',
    severity: 'LOW',
    created_at: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
    requested_by: 'usr-sys-agent-coder',
    requested_by_email: 'coder-agent@aura.local',
    requested_by_name: 'Aura Coder Agent',
    reviewer_id: null,
    reviewer_email: null,
    reviewer_name: null,
    reviewer_role: null,
    assignment_status: 'unassigned',
    escalation_count: 0,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    repository_id: 'repo-aura-api-5e6',
    repository: 'aura-api',
    repository_url: 'https://github.com/acme-corp/aura-api',
    file_path: 'src/middleware/security_headers.py',
    branch: 'security/csp-headers',
    commit_sha: 'h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7',
    pull_request_id: 456,
    title: 'Add Content-Security-Policy Header',
    description: 'Add Content-Security-Policy header to API responses - defense-in-depth against XSS',
    lines_added: 28,
    lines_removed: 0,
    files_changed: 2,
    agent_confidence: 0.96,
    agent_reasoning: 'CSP header configuration following OWASP recommendations. Report-only mode for initial deployment.',
    risk_assessment: 'Low risk - report-only mode allows monitoring without blocking',
    test_results: { passed: 112, failed: 0, skipped: 4, coverage_percent: 88.7 },
    sandbox_validation: { status: 'passed', duration_seconds: 75, environment: 'sandbox-api-01' },
    compliance_impact: ['OWASP-A05'],
    audit_trail_id: 'audit-9k0l1m2n',
    session_id: 'sess-appr-0e1f2g3h',
    request_id: 'req-1w2x3y4z5a6b',
    tags: ['low', 'csp', 'headers', 'security-hardening', 'unassigned'],
  },
];

/**
 * Get pending HITL approvals
 */
export async function getPendingApprovals({ severity, limit = 20 } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    let approvals = [...mockPendingApprovals];

    // Filter by severity if specified
    if (severity) {
      approvals = approvals.filter((a) => a.severity === severity);
    }

    // Sort by severity (CRITICAL first) then by created_at
    const severityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    approvals.sort((a, b) => {
      const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
      if (severityDiff !== 0) return severityDiff;
      return new Date(a.created_at) - new Date(b.created_at);
    });

    return {
      approvals: approvals.slice(0, limit),
      total: approvals.length,
    };
  }

  // Use existing approvals endpoint with status=pending filter
  const params = new URLSearchParams();
  params.append('status', 'pending');
  if (severity) params.append('severity', severity);
  if (limit) params.append('limit', limit.toString());

  const response = await apiRequest(`/api/v1/approvals?${params.toString()}`);

  // Transform response to match expected format
  return {
    approvals: response.approvals.map((a) => ({
      approval_id: a.id,
      patch_id: a.patch?.file || a.title,
      vulnerability_id: a.vulnerability?.cve,
      status: a.status?.toUpperCase() || 'PENDING',
      severity: a.severity?.toUpperCase() || 'MEDIUM',
      created_at: a.created_at,
      expires_at: a.expires_at, // Note: may need to compute from created_at + timeout
      reviewer_email: a.approved_by || a.rejected_by,
      escalation_count: a.escalation_count || 0,
    })),
    total: response.pending || response.approvals.length,
  };
}

/**
 * Approve a HITL request
 */
export async function approveRequest(approvalId, reason = '') {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const index = mockPendingApprovals.findIndex((a) => a.approval_id === approvalId);
    if (index === -1) {
      throw new Error('Approval request not found');
    }

    const approval = mockPendingApprovals[index];
    approval.status = 'APPROVED';
    approval.reviewed_at = new Date().toISOString();
    approval.decision_reason = reason;

    // Remove from pending list
    mockPendingApprovals.splice(index, 1);

    return approval;
  }

  return apiRequest(`/api/v1/approvals/${approvalId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

/**
 * Reject a HITL request
 */
export async function rejectRequest(approvalId, reason = '') {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const index = mockPendingApprovals.findIndex((a) => a.approval_id === approvalId);
    if (index === -1) {
      throw new Error('Approval request not found');
    }

    const approval = mockPendingApprovals[index];
    approval.status = 'REJECTED';
    approval.reviewed_at = new Date().toISOString();
    approval.decision_reason = reason;

    // Remove from pending list
    mockPendingApprovals.splice(index, 1);

    return approval;
  }

  return apiRequest(`/api/v1/approvals/${approvalId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

/**
 * Get approval statistics
 */
export async function getApprovalStats() {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const severityCounts = mockPendingApprovals.reduce((acc, a) => {
      acc[a.severity] = (acc[a.severity] || 0) + 1;
      return acc;
    }, {});

    return {
      total_pending: mockPendingApprovals.length,
      by_severity: {
        CRITICAL: severityCounts.CRITICAL || 0,
        HIGH: severityCounts.HIGH || 0,
        MEDIUM: severityCounts.MEDIUM || 0,
        LOW: severityCounts.LOW || 0,
      },
      expiring_soon: mockPendingApprovals.filter((a) => {
        const expires = new Date(a.expires_at);
        const now = new Date();
        const hoursLeft = (expires - now) / (1000 * 60 * 60);
        return hoursLeft < 2;
      }).length,
      avg_wait_time_hours: 8.5,
    };
  }

  return apiRequest('/api/v1/approvals/stats');
}

// Recurring Tasks API Functions (Phase 3)

// Production-realistic recurring tasks
const mockRecurringTasks = [
  {
    task_id: 'recur-8a9b0c1d',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'Weekly Security Scan - All Repositories',
    description: 'Comprehensive OWASP Top 10 and SANS 25 security scan across all 47 repositories',
    job_type: 'SECURITY_SCAN',
    cron_expression: '0 6 * * 1',
    cron_readable: 'Every Monday at 6:00 AM UTC',
    timezone: 'UTC',
    repository_id: null,
    repository_name: 'All Repositories',
    parameters: {
      depth: 'full',
      include_dependencies: true,
      scan_type: 'comprehensive',
      frameworks: ['owasp-top10', 'sans-25', 'cwe-top-25'],
      auto_create_issues: true,
      notification_channels: ['slack-security', 'email'],
    },
    enabled: true,
    created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-j5k6l7m8',
    created_by_email: 'james.wilson@acme-corp.com',
    created_by_name: 'James Wilson',
    updated_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-j5k6l7m8',
    last_run_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 127,
    last_run_findings: { critical: 0, high: 2, medium: 8, low: 15 },
    next_run_at: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
    run_count: 12,
    success_count: 12,
    failure_count: 0,
    success_rate: 100.0,
    avg_duration_minutes: 118,
    total_cost_usd: 36.50,
    avg_cost_usd: 3.04,
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    project_id: 'proj-weekly-scans-2m4',
    project_name: 'Weekly Security Scans',
    tags: ['weekly', 'security', 'comprehensive', 'all-repos'],
  },
  {
    task_id: 'recur-2e3f4g5h',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'Daily SOC2/CMMC Compliance Check',
    description: 'Automated compliance validation for SOC2, CMMC Level 2, and NIST 800-53 controls',
    job_type: 'COMPLIANCE_CHECK',
    cron_expression: '0 9 * * 1-5',
    cron_readable: 'Weekdays at 9:00 AM UTC',
    timezone: 'UTC',
    repository_id: null,
    repository_name: 'All Repositories',
    parameters: {
      frameworks: ['SOC2-TypeII', 'CMMC-L2', 'NIST-800-53'],
      auto_remediate: false,
      generate_report: true,
      report_format: 'pdf',
      recipients: ['compliance@acme-corp.com', 'security@acme-corp.com'],
      control_subset: 'critical',
    },
    enabled: true,
    created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-v9w0x1y2',
    created_by_email: 'victoria.chang@acme-corp.com',
    created_by_name: 'Victoria Chang',
    updated_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-v9w0x1y2',
    last_run_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 89,
    last_run_findings: { passing: 142, failing: 3, not_applicable: 12 },
    next_run_at: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
    run_count: 45,
    success_count: 44,
    failure_count: 1,
    success_rate: 97.78,
    avg_duration_minutes: 85,
    total_cost_usd: 180.00,
    avg_cost_usd: 4.00,
    team_id: 'team-compliance',
    team_name: 'Compliance & Governance',
    project_id: 'proj-soc2-audit-5r7',
    project_name: 'SOC2 Type II Audit 2026',
    tags: ['daily', 'compliance', 'soc2', 'cmmc', 'nist'],
  },
  {
    task_id: 'recur-6i7j8k9l',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'Monthly Dependency Updates',
    description: 'Automated dependency updates with security patches - creates PRs for review',
    job_type: 'DEPENDENCY_UPDATE',
    cron_expression: '0 6 1 * *',
    cron_readable: '1st of every month at 6:00 AM UTC',
    timezone: 'UTC',
    repository_id: null,
    repository_name: 'All Repositories',
    parameters: {
      auto_merge: false,
      create_pr: true,
      include_major: false,
      security_only: false,
      group_by_ecosystem: true,
      max_prs_per_repo: 5,
    },
    enabled: false,
    disabled_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    disabled_by: 'usr-r5s6t7u8',
    disabled_by_email: 'rachel.torres@acme-corp.com',
    disabled_by_name: 'Rachel Torres',
    disabled_reason: 'Paused pending review of breaking changes in React 19 and Node.js 22 LTS',
    created_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-r5s6t7u8',
    created_by_email: 'rachel.torres@acme-corp.com',
    created_by_name: 'Rachel Torres',
    updated_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-r5s6t7u8',
    last_run_at: new Date(Date.now() - 28 * 24 * 60 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 156,
    last_run_findings: { prs_created: 23, packages_updated: 67, breaking_changes: 3 },
    next_run_at: null,
    run_count: 6,
    success_count: 5,
    failure_count: 1,
    success_rate: 83.33,
    avg_duration_minutes: 142,
    total_cost_usd: 27.00,
    avg_cost_usd: 4.50,
    team_id: 'team-platform-eng',
    team_name: 'Platform Engineering',
    project_id: 'proj-dep-mgmt-6u8',
    project_name: 'Dependency Management',
    tags: ['monthly', 'dependencies', 'disabled', 'breaking-changes'],
  },
  {
    task_id: 'recur-0m1n2o3p',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'Hourly Threat Intelligence Feed',
    description: 'Real-time threat intelligence aggregation from NVD, GitHub Security Advisories, and CISA KEV',
    job_type: 'THREAT_ANALYSIS',
    cron_expression: '0 * * * *',
    cron_readable: 'Every hour at :00',
    timezone: 'UTC',
    repository_id: null,
    repository_name: 'All Repositories',
    parameters: {
      severity_threshold: 'HIGH',
      feeds: ['nvd', 'ghsa', 'cisa-kev', 'exploit-db'],
      auto_alert: true,
      alert_channels: ['slack-security-alerts', 'pagerduty'],
      match_dependencies: true,
      cve_age_days: 7,
    },
    enabled: true,
    created_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-n1o2p3q4',
    created_by_email: 'nina.patel@acme-corp.com',
    created_by_name: 'Nina Patel',
    updated_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-n1o2p3q4',
    last_run_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 8,
    last_run_findings: { new_cves: 12, matching_deps: 0, critical_alerts: 0 },
    next_run_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
    run_count: 336,
    success_count: 335,
    failure_count: 1,
    success_rate: 99.70,
    avg_duration_minutes: 7,
    total_cost_usd: 67.20,
    avg_cost_usd: 0.20,
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    project_id: 'proj-threat-intel-2m4',
    project_name: 'Threat Intelligence',
    tags: ['hourly', 'threat-intel', 'cve', 'automated'],
  },
  {
    task_id: 'recur-4q5r6s7t',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'Nightly Code Quality Analysis - Core Services',
    description: 'Automated code quality metrics: complexity, duplication, test coverage for core services',
    job_type: 'CODE_QUALITY_SCAN',
    cron_expression: '0 2 * * *',
    cron_readable: 'Every day at 2:00 AM UTC',
    timezone: 'UTC',
    repository_id: 'repo-aura-core-1a2',
    repository_name: 'aura-core',
    repository_url: 'https://github.com/acme-corp/aura-core',
    parameters: {
      metrics: ['cyclomatic_complexity', 'cognitive_complexity', 'duplication', 'coverage', 'maintainability_index'],
      threshold_fail: true,
      thresholds: { complexity: 10, duplication: 3, coverage: 80, maintainability: 65 },
      generate_report: true,
      trend_analysis: true,
    },
    enabled: true,
    created_at: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-z3a4b5c6',
    created_by_email: 'zoe.martinez@acme-corp.com',
    created_by_name: 'Zoe Martinez',
    updated_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-z3a4b5c6',
    last_run_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 42,
    last_run_findings: { complexity_avg: 7.2, duplication_percent: 2.1, coverage_percent: 87.3, maintainability: 72 },
    next_run_at: new Date(Date.now() + 16 * 60 * 60 * 1000).toISOString(),
    run_count: 45,
    success_count: 43,
    failure_count: 2,
    success_rate: 95.56,
    avg_duration_minutes: 38,
    total_cost_usd: 90.00,
    avg_cost_usd: 2.00,
    team_id: 'team-qa',
    team_name: 'Quality Assurance',
    project_id: 'proj-code-health-8w0',
    project_name: 'Code Health Initiative',
    tags: ['nightly', 'code-quality', 'metrics', 'aura-core'],
  },
  {
    task_id: 'recur-8u9v0w1x',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'GraphRAG Index Refresh - All Repositories',
    description: 'Nightly incremental index refresh for Neptune graph and OpenSearch vector embeddings',
    job_type: 'REPOSITORY_INDEXING',
    cron_expression: '30 3 * * *',
    cron_readable: 'Every day at 3:30 AM UTC',
    timezone: 'UTC',
    repository_id: null,
    repository_name: 'All Repositories',
    parameters: {
      full_reindex: false,
      include_embeddings: true,
      embedding_model: 'codebert-base-v2.1',
      index_targets: ['neptune-graph', 'opensearch-vector'],
      changed_files_only: true,
      commit_lookback_hours: 24,
    },
    enabled: true,
    created_at: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-sys-scheduler',
    created_by_email: 'scheduler@acme-corp.com',
    created_by_name: 'System Scheduler',
    updated_at: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-sys-scheduler',
    last_run_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 67,
    last_run_findings: { files_indexed: 1247, embeddings_generated: 1247, graph_nodes_updated: 3842 },
    next_run_at: new Date(Date.now() + 18 * 60 * 60 * 1000).toISOString(),
    run_count: 20,
    success_count: 20,
    failure_count: 0,
    success_rate: 100.0,
    avg_duration_minutes: 58,
    total_cost_usd: 80.00,
    avg_cost_usd: 4.00,
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    project_id: 'proj-graphrag-7v9',
    project_name: 'GraphRAG Infrastructure',
    tags: ['nightly', 'indexing', 'graphrag', 'neptune', 'opensearch'],
  },
  {
    task_id: 'recur-2y3z4a5b',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'Weekly Vulnerability Report',
    description: 'Executive vulnerability summary report with remediation recommendations and trend analysis',
    job_type: 'VULNERABILITY_ASSESSMENT',
    cron_expression: '0 8 * * 5',
    cron_readable: 'Every Friday at 8:00 AM UTC',
    timezone: 'UTC',
    repository_id: null,
    repository_name: 'All Repositories',
    parameters: {
      report_format: 'pdf',
      recipients: ['security@acme-corp.com', 'ciso@acme-corp.com', 'engineering-leads@acme-corp.com'],
      include_remediation: true,
      include_trend_analysis: true,
      comparison_period_weeks: 4,
      executive_summary: true,
    },
    enabled: true,
    created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-j5k6l7m8',
    created_by_email: 'james.wilson@acme-corp.com',
    created_by_name: 'James Wilson',
    updated_at: new Date(Date.now() - 21 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-j5k6l7m8',
    last_run_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 95,
    last_run_findings: { critical: 0, high: 4, medium: 23, low: 67, remediated_this_week: 12 },
    next_run_at: new Date(Date.now() + 4 * 24 * 60 * 60 * 1000).toISOString(),
    run_count: 8,
    success_count: 8,
    failure_count: 0,
    success_rate: 100.0,
    avg_duration_minutes: 88,
    total_cost_usd: 32.00,
    avg_cost_usd: 4.00,
    team_id: 'team-security-ops',
    team_name: 'Security Operations',
    project_id: 'proj-vuln-mgmt-4k8',
    project_name: 'Vulnerability Management',
    tags: ['weekly', 'vulnerability', 'report', 'executive'],
  },
  {
    task_id: 'recur-6c7d8e9f',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    name: 'PR Auto-Review - Frontend Repository',
    description: 'Automated code review for frontend pull requests during business hours',
    job_type: 'CODE_REVIEW',
    cron_expression: '*/30 9-18 * * 1-5',
    cron_readable: 'Every 30 minutes, 9 AM - 6 PM UTC, weekdays',
    timezone: 'UTC',
    repository_id: 'repo-frontend-app-8b2',
    repository_name: 'frontend-app',
    repository_url: 'https://github.com/acme-corp/frontend-app',
    parameters: {
      auto_approve: false,
      review_depth: 'standard',
      check_tests: true,
      check_lint: true,
      check_types: true,
      security_scan: true,
      max_prs_per_run: 10,
      skip_draft: true,
    },
    enabled: true,
    created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-r5s6t7u8',
    created_by_email: 'rachel.torres@acme-corp.com',
    created_by_name: 'Rachel Torres',
    updated_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-r5s6t7u8',
    last_run_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    last_run_status: 'SUCCEEDED',
    last_run_duration_minutes: 12,
    last_run_findings: { prs_reviewed: 3, comments_added: 7, approvals: 1, requests_changes: 1 },
    next_run_at: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
    run_count: 156,
    success_count: 153,
    failure_count: 3,
    success_rate: 98.08,
    avg_duration_minutes: 8,
    total_cost_usd: 46.80,
    avg_cost_usd: 0.30,
    team_id: 'team-frontend',
    team_name: 'Frontend Engineering',
    project_id: 'proj-pr-automation-3t5',
    project_name: 'PR Automation',
    tags: ['business-hours', 'code-review', 'frontend', 'pr-automation'],
  },
];

/**
 * Get all recurring tasks
 */
export async function getRecurringTasks({ enabled, limit = 50 } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    let tasks = [...mockRecurringTasks];
    if (enabled !== undefined) {
      tasks = tasks.filter((t) => t.enabled === enabled);
    }

    return {
      tasks: tasks.slice(0, limit),
      total: tasks.length,
    };
  }

  const params = new URLSearchParams();
  if (enabled !== undefined) params.append('enabled', enabled.toString());
  if (limit) params.append('limit', limit.toString());

  return apiRequest(`/api/v1/schedule/recurring?${params.toString()}`);
}

/**
 * Get a specific recurring task
 */
export async function getRecurringTask(taskId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const task = mockRecurringTasks.find((t) => t.task_id === taskId);
    if (!task) {
      throw new Error('Recurring task not found');
    }
    return task;
  }

  return apiRequest(`/api/v1/schedule/recurring/${taskId}`);
}

/**
 * Create a new recurring task
 */
export async function createRecurringTask(taskData) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));

    const newTask = {
      task_id: `recurring-${Date.now()}`,
      organization_id: 'org-default',
      ...taskData,
      created_at: new Date().toISOString(),
      created_by: 'dev-user',
      last_run_at: null,
      next_run_at: taskData.enabled ? calculateNextRun(taskData.cron_expression) : null,
    };

    mockRecurringTasks.unshift(newTask);
    return newTask;
  }

  return apiRequest('/api/v1/schedule/recurring', {
    method: 'POST',
    body: JSON.stringify(taskData),
  });
}

/**
 * Update a recurring task
 */
export async function updateRecurringTask(taskId, taskData) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const task = mockRecurringTasks.find((t) => t.task_id === taskId);
    if (!task) {
      throw new Error('Recurring task not found');
    }

    Object.assign(task, taskData);
    task.updated_at = new Date().toISOString();

    // Recalculate next run if cron changed or enabled
    if (taskData.cron_expression || taskData.enabled !== undefined) {
      task.next_run_at = task.enabled ? calculateNextRun(task.cron_expression) : null;
    }

    return task;
  }

  return apiRequest(`/api/v1/schedule/recurring/${taskId}`, {
    method: 'PUT',
    body: JSON.stringify(taskData),
  });
}

/**
 * Delete a recurring task
 */
export async function deleteRecurringTask(taskId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const index = mockRecurringTasks.findIndex((t) => t.task_id === taskId);
    if (index === -1) {
      throw new Error('Recurring task not found');
    }

    mockRecurringTasks.splice(index, 1);
    return { success: true };
  }

  return apiRequest(`/api/v1/schedule/recurring/${taskId}`, {
    method: 'DELETE',
  });
}

/**
 * Toggle recurring task enabled/disabled
 */
export async function toggleRecurringTask(taskId, enabled) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    const task = mockRecurringTasks.find((t) => t.task_id === taskId);
    if (!task) {
      throw new Error('Recurring task not found');
    }

    task.enabled = enabled;
    task.next_run_at = enabled ? calculateNextRun(task.cron_expression) : null;

    return task;
  }

  return apiRequest(`/api/v1/schedule/recurring/${taskId}/toggle`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  });
}

/**
 * Calculate next run time from cron expression (simplified)
 */
function calculateNextRun(cronExpression) {
  // Simple calculation - in production, use a proper cron parser
  const now = new Date();
  const parts = cronExpression.split(' ');

  if (parts.length !== 5) return null;

  const [minute, hour] = parts;

  // For now, just calculate next occurrence based on hour/minute
  const next = new Date(now);
  next.setMinutes(minute === '*' ? 0 : parseInt(minute));
  next.setSeconds(0);
  next.setMilliseconds(0);

  if (hour !== '*') {
    next.setHours(parseInt(hour));
  }

  // If time has passed today, move to tomorrow
  if (next <= now) {
    next.setDate(next.getDate() + 1);
  }

  return next.toISOString();
}

// Export job types for use in components
export const JOB_TYPES = mockJobTypes;
