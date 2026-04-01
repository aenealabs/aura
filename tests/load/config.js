/**
 * Project Aura - k6 Load Testing Configuration
 *
 * Centralized configuration for all load test scenarios.
 * Override with environment variables for different environments.
 *
 * Issue: #13 - Implement load testing framework
 *
 * Usage:
 *   k6 run -e BASE_URL=https://api.aura.dev tests/load/scenarios/api_endpoints.js
 */

// Environment configuration
export const config = {
  // Base URL for API endpoints
  baseUrl: __ENV.BASE_URL || "http://localhost:8000",

  // Authentication
  auth: {
    // For testing, use a pre-generated test token
    // In CI, inject via K6_AUTH_TOKEN environment variable
    token: __ENV.K6_AUTH_TOKEN || "test-token-for-load-testing",
    cognitoClientId: __ENV.COGNITO_CLIENT_ID || "test-client-id",
  },

  // Database endpoints (for direct performance testing)
  neptune: {
    endpoint: __ENV.NEPTUNE_ENDPOINT || "neptune.aura.local:8182",
    useSSL: __ENV.NEPTUNE_SSL === "true",
  },

  opensearch: {
    endpoint: __ENV.OPENSEARCH_ENDPOINT || "opensearch.aura.local:9200",
    index: __ENV.OPENSEARCH_INDEX || "aura-embeddings",
  },

  // Test data
  testData: {
    repositoryUrl: "https://github.com/test-org/sample-repo",
    jobId: "test-job-001",
    patchId: "test-patch-001",
  },
};

// Standard load profiles
export const loadProfiles = {
  // Smoke test: minimal load to verify tests work
  smoke: {
    vus: 1,
    duration: "30s",
    thresholds: {
      http_req_duration: ["p(95)<2000"],
      http_req_failed: ["rate<0.01"],
    },
  },

  // Average load: typical production traffic
  average: {
    stages: [
      { duration: "2m", target: 10 }, // Ramp up
      { duration: "5m", target: 10 }, // Stay at 10 users
      { duration: "2m", target: 0 }, // Ramp down
    ],
    thresholds: {
      http_req_duration: ["p(95)<1000", "p(99)<2000"],
      http_req_failed: ["rate<0.05"],
    },
  },

  // Stress test: find breaking point
  stress: {
    stages: [
      { duration: "2m", target: 10 },
      { duration: "5m", target: 50 },
      { duration: "5m", target: 100 },
      { duration: "5m", target: 150 },
      { duration: "2m", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<3000"],
      http_req_failed: ["rate<0.15"],
    },
  },

  // Spike test: sudden traffic surge
  spike: {
    stages: [
      { duration: "1m", target: 10 },
      { duration: "30s", target: 200 }, // Spike!
      { duration: "1m", target: 200 },
      { duration: "30s", target: 10 },
      { duration: "1m", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<5000"],
      http_req_failed: ["rate<0.20"],
    },
  },

  // Soak test: extended duration for memory leaks
  soak: {
    stages: [
      { duration: "5m", target: 20 },
      { duration: "30m", target: 20 },
      { duration: "5m", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<2000"],
      http_req_failed: ["rate<0.05"],
    },
  },
};

// Performance SLA thresholds
export const slaThresholds = {
  // API response times
  api: {
    health: { p95: 100, p99: 200 }, // Health checks must be fast
    jobs: { p95: 500, p99: 1000 }, // Job operations
    patches: { p95: 1000, p99: 2000 }, // Patch operations
    approval: { p95: 500, p99: 1000 }, // HITL approval
  },

  // Database query times
  neptune: {
    simpleQuery: { p95: 100, p99: 200 },
    graphTraversal: { p95: 500, p99: 1000 },
    complexQuery: { p95: 2000, p99: 5000 },
  },

  opensearch: {
    vectorSearch: { p95: 200, p99: 500 },
    hybridSearch: { p95: 500, p99: 1000 },
  },
};

// Helper to get load profile by name
export function getLoadProfile(name) {
  const profile = loadProfiles[name];
  if (!profile) {
    console.error(`Unknown load profile: ${name}. Using 'smoke'.`);
    return loadProfiles.smoke;
  }
  return profile;
}

// Default export for k6 options
export default {
  // Default to smoke test profile
  ...loadProfiles.smoke,

  // Output configuration
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};
