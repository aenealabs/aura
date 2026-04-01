/**
 * Schedule Report Modal Component
 *
 * Allows users to create and manage scheduled report delivery for dashboards.
 * Implements ADR-064 Phase 3 scheduled reports functionality.
 *
 * Features:
 * - Schedule frequency selection (daily, weekly, biweekly, monthly)
 * - Multiple recipient management
 * - Report format selection (PDF, HTML email, CSV)
 * - Time and timezone configuration
 * - Preview and manual send options
 */

import React, { useState, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';

// Schedule frequency options
const FREQUENCY_OPTIONS = [
  { value: 'daily', label: 'Daily', description: 'Send every day' },
  { value: 'weekly', label: 'Weekly', description: 'Send once per week' },
  { value: 'biweekly', label: 'Bi-weekly', description: 'Send every two weeks' },
  { value: 'monthly', label: 'Monthly', description: 'Send once per month' },
];

// Days of week for weekly schedules
const DAYS_OF_WEEK = [
  { value: 'monday', label: 'Monday' },
  { value: 'tuesday', label: 'Tuesday' },
  { value: 'wednesday', label: 'Wednesday' },
  { value: 'thursday', label: 'Thursday' },
  { value: 'friday', label: 'Friday' },
  { value: 'saturday', label: 'Saturday' },
  { value: 'sunday', label: 'Sunday' },
];

// Report format options
const FORMAT_OPTIONS = [
  { value: 'html_email', label: 'HTML Email', description: 'Interactive email with charts' },
  { value: 'pdf', label: 'PDF Attachment', description: 'Static PDF document' },
  { value: 'csv', label: 'CSV Data', description: 'Raw data for analysis' },
];

// Common timezones
const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'Europe/London', label: 'London (GMT)' },
  { value: 'Europe/Paris', label: 'Central European (CET)' },
  { value: 'Asia/Tokyo', label: 'Japan (JST)' },
];

/**
 * Recipient Input Component
 */
function RecipientInput({ recipients, onChange, maxRecipients = 20 }) {
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState('');

  const handleAdd = useCallback(() => {
    const email = inputValue.trim().toLowerCase();

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address');
      return;
    }

    // Check for duplicates
    if (recipients.includes(email)) {
      setError('This email is already added');
      return;
    }

    // Check max limit
    if (recipients.length >= maxRecipients) {
      setError(`Maximum ${maxRecipients} recipients allowed`);
      return;
    }

    onChange([...recipients, email]);
    setInputValue('');
    setError('');
  }, [inputValue, recipients, onChange, maxRecipients]);

  const handleRemove = useCallback((email) => {
    onChange(recipients.filter(r => r !== email));
  }, [recipients, onChange]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAdd();
    }
  }, [handleAdd]);

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          type="email"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter email address"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!inputValue.trim() || recipients.length >= maxRecipients}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium"
        >
          Add
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {recipients.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {recipients.map((email) => (
            <span
              key={email}
              className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
            >
              {email}
              <button
                type="button"
                onClick={() => handleRemove(email)}
                className="ml-1 text-gray-500 hover:text-red-500"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-500">
        {recipients.length}/{maxRecipients} recipients
      </p>
    </div>
  );
}

RecipientInput.propTypes = {
  recipients: PropTypes.arrayOf(PropTypes.string).isRequired,
  onChange: PropTypes.func.isRequired,
  maxRecipients: PropTypes.number,
};

/**
 * Schedule Report Modal Component
 */
function ScheduleReportModal({
  isOpen,
  onClose,
  dashboardId,
  dashboardName,
  existingSchedule = null,
  onSave,
  onSendNow,
}) {
  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [recipients, setRecipients] = useState([]);
  const [frequency, setFrequency] = useState('weekly');
  const [timeUtc, setTimeUtc] = useState('09:00');
  const [dayOfWeek, setDayOfWeek] = useState('monday');
  const [dayOfMonth, setDayOfMonth] = useState(1);
  const [timezone, setTimezone] = useState('UTC');
  const [format, setFormat] = useState('html_email');
  const [subjectTemplate, setSubjectTemplate] = useState('{dashboard_name} - {report_name} Report');
  const [isActive, setIsActive] = useState(true);

  // UI state
  const [isSaving, setIsSaving] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');

  // Initialize form with existing schedule
  useEffect(() => {
    if (existingSchedule) {
      setName(existingSchedule.name || '');
      setDescription(existingSchedule.description || '');
      setRecipients(existingSchedule.recipients || []);
      setFrequency(existingSchedule.schedule?.frequency || 'weekly');
      setTimeUtc(existingSchedule.schedule?.time_utc || '09:00');
      setDayOfWeek(existingSchedule.schedule?.day_of_week || 'monday');
      setDayOfMonth(existingSchedule.schedule?.day_of_month || 1);
      setTimezone(existingSchedule.schedule?.timezone || 'UTC');
      setFormat(existingSchedule.format || 'html_email');
      setSubjectTemplate(existingSchedule.subject_template || '{dashboard_name} - {report_name} Report');
      setIsActive(existingSchedule.is_active !== false);
    } else {
      // Reset to defaults
      setName('');
      setDescription('');
      setRecipients([]);
      setFrequency('weekly');
      setTimeUtc('09:00');
      setDayOfWeek('monday');
      setDayOfMonth(1);
      setTimezone('UTC');
      setFormat('html_email');
      setSubjectTemplate('{dashboard_name} - {report_name} Report');
      setIsActive(true);
    }
    setError('');
  }, [existingSchedule, isOpen]);

  // Build schedule data
  const buildScheduleData = useCallback(() => {
    const scheduleConfig = {
      frequency,
      time_utc: timeUtc,
      timezone,
    };

    if (frequency === 'weekly' || frequency === 'biweekly') {
      scheduleConfig.day_of_week = dayOfWeek;
    }

    if (frequency === 'monthly') {
      scheduleConfig.day_of_month = dayOfMonth;
    }

    return {
      name,
      description,
      recipients,
      schedule: scheduleConfig,
      format,
      subject_template: subjectTemplate,
      is_active: isActive,
    };
  }, [name, description, recipients, frequency, timeUtc, dayOfWeek, dayOfMonth, timezone, format, subjectTemplate, isActive]);

  // Validate form
  const validateForm = useCallback(() => {
    if (!name.trim()) {
      return 'Report name is required';
    }
    if (recipients.length === 0) {
      return 'At least one recipient is required';
    }
    if ((frequency === 'weekly' || frequency === 'biweekly') && !dayOfWeek) {
      return 'Day of week is required for weekly schedules';
    }
    if (frequency === 'monthly' && !dayOfMonth) {
      return 'Day of month is required for monthly schedules';
    }
    return null;
  }, [name, recipients, frequency, dayOfWeek, dayOfMonth]);

  // Handle save
  const handleSave = useCallback(async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      await onSave(buildScheduleData(), existingSchedule?.report_id);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save schedule');
    } finally {
      setIsSaving(false);
    }
  }, [validateForm, buildScheduleData, existingSchedule, onSave, onClose]);

  // Handle send now
  const handleSendNow = useCallback(async () => {
    if (!existingSchedule?.report_id) return;

    setIsSending(true);
    setError('');

    try {
      await onSendNow(existingSchedule.report_id);
    } catch (err) {
      setError(err.message || 'Failed to send report');
    } finally {
      setIsSending(false);
    }
  }, [existingSchedule, onSendNow]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {existingSchedule ? 'Edit Scheduled Report' : 'Schedule Report'}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Dashboard: {dashboardName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Error message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Report Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Report Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Weekly Security Summary"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              maxLength={100}
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description for this report schedule"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={2}
              maxLength={500}
            />
          </div>

          {/* Recipients */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Recipients *
            </label>
            <RecipientInput
              recipients={recipients}
              onChange={setRecipients}
            />
          </div>

          {/* Schedule Configuration */}
          <div className="border border-gray-200 rounded-lg p-4 space-y-4">
            <h3 className="text-sm font-medium text-gray-900">Schedule</h3>

            {/* Frequency */}
            <div>
              <label className="block text-sm text-gray-600 mb-2">
                Frequency
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {FREQUENCY_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setFrequency(option.value)}
                    className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                      frequency === option.value
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Day of Week (for weekly/biweekly) */}
            {(frequency === 'weekly' || frequency === 'biweekly') && (
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  Day of Week
                </label>
                <select
                  value={dayOfWeek}
                  onChange={(e) => setDayOfWeek(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {DAYS_OF_WEEK.map((day) => (
                    <option key={day.value} value={day.value}>
                      {day.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Day of Month (for monthly) */}
            {frequency === 'monthly' && (
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  Day of Month
                </label>
                <select
                  value={dayOfMonth}
                  onChange={(e) => setDayOfMonth(parseInt(e.target.value, 10))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                    <option key={day} value={day}>
                      {day}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Limited to 1-28 to ensure delivery every month
                </p>
              </div>
            )}

            {/* Time and Timezone */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  Time
                </label>
                <input
                  type="time"
                  value={timeUtc}
                  onChange={(e) => setTimeUtc(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  Timezone
                </label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {TIMEZONE_OPTIONS.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Report Format */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Report Format
            </label>
            <div className="space-y-2">
              {FORMAT_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`flex items-start p-3 rounded-lg border cursor-pointer transition-colors ${
                    format === option.value
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="format"
                    value={option.value}
                    checked={format === option.value}
                    onChange={(e) => setFormat(e.target.value)}
                    className="mt-1 mr-3"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900">
                      {option.label}
                    </div>
                    <div className="text-xs text-gray-500">
                      {option.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Subject Template */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Subject Template
            </label>
            <input
              type="text"
              value={subjectTemplate}
              onChange={(e) => setSubjectTemplate(e.target.value)}
              placeholder="{dashboard_name} - {report_name} Report"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              maxLength={200}
            />
            <p className="text-xs text-gray-500 mt-1">
              Available variables: {'{dashboard_name}'}, {'{report_name}'}, {'{date}'}
            </p>
          </div>

          {/* Active Toggle (for existing schedules) */}
          {existingSchedule && (
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <div className="text-sm font-medium text-gray-900">
                  Schedule Active
                </div>
                <div className="text-xs text-gray-500">
                  {isActive ? 'Reports will be sent on schedule' : 'Reports are paused'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsActive(!isActive)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  isActive ? 'bg-blue-500' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    isActive ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          )}

          {/* Schedule Stats (for existing schedules) */}
          {existingSchedule && (
            <div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
              <div>
                <div className="text-xs text-gray-500">Reports Sent</div>
                <div className="text-lg font-semibold text-gray-900">
                  {existingSchedule.send_count || 0}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Next Scheduled</div>
                <div className="text-sm font-medium text-gray-900">
                  {existingSchedule.next_run_at
                    ? new Date(existingSchedule.next_run_at).toLocaleString()
                    : 'Not scheduled'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50">
          <div>
            {existingSchedule && onSendNow && (
              <button
                type="button"
                onClick={handleSendNow}
                disabled={isSending || isSaving}
                className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 disabled:text-gray-400"
              >
                {isSending ? 'Sending...' : 'Send Now'}
              </button>
            )}
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 disabled:text-gray-400"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving || isSending}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm font-medium"
            >
              {isSaving ? 'Saving...' : existingSchedule ? 'Update Schedule' : 'Create Schedule'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

ScheduleReportModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  dashboardId: PropTypes.string.isRequired,
  dashboardName: PropTypes.string.isRequired,
  existingSchedule: PropTypes.shape({
    report_id: PropTypes.string,
    name: PropTypes.string,
    description: PropTypes.string,
    recipients: PropTypes.arrayOf(PropTypes.string),
    schedule: PropTypes.shape({
      frequency: PropTypes.string,
      time_utc: PropTypes.string,
      day_of_week: PropTypes.string,
      day_of_month: PropTypes.number,
      timezone: PropTypes.string,
    }),
    format: PropTypes.string,
    subject_template: PropTypes.string,
    is_active: PropTypes.bool,
    send_count: PropTypes.number,
    next_run_at: PropTypes.string,
  }),
  onSave: PropTypes.func.isRequired,
  onSendNow: PropTypes.func,
};

export default ScheduleReportModal;
