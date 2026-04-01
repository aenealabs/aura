/**
 * Principles Tab Component
 *
 * Displays Constitutional AI principles with:
 * - Category filter
 * - Severity filter
 * - Principle cards with violation metrics
 * - Category grouping
 */

import { memo, useState } from 'react';
import {
  ScaleIcon,
  ShieldExclamationIcon,
  CheckCircleIcon,
  FunnelIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { formatCategory } from '../../services/trustCenterApi';

// Category options
const CATEGORIES = [
  { value: null, label: 'All Categories' },
  { value: 'safety', label: 'Safety' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'transparency', label: 'Transparency' },
  { value: 'helpfulness', label: 'Helpfulness' },
  { value: 'anti_sycophancy', label: 'Anti-Sycophancy' },
  { value: 'code_quality', label: 'Code Quality' },
  { value: 'meta', label: 'Meta' },
];

// Severity options
const SEVERITIES = [
  { value: null, label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

/**
 * Filter Bar Component
 */
const FilterBar = memo(function FilterBar({ filter, setFilter }) {
  return (
    <div className="flex flex-wrap items-center gap-4 p-4 rounded-xl glass-card-subtle">
      <div className="flex items-center gap-2 text-surface-500 dark:text-surface-400">
        <FunnelIcon className="w-4 h-4" />
        <span className="text-sm font-medium">Filters</span>
      </div>

      {/* Category Filter */}
      <select
        value={filter.category || ''}
        onChange={(e) => setFilter({ ...filter, category: e.target.value || null })}
        className="
          px-3 py-2 rounded-lg text-sm
          bg-white dark:bg-surface-700
          border border-surface-200 dark:border-surface-600
          text-surface-900 dark:text-surface-100
          focus:outline-none focus:ring-2 focus:ring-aura-500
        "
      >
        {CATEGORIES.map((cat) => (
          <option key={cat.value || 'all'} value={cat.value || ''}>
            {cat.label}
          </option>
        ))}
      </select>

      {/* Severity Filter */}
      <select
        value={filter.severity || ''}
        onChange={(e) => setFilter({ ...filter, severity: e.target.value || null })}
        className="
          px-3 py-2 rounded-lg text-sm
          bg-white dark:bg-surface-700
          border border-surface-200 dark:border-surface-600
          text-surface-900 dark:text-surface-100
          focus:outline-none focus:ring-2 focus:ring-aura-500
        "
      >
        {SEVERITIES.map((sev) => (
          <option key={sev.value || 'all'} value={sev.value || ''}>
            {sev.label}
          </option>
        ))}
      </select>
    </div>
  );
});

/**
 * Severity Badge Component
 */
const SeverityBadge = memo(function SeverityBadge({ severity }) {
  const colorClasses = {
    critical: 'bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400',
    high: 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-400',
    medium: 'bg-aura-100 text-aura-700 dark:bg-aura-900/30 dark:text-aura-400',
    low: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
  };

  return (
    <span className={`
      inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium uppercase
      ${colorClasses[severity?.toLowerCase()] || colorClasses.low}
    `}>
      {severity}
    </span>
  );
});

/**
 * Principle Card Component
 */
const PrincipleCard = memo(function PrincipleCard({ principle }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="glass-card p-4 transition-all duration-200 hover:shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <ScaleIcon className={`w-5 h-5 flex-shrink-0 ${
              principle.enabled
                ? 'text-aura-500 dark:text-aura-400'
                : 'text-surface-400'
            }`} />
            <h4 className="font-semibold text-surface-900 dark:text-surface-100 truncate">
              {principle.name}
            </h4>
          </div>

          {/* Badges */}
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <SeverityBadge severity={principle.severity} />
            <span className="text-xs text-surface-500 dark:text-surface-400">
              {formatCategory(principle.category)}
            </span>
            {principle.enabled ? (
              <span className="inline-flex items-center gap-1 text-xs text-olive-600 dark:text-olive-400">
                <CheckCircleIcon className="w-3 h-3" />
                Active
              </span>
            ) : (
              <span className="text-xs text-surface-400">Disabled</span>
            )}
          </div>

          {/* Description */}
          <p className={`text-sm text-surface-600 dark:text-surface-400 ${!isExpanded ? 'line-clamp-2' : ''}`}>
            {principle.description}
          </p>

          {/* Expand/Collapse */}
          {principle.description?.length > 100 && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-2 text-xs text-aura-600 dark:text-aura-400 hover:underline"
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}

          {/* Domain Tags */}
          {principle.domain_tags?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-3">
              {principle.domain_tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-0.5 text-xs rounded-full bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Violation Stats */}
        {principle.violation_count_24h !== undefined && principle.violation_count_24h > 0 && (
          <div className="flex-shrink-0 text-right">
            <div className="flex items-center gap-1 text-warning-600 dark:text-warning-400">
              <ShieldExclamationIcon className="w-4 h-4" />
              <span className="text-lg font-bold">{principle.violation_count_24h}</span>
            </div>
            <span className="text-xs text-surface-500 dark:text-surface-400">
              violations (24h)
            </span>
          </div>
        )}
      </div>
    </div>
  );
});

/**
 * Category Section Component
 */
const CategorySection = memo(function CategorySection({ category, principles }) {
  const [isExpanded, setIsExpanded] = useState(true);

  const criticalCount = principles.filter(p => p.severity === 'critical').length;

  return (
    <div className="mb-6">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="
          flex items-center gap-2 w-full text-left mb-3
          group
        "
      >
        {isExpanded ? (
          <ChevronDownIcon className="w-5 h-5 text-surface-400" />
        ) : (
          <ChevronRightIcon className="w-5 h-5 text-surface-400" />
        )}
        <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 group-hover:text-aura-600 dark:group-hover:text-aura-400">
          {formatCategory(category)}
        </h3>
        <span className="text-sm text-surface-500 dark:text-surface-400">
          ({principles.length} principles)
        </span>
        {criticalCount > 0 && (
          <span className="px-2 py-0.5 text-xs rounded-full bg-critical-100 text-critical-700 dark:bg-critical-900/30 dark:text-critical-400">
            {criticalCount} critical
          </span>
        )}
      </button>

      {isExpanded && (
        <div className={`
          grid gap-4 md:grid-cols-2 lg:grid-cols-3
          ${principles.length >= 6 ? 'max-h-[480px] overflow-y-auto pr-2 scrollbar-thin' : ''}
        `}>
          {principles.map((principle) => (
            <PrincipleCard key={principle.id} principle={principle} />
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * Main Principles Tab Component
 */
export default function PrinciplesTab({
  principles,
  principlesByCategory,
  criticalPrinciples,
  filter,
  setFilter,
  loading,
}) {
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-16 rounded-xl" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="skeleton h-40 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  // If filtering, show flat list
  if (filter.category || filter.severity) {
    return (
      <div className="space-y-6">
        <FilterBar filter={filter} setFilter={setFilter} />

        <div className="text-sm text-surface-500 dark:text-surface-400">
          Showing {principles.length} principles
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {principles.map((principle) => (
            <PrincipleCard key={principle.id} principle={principle} />
          ))}
        </div>

        {principles.length === 0 && (
          <div className="text-center py-12 text-surface-500 dark:text-surface-400">
            No principles match the selected filters.
          </div>
        )}
      </div>
    );
  }

  // Show grouped by category
  const categories = Object.keys(principlesByCategory).sort();

  return (
    <div className="space-y-6">
      <FilterBar filter={filter} setFilter={setFilter} />

      {/* Summary */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-surface-600 dark:text-surface-400">
          {principles.length} total principles
        </span>
        {criticalPrinciples.length > 0 && (
          <span className="text-critical-600 dark:text-critical-400">
            {criticalPrinciples.length} critical
          </span>
        )}
      </div>

      {/* Category Sections */}
      {categories.map((category) => (
        <CategorySection
          key={category}
          category={category}
          principles={principlesByCategory[category]}
        />
      ))}
    </div>
  );
}
