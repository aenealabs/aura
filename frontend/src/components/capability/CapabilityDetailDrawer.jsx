/**
 * CapabilityDetailDrawer Component (ADR-071)
 *
 * Side panel showing detailed information about selected graph nodes.
 * Displays agent capabilities, escalation paths, and related analysis.
 *
 * @module components/capability/CapabilityDetailDrawer
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  XMarkIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ChevronRightIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  LinkIcon,
  ClockIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline';
import EditPermissionsModal from './EditPermissionsModal';

/**
 * Classification configuration
 */
const CLASSIFICATION_CONFIG = {
  safe: {
    label: 'SAFE',
    color: 'text-olive-600 dark:text-olive-400',
    bgColor: 'bg-olive-100 dark:bg-olive-900/30',
    icon: ShieldCheckIcon,
  },
  monitoring: {
    label: 'MONITORING',
    color: 'text-warning-600 dark:text-warning-400',
    bgColor: 'bg-warning-100 dark:bg-warning-900/30',
    icon: InformationCircleIcon,
  },
  dangerous: {
    label: 'DANGEROUS',
    color: 'text-orange-600 dark:text-orange-400',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    icon: ExclamationTriangleIcon,
  },
  critical: {
    label: 'CRITICAL',
    color: 'text-critical-600 dark:text-critical-400',
    bgColor: 'bg-critical-100 dark:bg-critical-900/30',
    icon: ShieldExclamationIcon,
  },
};

/**
 * DetailSection - Collapsible section within the drawer
 */
function DetailSection({ title, icon: Icon, children, badge }) {
  return (
    <div className="border-b border-surface-200 dark:border-surface-700 pb-4 mb-4 last:border-b-0 last:pb-0 last:mb-0">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4 text-surface-500" />}
          <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300">
            {title}
          </h4>
        </div>
        {badge && (
          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400">
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

DetailSection.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.elementType,
  children: PropTypes.node.isRequired,
  badge: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

/**
 * CapabilityItem - Individual capability display
 */
function CapabilityItem({ capability, onClick }) {
  const config = CLASSIFICATION_CONFIG[capability.classification] || CLASSIFICATION_CONFIG.safe;
  const Icon = config.icon;

  return (
    <button
      onClick={() => onClick?.(capability)}
      className={`
        w-full flex items-center gap-3 p-3 rounded-lg text-left
        ${config.bgColor} hover:opacity-90 transition-opacity
      `}
    >
      <Icon className={`w-5 h-5 flex-shrink-0 ${config.color}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-surface-900 dark:text-surface-100 truncate">
            {capability.name || capability.tool_id}
          </span>
          <span className={`text-xs font-medium ${config.color}`}>
            {config.label}
          </span>
        </div>
        {capability.description && (
          <p className="text-xs text-surface-600 dark:text-surface-400 mt-0.5 truncate">
            {capability.description}
          </p>
        )}
      </div>
      <ChevronRightIcon className="w-4 h-4 text-surface-400 flex-shrink-0" />
    </button>
  );
}

CapabilityItem.propTypes = {
  capability: PropTypes.shape({
    tool_id: PropTypes.string.isRequired,
    name: PropTypes.string,
    description: PropTypes.string,
    classification: PropTypes.string,
  }).isRequired,
  onClick: PropTypes.func,
};

/**
 * EscalationPathItem - Individual escalation path display
 */
function EscalationPathItem({ path }) {
  const riskLevel = path.risk_score >= 0.8 ? 'critical' : path.risk_score >= 0.5 ? 'high' : 'medium';
  const riskConfig = {
    critical: { color: 'text-critical-600', bg: 'bg-critical-100 dark:bg-critical-900/30' },
    high: { color: 'text-warning-600', bg: 'bg-warning-100 dark:bg-warning-900/30' },
    medium: { color: 'text-aura-600', bg: 'bg-aura-100 dark:bg-aura-900/30' },
  };

  return (
    <div className={`p-3 rounded-lg ${riskConfig[riskLevel].bg}`}>
      <div className="flex items-center justify-between mb-2">
        <span className={`text-sm font-medium ${riskConfig[riskLevel].color}`}>
          Risk Score: {Math.round(path.risk_score * 100)}%
        </span>
        <span className="text-xs text-surface-500">
          {path.steps?.length || 0} steps
        </span>
      </div>
      {path.steps && (
        <div className="flex items-center gap-1 flex-wrap">
          {path.steps.map((step, i) => (
            <React.Fragment key={i}>
              <span className="text-xs px-2 py-0.5 rounded bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300">
                {step}
              </span>
              {i < path.steps.length - 1 && (
                <ChevronRightIcon className="w-3 h-3 text-surface-400" />
              )}
            </React.Fragment>
          ))}
        </div>
      )}
      {path.description && (
        <p className="text-xs text-surface-600 dark:text-surface-400 mt-2">
          {path.description}
        </p>
      )}
    </div>
  );
}

EscalationPathItem.propTypes = {
  path: PropTypes.shape({
    risk_score: PropTypes.number.isRequired,
    steps: PropTypes.arrayOf(PropTypes.string),
    description: PropTypes.string,
  }).isRequired,
};

/**
 * InheritanceTree - Visual inheritance hierarchy
 */
function InheritanceTree({ inheritance }) {
  if (!inheritance || inheritance.length === 0) {
    return (
      <p className="text-sm text-surface-500 dark:text-surface-400 italic">
        No inheritance chain
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {inheritance.map((item, i) => (
        <div
          key={i}
          className="flex items-center gap-2"
          style={{ paddingLeft: `${i * 16}px` }}
        >
          {i > 0 && (
            <span className="text-surface-400">└</span>
          )}
          <span className="text-sm text-surface-700 dark:text-surface-300">
            {item.name || item}
          </span>
          {item.type && (
            <span className="text-xs text-surface-500 dark:text-surface-400">
              ({item.type})
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

InheritanceTree.propTypes = {
  inheritance: PropTypes.array,
};

/**
 * CapabilityDetailDrawer - Main component
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the drawer is visible
 * @param {Function} props.onClose - Callback to close the drawer
 * @param {Object} [props.selectedNode] - Currently selected node data
 * @param {Function} [props.fetchDetails] - Function to fetch additional details
 * @param {Function} [props.onCapabilityClick] - Callback when a capability is clicked
 * @param {string} [props.className] - Additional CSS classes
 */
function CapabilityDetailDrawer({
  isOpen,
  onClose,
  selectedNode,
  fetchDetails,
  onCapabilityClick,
  onPermissionsUpdate,
  className = '',
}) {
  const [details, setDetails] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // Fetch details when node changes
  useEffect(() => {
    if (!selectedNode || !fetchDetails) {
      setDetails(null);
      return;
    }

    const loadDetails = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await fetchDetails(selectedNode.id);
        setDetails(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    loadDetails();
  }, [selectedNode, fetchDetails]);

  if (!isOpen) return null;

  const nodeData = details || selectedNode || {};
  const isAgent = nodeData.type === 'agent';

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40"
        onClick={onClose}
      />

      {/* Drawer - compact height to avoid chat assistant overlap */}
      <div
        className={`
          fixed top-0 right-0 w-[360px] max-w-full
          bg-white dark:bg-surface-900
          border-l border-surface-200 dark:border-surface-700
          shadow-xl z-50 overflow-hidden flex flex-col
          max-h-[400px]
          ${className}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            {isAgent ? (
              <div className="p-2 rounded-lg bg-aura-100 dark:bg-aura-900/30">
                <UserCircleIcon className="w-5 h-5 text-aura-600 dark:text-aura-400" />
              </div>
            ) : (
              <div className={`p-2 rounded-lg ${CLASSIFICATION_CONFIG[nodeData.classification]?.bgColor || 'bg-surface-100 dark:bg-surface-800'}`}>
                {(() => {
                  const config = CLASSIFICATION_CONFIG[nodeData.classification];
                  const Icon = config?.icon || ShieldCheckIcon;
                  return <Icon className={`w-5 h-5 ${config?.color || 'text-surface-500'}`} />;
                })()}
              </div>
            )}
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-surface-100">
                {nodeData.label || nodeData.name || nodeData.id}
              </h2>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                {isAgent ? nodeData.agent_type || 'Agent' : nodeData.classification?.toUpperCase() || 'Tool'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-surface-500 hover:text-surface-700
                       dark:hover:text-surface-300 hover:bg-surface-100
                       dark:hover:bg-surface-800 transition-colors"
            aria-label="Close drawer"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <ArrowPathIcon className="w-6 h-6 animate-spin text-aura-500" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-critical-500">
              <ExclamationTriangleIcon className="w-8 h-8 mx-auto mb-2" />
              <p className="text-sm">{error}</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Risk indicator for agents */}
              {isAgent && nodeData.has_escalation_risk && (
                <div className="p-3 rounded-lg bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800">
                  <div className="flex items-center gap-2">
                    <ShieldExclamationIcon className="w-5 h-5 text-critical-500" />
                    <span className="font-medium text-critical-700 dark:text-critical-300">
                      Escalation Risk Detected
                    </span>
                  </div>
                  <p className="text-xs text-critical-600 dark:text-critical-400 mt-1">
                    This agent has capabilities that could allow privilege escalation.
                  </p>
                </div>
              )}

              {/* Description */}
              {nodeData.description && (
                <DetailSection title="Description" icon={DocumentTextIcon}>
                  <p className="text-sm text-surface-600 dark:text-surface-400">
                    {nodeData.description}
                  </p>
                </DetailSection>
              )}

              {/* Capabilities (for agents) */}
              {isAgent && nodeData.capabilities && (
                <DetailSection
                  title="Capabilities"
                  icon={ShieldCheckIcon}
                  badge={nodeData.capabilities.length}
                >
                  <div className="space-y-2">
                    {nodeData.capabilities.map((cap, i) => (
                      <CapabilityItem
                        key={cap.tool_id || i}
                        capability={cap}
                        onClick={onCapabilityClick}
                      />
                    ))}
                  </div>
                </DetailSection>
              )}

              {/* Escalation paths (for agents) */}
              {isAgent && nodeData.escalation_paths && nodeData.escalation_paths.length > 0 && (
                <DetailSection
                  title="Escalation Paths"
                  icon={ExclamationTriangleIcon}
                  badge={nodeData.escalation_paths.length}
                >
                  <div className="space-y-2">
                    {nodeData.escalation_paths.map((path, i) => (
                      <EscalationPathItem key={i} path={path} />
                    ))}
                  </div>
                </DetailSection>
              )}

              {/* Inheritance tree */}
              {nodeData.inheritance && (
                <DetailSection title="Inheritance" icon={LinkIcon}>
                  <InheritanceTree inheritance={nodeData.inheritance} />
                </DetailSection>
              )}

              {/* Metadata */}
              <DetailSection title="Metadata" icon={InformationCircleIcon}>
                <div className="space-y-2 text-sm">
                  {nodeData.id && (
                    <div className="flex justify-between">
                      <span className="text-surface-500 dark:text-surface-400">ID</span>
                      <span className="text-surface-700 dark:text-surface-300 font-mono text-xs">
                        {nodeData.id}
                      </span>
                    </div>
                  )}
                  {nodeData.type && (
                    <div className="flex justify-between">
                      <span className="text-surface-500 dark:text-surface-400">Type</span>
                      <span className="text-surface-700 dark:text-surface-300">
                        {nodeData.type}
                      </span>
                    </div>
                  )}
                  {nodeData.capabilities_count !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-surface-500 dark:text-surface-400">
                        Capability Count
                      </span>
                      <span className="text-surface-700 dark:text-surface-300">
                        {nodeData.capabilities_count}
                      </span>
                    </div>
                  )}
                  {nodeData.last_synced && (
                    <div className="flex justify-between">
                      <span className="text-surface-500 dark:text-surface-400">
                        Last Synced
                      </span>
                      <span className="text-surface-700 dark:text-surface-300">
                        {new Date(nodeData.last_synced).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
              </DetailSection>
            </div>
          )}
        </div>

        {/* Footer actions */}
        {selectedNode && nodeData.type === 'agent' && (
          <div className="p-4 border-t border-surface-200 dark:border-surface-700">
            <button
              onClick={() => setIsEditModalOpen(true)}
              className="w-full px-4 py-2 text-sm font-medium
                         bg-aura-600 text-white
                         rounded-lg hover:bg-aura-700
                         transition-colors"
            >
              Edit Permissions
            </button>
          </div>
        )}
      </div>

      {/* Edit Permissions Modal */}
      <EditPermissionsModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        agent={nodeData}
        onSave={async (data) => {
          await onPermissionsUpdate?.(data);
          // Refresh details after save
          if (fetchDetails && selectedNode) {
            const updated = await fetchDetails(selectedNode.id);
            setDetails(updated);
          }
        }}
      />
    </>
  );
}

CapabilityDetailDrawer.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  selectedNode: PropTypes.shape({
    id: PropTypes.string,
    type: PropTypes.string,
    label: PropTypes.string,
    name: PropTypes.string,
    classification: PropTypes.string,
    agent_type: PropTypes.string,
    description: PropTypes.string,
    capabilities: PropTypes.array,
    capabilities_count: PropTypes.number,
    escalation_paths: PropTypes.array,
    inheritance: PropTypes.array,
    has_escalation_risk: PropTypes.bool,
    last_synced: PropTypes.string,
  }),
  fetchDetails: PropTypes.func,
  onCapabilityClick: PropTypes.func,
  onPermissionsUpdate: PropTypes.func,
  className: PropTypes.string,
};

export default CapabilityDetailDrawer;
