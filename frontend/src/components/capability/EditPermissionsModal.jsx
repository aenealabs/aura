/**
 * EditPermissionsModal Component (ADR-066, ADR-071)
 *
 * Modal for editing agent capability permissions.
 * Allows administrators to grant/revoke tool access for agents.
 *
 * @module components/capability/EditPermissionsModal
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  XMarkIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  PlusIcon,
  TrashIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

/**
 * Tool classification tiers with colors and descriptions
 */
const TOOL_CLASSIFICATIONS = [
  {
    id: 'safe',
    label: 'Safe',
    abbrev: 'S',
    color: 'bg-olive-500',
    textColor: 'text-olive-600 dark:text-olive-400',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    description: 'Read-only operations, no side effects',
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    abbrev: 'M',
    color: 'bg-warning-500',
    textColor: 'text-warning-600 dark:text-warning-400',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    description: 'Observation tools with audit trails',
  },
  {
    id: 'dangerous',
    label: 'Dangerous',
    abbrev: 'D',
    color: 'bg-orange-500',
    textColor: 'text-orange-600 dark:text-orange-400',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    description: 'Write operations requiring approval',
  },
  {
    id: 'critical',
    label: 'Critical',
    abbrev: 'C',
    color: 'bg-critical-500',
    textColor: 'text-critical-600 dark:text-critical-400',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    description: 'High-impact operations with strict controls',
  },
];

/**
 * Available tools organized by classification
 */
const AVAILABLE_TOOLS = {
  safe: [
    { id: 'semantic_search', name: 'Semantic Search', description: 'Search code using semantic similarity' },
    { id: 'list_tools', name: 'List Tools', description: 'List available tools' },
    { id: 'get_documentation', name: 'Get Documentation', description: 'Retrieve documentation' },
    { id: 'get_agent_status', name: 'Get Agent Status', description: 'Get status of an agent' },
  ],
  monitoring: [
    { id: 'query_code_graph', name: 'Query Code Graph', description: 'Query code knowledge graph' },
    { id: 'query_audit_logs', name: 'Query Audit Logs', description: 'Query audit logs' },
    { id: 'get_vulnerability_report', name: 'Vulnerability Report', description: 'Get vulnerability scan results' },
    { id: 'analyze_code_complexity', name: 'Code Complexity', description: 'Analyze code complexity' },
  ],
  dangerous: [
    { id: 'generate_code', name: 'Generate Code', description: 'Generate new code' },
    { id: 'modify_code', name: 'Modify Code', description: 'Modify existing code' },
    { id: 'create_sandbox', name: 'Create Sandbox', description: 'Create sandbox environment' },
    { id: 'execute_tests', name: 'Execute Tests', description: 'Run test suites' },
  ],
  critical: [
    { id: 'deploy_code', name: 'Deploy Code', description: 'Deploy to environments' },
    { id: 'database_access', name: 'Database Access', description: 'Direct database access' },
    { id: 'approve_changes', name: 'Approve Changes', description: 'Approve code changes' },
    { id: 'manage_secrets', name: 'Manage Secrets', description: 'Access/modify secrets' },
  ],
};

/**
 * ToolCheckbox - Individual tool selection
 */
function ToolCheckbox({ tool, isGranted, onToggle, classification }) {
  const classConfig = TOOL_CLASSIFICATIONS.find(c => c.id === classification);

  return (
    <label className="flex items-start gap-3 p-2 rounded-lg hover:bg-surface-50 dark:hover:bg-surface-800 cursor-pointer">
      <input
        type="checkbox"
        checked={isGranted}
        onChange={() => onToggle(tool.id)}
        className="mt-1 h-4 w-4 rounded border-surface-300 text-aura-600 focus:ring-aura-500"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-surface-900 dark:text-surface-100 text-sm">
            {tool.name}
          </span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${classConfig?.bgColor} ${classConfig?.textColor}`}>
            {classConfig?.abbrev}
          </span>
        </div>
        <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
          {tool.description}
        </p>
      </div>
    </label>
  );
}

ToolCheckbox.propTypes = {
  tool: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    description: PropTypes.string,
  }).isRequired,
  isGranted: PropTypes.bool.isRequired,
  onToggle: PropTypes.func.isRequired,
  classification: PropTypes.string.isRequired,
};

/**
 * ClassificationSection - Tools grouped by classification
 */
function ClassificationSection({ classification, tools, grantedTools, onToggle, expanded, onToggleExpand }) {
  const classConfig = TOOL_CLASSIFICATIONS.find(c => c.id === classification);
  const grantedCount = tools.filter(t => grantedTools.includes(t.id)).length;

  return (
    <div className="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
      <button
        onClick={onToggleExpand}
        className="w-full flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-800 hover:bg-surface-100 dark:hover:bg-surface-700"
      >
        <div className="flex items-center gap-3">
          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold ${classConfig?.color}`}>
            {classConfig?.abbrev}
          </span>
          <div className="text-left">
            <span className="font-medium text-surface-900 dark:text-surface-100">
              {classConfig?.label}
            </span>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              {classConfig?.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-surface-600 dark:text-surface-400">
            {grantedCount}/{tools.length}
          </span>
          <svg
            className={`w-5 h-5 text-surface-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {expanded && (
        <div className="p-2 space-y-1 border-t border-surface-200 dark:border-surface-700">
          {tools.map(tool => (
            <ToolCheckbox
              key={tool.id}
              tool={tool}
              isGranted={grantedTools.includes(tool.id)}
              onToggle={onToggle}
              classification={classification}
            />
          ))}
        </div>
      )}
    </div>
  );
}

ClassificationSection.propTypes = {
  classification: PropTypes.string.isRequired,
  tools: PropTypes.array.isRequired,
  grantedTools: PropTypes.array.isRequired,
  onToggle: PropTypes.func.isRequired,
  expanded: PropTypes.bool.isRequired,
  onToggleExpand: PropTypes.func.isRequired,
};

/**
 * EditPermissionsModal - Main component
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is visible
 * @param {Function} props.onClose - Callback to close the modal
 * @param {Object} props.agent - Agent being edited
 * @param {Function} props.onSave - Callback when permissions are saved
 */
function EditPermissionsModal({ isOpen, onClose, agent, onSave }) {
  const [grantedTools, setGrantedTools] = useState([]);
  const [expandedSections, setExpandedSections] = useState(['safe', 'monitoring']);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Initialize granted tools from agent data
  useEffect(() => {
    if (agent?.capabilities) {
      const toolIds = agent.capabilities.map(c => c.tool_id || c.id);
      setGrantedTools(toolIds);
    } else {
      // Default capabilities based on agent type
      const defaults = getDefaultCapabilities(agent?.agent_type);
      setGrantedTools(defaults);
    }
    setHasChanges(false);
  }, [agent]);

  const getDefaultCapabilities = (agentType) => {
    switch (agentType) {
      case 'coder':
        return ['semantic_search', 'get_documentation', 'generate_code', 'modify_code'];
      case 'reviewer':
        return ['semantic_search', 'query_code_graph', 'analyze_code_complexity'];
      case 'validator':
        return ['semantic_search', 'execute_tests', 'get_vulnerability_report'];
      case 'patcher':
        return ['semantic_search', 'modify_code', 'deploy_code', 'database_access'];
      default:
        return ['semantic_search', 'list_tools', 'get_documentation'];
    }
  };

  const handleToggleTool = (toolId) => {
    setGrantedTools(prev => {
      const newTools = prev.includes(toolId)
        ? prev.filter(id => id !== toolId)
        : [...prev, toolId];
      setHasChanges(true);
      return newTools;
    });
  };

  const handleToggleSection = (classification) => {
    setExpandedSections(prev =>
      prev.includes(classification)
        ? prev.filter(c => c !== classification)
        : [...prev, classification]
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave?.({
        agent_id: agent?.id,
        granted_tools: grantedTools,
      });
      onClose();
    } catch (error) {
      console.error('Failed to save permissions:', error);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  const totalGranted = grantedTools.length;
  const criticalGranted = AVAILABLE_TOOLS.critical.filter(t => grantedTools.includes(t.id)).length;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 dark:bg-black/70 z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-x-4 top-[10%] mx-auto max-w-lg bg-white dark:bg-surface-900 rounded-xl shadow-2xl z-50 flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
          <div>
            <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">
              Edit Permissions
            </h2>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">
              {agent?.label || agent?.name || 'Agent'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Summary */}
        <div className="px-4 py-3 bg-surface-50 dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-surface-600 dark:text-surface-400">
              {totalGranted} tools granted
            </span>
            {criticalGranted > 0 && (
              <span className="flex items-center gap-1 text-critical-600 dark:text-critical-400">
                <ExclamationTriangleIcon className="w-4 h-4" />
                {criticalGranted} critical
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {TOOL_CLASSIFICATIONS.map(classification => (
            <ClassificationSection
              key={classification.id}
              classification={classification.id}
              tools={AVAILABLE_TOOLS[classification.id]}
              grantedTools={grantedTools}
              onToggle={handleToggleTool}
              expanded={expandedSections.includes(classification.id)}
              onToggleExpand={() => handleToggleSection(classification.id)}
            />
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-200 dark:border-surface-700 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-surface-700 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 rounded-lg hover:bg-surface-200 dark:hover:bg-surface-700"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
            className="px-4 py-2 text-sm font-medium text-white bg-aura-600 rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSaving ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </>
            ) : (
              <>
                <CheckIcon className="w-4 h-4" />
                Save Changes
              </>
            )}
          </button>
        </div>
      </div>
    </>
  );
}

EditPermissionsModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  agent: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    label: PropTypes.string,
    agent_type: PropTypes.string,
    capabilities: PropTypes.array,
  }),
  onSave: PropTypes.func,
};

export default EditPermissionsModal;
