/**
 * Edge Case Spotlight for ADR-088 Shadow Deployment Reports.
 *
 * Surfaces the 10 most-improved + 10 most-degraded cases relative
 * to the incumbent (per §Stage 7). Operators scan this list for
 * cherry-picking signals before approving a model swap.
 */

import { memo } from 'react';
import {
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusCircleIcon,
} from '@heroicons/react/24/outline';

const DELTA_STYLES = {
  improved: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    Icon: ArrowTrendingUpIcon,
    label: 'improved',
  },
  regressed: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    Icon: ArrowTrendingDownIcon,
    label: 'regressed',
  },
  tied: {
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    Icon: MinusCircleIcon,
    label: 'tied',
  },
};

const EdgeCaseSpotlight = memo(function EdgeCaseSpotlight({ cases = [] }) {
  if (!cases.length) {
    return (
      <p className="text-sm text-slate-500">
        No edge cases surfaced — candidate matched incumbent on every case.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-slate-200" aria-label="Edge case spotlight">
      {cases.map((ec) => {
        const style = DELTA_STYLES[ec.delta_label] || DELTA_STYLES.tied;
        const Icon = style.Icon;
        return (
          <li key={ec.case_id} className="flex items-start gap-3 py-3">
            <span
              className={`inline-flex h-7 w-7 items-center justify-center rounded-full ${style.bg}`}
              aria-hidden="true"
            >
              <Icon className={`h-4 w-4 ${style.text}`} />
            </span>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <code className="font-mono text-sm text-slate-800">
                  {ec.case_id}
                </code>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
                >
                  {style.label}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">{ec.description}</p>
              <div className="mt-1 flex gap-3 text-xs text-slate-500">
                <span>candidate: {ec.candidate_passed ? 'pass' : 'fail'}</span>
                <span>incumbent: {ec.incumbent_passed ? 'pass' : 'fail'}</span>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
});

export default EdgeCaseSpotlight;
