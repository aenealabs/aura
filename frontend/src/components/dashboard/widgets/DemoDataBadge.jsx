/**
 * Demo data badge.
 *
 * Wave-4 (#163) honest fallback for widgets where the backend API
 * does not exist yet. The May 10 GTM audit's primary complaint about
 * MOCK widgets was that they were indistinguishable from live data;
 * this badge fixes that without misleading users about what is real.
 *
 * Wave 5 will replace each instance with a real API call.
 *
 * @module components/dashboard/widgets/DemoDataBadge
 */

import { BeakerIcon } from '@heroicons/react/24/outline';

/**
 * Inline badge that marks a widget as showing demo data.
 *
 * Renders an amber pill with an icon + "Demo data" label. Designed
 * to sit next to a widget header so it's visible at a glance without
 * dominating the widget chrome.
 */
export function DemoDataBadge({ className = '' }) {
  return (
    <span
      title="This widget is rendering demo data. Live API wiring is tracked in #163 wave 5."
      className={`
        inline-flex items-center gap-1
        px-2 py-0.5 rounded-full
        text-[10px] font-semibold uppercase tracking-wide
        bg-amber-100 text-amber-800
        dark:bg-amber-900/40 dark:text-amber-200
        ${className}
      `}
    >
      <BeakerIcon className="w-3 h-3" />
      Demo data
    </span>
  );
}

export default DemoDataBadge;
