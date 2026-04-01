/**
 * Project Aura - API Endpoints Load Test
 *
 * Tests API endpoint throughput and response times under load.
 * Targets 100+ concurrent users with acceptable latency.
 *
 * Issue: #13 - Implement load testing framework
 *
 * Usage:
 *   # Smoke test (default)
 *   k6 run tests/load/scenarios/api_endpoints.js
 *
 *   # Stress test
 *   k6 run -e PROFILE=stress tests/load/scenarios/api_endpoints.js
 *
 *   # Custom base URL
 *   k6 run -e BASE_URL=https://api.aura.dev tests/load/scenarios/api_endpoints.js
 */

import { sleep, group } from "k6";
import { Trend, Counter, Rate } from "k6/metrics";
import {
  get,
  post,
  checkResponse,
  checkStatus,
  parseJson,
  uniqueId,
  sleepWithJitter,
} from "../lib/helpers.js";
import { config, getLoadProfile, slaThresholds } from "../config.js";

// Custom metrics for this scenario
const healthCheckDuration = new Trend("health_check_duration");
const jobListDuration = new Trend("job_list_duration");
const jobCreateDuration = new Trend("job_create_duration");
const patchListDuration = new Trend("patch_list_duration");
const slaViolations = new Counter("sla_violations");
const endpointErrors = new Rate("endpoint_errors");

// Get load profile from environment or default to smoke
const profile = __ENV.PROFILE || "smoke";
export const options = {
  ...getLoadProfile(profile),

  // Additional thresholds specific to API endpoints
  thresholds: {
    ...getLoadProfile(profile).thresholds,
    health_check_duration: [`p(95)<${slaThresholds.api.health.p95}`],
    job_list_duration: [`p(95)<${slaThresholds.api.jobs.p95}`],
    job_create_duration: [`p(95)<${slaThresholds.api.jobs.p95}`],
    patch_list_duration: [`p(95)<${slaThresholds.api.patches.p95}`],
    sla_violations: ["count<10"],
    endpoint_errors: ["rate<0.05"],
  },

  // Tags for filtering in Grafana
  tags: {
    scenario: "api_endpoints",
    profile: profile,
  },
};

// Setup function runs once before test
export function setup() {
  console.log(`Starting API endpoint load test with profile: ${profile}`);
  console.log(`Base URL: ${config.baseUrl}`);

  // Verify API is reachable
  const healthResponse = get("/health");
  if (healthResponse.status !== 200) {
    console.error(`API not reachable: ${healthResponse.status}`);
  }

  return {
    startTime: new Date().toISOString(),
  };
}

// Main test function
export default function (data) {
  // Test health endpoints
  group("Health Endpoints", function () {
    testHealthEndpoint();
    testReadinessEndpoint();
  });

  sleepWithJitter(500, 200);

  // Test job endpoints
  group("Job Endpoints", function () {
    testJobList();
    testJobStatus();
  });

  sleepWithJitter(500, 200);

  // Test patch endpoints
  group("Patch Endpoints", function () {
    testPatchList();
  });

  sleepWithJitter(500, 200);

  // Test settings endpoints
  group("Settings Endpoints", function () {
    testSettingsGet();
  });

  // Think time between iterations
  sleep(1);
}

// Teardown function runs once after test
export function teardown(data) {
  console.log(`Test completed. Started at: ${data.startTime}`);
  console.log(`Finished at: ${new Date().toISOString()}`);
}

// =============================================================================
// Health Endpoint Tests
// =============================================================================

function testHealthEndpoint() {
  const response = get("/health");
  const duration = response.timings.duration;

  healthCheckDuration.add(duration);

  const passed = checkResponse(response, "Health check");
  if (!passed) {
    endpointErrors.add(1);
  }

  // Check SLA
  if (duration > slaThresholds.api.health.p95) {
    slaViolations.add(1);
    console.warn(`Health SLA violation: ${duration}ms > ${slaThresholds.api.health.p95}ms`);
  }

  return passed;
}

function testReadinessEndpoint() {
  const response = get("/health/ready");
  const duration = response.timings.duration;

  healthCheckDuration.add(duration);

  const passed = checkResponse(response, "Readiness check");
  if (!passed) {
    endpointErrors.add(1);
  }

  return passed;
}

// =============================================================================
// Job Endpoint Tests
// =============================================================================

function testJobList() {
  const response = get("/jobs");
  const duration = response.timings.duration;

  jobListDuration.add(duration);

  // Accept 200 or 401 (if auth required)
  const passed = checkStatus(response, 200, "Job list") ||
                 checkStatus(response, 401, "Job list (auth required)");

  if (!passed && response.status >= 400) {
    endpointErrors.add(1);
  }

  // Check SLA
  if (duration > slaThresholds.api.jobs.p95) {
    slaViolations.add(1);
    console.warn(`Job list SLA violation: ${duration}ms`);
  }

  return passed;
}

function testJobStatus() {
  // Use a known test job ID or create one
  const jobId = config.testData.jobId;
  const response = get(`/jobs/${jobId}/status`);

  // Accept 200 (found), 404 (not found is ok for test ID), or 401
  const passed = checkStatus(response, 200, "Job status") ||
                 checkStatus(response, 404, "Job status (not found)") ||
                 checkStatus(response, 401, "Job status (auth required)");

  if (!passed && response.status >= 500) {
    endpointErrors.add(1);
  }

  return passed;
}

// =============================================================================
// Patch Endpoint Tests
// =============================================================================

function testPatchList() {
  const response = get("/patches");
  const duration = response.timings.duration;

  patchListDuration.add(duration);

  const passed = checkStatus(response, 200, "Patch list") ||
                 checkStatus(response, 401, "Patch list (auth required)");

  if (!passed && response.status >= 400) {
    endpointErrors.add(1);
  }

  // Check SLA
  if (duration > slaThresholds.api.patches.p95) {
    slaViolations.add(1);
    console.warn(`Patch list SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// Settings Endpoint Tests
// =============================================================================

function testSettingsGet() {
  const response = get("/settings");

  const passed = checkStatus(response, 200, "Settings get") ||
                 checkStatus(response, 401, "Settings (auth required)");

  if (!passed && response.status >= 500) {
    endpointErrors.add(1);
  }

  return passed;
}

// =============================================================================
// Handle Summary (for JSON output)
// =============================================================================

export function handleSummary(data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `tests/load/results/api_endpoints_${profile}_${timestamp}.json`;

  return {
    [filename]: JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: "  ", enableColors: true }),
  };
}

// Import text summary helper
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.2/index.js";
