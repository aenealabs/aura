/**
 * Project Aura - HITL Approval Workflow Load Test
 *
 * Tests the Human-in-the-Loop approval workflow under concurrent load.
 * Simulates multiple users reviewing and approving patches simultaneously.
 *
 * Issue: #13 - Implement load testing framework
 *
 * Usage:
 *   k6 run tests/load/scenarios/hitl_workflow.js
 *   k6 run -e PROFILE=stress tests/load/scenarios/hitl_workflow.js
 */

import { sleep, group } from "k6";
import { Trend, Counter, Rate } from "k6/metrics";
import {
  get,
  post,
  put,
  checkResponse,
  checkStatus,
  parseJson,
  uniqueId,
  sleepWithJitter,
} from "../lib/helpers.js";
import { config, getLoadProfile, slaThresholds } from "../config.js";

// Custom metrics for HITL workflow
const approvalListDuration = new Trend("approval_list_duration");
const approvalDetailDuration = new Trend("approval_detail_duration");
const approvalSubmitDuration = new Trend("approval_submit_duration");
const patchDiffDuration = new Trend("patch_diff_duration");
const workflowErrors = new Rate("workflow_errors");
const workflowSlaViolations = new Counter("workflow_sla_violations");
const approvalsProcessed = new Counter("approvals_processed");

// Get load profile
const profile = __ENV.PROFILE || "smoke";
export const options = {
  ...getLoadProfile(profile),

  thresholds: {
    ...getLoadProfile(profile).thresholds,
    approval_list_duration: [`p(95)<${slaThresholds.api.approval.p95}`],
    approval_detail_duration: [`p(95)<${slaThresholds.api.approval.p95}`],
    approval_submit_duration: [`p(95)<${slaThresholds.api.approval.p95}`],
    patch_diff_duration: ["p(95)<1000"],
    workflow_errors: ["rate<0.05"],
    workflow_sla_violations: ["count<10"],
  },

  tags: {
    scenario: "hitl_workflow",
    profile: profile,
  },
};

// Simulated approval decisions
const approvalDecisions = [
  { action: "approve", comment: "LGTM - changes look good" },
  { action: "approve", comment: "Verified fix addresses the vulnerability" },
  { action: "reject", comment: "Need more context on this change" },
  { action: "request_changes", comment: "Please add unit tests" },
  { action: "approve", comment: "Approved after review" },
];

export function setup() {
  console.log(`Starting HITL workflow load test with profile: ${profile}`);
  console.log(`Base URL: ${config.baseUrl}`);

  return {
    startTime: new Date().toISOString(),
    decisions: approvalDecisions,
  };
}

export default function (data) {
  const decisionIndex = __ITER % data.decisions.length;

  // Simulate reviewer workflow
  group("List Pending Approvals", function () {
    testListPendingApprovals();
  });

  sleepWithJitter(500, 200);

  group("View Approval Details", function () {
    testViewApprovalDetails();
  });

  sleepWithJitter(500, 200);

  group("View Patch Diff", function () {
    testViewPatchDiff();
  });

  sleepWithJitter(500, 200);

  group("Submit Approval Decision", function () {
    testSubmitApproval(data.decisions[decisionIndex]);
  });

  // Longer think time for approval workflow (users read code)
  sleep(2);
}

export function teardown(data) {
  console.log(`HITL workflow test completed`);
  console.log(`Started: ${data.startTime}`);
  console.log(`Finished: ${new Date().toISOString()}`);
}

// =============================================================================
// List Pending Approvals
// =============================================================================

function testListPendingApprovals() {
  const response = get("/approvals/pending");
  const duration = response.timings.duration;

  approvalListDuration.add(duration);

  const passed = checkStatus(response, 200, "Pending approvals") ||
                 checkStatus(response, 401, "Pending approvals (auth)");

  if (!passed && response.status >= 500) {
    workflowErrors.add(1);
  }

  // SLA check
  if (duration > slaThresholds.api.approval.p95) {
    workflowSlaViolations.add(1);
    console.warn(`Approval list SLA violation: ${duration}ms`);
  }

  // Parse response to get approval IDs for subsequent tests
  if (response.status === 200) {
    const body = parseJson(response);
    if (body && body.approvals && body.approvals.length > 0) {
      return body.approvals[0].id;
    }
  }

  return null;
}

// =============================================================================
// View Approval Details
// =============================================================================

function testViewApprovalDetails() {
  // Use test data ID or a generated one
  const approvalId = config.testData.patchId || uniqueId("approval");

  const response = get(`/approvals/${approvalId}`);
  const duration = response.timings.duration;

  approvalDetailDuration.add(duration);

  // Accept 200, 404 (test ID may not exist), or 401
  const passed = checkStatus(response, 200, "Approval details") ||
                 checkStatus(response, 404, "Approval details (not found)") ||
                 checkStatus(response, 401, "Approval details (auth)");

  if (!passed && response.status >= 500) {
    workflowErrors.add(1);
  }

  // SLA check
  if (duration > slaThresholds.api.approval.p95) {
    workflowSlaViolations.add(1);
    console.warn(`Approval detail SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// View Patch Diff
// =============================================================================

function testViewPatchDiff() {
  const patchId = config.testData.patchId || uniqueId("patch");

  const response = get(`/patches/${patchId}/diff`);
  const duration = response.timings.duration;

  patchDiffDuration.add(duration);

  const passed = checkStatus(response, 200, "Patch diff") ||
                 checkStatus(response, 404, "Patch diff (not found)") ||
                 checkStatus(response, 401, "Patch diff (auth)");

  if (!passed && response.status >= 500) {
    workflowErrors.add(1);
  }

  return passed;
}

// =============================================================================
// Submit Approval Decision
// =============================================================================

function testSubmitApproval(decision) {
  const approvalId = config.testData.patchId || uniqueId("approval");

  const payload = {
    action: decision.action,
    comment: decision.comment,
    reviewer_id: `reviewer-${__VU}`,
    timestamp: new Date().toISOString(),
  };

  const response = post(`/approvals/${approvalId}/decision`, payload);
  const duration = response.timings.duration;

  approvalSubmitDuration.add(duration);

  // Accept various status codes
  const passed = checkStatus(response, 200, "Approval submit") ||
                 checkStatus(response, 201, "Approval created") ||
                 checkStatus(response, 404, "Approval (not found)") ||
                 checkStatus(response, 401, "Approval (auth)") ||
                 checkStatus(response, 409, "Approval (conflict)");

  if (!passed && response.status >= 500) {
    workflowErrors.add(1);
  } else if (response.status === 200 || response.status === 201) {
    approvalsProcessed.add(1);
  }

  // SLA check
  if (duration > slaThresholds.api.approval.p95) {
    workflowSlaViolations.add(1);
    console.warn(`Approval submit SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// Additional Workflow Tests
// =============================================================================

function testApprovalHistory() {
  const response = get("/approvals/history?limit=20");
  const duration = response.timings.duration;

  const passed = checkStatus(response, 200, "Approval history") ||
                 checkStatus(response, 401, "Approval history (auth)");

  return passed;
}

function testApprovalStats() {
  const response = get("/approvals/stats");

  const passed = checkStatus(response, 200, "Approval stats") ||
                 checkStatus(response, 401, "Approval stats (auth)");

  return passed;
}

// =============================================================================
// Handle Summary
// =============================================================================

export function handleSummary(data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `tests/load/results/hitl_${profile}_${timestamp}.json`;

  return {
    [filename]: JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: "  ", enableColors: true }),
  };
}

import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.2/index.js";
