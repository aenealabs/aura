/**
 * Integrity verification badge for ADR-088 Shadow Deployment Reports.
 *
 * Renders a green CheckCircle when the SHA-256 over the report's
 * canonical-JSON payload matches the envelope's content_hash, a red
 * XCircle on mismatch (tampered), and an amber InfoCircle when the
 * report is mock-data placeholder.
 */

import { memo } from 'react';
import {
  CheckBadgeIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

const STATE_STYLES = {
  verified: {
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-700',
    Icon: CheckBadgeIcon,
    label: 'Integrity verified',
  },
  tampered: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-700',
    Icon: ShieldExclamationIcon,
    label: 'Integrity FAILED — report rejected',
  },
  demo: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-700',
    Icon: InformationCircleIcon,
    label: 'Demo mode (integrity unverified)',
  },
};

const IntegrityBadge = memo(function IntegrityBadge({
  state = 'verified',
  expected,
  actual,
}) {
  const style = STATE_STYLES[state] || STATE_STYLES.tampered;
  const Icon = style.Icon;
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 ${style.bg} ${style.border}`}
      role="status"
      aria-live="polite"
    >
      <Icon className={`h-4 w-4 ${style.text}`} aria-hidden="true" />
      <span className={`text-sm font-medium ${style.text}`}>{style.label}</span>
      {state === 'tampered' && expected && actual && (
        <span className="ml-2 font-mono text-xs text-red-600" title="expected vs actual hash">
          {expected.slice(0, 8)}… ≠ {actual.slice(0, 8)}…
        </span>
      )}
    </div>
  );
});

export default IntegrityBadge;
