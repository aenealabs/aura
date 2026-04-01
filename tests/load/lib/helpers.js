/**
 * Project Aura - k6 Load Testing Helpers
 *
 * Common utility functions for load test scenarios.
 *
 * Issue: #13 - Implement load testing framework
 */

import http from "k6/http";
import { check, fail } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";
import { config } from "../config.js";

// Custom metrics
export const errorRate = new Rate("errors");
export const requestDuration = new Trend("request_duration");
export const successfulRequests = new Counter("successful_requests");
export const failedRequests = new Counter("failed_requests");

/**
 * Get default headers for API requests.
 * @returns {Object} Headers object with auth and content-type
 */
export function getHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${config.auth.token}`,
    "X-Correlation-ID": `k6-${__VU}-${__ITER}-${Date.now()}`,
  };
}

/**
 * Make an authenticated GET request.
 * @param {string} path - API path (without base URL)
 * @param {Object} params - Optional request parameters
 * @returns {Object} k6 response object
 */
export function get(path, params = {}) {
  const url = `${config.baseUrl}${path}`;
  const response = http.get(url, {
    headers: getHeaders(),
    ...params,
  });

  trackMetrics(response);
  return response;
}

/**
 * Make an authenticated POST request.
 * @param {string} path - API path (without base URL)
 * @param {Object} body - Request body
 * @param {Object} params - Optional request parameters
 * @returns {Object} k6 response object
 */
export function post(path, body, params = {}) {
  const url = `${config.baseUrl}${path}`;
  const response = http.post(url, JSON.stringify(body), {
    headers: getHeaders(),
    ...params,
  });

  trackMetrics(response);
  return response;
}

/**
 * Make an authenticated PUT request.
 * @param {string} path - API path (without base URL)
 * @param {Object} body - Request body
 * @param {Object} params - Optional request parameters
 * @returns {Object} k6 response object
 */
export function put(path, body, params = {}) {
  const url = `${config.baseUrl}${path}`;
  const response = http.put(url, JSON.stringify(body), {
    headers: getHeaders(),
    ...params,
  });

  trackMetrics(response);
  return response;
}

/**
 * Make an authenticated DELETE request.
 * @param {string} path - API path (without base URL)
 * @param {Object} params - Optional request parameters
 * @returns {Object} k6 response object
 */
export function del(path, params = {}) {
  const url = `${config.baseUrl}${path}`;
  const response = http.del(url, null, {
    headers: getHeaders(),
    ...params,
  });

  trackMetrics(response);
  return response;
}

/**
 * Track custom metrics for a response.
 * @param {Object} response - k6 response object
 */
function trackMetrics(response) {
  const success = response.status >= 200 && response.status < 400;

  errorRate.add(!success);
  requestDuration.add(response.timings.duration);

  if (success) {
    successfulRequests.add(1);
  } else {
    failedRequests.add(1);
  }
}

/**
 * Standard check for successful response.
 * @param {Object} response - k6 response object
 * @param {string} name - Check name for reporting
 * @returns {boolean} Whether all checks passed
 */
export function checkResponse(response, name = "API call") {
  return check(response, {
    [`${name} - status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${name} - response time < 2s`]: (r) => r.timings.duration < 2000,
    [`${name} - has body`]: (r) => r.body && r.body.length > 0,
  });
}

/**
 * Check for specific status code.
 * @param {Object} response - k6 response object
 * @param {number} expectedStatus - Expected HTTP status code
 * @param {string} name - Check name for reporting
 * @returns {boolean} Whether check passed
 */
export function checkStatus(response, expectedStatus, name = "API call") {
  return check(response, {
    [`${name} - status is ${expectedStatus}`]: (r) =>
      r.status === expectedStatus,
  });
}

/**
 * Parse JSON response body safely.
 * @param {Object} response - k6 response object
 * @returns {Object|null} Parsed JSON or null on error
 */
export function parseJson(response) {
  try {
    return JSON.parse(response.body);
  } catch (e) {
    console.error(`Failed to parse JSON: ${e.message}`);
    return null;
  }
}

/**
 * Generate a random string for test data.
 * @param {number} length - String length
 * @returns {string} Random alphanumeric string
 */
export function randomString(length = 10) {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Generate a unique test ID.
 * @param {string} prefix - ID prefix
 * @returns {string} Unique ID
 */
export function uniqueId(prefix = "test") {
  return `${prefix}-${__VU}-${__ITER}-${Date.now()}`;
}

/**
 * Sleep with random jitter to avoid thundering herd.
 * @param {number} baseMs - Base sleep time in milliseconds
 * @param {number} jitterMs - Maximum jitter in milliseconds
 */
export function sleepWithJitter(baseMs, jitterMs = 500) {
  const jitter = Math.random() * jitterMs;
  const totalMs = baseMs + jitter;
  // k6's sleep takes seconds
  __sleep(totalMs / 1000);
}

// Import k6's sleep as __sleep to use in our helper
import { sleep as __sleep } from "k6";

/**
 * Batch multiple requests together.
 * @param {Array} requests - Array of request configs [{method, path, body}]
 * @returns {Array} Array of responses
 */
export function batchRequests(requests) {
  const batchConfig = requests.map((req) => {
    const url = `${config.baseUrl}${req.path}`;
    return {
      method: req.method || "GET",
      url: url,
      body: req.body ? JSON.stringify(req.body) : null,
      params: { headers: getHeaders() },
    };
  });

  return http.batch(batchConfig);
}

/**
 * Log test context for debugging.
 */
export function logContext() {
  console.log(`VU: ${__VU}, Iteration: ${__ITER}, Time: ${new Date().toISOString()}`);
}
