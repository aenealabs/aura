/**
 * Explainability API Service
 *
 * Provides API client functions for the Explainability Dashboard (ADR-068).
 * Endpoints:
 * - GET  /api/v1/explainability/decisions       - Get decision records
 * - GET  /api/v1/explainability/decisions/:id   - Get single decision detail
 * - GET  /api/v1/explainability/contradictions  - Get contradiction alerts
 * - POST /api/v1/explainability/contradictions/:id/resolve - Resolve contradiction
 * - POST /api/v1/explainability/contradictions/:id/dismiss - Dismiss contradiction
 * - GET  /api/v1/explainability/stats           - Get dashboard statistics
 *
 * In development mode, falls back to mock data when the backend is unavailable.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';
const IS_DEV = import.meta.env.DEV;

/**
 * Get auth headers for API requests
 */
function getAuthHeaders() {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Handle API response and parse JSON
 */
async function handleResponse(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Generate mock reasoning chain
 */
function generateMockReasoningChain(decisionType) {
  const chains = {
    code_generation: [
      {
        step: 1,
        description: 'Analyzed user request for new feature implementation',
        confidence: 0.95,
        evidenceSources: ['user_input', 'context_window'],
      },
      {
        step: 2,
        description: 'Retrieved relevant code patterns from knowledge graph',
        confidence: 0.88,
        evidenceSources: ['knowledge_graph', 'codebase_search'],
      },
      {
        step: 3,
        description: 'Evaluated 3 implementation approaches against best practices',
        confidence: 0.82,
        evidenceSources: ['design_patterns', 'security_guidelines'],
      },
      {
        step: 4,
        description: 'Selected approach balancing performance and maintainability',
        confidence: 0.85,
        evidenceSources: ['tradeoff_analysis'],
      },
      {
        step: 5,
        description: 'Generated code with inline documentation',
        confidence: 0.91,
        evidenceSources: ['template_library', 'coding_standards'],
      },
    ],
    security_review: [
      {
        step: 1,
        description: 'Scanned code for OWASP Top 10 vulnerabilities',
        confidence: 0.97,
        evidenceSources: ['semgrep', 'security_rules'],
      },
      {
        step: 2,
        description: 'Analyzed data flow for potential injection points',
        confidence: 0.92,
        evidenceSources: ['dataflow_analysis', 'taint_tracking'],
      },
      {
        step: 3,
        description: 'Verified authentication and authorization patterns',
        confidence: 0.89,
        evidenceSources: ['auth_patterns', 'rbac_config'],
      },
      {
        step: 4,
        description: 'Assessed cryptographic usage and key management',
        confidence: 0.94,
        evidenceSources: ['crypto_best_practices'],
      },
    ],
    deployment: [
      {
        step: 1,
        description: 'Validated deployment manifest against environment constraints',
        confidence: 0.96,
        evidenceSources: ['kubernetes_schema', 'env_config'],
      },
      {
        step: 2,
        description: 'Checked resource limits and scaling parameters',
        confidence: 0.91,
        evidenceSources: ['capacity_planning', 'historical_usage'],
      },
      {
        step: 3,
        description: 'Verified rollback strategy and health checks',
        confidence: 0.88,
        evidenceSources: ['deployment_standards', 'runbook'],
      },
    ],
  };

  return chains[decisionType] || chains.code_generation;
}

/**
 * Generate mock alternatives
 */
function generateMockAlternatives(decisionType) {
  const alternatives = {
    code_generation: [
      {
        id: 'alt-1',
        description: 'Factory pattern with dependency injection',
        score: 0.85,
        chosen: true,
        pros: ['Testability', 'Loose coupling', 'Easy to extend'],
        cons: ['Slightly more complex', 'More boilerplate'],
      },
      {
        id: 'alt-2',
        description: 'Direct instantiation with configuration',
        score: 0.72,
        chosen: false,
        pros: ['Simpler initial implementation', 'Less code'],
        cons: ['Harder to test', 'Tight coupling'],
        rejectionReason: 'Lower testability score',
      },
      {
        id: 'alt-3',
        description: 'Service locator pattern',
        score: 0.68,
        chosen: false,
        pros: ['Flexible', 'Runtime configuration'],
        cons: ['Hidden dependencies', 'Anti-pattern concerns'],
        rejectionReason: 'Generally considered an anti-pattern',
      },
    ],
    security_review: [
      {
        id: 'alt-1',
        description: 'Allow with additional input validation',
        score: 0.89,
        chosen: true,
        pros: ['Addresses security concern', 'Minimal code changes'],
        cons: ['Adds slight latency'],
      },
      {
        id: 'alt-2',
        description: 'Block until code is refactored',
        score: 0.75,
        chosen: false,
        pros: ['Maximum security'],
        cons: ['Blocks deployment', 'Longer timeline'],
        rejectionReason: 'Risk can be mitigated with validation',
      },
    ],
    deployment: [
      {
        id: 'alt-1',
        description: 'Rolling update with 25% max unavailable',
        score: 0.91,
        chosen: true,
        pros: ['Zero downtime', 'Gradual rollout', 'Easy rollback'],
        cons: ['Slower deployment', 'Requires spare capacity'],
      },
      {
        id: 'alt-2',
        description: 'Blue-green deployment',
        score: 0.82,
        chosen: false,
        pros: ['Instant rollback', 'Full testing before switch'],
        cons: ['Requires 2x resources temporarily'],
        rejectionReason: 'Resource constraints in current cluster',
      },
    ],
  };

  return alternatives[decisionType] || alternatives.code_generation;
}

/**
 * Mock data for development when backend is unavailable
 * Designed to simulate production environment with realistic scenarios
 */
const MOCK_DATA = {
  decisions: [
    {
      id: 'dec-001',
      timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      agentId: 'coder-agent',
      agentName: 'CoderAgent',
      type: 'code_generation',
      summary: 'Generated authentication middleware with JWT validation',
      title: 'Generated authentication middleware',
      description: 'Created JWT validation middleware with refresh token handling for the API gateway',
      input: 'Create a middleware function that validates JWT tokens, handles token refresh, and extracts user context for downstream services.',
      briefReasoning: 'Analyzed security requirements and implemented industry-standard JWT validation with automatic refresh handling.',
      output: 'async function validateJWT(req, res, next) {\n  const token = extractBearerToken(req);\n  const decoded = await verifyToken(token);\n  req.user = decoded;\n  next();\n}',
      confidence: 0.87,
      confidenceData: {
        pointEstimate: 0.87,
        lowerBound: 0.78,
        upperBound: 0.94,
        uncertaintySources: ['limited_training_examples', 'ambiguous_requirements'],
      },
      reasoningChain: generateMockReasoningChain('code_generation'),
      alternatives: generateMockAlternatives('code_generation'),
      selectedAlternativeIndex: 0,
      criteria: ['testability', 'maintainability', 'performance', 'security'],
      rationale: 'Selected factory pattern for optimal balance of testability and maintainability',
      severity: 'significant',
      hasContradiction: false,
      status: 'completed',
    },
    {
      id: 'dec-002',
      timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
      agentId: 'reviewer-agent',
      agentName: 'ReviewerAgent',
      type: 'security_review',
      summary: 'Security review: Identified SQL injection risk in user search',
      title: 'Security review: SQL injection risk',
      description: 'Identified potential SQL injection vulnerability in user search endpoint that could allow attackers to extract sensitive data.',
      input: 'Review the user search endpoint implementation for security vulnerabilities before production deployment.',
      briefReasoning: 'Static analysis detected string concatenation in SQL queries. Dataflow analysis confirmed user input reaches query construction.',
      output: 'APPROVE with condition: Replace string concatenation with parameterized queries using prepared statements.',
      confidence: 0.92,
      confidenceData: {
        pointEstimate: 0.92,
        lowerBound: 0.85,
        upperBound: 0.97,
        uncertaintySources: ['complex_data_flow'],
      },
      reasoningChain: generateMockReasoningChain('security_review'),
      alternatives: generateMockAlternatives('security_review'),
      selectedAlternativeIndex: 0,
      criteria: ['security', 'user_experience', 'deployment_velocity'],
      rationale: 'Input validation provides adequate protection without blocking deployment',
      severity: 'critical',
      hasContradiction: false,
      status: 'completed',
    },
    {
      id: 'dec-003',
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      agentId: 'validator-agent',
      agentName: 'ValidatorAgent',
      type: 'deployment',
      summary: 'Validated production deployment manifest for API v2.4.0',
      title: 'Validated production deployment manifest',
      description: 'Reviewed Kubernetes deployment configuration for API service v2.4.0 including resource limits, health checks, and rollback strategy.',
      input: 'Validate the Kubernetes deployment manifest for api-service v2.4.0 against production requirements and best practices.',
      briefReasoning: 'Manifest passes all schema validations. Resource limits align with capacity planning. Health checks configured correctly.',
      output: 'APPROVED: Deployment meets all requirements. Rolling update strategy configured with 25% max unavailable.',
      confidence: 0.95,
      confidenceData: {
        pointEstimate: 0.95,
        lowerBound: 0.90,
        upperBound: 0.98,
        uncertaintySources: [],
      },
      reasoningChain: generateMockReasoningChain('deployment'),
      alternatives: generateMockAlternatives('deployment'),
      selectedAlternativeIndex: 0,
      criteria: ['availability', 'resource_efficiency', 'rollback_safety'],
      rationale: 'Rolling update provides best balance of safety and resource utilization',
      severity: 'critical',
      hasContradiction: false,
      status: 'completed',
    },
    {
      id: 'dec-004',
      timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
      agentId: 'coder-agent',
      agentName: 'CoderAgent',
      type: 'code_generation',
      summary: 'Generated type-safe pagination utility for API responses',
      title: 'Generated pagination utility',
      description: 'Created reusable generic pagination component that handles cursor-based and offset pagination for API responses.',
      input: 'Create a reusable pagination utility that supports both cursor-based and offset pagination with TypeScript generics.',
      briefReasoning: 'Implemented generic class supporting multiple pagination strategies with compile-time type safety.',
      output: 'class Paginator<T> {\n  constructor(private strategy: PaginationStrategy) {}\n  async paginate(query: Query): Promise<Page<T>> { ... }\n}',
      confidence: 0.91,
      confidenceData: {
        pointEstimate: 0.91,
        lowerBound: 0.84,
        upperBound: 0.96,
        uncertaintySources: ['generic_type_complexity'],
      },
      reasoningChain: generateMockReasoningChain('code_generation'),
      alternatives: generateMockAlternatives('code_generation'),
      selectedAlternativeIndex: 0,
      criteria: ['reusability', 'type_safety', 'performance'],
      rationale: 'Generic implementation maximizes reuse across different entity types',
      severity: 'normal',
      hasContradiction: false,
      status: 'completed',
    },
    {
      id: 'dec-005',
      timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      agentId: 'patcher-agent',
      agentName: 'PatcherAgent',
      type: 'security_patch',
      summary: 'Applied CVE-2024-1234 remediation for lodash vulnerability',
      title: 'Applied CVE-2024-1234 remediation',
      description: 'Patched critical prototype pollution vulnerability in lodash package affecting versions < 4.17.21.',
      input: 'Remediate CVE-2024-1234 affecting lodash dependency with CVSS score 7.4 (High).',
      briefReasoning: 'Version upgrade to 4.17.21 confirmed to fix vulnerability. All integration tests pass with updated dependency.',
      output: 'Updated lodash from 4.17.20 to 4.17.21. Verified no breaking changes in dependent code.',
      confidence: 0.98,
      confidenceData: {
        pointEstimate: 0.98,
        lowerBound: 0.95,
        upperBound: 0.99,
        uncertaintySources: [],
      },
      reasoningChain: [
        {
          step: 1,
          description: 'Identified CVE-2024-1234 affecting lodash < 4.17.21',
          confidence: 1.0,
          evidenceSources: ['nvd', 'github_security_advisory'],
        },
        {
          step: 2,
          description: 'Verified package compatibility with updated version',
          confidence: 0.96,
          evidenceSources: ['npm_audit', 'test_suite'],
        },
        {
          step: 3,
          description: 'Applied patch and validated functionality',
          confidence: 0.98,
          evidenceSources: ['integration_tests', 'smoke_tests'],
        },
      ],
      alternatives: [
        {
          id: 'alt-1',
          description: 'Upgrade to patched version',
          score: 0.98,
          chosen: true,
          pros: ['Fixes vulnerability', 'Minimal changes', 'Backward compatible'],
          cons: [],
        },
        {
          id: 'alt-2',
          description: 'Remove lodash dependency entirely',
          score: 0.65,
          chosen: false,
          pros: ['Eliminates future lodash risks'],
          cons: ['Significant code changes', 'Risk of introducing bugs'],
          rejectionReason: 'Disproportionate effort for low-risk patch',
        },
      ],
      selectedAlternativeIndex: 0,
      criteria: ['security', 'stability', 'effort'],
      rationale: 'Direct version upgrade provides maximum security benefit with minimal risk',
      severity: 'critical',
      hasContradiction: false,
      status: 'completed',
    },
    {
      id: 'dec-006',
      timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      agentId: 'coder-agent',
      agentName: 'CoderAgent',
      type: 'code_generation',
      summary: 'Generated user service with error handling',
      title: 'Generated user service module',
      description: 'Created user service module with CRUD operations and comprehensive error handling.',
      input: 'Implement a user service with create, read, update, delete operations including comprehensive error handling.',
      briefReasoning: 'Comprehensive error handling is required for production robustness. Implemented service layer pattern.',
      output: 'class UserService {\n  async createUser(data: UserInput): Promise<User> {\n    // Note: Error handling implemented\n    return this.repository.create(data);\n  }\n}',
      confidence: 0.84,
      confidenceData: {
        pointEstimate: 0.84,
        lowerBound: 0.76,
        upperBound: 0.91,
        uncertaintySources: ['error_handling_completeness'],
      },
      reasoningChain: generateMockReasoningChain('code_generation'),
      alternatives: generateMockAlternatives('code_generation'),
      selectedAlternativeIndex: 0,
      criteria: ['reliability', 'maintainability', 'error_recovery'],
      rationale: 'Service layer pattern with repository abstraction provides clean separation of concerns',
      severity: 'significant',
      hasContradiction: true, // This decision has a contradiction
      status: 'completed',
    },
    {
      id: 'dec-007',
      timestamp: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
      agentId: 'reviewer-agent',
      agentName: 'ReviewerAgent',
      type: 'security_review',
      summary: 'Reviewed input validation in API endpoints',
      title: 'API input validation review',
      description: 'Comprehensive review of input validation patterns across all public API endpoints.',
      input: 'Review all public API endpoints for proper input validation and sanitization.',
      briefReasoning: 'Current input validation covers OWASP Top 10 requirements. Zod schemas provide runtime type checking.',
      output: 'APPROVED: Input validation meets security requirements with Zod schema validation.',
      confidence: 0.89,
      confidenceData: {
        pointEstimate: 0.89,
        lowerBound: 0.82,
        upperBound: 0.95,
        uncertaintySources: ['edge_case_coverage'],
      },
      reasoningChain: generateMockReasoningChain('security_review'),
      alternatives: generateMockAlternatives('security_review'),
      selectedAlternativeIndex: 0,
      criteria: ['security', 'usability', 'performance'],
      rationale: 'Zod schema validation provides type-safe runtime validation with good error messages',
      severity: 'significant',
      hasContradiction: true, // This decision has a contradiction
      status: 'completed',
    },
    {
      id: 'dec-008',
      timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      agentId: 'validator-agent',
      agentName: 'ValidatorAgent',
      type: 'deployment',
      summary: 'Validated blue-green deployment configuration',
      title: 'Blue-green deployment validation',
      description: 'Reviewed and validated blue-green deployment strategy for the payment service.',
      input: 'Validate deployment strategy for payment-service requiring zero-downtime updates.',
      briefReasoning: 'Rolling update recommended for this service profile due to resource constraints.',
      output: 'APPROVED: Blue-green deployment configured with proper health checks and traffic switching.',
      confidence: 0.86,
      confidenceData: {
        pointEstimate: 0.86,
        lowerBound: 0.78,
        upperBound: 0.92,
        uncertaintySources: ['resource_availability'],
      },
      reasoningChain: generateMockReasoningChain('deployment'),
      alternatives: generateMockAlternatives('deployment'),
      selectedAlternativeIndex: 1, // Note: reasoning favored rolling but approved blue-green
      criteria: ['availability', 'resource_efficiency', 'rollback_safety'],
      rationale: 'Blue-green selected for instant rollback capability despite higher resource cost',
      severity: 'critical',
      hasContradiction: false, // Was resolved
      status: 'completed',
    },
    {
      id: 'dec-009',
      timestamp: new Date(Date.now() - 36 * 60 * 60 * 1000).toISOString(),
      agentId: 'coder-agent',
      agentName: 'CoderAgent',
      type: 'code_generation',
      summary: 'Generated rate limiting middleware for API protection',
      title: 'Rate limiting implementation',
      description: 'Implemented sliding window rate limiting with Redis backend for API endpoint protection.',
      input: 'Implement rate limiting for public API endpoints with configurable limits per user tier.',
      briefReasoning: 'Sliding window algorithm provides smooth rate limiting. Redis enables distributed enforcement.',
      output: 'class RateLimiter {\n  constructor(private redis: Redis, private config: RateLimitConfig) {}\n  async checkLimit(key: string): Promise<boolean> { ... }\n}',
      confidence: 0.93,
      confidenceData: {
        pointEstimate: 0.93,
        lowerBound: 0.87,
        upperBound: 0.97,
        uncertaintySources: [],
      },
      reasoningChain: generateMockReasoningChain('code_generation'),
      alternatives: generateMockAlternatives('code_generation'),
      selectedAlternativeIndex: 0,
      criteria: ['scalability', 'accuracy', 'performance'],
      rationale: 'Sliding window with Redis provides accurate distributed rate limiting with low latency',
      severity: 'significant',
      hasContradiction: false,
      status: 'completed',
    },
    {
      id: 'dec-010',
      timestamp: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
      agentId: 'patcher-agent',
      agentName: 'PatcherAgent',
      type: 'security_patch',
      summary: 'Applied security headers configuration update',
      title: 'Security headers update',
      description: 'Updated Content-Security-Policy and added additional security headers for XSS protection.',
      input: 'Update security headers to address CSP bypass vulnerability and add missing headers.',
      briefReasoning: 'Current CSP allows unsafe-inline which can be exploited. Strict CSP with nonce-based scripts recommended.',
      output: 'Updated nginx.conf with strict CSP, X-Content-Type-Options, and Permissions-Policy headers.',
      confidence: 0.96,
      confidenceData: {
        pointEstimate: 0.96,
        lowerBound: 0.91,
        upperBound: 0.99,
        uncertaintySources: [],
      },
      reasoningChain: [
        {
          step: 1,
          description: 'Analyzed current security header configuration',
          confidence: 0.98,
          evidenceSources: ['nginx_config', 'security_audit'],
        },
        {
          step: 2,
          description: 'Identified CSP weaknesses allowing script injection',
          confidence: 0.95,
          evidenceSources: ['csp_evaluator', 'penetration_test_report'],
        },
        {
          step: 3,
          description: 'Applied strict CSP with nonce-based script execution',
          confidence: 0.96,
          evidenceSources: ['mdn_documentation', 'owasp_guidelines'],
        },
      ],
      alternatives: [
        {
          id: 'alt-1',
          description: 'Strict CSP with nonce-based scripts',
          score: 0.96,
          chosen: true,
          pros: ['Maximum XSS protection', 'Industry best practice'],
          cons: ['Requires code changes for inline scripts'],
        },
        {
          id: 'alt-2',
          description: 'Hash-based CSP for existing scripts',
          score: 0.85,
          chosen: false,
          pros: ['No code changes needed'],
          cons: ['Harder to maintain', 'Less flexible'],
          rejectionReason: 'Nonce-based approach more maintainable long-term',
        },
      ],
      selectedAlternativeIndex: 0,
      criteria: ['security', 'maintainability', 'compatibility'],
      rationale: 'Nonce-based CSP provides strongest protection while maintaining developer experience',
      severity: 'significant',
      hasContradiction: false,
      status: 'completed',
    },
  ],
  contradictions: [
    {
      id: 'cont-001',
      detectedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      decisionId: 'dec-006',
      agentId: 'coder-agent',
      agentName: 'CoderAgent',
      severity: 'medium',
      status: 'active',
      title: 'Reasoning-Action Mismatch: Error Handling',
      description:
        'Agent stated "comprehensive error handling required" but generated code lacks try-catch blocks in the createUser and updateUser methods.',
      reasoningStatement: 'Comprehensive error handling is required for production robustness. All service methods should include proper try-catch blocks with specific error types.',
      actualAction: 'Generated UserService class with createUser() and updateUser() methods that directly call repository methods without error handling constructs.',
      discrepancyScore: 0.72,
      suggestedResolution: 'Add try-catch blocks with appropriate error propagation and custom error types (UserNotFoundError, ValidationError, DatabaseError)',
      affectedCode: 'src/services/user-service.ts:45-67',
      impactAssessment: 'Medium - Unhandled database errors could cause 500 responses without proper error messages',
      relatedDecisions: ['dec-004', 'dec-009'],
    },
    {
      id: 'cont-002',
      detectedAt: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      decisionId: 'dec-007',
      agentId: 'reviewer-agent',
      agentName: 'ReviewerAgent',
      severity: 'low',
      status: 'active',
      title: 'Inconsistent Security Assessment Criteria',
      description:
        'Agent approved input validation as sufficient, but flagged similar pattern as XSS risk in a subsequent review of the same codebase.',
      reasoningStatement: 'Current input validation covers OWASP Top 10 requirements. Zod schemas provide runtime type checking and sanitization.',
      actualAction: 'In review dec-012, flagged similar Zod-validated input as potential XSS vector due to lack of output encoding.',
      discrepancyScore: 0.45,
      suggestedResolution: 'Clarify security assessment criteria: input validation prevents injection but output encoding is required for XSS prevention. Both reviews are technically correct but messaging should be consistent.',
      affectedCode: 'src/api/endpoints.py:123-145',
      impactAssessment: 'Low - Both assessments lead to secure code, but inconsistent messaging may confuse developers',
      relatedDecisions: ['dec-002', 'dec-010'],
    },
    {
      id: 'cont-003',
      detectedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      decisionId: 'dec-008',
      agentId: 'validator-agent',
      agentName: 'ValidatorAgent',
      severity: 'high',
      status: 'resolved',
      title: 'Deployment Strategy Contradiction',
      description: 'Reasoning recommended rolling update for resource efficiency, but approved blue-green deployment configuration.',
      reasoningStatement: 'Rolling update recommended for this service profile due to resource constraints in the production cluster. Current capacity cannot support 2x replica count.',
      actualAction: 'Approved blue-green deployment configuration requiring 2x replicas during deployment window.',
      discrepancyScore: 0.85,
      suggestedResolution: 'Either update reasoning to justify blue-green selection (instant rollback requirement) or modify deployment to rolling update strategy.',
      affectedCode: 'deploy/k8s/production.yaml',
      impactAssessment: 'High - Blue-green deployment may fail due to insufficient cluster resources during peak hours',
      relatedDecisions: ['dec-003'],
      resolvedAt: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(),
      resolvedBy: 'devops@aenealabs.com',
      resolution: 'Updated reasoning to clarify: blue-green selected for payment-service specifically due to PCI-DSS requirement for instant rollback capability. Resource constraint addressed by scheduling deployment during low-traffic window.',
    },
    {
      id: 'cont-004',
      detectedAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
      decisionId: 'dec-011',
      agentId: 'coder-agent',
      agentName: 'CoderAgent',
      severity: 'medium',
      status: 'resolved',
      title: 'Logging Strategy Inconsistency',
      description: 'Recommended structured logging but generated console.log statements.',
      reasoningStatement: 'Structured logging with correlation IDs is essential for production observability and debugging distributed systems.',
      actualAction: 'Generated utility functions using console.log() instead of the established logger service with structured format.',
      discrepancyScore: 0.68,
      suggestedResolution: 'Replace console.log statements with logger.info/error calls including correlation context.',
      affectedCode: 'src/utils/helpers.ts:12-34',
      impactAssessment: 'Medium - Console logs not captured by log aggregation, affecting debugging capability',
      relatedDecisions: [],
      resolvedAt: new Date(Date.now() - 44 * 60 * 60 * 1000).toISOString(),
      resolvedBy: 'backend@aenealabs.com',
      resolution: 'Regenerated utility functions with proper logger service integration. Added logging standards to agent context.',
    },
    {
      id: 'cont-005',
      detectedAt: new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString(),
      decisionId: 'dec-012',
      agentId: 'reviewer-agent',
      agentName: 'ReviewerAgent',
      severity: 'low',
      status: 'dismissed',
      title: 'Test Coverage Threshold Variance',
      description: 'Stated 80% coverage required but approved PR with 78% coverage.',
      reasoningStatement: 'Code coverage should meet 80% threshold for production code to ensure adequate testing.',
      actualAction: 'Approved pull request with 78.3% code coverage, below stated threshold.',
      discrepancyScore: 0.32,
      suggestedResolution: 'Either enforce strict 80% threshold or update guidelines to specify acceptable variance.',
      affectedCode: 'src/services/notification-service.ts',
      impactAssessment: 'Low - 1.7% variance is within reasonable tolerance; critical paths are fully covered',
      relatedDecisions: [],
      dismissedAt: new Date(Date.now() - 70 * 60 * 60 * 1000).toISOString(),
      dismissedBy: 'qa@aenealabs.com',
      dismissalReason: 'False positive - 80% is a guideline, not hard requirement. Critical code paths have 100% coverage. PR met intent of the policy.',
    },
  ],
  stats: {
    // Total: 1247 decisions in the system
    totalDecisions: 1247,
    // Weighted average of all decision confidence scores
    avgConfidence: 0.91,
    // Active contradictions (cont-001 and cont-002)
    activeContradictions: 2,
    // Contradictions resolved in last 24 hours
    resolvedToday: 5,
    // Decisions by agent (sum = 1247)
    decisionsByAgent: {
      CoderAgent: 498,      // ~40% - most active agent
      ReviewerAgent: 312,   // ~25% - security reviews
      ValidatorAgent: 249,  // ~20% - deployment validations
      PatcherAgent: 188,    // ~15% - security patches
    },
    // Confidence distribution (sum = 1247)
    confidenceDistribution: {
      high: 873,     // > 0.85 (70%)
      medium: 312,   // 0.70-0.85 (25%)
      low: 62,       // < 0.70 (5%)
    },
    // Contradiction status breakdown
    contradictionsByStatus: {
      active: 2,
      resolved: 23,
      dismissed: 5,
    },
    // Trend data for charts
    trendsLast7Days: {
      decisions: [156, 189, 203, 178, 167, 187, 167], // Daily decision counts
      avgConfidence: [0.89, 0.91, 0.90, 0.92, 0.91, 0.90, 0.91],
      contradictions: [1, 0, 2, 0, 1, 0, 1], // New contradictions per day
    },
    // Performance metrics
    performance: {
      avgDecisionTimeMs: 1247,
      p95DecisionTimeMs: 3421,
      p99DecisionTimeMs: 5892,
    },
  },
};

/**
 * Wrapper to fall back to mock data in development mode
 */
async function withMockFallback(apiCall, mockData, label) {
  try {
    return await apiCall();
  } catch (error) {
    if (IS_DEV) {
      console.warn(`[Explainability] ${label} API unavailable, using mock data:`, error.message);
      return mockData;
    }
    throw error;
  }
}

/**
 * Get decision records with optional filtering
 * @param {Object} [filters] - Filter options
 * @param {string[]} [filters.agents] - Filter by agent IDs
 * @param {string[]} [filters.severities] - Filter by severity levels
 * @param {string} [filters.timeRange] - Time range: '24h', '7d', '30d'
 * @param {number} [filters.limit=50] - Maximum results
 * @param {number} [filters.offset=0] - Pagination offset
 * @returns {Promise<Array>} Decision records
 */
export async function getDecisions(filters = {}) {
  return withMockFallback(
    async () => {
      const params = new URLSearchParams();
      if (filters.agents?.length) params.append('agents', filters.agents.join(','));
      if (filters.severities?.length) params.append('severities', filters.severities.join(','));
      if (filters.timeRange) params.append('time_range', filters.timeRange);
      if (filters.limit) params.append('limit', filters.limit.toString());
      if (filters.offset) params.append('offset', filters.offset.toString());

      const url = `${API_BASE}/api/v1/explainability/decisions${params.toString() ? `?${params}` : ''}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    // Apply client-side filtering to mock data
    (() => {
      let decisions = [...MOCK_DATA.decisions];
      if (filters.agents?.length) {
        decisions = decisions.filter((d) => filters.agents.includes(d.agentId));
      }
      if (filters.severities?.length) {
        decisions = decisions.filter((d) => filters.severities.includes(d.severity));
      }
      return decisions;
    })(),
    'Decisions'
  );
}

/**
 * Get detailed decision by ID
 * @param {string} decisionId - Decision ID
 * @returns {Promise<Object>} Decision detail with full reasoning chain
 */
export async function getDecisionDetail(decisionId) {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/explainability/decisions/${decisionId}`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.decisions.find((d) => d.id === decisionId) || MOCK_DATA.decisions[0],
    'Decision Detail'
  );
}

/**
 * Get contradiction alerts
 * @param {boolean} [includeResolved=false] - Include resolved contradictions
 * @returns {Promise<Array>} Contradiction records
 */
export async function getContradictions(includeResolved = false) {
  return withMockFallback(
    async () => {
      const params = includeResolved ? '?include_resolved=true' : '';
      const response = await fetch(`${API_BASE}/api/v1/explainability/contradictions${params}`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    includeResolved
      ? MOCK_DATA.contradictions
      : MOCK_DATA.contradictions.filter((c) => c.status === 'active'),
    'Contradictions'
  );
}

/**
 * Resolve a contradiction
 * @param {string} contradictionId - Contradiction ID
 * @param {string} resolution - Resolution description
 * @returns {Promise<Object>} Updated contradiction
 */
export async function resolveContradiction(contradictionId, resolution) {
  return withMockFallback(
    async () => {
      const response = await fetch(
        `${API_BASE}/api/v1/explainability/contradictions/${contradictionId}/resolve`,
        {
          method: 'POST',
          headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ resolution }),
        }
      );
      return handleResponse(response);
    },
    {
      ...MOCK_DATA.contradictions.find((c) => c.id === contradictionId),
      status: 'resolved',
      resolvedAt: new Date().toISOString(),
      resolution,
    },
    'Resolve Contradiction'
  );
}

/**
 * Dismiss a contradiction as false positive
 * @param {string} contradictionId - Contradiction ID
 * @param {string} reason - Dismissal reason
 * @returns {Promise<Object>} Updated contradiction
 */
export async function dismissContradiction(contradictionId, reason) {
  return withMockFallback(
    async () => {
      const response = await fetch(
        `${API_BASE}/api/v1/explainability/contradictions/${contradictionId}/dismiss`,
        {
          method: 'POST',
          headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason }),
        }
      );
      return handleResponse(response);
    },
    {
      ...MOCK_DATA.contradictions.find((c) => c.id === contradictionId),
      status: 'dismissed',
      dismissedAt: new Date().toISOString(),
      dismissalReason: reason,
    },
    'Dismiss Contradiction'
  );
}

/**
 * Get dashboard statistics
 * @returns {Promise<Object>} Dashboard statistics
 */
export async function getExplainabilityStats() {
  return withMockFallback(
    async () => {
      const response = await fetch(`${API_BASE}/api/v1/explainability/stats`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      return handleResponse(response);
    },
    MOCK_DATA.stats,
    'Stats'
  );
}

export default {
  getDecisions,
  getDecisionDetail,
  getContradictions,
  resolveContradiction,
  dismissContradiction,
  getExplainabilityStats,
};
