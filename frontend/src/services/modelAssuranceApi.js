/**
 * Project Aura - Model Assurance API Service
 *
 * Client-side service for the ADR-088 HITL approval queue.
 * Lists pending shadow deployment reports, verifies integrity hashes,
 * and submits operator decisions back to the pipeline.
 *
 * Mirrors the graceful-degradation pattern in approvalApi.js: API
 * failures fall back to mock data so the dashboard always renders.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export class ModelAssuranceApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ModelAssuranceApiError';
    this.status = status;
    this.details = details;
  }
}

async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = { 'Content-Type': 'application/json' };
  try {
    const response = await fetch(url, {
      ...options,
      headers: { ...defaultHeaders, ...options.headers },
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ModelAssuranceApiError(
        errorData.detail || errorData.error || `API error: ${response.status}`,
        response.status,
        errorData,
      );
    }
    return await response.json();
  } catch (err) {
    if (err instanceof ModelAssuranceApiError) throw err;
    return null; // network error → caller falls back to mocks
  }
}

/**
 * List all pending Shadow Deployment Reports awaiting HITL decision.
 * Returns null on network failure so callers can fall back to mock data.
 */
export async function listPendingReports() {
  return fetchApi('/model-assurance/approval-queue');
}

/**
 * Get one Shadow Deployment Report wrapped in its IntegrityEnvelope.
 * The envelope's content_hash MUST be verified before the report
 * is presented in the UI — see verifyIntegrity below.
 */
export async function getReport(reportId) {
  return fetchApi(`/model-assurance/reports/${encodeURIComponent(reportId)}`);
}

/**
 * Verify the content hash of an IntegrityEnvelope on the client side.
 * Matches the SHA-256 over canonical JSON used by the backend's
 * report.integrity.seal_report().
 *
 * Returns:
 *   { valid: boolean, expected: string, actual: string }
 */
export async function verifyIntegrity(envelope) {
  // Use the Web Crypto API; all modern browsers support SHA-256 here.
  const encoder = new TextEncoder();
  const data = encoder.encode(envelope.payload_json);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const actual = Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return {
    valid: actual === envelope.content_hash,
    expected: envelope.content_hash,
    actual,
  };
}

/**
 * Submit operator approval. Triggers the deployment pipeline
 * stage that updates the live model configuration.
 */
export async function approveReport(reportId, { notes } = {}) {
  return fetchApi(
    `/model-assurance/reports/${encodeURIComponent(reportId)}/approve`,
    { method: 'POST', body: JSON.stringify({ notes: notes || '' }) },
  );
}

/**
 * Submit operator rejection. The candidate enters sticky
 * quarantine — re-evaluation requires explicit operator override.
 */
export async function rejectReport(reportId, { reason } = {}) {
  return fetchApi(
    `/model-assurance/reports/${encodeURIComponent(reportId)}/reject`,
    { method: 'POST', body: JSON.stringify({ reason: reason || '' }) },
  );
}

/**
 * Submit a spot-check decision (5% sampling per ADR-088 §Stage 6).
 * The agreement/disagreement is surfaced on the report so the
 * operator can see whether the automated and human verdicts align.
 */
export async function submitSpotCheck(reportId, { caseId, humanPass, notes } = {}) {
  return fetchApi(
    `/model-assurance/reports/${encodeURIComponent(reportId)}/spot-check`,
    {
      method: 'POST',
      body: JSON.stringify({
        case_id: caseId,
        human_pass: humanPass,
        notes: notes || '',
      }),
    },
  );
}
