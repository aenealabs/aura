/**
 * API Inspector Drawer Component
 *
 * Slide-out drawer that displays captured API requests and responses
 * for debugging purposes.
 */

import { useState, useMemo } from 'react';
import {
  XMarkIcon,
  MagnifyingGlassIcon,
  TrashIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import { useDeveloperMode } from '../../context/DeveloperModeContext';

export default function APIInspectorDrawer() {
  const {
    enabled,
    apiInspector,
    apiRequests,
    clearApiRequests,
    toggleApiInspector,
  } = useDeveloperMode();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [activeTab, setActiveTab] = useState('request');

  // Filter requests based on search
  const filteredRequests = useMemo(() => {
    if (!searchQuery) return apiRequests;
    const query = searchQuery.toLowerCase();
    return apiRequests.filter(
      (req) =>
        req.url?.toLowerCase().includes(query) ||
        req.method?.toLowerCase().includes(query) ||
        String(req.status).includes(query)
    );
  }, [apiRequests, searchQuery]);

  if (!enabled || !apiInspector.enabled) {
    return null;
  }

  const handleCopyToClipboard = (data) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
  };

  return (
    <div className="fixed top-0 right-0 bottom-0 w-[480px] z-50 bg-white/95 dark:bg-surface-900/95 backdrop-blur-xl border-l border-surface-200 dark:border-surface-700 shadow-2xl flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-surface-200 dark:border-surface-700 bg-surface-50/80 dark:bg-surface-800/80">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
            API Inspector
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={clearApiRequests}
              className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
              title="Clear all requests"
            >
              <TrashIcon className="h-4 w-4 text-surface-500" />
            </button>
            <button
              onClick={toggleApiInspector}
              className="p-2 hover:bg-surface-100 dark:hover:bg-surface-700 rounded-lg transition-colors"
            >
              <XMarkIcon className="h-4 w-4 text-surface-500" />
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-surface-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter requests..."
            className="w-full pl-9 pr-4 py-2 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-600 rounded-lg text-sm focus:ring-2 focus:ring-aura-500 focus:border-aura-500"
          />
        </div>
      </div>

      {/* Request List */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Request List */}
        <div className={`${selectedRequest ? 'w-1/2' : 'w-full'} border-r border-surface-200 dark:border-surface-700 overflow-y-auto`}>
          {filteredRequests.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-surface-500 dark:text-surface-400">
              <ClockIcon className="h-12 w-12 mb-3 opacity-50" />
              <p className="text-sm">No requests captured yet</p>
              <p className="text-xs mt-1">API calls will appear here</p>
            </div>
          ) : (
            <div className="divide-y divide-surface-100 dark:divide-surface-800">
              {filteredRequests.map((request) => (
                <RequestListItem
                  key={request.id}
                  request={request}
                  isSelected={selectedRequest?.id === request.id}
                  onSelect={() => setSelectedRequest(request)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right Panel - Request Detail */}
        {selectedRequest && (
          <div className="w-1/2 flex flex-col overflow-hidden">
            {/* Detail Header */}
            <div className="flex-shrink-0 px-4 py-3 border-b border-surface-200 dark:border-surface-700 bg-surface-50/50 dark:bg-surface-800/50">
              <div className="flex items-center justify-between">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${getMethodColor(selectedRequest.method)}`}>
                  {selectedRequest.method}
                </span>
                <button
                  onClick={() => setSelectedRequest(null)}
                  className="p-1 hover:bg-surface-100 dark:hover:bg-surface-700 rounded"
                >
                  <XMarkIcon className="h-4 w-4 text-surface-400" />
                </button>
              </div>
              <p className="text-xs text-surface-600 dark:text-surface-400 mt-1 truncate font-mono">
                {selectedRequest.url}
              </p>
            </div>

            {/* Tabs */}
            <div className="flex-shrink-0 flex border-b border-surface-200 dark:border-surface-700">
              {['request', 'response', 'headers'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`
                    flex-1 px-4 py-2 text-sm font-medium capitalize
                    border-b-2 transition-colors
                    ${activeTab === tab
                      ? 'border-aura-500 text-aura-600 dark:text-aura-400'
                      : 'border-transparent text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
                    }
                  `}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {activeTab === 'request' && (
                <JsonViewer
                  data={selectedRequest.requestBody}
                  onCopy={() => handleCopyToClipboard(selectedRequest.requestBody)}
                />
              )}
              {activeTab === 'response' && (
                <JsonViewer
                  data={selectedRequest.responseBody}
                  onCopy={() => handleCopyToClipboard(selectedRequest.responseBody)}
                />
              )}
              {activeTab === 'headers' && (
                <div className="space-y-4">
                  <div>
                    <h4 className="text-xs font-semibold text-surface-500 uppercase tracking-wide mb-2">
                      Request Headers
                    </h4>
                    <HeadersViewer headers={selectedRequest.requestHeaders} />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-surface-500 uppercase tracking-wide mb-2">
                      Response Headers
                    </h4>
                    <HeadersViewer headers={selectedRequest.responseHeaders} />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div className="flex-shrink-0 px-4 py-2 border-t border-surface-200 dark:border-surface-700 bg-surface-50/80 dark:bg-surface-800/80">
        <div className="flex items-center justify-between text-xs text-surface-500">
          <span>{apiRequests.length} requests captured</span>
          <span>Max: {apiInspector.maxRequests}</span>
        </div>
      </div>
    </div>
  );
}

function RequestListItem({ request, isSelected, onSelect }) {
  const isSuccess = request.status >= 200 && request.status < 300;
  const isError = request.status >= 400;

  return (
    <button
      onClick={onSelect}
      className={`
        w-full px-4 py-3 text-left transition-colors
        ${isSelected
          ? 'bg-aura-50 dark:bg-aura-900/20'
          : 'hover:bg-surface-50 dark:hover:bg-surface-800/50'
        }
      `}
    >
      <div className="flex items-center gap-3">
        {/* Status Icon */}
        {isSuccess ? (
          <CheckCircleIcon className="h-4 w-4 text-olive-500 flex-shrink-0" />
        ) : isError ? (
          <ExclamationCircleIcon className="h-4 w-4 text-critical-500 flex-shrink-0" />
        ) : (
          <ClockIcon className="h-4 w-4 text-warning-500 flex-shrink-0" />
        )}

        {/* Method Badge */}
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium flex-shrink-0 ${getMethodColor(request.method)}`}>
          {request.method}
        </span>

        {/* URL */}
        <span className="flex-1 text-sm text-surface-700 dark:text-surface-300 truncate font-mono">
          {getPathFromUrl(request.url)}
        </span>

        {/* Status & Duration */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs font-medium ${isSuccess ? 'text-olive-600' : isError ? 'text-critical-600' : 'text-surface-500'}`}>
            {request.status}
          </span>
          <span className="text-xs text-surface-400">
            {request.duration}ms
          </span>
        </div>

        <ChevronRightIcon className="h-4 w-4 text-surface-300 flex-shrink-0" />
      </div>

      <p className="text-xs text-surface-400 mt-1">
        {new Date(request.timestamp).toLocaleTimeString()}
      </p>
    </button>
  );
}

function JsonViewer({ data, onCopy }) {
  // Note: expanded state reserved for future collapsible JSON tree view
  const [_expanded, _setExpanded] = useState(true);

  if (!data) {
    return (
      <div className="text-sm text-surface-500 italic">No data</div>
    );
  }

  const jsonString = JSON.stringify(data, null, 2);

  return (
    <div className="relative">
      <button
        onClick={onCopy}
        className="absolute top-2 right-2 p-1.5 bg-surface-100 dark:bg-surface-700 hover:bg-surface-200 dark:hover:bg-surface-600 rounded transition-colors"
        title="Copy to clipboard"
      >
        <DocumentDuplicateIcon className="h-4 w-4 text-surface-500" />
      </button>
      <pre className="text-xs font-mono text-surface-700 dark:text-surface-300 bg-surface-50 dark:bg-surface-800 rounded-lg p-4 overflow-x-auto">
        {jsonString}
      </pre>
    </div>
  );
}

function HeadersViewer({ headers }) {
  if (!headers || Object.keys(headers).length === 0) {
    return <div className="text-sm text-surface-500 italic">No headers</div>;
  }

  return (
    <div className="bg-surface-50 dark:bg-surface-800 rounded-lg p-3 space-y-2">
      {Object.entries(headers).map(([key, value]) => (
        <div key={key} className="flex gap-2 text-xs">
          <span className="font-medium text-surface-600 dark:text-surface-400">{key}:</span>
          <span className="text-surface-700 dark:text-surface-300 font-mono break-all">{value}</span>
        </div>
      ))}
    </div>
  );
}

function getMethodColor(method) {
  switch (method?.toUpperCase()) {
    case 'GET':
      return 'bg-olive-100 text-olive-700 dark:bg-olive-900/30 dark:text-olive-400';
    case 'POST':
      return 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400';
    case 'PUT':
    case 'PATCH':
      return 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400';
    case 'DELETE':
      return 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400';
    default:
      return 'bg-surface-100 text-surface-700 dark:bg-surface-700 dark:text-surface-300';
  }
}

function getPathFromUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.pathname + parsed.search;
  } catch {
    return url;
  }
}
