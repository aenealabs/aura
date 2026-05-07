/**
 * Mock data for the Model Assurance HITL queue.
 *
 * Mirrors the shape of the backend's
 * src/services/model_assurance/report/contracts.py::ShadowDeploymentReport
 * with an outer IntegrityEnvelope. Used when the backend API is
 * unreachable so the UI always renders something demoable.
 *
 * The content_hash values here are placeholders — when verifyIntegrity
 * runs against them it will report invalid; the UI surfaces a
 * "demo mode (integrity unverified)" badge to make this honest.
 */

export const MOCK_PENDING_REPORTS = [
  {
    report_id: 'ma-rpt-2026-05-06-001',
    candidate_id: 'anthropic.claude-3-7-sonnet-20260301-v1:0',
    candidate_display_name: 'Claude 3.7 Sonnet',
    incumbent_id: 'anthropic.claude-3-5-sonnet-20240620-v1:0',
    pipeline_decision: 'hitl_queued',
    overall_utility: 0.943,
    incumbent_utility: 0.912,
    floor_violations: [],
    axis_scores: {
      MA1_code_comprehension: 0.94,
      MA2_vulnerability_detection_recall: 0.96,
      MA3_patch_functional_correctness: 0.91,
      MA4_patch_security_equivalence: 0.97,
      MA5_latency_token_efficiency: 0.86,
      MA6_guardrail_compliance: 0.99,
    },
    cost_analysis: {
      candidate_input_mtok: 3.5,
      candidate_output_mtok: 17.5,
      incumbent_input_mtok: 3.0,
      incumbent_output_mtok: 15.0,
      monthly_delta_estimate: 875.0,
    },
    risk_notes: [
      'training-data lineage missing from provenance',
      'assurance verdict: accept',
    ],
    provenance_summary: 'verdict=approved trust=0.910',
    edge_cases: [
      {
        case_id: 'patch-0017',
        description: 'candidate improved on this case',
        candidate_passed: true,
        incumbent_passed: false,
        delta_label: 'improved',
      },
      {
        case_id: 'patch-0042',
        description: 'candidate improved on this case',
        candidate_passed: true,
        incumbent_passed: false,
        delta_label: 'improved',
      },
      {
        case_id: 'patch-0083',
        description: 'candidate regressed on this case',
        candidate_passed: false,
        incumbent_passed: true,
        delta_label: 'regressed',
      },
    ],
    spot_checks: [
      {
        case_id: 'patch-0042',
        automated_pass: true,
        human_pass: true,
        notes: 'reviewer confirmed structural equivalence',
        disagrees: false,
      },
      {
        case_id: 'vulnerability_detection-0020',
        automated_pass: true,
        human_pass: false,
        notes: 'reviewer flagged that the report missed a CWE-79 variant',
        disagrees: true,
      },
    ],
    generated_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
  },
  {
    report_id: 'ma-rpt-2026-05-06-002',
    candidate_id: 'meta-llama/CodeLlama-70b-Python-airgap-v1',
    candidate_display_name: 'CodeLlama 70b (Python, air-gap import)',
    incumbent_id: 'anthropic.claude-3-5-sonnet-20240620-v1:0',
    pipeline_decision: 'hitl_queued',
    overall_utility: 0.872,
    incumbent_utility: 0.912,
    floor_violations: [],
    axis_scores: {
      MA1_code_comprehension: 0.88,
      MA2_vulnerability_detection_recall: 0.85,
      MA3_patch_functional_correctness: 0.89,
      MA4_patch_security_equivalence: 0.95,
      MA5_latency_token_efficiency: 0.78,
      MA6_guardrail_compliance: 0.98,
    },
    cost_analysis: {
      candidate_input_mtok: 1.0,
      candidate_output_mtok: 5.0,
      incumbent_input_mtok: 3.0,
      incumbent_output_mtok: 15.0,
      monthly_delta_estimate: -640.0,
    },
    risk_notes: [
      'inferior overall utility vs incumbent (0.872 < 0.912)',
      'consider rejecting unless cost saving justifies',
    ],
    provenance_summary: 'verdict=approved trust=0.760 (HF curated, air-gap import)',
    edge_cases: [
      {
        case_id: 'patch-0009',
        description: 'candidate regressed on this case',
        candidate_passed: false,
        incumbent_passed: true,
        delta_label: 'regressed',
      },
    ],
    spot_checks: [],
    generated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  },
];

/**
 * Default integrity envelope wrapper for the mock reports above.
 * The hash is intentionally a placeholder — verifyIntegrity will
 * report it as invalid, and the UI surfaces a "demo mode" badge.
 */
export function mockEnvelopeFor(report) {
  const json = JSON.stringify(report);
  return {
    payload_json: json,
    content_hash: 'demo-mode-placeholder-hash',
    created_at: new Date().toISOString(),
    envelope_version: '1.0',
    signed_by: 'aura.model_assurance.report (demo)',
  };
}
