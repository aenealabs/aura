/**
 * ADR-088 Model Assurance HITL approval queue (top-level page).
 *
 * Layout: master-detail. Left list shows pending Shadow Deployment
 * Reports; right panel shows the selected report with the full
 * §Stage 7 layout (radar chart, edge cases, spot-checks, decision
 * buttons).
 *
 * Graceful degradation: if the API is unreachable the page falls
 * back to mock data and surfaces a "demo mode" badge so the
 * operator knows what they're looking at isn't live.
 */

import { memo, useEffect, useMemo, useState } from 'react';
import {
  ChevronRightIcon,
  ArrowPathIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';

import {
  approveReport,
  listPendingReports,
  rejectReport,
  verifyIntegrity,
} from '../../services/modelAssuranceApi';
import { MOCK_PENDING_REPORTS, mockEnvelopeFor } from './mockData';
import ShadowReportPanel from './ShadowReportPanel';

const ModelAssuranceQueue = memo(function ModelAssuranceQueue() {
  const [reports, setReports] = useState([]);
  const [demoMode, setDemoMode] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [integrityCache, setIntegrityCache] = useState({});

  const selectedReport = useMemo(
    () => reports.find((r) => r.report_id === selectedId) ?? null,
    [reports, selectedId],
  );

  const loadReports = async () => {
    setLoading(true);
    const data = await listPendingReports();
    if (data && Array.isArray(data.reports) && data.reports.length) {
      setReports(data.reports);
      setDemoMode(false);
    } else {
      setReports(MOCK_PENDING_REPORTS);
      setDemoMode(true);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadReports();
  }, []);

  useEffect(() => {
    if (!selectedReport || integrityCache[selectedReport.report_id]) return;
    const verify = async () => {
      const envelope = selectedReport.envelope ?? mockEnvelopeFor(selectedReport);
      try {
        const result = await verifyIntegrity(envelope);
        setIntegrityCache((prev) => ({
          ...prev,
          [selectedReport.report_id]: {
            state: demoMode
              ? 'demo'
              : result.valid
                ? 'verified'
                : 'tampered',
            verification: result,
          },
        }));
      } catch (err) {
        setIntegrityCache((prev) => ({
          ...prev,
          [selectedReport.report_id]: {
            state: 'tampered',
            verification: { valid: false, expected: 'unknown', actual: 'unknown' },
          },
        }));
      }
    };
    verify();
  }, [selectedReport, demoMode, integrityCache]);

  useEffect(() => {
    if (!selectedId && reports.length > 0) {
      setSelectedId(reports[0].report_id);
    }
  }, [reports, selectedId]);

  const handleApprove = async (report) => {
    setSubmitting(true);
    try {
      await approveReport(report.report_id);
      setReports((prev) => prev.filter((r) => r.report_id !== report.report_id));
      setSelectedId(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async (report) => {
    setSubmitting(true);
    try {
      await rejectReport(report.report_id);
      setReports((prev) => prev.filter((r) => r.report_id !== report.report_id));
      setSelectedId(null);
    } finally {
      setSubmitting(false);
    }
  };

  const integrity = selectedReport
    ? integrityCache[selectedReport.report_id]
    : null;

  return (
    <main className="flex h-full flex-col bg-slate-50">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-5">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Model Assurance Approvals
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            ADR-088 Continuous Model Assurance — pending Shadow Deployment
            Reports awaiting HITL review
          </p>
        </div>
        <div className="flex items-center gap-3">
          {demoMode && (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              Demo mode (mock data)
            </span>
          )}
          <button
            type="button"
            onClick={loadReports}
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <ArrowPathIcon className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>
      </header>

      <div className="flex flex-1 gap-6 overflow-hidden p-6">
        {/* List pane */}
        <aside
          className="flex w-80 shrink-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
          aria-label="Pending reports"
        >
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">
              {reports.length} pending
            </p>
          </div>
          <ul className="flex-1 divide-y divide-slate-200 overflow-y-auto" role="listbox">
            {loading && (
              <li className="px-4 py-6 text-center text-sm text-slate-500">
                Loading…
              </li>
            )}
            {!loading && !reports.length && (
              <li className="px-4 py-6 text-center text-sm text-slate-500">
                Queue is empty.
              </li>
            )}
            {reports.map((r) => {
              const selected = r.report_id === selectedId;
              return (
                <li key={r.report_id} role="option" aria-selected={selected}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(r.report_id)}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors ${
                      selected
                        ? 'bg-blue-50 text-slate-900'
                        : 'hover:bg-slate-50 text-slate-700'
                    }`}
                  >
                    <ChevronRightIcon
                      className={`mt-0.5 h-4 w-4 ${selected ? 'text-blue-600' : 'text-slate-400'}`}
                      aria-hidden="true"
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium">
                        {r.candidate_display_name}
                      </p>
                      <p className="mt-0.5 truncate font-mono text-xs text-slate-500">
                        {r.candidate_id}
                      </p>
                      <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                        <ClockIcon className="h-3 w-3" aria-hidden="true" />
                        {r.generated_at
                          ? new Date(r.generated_at).toLocaleTimeString()
                          : 'unknown'}
                      </p>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        {/* Detail pane */}
        <section className="flex-1 overflow-y-auto">
          <ShadowReportPanel
            report={selectedReport}
            integrityState={integrity?.state ?? 'demo'}
            integrityVerification={integrity?.verification ?? null}
            onApprove={handleApprove}
            onReject={handleReject}
            isSubmitting={submitting}
          />
        </section>
      </div>
    </main>
  );
});

export default ModelAssuranceQueue;
