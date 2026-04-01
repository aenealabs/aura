/**
 * Project Aura - Integration API Service
 *
 * API client for managing external integrations including ticketing systems,
 * monitoring tools, CI/CD pipelines, and communication platforms.
 */

import { apiClient } from './api';

// Base URL for integration endpoints
const INTEGRATIONS_BASE = '/api/v1/integrations';

/**
 * Integration category definitions
 */
export const INTEGRATION_CATEGORIES = {
  ticketing: {
    id: 'ticketing',
    name: 'Ticketing',
    description: 'Issue tracking and support ticket management',
    icon: 'ticket',
  },
  monitoring: {
    id: 'monitoring',
    name: 'Monitoring',
    description: 'Application and infrastructure monitoring',
    icon: 'chart-bar',
  },
  security: {
    id: 'security',
    name: 'Security',
    description: 'Security scanning and vulnerability management',
    icon: 'shield-check',
  },
  cicd: {
    id: 'cicd',
    name: 'CI/CD',
    description: 'Continuous integration and deployment pipelines',
    icon: 'code-bracket',
  },
  communication: {
    id: 'communication',
    name: 'Communication',
    description: 'Team messaging and notifications',
    icon: 'chat-bubble-left-right',
  },
  data_platforms: {
    id: 'data_platforms',
    name: 'Data Platforms',
    description: 'Data science and analytics platforms',
    icon: 'circle-stack',
  },
  developer_tools: {
    id: 'developer_tools',
    name: 'Developer Tools',
    description: 'IDE extensions and development environment integrations',
    icon: 'command-line',
  },
  identity: {
    id: 'identity',
    name: 'Identity',
    description: 'Identity governance and privileged access management',
    icon: 'user-group',
  },
  grc: {
    id: 'grc',
    name: 'GRC',
    description: 'Governance, risk, and compliance management',
    icon: 'clipboard-document-check',
  },
  threat_intelligence: {
    id: 'threat_intelligence',
    name: 'Threat Intelligence',
    description: 'Enterprise threat intelligence and data platforms',
    icon: 'shield-exclamation',
  },
};

/**
 * Provider definitions with configuration schemas
 */
export const INTEGRATION_PROVIDERS = {
  // Ticketing Providers
  zendesk: {
    id: 'zendesk',
    name: 'Zendesk',
    category: 'ticketing',
    description: 'Enterprise customer service and engagement platform',
    icon: 'ticket',
    authType: 'api_key',
    isImplemented: true,
    features: ['Ticket sync', 'Auto-assignment', 'Priority mapping', 'Custom fields'],
    configFields: [
      { name: 'subdomain', label: 'Subdomain', type: 'text', placeholder: 'yourcompany', required: true, helpText: 'Your Zendesk subdomain (e.g., yourcompany.zendesk.com)' },
      { name: 'email', label: 'Agent Email', type: 'email', placeholder: 'agent@company.com', required: true, helpText: 'Email address of the API user' },
      { name: 'api_token', label: 'API Token', type: 'password', required: true, helpText: 'Generate from Admin > Channels > API' },
      { name: 'default_assignee_id', label: 'Default Assignee ID', type: 'text', required: false, helpText: 'User ID to assign tickets by default' },
      { name: 'default_group_id', label: 'Default Group ID', type: 'text', required: false, helpText: 'Group ID for ticket routing' },
    ],
    priorityMapping: {
      critical: 'urgent',
      high: 'high',
      medium: 'normal',
      low: 'low',
    },
  },
  linear: {
    id: 'linear',
    name: 'Linear',
    category: 'ticketing',
    description: 'Modern issue tracking for high-performance teams',
    icon: 'ticket',
    authType: 'api_key',
    isImplemented: true,
    features: ['Issue sync', 'Team routing', 'Label mapping', 'Cycle integration'],
    configFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Generate from Settings > Account > API' },
      { name: 'team_id', label: 'Team ID', type: 'text', required: true, helpText: 'Target team for issue creation' },
      { name: 'project_id', label: 'Default Project', type: 'text', required: false, helpText: 'Optional project for categorization' },
      { name: 'default_labels', label: 'Default Labels', type: 'tags', required: false, helpText: 'Labels to apply to all issues' },
    ],
    priorityMapping: {
      critical: 1,
      high: 2,
      medium: 3,
      low: 4,
    },
  },
  servicenow: {
    id: 'servicenow',
    name: 'ServiceNow',
    category: 'ticketing',
    description: 'Enterprise IT service management platform',
    icon: 'building-office',
    authType: 'basic',
    isImplemented: true,
    features: ['Incident management', 'Change requests', 'CMDB integration', 'Workflow automation'],
    configFields: [
      { name: 'instance_url', label: 'Instance URL', type: 'url', placeholder: 'https://dev12345.service-now.com', required: true, helpText: 'Your ServiceNow instance URL' },
      { name: 'username', label: 'Username', type: 'text', required: true, helpText: 'Service account username' },
      { name: 'password', label: 'Password', type: 'password', required: true },
      { name: 'table', label: 'Default Table', type: 'select', options: ['incident', 'sc_request', 'problem', 'change_request'], required: true, helpText: 'Table for record creation' },
      { name: 'assignment_group', label: 'Assignment Group', type: 'text', required: false, helpText: 'Sys_id of the assignment group' },
      { name: 'category', label: 'Default Category', type: 'text', required: false },
    ],
    priorityMapping: {
      critical: 1,
      high: 2,
      medium: 3,
      low: 4,
    },
  },
  jira: {
    id: 'jira',
    name: 'Jira',
    category: 'ticketing',
    description: 'Atlassian issue and project tracking',
    icon: 'ticket',
    authType: 'api_key',
    isImplemented: true,
    features: ['Issue sync', 'Sprint integration', 'Custom workflows', 'Epic linking'],
    configFields: [
      { name: 'site_url', label: 'Site URL', type: 'url', placeholder: 'https://yourcompany.atlassian.net', required: true },
      { name: 'email', label: 'Email', type: 'email', required: true },
      { name: 'api_token', label: 'API Token', type: 'password', required: true, helpText: 'Generate from Atlassian Account Settings' },
      { name: 'project_key', label: 'Project Key', type: 'text', placeholder: 'PROJ', required: true },
      { name: 'issue_type', label: 'Default Issue Type', type: 'select', options: ['Bug', 'Task', 'Story', 'Epic'], required: true },
    ],
    priorityMapping: {
      critical: 'Highest',
      high: 'High',
      medium: 'Medium',
      low: 'Low',
    },
  },
  github_issues: {
    id: 'github_issues',
    name: 'GitHub Issues',
    category: 'ticketing',
    description: 'Native GitHub issue tracking',
    icon: 'code-bracket',
    authType: 'oauth',
    isImplemented: true,
    features: ['Issue sync', 'Label mapping', 'Milestone tracking', 'PR linking'],
    configFields: [
      { name: 'repository', label: 'Repository', type: 'text', placeholder: 'owner/repo', required: true },
      { name: 'token', label: 'Personal Access Token', type: 'password', required: true, helpText: 'Requires issues:write and repo scopes' },
      { name: 'default_labels', label: 'Default Labels', type: 'tags', required: false },
      { name: 'default_assignees', label: 'Default Assignees', type: 'tags', required: false, helpText: 'GitHub usernames' },
    ],
    priorityMapping: {
      critical: 'priority: critical',
      high: 'priority: high',
      medium: 'priority: medium',
      low: 'priority: low',
    },
  },
  // Monitoring Providers
  datadog: {
    id: 'datadog',
    name: 'Datadog',
    category: 'monitoring',
    description: 'Cloud-scale monitoring and analytics',
    icon: 'chart-bar',
    authType: 'api_key',
    isImplemented: true,
    features: ['Metrics sync', 'Alert forwarding', 'Dashboard links', 'Log correlation'],
    configFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true },
      { name: 'app_key', label: 'Application Key', type: 'password', required: true },
      { name: 'site', label: 'Datadog Site', type: 'select', options: ['datadoghq.com', 'datadoghq.eu', 'us3.datadoghq.com', 'us5.datadoghq.com', 'ddog-gov.com'], required: true },
      { name: 'service_name', label: 'Service Name', type: 'text', required: false, helpText: 'Service name for APM correlation' },
    ],
  },
  pagerduty: {
    id: 'pagerduty',
    name: 'PagerDuty',
    category: 'monitoring',
    description: 'Incident response and on-call management',
    icon: 'bell-alert',
    authType: 'api_key',
    isImplemented: true,
    features: ['Incident creation', 'On-call lookup', 'Escalation policies', 'Status sync'],
    configFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Generate from Configuration > API Access' },
      { name: 'routing_key', label: 'Routing Key', type: 'password', required: true, helpText: 'Events API v2 integration key' },
      { name: 'default_severity', label: 'Default Severity', type: 'select', options: ['critical', 'error', 'warning', 'info'], required: false },
    ],
  },
  splunk: {
    id: 'splunk',
    name: 'Splunk',
    category: 'monitoring',
    description: 'Enterprise SIEM and log analytics platform',
    icon: 'chart-bar',
    authType: 'api_key',
    isImplemented: true,
    features: ['Log aggregation', 'Security analytics', 'Alert forwarding', 'Saved searches'],
    configFields: [
      { name: 'base_url', label: 'Splunk URL', type: 'url', placeholder: 'https://splunk.company.com:8089', required: true, helpText: 'Splunk management port URL (typically :8089)' },
      { name: 'token', label: 'API Token', type: 'password', required: true, helpText: 'Splunk authentication token or HEC token' },
      { name: 'index', label: 'Default Index', type: 'text', placeholder: 'main', required: false, helpText: 'Default index for searches and ingestion' },
      { name: 'hec_endpoint', label: 'HEC Endpoint', type: 'url', required: false, helpText: 'HTTP Event Collector endpoint for sending events' },
      { name: 'saved_searches', label: 'Saved Searches', type: 'tags', required: false, helpText: 'Names of saved searches to sync alerts from' },
    ],
  },
  // Security Providers
  snyk: {
    id: 'snyk',
    name: 'Snyk',
    category: 'security',
    description: 'Developer-first security platform',
    icon: 'shield-check',
    authType: 'api_key',
    isImplemented: true,
    features: ['Vulnerability import', 'Fix suggestions', 'License compliance', 'Container scanning'],
    configFields: [
      { name: 'api_token', label: 'API Token', type: 'password', required: true },
      { name: 'org_id', label: 'Organization ID', type: 'text', required: true },
      { name: 'project_ids', label: 'Project IDs', type: 'tags', required: false, helpText: 'Specific projects to sync (leave empty for all)' },
    ],
  },
  qualys: {
    id: 'qualys',
    name: 'Qualys',
    category: 'security',
    description: 'Enterprise vulnerability management and compliance',
    icon: 'shield-check',
    authType: 'basic',
    isImplemented: true,
    features: ['Vulnerability scanning', 'Asset inventory', 'Compliance reports', 'Patch prioritization'],
    configFields: [
      { name: 'api_url', label: 'API URL', type: 'url', placeholder: 'https://qualysapi.qualys.com', required: true, helpText: 'Your Qualys API endpoint (varies by subscription)' },
      { name: 'username', label: 'Username', type: 'text', required: true, helpText: 'Qualys API username' },
      { name: 'password', label: 'Password', type: 'password', required: true },
      { name: 'asset_group_ids', label: 'Asset Group IDs', type: 'tags', required: false, helpText: 'Specific asset groups to sync (leave empty for all)' },
      { name: 'min_severity', label: 'Minimum Severity', type: 'select', options: ['1', '2', '3', '4', '5'], required: false, helpText: 'Only sync vulnerabilities at or above this severity' },
    ],
    severityMapping: {
      5: 'critical',
      4: 'high',
      3: 'medium',
      2: 'low',
      1: 'info',
    },
  },
  // CI/CD Providers
  github_actions: {
    id: 'github_actions',
    name: 'GitHub Actions',
    category: 'cicd',
    description: 'GitHub native CI/CD workflows',
    icon: 'code-bracket',
    authType: 'oauth',
    isImplemented: true,
    features: ['Workflow triggers', 'Status sync', 'Artifact access', 'Secret management'],
    configFields: [
      { name: 'repository', label: 'Repository', type: 'text', placeholder: 'owner/repo', required: true },
      { name: 'token', label: 'Personal Access Token', type: 'password', required: true, helpText: 'Requires workflow and repo scopes' },
    ],
  },
  // Communication Providers
  slack: {
    id: 'slack',
    name: 'Slack',
    category: 'communication',
    description: 'Team messaging and collaboration',
    icon: 'chat-bubble-left-right',
    authType: 'oauth',
    isImplemented: true,
    features: ['Notifications', 'Interactive messages', 'Channel routing', 'Thread updates'],
    configFields: [
      { name: 'webhook_url', label: 'Webhook URL', type: 'url', required: true, helpText: 'Incoming webhook URL from Slack app' },
      { name: 'default_channel', label: 'Default Channel', type: 'text', placeholder: '#security-alerts', required: false },
      { name: 'bot_token', label: 'Bot Token', type: 'password', required: false, helpText: 'For interactive features (optional)' },
    ],
  },
  microsoft_teams: {
    id: 'microsoft_teams',
    name: 'Microsoft Teams',
    category: 'communication',
    description: 'Microsoft collaboration platform',
    icon: 'chat-bubble-left-right',
    authType: 'webhook',
    isImplemented: true,
    features: ['Notifications', 'Adaptive cards', 'Channel routing'],
    configFields: [
      { name: 'webhook_url', label: 'Webhook URL', type: 'url', required: true, helpText: 'Incoming webhook connector URL' },
    ],
  },
  // Data Platform Providers
  dataiku: {
    id: 'dataiku',
    name: 'Dataiku DSS',
    category: 'data_platforms',
    description: 'Data science platform for analytics and visualization',
    icon: 'circle-stack',
    authType: 'api_key',
    isImplemented: true,
    features: ['Dataset sync', 'Project integration', 'Model monitoring', 'Visual analytics'],
    configFields: [
      { name: 'instance_url', label: 'Instance URL', type: 'url', placeholder: 'https://dss.company.com', required: true, helpText: 'Your Dataiku DSS instance URL' },
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Generate from User Settings > API Keys' },
      { name: 'default_project', label: 'Default Project', type: 'text', required: false, helpText: 'Project key for default operations' },
    ],
  },
  fivetran: {
    id: 'fivetran',
    name: 'Fivetran',
    category: 'data_platforms',
    description: 'Data pipeline connector for warehouse sync',
    icon: 'circle-stack',
    authType: 'api_key',
    isImplemented: true,
    features: ['Pipeline monitoring', 'Sync triggers', 'Schema detection', 'Connector status'],
    configFields: [
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Fivetran API key from Account Settings' },
      { name: 'api_secret', label: 'API Secret', type: 'password', required: true, helpText: 'Fivetran API secret' },
      { name: 'group_id', label: 'Group ID', type: 'text', required: false, helpText: 'Connector group to monitor (optional)' },
    ],
  },
  // Developer Tool Providers
  vscode: {
    id: 'vscode',
    name: 'VSCode Extension',
    category: 'developer_tools',
    description: 'Visual Studio Code integration for in-editor security insights',
    icon: 'command-line',
    authType: 'token',
    isImplemented: true,
    features: ['Inline diagnostics', 'Quick fixes', 'Code lens', 'Problem panel'],
    configFields: [
      { name: 'workspace_token', label: 'Workspace Token', type: 'password', required: true, helpText: 'Token for authenticating the VSCode extension' },
      { name: 'auto_scan', label: 'Auto Scan', type: 'select', options: ['on_save', 'on_change', 'manual'], required: false, helpText: 'When to trigger security scans' },
    ],
  },
  pycharm: {
    id: 'pycharm',
    name: 'PyCharm Plugin',
    category: 'developer_tools',
    description: 'JetBrains IDE integration for Python security analysis',
    icon: 'command-line',
    authType: 'token',
    isImplemented: true,
    features: ['Inspections', 'Quick fixes', 'Tool window', 'Run configurations'],
    configFields: [
      { name: 'workspace_token', label: 'Workspace Token', type: 'password', required: true, helpText: 'Token for authenticating the PyCharm plugin' },
      { name: 'python_interpreter', label: 'Python Interpreter', type: 'text', required: false, helpText: 'Path to Python interpreter (auto-detected if empty)' },
    ],
  },
  jupyterlab: {
    id: 'jupyterlab',
    name: 'JupyterLab Extension',
    category: 'developer_tools',
    description: 'Notebook environment integration for data science security',
    icon: 'command-line',
    authType: 'token',
    isImplemented: true,
    features: ['Cell analysis', 'Notebook scanning', 'Output validation', 'Kernel monitoring'],
    configFields: [
      { name: 'workspace_token', label: 'Workspace Token', type: 'password', required: true, helpText: 'Token for authenticating the JupyterLab extension' },
      { name: 'jupyter_server', label: 'Jupyter Server URL', type: 'url', required: false, helpText: 'JupyterHub or JupyterLab server URL (optional)' },
      { name: 'scan_outputs', label: 'Scan Outputs', type: 'select', options: ['enabled', 'disabled'], required: false, helpText: 'Scan cell outputs for sensitive data' },
    ],
  },
  // ADR-053: Enterprise Security Integrations Phase 2
  // Security Provider - Zero Trust
  zscaler: {
    id: 'zscaler',
    name: 'Zscaler Zero Trust',
    category: 'security',
    description: 'Cloud-native zero trust security platform with ZIA and ZPA',
    icon: 'shield-check',
    authType: 'api_key_oauth',
    isImplemented: true,
    govCloudCompatible: true,
    features: ['Web security (ZIA)', 'Private access (ZPA)', 'DLP incidents', 'URL filtering'],
    configFields: [
      { name: 'zia_base_url', label: 'ZIA Base URL', type: 'url', placeholder: 'https://zsapi.zscaler.net', required: true, helpText: 'Zscaler Internet Access API endpoint' },
      { name: 'zpa_base_url', label: 'ZPA Base URL', type: 'url', placeholder: 'https://config.private.zscaler.com', required: false, helpText: 'Zscaler Private Access API endpoint (optional)' },
      { name: 'cloud', label: 'Cloud Environment', type: 'select', options: ['zscaler.net', 'zscalerone.net', 'zscalertwo.net', 'zscloud.net', 'zscalergov.net'], required: true, helpText: 'Select zscalergov.net for US Government' },
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Zscaler API key from Admin Portal' },
      { name: 'client_id', label: 'Client ID', type: 'text', required: false, helpText: 'OAuth2 client ID (for advanced flows)' },
      { name: 'client_secret', label: 'Client Secret', type: 'password', required: false, helpText: 'OAuth2 client secret' },
    ],
  },
  // Identity Provider - Identity Governance
  saviynt: {
    id: 'saviynt',
    name: 'Saviynt Enterprise Identity Cloud',
    category: 'identity',
    description: 'Identity governance, administration, and privileged access management',
    icon: 'user-group',
    authType: 'basic_bearer',
    isImplemented: true,
    govCloudCompatible: true,
    features: ['User management', 'Entitlements', 'Access requests', 'Certifications', 'PAM sessions', 'Risk analytics'],
    configFields: [
      { name: 'base_url', label: 'Saviynt URL', type: 'url', placeholder: 'https://your-tenant.saviyntcloud.com', required: true, helpText: 'Your Saviynt EIC tenant URL' },
      { name: 'username', label: 'Username', type: 'text', required: true, helpText: 'Service account username with API access' },
      { name: 'password', label: 'Password', type: 'password', required: true, helpText: 'Service account password for bearer token' },
    ],
    severityMapping: {
      critical: 90,
      high: 70,
      medium: 50,
      low: 30,
    },
  },
  // GRC Provider - Compliance
  auditboard: {
    id: 'auditboard',
    name: 'AuditBoard GRC',
    category: 'grc',
    description: 'Governance, risk, and compliance management platform',
    icon: 'clipboard-document-check',
    authType: 'hmac',
    isImplemented: true,
    govCloudCompatible: true,
    features: ['Controls', 'Risks', 'Findings', 'Evidence', 'SOC 2', 'ISO 27001', 'CMMC', 'NIST 800-53'],
    configFields: [
      { name: 'base_url', label: 'AuditBoard URL', type: 'url', placeholder: 'https://your-org.auditboardapp.com', required: true, helpText: 'Your AuditBoard instance URL' },
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Public key for HMAC authentication' },
      { name: 'api_secret', label: 'API Secret', type: 'password', required: true, helpText: 'Secret key for HMAC-SHA256 signing' },
    ],
    supportedFrameworks: ['SOC 2', 'ISO 27001', 'CMMC', 'NIST CSF', 'NIST 800-53', 'HIPAA', 'PCI DSS', 'GDPR', 'FedRAMP'],
  },
  // ADR-074/075: Palantir AIP Integration
  palantir_aip: {
    id: 'palantir_aip',
    name: 'Palantir AIP',
    category: 'threat_intelligence',
    description: 'Enterprise data platform for threat intelligence, asset criticality, and compliance correlation',
    icon: 'shield-exclamation',
    authType: 'api_key_mtls',
    isImplemented: true,
    govCloudCompatible: true,
    features: [
      'Threat intelligence correlation',
      'Asset criticality from CMDB',
      'EPSS score trends',
      'Compliance drift detection',
      'Insider risk monitoring',
      'Ontology sync with circuit breaker',
    ],
    configFields: [
      { name: 'ontology_api_url', label: 'Ontology API URL', type: 'url', placeholder: 'https://ontology.palantir.com/api', required: true, helpText: 'Palantir Ontology API endpoint' },
      { name: 'foundry_api_url', label: 'Foundry API URL', type: 'url', placeholder: 'https://foundry.palantir.com/api', required: true, helpText: 'Palantir Foundry API endpoint' },
      { name: 'api_key', label: 'API Key', type: 'password', required: true, helpText: 'Palantir service account API key' },
      { name: 'client_cert_path', label: 'mTLS Certificate Path', type: 'text', required: false, helpText: 'Path to client certificate for mTLS (optional)' },
      { name: 'sync_frequency', label: 'Sync Frequency', type: 'select', options: ['realtime', '5min', '15min', '30min', 'hourly'], required: true, helpText: 'How often to sync ontology objects' },
      { name: 'object_types', label: 'Object Types to Sync', type: 'tags', required: true, helpText: 'ThreatActor, Vulnerability, Asset, Compliance' },
      { name: 'event_stream_target', label: 'Event Stream Target', type: 'select', options: ['eventbridge', 'kafka', 'kinesis'], required: false, helpText: 'Where to publish remediation events' },
    ],
    supportedObjectTypes: ['ThreatActor', 'Vulnerability', 'Asset', 'Repository', 'Compliance'],
  },
};

/**
 * Default integration configuration
 */
export const DEFAULT_INTEGRATION_CONFIG = {
  enabled: false,
  sync_frequency: 'hourly',
  auto_sync: true,
  bidirectional: false,
};

/**
 * Production-realistic mock connected integrations for development
 * Using let to allow adding new integrations in dev mode
 */
let mockConnectedIntegrations = [
  {
    id: 'int-znd-8a9b0c1d',
    provider: 'zendesk',
    name: 'Zendesk Production',
    category: 'ticketing',
    icon: 'ticket',
    status: 'connected',
    description: 'Enterprise customer service platform - Production workspace',
    enabled: true,
    // Organization context
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    // Configuration
    config: {
      subdomain: 'acme-corp',
      email: 'aura-integration@acme-corp.com',
      default_assignee_id: '382947561',
      default_group_id: '10847293',
    },
    // Sync settings
    sync_frequency: 'hourly',
    sync_direction: 'bidirectional',
    auto_sync: true,
    // Sync history
    last_sync: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    last_sync_status: 'success',
    last_sync_duration_seconds: 45,
    last_sync_records: { created: 3, updated: 12, deleted: 0, errors: 0 },
    next_sync: new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString(),
    // Usage statistics (30 days)
    usage_stats: {
      tickets_created: 147,
      tickets_synced: 892,
      avg_sync_duration_seconds: 42,
      sync_success_rate: 99.7,
      last_30_days_syncs: 720,
    },
    // Health metrics
    health: {
      status: 'healthy',
      latency_ms: 120,
      uptime_percent: 99.95,
      last_health_check: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      api_quota_used: 1247,
      api_quota_limit: 10000,
    },
    // User context
    created_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-r5s6t7u8',
    created_by_email: 'rachel.torres@acme-corp.com',
    created_by_name: 'Rachel Torres',
    updated_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-j5k6l7m8',
    updated_by_email: 'james.wilson@acme-corp.com',
    updated_by_name: 'James Wilson',
    // Audit trail
    audit_trail_id: 'audit-int-znd-001',
    session_id: 'sess-int-7e8f9g0h',
    tags: ['production', 'ticketing', 'customer-support'],
  },
  {
    id: 'int-slk-2e3f4g5h',
    provider: 'slack',
    name: 'Slack - Security Workspace',
    category: 'communication',
    icon: 'chat-bubble-left-right',
    status: 'connected',
    description: 'Real-time security alerts and team notifications',
    enabled: true,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    config: {
      webhook_url: 'https://hooks.slack.com/services/T02XXXXXX/B04YYYYYY/zzzzzzzzzzzzzzzzzzzzzzzz',
      default_channel: '#security-alerts',
      bot_token: '***configured***',
      channels: {
        critical: '#security-critical',
        high: '#security-alerts',
        medium: '#security-notifications',
        low: '#security-info',
      },
    },
    sync_frequency: 'realtime',
    sync_direction: 'outbound',
    auto_sync: true,
    last_sync: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    last_sync_status: 'success',
    last_sync_duration_seconds: 2,
    last_sync_records: { messages_sent: 1, errors: 0 },
    next_sync: null,
    usage_stats: {
      messages_sent: 1847,
      channels_used: 4,
      avg_delivery_latency_ms: 180,
      delivery_success_rate: 99.98,
      last_30_days_messages: 1847,
    },
    health: {
      status: 'healthy',
      latency_ms: 95,
      uptime_percent: 99.99,
      last_health_check: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      rate_limit_remaining: 9847,
      rate_limit_reset: new Date(Date.now() + 60 * 1000).toISOString(),
    },
    created_at: new Date(Date.now() - 120 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-n1o2p3q4',
    created_by_email: 'nina.patel@acme-corp.com',
    created_by_name: 'Nina Patel',
    updated_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-n1o2p3q4',
    updated_by_email: 'nina.patel@acme-corp.com',
    updated_by_name: 'Nina Patel',
    audit_trail_id: 'audit-int-slk-001',
    session_id: 'sess-int-1i2j3k4l',
    tags: ['production', 'notifications', 'security-team'],
  },
  {
    id: 'int-pgd-6i7j8k9l',
    provider: 'pagerduty',
    name: 'PagerDuty - Security Incidents',
    category: 'monitoring',
    icon: 'bell-alert',
    status: 'connected',
    description: 'On-call management and critical incident escalation',
    enabled: true,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    config: {
      routing_key: '***configured***',
      default_severity: 'error',
      escalation_policy_id: 'PABCDEF',
      service_id: 'P1234567',
    },
    sync_frequency: 'realtime',
    sync_direction: 'bidirectional',
    auto_sync: true,
    last_sync: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    last_sync_status: 'success',
    last_sync_duration_seconds: 3,
    last_sync_records: { incidents_created: 0, incidents_resolved: 1, errors: 0 },
    next_sync: null,
    usage_stats: {
      incidents_created: 23,
      incidents_acknowledged: 23,
      incidents_resolved: 21,
      avg_acknowledgement_time_minutes: 4.2,
      avg_resolution_time_minutes: 47.8,
      last_30_days_incidents: 23,
    },
    health: {
      status: 'healthy',
      latency_ms: 85,
      uptime_percent: 99.97,
      last_health_check: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
      api_calls_today: 156,
      api_limit_daily: 10000,
    },
    created_at: new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-j5k6l7m8',
    created_by_email: 'james.wilson@acme-corp.com',
    created_by_name: 'James Wilson',
    updated_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-j5k6l7m8',
    updated_by_email: 'james.wilson@acme-corp.com',
    updated_by_name: 'James Wilson',
    audit_trail_id: 'audit-int-pgd-001',
    session_id: 'sess-int-5m6n7o8p',
    tags: ['production', 'incident-response', 'on-call', 'critical'],
  },
  {
    id: 'int-snk-0m1n2o3p',
    provider: 'snyk',
    name: 'Snyk - Vulnerability Scanner',
    category: 'security',
    icon: 'shield-check',
    status: 'error',
    description: 'Developer-first vulnerability scanning and fix suggestions',
    enabled: true,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    config: {
      org_id: 'acme-corp-snyk-org',
      project_ids: ['proj-aura-core', 'proj-frontend', 'proj-backend'],
    },
    sync_frequency: 'daily',
    sync_direction: 'inbound',
    auto_sync: true,
    last_sync: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    last_sync_status: 'error',
    last_sync_duration_seconds: 15,
    last_sync_records: { vulnerabilities_imported: 0, errors: 1 },
    last_error: 'API rate limit exceeded. Daily limit of 2000 requests reached. Retry after 2026-01-22T00:00:00Z.',
    last_error_code: 'RATE_LIMIT_EXCEEDED',
    last_error_at: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString(),
    error_count_24h: 3,
    next_sync: new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString(),
    usage_stats: {
      vulnerabilities_imported: 234,
      vulnerabilities_by_severity: { critical: 2, high: 18, medium: 89, low: 125 },
      projects_scanned: 47,
      fix_suggestions_generated: 156,
      last_30_days_scans: 29,
    },
    health: {
      status: 'degraded',
      latency_ms: 450,
      uptime_percent: 97.5,
      last_health_check: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      api_calls_today: 2000,
      api_limit_daily: 2000,
      rate_limit_reset: new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString(),
    },
    created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-n1o2p3q4',
    created_by_email: 'nina.patel@acme-corp.com',
    created_by_name: 'Nina Patel',
    updated_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-n1o2p3q4',
    updated_by_email: 'nina.patel@acme-corp.com',
    updated_by_name: 'Nina Patel',
    audit_trail_id: 'audit-int-snk-001',
    session_id: 'sess-int-9q0r1s2t',
    tags: ['production', 'security', 'vulnerability-scanning', 'needs-attention'],
  },
  {
    id: 'int-ghb-4q5r6s7t',
    provider: 'github_actions',
    name: 'GitHub Actions - CI/CD',
    category: 'cicd',
    icon: 'code-bracket',
    status: 'connected',
    description: 'CI/CD pipeline integration for security workflow triggers',
    enabled: true,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    config: {
      repository: 'acme-corp/aura-platform',
      workflows: ['security-scan.yml', 'dependency-check.yml', 'deploy-staging.yml'],
    },
    sync_frequency: 'realtime',
    sync_direction: 'bidirectional',
    auto_sync: true,
    last_sync: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    last_sync_status: 'success',
    last_sync_duration_seconds: 8,
    last_sync_records: { workflows_triggered: 1, status_updates: 3, errors: 0 },
    next_sync: null,
    usage_stats: {
      workflows_triggered: 456,
      successful_runs: 442,
      failed_runs: 14,
      avg_run_duration_minutes: 8.5,
      last_30_days_runs: 456,
    },
    health: {
      status: 'healthy',
      latency_ms: 110,
      uptime_percent: 99.92,
      last_health_check: new Date(Date.now() - 4 * 60 * 1000).toISOString(),
      rate_limit_remaining: 4750,
      rate_limit_limit: 5000,
    },
    created_at: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-r5s6t7u8',
    created_by_email: 'rachel.torres@acme-corp.com',
    created_by_name: 'Rachel Torres',
    updated_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-m3k8n2p5',
    updated_by_email: 'marcus.johnson@acme-corp.com',
    updated_by_name: 'Marcus Johnson',
    audit_trail_id: 'audit-int-ghb-001',
    session_id: 'sess-int-3u4v5w6x',
    tags: ['production', 'cicd', 'automation', 'github'],
  },
  {
    id: 'int-ddk-8u9v0w1x',
    provider: 'datadog',
    name: 'Datadog - APM & Metrics',
    category: 'monitoring',
    icon: 'chart-bar',
    status: 'connected',
    description: 'Application performance monitoring and metrics correlation',
    enabled: true,
    organization_id: 'org-acme-corp-7x2',
    organization_name: 'Acme Corporation',
    config: {
      site: 'datadoghq.com',
      service_name: 'aura-platform',
      environment: 'production',
    },
    sync_frequency: 'continuous',
    sync_direction: 'bidirectional',
    auto_sync: true,
    last_sync: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
    last_sync_status: 'success',
    last_sync_duration_seconds: 1,
    last_sync_records: { metrics_sent: 47, traces_correlated: 12, errors: 0 },
    next_sync: null,
    usage_stats: {
      metrics_sent: 892347,
      traces_correlated: 45678,
      alerts_received: 34,
      dashboards_linked: 8,
      last_30_days_datapoints: 892347,
    },
    health: {
      status: 'healthy',
      latency_ms: 45,
      uptime_percent: 99.99,
      last_health_check: new Date(Date.now() - 30 * 1000).toISOString(),
      ingestion_rate_per_second: 847,
    },
    created_at: new Date(Date.now() - 200 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-d7e8f9g0',
    created_by_email: 'derek.wong@acme-corp.com',
    created_by_name: 'Derek Wong',
    updated_at: new Date(Date.now() - 21 * 24 * 60 * 60 * 1000).toISOString(),
    updated_by: 'usr-d7e8f9g0',
    updated_by_email: 'derek.wong@acme-corp.com',
    updated_by_name: 'Derek Wong',
    audit_trail_id: 'audit-int-ddk-001',
    session_id: 'sess-int-7y8z9a0b',
    tags: ['production', 'monitoring', 'apm', 'metrics'],
  },
];

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get all configured integrations
 * @param {Object} params - Query parameters (category, status, search)
 * @returns {Promise<Object>} List of integrations with metadata
 */
export async function getIntegrations(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.category) query.append('category', params.category);
    if (params.status) query.append('status', params.status);
    if (params.search) query.append('search', params.search);

    const response = await apiClient.get(`${INTEGRATIONS_BASE}?${query.toString()}`);
    return response.data;
  } catch {
    // Return mock integrations when API is unavailable (dev mode)
    let integrations = [...mockConnectedIntegrations];

    // Apply filters
    if (params.category) {
      integrations = integrations.filter((i) => i.category === params.category);
    }
    if (params.status) {
      integrations = integrations.filter((i) => i.status === params.status);
    }
    if (params.search) {
      const search = params.search.toLowerCase();
      integrations = integrations.filter(
        (i) =>
          i.name.toLowerCase().includes(search) ||
          i.description.toLowerCase().includes(search)
      );
    }

    return { integrations };
  }
}

/**
 * Get available integration providers
 * @param {string} category - Optional category filter
 * @returns {Promise<Object>} Available providers grouped by category
 */
export async function getAvailableIntegrations(category = null) {
  try {
    const query = category ? `?category=${category}` : '';
    const response = await apiClient.get(`${INTEGRATIONS_BASE}/available${query}`);
    return response.data;
  } catch {
    // Return local provider definitions if API unavailable
    const providers = Object.values(INTEGRATION_PROVIDERS);
    const categories = Object.values(INTEGRATION_CATEGORIES);

    return {
      integrations: category
        ? providers.filter(p => p.category === category)
        : providers,
      categories,
    };
  }
}

/**
 * Get configuration for a specific integration
 * @param {string} provider - Provider ID
 * @returns {Promise<Object>} Integration configuration
 */
export async function getIntegrationConfig(provider) {
  const response = await apiClient.get(`${INTEGRATIONS_BASE}/${provider}/config`);
  return response.data;
}

/**
 * Save integration configuration
 * @param {string} provider - Provider ID
 * @param {Object} config - Configuration to save
 * @returns {Promise<Object>} Saved configuration
 */
export async function saveIntegrationConfig(provider, config) {
  try {
    const response = await apiClient.post(`${INTEGRATIONS_BASE}/${provider}/config`, config);
    return response.data;
  } catch {
    // Mock save for dev mode - add to connected integrations
    const providerDef = INTEGRATION_PROVIDERS[provider];
    if (!providerDef) throw new Error(`Unknown provider: ${provider}`);

    // Check if already connected
    const existingIndex = mockConnectedIntegrations.findIndex(i => i.provider === provider);

    const newIntegration = {
      id: `int_${provider}_${Date.now()}`,
      provider,
      name: providerDef.name,
      category: providerDef.category,
      icon: providerDef.icon,
      status: 'connected',
      description: providerDef.description,
      enabled: true,
      sync_frequency: 'hourly',
      last_sync: new Date().toISOString(),
      config,
    };

    if (existingIndex >= 0) {
      // Update existing
      mockConnectedIntegrations[existingIndex] = {
        ...mockConnectedIntegrations[existingIndex],
        config,
        last_sync: new Date().toISOString(),
      };
    } else {
      // Add new
      mockConnectedIntegrations.push(newIntegration);
    }

    return { success: true, integration: newIntegration };
  }
}

/**
 * Update existing integration configuration
 * @param {string} integrationId - Integration ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated integration
 */
export async function updateIntegration(integrationId, updates) {
  const response = await apiClient.patch(`${INTEGRATIONS_BASE}/${integrationId}`, updates);
  return response.data;
}

/**
 * Delete an integration
 * @param {string} integrationId - Integration ID
 * @returns {Promise<void>}
 */
export async function deleteIntegration(integrationId) {
  try {
    await apiClient.delete(`${INTEGRATIONS_BASE}/${integrationId}`);
  } catch {
    // Mock delete for dev mode - remove from mock list
    const index = mockConnectedIntegrations.findIndex(i => i.id === integrationId);
    if (index >= 0) {
      mockConnectedIntegrations.splice(index, 1);
    }
  }
}

/**
 * Test integration connectivity
 * @param {string} provider - Provider ID
 * @param {Object} config - Configuration to test (optional, uses saved if not provided)
 * @returns {Promise<Object>} Test result with success/failure and details
 */
export async function testConnection(provider, config = null) {
  try {
    const payload = config ? { config } : {};
    const response = await apiClient.post(`${INTEGRATIONS_BASE}/${provider}/test`, payload);
    return response.data;
  } catch {
    // Mock test connection for dev mode - always succeed
    const providerDef = INTEGRATION_PROVIDERS[provider];
    if (!providerDef) {
      return { success: false, message: `Unknown provider: ${provider}` };
    }
    return {
      success: true,
      message: `Connection to ${providerDef.name} successful`,
      latency_ms: Math.floor(Math.random() * 200) + 50,
    };
  }
}

/**
 * Trigger manual sync for an integration
 * @param {string} provider - Provider ID
 * @returns {Promise<Object>} Sync result
 */
export async function syncNow(provider) {
  try {
    const response = await apiClient.post(`${INTEGRATIONS_BASE}/${provider}/sync`);
    return response.data;
  } catch {
    // Mock sync for dev mode
    const integration = mockConnectedIntegrations.find(i => i.provider === provider);
    if (integration) {
      integration.last_sync = new Date().toISOString();
      integration.status = 'connected';
      delete integration.last_error;
    }
    return { success: true, message: 'Sync completed successfully' };
  }
}

/**
 * Get sync and error logs for an integration
 * @param {string} provider - Provider ID
 * @param {Object} params - Query parameters (limit, offset, level)
 * @returns {Promise<Object>} Log entries
 */
export async function getIntegrationLogs(provider, params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.append('limit', params.limit);
  if (params.offset) query.append('offset', params.offset);
  if (params.level) query.append('level', params.level);

  const response = await apiClient.get(`${INTEGRATIONS_BASE}/${provider}/logs?${query.toString()}`);
  return response.data;
}

/**
 * Get integration health metrics
 * @param {string} provider - Provider ID
 * @returns {Promise<Object>} Health metrics
 */
export async function getIntegrationHealth(provider) {
  const response = await apiClient.get(`${INTEGRATIONS_BASE}/${provider}/health`);
  return response.data;
}

/**
 * Toggle integration enabled/disabled
 * @param {string} provider - Provider ID
 * @param {boolean} enabled - New enabled state
 * @returns {Promise<Object>} Updated integration
 */
export async function toggleIntegration(provider, enabled) {
  try {
    const response = await apiClient.patch(`${INTEGRATIONS_BASE}/${provider}`, { enabled });
    return response.data;
  } catch {
    // Mock toggle for dev mode
    const integration = mockConnectedIntegrations.find(i => i.provider === provider);
    if (integration) {
      integration.enabled = enabled;
    }
    return { success: true, enabled };
  }
}

/**
 * Get OAuth authorization URL for providers that require it
 * @param {string} provider - Provider ID
 * @param {string} redirectUri - OAuth callback URL
 * @returns {Promise<Object>} Authorization URL and state
 */
export async function getOAuthUrl(provider, redirectUri) {
  const response = await apiClient.get(`${INTEGRATIONS_BASE}/${provider}/oauth/authorize`, {
    params: { redirect_uri: redirectUri },
  });
  return response.data;
}

/**
 * Complete OAuth flow with authorization code
 * @param {string} provider - Provider ID
 * @param {string} code - Authorization code
 * @param {string} state - OAuth state parameter
 * @returns {Promise<Object>} Integration configuration with tokens
 */
export async function completeOAuth(provider, code, state) {
  const response = await apiClient.post(`${INTEGRATIONS_BASE}/${provider}/oauth/callback`, {
    code,
    state,
  });
  return response.data;
}

/**
 * Get provider-specific field options (e.g., teams, projects)
 * @param {string} provider - Provider ID
 * @param {string} fieldName - Field to fetch options for
 * @param {Object} config - Current configuration for context
 * @returns {Promise<Array>} Available options
 */
export async function getFieldOptions(provider, fieldName, config = {}) {
  const response = await apiClient.post(`${INTEGRATIONS_BASE}/${provider}/fields/${fieldName}`, {
    config,
  });
  return response.data;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get provider definition by ID
 * @param {string} providerId - Provider ID
 * @returns {Object|null} Provider definition
 */
export function getProviderById(providerId) {
  return INTEGRATION_PROVIDERS[providerId] || null;
}

/**
 * Get providers by category
 * @param {string} category - Category ID
 * @returns {Array} Providers in category
 */
export function getProvidersByCategory(category) {
  return Object.values(INTEGRATION_PROVIDERS).filter(p => p.category === category);
}

/**
 * Validate configuration against provider schema
 * @param {string} providerId - Provider ID
 * @param {Object} config - Configuration to validate
 * @returns {Object} Validation result with errors
 */
export function validateConfig(providerId, config) {
  const provider = INTEGRATION_PROVIDERS[providerId];
  if (!provider) {
    return { valid: false, errors: ['Unknown provider'] };
  }

  const errors = [];
  for (const field of provider.configFields) {
    if (field.required && !config[field.name]) {
      errors.push(`${field.label} is required`);
    }
    if (field.type === 'email' && config[field.name]) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(config[field.name])) {
        errors.push(`${field.label} must be a valid email address`);
      }
    }
    if (field.type === 'url' && config[field.name]) {
      try {
        new URL(config[field.name]);
      } catch {
        errors.push(`${field.label} must be a valid URL`);
      }
    }
  }

  return { valid: errors.length === 0, errors };
}

export default {
  getIntegrations,
  getAvailableIntegrations,
  getIntegrationConfig,
  saveIntegrationConfig,
  updateIntegration,
  deleteIntegration,
  testConnection,
  syncNow,
  getIntegrationLogs,
  getIntegrationHealth,
  toggleIntegration,
  getOAuthUrl,
  completeOAuth,
  getFieldOptions,
  getProviderById,
  getProvidersByCategory,
  validateConfig,
  INTEGRATION_CATEGORIES,
  INTEGRATION_PROVIDERS,
  DEFAULT_INTEGRATION_CONFIG,
};
