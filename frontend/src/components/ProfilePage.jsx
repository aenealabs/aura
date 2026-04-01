/**
 * Project Aura - User Profile Page
 *
 * Comprehensive profile management including:
 * - Avatar upload and personal information
 * - Password management
 * - Notification preferences (email, in-app, Slack)
 * - Session management
 * - API keys / Personal access tokens
 */

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  UserCircleIcon,
  KeyIcon,
  BellIcon,
  ComputerDesktopIcon,
  CommandLineIcon,
  ShieldCheckIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  TrashIcon,
  PlusIcon,
  EyeIcon,
  EyeSlashIcon,
  ClipboardDocumentIcon,
  XMarkIcon,
  GlobeAltIcon,
  EnvelopeIcon,
  ChatBubbleLeftRightIcon,
  DevicePhoneMobileIcon,
  ClockIcon,
  MapPinIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import { FormField, Input } from './ui/FormElements';
import { useToast } from './ui/Toast';

import {
  getProfile,
  updateProfile,
  uploadAvatar,
  deleteAvatar,
  changePassword,
  getNotificationPreferences,
  updateNotificationPreferences,
  getSessions,
  revokeSession,
  revokeAllSessions,
  getApiKeys,
  createApiKey,
  deleteApiKey,
  API_SCOPES,
} from '../services/profileApi';

// Tab configuration
const TABS = [
  { id: 'personal', label: 'Personal Info', icon: UserCircleIcon },
  { id: 'password', label: 'Password', icon: KeyIcon },
  { id: 'notifications', label: 'Notifications', icon: BellIcon },
  { id: 'sessions', label: 'Sessions', icon: ComputerDesktopIcon },
  { id: 'api-keys', label: 'API Keys', icon: CommandLineIcon },
];

/**
 * Toggle Switch Component
 */
function Toggle({ checked, onChange, disabled = false }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={`
        relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
        transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:focus:ring-offset-surface-800
        ${checked ? 'bg-aura-600' : 'bg-surface-200 dark:bg-surface-600'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      <span
        className={`
          pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
          transition duration-200 ease-in-out
          ${checked ? 'translate-x-5' : 'translate-x-0'}
        `}
      />
    </button>
  );
}

/**
 * Avatar Upload Component
 */
function AvatarUpload({ avatarUrl, name, onUpload, onDelete, isLoading }) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFileSelect = (file) => {
    if (file && file.type.startsWith('image/')) {
      if (file.size > 5 * 1024 * 1024) {
        alert('Image size must be less than 5MB');
        return;
      }
      onUpload(file);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFileSelect(file);
  };

  const getInitials = () => {
    if (name) {
      return name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    }
    return 'U';
  };

  return (
    <div className="flex items-center gap-6">
      <div
        className={`
          relative w-24 h-24 aspect-square flex-shrink-0
          rounded-full overflow-hidden
          border-2 border-black
          ${dragOver ? 'ring-4 ring-aura-500 ring-offset-2' : ''}
          ${isLoading ? 'opacity-50' : ''}
        `}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {avatarUrl ? (
          <img src={avatarUrl} alt={name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-black flex items-center justify-center text-white text-2xl font-semibold">
            {getInitials()}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={(e) => handleFileSelect(e.target.files?.[0])}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
        >
          {isLoading ? 'Uploading...' : 'Upload Photo'}
        </button>
        {avatarUrl && (
          <button
            onClick={onDelete}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-lg transition-colors"
          >
            Remove
          </button>
        )}
        <p className="text-xs text-surface-500 dark:text-surface-400">
          JPG, PNG or GIF. Max 5MB.
        </p>
      </div>
    </div>
  );
}

/**
 * Personal Information Tab
 */
function PersonalInfoTab({ profile, onUpdate, isLoading }) {
  const [formData, setFormData] = useState({
    name: profile?.name || '',
    email: profile?.email || '',
    department: profile?.department || '',
    timezone: profile?.timezone || 'UTC',
  });
  const [errors, setErrors] = useState({});
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (profile) {
      setFormData({
        name: profile.name || '',
        email: profile.email || '',
        department: profile.department || '',
        timezone: profile.timezone || 'UTC',
      });
      setHasChanges(false);
    }
  }, [profile]);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
    setErrors((prev) => ({ ...prev, [field]: null }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const newErrors = {};
    if (!formData.name.trim()) newErrors.name = 'Name is required';
    if (formData.name.length > 100) newErrors.name = 'Name must be less than 100 characters';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    await onUpdate(formData);
    setHasChanges(false);
  };

  const timezones = [
    { value: 'UTC', label: 'UTC' },
    { value: 'America/New_York', label: 'Eastern Time (ET)' },
    { value: 'America/Chicago', label: 'Central Time (CT)' },
    { value: 'America/Denver', label: 'Mountain Time (MT)' },
    { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
    { value: 'Europe/London', label: 'London (GMT)' },
    { value: 'Europe/Paris', label: 'Paris (CET)' },
    { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <FormField label="Full Name" error={errors.name} required>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            error={errors.name}
            disabled={isLoading}
            placeholder="Enter your full name"
          />
        </FormField>

        <FormField label="Email Address" helperText="Contact your administrator to change email">
          <Input
            id="email"
            type="email"
            value={formData.email}
            disabled
            className="bg-surface-50 dark:bg-surface-800"
          />
        </FormField>

        <FormField label="Department">
          <Input
            id="department"
            value={formData.department}
            onChange={(e) => handleChange('department', e.target.value)}
            disabled={isLoading}
            placeholder="e.g., Engineering, Security"
          />
        </FormField>

        <FormField label="Timezone">
          <select
            id="timezone"
            value={formData.timezone}
            onChange={(e) => handleChange('timezone', e.target.value)}
            disabled={isLoading}
            className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500 disabled:opacity-50"
          >
            {timezones.map((tz) => (
              <option key={tz.value} value={tz.value}>
                {tz.label}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      {/* Role Display */}
      <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-surface-900 dark:text-surface-100">Role</p>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Your role determines your access level in Project Aura
            </p>
          </div>
          <span className="px-3 py-1 bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 text-sm font-medium rounded-full capitalize">
            {profile?.role || 'viewer'}
          </span>
        </div>
      </div>

      {hasChanges && (
        <div className="flex justify-end gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
          <button
            type="button"
            onClick={() => {
              setFormData({
                name: profile?.name || '',
                email: profile?.email || '',
                department: profile?.department || '',
                timezone: profile?.timezone || 'UTC',
              });
              setHasChanges(false);
            }}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}
    </form>
  );
}

/**
 * Password Change Tab
 */
function PasswordTab({ onChangePassword, isLoading }) {
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false,
  });

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null }));
  };

  const validatePassword = (password) => {
    const requirements = [];
    if (password.length < 12) requirements.push('At least 12 characters');
    if (!/[A-Z]/.test(password)) requirements.push('One uppercase letter');
    if (!/[a-z]/.test(password)) requirements.push('One lowercase letter');
    if (!/[0-9]/.test(password)) requirements.push('One number');
    if (!/[^A-Za-z0-9]/.test(password)) requirements.push('One special character');
    return requirements;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const newErrors = {};

    if (!formData.currentPassword) {
      newErrors.currentPassword = 'Current password is required';
    }

    const passwordIssues = validatePassword(formData.newPassword);
    if (passwordIssues.length > 0) {
      newErrors.newPassword = `Password must have: ${passwordIssues.join(', ')}`;
    }

    if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const success = await onChangePassword(formData.currentPassword, formData.newPassword);
    if (success) {
      setFormData({ currentPassword: '', newPassword: '', confirmPassword: '' });
    }
  };

  const PasswordInput = ({ id, value, onChange, error, showPassword, onToggleShow, placeholder }) => (
    <div className="relative">
      <Input
        id={id}
        type={showPassword ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        error={error}
        placeholder={placeholder}
        className="pr-10"
      />
      <button
        type="button"
        onClick={onToggleShow}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
      >
        {showPassword ? (
          <EyeSlashIcon className="h-5 w-5" />
        ) : (
          <EyeIcon className="h-5 w-5" />
        )}
      </button>
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="max-w-md space-y-6">
      <div className="p-4 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
        <div className="flex gap-3">
          <ShieldCheckIcon className="h-5 w-5 text-aura-600 dark:text-aura-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-aura-800 dark:text-aura-200">Password Requirements</p>
            <ul className="mt-1 text-xs text-aura-700 dark:text-aura-300 space-y-1">
              <li>At least 12 characters long</li>
              <li>One uppercase and one lowercase letter</li>
              <li>One number and one special character</li>
            </ul>
          </div>
        </div>
      </div>

      <FormField label="Current Password" error={errors.currentPassword} required>
        <PasswordInput
          id="currentPassword"
          value={formData.currentPassword}
          onChange={(e) => handleChange('currentPassword', e.target.value)}
          error={errors.currentPassword}
          showPassword={showPasswords.current}
          onToggleShow={() => setShowPasswords((p) => ({ ...p, current: !p.current }))}
          placeholder="Enter current password"
        />
      </FormField>

      <FormField label="New Password" error={errors.newPassword} required>
        <PasswordInput
          id="newPassword"
          value={formData.newPassword}
          onChange={(e) => handleChange('newPassword', e.target.value)}
          error={errors.newPassword}
          showPassword={showPasswords.new}
          onToggleShow={() => setShowPasswords((p) => ({ ...p, new: !p.new }))}
          placeholder="Enter new password"
        />
      </FormField>

      <FormField label="Confirm New Password" error={errors.confirmPassword} required>
        <PasswordInput
          id="confirmPassword"
          value={formData.confirmPassword}
          onChange={(e) => handleChange('confirmPassword', e.target.value)}
          error={errors.confirmPassword}
          showPassword={showPasswords.confirm}
          onToggleShow={() => setShowPasswords((p) => ({ ...p, confirm: !p.confirm }))}
          placeholder="Confirm new password"
        />
      </FormField>

      <button
        type="submit"
        disabled={isLoading || !formData.currentPassword || !formData.newPassword || !formData.confirmPassword}
        className="w-full px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? 'Changing Password...' : 'Change Password'}
      </button>
    </form>
  );
}

/**
 * Notification Preferences Tab
 */
function NotificationsTab({ preferences, onUpdate, isLoading }) {
  const [localPrefs, setLocalPrefs] = useState(preferences);
  const [hasChanges, setHasChanges] = useState(false);
  const [slackWebhookVisible, setSlackWebhookVisible] = useState(false);

  useEffect(() => {
    setLocalPrefs(preferences);
    setHasChanges(false);
  }, [preferences]);

  const handleToggle = (channel, setting, value) => {
    setLocalPrefs((prev) => ({
      ...prev,
      [channel]: {
        ...prev[channel],
        [setting]: value,
      },
    }));
    setHasChanges(true);
  };

  const handleSlackConfigChange = (field, value) => {
    setLocalPrefs((prev) => ({
      ...prev,
      slack: {
        ...prev.slack,
        [field]: value,
      },
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    await onUpdate(localPrefs);
    setHasChanges(false);
  };

  const NotificationRow = ({ label, description, channel, setting }) => (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100">{label}</p>
        <p className="text-xs text-surface-500 dark:text-surface-400">{description}</p>
      </div>
      <Toggle
        checked={localPrefs[channel]?.[setting] ?? false}
        onChange={(checked) => handleToggle(channel, setting, checked)}
        disabled={isLoading || !localPrefs[channel]?.enabled}
      />
    </div>
  );

  return (
    <div className="space-y-8">
      {/* Email Notifications */}
      <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700">
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-aura-100 dark:bg-aura-900/30 rounded-lg">
                <EnvelopeIcon className="h-5 w-5 text-aura-600 dark:text-aura-400" />
              </div>
              <div>
                <h3 className="font-medium text-surface-900 dark:text-surface-100">Email Notifications</h3>
                <p className="text-xs text-surface-500 dark:text-surface-400">Receive updates via email</p>
              </div>
            </div>
            <Toggle
              checked={localPrefs.email?.enabled ?? false}
              onChange={(checked) => handleToggle('email', 'enabled', checked)}
              disabled={isLoading}
            />
          </div>
        </div>
        <div className="px-4 divide-y divide-surface-100 dark:divide-surface-700">
          <NotificationRow
            label="Security Alerts"
            description="Critical security issues requiring attention"
            channel="email"
            setting="security_alerts"
          />
          <NotificationRow
            label="Approval Requests"
            description="New patches and changes requiring your approval"
            channel="email"
            setting="approval_requests"
          />
          <NotificationRow
            label="System Updates"
            description="Platform updates and maintenance notifications"
            channel="email"
            setting="system_updates"
          />
          <NotificationRow
            label="Weekly Digest"
            description="Summary of activity and insights"
            channel="email"
            setting="weekly_digest"
          />
        </div>
      </div>

      {/* In-App Notifications */}
      <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700">
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-olive-100 dark:bg-olive-900/30 rounded-lg">
                <BellIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
              </div>
              <div>
                <h3 className="font-medium text-surface-900 dark:text-surface-100">In-App Notifications</h3>
                <p className="text-xs text-surface-500 dark:text-surface-400">Notifications within the dashboard</p>
              </div>
            </div>
            <Toggle
              checked={localPrefs.in_app?.enabled ?? false}
              onChange={(checked) => handleToggle('in_app', 'enabled', checked)}
              disabled={isLoading}
            />
          </div>
        </div>
        <div className="px-4 divide-y divide-surface-100 dark:divide-surface-700">
          <NotificationRow
            label="Security Alerts"
            description="Real-time security notifications"
            channel="in_app"
            setting="security_alerts"
          />
          <NotificationRow
            label="Approval Requests"
            description="Pending items requiring your action"
            channel="in_app"
            setting="approval_requests"
          />
          <NotificationRow
            label="Agent Updates"
            description="Status changes from your agents"
            channel="in_app"
            setting="agent_updates"
          />
          <NotificationRow
            label="Mentions"
            description="When someone mentions you"
            channel="in_app"
            setting="mentions"
          />
        </div>
      </div>

      {/* Slack Notifications */}
      <div className="bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700">
        <div className="p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <ChatBubbleLeftRightIcon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <h3 className="font-medium text-surface-900 dark:text-surface-100">Slack Notifications</h3>
                <p className="text-xs text-surface-500 dark:text-surface-400">Send alerts to a Slack channel</p>
              </div>
            </div>
            <Toggle
              checked={localPrefs.slack?.enabled ?? false}
              onChange={(checked) => handleToggle('slack', 'enabled', checked)}
              disabled={isLoading}
            />
          </div>
        </div>

        {localPrefs.slack?.enabled && (
          <div className="p-4 space-y-4 bg-surface-50 dark:bg-surface-800/50">
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Webhook URL
              </label>
              <div className="relative">
                <input
                  type={slackWebhookVisible ? 'text' : 'password'}
                  value={localPrefs.slack?.webhook_url || ''}
                  onChange={(e) => handleSlackConfigChange('webhook_url', e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  className="w-full px-3 py-2 pr-10 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
                />
                <button
                  type="button"
                  onClick={() => setSlackWebhookVisible(!slackWebhookVisible)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
                >
                  {slackWebhookVisible ? (
                    <EyeSlashIcon className="h-5 w-5" />
                  ) : (
                    <EyeIcon className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                Channel Name
              </label>
              <input
                type="text"
                value={localPrefs.slack?.channel || ''}
                onChange={(e) => handleSlackConfigChange('channel', e.target.value)}
                placeholder="#security-alerts"
                className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
              />
            </div>
          </div>
        )}

        {localPrefs.slack?.enabled && (
          <div className="px-4 divide-y divide-surface-100 dark:divide-surface-700">
            <NotificationRow
              label="Security Alerts"
              description="Critical security notifications"
              channel="slack"
              setting="security_alerts"
            />
            <NotificationRow
              label="Approval Requests"
              description="Pending approval notifications"
              channel="slack"
              setting="approval_requests"
            />
          </div>
        )}
      </div>

      {hasChanges && (
        <div className="flex justify-end gap-3 pt-4 border-t border-surface-200 dark:border-surface-700">
          <button
            type="button"
            onClick={() => {
              setLocalPrefs(preferences);
              setHasChanges(false);
            }}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Saving...' : 'Save Preferences'}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Sessions Tab
 */
function SessionsTab({ sessions, onRevokeSession, onRevokeAll, isLoading }) {
  const getDeviceIcon = (device) => {
    if (device.toLowerCase().includes('mobile') || device.toLowerCase().includes('ios') || device.toLowerCase().includes('android')) {
      return DevicePhoneMobileIcon;
    }
    return ComputerDesktopIcon;
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">Active Sessions</h3>
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Manage your active sessions across devices
          </p>
        </div>
        {sessions.length > 1 && (
          <button
            onClick={onRevokeAll}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-critical-600 dark:text-critical-400 hover:bg-critical-50 dark:hover:bg-critical-900/20 rounded-lg transition-colors"
          >
            <ExclamationTriangleIcon className="h-4 w-4" />
            Sign out all other sessions
          </button>
        )}
      </div>

      <div className="space-y-3">
        {sessions.map((session) => {
          const DeviceIcon = getDeviceIcon(session.device);

          return (
            <div
              key={session.id}
              className={`
                p-4 rounded-lg border transition-colors
                ${session.is_current
                  ? 'bg-olive-50 dark:bg-olive-900/20 border-olive-200 dark:border-olive-800'
                  : 'bg-white dark:bg-surface-800 border-surface-200 dark:border-surface-700'
                }
              `}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className={`p-2 rounded-lg ${session.is_current ? 'bg-olive-100 dark:bg-olive-900/40' : 'bg-surface-100 dark:bg-surface-700'}`}>
                    <DeviceIcon className={`h-5 w-5 ${session.is_current ? 'text-olive-600 dark:text-olive-400' : 'text-surface-500'}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        {session.device}
                      </p>
                      {session.is_current && (
                        <span className="px-2 py-0.5 text-xs font-medium bg-olive-100 dark:bg-olive-900/40 text-olive-700 dark:text-olive-400 rounded">
                          Current Session
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-4 text-sm text-surface-500 dark:text-surface-400">
                      <span className="flex items-center gap-1">
                        <MapPinIcon className="h-4 w-4" />
                        {session.location}
                      </span>
                      <span className="flex items-center gap-1">
                        <GlobeAltIcon className="h-4 w-4" />
                        {session.ip_address}
                      </span>
                    </div>
                    <p className="mt-1 flex items-center gap-1 text-xs text-surface-400 dark:text-surface-500">
                      <ClockIcon className="h-3.5 w-3.5" />
                      Last active: {formatTimeAgo(session.last_active)}
                    </p>
                  </div>
                </div>

                {!session.is_current && (
                  <button
                    onClick={() => onRevokeSession(session.id)}
                    disabled={isLoading}
                    className="p-2 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
                    title="Revoke session"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {sessions.length === 0 && (
        <div className="text-center py-12">
          <ComputerDesktopIcon className="h-12 w-12 text-surface-300 dark:text-surface-600 mx-auto mb-3" />
          <p className="text-surface-600 dark:text-surface-400">No active sessions found</p>
        </div>
      )}
    </div>
  );
}

/**
 * API Keys Tab
 */
function ApiKeysTab({ apiKeys, onCreate, onDelete, isLoading }) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [selectedScopes, setSelectedScopes] = useState([]);
  const [createdKey, setCreatedKey] = useState(null);
  const [copiedKey, setCopiedKey] = useState(false);

  const handleCreate = async () => {
    if (!newKeyName.trim() || selectedScopes.length === 0) return;

    const result = await onCreate(newKeyName, selectedScopes);
    if (result?.key) {
      setCreatedKey(result);
      setNewKeyName('');
      setSelectedScopes([]);
    }
  };

  const handleCopyKey = async () => {
    if (createdKey?.key) {
      await navigator.clipboard.writeText(createdKey.key);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">Personal Access Tokens</h3>
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Create tokens to authenticate with the Project Aura API
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
        >
          <PlusIcon className="h-4 w-4" />
          Create Token
        </button>
      </div>

      {/* Existing Keys */}
      <div className="space-y-3">
        {apiKeys.map((key) => (
          <div
            key={key.id}
            className="p-4 bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium text-surface-900 dark:text-surface-100">{key.name}</p>
                  <code className="px-2 py-0.5 text-xs bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 rounded">
                    {key.prefix}...
                  </code>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {key.scopes.map((scope) => (
                    <span
                      key={scope}
                      className="px-2 py-0.5 text-xs bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 rounded"
                    >
                      {scope}
                    </span>
                  ))}
                </div>
                <div className="mt-2 text-xs text-surface-500 dark:text-surface-400 space-x-4">
                  <span>Created: {formatDate(key.created_at)}</span>
                  <span>Last used: {formatDate(key.last_used)}</span>
                  {key.expires_at && (
                    <span className={new Date(key.expires_at) < new Date() ? 'text-critical-500' : ''}>
                      Expires: {formatDate(key.expires_at)}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => onDelete(key.id)}
                disabled={isLoading}
                className="p-2 text-surface-400 hover:text-critical-600 dark:hover:text-critical-400 transition-colors"
                title="Delete token"
              >
                <TrashIcon className="h-5 w-5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {apiKeys.length === 0 && (
        <div className="text-center py-12 bg-surface-50 dark:bg-surface-800/50 rounded-lg border border-dashed border-surface-300 dark:border-surface-600">
          <CommandLineIcon className="h-12 w-12 text-surface-300 dark:text-surface-600 mx-auto mb-3" />
          <p className="text-surface-600 dark:text-surface-400">No API tokens created yet</p>
          <p className="text-sm text-surface-500 dark:text-surface-500 mt-1">
            Create a token to start using the API
          </p>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-surface-800 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-auto">
            <div className="p-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
                {createdKey ? 'Token Created' : 'Create New Token'}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setCreatedKey(null);
                  setNewKeyName('');
                  setSelectedScopes([]);
                }}
                className="p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="p-4">
              {createdKey ? (
                <div className="space-y-4">
                  <div className="p-4 bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800 rounded-lg">
                    <div className="flex gap-3">
                      <ExclamationCircleIcon className="h-5 w-5 text-warning-600 dark:text-warning-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-warning-800 dark:text-warning-200">
                          Copy your token now
                        </p>
                        <p className="text-xs text-warning-700 dark:text-warning-300 mt-1">
                          This token will only be shown once. Make sure to copy it now.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Your Token
                    </label>
                    <div className="flex gap-2">
                      <code className="flex-1 p-3 bg-surface-100 dark:bg-surface-700 rounded-lg text-sm font-mono text-surface-900 dark:text-surface-100 break-all">
                        {createdKey.key}
                      </code>
                      <button
                        onClick={handleCopyKey}
                        className="flex-shrink-0 p-3 bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
                      >
                        {copiedKey ? (
                          <CheckCircleIcon className="h-5 w-5" />
                        ) : (
                          <ClipboardDocumentIcon className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setShowCreateModal(false);
                      setCreatedKey(null);
                    }}
                    className="w-full px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 transition-colors"
                  >
                    Done
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Token Name
                    </label>
                    <input
                      type="text"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      placeholder="e.g., CI/CD Pipeline"
                      className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:outline-none focus:ring-2 focus:ring-aura-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                      Permissions
                    </label>
                    <div className="space-y-2 max-h-48 overflow-auto">
                      {API_SCOPES.map((scope) => (
                        <label
                          key={scope.id}
                          className="flex items-start gap-3 p-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-700/50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedScopes.includes(scope.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedScopes((prev) => [...prev, scope.id]);
                              } else {
                                setSelectedScopes((prev) => prev.filter((s) => s !== scope.id));
                              }
                            }}
                            className="mt-0.5 h-4 w-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500"
                          />
                          <div>
                            <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                              {scope.label}
                            </p>
                            <p className="text-xs text-surface-500 dark:text-surface-400">
                              {scope.description}
                            </p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-3 pt-4">
                    <button
                      onClick={() => {
                        setShowCreateModal(false);
                        setNewKeyName('');
                        setSelectedScopes([]);
                      }}
                      className="flex-1 px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreate}
                      disabled={!newKeyName.trim() || selectedScopes.length === 0 || isLoading}
                      className="flex-1 px-4 py-2 text-sm font-medium bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {isLoading ? 'Creating...' : 'Create Token'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Main Profile Page Component
 */
export default function ProfilePage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState('personal');
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, _setSuccess] = useState(null);

  // Data states
  const [profile, setProfile] = useState(null);
  const [notificationPrefs, setNotificationPrefs] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, notifData, sessionsData, keysData] = await Promise.all([
        getProfile(),
        getNotificationPreferences(),
        getSessions(),
        getApiKeys(),
      ]);
      setProfile(profileData);
      setNotificationPrefs(notifData);
      setSessions(sessionsData);
      setApiKeys(keysData);
    } catch (err) {
      setError('Failed to load profile data');
      console.error('Profile load error:', err);
    } finally {
      setLoading(false);
    }
  };

  const showSuccess = (message) => {
    toast.success(message);
  };

  const showError = (message) => {
    toast.error(message);
  };

  // Handle refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await loadData();
      showSuccess('Profile refreshed');
    } catch (err) {
      showError('Failed to refresh profile');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Handlers
  const handleAvatarUpload = async (file) => {
    setSaving(true);
    try {
      const result = await uploadAvatar(file);
      setProfile((prev) => ({ ...prev, avatar_url: result.avatar_url }));
      showSuccess('Avatar updated successfully');
    } catch (err) {
      showError('Failed to upload avatar');
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarDelete = async () => {
    setSaving(true);
    try {
      await deleteAvatar();
      setProfile((prev) => ({ ...prev, avatar_url: null }));
      showSuccess('Avatar removed');
    } catch (err) {
      showError('Failed to remove avatar');
    } finally {
      setSaving(false);
    }
  };

  const handleProfileUpdate = async (data) => {
    setSaving(true);
    try {
      const updated = await updateProfile(data);
      setProfile(updated);
      showSuccess('Profile updated successfully');
    } catch (err) {
      showError('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordChange = async (currentPassword, newPassword) => {
    setSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      showSuccess('Password changed successfully');
      return true;
    } catch (err) {
      showError(err.message || 'Failed to change password');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleNotificationUpdate = async (prefs) => {
    setSaving(true);
    try {
      const updated = await updateNotificationPreferences(prefs);
      setNotificationPrefs(updated);
      showSuccess('Notification preferences updated');
    } catch (err) {
      showError('Failed to update notification preferences');
    } finally {
      setSaving(false);
    }
  };

  const handleRevokeSession = async (sessionId) => {
    setSaving(true);
    try {
      await revokeSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      showSuccess('Session revoked');
    } catch (err) {
      showError('Failed to revoke session');
    } finally {
      setSaving(false);
    }
  };

  const handleRevokeAllSessions = async () => {
    if (!confirm('Are you sure you want to sign out of all other sessions?')) return;

    setSaving(true);
    try {
      await revokeAllSessions();
      setSessions((prev) => prev.filter((s) => s.is_current));
      showSuccess('All other sessions have been signed out');
    } catch (err) {
      showError('Failed to revoke sessions');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateApiKey = async (name, scopes) => {
    setSaving(true);
    try {
      const newKey = await createApiKey(name, scopes);
      setApiKeys((prev) => [...prev, { ...newKey, key: undefined }]);
      return newKey;
    } catch (err) {
      showError('Failed to create API key');
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteApiKey = async (keyId) => {
    if (!confirm('Are you sure you want to delete this API key? This action cannot be undone.')) return;

    setSaving(true);
    try {
      await deleteApiKey(keyId);
      setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
      showSuccess('API key deleted');
    } catch (err) {
      showError('Failed to delete API key');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ArrowPathIcon className="h-12 w-12 text-aura-600 dark:text-aura-400 animate-spin mx-auto" />
          <p className="mt-4 text-surface-600 dark:text-surface-400">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      {/* Header */}
      <div className="bg-white dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <UserCircleIcon className="h-8 w-8 text-aura-600 dark:text-aura-400" />
            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Profile</h1>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Manage your account settings and preferences
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Status messages */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-critical-50 dark:bg-critical-900/30 border border-critical-200 dark:border-critical-800 rounded-lg flex items-center gap-3">
          <ExclamationTriangleIcon className="h-5 w-5 text-critical-600 dark:text-critical-400" />
          <span className="text-critical-700 dark:text-critical-300">{error}</span>
        </div>
      )}

      {success && (
        <div className="mx-6 mt-4 p-4 bg-olive-50 dark:bg-olive-900/30 border border-olive-200 dark:border-olive-800 rounded-lg flex items-center gap-3">
          <CheckCircleIcon className="h-5 w-5 text-olive-600 dark:text-olive-400" />
          <span className="text-olive-700 dark:text-olive-300">{success}</span>
        </div>
      )}

      <div className="px-6 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Sidebar with Avatar and Tabs */}
          <div className="lg:w-64 flex-shrink-0 space-y-6">
            {/* Avatar Card */}
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              <AvatarUpload
                avatarUrl={profile?.avatar_url}
                name={profile?.name || user?.name}
                onUpload={handleAvatarUpload}
                onDelete={handleAvatarDelete}
                isLoading={saving}
              />
            </div>

            {/* Tabs */}
            <nav className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] overflow-hidden">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    w-full flex items-center gap-3 px-4 py-3 text-left transition-colors
                    ${activeTab === tab.id
                      ? 'bg-aura-50 dark:bg-aura-900/20 text-aura-700 dark:text-aura-400 border-l-2 border-aura-600'
                      : 'text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700/50 border-l-2 border-transparent'
                    }
                  `}
                >
                  <tab.icon className="h-5 w-5" />
                  <span className="font-medium">{tab.label}</span>
                </button>
              ))}
            </nav>
          </div>

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30 shadow-[var(--shadow-glass)] p-6">
              {activeTab === 'personal' && (
                <PersonalInfoTab
                  profile={profile}
                  onUpdate={handleProfileUpdate}
                  isLoading={saving}
                />
              )}

              {activeTab === 'password' && (
                <PasswordTab
                  onChangePassword={handlePasswordChange}
                  isLoading={saving}
                />
              )}

              {activeTab === 'notifications' && notificationPrefs && (
                <NotificationsTab
                  preferences={notificationPrefs}
                  onUpdate={handleNotificationUpdate}
                  isLoading={saving}
                />
              )}

              {activeTab === 'sessions' && (
                <SessionsTab
                  sessions={sessions}
                  onRevokeSession={handleRevokeSession}
                  onRevokeAll={handleRevokeAllSessions}
                  isLoading={saving}
                />
              )}

              {activeTab === 'api-keys' && (
                <ApiKeysTab
                  apiKeys={apiKeys}
                  onCreate={handleCreateApiKey}
                  onDelete={handleDeleteApiKey}
                  isLoading={saving}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
