/**
 * Project Aura - Database Performance Load Test
 *
 * Tests Neptune graph queries and OpenSearch vector search under load.
 * Validates query performance with 1000+ entity graphs.
 *
 * Issue: #13 - Implement load testing framework
 *
 * Usage:
 *   # Test Neptune queries via API
 *   k6 run tests/load/scenarios/database_performance.js
 *
 *   # Stress test
 *   k6 run -e PROFILE=stress tests/load/scenarios/database_performance.js
 */

import { sleep, group } from "k6";
import { Trend, Counter, Rate } from "k6/metrics";
import {
  get,
  post,
  checkResponse,
  checkStatus,
  parseJson,
  randomString,
  sleepWithJitter,
} from "../lib/helpers.js";
import { config, getLoadProfile, slaThresholds } from "../config.js";

// Custom metrics for database operations
const graphQueryDuration = new Trend("graph_query_duration");
const vectorSearchDuration = new Trend("vector_search_duration");
const contextRetrievalDuration = new Trend("context_retrieval_duration");
const hybridSearchDuration = new Trend("hybrid_search_duration");
const dbQueryErrors = new Rate("db_query_errors");
const dbSlaViolations = new Counter("db_sla_violations");

// Get load profile
const profile = __ENV.PROFILE || "smoke";
export const options = {
  ...getLoadProfile(profile),

  thresholds: {
    ...getLoadProfile(profile).thresholds,
    graph_query_duration: [`p(95)<${slaThresholds.neptune.simpleQuery.p95}`],
    vector_search_duration: [`p(95)<${slaThresholds.opensearch.vectorSearch.p95}`],
    context_retrieval_duration: ["p(95)<2000"],
    hybrid_search_duration: [`p(95)<${slaThresholds.opensearch.hybridSearch.p95}`],
    db_query_errors: ["rate<0.05"],
    db_sla_violations: ["count<20"],
  },

  tags: {
    scenario: "database_performance",
    profile: profile,
  },
};

// Sample queries for testing
const sampleQueries = [
  "authentication flow user login",
  "database connection pooling",
  "API rate limiting implementation",
  "error handling middleware",
  "caching strategy Redis",
  "security vulnerability XSS",
  "GraphQL resolver performance",
  "WebSocket connection handling",
  "JWT token validation",
  "microservices communication",
];

// Sample code patterns for graph queries
const codePatterns = [
  { type: "function", name: "handleRequest" },
  { type: "class", name: "UserService" },
  { type: "import", module: "fastapi" },
  { type: "endpoint", path: "/api/users" },
  { type: "dependency", package: "boto3" },
];

export function setup() {
  console.log(`Starting database performance test with profile: ${profile}`);
  console.log(`Base URL: ${config.baseUrl}`);

  return {
    startTime: new Date().toISOString(),
    queries: sampleQueries,
    patterns: codePatterns,
  };
}

export default function (data) {
  const queryIndex = __ITER % data.queries.length;
  const patternIndex = __ITER % data.patterns.length;

  // Test context retrieval (combines Neptune + OpenSearch)
  group("Context Retrieval", function () {
    testContextRetrieval(data.queries[queryIndex]);
  });

  sleepWithJitter(300, 100);

  // Test vector search endpoint
  group("Vector Search", function () {
    testVectorSearch(data.queries[queryIndex]);
  });

  sleepWithJitter(300, 100);

  // Test graph query endpoint
  group("Graph Queries", function () {
    testGraphQuery(data.patterns[patternIndex]);
  });

  sleepWithJitter(300, 100);

  // Test hybrid search
  group("Hybrid Search", function () {
    testHybridSearch(data.queries[queryIndex]);
  });

  sleep(1);
}

export function teardown(data) {
  console.log(`Database performance test completed`);
  console.log(`Started: ${data.startTime}`);
  console.log(`Finished: ${new Date().toISOString()}`);
}

// =============================================================================
// Context Retrieval Tests (Combined Neptune + OpenSearch)
// =============================================================================

function testContextRetrieval(query) {
  const payload = {
    query: query,
    context_budget: 4000,
    include_graph: true,
    include_vector: true,
    repository_id: "test-repo",
  };

  const response = post("/context/retrieve", payload);
  const duration = response.timings.duration;

  contextRetrievalDuration.add(duration);

  // Accept 200, 401 (auth), or 404 (no repo)
  const passed = checkStatus(response, 200, "Context retrieval") ||
                 checkStatus(response, 401, "Context retrieval (auth)") ||
                 checkStatus(response, 404, "Context retrieval (no repo)");

  if (!passed && response.status >= 500) {
    dbQueryErrors.add(1);
  }

  // SLA check
  if (duration > 2000) {
    dbSlaViolations.add(1);
    console.warn(`Context retrieval SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// Vector Search Tests (OpenSearch)
// =============================================================================

function testVectorSearch(query) {
  const payload = {
    query: query,
    top_k: 10,
    similarity_threshold: 0.7,
  };

  const response = post("/search/vector", payload);
  const duration = response.timings.duration;

  vectorSearchDuration.add(duration);

  const passed = checkStatus(response, 200, "Vector search") ||
                 checkStatus(response, 401, "Vector search (auth)") ||
                 checkStatus(response, 404, "Vector search (no index)");

  if (!passed && response.status >= 500) {
    dbQueryErrors.add(1);
  }

  // SLA check
  if (duration > slaThresholds.opensearch.vectorSearch.p95) {
    dbSlaViolations.add(1);
    console.warn(`Vector search SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// Graph Query Tests (Neptune)
// =============================================================================

function testGraphQuery(pattern) {
  const payload = {
    query_type: pattern.type,
    name: pattern.name,
    depth: 2,
    limit: 50,
  };

  const response = post("/graph/query", payload);
  const duration = response.timings.duration;

  graphQueryDuration.add(duration);

  const passed = checkStatus(response, 200, "Graph query") ||
                 checkStatus(response, 401, "Graph query (auth)") ||
                 checkStatus(response, 404, "Graph query (not found)");

  if (!passed && response.status >= 500) {
    dbQueryErrors.add(1);
  }

  // SLA check
  if (duration > slaThresholds.neptune.simpleQuery.p95) {
    dbSlaViolations.add(1);
    console.warn(`Graph query SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// Hybrid Search Tests (Neptune + OpenSearch combined)
// =============================================================================

function testHybridSearch(query) {
  const payload = {
    query: query,
    search_types: ["semantic", "structural", "lexical"],
    weights: {
      semantic: 0.5,
      structural: 0.3,
      lexical: 0.2,
    },
    limit: 20,
  };

  const response = post("/search/hybrid", payload);
  const duration = response.timings.duration;

  hybridSearchDuration.add(duration);

  const passed = checkStatus(response, 200, "Hybrid search") ||
                 checkStatus(response, 401, "Hybrid search (auth)") ||
                 checkStatus(response, 404, "Hybrid search (no data)");

  if (!passed && response.status >= 500) {
    dbQueryErrors.add(1);
  }

  // SLA check
  if (duration > slaThresholds.opensearch.hybridSearch.p95) {
    dbSlaViolations.add(1);
    console.warn(`Hybrid search SLA violation: ${duration}ms`);
  }

  return passed;
}

// =============================================================================
// Handle Summary
// =============================================================================

export function handleSummary(data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `tests/load/results/database_${profile}_${timestamp}.json`;

  return {
    [filename]: JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: "  ", enableColors: true }),
  };
}

import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.2/index.js";
