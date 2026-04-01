import { useState, useEffect } from 'react';
import {
  ArrowLeftIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  GlobeAltIcon,
  CpuChipIcon,
  CurrencyDollarIcon,
  ServerStackIcon,
  ClipboardDocumentIcon,
  ArrowTopRightOnSquareIcon,
  CommandLineIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { LineChart } from './ui/Charts';
import { useToast } from './ui/Toast';
import MetricCard from './ui/MetricCard';
import { getActivities } from '../services/activityApi';
import { getEnvironmentMetrics } from '../services/environmentsApi';

// Status styles
const STATUS_STYLES = {
  active: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    icon: CheckCircleIcon,
    label: 'Active',
    dot: 'bg-olive-500',
  },
  pending_approval: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: ClockIcon,
    label: 'Pending Approval',
    dot: 'bg-warning-500',
  },
  provisioning: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    icon: ArrowPathIcon,
    label: 'Provisioning',
    dot: 'bg-aura-500 animate-pulse',
  },
  expiring: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    icon: ExclamationTriangleIcon,
    label: 'Expiring Soon',
    dot: 'bg-warning-500 animate-pulse',
  },
  terminating: {
    badge: 'bg-surface-100 text-surface-700 dark:bg-surface-700/30 dark:text-surface-400',
    icon: TrashIcon,
    label: 'Terminating',
    dot: 'bg-surface-500',
  },
  terminated: {
    badge: 'bg-surface-100 text-surface-500 dark:bg-surface-800/30 dark:text-surface-500',
    icon: XCircleIcon,
    label: 'Terminated',
    dot: 'bg-surface-400',
  },
  failed: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    icon: XCircleIcon,
    label: 'Failed',
    dot: 'bg-critical-500',
  },
};

// Type styles
const TYPE_STYLES = {
  quick: {
    badge: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    label: 'Quick Test',
    mechanism: 'EKS Namespace',
  },
  standard: {
    badge: 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400',
    label: 'Standard',
    mechanism: 'Service Catalog',
  },
  extended: {
    badge: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    label: 'Extended',
    mechanism: 'Service Catalog',
  },
  compliance: {
    badge: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    label: 'Compliance',
    mechanism: 'Dedicated VPC',
  },
};

// Default metrics structure (used when API returns no data)
const DEFAULT_METRICS = {
  cpu: {
    data: [],
    labels: [],
  },
  memory: {
    data: [],
    labels: [],
  },
  requests: {
    data: [],
    labels: [],
  },
};

// Format time
function formatDate(dateString) {
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatTimeRemaining(expiresAt) {
  const now = new Date();
  const expires = new Date(expiresAt);
  const diff = expires - now;

  if (diff <= 0) return 'Expired';

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (days > 0) return `${days}d ${hours}h remaining`;
  if (hours > 0) return `${hours}h ${minutes}m remaining`;
  return `${minutes}m remaining`;
}

// Copy to clipboard helper
function copyToClipboard(text) {
  navigator.clipboard.writeText(text);
}

// Info Row Component
function InfoRow({ icon: Icon, label, value, copyable = false, link = false }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-start gap-3 py-3 border-b border-surface-100 dark:border-surface-700/50 last:border-0">
      <Icon className="w-5 h-5 text-surface-400 dark:text-surface-500 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-surface-500 dark:text-surface-400 mb-0.5">{label}</p>
        <div className="flex items-center gap-2">
          <p className={`text-sm text-surface-900 dark:text-surface-100 ${copyable ? 'font-mono' : ''} truncate`}>
            {value}
          </p>
          {copyable && (
            <button
              onClick={handleCopy}
              className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
              title="Copy to clipboard"
            >
              {copied ? (
                <CheckCircleIcon className="w-4 h-4 text-olive-500" />
              ) : (
                <ClipboardDocumentIcon className="w-4 h-4 text-surface-400" />
              )}
            </button>
          )}
          {link && (
            <a
              href={`https://${value}`}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1 rounded hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
              title="Open in new tab"
            >
              <ArrowTopRightOnSquareIcon className="w-4 h-4 text-surface-400" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// Activity Timeline Component
function ActivityTimeline({ activities }) {
  return (
    <div className="space-y-4">
      {activities.map((activity, idx) => (
        <div key={activity.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className={`w-2 h-2 rounded-full ${idx === 0 ? 'bg-olive-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
            {idx < activities.length - 1 && (
              <div className="w-0.5 h-full bg-surface-200 dark:bg-surface-700 mt-1" />
            )}
          </div>
          <div className="flex-1 pb-4">
            <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
              {activity.action}
            </p>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              {activity.timestamp} by {activity.actor}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// Resource Card Component
function ResourceCard({ name, type, status, arn }) {
  return (
    <div className="p-3 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-surface-900 dark:text-surface-100 text-sm">{name}</span>
        <span className="px-2 py-0.5 text-xs rounded-full bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400">
          {status}
        </span>
      </div>
      <p className="text-xs text-surface-500 dark:text-surface-400">{type}</p>
      {arn && (
        <p className="text-xs font-mono text-surface-400 dark:text-surface-500 mt-1 truncate">{arn}</p>
      )}
    </div>
  );
}

// Main Environment Dashboard Component
export default function EnvironmentDashboard({ environment, onBack, onTerminate, onExtend }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activities, setActivities] = useState([]);
  const [metrics, setMetrics] = useState(DEFAULT_METRICS);
  const [activitiesLoading, setActivitiesLoading] = useState(true);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const { toast } = useToast();

  const statusStyle = STATUS_STYLES[environment.status] || STATUS_STYLES.active;
  const typeStyle = TYPE_STYLES[environment.environment_type] || TYPE_STYLES.standard;
  const _StatusIcon = statusStyle.icon;

  const isExpiringSoon = environment.status === 'expiring' ||
    (environment.status === 'active' && new Date(environment.expires_at) - new Date() < 2 * 60 * 60 * 1000);

  // Fetch activities and metrics on mount
  useEffect(() => {
    const fetchData = async () => {
      // Fetch activities
      try {
        const activityData = await getActivities({
          resourceType: 'environment',
          resourceId: environment.environment_id,
          limit: 20
        });
        // Transform API response to match component format
        const formattedActivities = (activityData || []).map((a, idx) => ({
          id: a.id || idx,
          action: a.action || a.description,
          timestamp: a.timestamp ? new Date(a.timestamp).toLocaleString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
          }) : 'Unknown',
          actor: a.actor || a.user || 'system',
        }));
        setActivities(formattedActivities);
      } catch (err) {
        // Activities API may not be available - use empty array
        setActivities([]);
      } finally {
        setActivitiesLoading(false);
      }

      // Fetch metrics
      try {
        const metricsData = await getEnvironmentMetrics(environment.environment_id);
        if (metricsData) {
          setMetrics({
            cpu: metricsData.cpu || DEFAULT_METRICS.cpu,
            memory: metricsData.memory || DEFAULT_METRICS.memory,
            requests: metricsData.requests || DEFAULT_METRICS.requests,
          });
        }
      } catch (err) {
        // Metrics API may not be available - use default empty metrics
        setMetrics(DEFAULT_METRICS);
      } finally {
        setMetricsLoading(false);
      }
    };

    fetchData();
  }, [environment.environment_id]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      // Refresh activities
      const activityData = await getActivities({
        resourceType: 'environment',
        resourceId: environment.environment_id,
        limit: 20
      });
      const formattedActivities = (activityData || []).map((a, idx) => ({
        id: a.id || idx,
        action: a.action || a.description,
        timestamp: a.timestamp ? new Date(a.timestamp).toLocaleString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
        }) : 'Unknown',
        actor: a.actor || a.user || 'system',
      }));
      setActivities(formattedActivities);

      // Refresh metrics
      const metricsData = await getEnvironmentMetrics(environment.environment_id);
      if (metricsData) {
        setMetrics({
          cpu: metricsData.cpu || DEFAULT_METRICS.cpu,
          memory: metricsData.memory || DEFAULT_METRICS.memory,
          requests: metricsData.requests || DEFAULT_METRICS.requests,
        });
      }

      toast.success('Environment refreshed');
    } catch (err) {
      toast.error('Failed to refresh environment');
    } finally {
      setIsRefreshing(false);
    }
  };

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'resources', label: 'Resources' },
    { id: 'metrics', label: 'Metrics' },
    { id: 'activity', label: 'Activity' },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200 mb-4 transition-colors"
          >
            <ArrowLeftIcon className="w-4 h-4" />
            Back to Environments
          </button>

          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                  {environment.display_name}
                </h1>
                <span className={`px-2.5 py-1 text-sm font-medium rounded-full ${statusStyle.badge} flex items-center gap-1.5`}>
                  <span className={`w-2 h-2 rounded-full ${statusStyle.dot}`} />
                  {statusStyle.label}
                </span>
              </div>
              <div className="flex items-center gap-4 text-sm text-surface-500 dark:text-surface-400">
                <span className="font-mono">{environment.environment_id}</span>
                <span className={`px-2 py-0.5 rounded-full ${typeStyle.badge}`}>
                  {typeStyle.label}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
              >
                <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              {(environment.status === 'active' || environment.status === 'expiring') && (
                <>
                  <button
                    onClick={() => onExtend(environment)}
                    className="px-4 py-2 text-sm font-medium rounded-lg bg-aura-50 text-aura-600 hover:bg-aura-100 dark:bg-aura-900/20 dark:text-aura-400 dark:hover:bg-aura-900/30 transition-colors"
                  >
                    Extend TTL
                  </button>
                  <button
                    onClick={() => onTerminate(environment)}
                    className="px-4 py-2 text-sm font-medium rounded-lg bg-critical-50 text-critical-600 hover:bg-critical-100 dark:bg-critical-900/20 dark:text-critical-400 dark:hover:bg-critical-900/30 transition-colors"
                  >
                    Terminate
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Expiring Warning */}
        {isExpiringSoon && (
          <div className="mb-6 p-4 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-lg flex items-center gap-3">
            <ExclamationTriangleIcon className="w-5 h-5 text-warning-500 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-warning-800 dark:text-warning-200">Environment Expiring Soon</p>
              <p className="text-sm text-warning-600 dark:text-warning-400">
                This environment will be automatically terminated in {formatTimeRemaining(environment.expires_at)}.
                Extend the TTL to continue using it.
              </p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-surface-200 dark:border-surface-700 mb-6">
          <nav className="flex gap-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  pb-3 text-sm font-medium border-b-2 transition-colors
                  ${activeTab === tab.id
                    ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                    : 'border-transparent text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
                  }
                `}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main Info */}
            <div className="lg:col-span-2 space-y-6">
              {/* Quick Stats */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <MetricCard
                  title="Daily Cost"
                  value={`$${environment.cost_estimate_daily.toFixed(2)}`}
                  icon={CurrencyDollarIcon}
                  iconColor="aura"
                />
                <MetricCard
                  title="Time Remaining"
                  value={formatTimeRemaining(environment.expires_at)}
                  icon={ClockIcon}
                  iconColor={isExpiringSoon ? 'warning' : 'olive'}
                />
                <MetricCard
                  title="Type"
                  value={typeStyle.mechanism}
                  icon={ServerStackIcon}
                  iconColor="olive"
                />
              </div>

              {/* Connection Info */}
              <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
                <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">Connection Details</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <GlobeAltIcon className="w-5 h-5 text-aura-500" />
                      <span className="font-medium text-surface-900 dark:text-surface-100">DNS Endpoint</span>
                    </div>
                    <code className="text-sm font-mono text-surface-600 dark:text-surface-400 break-all">
                      {environment.dns_name}
                    </code>
                    <button
                      onClick={() => copyToClipboard(environment.dns_name)}
                      className="mt-2 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                    >
                      Copy to clipboard
                    </button>
                  </div>
                  <div className="p-4 bg-surface-50 dark:bg-surface-700/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <CommandLineIcon className="w-5 h-5 text-olive-500" />
                      <span className="font-medium text-surface-900 dark:text-surface-100">Quick Connect</span>
                    </div>
                    <code className="text-sm font-mono text-surface-600 dark:text-surface-400 break-all">
                      curl https://{environment.dns_name}/health
                    </code>
                    <button
                      onClick={() => copyToClipboard(`curl https://${environment.dns_name}/health`)}
                      className="mt-2 text-xs text-aura-600 dark:text-aura-400 hover:underline"
                    >
                      Copy command
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Sidebar Info */}
            <div className="space-y-6">
              <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
                <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">Details</h3>
                <div>
                  <InfoRow icon={DocumentDuplicateIcon} label="Template" value={environment.template_id} />
                  <InfoRow icon={CpuChipIcon} label="Environment ID" value={environment.environment_id} copyable />
                  <InfoRow icon={ClockIcon} label="Created" value={formatDate(environment.created_at)} />
                  <InfoRow icon={ClockIcon} label="Expires" value={formatDate(environment.expires_at)} />
                  <InfoRow icon={GlobeAltIcon} label="DNS Name" value={environment.dns_name} copyable link />
                </div>
              </div>

              {/* Recent Activity */}
              <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-4">
                <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">Recent Activity</h3>
                {activitiesLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <ArrowPathIcon className="w-6 h-6 animate-spin text-surface-400" />
                  </div>
                ) : activities.length > 0 ? (
                  <ActivityTimeline activities={activities.slice(0, 4)} />
                ) : (
                  <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-4">No activity recorded</p>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'resources' && (
          <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">Provisioned Resources</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <ResourceCard
                name="API Service"
                type="ECS Service"
                status="Running"
                arn={environment.resources?.ecs_service || 'arn:aws:ecs:us-east-1:***:service/***'}
              />
              <ResourceCard
                name="CloudFormation Stack"
                type="AWS::CloudFormation::Stack"
                status="CREATE_COMPLETE"
                arn={environment.resources?.stack_name || 'SC-***-pp-***'}
              />
              <ResourceCard
                name="S3 Bucket"
                type="AWS::S3::Bucket"
                status="Active"
                arn={`aura-testenv-${environment.environment_id}-data`}
              />
              <ResourceCard
                name="DynamoDB Table"
                type="AWS::DynamoDB::Table"
                status="Active"
                arn={`aura-testenv-${environment.environment_id}-state`}
              />
              <ResourceCard
                name="DNS Record"
                type="Route53/dnsmasq"
                status="Active"
                arn={environment.dns_name}
              />
              <ResourceCard
                name="Security Group"
                type="AWS::EC2::SecurityGroup"
                status="Active"
                arn={`sg-testenv-${environment.environment_id.slice(-8)}`}
              />
            </div>
          </div>
        )}

        {activeTab === 'metrics' && (
          <div className="space-y-6">
            {metricsLoading ? (
              <div className="flex items-center justify-center py-16">
                <ArrowPathIcon className="w-8 h-8 animate-spin text-surface-400" />
              </div>
            ) : metrics.cpu.data.length === 0 && metrics.memory.data.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-surface-400">
                <ChartBarIcon className="w-12 h-12 mb-3" />
                <p className="text-lg font-medium">No metrics available</p>
                <p className="text-sm">Metrics will appear once the environment is actively running</p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <LineChart
                    data={metrics.cpu.data}
                    labels={metrics.cpu.labels}
                    title="CPU Utilization"
                    subtitle="Last 60 minutes"
                    color="aura"
                    height={200}
                    yAxisLabel="%"
                  />
                  <LineChart
                    data={metrics.memory.data}
                    labels={metrics.memory.labels}
                    title="Memory Utilization"
                    subtitle="Last 60 minutes"
                    color="olive"
                    height={200}
                    yAxisLabel="%"
                  />
                </div>
                <LineChart
                  data={metrics.requests.data}
                  labels={metrics.requests.labels}
                  title="Request Rate"
                  subtitle="Requests per second"
                  color="warning"
                  height={200}
                  yAxisLabel="req/s"
                />
              </>
            )}
          </div>
        )}

        {activeTab === 'activity' && (
          <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-6">Activity Log</h3>
            {activitiesLoading ? (
              <div className="flex items-center justify-center py-8">
                <ArrowPathIcon className="w-6 h-6 animate-spin text-surface-400" />
              </div>
            ) : activities.length > 0 ? (
              <ActivityTimeline activities={activities} />
            ) : (
              <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-8">No activity recorded</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
