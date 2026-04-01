/**
 * GPU Scheduler API Service
 *
 * Client for GPU workload scheduling and queue management API.
 * ADR-061: GPU Workload Scheduler - Phase 3 Frontend Integration
 */

const API_URL = import.meta.env.VITE_API_URL || '';
const WS_URL = import.meta.env.VITE_WS_BASE_URL || '';
const DEV_MODE = import.meta.env.DEV && !import.meta.env.VITE_API_URL;

// GPU job type definitions
export const GPU_JOB_TYPES = [
  {
    value: 'embedding_generation',
    label: 'Code Embedding Generation',
    description: 'Batch vectorization of repository code for semantic search',
    typicalDuration: '5-60 minutes',
    gpuMemory: '4-8 GB',
    icon: 'CodeBracket',
  },
  {
    value: 'local_inference',
    label: 'Local LLM Inference',
    description: 'On-premise model inference for cost optimization',
    typicalDuration: 'Continuous',
    gpuMemory: '8-16 GB',
    icon: 'CpuChip',
  },
  {
    value: 'vulnerability_training',
    label: 'Vulnerability Classifier Training',
    description: 'Fine-tuning security models on customer patterns',
    typicalDuration: '1-4 hours',
    gpuMemory: '8-16 GB',
    icon: 'ShieldCheck',
  },
  {
    value: 'swe_rl_training',
    label: 'Self-Play SWE-RL Training',
    description: 'Reinforcement learning for agent improvement (ADR-050)',
    typicalDuration: '2-8 hours',
    gpuMemory: '16-24 GB',
    icon: 'AcademicCap',
  },
  {
    value: 'memory_consolidation',
    label: 'Titan Memory Consolidation',
    description: 'Neural memory write operations (ADR-024)',
    typicalDuration: '5-15 minutes',
    gpuMemory: '4-8 GB',
    icon: 'CircleStack',
  },
];

// GPU job priority definitions
export const GPU_JOB_PRIORITIES = [
  {
    value: 'low',
    label: 'Low',
    description: 'Background optimization, experiments. Can be preempted.',
    maxConcurrent: 2,
  },
  {
    value: 'normal',
    label: 'Normal',
    description: 'Standard batch jobs. Cannot be preempted.',
    maxConcurrent: 4,
  },
  {
    value: 'high',
    label: 'High',
    description: 'Critical training, production inference. Can preempt low priority jobs.',
    maxConcurrent: 2,
  },
];

// Error type definitions
export const GPU_ERROR_TYPES = {
  oom: {
    label: 'Out of Memory',
    description: 'GPU ran out of memory',
    severity: 'high',
    action: 'Retry with more memory',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    textColor: 'text-red-700 dark:text-red-400',
  },
  spot_interruption: {
    label: 'Spot Interruption',
    description: 'AWS Spot instance was interrupted',
    severity: 'medium',
    action: 'Auto-retry from checkpoint',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    textColor: 'text-blue-700 dark:text-blue-400',
  },
  timeout: {
    label: 'Timeout',
    description: 'Job exceeded maximum runtime',
    severity: 'medium',
    action: 'Extend runtime or optimize',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    textColor: 'text-amber-700 dark:text-amber-400',
  },
  config_error: {
    label: 'Configuration Error',
    description: 'Invalid job configuration',
    severity: 'high',
    action: 'Fix config and retry',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    textColor: 'text-red-700 dark:text-red-400',
  },
  network_error: {
    label: 'Network Error',
    description: 'Network connectivity issue',
    severity: 'medium',
    action: 'Check network and retry',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    textColor: 'text-amber-700 dark:text-amber-400',
  },
};

// Mock data for development - Production-realistic GPU job data
const mockGPUJobs = [
  // Active job - Running embedding generation
  {
    job_id: 'gpu-job-e7f2a1b4',
    user_id: 'usr-m3k8n2p5',
    user_email: 'marcus.johnson@acme-corp.com',
    user_name: 'Marcus Johnson',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    project_id: 'proj-code-intel-9f4',
    project_name: 'Code Intelligence Pipeline',
    job_type: 'embedding_generation',
    job_title: 'Backend Services Code Embeddings',
    status: 'running',
    priority: 'normal',
    config: {
      repository_id: 'repo-backend-svc-2a1',
      repository_url: 'https://github.com/acme-corp/backend-services',
      branch: 'main',
      commit_sha: 'a8f3e2d1c4b5a6e7f8d9c0b1a2e3f4d5c6b7a8e9',
      model: 'codebert-base-v2.1',
      embedding_dimension: 768,
      batch_size: 64,
      include_docstrings: true,
      language_filter: ['python', 'javascript', 'typescript'],
    },
    gpu_type: 'nvidia-a10g',
    gpu_memory_gb: 8,
    gpu_memory_used_gb: 6.4,
    checkpoint_enabled: true,
    checkpoint_s3_path: 's3://aura-checkpoints-prod/acme-corp/gpu-job-e7f2a1b4/',
    checkpoint_count: 3,
    last_checkpoint_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    started_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    completed_at: null,
    progress_percent: 67,
    files_processed: 827,
    files_total: 1234,
    cost_usd: 0.54,
    cost_breakdown: { compute: 0.48, storage: 0.04, network: 0.02 },
    kubernetes_job_name: 'gpu-embed-e7f2a1b4-acme',
    kubernetes_namespace: 'aura-gpu-jobs',
    kubernetes_node: 'gpu-node-pool-a10g-2',
    error_message: null,
    error_type: null,
    estimated_remaining_minutes: 8,
    session_id: 'sess-gpu-8k2m4n6p',
    request_id: 'req-7f8a9b0c1d2e',
    triggered_by: 'scheduled',
    tags: ['embedding', 'backend', 'production', 'weekly-refresh'],
  },
  // Queued jobs - Vulnerability training
  {
    job_id: 'gpu-job-b3c4d5e6',
    user_id: 'usr-s7t8u9v0',
    user_email: 'sarah.chen@acme-corp.com',
    user_name: 'Sarah Chen',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-security-ml',
    team_name: 'Security ML Research',
    project_id: 'proj-vuln-detect-3k7',
    project_name: 'Vulnerability Detection System',
    job_type: 'vulnerability_training',
    job_title: 'Q1 2026 Vulnerability Classifier Fine-tuning',
    status: 'queued',
    priority: 'normal',
    config: {
      dataset_id: 'ds-vuln-2026-q1-final',
      dataset_version: '2.3.1',
      base_model: 'codebert-vuln-classifier-v3',
      epochs: 10,
      batch_size: 32,
      learning_rate: 0.0001,
      warmup_steps: 500,
      weight_decay: 0.01,
      eval_split: 0.15,
      vulnerability_categories: ['sql_injection', 'xss', 'path_traversal', 'auth_bypass', 'buffer_overflow'],
      class_weights: 'balanced',
    },
    gpu_type: 'nvidia-a100',
    gpu_memory_gb: 16,
    gpu_memory_used_gb: null,
    checkpoint_enabled: true,
    checkpoint_s3_path: null,
    checkpoint_count: 0,
    last_checkpoint_at: null,
    created_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    started_at: null,
    completed_at: null,
    progress_percent: null,
    files_processed: null,
    files_total: null,
    cost_usd: null,
    cost_breakdown: null,
    kubernetes_job_name: null,
    kubernetes_namespace: 'aura-gpu-jobs',
    kubernetes_node: null,
    error_message: null,
    error_type: null,
    queue_position: 1,
    estimated_wait_minutes: 12,
    session_id: 'sess-gpu-3j5k7m9n',
    request_id: 'req-2a3b4c5d6e7f',
    triggered_by: 'manual',
    tags: ['security', 'training', 'q1-2026', 'vulnerability-classifier'],
  },
  {
    job_id: 'gpu-job-f8g9h0i1',
    user_id: 'usr-m3k8n2p5',
    user_email: 'marcus.johnson@acme-corp.com',
    user_name: 'Marcus Johnson',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    project_id: 'proj-titan-mem-2f8',
    project_name: 'Titan Neural Memory',
    job_type: 'memory_consolidation',
    job_title: 'Session Memory Consolidation - Code Review Context',
    status: 'queued',
    priority: 'low',
    config: {
      session_id: 'sess-agent-abc123def456',
      memory_layer: 'long_term',
      retention_threshold: 0.7,
      max_memories: 1000,
      consolidation_strategy: 'importance_weighted',
      context_type: 'code_review',
      associated_project: 'proj-code-intel-9f4',
    },
    gpu_type: 'nvidia-t4',
    gpu_memory_gb: 4,
    gpu_memory_used_gb: null,
    checkpoint_enabled: false,
    checkpoint_s3_path: null,
    checkpoint_count: 0,
    last_checkpoint_at: null,
    created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    started_at: null,
    completed_at: null,
    progress_percent: null,
    files_processed: null,
    files_total: null,
    cost_usd: null,
    cost_breakdown: null,
    kubernetes_job_name: null,
    kubernetes_namespace: 'aura-gpu-jobs',
    kubernetes_node: null,
    error_message: null,
    error_type: null,
    queue_position: 2,
    estimated_wait_minutes: 45,
    session_id: 'sess-gpu-9p0q1r2s',
    request_id: 'req-8g9h0i1j2k3l',
    triggered_by: 'automatic',
    tags: ['memory', 'consolidation', 'titan-adr-024', 'background'],
  },
  // Completed - Embedding generation
  {
    job_id: 'gpu-job-j2k3l4m5',
    user_id: 'usr-m3k8n2p5',
    user_email: 'marcus.johnson@acme-corp.com',
    user_name: 'Marcus Johnson',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-ml-platform',
    team_name: 'ML Platform Engineering',
    project_id: 'proj-code-intel-9f4',
    project_name: 'Code Intelligence Pipeline',
    job_type: 'embedding_generation',
    job_title: 'Frontend App Code Embeddings',
    status: 'completed',
    priority: 'normal',
    config: {
      repository_id: 'repo-frontend-app-8b2',
      repository_url: 'https://github.com/acme-corp/frontend-app',
      branch: 'main',
      commit_sha: 'c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8',
      model: 'codebert-base-v2.1',
      embedding_dimension: 768,
      batch_size: 64,
      include_docstrings: true,
      language_filter: ['javascript', 'typescript', 'css'],
    },
    gpu_type: 'nvidia-a10g',
    gpu_memory_gb: 8,
    gpu_memory_used_gb: 7.1,
    checkpoint_enabled: true,
    checkpoint_s3_path: 's3://aura-checkpoints-prod/acme-corp/gpu-job-j2k3l4m5/',
    checkpoint_count: 5,
    last_checkpoint_at: new Date(Date.now() - 2.1 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    started_at: new Date(Date.now() - 2.5 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    progress_percent: 100,
    files_processed: 892,
    files_total: 892,
    cost_usd: 0.89,
    cost_breakdown: { compute: 0.79, storage: 0.06, network: 0.04 },
    kubernetes_job_name: 'gpu-embed-j2k3l4m5-acme',
    kubernetes_namespace: 'aura-gpu-jobs',
    kubernetes_node: 'gpu-node-pool-a10g-1',
    error_message: null,
    error_type: null,
    result_summary: {
      embeddings_generated: 892,
      total_tokens_processed: 2847562,
      avg_embedding_time_ms: 45.2,
      index_updated: true,
      opensearch_documents: 892,
    },
    session_id: 'sess-gpu-4t5u6v7w',
    request_id: 'req-3m4n5o6p7q8r',
    triggered_by: 'scheduled',
    tags: ['embedding', 'frontend', 'production', 'daily-refresh'],
  },
  // Completed - SWE-RL training
  {
    job_id: 'gpu-job-n6o7p8q9',
    user_id: 'usr-a1b2c3d4',
    user_email: 'david.kim@acme-corp.com',
    user_name: 'David Kim',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-agent-research',
    team_name: 'Agent Research',
    project_id: 'proj-swe-rl-1a5',
    project_name: 'Self-Play SWE-RL (ADR-050)',
    job_type: 'swe_rl_training',
    job_title: 'Batch 47 - Self-Play RL Training Run',
    status: 'completed',
    priority: 'high',
    config: {
      batch_id: 'batch-47-swe-rl-2026-01',
      max_epochs: 100,
      epochs_completed: 100,
      checkpoint_interval_minutes: 15,
      base_model: 'aura-coder-7b-v2',
      reward_model: 'aura-code-reward-v1.2',
      ppo_clip_range: 0.2,
      learning_rate: 5e-6,
      kl_penalty: 0.1,
      environment: 'sandbox-isolated',
      task_distribution: { bug_fixing: 0.4, feature_impl: 0.35, refactoring: 0.25 },
    },
    gpu_type: 'nvidia-a100',
    gpu_memory_gb: 24,
    gpu_memory_used_gb: 21.8,
    checkpoint_enabled: true,
    checkpoint_s3_path: 's3://aura-checkpoints-prod/acme-corp/gpu-job-n6o7p8q9/',
    checkpoint_count: 21,
    last_checkpoint_at: new Date(Date.now() - 4.1 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    started_at: new Date(Date.now() - 7.5 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    progress_percent: 100,
    files_processed: null,
    files_total: null,
    cost_usd: 3.21,
    cost_breakdown: { compute: 2.94, storage: 0.18, network: 0.09 },
    kubernetes_job_name: 'gpu-swe-rl-n6o7p8q9-acme',
    kubernetes_namespace: 'aura-gpu-jobs',
    kubernetes_node: 'gpu-node-pool-a100-1',
    error_message: null,
    error_type: null,
    result_summary: {
      final_reward: 0.847,
      reward_improvement: 0.12,
      episodes_completed: 4500,
      avg_episode_length: 23.4,
      success_rate: 0.78,
      model_artifact_path: 's3://aura-models-prod/swe-rl/batch-47/final/',
      evaluation_score: 0.823,
    },
    session_id: 'sess-gpu-8x9y0z1a',
    request_id: 'req-7s8t9u0v1w2x',
    triggered_by: 'pipeline',
    tags: ['swe-rl', 'adr-050', 'training', 'high-priority', 'batch-47'],
  },
  // Failed - Vulnerability training (OOM)
  {
    job_id: 'gpu-job-r0s1t2u3',
    user_id: 'usr-s7t8u9v0',
    user_email: 'sarah.chen@acme-corp.com',
    user_name: 'Sarah Chen',
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    team_id: 'team-security-ml',
    team_name: 'Security ML Research',
    project_id: 'proj-vuln-detect-3k7',
    project_name: 'Vulnerability Detection System',
    job_type: 'vulnerability_training',
    job_title: 'Large Dataset Vulnerability Training (Experimental)',
    status: 'failed',
    priority: 'normal',
    config: {
      dataset_id: 'ds-vuln-large-experimental',
      dataset_version: '1.0.0-beta',
      base_model: 'codebert-vuln-classifier-v3',
      epochs: 50,
      batch_size: 64,
      learning_rate: 0.0001,
      warmup_steps: 1000,
      weight_decay: 0.01,
      eval_split: 0.2,
      vulnerability_categories: ['all'],
      gradient_accumulation_steps: 4,
    },
    gpu_type: 'nvidia-a10g',
    gpu_memory_gb: 16,
    gpu_memory_used_gb: 15.8,
    checkpoint_enabled: true,
    checkpoint_s3_path: 's3://aura-checkpoints-prod/acme-corp/gpu-job-r0s1t2u3/',
    checkpoint_count: 2,
    last_checkpoint_at: new Date(Date.now() - 25.2 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(),
    started_at: new Date(Date.now() - 25.5 * 60 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString(),
    progress_percent: 12,
    files_processed: null,
    files_total: null,
    cost_usd: 0.12,
    cost_breakdown: { compute: 0.11, storage: 0.01, network: 0.00 },
    kubernetes_job_name: 'gpu-vuln-r0s1t2u3-acme',
    kubernetes_namespace: 'aura-gpu-jobs',
    kubernetes_node: 'gpu-node-pool-a10g-3',
    error_message: 'CUDA out of memory. Tried to allocate 4.5 GiB. GPU 0 has a total capacity of 15.89 GiB of which 892.0 MiB is free.',
    error_type: 'oom',
    error_details: {
      cuda_version: '12.1',
      pytorch_version: '2.1.0',
      peak_memory_gb: 15.8,
      requested_allocation_gb: 4.5,
      recommendation: 'Reduce batch_size from 64 to 32, or use gradient checkpointing',
      recoverable: true,
      last_successful_checkpoint: 's3://aura-checkpoints-prod/acme-corp/gpu-job-r0s1t2u3/checkpoint-epoch-6/',
    },
    session_id: 'sess-gpu-2b3c4d5e',
    request_id: 'req-1y2z3a4b5c6d',
    triggered_by: 'manual',
    tags: ['security', 'training', 'experimental', 'large-dataset', 'failed'],
  },
];

// Production-realistic GPU resource metrics
const mockGPUResources = {
  // Cluster capacity
  gpus_in_use: 1,
  gpus_total: 4,
  gpus_available: 3,
  gpu_types: {
    'nvidia-a100': { total: 1, in_use: 0, available: 1 },
    'nvidia-a10g': { total: 2, in_use: 1, available: 1 },
    'nvidia-t4': { total: 1, in_use: 0, available: 1 },
  },
  // Queue status
  queue_depth: 2,
  estimated_wait_minutes: 15,
  queue_by_priority: { high: 0, normal: 1, low: 1 },
  // Cost tracking
  cost_today_usd: 2.47,
  cost_delta_percent: 12.5,
  cost_mtd_usd: 47.82,
  budget_limit_usd: 100.00,
  budget_utilization_percent: 47.82,
  // Node status
  nodes_active: 1,
  nodes_scaling: 0,
  nodes_total: 2,
  node_details: [
    {
      node_name: 'gpu-node-pool-a10g-1',
      instance_type: 'g5.xlarge',
      gpu_type: 'nvidia-a10g',
      status: 'ready',
      gpus_total: 1,
      gpus_in_use: 1,
      memory_total_gb: 16,
      memory_used_gb: 6.4,
      jobs_running: 1,
      uptime_hours: 4.2,
      spot_instance: true,
    },
    {
      node_name: 'gpu-node-pool-a100-1',
      instance_type: 'p4d.24xlarge',
      gpu_type: 'nvidia-a100',
      status: 'idle',
      gpus_total: 1,
      gpus_in_use: 0,
      memory_total_gb: 40,
      memory_used_gb: 0,
      jobs_running: 0,
      uptime_hours: 0,
      spot_instance: false,
    },
  ],
  // Real-time metrics
  gpu_utilization_percent: 78,
  gpu_memory_used_gb: 6.4,
  gpu_memory_total_gb: 16,
  // Health status
  cluster_health: 'healthy',
  last_health_check: new Date(Date.now() - 30 * 1000).toISOString(),
  active_alerts: [],
  // Organization context
  organization_id: 'org-acme-corp-7x2',
  organization_name: 'Acme Corporation',
};

// Production-realistic queue metrics
const mockQueueMetrics = {
  // Queue summary
  total_queued: 2,
  total_running: 1,
  total_pending_approval: 0,
  // Breakdown by priority
  by_priority: {
    high: 0,
    normal: 1,
    low: 1,
  },
  // Breakdown by organization
  by_organization: {
    'org-acme-corp-7x2': { queued: 2, running: 1, name: 'Acme Corporation' },
  },
  // Breakdown by job type
  by_job_type: {
    embedding_generation: { queued: 0, running: 1 },
    vulnerability_training: { queued: 1, running: 0 },
    memory_consolidation: { queued: 1, running: 0 },
    swe_rl_training: { queued: 0, running: 0 },
    local_inference: { queued: 0, running: 0 },
  },
  // Running job details
  running_jobs: 1,
  running_by_priority: {
    high: 0,
    normal: 1,
    low: 0,
  },
  running_job_ids: ['gpu-job-e7f2a1b4'],
  // Wait time statistics
  avg_wait_time_seconds: 420,
  p50_wait_time_seconds: 360,
  p90_wait_time_seconds: 720,
  p99_wait_time_seconds: 1200,
  oldest_queued_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  oldest_queued_job_id: 'gpu-job-b3c4d5e6',
  estimated_drain_time_minutes: 45,
  // Preemption and fairness
  preemptions_last_hour: 0,
  preemptions_last_24h: 2,
  starvation_promotions_last_hour: 0,
  starvation_promotions_last_24h: 1,
  fairness_score: 0.94,
  // Throughput metrics
  jobs_completed_last_hour: 3,
  jobs_completed_last_24h: 47,
  avg_job_duration_minutes: 28.5,
  success_rate_last_24h: 0.957,
  // Timestamp
  metrics_timestamp: new Date().toISOString(),
  metrics_window_minutes: 60,
};

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

// GPU Job API Functions

/**
 * Get list of GPU jobs for organization
 * @param {Object} options - Query options
 * @param {string} [options.status] - Filter by status (queued, running, completed, failed)
 * @param {number} [options.limit] - Result limit
 * @returns {Promise<{jobs: Array, next_cursor: string|null}>}
 */
export async function getGPUJobs({ status, limit = 50 } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    let jobs = [...mockGPUJobs];
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

  return apiRequest(`/api/v1/gpu/jobs?${params.toString()}`);
}

/**
 * Get a specific GPU job
 * @param {string} jobId - Job ID
 * @returns {Promise<Object>}
 */
export async function getGPUJob(jobId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const job = mockGPUJobs.find((j) => j.job_id === jobId);
    if (!job) {
      throw new Error('GPU job not found');
    }
    return job;
  }

  return apiRequest(`/api/v1/gpu/jobs/${jobId}`);
}

/**
 * Submit a new GPU job
 * @param {Object} jobData - Job configuration
 * @returns {Promise<Object>}
 */
export async function submitGPUJob(jobData) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));

    const newJob = {
      job_id: `gpu-job-${Date.now()}`,
      user_id: 'dev-user',
      organization_id: 'org-default',
      ...jobData,
      status: 'queued',
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
      progress_percent: null,
      cost_usd: null,
      kubernetes_job_name: null,
      error_message: null,
      error_type: null,
      queue_position: mockGPUJobs.filter((j) => j.status === 'queued').length + 1,
      estimated_wait_minutes: 15 + Math.floor(Math.random() * 30),
    };

    mockGPUJobs.unshift(newJob);
    return newJob;
  }

  return apiRequest('/api/v1/gpu/jobs', {
    method: 'POST',
    body: JSON.stringify(jobData),
  });
}

/**
 * Cancel a GPU job
 * @param {string} jobId - Job ID
 * @returns {Promise<Object>}
 */
export async function cancelGPUJob(jobId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const job = mockGPUJobs.find((j) => j.job_id === jobId);
    if (!job) {
      throw new Error('GPU job not found');
    }

    if (!['queued', 'running', 'starting'].includes(job.status)) {
      throw new Error(`Cannot cancel job with status ${job.status}`);
    }

    job.status = 'cancelled';
    job.completed_at = new Date().toISOString();

    return job;
  }

  return apiRequest(`/api/v1/gpu/jobs/${jobId}`, {
    method: 'DELETE',
  });
}

/**
 * Boost priority of a queued job
 * @param {string} jobId - Job ID
 * @returns {Promise<Object>}
 */
export async function boostJobPriority(jobId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    const job = mockGPUJobs.find((j) => j.job_id === jobId);
    if (!job) {
      throw new Error('GPU job not found');
    }

    if (job.status !== 'queued') {
      throw new Error('Can only boost priority of queued jobs');
    }

    const priorityOrder = ['low', 'normal', 'high'];
    const currentIndex = priorityOrder.indexOf(job.priority);
    if (currentIndex < priorityOrder.length - 1) {
      job.priority = priorityOrder[currentIndex + 1];
    }

    return job;
  }

  return apiRequest(`/api/v1/gpu/jobs/${jobId}/boost`, {
    method: 'POST',
  });
}

// GPU Resource API Functions

/**
 * Get current GPU resource status
 * @returns {Promise<Object>}
 */
export async function getGPUResources() {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Add some randomness to make it feel live
    return {
      ...mockGPUResources,
      gpu_utilization_percent: mockGPUResources.gpu_utilization_percent + Math.floor(Math.random() * 10) - 5,
      gpu_memory_used_gb: mockGPUResources.gpu_memory_used_gb + (Math.random() * 0.5 - 0.25),
    };
  }

  return apiRequest('/api/v1/gpu/resources');
}

/**
 * Get GPU queue metrics
 * @returns {Promise<Object>}
 */
export async function getGPUQueueMetrics() {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    return mockQueueMetrics;
  }

  return apiRequest('/api/v1/gpu/queue/metrics');
}

/**
 * Get queue position estimate for a job
 * @param {string} jobId - Job ID
 * @returns {Promise<Object>}
 */
export async function getQueuePosition(jobId) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const job = mockGPUJobs.find((j) => j.job_id === jobId);
    if (!job) {
      throw new Error('GPU job not found');
    }

    return {
      job_id: jobId,
      queue_position: job.queue_position || 0,
      jobs_ahead: (job.queue_position || 1) - 1,
      jobs_ahead_by_priority: {
        high: 0,
        normal: job.queue_position > 1 ? 1 : 0,
        low: 0,
      },
      estimated_wait_minutes: job.estimated_wait_minutes || 0,
      estimated_start_time: new Date(Date.now() + (job.estimated_wait_minutes || 0) * 60 * 1000).toISOString(),
      confidence: 0.75,
      factors: ['1 normal job ahead: +12 min'],
      gpu_scaling_required: false,
      preemption_possible: false,
    };
  }

  return apiRequest(`/api/v1/gpu/queue/position/${jobId}`);
}

/**
 * Estimate queue position for a new job before submission
 * @param {Object} params - Job parameters
 * @param {string} params.priority - Priority level
 * @param {string} params.job_type - Job type
 * @returns {Promise<Object>}
 */
export async function estimateQueuePosition({ priority, job_type }) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const queuedJobs = mockGPUJobs.filter((j) => j.status === 'queued');
    const jobsAhead = queuedJobs.filter((j) => {
      const priorityOrder = { high: 0, normal: 1, low: 2 };
      return priorityOrder[j.priority] <= priorityOrder[priority];
    }).length;

    return {
      job_id: 'estimate',
      queue_position: jobsAhead + 1,
      jobs_ahead: jobsAhead,
      jobs_ahead_by_priority: {
        high: 0,
        normal: jobsAhead,
        low: 0,
      },
      estimated_wait_minutes: jobsAhead * 15,
      estimated_start_time: new Date(Date.now() + jobsAhead * 15 * 60 * 1000).toISOString(),
      confidence: 0.6,
      factors: jobsAhead > 0 ? [`${jobsAhead} jobs ahead: +${jobsAhead * 15} min`] : ['No jobs ahead'],
      gpu_scaling_required: mockGPUResources.gpus_in_use === 0,
      preemption_possible: priority === 'high' && queuedJobs.some((j) => j.priority === 'low'),
    };
  }

  return apiRequest('/api/v1/gpu/queue/estimate', {
    method: 'POST',
    body: JSON.stringify({ priority, job_type }),
  });
}

// GPU Cost API Functions

/**
 * Get GPU cost summary for a period
 * @param {Object} options - Query options
 * @param {string} [options.start_date] - Start date (ISO string)
 * @param {string} [options.end_date] - End date (ISO string)
 * @returns {Promise<Object>}
 */
export async function getGPUCosts({ start_date, end_date } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    return {
      total_cost_usd: 47.82,
      gpu_hours: 142.5,
      jobs_count: 89,
      avg_job_cost_usd: 0.54,
      by_job_type: {
        embedding_generation: 18.23,
        swe_rl_training: 24.15,
        vulnerability_training: 4.12,
        memory_consolidation: 1.32,
      },
      daily_costs: Array.from({ length: 7 }, (_, i) => ({
        date: new Date(Date.now() - (6 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        cost_usd: 5 + Math.random() * 10,
      })),
      budget_used_usd: 47.82,
      budget_total_usd: 100,
    };
  }

  const params = new URLSearchParams();
  if (start_date) params.append('start_date', start_date);
  if (end_date) params.append('end_date', end_date);

  return apiRequest(`/api/v1/gpu/costs?${params.toString()}`);
}

/**
 * Get budget status for the organization
 * @returns {Promise<Object>}
 */
export async function getBudgetStatus() {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 200));

    const budgetUsed = 47.82;
    const budgetTotal = 100;
    const usagePercent = (budgetUsed / budgetTotal) * 100;
    const daysElapsed = new Date().getDate();
    const daysInMonth = 30;
    const dailyAverage = budgetUsed / daysElapsed;
    const forecast = dailyAverage * daysInMonth;

    return {
      budget_limit_usd: budgetTotal,
      budget_used_usd: budgetUsed,
      budget_remaining_usd: budgetTotal - budgetUsed,
      usage_percent: usagePercent,
      forecast_end_of_month_usd: forecast,
      forecast_confidence_low_usd: forecast * 0.85,
      forecast_confidence_high_usd: forecast * 1.15,
      daily_average_usd: dailyAverage,
      days_elapsed: daysElapsed,
      days_remaining: daysInMonth - daysElapsed,
      alert_threshold_percent: 80,
      alert_triggered: usagePercent >= 80,
    };
  }

  return apiRequest('/api/v1/gpu/budget/status');
}

/**
 * Update budget settings
 * @param {Object} settings - Budget settings
 * @returns {Promise<Object>}
 */
export async function updateBudgetSettings(settings) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    return {
      ...settings,
      updated_at: new Date().toISOString(),
    };
  }

  return apiRequest('/api/v1/gpu/budget/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

/**
 * Get cost forecast
 * @returns {Promise<Object>}
 */
export async function getCostForecast() {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 250));

    const daysElapsed = new Date().getDate();
    const daysInMonth = 30;
    const currentTotal = 47.82;
    const dailyAvg = currentTotal / daysElapsed;
    const forecast = dailyAvg * daysInMonth;

    return {
      forecast_usd: forecast,
      confidence_low_usd: forecast * 0.85,
      confidence_high_usd: forecast * 1.15,
      daily_average_usd: dailyAvg,
      days_elapsed: daysElapsed,
      days_remaining: daysInMonth - daysElapsed,
      current_total_usd: currentTotal,
      trend: forecast > 100 ? 'over_budget' : forecast > 80 ? 'approaching' : 'on_track',
    };
  }

  return apiRequest('/api/v1/gpu/costs/forecast');
}

// Job Logs API Functions

/**
 * Get job logs
 * @param {string} jobId - Job ID
 * @param {Object} options - Query options
 * @param {number} [options.lines] - Number of lines to return
 * @param {boolean} [options.follow] - Whether to follow (stream) logs
 * @returns {Promise<Object>}
 */
export async function getJobLogs(jobId, { lines = 100 } = {}) {
  if (DEV_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 300));

    const job = mockGPUJobs.find((j) => j.job_id === jobId);
    if (!job) {
      throw new Error('GPU job not found');
    }

    const mockLogs = [
      { timestamp: new Date(Date.now() - 20 * 60 * 1000).toISOString(), level: 'INFO', message: 'Starting GPU job initialization...' },
      { timestamp: new Date(Date.now() - 19.5 * 60 * 1000).toISOString(), level: 'INFO', message: 'Loading model: codebert-base' },
      { timestamp: new Date(Date.now() - 19 * 60 * 1000).toISOString(), level: 'INFO', message: 'Model loaded successfully. GPU memory: 4.2 GB / 16 GB' },
      { timestamp: new Date(Date.now() - 18.5 * 60 * 1000).toISOString(), level: 'INFO', message: 'Cloning repository: backend-services@main' },
      { timestamp: new Date(Date.now() - 18 * 60 * 1000).toISOString(), level: 'INFO', message: 'Repository cloned. Found 1,234 files to process.' },
      { timestamp: new Date(Date.now() - 17.5 * 60 * 1000).toISOString(), level: 'INFO', message: 'Starting batch embedding generation...' },
      { timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(), level: 'INFO', message: 'Progress: 25% (308/1234 files)' },
      { timestamp: new Date(Date.now() - 12 * 60 * 1000).toISOString(), level: 'INFO', message: 'Progress: 50% (617/1234 files)' },
      { timestamp: new Date(Date.now() - 8 * 60 * 1000).toISOString(), level: 'INFO', message: 'Checkpoint saved to S3' },
      { timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(), level: 'INFO', message: 'Progress: 67% (827/1234 files)' },
    ];

    return {
      job_id: jobId,
      logs: mockLogs.slice(0, lines),
      has_more: false,
    };
  }

  const params = new URLSearchParams();
  if (lines) params.append('lines', lines.toString());

  return apiRequest(`/api/v1/gpu/jobs/${jobId}/logs?${params.toString()}`);
}

// WebSocket Connection for Real-time Updates

/**
 * WebSocket message types for GPU jobs
 */
export const GPUWSMessageType = {
  // Client -> Server
  SUBSCRIBE_JOB: 'subscribe_job',
  UNSUBSCRIBE_JOB: 'unsubscribe_job',
  SUBSCRIBE_QUEUE: 'subscribe_queue',

  // Server -> Client
  JOB_STARTED: 'job_started',
  JOB_PROGRESS: 'job_progress',
  JOB_COMPLETED: 'job_completed',
  JOB_FAILED: 'job_failed',
  JOB_CANCELLED: 'job_cancelled',
  QUEUE_UPDATED: 'queue_updated',
  RESOURCE_UPDATED: 'resource_updated',
  LOG_ENTRY: 'log_entry',
  ERROR: 'error',
  HEARTBEAT: 'heartbeat',
};

/**
 * Create a WebSocket connection for GPU job updates
 * @param {Object} options - Connection options
 * @param {Function} options.onMessage - Message handler
 * @param {Function} options.onError - Error handler
 * @param {Function} options.onClose - Close handler
 * @returns {Object} WebSocket connection with send/close methods
 */
export function createGPUWebSocket({ onMessage, onError, onClose }) {
  if (DEV_MODE) {
    // Mock WebSocket for development
    let interval = null;
    let subscriptions = new Set();

    const mockWs = {
      send: (data) => {
        const message = JSON.parse(data);
        if (message.type === GPUWSMessageType.SUBSCRIBE_JOB) {
          subscriptions.add(message.job_id);
        } else if (message.type === GPUWSMessageType.UNSUBSCRIBE_JOB) {
          subscriptions.delete(message.job_id);
        }
      },
      close: () => {
        if (interval) {
          clearInterval(interval);
          interval = null;
        }
      },
    };

    // Simulate progress updates
    interval = setInterval(() => {
      const runningJob = mockGPUJobs.find((j) => j.status === 'running');
      if (runningJob && subscriptions.has(runningJob.job_id)) {
        runningJob.progress_percent = Math.min(100, (runningJob.progress_percent || 0) + 1);
        runningJob.cost_usd = (runningJob.cost_usd || 0) + 0.01;

        onMessage?.({
          type: GPUWSMessageType.JOB_PROGRESS,
          job_id: runningJob.job_id,
          progress_percent: runningJob.progress_percent,
          cost_usd: runningJob.cost_usd,
          estimated_remaining_minutes: Math.max(0, (runningJob.estimated_remaining_minutes || 0) - 0.5),
        });
      }

      // Send heartbeat
      onMessage?.({
        type: GPUWSMessageType.HEARTBEAT,
        timestamp: new Date().toISOString(),
      });
    }, 5000);

    return mockWs;
  }

  // Real WebSocket connection
  const wsUrl = `${WS_URL}/ws/gpu`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      onMessage?.(message);
    } catch (err) {
      console.error('Failed to parse GPU WebSocket message:', err);
    }
  };

  ws.onerror = (error) => {
    console.error('GPU WebSocket error:', error);
    onError?.(error);
  };

  ws.onclose = (event) => {
    console.log('GPU WebSocket closed:', event.code, event.reason);
    onClose?.(event);
  };

  return {
    send: (data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(typeof data === 'string' ? data : JSON.stringify(data));
      }
    },
    close: () => ws.close(),
  };
}

// Utility Functions

/**
 * Format GPU memory size
 * @param {number} gb - Memory in GB
 * @returns {string}
 */
export function formatGPUMemory(gb) {
  if (gb < 1) return `${Math.round(gb * 1024)} MB`;
  return `${gb.toFixed(1)} GB`;
}

/**
 * Format cost in USD
 * @param {number} usd - Cost in USD
 * @returns {string}
 */
export function formatCost(usd) {
  if (usd === null || usd === undefined) return '-';
  return `$${usd.toFixed(2)}`;
}

/**
 * Format duration in human-readable format
 * @param {number} minutes - Duration in minutes
 * @returns {string}
 */
export function formatDuration(minutes) {
  if (!minutes || minutes < 0) return '-';

  if (minutes < 60) {
    return `${Math.round(minutes)} min`;
  } else {
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  }
}

/**
 * Get status badge color for GPU jobs
 * @param {string} status - Job status
 * @returns {string}
 */
export function getGPUStatusColor(status) {
  const colors = {
    queued: 'warning',
    starting: 'info',
    running: 'aura',
    completed: 'success',
    failed: 'critical',
    cancelled: 'surface',
  };
  return colors[status] || 'surface';
}

/**
 * Get priority badge color
 * @param {string} priority - Priority level
 * @returns {string}
 */
export function getGPUPriorityColor(priority) {
  const colors = {
    high: 'critical',
    normal: 'info',
    low: 'surface',
  };
  return colors[priority] || 'surface';
}

/**
 * Get job type info
 * @param {string} jobType - Job type value
 * @returns {Object|null}
 */
export function getJobTypeInfo(jobType) {
  return GPU_JOB_TYPES.find((t) => t.value === jobType) || null;
}

/**
 * Get error type info
 * @param {string} errorType - Error type value
 * @returns {Object|null}
 */
export function getErrorTypeInfo(errorType) {
  return GPU_ERROR_TYPES[errorType] || null;
}
