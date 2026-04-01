/**
 * Cron Expression Builder
 *
 * Visual builder for cron schedules with preset options and custom editor.
 * ADR-055 Phase 3: Recurring Tasks and Advanced Features
 */

import { useState, useEffect, useMemo } from 'react';
import {
  ClockIcon,
  CalendarDaysIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

// Preset schedules for common use cases
const PRESET_SCHEDULES = [
  { id: 'hourly', label: 'Every hour', cron: '0 * * * *', description: 'At minute 0 of every hour' },
  { id: 'daily-6am', label: 'Daily at 6 AM', cron: '0 6 * * *', description: 'Every day at 6:00 AM' },
  { id: 'daily-midnight', label: 'Daily at midnight', cron: '0 0 * * *', description: 'Every day at 12:00 AM' },
  { id: 'weekdays-9am', label: 'Weekdays at 9 AM', cron: '0 9 * * 1-5', description: 'Monday-Friday at 9:00 AM' },
  { id: 'weekly-monday', label: 'Weekly on Monday', cron: '0 6 * * 1', description: 'Every Monday at 6:00 AM' },
  { id: 'weekly-sunday', label: 'Weekly on Sunday', cron: '0 6 * * 0', description: 'Every Sunday at 6:00 AM' },
  { id: 'monthly-1st', label: 'Monthly on 1st', cron: '0 6 1 * *', description: '1st of every month at 6:00 AM' },
  { id: 'quarterly', label: 'Quarterly', cron: '0 6 1 1,4,7,10 *', description: 'Jan, Apr, Jul, Oct 1st at 6:00 AM' },
];

// Days of week options
const DAYS_OF_WEEK = [
  { value: '0', label: 'Sun', fullLabel: 'Sunday' },
  { value: '1', label: 'Mon', fullLabel: 'Monday' },
  { value: '2', label: 'Tue', fullLabel: 'Tuesday' },
  { value: '3', label: 'Wed', fullLabel: 'Wednesday' },
  { value: '4', label: 'Thu', fullLabel: 'Thursday' },
  { value: '5', label: 'Fri', fullLabel: 'Friday' },
  { value: '6', label: 'Sat', fullLabel: 'Saturday' },
];

// Hours options (0-23)
const HOURS = Array.from({ length: 24 }, (_, i) => ({
  value: i.toString(),
  label: i === 0 ? '12 AM' : i < 12 ? `${i} AM` : i === 12 ? '12 PM' : `${i - 12} PM`,
}));

// Minutes options (0, 15, 30, 45)
const MINUTES = [
  { value: '0', label: ':00' },
  { value: '15', label: ':15' },
  { value: '30', label: ':30' },
  { value: '45', label: ':45' },
];

// Frequency options
const FREQUENCIES = [
  { id: 'hourly', label: 'Hourly' },
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'custom', label: 'Custom' },
];

export default function CronExpressionBuilder({ value, onChange, showPreview = true }) {
  const [mode, setMode] = useState('preset'); // 'preset' | 'builder' | 'advanced'
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [frequency, setFrequency] = useState('daily');
  const [hour, setHour] = useState('6');
  const [minute, setMinute] = useState('0');
  const [selectedDays, setSelectedDays] = useState(['1']); // Monday
  const [dayOfMonth, setDayOfMonth] = useState('1');
  const [customCron, setCustomCron] = useState(value || '0 6 * * *');

  // Parse incoming value to set initial state
  useEffect(() => {
    if (value) {
      // Try to match a preset
      const matchingPreset = PRESET_SCHEDULES.find((p) => p.cron === value);
      if (matchingPreset) {
        setMode('preset');
        setSelectedPreset(matchingPreset.id);
        return;
      }

      // Try to parse the cron expression
      const parts = value.split(' ');
      if (parts.length === 5) {
        setCustomCron(value);
        parseCronToBuilder(parts);
      }
    }
  }, []);

  // Parse cron expression to builder state
  const parseCronToBuilder = (parts) => {
    const [min, hr, dom, , dow] = parts;

    setMinute(min === '*' ? '0' : min);
    setHour(hr === '*' ? '0' : hr);

    if (dow !== '*' && dow !== '?') {
      setFrequency('weekly');
      setSelectedDays(dow.includes(',') ? dow.split(',') : dow.includes('-') ? expandRange(dow) : [dow]);
    } else if (dom !== '*' && dom !== '?') {
      setFrequency('monthly');
      setDayOfMonth(dom);
    } else if (hr === '*') {
      setFrequency('hourly');
    } else {
      setFrequency('daily');
    }
  };

  // Expand range like "1-5" to ["1","2","3","4","5"]
  const expandRange = (range) => {
    const [start, end] = range.split('-').map(Number);
    return Array.from({ length: end - start + 1 }, (_, i) => (start + i).toString());
  };

  // Build cron expression from builder state
  const buildCronExpression = useMemo(() => {
    switch (frequency) {
      case 'hourly':
        return `${minute} * * * *`;
      case 'daily':
        return `${minute} ${hour} * * *`;
      case 'weekly':
        const days = selectedDays.sort((a, b) => Number(a) - Number(b)).join(',');
        return `${minute} ${hour} * * ${days || '*'}`;
      case 'monthly':
        return `${minute} ${hour} ${dayOfMonth} * *`;
      default:
        return customCron;
    }
  }, [frequency, minute, hour, selectedDays, dayOfMonth, customCron]);

  // Get the current cron expression based on mode
  const currentCron = useMemo(() => {
    if (mode === 'preset' && selectedPreset) {
      return PRESET_SCHEDULES.find((p) => p.id === selectedPreset)?.cron || '';
    } else if (mode === 'advanced') {
      return customCron;
    } else {
      return buildCronExpression;
    }
  }, [mode, selectedPreset, customCron, buildCronExpression]);

  // Notify parent of changes
  useEffect(() => {
    if (currentCron && currentCron !== value) {
      onChange?.(currentCron);
    }
  }, [currentCron, onChange, value]);

  // Human-readable description of cron
  const cronDescription = useMemo(() => {
    return describeCron(currentCron);
  }, [currentCron]);

  // Toggle day selection
  const toggleDay = (dayValue) => {
    setSelectedDays((prev) =>
      prev.includes(dayValue)
        ? prev.filter((d) => d !== dayValue)
        : [...prev, dayValue]
    );
  };

  return (
    <div className="space-y-4">
      {/* Mode Selector */}
      <div className="flex items-center gap-2 p-1 bg-surface-100 dark:bg-surface-700 rounded-lg">
        <button
          onClick={() => setMode('preset')}
          className={`flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'preset'
              ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-surface-100 shadow-sm'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
          }`}
        >
          Presets
        </button>
        <button
          onClick={() => setMode('builder')}
          className={`flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'builder'
              ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-surface-100 shadow-sm'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
          }`}
        >
          Builder
        </button>
        <button
          onClick={() => setMode('advanced')}
          className={`flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'advanced'
              ? 'bg-white dark:bg-surface-600 text-surface-900 dark:text-surface-100 shadow-sm'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200'
          }`}
        >
          Advanced
        </button>
      </div>

      {/* Preset Mode */}
      {mode === 'preset' && (
        <div className="grid grid-cols-2 gap-2">
          {PRESET_SCHEDULES.map((preset) => (
            <button
              key={preset.id}
              onClick={() => setSelectedPreset(preset.id)}
              className={`p-3 text-left rounded-lg border transition-all ${
                selectedPreset === preset.id
                  ? 'border-aura-500 bg-aura-50 dark:bg-aura-900/20 ring-2 ring-aura-500/20'
                  : 'border-surface-200 dark:border-surface-600 hover:border-surface-300 dark:hover:border-surface-500'
              }`}
            >
              <p className="font-medium text-sm text-surface-900 dark:text-surface-100">
                {preset.label}
              </p>
              <p className="text-xs text-surface-500 mt-0.5">{preset.description}</p>
            </button>
          ))}
        </div>
      )}

      {/* Builder Mode */}
      {mode === 'builder' && (
        <div className="space-y-4">
          {/* Frequency */}
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Frequency
            </label>
            <div className="flex flex-wrap gap-2">
              {FREQUENCIES.filter((f) => f.id !== 'custom').map((freq) => (
                <button
                  key={freq.id}
                  onClick={() => setFrequency(freq.id)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    frequency === freq.id
                      ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-300'
                      : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-600'
                  }`}
                >
                  {freq.label}
                </button>
              ))}
            </div>
          </div>

          {/* Time Selection (not for hourly) */}
          {frequency !== 'hourly' && (
            <div className="flex items-center gap-4">
              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Time
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={hour}
                    onChange={(e) => setHour(e.target.value)}
                    className="px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                  >
                    {HOURS.map((h) => (
                      <option key={h.value} value={h.value}>
                        {h.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={minute}
                    onChange={(e) => setMinute(e.target.value)}
                    className="px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
                  >
                    {MINUTES.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* Minute Selection (for hourly) */}
          {frequency === 'hourly' && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                At minute
              </label>
              <select
                value={minute}
                onChange={(e) => setMinute(e.target.value)}
                className="px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
              >
                {MINUTES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.value}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Day of Week Selection (for weekly) */}
          {frequency === 'weekly' && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Days of week
              </label>
              <div className="flex gap-1">
                {DAYS_OF_WEEK.map((day) => (
                  <button
                    key={day.value}
                    onClick={() => toggleDay(day.value)}
                    className={`w-10 h-10 text-sm font-medium rounded-lg transition-colors ${
                      selectedDays.includes(day.value)
                        ? 'bg-aura-500 text-white'
                        : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-600'
                    }`}
                    title={day.fullLabel}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Day of Month Selection (for monthly) */}
          {frequency === 'monthly' && (
            <div>
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                Day of month
              </label>
              <select
                value={dayOfMonth}
                onChange={(e) => setDayOfMonth(e.target.value)}
                className="px-3 py-2 text-sm border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
              >
                {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
                  <option key={d} value={d.toString()}>
                    {d}
                    {d === 1 ? 'st' : d === 2 ? 'nd' : d === 3 ? 'rd' : 'th'}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {/* Advanced Mode */}
      {mode === 'advanced' && (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
              Cron Expression
            </label>
            <input
              type="text"
              value={customCron}
              onChange={(e) => setCustomCron(e.target.value)}
              placeholder="0 6 * * *"
              className="w-full px-3 py-2 text-sm font-mono border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
            />
          </div>
          <div className="flex items-start gap-2 p-3 bg-surface-50 dark:bg-surface-800 rounded-lg">
            <InformationCircleIcon className="w-5 h-5 text-surface-400 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-surface-500">
              <p className="font-medium mb-1">Cron Format: minute hour day-of-month month day-of-week</p>
              <p>Examples:</p>
              <ul className="mt-1 space-y-0.5">
                <li><code className="bg-surface-200 dark:bg-surface-700 px-1 rounded">0 6 * * *</code> - Daily at 6 AM</li>
                <li><code className="bg-surface-200 dark:bg-surface-700 px-1 rounded">0 9 * * 1-5</code> - Weekdays at 9 AM</li>
                <li><code className="bg-surface-200 dark:bg-surface-700 px-1 rounded">0 0 1 * *</code> - Monthly on 1st at midnight</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Preview */}
      {showPreview && currentCron && (
        <div className="p-3 bg-aura-50 dark:bg-aura-900/20 border border-aura-200 dark:border-aura-800 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <ArrowPathIcon className="w-4 h-4 text-aura-600 dark:text-aura-400" />
            <span className="text-sm font-medium text-aura-700 dark:text-aura-300">
              Schedule Preview
            </span>
          </div>
          <p className="text-sm text-aura-600 dark:text-aura-400">{cronDescription}</p>
          <p className="text-xs text-aura-500 dark:text-aura-500 mt-1 font-mono">
            {currentCron}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Generate human-readable description of a cron expression
 */
function describeCron(cron) {
  if (!cron) return '';

  const parts = cron.split(' ');
  if (parts.length !== 5) return 'Invalid cron expression';

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

  // Check for preset matches
  const preset = PRESET_SCHEDULES.find((p) => p.cron === cron);
  if (preset) return preset.description;

  // Build description
  let desc = '';

  // Time component
  if (hour === '*') {
    desc = `Every hour at minute ${minute}`;
  } else {
    const hourNum = parseInt(hour);
    const minNum = parseInt(minute);
    const timeStr = formatTime(hourNum, minNum);
    desc = `At ${timeStr}`;
  }

  // Day of week component
  if (dayOfWeek !== '*' && dayOfWeek !== '?') {
    const days = dayOfWeek.split(',').map((d) => {
      if (d.includes('-')) {
        const [start, end] = d.split('-');
        return `${getDayName(start)}-${getDayName(end)}`;
      }
      return getDayName(d);
    });
    desc += ` on ${days.join(', ')}`;
  }
  // Day of month component
  else if (dayOfMonth !== '*' && dayOfMonth !== '?') {
    desc += ` on day ${dayOfMonth} of the month`;
  } else if (hour !== '*') {
    desc += ' every day';
  }

  // Month component
  if (month !== '*' && month !== '?') {
    const months = month.split(',').map(getMonthName);
    desc += ` in ${months.join(', ')}`;
  }

  return desc;
}

function formatTime(hour, minute) {
  const period = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  const displayMinute = minute.toString().padStart(2, '0');
  return `${displayHour}:${displayMinute} ${period}`;
}

function getDayName(day) {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  return days[parseInt(day)] || day;
}

function getMonthName(month) {
  const months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'];
  return months[parseInt(month)] || month;
}
