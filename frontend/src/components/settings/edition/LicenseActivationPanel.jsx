/**
 * License Activation Panel Component
 *
 * Provides license activation via code input, file upload, or trial.
 */

import { useState, useCallback } from 'react';
import {
  KeyIcon,
  DocumentArrowUpIcon,
  SparklesIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import { activateLicense, activateLicenseFile, startTrial } from '../../../services/editionApi';

const TABS = [
  { id: 'code', label: 'Activation Code', icon: KeyIcon },
  { id: 'file', label: 'Upload File', icon: DocumentArrowUpIcon },
];

export default function LicenseActivationPanel({
  onSuccess,
  onError,
  defaultExpanded = true,
  showTrial = true,
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [activeTab, setActiveTab] = useState('code');
  const [licenseKey, setLicenseKey] = useState('');
  const [licenseFile, setLicenseFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Handle license key activation
  const handleActivateCode = async () => {
    if (!licenseKey.trim()) {
      setError('Please enter a license key');
      return;
    }

    setActivating(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await activateLicense(licenseKey.trim());
      setSuccess('License activated successfully!');
      setLicenseKey('');
      onSuccess?.(result);
    } catch (err) {
      const message = err.message || 'Failed to activate license';
      setError(message);
      onError?.(message);
    } finally {
      setActivating(false);
    }
  };

  // Handle license file upload
  const handleActivateFile = async () => {
    if (!licenseFile) {
      setError('Please select a license file');
      return;
    }

    setActivating(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await activateLicenseFile(licenseFile);
      setSuccess('License activated successfully!');
      setLicenseFile(null);
      onSuccess?.(result);
    } catch (err) {
      const message = err.message || 'Failed to upload license file';
      setError(message);
      onError?.(message);
    } finally {
      setActivating(false);
    }
  };

  // Handle trial activation
  const handleStartTrial = async () => {
    setActivating(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await startTrial({});
      setSuccess('Trial activated! You have 30 days of Enterprise features.');
      onSuccess?.(result);
    } catch (err) {
      const message = err.message || 'Failed to start trial';
      setError(message);
      onError?.(message);
    } finally {
      setActivating(false);
    }
  };

  // Drag and drop handlers
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.name.endsWith('.lic') || file.name.endsWith('.json')) {
        setLicenseFile(file);
        setError(null);
      } else {
        setError('Please upload a .lic or .json license file');
      }
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      setLicenseFile(file);
      setError(null);
    }
  }, []);

  return (
    <div className="bg-white dark:bg-surface-800 backdrop-blur-xl rounded-xl border border-surface-200/50 dark:border-surface-700/30">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-6 text-left"
      >
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
          Activate License
        </h3>
        {expanded ? (
          <ChevronUpIcon className="h-5 w-5 text-surface-400" />
        ) : (
          <ChevronDownIcon className="h-5 w-5 text-surface-400" />
        )}
      </button>

      {/* Content */}
      {expanded && (
        <div className="px-6 pb-6 space-y-6">
          {/* Status Messages */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg text-critical-700 dark:text-critical-300 text-sm">
              <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0" />
              {error}
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 p-3 bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-800 rounded-lg text-olive-700 dark:text-olive-300 text-sm">
              <CheckCircleIcon className="h-5 w-5 flex-shrink-0" />
              {success}
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 border-b border-surface-200 dark:border-surface-700">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setError(null);
                  }}
                  className={`
                    flex items-center gap-2 px-4 py-2 text-sm font-medium
                    border-b-2 -mb-px transition-colors duration-200
                    ${activeTab === tab.id
                      ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                      : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
                    }
                  `}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <div className="min-h-[180px]">
            {activeTab === 'code' && (
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="license-key"
                    className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2"
                  >
                    Enter your license key
                  </label>
                  <input
                    id="license-key"
                    type="text"
                    value={licenseKey}
                    onChange={(e) => setLicenseKey(e.target.value)}
                    placeholder="AURA-ENT-XXXX-XXXX-XXXX"
                    autoComplete="off"
                    className="
                      w-full px-4 py-3
                      border border-surface-200/50 dark:border-surface-600/50
                      rounded-xl
                      bg-white dark:bg-surface-700
                      backdrop-blur-sm
                      text-surface-900 dark:text-surface-100
                      placeholder-surface-400 dark:placeholder-surface-500
                      focus:ring-2 focus:ring-aura-500 focus:border-aura-500
                      transition-all duration-200
                      font-mono text-sm tracking-wide
                    "
                  />
                </div>
                <button
                  onClick={handleActivateCode}
                  disabled={activating || !licenseKey.trim()}
                  className="
                    w-full py-3 px-4 rounded-xl
                    bg-aura-600 hover:bg-aura-700
                    disabled:bg-surface-300 dark:disabled:bg-surface-600
                    text-white font-medium
                    transition-colors duration-200
                    flex items-center justify-center gap-2
                    disabled:cursor-not-allowed
                  "
                >
                  {activating ? (
                    <>
                      <ArrowPathIcon className="h-5 w-5 animate-spin" />
                      Activating...
                    </>
                  ) : (
                    'Activate License'
                  )}
                </button>
              </div>
            )}

            {activeTab === 'file' && (
              <div className="space-y-4">
                <div
                  onDragEnter={handleDragEnter}
                  onDragLeave={handleDragLeave}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  className={`
                    border-2 border-dashed rounded-xl p-8 text-center
                    transition-all duration-200 cursor-pointer
                    ${isDragging
                      ? 'border-aura-400 bg-aura-50/50 dark:bg-aura-900/20'
                      : 'border-surface-300/50 dark:border-surface-600/50 hover:border-aura-400 hover:bg-aura-50/30 dark:hover:bg-aura-900/10'
                    }
                  `}
                  onClick={() => document.getElementById('license-file-input')?.click()}
                >
                  <input
                    id="license-file-input"
                    type="file"
                    accept=".lic,.json"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <DocumentArrowUpIcon className="h-10 w-10 mx-auto text-surface-400 dark:text-surface-500 mb-3" />
                  {licenseFile ? (
                    <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                      {licenseFile.name}
                    </p>
                  ) : (
                    <>
                      <p className="text-sm text-surface-600 dark:text-surface-400">
                        Drag and drop your license file here
                      </p>
                      <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                        or click to browse (.lic, .json)
                      </p>
                    </>
                  )}
                </div>
                <button
                  onClick={handleActivateFile}
                  disabled={activating || !licenseFile}
                  className="
                    w-full py-3 px-4 rounded-xl
                    bg-aura-600 hover:bg-aura-700
                    disabled:bg-surface-300 dark:disabled:bg-surface-600
                    text-white font-medium
                    transition-colors duration-200
                    flex items-center justify-center gap-2
                    disabled:cursor-not-allowed
                  "
                >
                  {activating ? (
                    <>
                      <ArrowPathIcon className="h-5 w-5 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    'Upload & Activate'
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Trial Section */}
          {showTrial && (
            <div className="pt-6 border-t border-surface-200/50 dark:border-surface-700/30">
              <div className="bg-gradient-to-r from-aura-50 to-purple-50 dark:from-aura-900/20 dark:to-purple-900/20 rounded-xl p-6 border border-aura-200/50 dark:border-aura-800/50">
                <div className="flex items-start gap-4">
                  <div className="p-2 bg-aura-100 dark:bg-aura-800/50 rounded-lg">
                    <SparklesIcon className="h-6 w-6 text-aura-600 dark:text-aura-400" />
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-surface-900 dark:text-surface-100">
                      Start 30-Day Enterprise Trial
                    </h4>
                    <p className="text-sm text-surface-600 dark:text-surface-400 mt-1">
                      No credit card required. Full Enterprise features for 30 days.
                    </p>
                    <button
                      onClick={handleStartTrial}
                      disabled={activating}
                      className="
                        mt-4 py-2 px-4 rounded-lg
                        bg-aura-600 hover:bg-aura-700
                        disabled:bg-surface-300 dark:disabled:bg-surface-600
                        text-white font-medium text-sm
                        transition-colors duration-200
                        flex items-center gap-2
                        disabled:cursor-not-allowed
                      "
                    >
                      {activating ? (
                        <>
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          Starting...
                        </>
                      ) : (
                        'Start Free Trial'
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
