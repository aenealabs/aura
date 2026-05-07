/**
 * Shadow Deployment Report panel for ADR-088 HITL approval.
 *
 * Renders all 8 sections from §Stage 7 of the ADR:
 *   1. Executive summary  (utility delta, decision, generated_at)
 *   2. Floor validation
 *   3. 6-axis radar chart with incumbent overlay
 *   4. Cost analysis (candidate vs incumbent monthly estimate)
 *   5. Risk assessment (warnings from provenance + sandbox)
 *   6. Provenance chain
 *   7. Edge case spotlight (improved + regressed)
 *   8. Human spot-check results (with disagreement flag)
 *
 * Plus the Integrity Badge that gates whether the report is shown
 * at all — a tampered report renders a hard error in place of the
 * sections.
 */

import { memo, useMemo } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ChatBubbleBottomCenterTextIcon,
  CurrencyDollarIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

import AxisRadarChart from './AxisRadarChart';
import EdgeCaseSpotlight from './EdgeCaseSpotlight';
import IntegrityBadge from './IntegrityBadge';

function formatCurrency(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '$—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

function formatPercent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

const ShadowReportPanel = memo(function ShadowReportPanel({
  report,
  integrityState = 'demo',
  integrityVerification = null,
  onApprove,
  onReject,
  isSubmitting = false,
}) {
  const utilityDelta = useMemo(() => {
    if (
      typeof report?.overall_utility !== 'number' ||
      typeof report?.incumbent_utility !== 'number'
    ) {
      return null;
    }
    return report.overall_utility - report.incumbent_utility;
  }, [report]);

  if (integrityState === 'tampered') {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <div className="flex items-start gap-3">
          <XCircleIcon className="mt-0.5 h-6 w-6 text-red-600" aria-hidden="true" />
          <div>
            <h2 className="text-base font-semibold text-red-800">
              Report rejected — integrity hash mismatch
            </h2>
            <p className="mt-1 text-sm text-red-700">
              The Shadow Deployment Report's content hash does not match the
              expected envelope hash. The report has been modified after
              sealing and cannot be presented for approval. Re-run the
              evaluation pipeline to generate a fresh report.
            </p>
            {integrityVerification && (
              <pre className="mt-3 overflow-x-auto rounded bg-red-100 p-2 font-mono text-xs text-red-800">
                expected: {integrityVerification.expected}
                {'\n'}
                actual:   {integrityVerification.actual}
              </pre>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
        Select a report from the queue to view details.
      </div>
    );
  }

  return (
    <article
      className="space-y-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      aria-labelledby="shadow-report-heading"
    >
      {/* --- Header / Executive summary --- */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            id="shadow-report-heading"
            className="text-2xl font-semibold text-slate-900"
          >
            {report.candidate_display_name}
          </h2>
          <p className="mt-1 font-mono text-xs text-slate-500">
            {report.candidate_id}
          </p>
          <p className="mt-3 text-sm text-slate-600">
            Pipeline decision:{' '}
            <span className="font-medium text-slate-900">
              {report.pipeline_decision}
            </span>
            {' · '}
            Generated{' '}
            {report.generated_at
              ? new Date(report.generated_at).toLocaleString()
              : 'unknown'}
          </p>
        </div>
        <IntegrityBadge
          state={integrityState}
          expected={integrityVerification?.expected}
          actual={integrityVerification?.actual}
        />
      </header>

      {/* --- Utility delta callout --- */}
      <section
        aria-label="Utility delta vs incumbent"
        className="grid grid-cols-1 gap-4 sm:grid-cols-3"
      >
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Candidate utility
          </p>
          <p className="mt-1 text-2xl font-semibold text-slate-900">
            {report.overall_utility?.toFixed(3) ?? '—'}
          </p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Incumbent utility
          </p>
          <p className="mt-1 text-2xl font-semibold text-slate-900">
            {report.incumbent_utility != null
              ? report.incumbent_utility.toFixed(3)
              : '—'}
          </p>
        </div>
        <div
          className={`rounded-md border p-4 ${
            utilityDelta == null
              ? 'border-slate-200 bg-slate-50'
              : utilityDelta > 0
                ? 'border-emerald-200 bg-emerald-50'
                : 'border-red-200 bg-red-50'
          }`}
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Δ utility
          </p>
          <p
            className={`mt-1 text-2xl font-semibold ${
              utilityDelta == null
                ? 'text-slate-900'
                : utilityDelta > 0
                  ? 'text-emerald-700'
                  : 'text-red-700'
            }`}
          >
            {utilityDelta != null
              ? `${utilityDelta > 0 ? '+' : ''}${utilityDelta.toFixed(3)}`
              : '—'}
          </p>
        </div>
      </section>

      {/* --- Floor validation --- */}
      <section aria-labelledby="floor-validation-heading">
        <h3
          id="floor-validation-heading"
          className="text-base font-semibold text-slate-900"
        >
          Floor validation
        </h3>
        {report.floor_violations?.length ? (
          <ul className="mt-2 list-disc pl-5 text-sm text-red-700">
            {report.floor_violations.map((v) => (
              <li key={v}>{v}</li>
            ))}
          </ul>
        ) : (
          <div className="mt-2 inline-flex items-center gap-2 rounded-md bg-emerald-50 px-3 py-1.5 text-sm text-emerald-700">
            <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
            All regression floors passed.
          </div>
        )}
      </section>

      {/* --- 6-axis radar --- */}
      <section
        className="grid grid-cols-1 gap-6 lg:grid-cols-[auto,1fr] lg:items-start"
        aria-labelledby="axis-radar-heading"
      >
        <div>
          <h3
            id="axis-radar-heading"
            className="text-base font-semibold text-slate-900"
          >
            6-axis assurance radar
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Candidate (blue) overlaid on incumbent (slate)
          </p>
        </div>
        <AxisRadarChart
          candidateScores={report.axis_scores}
          incumbentScores={report.incumbent_axis_scores ?? null}
        />
      </section>

      {/* --- Cost analysis --- */}
      <section aria-labelledby="cost-heading">
        <h3 id="cost-heading" className="text-base font-semibold text-slate-900">
          <CurrencyDollarIcon className="mr-1 inline h-4 w-4" aria-hidden="true" />
          Cost analysis
        </h3>
        {report.cost_analysis ? (
          <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <dt className="text-slate-500">Candidate input $/Mtok</dt>
            <dd className="text-slate-900">
              ${report.cost_analysis.candidate_input_mtok?.toFixed(2)}
            </dd>
            <dt className="text-slate-500">Candidate output $/Mtok</dt>
            <dd className="text-slate-900">
              ${report.cost_analysis.candidate_output_mtok?.toFixed(2)}
            </dd>
            <dt className="text-slate-500">Incumbent input $/Mtok</dt>
            <dd className="text-slate-900">
              ${report.cost_analysis.incumbent_input_mtok?.toFixed(2)}
            </dd>
            <dt className="text-slate-500">Incumbent output $/Mtok</dt>
            <dd className="text-slate-900">
              ${report.cost_analysis.incumbent_output_mtok?.toFixed(2)}
            </dd>
            <dt className="text-slate-500">Monthly delta estimate</dt>
            <dd
              className={`font-semibold ${
                report.cost_analysis.monthly_delta_estimate < 0
                  ? 'text-emerald-700'
                  : 'text-amber-700'
              }`}
            >
              {formatCurrency(report.cost_analysis.monthly_delta_estimate)}
            </dd>
          </dl>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            No cost analysis available (incumbent or candidate adapter
            metadata missing).
          </p>
        )}
      </section>

      {/* --- Risk assessment --- */}
      <section aria-labelledby="risk-heading">
        <h3 id="risk-heading" className="text-base font-semibold text-slate-900">
          Risk assessment
        </h3>
        {report.risk_notes?.length ? (
          <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
            {report.risk_notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            No risk notes — candidate cleared every check.
          </p>
        )}
      </section>

      {/* --- Provenance chain --- */}
      <section aria-labelledby="provenance-heading">
        <h3
          id="provenance-heading"
          className="text-base font-semibold text-slate-900"
        >
          <ShieldCheckIcon className="mr-1 inline h-4 w-4" aria-hidden="true" />
          Provenance chain
        </h3>
        <p className="mt-2 text-sm text-slate-700">
          {report.provenance_summary || 'no provenance summary available'}
        </p>
      </section>

      {/* --- Edge cases --- */}
      <section aria-labelledby="edge-case-heading">
        <h3
          id="edge-case-heading"
          className="text-base font-semibold text-slate-900"
        >
          Edge case spotlight
        </h3>
        <div className="mt-2">
          <EdgeCaseSpotlight cases={report.edge_cases ?? []} />
        </div>
      </section>

      {/* --- Spot checks --- */}
      <section aria-labelledby="spot-check-heading">
        <h3
          id="spot-check-heading"
          className="flex items-center gap-2 text-base font-semibold text-slate-900"
        >
          <ChatBubbleBottomCenterTextIcon
            className="h-4 w-4"
            aria-hidden="true"
          />
          Human spot-check results
        </h3>
        {!report.spot_checks?.length && (
          <p className="mt-2 text-sm text-slate-500">
            No spot-check samples submitted yet.
          </p>
        )}
        {report.spot_checks?.length > 0 && (
          <ul className="mt-2 space-y-2">
            {report.spot_checks.map((sc) => (
              <li
                key={sc.case_id}
                className={`rounded-md border p-3 text-sm ${
                  sc.disagrees
                    ? 'border-amber-300 bg-amber-50'
                    : 'border-slate-200 bg-slate-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <code className="font-mono text-xs text-slate-700">
                    {sc.case_id}
                  </code>
                  {sc.disagrees && (
                    <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-semibold text-amber-900">
                      reviewer disagrees
                    </span>
                  )}
                </div>
                <p className="mt-1 text-slate-600">
                  automated {sc.automated_pass ? 'pass' : 'fail'} · human{' '}
                  {sc.human_pass ? 'pass' : 'fail'}
                </p>
                {sc.notes && (
                  <p className="mt-1 italic text-slate-500">{sc.notes}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* --- Decision actions --- */}
      <section aria-labelledby="decision-heading" className="border-t border-slate-200 pt-6">
        <h3 id="decision-heading" className="sr-only">
          Decision actions
        </h3>
        <div className="flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            disabled={isSubmitting || integrityState === 'tampered'}
            onClick={() => onReject?.(report)}
            className="inline-flex items-center gap-2 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <XCircleIcon className="h-4 w-4" aria-hidden="true" />
            Reject
          </button>
          <button
            type="button"
            disabled={isSubmitting || integrityState === 'tampered'}
            onClick={() => onApprove?.(report)}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
            Approve & deploy
          </button>
        </div>
      </section>
    </article>
  );
});

export default ShadowReportPanel;
